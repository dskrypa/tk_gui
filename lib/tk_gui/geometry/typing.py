from __future__ import annotations

from .base import X, Y, Position, Size


XY = Position | Size | tuple[X, Y]
OptXY = Position | Size | tuple[X | None, Y | None]
OptXYF = Position | Size | tuple[float | int | None, float | int | None]
