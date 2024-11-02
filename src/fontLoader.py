import logging
import copy
import os
import traceback
import requests
from io import BytesIO
from fontTools.ttLib import TTCollection
import utils

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

@utils.printPerformance
def loadFont(fontName, externalFonts, fontPathMap, fontCache, FONT_TTL):

    if fontName in fontCache:
        cachedResult = fontCache[fontName]
        #刷新字体缓存过期时间
        fontCache.touch(fontName, expire= FONT_TTL)
        logger.info(f"{fontName} 字体缓存命中 - 占用: {len(cachedResult[0]) / (1024 * 1024):.2f}MB")
        return copy.deepcopy(cachedResult)

    try:
        if fontName in externalFonts:
            path = externalFonts[fontName]
            logger.info(f"从本地加载字体 {path}")
            if path.lower().startswith("http"):
                fontBytes = requests.get(path).content
            else:
                fontBytes = open(path, "rb").read()
        elif fontName in fontPathMap:
            path = fontPathMap[fontName]
            logger.info(f"从网络加载字体 https://fonts.storage.rd5isto.org{path}")
            fontBytes = requests.get(
                "https://fonts.storage.rd5isto.org" + path
            ).content

            # 构造完整的本地路径
            file_path = os.path.join("../fonts/download", path.lstrip('/'))
            # 确保路径中的文件夹存在
            local_path = os.path.dirname(file_path)
            os.makedirs(local_path, exist_ok=True)
            # 保存到本地
            with open(file_path, "wb") as f:
                f.write(fontBytes)
            logger.info(f"字体已下载到本地 {file_path}")
        else:
            return None

        if fontBytes[:4] == b"ttcf":
            fontInIO = BytesIO(fontBytes)
            ttc = TTCollection(fontInIO)
            for index, font in enumerate(ttc.fonts):
                for record in font["name"].names:
                    if record.nameID == 1 and str(record).strip() == fontName:
                        fontCache.set(fontName, [fontBytes, index], expire=FONT_TTL)
                        return copy.deepcopy([fontBytes, index])
        else:
            fontCache.set(fontName, [fontBytes, 0], expire=FONT_TTL)
            return copy.deepcopy([fontBytes, 0])
    except Exception as e:
        logger.error(f"加载字体出错 {fontName} : \n{traceback.format_exc()}")
        return None