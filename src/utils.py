import os
import re
import hashlib
import uuid
from pathlib import Path
import sys
import aiofiles
from charset_normalizer import from_bytes
import uharfbuzz
from constants import logger, FONTS_TYPE
from py2cy.c_utils import parse_table


def make_mini_size_fontmap(data):
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
    file_set = {}
    font_mini_size = {}
    for path in data.keys():
        size = data[path]["size"]
        for fontName, index in data[path]["fonts"].items():
            if fontName not in file_set or font_mini_size[fontName] > size:
                file_set[fontName] = (path, index)
                font_mini_size[fontName] = size
    return file_set


def get_all_files(path, types=FONTS_TYPE):
    file_list = []
    for home, _, files in os.walk(path):
        for filename in files:
            if Path(filename).suffix.lower()[1:] in types:
                # 保证所有系统下\\转变成/
                file_list.append(Path(home, filename).as_posix())
    return file_list


async def save_to_disk(path, raw_bytes):
    # await asyncio.sleep(3)
    async with aiofiles.open(path, "wb") as f:
        await f.write(raw_bytes)
        logger.info(f"网络字体已保存\t\t[{path}]")


def tag_to_integer(tag: str) -> int:
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
    assert len(tag) == 4, ValueError("The input string must be exactly 4 characters long.")
    return int.from_bytes(tag.encode("latin-1"), byteorder="big")


def bytes_to_hash(raw_bytes, hash_algorithm="sha256"):
    hash_func = {"md5": hashlib.md5, "sha1": hashlib.sha1, "sha256": hashlib.sha256}.get(hash_algorithm, hashlib.sha256)()  # 默认使用 SHA-256
    hash_func.update(raw_bytes)
    return hash_func.hexdigest()


srt_full_time_pattern = re.compile(r"@\d+@\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}@")


def is_srt(text):
    matches = srt_full_time_pattern.findall("@".join(text.splitlines()))
    return len(matches) > 2


srt_time_pattern = re.compile("-?\d\d:\d\d:\d\d")
srt_time_capture_pattern = re.compile(r"\d(\d:\d{2}:\d{2}),(\d{2})\d")
srt_time_arrow_pattern = re.compile(r"\s+-->\s+")
html_start_tag_pattern = re.compile(r"<([ubi])>")
html_end_tag_pattern = re.compile(r"</([ubi])>")
srt_font_color_start_pattern = re.compile(r'<font\s+color="?#(\w{2})(\w{2})(\w{2})"?>')
srt_font_color_end_pattern = re.compile(r"</font>")


def srt_to_ass(srt_text, srt_format, srt_style):
    srt_text = srt_text.replace("\r", "")
    lines = [x.strip() for x in srt_text.split("\n") if x.strip()]
    sub_lines = ""
    tmp_lines = ""
    line_count = 0

    for ln in range(len(lines)):
        line = lines[ln]
        if line.isdigit() and srt_time_pattern.match(lines[(ln + 1)]):
            if tmp_lines:
                sub_lines += tmp_lines.replace("\n", "\\n") + "\n"
            tmp_lines = ""
            line_count = 0
            continue
        else:
            if srt_time_pattern.match(line):
                line = line.replace("-0", "0")
                tmp_lines += "Dialogue: 0," + line + ",Default,,0,0,0,,"
            else:
                if line_count < 2:
                    tmp_lines += line
                else:
                    tmp_lines += "\n" + line
            line_count += 1
        ln += 1

    sub_lines += tmp_lines + "\n"

    sub_lines = srt_time_capture_pattern.sub("\\1.\\2", sub_lines)
    sub_lines = srt_time_arrow_pattern.sub(",", sub_lines)
    # replace style
    sub_lines = html_start_tag_pattern.sub("{\\\\\g<1>1}", sub_lines)
    sub_lines = html_end_tag_pattern.sub("{\\\\\g<1>0}", sub_lines)
    sub_lines = srt_font_color_start_pattern.sub("{\\\\c&H\\3\\2\\1&}", sub_lines)
    sub_lines = srt_font_color_end_pattern.sub("", sub_lines)

    head_str = (
        """[Script Info]
; This is an Advanced Sub Station Alpha v4+ script.
Title:
ScriptType: v4.00+
Collisions: Normal
PlayDepth: 0

[V4+ Styles]
"""
        + srt_format
        + "\n"
        + srt_style
        + """

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    )
    # Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
    # Style: Default,楷体,20,&H03FFFFFF,&H00FFFFFF,&H00000000,&H02000000,-1,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1
    output_str = head_str + "\n" + sub_lines
    logger.debug("SRT转ASS\n" + output_str)
    return output_str

def bytes_to_str(raw_bytes: bytes) -> tuple[str | None, str | None]:
    """
    快速将 bytes 转成 str，自动检测编码
    """
    result = from_bytes(raw_bytes).best()
    if result:
        logger.debug(f"判断编码: {result.encoding}")
        return result.encoding, str(result)
    else:
        return None, None

def equals_ignore_case(str1: str, str2: str) -> bool:
    return str1.lower().strip() == str2.lower().strip()

def get_font_score(
    font_name: str,
    weight: int,
    italic: bool,
    font_info: dict,
) -> int:
    """
    font_name：ass中用到的字体名称

    weight： ass中字体bold或者指定了其他值

    italic： ass中字体是否为斜体

    font_info: 待打分的字体信息

    返回分数，越小越好，为0则直接选中

    跳过字形检测~~在取得分数后，还需要检测是否包含指定字形，如不包含字形则不会采用~~
    """
    if any([equals_ignore_case(font_name, x) for x in font_info["familyName"]]):
        score = 0
        if italic and (font_info["italic"] == False):
            score += 1
        elif (italic == False) and font_info["italic"]:
            score += 4
        a_weight = font_info["weight"]
        if (weight > font_info["weight"] + 150) and (font_info["bold"] == False):
            a_weight += 120
        score += (73 * abs(a_weight - weight)) // 256
        return score
    else:
        full_name_match = any([equals_ignore_case(font_name, x) for x in font_info["fullName"]])
        postscript_name_match = any([equals_ignore_case(font_name, x) for x in font_info["postscriptName"]])
        if full_name_match == postscript_name_match:
            if full_name_match:
                return 0
            else:
                return sys.maxsize
        if font_info["postscriptCheck"]:
            if postscript_name_match:
                return 0
            else:
                return sys.maxsize
        else:
            if full_name_match:
                return 0
            else:
                return sys.maxsize


"""
匹配字体用到的参数
family，即fontname
bold，100的整数 100: Lowest, 400: Normal, 700: Bold, 900: Heaviest 默认为400 开启Bold为700 通过text中设置\b<weight>可以改为其他数字
italic，是斜体则100 普通则为100 
"""


def select_font_fromlist(target_font_name, target_weight, target_italic, font_infos):
    """
    给定的font_infos中的font，必定是满足family postscriptName fullName 其中有一个包含 target_font_name
    """
    if len(font_infos) == 0:
        return None
    scores = {}
    mini_score = sys.maxsize
    for fontInfo in font_infos:
        score = get_font_score(target_font_name, target_weight, target_italic, fontInfo)
        mini_score = min(mini_score, score)
        scores.setdefault(score, []).append(fontInfo)
    target = sorted(scores[mini_score], key=lambda x: x["size"], reverse=False)[0]
    # print("选择字体:", scores.keys())
    # print(json.dumps(target, indent=4, ensure_ascii=False))
    return target["path"], target["index"]


# def ass_insert_line(ass_str, endTimeText, insertContent):
#     try:
#         lines = ass_str.splitlines()
#         state = 0
#         for lineIndex, line in enumerate(lines):
#             if line == "":
#                 pass
#             elif state == 0 and line.startswith("[Events]"):
#                 state = 1
#             elif state == 1:
#                 assert line.startswith("Format:"), ValueError("解析Style格式失败 : " + line)
#                 eventFormat = line[7:].replace(" ", "").split(",")
#                 eventStyleIndex = eventFormat.index("Style")
#                 eventTextindex = eventFormat.index("Text")
#                 eventStartIndex = eventFormat.index("Start")
#                 eventEndIndex = eventFormat.index("End")
#                 assert eventTextindex == len(eventFormat) - 1, ValueError("Text不是最后一个 : " + line)
#                 assert eventStyleIndex != -1, ValueError("Format中未找到Style : " + line)
#                 assert eventTextindex != -1, ValueError("Format中未找到Text : " + line)
#                 assert eventStartIndex != -1, ValueError("Format中未找到Start : " + line)
#                 assert eventEndIndex != -1, ValueError("Format中未找到End : " + line)
#                 state = 2
#             elif state == 2:
#                 if line.startswith("Dialogue:"):
#                     index = -1
#                     splitIndexs = []  # 逗号的位置
#                     for _ in range(eventTextindex):
#                         index = line.find(",", index + 1)
#                         splitIndexs.append(index)
#                     style = (splitIndexs[eventStyleIndex - 1] + 1, splitIndexs[eventStyleIndex])
#                     start = (splitIndexs[eventStartIndex - 1] + 1, splitIndexs[eventStartIndex])
#                     end = (splitIndexs[eventEndIndex - 1] + 1, splitIndexs[eventEndIndex])
#                     text = (splitIndexs[eventTextindex - 1] + 1, len(line))
#                     charList = list(line)
#                     # print(line)
#                     # print(f"style[{line[style[0]:style[1]]}]")
#                     # print(f"start[{line[start[0]:start[1]]}]")
#                     # print(f"end[{line[end[0]:end[1]]}]")
#                     # print(f"text[{line[text[0]:text[1]]}]")
#                     replacements = [
#                         (style[0], style[1], "NOEXISTSTYLETODEFAULT"),
#                         (start[0], start[1], "0:00:00.00"),
#                         (end[0], end[1], endTimeText),
#                         (text[0], text[1], insertContent),
#                     ]
#                     for start, end, new_str in sorted(replacements, key=lambda x: x[0], reverse=True):
#                         charList[start:end] = new_str
#                     insertLine = "".join(charList)
#                     return "\n".join(lines[:lineIndex] + [insertLine] + lines[lineIndex:])
#     except Exception as e:
#         print("插入内容出错" + str(e))
#     print("插入内容失败")
#     return ass_str


styleMap = {
    "Name": "InsertByFontinass",
    "Fontname": "Arial",
    "Fontsize": "48",
    "PrimaryColour": "&HE0E0E0",
    "SecondaryColour": "&H000000",
    "OutlineColour": "&H000000",
    "BackColour": "&H000000",
    "Bold": "0",
    "Italic": "0",
    "Underline": "0",
    "StrikeOut": "0",
    "ScaleX": "100",
    "ScaleY": "100",
    "Spacing": "1",
    "Angle": "0",
    "BorderStyle": "1",
    "Outline": "2",
    "Shadow": "0",
    "Alignment": "7",
    "MarginL": "30",
    "MarginR": "30",
    "MarginV": "10",
    "Encoding": "1",
}
eventMap = {"Layer": "0", "Start": "0:00:00.00", "End": "endTime", "Style": "InsertByFontinass", "Name": "INSERT", "MarginL": "0", "MarginR": "0", "MarginV": "0", "Effect": "", "Text": "insertContent"}


def ass_insert_line(ass_str, end_time, insert_content):
    style = ("", -1)
    event = ("", -1)
    state = 0
    try:
        lines = ass_str.splitlines()
        for lineIndex, line in enumerate(lines):
            if line == "":
                pass
            elif state == 0 and line.startswith("[V4+ Styles]"):
                state = 1
            elif state == 1:
                assert line.startswith("Format:"), ValueError("解析Style格式失败 : " + line)
                style = (line[8:].replace(" ", ""), lineIndex + 1)
                state = 2
            elif state == 2 and line.startswith("[Events]"):
                state = 3
            elif state == 3:
                assert line.startswith("Format:"), ValueError("解析event格式失败 : " + line)
                event = (line[8:].replace(" ", ""), lineIndex + 1)
                break
        assert style[1] != -1 and event[1] != -1, ValueError("解析失败")
        insert_style = "Style: " + style[0]
        for key, value in styleMap.items():
            insert_style = insert_style.replace(key, value)

        insert_event = "Dialogue: " + event[0]
        for key, value in eventMap.items():
            insert_event = insert_event.replace(key, value)
        insert_event = insert_event.replace("endTime", end_time)
        insert_event = insert_event.replace("insertContent", insert_content)
        return "\n".join(lines[: style[1]] + [insert_style] + lines[style[1] : event[1]] + [insert_event] + lines[event[1] :])
    except Exception as e:
        logger.exception("插入内容出错")
        # print("插入内容出错" + str(e))
    # print("插入内容失败")
    return ass_str

def get_font_info(font_path):
    file_info_list = []
    font_info_list = []
    font_name_list = []
    blob = uharfbuzz.Blob.from_file_path(font_path)
    font_size = len(blob)
    face = uharfbuzz.Face(blob)
    font_count = face.count
    for index in range(font_count):
        face = uharfbuzz.Face(blob, index)
        names = face.list_names()
        uid_obj = uuid.uuid4().hex
        font_info = {
            "uid": uid_obj,
            "path": font_path,
            "size": font_size,
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
                    font_info["familyName"].append(family_name)
                    font_name_list.append(
                        {
                            "name": family_name,
                            "uid": uid_obj,
                        }
                    )
                # else:
                #     logger.warning(f"{font_path} 的其中一个family_name因为编码错误导致获取失败")
            if name_id == uharfbuzz.OTNameIdPredefined.FULL_NAME:
                full_name = face.get_name(name_id, language)
                if full_name:
                    full_name = full_name.strip().lower()
                    font_info["fullName"].append(full_name)
                    font_name_list.append(
                        {
                            "name": full_name,
                            "uid": uid_obj,
                        }
                    )
                # else:
                #     logger.warning(f"{font_path} 的其中一个full_name因为编码错误导致获取失败")
            if name_id == uharfbuzz.OTNameIdPredefined.POSTSCRIPT_NAME:
                postscript_name = face.get_name(name_id, language)
                if postscript_name:
                    postscript_name = postscript_name.strip().lower()
                    font_info["postscriptName"].append(postscript_name)
                    font_name_list.append(
                        {
                            "name": postscript_name,
                            "uid": uid_obj,
                        }
                    )
                # else:
                #     logger.warning(f"{font_path} 的其中一个postscript_name因为编码错误导致获取失败")

        # 此处判断是否读取到字体信息，如果读取不到任何一个都不应该存入数据库
        if font_name_list:
            if "head" in face.table_tags:
                table_blob = face.reference_table("head")
                table_data_filter = parse_table(table_blob.data, "head", [13])
                macStyle = table_data_filter[0]
            else:
                macStyle = 0  # 如果没有head表格，也给macStyle默认值
            if "OS/2" in face.table_tags:
                table_blob = face.reference_table("OS/2")
                table_data_filter = parse_table(table_blob.data, "OS/2", [2, 22])
                weight = table_data_filter[0]
                fsSelection = table_data_filter[1]
                bold = bool(fsSelection & 0x20 or macStyle & 0x01)
                italic = bool(fsSelection & 0x01 or macStyle & 0x02)
                font_info["bold"] = bold
                font_info["italic"] = italic
                font_info["weight"] = weight
            else:
                # 如果没有 OS/2 表，仍然仅根据 macStyle 判断粗体和斜体
                bold = bool(macStyle & 0x01)
                italic = bool(macStyle & 0x02)
                font_info["bold"] = bold
                font_info["italic"] = italic
            font_info["postscriptCheck"] = is_postscript_font(face.table_tags)
            font_info_list.append(font_info)
        else:
            logger.error(f"无法获取到该字体任何信息，请检查该字体内的编码是否正确：{font_path}")

    # 这里获取信息错误的字体不应该添加到数据库，但是还是先存 即便没有字体信息，判断font_info_list
    file_info_list.append(
        {
            "path": font_path,
            "size": font_size,
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

def insert_str(original, str, marker):
    index = original.find(marker)
    if index != -1:
        return original[: index + len(marker)] + str + original[index + len(marker) :]
    else:
        return original

# 没有使用
def restore_subset_fonts(ass_text: str) -> str:
    state = 0
    name_info = []
    for line in ass_text.splitlines():
        if line.startswith("; Font Subset:"):
            state = 1
            name = line[15:23]
            origin_name = line[26:].strip()
            name_info.append((name, origin_name))
        else:
            if state == 1:
                break
            elif line.startswith("[V4+ Styles]"):
                break
    if len(name_info) == 0:
        return ass_text
    else:
        new_text = ass_text
        for name, origin_name in name_info:
            new_text = new_text.replace(name, origin_name)
        return new_text

def remove_section(ass_text: str, section: str) -> str:
    """
    从 ASS 文本中移除指定的段落 (如 [Fonts], [Events] 等)。

    参数:
        ass_text (str): 原始 ASS 字符串
        section (str): 段落名，不带中括号，例如 "Fonts" 或 "Events"

    返回:
        str: 移除指定段落后的 ASS 文本
    """
    # 构造正则，匹配 [Section] 开头，到下一个 [XXX] 段之前
    pattern = rf"\[{re.escape(section)}\][\s\S]*?(?=\n\[|$)"
    return re.sub(pattern, "", ass_text, count=1)

def check_section(ass_text: str, section: str) -> int:
    """
    检测 ASS 文本中的指定段落情况。

    参数:
        ass_text (str): 原始 ASS 字符串
        section (str): 段落名，不带中括号，例如 "Fonts" 或 "Events"

    返回:
        int: 检测结果
            - 0: 没有该段落
            - 1: 有该段落且有内容
            - 2: 有该段落但无内容
    """
    pattern = rf"\[{re.escape(section)}\]([\s\S]*?)(?=\n\[|$)"
    match = re.search(pattern, ass_text)

    if not match:
        return 0

    content = match.group(1).strip()
    return 1 if content else 2