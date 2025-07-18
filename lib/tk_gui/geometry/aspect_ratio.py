from __future__ import annotations

from fractions import Fraction
from math import floor, ceil
from typing import Callable, Iterator, overload

__all__ = ['AspectRatio']

_NotSet = object()


class AspectRatio(Fraction):
    """
    The aspect ratio of an image, or more generally, a rectangle, is the ratio of its width to its height.  This class
    represents a given aspect ratio as a fraction to preserve the exact original integer ratio (such as 37:20 for the
    aspect ratio 1.85:1, which is commonly used in cinematography).

    Squares have an aspect ratio of 1:1 (or 1).
    Rectangles that are "vertical" (width < height) have an aspect ratio < 1.
    Rectangles that are "horizontal" (width > height) have an aspect ratio > 1.
    """

    __slots__ = ()

    # region Init

    @overload
    def __new__(cls, /, x: int | float, y: int | float) -> AspectRatio: ...

    @overload
    def __new__(cls, /, ratio: int | float | str | Fraction) -> AspectRatio: ...

    def __new__(cls, /, x_or_ratio: int | float | str | Fraction, y: int | float = _NotSet):
        try:
            return super().__new__(cls, *_init_args(x_or_ratio, y))
        except ZeroDivisionError as e:
            raise ZeroDivisionError(
                'Invalid aspect ratio - the denominator / proportional height must not be zero'
            ) from e

    @property
    def x(self):
        return self.numerator

    @property
    def y(self):
        return self.denominator

    # endregion

    # region Internal / Dunder Methods

    def __str__(self) -> str:
        return f'{self.x}:{self.y}'

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}[{self.x}:{self.y}][{float(self)}]>'

    def __iter__(self) -> Iterator[float | int]:
        yield self.numerator  # x
        yield self.denominator  # y

    def __hash__(self) -> int:
        return hash(self.__class__) ^ super().__hash__()

    # endregion

    def new_width(self, height: int) -> int:
        return _round_aspect(height * self, key=lambda n: abs(self - n / height))

    def new_height(self, width: int) -> int:
        return _round_aspect(width / self, key=lambda n: 0 if n == 0 else abs(self - width / n))


def _round_aspect(number: float | Fraction, key: Callable[[float], float]) -> int:
    rounded = min(floor(number), ceil(number), key=key)
    return rounded if rounded > 1 else 1


def _init_args(
    x_or_ratio: int | float | str | Fraction, y: int | float = _NotSet
) -> tuple[int | float, int | float] | tuple[str]:
    if isinstance(x_or_ratio, (str, Fraction)):
        if y is not _NotSet:
            raise TypeError(
                'AspectRatio may only be initialized from separate width/height proportions xor a string/Fraction'
            )
        if isinstance(x_or_ratio, Fraction):
            return x_or_ratio.numerator, x_or_ratio.denominator
        else:
            return (x_or_ratio.replace(':', '/'),)
    elif x_or_ratio.is_integer():  # Both ints and floats have this method; `(1.00).is_integer()` => True
        return x_or_ratio, 1 if y is _NotSet else y
    elif y is _NotSet or y == 1:
        # Using str because Fraction('2.35') -> Fraction(47, 20),
        # but Fraction(2.35) -> Fraction(5291729562160333, 2251799813685248)
        return (str(x_or_ratio),)
    else:
        return x_or_ratio, y
