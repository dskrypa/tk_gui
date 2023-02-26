"""
Tkinter GUI images

:author: Doug Skrypa
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from functools import lru_cache
from inspect import Signature
from pathlib import Path
from tkinter import Label, TclError, Event
from typing import TYPE_CHECKING, Optional, Any, Union

from PIL.Image import Image as PILImage, Resampling, open as open_image
from PIL.ImageSequence import Iterator as FrameIterator
from PIL.ImageTk import PhotoImage
from PIL.JpegImagePlugin import RAWMODE

from ..enums import Anchor
from ..images import SevenSegmentDisplay, calculate_resize, as_image
from ..images.cycle import FrameCycle, PhotoImageCycle
from ..images.spinner import Spinner
from ..images.utils import get_image_and_hash, get_image_path
from ..styles import Style, StyleSpec
from ..utils import get_user_temp_dir
from .element import Element

if TYPE_CHECKING:
    from ..pseudo_elements import Row
    from ..typing import XY, BindTarget, ImageType, Bool, OptInt, TkContainer, HasFrame

__all__ = ['Image', 'Animation', 'SpinnerImage', 'ClockImage', 'get_size']
log = logging.getLogger(__name__)

AnimatedType = Union[PILImage, Spinner, Path, str, '_ClockCycle']
_Image = Optional[Union[PILImage, PhotoImage]]
ImageAndSize = tuple[_Image, int, int]
ImageCycle = Union[FrameCycle, '_ClockCycle']


class Image(Element, base_style_layer='image'):
    _callback: BindTarget = None
    widget: Label = None
    animated: bool = False
    popup_title: str = None
    anchor_image: Anchor = Anchor.NONE

    def __init_subclass__(cls, animated: bool = None, **kwargs):
        super().__init_subclass__(**kwargs)
        if animated is not None:
            cls.animated = animated

    def __init__(
        self,
        image: ImageType = None,
        *,
        callback: BindTarget = None,
        popup: Bool = None,
        popup_title: str = None,
        anchor_image: Union[str, Anchor] = None,
        **kwargs,
    ):
        """
        :param image: The image to display.
        :param callback: Callback action to perform when the image is clicked (overrides left_click_cb).
        :param popup: True to open a popup with the image on left click (cannot be specified with ``callback``).
        :param popup_title: The title to use for the popup (defaults to the name of the image file).
        :param kwargs: Additional keyword arguments to pass to :class:`.Element`.
        """
        if (cb_provided := callback is not None) or popup:
            kwargs['bind_clicks'] = True
        super().__init__(**kwargs)
        self.image = image
        if popup:
            if cb_provided:
                raise TypeError(f"Only one of 'popup' xor 'callback' may be provided for {self.__class__.__name__}")
            self._callback = self._handle_open_popup
            self.popup_title = popup_title
        elif cb_provided:
            self._callback = callback
        if anchor_image:
            self.anchor_image = Anchor(anchor_image)

    # region Image Data

    @property
    def image(self) -> Optional[_GuiImage]:
        return self._image

    @image.setter
    def image(self, data: ImageType):
        self._image = _GuiImage(data)
        if self.widget is not None:
            self.resize(*self.size)

    # endregion

    # region Style

    @property
    def style_config(self) -> dict[str, Any]:
        return {
            **self.style.get_map('image', bd='border_width', background='bg', relief='relief'),
            **self._style_config,
        }

    # endregion

    # region Widget Init & Packing

    def _init_widget(self, tk_container: TkContainer):
        pass

    def grid_into(self, parent: HasFrame, row: int, column: int, **kwargs):
        raise RuntimeError('Grid is not currently supported for images')

    def pack_into(self, row: Row):
        try:
            width, height = self.size
        except TypeError:
            width, height = None, None

        # TODO: Right-click menu: save as
        image, width, height = self._image.as_size(width, height)
        self._pack_into(row, image, width, height)

    def _pack_into(self, row: Row, image: _Image, width: int, height: int):
        # log.debug(f'Packing {image=} into row with {width=}, {height=}')
        kwargs = {
            'width': width,
            'height': height,
            'anchor': self.anchor_image.value,
            'takefocus': int(self.allow_focus),
            **self.style_config,
        }
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
        widget.configure(image=image, width=width, height=height, anchor=self.anchor_image.value)

        widget.image = image
        widget.pack(**self.pad_kw)

    # endregion

    def target_size(self, width: int, height: int) -> XY:
        return self._image.target_size(width, height)

    def resize(self, width: int, height: int):
        image, width, height = self._image.as_size(width, height)
        self._re_pack(image, width, height)

    def _handle_open_popup(self, event: Event = None):
        from ..popups.image import ImagePopup

        img = self._image
        title = self.popup_title or (img.path.name if img.path else None)
        ImagePopup(img.src_image, title, parent=self.window).run()


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

    def pack_into(self, row: Row):
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

    # region Size & Resize

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

    # endregion

    # region Display Animation Frames

    def next(self):
        """
        Display the next frame in the animation.  While running, it is continuously registered to be called by the
        widget, after a delay.
        """
        frame, delay = next(self.image_cycle)
        width, height = self.size
        self.widget.configure(image=frame, width=width, height=height)
        if self._run:
            self._next_id = self.widget.after(delay, self.next)

    def previous(self):
        """
        Display the previous frame in the animation.  Similar to :meth:`.next`, while running in reverse, it is
        continuously registered to be called by the widget, after a delay.
        """
        frame, delay = self.image_cycle.back()
        width, height = self.size
        self.widget.configure(image=frame, width=width, height=height)
        if self._run:
            self._next_id = self.widget.after(delay, self.previous)

    # endregion

    # region Animation State & Play / Stop Controls

    @property
    def running(self) -> bool:
        return self._run

    def play(self):
        if not self._run:
            self._run = True
            self.next()

    def stop(self):
        self._run = False
        self._cancel()

    def _cancel(self):
        if next_id := self._next_id:
            try:
                self.widget.after_cancel(next_id)
            except (TclError, RuntimeError) as e:
                log.debug(f'Error canceling next animation step: {e}')
            self._next_id = None

    # endregion


class SpinnerImage(Animation):
    _spinner_keys = set(Signature.from_callable(Spinner).parameters.keys())
    DEFAULT_SIZE = (200, 200)
    DEFAULT_KWARGS = {'frame_fade_pct': 0.01, 'frame_duration_ms': 20, 'frames_per_spoke': 1}

    def __init__(self, **kwargs):
        """
        Supported Spinner params: size, color, spokes, bg, size_min_pct, opacity_min_pct, frames_per_spoke,
        frame_duration_ms, frame_fade_pct, reverse, clockwise.
        """
        spinner_kwargs = _extract_kwargs(kwargs, self._spinner_keys, self.DEFAULT_KWARGS)
        size = spinner_kwargs.setdefault('size', self.DEFAULT_SIZE)
        self.spinner = spinner = Spinner(**spinner_kwargs)
        super().__init__(spinner, size=size, **kwargs)

    def target_size(self, width: int, height: int) -> XY:
        # TODO: Add support for keeping aspect ratio
        return width, height


# region Digital Clock


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
        """
        Supported SevenSegmentDisplay params: width, bar, gap, corners, fg, bg, bar_pct, seconds.

        :param slim: Whether the "digital" numbers should be slim or normal.
        :param img_size: The desired full, outer size for the clock.
        :param style: The style to use.  By default, this element does not respect the selected :class:`.Style`, and
          uses a simple style that only defines that the background is black.  The default clock number color is ``#FF``
          (red), and should be specified via the ``fg`` kwarg instead of via ``style``.  If a style defining a different
          background color is provided, the ``bg`` kwarg should probably also be provided so that it is used when the
          :class:`.SevenSegmentDisplay` is initialized.
        :param toggle_slim_on_click: Whether a left-click callback should be registered to toggle between slim and
          normal numbers in the clock.
        :param kwargs: Additional keyword arguments to pass to :class:`.SevenSegmentDisplay` or :class:`Animation`.
        """
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


# endregion


class _GuiImage:
    __slots__ = ('src_image', 'current', 'current_tk', 'src_size', 'size', 'path', 'src_hash', 'max_thumbnail_size')
    src_image: PILImage | None
    current: PILImage | None
    current_tk: PhotoImage | None

    def __init__(self, image: ImageType, max_thumbnail_size: XY = (500, 500)):
        self.max_thumbnail_size = max_thumbnail_size
        self.path = get_image_path(image, True)
        image, self.src_hash = get_image_and_hash(image)
        # log.debug(f'Loaded image={image!r}')
        self.src_image = image
        self.current = image
        self.current_tk = None
        try:
            size = image.size
        except AttributeError:  # image is None
            size = (0, 0)
        self.src_size = size
        self.size = size

    # region Size Calculation

    def _normalize_size(self, width: OptInt, height: OptInt) -> XY:
        if width is None:
            width = self.size[0]
        if height is None:
            height = self.size[1]
        return width, height

    def target_size(self, width: OptInt, height: OptInt) -> XY:
        width, height = self._normalize_size(width, height)
        cur_width, cur_height = self.size
        if self.current is None or (cur_width == width and cur_height == height):
            return width, height
        # elif cur_width >= width and cur_height >= height:
        #     return calculate_resize(cur_width, cur_height, width, height)
        else:
            return calculate_resize(*self.src_size, width, height)

    # endregion

    # region Load & Resize Methods

    def as_size(self, width: OptInt, height: OptInt) -> ImageAndSize:
        width, height = self._normalize_size(width, height)
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

        return self._as_size(src, width, height, dst_width, dst_height)

    def _as_size(self, src: PILImage, width: OptInt, height: OptInt, dst_width: int, dst_height: int) -> ImageAndSize:
        thumbnail_path = self.get_thumbnail_path(width, height, dst_width, dst_height)
        dst_size = (dst_width, dst_height)
        last_tk = self.current_tk
        try:
            used_cache, image, tk_image = self._load_or_resize(thumbnail_path, src, dst_size)
            self.current = image
            self.current_tk = tk_image
        except OSError as e:
            log.warning(f'Error resizing image={src}: {e}')
            return src, width, height
        else:
            self.size = dst_size
            if thumbnail_path and not used_cache and not last_tk:  # Only save initial thumbnails, not misc resizes
                self._save_thumbnail(image, thumbnail_path)
            return tk_image, dst_width, dst_height

    @classmethod
    def _load_or_resize(cls, path: Path | None, src: PILImage, dst_size: XY) -> tuple[bool, PILImage, PhotoImage]:
        if path:
            try:
                image = _load_thumbnail(path)
                return True, image, PhotoImage(image)
            except FileNotFoundError:
                pass
            except OSError as e:
                log.debug(f'Error loading cached thumbnail from path={path.as_posix()}: {e}')

        if src.mode == 'P':
            # In this case, Image.resize ignores the resample arg and uses Resampling.NEAREST, so convert to RGB first
            image = src.convert('RGB').resize(dst_size, Resampling.LANCZOS)
        else:
            image = src.resize(dst_size, Resampling.LANCZOS)
        return False, image, PhotoImage(image)

    # endregion

    # region Thumbnail Methods

    @classmethod
    def _save_thumbnail(cls, image: PILImage, path: Path):
        if not (save_fmt := image.format):
            save_fmt = 'png' if image.mode == 'RGBA' else 'jpeg'
        if save_fmt == 'jpeg' and image.mode not in RAWMODE:
            image = image.convert('RGB')
        try:
            with path.open('wb') as f:
                image.save(f, save_fmt)
        except OSError as e:
            log.debug(f'Error saving thumbnail to path={path.as_posix()}: {e}')
        else:
            log.debug(f'Saved thumbnail to {path.as_posix()}')

    def get_thumbnail_path(self, width: OptInt, height: OptInt, dst_width: int, dst_height: int) -> Path | None:
        max_width, max_height = self.max_thumbnail_size
        if (
            not (src_hash := self.src_hash)                                         # Image is None
            or ((width and width > max_width) or (height and height > max_height))  # Too large to save
            or ((width and width < dst_width) or (height and height < dst_height))  # Smaller than target size
            or (width and height and width == dst_width and height == dst_height)   # Already at the target size
        ):
            return None

        # if (width and width > max_width) or (height and height > max_height):
        #     return None
        # elif not (src_hash := self.src_hash) or (width and width < dst_width) or (height and height < dst_height):
        #     return None
        return self._get_thumbnail_dir().joinpath(f'{src_hash}_{width}x{height}_{dst_width}x{dst_height}.thumb')

    @classmethod
    def _get_thumbnail_dir(cls) -> Path:
        try:
            return cls._thumbnail_dir  # noqa
        except AttributeError:
            cls._thumbnail_dir = thumbnail_dir = get_user_temp_dir('tk_gui_thumbnails')
            return thumbnail_dir

    # endregion


@lru_cache(20)
def _load_thumbnail(path: Path) -> PILImage:
    image = open_image(path)
    log.log(9, f'Loaded thumbnail from {path.as_posix()}')
    return image


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
            path = get_image_path(image)
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


def get_size(image: Union[AnimatedType, SevenSegmentDisplay]) -> XY:
    if isinstance(image, Spinner):
        return image.size
    elif isinstance(image, SevenSegmentDisplay):
        return image.time_size()
        # return image.width, image.height
    image = as_image(image)
    return image.size


def _extract_kwargs(kwargs: dict[str, Any], keys: set[str], defaults: dict[str, Any]) -> dict[str, Any]:
    pop = kwargs.pop
    extracted = {key: pop(key) for key in keys.intersection(kwargs)}
    for key, val in defaults.items():
        extracted.setdefault(key, val)

    return extracted
