def uuencode(const unsigned char[:] binaryData):
    """
    编码工具 (Cython实现)
    """
    cdef int OFFSET = 33
    cdef int CHUNK_SIZE = 20
    cdef int data_len = len(binaryData)
    cdef int remainder = data_len % 3
    cdef list encoded = [None] * ((data_len + 2) // 3)  # 预分配 `encoded` 大小
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
