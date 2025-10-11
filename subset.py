import json
import os
import sys
import requests
import base64


def get_subtitle_files(folder):
    exts = {'.ass', '.ssa', '.srt'}
    result = []
    for root, _, files in os.walk(folder):
        for file in files:
            if os.path.splitext(file)[1].lower() in exts:
                result.append(os.path.abspath(os.path.join(root, file)))
    return result


def getSubset(filePath, base_url):
    headers = {
        'Accept': '*/*',
        'Accept-Language': 'zh',
        'Connection': 'keep-alive',
        'Content-Type': 'application/octet-stream',
        'DNT': '1',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36 Edg/141.0.0.0',
        'X-Clear-Fonts': '1',
        'X-Fonts-Check': '0',
        'X-Renamed-Restore': '1',
        'X-Srt-Format':'Rm9ybWF0OiBOYW1lLCBGb250bmFtZSwgRm9udHNpemUsIFByaW1hcnlDb2xvdXIsIFNlY29uZGFyeUNvbG91ciwgT3V0bGluZUNvbG91ciwgQmFja0NvbG91ciwgQm9sZCwgSXRhbGljLCBVbmRlcmxpbmUsIFN0cmlrZU91dCwgU2NhbGVYLCBTY2FsZVksIFNwYWNpbmcsIEFuZ2xlLCBCb3JkZXJTdHlsZSwgT3V0bGluZSwgU2hhZG93LCBBbGlnbm1lbnQsIE1hcmdpbkwsIE1hcmdpblIsIE1hcmdpblYsIEVuY29kaW5n',
        'X-Srt-Style': 'U3R5bGU6IERlZmF1bHQs5qW35L2TLDIwLCZIMDNGRkZGRkYsJkgwMEZGRkZGRiwmSDAwMDAwMDAwLCZIMDIwMDAwMDAsLTEsMCwwLDAsMTAwLDEwMCwwLDAsMSwyLDAsMiwxMCwxMCwxMCwx',

    }
    url = base_url.rstrip('/') + '/api/subset'
    with open(filePath, 'rb') as f:
        response = requests.post(url, headers=headers, data=f.read(), verify=False)
    if response.headers.get("x-code") == '200':
        print(f"成功处理 {filePath}\n")
        return filePath, response.content, None
    else:
        message = response.headers.get("x-message")
        decoded_message = json.loads(base64.b64decode(message.encode("ascii")).decode("utf-8"))
        print(f"处理 {filePath} 时出错\n错误信息: {decoded_message}\n")
        return filePath, response.content, decoded_message


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("用法: python subset.py <文件夹路径> <base_url>")
        sys.exit(1)
    folder = sys.argv[1]
    base_url = sys.argv[2]
    files = get_subtitle_files(folder)
    subseted = [getSubset(x, base_url) for x in files]
    if input("全部处理完成，是否替换原文件？(y/n): ").lower() == 'y':
        for filePath, content, error in subseted:
            # if error is not None:
            #     print(f"跳过 {filePath}，因为处理时出错。")
            #     continue
            # else:
            with open(filePath, 'wb') as f:
                f.write(content)
            print(f"已替换 {filePath}")
    else:
        print("未替换任何文件。")
