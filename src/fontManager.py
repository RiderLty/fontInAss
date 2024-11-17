import asyncio
import os
import threading
import time
import aiofiles
import aiohttp
from cachetools import LRUCache, TTLCache
import json
from fontTools.ttLib import TTFont, TTCollection

from utils import getAllFiles, saveToDisk
from constants import *


def makeMiniSizeFontMap(data):
    """
    {
        /path/to/ttf/or/otf : {
            size: 62561,
            fonts:{
                YAHEI:0,
                FANGSONG,5
            }
        }
    }
    转化为

    {
        fontname : [path,index]
    }

    """
    fontFileMap = {}
    fontMiniSize = {}
    for path in data.keys():
        size = data[path]["size"]
        for fontName, index in data[path]["fonts"].items():
            if fontName not in fontFileMap or fontMiniSize[fontName] > size:
                fontFileMap[fontName] = (path, index)
                fontMiniSize[fontName] = size
    return fontFileMap


class fontManager:

    def __init__(self):
        self.cache = TTLCache(maxsize=FONT_CACHE_SIZE, ttl=FONT_CACHE_TTL) if FONT_CACHE_TTL > 0 else LRUCache(maxsize=FONT_CACHE_SIZE)
        with open(ONLINE_FONTS_PATH, "r", encoding="UTF-8") as f:
            self.onlineMap = makeMiniSizeFontMap(json.load(f))  # 在线字体map
        with open(LOCAL_FONTS_PATH, "r", encoding="UTF-8") as f:
            self.localFontDB = json.load(f)  # 本地字体原始数据
        self.localMap = makeMiniSizeFontMap(self.localFontDB)  # 本地字体map
        self.session = aiohttp.ClientSession(loop=MAIN_LOOP)  # 下载的session
        self.updateLocalLock = threading.Lock()  # 本地字体更新lock

    def close(self):
        MAIN_LOOP.create_task(self.session.close())

    def updateLocalFont(self):
        """更新本地字体"""
        with self.updateLocalLock:  # 确保不同时更新localFontDB与loadFont
            newLocalFontDB = {}
            for dirPath in FONT_DIRS:
                for file in getAllFiles(dirPath):
                    if file in self.localFontDB:
                        newLocalFontDB[file] = self.localFontDB[file]  # 跳过已存在的
                    else:
                        try:
                            if file.lower()[-3:] in ["ttc", "ttf", "otf"]:
                                logger.info(f"更新外部字体 {file}")
                                with open(file, "rb") as f:
                                    sfntVersion = f.read(4)
                                fonts = TTCollection(file).fonts if sfntVersion == b"ttcf" else [TTFont(file)]
                                fontIndex = {}  # name:index
                                for index, font in enumerate(fonts):
                                    for record in font["name"].names:
                                        if record.nameID == 1:  # Font Family name
                                            fontIndex[str(record).strip()] = index
                                newLocalFontDB[file] = {"size": os.path.getsize(file), "fonts": fontIndex}
                        except Exception as e:
                            logger.error(f"更新外部字体出错 {file} : {str(e)}")

            self.localFontDB = newLocalFontDB
            self.localMap = makeMiniSizeFontMap(newLocalFontDB)
            with open(LOCAL_FONTS_PATH, "w", encoding="UTF-8") as f:
                json.dump(newLocalFontDB, f, ensure_ascii=True, indent=4)  # 本地字体原始数据

    async def loadFont(self, fontName):
        """提供字体名称，返回bytes与index"""
        if fontName in self.cache:
            (fontBytes, index) = self.cache[fontName]  # 刷新缓存
            self.cache[fontName] = (fontBytes, index)
            logger.info(f"已缓存 {len(fontBytes) / (1024 * 1024):.2f}MB \t\t[{fontName}]")
            return (fontBytes, index)

        if fontName in self.localMap:
            (path, index) = self.localMap[fontName]
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
            resp = await self.session.get(f"https://fonts.storage.rd5isto.org{url}", timeout=10)
            fontBytes = await resp.read()
            logger.info(f"下载 {len(fontBytes) / (1024 * 1024):.2f}MB in {(time.perf_counter_ns() - start) / 1000000000:.2f}s\t[{fontName} <== https://fonts.storage.rd5isto.org{url}]")
            self.cache[fontName] = (fontBytes, index)
            fontSavePath = os.path.join(os.path.join(DEFAULT_FONT_PATH, "download"), url.lstrip("/"))
            fontSaveDir = os.path.dirname(fontSavePath)
            os.makedirs(fontSaveDir, exist_ok=True)
            asyncio.run_coroutine_threadsafe(saveToDisk(fontSavePath, fontBytes), MAIN_LOOP)
            return (fontBytes, index)

        return None, None
