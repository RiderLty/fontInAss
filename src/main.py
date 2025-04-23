import base64
import warnings

from colorAdjust import colorAdjust


warnings.filterwarnings("ignore")

import os
import ssl
import logging
import asyncio
import requests
import traceback
import coloredlogs
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from uvicorn import Config, Server
from constants import logger, EMBY_SERVER_URL, FONT_DIRS, DEFAULT_FONT_PATH, MAIN_LOOP, INSERT_JS
from dirmonitor import dirmonitor
from fontManager import fontManager
from assSubsetter import assSubsetter
from utils import insert_str


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


# sub_app = Bottle()
# sub_app = FastAPI()
app = FastAPI()

process = None

@app.get("/color/adjust", response_class=HTMLResponse)
async def setColor():
    return open(os.path.join(os.path.join(os.path.dirname(__file__) , "html"), "color.html"), "r", encoding="utf-8").read()

user_hsv_s = 1
user_hsv_v = 1

@app.get("/color/set/saturation/{val}")
async def set_saturation(val: float):
    """设置饱和度"""
    global user_hsv_s,user_hsv_v
    if val < 0 :
        return user_hsv_s
    user_hsv_s = val
    if user_hsv_s < 0:
        user_hsv_s = 0
    if user_hsv_s > 1:
        user_hsv_s = 1
    logger.info(f"饱和度 已设置为 {user_hsv_s}")
    return val

@app.get("/color/set/brightness/{val}")
async def set_brightness(val: float):
    """设置亮度"""
    global user_hsv_s,user_hsv_v
    if val < 0 :
        return user_hsv_v
    user_hsv_v = val
    if user_hsv_v < 0:
        user_hsv_v = 0
    if user_hsv_v > 1:
        user_hsv_v = 1
    logger.info(f"亮度 已设置为 {user_hsv_v}")
    return val      
        
@app.post("/fontinass/process_bytes")
async def process_bytes(request: Request):
    global user_hsv_s,user_hsv_v
    subtitleBytes = await request.body()
    try:
        error, srt, bytes = await process(subtitleBytes, user_hsv_s,user_hsv_v)
        return Response(
            content=bytes,
            headers={
                "error": base64.b64encode((error).encode("utf-8")).decode("ASCII"),
                "srt": "true" if srt else "false",
            },
        )
    except Exception as e:
        print(f"ERROR : {str(e)}")
        return Response(subtitleBytes)


@app.get("/web/modules/htmlvideoplayer/plugin.js")
async def htmlvideoplayer_plugin_js(request: Request, response: Response):
    try:
        sourcePath = f"{request.url.path}?{request.url.query}" if request.url.query else request.url.path
        embyRequestUrl = EMBY_SERVER_URL + sourcePath
        logger.info(f"JSURL: {embyRequestUrl}")
        serverResponse = requests.get(url=embyRequestUrl, headers=request.headers)
    except Exception as e:
        logger.error(f"获取原始JS出错:{str(e)}")
        return ""
    try:
        jsContent = serverResponse.content.decode("utf-8")
        jsContent = jsContent.replace("fetchSubtitleContent(textTrackUrl,!0)", "fetchSubtitleContent(textTrackUrl,false)")
        return Response(content=jsContent)
    except Exception as e:
        logger.error(f"处理出错，返回原始内容 : \n{traceback.format_exc()}")
        return Response(content=serverResponse.content)


@app.get("/web/bower_components/{path:path}/subtitles-octopus.js")
async def subtitles_octopus_js(request: Request, response: Response):
    try:
        sourcePath = f"{request.url.path}?{request.url.query}" if request.url.query else request.url.path
        embyRequestUrl = EMBY_SERVER_URL + sourcePath
        logger.info(f"JSURL: {embyRequestUrl}")
        serverResponse = requests.get(url=embyRequestUrl, headers=request.headers)
    except Exception as e:
        logger.error(f"获取原始JS出错:{str(e)}")
        return ""
    try:
        jsContent = serverResponse.content.decode("utf-8")
        jsContent = insert_str(jsContent, INSERT_JS, "function(options){")
        return Response(content=jsContent)
    except Exception as e:
        logger.error(f"处理出错，返回原始内容 : \n{traceback.format_exc()}")
        return Response(content=serverResponse.content)


@app.get("/{path:path}")
async def proxy_pass(request: Request, response: Response):
    global user_hsv_s,user_hsv_v
    try:
        sourcePath = f"{request.url.path}?{request.url.query}" if request.url.query else request.url.path
        embyRequestUrl = EMBY_SERVER_URL + sourcePath
        logger.info(f"字幕URL: {embyRequestUrl}")
        serverResponse = requests.get(url=embyRequestUrl, headers=request.headers)
    except Exception as e:
        logger.error(f"获取原始字幕出错:{str(e)}")
        return ""
    headers = {}
    try:
        subtitleBytes = serverResponse.content
        error, srt, bytes = await process(subtitleBytes, user_hsv_s,user_hsv_v)
        logger.info(f"字幕处理完成: {len(subtitleBytes) / (1024 * 1024):.2f}MB ==> {len(bytes) / (1024 * 1024):.2f}MB")
        if srt and ("user-agent" in request.headers) and ("infuse" in request.headers["user-agent"].lower()):
            raise BaseException("infuse客户端，无法使用SRT转ASS功能，返回原始字幕")
        headers["content-type"] = "text/x-ssa"
        headers["error"] = base64.b64encode((error).encode("utf-8")).decode("ASCII")
        headers["srt"] = "true" if srt else "false"
        if "content-disposition" in serverResponse.headers:
            headers["content-disposition"] = serverResponse.headers["content-disposition"]
        return Response(content=bytes, headers=headers)
    except Exception as e:
        logger.error(f"处理出错，返回原始内容 : \n{traceback.format_exc()}")
        reHeader = {key: value for (key, value) in serverResponse.headers.items()}
        reHeader["Content-Length"] = str(len(serverResponse.content))
        # print("reHeader",reHeader)
        return Response(content=serverResponse.content , headers=reHeader)


def getServer(port, serverLoop, app):
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
    event_handler = dirmonitor(callback=fontManagerInstance)  # 创建fonts字体文件夹监视实体
    event_handler.start()
    process = assSubsetterInstance.process  # 绑定函数
    serverInstance = getServer(8011, MAIN_LOOP, app)
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
