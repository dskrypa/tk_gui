r"""
Tkinter GUI base popups

:author: Doug Skrypa
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from threading import current_thread, main_thread
from typing import TYPE_CHECKING, Union, Collection, Mapping, Callable, Any

from tk_gui.caching import cached_property
from tk_gui.elements import Button, Text, Image, Multiline
from tk_gui.event_handling.futures import TkFuture
from tk_gui.styles import Style
from tk_gui.utils import max_line_len
from tk_gui.views.base import ViewWindowInitializer
from tk_gui.window import Window

if TYPE_CHECKING:
    from tkinter import Event
    from tk_gui.event_handling import BindMap
    from tk_gui.styles.typing import StyleSpec
    from tk_gui.typing import XY, Layout, Bool, ImageType

__all__ = ['Popup', 'BasicPopup', 'AnyPopup']
log = logging.getLogger(__name__)

_NotSet = object()


class PopupMixin(ABC):
    return_focus: Bool = True
    parent: Window | None

    def __init_subclass__(cls, return_focus: Bool = None, **kwargs):
        super().__init_subclass__(**kwargs)
        if return_focus is not None:
            cls.return_focus = return_focus

    @classmethod
    def as_callback(cls, *args, **kwargs) -> Callable:
        def callback(event: Event = None):
            return cls(*args, **kwargs).run()  # noqa

        return callback

    @abstractmethod
    def _run(self):
        raise NotImplementedError

    def run(self):
        if in_main_thread := current_thread() == main_thread():
            log.debug(f'Running popup={self!r} directly in the main thread')
            result = self._run()
        elif not (parent := self.parent):
            raise RuntimeError(f'Unable to run {self!r} with no parent Window')
        else:
            log.debug(f'Enqueueing threaded popup={self!r} with {parent=}')
            result = TkFuture.submit(parent, self._run).result()
            log.debug(f'Got threaded popup={self!r} {result=}')

        if in_main_thread and self.return_focus and (parent := self.parent):
            # log.debug(f'Returning focus to {parent=}')
            try:
                parent.take_focus()
            except AttributeError:  # Parent was already closed
                pass

        return result


class BasePopup(PopupMixin, ABC):
    _default_title: str = None
    title: str | None

    def __init_subclass__(cls, title: str = None, **kwargs):
        super().__init_subclass__(**kwargs)
        if title:
            cls._default_title = title

    def __init__(self, title: str = None, parent: Window = _NotSet, return_focus: Bool = None):
        self.title = title or self._default_title
        if parent is _NotSet:
            parent = Window.get_active_window()
        # else:
        #     log.debug(f'Popup parent window was explicitly provided: {parent}', extra={'color': 13})
        self.parent = parent
        if return_focus is not None:
            self.return_focus = return_focus

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}[title={self.title!r}]>'


class Popup(PopupMixin, ViewWindowInitializer, is_popup=True):
    def __init__(
        self,
        layout: Layout = (),
        title: str = None,
        *,
        bind_esc: Bool = False,
        keep_on_top: Bool = False,
        can_minimize: Bool = False,
        modal: Bool = True,
        return_focus: Bool = None,
        **kwargs
    ):
        kwargs['keep_on_top'] = keep_on_top
        kwargs['can_minimize'] = can_minimize
        kwargs['modal'] = modal
        super().__init__(title=title, **kwargs)
        if return_focus is not None:
            self.return_focus = return_focus
        self._bind_esc = bind_esc
        self.layout = layout

    def _get_bind_map(self) -> BindMap:
        bind_map = super()._get_bind_map()
        if self._bind_esc:
            bind_map.add('<Escape>', 'exit')
        return bind_map

    def get_pre_window_layout(self) -> Layout:
        return self.layout

    def run_window(self):
        # Runs the window.  May be overridden in subclasses to implement custom run behavior
        self.window.run()

    def _run(self):
        with self.finalize_window()(take_focus=True) as window:
            self.run_window()
            self.cleanup()
            return self.get_results()

    def __enter__(self) -> Popup:
        self.finalize_window()(take_focus=True)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.window.close()


class BasicPopup(Popup):
    def __init__(
        self,
        text: Any,
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
            raise TypeError('Use "button" or "buttons", not both')
        elif not buttons and not button:
            button = 'OK'
        super().__init__(**kwargs)
        text = str(text)
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
            return size  # type: ignore
        lines = self.lines
        n_lines = len(lines)
        if self.multiline:
            work_area = self.get_monitor().work_area
            lines_to_show = max(1, min(work_area.height // self.style.char_height(), n_lines) + 1)
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

    def get_pre_window_layout(self) -> Layout:
        yield from self.prepare_text()
        yield self.prepare_buttons()


AnyPopup = Union[BasePopup, Popup]
