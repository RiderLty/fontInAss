import struct
from typing import Dict, Optional

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
