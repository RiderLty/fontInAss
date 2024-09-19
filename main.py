import builtins
import contextlib
import datetime
import io
import logging
import coloredlogs
import chardet
import warnings


logger = logging.getLogger(f'{"main"}:{"loger"}')
fmt = f"🤖 %(asctime)s.%(msecs)03d .%(levelname)s \t%(message)s"
coloredlogs.install(
    level=logging.DEBUG, logger=logger, milliseconds=True, datefmt="%X", fmt=fmt
)


original_print = builtins.print


def custom_print(*args, **kwargs):
    logger.info("".join([str(x) for x in args]))


builtins.print = custom_print
# exit(0)

from io import BytesIO, StringIO
import threading
import traceback

# from easyass import *
import ass as ssa
from fastapi.responses import JSONResponse
from fontTools.ttLib import TTFont, TTCollection
from fontTools.subset import Subsetter

import os
import time
import json
import requests
import queue

import re
from uvicorn import Config, Server
from fastapi import FastAPI, Query, Request, Response
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from cachetools import LRUCache
import copy


import asyncio

import ssl



import ass as ssa
import numpy as np

import warnings
warnings.filterwarnings('ignore')

from colour import RGB_Colourspace
from colour.models import eotf_inverse_BT2100_PQ, sRGB_to_XYZ, XYZ_to_xyY, xyY_to_XYZ, XYZ_to_RGB, \
    RGB_COLOURSPACE_BT2020, eotf_BT2100_PQ

COLOURSPACE_BT2100_PQ = RGB_Colourspace(
    name='COLOURSPACE_BT2100',
    primaries=RGB_COLOURSPACE_BT2020.primaries,
    whitepoint=RGB_COLOURSPACE_BT2020.whitepoint,
    matrix_RGB_to_XYZ=RGB_COLOURSPACE_BT2020.matrix_RGB_to_XYZ,
    matrix_XYZ_to_RGB=RGB_COLOURSPACE_BT2020.matrix_XYZ_to_RGB,
    cctf_encoding=eotf_inverse_BT2100_PQ,
    cctf_decoding=eotf_BT2100_PQ,
)



serverLoop = asyncio.new_event_loop()
asyncio.set_event_loop(serverLoop)
ssl._create_default_https_context = ssl._create_unverified_context


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


cacheSize = int(os.environ.get("CACHE_SIZE") or 32)
fontCache = LRUCache(maxsize=cacheSize)
subCache = LRUCache(maxsize=cacheSize)


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


def printPerformance(func: callable) -> callable:
    def wrapper(*args, **kwargs):
        start = time.perf_counter_ns()
        result = func(*args, **kwargs)
        logger.info(
            f"{func.__name__}{args[1:]}{kwargs} 耗时 {(time.perf_counter_ns() - start) / 1000000} ms"
        )
        return result

    return wrapper


class fontLoader:
    def __init__(self, externalFonts={}) -> None:
        """除了使用脚本附带的的字体外，可载入额外的字体，格式为 { 字体名称：路径 | http url }"""
        self.externalFonts = makeFontMap(externalFonts)
        with open("fontMap.json", "r", encoding="UTF-8") as f:
            self.fontPathMap = makeFontMap(
                json.load(f)
            )

    @printPerformance
    def loadFont(self, fontName):
        cachedResult = fontCache.get(fontName)
        if cachedResult:
            logger.info(f"{fontName} 字体缓存命中")
            return copy.deepcopy(cachedResult)

        try:
            if fontName in self.externalFonts:
                path = self.externalFonts[fontName]
                logger.info(f"从本地加载字体 {path}")
                if path.lower().startswith("http"):
                    fontBytes = requests.get(path).content
                else:
                    fontBytes = open(path, "rb").read()
            elif fontName in self.fontPathMap:
                path = self.fontPathMap[fontName]
                fontBytes = requests.get(
                    "https://fonts.storage.rd5isto.org" + path
                ).content
            else:
                return None
            bio = BytesIO()
            bio.write(fontBytes)
            bio.seek(0)
            if fontBytes[:4] == b"ttcf":
                ttc = TTCollection(bio)
                for font in ttc.fonts:
                    for record in font["name"].names:
                        if record.nameID == 1 and str(record).strip() == fontName:
                            fontCache[fontName] = font
                            return font
            else:
                fontCache[fontName] = TTFont(bio)
                return copy.deepcopy(fontCache[fontName])
        except Exception as e:
            logger.error(f"加载字体出错 {fontName} : \n{traceback.format_exc()}")
            return None


class hdrify:
    """
    https://github.com/gky99/ssaHdrify
    """

    def __init__(self) -> None:
        pass

    def ssaProcessor(self, assText: str,srgb_brightness = 100):
        sub = ssa.parse_string(assText)
        for s in sub.styles:
            self.transformColour(s.primary_color,srgb_brightness)
            self.transformColour(s.secondary_color,srgb_brightness)
            self.transformColour(s.outline_color,srgb_brightness)
            self.transformColour(s.back_color,srgb_brightness)
        for e in sub.events:
            self.transformEvent(e,srgb_brightness)

        out = StringIO()
        sub.dump_file(out)
        return out.getvalue()


        # output_fname = os.path.splitext(fname)
        # output_fname = output_fname[0] + ".hdr.ass"

        # with open(output_fname, "w", encoding="utf_8_sig") as f:
        #     sub.dump_file(f)
        #     print(f"Wrote {output_fname}")
    
    
    def transformColour(self,colour,srgb_brightness):
        rgb = (colour.r, colour.g, colour.b)
        transformed = self.sRgbToHdr(rgb,srgb_brightness)
        colour.r = transformed[0]
        colour.g = transformed[1]
        colour.b = transformed[2]
    
    
    
    def transformEvent(self, event,srgb_brightness):
        line = event.text
        matches = []
        for match in re.finditer(r"\\[0-9]?c&H([0-9a-fA-F]{2,})&", line):
            start = match.start(1)
            end = match.end(1)
            hex_colour = match.group(1)
            hex_colour.rjust(6, "0")
            b = int(hex_colour[0:2], 16)
            g = int(hex_colour[2:4], 16)
            r = int(hex_colour[4:6], 16)
            (r, g, b) = self.sRgbToHdr((r, g, b),srgb_brightness)
            hex_colour = "{:02x}{:02x}{:02x}".format(b, g, r)
            matches.append((start, end, hex_colour.upper()))

        for start, end, hex_colour in matches:
            line = line[:start] + hex_colour + line[end:]

        event.text = line

    def sRgbToHdr(
        self, source: tuple[int, int, int] , srgb_brightness
    ) -> tuple[int, int, int]:
        """
        Convert RGB color in SDR color space to HDR color space.

        How it works:
        1. Convert the RGB color to reference xyY color space to get absolute chromaticity and linear luminance response
        2. Time the target brightness of SDR color space to the Y because Rec.2100 has an absolute luminance
        3. Convert the xyY color back to RGB under Rec.2100/Rec.2020 color space.

        Notes:
        -  Unlike sRGB and Rec.709 color space which have their OOTF(E) = EOTF(OETF(E)) equals or almost equals to y = x,
            it's OOTF is something close to gamma 2.4. Therefore, to have matched display color for color in SDR color space
            the COLOURSPACE_BT2100_PQ denotes a display color space rather than a scene color space. It wasted me quite some
            time to figure that out :(
        -  Option to set output luminance is removed because PQ has an absolute luminance level, which means any color in
            the Rec.2100 color space will be displayed the same on any accurate display regardless of the capable peak
            brightness of the device if no clipping happens. Therefore, the peak brightness should always target 10000 nits
            so the SDR color can be accurately projected to the sub-range of Rec.2100 color space
        args:
        colour -- (0-255, 0-255, 0-255)
        """
        normalized_sdr_color = np.array(source) / 255
        xyY_sdr_color = XYZ_to_xyY(
            sRGB_to_XYZ(normalized_sdr_color, apply_cctf_decoding=True)
        )

        xyY_hdr_color = xyY_sdr_color.copy()
        target_luminance = xyY_sdr_color[2] * srgb_brightness
        xyY_hdr_color[2] = target_luminance

        output = XYZ_to_RGB(
            xyY_to_XYZ(xyY_hdr_color),
            colourspace=COLOURSPACE_BT2100_PQ,
            apply_cctf_encoding=True,
        )
        output = np.round(output * 255)
        return (int(output[0]), int(output[1]), int(output[2]))


class assSubsetter:
    def __init__(self, fontLoader) -> None:
        self.fontLoader = fontLoader

    # def analyseAssVer0(self, ass_str):
    #     """分析ass文件 返回 字体：{unicodes}"""
    #     ass_obj = Ass()
    #     ass_obj.parse(ass_str)
    #     style_fontName = {}  # 样式 => 字体
    #     font_charList = {}  # 字体 => unicode list
    #     for style in ass_obj.styles:
    #         styleName = style.Name.strip()
    #         fontName = style.Fontname.strip().replace("@", "")
    #         style_fontName[styleName] = fontName
    #         font_charList[fontName] = set()
    #     for event in ass_obj.events:
    #         fontName = style_fontName[event.Style.replace("*", "")]
    #         for ch in event.Text.dump():
    #             font_charList[fontName].add(ord(ch))
    #     for line in ass_str.splitlines():
    #         # 比较坑爹这里
    #         for match in re.findall(r"{[^\\]*\\fn([^}|\\]*)[\\|}]", line):
    #             fontName = match.replace("@", "")
    #             for ch in line:
    #                 if fontName not in font_charList:
    #                     font_charList[fontName] = set()
    #                 font_charList[fontName].add(ord(ch))
    #     return font_charList

    def analyseAss(self, ass_str):
        """分析ass文件 返回 字体：{unicodes}"""
        sub = ssa.parse_string(ass_str)
        style_fontName = {}  # 样式 => 字体
        font_charList = {}  # 字体 => unicode list
        for style in sub.styles:
            styleName = style.name.strip()
            fontName = style.fontname.strip().replace("@", "")
            style_fontName[styleName] = fontName
            font_charList[fontName] = set()
        for event in sub.events:
            os.getenv("DEV") == "true" and logger.debug("")
            os.getenv("DEV") == "true" and logger.debug("原始Event文本 : " + event.text)
            eventStyle =  event.style.replace("*","")
            if eventStyle not in style_fontName:
                logger.error(f"event[{eventStyle}]使用了未知样式")
                continue
            fontLine = r"{\fn" + style_fontName[eventStyle] + "}" + event.text
            # 在首部加上对应的style的字体
            for inlineStyle in re.findall(
                r"({[^\\]*\\r[^}|\\]*[\\|}])", event.text
            ):  # 用于匹配 {\rXXX} 其中xxx为style名称
                # {\r} 会有这种 空的
                styleName = re.findall(r"{[^\\]*\\r([^}|\\]*)[\\|}]", inlineStyle)[0]
                if styleName in style_fontName:
                    fontLine = fontLine.replace(
                        inlineStyle, r"{\fn" + style_fontName[styleName] + "}"
                    )  # 将内联style，改为指定字体名称的形式
                else:
                    logger.error(f"event内联[{styleName}]使用了未知样式")
            res = [
                (fn.groups()[0], fn.start(), fn.end())
                for fn in re.finditer(r"{[^\\]*\\fn([^}|\\]*)[\\|}]", fontLine)
            ]
            # 获取所有的内联字体位置名称信息
            for i in range(len(res)):
                fontName = res[i][0].replace("@", "")
                textStart = res[i][2]
                textEnd = None if i == len(res) - 1 else res[i + 1][1]
                text = re.sub(
                    r"(?<!{)\{\\([^{}]*)\}(?!})", "", fontLine[textStart:textEnd]
                )
                os.getenv("DEV") == "true" and logger.debug(
                    f"{fontName} :  {fontLine[textStart:textEnd]}  ===> {text}"
                )
                for ch in text:
                    if fontName not in font_charList:
                        font_charList[fontName] = set()
                    font_charList[fontName].add(ord(ch))
            # print("")
            # 最终获取 字体 : 文本code
        # print(font_charList)
        return font_charList

    def uuencode(self, binaryData):
        """编码工具"""
        OFFSET = 33
        encoded = []
        for i in range(0, (len(binaryData) // 3) * 3, 3):
            bytes_chunk = binaryData[i : i + 3]
            if len(bytes_chunk) < 3:
                bytes_chunk += b"\x00" * (3 - len(bytes_chunk))
            packed = int.from_bytes(bytes_chunk, "big")
            # packed = (packed & 0xFFFFFF)  # 确保只有24位
            six_bits = [((packed >> (18 - i * 6)) & 0x3F) for i in range(4)]
            encoded_group = "".join(chr(OFFSET + num) for num in six_bits)
            encoded.append(encoded_group)
        # print(f"输入({len(data)}){data} => {data[:(len(data) // 3) * 3]}|{data[(len(data) // 3) * 3:]}")
        last = None
        if len(binaryData) % 3 == 0:
            pass
        elif len(binaryData) % 3 == 1:
            last = binaryData[(len(binaryData) // 3) * 3 :] + b"\x00\x00"
            packed = int.from_bytes(last, "big")
            six_bits = [((packed >> (18 - i * 6)) & 0x3F) for i in range(4)]
            encoded_group = "".join(chr(OFFSET + num) for num in six_bits)[:2]
            encoded.append(encoded_group)
        elif len(binaryData) % 3 == 2:
            last = binaryData[(len(binaryData) // 3) * 3 :] + b"\x00"
            packed = int.from_bytes(last, "big")
            six_bits = [((packed >> (18 - i * 6)) & 0x3F) for i in range(4)]
            encoded_group = "".join(chr(OFFSET + num) for num in six_bits)[:3]
            encoded.append(encoded_group)
        encoded_lines = []
        for i in range(0, (len(encoded) // 20) * 20, 20):
            encoded_lines.append("".join(encoded[i : i + 20]))
        encoded_lines.append("".join(encoded[(len(encoded) // 20) * 20 :]))
        return "\n".join(encoded_lines)

    def makeOneEmbedFontsText(self, fontName, unicodeSet, resultQueue, sem):
        with sem:
            font = self.fontLoader.loadFont(fontName)
            if font == None:
                resultQueue.put((f"{fontName} miss", None))
            else:
                try:
                    originNames = font["name"].names

                    subsetter = Subsetter()
                    subsetter.populate(unicodes=unicodeSet)
                    subsetter.subset(font)

                    font["name"].names = originNames
                    fontOutIO = BytesIO()
                    font.save(fontOutIO)
                    enc = self.uuencode(fontOutIO.getvalue())
                    resultQueue.put((None, f"fontname:{fontName}_0.ttf\n{enc}\n"))
                except Exception as e:
                    logger.error(f"子集化{fontName}出错 : \n{traceback.format_exc()}")
                    resultQueue.put((f" {fontName} : {str(e)}", None))

    def makeEmbedFonts(self, font_charList):
        """对于给定的 字体:使用到的编码列表 返回编码后的，可嵌入ASS的文本"""
        embedFontsText = "[Fonts]\n"
        errors = []
        resultQueue = queue.Queue()
        sem = threading.Semaphore(8)
        for fontName, unicodeSet in font_charList.items():
            if len(unicodeSet) != 0:
                threading.Thread(
                    target=self.makeOneEmbedFontsText,
                    args=(fontName, unicodeSet, resultQueue, sem),
                ).start()
        for fontName, unicodeSet in font_charList.items():
            if len(unicodeSet) != 0:
                (err, result) = resultQueue.get()
                if err:
                    errors.append(err)
                else:
                    embedFontsText += result
        return errors, embedFontsText


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


fontDirList = [r"fonts"]

if os.environ.get("FONT_DIRS"):
    for dirPath in os.environ.get("FONT_DIRS").split(";"):
        if dirPath.strip() != "" and os.path.exists(dirPath):
            fontDirList.append(dirPath.strip())
logger.info("本地字体文件夹:" + ",".join(fontDirList))

if not os.path.exists("localFontMap.json"):
    with open("localFontMap.json", "w", encoding="UTF-8") as f:
        json.dump({}, f)

if not os.path.exists("fonts"):
    os.makedirs("fonts", exist_ok=True)

with open("localFontMap.json", "r", encoding="UTF-8") as f:
    localFonts = updateFontMap(fontDirList, json.load(f))

with open("localFontMap.json", "w", encoding="UTF-8") as f:
    json.dump(localFonts, f, indent=4, ensure_ascii=True)

asu = assSubsetter(fontLoader(externalFonts=localFonts))
hdr = hdrify()
app = FastAPI()

# @app.get("/update")


def updateLocal():
    """更新本地字体库"""
    logger.info("更新本地字体库中...")
    global asu
    with open("localFontMap.json", "r", encoding="UTF-8") as f:
        localFonts = updateFontMap(fontDirList, json.load(f))
    with open("localFontMap.json", "w", encoding="UTF-8") as f:
        json.dump(localFonts, f, indent=4, ensure_ascii=True)
    asu = assSubsetter(fontLoader(externalFonts=localFonts))
    return JSONResponse(localFonts)


def bytes2str(bytes):
    result = chardet.detect(bytes)
    logger.info(f"判断编码:{str(result)}")
    return bytes.decode(result["encoding"])


def process(assBytes):
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
    else:  # 非DEV模式，才使用字幕缓存
        cachedResult = subCache.get(assBytes)
        if cachedResult:
            logger.info("字幕缓存命中")
            return cachedResult[0], cachedResult[1]
        assText = bytes2str(assBytes)
    # os.getenv("DEV") == "true" and logger.debug("原始字幕\n" + assText)

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
            assText = hdr.ssaProcessor(assText,int(os.getenv("HDR")))
        except Exception as e:
            logger.error(f"HDR适配出错: \n{traceback.format_exc()}")

    font_charList = asu.analyseAss(assText)
    errors, embedFontsText = asu.makeEmbedFonts(font_charList)
    head, tai = assText.split("[Events]")
    logger.info(
        f"嵌入完成，用时 {time.time() - start:.2f}s \n生成Fonts {len(embedFontsText)}"
    )
    logger.info(f"生成Fonts部分长度 {len(embedFontsText)}")
    len(errors) != 0 and logger.info("ERRORS:" + "\n".join(errors))
    resultText = head + embedFontsText + "\n[Events]" + tai

    

    resultBytes = resultText.encode("UTF-8-sig")

    subCache[assBytes] = (srt, resultBytes)
    # os.getenv("DEV") == "true" and logger.debug("处理后字幕\n" + resultText)
    return (srt, resultBytes)


@app.post("/process_bytes")
async def process_bytes(request: Request):
    """传入字幕字节"""
    print(request.headers)
    subtitleBytes = await request.body()
    try:
        srt, bytes = process(subtitleBytes)
        return Response(
            content=bytes, headers={"Srt2Ass": str(srt), "fontinass-exception": "None"}
        )
    except Exception as e:
        logger.error(f"处理出错，返回原始内容 : \n{traceback.format_exc()}")
        return Response(
            content=subtitleBytes,
            headers={"Srt2Ass": str(False), "fontinass-exception": str(e)},
        )


@app.get("/process_url")
async def process_url(ass_url: str = Query(None)):
    """传入字幕url"""
    print("loading " + ass_url)
    try:
        subtitleBytes = requests.get(ass_url).content
        srt, bytes = process(subtitleBytes)
        return Response(
            content=bytes, headers={"Srt2Ass": str(srt), "fontinass-exception": "None"}
        )
    except Exception as e:
        logger.error(f"处理出错，返回原始内容 : \n{traceback.format_exc()}")
        return Response(
            content=subtitleBytes,
            headers={"Srt2Ass": str(False), "fontinass-exception": str(e)},
        )


# 手动修改此处，或者使用环境变量
EMBY_SERVER_URL = "尚未EMBY_SERVER_URL环境变量"


@app.get("/{path:path}")
async def proxy_pass(request: Request, response: Response):
    try:
        host = os.environ.get("EMBY_SERVER_URL") or EMBY_SERVER_URL
        url = (
            f"{request.url.path}?{request.url.query}"
            if request.url.query
            else request.url.path
        )
        embyRequestUrl = host + url
        logger.info(f"字幕URL:{embyRequestUrl}")
        serverResponse = requests.get(url=embyRequestUrl, headers=request.headers)
        copyHeaders = {key: str(value) for key, value in response.headers.items()}
    except Exception as e:
        info = f"fontinass获取原始字幕出错:{str(e)}"
        logger.error(info)
        return info
    try:
        logger.info(f"原始大小:{len(serverResponse.content)}")
        srt, bytes = process(serverResponse.content)
        logger.info(f"处理后大小:{len(bytes)}")
        copyHeaders["Content-Length"] = str(len(bytes))
        if srt:
            if (
                "user-agent" in request.headers
                and "infuse" in request.headers["user-agent"].lower()
            ):
                raise ValueError("infuse客户端，无法使用SRT转ASS功能，返回原始字幕")
        return Response(content=bytes)
    except Exception as e:
        logger.error(f"处理出错，返回原始内容 : \n{traceback.format_exc()}")
        return Response(content=serverResponse.content)


class MyHandler(FileSystemEventHandler):
    def on_created(self, event):
        updateLocal()

    def on_deleted(self, event):
        updateLocal()


def getServer(port):
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
    event_handler = MyHandler()
    observer = Observer()
    for fontDir in fontDirList:
        logger.info("监控中:" + os.path.abspath(fontDir))
        observer.schedule(event_handler, os.path.abspath(fontDir), recursive=True)
    observer.start()
    serverInstance = getServer(8011)
    init_logger()
    serverLoop.run_until_complete(serverInstance.serve())
    observer.stop()
    observer.join()
#ok
