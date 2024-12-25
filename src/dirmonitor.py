import os
import traceback
from pathlib import Path
from threading import Timer , Lock
from watchdog import observers
from watchdog.utils.dirsnapshot import DirectorySnapshot, DirectorySnapshotDiff
from watchdog.events import FileSystemEventHandler
from constants import logger, FONT_DIRS, FONTS_TYPE, LOG_LEVEL

class FileEventHandler(FileSystemEventHandler):
    def __init__(self, fontDir, callBack):
        FileSystemEventHandler.__init__(self)
        self.fontDir = fontDir
        self.snapshot = DirectorySnapshot(self.fontDir)
        self.timer = None
        self.callBack = callBack
        self.lock = Lock()
        if LOG_LEVEL == "DEBUG":
            self.delay = 1
        else:
            self.delay = 10

    def on_any_event(self, event):
        if self.timer:
            self.timer.cancel()
        self.timer = Timer(self.delay, self.checkSnapshot)
        self.timer.start()

    def checkSnapshot(self): # 如果文件被修改，会先触发添加再触发删除 待解决
        with self.lock:
            try:
                snapshot = DirectorySnapshot(self.fontDir)
                diff = DirectorySnapshotDiff(self.snapshot, snapshot)
                self.snapshot = snapshot
                self.timer = None
                if diff.files_moved:
                    list = self.filter_font_files(diff.files_moved, is_moved=True)
                    if list:
                        self.callBack.update_fontinfo_with_filepath(list)
                if diff.files_created:
                    list = self.filter_font_files(diff.files_created)
                    if list:
                        self.callBack.ins_fontinfo_and_fontdetail(list)
                if diff.files_deleted:
                    list = self.filter_font_files(diff.files_deleted)
                    if list:
                        self.callBack.del_fontinfo_with_filepath(list)
                if diff.files_modified:
                    list = self.filter_font_files(diff.files_modified)
                    if list:
                        self.callBack.del_fontinfo_with_filepath(list)
                        self.callBack.ins_fontinfo_and_fontdetail(list)
            except Exception as e:
                print(e)

    def filter_font_files(self, files_list, is_moved=False):
        filtered_files = []
        if is_moved:
            for old_file_path, new_file_path in files_list:
                old_file_path = Path(old_file_path)
                new_file_path = Path(new_file_path)
                # 检查旧路径是否符合字体类型后缀
                if old_file_path.suffix and old_file_path.suffix[1:].lower() in FONTS_TYPE:
                    # 将符合条件的文件路径加入到列表中
                    filtered_files.append({
                        "file_path": old_file_path.as_posix(),  # 旧路径
                        "new_file_path": new_file_path.as_posix()  # 新路径
                    })
        else:
            for file_path in files_list:
                file_path = Path(file_path)
                # 检查文件路径是否符合字体类型后缀
                if file_path.suffix and file_path.suffix[1:].lower() in FONTS_TYPE:
                    # 将符合条件的文件路径加入到列表中
                    filtered_files.append(file_path.as_posix())
        # 最后返回符合条件的文件列表
        return filtered_files


class dirmonitor(object):

    def __init__(self, callBack: callable):
        self.observer = observers.Observer()
        self.callBack = callBack

    def start(self):
        try:
            for fontDir in FONT_DIRS:
                fontpath = os.path.abspath(fontDir)
                logger.info("监控中:" + fontpath)
                eventHandler = FileEventHandler(fontpath, callBack=self.callBack)
                self.observer.schedule(eventHandler, fontpath, recursive=True)
            self.observer.start()
        except Exception as e:
            logger.error(f"监视文件错误 : \n{traceback.format_exc()}")

    def stop(self):
        self.observer.stop()

    def join(self):
        self.observer.join()
