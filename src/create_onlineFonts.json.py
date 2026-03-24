
from typing import Any


import os
import json
import sys
from pathlib import Path
from tqdm import tqdm
sys.path.append(str(Path(__file__).parent.parent))
from utils import get_all_files, get_font_info

# 在线字体库的URL前缀
HOSTS = [r"https://vip.123pan.cn/1833788059/direct/",r"https://fonts.storage.rd5isto.org/"]
# 要扫描的字体文件所在的根目录
TARGET_DIR = r"/mnt/storage/Fonts/"
# 生成的JSON文件的输出路径
OUTPUT_FILE = "customOnlineFonts.json"

def main():
    """主函数，利用现有工具函数扫描字体并生成与 make_online_map 格式一致的 JSON"""
    if not TARGET_DIR or not OUTPUT_FILE:
        print("错误: 请在脚本顶部设置 TARGET_DIR 和 OUTPUT_FILE 变量。")
        sys.exit(1)

    if not os.path.isdir(TARGET_DIR):
        print(f"错误: 目录 '{TARGET_DIR}' 不存在。")
        sys.exit(1)

    print(f"正在从 '{TARGET_DIR}' 扫描所有字体文件...")
    all_font_files = get_all_files(TARGET_DIR)

    if not all_font_files:
        print("警告: 在指定目录中没有找到任何字体文件。")
        sys.exit(0)

    print(f"找到了 {len(all_font_files)} 个字体文件，开始解析...")
    font_list = []

    with tqdm(
        total=len(all_font_files),
        desc="解析字体",
        unit="file",
        bar_format="{l_bar}{bar} {n_fmt}/{total_fmt} | {rate_fmt} | {remaining}",
    ) as pbar:
        for font_path in all_font_files:
            try:
                _, font_info_list, _ = get_font_info(font_path)

                for info in font_info_list:
                    # 计算相对路径
                    relative_path = str(Path(font_path).relative_to(TARGET_DIR)).replace('\\', '/')
                    
                    # 创建与 make_online_map 兼容的字体记录
                    font_record = {
                        "path": relative_path,
                        "size": info.get("size"),
                        "index": info.get("index"),
                        "familyName": info.get("familyName"),
                        "fullName": info.get("fullName"),
                        "postscriptName": info.get("postscriptName"),
                        "postscriptCheck": info.get("postscriptCheck"),
                        "weight": info.get("weight"),
                        "bold": info.get("bold"),
                        "italic": info.get("italic"),
                    }
                    font_list.append(font_record)

            except Exception as e:
                print(f"\n错误: 处理文件 '{font_path}' 失败: {e}")
            finally:
                pbar.update(1)

    print(f"\n解析完成。共找到 {len(font_list)} 个独立字体。开始构建名称索引...")

    name_index_map = {}
    for index, fontInfo in enumerate[Any](font_list):
        for names in [fontInfo["familyName"], fontInfo["postscriptName"], fontInfo["fullName"]]:
            for name in names:
                name_index_map.setdefault(name, set()).add(index)

    name_index_dict = {}
    for name, indexSet in name_index_map.items():
        name_index_dict[name] = list(indexSet)

    final_json_structure = [
        HOSTS,
        name_index_dict,
        font_list
    ]

    print(f"索引构建完成，包含 {len(name_index_dict)} 个名称条目。")

    try:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            # 使用与 make_online_map 相同的参数，确保格式完全一致（无缩进，ASCII编码）
            json.dump(final_json_structure, f, ensure_ascii=True)
        print(f"成功将数据写入: {OUTPUT_FILE}")
    except Exception as e:
        print(f"错误: 写入文件 '{OUTPUT_FILE}' 失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
