from pathlib import Path
import time
from utils import getAllFiles, logger
from py2cy.c_utils import analyseAss as analyseAss_OLD
from lib import analyseAss as analyseAss_NEW
from utils import assInsertLine, bytesToStr, isSRT, bytesToHashName, srtToAss

# for file in getAllFiles("/mnt/storage/Media/EmbyMedia/123pan/" , ["ass"]):
for file in getAllFiles("./test" , ["ass"]):
# for file in ["./test.ass"]:
# for file in ["./test/[UHA-WINGS&VCB-Studio] EIGHTY SIX [S01E02][Ma10p_1080p][x265_flac_aac].chs.ass"]:
    print()
    print()
    print("-"*64)
    print(file)
    with open(file, "rb") as f:
        subtitle = bytesToStr(f.read())

    start = time.perf_counter_ns()

    old = analyseAss_OLD(subtitle)

    middle = time.perf_counter_ns()

    new = analyseAss_NEW(subtitle)

    end = time.perf_counter_ns()

    logger.warning(f"{old == new} {(middle - start) / 1000000:.2f}ms vs {(end - middle ) / 1000000:.2f}ms")

    for k in old.keys():
        old[k] = [chr(x) for x in old[k]]
    for k in new.keys():
        new[k] = [chr(x) for x in new[k]]

    print("keys(old - new) ", [x for x in old if x not in new])
    print("keys(new - old) ", [x for x in new if x not in old])

    if len([x for x in old if x not in new]) + len([x for x in new if x not in old]) == 0:
        for key in old:
            print(key, "(old - new):", str([x for x in old[key] if x not in new[key]]))
            print(key, "(new - old):", str([x for x in new[key] if x not in old[key]]))
    # print(new)