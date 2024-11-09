import asyncio
import logging
import traceback
import aiofiles
import requests
import utils
import config

logger = logging.getLogger(f'{"main"}:{"loger"}')


# def __init__(externalFonts={}) -> None:
#     """除了使用脚本附带的的字体外，可载入额外的字体，格式为 { 字体名称：路径 | http url }"""
#     externalFonts = makeFontMap(externalFonts)
#     with open("fontMap.json", "r", encoding="UTF-8") as f:
#         fontPathMap = makeFontMap(
#             json.load(f)
#         )


def makeFontMap(data):
    """
    {
        /path/to/ttf/or/otf : {
            size: 62561,
            fonts:[
                YAHEI,
                FANGSONG,
                ...
            ]
        }
    }
    """
    font_file_map = {}
    font_miniSize = {}
    for path, info in data.items():
        for font_name in info["fonts"]:
            if font_name in font_file_map and font_miniSize[font_name] <= info["size"]:
                continue
            font_file_map[font_name] = path
            font_miniSize[font_name] = info["size"]
    return font_file_map


async def save_to_disk(path, fontBytes):
    # print("我要等100秒再写入" + str(path))
    # await asyncio.sleep(100)
    async with aiofiles.open(path, "wb") as f:
        await f.write(fontBytes)
        logger.info(f"字体已保存到本地 {path}")


@utils.printPerformance
def loadFont(fontName, externalFonts, fontPathMap):
    try:
        if fontName in externalFonts:
            path = externalFonts[fontName]
            logger.info(f"从本地加载字体 {path}")
            return open(path, "rb").read()
        elif fontName in fontPathMap:
            path = fontPathMap[fontName]
            logger.info(f"从网络加载字体 https://fonts.storage.rd5isto.org{path}")
            fontBytes = requests.get("https://fonts.storage.rd5isto.org" + path, timeout=10).content

            # 判断字体的文件夹是否存在
            file_path = utils.exist_path(config.DEFAULT_FONT_PATH, path)

            # 协程保存到本地,直接返回 fontBytes,减少因为写入时间而增加的总处理时长
            asyncio.run_coroutine_threadsafe(save_to_disk(file_path, fontBytes), config.loop)
            # print("我先走了：" + str(file_path))
            return fontBytes
        else:
            return None
    except Exception as e:
        logger.error(f"加载字体出错 {fontName} : \n{traceback.format_exc()}")
        return None
