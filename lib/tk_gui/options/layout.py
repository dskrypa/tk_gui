"""
Layout / rendering utilities for gui options
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Iterable, Iterator, Union

from tk_gui.elements import InteractiveFrame

if TYPE_CHECKING:
    from tk_gui.typing import TraceCallback, Layout
    from .options import Opt

__all__ = ['OptionGrid', 'OptionColumn', 'OptionLayout', 'OptionComponent']


class OptionContainer(ABC):
    __slots__ = ()

    @abstractmethod
    def options(self) -> Iterator[Opt]:
        raise NotImplementedError


class OptionColumn(OptionContainer):
    __slots__ = ('_options', 'frame_kwargs')
    _options: list[OptionComponent]

    def __init__(self, options: Iterable[OptionComponent], **kwargs):
        self._options = list(options)
        self.frame_kwargs = kwargs

    def as_element(self, disable_all: bool, change_cb: TraceCallback = None) -> InteractiveFrame:
        layout = ([opt.as_element(disable_all, change_cb)] for opt in self._options)
        self.frame_kwargs.setdefault('pad', (0, 0))
        return InteractiveFrame(layout, **self.frame_kwargs)

    def options(self) -> Iterator[Opt]:
        for opt in self._options:
            if isinstance(opt, OptionContainer):
                yield from opt.options()
            else:
                yield opt


class OptionRows(OptionContainer):
    __slots__ = ('rows',)
    rows: list[list[OptionComponent]]

    def options(self) -> Iterator[Opt]:
        for row in self.rows:
            for opt in row:
                if isinstance(opt, OptionContainer):
                    yield from opt.options()
                else:
                    yield opt


class OptionGrid(OptionRows):
    __slots__ = ('frame_kwargs',)

    def __init__(self, option_layout: Iterable[Iterable[OptionComponent]], **kwargs):
        self.rows = [[opt for opt in row] for row in option_layout]
        self.frame_kwargs = kwargs

    def as_element(self, disable_all: bool, change_cb: TraceCallback = None) -> InteractiveFrame:
        layout = ((opt.as_element(disable_all, change_cb) for opt in row) for row in self.rows)
        self.frame_kwargs.setdefault('pad', (0, 0))
        return InteractiveFrame(layout, grid=True, **self.frame_kwargs)


class OptionLayout(OptionRows):
    __slots__ = ()

    def __init__(self, option_layout: Iterable[Iterable[OptionComponent]]):
        self.rows = [[opt for opt in row] for row in option_layout]

    def layout(self, disable_all: bool, change_cb: TraceCallback = None) -> Layout:
        for row in self.rows:
            yield [opt.as_element(disable_all, change_cb) for opt in row]

    def as_frame(
        self, disable_all: bool, change_cb: TraceCallback = None, title: str = None, **kwargs
    ) -> InteractiveFrame:
        return InteractiveFrame(self.layout(disable_all, change_cb), title=title, **kwargs)


OptionComponent = Union['Opt', OptionGrid, OptionColumn]
