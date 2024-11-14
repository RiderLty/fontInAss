import os
import traceback
from threading import Timer
from watchdog import observers, events
from watchdog.utils import dirsnapshot
from constants import *


class FileEventHandler(events.FileSystemEventHandler):
    def __init__(self, fontDir,callBack):
        events.FileSystemEventHandler.__init__(self)
        self.fontDir = fontDir
        self.snapshot = dirsnapshot.DirectorySnapshot(self.fontDir)
        self.timer = None
        self.callBack = callBack

    def on_any_event(self, event):
        if self.timer:
            self.timer.cancel()
        self.timer = Timer(1, self.checkSnapshot)
        self.timer.start()

    def checkSnapshot(self):
        snapshot = dirsnapshot.DirectorySnapshot(self.fontDir)
        diff = dirsnapshot.DirectorySnapshotDiff(self.snapshot, snapshot)
        self.snapshot = snapshot
        self.timer = None
        if len(diff.files_created) or len(diff.files_deleted) or len(diff.files_modified) or len(diff.files_moved):
            # 更新
            self.callBack()


class dirmonitor(object):

    def __init__(self, callBack :callable):
        self.observer = observers.Observer()
        self.callBack = callBack

    def start(self):
        try:
            for fontDir in FONT_DIRS:
                fontpath = os.path.abspath(fontDir)
                logger.info("监控中:" + fontpath)
                eventHandler = FileEventHandler(fontpath,callBack=self.callBack)
                self.observer.schedule(eventHandler, fontpath, recursive=True)
            self.observer.start()
        except Exception as e:
            logger.error(f"监视文件错误 : \n{traceback.format_exc()}")

    def stop(self):
        self.observer.stop()

    def join(self):
        self.observer.join()
