from __future__ import annotations

from typing import TYPE_CHECKING, Iterator, overload

if TYPE_CHECKING:
    from tk_gui.typing import HasSize
    from .typing import X, Y, XY

__all__ = ['Padding']


class Padding:
    """
    Padding to be applied around items in images.  May be initialized similarly to the way that
    `padding is defined in CSS <https://www.w3schools.com/cssref/pr_padding.php>`__.
    """

    __slots__ = ('top', 'right', 'bottom', 'left')
    top: Y
    right: X
    bottom: Y
    left: X

    @overload
    def __init__(self, /, top: Y, right: X, bottom: Y, left: X): ...

    @overload
    def __init__(self, /, top: Y, right_and_left: X, bottom: Y): ...

    @overload
    def __init__(self, /, top_and_bottom: Y, right_and_left: X): ...

    @overload
    def __init__(self, /, all_sides: int): ...

    def __init__(self, *args):
        n_args = len(args)
        if not args or n_args > 4:
            raise ValueError(f'Padding may be initialized with 1 to 4 integers; found {len(args)} args')
        elif not all(isinstance(a, int) for a in args):
            raise TypeError('Padding may be initialized with 1 to 4 integers; found invalid types')

        if n_args == 4:
            self.top, self.right, self.bottom, self.left = args
        elif n_args == 3:
            self.top, self.right, self.bottom = args
            self.left = self.right
        elif n_args == 2:
            self.top, self.right = self.bottom, self.left = args
        else:
            self.top = self.right = self.bottom = self.left = args[0]

    def size_for(self, sized: HasSize) -> XY:
        width, height = sized.size
        return width + self.left + self.right, height + self.top + self.bottom

    def __bool__(self) -> bool:
        return (self.top or self.right or self.bottom or self.left) != 0

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({self.top}, {self.right}, {self.bottom}, {self.left})'

    def __eq__(self, op: Padding) -> bool:
        if not isinstance(op, Padding):
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
                raise IndexError('Padding index out of range')
            if index < 0:
                index += 4
            if index:
                return self.right if index == 1 else self.bottom if index == 2 else self.left
            else:
                return self.top
        elif isinstance(index, slice):
            return tuple(self)[index]
        else:
            raise TypeError(f'Padding indices must be integers or slices, not {index.__class__.__name__}')
