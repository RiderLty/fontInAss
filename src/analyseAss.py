import re
import time
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
                lineDefaultFontName = styleFontName[styleName]  # 记录初始字体 weight 斜体，如果使用{\r}则会切换回默认style
                lineDefaultWeight = styleWeight[styleName]
                lineDefaultItalic = styleItalic[styleName]
                currentFontName = lineDefaultFontName
                currentWeight = lineDefaultWeight
                currentItalic = lineDefaultItalic
                currentCharSet = fontCharList.setdefault((currentFontName,currentWeight,currentItalic) , set())
                
                testState = 0
                codeStart = -1
                codeEnd = -1
                for index , char in enumerate(eventText):
                    if testState == 0:#初始，判断转义，代码，文本
                        if char == "\\":#转义
                            testState = -1
                        else:
                            if char == "{":#代码
                                testState = 1
                            else:#
                                currentCharSet.add(ord(char))
                    elif testState == -1:#转义
                        testState = 0
                        if char == "{" or char == "}":
                            currentCharSet.add(ord(char))
                        elif char == "N" or char == "n" or char == "h":
                            pass
                        else:#普通的\号 非转义
                            currentCharSet.add(ord(char))
                            currentCharSet.add(92)
                    elif testState == 1:#代码部分
                        if char == "\\":
                            testState = 2#一个代码段开始
                            codeStart = index
                    elif testState == 2:#代码段
                        _end = codeEnd
                        if char == "\\":#下一个代码段开始
                            testState = 2
                            codeEnd = index
                        elif char == "}":#代码部分结束
                            testState = 0
                            codeEnd = index
                        else:
                            pass
                        if _end != codeEnd:
                            tag = eventText[codeStart+1:codeEnd]
                            codeStart = index
                            if (tag.startswith("rndx") or tag.startswith("rndy") or tag.startswith("rndz") ) and tag[4:].isdigit():
                                pass
                            elif tag.startswith("rnd") and tag[3:].isdigit():
                                pass
                            elif tag.startswith("r"):
                                rStyleName = tag[1:].replace("*","")
                                if rStyleName == "":#清除样式
                                    currentFontName = lineDefaultFontName
                                    currentWeight = lineDefaultWeight
                                    currentItalic = lineDefaultItalic
                                else:
                                    if rStyleName in styleFontName:#切换样式
                                        currentFontName = styleFontName[rStyleName]
                                        currentWeight = styleWeight[rStyleName]
                                        currentItalic = styleItalic[rStyleName]
                                    else:#无样式 或者0 切换默认样式
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
                        if testState == 0:
                            currentCharSet = fontCharList.setdefault((currentFontName,currentWeight,currentItalic) , set())
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
Style: Default,黑体,65,&H00FFFFFF,&H000000FF,&H00DD5E15,&H00000000,0,0,0,0,100,100,2,0,1,2,2,2,10,10,40,1
Style: style1,楷体,65,&H00FFFFFF,&H000000FF,&H00DD5E15,&H00000000,0,0,0,0,100,100,2,0,1,2,2,2,10,10,40,1
Style: style2,宋体,65,&H00FFFFFF,&H000000FF,&H00DD5E15,&H00000000,0,0,0,0,100,100,2,0,1,2,2,2,10,10,40,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.88,0:59:59.82,style1,,0,0,0,,我{你甚至可以在这里写注释\CODE_HERE\前面可以是一段代码，但无需关注}能{这里是\rndx10}吞下{\fn宋体\b1\i1}玻璃而{\pos(400,400)}不{\r0}伤{\r}身{\rstyle2}体\{这是转义的\n括号\}
"""
    )
    print(fontCharList)
    # from pathlib import Path
    # subtitles: list[str] = []
    # for path in (Path(__file__).parent.parent / "test").iterdir():
    #     print(path)
    #     subtitles.append(path.read_text(encoding="utf-8"))
    # start = time.perf_counter_ns()
    # for subtitle in subtitles:
    #     analyseAss(subtitle)
    # logger.warning(f"used {(time.perf_counter_ns() - start) / 1000000:.2f}ms")