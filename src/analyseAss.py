import re
from utils import logger

codePatern = re.compile(r"(?<!{)\{\\([^{}]*)\}(?!})")
rfnPatern = re.compile(
    r"[^\\]*(\\r|\\fn(?=@?)|\\i\d+|\\b\d+)([^}|\\]*)"
)  # 匹配 \r 或者 \fn 并捕获之后的内容


def analyseAss(ass_str: str) -> dict[tuple[str, int, bool], set[int]]:
    """分析ass文件 返回 字体：{unicodes}"""
    lines = ass_str.splitlines()
    state: int = 0
    styleNameIndex: int = -1
    fontNameIndex: int = -1
    boldIndex: int = -1
    italicIndex: int = -1
    styleFontName: dict[str, str] = {}
    styleWeight: dict[str, int] = {}
    styleItalic: dict[str, bool] = {}
    eventStyleIndex: int = -1
    eventTextindex: int = -1
    fontCharList: dict[tuple[str, int, bool], set[int]] = {}
    firstStyleName: str = ""
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
                if firstStyleName == "":
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

                if (
                    styleName not in styleFontName
                ):  # 当前行使用的style 不在定义的style中，使用第一个
                    styleName = firstStyleName
                lineDefaultFontName = styleFontName[
                    styleName
                ]  # 记录初始字体 weight 斜体，如果使用{\r}则会切换回默认style
                lineDefaultWeight = styleWeight[styleName]
                lineDefaultItalic = styleItalic[styleName]
                currentFontName: str = lineDefaultFontName
                currentWeight: int = lineDefaultWeight
                currentItalic: bool = lineDefaultItalic

                lastEnd: int = 0
                for code in codePatern.finditer(eventText):  # 匹配所有代码部分，
                    start, end = code.span()
                    # logger.debug(f"({start},{end})")
                    if lastEnd < start:  # 在这里处理代码之间的内容
                        text = eventText[lastEnd:start]
                        key = (currentFontName, currentWeight, currentItalic)
                        if key not in fontCharList:
                            fontCharList[key] = set()
                        for ch in text:
                            fontCharList[key].add(ord(ch))
                        logger.debug(f"{key} : [{text}]")
                    rfnMatch = rfnPatern.findall(eventText[start:end])
                    if len(rfnMatch) != 0:
                        tag, content = rfnMatch[-1]
                        if tag == r"\r":
                            if content == "":  # {\r} 清除样式 回到默认行样式
                                currentFontName = lineDefaultFontName
                                currentWeight = lineDefaultWeight
                                currentItalic = lineDefaultItalic
                            elif content == "0":  # {\r0} 使用第一个style的样式
                                if "Default" in styleFontName:
                                    currentFontName = styleFontName["Default"]
                                    lineDefaultWeight = styleWeight["Default"]
                                    lineDefaultItalic = styleItalic["Default"]
                                else:
                                    # logger.error(f"event[{eventStyle}]使用了未知样式")
                                    pass  # 样式表中不存在Default样式 忽略
                            else:  # {\rstyleName} 切换到指定样式
                                tempStyleName = content.replace("*", "")
                                if tempStyleName in styleFontName:
                                    currentFontName = styleFontName[tempStyleName]
                                    lineDefaultWeight = styleWeight[tempStyleName]
                                    lineDefaultItalic = styleItalic[tempStyleName]
                                else:
                                    # logger.error(f"event[{eventStyle}]使用了未知样式")
                                    pass  # 样式表中不存在code中指定的样式 忽略
                        elif tag == r"\fn":
                            currentFontName = content.replace("@", "")
                        else:
                            if tag == r"\i0":
                                currentItalic = False
                            elif tag == r"\i1":
                                currentItalic = True
                            else:
                                assert tag.startswith(r"\b"), ValueError(
                                    "MatchError : " + eventText
                                )
                                boldValue = tag[2:]
                                if boldValue == "0":
                                    currentWeight = 400
                                elif boldValue == "1":
                                    currentWeight = 700
                                else:
                                    currentWeight = int(boldValue)
                    lastEnd = end

                if lastEnd < len(eventText):
                    text = eventText[lastEnd:]
                    key = (currentFontName, currentWeight, currentItalic)
                    if key not in fontCharList:
                        fontCharList[key] = set()
                    for ch in text:
                        fontCharList[key].add(ord(ch))
                    logger.debug(f"{key} : [{text}]")
    return fontCharList
