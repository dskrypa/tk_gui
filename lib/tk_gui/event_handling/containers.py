"""
Containers for events to bind to callbacks, and to store resulting function IDs for unbinding later.
"""

from __future__ import annotations

from collections.abc import MutableMapping, ItemsView, KeysView, ValuesView, Iterable
from typing import TYPE_CHECKING, Any, Mapping, Collection, Iterator, Union

from tk_gui.typing import BindCallback, Bindable, BindTarget, Bool
from tk_gui.utils import unbind

if TYPE_CHECKING:
    from tkinter import BaseWidget

__all__ = ['BindMap', 'BindManager']

_NotSet = object()
_BindVal = Union[BindTarget, Collection[BindTarget]]
BindMapping = Mapping[Bindable, _BindVal]


class BindMap(MutableMapping[Bindable, list[BindTarget]]):
    __slots__ = ('_data',)
    _data: dict[Bindable, list[BindTarget]]

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

    def __rich_repr__(self):
        yield self._data

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

    def remove(self, key: Bindable, target: BindTarget = _NotSet):
        """
        Remove the target from the binds for the given key, or all targets for the given key if no target is specified.
        Raises :class:`KeyError` or :class:`ValueError` if the key or target are not present, respectively.
        """
        if target is _NotSet:
            del self._data[key]
        else:
            targets = self._data[key]
            targets.remove(target)
            if not targets:
                del self._data[key]

    def discard(self, key: Bindable, target: BindTarget = _NotSet):
        """
        Remove the target from the binds for the given key, or all targets for the given key if no target is specified.
        If the key or target are not present, then they will not be removed (no exception will be raised).
        """
        try:
            self.remove(key, target)
        except (KeyError, ValueError):
            pass

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
            unbind(widget, event_pat, cb_id)

        self.event_bound_id_map = {}

    def bind(self, event_pat: str, callback: BindCallback | None, widget: BaseWidget, add: Bool = True):
        if callback is None:
            return
        self.event_cb_map[event_pat] = callback
        self.event_bound_id_map[event_pat] = widget.bind(event_pat, callback, add=add)

    def unbind(self, event_pat: str, widget: BaseWidget):
        if cb_id := self.event_bound_id_map.pop(event_pat, None):
            unbind(widget, event_pat, cb_id)

    def replace(self, event_pat: str, callback: BindCallback | None, widget: BaseWidget, add: Bool = True):
        self.unbind(event_pat, widget)
        self.bind(event_pat, callback, widget, add)
