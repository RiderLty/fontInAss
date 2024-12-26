import os
import re
import hashlib
import struct
import uuid
from pathlib import Path
import sys
import aiofiles
import chardet
import uharfbuzz
from constants import logger, SRT_2_ASS_FORMAT, SRT_2_ASS_STYLE, FONTS_TYPE


def makeMiniSizeFontMap(data):
    """
    {
        /path/to/ttf/or/otf : {
            size: 62561,
            fonts:{
                YAHEI:0,
                FANGSONG,5
            }
        }
    }
    转化为

    {
        fontname : [path,index]
    }

    """
    fontFileMap = {}
    fontMiniSize = {}
    for path in data.keys():
        size = data[path]["size"]
        for fontName, index in data[path]["fonts"].items():
            if fontName not in fontFileMap or fontMiniSize[fontName] > size:
                fontFileMap[fontName] = (path, index)
                fontMiniSize[fontName] = size
    return fontFileMap


def getAllFiles(path, types=FONTS_TYPE):
    Filelist = []
    for home, _, files in os.walk(path):
        for filename in files:
            if Path(filename).suffix.lower()[1:] in types:
                # 保证所有系统下\\转变成/
                Filelist.append(Path(home, filename).as_posix())
    return Filelist


async def saveToDisk(path, fontBytes):
    # await asyncio.sleep(3)
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
    return ((ord(tagString[0]) & 0xFF) << 24) | ((ord(tagString[1]) & 0xFF) << 16) | ((ord(tagString[2]) & 0xFF) << 8) | (ord(tagString[3]) & 0xFF)


def bytesToHashName(bytes, hash_algorithm="sha256"):
    hash_func = {"md5": hashlib.md5, "sha1": hashlib.sha1, "sha256": hashlib.sha256}.get(hash_algorithm, hashlib.sha256)()  # 默认使用 SHA-256
    hash_func.update(bytes)
    return hash_func.hexdigest()


srt_full_time_pattern = re.compile(r"@\d+@\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}@")


def isSRT(text):
    matches = srt_full_time_pattern.findall("@".join(text.splitlines()))
    return len(matches) > 0


srt_time_pattern = re.compile("-?\d\d:\d\d:\d\d")
srt_time_capture_pattern = re.compile(r"\d(\d:\d{2}:\d{2}),(\d{2})\d")
srt_time_arrow_pattern = re.compile(r"\s+-->\s+")
html_start_tag_pattern = re.compile(r"<([ubi])>")
html_end_tag_pattern = re.compile(r"</([ubi])>")
srt_font_color_start_pattern = re.compile(r'<font\s+color="?#(\w{2})(\w{2})(\w{2})"?>')
srt_font_color_end_pattern = re.compile(r"</font>")


def srtToAss(srtText):
    srtText = srtText.replace("\r", "")
    lines = [x.strip() for x in srtText.split("\n") if x.strip()]
    subLines = ""
    tmpLines = ""
    lineCount = 0

    for ln in range(len(lines)):
        line = lines[ln]
        if line.isdigit() and srt_time_pattern.match(lines[(ln + 1)]):
            if tmpLines:
                subLines += tmpLines.replace("\n", "\\n") + "\n"
            tmpLines = ""
            lineCount = 0
            continue
        else:
            if srt_time_pattern.match(line):
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

    subLines = srt_time_capture_pattern.sub("\\1.\\2", subLines)
    subLines = srt_time_arrow_pattern.sub(",", subLines)
    # replace style
    subLines = html_start_tag_pattern.sub("{\\\\\g<1>1}", subLines)
    subLines = html_end_tag_pattern.sub("{\\\\\g<1>0}", subLines)
    subLines = srt_font_color_start_pattern.sub("{\\\\c&H\\3\\2\\1&}", subLines)
    subLines = srt_font_color_end_pattern.sub(subLines)

    head_str = (
        """[Script Info]
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


def strCaseCmp(str1: str, str2: str) -> bool:
    return str1.lower().strip() == str2.lower().strip()


def getFontScore(
    fontName: str,
    weight: int,
    italic: bool,
    fontInfo: dict,
) -> int:
    """
    fontName：ass中用到的字体名称

    weight： ass中字体bold或者指定了其他值

    italic： ass中字体是否为斜体

    fontInfo: 待打分的字体信息

    返回分数，越小越好，为0则直接选中

    跳过字形检测~~在取得分数后，还需要检测是否包含指定字形，如不包含字形则不会采用~~
    """
    if any([strCaseCmp(fontName, x) for x in fontInfo["familyName"]]):
        score = 0
        if italic and (fontInfo["italic"] == False):
            score += 1
        elif (italic == False) and fontInfo["italic"]:
            score += 4
        a_weight = fontInfo["weight"]
        if (weight > fontInfo["weight"] + 150) and (fontInfo["bold"] == False):
            a_weight += 120
        score += (73 * abs(a_weight - weight)) // 256
        return score
    else:
        fullNamesMatch = any([strCaseCmp(fontName, x) for x in fontInfo["fullName"]])
        postscriptNameMatch = any([strCaseCmp(fontName, x) for x in fontInfo["postscriptName"]])
        if fullNamesMatch == postscriptNameMatch:
            if fullNamesMatch:
                return 0
            else:
                return sys.maxsize
        if fontInfo["postscriptCheck"]:
            if postscriptNameMatch:
                return 0
            else:
                return sys.maxsize
        else:
            if fullNamesMatch:
                return 0
            else:
                return sys.maxsize


# def getFontInfo(font, path, size, index):
#     fontInfo = {
#         "path": path,
#         "size": size,
#         "index": index,
#         "family": set(),
#         "postscriptName": set(),
#         "postscriptCheck": False,
#         "fullName": set(),
#         "weight": 400,  # 默认值
#         "bold": False,  # 默认值
#         "italic": False,  # 默认值
#     }
#     for record in font["name"].names:
#         if record.nameID == 1:
#             fontInfo["family"].add(conv2unicode(str(record).strip()))
#         elif record.nameID == 4:
#             fontInfo["fullName"].add(conv2unicode(str(record).strip()))
#         elif record.nameID == 6:
#             fontInfo["postscriptName"].add(conv2unicode(str(record).strip()))
#             # if fontInfo["postscriptName"] != "":
#             #     assert fontInfo["postscriptName"] == str(record).strip(), f'{path} {index} postscriptName 不唯一 : {str(record).strip()} , {fontInfo["postscriptName"]} : AI {font["name"].getName(6, 3, 1, 0x409)}'
#             # else:
#             #     fontInfo["postscriptName"] = str(record).strip()
#             # 按照 fullname与family的方式处理了

#     fontInfo["postscriptCheck"] = ("CFF " in font) or ("CFF2" in font) or (("glyf" in font) and ("post" in font))
#     if "OS/2" in font:
#         os2_table = font["OS/2"]
#         fontInfo["weight"] = int(os2_table.usWeightClass)
#         fontInfo["bold"] = bool(os2_table.fsSelection & FT_STYLE_FLAG_BOLD)
#         fontInfo["italic"] = bool(os2_table.fsSelection & FT_STYLE_FLAG_ITALIC)
#         # fontInfo["family"] = list(fontInfo["family"])
#         # fontInfo["postscriptName"] = list(fontInfo["postscriptName"])
#         # fontInfo["fullName"] = list(fontInfo["fullName"])

#     return fontInfo


# def getFontFileInfos(fontPath):
#     with open(fontPath, "rb") as f:
#         sfntVersion = f.read(4)
#     fontSize = os.path.getsize(fontPath)
#     fonts = TTCollection(fontPath).fonts if sfntVersion == b"ttcf" else [TTFont(fontPath)]
#     return [getFontInfo(font, fontPath, fontSize, index) for index, font in enumerate(fonts)]


"""
匹配字体用到的参数
family，即fontname
bold，100的整数 100: Lowest, 400: Normal, 700: Bold, 900: Heaviest 默认为400 开启Bold为700 通过text中设置\b<weight>可以改为其他数字
italic，是斜体则100 普通则为100 
"""


def selectFontFromList(targetFontName, targetWeight, targetItalic, fontInfos):
    """
    给定的fontInfos中的font，必定是满足family postscriptName fullName 其中有一个包含 targetFontName
    """
    if len(fontInfos) == 0:
        return None
    scores = {}
    miniScore = sys.maxsize
    for fontInfo in fontInfos:
        score = getFontScore(targetFontName, targetWeight, targetItalic, fontInfo)
        miniScore = min(miniScore, score)
        scores.setdefault(score, []).append(fontInfo)
    target = sorted(scores[miniScore], key=lambda x: x["size"], reverse=False)[0]
    # print("选择字体:", scores.keys())
    # print(json.dumps(target, indent=4, ensure_ascii=False))
    return target["path"], target["index"]


def assInsertLine(ass_str, endTimeText, insertContent):
    try:
        lines = ass_str.splitlines()
        state = 0
        for lineIndex, line in enumerate(lines):
            if line == "":
                pass
            elif state == 0 and line.startswith("[Events]"):
                state = 1
            elif state == 1:
                assert line.startswith("Format:"), ValueError("解析Style格式失败 : " + line)
                eventFormat = line[7:].replace(" ", "").split(",")
                eventStyleIndex = eventFormat.index("Style")
                eventTextindex = eventFormat.index("Text")
                eventStartIndex = eventFormat.index("Start")
                eventEndIndex = eventFormat.index("End")
                assert eventTextindex == len(eventFormat) - 1, ValueError("Text不是最后一个 : " + line)
                assert eventStyleIndex != -1, ValueError("Format中未找到Style : " + line)
                assert eventTextindex != -1, ValueError("Format中未找到Text : " + line)
                assert eventStartIndex != -1, ValueError("Format中未找到Start : " + line)
                assert eventEndIndex != -1, ValueError("Format中未找到End : " + line)
                state = 2
            elif state == 2:
                if line.startswith("Dialogue:"):
                    index = -1
                    splitIndexs = []  # 逗号的位置
                    for _ in range(eventTextindex):
                        index = line.find(",", index + 1)
                        splitIndexs.append(index)
                    style = (splitIndexs[eventStyleIndex - 1] + 1, splitIndexs[eventStyleIndex])
                    start = (splitIndexs[eventStartIndex - 1] + 1, splitIndexs[eventStartIndex])
                    end = (splitIndexs[eventEndIndex - 1] + 1, splitIndexs[eventEndIndex])
                    text = (splitIndexs[eventTextindex - 1] + 1, len(line))
                    charList = list(line)
                    # print(line)
                    # print(f"style[{line[style[0]:style[1]]}]")
                    # print(f"start[{line[start[0]:start[1]]}]")
                    # print(f"end[{line[end[0]:end[1]]}]")
                    # print(f"text[{line[text[0]:text[1]]}]")
                    replacements = [
                        (style[0], style[1], "NOEXISTSTYLETODEFAULT"),
                        (start[0], start[1], "0:00:00.00"),
                        (end[0], end[1], endTimeText),
                        (text[0], text[1], insertContent),
                    ]
                    for start, end, new_str in sorted(replacements, key=lambda x: x[0], reverse=True):
                        charList[start:end] = new_str
                    insertLine = "".join(charList)
                    return "\n".join(lines[:lineIndex] + [insertLine] + lines[lineIndex:])
    except Exception as e:
        print("插入内容出错" + str(e))
    print("插入内容失败")
    return ass_str


# class TT_OS2(ctypes.Structure):
#     _fields_ = [
#         ("version", ctypes.c_ushort),
#         ("xAvgCharWidth", ctypes.c_short),
#         ("usWeightClass", ctypes.c_ushort),
#         ("usWidthClass", ctypes.c_ushort),
#         ("fsType", ctypes.c_ushort),
#         ("ySubscriptXSize", ctypes.c_short),
#         ("ySubscriptYSize", ctypes.c_short),
#         ("ySubscriptXOffset", ctypes.c_short),
#         ("ySubscriptYOffset", ctypes.c_short),
#         ("ySuperscriptXSize", ctypes.c_short),
#         ("ySuperscriptYSize", ctypes.c_short),
#         ("ySuperscriptXOffset", ctypes.c_short),
#         ("ySuperscriptYOffset", ctypes.c_short),
#         ("yStrikeoutSize", ctypes.c_short),
#         ("yStrikeoutPosition", ctypes.c_short),
#         ("sFamilyClass", ctypes.c_short),
#         ("panose", ctypes.c_ubyte * 10),
#         ("ulUnicodeRange1", ctypes.c_ulong),
#         ("ulUnicodeRange2", ctypes.c_ulong),
#         ("ulUnicodeRange3", ctypes.c_ulong),
#         ("ulUnicodeRange4", ctypes.c_ulong),
#         ("achVendID", ctypes.c_char * 4),
#         ("fsSelection", ctypes.c_ushort),
#         ("usFirstCharIndex", ctypes.c_ushort),
#         ("usLastCharIndex", ctypes.c_ushort),
#         ("sTypoAscender", ctypes.c_short),
#         ("sTypoDescender", ctypes.c_short),
#         ("sTypoLineGap", ctypes.c_short),
#         ("usWinAscent", ctypes.c_ushort),
#         ("usWinDescent", ctypes.c_ushort),
#         ("ulCodePageRange1", ctypes.c_ulong),
#         ("ulCodePageRange2", ctypes.c_ulong),
#         ("sxHeight", ctypes.c_short),
#         ("sCapHeight", ctypes.c_short),
#         ("usDefaultChar", ctypes.c_ushort),
#         ("usBreakChar", ctypes.c_ushort),
#         ("usMaxContext", ctypes.c_ushort),
#         ("usLowerOpticalPointSize", ctypes.c_ushort),
#         ("usUpperOpticalPointSize", ctypes.c_ushort),
#     ]
#
#     def __str__(self):
#         return (
#             f"TT_OS2(\n"
#             f"  version={self.version},\n"
#             f"  xAvgCharWidth={self.xAvgCharWidth},\n"
#             f"  usWeightClass={self.usWeightClass},\n"
#             f"  usWidthClass={self.usWidthClass},\n"
#             f"  fsType={self.fsType},\n"
#             f"  ySubscriptXSize={self.ySubscriptXSize},\n"
#             f"  ySubscriptYSize={self.ySubscriptYSize},\n"
#             f"  ySubscriptXOffset={self.ySubscriptXOffset},\n"
#             f"  ySubscriptYOffset={self.ySubscriptYOffset},\n"
#             f"  ySuperscriptXSize={self.ySuperscriptXSize},\n"
#             f"  ySuperscriptYSize={self.ySuperscriptYSize},\n"
#             f"  ySuperscriptXOffset={self.ySuperscriptXOffset},\n"
#             f"  ySuperscriptYOffset={self.ySuperscriptYOffset},\n"
#             f"  yStrikeoutSize={self.yStrikeoutSize},\n"
#             f"  yStrikeoutPosition={self.yStrikeoutPosition},\n"
#             f"  sFamilyClass={self.sFamilyClass},\n"
#             f"  panose={list(self.panose)},\n"
#             f"  ulUnicodeRange1={self.ulUnicodeRange1},\n"
#             f"  ulUnicodeRange2={self.ulUnicodeRange2},\n"
#             f"  ulUnicodeRange3={self.ulUnicodeRange3},\n"
#             f"  ulUnicodeRange4={self.ulUnicodeRange4},\n"
#             f"  achVendID={self.achVendID.decode('utf-8')},\n"
#             f"  fsSelection={self.fsSelection},\n"
#             f"  usFirstCharIndex={self.usFirstCharIndex},\n"
#             f"  usLastCharIndex={self.usLastCharIndex},\n"
#             f"  sTypoAscender={self.sTypoAscender},\n"
#             f"  sTypoDescender={self.sTypoDescender},\n"
#             f"  sTypoLineGap={self.sTypoLineGap},\n"
#             f"  usWinAscent={self.usWinAscent},\n"
#             f"  usWinDescent={self.usWinDescent},\n"
#             f"  ulCodePageRange1={self.ulCodePageRange1},\n"
#             f"  ulCodePageRange2={self.ulCodePageRange2},\n"
#             f"  sxHeight={self.sxHeight},\n"
#             f"  sCapHeight={self.sCapHeight},\n"
#             f"  usDefaultChar={self.usDefaultChar},\n"
#             f"  usBreakChar={self.usBreakChar},\n"
#             f"  usMaxContext={self.usMaxContext},\n"
#             f"  usLowerOpticalPointSize={self.usLowerOpticalPointSize},\n"
#             f"  usUpperOpticalPointSize={self.usUpperOpticalPointSize}\n"
#             f")"
#         )
#
#
# class PS_FontInfoRec(ctypes.Structure):
#     _fields_ = [
#         ("version", ctypes.c_char_p),
#         ("notice", ctypes.c_char_p),
#         ("full_name", ctypes.c_char_p),
#         ("family_name", ctypes.c_char_p),
#         ("weight", ctypes.c_char_p),
#         ("italic_angle", ctypes.c_long),
#         ("is_fixed_pitch", ctypes.c_int),
#         ("underline_position", ctypes.c_short),
#         ("underline_thickness", ctypes.c_short),
#     ]
#
#     def __str__(self):
#         return (
#             f"PS_FontInfoRec(\n"
#             f"  Version: {self.version.decode('utf-8') if self.version else 'N/A'},\n"
#             f"  Notice: {self.notice.decode('utf-8') if self.notice else 'N/A'},\n"
#             f"  Full Name: {self.full_name.decode('utf-8') if self.full_name else 'N/A'},\n"
#             f"  Family Name: {self.family_name.decode('utf-8') if self.family_name else 'N/A'},\n"
#             f"  Weight: {self.weight.decode('utf-8') if self.weight else 'N/A'},\n"
#             f"  Italic Angle: {self.italic_angle},\n"
#             f"  Is Fixed Pitch: {self.is_fixed_pitch},\n"
#             f"  Underline Position: {self.underline_position},\n"
#             f"  Underline Thickness: {self.underline_thickness}\n"
#             f")"
#         )
#
#
# DWRITE_FONT_FACE_TYPE_CFF = 0
# DWRITE_FONT_FACE_TYPE_RAW_CFF = 7
# DWRITE_FONT_FACE_TYPE_TYPE1 = 3
# FT_SFNT_OS2 = 2
# libfreetype = freetype.raw._lib
# libfreetype.FT_Get_Sfnt_Table.restype = ctypes.POINTER(TT_OS2)
# libfreetype.FT_Get_Sfnt_Table.argtypes = [ctypes.c_void_p, ctypes.c_int]


# def getFontFileInfos(fontPath):
#     index = 0
#     infos = []
#     fontSize = os.path.getsize(fontPath)
#     while True:
#         # print(f"handeling ... [{index}]  {fontPath} " )
#         fontInfo = {
#             "path": fontPath,
#             "size": fontSize,
#             "index": index,
#             "family": set(),
#             "postscriptName": set(),
#             "postscriptCheck": False,
#             "fullName": set(),
#             "weight": 400,  # 默认值
#             "bold": False,  # 默认值
#             "italic": False,  # 默认值
#         }
#         face = freetype.Face(fontPath, index)
#         for i in range(face.sfnt_name_count):
#             sfnt_name = face.get_sfnt_name(i)
#             try:
#                 if sfnt_name.name_id == 1:
#                     name = sfnt_name.string.decode("utf-16-be" if sfnt_name.platform_id == 3 else "latin-1").strip().lower()
#                     fontInfo["family"].add(name)
#                 elif sfnt_name.name_id == 4:
#                     name = sfnt_name.string.decode("utf-16-be" if sfnt_name.platform_id == 3 else "latin-1").strip().lower()
#                     fontInfo["fullName"].add(name)
#                 elif sfnt_name.name_id == 6:
#                     name = sfnt_name.string.decode("utf-16-be" if sfnt_name.platform_id == 3 else "latin-1").strip().lower()
#                     fontInfo["postscriptName"].add(name)
#             except Exception as e:
#                 print(f"无法解码记录 {i}: {e}")
#         try:
#             style_flags = face.style_flags
#             fontInfo["bold"] = bool(style_flags & freetype.FT_STYLE_FLAG_BOLD)
#             fontInfo["italic"] = bool(style_flags & freetype.FT_STYLE_FLAG_ITALIC)
#             ps_font_info = PS_FontInfoRec()
#             fontInfo["postscriptCheck"] = not bool(freetype.FT_Get_PS_Font_Info(face._FT_Face, ctypes.byref(ps_font_info)))
#             os2 = libfreetype.FT_Get_Sfnt_Table(face._FT_Face, FT_SFNT_OS2).contents
#             fontInfo["weight"] = os2.usWeightClass
#             infos.append(fontInfo)
#         except Exception as e:
#             print(e, fontPath, index)
#         if index == face.num_faces - 1:
#             return infos
#         else:
#             index += 1

# def getFontFileInfos(fontPath):
#     infos = []
#
#     blob = uharfbuzz.Blob.from_file_path(fontPath)
#     fontSize = len(blob)
#     face = uharfbuzz.Face(blob)
#     font_count = face.count
#     for index in range(font_count):
#         fontInfo = {
#             "path": fontPath,
#             "size": fontSize,
#             "index": index,
#             "family": set(),
#             "postscriptName": set(),
#             "postscriptCheck": False,
#             "fullName": set(),
#             "weight": 400,  # 默认值
#             "bold": False,  # 默认值
#             "italic": False,  # 默认值
#         }
#         face = uharfbuzz.Face(blob, index)
#         names = face.list_names()
#         for name_id, language in names:
#             if name_id == uharfbuzz.OTNameIdPredefined.FONT_FAMILY:
#                 family_name = face.get_name(name_id, language)
#                 # 某些字体因为编码问题导致某个family_name会返回None
#                 if family_name:
#                     fontInfo["family"].add(family_name.strip().lower())
#                 else:
#                     logger.debug(f"{fontPath} 的其中一个family_name因为编码错误导致获取失败")
#             if name_id == uharfbuzz.OTNameIdPredefined.FULL_NAME:
#                 full_name = face.get_name(name_id, language)
#                 if full_name:
#                     fontInfo["fullName"].add(full_name.strip().lower())
#                 else:
#                     logger.debug(f"{fontPath} 的其中一个full_name因为编码错误导致获取失败")
#             if name_id == uharfbuzz.OTNameIdPredefined.POSTSCRIPT_NAME:
#                 postscript_name = face.get_name(name_id, language)
#                 if postscript_name:
#                     fontInfo["postscriptName"].add(postscript_name.strip().lower())
#                 else:
#                     logger.debug(f"{fontPath} 的其中一个postscript_name因为编码错误导致获取失败")
#
#         if "head" in face.table_tags:
#             table_blob = face.reference_table("head")
#             table_data_filter = parse_table(table_blob.data, "head", ["macStyle"])
#             macStyle = table_data_filter["macStyle"]
#         else:
#             macStyle = 0  # 如果没有head表格，也给macStyle默认值
#         if "OS/2" in face.table_tags:
#             table_blob = face.reference_table("OS/2")
#             table_data_filter = parse_table(table_blob.data, "OS/2", ["usWeightClass", "fsSelection"])
#             weight = table_data_filter["usWeightClass"]
#             fsSelection = table_data_filter["fsSelection"]
#             bold = bool(fsSelection & 0x20 or macStyle & 0x01)
#             italic = bool(fsSelection & 0x01 or macStyle & 0x02)
#             fontInfo["bold"] = bold
#             fontInfo["italic"] = italic
#             fontInfo["weight"] = weight
#         else:
#             # 如果没有 OS/2 表，仍然仅根据 macStyle 判断粗体和斜体
#             bold = bool(macStyle & 0x01)
#             italic = bool(macStyle & 0x02)
#             fontInfo["bold"] = bold
#             fontInfo["italic"] = italic
#         fontInfo["postscriptCheck"] = is_postscript_font(face.table_tags)
#         infos.append(fontInfo)
#     return infos


def getFontFileInfos(fontPath):
    file_info_list = []
    font_info_list = []
    font_name_list = []
    blob = uharfbuzz.Blob.from_file_path(fontPath)
    fontSize = len(blob)
    face = uharfbuzz.Face(blob)
    font_count = face.count
    for index in range(font_count):
        face = uharfbuzz.Face(blob, index)
        names = face.list_names()
        uid_obj = uuid.uuid4().hex
        fontInfo = {
            "uid": uid_obj,
            "path": fontPath,
            "size": fontSize,
            "index": index,
            "familyName": [],
            "postscriptName": [],
            "postscriptCheck": False,
            "fullName": [],
            "weight": 400,  # 默认值
            "bold": False,  # 默认值
            "italic": False,  # 默认值
        }
        for name_id, language in names:
            if name_id == uharfbuzz.OTNameIdPredefined.FONT_FAMILY:
                family_name = face.get_name(name_id, language)
                # 某些字体因为编码问题导致某个family_name会返回None
                if family_name:
                    family_name = family_name.strip().lower()
                    fontInfo["familyName"].append(family_name)
                    font_name_list.append(
                        {
                            "name": family_name,
                            "uid": uid_obj,
                        }
                    )
                else:
                    logger.warning(f"{fontPath} 的其中一个family_name因为编码错误导致获取失败")
            if name_id == uharfbuzz.OTNameIdPredefined.FULL_NAME:
                full_name = face.get_name(name_id, language)
                if full_name:
                    full_name = full_name.strip().lower()
                    fontInfo["fullName"].append(full_name)
                    font_name_list.append(
                        {
                            "name": full_name,
                            "uid": uid_obj,
                        }
                    )
                else:
                    logger.warning(f"{fontPath} 的其中一个full_name因为编码错误导致获取失败")
            if name_id == uharfbuzz.OTNameIdPredefined.POSTSCRIPT_NAME:
                postscript_name = face.get_name(name_id, language)
                if postscript_name:
                    postscript_name = postscript_name.strip().lower()
                    fontInfo["postscriptName"].append(postscript_name)
                    font_name_list.append(
                        {
                            "name": postscript_name,
                            "uid": uid_obj,
                        }
                    )
                else:
                    logger.warning(f"{fontPath} 的其中一个postscript_name因为编码错误导致获取失败")

        # 此处判断是否读取到字体信息，如果读取不到任何一个都不应该存入数据库
        if font_name_list:
            if "head" in face.table_tags:
                table_blob = face.reference_table("head")
                table_data_filter = parse_table(table_blob.data, "head", ["macStyle"])
                macStyle = table_data_filter["macStyle"]
            else:
                macStyle = 0  # 如果没有head表格，也给macStyle默认值
            if "OS/2" in face.table_tags:
                table_blob = face.reference_table("OS/2")
                table_data_filter = parse_table(table_blob.data, "OS/2", ["usWeightClass", "fsSelection"])
                weight = table_data_filter["usWeightClass"]
                fsSelection = table_data_filter["fsSelection"]
                bold = bool(fsSelection & 0x20 or macStyle & 0x01)
                italic = bool(fsSelection & 0x01 or macStyle & 0x02)
                fontInfo["bold"] = bold
                fontInfo["italic"] = italic
                fontInfo["weight"] = weight
            else:
                # 如果没有 OS/2 表，仍然仅根据 macStyle 判断粗体和斜体
                bold = bool(macStyle & 0x01)
                italic = bool(macStyle & 0x02)
                fontInfo["bold"] = bold
                fontInfo["italic"] = italic
            fontInfo["postscriptCheck"] = is_postscript_font(face.table_tags)
            font_info_list.append(fontInfo)
        else:
            logger.warning(f"获取信息错误：{fontPath}")

    # 这里获取信息错误的字体不应该添加到数据库，但是还是先存 即便没有字体信息，判断font_info_list
    file_info_list.append(
        {
            "path": fontPath,
            "size": fontSize,
        }
    )
    return file_info_list, font_info_list, font_name_list


def is_postscript_font(table_tag):
    # 检查是否包含 CFF 或 CFF2 表
    if "CFF " in table_tag or "CFF2" in table_tag:
        return True
    # 如果包含 glyf 和 post 表，可能是混合字体
    if "glyf" in table_tag and "post" in table_tag:
        return False  # 这表明字体不是纯 PostScript 字体，可能是 TrueType
    return False


head_format = {
    # (offset, length, type)
    "majorVersion": (0, 2, "H"),  # uint16
    "minorVersion": (2, 2, "H"),  # uint16
    "fontRevision": (4, 4, "f"),  # Fixed (float)
    "checksumAdjustment": (8, 4, "I"),  # uint32
    "magicNumber": (12, 4, "I"),  # uint32
    "flags": (16, 2, "H"),  # uint16
    "unitsPerEm": (18, 2, "H"),  # uint16
    "created": (20, 8, "Q"),  # LONGDATETIME (8 bytes, signed long long)
    "modified": (28, 8, "Q"),  # LONGDATETIME (8 bytes, signed long long)
    "xMin": (36, 2, "h"),  # int16
    "yMin": (38, 2, "h"),  # int16
    "xMax": (40, 2, "h"),  # int16
    "yMax": (42, 2, "h"),  # int16
    "macStyle": (44, 2, "H"),  # uint16
    "lowestRecPPEM": (46, 2, "H"),  # uint16
    "fontDirectionHint": (48, 2, "h"),  # int16
    "indexToLocFormat": (50, 2, "h"),  # int16
    "glyphDataFormat": (52, 2, "h"),  # int16
}

os2_format = {
    # (offset, length, type) V5
    "version": (0, 2, "H"),  # uint16
    "xAvgCharWidth": (2, 2, "h"),  # int16
    "usWeightClass": (4, 2, "H"),  # uint16
    "usWidthClass": (6, 2, "H"),  # uint16
    "fsType": (8, 2, "H"),  # uint16
    "ySubscriptXSize": (10, 2, "h"),  # int16
    "ySubscriptYSize": (12, 2, "h"),  # int16
    "ySubscriptXOffset": (14, 2, "h"),  # int16
    "ySubscriptYOffset": (16, 2, "h"),  # int16
    "ySuperscriptXSize": (18, 2, "h"),  # int16
    "ySuperscriptYSize": (20, 2, "h"),  # int16
    "ySuperscriptXOffset": (22, 2, "h"),  # int16
    "ySuperscriptYOffset": (24, 2, "h"),  # int16
    "yStrikeoutSize": (26, 2, "h"),  # int16
    "yStrikeoutPosition": (28, 2, "h"),  # int16
    "sFamilyClass": (30, 2, "h"),  # int16
    "panose": (32, 10, "10B"),  # PANOSE (10 bytes, binary data)
    "ulUnicodeRange1": (42, 4, "I"),  # uint32
    "ulUnicodeRange2": (46, 4, "I"),  # uint32
    "ulUnicodeRange3": (50, 4, "I"),  # uint32
    "ulUnicodeRange4": (54, 4, "I"),  # uint32
    "achVendID": (58, 4, "4s"),  # String of 4 characters
    "fsSelection": (62, 2, "H"),  # uint16
    "usFirstCharIndex": (64, 2, "H"),  # uint16
    "usLastCharIndex": (66, 2, "H"),  # uint16
    "sTypoAscender": (68, 2, "h"),  # int16
    "sTypoDescender": (70, 2, "h"),  # int16
    "sTypoLineGap": (72, 2, "h"),  # int16
    "usWinAscent": (74, 2, "H"),  # uint16
    "usWinDescent": (76, 2, "H"),  # uint16
    "ulCodePageRange1": (78, 4, "I"),  # uint32
    "ulCodePageRange2": (82, 4, "I"),  # uint32
    "sxHeight": (86, 2, "h"),  # int16
    "sCapHeight": (88, 2, "h"),  # int16
    "usDefaultChar": (90, 2, "H"),  # uint16
    "usBreakChar": (92, 2, "H"),  # uint16
    "usMaxContext": (94, 2, "H"),  # uint16
    "usLowerOpticalPointSize": (96, 2, "H"),  # uint16
    "usUpperOpticalPointSize": (98, 2, "H"),  # uint16
}

table_mapper = {
    "OS/2": os2_format,
    "head": head_format,
}


def parse_table(table_bytes, table_name: str, tag_filter=None):
    data = {}
    table_format = table_mapper.get(table_name)
    if not table_format:
        raise ValueError(f"undefined table: {table_name}")

    byte_parsers = {
        "H": lambda bytes_data: int.from_bytes(bytes_data, byteorder="big"),
        "h": lambda bytes_data: int.from_bytes(bytes_data, byteorder="big", signed=True),
        "I": lambda bytes_data: int.from_bytes(bytes_data, byteorder="big"),
        "4s": lambda bytes_data: bytes_data.decode("utf-8").strip("\x00"),
        "10B": lambda bytes_data: tuple(bytes_data),
        "f": lambda bytes_data: struct.unpack(">f", bytes_data)[0],
        "Q": lambda bytes_data: struct.unpack(">q", bytes_data)[0],
    }
    if tag_filter:
        tag_filter = set(tag_filter)
        table_format = {k: v for k, v in table_format.items() if k in tag_filter}
    for tag, (offset, length, fmt) in table_format.items():
        byte_slice = table_bytes[offset : offset + length]
        if fmt == "f":
            raw_value = int.from_bytes(byte_slice, byteorder="big")
            value = raw_value / 65536.0
        else:
            value = byte_parsers.get(fmt, lambda bytes_data: struct.unpack(fmt, bytes_data))(byte_slice)
        data[tag] = value
    return data
