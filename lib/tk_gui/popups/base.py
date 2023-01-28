r"""
Tkinter GUI base popups

:author: Doug Skrypa
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from concurrent.futures import Future
from queue import Queue
from threading import current_thread, main_thread
from typing import TYPE_CHECKING, Union, Collection, Mapping, Callable, Any

from tk_gui.caching import cached_property
from ..elements import Button, Text, Image, Multiline
from ..event_handling import HandlesEvents, BindMap
from ..positioning import positioner
from ..styles import Style, StyleSpec
from ..utils import max_line_len
from ..window import Window

if TYPE_CHECKING:
    from tkinter import Event
    from screeninfo import Monitor
    from ..typing import XY, Layout, Bool, ImageType, Key

__all__ = ['Popup', 'POPUP_QUEUE', 'BasicPopup']
log = logging.getLogger(__name__)

_NotSet = object()
POPUP_QUEUE = Queue()


class BasePopup(ABC):
    __slots__ = ('title', 'parent', 'return_focus')

    _default_title: str = None
    _return_focus: Bool = True
    title: str | None
    parent: Window | None
    return_focus: Bool

    def __init_subclass__(cls, title: str = None, return_focus: Bool = None, **kwargs):
        super().__init_subclass__(**kwargs)
        if title:
            cls._default_title = title
        if return_focus is not None:
            cls._return_focus = return_focus

    def __init__(self, title: str = None, parent: Window = _NotSet, return_focus: Bool = None):
        self.title = title or self._default_title
        if parent is _NotSet:
            if (active := Window.get_active_windows(False)) and (len(active) == 1):
                parent = active[0]
            else:
                parent = None
        self.parent = parent
        self.return_focus = self._return_focus if return_focus is None else return_focus

    @classmethod
    def as_callback(cls, *args, **kwargs) -> Callable:
        def callback(event: Event = None):
            return cls(*args, **kwargs).run()

        return callback

    @abstractmethod
    def _run(self) -> dict[Key, Any]:
        raise NotImplementedError

    def _get_monitor(self) -> Monitor | None:
        if parent := self.parent:
            return positioner.get_monitor(*parent.position)
        else:
            return positioner.get_monitor(0, 0)

    def run(self):
        if current_thread() == main_thread():
            result = self._run()
        else:
            future = Future()
            POPUP_QUEUE.put((future, self._run, (), {}))
            result = future.result()

        if self.return_focus and (parent := self.parent):
            # log.debug(f'Returning focus to {parent=}')
            parent.take_focus()
        return result


class Popup(BasePopup, HandlesEvents):
    def __init__(
        self,
        layout: Layout = (),
        title: str = None,
        *,
        parent: Window = _NotSet,
        bind_esc: Bool = False,
        keep_on_top: Bool = False,
        can_minimize: Bool = False,
        return_focus: Bool = None,
        **kwargs
    ):
        super().__init__(title, parent, return_focus)
        self.layout = layout
        kwargs['keep_on_top'] = keep_on_top
        kwargs['can_minimize'] = can_minimize
        binds = BindMap.pop_and_normalize(kwargs) | self.event_handler_binds()
        if bind_esc:
            binds.add('<Escape>', 'exit')
        if binds:
            kwargs['binds'] = binds
        self.window_kwargs = kwargs

    def get_layout(self) -> Layout:
        return self.layout

    def prepare_window(self) -> Window:
        return Window(self.get_layout(), title=self.title, is_popup=True, **self.window_kwargs)

    @cached_property
    def window(self) -> Window:
        window = self.prepare_window()
        if parent := self.parent:
            window.move_to_center(parent)
        return window

    def _run(self) -> dict[Key, Any]:
        with self.window(take_focus=True) as window:
            window.run()
            return window.results


class BasicPopup(Popup):
    def __init__(
        self,
        text: str,
        *,
        button: Union[str, Button] = None,
        buttons: Union[Mapping[str, str], Collection[str], Collection[Button]] = None,
        multiline: Bool = None,
        style: StyleSpec = None,
        image: ImageType = None,
        image_size: XY = None,
        text_kwargs: dict[str, Any] = None,
        **kwargs,
    ):
        if buttons and button:
            raise ValueError('Use "button" or "buttons", not both')
        elif not buttons and not button:
            button = 'OK'
        super().__init__(**kwargs)
        self.text = text
        self.buttons = (button,) if button else buttons
        self.multiline = '\n' in text if multiline is None else multiline
        self.style = Style.get_style(style)
        self.image = image
        self.image_size = image_size or (100, 100)
        self.text_kwargs = text_kwargs or {}

    @cached_property
    def lines(self) -> list[str]:
        return self.text.splitlines()

    @cached_property
    def text_size(self) -> XY:
        if size := self.window_kwargs.pop('size', None):
            return size
        lines = self.lines
        n_lines = len(lines)
        if self.multiline:
            monitor = self._get_monitor()
            lines_to_show = max(1, min(monitor.height // self.style.char_height(), n_lines) + 1)
        else:
            lines_to_show = 1

        return max_line_len(lines), lines_to_show

    def prepare_buttons(self) -> Collection[Button]:
        buttons = self.buttons
        if all(isinstance(button, Button) for button in buttons):
            return buttons

        n_buttons = len(buttons)
        if n_buttons == 1:
            sides = ('right',)
            anchors = (None,)
        elif n_buttons == 2:
            sides = ('left', 'right')
            anchors = (None, None)
        elif n_buttons == 3:
            sides = ('left', 'left', 'left')
            # TODO: These anchor values are probably wrong - anchor affects the text within the buttons, not where the
            #  buttons are placed.
            anchors = ('left', 'center', 'right')
        else:
            sides = anchors = ('left' for _ in buttons)

        # log.debug(f'Preparing {buttons=} with {anchors=}, {sides=}')
        if isinstance(buttons, Mapping):
            buttons = [Button(v, key=k, anchor=a, side=s) for a, s, (k, v) in zip(anchors, sides, buttons.items())]
        else:
            buttons = [Button(val, key=val, anchor=a, side=s) for a, s, val in zip(anchors, sides, buttons)]

        return buttons

    def prepare_text(self) -> Layout:
        if self.multiline:
            width, height = size = self.text_size
            text_kwargs = self.text_kwargs.copy()
            text_kwargs.setdefault('size', size)
            text_kwargs.setdefault('read_only_style', True)
            text_kwargs.setdefault('scroll_y', len(self.lines) > height)
            text = Multiline(self.text, read_only=True, **text_kwargs)
        else:
            text = Text(self.text, **self.text_kwargs)

        if image := self.image:
            yield [Image(image, size=self.image_size), text]
        else:
            yield [text]

    def get_layout(self) -> Layout:
        yield from self.prepare_text()
        yield self.prepare_buttons()
