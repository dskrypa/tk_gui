"""
Table GUI elements

:author: Doug Skrypa
"""

from __future__ import annotations

import logging
from itertools import chain
from tkinter import TclError
from tkinter.ttk import Treeview, Style as TtkStyle
from typing import TYPE_CHECKING, Union, Callable, Literal, Mapping, Any, Iterable
from unicodedata import normalize

from wcwidth import wcswidth

from tk_gui.caching import cached_property
from tk_gui.enums import Anchor
from tk_gui.widgets.scroll import ScrollableTreeview
from .element import Interactive

if TYPE_CHECKING:
    from tkinter import BaseWidget
    from tk_gui.pseudo_elements import Row
    from tk_gui.styles.typing import Font, Layer
    from tk_gui.typing import TkContainer

__all__ = ['TableColumn', 'Table']
log = logging.getLogger(__name__)

SelectMode = Literal['none', 'browse', 'extended']  # browse = select only 1, extended = select multiple rows
XGROUND_DEFAULT_HIGHLIGHT_COLOR_MAP = {'foreground': 'SystemHighlightText', 'background': 'SystemHighlight'}
_Width = Union[float, Mapping[Any, Mapping[str, Any]], Iterable[Union[Mapping[str, Any], Any]]]
FormatFunc = Callable[[Any], str]

TableRow = dict[str, Union[str, int]]
TableRows = list[TableRow]


class TableColumn:
    __slots__ = ('key', 'title', '_width', 'show', 'fmt_func', 'anchor_header', 'anchor_values')

    def __init__(
        self,
        key: str,
        title: str = None,
        width: _Width = None,
        show: bool = True,
        fmt_func: FormatFunc = None,
        anchor_header: Anchor | str = None,
        anchor_values: Anchor | str = None,
    ):
        self.key = key
        self.title = str(title or key)
        self._width = 0
        self.show = show
        self.fmt_func = fmt_func
        self.width = width
        self.anchor_header = Anchor(anchor_header) if anchor_header else Anchor.MID_CENTER
        self.anchor_values = Anchor(anchor_values) if anchor_values else Anchor.MID_LEFT

    @property
    def width(self) -> int:
        return self._width

    @width.setter
    def width(self, value: _Width):
        try:
            self._width = max(self._calc_width(value), mono_width(self.title))
        except Exception:
            log.error(f'Error calculating width for column={self.key!r}', exc_info=True)
            raise

    def width_for(self, char_width: int) -> int:
        return self.width * char_width + 10

    def _calc_width(self, width: _Width) -> int:
        try:
            return int(width)
        except (TypeError, ValueError):
            pass

        if fmt_func := self.fmt_func:
            def _len(obj: Any):
                return mono_width(fmt_func(obj))
        else:
            def _len(obj: Any):
                return mono_width(str(obj))

        key = self.key
        try:
            return max(_len(e[key]) for e in width.values())
        except (KeyError, TypeError, AttributeError):
            pass
        try:
            return max(_len(e[key]) for e in width)
        except (KeyError, TypeError, AttributeError):
            pass
        try:
            return max(map(_len, width))
        except ValueError as e:
            if 'Unknown format code' in str(e):
                if fmt_func := self.fmt_func:
                    values = []
                    for obj in width:
                        try:
                            values.append(fmt_func(obj))
                        except ValueError:
                            values.append(str(obj))
                else:
                    values = list(map(str, width))
                return max(map(mono_width, values))
            raise


class Table(Interactive, base_style_layer='table'):
    widget: Union[Treeview, ScrollableTreeview]
    tree_view: Treeview
    columns: dict[str, TableColumn]

    def __init__(
        self,
        *columns: TableColumn,
        data: TableRows,
        rows: int = None,
        show_row_nums: bool = False,
        row_height: int = None,
        selected_row_color: tuple[str, str] = None,  # fg, bg
        select_mode: SelectMode = None,
        scroll_y: bool = True,
        scroll_x: bool = False,
        init_focus_row: int | tuple[str, str | int] | None = 0,
        **kwargs,
    ):
        super().__init__(**kwargs)
        if show_row_nums:
            columns = chain((TableColumn('#', width=len(f'{len(data):>,d}'), fmt_func='{:>,d}'.format),), columns)
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
    def from_data(cls, data: list[dict[str, Union[str, int]]], **kwargs) -> Table:
        keys = {k: None for k in chain.from_iterable(data)}  # dict retains key order, but set does not
        columns = [TableColumn(key, key.replace('_', ' ').title(), data) for key in keys]
        return cls(*columns, data=data, **kwargs)

    def set_focus_on_value(self, key: str, value: Union[str, int]):
        for i, row in enumerate(self.data):
            if row[key] == value:
                self.set_focus_on_row(i)
                return
        raise ValueError(f'Unable to find row with {key=} {value=}')

    def set_focus_on_row(self, n: int):
        tree_view = self.tree_view
        child_id = tree_view.get_children()[n]
        tree_view.selection_set(child_id)
        tree_view.focus(child_id)

    def take_focus(self, force: bool = False):
        if force:
            self.tree_view.focus_force()
        else:
            self.tree_view.focus_set()

        if (focus_row := self._init_focus_row) is not None:
            try:
                self.set_focus_on_value(*focus_row)
            except TypeError:
                self.set_focus_on_row(focus_row)

    def enable(self):
        pass

    def disable(self):
        pass

    def _ttk_style(self) -> tuple[str, TtkStyle]:
        style = self.style
        name, ttk_style = style.make_ttk_style('customtable.Treeview')
        ttk_style.configure(name, rowheight=self.row_height or style.char_height('table'))

        if base := self._tk_style_config(ttk_style, name, 'table'):
            if (selected_row_color := self.selected_row_color) and ('foreground' in base or 'background' in base):
                for i, (xground, default) in enumerate(XGROUND_DEFAULT_HIGHLIGHT_COLOR_MAP.items()):
                    if xground in base and (selected := selected_row_color[i]) is not None:
                        ttk_style.map(name, **{xground: _style_map_data(ttk_style, name, xground, selected or default)})

        self._tk_style_config(ttk_style, f'{name}.Heading', 'table_header')
        return name, ttk_style

    def _tk_style_config(self, ttk_style: TtkStyle, name: str, layer: Layer) -> dict[str, Union[Font, str, None]]:
        style_cfg = self.style.get_map(layer, foreground='fg', background='bg', font='font')
        if layer == 'table' and (bg := style_cfg.get('background')):
            style_cfg['fieldbackground'] = bg
        ttk_style.configure(name, **style_cfg)
        return style_cfg

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
            tree_view.heading(col.key, text=col.title, anchor=col.anchor_header.value)
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

    def pack_into(self, row: Row):
        self._init_widget(row.frame)
        self.pack_widget(expand=True)

    @cached_property
    def widgets(self) -> list[BaseWidget]:
        widget = self.widget
        try:
            return widget.widgets
        except AttributeError:
            return [widget]


def _style_map_data(style: TtkStyle, name: str, query_opt: str, selected_color: str = None):
    # Based on the fix for setting text color for Tkinter 8.6.9 from: https://core.tcl.tk/tk/info/509cafafae
    base = _filtered_style_map_eles(style, 'Treeview', query_opt)
    rows = _filtered_style_map_eles(style, name, query_opt)
    if selected_color:
        rows.append(('selected', selected_color))
    return rows + base


def _filtered_style_map_eles(style: TtkStyle, name: str, query_opt: str):
    return [ele for ele in style.map(name, query_opt=query_opt) if '!' not in ele[0] and 'selected' not in ele[0]]


def mono_width(text: str) -> int:
    return wcswidth(normalize('NFC', text))
