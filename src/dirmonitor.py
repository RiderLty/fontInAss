import contextlib
import errno
import os
from pathlib import Path
from stat import S_ISDIR
from threading import Timer, Lock
from typing import Iterator
from watchdog import observers
from watchdog.utils.dirsnapshot import DirectorySnapshot, DirectorySnapshotDiff
from watchdog.events import FileSystemEventHandler
from constants import logger, FONT_DIRS, FONTS_TYPE, LOG_LEVEL
from fontmanager import FontManager

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
    def __init__(
            self,
            ref: DirectorySnapshot,
            snapshot: DirectorySnapshot,
            *,
            ignore_device: bool = False,
    ) -> None:
        super().__init__(ref, snapshot, ignore_device=ignore_device)
        created = snapshot.paths - ref.paths
        deleted = ref.paths - snapshot.paths

        if ignore_device:

            def get_inode(directory: DirectorySnapshot, full_path: bytes | str) -> int | tuple[int, int]:
                return directory.inode(full_path)[0]

        else:

            def get_inode(directory: DirectorySnapshot, full_path: bytes | str) -> int | tuple[int, int]:
                return directory.inode(full_path)

        # check that all unchanged paths have the same inode
        for path in ref.paths & snapshot.paths:
            if get_inode(ref, path) != get_inode(snapshot, path):
                created.add(path)
                deleted.add(path)

        # find moved paths
        moved: set[tuple[bytes | str, bytes | str]] = set()
        for path in set(deleted):
            inode = ref.inode(path)
            new_path = snapshot.path(inode)
            if new_path and ref.mtime(path) == snapshot.mtime(new_path):
                # file is not deleted but moved
                deleted.remove(path)
                moved.add((path, new_path))

        for path in set(created):
            inode = snapshot.inode(path)
            old_path = ref.path(inode)
            if old_path and ref.mtime(old_path) == snapshot.mtime(path):
                created.remove(path)
                moved.add((old_path, path))

        # find modified paths
        # first check paths that have not moved
        modified: set[bytes | str] = set()
        for path in ref.paths & snapshot.paths:
            if get_inode(ref, path) == get_inode(snapshot, path) and (
                ref.mtime(path) != snapshot.mtime(path) or ref.size(path) != snapshot.size(path)
            ):
                modified.add(path)

        for old_path, new_path in moved:
            if ref.mtime(old_path) != snapshot.mtime(new_path) or ref.size(old_path) != snapshot.size(new_path):
                modified.add(old_path)

        self._dirs_created = [path for path in created if snapshot.isdir(path)]
        self._dirs_deleted = [path for path in deleted if ref.isdir(path)]
        self._dirs_modified = [path for path in modified if ref.isdir(path)]
        self._dirs_moved = [(frm, to) for (frm, to) in moved if ref.isdir(frm)]

        self._files_created = list(created - set(self._dirs_created))
        self._files_deleted = list(deleted - set(self._dirs_deleted))
        self._files_modified = list(modified - set(self._dirs_modified))
        self._files_moved = list(moved - set(self._dirs_moved))

    @property
    def files_moved(self) -> list[dict[str, bytes | str]]:
        """重写 files_moved 方法，直接构造moved所需要的字典"""
        return [{"old": src, "new": new} for src, new in self._files_moved]

class FileEventHandler(FileSystemEventHandler):
    def __init__(self, font_dir, font_manager_instance: FontManager):
        FileSystemEventHandler.__init__(self)
        self.font_dir = font_dir
        self.snapshot = _DirectorySnapshot(self.font_dir)
        self.timer = None
        self.font_manager_instance = font_manager_instance
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
                snapshot = _DirectorySnapshot(self.font_dir)
                diff = _DirectorySnapshotDiff(self.snapshot, snapshot)
                self.snapshot = snapshot
                self.timer = None
                if diff.files_deleted:
                    # print(f"diff.files_deleted: {diff.files_deleted}")
                    self.font_manager_instance.del_fileinfo_with_filepath(diff.files_deleted)
                if diff.files_created:
                    # print(f"diff.files_created: {diff.files_created}")
                    self.font_manager_instance.ins_fileinfo_and_fontinfo(diff.files_created)
                if diff.files_modified:
                    # print(f"diff.files_modified: {diff.files_modified}")
                    self.font_manager_instance.del_fileinfo_with_filepath(diff.files_modified)
                    self.font_manager_instance.ins_fileinfo_and_fontinfo(diff.files_modified)
                if diff.files_moved:
                    # print(f"diff.files_moved: {diff.files_moved}")
                    self.font_manager_instance.update_fileinfo_with_filepath(diff.files_moved)
            except Exception as e:
                logger.exception("监视文件变化发生错误")

class dirmonitor(object):

    def __init__(self, font_manager_instance: FontManager):
        self.observer = observers.Observer()
        self.font_manager_instance = font_manager_instance

    def start(self):
        try:
            for font_dir in FONT_DIRS:
                font_path = os.path.abspath(font_dir)
                logger.info("监控中:" + font_path)
                event_handler = FileEventHandler(font_path, font_manager_instance=self.font_manager_instance)
                self.observer.schedule(event_handler, font_path, recursive=True)
            self.observer.start()
        except Exception as e:
            logger.exception("监视文件错误")
            # logger.error(f"监视文件错误 : \n{traceback.format_exc()}")

    def stop(self):
        self.observer.stop()

    def join(self):
        self.observer.join()
