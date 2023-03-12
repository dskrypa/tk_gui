"""
Generic Sized and Box classes defined for common tasks related to positioning, resizing, etc.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from math import floor, ceil
from typing import TYPE_CHECKING, Callable

from .caching import cached_property

if TYPE_CHECKING:
    from .typing import XY, HasSize, OptXYF

__all__ = ['Sized', 'Box']

X = Y = int


class Sized(ABC):
    @property
    @abstractmethod
    def width(self) -> int:
        raise NotImplementedError

    @property
    @abstractmethod
    def height(self) -> int:
        raise NotImplementedError

    @cached_property
    def size(self) -> XY:
        return self.width, self.height

    # region Aspect Ratio

    @cached_property
    def aspect_ratio(self) -> float:
        width, height = self.size
        return width / height

    def new_aspect_ratio_size(self, width: float, height: float) -> XY:
        """Copied logic from :meth:`PIL.Image.Image.thumbnail`"""
        x, y = floor(width), floor(height)
        if x / y >= self.aspect_ratio:
            x = self.new_aspect_ratio_width(y)
        else:
            y = self.new_aspect_ratio_height(x)
        return x, y

    def new_aspect_ratio_width(self, y: int) -> int:
        aspect = self.aspect_ratio
        return _round_aspect(y * aspect, key=lambda n: abs(aspect - n / y))

    def new_aspect_ratio_height(self, x: int) -> int:
        aspect = self.aspect_ratio
        return _round_aspect(x / aspect, key=lambda n: 0 if n == 0 else abs(aspect - x / n))

    # endregion

    # region Resize

    def target_size(self, size: OptXYF, keep_ratio: bool = True) -> XY:
        dst_w, dst_h = size
        if dst_w is dst_h is None:
            return self.size
        elif None not in size:
            if keep_ratio:
                return self.new_aspect_ratio_size(dst_w, dst_h)
            return floor(dst_w), floor(dst_h)
        elif keep_ratio:
            if dst_w is None:
                dst_h = floor(dst_h)
                dst_w = self.new_aspect_ratio_width(dst_h)
            elif dst_h is None:
                dst_w = floor(dst_w)
                dst_h = self.new_aspect_ratio_height(dst_w)
            return dst_w, dst_h
        else:
            src_w, src_h = self.size
            if dst_w is None:
                return src_w, floor(dst_h)
            elif dst_h is None:
                return floor(dst_w), src_h

    def scale_size(self, size: OptXYF, keep_ratio: bool = True) -> XY:
        """
        Scale this object's size to as close to the given target size as possible, optionally respecting aspect ratio.

        The intended use case is for this Sized/Box object to be the bounding box for an image's visible content, to
        scale the outer size so that an image cropped to that content will be as close as possible to the target size.
        """
        dst_w, dst_h = size
        trg_w = dst_w / (self.width / dst_w)
        trg_h = dst_h / (self.height / dst_h)
        return self.target_size((trg_w, trg_h), keep_ratio)

    # endregion


@dataclass
class Box(Sized):
    left: X
    top: Y
    right: X
    bottom: Y

    @classmethod
    def from_pos_and_size(cls, x: X, y: Y, width: int, height: int) -> Box:
        return cls(x, y, x + width, y + height)

    @classmethod
    def from_size_and_pos(cls, width: int, height: int, x: X, y: Y) -> Box:
        return cls(x, y, x + width, y + height)

    def __repr__(self) -> str:
        x, y, width, height = self.left, self.top, self.width, self.height
        return f'<{self.__class__.__name__}({x=}, {y=}, {width=}, {height=})>'

    # region Bounding Area

    def as_bbox(self) -> tuple[X, Y, X, Y]:
        return self.left, self.top, self.right, self.bottom

    def __contains__(self, other: Box) -> bool:
        return self.contains_x(other) and self.contains_y(other)

    def contains_x(self, other: Box) -> bool:
        return self.left <= other.left and self.right >= other.right

    def contains_y(self, other: Box) -> bool:
        return self.top <= other.top and self.bottom >= other.bottom

    # endregion

    # region Size

    @cached_property
    def width(self) -> int:
        return self.right - self.left

    @cached_property
    def height(self) -> int:
        return self.bottom - self.top

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

    @property
    def top_left(self) -> XY:
        return self.min_xy

    @property
    def bottom_right(self) -> XY:
        return self.max_xy

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

    def center(self, obj: XY | HasSize) -> Box:
        try:
            width, height = obj.size
        except AttributeError:  # It was a tuple already
            width, height = obj
        x = self.center_horizontally(width)
        y = self.center_vertically(height)
        return self.from_pos_and_size(x, y, width, height)

    def lazy_center(self, other: Box) -> Box:
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


def _round_aspect(number: float, key: Callable[[float], float]) -> int:
    rounded = min(floor(number), ceil(number), key=key)
    return rounded if rounded > 1 else 1
