import warnings


warnings.filterwarnings("ignore")

import os
import ssl
import logging
import asyncio
import requests
import traceback
import coloredlogs
from fastapi import FastAPI, Request, Response
from uvicorn import Config, Server
from constants import logger, EMBY_SERVER_URL, FONT_DIRS, DEFAULT_FONT_PATH, MAIN_LOOP
from dirmonitor import dirmonitor
from fontManager import fontManager
from assSubsetter import assSubsetter

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
        logger.error(f"获取原始字幕出错:{str(e)}")
        return ""
    try:
        subtitleBytes = serverResponse.content
        srt, bytes = await process(subtitleBytes)
        logger.info(f"字幕处理完成: {len(subtitleBytes) / (1024 * 1024):.2f}MB ==> {len(bytes) / (1024 * 1024):.2f}MB")
        # copyHeaders["Content-Length"] = str(len(bytes))
        if srt and ("user-agent" in request.headers) and ("infuse" in request.headers["user-agent"].lower()):
            logger.error("infuse客户端，无法使用SRT转ASS功能，返回原始字幕")
            return Response(content=subtitleBytes)
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


if __name__ == "__main__":
    logger.info("本地字体文件夹:" + ",".join(FONT_DIRS))
    os.makedirs(DEFAULT_FONT_PATH, exist_ok=True)
    asyncio.set_event_loop(MAIN_LOOP)
    ssl._create_default_https_context = ssl._create_unverified_context
    fontManagerInstance = fontManager()
    assSubsetterInstance = assSubsetter(fontManagerInstance=fontManagerInstance)
    event_handler = dirmonitor(callBack=fontManagerInstance)  # 创建fonts字体文件夹监视实体
    event_handler.start()
    process = assSubsetterInstance.process  # 绑定函数
    serverInstance = getServer(8011, MAIN_LOOP)
    init_logger()
    MAIN_LOOP.run_until_complete(serverInstance.serve())
    # # 关闭和清理资源
    event_handler.stop()  # 停止文件监视器
    event_handler.join()  # 等待文件监视退出
    fontManagerInstance.close()  # 关闭aiohttp的session
    # assSubsetterInstance.close()  # 关闭进程池
    pending = asyncio.all_tasks(MAIN_LOOP)
    MAIN_LOOP.run_until_complete(asyncio.gather(*pending, return_exceptions=True))  # 等待异步任务结束
    MAIN_LOOP.stop()  # 停止事件循环
    MAIN_LOOP.close()  # 清理资源
