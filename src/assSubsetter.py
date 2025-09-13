from sys import getsizeof
import time
import asyncio
import traceback
import chardet
import uharfbuzz
from cachetools import LRUCache, TTLCache
from fontmanager import FontManager
import colorAdjust
from utils import assInsertLine, bytes_to_str, is_srt, bytes_to_hash, srt_to_ass, remove_section
from py2cy.c_utils import uuencode
from constants import (RENAMED_FONT_RESTORE , ERROR_DISPLAY_IGNORE_GLYPH, logger, ERROR_DISPLAY,
                       PUNCTUATION_UNICODES, SUB_CACHE_SIZE, SUB_CACHE_TTL, SRT_2_ASS_FORMAT, SRT_2_ASS_STYLE,
                       MISS_LOGS, MISS_GLYPH_LOGS, miss_logs_manager, Result)

# from analyseAss import analyseAss
from py2cy.c_utils import analyseAss


class assSubsetter:
    def __init__(self, fontManagerInstance: FontManager) -> None:
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
            # utils.tag_to_integer("name") 计算得出 1851878757
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
                # 与return后的totalErrors显示重复
                # logger.error(f"字体缺失 \t\t[{fontName}]")
                return f"字体缺失 \t\t[{fontName}]", ""
        except Exception as e:
            logger.error(f"加载字体出错 \t[{fontName}]: \n{traceback.format_exc()}")
            return f"加载字体出错 \t[{fontName}]: \n{traceback.format_exc()}", ""
        return assSubsetter.fontSubsetter(fontBytes, index, fontName, weight, italic, unicodeSet)

    async def process(self, subtitleBytes, user_hsv_s,user_hsv_v):
        bytesHash = bytes_to_hash(subtitleBytes + int((user_hsv_s*10 + user_hsv_v) * 100).to_bytes(4, byteorder="big", signed=True))
        # if bytesHash in self.cache:
        #     (srt, resultBytes) = self.cache[bytesHash]
        #     self.cache[bytesHash] = (srt, resultBytes)
        #     logger.info(f"字幕缓存命中 占用: {len(resultBytes) / (1024 * 1024):.2f}MB")
        #     return ("", srt, resultBytes)

        assText = bytes_to_str(subtitleBytes)
        # assText = subfonts_rename_restore(assText)
        srt = is_srt(assText)
        if srt:
            if SRT_2_ASS_FORMAT and SRT_2_ASS_STYLE:
                logger.info("SRT ==> ASS")
                assText = srt_to_ass(assText, SRT_2_ASS_FORMAT, SRT_2_ASS_STYLE)
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

            if RENAMED_FONT_RESTORE:
                for replacedName, originName in subRename.items():
                    assText = assText.replace(replacedName, originName)

            assFinish = time.perf_counter_ns()
            tasks = [self.loadSubsetEncode(fontName, weight, italic, unicodeSet) for ((fontName, weight, italic), unicodeSet) in fontCharList.items()]
            totalErrors = []
            displayErrors = []
            errLogs = []
            for task in asyncio.as_completed(tasks):
                err, result = await task
                if err:
                    totalErrors.append(err)
                    if err.startswith("字体缺失"):
                        if MISS_LOGS:
                            errLogs.append(err)
                    if err.startswith("缺少字形"):
                        if not ERROR_DISPLAY_IGNORE_GLYPH:
                            displayErrors.append(err)
                        if MISS_GLYPH_LOGS:
                            errLogs.append(err)
                    else:
                        displayErrors.append(err)
                embedFontsText += result
            logger.info(f"ass分析 {(assFinish - start) / 1000000:.2f}ms")  # {len(embedFontsText) / (1024 * 1024):.2f}MB in
            logger.info(f"子集化嵌入 {(time.perf_counter_ns() - assFinish) / 1000000:.2f}ms")  # {len(embedFontsText) / (1024 * 1024):.2f}MB in
            if len(displayErrors) != 0 and ERROR_DISPLAY > 0 and ERROR_DISPLAY <= 60:
                assText = assInsertLine(assText, f"0:00:{ERROR_DISPLAY:05.2f}", r"fontinass 子集化存在错误：\N" + r"\N".join(displayErrors))
            if errLogs:
                asyncio.create_task(miss_logs_manager.insert(errLogs))
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

    async def process_subset(self, subtitleBytes, fonts_check=True,
                             srt_format=None, srt_style=None, renamed_restore=False, clear_fonts=False):
        # 如果renamed_restore在程序运行中会发生变化，需要生成与renamed_restore关联的bytes_hash，否则会导致结果与缓存不一致
        bytes_hash = bytes_to_hash(subtitleBytes + int(renamed_restore).to_bytes(4, byteorder="big", signed=True))
        ass_text = bytes_to_str(subtitleBytes)
        srt = is_srt(ass_text)
        if srt:
            if srt_format and srt_style:
                logger.info("SRT ==> ASS")
                ass_text = srt_to_ass(ass_text, srt_format, srt_style)
            else:
                # 缺失错误
                return Result(400, "未开启SRT转ASS", None)

        if "[Fonts]\n" in ass_text:
            if clear_fonts:
                ass_text = remove_section(ass_text, "Fonts")
            else:
                return Result(401, "已有内嵌字体", None)

        total_errors = []
        if bytes_hash in self.cache:
            embed_fonts_text = self.cache[bytes_hash]
            logger.info(f"字幕缓存命中 占用: {getsizeof(embed_fonts_text) / (1024 * 1024):.2f}MB")
        else:
            if "utf-8" in chardet.detect(subtitleBytes)["encoding"].lower() and not srt:
                font_char_list, sub_rename = analyseAss(assBytes=subtitleBytes)
            else:
                font_char_list, sub_rename = analyseAss(assText=ass_text)

            if not font_char_list:
                # 缺失错误
                return Result(400, "analyseAss无法解析字幕所需字体", None)

            # 严格模式 缺一不可
            if fonts_check:
                tasks = [self.fontManagerInstance.select_font(fontName, weight, italic) for
                         ((fontName, weight, italic), _) in font_char_list.items()]
                for task in asyncio.as_completed(tasks):
                    result, message = await task
                    if not result:
                        total_errors.append(message)
                if total_errors:
                    return Result(300, total_errors, None)

            embed_fonts_text = "[Fonts]\n"

            if renamed_restore:
                for replacedName, originName in sub_rename.items():
                    ass_text = ass_text.replace(replacedName, originName)

            tasks = [self.loadSubsetEncode(fontName, weight, italic, unicodeSet) for
                     ((fontName, weight, italic), unicodeSet) in font_char_list.items()]
            for task in asyncio.as_completed(tasks):
                err, result = await task
                if err:
                    total_errors.append(err)
                embed_fonts_text += result

        # 经常报错点，理应先检查ass_text
        head, sep, tai = ass_text.partition("[Events]")
        if sep:
            result_text = head + embed_fonts_text + "\n" + sep + tai
        else:
            # 缺失错误
            return Result(400, "没有找到[Events]标签，请检查字幕文件内容", None)
        result_bytes = result_text.encode("UTF-8-sig")
        if len(total_errors) == 0:
            self.cache[bytes_hash] = embed_fonts_text
            # 成功
            return Result(200, None, result_bytes)
        else:
            # 部分错误
            return Result(201, total_errors, result_bytes)
