import time
import asyncio
import traceback
import uharfbuzz
from cachetools import LRUCache, TTLCache
from fontManager import fontManager

import hdrify
from utils import bytesToStr, isSRT, tagToInteger, bytesToHashName, srtToAss
from py2cy.c_utils import uuencode
from constants import logger, SUB_CACHE_SIZE, SUB_CACHE_TTL, SRT_2_ASS_FORMAT, HDR


# from utils import analyseAss
from analyseAss import analyseAss

# from concurrent.futures import ProcessPoolExecutor

# def initpass():
#     pass


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
    def fontSubsetter(fontBytes, index, fontName, unicodeSet, submitTime):
        # logger.debug(f"{fontName} 子集化 启动时{(time.perf_counter_ns() - submitTime) / 1000000:.2f}ms")
        try:
            start = time.perf_counter_ns()
            face = uharfbuzz.Face(fontBytes, index)
            inp = uharfbuzz.SubsetInput()
            inp.sets(uharfbuzz.SubsetInputSets.UNICODE).set(unicodeSet)
            assert "name" in face.table_tags, ValueError("name 表未找到")
            inp.sets(uharfbuzz.SubsetInputSets.NO_SUBSET_TABLE_TAG).set({tagToInteger("name")})
            face = uharfbuzz.subset(face, inp)
            enc = uuencode(face.blob.data)
            del face
            logger.debug(f"子集化 {len(unicodeSet)} in {(time.perf_counter_ns() - start) / 1000000:.2f}ms \t[{fontName}]")
            return f"fontname:{fontName}_0.ttf\n{enc}\n"
        except Exception as e:
            logger.error(f"子集化出错 \t[{fontName}]: \n{traceback.format_exc()}")
            return ""

    async def loadSubsetEncode(self, fontName, weight, italic, unicodeSet):
        try:
            fontBytes, index = await self.fontManagerInstance.loadFont(fontName, weight, italic)
            if fontBytes is None:
                logger.error(f"字体缺失 \t\t[{fontName}]")
                return ""
        except Exception as e:
            logger.error(f"加载字体出错 \t[{fontName}]: \n{traceback.format_exc()}")
            return ""
        submitTime = time.perf_counter_ns()
        # result = await MAIN_LOOP.run_in_executor(self.processPool, assSubsetter.fontSubsetter, fontBytes, index, fontName, unicodeSet , submitTime)
        result = assSubsetter.fontSubsetter(fontBytes, index, fontName, unicodeSet, submitTime)
        # logger.debug(f"{fontName} 子集化 实际用时{(time.perf_counter_ns() - submitTime) / 1000000:.2f}ms")
        return result

    async def process(self, subtitleBytes, userHDR=0):
        bytesHash = bytesToHashName(subtitleBytes + userHDR.to_bytes(4, byteorder="big", signed=True))
        if bytesHash in self.cache:
            (srt, resultBytes) = self.cache[bytesHash]
            self.cache[bytesHash] = (srt, resultBytes)
            logger.info(f"字幕缓存命中 占用: {len(resultBytes) / (1024 * 1024):.2f}MB")
            return (srt, resultBytes)

        assText = bytesToStr(subtitleBytes)

        srt = isSRT(assText)
        if srt:
            if SRT_2_ASS_FORMAT and SRT_2_ASS_FORMAT:
                logger.info("SRT ==> ASS")
                assText = srtToAss(assText)
            else:
                logger.info("未开启SRT转ASS")
                return (True, assText.encode("UTF-8-sig"))

        if "[Fonts]\n" in assText:
            logger.error("已有内嵌字体")
            return (False, subtitleBytes)

        targetHDR = HDR if userHDR == 0 else userHDR
        if targetHDR != -1:
            logger.info(f"HDR适配 {targetHDR}")
            try:
                assText = hdrify.ssaProcessor(assText, targetHDR)
            except Exception as e:
                logger.error(f"HDR适配出错: \n{traceback.format_exc()}")

        head, tai = assText.split("[Events]")
        embedFontsText = "[Fonts]\n"
        start = time.perf_counter_ns()
        fontCharList = analyseAss(assText)
        assFinish = time.perf_counter_ns()
        tasks = [self.loadSubsetEncode(fontName, weight, italic, unicodeSet) for ((fontName, weight, italic), unicodeSet) in fontCharList.items()]
        error = False
        for task in asyncio.as_completed(tasks):
            result = await task
            if result == "":
                error = True
            else:
                embedFontsText += result
        logger.debug(f"ass分析 {(assFinish - start) / 1000000:.2f}ms")  # {len(embedFontsText) / (1024 * 1024):.2f}MB in
        logger.info(f"子集化嵌入 {(time.perf_counter_ns() - assFinish) / 1000000:.2f}ms")  # {len(embedFontsText) / (1024 * 1024):.2f}MB in
        resultText = head + embedFontsText + "\n[Events]" + tai
        # print(resultText)
        resultBytes = resultText.encode("UTF-8-sig")
        if not error:
            self.cache[bytesHash] = (srt, resultBytes)
        else:
            logger.error("存在错误，未缓存")
        return (srt, resultBytes)
