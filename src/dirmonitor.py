#!/usr/bin/python
# -*- coding: utf-8 -*-
import logging
import os
import traceback
from threading import Timer
from watchdog import observers, events
from watchdog.utils import dirsnapshot
import utils

logger = logging.getLogger(f'{"main"}:{"loger"}')


class FileEventHandler(events.FileSystemEventHandler):
    def __init__(self, fontDir, fontDirList):
        events.FileSystemEventHandler.__init__(self)
        self.fontDir = fontDir
        self.fontDirList = fontDirList
        self.snapshot = dirsnapshot.DirectorySnapshot(self.fontDir)
        self.timer = None

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
            # print("file change", diff.files_created)
            utils.updateLocal(self.fontDirList)
        # 下面是应处理的各种事项
        # if len(diff.files_created):
        #     print("file create", diff.files_created)
        #     utils.updateLocal(self.fontDirList)
        # if len(diff.files_deleted):
        #     print("file delete", diff.files_deleted)
        #     utils.updateLocal(self.fontDirList)
        # if len(diff.files_modified):
        #     print("file modify", diff.files_modified)
        #     utils.updateLocal(self.fontDirList)
        # if len(diff.files_moved):
        #     print("file move", diff.files_moved)
        #     utils.updateLocal(self.fontDirList)
        # if len(diff.dirs_modified):
        #     print("dir modify", diff.dirs_modified)
        # if len(diff.dirs_moved):
        #     print("dir move", diff.dirs_moved)
        # if len(diff.dirs_deleted):
        #     print("dir delete", diff.dirs_deleted)
        # if len(diff.dirs_created):
        #     print("dir cteate", diff.dirs_created)


class dirmonitor(object):
    """文件夹监视类"""

    def __init__(self, fontDirList: list):
        """构造函数"""
        self.fontDirList = fontDirList
        self.observer = observers.Observer()

    def start(self):
        """启动"""
        try:
            for fontDir in self.fontDirList:
                fontpath = os.path.abspath(fontDir)
                logger.info("监控中:" + fontpath)
                event_handler = FileEventHandler(fontpath, self.fontDirList)
                self.observer.schedule(event_handler, fontpath, recursive=True)
            self.observer.start()
        except Exception as e:
            print(f"监视文件错误 : \n{traceback.format_exc()}")

    def stop(self):
        """停止"""
        self.observer.stop()

    def join(self):
        """停止"""
        self.observer.join()