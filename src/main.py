from enum import Enum
import warnings
warnings.filterwarnings("ignore")
import base64
import json
import os
import ssl
import time
import logging
import asyncio
import platform
import requests
import coloredlogs
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from uvicorn import Config, Server
from constants import logger, EMBY_SERVER_URL, FONT_DIRS, DEFAULT_FONT_PATH, MAIN_LOOP, INSERT_JS, ROOT_PATH, DATA_PATH
from dirmonitor import dirmonitor
from fontmanager import FontManager
from subsetter import SubSetter
from utils import insert_str
from config import ConfigManager, CONFIG_SCHEMA
from sse_handler import sse_handler, sse_log_stream
import mimetypes

_start_time = time.time()



def init_logger():
    logger_name = (
        "uvicorn",
        "uvicorn.access",
    )
    for name in logger_name:
        logging_logger = logging.getLogger(name)
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

app.add_middleware(
    CORSMiddleware,
    # 本地前后端分离开发npm dev端口
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Code", "X-Message"],
)

process = None
process_subset = None

# YAML config manager
config_manager = ConfigManager(
    schema=CONFIG_SCHEMA,
    yaml_path=os.path.join(DATA_PATH, "config.yaml"),
)

# Install SSE log handler
sse_handler.setFormatter(logging.Formatter("%(message)s"))
logging.getLogger("main:loger").addHandler(sse_handler)

# Override module-level constants from YAML/env config
import constants
for key in CONFIG_SCHEMA:
    if hasattr(constants, key):
        val, _ = config_manager.get(key)
        if val is not None:
            setattr(constants, key, val)

# 修复 Windows / 某些系统默认缺失的 MIME 类型
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")

# 挂载前端静态文件，访问 ip:8011/subset
app.mount(
    "/subset",
    StaticFiles(directory=os.path.join(ROOT_PATH, "subset/dist"), html=True),
    name="subset"
)

@app.post("/api/subset")
async def index_subset(request: Request):
    try:
        raw_bytes = await request.body()
        srt_format = request.headers.get("X-Srt-Format")
        srt_style = request.headers.get("X-Srt-Style")
        if srt_format:
            srt_format = base64.b64decode(srt_format).decode("utf-8")
        if srt_style:
            srt_style = base64.b64decode(srt_style).decode("utf-8")
        renamed_restore = request.headers.get("X-Renamed-Restore") == "1"
        clear_fonts = request.headers.get("X-Clear-Fonts") == "1"
        fonts_check = request.headers.get("X-Fonts-Check") == "1"
        hsv_s = config_manager.get("HDR_SATURATION")[0]
        hsv_v = config_manager.get("HDR_BRIGHTNESS")[0]

        result = await process_subset(
            raw_bytes,
            fonts_check=fonts_check,
            srt_format=srt_format,
            srt_style=srt_style,
            renamed_restore=renamed_restore,
            clear_fonts=clear_fonts,
            hsv_s=hsv_s,
            hsv_v=hsv_v,
        )

        message = ""
        if result.message:
            message = base64.b64encode(json.dumps(result.message).encode("utf-8")).decode("ascii")

        return Response(
            content=result.data,
            media_type="application/octet-stream",
            headers={
                "X-Code": str(result.code),
                "X-Message": message,
            }
        )
    except Exception as e:
        logger.exception("/api/subset 处理出错")
        # logger.error(f"/api/subset 处理出错: \n{traceback.format_exc()}")
        message = base64.b64encode(str(e).encode('utf-8')).decode('ascii')
        return Response(
            content= b"",
            media_type="application/octet-stream",
            headers={
                "X-Code": str(500),
                "X-Message": message,
            }
        )

# ========= Config / Status / Logs API =========

@app.get("/api/config")
async def get_config():
    return config_manager.get_all()

@app.put("/api/config")
async def update_config(request: Request):
    body = await request.json()
    if "key" in body and "value" in body:
        key, value = body["key"], body["value"]
        try:
            new_val, new_src, old_val, old_src = config_manager.set(key, value)
            return {"success": True, "key": key, "value": new_val, "source": new_src,
                    "previous_value": old_val, "previous_source": old_src}
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Key not found in schema: {key}")
    elif "updates" in body:
        results = []
        for k, v in body["updates"].items():
            try:
                new_val, new_src, old_val, old_src = config_manager.set(k, v)
                results.append({"key": k, "value": new_val, "source": new_src})
            except KeyError:
                results.append({"key": k, "error": f"Key not found in schema"})
        return {"success": True, "results": results}
    raise HTTPException(status_code=400, detail="Invalid request body")

@app.delete("/api/config/{key}")
async def delete_config(key: str):
    try:
        value, source = config_manager.delete(key)
        return {"success": True, "key": key, "current_value": value, "current_source": source}
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Key not found in schema: {key}")

@app.get("/api/logs/stream")
async def logs_stream(request: Request):
    return StreamingResponse(
        sse_log_stream(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

@app.get("/api/status")
async def get_status():
    return {
        "version": "0.1.0",
        "uptime_seconds": int(time.time() - _start_time),
        "python_version": platform.python_version(),
        "config_source": "yaml" if config_manager._yaml_data else "default",
        "config_path": str(config_manager._yaml_path),
        "log_level": config_manager.get("LOG_LEVEL")[0],
        "emby_server_url": config_manager.get("EMBY_SERVER_URL")[0],
    }

# 重定向/subset 到 /subset/
@app.get("/subset")
async def redirect_subset():
    return RedirectResponse(url="/subset/")

@app.post("/fontinass/process_bytes")
async def process_bytes(request: Request):
    raw_bytes = await request.body()
    hsv_s = config_manager.get("HDR_SATURATION")[0]
    hsv_v = config_manager.get("HDR_BRIGHTNESS")[0]
    try:
        error, srt, result_bytes = await process(raw_bytes, hsv_s, hsv_v)
        return Response(
            content=result_bytes,
            headers={
                "error": base64.b64encode(error.encode("utf-8")).decode("ASCII"),
                "srt": "true" if srt else "false",
            },
        )
    except Exception as e:
        logger.exception("/fontinass/process_bytes ERROR")
        return Response(raw_bytes)


@app.get("/web/modules/htmlvideoplayer/plugin.js")
async def html_videoplayer_plugin_js(request: Request, response: Response):
    try:
        source_path = f"{request.url.path}?{request.url.query}" if request.url.query else request.url.path
        request_url = EMBY_SERVER_URL + source_path
        logger.info(f"JSURL: {request_url}")
        server_response = requests.get(url=request_url, headers=request.headers)
    except Exception as e:
        logger.exception("获取原始JS出错")
        return ""
    try:
        content = server_response.content.decode("utf-8")
        content = content.replace("fetchSubtitleContent(textTrackUrl,!0)", "fetchSubtitleContent(textTrackUrl,false)")
        return Response(content=content)
    except Exception as e:
        logger.exception("处理出错，返回原始内容")
        # logger.error(f"处理出错，返回原始内容 : \n{traceback.format_exc()}")
        return Response(content=server_response.content)


@app.get("/web/bower_components/{path:path}/subtitles-octopus.js")
async def subtitles_octopus_js(request: Request, response: Response):
    try:
        source_path = f"{request.url.path}?{request.url.query}" if request.url.query else request.url.path
        request_url = EMBY_SERVER_URL + source_path
        logger.info(f"JSURL: {request_url}")
        server_response = requests.get(url=request_url, headers=request.headers)
    except Exception as e:
        logger.exception("获取原始JS出错")
        return ""
    try:
        content = server_response.content.decode("utf-8")
        content = insert_str(content, INSERT_JS, "function(options){")
        return Response(content=content)
    except Exception as e:
        logger.exception("处理出错，返回原始内容")
        # logger.error(f"处理出错，返回原始内容 : \n{traceback.format_exc()}")
        return Response(content=server_response.content)



#/videos/(.*)/Subtitles/(.*)/(Stream.ass|Stream.ssa|Stream.srt) Emby
#/videos/(.*)/Subtitles/(.*)/(Stream.ass|Stream.ssa|Stream.srt|Stream.subrip) 新版emby
#/videos/(.*)/Subtitles/(.*)/(Stream.) infuse
#/v/api/v1/subtitle/dl/(.*) 飞牛
@app.get("/{path:path}/Stream.")
@app.get("/{path:path}/Stream.ass")
@app.get("/{path:path}/Stream.ssa")
@app.get("/{path:path}/Stream.srt")
@app.get("/{path:path}/Stream.subrip")

@app.get("/{path:path}/stream.")
@app.get("/{path:path}/stream.ass")
@app.get("/{path:path}/stream.ssa")
@app.get("/{path:path}/stream.srt")
@app.get("/{path:path}/stream.subrip")
@app.get("/v/api/v1/subtitle/dl/{subtitle}")
# @app.get("{path:path}")
async def proxy_pass(request: Request, response: Response ):
    try:
        source_path = f"{request.url.path}?{request.url.query}" if request.url.query else request.url.path
        request_url = EMBY_SERVER_URL + source_path
        logger.info(f"字幕URL: {request_url}")
        server_response = requests.get(url=request_url, headers=request.headers)
    except Exception as e:
        logger.exception("获取原始字幕出错")
        return ""
    headers = {}
    try:
        raw_bytes = server_response.content
        hsv_s = config_manager.get("HDR_SATURATION")[0]
        hsv_v = config_manager.get("HDR_BRIGHTNESS")[0]
        error, srt, result_bytes = await process(raw_bytes, hsv_s, hsv_v)
        if not result_bytes:
            raise Exception(f"{error}，返回原始内容")
        if srt and ("user-agent" in request.headers) and ("infuse" in request.headers["user-agent"].lower()):
            raise Exception("infuse客户端，无法使用SRT转ASS功能，返回原始字幕")
        logger.info(f"字幕处理完成: {len(raw_bytes) / (1024 * 1024):.2f}MB ==> {len(result_bytes) / (1024 * 1024):.2f}MB")
        headers["content-type"] = "text/x-ssa"
        headers["error"] = base64.b64encode((error).encode("utf-8")).decode("ASCII")
        headers["srt"] = "true" if srt else "false"
        if "content-disposition" in server_response.headers:
            headers["content-disposition"] = server_response.headers["content-disposition"]
        return Response(content=result_bytes, headers=headers)
    except Exception as e:
        logger.exception("处理出错，返回原始内容")
        # logger.error(f"处理出错，返回原始内容 : \n{traceback.format_exc()}")
        excluded_headers = ["Content-Encoding", "Transfer-Encoding", "Content-Length", "Connection"]
        source_headers = {
            key: value
            for key, value in server_response.headers.items()
            if key not in excluded_headers
        }
        # print(f"source_headers: {source_headers}")
        return Response(content=server_response.content, status_code=server_response.status_code, headers=source_headers)


def get_server(port, server_loop, web_app):
    server_config = Config(
        app=web_app,
        host=None,
        port=port,
        log_level="info",
        loop=server_loop,
        ws_max_size=1024 * 1024 * 1024 * 1024,
    )
    return Server(server_config)


if __name__ == "__main__":
    logger.info("本地字体文件夹:" + ",".join(FONT_DIRS))
    os.makedirs(DEFAULT_FONT_PATH, exist_ok=True)
    asyncio.set_event_loop(MAIN_LOOP)
    ssl._create_default_https_context = ssl._create_unverified_context
    font_manager_instance = FontManager()
    subsetter_instance = SubSetter(font_manager_instance=font_manager_instance)
    event_handler = dirmonitor(font_manager_instance=font_manager_instance)  # 创建fonts字体文件夹监视实体
    event_handler.start()
    process = subsetter_instance.process  # 绑定函数
    process_subset = subsetter_instance.process_subset  # 绑定函数
    server_instance = get_server(8011, MAIN_LOOP, app)
    init_logger()
    MAIN_LOOP.run_until_complete(server_instance.serve())
    # # 关闭和清理资源
    event_handler.stop()  # 停止文件监视器
    event_handler.join()  # 等待文件监视退出
    font_manager_instance.close()  # 关闭aiohttp的session
    # subsetter_instance.close()  # 关闭进程池
    pending = asyncio.all_tasks(MAIN_LOOP)
    MAIN_LOOP.run_until_complete(asyncio.gather(*pending, return_exceptions=True))  # 等待异步任务结束
    MAIN_LOOP.stop()  # 停止事件循环
    MAIN_LOOP.close()  # 清理资源
