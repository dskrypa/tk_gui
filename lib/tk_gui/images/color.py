"""
Tkinter GUI popup: Style

:author: Doug Skrypa
"""

from __future__ import annotations

from colorsys import rgb_to_hls
from random import randrange
from typing import TYPE_CHECKING, Collection

from PIL.ImageColor import getrgb

if TYPE_CHECKING:
    from tk_gui.typing import RGB, RGBA, Color

__all__ = [
    'color_to_rgb', 'get_hue', 'get_lightness', 'get_saturation', 'pick_fg', 'find_unused_color', 'color_to_rgb_str'
]


def color_to_rgb(color: Color) -> RGB | RGBA:
    if isinstance(color, tuple):
        return color
    try:
        return getrgb(color)
    except ValueError:
        if isinstance(color, str) and len(color) in (3, 4, 6, 8):
            return getrgb(f'#{color}')
        raise


def color_to_rgb_str(color: Color) -> str:
    if isinstance(color, str) and color.startswith('#') and len(color) == 7:
        return color
    r, g, b, *a = color_to_rgb(color)
    return f'#{r:2x}{g:2x}{b:2x}'


def pick_fg(bg: Color | None) -> str | None:
    if not bg:
        return None
    try:
        lightness = get_lightness(bg)
    except ValueError:  # Not in rgb format
        return '#000000'

    if lightness < 0.5:
        return '#ffffff'
    else:
        return '#000000'


def get_hue(color: Color) -> int:
    r, g, b, *a = color_to_rgb(color)
    value = rgb_to_hls(r / 255, g / 255, b / 255)[0]
    return round(value * 360)


def get_lightness(color: Color) -> float:
    r, g, b, *a = color_to_rgb(color)
    return rgb_to_hls(r / 255, g / 255, b / 255)[1]


def get_saturation(color: Color) -> float:
    r, g, b, *a = color_to_rgb(color)
    return rgb_to_hls(r / 255, g / 255, b / 255)[2]


def find_unused_color(used: Collection[RGB]) -> RGB:
    used = set(used)
    if len(used) > 256 ** 3:
        raise ValueError(f'Too many colors ({len(used)}) - impossible to generate different unique random color')
    while True:
        color = (randrange(256), randrange(256), randrange(256))
        if color not in used:
            return color
