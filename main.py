
from io import BytesIO
import threading
from easyass import *
from fastapi.responses import JSONResponse
from fontTools.ttLib import TTFont, TTCollection
from fontTools.subset import Subsetter
# from bottle import run, get, post, request, response
import os
import time
import json
import requests
import queue

import re
import uvicorn
from fastapi import FastAPI, Query, Request, Response
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


def getAllFiles(path):
    Filelist = []
    for home, dirs, files in os.walk(path):
        for filename in files:
            Filelist.append(os.path.join(home, filename))
    return Filelist


def pathReplacer(path):
    # return path.replace("E:\\", "/").replace("\\", "/")
    return path


def updateFontMap(dirPathList, old={}):
    fontMap = {}
    for dirPath in dirPathList:
        for file in getAllFiles(dirPath):
            if pathReplacer(file) in old:
                fontMap[pathReplacer(file)] = old[pathReplacer(file)]
            else:
                try:
                    fonts = None
                    if file.lower().endswith("ttc") or file.lower().endswith("ttf") or file.lower().endswith("otf"):
                        print(file)
                        with open(file, 'rb') as f:
                            f.seek(0)
                            sfntVersion = f.read(4)
                            if sfntVersion == b"ttcf":
                                fonts = TTCollection(file).fonts
                            else:
                                fonts = [TTFont(file)]
                    if fonts:
                        names = set()
                        for font in fonts:
                            for record in font['name'].names:
                                if record.nameID == 1:  # Font Family name
                                    names.add(
                                        str(record).strip())
                        fontMap[pathReplacer(file)] = {
                            "size": os.path.getsize(file),
                            "fonts": list(names)
                        }

                except Exception as e:
                    print(file, e)
    return fontMap


def makeFontMap(data):
    '''
    {
        /path/to/ttf/or/otf : {
            size: 62561,
            fonts:[
                YAHEI,
                FANGSONG, 
                ...
            ]
        }
    }
    '''
    font_file_map = {}
    font_miniSize = {}
    for path, info in data.items():
        for font_name in info["fonts"]:
            if font_name in font_file_map and font_miniSize[font_name] <= info["size"]:
                continue
            font_file_map[font_name] = path
            font_miniSize[font_name] = info["size"]
            # print(font_name , info["size"])
    return font_file_map


def printPerformance(func: callable) -> callable:
    def wrapper(*args, **kwargs):
        start = time.perf_counter_ns()
        result = func(*args, **kwargs)
        print(
            f"{func.__name__}{args[1:]}{kwargs} 耗时 {(time.perf_counter_ns() - start) / 1000000} ms")
        return result
    return wrapper


class fontLoader():
    def __init__(self, externalFonts={}) -> None:
        '''除了使用脚本附带的的字体外，可载入额外的字体，格式为 { 字体名称：路径 | http url }'''
        self.externalFonts = makeFontMap(externalFonts)
        self.fontPathMap = makeFontMap(json.load(
            open("fontMap.json", 'r', encoding="UTF-8")))

    @printPerformance
    def loadFont(self, fontName):
        try:
            if fontName in self.externalFonts:
                path = self.externalFonts[fontName]
                print(f"load {path} from external fonts")
                if path.lower().startswith("http"):
                    fontBytes = requests.get(path).content
                else:
                    fontBytes = open(path, 'rb').read()
            elif fontName in self.fontPathMap:
                path = self.fontPathMap[fontName]
                start = time.time()
                fontBytes = requests.get(
                    "https://fonts.storage.rd5isto.org" + path).content
                # print( f"load {path} {len(fontBytes) // 1048576:.2f}MB in {(time.time() - start):.2f}s")
            else:
                return None
            bio = BytesIO()
            bio.write(fontBytes)
            bio.seek(0)
            if fontBytes[:4] == b"ttcf":
                ttc = TTCollection(bio)
                for font in ttc.fonts:
                    for record in font['name'].names:
                        if record.nameID == 1 and str(record).strip() == fontName:
                            return font
            else:
                return TTFont(bio)
        except Exception as e:
            print(f"ERROR loading {fontName} : {str(e)}")
            return None


class assSubsetter():
    def __init__(self, fontLoader) -> None:
        self.fontLoader = fontLoader

    def analyseAss(self, ass_str):
        '''分析ass文件 返回 字体：{unicodes}'''
        ass_obj = Ass()
        ass_obj.parse(ass_str)
        style_fontName = {}  # 样式 => 字体
        font_charList = {}  # 字体 => unicode list
        for style in ass_obj.styles:
            styleName = style.Name.strip()
            fontName = style.Fontname.strip().replace("@", "")
            style_fontName[styleName] = fontName
            font_charList[fontName] = set()
        for event in ass_obj.events:
            fontName = style_fontName[event.Style.replace("*", "")]
            for ch in event.Text.dump():
                font_charList[fontName].add(ord(ch))
        for line in ass_str.splitlines():
            # 比较坑爹这里
            for match in re.findall(r'{[^\\]*\\fn([^}|\\]*)[\\|}]', line):
                fontName = match.replace("@", "")
                for ch in line:
                    if fontName not in font_charList:
                        font_charList[fontName] = set()
                    font_charList[fontName].add(ord(ch))
        return font_charList

    def uuencode(self, binaryData):
        '''编码工具'''
        OFFSET = 33
        encoded = []
        for i in range(0, (len(binaryData) // 3) * 3, 3):
            bytes_chunk = binaryData[i:i+3]
            if len(bytes_chunk) < 3:
                bytes_chunk += b'\x00' * (3 - len(bytes_chunk))
                print(bytes_chunk)
            packed = int.from_bytes(bytes_chunk, 'big')
            # packed = (packed & 0xFFFFFF)  # 确保只有24位
            six_bits = [((packed >> (18 - i * 6)) & 0x3F) for i in range(4)]
            encoded_group = ''.join(chr(OFFSET + num) for num in six_bits)
            encoded.append(encoded_group)
        # print(f"输入({len(data)}){data} => {data[:(len(data) // 3) * 3]}|{data[(len(data) // 3) * 3:]}")
        last = None
        if len(binaryData) % 3 == 0:
            pass
        elif len(binaryData) % 3 == 1:
            last = binaryData[(len(binaryData) // 3) * 3:] + b"\x00\x00"
            packed = int.from_bytes(last, 'big')
            six_bits = [((packed >> (18 - i * 6)) & 0x3F) for i in range(4)]
            encoded_group = ''.join(chr(OFFSET + num) for num in six_bits)[:2]
            encoded.append(encoded_group)
        elif len(binaryData) % 3 == 2:
            last = binaryData[(len(binaryData) // 3) * 3:] + b"\x00"
            packed = int.from_bytes(last, 'big')
            six_bits = [((packed >> (18 - i * 6)) & 0x3F) for i in range(4)]
            encoded_group = ''.join(chr(OFFSET + num) for num in six_bits)[:3]
            encoded.append(encoded_group)
        encoded_lines = []
        for i in range(0, (len(encoded) // 20) * 20, 20):
            encoded_lines.append("".join(encoded[i:i+20]))
        encoded_lines.append("".join(encoded[(len(encoded) // 20) * 20:]))
        return "\n".join(encoded_lines)

    def makeOneEmbedFontsText(self, fontName, unicodeSet, resultQueue, sem):
        with sem:
            font = self.fontLoader.loadFont(fontName)
            if font == None:
                resultQueue.put((f"{fontName} miss", None))
            else:
                try:
                    originNames = font['name'].names
                    subsetter = Subsetter()
                    subsetter.populate(unicodes=unicodeSet)
                    subsetter.subset(font)
                    font["name"].names = originNames
                    fontOutIO = BytesIO()
                    font.save(fontOutIO)
                    enc = self.uuencode(fontOutIO.getvalue())
                    resultQueue.put(
                        (None, f"fontname:{fontName}_0.ttf\n{enc}\n"))
                except Exception as e:
                    resultQueue.put((f"{fontName} : {str(e)}", None))

    def makeEmbedFonts(self, font_charList):
        '''对于给定的 字体:使用到的编码列表 返回编码后的，可嵌入ASS的文本 '''
        embedFontsText = "[Fonts]\n"
        errors = []
        resultQueue = queue.Queue()
        sem = threading.Semaphore(8)
        for fontName, unicodeSet in font_charList.items():
            if len(unicodeSet) != 0:
                threading.Thread(target=self.makeOneEmbedFontsText, args=(
                    fontName, unicodeSet, resultQueue, sem)).start()
        for fontName, unicodeSet in font_charList.items():
            if len(unicodeSet) != 0:
                (err, result) = resultQueue.get()
                if err:
                    errors.append(err)
                else:
                    embedFontsText += result
        return errors, embedFontsText


def isSRT(text):
    srt_pattern = r'@\d+@\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}@'
    matches = re.findall(srt_pattern, "@".join(text.splitlines()))
    return len(matches) > 0


def srt2ass(srtText):
    src = ''
    utf8bom = ''

    if u'\ufeff' in srtText:
        srtText = srtText.replace(u'\ufeff', '')
        utf8bom = u'\ufeff'

    srtText = srtText.replace("\r", "")
    lines = [x.strip() for x in srtText.split("\n") if x.strip()]
    subLines = ''
    tmpLines = ''
    lineCount = 0

    for ln in range(len(lines)):
        line = lines[ln]
        if line.isdigit() and re.match('-?\d\d:\d\d:\d\d', lines[(ln+1)]):
            if tmpLines:
                subLines += tmpLines.replace("\n", "\\n") + "\n"
            tmpLines = ''
            lineCount = 0
            continue
        else:
            if re.match('-?\d\d:\d\d:\d\d', line):
                line = line.replace('-0', '0')
                tmpLines += 'Dialogue: 0,' + line + ',Default,,0,0,0,,'
            else:
                if lineCount < 2:
                    tmpLines += line
                else:
                    tmpLines += "\n" + line
            lineCount += 1
        ln += 1

    subLines += tmpLines + "\n"

    subLines = re.sub(r'\d(\d:\d{2}:\d{2}),(\d{2})\d', '\\1.\\2', subLines)
    subLines = re.sub(r'\s+-->\s+', ',', subLines)
    # replace style
    subLines = re.sub(r'<([ubi])>', "{\\\\\g<1>1}", subLines)
    subLines = re.sub(r'</([ubi])>', "{\\\\\g<1>0}", subLines)
    subLines = re.sub(
        r'<font\s+color="?#(\w{2})(\w{2})(\w{2})"?>', "{\\\\c&H\\3\\2\\1&}", subLines)
    subLines = re.sub(r'</font>', "", subLines)

    head_str = '''[Script Info]
; This is an Advanced Sub Station Alpha v4+ script.
Title:
ScriptType: v4.00+
Collisions: Normal
PlayDepth: 0


[V4+ Styles]
''' + os.environ.get("SRT_2_ASS_FORMAT") +"\n"+ os.environ.get("SRT_2_ASS_STYLE") + '''
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text'''

# Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
# Style: Default,楷体,20,&H03FFFFFF,&H00FFFFFF,&H00000000,&H02000000,-1,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1
    print("head_str\n\n",head_str)
    output_str = utf8bom + head_str + '\n' + subLines
    return output_str


fontDirList = [r"fonts"]

if os.environ.get("FONT_DIRS"):
    for dirPath in os.environ.get("FONT_DIRS").split(";"):
        if dirPath.strip() != "" and os.path.exists(dirPath):
            fontDirList.append(dirPath.strip())
print("本地字体文件夹:", ",".join(fontDirList))

if not os.path.exists("localFontMap.json"):
    with open("localFontMap.json", 'w', encoding="UTF-8") as f:
        json.dump({}, f)

if not os.path.exists("fonts"):
    os.makedirs("fonts", exist_ok=True)

with open("localFontMap.json", 'r', encoding="UTF-8") as f:
    localFonts = updateFontMap(fontDirList, json.load(f))

with open("localFontMap.json", 'w', encoding="UTF-8") as f:
    json.dump(localFonts, f, indent=4, ensure_ascii=True)

asu = assSubsetter(fontLoader(externalFonts=localFonts))

<<<<<<< HEAD
=======

def bytes2textWithCode(content):
    encodings = ["ascii", "utf-8", "utf-16",
                 "utf-32", "cp1252", "gb2312", "gbk", "big5"]
    for enc in encodings:
        try:
            tmp = content.decode(enc)
            return tmp, enc
        except:
            pass
    return None,None


def srt2ass(text):
    tmp = text
    src = ''
    utf8bom = ''

    if u'\ufeff' in tmp:
        tmp = tmp.replace(u'\ufeff', '')
        utf8bom = u'\ufeff'

    tmp = tmp.replace("\r", "")
    lines = [x.strip() for x in tmp.split("\n") if x.strip()]
    subLines = ''
    tmpLines = ''
    lineCount = 0

    for ln in range(len(lines)):
        line = lines[ln]
        if line.isdigit() and re.match('-?\d\d:\d\d:\d\d', lines[(ln+1)]):
            if tmpLines:
                subLines += tmpLines.replace("\n", "\\n") + "\n"
            tmpLines = ''
            lineCount = 0
            continue
        else:
            if re.match('-?\d\d:\d\d:\d\d', line):
                line = line.replace('-0', '0')
                tmpLines += 'Dialogue: 0,' + line + ',Default,,0,0,0,,'
            else:
                if lineCount < 2:
                    tmpLines += line
                else:
                    tmpLines += "\n" + line
            lineCount += 1
        ln += 1

    subLines += tmpLines + "\n"

    subLines = re.sub(r'\d(\d:\d{2}:\d{2}),(\d{2})\d', '\\1.\\2', subLines)
    subLines = re.sub(r'\s+-->\s+', ',', subLines)
    # replace style
    subLines = re.sub(r'<([ubi])>', "{\\\\\g<1>1}", subLines)
    subLines = re.sub(r'</([ubi])>', "{\\\\\g<1>0}", subLines)
    subLines = re.sub(
        r'<font\s+color="?#(\w{2})(\w{2})(\w{2})"?>', "{\\\\c&H\\3\\2\\1&}", subLines)
    subLines = re.sub(r'</font>', "", subLines)

    head_str = '''[Script Info]
; This is an Advanced Sub Station Alpha v4+ script.
Title:
ScriptType: v4.00+
Collisions: Normal
PlayDepth: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,楷体,20,&H03FFFFFF,&H00FFFFFF,&H00000000,&H02000000,-1,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text'''

    output_str = utf8bom + head_str + '\n' + subLines
    return output_str

def isSRT(text):
    srt_pattern = r'@\d+@\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}@'
    matches = re.findall(srt_pattern, "@".join(text.splitlines()))
    return len(matches) > 0

>>>>>>> c7bde4b3d34394819c1c58a4694a950203a1825e
app = FastAPI()

# @app.get("/update")


def updateLocal():
    '''更新本地字体库'''
    print("更新本地字体库中...")
    global asu
    with open("localFontMap.json", 'r', encoding="UTF-8") as f:
        localFonts = updateFontMap(fontDirList, json.load(f))
    with open("localFontMap.json", 'w', encoding="UTF-8") as f:
        json.dump(localFonts, f, indent=4, ensure_ascii=True)
    asu = assSubsetter(fontLoader(externalFonts=localFonts))
    return JSONResponse(localFonts)


def process(subText ):
    start = time.time()
<<<<<<< HEAD
    assText = assBytes.decode("UTF-8-sig")

    if isSRT(assText):
        if os.environ.get("SRT_2_ASS_FORMAT") and os.environ.get("SRT_2_ASS_STYLE"):
            print("SRT ===> ASS")
            assText = srt2ass(assText)
        else:
            raise ValueError("SRT字幕")

    if "[Fonts]\n" in assText:
        raise ValueError("已有内嵌字幕")

    if os.getenv('DEV') == 'true' and os.path.exists("DEV") and len(os.listdir("DEV")) == 1:
        print("DEV模式 使用字幕", os.path.join("DEV", os.listdir("DEV")[0]))
        with open(os.path.join("DEV", os.listdir("DEV")[0]), "r", encoding="UTF-8-sig") as f:
            assText = f.read()
=======
    if os.getenv('DEV') == 'true' and os.path.exists("DEV") and len(os.listdir("DEV")) == 1:
        print("DEV模式 使用字幕", os.path.join("DEV", os.listdir("DEV")[0]))
        with open(os.path.join("DEV", os.listdir("DEV")[0]), "rb") as f:
            subText,code = bytes2textWithCode(f.read())
    if isSRT(subText):
        raise ValueError("SRT文件")
        # print("SRT ===> ASS")
        # assText = srt2ass(subText)
    else:
        assText = subText
    
    if "[Fonts]\n" in assText:
        raise ValueError("已有内嵌字幕")
    
>>>>>>> c7bde4b3d34394819c1c58a4694a950203a1825e
    font_charList = asu.analyseAss(assText)
    errors, embedFontsText = asu.makeEmbedFonts(font_charList)
    head, tai = assText.split("[Events]")
    print(
        f"嵌入完成，用时 {time.time() - start:.2f}s \n生成Fonts {len(embedFontsText)}")
    len(errors) != 0 and print("ERRORS:" + "\n".join(errors))
    return (head + embedFontsText+"\n[Events]" + tai).encode("UTF-8-sig")


@app.post("/process_bytes")
async def process_bytes(request: Request):
    '''传入字幕字节'''
    subtitleBytes = await request.body()
    try:
        subText , code  = bytes2textWithCode(subtitleBytes)
        assBytes = process(subText)
        return Response(assBytes)
    except Exception as e:
        print(f"ERROR : {str(e)}")
        return Response(subtitleBytes)

@app.get("/process_url")
async def process_url(request: Request, ass_url: str = Query(None)):
    '''传入字幕url'''
    print("loading "+ass_url)
    try:
        subtitleBytes = requests.get(ass_url).content
        subText , code  = bytes2textWithCode(subtitleBytes)
        return Response(process(subText))
    except Exception as e:
        print(f"ERROR : {str(e)}")
        return Response(subtitleBytes)


class MyHandler(FileSystemEventHandler):
    def on_created(self, event):
        updateLocal()

    def on_deleted(self, event):
        updateLocal()


if __name__ == "__main__":
    event_handler = MyHandler()
    observer = Observer()
    for fontDir in fontDirList:
        print("监控中:", os.path.abspath(fontDir))
        observer.schedule(event_handler, os.path.abspath(
            fontDir), recursive=True)
    observer.start()
    uvicorn.run(app, host="0.0.0.0", port=8011)
    observer.stop()
    observer.join()
