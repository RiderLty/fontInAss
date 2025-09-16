import hashlib
from sys import getsizeof
import time
import asyncio
import uharfbuzz
from cachetools import LRUCache, TTLCache
from fontmanager import FontManager
import colorAdjust
from utils import ass_insert_line, bytes_to_str, is_srt, bytes_to_hash, srt_to_ass, remove_section, check_section
from py2cy.c_utils import uuencode
from constants import (RENAMED_FONT_RESTORE , ERROR_DISPLAY_IGNORE_GLYPH, logger, ERROR_DISPLAY,
                       PUNCTUATION_UNICODES, SUB_CACHE_SIZE, SUB_CACHE_TTL, SRT_2_ASS_FORMAT, SRT_2_ASS_STYLE,
                       MISS_LOGS, MISS_GLYPH_LOGS, miss_logs_manager, Result)

# from analyseAss import analyseAss
from py2cy.c_utils import analyseAss

class SubSetter:
    def __init__(self, font_manager_instance: FontManager) -> None:
        self.font_manager_instance = font_manager_instance
        # self.processPool = ProcessPoolExecutor(max_workers=POOL_CPU_MAX)
        # logger.info(f"子集化进程数量：{POOL_CPU_MAX}")
        # 提交一个简单的任务来预热进程池
        # self.processPool.submit(initpass)
        self.cache = TTLCache(maxsize=SUB_CACHE_SIZE, ttl=SUB_CACHE_TTL) if SUB_CACHE_TTL > 0 else LRUCache(maxsize=SUB_CACHE_SIZE)

    # def close(self):
    # self.processPool.shutdown()

    @staticmethod
    def font_subsetter(font_bytes, index, font_name, weight, italic, unicode_set) -> tuple[str | None, str]:
        try:
            start = time.perf_counter_ns()
            face = uharfbuzz.Face(font_bytes, index)
            inp = uharfbuzz.SubsetInput()
            inp.sets(uharfbuzz.SubsetInputSets.UNICODE).set(unicode_set)
            assert "name" in face.table_tags, ValueError("name 表未找到")
            # utils.tag_to_integer("name") 计算得出 1851878757
            inp.sets(uharfbuzz.SubsetInputSets.NO_SUBSET_TABLE_TAG).set({1851878757})
            face = uharfbuzz.subset(face, inp)
            enc = uuencode(face.blob.data)
            # miss_glyph = "".join([chr(x) for x in unicode_set if (x not in face.unicodes) and (x not in PUNCTUATION_UNICODES)])
            logger.debug(f"子集化 {len(unicode_set)} in {(time.perf_counter_ns() - start) / 1000000:.2f}ms \t[{font_name}]")
            miss_glyph = "".join([chr(x) for x in unicode_set.difference(face.unicodes) if x not in PUNCTUATION_UNICODES])
            result = f"fontname:{font_name}_{'B' if weight > 400 else ''}{'I' if italic else ''}0.ttf\n{enc}\n"
            if miss_glyph == "":
                return None, result
            else:
                return f"缺少字形 \t\t[{font_name}]{miss_glyph}", result
        except Exception as e:
            logger.exception(f"子集化出错 \t\t[{font_name}]")
            # logger.error(f"子集化出错 \t\t[{font_name}]: \n{traceback.format_exc()}")
            return f"子集化出错 \t\t[{font_name}]: \n{str(e)}", ""

    async def load_subset_encode(self, font_name, weight, italic, unicode_set) -> tuple[str | None, str]:
        try:
            font_bytes, index = await self.font_manager_instance.load_font(font_name, weight, italic)
            if font_bytes is None:
                # 与return后的totalErrors显示重复
                # logger.error(f"字体缺失 \t\t[{font_name}]")
                return f"字体缺失 \t\t[{font_name}]", ""
        except Exception as e:
            logger.exception(f"加载字体出错 \t\t[{font_name}]")
            # logger.error(f"加载字体出错 \t\t[{font_name}]: \n{traceback.format_exc()}")
            return f"加载字体出错 \t\t[{font_name}]: \n{str(e)}", ""
        return SubSetter.font_subsetter(font_bytes, index, font_name, weight, italic, unicode_set)

    async def process(self, raw_bytes, user_hsv_s, user_hsv_v):
        bytes_hash = bytes_to_hash(raw_bytes + int((user_hsv_s*10 + user_hsv_v) * 100).to_bytes(4, byteorder="big", signed=True))

        ass_encode, ass_text = bytes_to_str(raw_bytes)
        if not ass_encode:
            # 让上层抛出异常并且返回原始内容
            return "无法解析文件编码", False, None

        # ass_text = restore_subset_fonts(ass_text)
        srt = is_srt(ass_text)
        if srt:
            if SRT_2_ASS_FORMAT and SRT_2_ASS_STYLE:
                logger.info("SRT ==> ASS")
                ass_text = srt_to_ass(ass_text, SRT_2_ASS_FORMAT, SRT_2_ASS_STYLE)
            else:
                logger.warning("未开启SRT转ASS")
                return "未开启SRT转ASS", True, raw_bytes.encode("UTF-8-sig")

        status = check_section(ass_text, "Fonts")
        if status == 1:  # 有 Fonts 且有内容
            logger.warning("已有内嵌字体")
            return "已有内嵌字体", False, raw_bytes
        elif status == 2:  # 有 Fonts 但是没内容
            ass_text = remove_section(ass_text, "Fonts")

        if user_hsv_s == 1 and user_hsv_v == 1:
            pass
        else:
            logger.info(f"颜色调整 饱和度x{user_hsv_s} 亮度x{user_hsv_v}")
            ass_text = colorAdjust.ssaProcessor(ass_text , user_hsv_s , user_hsv_v)

        if bytes_hash in self.cache:
            embed_fonts_text = self.cache[bytes_hash]
            total_errors = []
            logger.info(f"字幕缓存命中 占用: {getsizeof(embed_fonts_text) / (1024 * 1024):.2f}MB")
        else:
            analyse_start_time = time.perf_counter_ns()
            if "utf_8" == ass_encode and not srt:
                font_char_list, sub_rename = analyseAss(assBytes=raw_bytes)
            else:
                font_char_list, sub_rename = analyseAss(assText=ass_text)
            analyse_end_time = time.perf_counter_ns()

            if not font_char_list:
                return "analyseAss无法解析字幕所需字体", srt, None

            embed_fonts_text = "[Fonts]\n"

            if RENAMED_FONT_RESTORE:
                for replacedName, originName in sub_rename.items():
                    ass_text = ass_text.replace(replacedName, originName)

            subset_start_time = time.perf_counter_ns()
            tasks = [self.load_subset_encode(font_name, weight, italic, unicode_set) for ((font_name, weight, italic), unicode_set) in font_char_list.items()]
            total_errors = []
            display_errors = []
            logs_errors = []

            for task in asyncio.as_completed(tasks):
                err, result = await task
                if err:
                    total_errors.append(err)
                    if err.startswith("字体缺失"):
                        display_errors.append(err)
                        if MISS_LOGS:
                            logs_errors.append(err)
                    if err.startswith("缺少字形"):
                        # 忽略缺失字形显示意思，默认值为False，意思就是默认不忽略
                        if not ERROR_DISPLAY_IGNORE_GLYPH:
                            display_errors.append(err)
                        if MISS_GLYPH_LOGS:
                            logs_errors.append(err)
                embed_fonts_text += result

            logger.info(f"ass分析 {(analyse_end_time - analyse_start_time) / 1000000:.2f}ms")  # {len(embed_fonts_text) / (1024 * 1024):.2f}MB in
            logger.info(f"子集化嵌入 {(time.perf_counter_ns() - subset_start_time) / 1000000:.2f}ms")  # {len(embed_fonts_text) / (1024 * 1024):.2f}MB in
            if len(display_errors) != 0 and 0 < ERROR_DISPLAY <= 60:
                ass_text = ass_insert_line(ass_text, f"0:00:{ERROR_DISPLAY:05.2f}", r"fontinass 子集化存在错误：\N" + r"\N".join(display_errors))
            if logs_errors:
                asyncio.create_task(miss_logs_manager.insert(logs_errors))
        # head, tai = ass_text.split("[Events]")
        # result_text = head + embed_fonts_text + "\n[Events]" + tai
        head, sep, tai = ass_text.partition("[Events]")
        if sep:
            result_text = head + embed_fonts_text + "\n" + sep + tai
        else:
            return "没有找到[Events]标签，请检查字幕文件内容", srt, None
        result_bytes = result_text.encode("UTF-8-sig")
        if len(total_errors) == 0:
            self.cache[bytes_hash] = embed_fonts_text
        else:
            logger.error("存在错误，未缓存")
            for err in total_errors:
                logger.error(err)
        return "\n".join(total_errors), srt, result_bytes

    async def process_subset(self, raw_bytes, fonts_check=True,
                             srt_format=None, srt_style=None, renamed_restore=False, clear_fonts=False):
        # 如果renamed_restore在程序运行中会发生变化，需要生成与renamed_restore关联的bytes_hash，否则会导致结果与缓存不一致
        bytes_hash = bytes_to_hash(raw_bytes + int(renamed_restore).to_bytes(4, byteorder="big", signed=True))
        ass_encode, ass_text = bytes_to_str(raw_bytes)
        if not ass_encode:
            return Result(400, "无法解析字幕文件编码", None)

        srt = is_srt(ass_text)
        if srt:
            if srt_format and srt_style:
                logger.info("SRT ==> ASS")
                ass_text = srt_to_ass(ass_text, srt_format, srt_style)
            else:
                # 缺失错误
                return Result(400, "未开启SRT转ASS", None)

        status = check_section(ass_text, "Fonts")
        if status == 1:  # 有 Fonts 且有内容
            if clear_fonts:
                ass_text = remove_section(ass_text, "Fonts")
            else:
                return Result(400, "已有内嵌字体", None)
        elif status == 2:  # 有 Fonts 但是没内容
            ass_text = remove_section(ass_text, "Fonts")

        total_errors = []
        if bytes_hash in self.cache:
            embed_fonts_text = self.cache[bytes_hash]
            logger.info(f"字幕缓存命中 占用: {getsizeof(embed_fonts_text) / (1024 * 1024):.2f}MB")
        else:
            # print(ass_encode)
            if "utf_8" == ass_encode and not srt:
                font_char_list, sub_rename = analyseAss(assBytes=raw_bytes)
            else:
                font_char_list, sub_rename = analyseAss(assText=ass_text)

            if not font_char_list:
                # 缺失错误
                return Result(400, "analyseAss无法解析字幕所需字体", None)

            # 严格模式 缺一不可
            if fonts_check:
                tasks = [self.font_manager_instance.select_font(font_name, weight, italic) for
                         ((font_name, weight, italic), _) in font_char_list.items()]
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

            tasks = [self.load_subset_encode(font_name, weight, italic, unicode_set) for
                     ((font_name, weight, italic), unicode_set) in font_char_list.items()]
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
        result_bytes = result_text.encode("UTF-8")
        if len(total_errors) == 0:
            self.cache[bytes_hash] = embed_fonts_text
            # 成功
            return Result(200, None, result_bytes)
        else:
            # 警告 部分错误
            return Result(201, total_errors, result_bytes)
