"""

"""

from __future__ import annotations

import logging
from abc import ABCMeta
from contextvars import ContextVar
from functools import partial
from typing import TYPE_CHECKING, Any, Callable, Type, Iterator

from tk_gui.caching import cached_property
from tk_gui.enums import BindEvent
from .containers import BindMap
from .mixins import CustomEventResultsMixin

if TYPE_CHECKING:
    from tkinter import Event
    from tk_gui.elements.buttons import Button
    from tk_gui.typing import BindCallback, ButtonEventCB

__all__ = ['event_handler', 'button_handler', 'HandlesEvents']
log = logging.getLogger(__name__)

_stack = ContextVar('tk_gui.event_handling.stack', default=[])


# region Decorators


def event_handler(*binds: str, method: bool = True, add: bool = True) -> Callable[[BindCallback], EventHandler]:
    """
    Decorator that registers the decorated function/method as the handler for the specified bind events.  The function
    must accept a single positional :class:`python:tkinter.Event` argument.
    """
    if not binds:
        raise ValueError('At least one tkinter event key is required to bind to')

    def _event_handler(func):
        # Store in the event_handlers list for the class being defined
        _stack.get()[-1][0].append(EventHandler(func, binds, method, add))
        return func

    return _event_handler


def button_handler(*keys: str, method: bool = True, add: bool = False) -> Callable[[ButtonEventCB], ButtonHandler]:
    """
    Decorator that registers the decorated function/method as the handler for the specified buttons.  The function
    must accept two positional args - a :class:`python:tkinter.Event`, and the key of the :class:`Button` that was
    activated.
    """
    if not keys:
        raise ValueError('At least one Button key is required to bind to')

    def _button_handler(func):
        _stack.get()[-1][1].append(ButtonHandler(func, keys, method, add))
        return func

    return _button_handler


class EventHandler:
    __slots__ = ('handler', 'binds', 'method', 'add')

    def __init__(self, handler: BindCallback, binds: tuple[str, ...], method: bool = True, add: bool = True):
        self.handler = handler
        self.binds = binds
        self.method = method
        self.add = add

    def __repr__(self) -> str:
        binds, method, add = self.binds, self.method, self.add
        return f'<{self.__class__.__name__}[{self.handler}, {binds=}, {method=}, {add=}]>'

    def __iter__(self) -> Iterator[tuple[str, bool]]:
        add = self.add
        for bind in self.binds:
            yield bind, add


class ButtonEventHandler(EventHandler):
    __slots__ = ()

    def __init__(self, handler: BindCallback):
        super().__init__(handler, (BindEvent.BUTTON_CLICKED.value,))


class ButtonHandler(EventHandler):
    __slots__ = ('keys',)

    def __init__(self, handler: ButtonEventCB, keys: tuple[str, ...], method: bool = True, add: bool = False):
        super().__init__(handler, (), method=method, add=add)
        self.keys = keys

    def __repr__(self) -> str:
        keys, method, add = self.binds, self.method, self.add
        return f'<{self.__class__.__name__}[{self.handler}, {keys=}, {method=}, {add=}]>'

    def __iter__(self) -> Iterator[tuple[str, bool]]:
        add = self.add
        for key in self.keys:
            yield key, add


# endregion


class HandlesEventsMeta(ABCMeta, type):
    @classmethod
    def __prepare__(mcs, name: str, bases: tuple[type, ...], **kwargs) -> dict:
        """
        Called before ``__new__`` and before evaluating the contents of a class, which enables the establishment of a
        custom context to handle event handler registration.
        """
        # These lists become the _event_handlers_ and _button_handlers_ class attrs for the HandlesEvents subclass
        _stack.get().append(([], []))
        return {}

    def __new__(mcs, name: str, bases: tuple[type, ...], namespace: dict[str, Any], **kwargs):
        cls = super().__new__(mcs, name, bases, namespace, **kwargs)
        event_handlers, button_handlers = _stack.get().pop()
        try:
            parent_ehs, parent_bhs = cls._event_handlers_, cls._button_handlers_
        except AttributeError:
            cls._event_handlers_, cls._button_handlers_ = event_handlers, button_handlers
        else:
            cls._event_handlers_ = [eh for eh in parent_ehs if not isinstance(eh, ButtonEventHandler)] + event_handlers
            cls._button_handlers_ = parent_bhs + button_handlers

        if cls._button_handlers_:
            try:
                cls._event_handlers_.append(ButtonEventHandler(cls._handle_button_clicked_))  # noqa
            except AttributeError as e:
                raise TypeError(
                    f'Unable to register button handlers for {cls=} - it is missing a _handle_button_clicked_ method'
                ) from e

        return cls

    def event_handler_binds(cls: HandlesEventsMeta, he_obj) -> BindMap:
        return cls._get_bind_map(he_obj, '_event_handlers_')

    def button_handler_binds(cls: HandlesEventsMeta, he_obj) -> BindMap:
        return cls._get_bind_map(he_obj, '_button_handlers_')

    def _get_bind_map(cls: HandlesEventsMeta, he_obj, attr_name: str) -> BindMap:
        bind_map = BindMap()
        for handler in getattr(cls, attr_name):  # type: EventHandler | ButtonHandler
            cb = partial(handler.handler, he_obj) if handler.method else handler.handler
            # log.debug(f'Found {handler=} -> {cb=}', extra={'color': 14})
            for key_or_bind, add in handler:
                bind_map.add(key_or_bind, cb, add)

        return bind_map


class HandlesEvents(metaclass=HandlesEventsMeta):
    _event_handlers_: list[EventHandler]
    _button_handlers_: list[ButtonHandler]
    __button_handler_map = None

    def event_handler_binds(self) -> BindMap:
        cls: HandlesEventsMeta = self.__class__
        return cls.__class__.event_handler_binds(cls, self)

    def button_handler_binds(self) -> BindMap:
        cls: HandlesEventsMeta = self.__class__
        return cls.__class__.button_handler_binds(cls, self)

    @cached_property
    def _button_handler_map(self) -> BindMap:
        if (bh_map := self.__button_handler_map) is None:
            self.__button_handler_map = bh_map = self.button_handler_binds()
        return bh_map

    def _handle_button_clicked_(self, event: Event):
        button_cls: Type[Button] = CustomEventResultsMixin._fqn_cls_map['tk_gui.elements.buttons.Button']
        button: Button = button_cls.get_result(event)
        key = button.key
        try:
            handlers = self._button_handler_map[key]  # noqa
        except KeyError:
            log.debug(f'No button handlers found for {key=}: {self._button_handler_map=}')
            return

        window = button.window
        for handler in handlers:
            result = handler(event, key)
            window._handle_callback_action(result, event, button)
