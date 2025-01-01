import re
from utils import logger


def analyseAss(ass_str: str) -> dict[tuple[str, int, bool], set[int]]:
    """分析ass文件 返回 字体：{unicodes}"""
    lines = ass_str.splitlines()
    state = 0
    styleNameIndex = -1
    fontNameIndex = -1
    boldIndex = -1
    italicIndex = -1
    styleFontName = {}
    styleWeight = {}
    styleItalic = {}
    eventStyleIndex = -1
    eventTextindex = -1
    fontCharList: dict[tuple[str, int, bool], set[int]] = {}
    firstStyleName: str | None = None
    for line in lines:
        if line == "":
            pass
        elif state == 0 and line.startswith("[V4+ Styles]"):
            state = 1
        elif state == 1:
            assert line.startswith("Format:"), ValueError("解析Style格式失败 : " + line)
            styleFormat = line[7:].replace(" ", "").split(",")
            styleNameIndex = styleFormat.index("Name")
            fontNameIndex = styleFormat.index("Fontname")
            assert styleNameIndex != -1 and fontNameIndex != -1, ValueError(
                "Format中未找到Name或Fontname : " + line
            )
            boldIndex = styleFormat.index("Bold")
            italicIndex = styleFormat.index("Italic")
            state = 2
        elif state == 2:
            if line.startswith("[Events]"):
                state = 3
            elif line.startswith("Style:"):
                styleData = line[6:].strip().split(",")
                styleName = styleData[styleNameIndex].strip().replace("*", "")
                fontName = styleData[fontNameIndex].strip().replace("@", "")
                fontWeight = 400
                if (
                    boldIndex != -1 and styleData[boldIndex].strip() == "1"
                ):  # 没有Bold则默认400，有则700 ，Text里代码也可以改变
                    fontWeight = 700
                fontItalic = False
                if (
                    italicIndex != -1 and styleData[italicIndex].strip() == "1"
                ):  # 斜体 只有是否
                    fontItalic = True
                styleFontName[styleName] = fontName
                styleWeight[styleName] = fontWeight
                styleItalic[styleName] = fontItalic
                if firstStyleName == None:
                    firstStyleName = styleName
            else:
                pass
        elif state == 3:
            assert line.startswith("Format:"), ValueError("解析Event格式失败 : " + line)
            eventFormat = line[7:].replace(" ", "").split(",")
            eventStyleIndex = eventFormat.index("Style")
            eventTextindex = eventFormat.index("Text")
            assert eventTextindex == len(eventFormat) - 1, ValueError(
                "Text不是最后一个 : " + line
            )
            assert eventStyleIndex != -1 and eventTextindex != -1, ValueError(
                "Format中未找到Style或Text : " + line
            )
            state = 4
            # print(styleFontName)
            # print(styleWeight)
            # print(styleItalic)
        elif state == 4:
            if line.startswith("Dialogue:"):
                parts = line.replace("Dialogue:", "").split(",")
                styleName = parts[eventStyleIndex].replace("*", "")
                eventText = ",".join(parts[eventTextindex:])
                logger.debug(f"")
                logger.debug(f"原始文本 : {eventText}")

                if styleName not in styleFontName:
                    styleName = firstStyleName  # 当前行使用的style 不在定义的style中，使用第一个
                lineDefaultFontName = styleFontName[
                    styleName
                ]  # 记录初始字体 weight 斜体，如果使用{\r}则会切换回默认style
                lineDefaultWeight = styleWeight[styleName]
                lineDefaultItalic = styleItalic[styleName]
                currentFontName = lineDefaultFontName
                currentWeight = lineDefaultWeight
                currentItalic = lineDefaultItalic

                def string2fontCharList(string: str, key: tuple[str, int, bool]):
                    """
                    将字符串添加到字体字符集中

                    :param string: 字符串
                    :param key: 字体名，字重，斜体
                    """
                    if key not in fontCharList:
                        fontCharList[key] = set()
                    logger.debug(f"{key}: {string}")
                    for char in string:
                        fontCharList[key].add(ord(char))

                buffer: str = ""  # 缓存区
                for char in eventText:
                    if char == "{":  # 遇到 {，先处理缓存区，后续再判断是否是特殊样式
                        string2fontCharList(
                            buffer, (currentFontName, currentWeight, currentItalic)
                        )
                        buffer = char
                    elif char == "}" and buffer.startswith("{\\"):
                        tags = buffer[2:].split("\\")  # 去掉 {\ 并且分割
                        logger.debug(f"特殊样式代码结束，匹配标签：{tags}")
                        for tag in tags:
                            if tag == "r":
                                currentFontName = lineDefaultFontName
                                currentWeight = lineDefaultWeight
                                currentItalic = lineDefaultItalic
                            elif tag.startswith("fn"):  # 字体
                                currentFontName = tag[2:].replace("@", "")
                            elif tag.startswith("b") and tag[1:].isdigit():  # 字重
                                if tag == "b0":
                                    currentWeight = 400
                                elif tag == "b1":
                                    currentWeight = 700
                                else:
                                    currentWeight = int(tag[1:])
                            elif tag == "i0":
                                currentItalic = False
                            elif tag == "i1":
                                currentItalic = True
                        buffer = ""  # 特殊样式结束，清空缓存区
                    else:
                        buffer += char
                if buffer != "":
                    string2fontCharList(
                        buffer, (currentFontName, currentWeight, currentItalic)
                    )
    return fontCharList


if __name__ == "__main__":
    logger.setLevel("DEBUG")
    fontCharList = analyseAss(
        r"""
[Script Info]
; Script generated by Aegisub 3.2.2
; http://www.aegisub.org/
Title: Default Aegisub file
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.601
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,方正悠黑_GBK 511M,65,&H00FFFFFF,&H000000FF,&H00DD5E15,&H00000000,0,0,0,0,100,100,2,0,1,2,2,2,10,10,40,1
Style: style1,方正悠黑_GBK 511M,65,&H00FFFFFF,&H000000FF,&H00DD5E15,&H00000000,0,0,0,0,100,100,2,0,1,2,2,2,10,10,40,1
Style: style2,方正悠黑_GBK 511M,65,&H00FFFFFF,&H000000FF,&H00DD5E15,&H00000000,0,0,0,0,100,100,2,0,1,2,2,2,10,10,40,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:02.88,0:00:04.82,86 taici,,0,0,0,,我{\CODE_HERE}能吞下{\fn宋体\b1\i1}玻璃而{\pos(400,400)}不伤{\r}身{体}
"""
    )
    print(fontCharList)
