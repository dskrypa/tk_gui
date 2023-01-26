"""

"""

from __future__ import annotations

import logging
from itertools import count
from tkinter import TclError, BaseWidget, Event
from typing import TYPE_CHECKING, Any

from .containers import BindMap, BindMapping

if TYPE_CHECKING:
    from tk_gui.typing import Bindable, BindTarget, Bool

__all__ = ['BindMixin', 'CustomEventResultsMixin']
log = logging.getLogger(__name__)


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
