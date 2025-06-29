"""
Tkinter GUI popups: File-related prompts

:author: Doug Skrypa
"""

from __future__ import annotations

import logging
import os
from functools import cached_property
from pathlib import Path
from shutil import copyfile, copystat
from time import monotonic
from typing import TYPE_CHECKING, Union, Collection, Mapping, Iterator

from ..elements import Text, ProgressBar
from ..utils import readable_bytes
from .base import Popup

if TYPE_CHECKING:
    from ..typing import Layout

__all__ = ['CopyFilesPopup']
log = logging.getLogger(__name__)

SrcDstPaths = Union[Collection[tuple[Path, Path]], Mapping[Path, Path]]


# region Tree


class CopyNode:
    __slots__ = ('parent', 'root', 'src', 'dst', '_dst_exists')

    def __init__(self, src: Path, dst: Path, parent: CopyDir | None = None):
        self.parent = parent
        self.root = parent or self
        self.src = src
        self.dst = dst
        self._dst_exists = None

    def rel_path(self) -> str:
        if self.parent:
            if base := self.parent.rel_path():
                return f'{base}/{self.src.name}'
            return self.src.name
        return ''

    def _check_dst_exists(self) -> bool:
        return self.dst.exists()

    @property
    def dst_exists(self) -> bool:
        if self._dst_exists is None:
            if self.parent and not self.parent.dst_exists:
                self._dst_exists = False
            else:
                self._dst_exists = self._check_dst_exists()
        return self._dst_exists

    @dst_exists.setter
    def dst_exists(self, value: bool):
        self._dst_exists = value
        if value and self.parent and not self.parent._dst_exists:
            self.parent.dst_exists = value


class CopyDir(CopyNode):
    __slots__ = ('dirs', 'files')

    def __init__(self, src: Path, dst: Path, parent: CopyDir | None = None):
        super().__init__(src, dst, parent)
        self.dirs: list[CopyDir] = []
        self.files: list[CopyFile] = []

    @classmethod
    def build_tree(cls, src: Path, dst: Path, parent: CopyDir | None = None) -> CopyDir:
        node = cls(src, dst, parent)
        with os.scandir(src) as scanner:
            for entry in sorted(scanner, key=lambda de: de.name):
                if entry.is_dir():
                    node.dirs.append(cls.build_tree(src.joinpath(entry.name), dst.joinpath(entry.name), node))
                else:
                    node.files.append(
                        CopyFile(src.joinpath(entry.name), dst.joinpath(entry.name), entry.stat().st_size, node)
                    )

        return node

    def _check_dst_exists(self) -> bool:
        if not self.dst.exists():
            return False
        elif not self.dst.is_dir():
            raise FileExistsError(f'dst_dir={path_repr(self.dst)} already exists, but it is not a directory')
        return True

    def any_dst_files_exist(self) -> bool:
        if not self.dst_exists:
            return False
        elif any(f.dst_exists for f in self.files):
            return True
        return any(d.any_dst_files_exist() for d in self.dirs)

    def any_dst_exists(self, include_self: bool = True) -> bool:
        if not self.dst_exists:
            return False
        elif include_self:
            return True
        else:
            return any(f.dst_exists for f in self.files) or any(d.dst_exists for d in self.dirs)

    def get_existing_files(self) -> list[CopyFile]:
        return list(self._iter_existing_files())

    def _iter_existing_files(self) -> Iterator[CopyFile]:
        if not self.dst_exists:
            return
        for file_node in self.files:
            if file_node.dst_exists:
                yield file_node
        for dir_node in self.dirs:
            yield from dir_node._iter_existing_files()

    def iter_files(self) -> Iterator[CopyFile]:
        yield from self.files
        for dir_node in self.dirs:
            yield from dir_node.iter_files()

    def maybe_mkdir_dst(self):
        if self.dst_exists:
            return
        self.dst.mkdir(parents=True, exist_ok=True)
        self.dst_exists = True


class CopyFile(CopyNode):
    __slots__ = ('size',)

    def __init__(self, src: Path, dst: Path, size: int, parent: CopyDir | None = None):
        super().__init__(src, dst, parent)
        self.size = size

    def copy_to_dst(self):
        copyfile(self.src, self.dst)
        copystat(self.src, self.dst)


# endregion


class CopyFilesPopup(Popup):
    progress_bar: ProgressBar
    progress_text: Text
    file_num_text: Text
    speed_text: Text
    _src_root = None

    def __init__(self, root: CopyDir, **kwargs):
        kwargs['bind_esc'] = False
        kwargs.setdefault('title', 'Copying Files...')
        super().__init__(**kwargs)
        self.root = root

    @classmethod
    def copy_dir(cls, src_dir: Path, dst_dir: Path, **kwargs) -> CopyFilesPopup:
        node = CopyDir.build_tree(src_dir.resolve(), dst_dir)
        if existing := node.get_existing_files():
            msg = f'{len(existing)} path(s) already exist: ' + ', '.join(repr(f.rel_path()) for f in existing)
            raise FileExistsError(f'Unable to copy src={src_dir.as_posix()} to dst={dst_dir.as_posix()} - {msg}')
        return cls(node, **kwargs)

    @cached_property
    def file_nodes(self) -> list[CopyFile]:
        return list(self.root.iter_files())

    def get_pre_window_layout(self) -> Layout:
        self.progress_bar = ProgressBar(len(self.file_nodes), size=(500, 30), side='t')
        max_path_len = max(len(file.rel_path()) for file in self.file_nodes)
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

    def copy_files(self):
        total = len(self.file_nodes)
        copied = 0
        start = monotonic()
        for i, file_node in enumerate(self.file_nodes, 1):
            self.file_num_text.update(f'{i:,d} / {total:,d}')
            file_node.parent.maybe_mkdir_dst()
            self.progress_text.update(file_node.rel_path())
            file_node.copy_to_dst()
            self.progress_bar.increment()
            copied += file_node.size
            elapsed = (monotonic() - start) or 1
            self.speed_text.update(readable_bytes(copied / elapsed, rate=True))


def path_repr(path: Path) -> str:
    try:
        rel_path = path.relative_to(Path.home())
    except Exception:  # noqa
        path_str = path.as_posix()
    else:
        path_str = f'~/{rel_path.as_posix()}'

    return (path_str + '/') if path.is_dir() else path_str
