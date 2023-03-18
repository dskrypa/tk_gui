"""
The GuiState class provides a ``data`` dict for shared state between Views, and FILO queues for history / future Views
to be displayed.
"""

from __future__ import annotations

from collections import deque
from enum import IntEnum
from typing import Any

from .spec import ViewSpec

__all__ = ['GuiState', 'Direction']


class Direction(IntEnum):
    REVERSE = 0
    FORWARD = 1

    def __invert__(self) -> Direction:
        """``~Direction.REVERSE`` -> ``Direction.FORWARD``, and vice versa."""
        return self.REVERSE if self == self.FORWARD else self.FORWARD

    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            return cls._member_map_[value.upper()]
        return super()._missing_(value)


class History:
    __slots__ = ('_data',)
    _data: tuple[deque[ViewSpec], deque[ViewSpec]]

    def __init__(self, max_len: int = None):
        self._data = (deque(maxlen=max_len), deque(maxlen=max_len))

    def __repr__(self) -> str:
        reverse, forward = map(len, self._data)
        return f'<{self.__class__.__name__}[{reverse=}, {forward}]>'

    @property
    def reverse(self) -> deque[ViewSpec]:
        return self._data[0]

    @property
    def forward(self) -> deque[ViewSpec]:
        return self._data[1]

    def __getitem__(self, direction: Direction | int) -> deque[ViewSpec]:
        return self._data[direction]

    def clear(self, reverse: bool = True, forward: bool = True):
        if reverse:
            self._data[Direction.REVERSE].clear()
        if forward:
            self._data[Direction.FORWARD].clear()

    def append(self, spec: ViewSpec, direction: Direction | int):
        self._data[direction].append(spec)

    def pop(self, direction: Direction | int) -> ViewSpec:
        return self._data[direction].pop()


class QueuedViewSpec:
    __slots__ = ('spec', 'forget_last', 'from_hist', 'hist_dir')

    def __init__(
        self, spec: ViewSpec, forget_last: bool, from_hist: bool = False, hist_dir: Direction = Direction.REVERSE
    ):
        self.spec = spec
        self.forget_last = forget_last
        self.from_hist = from_hist
        self.hist_dir = hist_dir


class GuiState:
    __slots__ = ('data', '_current', '_history', '_enqueued')
    data: dict[str, Any]  # Intended for use by applications for shared state between Views
    _current: ViewSpec | None
    _history: History
    _enqueued: deque[QueuedViewSpec]

    def __init__(self, max_len: int = None):
        self.data = {}
        self._current = None
        self._history = History(max_len)
        self._enqueued = deque(maxlen=max_len)

    @classmethod
    def init(cls, spec: ViewSpec, max_len: int = None) -> GuiState:
        self = cls(max_len)
        self._current = spec
        return self

    def __repr__(self) -> str:
        enqueued, history = len(self._enqueued), self._history
        return f'<{self.__class__.__name__}[{enqueued=}, {history=}]>'

    def pop_next_view(self) -> ViewSpec:
        try:
            item = self._enqueued.popleft()
        except IndexError:
            raise NoNextView from None
        if item.from_hist:
            self._history.pop(~item.hist_dir)
        if not item.forget_last and self._current:
            self._history.append(self._current, item.hist_dir)
        self._current = item.spec
        return item.spec

    # region Enqueue

    def enqueue_view(self, spec: ViewSpec, forget_last: bool = False, clear: bool = False):
        """
        :param spec: The ViewSpec for the new View that should be displayed.
        :param forget_last: If True, then the ViewSpec for the View that the given ``spec`` follows will not be saved
          in the ViewSpec history.  Typically used if the View needed to be reloaded in-place.
        :param clear: If True, clear any existing enqueued ViewSpecs before enqueueing the given one.
        """
        if clear:
            self._enqueued.clear()
        self._enqueued.append(QueuedViewSpec(spec, forget_last))

    def enqueue_hist_view(self, direction: Direction | int, forget_last: bool = False, **kwargs) -> bool:
        try:
            spec = self._history[direction][-1]
        except IndexError:
            return False
        if kwargs:
            spec.update(**kwargs)
        self._enqueued.append(QueuedViewSpec(spec, forget_last, from_hist=True, hist_dir=~Direction(direction)))
        return True

    def enqueue_reverse_view(self, forget_last: bool = False, **kwargs) -> bool:
        return self.enqueue_hist_view(Direction.REVERSE, forget_last, **kwargs)

    def enqueue_forward_view(self, forget_last: bool = False, **kwargs) -> bool:
        return self.enqueue_hist_view(Direction.FORWARD, forget_last, **kwargs)

    # endregion

    # region Peek / Introspection

    def peek_next_view(self) -> ViewSpec | None:
        try:
            return self._enqueued[0].spec
        except IndexError:
            return None

    def peek_hist_view(self, direction: Direction | int) -> ViewSpec | None:
        try:
            return self._history[direction][-1]
        except IndexError:
            return None

    @property
    def can_go_reverse(self) -> bool:
        return bool(self._history[Direction.REVERSE])

    @property
    def can_go_forward(self) -> bool:
        return bool(self._history[Direction.FORWARD])

    @property
    def prev_view_name(self) -> str | None:
        if spec := self.peek_hist_view(Direction.REVERSE):
            return spec.name
        return None

    @property
    def next_view_name(self) -> str | None:
        if spec := self.peek_next_view():
            return spec.name
        return None

    # endregion

    def clear(self):
        self._enqueued.clear()

    def clear_history(self, reverse: bool = True, forward: bool = True):
        self._history.clear(reverse, forward)


class NoNextView(Exception):
    pass
