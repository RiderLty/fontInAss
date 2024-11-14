import builtins
import asyncio
import logging
import os

import coloredlogs

logger = logging.getLogger(f'{"main"}:{"loger"}')
fmt = f"🤖 %(asctime)s.%(msecs)03d .%(levelname)s \t%(message)s"
coloredlogs.install(level=logging.DEBUG, logger=logger, milliseconds=True, datefmt="%X", fmt=fmt)


def custom_print(*args, **kwargs):
    logger.info("".join([str(x) for x in args]))


original_print = builtins.print
builtins.print = custom_print


ROOT_PATH = os.path.dirname(os.path.abspath(__file__))
DEFAULT_FONT_PATH = os.path.join(ROOT_PATH, r"../fonts")

FONT_DIRS = [DEFAULT_FONT_PATH]

if os.environ.get("FONT_DIRS"):
    for dirPath in os.environ.get("FONT_DIRS").split(";"):
        if dirPath.strip() != "" and os.path.exists(dirPath):
            FONT_DIRS.append(dirPath.strip())

ONLINE_FONTS_PATH = os.path.join(ROOT_PATH, r"../onlineFonts.json")
LOCAL_FONTS_PATH = os.path.join(ROOT_PATH, r"../localFonts.json")

MAIN_LOOP = asyncio.new_event_loop()
cpu_count = int(os.cpu_count())
POOL_CPU_MAX = int(os.environ.get("POOL_CPU_MAX", default=cpu_count))
if POOL_CPU_MAX >= cpu_count or POOL_CPU_MAX <= 0:
    POOL_CPU_MAX = cpu_count

EMBY_SERVER_URL = os.environ.get("EMBY_SERVER_URL", default="尚未EMBY_SERVER_URL环境变量")

SUB_CACHE_SIZE = int(os.environ.get("SUB_CACHE_SIZE", default=50))
SUB_CACHE_TTL = int(os.environ.get("SUB_CACHE_TTL", default=60)) * 60

FONT_CACHE_SIZE = int(os.environ.get("FONT_CACHE_SIZE", default=30))
FONT_CACHE_TTL = int(os.environ.get("FONT_CACHE_TTL", default=30)) * 60

SRT_2_ASS_FORMAT = os.environ.get("SRT_2_ASS_FORMAT", None)
SRT_2_ASS_STYLE = os.environ.get("SRT_2_ASS_STYLE", None)

DEBUG = os.environ.get("DEBUG", "") != ""
HDR = int(os.environ.get("DEBUG", -1))