import hashlib
import json
import logging
import os
import re
import time
import traceback

import chardet
from fontTools.ttLib import TTFont, TTCollection

import assSubsetter
import fontLoader
import hdrify
from config import LOCAL_FONT_MAP_PATH

logger = logging.getLogger(f'{"main"}:{"loger"}')


def getAllFiles(path):
    Filelist = []
    for home, dirs, files in os.walk(path):
        for filename in files:
            Filelist.append(os.path.join(home, filename))
    return Filelist


def pathReplacer(path):
    # return path.replace("E:\\", "/").replace("\\", "/")
    return path


def updateFontMap(dirPathList, old={}):
    fontMap = {}
    for dirPath in dirPathList:
        for file in getAllFiles(dirPath):
            if pathReplacer(file) in old:
                fontMap[pathReplacer(file)] = old[pathReplacer(file)]
            else:
                try:
                    fonts = None
                    if (
                            file.lower().endswith("ttc")
                            or file.lower().endswith("ttf")
                            or file.lower().endswith("otf")
                    ):
                        logger.info(f"更新外部字体 {file}")
                        with open(file, "rb") as f:
                            f.seek(0)
                            sfntVersion = f.read(4)
                            if sfntVersion == b"ttcf":
                                fonts = TTCollection(file).fonts
                            else:
                                fonts = [TTFont(file)]
                    if fonts:
                        names = set()
                        for font in fonts:
                            for record in font["name"].names:
                                if record.nameID == 1:  # Font Family name
                                    names.add(str(record).strip())
                        fontMap[pathReplacer(file)] = {
                            "size": os.path.getsize(file),
                            "fonts": list(names),
                        }

                except Exception as e:
                    logger.error(f"更新外部字体出错 {file} : {str(e)}")
    return fontMap


def updateLocal(fontDirList):
    """更新本地字体库"""
    logger.info("更新本地字体库中...")
    with open(LOCAL_FONT_MAP_PATH, "r", encoding="UTF-8") as f:
        localFonts = updateFontMap(fontDirList, json.load(f))

    with open(LOCAL_FONT_MAP_PATH, "w", encoding="UTF-8") as f:
        json.dump(localFonts, f, indent=4, ensure_ascii=True)
    externalFonts = fontLoader.makeFontMap(localFonts)
    return externalFonts
    # return JSONResponse(localFonts)
    # return externalFonts


def printPerformance(func: callable) -> callable:
    def wrapper(*args, **kwargs):
        start = time.perf_counter_ns()
        result = func(*args, **kwargs)
        duration = (time.perf_counter_ns() - start) / 1000000
        logger.info(
            f"{func.__name__}{args[0:1]}{kwargs} 用时 {duration:.2f}ms"
        )
        return result

    return wrapper

def isSRT(text):
    srt_pattern = r"@\d+@\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}@"
    matches = re.findall(srt_pattern, "@".join(text.splitlines()))
    return len(matches) > 0


def srt2ass(srtText):
    srtText = srtText.replace("\r", "")
    lines = [x.strip() for x in srtText.split("\n") if x.strip()]
    subLines = ""
    tmpLines = ""
    lineCount = 0

    for ln in range(len(lines)):
        line = lines[ln]
        if line.isdigit() and re.match("-?\d\d:\d\d:\d\d", lines[(ln + 1)]):
            if tmpLines:
                subLines += tmpLines.replace("\n", "\\n") + "\n"
            tmpLines = ""
            lineCount = 0
            continue
        else:
            if re.match("-?\d\d:\d\d:\d\d", line):
                line = line.replace("-0", "0")
                tmpLines += "Dialogue: 0," + line + ",Default,,0,0,0,,"
            else:
                if lineCount < 2:
                    tmpLines += line
                else:
                    tmpLines += "\n" + line
            lineCount += 1
        ln += 1

    subLines += tmpLines + "\n"

    subLines = re.sub(r"\d(\d:\d{2}:\d{2}),(\d{2})\d", "\\1.\\2", subLines)
    subLines = re.sub(r"\s+-->\s+", ",", subLines)
    # replace style
    subLines = re.sub(r"<([ubi])>", "{\\\\\g<1>1}", subLines)
    subLines = re.sub(r"</([ubi])>", "{\\\\\g<1>0}", subLines)
    subLines = re.sub(
        r'<font\s+color="?#(\w{2})(\w{2})(\w{2})"?>', "{\\\\c&H\\3\\2\\1&}", subLines
    )
    subLines = re.sub(r"</font>", "", subLines)

    head_str = (
            """[Script Info]
    ; This is an Advanced Sub Station Alpha v4+ script.
    Title:
    ScriptType: v4.00+
    Collisions: Normal
    PlayDepth: 0

    [V4+ Styles]
    """
            + os.environ.get("SRT_2_ASS_FORMAT")
            + "\n"
            + os.environ.get("SRT_2_ASS_STYLE")
            + """

    [Events]
    Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
    """
    )

    # Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
    # Style: Default,楷体,20,&H03FFFFFF,&H00FFFFFF,&H00000000,&H02000000,-1,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1
    output_str = head_str + "\n" + subLines
    # print(output_str)
    os.getenv("DEV") == "true" and logger.debug("SRT转ASS\n" + output_str)
    return output_str


def bytes2str(bytes):
    result = chardet.detect(bytes)
    logger.info(f"判断编码:{str(result)}")
    return bytes.decode(result["encoding"])

def split_ass_text(ass_text_chunk):
    parts = ass_text_chunk.split("[Events]")
    if len(parts) == 2:
        return parts  # 正常返回 head 和 tai
    else:
        # 如果没有找到 "[Events]"，可以返回一个默认值或抛出异常
        return "", ass_text_chunk  # 返回空的 head 和原始 chunk 作为 tai

def process(pool, sub_HNmae, assBytes, externalFonts, fontPathMap, subCache, fontCache):
    devFlag = (
            os.getenv("DEV") == "true"
            and os.path.exists("DEV")
            and len(os.listdir("DEV")) == 1
    )
    start = time.time()

    if devFlag:
        logger.debug("DEV模式 使用字幕" + os.path.join("DEV", os.listdir("DEV")[0]))
        with open(
                os.path.join("DEV", os.listdir("DEV")[0]),
                "rb",
        ) as f:
            assBytes = f.read()
            assText = bytes2str(assBytes)
    else:  # 非DEV模式，才使用字幕缓存+
        if sub_HNmae in subCache:
            cachedResult = subCache[sub_HNmae]
            # 刷新字幕缓存过期时间
            subCache[sub_HNmae] = cachedResult
            logger.info(f"字幕缓存命中 - 占用: {len(cachedResult[1]) / (1024 * 1024):.2f}MB")
            return cachedResult[0], cachedResult[1]
        assText = bytes2str(assBytes)
    os.getenv("DEV") == "true" and logger.debug("原始字幕\n" + assText)

    srt = isSRT(assText)

    if srt:
        if os.environ.get("SRT_2_ASS_FORMAT") and os.environ.get("SRT_2_ASS_STYLE"):
            logger.info("SRT ===> ASS")
            assText = srt2ass(assText)
        else:
            logger.info("未开启SRT转ASS")
            return (True, assText.encode("UTF-8-sig"))

    if "[Fonts]\n" in assText:
        raise ValueError("已有内嵌字幕")

    if os.getenv("HDR"):
        logger.info(f"HDR适配")
        try:
            assText = hdrify.ssaProcessor(assText, int(os.getenv("HDR")))
        except Exception as e:
            logger.error(f"HDR适配出错: \n{traceback.format_exc()}")

    font_charList = assSubsetter.analyseAss(assText)
    errors, embedFontsText = assSubsetter.makeEmbedFonts(pool, font_charList, externalFonts, fontPathMap, fontCache)
    head, tai = assText.split("[Events]")
    # print(assText)
    logger.info(f"嵌入完成 用时 {time.time() - start:.2f}s - 生成Fonts部分大小: {len(embedFontsText) / (1024 * 1024):.2f}MB")
    len(errors) != 0 and logger.info("ERRORS:" + "\n".join(errors))
    resultText = head + embedFontsText + "\n[Events]" + tai

    resultBytes = resultText.encode("UTF-8-sig")

    subCache[sub_HNmae] = (srt, resultBytes)

    # os.getenv("DEV") == "true" and logger.debug("处理后字幕\n" + resultText)
    return (srt, resultBytes)

#计算文件哈希值
def bytes_to_hashName(bytes, hash_algorithm='sha256'):
    hash_func = {
        'md5': hashlib.md5,
        'sha1': hashlib.sha1,
        'sha256': hashlib.sha256
    }.get(hash_algorithm, hashlib.sha256)()  # 默认使用 SHA-256
    hash_func.update(bytes)
    return hash_func.hexdigest()

def tag_to_integer(tag_string):
    """
    SubsetInputSets的TAG
    https://harfbuzz.github.io/harfbuzz-hb-subset.html
    TAG计算方式
    https://harfbuzz.github.io/harfbuzz-hb-common.html#HB-TAG:CAPS
    计算公式：
    #define HB_TAG(c1,c2,c3,c4) ((hb_tag_t)((((uint32_t)(c1)&0xFF)<<24)|(((uint32_t)(c2)&0xFF)<<16)|(((uint32_t)(c3)&0xFF)<<8)|((uint32_t)(c4)&0xFF)))
    将一个 4 个字符的字符串转换为 hb_tag_t 整数值。
    参数：
    tag_string：一个 4 个字符的字符串。
    返回：
    对应的 hb_tag_t 整数值。
    """
    if len(tag_string) != 4:
        raise ValueError("输入的字符串必须恰好包含 4 个字符。")

    # 将字符串转换为对应的 hb_tag_t 整数值
    return ((ord(tag_string[0]) & 0xFF) << 24) | \
           ((ord(tag_string[1]) & 0xFF) << 16) | \
           ((ord(tag_string[2]) & 0xFF) << 8) | \
           (ord(tag_string[3]) & 0xFF)