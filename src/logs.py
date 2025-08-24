import asyncio
import os
from collections import OrderedDict
import aiofiles

class logsManager:
    def __init__(self, file_path, max_lines, order=True):
        self._check_and_create_file(file_path)
        self._lock = asyncio.Lock()
        self._file_path = file_path
        self._max_lines = max(max_lines, 1)
        self._order = order
        self._data = OrderedDict()
        self._last_known_state = self._get_file_state()
        self._load()

    def _check_and_create_file(self, file_path):
        if not file_path.lower().endswith(".txt"):
            raise ValueError("必须为txt文件")
        if not os.path.exists(file_path):
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    pass
            except Exception as e:
                print(f"创建日记文件失败: {e}")

    def _get_file_state(self):
        if not os.path.exists(self._file_path):
            return None
        stat = os.stat(self._file_path)
        return (stat.st_mtime, stat.st_size)

    def _sync_with_file(self):
        current_state = self._get_file_state()
        if current_state is None:
            # if self._data:
                # print("日记文件运行中被删除了")
            self._data.clear()
            return None
        if current_state != self._last_known_state:
            # print("日记文件运行中被外部修改了")
            self._load()
            return True
        return False

    def _load(self):
        if not os.path.exists(self._file_path):
            return None
        self._data.clear()
        with open(self._file_path, 'r', encoding='utf-8') as f:
            for line in f:
                key = line.strip()
                if key:
                    self._data[key] = None
            # print(self._data)
        #如果后面没有_save 这里必须加 self._last_known_state = self._get_file_state()

    async def insert(self, keys):
        async with self._lock:
            # print("我要测试是否阻塞主线程了")
            # await asyncio.sleep(10)
            if not isinstance(keys, (list, tuple)):
                keys = [keys]

            self._sync_with_file()

            for key in keys:
                self._data[key] = None
                # True移动到末尾（顺序模式）或者 False开头（逆序模式）
                self._data.move_to_end(key, last=self._order)

            # 超出上限则删除多余的
            excess = len(self._data) - self._max_lines
            for _ in range(max(0, excess)):
                self._data.popitem(last=not self._order)
            # print("完成开始保存")
            await self._save()


    async def delete(self, keys):
        async with self._lock:
            if not isinstance(keys, (list, tuple)):
                keys = [keys]

            self._sync_with_file()

            for key in keys:
                self._data.pop(key, None)
            await self._save()

    async def _save(self):
        content = '\n'.join(self._data) if self._data else ''
        async with aiofiles.open(self._file_path, "w", encoding="utf-8") as f:
            await f.write(content)
        self._last_known_state = self._get_file_state()

# if __name__ == "__main__":
#     # 测试用例
#     logs = logsManager(
#         "logs.txt",
#         max_lines=3,
#         order=False
#     )
#     # for i in range(1, 3):
#     #     logs.insert(f"字体{i}")
#
#     logs.insert(f"字体99")
#     logs.insert(f"字体98")
#     # logs.delete(f"字体99")
#     logs.insert(f"字体99")
#     logs.insert(["字体96","字体989",])
#     logs.delete(f"字体96")
#     logs.delete(f"字体2")
#     logs.delete(f"字体1")