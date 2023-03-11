"""
Tkinter GUI image popups

:author: Doug Skrypa
"""

from __future__ import annotations

import logging
from concurrent.futures import Future, TimeoutError
from threading import Thread
from typing import TYPE_CHECKING, Optional, Union, Callable, TypeVar, ParamSpec

from PIL.Image import MIME

from tk_gui.caching import cached_property
from tk_gui.elements import Text
from tk_gui.elements.images import AnimatedType, Image, Animation, ClockImage, SpinnerImage, get_size
from tk_gui.event_handling import event_handler
from tk_gui.event_handling.futures import run_func_in_future
from tk_gui.images import as_image
from tk_gui.images.wrapper import ImageWrapper, SourceImage
from .base import Popup

if TYPE_CHECKING:
    from tkinter import Event
    from tk_gui.typing import XY, Layout, ImageType

__all__ = ['ImagePopup', 'AnimatedPopup', 'SpinnerPopup', 'ClockPopup']
log = logging.getLogger(__name__)

_NotSet = object()

P = ParamSpec('P')
T = TypeVar('T')


class NewImagePopup(Popup):
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
        self.src_image = SourceImage.from_image(image)
        self.image = self.src_image

    # region Title

    @property
    def title(self) -> str:
        img_w, img_h = self.image.size
        return f'{self._title} ({img_w}x{img_h}, {self.image.size_percent:.0%})'

    @title.setter
    def title(self, value: str):
        self._title = value

    # endregion

    def __repr__(self) -> str:
        title, src_image = self._title, self.src_image
        return f'<{self.__class__.__name__}[{title=}, {src_image=}]>'

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
            log.debug(f'_init_size: monitor size={(mon_w, mon_h)}')
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


class ImagePopup(Popup):
    _empty: bool = True
    _gui_image: Image = _NotSet
    _last_size: XY
    text: str = None
    text_above_img: bool = True
    orig_size: XY

    def __init__(
        self,
        image: Union[ImageType, AnimatedType],
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
        if self.gui_image is _NotSet:
            # This will only happen for non-cached properties, but it will also (intentionally) force subclasses that
            # usa a cached_property to populate the value immediately.
            self.gui_image = image
        if text:
            self.text = text
            self.text_above_img = text_above_img

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

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}[title={self.title!r}, orig={self.orig_size}, empty: {self._empty}]>'

    def get_pre_window_layout(self) -> Layout:
        image_row = [self.gui_image]
        if text := self.text:
            text_row = [Text(text, side='t')]
            return [text_row, image_row] if self.text_above_img else [image_row, text_row]
        return [image_row]

    @property
    def gui_image(self) -> Image:
        return self._gui_image

    @gui_image.setter
    def gui_image(self, value: ImageType):
        image = as_image(value)
        self._empty = image is None
        self.orig_size = image.size if image else (0, 0)
        self._last_size = init_size = self._init_size()
        self._gui_image = gui_image = Image(value, size=init_size, pad=(2, 2))
        if new_size := _get_new_size(gui_image, *init_size):
            # TODO: init size still needs work - may need to account for title bar size?
            gui_image.size = new_size
        if image:
            log.debug(
                f'{self}: Using {init_size=}, {new_size=} to display {image=}'
                f' with {image.format=} mime={MIME.get(image.format)!r}'
            )

    def _init_size(self) -> XY:
        width, height = self.orig_size
        if monitor := self.get_monitor():
            log.debug(f'_init_size: monitor size={(monitor.width, monitor.height)}')
            return min(monitor.width - 70, width or 0), min(monitor.height - 70, height or 0)
        return width, height

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


def _get_new_size(image: Image, new_w: int, new_h: int) -> XY | None:
    pad_x, pad_y = image.pad
    new_size = (new_w - pad_x * 2 - 2, new_h - pad_y * 2 - 2)
    new_img = image.target_size(*new_size)
    if new_img != image.size:
        return new_size
    return None


class AnimatedPopup(ImagePopup):
    _gui_image: Animation

    @property
    def gui_image(self) -> Animation:
        return self._gui_image

    @gui_image.setter
    def gui_image(self, value: AnimatedType):
        # log.debug(f'_set_image: {image=}')
        self.orig_size = get_size(value) if value else (0, 0)
        self._last_size = init_size = self._init_size()
        self._gui_image = animation = Animation(value, size=init_size, pad=(2, 2))
        self._empty = animation.size == (0, 0)

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


class SpinnerPopup(AnimatedPopup):
    _empty = False

    def __init__(self, *args, img_size: XY = None, **kwargs):
        self._img_size = img_size
        kwargs.setdefault('bind_esc', False)
        kwargs.setdefault('keep_on_top', True)
        kwargs.setdefault('can_minimize', False)
        kwargs.setdefault('no_title_bar', True)
        # kwargs.setdefault('alpha_channel', 0.8)  # This would make it semi-transparent; transparent_color didn't work
        super().__init__(None, *args, **kwargs)

    @cached_property
    def gui_image(self) -> SpinnerImage:
        self.orig_size = self._img_size or SpinnerImage.DEFAULT_SIZE
        self._last_size = init_size = self._init_size()
        return SpinnerImage(size=init_size, pad=(2, 2))


class ClockPopup(AnimatedPopup):
    _empty = False

    def __init__(self, *args, img_size: XY = None, toggle_slim_on_click: bool = False, **kwargs):
        self._img_size = img_size
        self._toggle_slim_on_click = toggle_slim_on_click
        super().__init__(None, *args, **kwargs)

    @cached_property
    def gui_image(self) -> ClockImage:
        kwargs = {'toggle_slim_on_click': self._toggle_slim_on_click, 'pad': (2, 2)}
        if img_size := self._img_size:
            self.orig_size = img_size
            self._last_size = init_size = self._init_size()
            return ClockImage(img_size=init_size, **kwargs)
        else:
            gui_image = ClockImage(**kwargs)
            self.orig_size = self._last_size = gui_image.size
            return gui_image
