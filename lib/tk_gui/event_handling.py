"""

"""

from __future__ import annotations

import logging
from abc import ABCMeta, ABC
from collections.abc import MutableMapping, ItemsView, KeysView, ValuesView, Iterable
from contextvars import ContextVar
from functools import partial, update_wrapper
from itertools import count
from tkinter import TclError, BaseWidget, Event
from typing import TYPE_CHECKING, Any, Optional, Callable, Mapping, Collection, Iterator, Type

from .caching import cached_property
from .enums import BindEvent
from .typing import BindCallback, ButtonEventCB, Bindable, BindTarget, Bool

if TYPE_CHECKING:
    from .elements.buttons import Button

__all__ = [
    'BindMap', 'BindMixin', 'HandlesEventsMeta', 'HandlesEvents', 'event_handler', 'BindManager', 'button_handler'
]
log = logging.getLogger(__name__)

_stack = ContextVar('tk_gui.event_handling.stack', default=[])

_BindVal = BindTarget | Collection[BindTarget]
BindMapping = Mapping[Bindable, _BindVal]


class BindMap(MutableMapping[Bindable, list[BindTarget]]):
    __slots__ = ('_data',)
    # TODO: This should probably be renamed to something like MultiValDict or similar

    def __init__(self, binds: BindMapping | BindMap = None, **kwargs: _BindVal):
        self._data = {}
        self._update(binds, kwargs, True)

    def __getitem__(self, item: Bindable) -> list[BindTarget]:
        return self._data[item]

    def __setitem__(self, key: Bindable, value: BindTarget | Collection[BindTarget]):
        self._set(key, value, False)

    def __delitem__(self, key: Bindable):
        del self._data[key]

    def __len__(self) -> int:
        """The number of events for which callbacks have been registered"""
        return len(self._data)

    def __iter__(self):
        yield from self._data

    def __or__(self, other: BindMapping | BindMap) -> BindMap:
        """
        Return the union of this BindMap and ``other``, based on `PEP-584 <https://peps.python.org/pep-0584/>`__.
        """
        if not isinstance(other, Mapping):
            return NotImplemented
        clone = self.copy()
        clone.update_add(other)
        return clone

    def __ior__(self, other: BindMapping | BindMap) -> BindMap:
        self.update_add(other)
        return self

    def __ror__(self, other: BindMapping | BindMap) -> BindMap:
        if not isinstance(other, Mapping):
            return NotImplemented
        obj = BindMap(other)
        obj.update_add(self)
        return obj

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({self._data})'

    def copy(self) -> BindMap:
        clone = BindMap()
        clone._data = {k: v[:] for k, v in self._data.items()}
        return clone

    def keys(self) -> KeysView[Bindable]:
        return self._data.keys()

    def values(self) -> ValuesView[list[BindTarget]]:
        return self._data.values()

    def items(self) -> ItemsView[Bindable, list[BindTarget]]:
        return self._data.items()

    def clear(self):
        self._data.clear()

    def flat_items(self) -> Iterator[tuple[Bindable, BindTarget]]:
        for key, callbacks in self._data.items():
            for callback in callbacks:
                yield key, callback

    def _set(self, key: Bindable, value: _BindVal, add: Bool = True):
        match value:
            case str():
                self.add(key, value, add)
            case Iterable():
                self.extend(key, value, add)
            case _:
                self.add(key, value, add)

    def add(self, key: Bindable, target: BindTarget, add: Bool = True):
        if add:
            self._data.setdefault(key, []).append(target)
        else:
            self._data[key] = [target]

    def extend(self, key: Bindable, targets: Collection[BindTarget], add: Bool = True):
        if add:
            self._data.setdefault(key, []).extend(targets)
        else:
            self._data[key] = [target for target in targets]

    def _update(self, binds: BindMapping | BindMap | None, kwargs: BindMapping, add: Bool):
        for obj in (binds, kwargs):
            if obj:
                for key, val in binds.items():
                    self._set(key, val, add)

    def update(self, binds: BindMapping | BindMap = None, **kwargs: _BindVal):
        """Update this BindMap with the given new targets, replacing any existing target callbacks."""
        self._update(binds, kwargs, False)

    def update_add(self, binds: BindMapping | BindMap = None, **kwargs: _BindVal):
        """Update this BindMap with the given new targets, extending any existing target callbacks."""
        self._update(binds, kwargs, True)

    @classmethod
    def pop_and_normalize(cls, kwargs: dict[str, Any], key: str = 'binds') -> BindMap:
        return cls.normalize(kwargs.pop(key, None))

    @classmethod
    def normalize(cls, obj: BindMapping | BindMap | None) -> BindMap:
        if obj is None:
            return cls()
        elif isinstance(obj, cls):
            return obj
        else:
            return cls(obj)


class BindMixin:
    _binds: BindMap = None

    @property
    def binds(self) -> BindMap:
        if (binds := self._binds) is None:
            self._binds = binds = BindMap()
        return binds

    @binds.setter
    def binds(self, value: BindMapping | BindMap | None):
        self._binds = value if isinstance(value, BindMap) else BindMap(value)

    @property
    def _bind_widget(self) -> BaseWidget | None:
        """The widget that should be used for bind operations"""
        raise NotImplementedError

    def bind(self, event_pat: Bindable, cb: BindTarget, add: Bool = True):
        if self._bind_widget:
            self._bind(event_pat, cb, add)
        else:
            self.binds.add(event_pat, cb, add)

    def _bind(self, event_pat: Bindable, cb: BindTarget, add: Bool = True):
        if cb is None:
            return
        # log.debug(f'Binding event={event_pat!r} to {cb=}')
        try:
            self._bind_widget.bind(event_pat, cb, add=add)
        except (TclError, RuntimeError) as e:
            log.error(f'Unable to bind event={event_pat!r}: {e}')
            # self._bind_widget.unbind_all(event_pat)

    def apply_binds(self):
        for event_pat, callback in self.binds.flat_items():
            self._bind(event_pat, callback, True)


class EventHandler:
    def __init__(
        self, handler: BindCallback, binds: tuple[str, ...], method: bool = True, add: bool = True, _auto: bool = True
    ):
        self.handler = handler
        self.binds = binds
        self.method = method
        self.add = add
        update_wrapper(self, handler)
        if _auto:
            _stack.get()[-1].append(self)  # Store in the event_handlers list for the class being defined

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}[{self.handler}, binds={self.binds!r}]>'


def event_handler(*binds: str, method: bool = True, add: bool = True) -> Callable[[BindCallback], EventHandler]:
    """
    Decorator that registers the decorated function/method as the handler for the specified bind events.  The function
    must accept a single positional :class:`python:tkinter.Event` argument.
    """
    if not binds:
        raise ValueError('At least one tkinter event key is required to bind to')
    return partial(EventHandler, binds=binds, method=method, add=add)


class ButtonHandler(EventHandler):
    def __init__(self, handler: ButtonEventCB, keys: tuple[str, ...], method: bool = True, add: bool = True):
        super().__init__(handler, (), method=method, add=add)
        self.keys = keys

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}[{self.handler}, keys={self.keys!r}]>'


def button_handler(*keys: str, method: bool = True, add: bool = True) -> Callable[[ButtonEventCB], ButtonHandler]:
    """
    Decorator that registers the decorated function/method as the handler for the specified buttons.  The function
    must accept two positional args - a :class:`python:tkinter.Event`, and the key of the :class:`Button` that was
    activated.
    """
    if not keys:
        raise ValueError('At least one Button key is required to bind to')
    return partial(ButtonHandler, keys=keys, method=method, add=add)


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
        event_handlers, button_handlers = [], []
        for handler in _stack.get().pop():
            if isinstance(handler, ButtonHandler):
                button_handlers.append(handler)
            else:
                event_handlers.append(handler)
        cls._event_handlers_ = event_handlers
        cls._button_handlers_ = button_handlers
        return cls

    @classmethod
    def get_parent_hem(mcs, cls: HandlesEventsMeta, include_abc: bool = True) -> Optional[HandlesEventsMeta]:
        for parent_cls in type.mro(cls)[1:]:
            if isinstance(parent_cls, mcs) and (include_abc or ABC not in parent_cls.__bases__):
                return parent_cls
        return None

    def _iter_event_handlers(cls) -> Iterator[EventHandler]:
        if cls._button_handlers_:
            try:
                yield EventHandler(cls._handle_button_clicked_, (BindEvent.BUTTON_CLICKED.value,), _auto=False)  # noqa
            except AttributeError as e:
                raise TypeError(
                    f'Unable to register button handlers for {cls=} - it is missing a _handle_button_clicked_ method'
                ) from e
        yield from cls._event_handlers_

    def event_handler_binds(cls: HandlesEventsMeta, he_obj) -> BindMap:
        mcs = cls.__class__
        if parent := mcs.get_parent_hem(cls):
            bind_map = mcs.event_handler_binds(parent, he_obj).copy()
        else:
            bind_map = BindMap()

        for handler in cls._iter_event_handlers():
            cb = partial(handler.handler, he_obj) if handler.method else handler.handler
            add = handler.add
            for bind in handler.binds:
                bind_map.add(bind, cb, add)

        return bind_map

    def button_handler_binds(cls: HandlesEventsMeta, he_obj) -> BindMap:
        mcs = cls.__class__
        if parent := mcs.get_parent_hem(cls):
            bind_map = mcs.button_handler_binds(parent, he_obj).copy()
        else:
            bind_map = BindMap()

        for handler in cls._button_handlers_:  # type: ButtonHandler
            cb = partial(handler.handler, he_obj) if handler.method else handler.handler
            add = handler.add
            for key in handler.keys:
                bind_map.add(key, cb, add)

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


class BindManager:
    __slots__ = ('event_cb_map', 'event_bound_id_map')

    def __init__(self, event_cb_map: MutableMapping[str, BindCallback] = None):
        self.event_cb_map = {} if event_cb_map is None else event_cb_map
        self.event_bound_id_map = {}

    def bind_all(self, widget: BaseWidget, add: Bool = True):
        for event_pat, callback in self.event_cb_map.items():
            self.event_bound_id_map[event_pat] = widget.bind(event_pat, callback, add=add)

    def unbind_all(self, widget: BaseWidget):
        for event_pat, cb_id in tuple(self.event_bound_id_map.items()):
            widget.unbind(event_pat, cb_id)

        self.event_bound_id_map = {}

    def bind(self, event_pat: str, callback: BindCallback | None, widget: BaseWidget, add: Bool = True):
        if callback is None:
            return
        self.event_cb_map[event_pat] = callback
        self.event_bound_id_map[event_pat] = widget.bind(event_pat, callback, add=add)

    def unbind(self, event_pat: str, widget: BaseWidget):
        if cb_id := self.event_bound_id_map.pop(event_pat, None):
            widget.unbind(event_pat, cb_id)

    def replace(self, event_pat: str, callback: BindCallback | None, widget: BaseWidget, add: Bool = True):
        self.unbind(event_pat, widget)
        self.bind(event_pat, callback, widget, add)


class CustomEventResultsMixin:
    __slots__ = ()
    _fqn_cls_map = {}
    __result_counter: count
    _results_: dict[int, Any]

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if not hasattr(cls, '_results_'):
            cls._fqn_cls_map[f'{cls.__module__}.{cls.__qualname__}'] = cls
            cls.__result_counter = count()
            cls._results_ = {}  # noqa

    @classmethod
    def add_result(cls, result: Any) -> int:
        num = next(cls.__result_counter)
        cls._results_[num] = result
        return num

    @classmethod
    def get_result(cls, event: Event):
        return cls._results_.pop(event.state, None)
