import json
import sys
import aiohttp
import asyncio
import aiofiles
from cachetools import LRUCache, TTLCache
from constants import logger, FONT_DIRS, DEFAULT_FONT_PATH, MAIN_LOOP, FONT_CACHE_SIZE, FONT_CACHE_TTL, ONLINE_FONTS_DB_PATH, LOCAL_FONTS_DB_PATH, POOL_CPU_MAX
from utils import getAllFiles, getFontFileInfos, saveToDisk,  selectFontFromList
from sqlalchemy import Column, Integer, String, Boolean, and_, create_engine, ForeignKey, Index, event, update, bindparam, delete, select
from sqlalchemy.dialects.sqlite import insert  # 2.0新特性批量插入
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict
import os
import time
from io import BytesIO
from tqdm import tqdm

# 声明基类
Base = declarative_base()
# 创建 SQLAlchemy 引擎和会话
engine = create_engine(f"sqlite:///{LOCAL_FONTS_DB_PATH}")
Session = sessionmaker(bind=engine)


# 启用 SQLite 外键支持
@event.listens_for(engine, "connect")
def enable_foreign_keys(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


class FileInfo(Base):
    __tablename__ = "file_info"
    path = Column(String, primary_key=True, nullable=False)  # 唯一的文件路径
    size = Column(Integer, nullable=False)
    font_info = relationship("FontInfo", cascade="all, delete-orphan")
    family_names = relationship("familyName", cascade="all, delete-orphan")
    full_names = relationship("fullName", cascade="all, delete-orphan")
    postscript_names = relationship("postscriptName", cascade="all, delete-orphan")

    # FontInfo = relationship("FontInfo", cascade="all, delete-orphan")
    # __table_args__ = (Index("idx_font_info_file_path", "file_path"),)


class FontInfo(Base):
    __tablename__ = "font_info"
    path = Column(String, ForeignKey("file_info.path", ondelete="CASCADE", onupdate="CASCADE"), primary_key=True, nullable=False)
    size = Column(Integer)
    index = Column(Integer, primary_key=True, nullable=False)
    postscriptCheck = Column(Boolean)
    weight = Column(Integer)
    bold = Column(Boolean)
    italic = Column(Boolean)
    # __table_args__ = (Index("idx_font_detail_file_path", "file_path"), Index("idx_font_detail_family_name", "family_name"))


class Name(Base):
    __tablename__ = "name"
    name = Column(String, primary_key=True, nullable=False)


class familyName(Base):
    __tablename__ = "family_name"
    name = Column(String, ForeignKey("name.name"), primary_key=True, nullable=False)
    path = Column(String, ForeignKey("file_info.path", ondelete="CASCADE", onupdate="CASCADE"), primary_key=True, nullable=False)
    index = Column(Integer, primary_key=True, nullable=False)


class fullName(Base):
    __tablename__ = "full_name"
    name = Column(String, ForeignKey("name.name"), primary_key=True, nullable=False)
    path = Column(String, ForeignKey("file_info.path", ondelete="CASCADE", onupdate="CASCADE"), primary_key=True, nullable=False)
    index = Column(Integer, primary_key=True, nullable=False)


class postscriptName(Base):
    __tablename__ = "postscript_name"
    name = Column(String, ForeignKey("name.name"), primary_key=True, nullable=False)
    path = Column(String, ForeignKey("file_info.path", ondelete="CASCADE", onupdate="CASCADE"), primary_key=True, nullable=False)
    index = Column(Integer, primary_key=True, nullable=False)


# 数据库管理类
class fontManager:
    def __init__(self):
        self.cache = TTLCache(maxsize=FONT_CACHE_SIZE, ttl=FONT_CACHE_TTL) if FONT_CACHE_TTL > 0 else LRUCache(maxsize=FONT_CACHE_SIZE)

        with open(ONLINE_FONTS_DB_PATH, "r", encoding="UTF-8") as f:
            (self.onlineMapIndex, self.onlineMapData) = json.load(f)
        self.http_session = aiohttp.ClientSession(loop=MAIN_LOOP , connector=aiohttp.TCPConnector(verify_ssl=False , loop=MAIN_LOOP))  # 下载的session
        self.executor = ThreadPoolExecutor(max_workers=POOL_CPU_MAX * 2)
        # 初始化数据库
        Base.metadata.create_all(engine)
        self.db_session = Session()
        # 同步目录
        self.sync_db_with_dir()
        # self.makeOnlineMap()

    def sync_db_with_dir(self):
        try:
            logger.info("开始检查数据库与目录的一致性...")
            # 从数据库获取所有记录
            stmt = select(FileInfo.path, FileInfo.size)
            result = self.db_session.execute(stmt).all()
            db_files = {row.path: row.size for row in result}
            # 获取目录中的所有字体文件
            fontdir_files = {}
            for dir_path in FONT_DIRS:
                files = getAllFiles(dir_path)
                for file_path in files:
                    fontdir_files[file_path] = os.path.getsize(file_path)

            # 计算差异
            ins_files = set(fontdir_files.keys()) - set(db_files.keys())
            del_files = set(db_files.keys()) - set(fontdir_files.keys())
            update_files = {file_path for file_path in fontdir_files if file_path in db_files and fontdir_files[file_path] != db_files[file_path]}

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

    def update_fontinfo_with_filepath(self, data: List[Dict[str, str]]):
        # print("更新:",data)
        try:
            start = time.perf_counter_ns()
            stmt = update(FileInfo).where(FileInfo.path == bindparam("file_path")).values(path=bindparam("new_file_path")).execution_options(synchronize_session=None)
            self.db_session.connection().execute(stmt, data)
            self.db_session.commit()
            logger.info(f"更新了 {len(data)} 条记录，耗时 {(time.perf_counter_ns() - start) / 1_000_000:.2f}ms")
        except SQLAlchemyError as e:
            self.db_session.rollback()  # 回滚事务
            logger.error(f"更新数据时发生错误: {e}")
            raise e

    def ins_fontinfo_and_fontdetail(self, data: List[str]):
        # print("插入:",data)
        try:
            start = time.perf_counter_ns()
            fontInfos = []
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
                    fontInfos.extend(getFontFileInfos(file))
                    pbar.update(1)
            logger.info(f"分析了 {len(data)} 个字体，耗时 {(time.perf_counter_ns() - start) / 1_000_000:.2f}ms")
            insertStart = time.perf_counter_ns()
            self.insertFontInfos(fontInfos)
            self.db_session.commit()
            logger.info(f"添加记录，耗时 {(time.perf_counter_ns() - insertStart) / 1_000_000:.2f}ms")
        except SQLAlchemyError as e:
            self.db_session.rollback()  # 回滚事务
            logger.error(f"添加数据时发生错误: {e}")
            raise e

    def del_fontinfo_with_filepath(self, data: List[str]):
        # print("删除:",data)
        try:
            start = time.perf_counter_ns()
            stmt = delete(FileInfo).where(FileInfo.path.in_(data))
            self.db_session.execute(stmt)
            self.db_session.commit()
            logger.info(f"删除了 {len(data)} 条记录，耗时 {(time.perf_counter_ns() - start) / 1_000_000:.2f}ms")
        except SQLAlchemyError as e:
            self.db_session.rollback()  # 回滚事务
            logger.error(f"删除数据时发生错误: {e}")
            raise e

    def makeOnlineMap(self):
        """
        创建在线列表，需要确保本地与在线文件格式一致
        """
        familyNameResult = self.db_session.execute((select(familyName.name, familyName.path, familyName.index))).all()
        fullNameResult = self.db_session.execute((select(fullName.name, fullName.path, fullName.index))).all()
        postscriptNameResult = self.db_session.execute((select(postscriptName.name, postscriptName.path, postscriptName.index))).all()
        toSelectFonts = {}
        toSelectFontsList = []
        toSelectFontsListIndex = 0
        for result in [familyNameResult, fullNameResult, postscriptNameResult]:
            for name, path, index in result:
                if (path, index) in toSelectFonts:
                    continue
                size, postscriptCheck, weight, bold, italic = self.queryFontInfo(path, index)
                toSelectFontsList.append(
                    {
                        "path": path[30:],  # 截取掉前面的路径
                        "size": size,
                        "index": index,
                        "family": [],
                        "postscriptName": [],
                        "postscriptCheck": postscriptCheck,
                        "fullName": [],
                        "weight": weight,
                        "bold": bold,
                        "italic": italic,
                    }
                )
                toSelectFonts[(path, index)] = toSelectFontsListIndex
                toSelectFontsListIndex += 1

        for name, path, index in familyNameResult:
            toSelectFontsList[toSelectFonts[(path, index)]]["family"].append(name)
        for name, path, index in fullNameResult:
            toSelectFontsList[toSelectFonts[(path, index)]]["postscriptName"].append(name)
        for name, path, index in postscriptNameResult:
            toSelectFontsList[toSelectFonts[(path, index)]]["fullName"].append(name)

        nameMapPathIndex = {}
        for result in [familyNameResult, fullNameResult, postscriptNameResult]:
            for name, path, index in result:
                nameMapPathIndex.setdefault(name, set()).add((path, index))
        nameMapDetail = {}
        for name, indexSet in nameMapPathIndex.items():
            nameMapDetail[name] = [toSelectFonts[x] for x in indexSet]

        with open("onlineFonts.json", "w", encoding="UTF-8") as f:
            json.dump([nameMapDetail, toSelectFontsList], f, ensure_ascii=True)
        print("onlineFonts.json 已写入")

    def selectFontOnline(self, targetFontName, targetWeight, targetItalic):
        if targetFontName in self.onlineMapIndex:
            toSelectFonts = [self.onlineMapData[index] for index in self.onlineMapIndex[targetFontName]]
            (path, index) = selectFontFromList(targetFontName, targetWeight, targetItalic, toSelectFonts)
            return path, index
        return None

    def selectFontLocal(self, targetFontName, targetWeight, targetItalic):
        familyNameResult = self.db_session.execute((select(familyName.path, familyName.index).where(familyName.name == targetFontName))).all()
        fullNameResult = self.db_session.execute((select(fullName.path, fullName.index).where(fullName.name == targetFontName))).all()
        postscriptNameResult = self.db_session.execute((select(postscriptName.path, postscriptName.index).where(postscriptName.name == targetFontName))).all()
        toSelectFonts = {}
        for result in [familyNameResult, fullNameResult, postscriptNameResult]:
            for path, index in result:
                size, postscriptCheck, weight, bold, italic = self.queryFontInfo(path, index)
                toSelectFonts[(path, index)] = {
                    "path": path,
                    "size": size,
                    "index": index,
                    "family": [],
                    "postscriptName": [],
                    "postscriptCheck": postscriptCheck,
                    "fullName": [],
                    "weight": weight,
                    "bold": bold,
                    "italic": italic,
                }
        for path, index in familyNameResult:
            toSelectFonts[(path, index)]["family"].append(targetFontName)
        for path, index in fullNameResult:
            toSelectFonts[(path, index)]["postscriptName"].append(targetFontName)
        for path, index in postscriptNameResult:
            toSelectFonts[(path, index)]["fullName"].append(targetFontName)
        # print(json.dumps(list(toSelectFonts.values()) , indent= 4 , ensure_ascii= False))
        return selectFontFromList(targetFontName, targetWeight, targetItalic, toSelectFonts.values())

    

    def queryFontInfo(self, path, index):
        return self.db_session.execute(
            (select(FontInfo.size, FontInfo.postscriptCheck, FontInfo.weight, FontInfo.bold, FontInfo.italic).where(and_(FontInfo.path == path, FontInfo.index == index)))
        ).first()


    def insertFontInfos(self, fontInfos):
        file_info_list = {}
        font_info_list = []
        name_list = {}
        family_name_list = []
        full_name_list = []
        postscript_name_list = []
        for info in fontInfos:
            file_info_list[info["path"]] = {
                "path": info["path"],
                "size": info["size"],
            }
            font_info_list.append(
                {
                    "path": info["path"],
                    "size": info["size"],
                    "index": info["index"],
                    "postscriptCheck": info["postscriptCheck"],
                    "weight": info["weight"],
                    "bold": info["bold"],
                    "italic": info["italic"],
                }
            )
            for name in info["family"]:
                name_list[name] = {"name": name}
                family_name_list.append(
                    {
                        "name": name,
                        "path": info["path"],
                        "index": info["index"],
                    }
                )

            for name in info["fullName"]:
                name_list[name] = {"name": name}
                full_name_list.append(
                    {
                        "name": name,
                        "path": info["path"],
                        "index": info["index"],
                    }
                )

            for name in info["postscriptName"]:
                name_list[name] = {"name": name}
                postscript_name_list.append(
                    {
                        "name": name,
                        "path": info["path"],
                        "index": info["index"],
                    }
                )

        # print(json.dumps(list(file_info_list.values()), indent=4, ensure_ascii=False))
        # print(json.dumps(list(list(name_list.values())), indent=4, ensure_ascii=False))
        # print(json.dumps(list(font_info_list), indent=4, ensure_ascii=False))
        # print(json.dumps(list(family_name_list), indent=4, ensure_ascii=False))
        # print(json.dumps(list(full_name_list), indent=4, ensure_ascii=False))
        # print(json.dumps(list(postscript_name_list), indent=4, ensure_ascii=False))

        self.db_session.execute(insert(FileInfo).values(list(file_info_list.values())).on_conflict_do_nothing())
        self.db_session.execute(insert(Name).values(list(name_list.values())).on_conflict_do_nothing())
        self.db_session.execute(insert(FontInfo).values(font_info_list).on_conflict_do_nothing())
        len(postscript_name_list) != 0 and self.db_session.execute(insert(familyName).values(family_name_list).on_conflict_do_nothing())
        len(postscript_name_list) != 0 and self.db_session.execute(insert(fullName).values(full_name_list).on_conflict_do_nothing())
        len(postscript_name_list) != 0 and self.db_session.execute(insert(postscriptName).values(postscript_name_list).on_conflict_do_nothing())


    def close(self):
        """关闭线程池"""
        try:
            self.executor.shutdown(wait=True)
        except Exception as e:
            logger.error(f"关闭线程池时发生错误: {e}")
        finally:
            MAIN_LOOP.create_task(self.http_session.close())
            self.db_session.close()
            # self.db_session.remove()
            engine.dispose()

    async def loadFont(self, targetFontName, targetWeight, targetItalic):
        if (targetFontName, targetWeight, targetItalic) in self.cache:
            (fontBytes, index) = self.cache[(targetFontName, targetWeight, targetItalic)]  # 刷新缓存
            self.cache[(targetFontName, targetWeight, targetItalic)] = (fontBytes, index)
            logger.info(f"已缓存 {len(fontBytes) / (1024 * 1024):.2f}MB \t\t[{(targetFontName,targetWeight,targetItalic)} <== <cache> ]")
            return (fontBytes, index)
        elif result := self.selectFontLocal(targetFontName, targetWeight, targetItalic):
            path, index = result
            start = time.perf_counter_ns()
            async with aiofiles.open(path, "rb") as f:
                fontBytes = await f.read()
            logger.info(f"本地 {len(fontBytes) / (1024 * 1024):.2f}MB {(time.perf_counter_ns() - start) / 1000000:.2f}ms \t[{(targetFontName, targetWeight, targetItalic)} <== {path}]")
            self.cache[(targetFontName, targetWeight, targetItalic)] = (fontBytes, index)
            return (fontBytes, index)
        elif result := self.selectFontOnline(targetFontName, targetWeight, targetItalic):
            path, index = result
            url = f"https://fonts.storage.rd5isto.org/超级字体整合包 XZ/{path}"
            logger.info(f"下载字体 [{url}]")
            start = time.perf_counter_ns()
            resp = await self.http_session.get(url, timeout=10)
            fontBytes = await resp.read()
            logger.info(f"下载 {len(fontBytes) / (1024 * 1024):.2f}MB {(time.perf_counter_ns() - start) / 1000000:.2f}ms \t[{(targetFontName, targetWeight, targetItalic)} <== {url}]")
            self.cache[(targetFontName, targetWeight, targetItalic)] = (fontBytes, index)
            fontSavePath = os.path.join(os.path.join(DEFAULT_FONT_PATH, "download"), f"超级字体整合包 XZ/{path}")
            fontSaveDir = os.path.dirname(fontSavePath)
            os.makedirs(fontSaveDir, exist_ok=True)
            asyncio.run_coroutine_threadsafe(saveToDisk(fontSavePath, fontBytes), MAIN_LOOP)
            return (fontBytes, index)
        return (None, None)
