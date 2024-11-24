import os
import traceback
from pathlib import Path
from threading import Timer
from watchdog import observers, events
from watchdog.utils import dirsnapshot
from constants import logger, FONT_DIRS, FONTS_TYPE, LOG_LEVEL



class FileEventHandler(events.FileSystemEventHandler):
    def __init__(self, fontDir, callBack):
        events.FileSystemEventHandler.__init__(self)
        self.fontDir = fontDir
        self.snapshot = dirsnapshot.DirectorySnapshot(self.fontDir)
        self.timer = None
        self.callBack = callBack
        if LOG_LEVEL == "DEBUG":
            self.delay = 1
        else:
            self.delay = 10

    def on_any_event(self, event):
        if self.timer:
            self.timer.cancel()
        self.timer = Timer(self.delay, self.checkSnapshot)
        self.timer.start()

    def checkSnapshot(self):
        snapshot = dirsnapshot.DirectorySnapshot(self.fontDir)
        diff = dirsnapshot.DirectorySnapshotDiff(self.snapshot, snapshot)
        self.snapshot = snapshot
        self.timer = None
        if diff.files_moved:
            list = self.filter_font_files(diff.files_moved, is_moved=True)
            self.callBack.update_fontinfo_with_filepath(list)
        if diff.files_created:
            list = self.filter_font_files(diff.files_created)
            self.callBack.ins_fontinfo_and_fontdetail(list)
        if diff.files_deleted:
            list = self.filter_font_files(diff.files_deleted)
            self.callBack.del_fontinfo_with_filepath(list)
        if diff.files_modified:
            list = self.filter_font_files(diff.files_modified)
            self.callBack.del_fontinfo_with_filepath(list)
            self.callBack.ins_fontinfo_and_fontdetail(list)

    def filter_font_files(self, files, is_moved=False):
        """
        过滤文件列表，仅保留后缀属于 FONTS_TYPE 的文件，并将路径转换为 POSIX 格式。
        :param files: 文件路径列表（单路径或双路径） [x,x,...] [(x,y),(x,y),...]
        :param is_moved: 是否为移动文件操作（需要双路径处理），顺便构造数据结构
        :return: 过滤后的文件路径列表或路径对列表
        """
        if is_moved:
            return [
                {"file_path": str(Path(file[0]).as_posix()), "new_file_path": str(Path(file[1]).as_posix())}
                for file in files
                if Path(file[0]).suffix.lower()[1:] in FONTS_TYPE and Path(file[1]).suffix.lower()[1:] in FONTS_TYPE
            ]
        else:
            return [
                str(Path(file_path).as_posix())
                for file_path in files
                if Path(file_path).suffix.lower()[1:] in FONTS_TYPE
            ]


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
