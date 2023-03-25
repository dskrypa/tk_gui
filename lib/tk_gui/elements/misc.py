"""
Misc GUI elements

:author: Doug Skrypa
"""

from __future__ import annotations

import tkinter.constants as tkc
from tkinter import Frame
from tkinter.ttk import Sizegrip
from typing import TYPE_CHECKING, Union, Any

from tk_gui.caching import cached_property
from .element import ElementBase
from .frame import RowFrame
from .text import Text

if TYPE_CHECKING:
    from tk_gui.enums import Side
    from tk_gui.pseudo_elements import Row
    from tk_gui.typing import XY, TkContainer, E, TkSide, TkFill, Bool

__all__ = ['SizeGrip', 'Spacer', 'InfoBar']


class SizeGrip(ElementBase):
    """Visual indicator that resizing is possible, located at the bottom-right corner of a window"""
    widget: Sizegrip

    def __init__(self, side: Union[str, Side] = tkc.BOTTOM, pad: XY = (0, 0), **kwargs):
        super().__init__(side=side, pad=pad, **kwargs)

    def _init_widget(self, tk_container: TkContainer):
        style = self.style
        name, ttk_style = style.make_ttk_style('.Sizegrip.TSizegrip')
        ttk_style.configure(name, background=style.base.bg.default)
        self.widget = Sizegrip(tk_container, style=name, takefocus=int(self.allow_focus))

    def pack_into(self, row: Row):
        self._init_widget(row.frame)
        self.pack_widget(fill=tkc.X, expand=True, anchor=tkc.SE)


class Spacer(ElementBase):
    widget: Frame

    def __init__(self, size: XY, pad: XY = (0, 0), **kwargs):
        super().__init__(pad=pad, **kwargs)
        self.size = size

    @property
    def style_config(self) -> dict[str, Any]:
        return {'bg': self.style.base.bg.default, **self._style_config}

    def _init_widget(self, tk_container: TkContainer):
        width, height = self.size
        self.widget = Frame(tk_container, width=width, height=height, **self.style_config)


class InfoBar(RowFrame):
    """
    An info bar, intended to be at the bottom of a window.
    May be included directly in a layout as a row (i.e., it does not need to be wrapped inside another row).
    """
    element_map: dict[str, Text]

    def __init__(
        self, element_map: dict[str, Text], side: TkSide = 'b', fill: TkFill = 'both', pad: XY = (0, 0), **kwargs
    ):
        super().__init__(side=side, fill=fill, pad=pad, **kwargs)
        self.element_map = element_map

    @classmethod
    def from_dict(cls, data: dict[str, str | tuple[str, XY]], text_pad_width: int = 2, **kwargs) -> InfoBar:
        element_map = {}
        for key, val in data.items():
            if isinstance(val, tuple):
                val, size = val
            else:
                size = None

            element_map[key] = Text(
                val, size=size, use_input_style=True, justify='c', pad=(0, 0), pad_width=text_pad_width
            )

        return cls(element_map, **kwargs)

    @cached_property
    def elements(self) -> tuple[E, ...]:
        return (*self.element_map.values(), SizeGrip(pad=(0, 0)))

    def __getitem__(self, key: str) -> str:
        return self.element_map[key].value

    def __setitem__(self, key: str, value: str):
        self.element_map[key].update(value)

    def update(self, data: dict[str, str], auto_resize: Bool = False):
        element_map = self.element_map
        for key, val in data.items():
            element_map[key].update(val, auto_resize=auto_resize)
