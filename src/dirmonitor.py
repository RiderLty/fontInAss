import contextlib
import errno
import os
import traceback
from pathlib import Path
from stat import S_ISDIR
from threading import Timer, Lock
from typing import Iterator
from watchdog import observers
from watchdog.utils.dirsnapshot import DirectorySnapshot, DirectorySnapshotDiff
from watchdog.events import FileSystemEventHandler
from constants import logger, FONT_DIRS, FONTS_TYPE, LOG_LEVEL

class _DirectorySnapshot(DirectorySnapshot):
    def walk(self, root: str) -> Iterator[tuple[str, os.stat_result]]:
        """重写 walk 方法，递归遍历目录树，仅返回符合条件的文件"""
        try:
            paths = [Path(root, entry.name).as_posix() for entry in self.listdir(root)]
        except OSError as e:
            if e.errno in (errno.ENOENT, errno.ENOTDIR, errno.EINVAL):
                return
            else:
                raise
        entries = []
        for p in paths:
            with contextlib.suppress(OSError):
                entry = (p, self.stat(p))
                entries.append(entry)
                # 只处理指定类型的文件
                if os.path.isfile(p) and p.lower().endswith(tuple(FONTS_TYPE)):
                    yield entry
        if self.recursive:
            for path, st in entries:
                with contextlib.suppress(PermissionError):
                    if S_ISDIR(st.st_mode):
                        yield from self.walk(path)

class _DirectorySnapshotDiff(DirectorySnapshotDiff):
    @property
    def files_moved(self) -> list[dict[str, bytes | str]]:
        """重写 files_moved 方法，直接构造moved所需要的字典"""
        return [{"old": src, "new": new} for src, new in self._files_moved]

class FileEventHandler(FileSystemEventHandler):
    def __init__(self, fontDir, callback):
        FileSystemEventHandler.__init__(self)
        self.fontDir = fontDir
        self.snapshot = _DirectorySnapshot(self.fontDir)
        self.timer = None
        self.callback = callback
        self.lock = Lock()
        self.delay = 1 if LOG_LEVEL == "DEBUG" else 5

    def on_any_event(self, event):
        if self.timer:
            self.timer.cancel()
        self.timer = Timer(self.delay, self.check_snapshot)
        self.timer.start()

    def check_snapshot(self):
        with self.lock:
            try:
                snapshot = _DirectorySnapshot(self.fontDir)
                diff = _DirectorySnapshotDiff(self.snapshot, snapshot)
                self.snapshot = snapshot
                self.timer = None
                if diff.files_deleted:
                    # print(f"diff.files_deleted: {diff.files_deleted}")
                    self.callback.del_fileinfo_with_filepath(diff.files_deleted)
                if diff.files_created:
                    # print(f"diff.files_created: {diff.files_created}")
                    self.callback.ins_fileinfo_and_fontinfo(diff.files_created)
                if diff.files_modified:
                    # print(f"diff.files_modified: {diff.files_modified}")
                    self.callback.del_fileinfo_with_filepath(diff.files_modified)
                    self.callback.ins_fileinfo_and_fontinfo(diff.files_modified)
                if diff.files_moved:
                    # print(f"diff.files_moved: {diff.files_moved}")
                    self.callback.update_fileinfo_with_filepath(diff.files_moved)
            except Exception as e:
                print(e)

class dirmonitor(object):

    def __init__(self, callback: callable):
        self.observer = observers.Observer()
        self.callback = callback

    def start(self):
        try:
            for fontDir in FONT_DIRS:
                fontpath = os.path.abspath(fontDir)
                logger.info("监控中:" + fontpath)
                eventHandler = FileEventHandler(fontpath, callback=self.callback)
                self.observer.schedule(eventHandler, fontpath, recursive=True)
            self.observer.start()
        except Exception as e:
            logger.error(f"监视文件错误 : \n{traceback.format_exc()}")

    def stop(self):
        self.observer.stop()

    def join(self):
        self.observer.join()
