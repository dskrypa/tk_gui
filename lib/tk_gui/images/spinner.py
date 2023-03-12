"""
Utilities for working with PIL images.

:author: Doug Skrypa
"""

from __future__ import annotations

import logging
from math import pi, cos, sin
from pathlib import Path
from typing import TYPE_CHECKING, Union, Callable, Iterator

from PIL.Image import Image as PILImage, new as new_image
from PIL.ImageDraw import ImageDraw, Draw

from .color import color_to_rgb, find_unused_color
from .cycle import FrameCycle

if TYPE_CHECKING:
    from ..typing import XY, PathLike

__all__ = ['Spinner']
log = logging.getLogger(__name__)

FloatBox = tuple[float, float, float, float]


class Spinner:
    def __init__(
        self,
        size: Union[XY, int],
        color: str = '#204274',  # sort of a slate blue
        spokes: int = 8,
        bg: str = None,
        size_min_pct: float = 0.5,
        opacity_min_pct: float = 0.4,
        frames_per_spoke: int = 4,
        frame_duration_ms: int = 30,
        frame_fade_pct: float = 0.05,
        reverse: bool = False,
        clockwise: bool = True,
    ):
        self.rgb = color_to_rgb(color)
        self.size = size  # width, height
        self.bg = color_to_rgb(bg) if bg else (*find_unused_color([self.rgb]), 0)
        self.spokes = spokes
        self.size_min_pct = size_min_pct
        self.opacity_min_pct = opacity_min_pct
        self.frames_per_spoke = frames_per_spoke
        self.frame_duration_ms = frame_duration_ms
        self.frame_fade_pct = frame_fade_pct
        self.reverse = reverse
        self.clockwise = clockwise

    @property
    def size(self) -> XY:
        """The (width, height) of this Spinner"""
        return self._size

    @size.setter
    def size(self, value: Union[XY, int]):
        if isinstance(value, int):
            value = (value, value)
        self._size = value
        self.inner_radius = int(min(self.size) / 2 * 0.7)
        self.spoke_radius = self.inner_radius // 3

    def __len__(self) -> int:
        return self.spokes * self.frames_per_spoke

    def _iter_centers(self, spoke: int = 0) -> Iterator[tuple[float, float]]:
        a, b = map(lambda s: s // 2, self.size)
        r = self.inner_radius
        angle = (2 * pi / self.spokes) * (1 if self.reverse else -1)
        spoke_nums = range(self.spokes) if self.clockwise else range(self.spokes - 1, -1, -1)
        for n in spoke_nums:
            t = (n + spoke) * angle
            yield a + r * cos(t), b + r * sin(t)

    def _iter_boxes(self, spoke: int = 0) -> Iterator[tuple[int, float, FloatBox]]:
        step = (1 - self.size_min_pct) / self.spokes
        for i, (x, y) in enumerate(self._iter_centers(spoke)):
            r = self.spoke_radius * (1 - (i * step))
            yield i, r, (x - r, y - r, x + r, y + r)

    def create_frame(self, spoke: int = 0, spoke_frame: int = 0) -> PILImage:
        image = new_image('RGBA', self.size, self.bg)
        draw = Draw(image, 'RGBA')  # type: ImageDraw
        opacity_step_pct = (1 - self.opacity_min_pct) / self.spokes
        a_offset = int(255 * (spoke_frame * self.frame_fade_pct))
        # log.debug(f'Creating frame for focused {spoke=} {spoke_frame=} {opacity_step_pct=} {a_offset=}')
        for i, r, box in self._iter_boxes(spoke):
            a = int(255 * (1 - (i * opacity_step_pct))) - a_offset
            # log.debug(f'    Drawing spoke={i} with {box=} alpha={a} {r=} area={pi * r ** 2:,.2f} px')
            draw.ellipse(box, fill=(*self.rgb, a))
        return image

    def __getitem__(self, i: int) -> PILImage:
        spoke, spoke_frame = divmod(i, self.frames_per_spoke)
        if i < 0 or spoke >= self.spokes or spoke_frame >= self.frames_per_spoke:
            last = len(self) - 1
            raise IndexError(f'Invalid frame {i=} ({spoke=}, {spoke_frame=}) - must be between 0 - {last} (inclusive)')
        return self.create_frame(spoke, spoke_frame)

    def __iter__(self) -> Iterator[PILImage]:
        spoke_nums = range(self.spokes) if self.clockwise ^ (not self.reverse) else range(self.spokes - 1, -1, -1)
        for spoke in spoke_nums:
            for spoke_frame in range(self.frames_per_spoke):
                yield self.create_frame(spoke, spoke_frame)

    frames = __iter__

    def resize(self, size: Union[XY, int]):
        self.size = (size, size) if isinstance(size, int) else size
        return self

    def cycle(
        self, wrapper: Callable = None, duration: int = None, default_duration: int = 100, n: int = 0
    ) -> FrameCycle:
        return FrameCycle(self.frames(), wrapper, duration, default_duration, n=n)

    def save_frames(self, path: PathLike, prefix: str = 'frame_', format: str = 'PNG', mode: str = None):  # noqa
        path = _prepare_dir(path)
        name_fmt = prefix + '{:0' + str(len(str(len(self)))) + 'd}.' + format.lower()
        for i, frame in enumerate(self.frames()):
            if mode and mode != frame.mode:
                frame = frame.convert(mode=mode)
            frame_path = path.joinpath(name_fmt.format(i))
            log.info(f'Saving {frame_path.as_posix()}')
            with frame_path.open('wb') as f:
                frame.save(f, format=format)


def _prepare_dir(path: PathLike) -> Path:
    path = Path(path).expanduser().resolve() if isinstance(path, str) else path
    if path.exists():
        if not path.is_dir():
            raise ValueError(f'Invalid path={path.as_posix()!r} - it must be a directory')
    else:
        path.mkdir(parents=True, exist_ok=True)
    return path
