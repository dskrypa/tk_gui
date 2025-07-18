from __future__ import annotations

from typing import TYPE_CHECKING

from .base import Position
from .padding import Padding
from .sized import Sized

if TYPE_CHECKING:
    from .typing import X, Y

__all__ = []


class Block(Sized):
    pos: Position
    pad: Padding
    _width: X
    _height: Y

    def __init__(self, width: X, height: Y, *, pos: Position = Position(0, 0), pad: Padding = Padding(0)):
        self.pos = pos
        self.pad = pad
        self._width = width
        self._height = height

    @property
    def width(self) -> X:
        return self._width + self.pad.left + self.pad.right

    @property
    def height(self) -> Y:
        return self._height + self.pad.top + self.pad.bottom
