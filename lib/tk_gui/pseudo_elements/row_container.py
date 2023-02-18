"""
Tkinter GUI row container

:author: Doug Skrypa
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from itertools import count
from tkinter import Toplevel, Frame, BaseWidget
from typing import TYPE_CHECKING, Optional, Union, Any, Iterator, Type, Generic, overload

from tk_gui.caching import cached_property
from tk_gui.enums import Anchor, Justify, Side
from tk_gui.styles import Style, StyleSpec
from tk_gui.utils import call_with_popped
from tk_gui.typing import XY, Layout, Bool, TkContainer, E
from .row import Row, RowBase

if TYPE_CHECKING:
    from tk_gui.elements.element import ElementBase
    from tk_gui.window import Window
    from tk_gui.widgets.scroll import ScrollableContainer, ScrollableToplevel

__all__ = ['RowContainer', 'CONTAINER_PARAMS']
log = logging.getLogger(__name__)

CONTAINER_PARAMS = {
    'anchor_elements', 'text_justification', 'element_side', 'element_padding', 'element_size',
    'scroll_y', 'scroll_x', 'scroll_y_div', 'scroll_x_div',
}

ElementLike = Union[RowBase, E, 'RowContainer']


class RowContainer(Generic[E], ABC):
    _counter = count()
    ignore_grab: bool = False
    scroll_y: Bool = False
    scroll_x: Bool = False
    scroll_y_div: float = 2
    scroll_x_div: float = 1
    anchor_elements: Anchor
    text_justification: Justify
    element_side: Side
    element_padding: Optional[XY]
    element_size: Optional[XY]
    rows: list[Row[E]]

    # region Init Overload

    @overload
    def __init__(
        self,
        layout: Layout[E] = None,
        *,
        style: StyleSpec = None,
        anchor_elements: Union[str, Anchor] = None,
        text_justification: Union[str, Justify] = None,
        element_side: Union[str, Side] = None,
        element_padding: XY = None,
        element_size: XY = None,
        scroll_y: Bool = False,
        scroll_x: Bool = False,
        scroll_y_div: float = None,
        scroll_x_div: float = None,
    ):
        ...

    # endregion

    def __init__(self, layout: Layout[E] = None, *, style: StyleSpec = None, **kwargs):
        self._id = next(self._counter)
        self.style = Style.get_style(style)
        self.init_container(layout, **kwargs)

    def init_container_from_kwargs(self, *args, kwargs: dict[str, Any]):
        call_with_popped(self.init_container, CONTAINER_PARAMS, kwargs, args)

    def init_container(
        self,
        layout: Layout[E] = None,
        anchor_elements: Union[str, Anchor] = None,
        text_justification: Union[str, Justify] = None,
        element_side: Union[str, Side] = None,
        element_padding: XY = None,
        element_size: XY = None,
        scroll_y: Bool = False,
        scroll_x: Bool = False,
        scroll_y_div: float = None,
        scroll_x_div: float = None,
    ):
        self.anchor_elements = Anchor(anchor_elements)
        self.text_justification = Justify(text_justification)
        self.element_side = Side(element_side) if element_side else Side.LEFT
        self.element_padding = element_padding
        self.element_size = element_size
        self.rows = [row for row in self._normalize_rows(layout)] if layout else []
        self.scroll_y = scroll_y
        self.scroll_x = scroll_x
        self.scroll_y_div = scroll_y_div
        self.scroll_x_div = scroll_x_div

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}[{self._id}]>'

    def _normalize_rows(self, layout: Layout[E], row_cls: Type[Row] = Row) -> Iterator[Row[E]]:
        for raw_row in layout:
            if isinstance(raw_row, row_cls):
                log.debug(f'Found pre-built row={raw_row!s}', extra={'color': 11})
                yield raw_row
            else:
                yield row_cls(self, raw_row)

    def add_rows(self, layout: Layout[E], pack: Bool = False, debug: Bool = False, update: Bool = False):
        if not pack:
            self.rows.extend(self._normalize_rows(layout))
        elif debug:
            update_idletasks = self.widget.update_idletasks
            n_rows = len(self.rows)
            for i, row in enumerate(self._add_rows(layout), n_rows):
                log.debug(f'Packing row {i} / {n_rows}')
                row.pack(debug)
                if update:
                    update_idletasks()
        elif update:
            update_idletasks = self.widget.update_idletasks
            for row in self._add_rows(layout):
                row.pack(debug)
                update_idletasks()
        else:
            added = [row for row in self._add_rows(layout)]
            for row in added:
                row.pack()

    def _add_rows(self, layout: Layout[E]):
        rows = self.rows
        for row in self._normalize_rows(layout):
            rows.append(row)
            yield row

    # region Abstract Properties

    @property
    @abstractmethod
    def widget(self) -> Union[Frame, Toplevel, ScrollableToplevel]:
        raise NotImplementedError

    @property
    @abstractmethod
    def tk_container(self) -> TkContainer:
        raise NotImplementedError

    @property
    @abstractmethod
    def window(self) -> Window:
        raise NotImplementedError

    @property
    def frame(self) -> TkContainer:
        return self.tk_container

    # endregion

    # region Widget / Element Contents

    @cached_property
    def widgets(self) -> list[BaseWidget]:
        """Primarily used during population of ``widget_id_element_map`` properties."""
        widgets = [w for row in self.rows for w in row.widgets]
        try:
            widgets.extend(self.widget.widgets)
        except AttributeError:
            widgets.append(self.widget)
        return widgets

    def __iter_widget_eles(self) -> Iterator[tuple[str, ElementLike, ElementLike]]:
        """Used to build :attr:`.widget_id_element_map`."""
        for row in self.rows:
            for widget_id, ele in row.widget_id_element_map.items():
                yield widget_id, ele, ele

        try:
            widgets = self.widget.widgets
        except AttributeError:
            widgets = (self.widget,)

        for widget in widgets:
            yield widget._w, self, widget  # noqa

    @cached_property
    def widget_id_element_map(self) -> dict[str, ElementLike]:
        """
        This mapping is used for the following use cases:
            - Used by Window when grab_anywhere is enabled to find which Element was clicked, in case it was configured
              to ``ignore_grab``.
            - Used by the following attributes / methods:
                - id_ele_map
                - all_elements
            - Used by :meth:`.__getitem__`
        """
        widget_ele_map = {}
        setdefault = widget_ele_map.setdefault
        for widget, ele, maybe_has_map in self.__iter_widget_eles():
            setdefault(widget, ele)
            # TODO: This seems to be mapping widget IDs to the frame that contains a given element in many cases
            try:
                nested_map = maybe_has_map.widget_id_element_map
            except AttributeError:
                pass
            else:
                widget_ele_map.update(nested_map)

        return widget_ele_map

    @cached_property
    def id_ele_map(self) -> dict[str, E]:
        id_ele_map = {}
        for ele in self.widget_id_element_map.values():
            try:
                id_ele_map[ele.id] = ele
            except AttributeError:
                pass
        return id_ele_map

    def all_elements(self) -> Iterator[Union[E, Row[E]]]:
        from ..elements.element import ElementBase

        yield from (e for e in self.widget_id_element_map.values() if isinstance(e, (ElementBase, Row)))

    def __getitem__(self, item: Union[str, BaseWidget]) -> E:
        """
        :param item: A widget, widget ID (assigned by tk/tkinter), or element ID (assigned in
          :meth:`ElementBase.__init__`).
        :return: The Element associated with the given identifier/widget.
        """
        # log.warning(f'{self!r}[{item!r}]', extra={'color': 9}, stack_info=True)
        orig_item = item
        if isinstance(item, BaseWidget):
            item = item._w  # noqa
        if isinstance(item, str):
            try:
                return self.id_ele_map[item]
            except KeyError:
                pass
            try:
                return self.widget_id_element_map[item]
            except KeyError:
                pass
        else:
            raise TypeError(f'Unexpected type={orig_item.__class__.__name__} for element identifier={orig_item!r}')

        raise KeyError(f'Invalid element ID/key / widget: {orig_item!r}')

    # endregion

    def _scroll_divisors(self) -> tuple[float, float]:
        x_div, y_div = self.scroll_x_div, self.scroll_y_div
        if x_div is None:
            x_div = 1
        if y_div is None:
            y_div = 1.5
        return x_div, y_div

    def _update_scroll_region(self, outer: ScrollableContainer, inner: TkContainer, size: Optional[XY]):
        inner.update_idletasks()  # Required for the required height/width to be correct
        try:
            width, height = size
        except TypeError:
            x_div, y_div = self._scroll_divisors()
            req_width = inner.winfo_reqwidth()
            req_height = inner.winfo_reqheight()
            width = req_width // x_div
            height = req_height // y_div
            # log.debug(f'Using size=({width}, {height}) for required=({req_width}, {req_height})')

        canvas = outer.canvas
        canvas.configure(scrollregion=canvas.bbox('all'), width=width, height=height)

    def pack_rows(self, debug: Bool = False):
        # PySimpleGUI: PackFormIntoFrame(window, master, window)
        if debug:
            n_rows = len(self.rows)
            for i, row in enumerate(self.rows):
                log.debug(f'Packing row {i} / {n_rows}')
                row.pack(debug)
        else:
            for row in self.rows:
                row.pack()

    def grid_rows(self):
        for r, row in enumerate(self.rows):
            for c, ele in enumerate(row.elements):
                ele.grid_into_frame(self, r, c)

        self.frame.grid_rowconfigure(1, weight=1)
        self.frame.grid_columnconfigure(1, weight=1)
