"""
Utilities for working with PIL images.

:author: Doug Skrypa
"""

from __future__ import annotations

from importlib.resources import path as get_data_path
from math import floor, ceil
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from pathlib import Path
    from ..typing import XY

__all__ = ['icon_path', 'calculate_resize']


with get_data_path('tk_gui', 'icons') as _icon_path:
    ICONS_DIR = _icon_path


def icon_path(rel_path: str) -> Path:
    return ICONS_DIR.joinpath(rel_path)


def calculate_resize(src_w: float, src_h: float, new_w: float, new_h: float) -> XY:
    """Copied logic from :meth:`PIL.Image.Image.thumbnail`"""
    x, y = floor(new_w), floor(new_h)
    aspect = src_w / src_h
    if x / y >= aspect:
        x = _round_aspect(y * aspect, key=lambda n: abs(aspect - n / y))
    else:
        y = _round_aspect(x / aspect, key=lambda n: 0 if n == 0 else abs(aspect - x / n))
    return x, y


def _round_aspect(number: float, key: Callable[[float], float]) -> int:
    rounded = min(floor(number), ceil(number), key=key)
    return rounded if rounded > 1 else 1
