"""
Tkinter GUI element utils

:author: Doug Skrypa
"""

from __future__ import annotations

import logging
from os import startfile
from pathlib import Path
from subprocess import Popen
from tkinter import TclError, Entry, Text, BaseWidget
from typing import TYPE_CHECKING, Optional, Union, Iterator

from tk_gui.utils import ON_LINUX, ON_WINDOWS

if TYPE_CHECKING:
    from tk_gui.typing import XY

__all__ = ['normalize_underline', 'get_selection_pos', 'find_descendants', 'get_top_level', 'launch', 'explore']
log = logging.getLogger(__name__)

OPEN_CMD = 'xdg-open' if ON_LINUX else 'open'  # open is for OSX


def normalize_underline(underline: Union[str, int], label: str) -> Optional[int]:
    try:
        return int(underline)
    except (TypeError, ValueError):
        pass
    try:
        return label.index(underline)
    except (ValueError, TypeError):
        return None


def get_selection_pos(
    widget: Union[Entry, Text], raw: bool = False
) -> Union[XY, tuple[XY, XY], tuple[None, None], tuple[str, str]]:
    try:
        first, last = widget.index('sel.first'), widget.index('sel.last')
    except (AttributeError, TclError):
        return None, None
    if raw:
        return first, last
    try:
        return int(first), int(last)
    except ValueError:
        pass
    first_line, first_index = map(int, first.split('.', 1))
    last_line, last_index = map(int, last.split('.', 1))
    return (first_line, first_index), (last_line, last_index)


def find_descendants(widget: BaseWidget) -> Iterator[BaseWidget]:
    for child in widget.children.values():
        yield child
        yield from find_descendants(child)


def get_top_level(widget: BaseWidget) -> BaseWidget:
    name = widget._w  # noqa
    return widget.nametowidget('.!'.join(name.split('.!')[:2]))


def launch(path: Union[Path, str]):
    """Open the given path with its associated application"""
    path = Path(path)
    if ON_WINDOWS:
        startfile(str(path))
    else:
        Popen([OPEN_CMD, path.as_posix()])


def explore(path: Union[Path, str]):
    """Open the given path in the default file manager"""
    path = Path(path)
    if ON_WINDOWS:
        cmd = list(filter(None, ('explorer', '/select,' if path.is_file() else None, str(path))))
    else:
        cmd = [OPEN_CMD, (path if path.is_dir() else path.parent).as_posix()]

    log.debug(f'Running: {cmd}')
    Popen(cmd)
