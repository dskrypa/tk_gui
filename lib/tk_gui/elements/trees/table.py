"""
Table GUI elements

:author: Doug Skrypa
"""

from __future__ import annotations

import logging
from itertools import chain
from tkinter import TclError
from tkinter.ttk import Treeview
from typing import TYPE_CHECKING, Union

from tk_gui.widgets.scroll import ScrollableTreeview
from .base import TreeViewBase, Column

if TYPE_CHECKING:
    from tk_gui.typing import TkContainer, TreeSelectModes

__all__ = ['Table']
log = logging.getLogger(__name__)

TableRow = dict[str, Union[str, int]]
TableRows = list[TableRow]


class Table(TreeViewBase, base_style_layer='table'):
    columns: dict[str, Column]

    def __init__(
        self,
        *columns: Column,
        data: TableRows,
        rows: int = None,
        show_row_nums: bool = False,
        row_height: int = None,
        selected_row_color: tuple[str, str] = None,  # fg, bg
        select_mode: TreeSelectModes = None,
        scroll_y: bool = True,
        scroll_x: bool = False,
        init_focus_row: int | tuple[str, str | int] | None = 0,
        **kwargs,
    ):
        super().__init__(**kwargs)
        if show_row_nums:
            columns = chain((Column('#', width=len(f'{len(data):>,d}'), fmt_func='{:>,d}'.format),), columns)
        self.columns = {col.key: col for col in columns}
        self.data = data
        self.num_rows = rows
        self.show_row_nums = show_row_nums
        self.row_height = row_height
        self.selected_row_color = selected_row_color
        self.select_mode = select_mode
        self.scroll_x = scroll_x
        self.scroll_y = scroll_y
        self._tree_ids = []
        self._init_focus_row = init_focus_row

    @property
    def value(self) -> TableRows:
        try:
            selection = self.tree_view.selection()
        except TclError:
            return []
        if selection:
            rows = self.data
            return [rows[int(i)] for i in selection]
        return []

    @classmethod
    def from_data(cls, data: list[dict[str, str | int]], **kwargs) -> Table:
        keys = {k: None for k in chain.from_iterable(data)}  # dict retains key order, but set does not
        columns = [Column(key, key.replace('_', ' ').title(), data) for key in keys]
        return cls(*columns, data=data, **kwargs)

    def set_focus_on_value(self, key: str, value: str | int):
        for i, row in enumerate(self.data):
            if row[key] == value:
                self.set_focus_on_row(i)
                return
        raise ValueError(f'Unable to find row with {key=} {value=}')

    def _init_widget(self, tk_container: TkContainer):
        columns, style = self.columns, self.style
        kwargs = {
            'columns': [col.key for col in columns.values()],
            'displaycolumns': [col.key for col in columns.values() if col.show],
            'height': self.num_rows if self.num_rows else self.size[1] if self.size else len(self.data),
            'show': 'headings',
            'selectmode': self.select_mode,
            'takefocus': int(self.allow_focus),
            **self.style_config,
        }
        if self.scroll_y or self.scroll_x:
            self.widget = outer = ScrollableTreeview(tk_container, self.scroll_y, self.scroll_x, style, **kwargs)
            self.tree_view = tree_view = outer.inner_widget
        else:
            self.widget = self.tree_view = tree_view = Treeview(tk_container, **kwargs)

        char_width = style.char_width('table')
        for col in columns.values():
            tree_view.heading(col.key, text=col.title, anchor=col.anchor_header.value)  # noqa
            # tree_view.column(col.key, width=col.width * char_width + 10, minwidth=10, stretch=False)
            tree_view.column(
                col.key, width=col.width_for(char_width), minwidth=10, stretch=False, anchor=col.anchor_values.value
            )

        for i, row in enumerate(self.data):
            values = (val for key, val in row.items() if columns[key].show)
            values = [i, *values] if self.show_row_nums else list(values)
            self._tree_ids.append(tree_view.insert('', 'end', text=values, iid=i, values=values, tag=i))  # noqa

        if alt_row_style := style.table_alt:
            font, fg, bg = alt_row_style.font.default, alt_row_style.fg.default, alt_row_style.bg.default
            tc_kw = {k: v for k, v in {'background': bg, 'foreground': fg, 'font': font}.items() if v is not None}
            if tc_kw:
                for row in range(0, len(self.data), 2):
                    tree_view.tag_configure(row, **tc_kw)  # noqa

        tree_view.configure(style=self._ttk_style()[0])
        # tree_view.bind('<<TreeviewSelect>>', self._treeview_selected)
