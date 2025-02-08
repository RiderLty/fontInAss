import ctypes
import struct
import time
import platform
from pathlib import Path
from setuptools import setup, Extension
from Cython.Build import cythonize

file_dir = Path(__file__).parent

if platform.system() == "Windows":
    cdllPath = file_dir / "analyseAss.dll"
elif platform.system() in ["Linux", "Darwin"]:
    cdllPath = file_dir / "analyseAss.so"

lib = ctypes.CDLL(cdllPath)
lib.analyseAss.restype = ctypes.POINTER(ctypes.c_ubyte)


def analyseAss(assText: str):
    assBytes = assText.encode("UTF-8")  #耗时 考虑直接传递bytes
    # start = time.perf_counter_ns()
    result = lib.analyseAss(assBytes)
    # print(f"耗时 {(time.perf_counter_ns() - start) / 1_000_000:.2f}ms")
    itemCount = struct.unpack("i", bytes(result[:4]))[0]
    index = 4
    anaResult = {}
    for i in range(itemCount):
        nameLen = struct.unpack("i", bytes(result[index : index + 4]))[0]
        index += 4
        fontNname = bytes(result[index : index + nameLen]).decode("utf-8")
        index += nameLen
        weight = struct.unpack("i", bytes(result[index : index + 4]))[0]
        index += 4

        italic = 0 != struct.unpack("i", bytes(result[index : index + 4]))[0]
        index += 4

        resultLen = struct.unpack("i", bytes(result[index : index + 4]))[0]
        index += 4

        valueSet = set()
        anaResult[(fontNname, weight, italic)] = valueSet

        for i in range(resultLen):
            value = struct.unpack("i", bytes(result[index : index + 4]))[0]
            index += 4
            valueSet.add(value)

    # print(anaResult)
    return anaResult


if __name__ == "__main__":
    # with open("/mnt/storage/Projects/fontInAss/test/[UHA-WINGS&VCB-Studio] EIGHTY SIX [S01E01][Ma10p_1080p][x265_flac_aac].chs.ass", "r", encoding="UTF-8-sig") as f:
    with open("/mnt/storage/Projects/fontInAss/test.ass", "r", encoding="UTF-8-sig") as f:
        res = analyseAss(f.read())
        print(res)
