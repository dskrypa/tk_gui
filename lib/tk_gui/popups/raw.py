"""
Tkinter GUI low level popups, including file prompts

:author: Doug Skrypa
"""

from __future__ import annotations

import logging
from abc import ABC
from pathlib import Path
from tkinter import filedialog, colorchooser
from typing import TYPE_CHECKING, Union, Collection, Optional

from .base import BasePopup
from ..utils import ON_MAC

if TYPE_CHECKING:
    from tk_gui.window import Window

__all__ = ['PickFolder', 'PickFile', 'PickFiles', 'SaveAs', 'PickColor']
log = logging.getLogger(__name__)

PathLike = Union[Path, str]
FileTypes = Collection[tuple[str, str]]

ALL_FILES = (('ALL Files', '*.* *'),)


class RawPopup(BasePopup, ABC):
    __slots__ = ()

    def _get_root(self):
        if parent := self.parent:
            return parent.root
        else:
            return None


# region File Prompts


class FilePopup(RawPopup, ABC):
    __slots__ = ('initial_dir',)

    def __init__(self, initial_dir: PathLike = None, title: str = None, parent: Window = None):
        super().__init__(title=title, parent=parent)
        self.initial_dir = initial_dir


class PickFolder(FilePopup):
    __slots__ = ()

    def _run(self) -> Optional[Path]:
        kwargs = {} if ON_MAC else {'parent': self._get_root()}
        if name := filedialog.askdirectory(initialdir=self.initial_dir, title=self.title, **kwargs):
            return Path(name)
        return None


class PickFile(FilePopup):
    __slots__ = ('file_types',)

    def __init__(
        self, initial_dir: PathLike = None, file_types: FileTypes = None, title: str = None, parent: Window = None
    ):
        super().__init__(initial_dir, title=title, parent=parent)
        self.file_types = file_types

    def _dialog_kwargs(self):
        if ON_MAC:
            return {}
        return {'parent': self._get_root(), 'filetypes': self.file_types or ALL_FILES}

    def _run(self) -> Optional[Path]:
        if name := filedialog.askopenfilename(initialdir=self.initial_dir, title=self.title, **self._dialog_kwargs()):
            return Path(name)
        return None


class PickFiles(PickFile):
    __slots__ = ()

    def _run(self) -> list[Path]:
        if names := filedialog.askopenfilenames(initialdir=self.initial_dir, title=self.title, **self._dialog_kwargs()):
            return [Path(name) for name in names]
        return []


class SaveAs(PickFile):
    __slots__ = ('default_ext',)

    def __init__(
        self,
        initial_dir: PathLike = None,
        file_types: FileTypes = None,
        default_ext: str = None,
        title: str = None,
        parent: Window = None,
    ):
        super().__init__(initial_dir, file_types, title=title, parent=parent)
        self.default_ext = default_ext

    def _run(self) -> Optional[Path]:
        kwargs = self._dialog_kwargs()
        kwargs['defaultextension'] = self.default_ext
        if name := filedialog.asksaveasfilename(initialdir=self.initial_dir, title=self.title, **kwargs):
            return Path(name)
        return None


# endregion


class PickColor(RawPopup):
    __slots__ = ('initial_color',)

    def __init__(self, initial_color: str = None, title: str = None, parent: Window = None):
        super().__init__(title=title, parent=parent)
        self.initial_color = initial_color

    def _run(self) -> Optional[tuple[tuple[int, int, int], str]]:
        if color := colorchooser.askcolor(self.initial_color, title=self.title, parent=self._get_root()):
            return color  # noqa  # hex RGB
        return None
