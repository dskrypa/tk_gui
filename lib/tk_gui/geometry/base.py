from __future__ import annotations

from typing import NamedTuple

__all__ = ['Position', 'Size']

X = Y = int


class Position(NamedTuple):
    x: X
    y: Y


class Size(NamedTuple):
    width: X
    height: Y

    def __str__(self) -> str:
        return f'{self.width} x {self.height}'
