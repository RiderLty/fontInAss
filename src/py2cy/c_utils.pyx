# cython: language_level=3
import struct
from cpython.unicode cimport PyUnicode_DecodeASCII
from libc.stdlib cimport malloc, free
from libc.string cimport memcpy, memchr
from libc.stdint cimport int64_t
import time

cdef int CHUNK_SIZE = 80
cdef int OFFSET = 33
cdef char chr_map[64]
for i in range(64):
    chr_map[i] = OFFSET + i

def uuencode(const unsigned char[:] binaryData):
    """
    编码工具 (Cython实现)
    https://en.wikipedia.org/wiki/Uuencoding
    https://github.com/weizhenye/ASS/wiki/ASS-%E5%AD%97%E5%B9%95%E6%A0%BC%E5%BC%8F%E8%A7%84%E8%8C%83#9-%E9%99%84%E5%BD%95-b---%E5%86%85%E5%B5%8C%E5%AD%97%E4%BD%93%E5%9B%BE%E7%89%87%E7%BC%96%E7%A0%81
    """
    cdef int data_len = binaryData.shape[0]
    cdef int remainder = data_len % 3
    cdef int encoded_size = (data_len + 2) // 3 * 4
    cdef int encoded_lines_size = encoded_size + (encoded_size + CHUNK_SIZE - 1) // CHUNK_SIZE
    cdef char *encoded = <char *>malloc(encoded_lines_size)
    if not encoded:
        raise MemoryError("Unable to allocate memory for encoded data")
    cdef int packed, i
    cdef int index = 0
    cdef int counter = CHUNK_SIZE
    cdef int six_bit0, six_bit1, six_bit2, six_bit3
    cdef const unsigned char *binaryData_ptr = &binaryData[0]
    try:
        # 遍历 3 字节一组的块
        for i in range(0, data_len - remainder, 3):
            packed = (binaryData_ptr[i] << 16) | (binaryData_ptr[i + 1] << 8) | binaryData_ptr[i + 2]
            six_bit0 = (packed >> 18) & 0x3F
            six_bit1 = (packed >> 12) & 0x3F
            six_bit2 = (packed >> 6) & 0x3F
            six_bit3 = packed & 0x3F
            encoded[index] = chr_map[six_bit0]
            encoded[index + 1] = chr_map[six_bit1]
            encoded[index + 2] = chr_map[six_bit2]
            encoded[index + 3] = chr_map[six_bit3]
            index += 4
            counter -= 4
            if counter == 0:
                encoded[index] = 10
                index += 1
                counter = CHUNK_SIZE

        # 处理不足 3 字节的情况
        if remainder == 1:
            packed = binaryData_ptr[data_len - 1] << 16
            six_bit0 = (packed >> 18) & 0x3F
            six_bit1 = (packed >> 12) & 0x3F
            encoded[index] = chr_map[six_bit0]
            encoded[index + 1] = chr_map[six_bit1]
            index += 2
        elif remainder == 2:
            packed = (binaryData_ptr[data_len - 2] << 16) | (binaryData_ptr[data_len - 1] << 8)
            six_bit0 = (packed >> 18) & 0x3F
            six_bit1 = (packed >> 12) & 0x3F
            six_bit2 = (packed >> 6) & 0x3F
            encoded[index] = chr_map[six_bit0]
            encoded[index + 1] = chr_map[six_bit1]
            encoded[index + 2] = chr_map[six_bit2]
            index += 3
        if index > 0 and counter == CHUNK_SIZE and encoded[index - 1] == 10:
            index -= 1
        return PyUnicode_DecodeASCII(encoded, index, NULL)
    finally:
        free(encoded)

cdef enum FieldType:
    F_UINT16 = 0
    F_INT16  = 1
    F_UINT32 = 2
    F_FIXED  = 3
    F_INT64  = 4
    F_BYTES4 = 5
    F_BYTES10 = 6

cdef struct TableField:
    int offset
    int length
    FieldType type

cdef struct TableFormat:
    TableField* fields
    int field_count

cdef list os2_field_names = [
    "version", "xAvgCharWidth", "usWeightClass", "usWidthClass", "fsType",
    "ySubscriptXSize", "ySubscriptYSize", "ySubscriptXOffset", "ySubscriptYOffset",
    "ySuperscriptXSize", "ySuperscriptYSize", "ySuperscriptXOffset", "ySuperscriptYOffset",
    "yStrikeoutSize", "yStrikeoutPosition", "sFamilyClass", "panose",
    "ulUnicodeRange1", "ulUnicodeRange2", "ulUnicodeRange3", "ulUnicodeRange4",
    "achVendID", "fsSelection", "usFirstCharIndex", "usLastCharIndex",
    "sTypoAscender", "sTypoDescender", "sTypoLineGap", "usWinAscent", "usWinDescent",
    "ulCodePageRange1", "ulCodePageRange2", "sxHeight", "sCapHeight",
    "usDefaultChar", "usBreakChar", "usMaxContext", "usLowerOpticalPointSize",
    "usUpperOpticalPointSize"
]

cdef list head_field_names = [
    "majorVersion", "minorVersion", "fontRevision", "checksumAdjustment",
    "magicNumber", "flags", "unitsPerEm", "created", "modified",
    "xMin", "yMin", "xMax", "yMax", "macStyle", "lowestRecPPEM",
    "fontDirectionHint", "indexToLocFormat", "glyphDataFormat"
]

cdef TableField os2_fields[39]
os2_fields[0]  = TableField(0,   2, F_UINT16)   # version
os2_fields[1]  = TableField(2,   2, F_INT16)    # xAvgCharWidth
os2_fields[2]  = TableField(4,   2, F_UINT16)   # usWeightClass
os2_fields[3]  = TableField(6,   2, F_UINT16)   # usWidthClass
os2_fields[4]  = TableField(8,   2, F_UINT16)   # fsType
os2_fields[5]  = TableField(10,  2, F_INT16)    # ySubscriptXSize
os2_fields[6]  = TableField(12,  2, F_INT16)    # ySubscriptYSize
os2_fields[7]  = TableField(14,  2, F_INT16)    # ySubscriptXOffset
os2_fields[8]  = TableField(16,  2, F_INT16)    # ySubscriptYOffset
os2_fields[9]  = TableField(18,  2, F_INT16)    # ySuperscriptXSize
os2_fields[10] = TableField(20,  2, F_INT16)    # ySuperscriptYSize
os2_fields[11] = TableField(22,  2, F_INT16)    # ySuperscriptXOffset
os2_fields[12] = TableField(24,  2, F_INT16)    # ySuperscriptYOffset
os2_fields[13] = TableField(26,  2, F_INT16)    # yStrikeoutSize
os2_fields[14] = TableField(28,  2, F_INT16)    # yStrikeoutPosition
os2_fields[15] = TableField(30,  2, F_INT16)    # sFamilyClass
os2_fields[16] = TableField(32, 10, F_BYTES10)  # panose
os2_fields[17] = TableField(42,  4, F_UINT32)   # ulUnicodeRange1
os2_fields[18] = TableField(46,  4, F_UINT32)   # ulUnicodeRange2
os2_fields[19] = TableField(50,  4, F_UINT32)   # ulUnicodeRange3
os2_fields[20] = TableField(54,  4, F_UINT32)   # ulUnicodeRange4
os2_fields[21] = TableField(58,  4, F_BYTES4)   # achVendID
os2_fields[22] = TableField(62,  2, F_UINT16)   # fsSelection
os2_fields[23] = TableField(64,  2, F_UINT16)   # usFirstCharIndex
os2_fields[24] = TableField(66,  2, F_UINT16)   # usLastCharIndex
os2_fields[25] = TableField(68,  2, F_INT16)    # sTypoAscender
os2_fields[26] = TableField(70,  2, F_INT16)    # sTypoDescender
os2_fields[27] = TableField(72,  2, F_INT16)    # sTypoLineGap
os2_fields[28] = TableField(74,  2, F_UINT16)   # usWinAscent
os2_fields[29] = TableField(76,  2, F_UINT16)   # usWinDescent
os2_fields[30] = TableField(78,  4, F_UINT32)   # ulCodePageRange1
os2_fields[31] = TableField(82,  4, F_UINT32)   # ulCodePageRange2
os2_fields[32] = TableField(86,  2, F_INT16)    # sxHeight
os2_fields[33] = TableField(88,  2, F_INT16)    # sCapHeight
os2_fields[34] = TableField(90,  2, F_UINT16)   # usDefaultChar
os2_fields[35] = TableField(92,  2, F_UINT16)   # usBreakChar
os2_fields[36] = TableField(94,  2, F_UINT16)   # usMaxContext
os2_fields[37] = TableField(96,  2, F_UINT16)   # usLowerOpticalPointSize
os2_fields[38] = TableField(98,  2, F_UINT16)   # usUpperOpticalPointSize

cdef TableField head_fields[18]
head_fields[0]  = TableField(0,   2, F_UINT16)  # majorVersion
head_fields[1]  = TableField(2,   2, F_UINT16)  # minorVersion
head_fields[2]  = TableField(4,   4, F_FIXED)   # fontRevision
head_fields[3]  = TableField(8,   4, F_UINT32)  # checksumAdjustment
head_fields[4]  = TableField(12,  4, F_UINT32)  # magicNumber
head_fields[5]  = TableField(16,  2, F_UINT16)  # flags
head_fields[6]  = TableField(18,  2, F_UINT16)  # unitsPerEm
head_fields[7]  = TableField(20,  8, F_INT64)   # created
head_fields[8]  = TableField(28,  8, F_INT64)   # modified
head_fields[9]  = TableField(36,  2, F_INT16)   # xMin
head_fields[10] = TableField(38,  2, F_INT16)   # yMin
head_fields[11] = TableField(40,  2, F_INT16)   # xMax
head_fields[12] = TableField(42,  2, F_INT16)   # yMax
head_fields[13] = TableField(44,  2, F_UINT16)  # macStyle
head_fields[14] = TableField(46,  2, F_UINT16)  # lowestRecPPEM
head_fields[15] = TableField(48,  2, F_INT16)   # fontDirectionHint
head_fields[16] = TableField(50,  2, F_INT16)   # indexToLocFormat
head_fields[17] = TableField(52,  2, F_INT16)   # glyphDataFormat

cdef TableFormat table_formats[2]
table_formats[0] = TableFormat(&os2_fields[0], sizeof(os2_fields) // sizeof(TableField))
table_formats[1] = TableFormat(&head_fields[0], sizeof(head_fields) // sizeof(TableField))

cdef inline int parse_uint16(const unsigned char *data):
    return (data[0] << 8) | data[1]

cdef inline int parse_int16(const unsigned char *data):
    cdef int val = (data[0] << 8) | data[1]
    return val - 0x10000 if val & 0x8000 else val

cdef inline unsigned int parse_uint32(const unsigned char *data):
    return (data[0] << 24) | (data[1] << 16) | (data[2] << 8) | data[3]

cdef inline float parse_fixed(const unsigned char *data):
    return parse_uint32(data) / 65536.0

cdef inline int64_t parse_int64(const unsigned char* data):
    return (
        (<int64_t>data[0] << 56) |
        (<int64_t>data[1] << 48) |
        (<int64_t>data[2] << 40) |
        (<int64_t>data[3] << 32) |
        (<int64_t>data[4] << 24) |
        (<int64_t>data[5] << 16) |
        (<int64_t>data[6] << 8) |
        <int64_t>data[7]
    )

cdef inline tuple parse_bytes10(const unsigned char* data):
    return (
        data[0], data[1], data[2], data[3], data[4],
        data[5], data[6], data[7], data[8], data[9]
    )
cdef object parse_bytes4(const unsigned char* p):
    cdef const void* null_pos = memchr(p, 0, 4)
    cdef Py_ssize_t length
    if null_pos != NULL:
        length = <const char*>null_pos - <const char*>p
    else:
        length = 4
    return PyUnicode_DecodeASCII(<char*>p, length, "strict")

def parse_table(bytes table_bytes, str table_name, tag_filter: list[int] = None, py_dict = False):
    cdef unsigned char *raw_data = <unsigned char *> table_bytes
    cdef int table_length = len(table_bytes)
    cdef TableFormat* table_format
    cdef list field_names
    cdef int i
    cdef TableField field

    if table_name == "OS/2":
        table_format = &table_formats[0]
        field_names = os2_field_names
    elif table_name == "head":
        table_format = &table_formats[1]
        field_names = head_field_names
    else:
        raise ValueError(f"Undefined table: {table_name}")

    cdef list indices = tag_filter if tag_filter is not None else list(range(table_format.field_count))
    cdef list values = [0] * len(indices)

    cdef unsigned char* ptr
    cdef tuple byte_tuple

    for i, idx in enumerate(indices):
        field = table_format.fields[idx]

        if field.offset + field.length > table_length:
            values[i] = 0
        elif field.type == F_UINT16:
            values[i] = parse_uint16(raw_data + field.offset)
        elif field.type == F_INT16:
            values[i] = parse_int16(raw_data + field.offset)
        elif field.type == F_UINT32:
            values[i] = parse_uint32(raw_data + field.offset)
        elif field.type == F_FIXED:
            values[i] = parse_fixed(raw_data + field.offset)
        elif field.type == F_INT64:
            values[i] = parse_int64(raw_data + field.offset)
        elif field.type == F_BYTES10:
            values[i] = parse_bytes10(raw_data + field.offset)
        elif field.type == F_BYTES4:
            values[i] = parse_bytes4(raw_data + field.offset)

    if py_dict:
        return {field_names[idx]: val for idx, val in zip(indices, values)}
    else:
        return tuple(values)

cdef extern from "cpp_utils.cpp":
    unsigned char *analyseAss_CPP(const char *assStr)
    void ptrFree(unsigned char *ptr)


def analyseAss(assText: str = None, assBytes: bytes = None):
    if assBytes == None:
        start = time.perf_counter_ns()
        assChars = assText.encode("UTF-8")  # 耗时 考虑直接传递bytes
        middle = time.perf_counter_ns()
        # print("encode time:", (middle - start) / 1000000 , "ms")
    else:
        assChars = assBytes
    cdef unsigned char* result = analyseAss_CPP(assChars)
    itemCount = struct.unpack("I", result[:4])[0]
    index = 4
    anaResult = {}
    for i in range(itemCount):
        nameLen = struct.unpack("I",result[index : index + 4])[0]
        index += 4
        fontNname = result[index : index + nameLen].decode("utf-8")
        index += nameLen
        weight = struct.unpack("I", result[index : index + 4])[0]
        index += 4

        italic = 0 != struct.unpack("I", result[index : index + 4])[0]
        index += 4

        resultLen = struct.unpack("I", result[index : index + 4])[0]
        index += 4

        valueSet = set()
        anaResult[(fontNname, weight, italic)] = valueSet

        for i in range(resultLen):
            value = struct.unpack("I", result[index : index + 4])[0]
            index += 4
            valueSet.add(value)

    subRenameItemCount = struct.unpack("I", result[index : index + 4])[0]
    index += 4
    subRename = {}
    for i in range(subRenameItemCount):
        replacedName = result[index : index + 8].decode("utf-8")
        index += 8
        originNameLen = struct.unpack("I",result[index : index + 4])[0]
        index += 4
        originName = result[index : index + originNameLen].decode("utf-8")
        index += originNameLen
        subRename[replacedName] = originName
    ptrFree(result);
    return anaResult,subRename