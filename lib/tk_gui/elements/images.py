"""
Tkinter GUI images

:author: Doug Skrypa
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from inspect import Signature
from pathlib import Path
from tkinter import Label, TclError, Event
from typing import TYPE_CHECKING, Optional, Any, Union

from PIL.Image import Image as PILImage, Resampling
from PIL.ImageSequence import Iterator as FrameIterator
from PIL.ImageTk import PhotoImage

from ..images import SevenSegmentDisplay, calculate_resize, as_image
from ..images.cycle import FrameCycle, PhotoImageCycle
from ..images.spinner import Spinner
from ..styles import Style, StyleSpec
from .element import Element

if TYPE_CHECKING:
    from ..pseudo_elements import Row
    from ..typing import XY, BindTarget, ImageType

__all__ = ['Image', 'Animation', 'SpinnerImage', 'ClockImage', 'get_size']
log = logging.getLogger(__name__)

AnimatedType = Union[PILImage, Spinner, Path, str, '_ClockCycle']
_Image = Optional[Union[PILImage, PhotoImage]]
ImageAndSize = tuple[_Image, int, int]
ImageCycle = Union[FrameCycle, '_ClockCycle']


class Image(Element, base_style_layer='image'):
    widget: Label = None
    animated: bool = False

    def __init_subclass__(cls, animated: bool = None, **kwargs):
        super().__init_subclass__(**kwargs)
        if animated is not None:
            cls.animated = animated

    def __init__(self, image: ImageType = None, callback: BindTarget = None, **kwargs):
        """
        :param image: The image to display
        :param callback: Callback action to perform when the image is clicked (overrides left_click_cb).  Supports
          ``'popup'`` to open a popup with the image.
        :param kwargs: Additional keyword arguments to pass to :class:`.Element`
        """
        if callback is not None:
            kwargs['bind_clicks'] = True
        super().__init__(**kwargs)
        self.image = image
        self._callback = callback

    @property
    def image(self) -> Optional[_GuiImage]:
        return self._image

    @image.setter
    def image(self, data: ImageType):
        self._image = _GuiImage(data)
        if self.widget is not None:
            self.refresh()

    def pack_into(self, row: Row, column: int):
        try:
            width, height = self.size
        except TypeError:
            width, height = None, None

        image, width, height = self._image.as_size(width, height)
        self._pack_into(row, image, width, height)

    @property
    def style_config(self) -> dict[str, Any]:
        return {
            **self.style.get_map('image', bd='border_width', background='bg', relief='relief'),
            **self._style_config,
        }

    def _pack_into(self, row: Row, image: _Image, width: int, height: int):
        # log.debug(f'Packing {image=} into row with {width=}, {height=}')
        kwargs = {'width': width, 'height': height, 'takefocus': int(self.allow_focus), **self.style_config}
        if image:
            kwargs['image'] = image

        self.size = (width, height)
        self.widget = label = Label(row.frame, **kwargs)
        label.image = image
        self.pack_widget()
        if (callback := self._callback) is not None:
            self.left_click_cb = self.normalize_callback(callback)

    def _re_pack(self, image: _Image, width: int, height: int):
        # log.debug(f'_re_pack: {width=}, {height=}, {self}')
        self.size = (width, height)
        widget = self.widget
        widget.configure(image=image, width=width, height=height)

        widget.image = image
        widget.pack(**self.pad_kw)

    def target_size(self, width: int, height: int) -> XY:
        return self._image.target_size(width, height)

    def refresh(self):
        self.resize(*self.size)

    def resize(self, width: int, height: int):
        image, width, height = self._image.as_size(width, height)
        self._re_pack(image, width, height)

    def handle_open_popup(self, event: Event = None):
        from ..popups.image import ImagePopup

        img = self._image
        ImagePopup(img.src_image, img.path.name if img.path else None, parent=self.window).run()


class Animation(Image, animated=True):
    image_cycle: FrameCycle

    def __init__(
        self,
        image: AnimatedType,
        last_frame_num: int = 0,
        paused: bool = False,
        *,
        callback: BindTarget = None,
        **kwargs,
    ):
        Element.__init__(self, **kwargs)
        self.__image = image
        self._last_frame_num = last_frame_num
        self._next_id = None
        self._run = not paused
        self._callback = callback

    @property
    def paused(self):
        return not self._run

    def pack_into(self, row: Row, column: int):
        # log.debug(f'pack_into: {self.size=}')
        self.image_cycle = image_cycle = normalize_image_cycle(self.__image, self.size, self._last_frame_num)
        # log.debug(f'Prepared {len(image_cycle)} frames')
        frame, delay = next(image_cycle)
        try:
            width, height = self.size
        except TypeError:
            width = frame.width()
            height = frame.height()
            self.size = (width, height)

        self._pack_into(row, frame, width, height)
        if self._run:
            self._next_id = self.widget.after(delay, self.next)

    def target_size(self, width: int, height: int) -> XY:
        try:
            size = self.__image.size
        except AttributeError:
            size = self.size
        return calculate_resize(*size, width, height)

    def resize(self, width: int, height: int):
        # log.debug(f'resize: {width=}, {height=}, {self}')
        # self.size = size = (width, height)
        self.image_cycle = image_cycle = self._resize_cycle((width, height))
        image = self.__image
        try:
            width, height = size = image.size
        except AttributeError:
            width, height = size = image.width, image.height

        # self.size = size
        frame, delay = next(image_cycle)
        self._re_pack(frame, width, height)
        if self._run:
            self._cancel()
            self.next()
            # self._next_id = self.widget.after(delay, self.next)

    def _resize_cycle(self, size: XY) -> ImageCycle:
        return normalize_image_cycle(self.__image, size, self.image_cycle.n)

    def next(self):
        frame, delay = next(self.image_cycle)
        width, height = self.size
        self.widget.configure(image=frame, width=width, height=height)
        if self._run:
            self._next_id = self.widget.after(delay, self.next)

    def previous(self):
        frame, delay = self.image_cycle.back()
        width, height = self.size
        self.widget.configure(image=frame, width=width, height=height)
        if self._run:
            self._next_id = self.widget.after(delay, self.previous)

    def _cancel(self):
        if next_id := self._next_id:
            try:
                self.widget.after_cancel(next_id)
            except (TclError, RuntimeError) as e:
                log.debug(f'Error canceling next animation step: {e}')
            self._next_id = None

    def pause(self):
        self._run = False
        self._cancel()

    def resume(self):
        self._run = True
        self.next()


class SpinnerImage(Animation):
    _spinner_keys = set(Signature.from_callable(Spinner).parameters.keys())
    DEFAULT_SIZE = (200, 200)
    DEFAULT_KWARGS = {'frame_fade_pct': 0.01, 'frame_duration_ms': 20, 'frames_per_spoke': 1}

    def __init__(self, **kwargs):
        spinner_kwargs = _extract_kwargs(kwargs, self._spinner_keys, self.DEFAULT_KWARGS)
        size = spinner_kwargs.setdefault('size', self.DEFAULT_SIZE)
        spinner = Spinner(**spinner_kwargs)
        super().__init__(spinner, size=size, **kwargs)

    def target_size(self, width: int, height: int) -> XY:
        # TODO: Add support for keeping aspect ratio
        return width, height


class _ClockCycle:
    __slots__ = ('clock', 'delay', 'last_time', '_last_frame', 'n')
    SECOND = timedelta(seconds=1)

    def __init__(self, clock: SevenSegmentDisplay):
        self.clock = clock
        self.delay = 200 if clock.seconds else 1000
        self.last_time = datetime.now() - self.SECOND
        self._last_frame = None
        self.n = 0

    def __next__(self):
        now = datetime.now()
        if now.second != self.last_time.second:
            self.last_time = now
            self._last_frame = frame = PhotoImage(self.clock.draw_time(now))
        else:
            frame = self._last_frame

        return frame, self.delay

    back = __next__

    @property
    def size(self) -> XY:
        return self.clock.time_size()


class ClockImage(Animation):
    image_cycle: _ClockCycle
    _clock_keys = set(Signature.from_callable(SevenSegmentDisplay).parameters.keys())
    DEFAULT_KWARGS = {'bar_pct': 0.2, 'width': 40}

    def __init__(
        self,
        slim: bool = False,
        img_size: XY = None,
        style: StyleSpec = None,
        toggle_slim_on_click: Union[bool, str] = False,
        **kwargs,
    ):
        clock_kwargs = _extract_kwargs(kwargs, self._clock_keys, self.DEFAULT_KWARGS)
        self._slim = slim
        self.clock = clock = SevenSegmentDisplay(**clock_kwargs)
        if img_size is not None:
            clock.resize_full(*img_size)

        if toggle_slim_on_click:
            if toggle_slim_on_click is True:
                kwargs['left_click_cb'] = self.toggle_slim
            elif isinstance(toggle_slim_on_click, str):
                kwargs.setdefault('binds', {})[toggle_slim_on_click] = self.toggle_slim

        kwargs.setdefault('pad', (0, 0))
        kwargs.setdefault('size', clock.time_size())
        super().__init__(_ClockCycle(clock), style=style or Style(bg='black'), **kwargs)

    def toggle_slim(self, event: Event = None):
        slim = self._slim
        clock = self.clock
        clock.resize(bar_pct=(clock.bar_pct * (2 if slim else 0.5)), preserve_height=True)
        self._slim = not slim
        self.image_cycle.last_time -= _ClockCycle.SECOND

    def _resize_cycle(self, size: XY) -> ImageCycle:
        self.clock.resize_full(*size)
        self.image_cycle.last_time -= _ClockCycle.SECOND
        return self.image_cycle

    def target_size(self, width: int, height: int) -> XY:
        return self.clock.calc_resize_width(width, height)[0]


class _GuiImage:
    __slots__ = ('src_image', 'current', 'current_tk', 'src_size', 'size', 'path')

    def __init__(self, image: ImageType):
        try:
            self.path = _get_path(image)
        except ValueError:
            self.path = None
        image = as_image(image)
        # log.debug(f'Loaded image={image!r}')
        self.src_image: Optional[PILImage] = image
        self.current: Optional[PILImage] = image
        self.current_tk: Optional[PhotoImage] = None
        try:
            size = image.size
        except AttributeError:  # image is None
            size = (0, 0)
        self.src_size = size
        self.size = size

    def _normalize(self, width: Optional[int], height: Optional[int]) -> XY:
        if width is None:
            width = self.size[0]
        if height is None:
            height = self.size[1]
        return width, height

    def target_size(self, width: Optional[int], height: Optional[int]) -> XY:
        width, height = self._normalize(width, height)
        cur_width, cur_height = self.size
        if self.current is None or (cur_width == width and cur_height == height):
            return width, height
        # elif cur_width >= width and cur_height >= height:
        #     return calculate_resize(cur_width, cur_height, width, height)
        else:
            return calculate_resize(*self.src_size, width, height)

    def as_size(self, width: Optional[int], height: Optional[int]) -> ImageAndSize:
        width, height = self._normalize(width, height)
        if (current := self.current) is None:
            return None, width, height

        cur_width, cur_height = self.size
        if cur_width == width and cur_height == height:
            if not (current_tk := self.current_tk):
                self.current_tk = current_tk = PhotoImage(current)
            return current_tk, width, height
        elif cur_width >= width and cur_height >= height:
            src = current
            dst_width, dst_height = calculate_resize(cur_width, cur_height, width, height)
        else:
            src = self.src_image
            dst_width, dst_height = calculate_resize(*self.src_size, width, height)

        dst_size = (dst_width, dst_height)
        try:
            self.current = image = src.resize(dst_size, Resampling.LANCZOS)
            self.current_tk = tk_image = PhotoImage(image)
        except OSError as e:
            log.warning(f'Error resizing image={src}: {e}')
            return src, width, height
        else:
            self.size = dst_size
            return tk_image, dst_width, dst_height


def normalize_image_cycle(image: AnimatedType, size: XY = None, last_frame_num: int = 0) -> ImageCycle:
    if isinstance(image, Spinner):
        if size:
            image.resize(size)
        frame_cycle = image.cycle(PhotoImage)
    elif isinstance(image, _ClockCycle):
        frame_cycle = image
        if size:
            clock = frame_cycle.clock
            clock.resize_full(*size)
            frame_cycle.last_time -= frame_cycle.SECOND
    else:
        try:
            path = _get_path(image)
        except ValueError:
            image = as_image(image)
            frame_cycle = FrameCycle(tuple(FrameIterator(image)), PhotoImage)
        else:
            frame_cycle = PhotoImageCycle(path)

        # TODO: Likely need a different lib for gif resize
        # if size and size != get_size(image):
        #     frame_cycle = frame_cycle.resized(*size)

    # elif isinstance(image, (Path, str)):
    #     frame_cycle = PhotoImageCycle(Path(image).expanduser())
    #     if size:
    #         log.debug(f'Resizing {frame_cycle=} to {size=}')
    #         frame_cycle = frame_cycle.resized(*size)
    # else:  # TODO: PhotoImageCycle will not result in expected resize behavior...
    #     if path := getattr(image, 'filename', None) or getattr(getattr(image, 'fp', None), 'name', None):
    #         frame_cycle = PhotoImageCycle(Path(path))
    #         if size:
    #             log.debug(f'Resizing {frame_cycle=} to {size=}')
    #             frame_cycle = frame_cycle.resized(*size)
    #     else:
    #         raise ValueError(f'Unexpected image type for {image=}')
    #         # image = AnimatedGif(image)
    #         # if size:
    #         #     image = image.resize(size, 1)
    #         # frame_cycle = image.cycle(PhotoImage)

    frame_cycle.n = last_frame_num
    return frame_cycle


def _get_path(image: ImageType) -> Path:
    if isinstance(image, Path):
        return image
    elif isinstance(image, str):
        return Path(image).expanduser()
    elif path := getattr(image, 'filename', None) or getattr(getattr(image, 'fp', None), 'name', None):
        return Path(path)
    raise ValueError(f'Unexpected image type for {image=}')


def get_size(image: Union[AnimatedType, SevenSegmentDisplay]) -> XY:
    if isinstance(image, Spinner):
        return image.size
    elif isinstance(image, SevenSegmentDisplay):
        return image.time_size()
        # return image.width, image.height
    image = as_image(image)
    return image.size


def _extract_kwargs(kwargs: dict[str, Any], keys: set[str], defaults: dict[str, Any]) -> dict[str, Any]:
    extracted = {key: kwargs.pop(key) for key in keys if key in kwargs}
    for key, val in defaults.items():
        extracted.setdefault(key, val)

    return extracted
