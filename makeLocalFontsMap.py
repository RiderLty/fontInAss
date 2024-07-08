import os
from io import BytesIO
from easyass import *
from fontTools.ttLib import TTFont, TTCollection
import os
import time
import json


def getAllSub(path):
    Filelist = []
    for home, dirs, files in os.walk(path):
        for filename in files:
            Filelist.append(os.path.join(home, filename))
    return Filelist


def pathReplacer(path):
    return path.replace("E:\\", "/").replace("\\", "/")
    # return path

if __name__ == "__main__":
    font_file_map = {}
    font_miniSize = {}

    def addFont(font_name, path):
        if font_name in font_file_map and font_miniSize[font_name] <= os.path.getsize(path):
            return
        font_file_map[font_name] = pathReplacer(path)
        font_miniSize[font_name] = os.path.getsize(path)

    for file in getAllSub(r"E:\超级字体整合包 XZ"):
        try:
            fonts = []
            if file.lower().endswith("ttc"):
                fonts = TTCollection(file).fonts
            elif file.lower().endswith("ttf") or file.lower().endswith("otf"):
                fonts = [TTFont(file)]
            for font in fonts:
                for record in font['name'].names:
                    if record.nameID == 1:  # Font Family name
                        addFont(str(record).strip(), file)
        except Exception as e:
            print(e, file)

    with open("./fontMap.json" , 'w' , encoding="UTF-8") as f:
    # with open("./localFontMap.json" , 'w' , encoding="UTF-8") as f:
        f.write(json.dumps(font_file_map , indent=4 ,ensure_ascii=True))
