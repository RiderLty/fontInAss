import json
import aiohttp
import asyncio
import aiofiles
from cachetools import LRUCache, TTLCache
from constants import logger, FONT_DIRS, DEFAULT_FONT_PATH, MAIN_LOOP, FONT_CACHE_SIZE, FONT_CACHE_TTL, \
    ONLINE_FONTS_PATH, LOCAL_FONTS_DB, POOL_CPU_MAX
from utils import getAllFiles, saveToDisk, conv2unicodee, makeMiniSizeFontMap
from sqlalchemy import Column, Integer, String, create_engine, ForeignKey, Index, event, update, bindparam, delete, select
from sqlalchemy.dialects.sqlite import insert  #2.0新特性批量插入
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from fontTools.ttLib import TTCollection, TTFont
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict
import os
import time
from io import BytesIO

# 声明基类
Base = declarative_base()
# 创建 SQLAlchemy 引擎和会话
engine = create_engine(f"sqlite:///{LOCAL_FONTS_DB}")
Session = sessionmaker(bind=engine)

# 启用 SQLite 外键支持
@event.listens_for(engine, "connect")
def enable_foreign_keys(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

# 数据库实体类
class FontInfo(Base):
    __tablename__ = "font_info"
    file_path = Column(String, primary_key=True, nullable=False)  # 唯一的文件路径
    file_size = Column(Integer)
    file_mtime = Column(Integer)
    font_count = Column(Integer)
    details = relationship("FontDetail", cascade="all, delete-orphan")

    __table_args__ = (Index("idx_font_info_file_path", "file_path"),)

class FontDetail(Base):
    __tablename__ = "font_detail"
    id = Column(Integer, primary_key=True, autoincrement=True)
    file_path = Column(String, ForeignKey("font_info.file_path", ondelete="CASCADE", onupdate="CASCADE"))
    family_name = Column(String)
    family_index = Column(Integer)

    __table_args__ = (Index("idx_font_detail_file_path", "file_path"),Index("idx_font_detail_family_name", "family_name"))

# 数据库管理类
class fontManager:
    def __init__(self):
        self.cache = TTLCache(maxsize=FONT_CACHE_SIZE, ttl=FONT_CACHE_TTL) if FONT_CACHE_TTL > 0 else LRUCache(maxsize=FONT_CACHE_SIZE)
        with open(ONLINE_FONTS_PATH, "r", encoding="UTF-8") as f:
            self.onlineMap = makeMiniSizeFontMap(json.load(f))  # 在线字体map
        self.http_session = aiohttp.ClientSession(loop=MAIN_LOOP)  # 下载的session

        self.executor = ThreadPoolExecutor(max_workers=POOL_CPU_MAX * 2)
        # 初始化数据库
        Base.metadata.create_all(engine)
        self.db_session = Session()
        # 同步目录
        self.sync_db_with_dir()

    def sync_db_with_dir(self):
        try:
            logger.info("开始检查数据库与目录的一致性...")

            # 从数据库获取所有记录
            stmt = select(FontInfo.file_path, FontInfo.file_size)
            result = self.db_session.execute(stmt).all()
            # 转换为字典
            db_files = {row.file_path: row.file_size for row in result}

            # 获取目录中的所有字体文件
            fontdir_files = {}
            for dir_path in FONT_DIRS:
                files = getAllFiles(dir_path)
                for file_path in files:
                    fontdir_files[file_path] = os.path.getsize(file_path)

            # 计算差异
            ins_files = set(fontdir_files.keys()) - set(db_files.keys())
            del_files = set(db_files.keys()) - set(fontdir_files.keys())
            update_files = {
                file_path for file_path in fontdir_files
                if file_path in db_files and fontdir_files[file_path] != db_files[file_path]
            }

            # 将更新的文件同时加入删除和新增
            del_files.update(update_files)
            ins_files.update(update_files)

            # 执行对应操作
            if del_files:
                self.del_fontinfo_with_filepath(list(del_files))
            if ins_files:
                self.ins_fontinfo_and_fontdetail(list(ins_files))

        except Exception as e:
            logger.error(f"检查数据库一致性时发生错误: {e}")
            raise

    def ins_fontinfo_and_fontdetail(self, data: List[str]):
        '''
        data 结构为 [x,y,]
        font_info_list与font_detail_list 结构为 [{x:x,y:y},...]
        '''
        try:
            start = time.perf_counter_ns()
            #这里使用线程池比进程池速度更快
            results = self.executor.map(self.gen_font_info, data)
            # logger.info(f"处理新增字体信息耗时 {(time.perf_counter_ns() - start) / 1_000_000:.2f}ms")
            font_info_list = []
            font_detail_list = []
            for font_info, font_details in results:
                font_info_list.extend(font_info)
                font_detail_list.extend(font_details)
            # 批量插入 FontInfo 和 FontDetail
            self.db_session.execute(insert(FontInfo), font_info_list)
            self.db_session.execute(insert(FontDetail), font_detail_list)
            self.db_session.commit()
            logger.info(f"新增了 {len(data)} 条记录，耗时 {(time.perf_counter_ns() - start) / 1_000_000:.2f}ms")
        except SQLAlchemyError as e:
            self.db_session.rollback()  # 回滚事务
            logger.error(f"更新数据时发生错误: {e}")
            raise

    def update_fontinfo_with_filepath(self, data: List[Dict[str, str]]):
        '''
        data 结构为 [{x:x,y:y},...]
        stmt_data 结构为 [{x:x,y:y},...]
        '''
        try:
            start = time.perf_counter_ns()
            # stmt_data = [{"file_path": src,"new_file_path": dest, } for src, dest in data]
            stmt = update(FontInfo).where(FontInfo.file_path == bindparam("file_path")).values(
                file_path=bindparam("new_file_path")).execution_options(synchronize_session=None)
            self.db_session.connection().execute(stmt, data)
            self.db_session.commit()
            logger.info(f"更新了 {len(data)} 条记录，耗时 {(time.perf_counter_ns() - start) / 1_000_000:.2f}ms")
        except SQLAlchemyError as e:
            self.db_session.rollback()  # 回滚事务
            logger.error(f"更新数据时发生错误: {e}")
            raise

    def del_fontinfo_with_filepath(self, data: List[str]):
        '''
        data 结构为 [x,y,]
        '''
        try:
            start = time.perf_counter_ns()
            stmt = delete(FontInfo).where(FontInfo.file_path.in_(data))
            self.db_session.execute(stmt)
            self.db_session.commit()
            logger.info(f"删除了 {len(data)} 条记录，耗时 {(time.perf_counter_ns() - start) / 1_000_000:.2f}ms")
        except SQLAlchemyError as e:
            self.db_session.rollback()  # 回滚事务
            logger.error(f"更新数据时发生错误: {e}")
            raise

    def get_fontinfo_by_familyname(self, family_name: str):
        try:
            # start = time.perf_counter_ns()
            stmt = select(FontDetail.file_path, FontDetail.family_index).where(
                FontDetail.family_name == family_name
            )
            # 返回第一条
            result = self.db_session.execute(stmt).first()
            # 返回全部
            # result = self.db_session.execute(stmt).all()
            # logger.info(f"{family_name} 查询耗时{(time.perf_counter_ns() - start) / 1000000:.2f}ms")
            return result
        except Exception as e:
            logger.error(f"查询字体信息时出错: {e}")
            return None

    def gen_font_info(self, file_path):
        with open(file_path, "rb") as f:
            data = f.read()
        sfntVersion = data[:4]
        fonts = TTCollection(BytesIO(data)).fonts if sfntVersion == b"ttcf" else [TTFont(BytesIO(data))]
        file_size = os.path.getsize(file_path)
        file_mtime = int(os.path.getmtime(file_path))
        font_count = len(fonts)
        # 直接构造 font_info_list 和 font_detail_list
        font_info_list = [{
            "file_path": file_path,
            "file_size": file_size,
            "file_mtime": file_mtime,
            "font_count": font_count
        }]
        font_detail_list = []
        for index, font in enumerate(fonts):
            family = []
            for record in font["name"].names:
                if record.nameID == 1:
                    fontName = str(record).strip()
                    family_name = conv2unicodee(fontName)
                    if family_name not in family:
                        family.append(family_name)
                        font_detail_list.append({
                            "file_path": file_path,
                            "family_name": family_name,
                            "family_index": index
                        })
        return font_info_list, font_detail_list

    def close(self):
        """关闭线程池"""
        try:
            self.executor.shutdown(wait=True)
        except Exception as e:
            logger.error(f"关闭线程池时发生错误: {e}")
        finally:
            MAIN_LOOP.create_task(self.http_session.close())
            self.db_session.close()
            self.db_session.remove()
            engine.dispose()

    async def loadFont(self, fontName):
        """提供字体名称，返回bytes与index"""
        if fontName in self.cache:
            (fontBytes, index) = self.cache[fontName]  # 刷新缓存
            self.cache[fontName] = (fontBytes, index)
            logger.info(f"已缓存 {len(fontBytes) / (1024 * 1024):.2f}MB \t\t[{fontName}]")
            return (fontBytes, index)

        # if fontName in res:
        if (res := self.get_fontinfo_by_familyname(fontName)):
            path, index = res
            start = time.perf_counter_ns()
            async with aiofiles.open(path, "rb") as f:
                fontBytes = await f.read()
                logger.info(f"本地 {len(fontBytes) / (1024 * 1024):.2f}MB {(time.perf_counter_ns() - start) / 1000000:.2f}ms \t[{fontName} <== {path}]")
                self.cache[fontName] = (fontBytes, index)
                return (fontBytes, index)

        if fontName in self.onlineMap:
            (url, index) = self.onlineMap[fontName]
            logger.info(f"从网络下载字体\t\t[{fontName} <== https://fonts.storage.rd5isto.org{url}]")
            start = time.perf_counter_ns()
            resp = await self.http_session.get(f"https://fonts.storage.rd5isto.org{url}", timeout=10)
            fontBytes = await resp.read()
            logger.info(f"下载 {len(fontBytes) / (1024 * 1024):.2f}MB in {(time.perf_counter_ns() - start) / 1000000000:.2f}s\t[{fontName} <== https://fonts.storage.rd5isto.org{url}]")
            self.cache[fontName] = (fontBytes, index)
            fontSavePath = os.path.join(os.path.join(DEFAULT_FONT_PATH, "download"), url.lstrip("/"))
            fontSaveDir = os.path.dirname(fontSavePath)
            os.makedirs(fontSaveDir, exist_ok=True)
            asyncio.run_coroutine_threadsafe(saveToDisk(fontSavePath, fontBytes), MAIN_LOOP)
            return (fontBytes, index)

        return None, None