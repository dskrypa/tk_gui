"""
Utilities for working with animated gif images

:author: Doug Skrypa
"""

from __future__ import annotations

import logging
from pathlib import Path
from tkinter import PhotoImage
from typing import TYPE_CHECKING, Iterator, Iterable, Callable, Union, TypeVar, Generic, Optional

from PIL.GifImagePlugin import GifImageFile
from PIL.Image import Image as PILImage, new as new_image
from PIL.ImageSequence import Iterator as FrameIterator
from PIL.ImageTk import PhotoImage as PilPhotoImage

from .wrapper import SourceImage

if TYPE_CHECKING:
    from tk_gui.typing import PathLike

__all__ = ['FrameCycle', 'PhotoImageCycle']
log = logging.getLogger(__name__)

T_co = TypeVar('T_co', covariant=True)


class FrameCycle(Generic[T_co]):
    __slots__ = ('n', '_frames', '_wrapper', '_duration', '_default_duration', '_frames_and_durations', 'first_delay')

    def __init__(
        self,
        frames: Iterable[Union[PILImage, tuple[PILImage, Optional[int]]]],
        wrapper: Callable[[PILImage], T_co] = None,
        duration: int = None,
        default_duration: int = 100,
    ):
        self.n = 0
        self._wrapper = wrapper
        self._duration = duration
        self._default_duration = default_duration

        self._frames = frames = tuple(frames)
        if isinstance(frames[0], tuple):
            self._frames = tuple(f[0] for f in frames)
            self._frames_and_durations = tuple(
                (f, duration if duration else (default_duration if d is None else d)) for f, d in frames
            )
        else:
            def get_duration(f):
                return duration if duration is not None else f.info.get('duration', default_duration)

            if wrapper is None:
                self._frames_and_durations = tuple((f, get_duration(f)) for f in self._frames)
            else:
                self._frames_and_durations = tuple((wrapper(f), get_duration(f)) for f in self._frames)

        self.first_delay = self._frames_and_durations[0][1]

    def __len__(self) -> int:
        return len(self._frames_and_durations)

    def __iter__(self) -> Iterator[tuple[T_co, int]]:
        return self

    def __next__(self) -> tuple[T_co, int]:
        self.n += 1
        try:
            return self._frames_and_durations[self.n]
        except IndexError:
            self.n = 0
            return self._frames_and_durations[0]

    next = __next__

    def back(self) -> tuple[T_co, int]:
        self.n -= 1
        if self.n < 0:
            self.n = len(self._frames_and_durations) - 1
        return self._frames_and_durations[self.n]

    @property
    def current_image(self) -> PILImage:
        return self._frames[self.n]

    @property
    def current_frame(self) -> T_co:
        return self._frames_and_durations[self.n][0]

    def resized(self, width: int, height: int) -> FrameCycle[PilPhotoImage]:
        size = (width, height)
        mode = _get_mode(self._frames)  # noqa
        raw_frames = iter_independent_frames(self._frames, mode)  # noqa
        frames = [
            (frame.resize(size), duration) for frame, (_, duration) in zip(raw_frames, self._frames_and_durations)
        ]
        # frames = [frame.copy().resize(size) for frame in self._frames]
        return FrameCycle(frames, PilPhotoImage, self._duration, self._default_duration)


class PhotoImageCycle(FrameCycle[PhotoImage]):
    __slots__ = ('src_image', '_pi_frames')

    def __init__(self, path: PathLike, duration: int = None, default_duration: int = 100):  # noqa
        self.src_image = src_image = SourceImage.from_image(Path(path).expanduser())
        self.n = 0
        self._pi_frames = tuple(
            PhotoImage(file=path.as_posix(), format=f'gif -index {n}') for n in range(src_image.pil_image.n_frames)
        )
        self._frames = tuple(FrameIterator(src_image.pil_image))
        self._wrapper = PhotoImage
        self._duration = duration
        self._default_duration = default_duration

        def get_duration(f):
            return duration if duration is not None else f.info.get('duration', default_duration)

        self._frames_and_durations = tuple((pi, get_duration(f)) for pi, f in zip(self._pi_frames, self._frames))
        self.first_delay = self._frames_and_durations[0][1]

    @property
    def path(self) -> Path:
        return self.src_image.path


# region Frame Extraction


def iter_independent_frames(frames: Iterable[GifImageFile], mode: str) -> Iterator[PILImage]:
    frames = iter(frames)
    first = next(frames)
    p = first.getpalette()
    prev_frame = first.convert('RGBA')
    yield first
    for frame in frames:
        if not frame.getpalette():
            try:
                frame.putpalette(p)
            except ValueError:
                pass

        new_frame = new_image('RGBA', frame.size)
        if mode == 'partial':
            new_frame.paste(prev_frame)
        new_frame.paste(frame, (0, 0), frame.convert('RGBA'))  # noqa
        yield new_frame
        prev_frame = new_frame


def iter_frames(image: GifImageFile) -> Iterator[tuple[PILImage, Optional[int]]]:
    # Based on https://gist.github.com/almost/d2832d0998ad9dfec2cacef934e7d247
    mode = get_mode(image)
    p = image.getpalette()
    prev_frame = image.convert('RGBA')
    try:
        while True:
            if not image.getpalette():
                image.putpalette(p)

            new_frame = new_image('RGBA', image.size)
            if mode == 'partial':
                new_frame.paste(prev_frame)
            new_frame.paste(image, (0, 0), image.convert('RGBA'))  # noqa
            yield new_frame, image.info.get('duration')
            prev_frame = new_frame
            image.seek(image.tell() + 1)
    except EOFError:
        pass


def get_mode(image: GifImageFile) -> str:
    mode = _get_mode(_iter_raw_frames(image))
    image.seek(0)
    return mode


def _get_mode(frames: Iterable[GifImageFile]) -> str:
    mode = 'full'
    for frame in frames:
        try:
            if frame.tile:
                tile = frame.tile[0]
                update_region = tile[1]
                update_region_dimensions = update_region[2:]
                if update_region_dimensions != frame.size:
                    mode = 'partial'
                    break
        except AttributeError:
            break

    return mode


def _iter_raw_frames(image: GifImageFile) -> Iterator[GifImageFile]:
    try:
        while True:
            yield image
            image.seek(image.tell() + 1)
    except EOFError:
        pass


# endregion
