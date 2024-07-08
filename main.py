
from io import BytesIO
import threading
from easyass import *
from fontTools.ttLib import TTFont, TTCollection
from fontTools.subset import Subsetter
import os
import time
import json
import requests
import queue
import boto3
import uvicorn
from fastapi import FastAPI, Query, Request, Response


class fontLoader():
    def __init__(self) -> None:
        self.font_2_path = json.load(
            open("fontMap.json", 'r', encoding="UTF-8"))
        usingS3 = os.environ.get("S3_ENDPOINT_URL") and os.environ.get(
            "S3_AWS_ACCESS_KEY_ID") and os.environ.get("S3_AWS_SECRET_ACCESS_KEY")
        if usingS3:
            print("env S3_ENDPOINT_URL,S3_AWS_ACCESS_KEY_ID,S3_AWS_SECRET_ACCESS_KEY found ! using s3 to load fonts")
            self.Bucket = boto3.resource(
                's3',
                endpoint_url=os.environ.get("S3_ENDPOINT_URL"),
                aws_access_key_id=os.environ.get("S3_AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.environ.get(
                    "S3_AWS_SECRET_ACCESS_KEY")
            ).Bucket("fonts")
        else:
            print("env not found ! using http to load fonts")
            self.Bucket = None

    def loadFont(self, fontName):
        if not self.Bucket:
            if fontName in self.font_2_path:
                try:
                    path = self.font_2_path[fontName]
                    start = time.time()
                    rawStream = self.Bucket.Object(path[1:]).get()['Body'].read()
                    print(f"load {fontName} {len(rawStream) // 1048576:.2f}MB in {(time.time() - start):.2f}s")
                    bio = BytesIO()
                    bio.write(rawStream)
                    bio.seek(0)
                    if path.lower().endswith("ttc"):
                        ttc = TTCollection(bio)
                        for font in ttc.fonts:
                            for record in font['name'].names:
                                if record.nameID == 1 and str(record) == fontName:
                                    return font
                    elif path.lower().endswith("ttf") or path.lower().endswith("otf"):
                        return TTFont(bio)
                    else:
                        return None
                except Exception as e:
                    print(f"{fontName} error : {str(e)}")
                    return None
            else:
                return None

        else:
            if fontName in self.font_2_path:
                try:
                    path = self.font_2_path[fontName]
                    start = time.time()
                    data = requests.get("https://fonts.storage.rd5isto.org" + path).content
                    print(f"load {fontName} {len(data) // 1048576:.2f}MB in {(time.time() - start):.2f}s")
                    bio = BytesIO()
                    bio.write(data)
                    bio.seek(0)
                    if path.lower().endswith("ttc"):
                        ttc = TTCollection(bio)
                        for font in ttc.fonts:
                            for record in font['name'].names:
                                if record.nameID == 1 and str(record) == fontName:
                                    return font
                    elif path.lower().endswith("ttf") or path.lower().endswith("otf"):
                        return TTFont(bio)
                    else:
                        return None
                except Exception as e:
                    print(f"{fontName} error : {str(e)}")
                    return None
            else:
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
            match = re.findall(r'{.*\\fn(.*?)\\|}', line)
            if len(match) != 0 and match[0] != "":
                fontName = match[0].replace("@", "")
                for ch in line[line.index("}")+1:]:
                    if fontName not in font_charList:
                        font_charList[fontName] = set()
                    font_charList[fontName].add(ord(ch))
        return font_charList

    def encode_binary_data(self, binaryData):
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

    def makeOneEmbedFontsText(self, fontName, unicodeSet, resultQueue , sem):
        with sem:
            print(f"loading : {fontName}")
            font = self.fontLoader.loadFont(fontName)
            if font == None:
                # return f"{fontName} miss", None
                resultQueue.put((f"{fontName} miss", None))
            else:
                try:
                    originNames = font['name'].names
                    subsetter = Subsetter()
                    subsetter.populate(unicodes=unicodeSet)  # 输入需要子集化的文本内容
                    subsetter.subset(font)
                    font["name"].names = originNames
                    fontOutIO = BytesIO()
                    font.save(fontOutIO)  # 生成新的子集字体文件
                    enc = self.encode_binary_data(fontOutIO.getvalue())
                    # return None, f"fontname:{fontName}_0.ttf\n{enc}\n"
                    resultQueue.put((None, f"fontname:{fontName}_0.ttf\n{enc}\n"))
                except Exception as e:
                    # return f"{fontName} : {str(e)}", None
                    resultQueue.put((f"{fontName} : {str(e)}", None))

    def makeEmbedFonts(self, font_charList):
        '''对于给定的 字体:使用到的编码列表 返回编码后的，可嵌入ASS的文本 '''
        embedFontsText = "[Fonts]\n"
        errors = []
        resultQueue = queue.Queue()
        
        sem = threading.Semaphore(3)
        
        for fontName, unicodeSet in font_charList.items():
            if len(unicodeSet) != 0:
                
                threading.Thread(target=self.makeOneEmbedFontsText, args=(fontName, unicodeSet, resultQueue , sem)).start()
        for fontName, unicodeSet in font_charList.items():
            if len(unicodeSet) != 0:
                (err, result) = resultQueue.get()
                if err:
                    errors.append(errors)
                else:
                    embedFontsText += result
        return errors, embedFontsText


asu = assSubsetter(fontLoader=fontLoader())
# assText = open(r"S01E22.chs.ass", 'r', encoding="UTF-8-sig").read()
# font_charList = asu.analyseAss(assText)
# print(font_charList)
# errors, embedFontsText = asu.makeEmbedFonts(font_charList)
# ok = assText.replace("[Events]\n", embedFontsText + "\n[Events]\n")
# open(r"S01E22.chs.finished.ass", 'w', encoding="UTF-8-sig").write(ok)

app = FastAPI()


@app.post("/process_bytes")
async def process(request: Request):
    start = time.time()
    subtitleBytes = await request.body()
    try:
        assText = subtitleBytes.decode("UTF-8-sig")
        font_charList = asu.analyseAss(assText)
        errors, embedFontsText = asu.makeEmbedFonts(font_charList)
        head, tai = assText.split("[Events]")
        print(f"嵌入完成，用时 {time.time() - start:.2f}s")
        return Response((head + embedFontsText+"\n[Events]" + tai).encode("UTF-8-sig"))
    except Exception as e:
        return Response(subtitleBytes)

@app.get("/process_url")
async def process(request: Request , ass_url: str = Query(None)):
    start = time.time()
    subtitleBytes = requests.get(ass_url).content
    try:
        assText = subtitleBytes.decode("UTF-8-sig")
        font_charList = asu.analyseAss(assText)
        errors, embedFontsText = asu.makeEmbedFonts(font_charList)
        head, tai = assText.split("[Events]")
        print(f"嵌入完成，用时 {time.time() - start:.2f}s")
        return Response((head + embedFontsText+"\n[Events]" + tai).encode("UTF-8-sig"))
    except Exception as e:
        return Response(subtitleBytes)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8011)
