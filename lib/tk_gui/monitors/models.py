"""
Models representing Monitors and the Rectangle that represents its size/area/coordinates.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from tk_gui.caching import cached_property

if TYPE_CHECKING:
    from tk_gui.typing import XY, HasSize

__all__ = ['Monitor', 'Rectangle']

X = Y = int


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
        return self.full_area.width

    @property
    def height(self) -> int:
        return self.full_area.height

    @property
    def size(self) -> XY:
        return self.full_area.size

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


@dataclass(frozen=True)
class Rectangle:
    left: int
    top: int
    right: int
    bottom: int

    @classmethod
    def from_pos_and_size(cls, x: X, y: Y, width: int, height: int) -> Rectangle:
        return cls(x, y, x + width, y + height)

    @cached_property
    def is_primary(self) -> bool:
        return self.left == self.top == 0

    def as_bbox(self) -> tuple[X, Y, X, Y]:
        return self.left, self.top, self.right, self.bottom

    def __repr__(self) -> str:
        x, y, width, height = self.left, self.top, self.width, self.height
        return f'<{self.__class__.__name__}({x=}, {y=}, {width=}, {height=})>'

    def __contains__(self, other: Rectangle) -> bool:
        return self.contains_x(other) and self.contains_y(other)

    def contains_x(self, other: Rectangle) -> bool:
        return self.left <= other.left and self.right >= other.right

    def contains_y(self, other: Rectangle) -> bool:
        return self.top <= other.top and self.bottom >= other.bottom

    # region Size

    @cached_property
    def width(self) -> int:
        return self.right - self.left

    @cached_property
    def height(self) -> int:
        return self.bottom - self.top

    @cached_property
    def size(self) -> XY:
        return self.width, self.height

    # endregion

    # region Position / Coordinates

    @property
    def position(self) -> XY:
        """(X, Y) coordinates of the top-left corner of this Rectangle."""
        return self.min_xy

    @cached_property
    def min_xy(self) -> XY:
        return self.left, self.top

    @cached_property
    def max_xy(self) -> XY:
        return self.right, self.bottom

    @property
    def min_max_coordinates(self) -> tuple[XY, XY]:
        return self.min_xy, self.max_xy

    # endregion

    # region Centering

    def center_horizontally(self, width: int) -> X:
        return self.left + (self.width - width) // 2

    def center_vertically(self, height: int) -> Y:
        return self.top + (self.height - height) // 2

    def center_coordinates(self, obj: XY | HasSize) -> XY:
        try:
            width, height = obj.size
        except AttributeError:  # It was a tuple already
            width, height = obj
        x = self.center_horizontally(width)
        y = self.center_vertically(height)
        return x, y

    def center(self, obj: XY | HasSize) -> Rectangle:
        try:
            width, height = obj.size
        except AttributeError:  # It was a tuple already
            width, height = obj
        x = self.center_horizontally(width)
        y = self.center_vertically(height)
        return self.from_pos_and_size(x, y, width, height)

    def lazy_center(self, other: Rectangle) -> Rectangle:
        in_x, in_y = self.contains_x(other), self.contains_y(other)
        if in_x and in_y:
            return other
        x, y = other.position
        width, height = other.size
        if not in_x:
            # log.debug(f'Centering within {self} horizontally: {other}')
            x = self.center_horizontally(width)
        if not in_y:
            # log.debug(f'Centering within {self} vertically: {other}')
            y = self.center_vertically(height)
        return self.from_pos_and_size(x, y, width, height)

    # endregion
