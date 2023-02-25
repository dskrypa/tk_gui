"""
Tkinter GUI low level popups, including file prompts

:author: Doug Skrypa
"""

from __future__ import annotations

from abc import ABC
from pathlib import Path
from tkinter.colorchooser import askcolor
from tkinter.filedialog import Open, Directory, SaveAs as TkSaveAs
from typing import TYPE_CHECKING, Collection, Optional

from ..utils import ON_MAC
from .base import BasePopup

if TYPE_CHECKING:
    from tk_gui.typing import RGB, PathLike

__all__ = [
    'PickFolder', 'PickFile', 'PickFiles', 'SaveAs', 'PickColor',
    'pick_folder_popup', 'pick_file_popup', 'pick_files_popup', 'save_as_popup', 'pick_color_popup',
]

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

    def __init__(self, initial_dir: PathLike = None, title: str = None, **kwargs):
        super().__init__(title=title, **kwargs)
        self.initial_dir = initial_dir


class PickFolder(FilePopup):
    __slots__ = ()

    def _run(self) -> Optional[Path]:
        kwargs = {} if ON_MAC else {'parent': self._get_root()}
        if name := Directory(initialdir=self.initial_dir, title=self.title, **kwargs).show():
            return Path(name)
        return None


class PickFile(FilePopup):
    __slots__ = ('file_types',)

    def __init__(self, initial_dir: PathLike = None, file_types: FileTypes = None, title: str = None, **kwargs):
        super().__init__(initial_dir, title=title, **kwargs)
        self.file_types = file_types

    def _dialog_kwargs(self):
        if ON_MAC:
            return {}
        return {'parent': self._get_root(), 'filetypes': self.file_types or ALL_FILES}

    def _run(self) -> Optional[Path]:
        if name := Open(initialdir=self.initial_dir, title=self.title, **self._dialog_kwargs()).show():
            return Path(name)
        return None


class PickFiles(PickFile):
    __slots__ = ()

    def _run(self) -> list[Path]:
        if names := Open(initialdir=self.initial_dir, title=self.title, multiple=1, **self._dialog_kwargs()).show():
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
        **kwargs,
    ):
        super().__init__(initial_dir, file_types, title=title, **kwargs)
        self.default_ext = default_ext

    def _run(self) -> Optional[Path]:
        kwargs = self._dialog_kwargs()
        kwargs['defaultextension'] = self.default_ext
        if name := TkSaveAs(initialdir=self.initial_dir, title=self.title, **kwargs).show():
            return Path(name)
        return None


def pick_folder_popup(initial_dir: PathLike = None, title: str = None, **kwargs) -> Optional[Path]:
    return PickFolder(initial_dir, title, **kwargs).run()


def pick_file_popup(
    initial_dir: PathLike = None, file_types: FileTypes = None, title: str = None, **kwargs
) -> Optional[Path]:
    return PickFile(initial_dir, file_types, title, **kwargs).run()


def pick_files_popup(
    initial_dir: PathLike = None, file_types: FileTypes = None, title: str = None, **kwargs
) -> list[Path]:
    return PickFiles(initial_dir, file_types, title, **kwargs).run()


def save_as_popup(
    initial_dir: PathLike = None,
    file_types: FileTypes = None,
    default_ext: str = None,
    title: str = None,
    **kwargs,
) -> Optional[Path]:
    return SaveAs(initial_dir, file_types, default_ext, title, **kwargs).run()


# endregion


class PickColor(RawPopup):
    __slots__ = ('initial_color',)

    def __init__(self, initial_color: str = None, title: str = None, **kwargs):
        super().__init__(title=title, **kwargs)
        self.initial_color = initial_color

    def _run(self) -> Optional[tuple[RGB, str]]:
        if color := askcolor(self.initial_color, title=self.title, parent=self._get_root()):
            return color  # noqa  # hex RGB
        return None


def pick_color_popup(initial_color: str = None, title: str = None, **kwargs) -> Optional[tuple[RGB, str]]:
    return PickColor(initial_color, title, **kwargs).run()
