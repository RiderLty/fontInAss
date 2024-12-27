import time
import asyncio
import traceback
import uharfbuzz
from cachetools import LRUCache, TTLCache
from fontManager import fontManager
import hdrify
from utils import assInsertLine, bytesToStr, isSRT, bytesToHashName, srtToAss
from py2cy.c_utils import uuencode
from constants import logger, ERROR_DISPLAY, PUNCTUATION_UNICODES, SUB_CACHE_SIZE, SUB_CACHE_TTL, SRT_2_ASS_FORMAT, HDR
from analyseAss import analyseAss

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
    def fontSubsetter(fontBytes, index, fontName, unicodeSet):
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
            missGlyph = "".join(
                [chr(x) for x in unicodeSet.difference(face.unicodes)
                 if x not in PUNCTUATION_UNICODES])
            logger.debug(f"子集化 {len(unicodeSet)} in {(time.perf_counter_ns() - start) / 1000000:.2f}ms \t[{fontName}]")
            if missGlyph == "":
                return None, f"fontname:{fontName}_0.ttf\n{enc}\n"
            else:
                return f"[{fontName}] 缺少字形:{missGlyph}", f"fontname:{fontName}_0.ttf\n{enc}\n"
        except Exception as e:
            logger.error(f"子集化出错 \t[{fontName}]: \n{traceback.format_exc()}")
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
        return assSubsetter.fontSubsetter(fontBytes, index, fontName, unicodeSet)

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

        embedFontsText = "[Fonts]\n"
        start = time.perf_counter_ns()
        fontCharList = analyseAss(assText)
        assFinish = time.perf_counter_ns()
        tasks = [self.loadSubsetEncode(fontName, weight, italic, unicodeSet) for ((fontName, weight, italic), unicodeSet) in fontCharList.items()]
        errors = []
        for task in asyncio.as_completed(tasks):
            err, result = await task
            if err:
                errors.append(err)
            embedFontsText += result
        logger.debug(f"ass分析 {(assFinish - start) / 1000000:.2f}ms")  # {len(embedFontsText) / (1024 * 1024):.2f}MB in
        logger.info(f"子集化嵌入 {(time.perf_counter_ns() - assFinish) / 1000000:.2f}ms")  # {len(embedFontsText) / (1024 * 1024):.2f}MB in
        if ERROR_DISPLAY > 0 and ERROR_DISPLAY <= 60 and len(errors) != 0:
            assText = assInsertLine(
                assText, f"0:00:{ERROR_DISPLAY:05.2f}", r"{\fnArial\fs48\an7\1c&HE0E0E0&\2c&H000000&\3c&H000000&\4c&H000000&\bord5\blur7}fontinass 子集化存在错误：\N" + r"\N".join(errors)
            )
        head, tai = assText.split("[Events]")
        resultText = head + embedFontsText + "\n[Events]" + tai
        resultBytes = resultText.encode("UTF-8-sig")
        if len(errors) == 0:
            self.cache[bytesHash] = (srt, resultBytes)
        else:
            logger.error("存在错误，未缓存")
            for err in errors:
                logger.error(err)
        return (srt, resultBytes)
