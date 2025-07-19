from __future__ import annotations

from dataclasses import dataclass
from math import floor
from typing import TYPE_CHECKING

from ..caching import cached_property
from .aspect_ratio import AspectRatio
from .base import Position, Size
from .sized import Resizable

if TYPE_CHECKING:
    from tk_gui.typing import HasSize
    from .typing import X, Y, XY

__all__ = ['BBox']


@dataclass
class BBox(Resizable):
    left: X
    top: Y
    right: X
    bottom: Y

    @classmethod
    def from_pos_and_size(cls, x: X, y: Y, width: int, height: int) -> BBox:
        return cls(x, y, x + width, y + height)

    @classmethod
    def from_size_and_pos(cls, width: int, height: int, x: X = 0, y: Y = 0) -> BBox:
        return cls(x, y, x + width, y + height)

    @classmethod
    def from_sized(cls, sized: HasSize) -> BBox:
        return cls.from_size_and_pos(*sized.size)

    def __repr__(self) -> str:
        x, y, width, height = self.left, self.top, self.width, self.height
        return f'<{self.__class__.__name__}({x=}, {y=}, {width=}, {height=})>'

    # region Bounding Area

    def as_bbox(self) -> tuple[X, Y, X, Y]:
        return self.left, self.top, self.right, self.bottom

    def __contains__(self, other: BBox) -> bool:
        return self.contains_x(other) and self.contains_y(other)

    def contains_x(self, other: BBox, inclusive: bool = True) -> bool:
        if inclusive:
            return self.left <= other.left and self.right >= other.right
        return self.left < other.left and self.right > other.right

    def contains_y(self, other: BBox, inclusive: bool = True) -> bool:
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
    def size(self) -> Size:
        return Size(self.right - self.left, self.bottom - self.top)

    # endregion

    # region Position / Coordinates

    @property
    def position(self) -> Position:
        """(X, Y) coordinates of the top-left corner of this Rectangle."""
        return self.min_xy

    @cached_property(block=False)
    def min_xy(self) -> Position:
        return Position(self.left, self.top)

    @cached_property(block=False)
    def max_xy(self) -> Position:
        return Position(self.right, self.bottom)

    @property
    def min_max_coordinates(self) -> tuple[Position, Position]:
        return self.min_xy, self.max_xy

    @property
    def top_left(self) -> Position:
        return self.min_xy

    @property
    def bottom_right(self) -> Position:
        return self.max_xy

    @property
    def center_pos(self) -> Position:
        x, y = self.min_xy
        x += self.width // 2
        y += self.height // 2
        return Position(x, y)

    # endregion

    # region Resize & Move

    def with_size_offset(self, offset: XY | int, anchor_center: bool = False) -> BBox:
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

    def with_pos(self, x: X, y: Y) -> BBox:
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

    def center(self, obj: XY | HasSize) -> BBox:
        """Returns a BBox that represents the position that would place the given object at the center of this box."""
        try:
            width, height = obj.size
        except AttributeError:  # It was a tuple already
            width, height = obj
        x = self.center_horizontally(width)
        y = self.center_vertically(height)
        return self.from_pos_and_size(x, y, width, height)

    def lazy_center(self, other: BBox) -> BBox:
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

    # region Cropping

    def centered_crop_to_ratio(self, x: int | float, y: int | float) -> BBox:
        if self.left != 0 or self.top != 0:
            raise ValueError('Crop to ratio is currently only supported for boxes without a top/left offset')
        try:
            return self._centered_crop_to_ratio(x, y)
        except ZeroDivisionError as e:
            raise ValueError(f'Unable to crop {self} to aspect ratio {x}:{y}') from e

    def _centered_crop_to_ratio(self, x: int | float, y: int | float) -> BBox:
        width, height = self.size
        ratio = AspectRatio(x, y)
        if ratio == self.aspect_ratio:
            return self
        elif ratio > 1 or (ratio == 1 and self.aspect_ratio < 1):
            # Target state is a horizontal box, so trim the height
            new_height = ratio.new_height(width)  # noqa
            top = floor((height - new_height) / 2)
            if top < 0:
                raise ValueError(f'Unable to crop {self} to aspect ratio {x}:{y} while maintaining the current width')
            return BBox(0, top, width, top + new_height)
        else:
            # Target state is a vertical box, so trim the width
            new_width = ratio.new_width(height)
            left = floor((width - new_width) / 2)
            if left < 0:
                raise ValueError(f'Unable to crop {self} to aspect ratio {x}:{y} while maintaining the current height')
            return BBox(left, 0, left + new_width, height)

    # endregion
