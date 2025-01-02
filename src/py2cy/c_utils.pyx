import struct
from typing import Dict, Optional, Set, Tuple

def uuencode(const unsigned char[:] binaryData):
    """
    编码工具 (Cython实现)
    """
    cdef int OFFSET = 33
    cdef int CHUNK_SIZE = 20
    cdef int data_len = len(binaryData)
    cdef int remainder = data_len % 3
    cdef list encoded = [None] * ((data_len + 2) // 3)  # 预分配 encoded 大小
    cdef list encoded_lines = []
    cdef int packed, i
    cdef int six_bits[4]
    cdef str encoded_group

    # 提前生成字符映射数组，避免重复调用 chr()
    cdef bytes chr_map = bytes([OFFSET + i for i in range(64)])  # 用 bytes 存储映射字符

    # 遍历 3 字节一组的块
    cdef int index = 0
    for i in range(0, (data_len // 3) * 3, 3):
        packed = (binaryData[i] << 16) | (binaryData[i + 1] << 8) | binaryData[i + 2]
        six_bits[0] = (packed >> 18) & 0x3F
        six_bits[1] = (packed >> 12) & 0x3F
        six_bits[2] = (packed >> 6) & 0x3F
        six_bits[3] = packed & 0x3F
        encoded_group = (
            chr_map[six_bits[0]:six_bits[0] + 1].decode() +
            chr_map[six_bits[1]:six_bits[1] + 1].decode() +
            chr_map[six_bits[2]:six_bits[2] + 1].decode() +
            chr_map[six_bits[3]:six_bits[3] + 1].decode()
        )
        encoded[index] = encoded_group
        index += 1

    # 处理不满 3 字节的情况
    if remainder == 1:
        packed = binaryData[-1] << 16  # 将末尾单字节左移到24位
        six_bits[0] = (packed >> 18) & 0x3F
        six_bits[1] = (packed >> 12) & 0x3F
        encoded_group = chr_map[six_bits[0]:six_bits[0] + 1].decode() + chr_map[six_bits[1]:six_bits[1] + 1].decode()
        encoded[index] = encoded_group
    elif remainder == 2:
        packed = (binaryData[-2] << 16) | (binaryData[-1] << 8)  # 将末尾双字节左移到24位
        six_bits[0] = (packed >> 18) & 0x3F
        six_bits[1] = (packed >> 12) & 0x3F
        six_bits[2] = (packed >> 6) & 0x3F
        encoded_group = (
            chr_map[six_bits[0]:six_bits[0] + 1].decode() +
            chr_map[six_bits[1]:six_bits[1] + 1].decode() +
            chr_map[six_bits[2]:six_bits[2] + 1].decode()
        )
        encoded[index] = encoded_group

    # 分行显示
    cdef int num_chunks = (index + CHUNK_SIZE - 1) // CHUNK_SIZE  # 计算块数
    for i in range(num_chunks):
        encoded_lines.append("".join(encoded[i * CHUNK_SIZE:(i + 1) * CHUNK_SIZE]))

    return "\n".join(encoded_lines)

# 定义表映射
table_mapper = {
    "OS/2": {
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
        "usUpperOpticalPointSize": (98, 2, "H")  # uint16
    },
    "head": {
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
}

cdef dict byte_parsers = {
    "H": lambda bytes_data: int.from_bytes(bytes_data, byteorder='big'),
    "h": lambda bytes_data: int.from_bytes(bytes_data, byteorder='big', signed=True),
    "I": lambda bytes_data: int.from_bytes(bytes_data, byteorder='big'),
    "4s": lambda bytes_data: bytes_data.decode('utf-8').strip('\x00'),
    "10B": lambda bytes_data: tuple(bytes_data),
    "f": lambda bytes_data: int.from_bytes(bytes_data, byteorder='big') / 65536.0,
    "Q": lambda bytes_data: struct.unpack('>q', bytes_data)[0],
}

def parse_table(bytes table_bytes, str table_name, tag_filter: Optional[list] = None) -> Dict[str, object]:
    cdef dict data = {}
    cdef dict table_format

    table_format = table_mapper.get(table_name)
    if not table_format:
        raise ValueError(f"undefined table: {table_name}")

    if tag_filter:
        table_format = {k: v for k, v in table_format.items() if k in tag_filter}

    for tag, (offset, length, fmt) in table_format.items():
        byte_slice = table_bytes[offset:offset + length]
        value = byte_parsers.get(fmt, lambda bytes_data: struct.unpack(fmt, bytes_data))(byte_slice)
        data[tag] = value
    return data



def analyseAss(str ass_str) -> Dict[Tuple[str, int, bool], Set[int]]:
    cdef list[str] lines = ass_str.splitlines()
    cdef int state = 0
    cdef int styleNameIndex = -1
    cdef int fontNameIndex = -1
    cdef int boldIndex = -1
    cdef int italicIndex = -1
    cdef dict styleFontName = {}  # 默认字典
    cdef dict styleWeight = {}
    cdef dict styleItalic = {}
    cdef int eventStyleIndex = -1
    cdef int eventTextindex = -1
    cdef dict fontCharList = dict()
    cdef str firstStyleName = ''
    cdef int testState = 0
    cdef str tag = ''
    # cdef str eventText = ''
    for line in lines:
        if line == "":
            continue
        elif state == 0 and line.startswith("[V4+ Styles]"):
            state = 1
        elif state == 1:
            assert line.startswith("Format:"), ValueError("解析Style格式失败 : " + line)
            styleFormat = line[7:].replace(" ", "").split(",")
            for index,style in enumerate(styleFormat):
                if style == "Name":
                    styleNameIndex = index
                if style == "Fontname":
                    fontNameIndex = index
                if style == "Bold":
                    boldIndex = index
                if style == "Italic":
                    italicIndex = index
            assert styleNameIndex != -1 and fontNameIndex != -1, ValueError(
                "Format中未找到Name或Fontname : " + line
            )
            state = 2
        elif state == 2:
            if line.startswith("[Events]"):
                state = 3
            elif line.startswith("Style:"):
                styleData = line[6:].strip().split(",")
                styleName = styleData[styleNameIndex].strip().replace("*", "")
                fontName = styleData[fontNameIndex].strip().replace("@", "")
                fontWeight = 400
                if boldIndex != -1 and styleData[boldIndex].strip() == "1":
                    fontWeight = 700
                fontItalic = False
                if italicIndex != -1 and styleData[italicIndex].strip() == "1":
                    fontItalic = True
                
                styleFontName[styleName] = fontName
                styleWeight[styleName] = fontWeight
                styleItalic[styleName] = fontItalic
                if firstStyleName == '':
                    firstStyleName = styleName
        elif state == 3:
            assert line.startswith("Format:"), ValueError("解析Event格式失败 : " + line)
            eventFormat = line[7:].replace(" ", "").split(",")
            for index,event in enumerate(eventFormat):
                if event == "Style":
                    eventStyleIndex = index
                if event == "Text":
                    eventTextindex = index
            assert eventStyleIndex != -1 and eventTextindex != -1, ValueError("Format中未找到Style或Text : " + line)
            assert eventTextindex == len(eventFormat) - 1, ValueError("Text不是最后一个 : " + line)
            state = 4
        elif state == 4:
            if not line.startswith("Dialogue:"):
                continue
            commaCount = 0 
            styleStart = -1
            styleEnd = -1
            textStart = -1
            dialogue = line[9:]
            # print("dialogue",dialogue)
            # print("eventStyleIndex",eventStyleIndex)
            # print("eventTextindex",eventTextindex)
            for index,char in enumerate(dialogue):
                if char == "," or index == 0 :
                    commaCount += 1
                    if commaCount == eventStyleIndex + 1:
                        styleStart = index + 1
                    if commaCount == eventStyleIndex + 2:
                        styleEnd = index 
                    if commaCount == eventTextindex + 1:
                        textStart = index + 1
                        break
            # print("all:",dialogue)
            # print("style:",dialogue[styleStart:styleEnd])
            # print("text:",dialogue[textStart:])
            styleName = dialogue[styleStart:styleEnd].replace("*" , "")
            eventText = dialogue[textStart:]
            # print(eventText)
            if styleName not in styleFontName:
                styleName = firstStyleName

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
    # cdef str line
    return fontCharList