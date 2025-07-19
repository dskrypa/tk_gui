"""
This module contains basic classes required for box geometry calculations, on which the other modules in the package
build upon.

The Position/Size classes represent 2-tuples storing (X, Y) coordinates and (width, height) values, respectively.

Additionally, classes are defined here to represent edge spacing around rectangular content, following the same model
as the CSS Box Model:

┌───────────────────────────────┐
│           Margin              │
│  ┌────────────────────────┐   │
│  │        Border          │   │
│  │  ┌──────────────────┐  │   │
│  │  │     Padding      │  │   │
│  │  │  ┌────────────┐  │  │   │
│  │  │  │  Content   │  │  │   │
│  │  │  └────────────┘  │  │   │
│  │  └──────────────────┘  │   │
│  └────────────────────────┘   │
└───────────────────────────────┘
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterator, NamedTuple, TypeVar, overload

if TYPE_CHECKING:
    from tk_gui.typing import HasSize
    from .typing import XY

__all__ = ['Position', 'Size', 'Padding', 'Border', 'Margin']

X = Y = int
T = TypeVar('T')


class Position(NamedTuple):
    x: X
    y: Y


class Size(NamedTuple):
    width: X
    height: Y

    def __str__(self) -> str:
        return f'{self.width} x {self.height}'

    @overload
    def __add__(self, other: Padding | Border | Margin) -> Size: ...

    @overload
    def __add__(self, other: tuple[T, ...]) -> tuple[int | T, ...]: ...

    def __add__(self, other):
        match other:
            case EdgeSpacing():
                return Size(self.width + other.right + other.left, self.height + other.top + other.bottom)
            case tuple():
                return self.width, self.height, *other
            case _:
                raise TypeError(
                    f'Can only concatenate Size with Padding/Border/Margin objects or other tuples,'
                    f' not {other.__class__.__name__}'
                )


class EdgeSpacing:
    """
    Defines the size of spaces around the edges of a box / rectangle.  Base class for Padding / Border / Margin classes
    that can be used to define specific edge layers following a model that mimics the CSS Box Model.
    """

    __slots__ = ('top', 'right', 'bottom', 'left')
    top: Y
    right: X
    bottom: Y
    left: X

    # region Init

    @overload
    def __init__(self, /, top: Y, right: X, bottom: Y, left: X):
        ...

    @overload
    def __init__(self, /, top: Y, right_and_left: X, bottom: Y):
        ...

    @overload
    def __init__(self, /, top_and_bottom: Y, right_and_left: X):
        ...

    @overload
    def __init__(self, /, all_sides: int):
        ...

    def __init__(self, *args):
        n_args = len(args)
        if not args or n_args > 4:
            raise ValueError(
                f'{self.__class__.__name__} may be initialized with 1 to 4 integers; found {len(args)} args'
            )
        elif not all(isinstance(a, int) for a in args):
            raise TypeError(f'{self.__class__.__name__} may be initialized with 1 to 4 integers; found invalid types')

        if n_args == 4:
            self.top, self.right, self.bottom, self.left = args
        elif n_args == 3:
            self.top, self.right, self.bottom = args
            self.left = self.right
        elif n_args == 2:
            self.top, self.right = self.bottom, self.left = args
        else:
            self.top = self.right = self.bottom = self.left = args[0]

    # endregion

    def __bool__(self) -> bool:
        return (self.top or self.right or self.bottom or self.left) != 0

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({self.top}, {self.right}, {self.bottom}, {self.left})'

    def __eq__(self, op: EdgeSpacing) -> bool:
        if not isinstance(op, EdgeSpacing):
            return NotImplemented
        return self.top == op.top and self.right == op.right and self.bottom == op.bottom and self.left == op.left

    def __hash__(self) -> int:
        return hash(self.__class__) ^ hash(self.top) ^ hash(self.right) ^ hash(self.bottom) ^ hash(self.left)

    def __iter__(self) -> Iterator[int]:
        yield self.top
        yield self.right
        yield self.bottom
        yield self.left

    def __getitem__(self, index: int | slice) -> int | tuple[int, ...]:
        if isinstance(index, int):
            if -5 <= index or index >= 4:
                raise IndexError(f'{self.__class__.__name__} index out of range')
            if index < 0:
                index += 4
            if index:
                return self.right if index == 1 else self.bottom if index == 2 else self.left
            else:
                return self.top
        elif isinstance(index, slice):
            return tuple(self)[index]
        else:
            raise TypeError(
                f'{self.__class__.__name__} indices must be integers or slices, not {index.__class__.__name__}'
            )

    def __add__(self, other: XY | HasSize) -> Size:
        width, height = _get_size(other)
        return Size(width + self.left + self.right, height + self.top + self.bottom)


class Padding(EdgeSpacing):
    """
    Padding to be applied around boxes / rectangles / items in images.  May be initialized similarly to the way that
    `padding is defined in CSS <https://www.w3schools.com/Css/css_padding.asp>`__.
    """
    __slots__ = ()


class Border(EdgeSpacing):
    """
    Borders to be applied around boxes / rectangles / items in images.  May be initialized similarly to the way that
    padding/margins are defined in CSS.

    Does not currently support defining a line style/color/etc.
    """
    __slots__ = ()


class Margin(EdgeSpacing):
    """
    Margins to be applied around boxes / rectangles / items in images.  May be initialized similarly to the way that
    `margins are defined in CSS <https://www.w3schools.com/Css/css_margin.asp>`__.
    """
    __slots__ = ()


def _get_size(obj) -> XY:
    match obj:
        case Size() | (int(), int()):
            return obj

    try:
        # This is faster than a hasattr check or moving HasSize here and adding `case HasSize():` above
        return _get_size(obj.size)
    except AttributeError:
        pass

    raise TypeError(f"Expected a Size or sequence of 2 ints, or an object with a 'size' attribute with such a value")
