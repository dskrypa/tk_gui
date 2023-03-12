"""
Tkinter GUI image popups

:author: Doug Skrypa
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from concurrent.futures import Future, TimeoutError
from threading import Thread
from typing import TYPE_CHECKING, Optional, Callable, TypeVar, ParamSpec

from tk_gui.caching import cached_property
from tk_gui.elements import Text
from tk_gui.elements.images import Image, BaseImage, BaseAnimation, Animation, ClockImage, SpinnerImage
from tk_gui.event_handling import event_handler
from tk_gui.event_handling.futures import run_func_in_future
from tk_gui.images.wrapper import ImageWrapper, SourceImage
from .base import Popup

if TYPE_CHECKING:
    from tkinter import Event
    from tk_gui.typing import XY, Layout, ImageType

__all__ = ['ImagePopup', 'AnimatedPopup', 'SpinnerPopup', 'ClockPopup']
log = logging.getLogger(__name__)

P = ParamSpec('P')
T = TypeVar('T')


class ImagePopup(Popup):
    _last_size: XY = None
    src_image: SourceImage
    text: str = None
    text_above_img: bool = True

    def __init__(
        self,
        image: ImageType | ImageWrapper,
        title: str = None,
        *,
        text: str = None,
        text_above_img: bool = True,
        **kwargs,
    ):
        kwargs.setdefault('margins', (0, 0))
        kwargs.setdefault('bind_esc', True)
        kwargs.setdefault('keep_on_top', False)
        kwargs.setdefault('can_minimize', True)
        super().__init__(title=title or 'Image', **kwargs)
        if text:
            self.text = text
            self.text_above_img = text_above_img
        # TODO: Init may be setting smaller images a few % larger than 100% unnecessarily?
        self.src_image = SourceImage.from_image(image)
        self.image = self.src_image

    # region Title

    @property
    def title(self) -> str:
        return f'{self._title} ({self.image.size_str}, {self.image.size_percent:.0%})'

    @title.setter
    def title(self, value: str):
        self._title = value

    # endregion

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}[title={self._title!r}, src_image={self.src_image!r}]>'

    def get_pre_window_layout(self) -> Layout:
        image_row = [self.gui_image]
        if text := self.text:
            text_row = [Text(text, side='t')]
            return [text_row, image_row] if self.text_above_img else [image_row, text_row]
        else:
            return [image_row]

    @cached_property
    def gui_image(self) -> Image:
        init_size = self._init_size()
        src = self.src_image
        if src.pil_image:
            log.debug(f'{self}: Using {init_size=} to display image={src!r} with {src.format=} mime={src.mime_type!r}')
        self.image = image = src.as_size(init_size)
        return Image(image, size=init_size, pad=(2, 2))

    def _init_size(self) -> XY:
        src_w, src_h = self.src_image.size
        if monitor := self.get_monitor():
            mon_w, mon_h = monitor.work_area.size
            # log.debug(f'_init_size: monitor size={(mon_w, mon_h)}')
            return min(mon_w - 60, src_w), min(mon_h - 60, src_h)
        return src_w, src_h

    @event_handler('SIZE_CHANGED')
    def handle_size_changed(self, event: Event, size: XY):
        if not self.src_image.pil_image or self._last_size == size:
            # log.debug(f'Ignoring config {event=} {size=} for {self}')
            return
        self._last_size = size
        if new_size := _get_new_size(self.gui_image, *size):
            # log.debug(f'Handling config {event=} {size=} for {self}')
            self.image = self.gui_image.resize(*new_size)
            self.window.set_title(self.title)
        # else:
        #     log.debug(f'No change necessary for config {event=} {size=} for {self}')


def _get_new_size(image: BaseImage, new_w: int, new_h: int) -> XY | None:
    pad_x, pad_y = image.pad
    new_size = (new_w - pad_x * 2 - 2, new_h - pad_y * 2 - 2)
    new_img = image.target_size(*new_size)
    if new_img != image.size:
        return new_size
    return None


class BaseAnimatedPopup(Popup, ABC):
    gui_image: BaseAnimation
    _empty: bool = True
    _last_size: XY
    orig_size: XY
    text: str = None
    text_above_img: bool = True

    def __init__(self, title: str = None, *, text: str = None, text_above_img: bool = True, **kwargs):
        kwargs.setdefault('margins', (0, 0))
        kwargs.setdefault('bind_esc', True)
        kwargs.setdefault('keep_on_top', False)
        kwargs.setdefault('can_minimize', True)
        super().__init__(title=title or 'Image', **kwargs)
        self.gui_image = self.init_gui_image()
        if text:
            self.text = text
            self.text_above_img = text_above_img

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}[title={self.title!r}, orig={self.orig_size}]>'

    @abstractmethod
    def init_gui_image(self) -> BaseAnimation:
        raise NotImplementedError

    # region Title

    @property
    def title(self) -> str:
        try:
            img_w, img_h = self.gui_image.size
        except TypeError:
            return self._title
        else:
            src_w, src_h = self.orig_size
            return f'{self._title} ({img_w}x{img_h}, {img_w / src_w if src_w else 1:.0%})'

    @title.setter
    def title(self, value: str):
        self._title = value

    # endregion

    def get_pre_window_layout(self) -> Layout:
        image_row = [self.gui_image]
        if text := self.text:
            text_row = [Text(text, side='t')]
            return [text_row, image_row] if self.text_above_img else [image_row, text_row]
        return [image_row]

    def _init_size(self) -> XY:
        src_w, src_h = self.orig_size
        if monitor := self.get_monitor():
            mon_w, mon_h = monitor.work_area.size
            # log.debug(f'_init_size: monitor size={(mon_w, mon_h)}')
            return min(mon_w - 60, src_w), min(mon_h - 60, src_h)
        return src_w, src_h

    def _get_new_size(self, new_w: int, new_h: int) -> Optional[XY]:
        # image = self.gui_image
        # px, py = image.pad
        # new_size = (new_w - px * 2 - 2, new_h - py * 2 - 2)
        # new_img = image.target_size(*new_size)
        # if new_img != image.size:
        #     # log.debug(
        #     #     f'Resizing from old_win={self._last_size} to new_win={(new_w, new_h)},'
        #     #     f' old_img={image.size} to {new_img=}, using {new_size=} due to event for {self}'
        #     # )
        #     return new_size
        # # log.debug(
        # #     f'Not resizing: old_win={self._last_size}, new_win={(new_w, new_h)},'
        # #     f' old_img={image.size} == {new_img=}, using {new_size=} for {self}'
        # # )
        # return None
        return _get_new_size(self.gui_image, new_w, new_h)

    @event_handler('SIZE_CHANGED')
    def handle_size_changed(self, event: Event, size: XY):
        if self._empty or self._last_size == size:
            # log.debug(f'Ignoring config {event=} for {self} @ {monotonic()}')
            return
        # log.debug(f'Handling config {event=} for {self}')
        if new_size := self._get_new_size(*size):
            self._last_size = size
            self.gui_image.resize(*new_size)
            self.window.set_title(self.title)

    def play_animation(self, event: Event = None):
        self.gui_image.play()

    def stop_animation(self, event: Event = None):
        self.gui_image.stop()

    def run_task_in_thread(self, func: Callable[P, T], args: P.args = (), kwargs: P.kwargs = None) -> T:
        """
        Primarily intended to be used with spinner animations.  Starts a Thread with the function as the target.  Once
        the function is complete, the animation stops, and the value returned by the function is returned.  If an
        exception was raised by the function, then it will be raised after the animation has been stopped.

        :param func: The function to call in a thread.
        :param args: Positional arguments to pass to that function.
        :param kwargs: Keyword arguments to pass to that function.
        :return: The return value from that function.
        """
        future = Future()
        func_thread = Thread(target=run_func_in_future, args=(future, func, args, kwargs), daemon=True)
        with self:
            window = self.window
            func_thread.start()
            while True:
                try:
                    return future.result(0.05)
                except TimeoutError:
                    window.update()


class AnimatedPopup(BaseAnimatedPopup):
    src_image: SourceImage
    gui_image: Animation

    def __init__(
        self,
        image: ImageType | ImageWrapper,
        title: str = None,
        *,
        text: str = None,
        text_above_img: bool = True,
        **kwargs,
    ):
        self.src_image = SourceImage.from_image(image)
        super().__init__(title=title, text=text, text_above_img=text_above_img, **kwargs)

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}[title={self.title!r}, orig={self.orig_size}, empty={self._empty}]>'

    def init_gui_image(self) -> Animation:
        self.orig_size = self.src_image.size
        self._last_size = init_size = self._init_size()
        animation = Animation(self.src_image, size=init_size, pad=(2, 2))
        self._empty = animation.size == (0, 0)
        return animation


class SpinnerPopup(BaseAnimatedPopup):
    gui_image: SpinnerImage
    _empty = False

    def __init__(self, *args, img_size: XY = None, **kwargs):
        self._img_size = img_size
        kwargs.setdefault('bind_esc', False)
        kwargs.setdefault('keep_on_top', True)
        kwargs.setdefault('can_minimize', False)
        kwargs.setdefault('no_title_bar', True)
        # kwargs.setdefault('alpha_channel', 0.8)  # This would make it semi-transparent; transparent_color didn't work
        super().__init__(*args, **kwargs)

    def init_gui_image(self) -> SpinnerImage:
        self.orig_size = self._img_size or SpinnerImage.DEFAULT_SIZE
        self._last_size = init_size = self._init_size()
        return SpinnerImage(size=init_size, pad=(2, 2))


class ClockPopup(BaseAnimatedPopup):
    gui_image: ClockImage
    _empty = False

    def __init__(self, *args, img_size: XY = None, toggle_slim_on_click: bool = False, **kwargs):
        self._img_size = img_size
        self._toggle_slim_on_click = toggle_slim_on_click
        kwargs.setdefault('style', {'bg': '#000000'})
        super().__init__(*args, **kwargs)

    def init_gui_image(self) -> ClockImage:
        kwargs = {'toggle_slim_on_click': self._toggle_slim_on_click, 'pad': (2, 2)}
        if img_size := self._img_size:
            self.orig_size = img_size
            self._last_size = init_size = self._init_size()
            return ClockImage(img_size=init_size, **kwargs)
        else:
            gui_image = ClockImage(**kwargs)
            self.orig_size = self._last_size = gui_image.size
            return gui_image
