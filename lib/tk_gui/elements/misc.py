"""
Misc GUI elements

:author: Doug Skrypa
"""

from __future__ import annotations

import tkinter.constants as tkc
from tkinter import Frame
from tkinter.ttk import Sizegrip
from typing import TYPE_CHECKING, Union, Any

from ..enums import Anchor
from ..utils import Inheritable
from .element import ElementBase

if TYPE_CHECKING:
    from ..enums import Side
    from ..pseudo_elements import Row
    from ..typing import XY

__all__ = ['SizeGrip', 'Spacer']


class SizeGrip(ElementBase):
    """Visual indicator that resizing is possible, located at the bottom-right corner of a window"""
    widget: Sizegrip

    def __init__(self, side: Union[str, Side] = tkc.BOTTOM, **kwargs):
        super().__init__(side=side, **kwargs)

    def pack_into(self, row: Row):
        style = self.style
        name, ttk_style = style.make_ttk_style('.Sizegrip.TSizegrip')
        ttk_style.configure(name, background=style.base.bg.default)
        self.widget = Sizegrip(row.frame, style=name, takefocus=int(self.allow_focus))
        self.pack_widget(fill=tkc.X, expand=True, anchor=tkc.SE)


class Spacer(ElementBase):
    widget: Frame
    anchor: Anchor = Inheritable('anchor_elements', type=Anchor)

    def __init__(self, size: XY, pad: XY = (0, 0), anchor: Union[str, Anchor] = None, **kwargs):
        super().__init__(pad=pad, **kwargs)
        self.size = size
        self.anchor = anchor

    @property
    def style_config(self) -> dict[str, Any]:
        return {'bg': self.style.base.bg.default, **self._style_config}

    def pack_into(self, row: Row):
        width, height = self.size
        self.widget = Frame(row.frame, width=width, height=height, **self.style_config)
        if anchor := self.anchor.value:
            self.pack_widget(anchor=anchor)
        else:
            self.pack_widget()
