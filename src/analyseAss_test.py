from pathlib import Path
import time
from utils import getAllFiles, logger
from py2cy.c_utils import analyseAss_OLD
from py2cy.c_utils import analyseAssWarp as analyseAss_NEW
from utils import assInsertLine, bytesToStr, isSRT, bytesToHashName, srtToAss
import re

for file in getAllFiles("/mnt/storage/Media/EmbyMedia/123pan/" , ["ass"]):
# for file in getAllFiles("./test" , ["ass"]):
# for file in ["./test.ass"]:
    try:
        print()
        print()
        print("-"*64)
        print(file)
       
        with open(file, "rb") as f:
            subtitleBytes = f.read()
            subtitle = bytesToStr(subtitleBytes)
    
        # for line in subtitle.split("\n"):
        #     if re.search(r'{[^\\]', line):
        #         print(f"{line}")

        start = time.perf_counter_ns()

        old = analyseAss_OLD(subtitle)

        middle = time.perf_counter_ns()

        # new = analyseAss_NEW(__assBytes = subtitleBytes)
        new = analyseAss_NEW(assText = subtitle)

        end = time.perf_counter_ns()
        logger.warning(f"{old == new} {(middle - start) / 1000000:.2f}ms vs {(end - middle ) / 1000000:.2f}ms")
        if old == new :
            continue
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
        print("old=========================\n",old)
        print("new=========================\n",new)
    except Exception as e:
        print(e)
    
    