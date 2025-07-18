from __future__ import annotations

from abc import ABC, abstractmethod
from math import floor
from typing import TYPE_CHECKING

from ..caching import cached_property
from .aspect_ratio import AspectRatio
from .base import Size

if TYPE_CHECKING:
    from .typing import XY, OptXYF

__all__ = ['Sized', 'Resizable']


class Sized(ABC):
    __slots__ = ()

    @property
    @abstractmethod
    def width(self) -> int:
        raise NotImplementedError

    @property
    @abstractmethod
    def height(self) -> int:
        raise NotImplementedError

    @property
    def size(self) -> Size:
        return Size(self.width, self.height)

    @property
    def size_str(self) -> str:
        return '{} x {}'.format(*self.size)

    @property
    def area(self) -> int:
        return self.width * self.height

    @property
    def aspect_ratio(self) -> AspectRatio:
        return AspectRatio(self.width, self.height)


class Resizable(Sized, ABC):
    @cached_property(block=False)
    def size(self) -> Size:
        return Size(self.width, self.height)

    @cached_property(block=False)
    def aspect_ratio(self) -> AspectRatio:
        return AspectRatio(self.width, self.height)

    # region Aspect Ratio

    def new_aspect_ratio_size(self, width: float, height: float) -> Size:
        """Copied logic from :meth:`PIL.Image.Image.thumbnail`"""
        x, y = floor(width), floor(height)
        # A "vertical" rectangle has width < height; ar < 1
        # A "horizontal" rectangle has width > height; ar > 1
        try:
            if x / y >= self.aspect_ratio:
                # This rectangle is vertical and the specified dimensions would be for a horizontal rectangle or a
                # vertical rectangle with a relatively shorter height than this one.  To fit within that size, the
                # provided height is used, but a new width is calculated such that this rectangle's aspect ratio is
                # maintained.  The new width will be less than the provided width.
                x = self.aspect_ratio.new_width(y)
            else:
                # This rectangle is horizontal and the specified dimensions would be for a vertical rectangle or a
                # horizontal rectangle with a relatively shorter width than this one.  To fit within that size, the
                # provided width is used, but a new height is calculated such that this rectangle's aspect ratio is
                # maintained.  The new height will be less than the provided height.
                y = self.aspect_ratio.new_height(x)
        except ZeroDivisionError:
            pass
        return Size(x, y)

    # endregion

    # region Resize

    def target_size(self, size: OptXYF, keep_ratio: bool = True) -> Size:
        match size:
            case (None, None):
                return self.size
            case (None, dst_h):
                dst_h = floor(dst_h)
                return Size(self.aspect_ratio.new_width(dst_h) if keep_ratio else self.width, dst_h)
            case (dst_w, None):
                dst_w = floor(dst_w)
                return Size(dst_w, self.aspect_ratio.new_height(dst_w) if keep_ratio else self.height)
            case (dst_w, dst_h):
                if keep_ratio:
                    return self.new_aspect_ratio_size(dst_w, dst_h)
                return Size(floor(dst_w), floor(dst_h))
            case _:
                raise TypeError('Unexpected size - expected a 2-tuple of int/float/None values')

    def fit_inside_size(self, size: XY, keep_ratio: bool = True) -> Size:
        """Determine a target size that would make this object's size fit inside a box of the given size"""
        out_w, out_h = size
        src_w, src_h = self.size
        w_ok, h_ok = src_w <= out_w, src_h <= out_h
        if w_ok and h_ok:
            return Size(src_w, src_h)
        elif w_ok or h_ok:
            return self.target_size((src_w, out_h) if w_ok else (out_w, src_h), keep_ratio)
        else:
            return self.target_size(size, keep_ratio)

    def fill_size(self, size: XY, keep_ratio: bool = True) -> Size:
        out_w, out_h = size
        src_w, src_h = self.size
        if src_w >= out_w or src_h >= out_h:
            return self.fit_inside_size(size, keep_ratio)
        else:
            return self.target_size(size, keep_ratio)

    def scale_size(self, size: OptXYF, keep_ratio: bool = True) -> Size:
        """
        Scale this object's size to as close to the given target size as possible, optionally respecting aspect ratio.

        The intended use case is for this Sized/BBox object to be the bounding box for an image's visible content, to
        scale the outer size so that an image cropped to that content will be as close as possible to the target size.
        """
        dst_w, dst_h = size
        trg_w = dst_w / (self.width / dst_w)
        trg_h = dst_h / (self.height / dst_h)
        return self.target_size((trg_w, trg_h), keep_ratio)

    def scale_percent(self, percent: float) -> Size:
        src_w, src_h = self.size
        return self.target_size((src_w * percent, src_h * percent))

    # endregion
