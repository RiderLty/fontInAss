# import json
# import sys
# import time
# import warnings

# from analyseAss import analyseAss


# warnings.filterwarnings("ignore")

# import os


# import ssl
# import logging
# import asyncio
# import requests
# import traceback
# import coloredlogs
# from fastapi import FastAPI, Request, Response
# from fastapi.responses import HTMLResponse
# from uvicorn import Config, Server
# from constants import FT_STYLE_FLAG_BOLD, FT_STYLE_FLAG_ITALIC, logger, EMBY_SERVER_URL, FONT_DIRS, DEFAULT_FONT_PATH, MAIN_LOOP
# from dirmonitor import dirmonitor
# from fontManager import fontManager
# from assSubsetter import assSubsetter
# from py2cy.c_utils import uuencode
# from utils import assInsertLine, bytesToHashName, bytesToStr, getFontScore, strCaseCmp, tagToInteger


# def init_logger():
#     LOGGER_NAMES = (
#         "uvicorn",
#         "uvicorn.access",
#     )
#     for logger_name in LOGGER_NAMES:
#         logging_logger = logging.getLogger(logger_name)
#         fmt = f"🌏 %(asctime)s.%(msecs)03d .%(levelname)s \t%(message)s"  # 📨
#         coloredlogs.install(
#             level=logging.DEBUG,
#             logger=logging_logger,
#             milliseconds=True,
#             datefmt="%X",
#             fmt=fmt,
#         )


# # app = Bottle()
# app = FastAPI()

# process = None

# userHDR = 0


# @app.post("/setHDR/{value}")
# async def setHDR(value: int):
#     """实时调整HDR，-1 禁用HDR，0 使用环境变量值，大于0 替代当前值"""
#     global userHDR
#     userHDR = value
#     logger.error(f"临时HDR 已设置为 {userHDR}")
#     return value


# @app.get("/setHDR", response_class=HTMLResponse)
# async def setHDRIndex():
#     return """
# <!DOCTYPE html>
# <html lang="en">
# <head>
#     <meta charset="UTF-8">
#     <meta name="viewport" content="width=device-width, initial-scale=1.0">
#     <title>临时调整HDR</title>
#     <style>
#         body {
#             font-family: Arial, sans-serif;
#             display: flex;
#             justify-content: center;
#             align-items: center;
#             flex-direction: column;
#             height: 80vh;
#             color: #BDBDBD;
#             background-color: #212121;
#         }
#         .slider-container {
#             text-align: center;
#             margin-bottom: 20px;
#         }
#         input[type="range"] {
#             width: 80vw;
#         }
#         button {
#             margin: 5px;
#             padding: 10px 20px;
#             font-size: 16px;
#             border-radius: 16px;
#             color: #000000;
#         }
#     </style>
# </head>
# <body>
#     <div class="slider-container">
#         <h1>Set HDR Value</h1>
#         <input type="range" id="hdrSlider" min="1" max="10000" value="0">
#         <p>Current Value: <span id="sliderValue">0</span></p>
#         <button id="disableButton">禁用</button>
#         <button id="defaultButton">默认</button>
#     </div>

#     <script>
#         const slider = document.getElementById('hdrSlider');
#         const sliderValue = document.getElementById('sliderValue');
#         const disableButton = document.getElementById('disableButton');
#         const defaultButton = document.getElementById('defaultButton');

#         function calculateNonLinearValue(value) {
#             const normalizedValue = value / 10000; // Normalize to 0-1
#             return Math.pow(normalizedValue, 3) * 10000; // Apply exponent of 3
#         }

#         slider.addEventListener('input', () => {
#             const nonLinearValue = calculateNonLinearValue(slider.value);
#             sliderValue.textContent = Math.round(nonLinearValue);
#         });

#         slider.addEventListener('change', async () => {
#             const value = calculateNonLinearValue(slider.value);
#             await sendValue(Math.round(value));
#         });

#         disableButton.addEventListener('click', async () => {
#             await sendValue(-1);
#         });

#         defaultButton.addEventListener('click', async () => {
#             await sendValue(0);
#         });

#         async function sendValue(value) {
#             const response = await fetch(`/setHDR/${value}`, {
#                 method: 'POST' // 使用 POST 方法
#             });
#             if (response.ok) {
#                 console.log(`Value ${value} sent to /setHDR/${value}`);
#             } else {
#                 console.error('Error sending value:', response.status);
#             }
#         }
#     </script>
# </body>
# </html>
# """


# @app.get("/{path:path}")
# async def proxy_pass(request: Request, response: Response):
#     try:
#         sourcePath = f"{request.url.path}?{request.url.query}" if request.url.query else request.url.path
#         embyRequestUrl = EMBY_SERVER_URL + sourcePath
#         logger.info(f"字幕URL: {embyRequestUrl}")
#         serverResponse = requests.get(url=embyRequestUrl, headers=request.headers)
#         # copyHeaders = {key: str(value) for key, value in response.headers.items()}
#     except Exception as e:
#         logger.error(f"获取原始字幕出错:{str(e)}")
#         return ""
#     try:
#         subtitleBytes = serverResponse.content
#         srt, bytes = await process(subtitleBytes, userHDR)
#         logger.info(f"字幕处理完成: {len(subtitleBytes) / (1024 * 1024):.2f}MB ==> {len(bytes) / (1024 * 1024):.2f}MB")
#         # copyHeaders["Content-Length"] = str(len(bytes))
#         if srt and ("user-agent" in request.headers) and ("infuse" in request.headers["user-agent"].lower()):
#             logger.error("infuse客户端，无法使用SRT转ASS功能，返回原始字幕")
#             return Response(content=subtitleBytes)
#         return Response(content=bytes)
#     except Exception as e:
#         logger.error(f"处理出错，返回原始内容 : \n{traceback.format_exc()}")
#         return Response(content=serverResponse.content)


# def getServer(port, serverLoop):
#     serverConfig = Config(
#         app=app,
#         # host="::",
#         host="0.0.0.0",
#         port=port,
#         log_level="info",
#         loop=serverLoop,
#         ws_max_size=1024 * 1024 * 1024 * 1024,
#     )
#     return Server(serverConfig)


# # "[UHA-WINGS&VCB-Studio] EIGHTY SIX [S01E03][Ma10p_1080p][x265_flac_aac].chs.ass",
# # "[UHA-WINGS&VCB-Studio] EIGHTY SIX [S01E02][Ma10p_1080p][x265_flac_aac].chs.ass",
# # analyseAss 约40ms


# # async def test():
# #     files = [
# #         # "test/[UHA-WINGS&VCB-Studio] EIGHTY SIX [S01E04][Ma10p_1080p][x265_flac_aac].chs.ass",
# #         # "test/[UHA-WINGS&VCB-Studio] EIGHTY SIX [S01E03][Ma10p_1080p][x265_flac_aac].chs.ass",
# #         # "test/[UHA-WINGS&VCB-Studio] EIGHTY SIX [S01E02][Ma10p_1080p][x265_flac_aac].chs.ass",
# #         # "test/[UHA-WINGS&VCB-Studio] EIGHTY SIX [S01E01][Ma10p_1080p][x265_flac_aac].chs.ass",
# #         # "test/[DMG&SumiSora&VCB-Studio] Engage Kiss [S01E07][Ma10p_1080p][x265_flac].chs.ass"
# #         # "test/[Ygm&MAI] JoJo's Bizarre Adventure - Stone Ocean [S05E01][Ma10p_2160p][x265_flac_ass].extract.ass"
# #         "test/[Ygm&MAI] JoJo's Bizarre Adventure - Stardust Crusaders [S02E47][Ma10p_2160p][x265_DTS-HDMA_ass].chs.ass"
# #     ]
# #     for file in files:
# #         with open(file, "rb") as f:
# #             subtitleBytes = f.read()
# #         start = time.perf_counter_ns()
# #         await process(subtitleBytes)
# #         logger.error(f"测试完成 用时 {(time.perf_counter_ns() - start) / 1000000:.2f} ms")
# #         logger.error(f"")

# #     for file in files:
# #         with open(file, "rb") as f:
# #             subtitleBytes = f.read() + b"0"
# #         start = time.perf_counter_ns()
# #         await process(subtitleBytes)
# #         logger.error(f"测试完成 用时 {(time.perf_counter_ns() - start) / 1000000:.2f} ms")
# #         logger.error(f"")


# # def initpass():
# #     pass


# # def worker(start):
# #     logger.error(f"启动用时 {(time.perf_counter_ns() - start) / 1000000:.2f} ms")
# #     return time.perf_counter_ns()


# # async def submit(pool):
# #     start = time.perf_counter_ns()
# #     end = await MAIN_LOOP.run_in_executor(pool, worker, start)
# #     logger.debug(f"运行用时 {(end - start) / 1000000:.2f} ms")


# # async def testPool():
# #     pool = ProcessPoolExecutor(max_workers=int(os.cpu_count()))
# #     pool.submit(initpass)
# #     await asyncio.gather(*[submit(pool) for _ in range(10)])
# #     pool.shutdown()
# from pathlib import Path
# import shlex
# import os
# import subprocess

# from io import BytesIO
# import os
# from fontTools.ttLib import TTCollection, TTFont
# import uharfbuzz


# def executeCommand(command_with_args, content):
#     try:
#         proc = subprocess.Popen(
#             shlex.split(command_with_args),
#             stdout=subprocess.DEVNULL,
#             stderr=subprocess.PIPE,
#             universal_newlines=True,
#         )
#         with open(r"/mnt/storage/Projects/fontInAss/asspipe", "wb") as f:
#             print
#             f.write(content)
#         _, stderr = proc.communicate()
#         return {
#             "code": proc.returncode,
#             "out": None,
#             "error": stderr,
#         }
#     except Exception as generic_e:
#         return {
#             "code": -30,
#             "out": "",
#             "error": generic_e,
#         }


# def getAllFiles(path):
#     Filelist = []
#     for home, _, files in os.walk(path):
#         for filename in files:
#             if Path(filename).suffix.lower()[1:] in ["ttc", "ttf", "otf"]:
#                 # 保证所有系统下\\转变成/
#                 Filelist.append(Path(home, filename).as_posix())
#     return Filelist


# def rle_compress_optimized(bitmap):
#     """RLE 压缩，假设第一个值是 0，后续值交替出现。"""
#     compressed = []
#     count = 1
#     for i in range(1, len(bitmap)):
#         if bitmap[i] == bitmap[i - 1]:
#             count += 1
#         else:
#             compressed.append(count)
#             count = 1
#     compressed.append(count)  # 添加最后一段
#     return compressed


# def is_bit_set_in_rle(compressed, index):
#     """
#     判断位图某一位是否为 1（基于优化 RLE 压缩数据）。

#     :param compressed: 压缩后的长度列表。
#     :param index: 要判断的目标位索引。
#     :return: True if the bit is 1, else False.
#     """
#     position = 0  # 当前段起始位置
#     for i, length in enumerate(compressed):
#         if position + length > index:
#             # 判断目标位是否在当前段
#             return i % 2 == 1  # 偶数段是 0，奇数段是 1
#         position += length
#     raise IndexError("索引超出位图范围")  # 如果索引超出范围


# def rle_decompress_optimized(compressed):
#     """解压 RLE 压缩的位图，第一个值为 0，后续值交替。"""
#     bitmap = []
#     current_value = 0  # 第一个值默认为 0
#     for count in compressed:
#         bitmap.extend([current_value] * count)
#         current_value = 1 - current_value  # 交替切换 0 和 1
#     return bitmap


# def getFontCmap(keys):
#     max_unicode = 0x10FFFF
#     bitmap = [0] * (max_unicode + 1)
#     for code in keys:
#         bitmap[code] = 1
#     return rle_compress_optimized(bitmap)


# # unicodes = set()
# # for table in font["cmap"].tables:
# #     if table.isUnicode():
# #         unicodes.update(table.cmap.keys())
# # fontInfo["cmapMap"] = getFontCmap(unicodes)


# def makeAss(font="", fontname="Arial"):
#     txt = (
#         """[Script Info]
# ; Script generated by Aegisub 3.3.3
# ; http://www.aegisub.org/
# Title: [Nekomoe kissaten] Isekai wa Smartphone to Tomo ni. [05][BDRip 1080p HEVC-10bit FLAC_AAC].SC
# ScriptType: v4.00+
# WrapStyle: 0
# ScaledBorderAndShadow: yes
# YCbCr Matrix: TV.601
# PlayResX: 1920
# PlayResY: 1080

# [Aegisub Project Garbage]
# Last Style Storage: lv1
# Audio File: E:/1/[Beatrice-Raws] Isekai wa Smartphone to Tomo ni [BDRip 1920x1080 x264 FLAC]/[Beatrice-Raws] Isekai wa Smartphone to Tomo ni 05 [BDRip 1920x1080 x264 FLAC].mkv
# Video File: E:/1/[Beatrice-Raws] Isekai wa Smartphone to Tomo ni [BDRip 1920x1080 x264 FLAC]/[Beatrice-Raws] Isekai wa Smartphone to Tomo ni 05 [BDRip 1920x1080 x264 FLAC].mkv
# Video AR Mode: 4
# Video AR Value: 1.777778
# Video Zoom Percent: 0.250000
# Scroll Position: 1626
# Active Line: 1675
# Video Position: 4193
# """
#         + font
#         + """[V4+ Styles]
# Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
# Style: Default,"""
#         + fontname
#         + """,120,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,3,3,2,15,15,15,1

# [Events]
# Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
# Dialogue: 3,0:00:00.00,0:59:00.00,Default,,0,0,0,fx,HELLO
# """
#     )
#     # print(txt)
#     return txt.encode("UTF-8-sig")


# async def test():
#     # print("ok")
#     # bytes = (await process(open("test.ass", "rb").read()))[1]
#     # with open("test_emb.ass", "wb") as f:
#     #     f.write(bytes)
#     files = getAllFiles(r"/mnt/storage/Fonts/超级字体整合包 XZ")
#     print("共", len(files))
#     fontInfoList = []
#     for fileIndex, file in enumerate(files):
#         # if "何尼玛" not in file :
#         # continue
#         print(f"{fileIndex}/{len(files)} : {file}")
#         try:
#             # fontInfoList.extend(loadFontInfo(file))

#             # for index, nameID, fontName in font_detail_list:
#             #     face = uharfbuzz.Face(data, index)
#             #     inp = uharfbuzz.SubsetInput()
#             #     inp.sets(uharfbuzz.SubsetInputSets.UNICODE).set([ord(x) for x in "HELLO"])
#             #     assert "name" in face.table_tags, ValueError("name 表未找到")
#             #     inp.sets(uharfbuzz.SubsetInputSets.NO_SUBSET_TABLE_TAG).set({tagToInteger("name")})
#             #     face = uharfbuzz.subset(face, inp)
#             #     enc = uuencode(face.blob.data)
#             #     del face
#             #     content = makeAss(f"[Fonts]\nfontname:{fontName}_0.ttf\n{enc}\n", fontName)
#             #     # print(content)
#             #     res = executeCommand(
#             #         'ffmpeg -f lavfi -i color=#000000@0:s=1920x1080 -vf "subtitles=/mnt/storage/Projects/fontInAss/asspipe" -ss 3 -vframes 1 -vsync 0 -f image2pipe -vframes 1 -', content
#             #     )
#             #     # 使用默认字体 ，则说明匹配失败
#             #     # 默认字体需要手动定义
#             #     success = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf" not in res["error"]
#             #     # print(res["error"])
#             #     print(success, "\t", index, "\t", nameID, "\t", fontName)
#             pass
#         except Exception as e:
#             print(e)
#         # break
#     with open("newFontMapNOCMAP.json", "w", encoding="UTF-8") as f:
#         print(len(fontInfoList))
#         f.write(json.dumps(fontInfoList, indent=4, ensure_ascii=False))


# """
# fontList:

# [
#     {
#         path : "path/to/fonts",
#         size : int 得分相同的情况下，选择大小最小的
#         index: index of font in fonts
#         allNames : [ 全部名称 family， fullname ， postscriptname ] # 用于在外部判断，allNames不包括的不会进来筛选
#         family: []
#         postscriptName: []
#         fullName:[]
#         weight: int
#         bold: bool 是否粗体
#         italic: bool 是否斜体
#         postscriptCheck: bool 是否是postscript类型
#         cmapMap : [int] 压缩过的
#     },
#     ...
# ]

# """


# async def selectFont():
#     with open("newFontMapNOCMAP.json", "r", encoding="UTF-8") as f:
#         data = json.loads(f.read())
#     fontName = "Arial"
#     weight = 700
#     italic = False
#     start = time.perf_counter_ns()
#     scores = {}
#     miniScore = sys.maxsize
#     for fontInfo in data:
#         if fontName in fontInfo["allNames"]:
#             score = getFontScore(fontName, weight, italic, fontInfo)
#             miniScore = min(miniScore, score)
#             scores.setdefault(score, []).append(fontInfo)
#     if scores == {}:
#         return None
#     else:
#         target = sorted(scores[miniScore], key=lambda x: x["size"], reverse=False)[0]
#         print(target)
#     end = time.perf_counter_ns()
#     logger.info(f"耗时 {(end - start) / 1_000_000:.2f}ms")


# if __name__ == "__main__":

#     logger.info("本地字体文件夹:" + ",".join(FONT_DIRS))
#     os.makedirs(DEFAULT_FONT_PATH, exist_ok=True)
#     asyncio.set_event_loop(MAIN_LOOP)
#     ssl._create_default_https_context = ssl._create_unverified_context
#     fontManagerInstance = fontManager()
#     assSubsetterInstance = assSubsetter(fontManagerInstance=fontManagerInstance)
#     event_handler = dirmonitor(callBack=fontManagerInstance)  # 创建fonts字体文件夹监视实体
#     event_handler.start()
#     process = assSubsetterInstance.process  # 绑定函数
#     serverInstance = getServer(8011, MAIN_LOOP)
#     init_logger()

#     # MAIN_LOOP.run_until_complete(test())
#     # MAIN_LOOP.run_until_complete(selectFont())
#     async def loadTEst():
#         # await fontManagerInstance.loadFont__("Arial",400,False)
#         # await fontManagerInstance.loadFont__("Arial",700,False)
#         # await fontManagerInstance.loadFont__("Arial",400,True)
#         # await fontManagerInstance.loadFont__("Arial",700,True)

#         # await fontManagerInstance.loadFont__("Arial",400,False)
#         files = [
#             "test/[UHA-WINGS&VCB-Studio] EIGHTY SIX [S01E04][Ma10p_1080p][x265_flac_aac].chs.ass",
#             "test/[UHA-WINGS&VCB-Studio] EIGHTY SIX [S01E03][Ma10p_1080p][x265_flac_aac].chs.ass",
#             "test/[UHA-WINGS&VCB-Studio] EIGHTY SIX [S01E02][Ma10p_1080p][x265_flac_aac].chs.ass",
#             "test/[UHA-WINGS&VCB-Studio] EIGHTY SIX [S01E01][Ma10p_1080p][x265_flac_aac].chs.ass",
#             r"test/[Ygm&MAI] JoJo's Bizarre Adventure - Stone Ocean [S05E01][Ma10p_2160p][x265_flac_ass].extract.ass",
#             r"test/[Ygm&MAI] JoJo's Bizarre Adventure - Stardust Crusaders [S02E47][Ma10p_2160p][x265_DTS-HDMA_ass].chs.ass",
#         ]

#         for file in files:
#             with open(file, "rb") as f:
#                 subtitleBytes = f.read()
#             start = time.perf_counter_ns()
#             # print(analyseAss_libassLike( bytesToStr(subtitleBytes) ))
#             # assInsertLine(bytesToStr(subtitleBytes),"hello insert")
#             print(assInsertLine(bytesToStr(subtitleBytes),"hello insert"))
#             logger.error(f"测试完成 用时 {(time.perf_counter_ns() - start) / 1000000:.2f} ms")
#             logger.error(f"")

#     MAIN_LOOP.run_until_complete(loadTEst())

#     # # 关闭和清理资源
#     event_handler.stop()  # 停止文件监视器
#     event_handler.join()  # 等待文件监视退出
#     fontManagerInstance.close()  # 关闭aiohttp的session
#     # assSubsetterInstance.close()  # 关闭进程池
#     pending = asyncio.all_tasks(MAIN_LOOP)
#     MAIN_LOOP.run_until_complete(asyncio.gather(*pending, return_exceptions=True))  # 等待异步任务结束
#     MAIN_LOOP.stop()  # 停止事件循环
#     MAIN_LOOP.close()  # 清理资源

# # from io import BytesIO
# # import os
# # from fontTools.ttLib import TTCollection, TTFont
# # from fontTools.misc.encodingTools import getEncoding


# # def gen_font_info( file_path):
# #         with open(file_path, "rb") as f:
# #             data = f.read()
# #         sfntVersion = data[:4]
# #         print('sfntVersion == b"ttcf" ? ', sfntVersion == b"ttcf")
# #         fonts = TTCollection(BytesIO(data)).fonts if sfntVersion == b"ttcf" else [TTFont(BytesIO(data))]
# #         file_size = os.path.getsize(file_path)
# #         file_mtime = int(os.path.getmtime(file_path))
# #         font_count = len(fonts)
# #         # 直接构造 font_info_list 和 font_detail_list
# #         font_info_list = [{
# #             "file_path": file_path,
# #             "file_size": file_size,
# #             "file_mtime": file_mtime,
# #             "font_count": font_count
# #         }]
# #         font_detail_list = []
# #         for index, font in enumerate(fonts):
# #             print("\nfontIndex = ",index)
# #             family = []
# #             for record in font["name"].names:
# #                 if record.nameID in [1,2,4,6,16,17]:
# #                     fontName = str(record).strip()
# #                     jpname = str(record.toBytes().decode('shift_jis', errors='ignore'))
# #                     # fontName = str(record.toBytes())
# #                     # print(help(record))
# #                     print(f"RECID = {record.nameID} encoding = {record.getEncoding()}\t:{fontName}\tshift_jis decode[{jpname}]" )
# #             continue
# #             print("Font Tables:")
# #             for table in font.keys():
# #                 print(f"- {table}")

# #             # 获取 'name' 表的信息（包含字体名称等元数据）
# #             name_table = font["name"]
# #             print("\nName Table Entries:")
# #             for record in name_table.names:
# #                 name_id = record.nameID
# #                 platform_id = record.platformID
# #                 enc_id = record.platEncID
# #                 lang_id = record.langID
# #                 string = record.string.decode(record.getEncoding(), errors="replace")

# #                 # print("getEncoding():",getEncoding(record.platformID ,enc_id ,lang_id))


# #                 print(f"NameID {name_id} (Platform {platform_id}, Lang {lang_id}): {string}")

# #             # 获取 'head' 表的信息（包含头部元数据，如版本、创建时间等）
# #             head_table = font["head"]
# #             print("\nHead Table Info:")
# #             print(f"Font Revision: {head_table.fontRevision}")
# #             print(f"Created: {head_table.created}")
# #             print(f"Modified: {head_table.modified}")
# #             print(f"Units per EM: {head_table.unitsPerEm}")
# #             print(f"Lowest Rec PPEM: {head_table.lowestRecPPEM}")

# #             # 获取其他表的内容（如 'OS/2'，包含版权、权重等信息）
# #             os2_table = font["OS/2"]
# #             print("\nOS/2 Table Info:")
# #             print(f"Weight Class: {os2_table.usWeightClass}")
# #             print(f"Width Class: {os2_table.usWidthClass}")
# #             print(f"License Type: {os2_table.fsType}")


# #         return font_info_list, font_detail_list

# # gen_font_info(r"fonts/何尼玛-细体 常规.ttf")
# # print("=============================================")
# # # gen_font_info(r"fonts/何尼玛-细体-改.ttf")
# # gen_font_info(r"fonts/何尼玛-细体-去全.ttf")

# # # gen_font_info(r"fonts/DFSoGei-W7 & DFPSoGei-W7 & DFGSoGei-W7.ttc")
# # # gen_font_info(r"fonts/[128] ＤＦ綜藝体W7.ttc")

# # # gen_font_info(r"fonts/NotoSansCJKtc-Bold 1.004.otf")
# # # print("=============================================")
# # # gen_font_info(r"fonts/NotoSansCJKtc-Bold 2.001.otf")
# # # gen_font_info(r"fonts/黑体-繁 细体 & 黑体-简 细体 & .Heiti GB18030PUA Light & .黑体-韩语 细体 & .黑体-日本语 细体 & 何尼玛-细体 常规.ttc")


# # from PIL import Image
# # from datetime import timedelta
# # import ass
# # from ass.renderer import Context
# # with open("test.ass", "r" , encoding="UTF-8-sig") as f:
# #     doc = ass.parse(f)

# # print(doc.styles)
# # ctx = Context()
# # t = ctx.make_track()
# # t.populate(doc)
# # r = ctx.make_renderer()
# # r.set_fonts(fontconfig_config="/etc/fonts/fonts.conf")
# # r.set_all_sizes((1920, 1080))
# # im_out = Image.new("RGB", (1920,1080), 0xffffff)
# # im_data = im_out.load()

# # for img in r.render_frame(t, timedelta(0)):
# #     r, g, b, a = img.rgba

# #     for y in range(img.h):
# #         for x in range(img.w):
# #             a_src = img[x, y] * (256 - a) // 256
# #             r_dst, g_dst, b_dst = im_data[x + img.dst_x, y + img.dst_y]
# #             r_out = ((r * a_src) + (r_dst * (256 - a_src))) // 256
# #             g_out = ((g * a_src) + (g_dst * (256 - a_src))) // 256
# #             b_out = ((b * a_src) + (b_dst * (256 - a_src))) // 256
# #             im_data[x + img.dst_x, y + img.dst_y] = (r_out, g_out, b_out)

# # im_out.save("test.png")


# import json
# with open(r"onlineFonts.json",'r') as f:
#     index,data = json.loads(f.read())
#     for rec in data:
#         print(rec["italic"])


# import ctypes
# import os
# from ctypes import c_char, c_char_p, c_void_p, c_int, POINTER, c_size_t

# def getAllFiles(path):
#     Filelist = []
#     for home, dirs, files in os.walk(path):
#         for filename in files:
#             Filelist.append(os.path.join(home, filename))
#     return Filelist

# class FT_LibraryRec(ctypes.Structure):
#     _fields_ = []

# class FT_FaceRec(ctypes.Structure):
#     _fields_ = [
#         ("face_flags", c_int),
#         ("style_flags", c_int),
#         ("num_glyphs", c_int),
#         ("family_name", c_char_p),
#         ("style_name", c_char_p)
#     ]

# # 加载 FreeType 库
# freetype = ctypes.cdll.LoadLibrary("libfreetype.so")

# # 定义 FreeType 函数原型
# freetype.FT_Init_FreeType.restype = c_int
# freetype.FT_Init_FreeType.argtypes = [POINTER(c_void_p)]

# freetype.FT_New_Memory_Face.restype = c_int
# freetype.FT_New_Memory_Face.argtypes = [c_void_p, c_char_p, c_size_t, c_int, POINTER(POINTER(FT_FaceRec))]

# freetype.FT_Done_Face.restype = None
# freetype.FT_Done_Face.argtypes = [POINTER(FT_FaceRec)]

# freetype.FT_Done_FreeType.restype = None
# freetype.FT_Done_FreeType.argtypes = [c_void_p]

# def get_style_flags_from_font_bytes(font_bytes):
#     # 初始化 FreeType
#     library = c_void_p()
#     if freetype.FT_Init_FreeType(ctypes.byref(library)) != 0:
#         raise Exception("Could not initialize FreeType library")

#     # 创建字节数组
#     font_size = len(font_bytes)
#     font_buffer = (c_char * font_size).from_buffer_copy(font_bytes)

#     # 从内存中创建字体面
#     face = POINTER(FT_FaceRec)()
#     if freetype.FT_New_Memory_Face(library, font_buffer, font_size, 0, ctypes.byref(face)) != 0:
#         freetype.FT_Done_FreeType(library)  # 清理库
#         raise Exception("Could not create font face from memory")

#     # 获取 style_flags
#     style_flags = face.contents.style_flags

#     # 清理
#     freetype.FT_Done_Face(face)
#     freetype.FT_Done_FreeType(library)

#     return style_flags

# # 示例用法
# if __name__ == "__main__":
#     for file in getAllFiles("/mnt/storage/Fonts/超级字体整合包 XZ"):
#         if file.endswith("ttf"):
#             print(file)
#             with open(file, "rb") as f:
#                 font_data = f.read()
#                 style_flags = get_style_flags_from_font_bytes(font_data)
#                 print(f"Style Flags: {style_flags}")


# import ctypes
# import json
# import os
# import time
# import freetype
# import freetype.raw
# from utils import  getAllFiles, getFontFileInfos
# from constants import ONLINE_FONTS_DB_PATH
# with open(ONLINE_FONTS_DB_PATH, "r", encoding="UTF-8") as f:
#     onlineMapIndex, onlineMapData = json.load(f)

# "56330MB"

# if __name__ == "__main__":
#     font_path = "/mnt/storage/Projects/fontInAss/FZLTCH.ttf"
#     start = time.perf_counter_ns()
#     for file in getAllFiles("/mnt/storage/Fonts/超级字体整合包 XZ"):
#         res = getFontFileInfos(file)
#         # print(res)
#     print(f"读取 {(time.perf_counter_ns() - start) / 1000000000:.2f}s")



import time
from py2cy.c_utils import analyseAss
from utils import  getAllFiles

for file in getAllFiles("/mnt/storage/Projects/fontInAss/test","ass"):
    print(file)
    start = time.perf_counter_ns()
    analyseAss(assBytes = open(file,'rb').read())
    print(f"耗时 {(time.perf_counter_ns() - start) / 1_000_000:.2f}ms")
    
