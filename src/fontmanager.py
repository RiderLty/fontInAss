import base64
import json
import sys
import aiohttp
import asyncio
import uharfbuzz
from cachetools import LRUCache, TTLCache
from constants import logger, FONT_DIRS, DEFAULT_FONT_PATH, MAIN_LOOP, FONT_CACHE_SIZE, FONT_CACHE_TTL, ONLINE_FONTS_DB_PATH, LOCAL_FONTS_DB_PATH, POOL_CPU_MAX , DISABLE_ONLINE_FONTS
from utils import get_all_files, get_font_info, save_to_disk, select_font_fromlist
from sqlalchemy import Column, Integer, String, Boolean, TypeDecorator, create_engine, ForeignKey, event, update, bindparam, delete, select, or_, JSON
from sqlalchemy.dialects.sqlite import insert  # 2.0新特性批量插入
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import declarative_base, sessionmaker

# from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict
import os
import time
from tqdm import tqdm

# 声明基类
Base = declarative_base()
# 创建 SQLAlchemy 引擎和会话
engine = create_engine(
    f"sqlite:///{LOCAL_FONTS_DB_PATH}",
    json_serializer=lambda x: json.dumps(x, ensure_ascii=False),
)
Session = sessionmaker(bind=engine)


# 启用 SQLite 外键支持
@event.listens_for(engine, "connect")
def enable_foreign_keys(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

class PathBase64(TypeDecorator):
    impl = String
    def process_bind_param(self, value, dialect):
        if value:
            raw_bytes = os.fsencode(value) if isinstance(value, str) else value
            return base64.b64encode(raw_bytes).decode("utf-8")
        return None

    def process_result_value(self, value, dialect):
        if value:
            raw_bytes = base64.b64decode(value.encode("utf-8"))
            return os.fsdecode(raw_bytes)
        return None


class FileInfo(Base):
    __tablename__ = "file_info"
    path = Column(PathBase64(), index=True, primary_key=True, nullable=False)  # 唯一的文件路径
    size = Column(Integer, nullable=False)


class FontInfo(Base):
    __tablename__ = "font_info"
    uid = Column(String, index=True, primary_key=True, nullable=False)  # 字体信息关联 在获取信息时候使用uuid生成
    path = Column(PathBase64(), ForeignKey("file_info.path", ondelete="CASCADE", onupdate="CASCADE"), index=True, nullable=False)
    size = Column(Integer, nullable=False)
    index = Column(Integer)
    familyName = Column(JSON)
    fullName = Column(JSON)
    postscriptName = Column(JSON)
    postscriptCheck = Column(Boolean)
    weight = Column(Integer)
    bold = Column(Boolean)
    italic = Column(Boolean)


class FontName(Base):
    # 不推荐用name名字， 可能是数据库中的保留关键字
    __tablename__ = "name"
    # id = Column(Integer, index=True, primary_key=True, autoincrement=True)
    name = Column(String, primary_key=True, index=True)
    uid = Column(String, ForeignKey("font_info.uid", ondelete="CASCADE", onupdate="CASCADE"), primary_key=True, index=True, nullable=False)

# 数据库管理类
class FontManager:
    def __init__(self):
        self.cache = TTLCache(maxsize=FONT_CACHE_SIZE, ttl=FONT_CACHE_TTL) if FONT_CACHE_TTL > 0 else LRUCache(maxsize=FONT_CACHE_SIZE)

        with open(ONLINE_FONTS_DB_PATH, "r", encoding="UTF-8") as f:
            (self.onlineMapIndex, self.onlineMapData) = json.load(f)
        self.http_session = aiohttp.ClientSession(loop=MAIN_LOOP, connector=aiohttp.TCPConnector(verify_ssl=False, loop=MAIN_LOOP))  # 下载的session
        # self.executor = ThreadPoolExecutor(max_workers=POOL_CPU_MAX * 2)
        # 初始化数据库
        Base.metadata.create_all(engine)
        self.db_session = Session()
        # 同步目录
        self.sync_db_with_dir()
        # self.make_online_map()

    def sync_db_with_dir(self):
        try:
            logger.info("开始检查数据库与目录的一致性...")
            # 从数据库获取所有记录
            stmt = select(FileInfo.path, FileInfo.size)
            result = self.db_session.execute(stmt).all()
            db_files = {row.path: row.size for row in result}
            # 获取目录中的所有字体文件
            fonts_files = {}
            for dir_path in FONT_DIRS:
                files = get_all_files(dir_path)
                for file_path in files:
                    fonts_files[file_path] = os.path.getsize(file_path)

            # 计算差异
            ins_files = set(fonts_files.keys()) - set(db_files.keys())
            del_files = set(db_files.keys()) - set(fonts_files.keys())
            update_files = {file_path for file_path in fonts_files if file_path in db_files and fonts_files[file_path] != db_files[file_path]}

            # 将更新的文件同时加入删除和新增
            del_files.update(update_files)
            ins_files.update(update_files)

            # 执行对应操作
            if del_files:
                self.del_fileinfo_with_filepath(list(del_files))
            if ins_files:
                self.ins_fileinfo_and_fontinfo(list(ins_files))

        except Exception as e:
            logger.exception("检查数据库一致性时发生错误")
            raise

    def update_fileinfo_with_filepath(self, data: List[Dict[str, str]]):
        # print("更新:",data)
        try:
            start = time.perf_counter_ns()
            stmt = update(FileInfo).where(FileInfo.path == bindparam("old")).values(path=bindparam("new")).execution_options(synchronize_session=None)
            self.db_session.connection().execute(stmt, data)
            self.db_session.commit()
            logger.info(f"更新了 {len(data)} 条记录，耗时 {(time.perf_counter_ns() - start) / 1_000_000:.2f}ms")
        except SQLAlchemyError as e:
            self.db_session.rollback()  # 回滚事务
            logger.exception("更新数据时发生错误")
            raise

    def ins_fileinfo_and_fontinfo(self, data: List[str]):
        # print("插入:",data)
        try:
            start = time.perf_counter_ns()
            file_info = []
            font_info = []
            font_name = []
            with tqdm(
                total=len(data),
                desc="Load",
                unit=" font",
                bar_format="{l_bar}{bar} {n_fmt}/{total_fmt} | {rate_fmt} | {remaining}\n",
                file=sys.stdout,
                miniters=len(data) // 100,
                dynamic_ncols=False,
                mininterval=3,
                maxinterval=10,
                position=0,
            ) as pbar:
                for file in data:
                    file_info_list, font_info_list, font_name_list = get_font_info(file)
                    file_info.extend(file_info_list)
                    font_info.extend(font_info_list)
                    font_name.extend(font_name_list)
                    pbar.update(1)
            logger.info(f"分析了 {len(data)} 个字体，耗时 {(time.perf_counter_ns() - start) / 1_000_000:.2f}ms")
            start = time.perf_counter_ns()
            if file_info:
                self.db_session.execute(insert(FileInfo).on_conflict_do_nothing(), file_info)
            if font_info:
                self.db_session.execute(insert(FontInfo).on_conflict_do_nothing(), font_info)
            if font_name:
                self.db_session.execute(insert(FontName).on_conflict_do_nothing(), font_name)
            self.db_session.commit()
            logger.info(f"添加记录，耗时 {(time.perf_counter_ns() - start) / 1_000_000:.2f}ms")
        except SQLAlchemyError as e:
            self.db_session.rollback()  # 回滚事务
            logger.exception("添加数据时发生错误")
            raise

    def del_fileinfo_with_filepath(self, data: List[str]):
        # print("删除:",data)
        try:
            start = time.perf_counter_ns()
            stmt = delete(FileInfo).where(FileInfo.path.in_(data))
            self.db_session.execute(stmt)
            self.db_session.commit()
            logger.info(f"删除了 {len(data)} 条记录，耗时 {(time.perf_counter_ns() - start) / 1_000_000:.2f}ms")
        except SQLAlchemyError as e:
            self.db_session.rollback()  # 回滚事务
            logger.exception("删除数据时发生错误")
            raise

    def make_online_map(self):
        """
        创建在线列表，需要确保本地与在线文件格式一致
        """
        result = (
            self.db_session.execute(
                select(
                    FontInfo.path,
                    FontInfo.size,
                    FontInfo.index,
                    FontInfo.familyName,
                    FontInfo.postscriptName,
                    FontInfo.postscriptCheck,
                    FontInfo.fullName,
                    FontInfo.weight,
                    FontInfo.bold,
                    FontInfo.italic,
                )
            )
            .mappings()
            .all()
        )

        name_index_map = {}
        for index, fontInfo in enumerate(result):
            for names in [fontInfo.familyName, fontInfo.postscriptName, fontInfo.fullName]:
                for name in names:
                    name_index_map.setdefault(name, set()).add(index)

        name_index_dict = {}
        for name, indexSet in name_index_map.items():
            name_index_dict[name] = list(indexSet)

        font_list = []
        for row in result:
            rec = dict(row)
            rec["path"] = rec["path"][30:]
            font_list.append(rec)

        with open("onlineFonts.json", "w", encoding="UTF-8") as f:
            json.dump([name_index_dict, font_list], f, ensure_ascii=True)
        print("onlineFonts.json 已写入")

    def select_font_online(self, target_font_name, target_weight, target_italic):
        if target_font_name in self.onlineMapIndex:
            font_list = [self.onlineMapData[index] for index in self.onlineMapIndex[target_font_name]]
            path, index = select_font_fromlist(target_font_name, target_weight, target_italic, font_list)
            return path, index
        return None

    def select_font_local(self, target_font_name, target_weight, target_italic):
        result = (
            self.db_session.execute(
                select(
                    FontInfo.path,
                    FontInfo.size,
                    FontInfo.index,
                    FontInfo.familyName,
                    FontInfo.postscriptName,
                    FontInfo.postscriptCheck,
                    FontInfo.fullName,
                    FontInfo.weight,
                    FontInfo.bold,
                    FontInfo.italic,
                )
                .join(FontName, FontInfo.uid == FontName.uid)
                .where(
                    FontName.name == target_font_name,
                )
            )
            .mappings()
            .all()
        )
        return select_font_fromlist(target_font_name, target_weight, target_italic, result)

    def close(self):
        try:
            # self.executor.shutdown(wait=True)
            self.db_session.close()
            engine.dispose()
            MAIN_LOOP.create_task(self.http_session.close())
        except Exception as e:
            logger.exception("关闭数据库连接发生错误")

    async def load_font(self, target_font_name, target_weight, target_italic):
        db_font_name = target_font_name.strip().lower()
        if (db_font_name, target_weight, target_italic) in self.cache:
            (font_bytes, index) = self.cache[(db_font_name, target_weight, target_italic)]  # 刷新缓存
            self.cache[(db_font_name, target_weight, target_italic)] = (font_bytes, index)
            logger.info(f"已缓存 {len(font_bytes) / (1024 * 1024):.2f}MB \t\t[{(db_font_name, target_weight, target_italic)} <== <cache> ]")
            return font_bytes, index
        elif result := self.select_font_local(db_font_name, target_weight, target_italic):
            path, index = result
            start = time.perf_counter_ns()
            font_bytes = uharfbuzz.Blob.from_file_path(path)
            logger.info(f"本地 {len(font_bytes) / (1024 * 1024):.2f}MB {(time.perf_counter_ns() - start) / 1000000:.2f}ms \t[{(db_font_name, target_weight, target_italic)} <== {path}]")
            self.cache[(db_font_name, target_weight, target_italic)] = (font_bytes, index)
            return font_bytes, index
        else:
            if DISABLE_ONLINE_FONTS:
                logger.info(f"已禁用在线字体下载 [{(target_font_name, target_weight, target_italic)}]")
                return None, None
            elif result := self.select_font_online(db_font_name, target_weight, target_italic):
                path, index = result
                logger.info(f"下载字体 [CDN:{path}]")
                start = time.perf_counter_ns()
                resp = await self.http_session.get(f"https://vip.123pan.cn/1833788059/direct/超级字体整合包 XZ/{path}", timeout=10)
                if not resp.ok:
                    resp = await self.http_session.get(f"https://fonts.storage.rd5isto.org/超级字体整合包 XZ/{path}", timeout=10)
                font_bytes = await resp.read()
                logger.info(f"下载 {len(font_bytes) / (1024 * 1024):.2f}MB {(time.perf_counter_ns() - start) / 1000000:.2f}ms \t[{(db_font_name, target_weight, target_italic)} <== CDN:{path}]")
                self.cache[(db_font_name, target_weight, target_italic)] = (font_bytes, index)
                save_path = os.path.join(os.path.join(DEFAULT_FONT_PATH, "download"), f"超级字体整合包 XZ/{path}")
                save_dir = os.path.dirname(save_path)
                os.makedirs(save_dir, exist_ok=True)
                asyncio.create_task(save_to_disk(save_path, font_bytes))
                return font_bytes, index
            else:
                return None, None

    async def select_font(self, target_font_name, target_weight, target_italic):
        db_font_name = target_font_name.strip().lower()
        if (
            (db_font_name, target_weight, target_italic) in self.cache
            or self.select_font_local(db_font_name, target_weight, target_italic)
            or self.select_font_online(db_font_name, target_weight, target_italic)
        ):
            return True, None
        return False, f"[{target_font_name}]"