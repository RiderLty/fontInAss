import os
from io import BytesIO
from easyass import *
from fontTools.ttLib import TTFont, TTCollection
from fontTools.ttLib.sfnt import readTTCHeader
import os
import time
import json


def getAllFiles(path):
    Filelist = []
    for home, dirs, files in os.walk(path):
        for filename in files:
            Filelist.append(os.path.join(home, filename))
    return Filelist


def pathReplacer(path):
    # return path.replace("E:\\", "/").replace("\\", "/")
    return path


def updateFontMap(dirPath, old={}):
    fontMap = {}
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


if __name__ == "__main__":
    # json.load(open("./fontMap.json", 'r', encoding="UTF-8"))
    # res = updateFontMap(r"E:\超级字体整合包 XZ")
    # with open("./fontMap.json", 'w', encoding="UTF-8") as f:
    #     f.write(json.dumps(res, indent=4, ensure_ascii=True))


    res = updateFontMap(r"E:\超级字体整合包 XZ")
    with open("./localFontMap.json", 'w', encoding="UTF-8") as f:
        f.write(json.dumps(res, indent=4, ensure_ascii=True))
