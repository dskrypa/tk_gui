"""
Tkinter GUI Scroll Bar Utils

:author: Doug Skrypa
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, TypeVar, Generic

from tk_gui.enums import ScrollUnit
from tk_gui.utils import extract_kwargs
from .utils import get_root_widget

if TYPE_CHECKING:
    from tkinter import BaseWidget
    from tk_gui.typing import Bool, Axis, TkContainer, ScrollWhat, TkScrollWhat, OptInt

__all__ = ['AxisConfig', 'ScrollAmount', 'FillConfig']
log = logging.getLogger(__name__)

ScrollAmount = TypeVar('ScrollAmount', int, float)


def _fill_config_key_map(axis: Axis):
    return {f'fill_{axis}': 'fill', f'fill_{axis}_pct': 'fill_pct', f'fill_pct_{axis}': 'fill_pct'}


def _axis_config_key_map(axis: Axis):
    return {
        f'scroll_{axis}': 'scroll', f'fill_{axis}': 'fill', f'scroll_{axis}_div': 'size_div',
        f'amount_{axis}': 'amount', f'scroll_{axis}_amount': 'amount',
        f'what_{axis}': 'what', f'scroll_{axis}_what': 'what',
    }


class AxisConfig(Generic[ScrollAmount]):
    __slots__ = ('axis', 'what', 'amount', 'scroll', 'fill', '_size_div')
    # _default_divs = {'x': 1, 'y': 1.5}
    _default_divs = {'x': 1, 'y': 2}
    _key_maps = {'x': _axis_config_key_map('x'), 'y': _axis_config_key_map('y')}
    _keys = {axis: frozenset(key_map) for axis, key_map in _key_maps.items()}

    def __init__(
        self,
        axis: Axis,
        scroll: bool = False,
        amount: ScrollAmount = 4,
        what: ScrollWhat = ScrollUnit.UNITS,
        fill: bool = False,
        size_div: float = None,
    ):
        self.axis = axis
        self.what = what = ScrollUnit(what)
        if not isinstance(amount, int) and what != ScrollUnit.PIXELS:
            raise TypeError(f'Invalid type={amount.__class__.__name__} for {amount=} with {what=}')
        self.scroll = scroll
        self.amount = amount
        self.fill = fill
        self._size_div = size_div

    @classmethod
    def from_kwargs(cls, axis: Axis, kwargs: dict[str, Any]) -> AxisConfig:
        if extracted := extract_kwargs(kwargs, cls._keys[axis]):
            key_map = cls._key_maps[axis]
            return cls(axis, **{key_map[key]: val for key, val in extracted.items()})
        return cls(axis)

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}({self.arg_str()})>'

    def view_scroll_args(self, positive: bool) -> tuple[ScrollAmount, TkScrollWhat]:
        amount = self.amount if positive else -self.amount
        # when `what` is `units`, 1 unit = the scroll increment, which defaults to 1/10th of the window's width/height
        # when `what` is `pages`, 1 page = 9/10ths of the window's width/height
        what = 'units' if self.what == ScrollUnit.PIXELS else self.what.value
        # log.debug(f'Scrolling along axis={self.axis} {amount=} what={self.what.value}')
        return amount, what

    def arg_str(self, include_axis: Bool = False) -> str:
        format_key = f'{{}}_{self.axis}'.format if include_axis else str
        data = {
            'scroll': self.scroll,
            'amount': self.amount,
            'what': self.what.value,
            'fill': self.fill,
            'size_div': self.size_div,
        }
        return ', '.join(f'{format_key(k)}={v!r}' for k, v in data.items())

    @property
    def size_div(self) -> float | int:
        if size_div := self._size_div:
            return size_div
        return self._default_divs[self.axis]

    def target_size(self, inner_container: BaseWidget) -> int:
        # Target size for a scrollable region
        if self.fill:
            # Even if this overshoots the available space, it is handled well
            top_level = get_root_widget(inner_container)
            # target = req_value = _get_size(top_level, 'width' if self.axis == 'x' else 'height')
            # log.debug(f'Using {target=} = {req_value=} for axis={self.axis} from {top_level=}')
            return _get_size(top_level, 'width' if self.axis == 'x' else 'height')
        else:
            req_value = _get_size(inner_container, 'reqwidth' if self.axis == 'x' else 'reqheight')
            # target = req_value // self.size_div
            # log.debug(f'Using {target=} = {req_value=} // {self.size_div} for axis={self.axis}')
            return req_value // self.size_div
        # return target


class FillConfig:
    __slots__ = ('axis', 'fill', '_fill_pct')
    _default_percents = {'x': 1, 'y': 0.8}
    _key_maps = {'x': _fill_config_key_map('x'), 'y': _fill_config_key_map('y')}
    _keys = {axis: frozenset(key_map) for axis, key_map in _key_maps.items()}

    def __init__(self, axis: Axis, fill: bool = False, fill_pct: float = None):
        self.axis = axis
        self.fill = fill
        if fill_pct is not None and not (0 < fill_pct <= 1):
            raise TypeError(f'Invalid {fill_pct=} for {axis=} - must be greater than 0 and <= 1')
        self._fill_pct = fill_pct

    @classmethod
    def from_kwargs(cls, axis: Axis, kwargs: dict[str, Any]) -> FillConfig:
        if extracted := extract_kwargs(kwargs, cls._keys[axis]):
            key_map = cls._key_maps[axis]
            return cls(axis, **{key_map[key]: val for key, val in extracted.items()})
        return cls(axis)

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}({self.arg_str()})>'

    def arg_str(self, include_axis: Bool = False) -> str:
        format_key = f'{{}}_{self.axis}'.format if include_axis else str
        data = {'fill': self.fill, 'fill_pct': self.fill_pct}
        return ', '.join(f'{format_key(k)}={v!r}' for k, v in data.items())

    @property
    def fill_pct(self) -> float:
        if fill_pct := self._fill_pct:
            return fill_pct
        return self._default_percents[self.axis]

    def target_size(self, inner_container: TkContainer, default: int = None) -> OptInt:
        if not self.fill:
            return default
        top_level = get_root_widget(inner_container)
        req_value = _get_size(top_level, 'width' if self.axis == 'x' else 'height')
        # result = int(req_value * self.fill_pct)
        # # log.debug(f'Using {result=} from {req_value=} for {self}, widget={top_level!r}')
        # return result
        return int(req_value * self.fill_pct)


def _get_size(widget: BaseWidget, attr: str) -> int:
    # Equivalent to widget.winfo_{req}{height|width}()
    return int(widget.tk.call('winfo', attr, widget._w))  # noqa
