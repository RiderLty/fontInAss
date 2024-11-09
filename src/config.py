import asyncio
import os
import threading

ROOT_PATH = os.path.dirname(os.path.abspath(__file__))
DEFAULT_FONT_PATH = os.path.join(ROOT_PATH, r"../fonts")
FONT_MAP_PATH = os.path.join(ROOT_PATH, r"../fontMap.json")
LOCAL_FONT_MAP_PATH = os.path.join(ROOT_PATH, r"../localFontMap.json")
externalFonts = []

# 检查事件循环是否已经存在
if not asyncio.get_event_loop().is_running():
    # 启动后台事件循环,用来协助某些在多线程中需要的额外操作
    loop = asyncio.new_event_loop()
    threading.Thread(target=loop.run_forever, daemon=True).start()