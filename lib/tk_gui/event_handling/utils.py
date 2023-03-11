"""
Utilities that are useful for debugging Tkinter / tk_gui GUIs.

Notes:
    - For an event with multiple bound callbacks, if one returns `'break'`, then remaining callbacks for that event will
      be skipped.
    - `Bind modifiers <https://tcl.tk/man/tcl8.6.13/TkCmd/bind.htm#M6>`__:
        - Control, Alt, Shift, Lock, Extended, Command, Option, Meta / M, Mod[1-5] / M[1-5]
        - Button[1-5] / B[1-5]
        - Double, Triple, Quadruple
    - `Event types <https://tcl.tk/man/tcl8.6.13/TkCmd/bind.htm#M7>`__:
        - ButtonPress / Button, ButtonRelease, MouseWheel, Motion
        - KeyPress / Key, KeyRelease
        - Activate, Deactivate, Enter, Leave, FocusIn, FocusOut
        - Configure, Destroy, Visibility
"""

from __future__ import annotations

import logging
from functools import partial
from time import monotonic
from tkinter import TclError, BaseWidget, Misc, Event
from typing import TYPE_CHECKING, Mapping, Any, Union

from tk_gui.widgets.utils import unbind, log_event_widget_data, get_widget_ancestor

if TYPE_CHECKING:
    from tk_gui.elements.element import ElementBase, Element
    from tk_gui.typing import Color, SupportsBind, Bool, XY

__all__ = ['ClickHighlighter', 'Interrupt', 'MotionTracker']
log = logging.getLogger(__name__)


class Interrupt:
    __slots__ = ('time', 'event', 'element')

    def __init__(self, event: Event = None, element: Union[ElementBase, Element] = None, time: float = None):
        self.time = monotonic() if time is None else time
        self.event = event
        self.element = element

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}@{self.time}[event={self.event!r}, element={self.element}]>'


class MotionTracker:
    __slots__ = ('start_pos', 'mouse_pos')

    def __init__(self, start_pos: XY, event: Event):
        self.start_pos = start_pos
        self.mouse_pos = self._mouse_position(event)

    @classmethod
    def _mouse_position(cls, event: Event) -> XY:
        widget: BaseWidget = event.widget
        x = event.x + widget.winfo_rootx()
        y = event.y + widget.winfo_rooty()
        return x, y

    def new_position(self, event: Event) -> XY:
        src_x, src_y = self.start_pos
        old_x, old_y = self.mouse_pos
        new_x, new_y = self._mouse_position(event)
        return src_x + (new_x - old_x), src_y + (new_y - old_y)


class ClickHighlighter:
    """
    Highlights the clicked widget using the specified color while the specified mouse button is down, then restores the
    original color upon button release.  Uses the background, red, and button 1 (left click) by default.
    """
    __slots__ = (
        'modifier', 'button_num', 'color', 'attr', '_widget_data', '_bind_id', 'log_event', 'log_event_kwargs', 'level'
    )

    def __init__(
        self,
        *,
        color: Color = '#ff0000',
        button_num: int = 1,
        attr: str = 'background',
        modifier: str = None,
        log_event: Bool = False,
        log_event_kwargs: Mapping[str, Any] = None,
        level: int = 0,
    ):
        self.modifier = modifier
        self.button_num = button_num
        self.color = color
        self.attr = attr
        self._widget_data = {}
        self._bind_id = None
        self.log_event = log_event
        self.log_event_kwargs = log_event_kwargs
        self.level = level

    # region Register / Unregister

    def register(self, supports_bind: SupportsBind):
        self._bind_id = supports_bind.bind(self.press_key, self.on_button_down, add=True)

    def unregister(self, supports_bind: SupportsBind):
        if bind_id := self._bind_id:
            # log.debug(f'Unbinding event={self.press_key!r} with {bind_id=}')
            if isinstance(supports_bind, Misc):
                unbind(supports_bind, self.press_key, bind_id)
            else:
                supports_bind.unbind(self.press_key, bind_id)
            self._bind_id = None

    # endregion

    # region Bind Sequence

    def _key(self, action: str):
        if modifier := self.modifier:
            return f'<{modifier}-{action}-{self.button_num}>'
        return f'<{action}-{self.button_num}>'

    @property
    def press_key(self) -> str:
        return self._key('ButtonPress')

    @property
    def release_key(self) -> str:
        return self._key('ButtonRelease')

    # endregion

    def _maybe_log_event(self, event: Event, widget: BaseWidget = None):
        if not self.log_event:
            return
        kwargs = {'window': None}
        if extra_kwargs := self.log_event_kwargs:
            kwargs.update(extra_kwargs)

        log_event_widget_data(event=event, widget=widget, **kwargs)

    # region Event Handling

    def _get_widget(self, event: Event) -> tuple[BaseWidget, BaseWidget]:
        orig_widget = widget = event.widget
        if level := self.level:
            widget = get_widget_ancestor(widget, level, permissive=True)
        return orig_widget, widget

    def on_button_down(self, event: Event):
        try:
            orig_widget, widget = self._get_widget(event)
        except (AttributeError, TclError):
            self._maybe_log_event(event)
            return
        self._maybe_log_event(event, widget)
        try:
            old_widget_color = widget.configure()[self.attr][-1]
        except KeyError:
            return
        widget.configure({self.attr: self.color})

        release_bind_id = orig_widget.bind(self.release_key, partial(self.on_button_release, orig_widget), add=True)

        self._widget_data[orig_widget] = (old_widget_color, release_bind_id, widget)

    def on_button_release(self, orig_widget: BaseWidget, event: Event = None):
        try:
            old_widget_color, release_bind_id, widget = self._widget_data.pop(orig_widget)
        except KeyError:
            return
        widget.configure({self.attr: old_widget_color})
        # log.debug(f'Unbinding event={self.release_key!r} with {release_bind_id=}')
        unbind(orig_widget, self.release_key, release_bind_id)

    # endregion
