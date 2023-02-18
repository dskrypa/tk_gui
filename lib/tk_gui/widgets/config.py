"""
Tkinter GUI Scroll Bar Utils

:author: Doug Skrypa
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, TypeVar, Generic

from tk_gui.enums import ScrollUnit
from tk_gui.utils import extract_kwargs

if TYPE_CHECKING:
    from tk_gui.typing import Bool, Axis, TkContainer, ScrollWhat, TkScrollWhat

__all__ = ['AxisConfig', 'ScrollAmount']
log = logging.getLogger(__name__)

ScrollAmount = TypeVar('ScrollAmount', int, float)


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
        return amount, self.what.value

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

    def target_size(self, tk_container: TkContainer) -> int:
        # Target size for a scrollable region
        req_value = tk_container.winfo_reqheight() if self.axis == 'y' else tk_container.winfo_reqwidth()
        return req_value // self.size_div
