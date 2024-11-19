import re
from utils import logger

def analyseAss(ass_str: str):
    """分析ass文件 返回 字体：{unicodes}"""
    lines = ass_str.splitlines()
    state = 0
    styleNameIndex = -1
    fontNameIndex = -1
    styleFontName = {}
    eventStyleIndex = -1
    eventTextindex = -1
    fontCharList = {}
    codePatern = re.compile(r"(?<!{)\{\\([^{}]*)\}(?!})")
    rfnPatern = re.compile(r"[^\\]*(\\r|\\fn(?=@?))([^}|\\]*)")  # 匹配 \r 或者 \fn 并捕获之后的内容
    firstStyleFontName = None
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
            assert styleNameIndex != -1 and fontNameIndex != -1, ValueError("Format中未找到Name或Fontname : " + line)
            state = 2
        elif state == 2:
            if line.startswith("[Events]"):
                state = 3
            else:
                assert line.startswith("Style:"), ValueError("解析Style失败 : " + line)
                styleData = line[6:].strip().split(",")
                styleName = styleData[styleNameIndex].strip()
                fontName = styleData[fontNameIndex].strip()
                styleFontName[styleName.replace("*","")] = fontName.replace("@", "")
                if firstStyleFontName == None:
                    firstStyleFontName = fontName.replace("@", "")
        elif state == 3:
            assert line.startswith("Format:"), ValueError("解析Event格式失败 : " + line)
            eventFormat = line[7:].replace(" ", "").split(",")
            eventStyleIndex = eventFormat.index("Style")
            eventTextindex = eventFormat.index("Text")
            assert eventTextindex == len(eventFormat) - 1, ValueError("Text不是最后一个 : " + line)
            assert eventStyleIndex != -1 and eventTextindex != -1, ValueError("Format中未找到Style或Text : " + line)
            state = 4
        elif state == 4:
            if line.startswith("Dialogue:"):
                index = -1
                for i in range(eventTextindex):
                    index = line.find(",", index + 1)
                    if i == eventStyleIndex - 1:
                        styleStart = index
                    elif i == eventStyleIndex:
                        styleEnd = index
                    elif i == eventTextindex - 1:
                        textStart = index
                styleName = line[styleStart + 1 : styleEnd]
                eventText = line[textStart + 1 :]
                logger.debug(f"")
                logger.debug(f"原始文本 : {eventText}")
                if styleName.replace("*","") in styleFontName: # Style不在定义的Style中，使用第一个style
                    defaultFontName = styleFontName[styleName.replace("*","")]
                else:
                    defaultFontName = firstStyleFontName
                currentFontName = defaultFontName.replace("@", "")
                lastEnd = 0
                for code in codePatern.finditer(eventText):  # 匹配所有代码部分，
                    start, end = code.span()
                    # logger.debug(f"({start},{end})")
                    if lastEnd < start:
                        text = eventText[lastEnd:start]
                        if currentFontName not in fontCharList:
                            fontCharList[currentFontName] = set()
                        for ch in text:
                            fontCharList[currentFontName].add(ord(ch))
                        logger.debug(f"{currentFontName} : [{text}]")
                    rorfnMatch = rfnPatern.findall(eventText[start:end])
                    if len(rorfnMatch) != 0:
                        type, content = rorfnMatch[-1]
                        if type == r"\r":
                            if content == "":  # {\r}
                                currentFontName = defaultFontName.replace("@", "")
                            elif content == r"0":  # {\r0}
                                if "Default" in styleFontName:
                                    currentFontName = styleFontName["Default"].replace("@", "")
                                else:
                                    # logger.error(f"event[{eventStyle}]使用了未知样式")
                                    pass # 样式表中不存在Default样式 忽略
                            else:  # {\rstyleName}
                                if content.replace("*","") in styleFontName:
                                    currentFontName = styleFontName[content.replace("*","")].replace("@", "")
                                else:
                                    # logger.error(f"event[{eventStyle}]使用了未知样式")
                                    pass # 样式表中不存在code中指定的样式 忽略
                        elif type == r"\fn":
                            currentFontName = content.replace("@", "")
                        else:
                            raise ValueError("MatchError : " + eventText)
                    lastEnd = end
                if lastEnd < len(eventText):
                    text = eventText[lastEnd:]
                    if currentFontName not in fontCharList:
                        fontCharList[currentFontName] = set()
                    for ch in text:
                        fontCharList[currentFontName].add(ord(ch))
                    logger.debug(f"{currentFontName} : [{text}]")
    return fontCharList
