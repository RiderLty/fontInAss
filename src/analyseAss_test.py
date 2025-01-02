from pathlib import Path
import time
from utils import getAllFiles, logger

# from viztracer import VizTracer  # type: ignore

# from analyseAss import analyseAss

# subtitles: list[str] = []
# for path in (Path(__file__).parent.parent / "test").iterdir():
#     print(path)
#     subtitles.append(path.read_text(encoding="utf-8"))

# with VizTracer() as tracer:
#     for subtitle in subtitles:
#         analyseAss(subtitle)








# from analyseAss import analyseAss as analyseAss_PY
# from py2cy.c_utils import analyseAss as analyseAss_CY

# subtitles: list[str] = []
# for path in (Path(__file__).parent.parent / "test").iterdir():
#     print(path)
#     subtitle = path.read_text(encoding="utf-8")
    
#     start = time.perf_counter_ns()
#     for i in range(10):
#         p = analyseAss_PY(subtitle)
#     logger.warning(f"py used {(time.perf_counter_ns() - start) / 1000000_0:.2f}ms")

#     start = time.perf_counter_ns()
#     for i in range(10):
#         c = analyseAss_CY(subtitle)
#     logger.warning(f"cy used {(time.perf_counter_ns() - start) / 1000000_0:.2f}ms")
    
#     if p != c:
#         print("NOT SAME")
#         for key in p:
#             if p[key] !=  c[key]:
#                 print(key , p[key] - c[key] , c[key]  - p[key])






from analyseAss import analyseAss as analyseAss_PY
from py2cy.c_utils import analyseAss as analyseAss_CY
from utils import assInsertLine, bytesToStr, isSRT, bytesToHashName, srtToAss
for file in getAllFiles("/mnt/storage/Media/EmbyMedia/123pan/" , ["ass"]):
    print(file)
    with open(file,"rb") as f:
        subtitle = bytesToStr(f.read())
    
    start = time.perf_counter_ns()

    p = analyseAss_PY(subtitle)

    middle = time.perf_counter_ns()

    c = analyseAss_CY(subtitle)

    end = time.perf_counter_ns()

    logger.warning(f"{p == c} {(middle - start) / 1000000:.2f}ms vs {(end - middle ) / 1000000:.2f}ms")
