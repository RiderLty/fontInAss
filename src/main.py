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
    return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>颜色调整器</title>
    <style>
        body {
            background-color: #212121;
            font-family: 'Arial', sans-serif;
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 40px 20px;
        }
        
        .container {
            max-width: 500px;
            width: 100%;
            display: flex;
            flex-direction: column;
            align-items: center;
        }
        
        .color-box {
            width: 150px;
            height: 150px;
            border-radius: 8px;
            margin: 8px 0;
            cursor: pointer;
            display: flex;
            justify-content: center;
            align-items: center;
            transition: transform 0.2s ease;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        
        .color-box:hover {
            transform: scale(1.02);
        }
        
        .color-box:first-child {
            margin-top: 0;
        }
        
        .color-picker {
            position: absolute;
            display: none;
        }
        
        .slider-container {
            width: 100%;
            margin-top: 32px;
        }
        
        .slider-group {
            margin-bottom: 20px;
            color: #BDBDBD;
        }
        
        .slider-group label {
            display: block;
            margin-bottom: 8px;
            font-weight: bold;
        }
        
        .slider {
            width: 100%;
            margin-bottom: 8px;
        }
        
        .slider-value {
            text-align: center;
            font-weight: bold;
            margin-top: 5px;
        }
        
        .instructions {
            margin-top: 20px;
            text-align: center;
            color: #666;
            font-size: 14px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="color-box" id="original-color-box" style="background-color: white; cursor: pointer;">
            <input type="color" id="color-picker" class="color-picker" value="#ffffff">
        </div>
        
        <div style="display: flex; align-items: center; justify-content: center; margin: 16px 0;">
            <span style="font-size: 24px; color: #BDBDBD; margin-right: 8px;" id="saturation-value-display">饱和度x1.00</span>
            <span style="font-size: 24px; color: #BDBDBD;">↓</span>
            <span style="font-size: 24px; color: #BDBDBD; margin-left: 8px;" id="brightness-value-display">亮度x1.00</span>
        </div>

        <div class="color-box" id="adjusted-color-box" style="background-color: white;" ></div>
        
        <div class="slider-container">
            <div class="slider-group">
                <label for="saturation-slider">饱和度 (S):</label>
                <input type="range" id="saturation-slider" class="slider" min="0" max="1" step="0.01" value="1">
                <div class="slider-value" id="saturation-value">1.00</div>
            </div>
            
            <div class="slider-group">
                <label for="brightness-slider">亮度 (V):</label>
                <input type="range" id="brightness-slider" class="slider" min="0" max="1" step="0.01" value="1">
                <div class="slider-value" id="brightness-value">1.00</div>
            </div>
        </div>
        
        <div class="instructions">
            点击上方色块选择颜色，用滑块调整饱和度和亮度
        </div>
    </div>

    <script>
        const originalColorBox = document.getElementById('original-color-box');
        const adjustedColorBox = document.getElementById('adjusted-color-box');
        const colorPicker = document.getElementById('color-picker');
        const saturationSlider = document.getElementById('saturation-slider');
        const brightnessSlider = document.getElementById('brightness-slider');
        const saturationValue = document.getElementById('saturation-value');
        const brightnessValue = document.getElementById('brightness-value');
        const saturationValue_display = document.getElementById('saturation-value-display');
        const brightnessValue_display = document.getElementById('brightness-value-display');
        
        // 当前选中的原始颜色 (HEX)
        let originalColor = '#ffffff';
        
        // 点击原始色块时显示颜色选择器
        originalColorBox.addEventListener('click', () => {
            colorPicker.click();
        });
        
        // 颜色选择器变化时更新原始颜色
        colorPicker.addEventListener('input', (e) => {
            originalColor = e.target.value;
            originalColorBox.style.backgroundColor = originalColor;
            
            // 更新调整后的颜色
            updateAdjustedColor();
        });
        

        fetch("/color/set/brightness/-1").then(resp => resp.text()).then(val => {
            console.log("亮度:", val);
            brightnessSlider.value = val;
            brightnessValue.textContent = parseFloat(val).toFixed(2);
            brightnessValue_display.textContent = `亮度x${parseFloat(val).toFixed(2)}`;
            updateAdjustedColor();
            brightnessSlider.addEventListener('input', () => {
                brightnessValue.textContent = parseFloat(brightnessSlider.value).toFixed(2);
                brightnessValue_display.textContent = `亮度x${parseFloat(brightnessSlider.value).toFixed(2)}`;
                updateAdjustedColor();
            });
            brightnessSlider.addEventListener('change', () => {
                brightnessValue.textContent = parseFloat(brightnessSlider.value).toFixed(2);
                brightnessValue_display.textContent = `亮度x${parseFloat(brightnessSlider.value).toFixed(2)}`;
                updateAdjustedColor();
                console.log('亮度:', parseFloat(brightnessSlider.value).toFixed(2) , "提交");
                fetch("/color/set/brightness/" + parseFloat(brightnessSlider.value).toFixed(2))

            });
        });
        fetch("/color/set/saturation/-1").then(resp => resp.text()).then(val => {
            console.log("饱和度:", val);
            saturationSlider.value = val;
            saturationValue.textContent = parseFloat(val).toFixed(2);
            saturationValue_display.textContent = `饱和度x${parseFloat(val).toFixed(2)}`;
            updateAdjustedColor();
            saturationSlider.addEventListener('input', () => {
                saturationValue.textContent = parseFloat(saturationSlider.value).toFixed(2);
                saturationValue_display.textContent = `饱和度x${parseFloat(saturationSlider.value).toFixed(2)}`;
                updateAdjustedColor();
            });
            saturationSlider.addEventListener('change', () => {
                saturationValue.textContent = parseFloat(saturationSlider.value).toFixed(2);
                saturationValue_display.textContent = `饱和度x${parseFloat(saturationSlider.value).toFixed(2)}`;
                updateAdjustedColor();
                console.log('饱和度:', parseFloat(saturationSlider.value).toFixed(2) , "提交");
                fetch("/color/set/saturation/" + parseFloat(saturationSlider.value).toFixed(2))
            });
        });
        
        // 更新调整后的颜色
        function updateAdjustedColor() {
            // 将原始颜色转换为HSB值
            const originalRGB = hexToRgb(originalColor);
            const originalHSB = rgbToHsb(originalRGB.r, originalRGB.g, originalRGB.b);
            
            // 应用滑块调整的饱和度和亮度
            const adjustedS = originalHSB.s * parseFloat(saturationSlider.value);
            const adjustedB = originalHSB.b * parseFloat(brightnessSlider.value);
            
            // 将调整后的HSB转换回RGB
            const adjustedRGB = hsbToRgb(originalHSB.h, adjustedS, adjustedB);
            
            // 更新显示的调整后颜色
            adjustedColorBox.style.backgroundColor = `rgb(${adjustedRGB.r}, ${adjustedRGB.g}, ${adjustedRGB.b})`;
        }
        
        // 辅助函数：HEX转RGB
        function hexToRgb(hex) {
            const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
            return result ? {
                r: parseInt(result[1], 16),
                g: parseInt(result[2], 16),
                b: parseInt(result[3], 16)
            } : { r: 0, g: 0, b: 0 };
        }
        
        // 辅助函数：RGB转HSB
        function rgbToHsb(r, g, b) {
            r /= 255;
            g /= 255;
            b /= 255;
            
            const max = Math.max(r, g, b);
            const min = Math.min(r, g, b);
            let h, s, v = max;
            
            const d = max - min;
            s = max === 0 ? 0 : d / max;
            
            if (max === min) {
                h = 0;
            } else {
                switch (max) {
                    case r: h = (g - b) / d + (g < b ? 6 : 0); break;
                    case g: h = (b - r) / d + 2; break;
                    case b: h = (r - g) / d + 4; break;
                }
                h /= 6;
            }
            
            return { h, s, b: v };
        }
        
        // 辅助函数：HSB转RGB
        function hsbToRgb(h, s, b) {
            const k = n => (n + h * 6) % 6;
            const f = n => b * (1 - s * Math.max(0, Math.min(k(n), 4 - k(n), 1)));
            
            return {
                r: Math.round(f(5) * 255),
                g: Math.round(f(3) * 255),
                b: Math.round(f(1) * 255)
            };
        }
        
        // 初始化
        saturationValue.textContent = '1.00';
        brightnessValue.textContent = '1.00';
        updateAdjustedColor();
    </script>
</body>
</html>
"""

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
