"""
Tkinter GUI images

:author: Doug Skrypa
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from inspect import Signature
from tkinter import Label, TclError, Event
from typing import TYPE_CHECKING, Optional, Any, Union, Callable

from PIL.Image import Resampling
from PIL.ImageSequence import Iterator as FrameIterator
from PIL.ImageTk import PhotoImage

from tk_gui.enums import Anchor
from tk_gui.images import ImageWrapper, SourceImage, ResizedImage, FrameCycle, PhotoImageCycle, Spinner
from tk_gui.images.clock import SevenSegmentDisplay, ClockCycle
from tk_gui.styles import Style
from tk_gui.widgets.configuration import AxisConfig
from tk_gui.widgets.images import ScrollableImage as ScrollableImageWidget
from .element import Element

if TYPE_CHECKING:
    from tk_gui.pseudo_elements import Row
    from tk_gui.styles.typing import StyleSpec
    from tk_gui.typing import XY, BindTarget, ImageType, Bool, TkContainer, HasFrame

__all__ = ['Image', 'Animation', 'SpinnerImage', 'ClockImage']
log = logging.getLogger(__name__)

ImageCycle = Union[FrameCycle, ClockCycle]


# region Static Images


class BaseImage(Element, ABC, base_style_layer='image'):
    _callback: BindTarget = None
    widget: Label = None
    animated: bool = False
    anchor_image: Anchor = Anchor.NONE

    def __init_subclass__(cls, animated: bool = None, **kwargs):
        super().__init_subclass__(**kwargs)
        if animated is not None:
            cls.animated = animated

    def __init__(self, *, callback: BindTarget = None, anchor_image: Union[str, Anchor] = None, **kwargs):
        """
        :param image: The image to display.
        :param callback: Callback action to perform when the image is clicked (overrides left_click_cb).
        :param kwargs: Additional keyword arguments to pass to :class:`.Element`.
        """
        if cb_provided := callback is not None:
            kwargs['bind_clicks'] = True
        super().__init__(**kwargs)
        if cb_provided:
            self._callback = callback
        if anchor_image:
            self.anchor_image = Anchor(anchor_image)

    @abstractmethod
    def target_size(self, width: int, height: int) -> XY:
        raise NotImplementedError

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

    def _pack_into(self, row: Row, image: PhotoImage, width: int, height: int):
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

    def _re_pack(self, image: PhotoImage, width: int, height: int):
        # log.debug(f'_re_pack: {width=}, {height=}, {self}')
        self.size = (width, height)
        widget: Label = self.widget
        widget.configure(image=image, width=width, height=height, anchor=self.anchor_image.value)
        widget.image = image
        widget.pack(**self.pad_kw)

    # endregion


class SrcImageMixin:
    widget: Label | ScrollableImageWidget
    resize: Callable
    size: XY
    _src_image: SourceImage = None
    _resize_kwargs: dict[str, bool | Resampling | None]

    def init_src_image(
        self,
        image: ImageType | ImageWrapper = None,
        use_cache: bool = False,
        keep_ratio: bool = True,
        resample: Resampling | None = Resampling.LANCZOS,
    ):
        self._resize_kwargs = {'use_cache': use_cache, 'keep_ratio': keep_ratio, 'resample': resample}
        self.image = image

    # region Image Data

    @property
    def image(self) -> Optional[SourceImage]:
        return self._src_image

    @image.setter
    def image(self, data: ImageType | ImageWrapper):
        self._src_image = SourceImage.from_image(data)
        if self.widget is not None:
            self.resize(*self.size)

    # endregion

    def target_size(self, width: int, height: int) -> XY:
        return self._src_image.target_size((width, height), keep_ratio=self._resize_kwargs['keep_ratio'])

    def update(self, image: ImageType | ImageWrapper, size: XY = None):
        if size:
            self.size = size
        self.image = image


class Image(SrcImageMixin, BaseImage):
    popup_title: str = None

    def __init__(
        self,
        image: ImageType | ImageWrapper = None,
        *,
        callback: BindTarget = None,
        popup: Bool = None,
        popup_title: str = None,
        anchor_image: Union[str, Anchor] = None,
        use_cache: bool = False,
        keep_ratio: bool = True,
        resample: Resampling | None = Resampling.LANCZOS,
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
        Element.__init__(self, **kwargs)
        self.init_src_image(image, use_cache=use_cache, keep_ratio=keep_ratio, resample=resample)
        if popup:
            if cb_provided:
                raise TypeError(f"Only one of 'popup' xor 'callback' may be provided for {self.__class__.__name__}")
            self._callback = self._handle_open_popup
            self.popup_title = popup_title
        elif cb_provided:
            self._callback = callback
        if anchor_image:
            self.anchor_image = Anchor(anchor_image)

    # region Widget Init & Packing

    def pack_into(self, row: Row):
        resized = self._src_image.as_size(self.size, **self._resize_kwargs)
        self._pack_into(row, resized.as_tk_image(), *resized.size)

    # endregion

    def resize(self, width: int, height: int) -> ResizedImage:
        resized = self._src_image.as_size((width, height), **self._resize_kwargs)
        self._re_pack(resized.as_tk_image(), *resized.size)
        return resized

    def _handle_open_popup(self, event: Event = None):
        from tk_gui.popups.image import ImagePopup

        src_image = self._src_image
        title = self.popup_title or (src_image.path.name if src_image.path else None)
        ImagePopup(src_image, title, parent=self.window).run()


# endregion


# region Scrollable Image


class ScrollableImage(SrcImageMixin, Element, base_style_layer='image'):
    widget: ScrollableImageWidget = None

    def __init__(
        self,
        image: ImageType | ImageWrapper = None,
        *,
        use_cache: bool = False,
        keep_ratio: bool = True,
        resample: Resampling | None = Resampling.LANCZOS,
        **kwargs,
    ):
        kwargs.setdefault('scroll_x', True)
        kwargs.setdefault('scroll_y', True)
        kwargs.setdefault('scroll_x_amount', 1)
        kwargs.setdefault('scroll_y_amount', 1)
        self.x_config = AxisConfig.from_kwargs('x', kwargs)
        self.y_config = AxisConfig.from_kwargs('y', kwargs)
        kwargs.setdefault('pad', (0, 0))
        Element.__init__(self, **kwargs)
        self.init_src_image(image, use_cache=use_cache, keep_ratio=keep_ratio, resample=resample)

    # def __repr__(self) -> str:
    #     size = self.size
    #     box_map = self.widget.get_boxes()
    #     box_str = '{\n' + ',\n'.join(f'        {k!r}: {v!r}' for k, v in box_map.items()) + '\n    }'
    #     return f'<{self.__class__.__name__}[id={self.id}, {size=}, boxes={box_str}]>'

    # region Widget Init & Packing

    @property
    def style_config(self) -> dict[str, Any]:
        return {
            **self.style.get_map('image', bd='border_width', background='bg', relief='relief'),
            **self._style_config,
        }

    def _init_widget(self, tk_container: TkContainer):
        pass

    def grid_into(self, parent: HasFrame, row: int, column: int, **kwargs):
        raise RuntimeError('Grid is not currently supported for images')

    def pack_into(self, row: Row):
        resized = self._src_image.as_size(self.size, **self._resize_kwargs)
        width, height = size = resized.size
        # log.debug(f'Packing {resized=} into row with {width=}, {height=}')
        kwargs = {
            'width': width,
            'height': height,
            'takefocus': int(self.allow_focus),
            'x_config': self.x_config,
            'y_config': self.y_config,
            'style': self.style,
            **self.style_config,
        }
        self.size = size
        self.widget = ScrollableImageWidget(resized.as_tk_image(), parent=row.frame, **kwargs)
        self.pack_widget()

    # endregion

    def resize(self, width: int, height: int) -> ResizedImage:
        resized = self._src_image.as_size((width, height), **self._resize_kwargs)
        self.size = size = resized.size
        # log.debug(f'resize: {size=}, {self}')
        self.widget.replace_image(resized.as_tk_image(), size)
        return resized


# endregion


# region Animated Images


class BaseAnimation(BaseImage, ABC, animated=True):
    image_cycle: FrameCycle

    def __init__(self, last_frame_num: int = 0, paused: bool = False, *, callback: BindTarget = None, **kwargs):
        Element.__init__(self, **kwargs)
        self._last_frame_num = last_frame_num
        self._next_id = None
        self._run = not paused
        self._callback = callback

    @abstractmethod
    def init_image_cycle(self) -> ImageCycle:
        raise NotImplementedError

    def pack_into(self, row: Row):
        # log.debug(f'pack_into: {self.size=}')
        self.image_cycle = image_cycle = self.init_image_cycle()
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

    @abstractmethod
    def resize(self, width: int, height: int):
        raise NotImplementedError

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


class Animation(BaseAnimation):
    _src_image: SourceImage = None

    def __init__(
        self,
        image: ImageType | ImageWrapper = None,
        last_frame_num: int = 0,
        paused: bool = False,
        *,
        callback: BindTarget = None,
        **kwargs,
    ):
        super().__init__(last_frame_num=last_frame_num, paused=paused, callback=callback, **kwargs)
        self._src_image = SourceImage.from_image(image)

    def init_image_cycle(self) -> ImageCycle:
        src_image = self._src_image
        if path := src_image.path:
            return PhotoImageCycle(path, n=self._last_frame_num)
        else:
            return FrameCycle(tuple(FrameIterator(src_image.pil_image)), PhotoImage, n=self._last_frame_num)

    # region Size & Resize

    def target_size(self, width: int, height: int) -> XY:
        return self._src_image.target_size((width, height))

    def resize(self, width: int, height: int):
        # log.debug(f'resize: {width=}, {height=}, {self}')
        # Note: GIF resizing does not work well with PIL - a different lib is likely necessary
        self._re_pack(next(self.image_cycle)[0], *self._src_image.size)
        if self._run:
            self._cancel()
            self.next()

    # endregion


class SpinnerImage(BaseAnimation):
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
        self.spinner = Spinner(**spinner_kwargs)
        super().__init__(size=size, **kwargs)

    def init_image_cycle(self) -> ImageCycle:
        if size := self.size:
            self.spinner.resize(size)
        return self.spinner.cycle(PhotoImage, n=self._last_frame_num)

    def target_size(self, width: int, height: int) -> XY:
        # TODO: Add support for keeping aspect ratio?
        return width, height

    def resize(self, width: int, height: int):
        # log.debug(f'resize: {width=}, {height=}, {self}')
        spinner = self.spinner
        spinner.resize((width, height))
        self.image_cycle = frame_cycle = spinner.cycle(PhotoImage, n=self.image_cycle.n)
        self._re_pack(next(frame_cycle)[0], *spinner.size)
        if self._run:
            self._cancel()
            self.next()


class ClockImage(BaseAnimation):
    image_cycle: ClockCycle
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
        super().__init__(style=style or Style(bg='black'), **kwargs)
        self._clock_cycle = ClockCycle(clock)

    def toggle_slim(self, event: Event = None):
        slim, clock = self._slim, self.clock
        clock.resize(bar_pct=(clock.bar_pct * (2 if slim else 0.5)), preserve_height=True)
        self._slim = not slim
        self.image_cycle.last_time -= ClockCycle.SECOND

    def init_image_cycle(self) -> ImageCycle:
        frame_cycle = self._clock_cycle
        if size := self.size:
            frame_cycle.clock.resize_full(*size)
            frame_cycle.last_time -= frame_cycle.SECOND
        return frame_cycle

    def target_size(self, width: int, height: int) -> XY:
        return self.clock.calc_resize_width(width, height)[0]

    def resize(self, width: int, height: int):
        # log.debug(f'resize: {width=}, {height=}, {self}')
        self.clock.resize_full(width, height)
        self.image_cycle.last_time -= ClockCycle.SECOND
        self._re_pack(next(self.image_cycle)[0], *self._clock_cycle.size)
        if self._run:
            self._cancel()
            self.next()


# endregion


def _extract_kwargs(kwargs: dict[str, Any], keys: set[str], defaults: dict[str, Any]) -> dict[str, Any]:
    pop = kwargs.pop
    extracted = {key: pop(key) for key in keys.intersection(kwargs)}
    for key, val in defaults.items():
        extracted.setdefault(key, val)

    return extracted
