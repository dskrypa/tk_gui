"""
Utilities for loading fonts bundled with this library.

For discovery of fonts that are already installed, or finding fonts with certain properties, see::

    from matplotlib.font_manager import FontProperties, FontManager, fontManager
"""

from __future__ import annotations

import logging
from importlib.resources import files
from os import environ
from pathlib import Path
from shutil import copy

from tk_gui.environment import ON_WINDOWS, ON_LINUX, ON_MAC

__all__ = ['FontLoader']
log = logging.getLogger(__name__)


class FontLoader:
    __slots__ = ('src_paths',)
    src_paths: list[Path]

    def __init__(self):
        # noinspection PyTypeChecker,PyUnresolvedReferences
        self.src_paths = [f for d in files('tk_gui.data.fonts').iterdir() for f in d.iterdir() if f.suffix == '.ttf']

    def load(self):
        if environ.get('TK_GUI_SKIP_CUSTOM_FONTS'):
            log.debug('Skipping custom fonts due to env var')
        elif ON_WINDOWS:
            self._load_windows()
        else:
            self._maybe_copy_fonts(_get_user_fonts_dir())

    def _maybe_copy_fonts(self, fonts_dir: Path):
        call_mkdir = True
        for src_path in self.src_paths:
            dst_path = fonts_dir.joinpath(src_path.name)
            if not dst_path.exists():
                log.debug(f'Copying font={src_path.name!r} into {fonts_dir.as_posix()}')
                if call_mkdir:
                    fonts_dir.mkdir(parents=True, exist_ok=True)
                    call_mkdir = False

                copy(src_path, dst_path)

    def _load_windows(self):
        # This has not been tested yet
        import ctypes
        # LOAD_WITHOUT_WRITING_SYSTEM = 0x10
        for src_path in self.src_paths:
            ctypes.windll.gdi32.AddFontResourceExW(src_path.as_posix(), 0x10, 0)


def _get_user_fonts_dir() -> Path:
    if ON_LINUX:
        # "If $XDG_DATA_HOME is either not set or empty, a default equal to $HOME/.local/share should be used."
        # Source: https://specifications.freedesktop.org/basedir-spec/latest/
        if xdg_home := environ.get('XDG_DATA_HOME'):
            return Path(xdg_home).expanduser().joinpath('fonts')
        return Path.home().joinpath('.local/share/fonts')
    elif ON_MAC:
        # This location was copied from the location that PIL.ImageFont uses - it has not been tested
        return Path.home().joinpath('Library/Fonts')
    else:
        raise RuntimeError('User font directories are not supported on this platform')
