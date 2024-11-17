import hashlib
import os

import aiofiles
import os
import re
import chardet
import ass as ssa
from constants import *

def getAllFiles(path):
    Filelist = []
    for home, _, files in os.walk(path):
        for filename in files:
            Filelist.append(os.path.join(home, filename))
    return Filelist


async def saveToDisk(path, fontBytes):
    async with aiofiles.open(path, "wb") as f:
        await f.write(fontBytes)
        logger.info(f"网络字体已保存\t\t[{path}]")
        

def tagToInteger(tagString):
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
    if len(tagString) != 4:
        raise ValueError("输入的字符串必须恰好包含 4 个字符。")

    # 将字符串转换为对应的 hb_tag_t 整数值
    return ((ord(tagString[0]) & 0xFF) << 24) | \
           ((ord(tagString[1]) & 0xFF) << 16) | \
           ((ord(tagString[2]) & 0xFF) << 8) | \
           (ord(tagString[3]) & 0xFF)

def bytesToHashName(bytes, hash_algorithm='sha256'):
    hash_func = {
        'md5': hashlib.md5,
        'sha1': hashlib.sha1,
        'sha256': hashlib.sha256
    }.get(hash_algorithm, hashlib.sha256)()  # 默认使用 SHA-256
    hash_func.update(bytes)
    return hash_func.hexdigest()

def analyseAss(ass_str):
    """分析ass文件 返回 字体：{unicodes}"""
    sub = ssa.parse_string(ass_str)
    style_fontName = {}  # 样式 => 字体
    font_charList = {}  # 字体 => unicode list
    for style in sub.styles:
        styleName = style.name.strip()
        fontName = style.fontname.strip().replace("@", "")
        style_fontName[styleName] = fontName
    for event in sub.events:
        # logger.debug("原始Event文本 : " + event.text)
        eventStyle = event.style.replace("*", "")
        if eventStyle not in style_fontName:
            logger.error(f"event[{eventStyle}]使用了未知样式")
            continue
        fontLine = r"{\fn" + style_fontName[eventStyle] + "}" + event.text
        # 在首部加上对应的style的字体
        for inlineStyle in re.findall(r"({[^\\]*\\r[^}|\\]+[\\|}])", event.text):  # 用于匹配 {\rXXX} 其中xxx为style名称
            # {\r} 会有这种 空的
            styleName = re.findall(r"{[^\\]*\\r([^}|\\]+)[\\|}]", inlineStyle)[0]
            if styleName in style_fontName:
                fontLine = fontLine.replace(inlineStyle, r"{\fn" + style_fontName[styleName] + "}")  # 将内联style，改为指定字体名称的形式
            else:
                logger.error(f"event内联[{styleName}]使用了未知样式")
        res = [(fn.groups()[0], fn.start(), fn.end()) for fn in re.finditer(r"{[^\\]*\\fn([^}|\\]*)[\\|}]", fontLine)]
        # 获取所有的内联字体位置名称信息
        for i in range(len(res)):
            fontName = res[i][0].replace("@", "")
            textStart = res[i][2]
            textEnd = None if i == len(res) - 1 else res[i + 1][1]
            text = re.sub(r"(?<!{)\{\\([^{}]*)\}(?!})", "", fontLine[textStart:textEnd])
            logger.debug(f"{fontName} : {fontLine[textStart:textEnd]}  ==> {text}")
            for ch in text:
                if fontName not in font_charList:
                    font_charList[fontName] = set()
                font_charList[fontName].add(ord(ch))
    return font_charList


def isSRT(text):
    srt_pattern = r"@\d+@\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}@"
    matches = re.findall(srt_pattern, "@".join(text.splitlines()))
    return len(matches) > 0

def srtToAss(srtText):
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

    head_str = ("""[Script Info]
; This is an Advanced Sub Station Alpha v4+ script.
Title:
ScriptType: v4.00+
Collisions: Normal
PlayDepth: 0

[V4+ Styles]
"""
        + SRT_2_ASS_FORMAT
        + "\n"
        + SRT_2_ASS_STYLE
        + """

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    )
    # Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
    # Style: Default,楷体,20,&H03FFFFFF,&H00FFFFFF,&H00000000,&H02000000,-1,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1
    output_str = head_str + "\n" + subLines
    logger.debug("SRT转ASS\n" + output_str)
    return output_str
    
def bytesToStr(bytes):
    result = chardet.detect(bytes)
    logger.info(f"判断编码:{str(result)}")
    return bytes.decode(result["encoding"])
