import warnings
warnings.filterwarnings('ignore')

import builtins
import logging
import multiprocessing

import coloredlogs
import fontLoader
import traceback
import os
import json
import requests

from fastapi import FastAPI, Query, Request, Response
from uvicorn import Config, Server
from cachetools import LRUCache
import asyncio
import ssl

import utils
from dirmonitor import dirmonitor

logger = logging.getLogger(f'{"main"}:{"loger"}')
app = FastAPI()


def custom_print(*args, **kwargs):
    logger.info("".join([str(x) for x in args]))

def init_logger():
    LOGGER_NAMES = (
        "uvicorn",
        "uvicorn.access",
    )
    for logger_name in LOGGER_NAMES:
        logging_logger = logging.getLogger(logger_name)
        fmt = f"🌏 %(asctime)s.%(msecs)03d .%(levelname)s \t%(message)s"  # 📨
        coloredlogs.install(
            level=logging.DEBUG,
            logger=logging_logger,
            milliseconds=True,
            datefmt="%X",
            fmt=fmt,
        )


@app.post("/process_bytes")
async def process_bytes(request: Request):
    """传入字幕字节"""
    print(request.headers)
    subtitleBytes = await request.body()
    try:
        srt, bytes = utils.process(pool, subtitleBytes, subCache, externalFonts, fontPathMap, fontCache)
        return Response(
            content=bytes, headers={"Srt2Ass": str(srt), "fontinass-exception": "None"}
        )
    except Exception as e:
        logger.error(f"处理出错，返回原始内容 : \n{traceback.format_exc()}")
        return Response(
            content=subtitleBytes,
            headers={"Srt2Ass": str(False), "fontinass-exception": str(e)},
        )


@app.get("/process_url")
async def process_url(ass_url: str = Query(None)):
    """传入字幕url"""
    print("loading " + ass_url)
    try:
        subtitleBytes = requests.get(ass_url).content
        srt, bytes = utils.process(pool, subtitleBytes, subCache, externalFonts, fontPathMap, fontCache)
        return Response(
            content=bytes, headers={"Srt2Ass": str(srt), "fontinass-exception": "None"}
        )
    except Exception as e:
        logger.error(f"处理出错，返回原始内容 : \n{traceback.format_exc()}")
        return Response(
            content=subtitleBytes,
            headers={"Srt2Ass": str(False), "fontinass-exception": str(e)},
        )

@app.get("/{path:path}")
async def proxy_pass(request: Request, response: Response):
    try:
        host = os.environ.get("EMBY_SERVER_URL") or EMBY_SERVER_URL
        url = (
            f"{request.url.path}?{request.url.query}"
            if request.url.query
            else request.url.path
        )
        embyRequestUrl = host + url
        logger.info(f"字幕URL:{embyRequestUrl}")
        serverResponse = requests.get(url=embyRequestUrl, headers=request.headers)
        copyHeaders = {key: str(value) for key, value in response.headers.items()}
    except Exception as e:
        info = f"fontinass获取原始字幕出错:{str(e)}"
        logger.error(info)
        return info
    try:
        logger.info(f"原始大小:{len(serverResponse.content)}")
        srt, bytes = utils.process(pool, serverResponse.content, subCache, externalFonts, fontPathMap, fontCache)
        logger.info(f"处理后大小:{len(bytes)}")
        copyHeaders["Content-Length"] = str(len(bytes))
        if srt:
            if (
                "user-agent" in request.headers
                and "infuse" in request.headers["user-agent"].lower()
            ):
                raise ValueError("infuse客户端，无法使用SRT转ASS功能，返回原始字幕")
        return Response(content=bytes)
    except Exception as e:
        logger.error(f"处理出错，返回原始内容 : \n{traceback.format_exc()}")
        return Response(content=serverResponse.content)


# class MyHandler(FileSystemEventHandler):
#     def on_created(self, event):
#         self.emit_once = True
#         utils.updateLocal(fontDirList)
#
#     def on_deleted(self, event):
#         self.emit_once = True
#         utils.updateLocal(fontDirList)

def getServer(port,serverLoop):
    serverConfig = Config(
        app=app,
        # host="::",
        host="0.0.0.0",
        port=port,
        log_level="info",
        loop=serverLoop,
        ws_max_size=1024 * 1024 * 1024 * 1024,
    )
    return Server(serverConfig)

if __name__ == "__main__":
    #根据CPU逻辑处理器数创建子进程池
    pool = multiprocessing.Pool(int(os.cpu_count()))
    fmt = f"🤖 %(asctime)s.%(msecs)03d .%(levelname)s \t%(message)s"
    coloredlogs.install(
        level=logging.DEBUG, logger=logger, milliseconds=True, datefmt="%X", fmt=fmt
    )
    original_print = builtins.print
    builtins.print = custom_print
    # 手动修改此处，或者使用环境变量
    EMBY_SERVER_URL = "尚未EMBY_SERVER_URL环境变量"

    cacheSize = int(os.environ.get("CACHE_SIZE") or 32)
    subCache = LRUCache(maxsize=cacheSize)

    serverLoop = asyncio.new_event_loop()
    asyncio.set_event_loop(serverLoop)
    ssl._create_default_https_context = ssl._create_unverified_context

    fontDirList = [r"../fonts"]

    # externalFonts = utils.updateLocal(fontDirList)
    with open("../localFontMap.json", "r", encoding="UTF-8") as f:
        localFonts = utils.updateFontMap(fontDirList, json.load(f))

    with open("../localFontMap.json", "w", encoding="UTF-8") as f:
        json.dump(localFonts, f, indent=4, ensure_ascii=True)

    externalFonts = fontLoader.makeFontMap(localFonts)
    with open("../fontMap.json", "r", encoding="UTF-8") as f:
        fontPathMap = fontLoader.makeFontMap(
            json.load(f)
        )

    if os.environ.get("FONT_DIRS"):
        for dirPath in os.environ.get("FONT_DIRS").split(";"):
            if dirPath.strip() != "" and os.path.exists(dirPath):
                fontDirList.append(dirPath.strip())
    logger.info("本地字体文件夹:" + ",".join(fontDirList))

    if not os.path.exists("../localFontMap.json"):
        with open("../localFontMap.json", "w", encoding="UTF-8") as f:
            json.dump({}, f)

    if not os.path.exists("../fonts"):
        os.makedirs("../fonts", exist_ok=True)

    cacheSize = int(os.environ.get("CACHE_SIZE") or 32)
    fontCache = LRUCache(maxsize=cacheSize)


    # event_handler = MyHandler()
    event_handler = dirmonitor(fontDirList)
    event_handler.start()
    # observer = Observer()
    # for fontDir in fontDirList:
    #     logger.info("监控中:" + os.path.abspath(fontDir))
    #     observer.schedule(event_handler, os.path.abspath(fontDir), recursive=True)
    # observer.start()
    serverInstance = getServer(8011,serverLoop)
    init_logger()
    serverLoop.run_until_complete(serverInstance.serve())
    # observer.stop()
    # observer.join()
    event_handler.stop()
    event_handler.join()
    pool.close()
    pool.join()  # 等待所有进程完成
