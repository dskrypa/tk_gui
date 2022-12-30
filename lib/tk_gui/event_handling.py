"""

"""

from __future__ import annotations

import logging
from abc import ABCMeta, ABC
from contextvars import ContextVar
from functools import partial, update_wrapper
from typing import TYPE_CHECKING, Any, Optional, Callable

if TYPE_CHECKING:
    from .typing import BindCallback

__all__ = ['HandlesEventsMeta', 'HandlesEvents', 'event_handler']
log = logging.getLogger(__name__)

_stack = ContextVar('tk_gui.event_handling.stack', default=[])


class EventHandler:
    def __init__(self, handler: BindCallback, binds: tuple[str, ...], method: bool = True):
        self.handler = handler
        self.binds = binds
        self.method = method
        update_wrapper(self, handler)
        _stack.get()[-1].append(self)  # Store in the event_handlers list for the class being defined

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}[{self.handler}, binds={self.binds!r}]>'


def event_handler(*binds: str, method: bool = True) -> Callable[[BindCallback], EventHandler]:
    """
    Decorator that registers the decorated function/method as the handler for the specified bind events.  The function
    must accept a single positional :class:`python:tkinter.Event` argument.
    """
    if not binds:
        raise ValueError('At least one tkinter event key is required to bind to')
    return partial(EventHandler, binds=binds, method=method)


class HandlesEventsMeta(ABCMeta, type):
    @classmethod
    def __prepare__(mcs, name: str, bases: tuple[type, ...], **kwargs) -> dict:
        """
        Called before ``__new__`` and before evaluating the contents of a class, which enables the establishment of a
        custom context to handle event handler registration.
        """
        _stack.get().append([])  # This list becomes the _event_handlers_ class attr for the HandlesEvents subclass
        return {}

    def __new__(mcs, name: str, bases: tuple[type, ...], namespace: dict[str, Any], **kwargs):
        cls = super().__new__(mcs, name, bases, namespace, **kwargs)
        cls._event_handlers_ = _stack.get().pop()
        return cls

    @classmethod
    def get_parent_hem(mcs, cls: HandlesEventsMeta, include_abc: bool = True) -> Optional[HandlesEventsMeta]:
        for parent_cls in type.mro(cls)[1:]:
            if isinstance(parent_cls, mcs) and (include_abc or ABC not in parent_cls.__bases__):
                return parent_cls
        return None

    def event_handler_binds(cls: HandlesEventsMeta, he_obj) -> dict[str, BindCallback]:
        mcs = cls.__class__
        if parent := mcs.get_parent_hem(cls):
            bind_map = mcs.event_handler_binds(parent, he_obj).copy()
        else:
            bind_map = {}

        for handler in cls._event_handlers_:
            target = partial(handler.handler, he_obj) if handler.method else handler.handler
            for bind in handler.binds:
                bind_map[bind] = target

        return bind_map


class HandlesEvents(metaclass=HandlesEventsMeta):
    _event_handlers_: list[EventHandler]

    def event_handler_binds(self) -> dict[str, BindCallback]:
        cls: HandlesEventsMeta = self.__class__
        return cls.__class__.event_handler_binds(cls, self)
