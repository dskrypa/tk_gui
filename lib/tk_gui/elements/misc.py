"""
Misc GUI elements

:author: Doug Skrypa
"""

from __future__ import annotations

import tkinter.constants as tkc
from tkinter import Frame
from tkinter.ttk import Sizegrip
from typing import TYPE_CHECKING, Union, Any

from .element import ElementBase

if TYPE_CHECKING:
    from ..enums import Side
    from ..pseudo_elements import Row
    from ..typing import XY, TkContainer

__all__ = ['SizeGrip', 'Spacer']


class SizeGrip(ElementBase):
    """Visual indicator that resizing is possible, located at the bottom-right corner of a window"""
    widget: Sizegrip

    def __init__(self, side: Union[str, Side] = tkc.BOTTOM, **kwargs):
        super().__init__(side=side, **kwargs)

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
