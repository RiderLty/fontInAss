from sys import getsizeof
import time
import asyncio
import traceback
import chardet
import uharfbuzz
from cachetools import LRUCache, TTLCache
from fontManager import fontManager
import colorAdjust
from utils import assInsertLine, bytesToStr, isSRT, bytesToHashName, srtToAss, subfonts_rename_restore
from py2cy.c_utils import uuencode
from constants import ERROR_DISPLAY_IGNORE_GLYPH, logger, ERROR_DISPLAY, PUNCTUATION_UNICODES, SUB_CACHE_SIZE, SUB_CACHE_TTL, SRT_2_ASS_FORMAT

# from analyseAss import analyseAss
from py2cy.c_utils import analyseAss


class assSubsetter:
    def __init__(self, fontManagerInstance: fontManager) -> None:
        self.fontManagerInstance = fontManagerInstance
        # self.processPool = ProcessPoolExecutor(max_workers=POOL_CPU_MAX)
        # logger.info(f"子集化进程数量：{POOL_CPU_MAX}")
        # 提交一个简单的任务来预热进程池
        # self.processPool.submit(initpass)
        self.cache = TTLCache(maxsize=SUB_CACHE_SIZE, ttl=SUB_CACHE_TTL) if SUB_CACHE_TTL > 0 else LRUCache(maxsize=SUB_CACHE_SIZE)

    # def close(self):
    # self.processPool.shutdown()

    @staticmethod
    def fontSubsetter(fontBytes, index, fontName, weight, italic, unicodeSet):
        try:
            start = time.perf_counter_ns()
            face = uharfbuzz.Face(fontBytes, index)
            inp = uharfbuzz.SubsetInput()
            inp.sets(uharfbuzz.SubsetInputSets.UNICODE).set(unicodeSet)
            assert "name" in face.table_tags, ValueError("name 表未找到")
            # utils.tag2integer("name") 计算得出 1851878757
            inp.sets(uharfbuzz.SubsetInputSets.NO_SUBSET_TABLE_TAG).set({1851878757})
            face = uharfbuzz.subset(face, inp)
            enc = uuencode(face.blob.data)
            # missGlyph = "".join([chr(x) for x in unicodeSet if (x not in face.unicodes) and (x not in PUNCTUATION_UNICODES)])
            logger.debug(f"子集化 {len(unicodeSet)} in {(time.perf_counter_ns() - start) / 1000000:.2f}ms \t[{fontName}]")
            missGlyph = "".join([chr(x) for x in unicodeSet.difference(face.unicodes) if x not in PUNCTUATION_UNICODES])
            if missGlyph == "":
                return None, f"fontname:{fontName}_{'B' if weight > 400 else ''}{'I' if italic else ''}0.ttf\n{enc}\n"
            else:
                return f"缺少字形 \t\t[{fontName}]:{missGlyph}", f"fontname:{fontName}_{'B' if weight > 400 else ''}{'I' if italic else ''}0.ttf\n{enc}\n"
        except Exception as e:
            logger.error(f"子集化出错 \t\t[{fontName}]: \n{traceback.format_exc()}")
            return str(e), ""

    async def loadSubsetEncode(self, fontName, weight, italic, unicodeSet):
        try:
            fontBytes, index = await self.fontManagerInstance.loadFont(fontName, weight, italic)
            if fontBytes is None:
                logger.error(f"字体缺失 \t\t[{fontName}]")
                return f"字体缺失 \t\t[{fontName}]", ""
        except Exception as e:
            logger.error(f"加载字体出错 \t[{fontName}]: \n{traceback.format_exc()}")
            return f"加载字体出错 \t[{fontName}]: \n{traceback.format_exc()}", ""
        return assSubsetter.fontSubsetter(fontBytes, index, fontName, weight, italic, unicodeSet)

    async def process(self, subtitleBytes, user_hsv_s,user_hsv_v):
        bytesHash = bytesToHashName(subtitleBytes + int((user_hsv_s*10 + user_hsv_v) * 100).to_bytes(4, byteorder="big", signed=True))
        # if bytesHash in self.cache:
        #     (srt, resultBytes) = self.cache[bytesHash]
        #     self.cache[bytesHash] = (srt, resultBytes)
        #     logger.info(f"字幕缓存命中 占用: {len(resultBytes) / (1024 * 1024):.2f}MB")
        #     return ("", srt, resultBytes)
        
        assText = bytesToStr(subtitleBytes)
        # assText = subfonts_rename_restore(assText)
        srt = isSRT(assText)
        if srt:
            if SRT_2_ASS_FORMAT and SRT_2_ASS_FORMAT:
                logger.info("SRT ==> ASS")
                assText = srtToAss(assText)
            else:
                logger.info("未开启SRT转ASS")
                return ("未开启SRT转ASS", True, assText.encode("UTF-8-sig"))

        if "[Fonts]\n" in assText:
            logger.error("已有内嵌字体")
            return ("已有内嵌字体", False, subtitleBytes)

        if user_hsv_s == 1 and user_hsv_v == 1:
            pass
        else:
            logger.info(f"颜色调整 饱和度x{user_hsv_s} 亮度x{user_hsv_v}")
            assText = colorAdjust.ssaProcessor(assText , user_hsv_s , user_hsv_v)

        if bytesHash in self.cache:
            embedFontsText = self.cache[bytesHash]
            totalErrors = []
            logger.info(f"字幕缓存命中 占用: {getsizeof(embedFontsText) / (1024 * 1024):.2f}MB")
        else:
            embedFontsText = "[Fonts]\n"
            start = time.perf_counter_ns()

            if "utf-8" in chardet.detect(subtitleBytes)["encoding"].lower() and not srt:
                fontCharList, subRename = analyseAss(assBytes=subtitleBytes)
            else:
                fontCharList, subRename = analyseAss(assText=assText)
            for replacedName, originName in subRename.items():
                assText = assText.replace(replacedName, originName)

            assFinish = time.perf_counter_ns()
            tasks = [self.loadSubsetEncode(fontName, weight, italic, unicodeSet) for ((fontName, weight, italic), unicodeSet) in fontCharList.items()]
            totalErrors = []
            displayErrors = []
            for task in asyncio.as_completed(tasks):
                err, result = await task
                if err:
                    totalErrors.append(err)
                    if err.startswith("缺少字形"):
                        if not ERROR_DISPLAY_IGNORE_GLYPH:
                            displayErrors.append(err)
                    else:
                        displayErrors.append(err)
                embedFontsText += result
            logger.info(f"ass分析 {(assFinish - start) / 1000000:.2f}ms")  # {len(embedFontsText) / (1024 * 1024):.2f}MB in
            logger.info(f"子集化嵌入 {(time.perf_counter_ns() - assFinish) / 1000000:.2f}ms")  # {len(embedFontsText) / (1024 * 1024):.2f}MB in
            if len(displayErrors) != 0 and ERROR_DISPLAY > 0 and ERROR_DISPLAY <= 60:
                assText = assInsertLine(assText, f"0:00:{ERROR_DISPLAY:05.2f}", r"fontinass 子集化存在错误：\N" + r"\N".join(displayErrors))
        head, tai = assText.split("[Events]")
        resultText = head + embedFontsText + "\n[Events]" + tai
        resultBytes = resultText.encode("UTF-8-sig")
        if len(totalErrors) == 0:
            self.cache[bytesHash] = embedFontsText
        else:
            logger.error("存在错误，未缓存")
            for err in totalErrors:
                logger.error(err)
        return ("\n".join(totalErrors), srt, resultBytes)
