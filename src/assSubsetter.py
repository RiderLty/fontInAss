import asyncio
from concurrent.futures import ProcessPoolExecutor
import time
import traceback
from cachetools import LRUCache, TTLCache
import uharfbuzz
from fontManager import fontManager
import hdrify
from utils import analyseAss, bytesToStr, isSRT, tagToInteger, bytesToHashName , srtToAss
from py2cy.c_utils import uuencode
from constants import *


class assSubsetter:
    def __init__(self, fontManagerInstance: fontManager) -> None:
        self.fontManagerInstance = fontManagerInstance
        self.processPool = ProcessPoolExecutor(max_workers=POOL_CPU_MAX)
        self.cache = TTLCache(maxsize=SUB_CACHE_SIZE, ttl=SUB_CACHE_TTL) if SUB_CACHE_TTL > 0 else LRUCache(maxsize=SUB_CACHE_SIZE)

    def close(self):
        self.processPool.shutdown()

    @staticmethod
    def fontSubsetter(fontBytes, index, fontName, unicodeSet):
        if fontBytes is None:
            logger.error(f"{fontName} 字体缺失")
            return ""
        try:
            face = uharfbuzz.Face(fontBytes, index)
            inp = uharfbuzz.SubsetInput()
            inp.sets(uharfbuzz.SubsetInputSets.UNICODE).set(unicodeSet)
            assert "name" in face.table_tags, ValueError("name 表未找到")
            inp.sets(uharfbuzz.SubsetInputSets.NO_SUBSET_TABLE_TAG).set({tagToInteger("name")})
            face = uharfbuzz.subset(face, inp)
            enc = uuencode(face.blob.data)
            del face
            return f"fontname:{fontName}_0.ttf\n{enc}\n"
        except Exception as e:
            logger.error(f"子集化{fontName}出错 : \n{traceback.format_exc()}")
            return ""

    async def loadSubsetEncode(self, fontName, unicodeSet):
        try:
            fontBytes, index = await self.fontManagerInstance.loadFont(fontName)
        except Exception as e:
            logger.error(f"{fontName} 加载字体出错 : \n{traceback.format_exc()}")
            return ""
        return await MAIN_LOOP.run_in_executor(self.processPool, assSubsetter.fontSubsetter, fontBytes, index, fontName, unicodeSet)

    async def process(self, subtitleBytes):
        bytesHash = bytesToHashName(subtitleBytes)
        if bytesHash in self.cache:
            (srt, resultBytes) = self.cache[bytesHash]
            self.cache[bytesHash] = (srt, resultBytes)
            return (srt, resultBytes)

        assText = bytesToStr(subtitleBytes)

        srt = isSRT(assText)
        if srt:
            if os.environ.get("SRT_2_ASS_FORMAT") and os.environ.get("SRT_2_ASS_STYLE"):
                logger.info("SRT ===> ASS")
                assText = srtToAss(assText)
            else:
                logger.info("未开启SRT转ASS")
                return (True, assText.encode("UTF-8-sig"))
        
        if "[Fonts]\n" in assText:
            logger.error("已有内嵌字体")
            return (False, subtitleBytes)
        
        if HDR != -1:
            logger.info(f"HDR适配")
            try:
                assText = hdrify.ssaProcessor(assText, HDR)
            except Exception as e:
                logger.error(f"HDR适配出错: \n{traceback.format_exc()}")

        head, tai = assText.split("[Events]")
        embedFontsText = "[Fonts]\n"
        fontCharList = analyseAss(assText)
        start = time.perf_counter_ns()
        tasks = [self.loadSubsetEncode(fontName, unicodeSet) for (fontName, unicodeSet) in fontCharList.items()]
        for task in asyncio.as_completed(tasks):
            embedFontsText += await task
        head, tai = assText.split("[Events]")
        logger.info(f"嵌入完成 用时 {(time.perf_counter_ns() - start) / 1000000:.2f} ms - 生成Fonts部分大小: {len(embedFontsText) / (1024 * 1024):.2f}MB")
        resultText = head + embedFontsText + "\n[Events]" + tai
        # print(resultText)
        resultBytes = resultText.encode("UTF-8-sig")
        self.cache[bytesHash] = (srt, resultBytes)
        return (srt, resultBytes)
