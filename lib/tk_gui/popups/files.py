"""
Tkinter GUI popups: basic prompts

:author: Doug Skrypa
"""

from __future__ import annotations

import logging
import os
from functools import cached_property
from pathlib import Path
from shutil import copyfile, copystat
from stat import S_ISDIR
from time import monotonic
from typing import TYPE_CHECKING, Union, Collection, Mapping

from ..elements import Text, ProgressBar
from ..utils import readable_bytes
from .base import Popup

if TYPE_CHECKING:
    from ..typing import Layout

__all__ = ['CopyFilesPopup']
log = logging.getLogger(__name__)

SrcDstPaths = Union[Collection[tuple[Path, Path]], Mapping[Path, Path]]


class CopyFilesPopup(Popup):
    progress_bar: ProgressBar
    progress_text: Text
    file_num_text: Text
    speed_text: Text
    _src_root = None

    def __init__(self, src_dst_paths: SrcDstPaths, src_root: Path = None, **kwargs):
        kwargs['bind_esc'] = False
        kwargs.setdefault('title', 'Copying Files...')
        super().__init__(**kwargs)
        self.src_root = src_root
        try:
            self.src_dst_paths = src_dst_paths.items()
        except AttributeError:
            self.src_dst_paths = src_dst_paths

    @classmethod
    def copy_dir(cls, src_dir: Path, dst_dir: Path, **kwargs) -> CopyFilesPopup:
        src_dst_paths = []
        src_dir = src_dir.resolve()
        for root, dirs, files in os.walk(src_dir):
            if files:
                src_root = Path(root)
                dst_root = dst_dir.joinpath(src_root.relative_to(src_dir))
                for file in files:
                    src_dst_paths.append((src_root / file, dst_root / file))

        return cls(src_dst_paths, src_dir, **kwargs)

    @property
    def src_root(self) -> Path:
        if self._src_root is not None:
            return self._src_root
        elif prefix := os.path.commonprefix([src for src, _ in self.src_dst_paths]):
            prefix = Path(prefix).resolve()
            if prefix.is_dir():
                self._src_root = prefix
                return prefix
        self._src_root = Path.cwd().resolve()
        return self._src_root

    @src_root.setter
    def src_root(self, value: Path):
        self._src_root = value

    def get_pre_window_layout(self) -> Layout:
        self.progress_bar = ProgressBar(len(self._src_dst_files), size=(500, 30), side='t')
        max_path_len = max(len(rel_path) for _, _, rel_path, _ in self._src_dst_files)
        self.progress_text = Text('', size=(min(max_path_len, 180), 1))
        self.file_num_text = Text('', size=(30, 1))
        self.speed_text = Text('', size=(20, 1))
        yield [self.progress_bar]
        yield [Text('Copying:'), self.progress_text]
        yield [Text('Num:'), self.file_num_text, Text('Speed:'), self.speed_text]

    def run_window(self):
        self.window.update()
        self.copy_files()
        self.window.update()

    @cached_property
    def _classified_paths(self):
        files = []
        to_create = set()
        exists = set()

        src_root = self.src_root
        for src_path, dst_path in self.src_dst_paths:
            src_stat = src_path.stat()
            if S_ISDIR(src_stat.st_mode):
                dst_dir = dst_path
            else:
                try:
                    rel_path = src_path.resolve().relative_to(src_root).as_posix()
                except Exception:  # noqa
                    rel_path = src_path.name
                files.append((src_path, dst_path, rel_path, src_stat.st_size))
                dst_dir = dst_path.parent

            if dst_dir in exists:
                continue
            elif dst_dir.is_dir():
                exists.add(dst_dir)
            elif dst_dir.exists():
                raise FileExistsError(f'dst_dir={path_repr(dst_dir)} already exists, but it is not a directory')
            else:
                to_create.add(dst_dir)
        return files, to_create

    @cached_property
    def _src_dst_files(self) -> list[tuple[Path, Path, str, int]]:
        return self._classified_paths[0]

    @cached_property
    def _dirs_to_create(self) -> set[Path]:
        return self._classified_paths[1]

    def copy_files(self):
        total = len(self._src_dst_files)
        copied = 0
        start = monotonic()
        for i, (src_path, dst_path, rel_path, size) in enumerate(self._src_dst_files, 1):
            self.file_num_text.update(f'{i:,d} / {total:,d}')
            self._copy_file(src_path, dst_path, rel_path)
            copied += size
            elapsed = (monotonic() - start) or 1
            self.speed_text.update(readable_bytes(copied / elapsed, rate=True))

    def _copy_file(self, src_path: Path, dst_path: Path, rel_path: str):
        if dst_path.parent in self._dirs_to_create:
            self._dirs_to_create.remove(dst_path.parent)
            dst_path.parent.mkdir(parents=True, exist_ok=True)

        self.progress_text.update(rel_path)
        copyfile(src_path, dst_path)
        copystat(src_path, dst_path)
        self.progress_bar.increment()


def path_repr(path: Path) -> str:
    try:
        rel_path = path.relative_to(Path.home())
    except Exception:  # noqa
        path_str = path.as_posix()
    else:
        path_str = f'~/{rel_path.as_posix()}'

    return (path_str + '/') if path.is_dir() else path_str
