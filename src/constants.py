import os
import asyncio
import logging
import builtins
import coloredlogs
from dataclasses import dataclass, field
from typing import Any

@dataclass
class Result:
    code: int
    message: str | list | None
    data: Any
    extra: dict = field(default_factory=dict)

logger = logging.getLogger(f'{"main"}:{"loger"}')
fmt = f"🤖 %(asctime)s.%(msecs)03d .%(levelname)s \t%(message)s"
coloredlogs.install(level=logging.DEBUG, logger=logger, milliseconds=True, datefmt="%X", fmt=fmt)

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
assert LOG_LEVEL in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], f"LOG_LEVEL={LOG_LEVEL}, 可用值 DEBUG INFO WARNING ERROR CRITICAL"
logger.setLevel(LOG_LEVEL)

def custom_print(*args, **kwargs):
    logger.info("".join([str(x) for x in args]))

original_print = builtins.print
builtins.print = custom_print

ROOT_PATH = os.path.dirname(os.path.abspath(__file__))
DEFAULT_FONT_PATH = os.path.join(os.path.dirname(ROOT_PATH), r"fonts")
DATA_PATH = os.path.join(os.path.dirname(ROOT_PATH), r"data")
LOGS_PATH = os.path.join(os.path.dirname(ROOT_PATH), r"logs")
FONT_DIRS = [DEFAULT_FONT_PATH]

if os.environ.get("FONT_DIRS"):
    for dirPath in os.environ.get("FONT_DIRS").split(";"):
        if dirPath.strip() != "" and os.path.exists(dirPath):
            FONT_DIRS.append(dirPath.strip())

CUSTOM_ONLINE_FONTS = os.path.join(DATA_PATH, r"customOnlineFonts.json")
ONLINE_FONTS_DB_PATH = os.path.join(os.path.dirname(ROOT_PATH), r"onlineFonts.json")

LOCAL_FONTS_DB_VERSION = "2.6"
LOCAL_FONTS_DB_PATH = os.path.join(DATA_PATH, f"localFonts.ver.{LOCAL_FONTS_DB_VERSION}.db")

os.makedirs(DATA_PATH, exist_ok=True)
os.makedirs(LOGS_PATH, exist_ok=True)
MAIN_LOOP = asyncio.new_event_loop()
cpu_count = int(os.cpu_count())

FONTS_TYPE = os.environ.get("FONTS_TYPE", ["ttc", "ttf", "otf"])

ERROR_DISPLAY_IGNORE_GLYPH = os.environ.get("ERROR_DISPLAY_IGNORE_GLYPH", default="False") == "True"

PUNCTUATION_UNICODES = set()
ranges = [
    # 基本拉丁文标点符号 (ASCII)
    (0x0020, 0x007F),
    # 拉丁文附加标点符号
    (0x00A0, 0x00FF),
    # 中日韩字符标点符号
    (0x3000, 0x303F),
    # 一般标点符号
    (0x2000, 0x206F),
    # 数学符号
    (0x2000, 0x22FF),
    # 全角标点符号
    (0xFF00, 0xFFEF),
]
for start, end in ranges:
    for code_point in range(start, end + 1):
        PUNCTUATION_UNICODES.add(code_point)

# miss_logs settings
MISS_LOGS_SIZE = int(os.environ.get("MISS_LOGS_SIZE", default=20))  # MB
MISS_LOGS_DB_PATH = os.path.join(DATA_PATH, "miss_logs.db")
MISS_LOGS_TXT_PATH = os.path.join(LOGS_PATH, "miss_logs.txt")
