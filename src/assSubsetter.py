import os
import logging
import re
import threading
import uharfbuzz
import traceback
import ass as ssa
import fontLoader
import utils
from concurrent.futures import as_completed

logger = logging.getLogger(f'{"main"}:{"loger"}')


def analyseAss(ass_str):
    """分析ass文件 返回 字体：{unicodes}"""
    sub = ssa.parse_string(ass_str)
    style_fontName = {}  # 样式 => 字体
    font_charList = {}  # 字体 => unicode list
    for style in sub.styles:
        styleName = style.name.strip()
        fontName = style.fontname.strip().replace("@", "")
        style_fontName[styleName] = fontName
        font_charList[fontName] = set()
    for event in sub.events:
        os.getenv("DEV") == "true" and logger.debug("")
        os.getenv("DEV") == "true" and logger.debug("原始Event文本 : " + event.text)
        eventStyle = event.style.replace("*", "")
        if eventStyle not in style_fontName:
            logger.error(f"event[{eventStyle}]使用了未知样式")
            continue
        fontLine = r"{\fn" + style_fontName[eventStyle] + "}" + event.text
        # 在首部加上对应的style的字体
        for inlineStyle in re.findall(r"({[^\\]*\\r[^}|\\]+[\\|}])", event.text):  # 用于匹配 {\rXXX} 其中xxx为style名称
            # {\r} 会有这种 空的
            styleName = re.findall(r"{[^\\]*\\r([^}|\\]+)[\\|}]", inlineStyle)[0]
            if styleName in style_fontName:
                fontLine = fontLine.replace(inlineStyle, r"{\fn" + style_fontName[styleName] + "}")  # 将内联style，改为指定字体名称的形式
            else:
                logger.error(f"event内联[{styleName}]使用了未知样式")
        res = [(fn.groups()[0], fn.start(), fn.end()) for fn in re.finditer(r"{[^\\]*\\fn([^}|\\]*)[\\|}]", fontLine)]
        # 获取所有的内联字体位置名称信息
        for i in range(len(res)):
            fontName = res[i][0].replace("@", "")
            textStart = res[i][2]
            textEnd = None if i == len(res) - 1 else res[i + 1][1]
            text = re.sub(r"(?<!{)\{\\([^{}]*)\}(?!})", "", fontLine[textStart:textEnd])
            os.getenv("DEV") == "true" and logger.debug(f"{fontName} :  {fontLine[textStart:textEnd]}  ===> {text}")
            for ch in text:
                if fontName not in font_charList:
                    font_charList[fontName] = set()
                font_charList[fontName].add(ord(ch))
        # print("")
        # 最终获取 字体 : 文本code
    # print(font_charList)
    return font_charList


def uuencode(binaryData):
    """编码工具"""
    OFFSET = 33
    encoded = []
    for i in range(0, (len(binaryData) // 3) * 3, 3):
        bytes_chunk = binaryData[i : i + 3]
        if len(bytes_chunk) < 3:
            bytes_chunk += b"\x00" * (3 - len(bytes_chunk))
        packed = int.from_bytes(bytes_chunk, "big")
        # packed = (packed & 0xFFFFFF)  # 确保只有24位
        six_bits = [((packed >> (18 - i * 6)) & 0x3F) for i in range(4)]
        encoded_group = "".join(chr(OFFSET + num) for num in six_bits)
        encoded.append(encoded_group)
    # print(f"输入({len(data)}){data} => {data[:(len(data) // 3) * 3]}|{data[(len(data) // 3) * 3:]}")
    last = None
    if len(binaryData) % 3 == 0:
        pass
    elif len(binaryData) % 3 == 1:
        last = binaryData[(len(binaryData) // 3) * 3 :] + b"\x00\x00"
        packed = int.from_bytes(last, "big")
        six_bits = [((packed >> (18 - i * 6)) & 0x3F) for i in range(4)]
        encoded_group = "".join(chr(OFFSET + num) for num in six_bits)[:2]
        encoded.append(encoded_group)
    elif len(binaryData) % 3 == 2:
        last = binaryData[(len(binaryData) // 3) * 3 :] + b"\x00"
        packed = int.from_bytes(last, "big")
        six_bits = [((packed >> (18 - i * 6)) & 0x3F) for i in range(4)]
        encoded_group = "".join(chr(OFFSET + num) for num in six_bits)[:3]
        encoded.append(encoded_group)
    encoded_lines = []
    for i in range(0, (len(encoded) // 20) * 20, 20):
        encoded_lines.append("".join(encoded[i : i + 20]))
    encoded_lines.append("".join(encoded[(len(encoded) // 20) * 20 :]))
    return "\n".join(encoded_lines)

def makeOneEmbedFontsText(args):
    # 在每个子进程中设置日志
    logging.basicConfig(level=logging.ERROR, format="%(asctime)s - %(levelname)s - %(message)s")
    fontBytes, fontName, unicodeSet,= args
    if fontBytes is None:
        return f"缺少字体 {fontName}", None
    else:
        try:
            # logger.error(f"当前字体[{fontName}]处于ttc的index : {fontBytes[1]}")
            # 转harfbuzz.Face对象 指定blob的faces_index
            face = uharfbuzz.Face(fontBytes[0], fontBytes[1])# 初始化子集化UNICODE
            inp = uharfbuzz.SubsetInput()
            inp.sets(uharfbuzz.SubsetInputSets.UNICODE).set(unicodeSet)
            assert "name" in face.table_tags , ValueError("name table not found")
            inp.sets(uharfbuzz.SubsetInputSets.NO_SUBSET_TABLE_TAG).set({utils.tag_to_integer("name") })
            face = uharfbuzz.subset(face, inp)
            enc = uuencode(face.blob.data)
            del face
            return None, f"fontname:{fontName}_0.ttf\n{enc}\n"
        except Exception as e:
            logger.error(f"子集化{fontName}出错 : \n{traceback.format_exc()}")
            return f" {fontName} : {str(e)}", None


def taskMaker(lock, tasks, fontName, unicodeSet, externalFonts, fontPathMap, fontCache):
    # with sem:
    # 分离逻辑处理，尽量只保留I/O操作，释放GIL锁，较大的/较长时间下载的字体所耗时间可以留给其他load-ready的字体进行逻辑处理
    fontBytes = fontLoader.loadFont(fontName, externalFonts, fontPathMap)
    # 获取ttc的index
    fontBytes = utils.get_ttc_index(fontBytes, fontName)
    # 读取到的字体bytes存入内存缓存
    fontCache[fontName] = fontBytes
    # 提前创建任务列表，减少 lock 占用时间
    task = (fontBytes, fontName, unicodeSet)
    with lock:
        tasks.append(task)

def makeEmbedFonts(pool, thread_pool, font_charList, externalFonts, fontPathMap, fontCache):
    """对于给定的 字体:使用到的编码列表 返回编码后的，可嵌入ASS的文本"""
    embedFontsText = "[Fonts]\n"
    errors = []
    # 准备子集化任务参数
    tasks = []
    # sem = threading.Semaphore(8)
    lock = threading.Lock()
    threads = []
    # 使用线程池
    futures = []
    for fontName, unicodeSet in font_charList.items():
        if fontName in fontCache:
            fontBytes = fontCache[fontName]
            # 刷新字体缓存过期时间
            fontCache[fontName] = fontBytes
            tasks.append((fontBytes, fontName, unicodeSet))
            logger.info(f"{fontName} 字体缓存命中 - 占用: {len(fontBytes[0]) / (1024 * 1024):.2f}MB")
        else:
            threads.append(thread_pool.submit(taskMaker, lock, tasks, fontName, unicodeSet, externalFonts, fontPathMap,fontCache))

    # print("哼想逃")
    # 使用 as_completed 遍历已完成的任务
    for future in as_completed(threads):
        future.result()  # 阻塞直到该任务完成
        # print("我滴任务完成辣")

    results = pool.map(makeOneEmbedFontsText, tasks)
    # 处理结果
    for err, result in results:
        if err:
            errors.append(err)
        else:
            embedFontsText += result

    return errors, embedFontsText