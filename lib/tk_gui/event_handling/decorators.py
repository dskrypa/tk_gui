"""
Decorators for facilitating common event handling tasks.
"""

from __future__ import annotations

import logging
from functools import partial
from typing import TYPE_CHECKING, Any, Callable, Union, Type, TypeVar

if TYPE_CHECKING:
    from tkinter import Event, BaseWidget
    from tk_gui.enums import BindEvent
    from tk_gui.typing import BindCallback
    from tk_gui.window import Window

__all__ = ['delayed_event_handler']
log = logging.getLogger(__name__)

C = TypeVar('C')
BindMethod = Callable[[C, 'Event'], Any]


class DelayedEventHandler:
    """
    Wrapper for callbacks that handle events like ``<Configure>`` that are triggered frequently within a short time
    span.  The most frequently the decorated method may be called is ``delay_ms`` milliseconds.  When the callback is
    triggered multiple times within that time span, the timer is reset, and the method is re-registered to be actually
    called ``delay_ms`` milliseconds from then.
    """
    # TODO: `jump`? https://www.tcl-lang.org/man/tcl8.6.14/TkCmd/options.htm#M-jump

    __slots__ = ('name', 'cb_id_attr', 'widget_attr', 'delay_ms', 'func', 'window_root')

    def __init__(self, func: BindMethod, widget_attr: str = None, delay_ms: int = 200, window_root: bool = False):
        if window_root and widget_attr:
            raise TypeError(f'Invalid param combo - {widget_attr=} is not supported with {window_root=}')
        self.widget_attr = widget_attr
        self.delay_ms = delay_ms
        self.func = func
        self.window_root = window_root

    def __set_name__(self, owner: Type[C], name: str):
        self.name = name
        self.cb_id_attr = f'__{name}_cb_id'

    def __repr__(self) -> str:
        func, widget_attr, delay_ms, window_root = self.func, self.delay_ms, self.delay_ms, self.window_root
        return f'<{self.__class__.__name__}({func=}, {widget_attr=}, {delay_ms=}, {window_root=})>'

    def __get__(self, instance: C, owner: Type[C]) -> DelayedEventHandler | BindCallback:
        if instance is None:
            return self
        return partial(self.handle_event, instance)

    def __call__(self, instance: C, *args, **kwargs):
        return self.handle_event(instance, *args, **kwargs)

    def _find_widget_and_cancel(self, instance: C) -> tuple[BaseWidget, Callable[[int | str], Any]]:
        if widget_attr := self.widget_attr:
            widget: BaseWidget = getattr(instance, widget_attr)
            return widget, widget.after_cancel
        elif self.window_root:
            widget: BaseWidget = instance.window.root
            return widget, widget.after_cancel

        try:
            return instance, instance.after_cancel
        except AttributeError:
            pass

        try:
            widget = instance.widget
            after_cancel = widget.after_cancel
        except AttributeError:
            pass
        else:
            self.widget_attr = 'widget'
            return widget, after_cancel

        try:
            widget = instance.window.root
        except AttributeError:
            pass
        else:
            self.window_root = True
            return widget, widget.after_cancel

        raise TypeError(f'No widget attribute was found in instance with type={instance.__class__.__name__}')

    def handle_event(self, instance: C, event: Event):
        widget, after_cancel = self._find_widget_and_cancel(instance)
        attrs = instance.__dict__
        if cb_id := attrs.get(self.cb_id_attr):
            after_cancel(cb_id)

        attrs[self.cb_id_attr] = widget.after(self.delay_ms, self.handle_callback, instance, event)

    def handle_callback(self, instance: C, event: Event):
        instance.__dict__[self.cb_id_attr] = None
        self.func(instance, event)


def delayed_event_handler(
    func: BindMethod = None, *, widget_attr: str = None, delay_ms: int = 200, window_root: bool = False
) -> DelayedEventHandler | Callable[[BindMethod], DelayedEventHandler]:
    # TODO: Maybe refactor to just look at a Window attr to determine whether initialization is done or not?
    if func is not None:
        return DelayedEventHandler(func, widget_attr, delay_ms, window_root)

    def _delayed_event_handler(method: BindMethod) -> DelayedEventHandler:
        return DelayedEventHandler(method, widget_attr, delay_ms, window_root)

    return _delayed_event_handler


def _tk_event_handler(tk_event: Union[str, BindEvent], always_bind: bool = False):
    return partial(_TkEventHandler, tk_event, always_bind)


class _TkEventHandler:
    __slots__ = ('tk_event', 'func', 'always_bind')

    def __init__(self, tk_event: Union[str, BindEvent], always_bind: bool, func: BindCallback):
        self.tk_event = tk_event
        self.always_bind = always_bind
        self.func = func

    def __set_name__(self, owner: Type[Window], name: str):
        bind_event = self.tk_event
        try:
            event = bind_event.event
        except AttributeError:
            event = bind_event
        owner._tk_event_handlers[event] = name
        if self.always_bind:
            owner._always_bind_events.add(bind_event)
        setattr(owner, name, self.func)  # replace wrapper with the original function
        try:
            self.func.__set_name__(owner, name)  # noqa
        except AttributeError:
            pass
