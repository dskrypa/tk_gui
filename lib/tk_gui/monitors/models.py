"""
Models representing Monitors and the Rectangle that represents its size/area/coordinates.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from tk_gui.caching import cached_property
from tk_gui.geometry import BBox

if TYPE_CHECKING:
    from tk_gui.geometry.typing import XY
    from tk_gui.typing import HasSize

__all__ = ['Monitor', 'Rectangle']


@dataclass(frozen=True)
class Monitor:
    x: int
    y: int
    full_area: Rectangle
    _work_area: Optional[Rectangle] = None
    name: Optional[str] = None
    is_primary: Optional[bool] = None

    def __repr__(self) -> str:
        width, height = self.full_area.size
        x, y, name, is_primary = self.x, self.y, self.name, self.is_primary
        return f'{self.__class__.__name__}({x=}, {y=}, {width=}, {height=}, {name=}, {is_primary=})'

    def __lt__(self, other: Monitor) -> bool:
        if self.is_primary:
            return True
        if self.y > other.y:
            return False
        return self.x < other.x

    @property
    def position(self) -> XY:
        return self.x, self.y

    # region Size

    @property
    def width(self) -> int:
        return self.work_area.width

    @property
    def height(self) -> int:
        return self.work_area.height

    @property
    def size(self) -> XY:
        return self.work_area.size

    # endregion

    @cached_property
    def work_area(self) -> Rectangle:
        if work_area := self._work_area:
            return work_area
        return self.full_area

    @property
    def min_max_coordinates(self) -> tuple[XY, XY]:
        return self.work_area.min_max_coordinates

    def center_coordinates(self, size: XY | HasSize) -> XY:
        return self.work_area.center_coordinates(size)


class Rectangle(BBox):
    @cached_property
    def is_primary(self) -> bool:
        return self.left == self.top == 0
