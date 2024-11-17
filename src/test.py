import warnings
warnings.filterwarnings("ignore")

import os
import ssl
import time
import json
import asyncio
import requests
import logging
import traceback
import coloredlogs
from fastapi import FastAPI, Request, Response
from uvicorn import Config, Server
from concurrent.futures import ProcessPoolExecutor

from constants import logger, EMBY_SERVER_URL, FONT_DIRS, LOCAL_FONTS_PATH, LOCAL_FONTS_PATH, DEFAULT_FONT_PATH, MAIN_LOOP
from assSubsetter import assSubsetter
from fontManager import fontManager
from dirmonitor import dirmonitor


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


# app = Bottle()
app = FastAPI()

process = None


@app.get("/{path:path}")
async def proxy_pass(request: Request, response: Response):
    try:
        sourcePath = f"{request.url.path}?{request.url.query}" if request.url.query else request.url.path
        embyRequestUrl = EMBY_SERVER_URL + sourcePath
        logger.info(f"字幕URL: {embyRequestUrl}")
        serverResponse = requests.get(url=embyRequestUrl, headers=request.headers)
        # copyHeaders = {key: str(value) for key, value in response.headers.items()}
    except Exception as e:
        logger.error(f"fontinass获取原始字幕出错:{str(e)}")
        return ""
    try:
        subtitleBytes = serverResponse.content
        logger.info(f"原始大小: {len(subtitleBytes) / (1024 * 1024):.2f}MB")
        srt, bytes = await process(subtitleBytes)
        logger.info(f"处理后大小: {len(bytes) / (1024 * 1024):.2f}MB")
        # copyHeaders["Content-Length"] = str(len(bytes))
        if srt:
            if "user-agent" in request.headers and "infuse" in request.headers["user-agent"].lower():
                raise ValueError("infuse客户端，无法使用SRT转ASS功能，返回原始字幕")
        return Response(content=bytes)
    except Exception as e:
        logger.error(f"处理出错，返回原始内容 : \n{traceback.format_exc()}")
        return Response(content=serverResponse.content)


def getServer(port, serverLoop):
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


# "[UHA-WINGS&VCB-Studio] EIGHTY SIX [S01E03][Ma10p_1080p][x265_flac_aac].chs.ass",
# "[UHA-WINGS&VCB-Studio] EIGHTY SIX [S01E02][Ma10p_1080p][x265_flac_aac].chs.ass",
# analyseAss 约40ms


async def test():
    files = [
        "test/[UHA-WINGS&VCB-Studio] EIGHTY SIX [S01E04][Ma10p_1080p][x265_flac_aac].chs.ass",
        "test/[UHA-WINGS&VCB-Studio] EIGHTY SIX [S01E01][Ma10p_1080p][x265_flac_aac].chs.ass",
        # analyseAss 约5ms
    ]
    for file in files:
        with open(file, "rb") as f:
            subtitleBytes = f.read()
        start = time.perf_counter_ns()
        await process(subtitleBytes)
        logger.debug(f"测试完成 用时 {(time.perf_counter_ns() - start) / 1000000:.2f} ms")


def initpass():
    pass


def worker(start):
    logger.error(f"启动用时 {(time.perf_counter_ns() - start) / 1000000:.2f} ms")
    return time.perf_counter_ns()


async def submit(pool):
    start = time.perf_counter_ns()
    end = await MAIN_LOOP.run_in_executor(pool, worker, start)
    logger.debug(f"运行用时 {(end - start) / 1000000:.2f} ms")


async def testPool():
    pool = ProcessPoolExecutor(max_workers=int(os.cpu_count()))
    pool.submit(initpass)
    await asyncio.gather(*[submit(pool) for _ in range(10)])
    pool.shutdown()


if __name__ == "__main__":
    logger.info("本地字体文件夹:" + ",".join(FONT_DIRS))
    if not os.path.exists(LOCAL_FONTS_PATH):
        with open(LOCAL_FONTS_PATH, "w", encoding="UTF-8") as f:
            json.dump({}, f)
    os.makedirs(DEFAULT_FONT_PATH, exist_ok=True)
    asyncio.set_event_loop(MAIN_LOOP)
    ssl._create_default_https_context = ssl._create_unverified_context
    fontManagerInstance = fontManager()
    fontManagerInstance.updateLocalFont()  # 更新本地字体
    assSubsetterInstance = assSubsetter(fontManagerInstance=fontManagerInstance)
    event_handler = dirmonitor(callBack=fontManagerInstance.updateLocalFont)  # 创建fonts字体文件夹监视实体
    event_handler.start()
    process = assSubsetterInstance.process  # 绑定函数
    serverInstance = getServer(8011, MAIN_LOOP)
    init_logger()
    MAIN_LOOP.run_until_complete(test())
    # MAIN_LOOP.run_until_complete(testPool())
    # # 关闭和清理资源
    event_handler.stop()  # 停止文件监视器
    event_handler.join()  # 等待文件监视退出
    fontManagerInstance.close()  # 关闭aiohttp的session
    # assSubsetterInstance.close()  # 关闭进程池
    pending = asyncio.all_tasks(MAIN_LOOP)
    MAIN_LOOP.run_until_complete(asyncio.gather(*pending, return_exceptions=True))  # 等待异步任务结束
    MAIN_LOOP.stop()  # 停止事件循环
    MAIN_LOOP.close()  # 清理资源
