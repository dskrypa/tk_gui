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

    @cached_property(block=False)
    def size(self) -> XY:
        return self.width, self.height

    @property
    def size_str(self) -> str:
        return '{}x{}'.format(*self.size)

    # region Aspect Ratio

    @cached_property(block=False)
    def aspect_ratio(self) -> float:
        width, height = self.size
        return width / height

    def new_aspect_ratio_size(self, width: float, height: float) -> XY:
        """Copied logic from :meth:`PIL.Image.Image.thumbnail`"""
        x, y = floor(width), floor(height)
        try:
            if x / y >= self.aspect_ratio:
                x = self.new_aspect_ratio_width(y)
            else:
                y = self.new_aspect_ratio_height(x)
        except ZeroDivisionError:
            pass
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

    def fit_inside_size(self, size: XY, keep_ratio: bool = True) -> XY:
        """Determine a target size that would make this object's size fit inside a box of the given size"""
        out_w, out_h = size
        src_w, src_h = self.size
        w_ok, h_ok = src_w <= out_w, src_h <= out_h
        if w_ok and h_ok:
            return src_w, src_h
        elif w_ok or h_ok:
            return self.target_size((src_w, out_h) if w_ok else (out_w, src_h), keep_ratio)
        else:
            return self.target_size(size, keep_ratio)

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

    def scale_percent(self, percent: float) -> XY:
        src_w, src_h = self.size
        return self.target_size((src_w * percent, src_h * percent))

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

    def contains_x(self, other: Box, inclusive: bool = True) -> bool:
        if inclusive:
            return self.left <= other.left and self.right >= other.right
        return self.left < other.left and self.right > other.right

    def contains_y(self, other: Box, inclusive: bool = True) -> bool:
        if inclusive:
            return self.top <= other.top and self.bottom >= other.bottom
        return self.top < other.top and self.bottom > other.bottom

    def fits_inside(self, other: XY | HasSize, inclusive: bool = True) -> bool:
        try:
            width, height = other.size
        except AttributeError:
            width, height = other
        return self.fits_inside_x(width, inclusive) and self.fits_inside_y(height, inclusive)

    def fits_inside_x(self, width: X, inclusive: bool = True) -> bool:
        return (width >= self.width) if inclusive else (width > self.width)

    def fits_inside_y(self, height: Y, inclusive: bool = True) -> bool:
        return (height >= self.height) if inclusive else (height > self.height)

    def fits_around(self, other: XY | HasSize, inclusive: bool = True) -> bool:
        try:
            width, height = other.size
        except AttributeError:
            width, height = other
        return self.fits_around_x(width, inclusive) and self.fits_around_y(height, inclusive)

    def fits_around_x(self, width: X, inclusive: bool = True) -> bool:
        return (width <= self.width) if inclusive else (width < self.width)

    def fits_around_y(self, height: Y, inclusive: bool = True) -> bool:
        return (height <= self.height) if inclusive else (height < self.height)

    # endregion

    # region Size

    @cached_property(block=False)
    def width(self) -> int:
        return self.right - self.left

    @cached_property(block=False)
    def height(self) -> int:
        return self.bottom - self.top

    # endregion

    # region Position / Coordinates

    @property
    def position(self) -> XY:
        """(X, Y) coordinates of the top-left corner of this Rectangle."""
        return self.min_xy

    @cached_property(block=False)
    def min_xy(self) -> XY:
        return self.left, self.top

    @cached_property(block=False)
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

    @property
    def center_pos(self) -> XY:
        x, y = self.min_xy
        x += self.width // 2
        y += self.height // 2
        return x, y

    # endregion

    # region Resize & Move

    def with_size_offset(self, offset: XY | int, anchor_center: bool = False) -> Box:
        try:
            x_off, y_off = offset
        except TypeError:
            x_off = y_off = offset

        width, height = self.size
        x, y = self.min_xy
        if not anchor_center:
            return self.from_size_and_pos(width + x_off, height + y_off, x, y)

        dx = (x_off if x_off > 0 else -x_off) // 2
        dy = (y_off if y_off > 0 else -y_off) // 2
        return self.from_size_and_pos(width + x_off, height + y_off, x - dx, y - dy)

    def with_pos(self, x: X, y: Y) -> Box:
        return self.from_pos_and_size(x, y, *self.size)

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
        """Returns a Box that represents the position that would place the given object at the center of this box."""
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
