from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from tkinter.ttk import Treeview, Style as TtkStyle
from typing import TYPE_CHECKING, Any, Union, Callable, Mapping, Iterable

from tk_gui.caching import cached_property
from tk_gui.elements.element import Interactive
from tk_gui.enums import Anchor
from tk_gui.widgets.scroll import ScrollableTreeview
from .utils import _style_map_data, mono_width

if TYPE_CHECKING:
    from tkinter import BaseWidget
    from tk_gui.styles.typing import Font, Layer
    from tk_gui.pseudo_elements import Row

__all__ = ['TreeViewBase', 'Column']
log = logging.getLogger(__name__)

_Width = Union[float, Mapping[Any, Mapping[str, Any]], Iterable[Union[Mapping[str, Any], Any]]]
FormatFunc = Callable[[Any], str]

XGROUND_DEFAULT_HIGHLIGHT_COLOR_MAP = {'foreground': 'SystemHighlightText', 'background': 'SystemHighlight'}


class TreeViewBase(Interactive, ABC):
    widget: Treeview | ScrollableTreeview
    tree_view: Treeview
    row_height: int | None = None
    selected_row_color: tuple[str, str] | None = None

    def enable(self):
        pass

    def disable(self):
        pass

    def pack_into(self, row: Row):
        self._init_widget(row.frame)
        self.pack_widget(expand=True)

    @property
    def _bind_widget(self) -> BaseWidget | None:
        return self.tree_view

    @cached_property
    def widgets(self) -> list[BaseWidget]:
        widget = self.widget
        try:
            return widget.widgets
        except AttributeError:
            return [widget]

    def _ttk_style(self) -> tuple[str, TtkStyle]:
        style = self.style
        # name, ttk_style = style.make_ttk_style('customtable.Treeview')
        name, ttk_style = style.make_ttk_style(f'tk_gui_{self._base_style_layer}.Treeview')
        ttk_style.configure(name, rowheight=self.row_height or style.char_height(self._base_style_layer))

        if base := self._tk_style_config(ttk_style, name, self._base_style_layer):
            if (selected_row_color := self.selected_row_color) and ('foreground' in base or 'background' in base):
                for i, (xground, default) in enumerate(XGROUND_DEFAULT_HIGHLIGHT_COLOR_MAP.items()):
                    if xground in base and (selected := selected_row_color[i]) is not None:
                        ttk_style.map(name, **{xground: _style_map_data(ttk_style, name, xground, selected or default)})

        self._tk_style_config(ttk_style, f'{name}.Heading', f'{self._base_style_layer}_header')  # noqa
        return name, ttk_style

    def _tk_style_config(self, ttk_style: TtkStyle, name: str, layer: Layer) -> dict[str, Font | str | None]:
        style_cfg = self.style.get_map(layer, foreground='fg', background='bg', font='font')
        if layer == self._base_style_layer and (bg := style_cfg.get('background')):
            style_cfg['fieldbackground'] = bg
        ttk_style.configure(name, **style_cfg)
        return style_cfg


class Column:
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
        if width is not None:
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
