import warnings


warnings.filterwarnings("ignore")

import os
import ssl
import json
import logging
import asyncio
import requests
import traceback
import coloredlogs
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse
from uvicorn import Config, Server
from constants import logger, EMBY_SERVER_URL, FONT_DIRS, LOCAL_FONTS_PATH, LOCAL_FONTS_PATH, DEFAULT_FONT_PATH, MAIN_LOOP
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

userHDR = 0

@app.post("/setHDR/{value}")
async def setHDR(value: int):
    """实时调整HDR，-1 禁用HDR，0 使用环境变量值，大于0 替代当前值"""
    global userHDR
    userHDR = value
    logger.error(f"临时HDR 已设置为 {userHDR}")
    return value


@app.get("/setHDR",response_class=HTMLResponse)
async def setHDRIndex():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>临时调整HDR</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            flex-direction: column;
            background-color: #f4f4f4;
        }
        .slider-container {
            text-align: center;
            margin-bottom: 20px;
        }
        input[type="range"] {
            width: 100%;
            max-width: 600px;
        }
        button {
            margin: 5px;
            padding: 10px 20px;
            font-size: 16px;
        }
    </style>
</head>
<body>
    <div class="slider-container">
        <h1>Set HDR Value</h1>
        <input type="range" id="hdrSlider" min="1" max="10000" value="1000">
        <p>Current Value: <span id="sliderValue">1000</span></p>
        <button id="disableButton">禁用</button>
        <button id="defaultButton">默认</button>
    </div>

    <script>
        const slider = document.getElementById('hdrSlider');
        const sliderValue = document.getElementById('sliderValue');
        const disableButton = document.getElementById('disableButton');
        const defaultButton = document.getElementById('defaultButton');

        slider.addEventListener('input', () => {
            sliderValue.textContent = slider.value;
        });

        slider.addEventListener('change', async () => {
            const value = slider.value;
            await sendValue(value);
        });

        disableButton.addEventListener('click', async () => {
            await sendValue(-1);
        });

        defaultButton.addEventListener('click', async () => {
            await sendValue(0);
        });

        async function sendValue(value) {
            const response = await fetch(`/setHDR/${value}`, {
                method: 'POST' // 使用 POST 方法
            });
            if (response.ok) {
                console.log(`Value ${value} sent to /setHDR/${value}`);
            } else {
                console.error('Error sending value:', response.status);
            }
        }
    </script>
</body>
</html>
"""


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
        srt, bytes = await process(subtitleBytes, userHDR)
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
