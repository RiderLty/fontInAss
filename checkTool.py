# -*- coding: utf-8 -*-
# 检测ass是否可以成功子集化的脚本

# API_URL = "http://192.168.3.1:8011/fontinass/process_bytes"
API_URL = "http://192.168.3.133:8011/fontinass/process_bytes"

import os
import requests
from pathlib import Path
import base64

# path = input("文件夹路径:")
path = "/mnt/storage/Projects/fontInAss/test"
for home, _, files in os.walk(path):
    for filename in files:
        if Path(filename).suffix.lower()[1:] == "ass":
            file = Path(home, filename)
            with open(file, "rb") as f:
                res = requests.post(url=API_URL, data=f.read())
                # print(res.headers["error"])
                if "error" not in res.headers:
                    print(file)
                    print("未知错误！")
                elif res.headers["error"] != "":
                    print(file)
                    print(base64.b64decode(res.headers["error"].encode('ASCII')).decode("UTF-8"))
                    print("")
