"""
Tkinter GUI element utils

:author: Doug Skrypa
"""

from __future__ import annotations

import logging
try:
    from os import startfile
except ImportError:  # Non-Windows OS
    startfile = None
from pathlib import Path
from subprocess import Popen
from typing import Optional, Union

from tk_gui.environment import ON_LINUX, ON_WINDOWS

__all__ = ['normalize_underline', 'launch', 'explore']
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
