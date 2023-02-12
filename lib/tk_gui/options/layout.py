"""
Layout / rendering utilities for gui options
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import TYPE_CHECKING, Optional, ContextManager, Iterable, Iterator

from tk_gui.elements.choices import CheckBox, make_checkbox_grid
from tk_gui.elements import Text, Submit, Frame, InteractiveFrame
from tk_gui.elements.text import normalize_text_ele_widths
from .options import OptionTuples, Opt, _NotSet

if TYPE_CHECKING:
    from tk_gui.typing import TraceCallback, Layout, E

__all__ = ['OptionGrid', 'OptionColumn', 'OldOptionLayout', 'OptionLayout', 'OptionComponent']
log = logging.getLogger(__name__)


class OptionContainer(ABC):
    __slots__ = ()

    @abstractmethod
    def options(self) -> Iterator[Opt]:
        raise NotImplementedError


class OptionColumn(OptionContainer):
    __slots__ = ('_options',)
    _options: list[OptionComponent]

    def __init__(self, options: Iterable[OptionComponent]):
        self._options = list(options)

    def as_element(self, disable_all: bool, change_cb: TraceCallback = None, **kwargs) -> InteractiveFrame:
        layout = ([opt.as_element(disable_all, change_cb)] for opt in self._options)
        kwargs.setdefault('pad', (0, 0))
        return InteractiveFrame(layout, **kwargs)

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
    __slots__ = ()

    def __init__(self, option_layout: Iterable[Iterable[OptionComponent]]):
        self.rows = [[opt for opt in row] for row in option_layout]

    def as_element(self, disable_all: bool, change_cb: TraceCallback = None, **kwargs) -> InteractiveFrame:
        layout = ((opt.as_element(disable_all, change_cb) for opt in row) for row in self.rows)
        kwargs.setdefault('pad', (0, 0))
        return InteractiveFrame(layout, grid=True, **kwargs)


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


class OldOptionLayout:
    option_map: dict[str, Opt]

    def __init__(
        self,
        option_map: dict[str, Opt] = None,
        align_text: bool = True,
        align_checkboxes: bool = True,
    ):
        self.option_map = {} if option_map is None else option_map
        self.align_text = align_text
        self.align_checkboxes = align_checkboxes
        self._rows_per_column: dict[int | None, int] = {}
        self._max_row = -1
        self._default_row = 0
        self._default_col = 0

    def _update_row_and_col(self, row: int, col: int):
        col_rows = self._rows_per_column.get(col, 0)
        self._rows_per_column[col] = max(col_rows, row + 1)
        self._max_row = max(self._max_row, row)

    def add_option(self, option: Opt, row: int = None, col: int = None) -> Opt:
        if option.row is _NotSet:
            if row is None:
                row = self._default_row
            option.row = row
        if option.col is _NotSet:
            if col is None:
                col = self._default_col
            option.col = col
        self._update_row_and_col(*option.row_and_col)
        self.option_map[option.name] = option
        return option

    def _generate_layout(self, disable_all: bool, change_cb: TraceCallback = None) -> OptionTuples:
        for name, opt in self.option_map.items():
            yield from opt.prepare_layout(disable_all, change_cb)

    def _pack(self, basic_rows: list[list[E]], columns: list[list[list[E]]]) -> list[list[E]]:
        if self.align_text or self.align_checkboxes:
            if columns:
                row_sets = [basic_rows + columns[0], columns[1:]] if len(columns) > 1 else [basic_rows + columns[0]]
            else:
                row_sets = [basic_rows]

            for row_set in row_sets:
                if self.align_text and (rows_with_text := [r for r in row_set if r and isinstance(r[0], Text)]):
                    normalize_text_ele_widths(rows_with_text)  # noqa
                if self.align_checkboxes:
                    if box_rows := [r for r in row_set if r and all(isinstance(e, CheckBox) for e in r)]:
                        log.info(f'Processing checkboxes into grid: {box_rows}')
                        make_checkbox_grid(box_rows)  # noqa

        if not basic_rows and len(columns) == 1:
            layout = columns[0]
        else:
            # layout.append([Frame(column, pad=(0, 0)) for column in columns])
            layout = basic_rows + [[Frame(column, pad=(0, 0)) for column in columns]]
            # layout.extend(BasicRowFrame(column) for column in columns)
            # layout.extend([Frame(column, pad=(0, 0), expand=True, fill='x', anchor='e')] for column in columns)
            # layout.append([Frame(column, pad=(0, 0), expand=True, fill='x', anchor_elements='e', side='l') for column in columns])
            # layout.append([Frame(column, pad=(0, 0), anchor_elements='e', side='l') for column in columns])
            # layout.append([Frame(column, pad=(0, 0)) for column in columns])

        return layout

    def layout(
        self,
        submit_text: str | None,
        submit_key: str | None,
        disable_all: bool,
        submit_row: int = None,
        change_cb: TraceCallback = None,
    ) -> Layout:
        rows_per_column = sorted(((col, val) for col, val in self._rows_per_column.items() if col is not None))
        layout = [[] for _ in range(none_cols)] if (none_cols := self._rows_per_column.get(None)) else []
        columns = [[[] for _ in range(r)] for c, r in rows_per_column]
        for col_num, row_num, ele in self._generate_layout(disable_all, change_cb):
            if col_num is None:
                layout[row_num].append(ele)
            else:
                columns[col_num][row_num].append(ele)

        layout = self._pack(layout, columns)

        if submit_text:
            submit_ele = Submit(submit_text, disabled=disable_all, key=submit_key or submit_text)
            if submit_row is None:
                layout.append([submit_ele])
            else:
                while len(layout) < (submit_row + 1):
                    layout.append([])
                layout[submit_row].append(submit_ele)

        return layout

    # def layout(
    #     self, submit_key: str = None, disable_all: bool = None, submit_row: int = None, change_cb: TraceCallback = None
    # ) -> Layout:
    #     if disable_all is None:
    #         disable_all = self.disable_on_parsed and self.parsed
    #     log.debug(f'Building option layout with {self.parsed=!r} {submit_key=!r} {disable_all=!r}')
    #
    #     # rows_per_column = sorted(((col, val) for col, val in self._rows_per_column.items() if col is not None))
    #
    #     if none_cols := self._rows_per_column.get(None):
    #         basic_rows = [[] for _ in range(none_cols)]
    #     else:
    #         basic_rows = []
    #
    #     max_col = max(c for c in self._rows_per_column if c is not None)
    #     max_row = max(self._rows_per_column.values())
    #     grid: list[list[E | None]] = [[None for _ in range(max_col + 1)] for _ in range(max_row + 1)]
    #
    #     # columns = [[[] for _ in range(r)] for c, r in rows_per_column]
    #     for col_num, row_num, ele in self._generate_layout(disable_all, change_cb):
    #         log.debug(f'Processing {row_num=}, {col_num=} for {ele=}')
    #         if col_num is None:
    #             basic_rows[row_num].append(ele)
    #         else:
    #             grid[row_num][col_num] = ele
    #             # columns[col_num][row_num].append(ele)
    #
    #     # layout = self._pack(basic_rows, columns)
    #     layout = self._grid(basic_rows, grid)
    #
    #     if self.submit_text:
    #         submit_ele = Submit(self.submit_text, disabled=disable_all, key=submit_key or self.submit_text)
    #         if submit_row is None:
    #             layout.append([submit_ele])
    #         else:
    #             while len(layout) < (submit_row + 1):
    #                 layout.append([])
    #             layout[submit_row].append(submit_ele)
    #
    #     return layout

    # def _grid(self, layout: list[list[E]], grid: list[list[E]]) -> list[list[E]]:
    #     if grid:
    #         grid = [[Spacer((1, 1)) if ele is None else ele for ele in row] for row in grid]
    #         layout.append([Frame(grid, grid=True, pad=(0, 0))])
    #     return layout

    def as_frame(
        self,
        submit_text: str | None,
        submit_key: str | None,
        disable_all: bool,
        submit_row: int = None,
        change_cb: TraceCallback = None,
        title: str = None,
        **kwargs,
    ) -> InteractiveFrame:
        return InteractiveFrame(
            self.layout(submit_text, submit_key, disable_all, submit_row, change_cb), title=title, **kwargs
        )

    @contextmanager
    def column(self, col: Optional[int]) -> ContextManager[OptionLayout]:
        old = self._default_col
        self._default_col = col
        try:
            yield self
        finally:
            self._default_col = old

    @contextmanager
    def row(self, row: int) -> ContextManager[OptionLayout]:
        old = self._default_row
        self._default_row = row
        try:
            yield self
        finally:
            self._default_row = old

    @contextmanager
    def next_row(self) -> ContextManager[OptionLayout]:
        old = self._default_row
        self._default_row = self._max_row + 1
        try:
            yield self
        finally:
            self._default_row = old

    @contextmanager
    def column_and_row(self, col: Optional[int], row: int) -> ContextManager[OptionLayout]:
        old_col, old_row = self._default_col, self._default_row
        self._default_col = col
        self._default_row = row
        try:
            yield self
        finally:
            self._default_col = old_col
            self._default_row = old_row


OptionComponent = Opt | OptionGrid | OptionColumn
