"""
Tkinter GUI core Row class

:author: Doug Skrypa
"""

from __future__ import annotations

import logging
import tkinter.constants as tkc
from abc import ABC, abstractmethod
from functools import cached_property
from tkinter import Frame, LabelFrame, Widget, BaseWidget
from typing import TYPE_CHECKING, Optional, Union, Iterable, Sequence

from ..enums import Anchor, Justify, Side
from ..styles import Style
from ..utils import Inheritable

if TYPE_CHECKING:
    from ..elements.element import Element, ElementBase
    from ..typing import Bool, XY
    from ..window import Window
    from .row_container import RowContainer

__all__ = ['Row']
log = logging.getLogger(__name__)


class RowBase(ABC):
    parent: Optional[Union[RowBase, RowContainer]]
    anchor_elements: Anchor = Inheritable(type=Anchor, attr_name='parent_rc')
    text_justification: Justify = Inheritable(type=Justify, attr_name='parent_rc')
    element_side: Side = Inheritable(type=Side, attr_name='parent_rc')
    element_padding: XY = Inheritable(attr_name='parent_rc')
    element_size: XY = Inheritable(attr_name='parent_rc')
    style: Style = Inheritable(attr_name='parent_rc')
    auto_size_text: bool = Inheritable(attr_name='parent_rc')

    @property
    @abstractmethod
    def parent_rc(self) -> RowContainer:
        raise NotImplementedError

    @property
    @abstractmethod
    def frame(self) -> Union[Frame, LabelFrame]:
        raise NotImplementedError

    @property
    @abstractmethod
    def elements(self) -> Sequence[Element]:
        """
        Intended to be overridden by subclasses to provide a standardized way of defining custom element members for
        compound elements.

        See :class:`.RowFrame` and :class:`.InteractiveRowFrame` for the higher level classes intended to be extended
        for this purpose.

        See :meth:`.Frame.get_custom_layout` for the equivalent method for multi-row compound elements.
        """
        raise NotImplementedError

    @cached_property
    def widgets(self) -> list[BaseWidget]:
        return [self.frame, *(w for element in self.elements for w in element.widgets)]

    @cached_property
    def widget_element_map(self) -> dict[BaseWidget, Union[RowBase, ElementBase]]:
        widget_ele_map = {self.frame: self}
        setdefault = widget_ele_map.setdefault
        for ele in self.elements:
            try:
                nested_map = ele.widget_element_map  # noqa
            except AttributeError:
                for widget in ele.widgets:
                    setdefault(widget, ele)
            else:
                widget_ele_map.update(nested_map)
                setdefault(ele.widget, ele)

        return widget_ele_map

    @cached_property
    def id_ele_map(self) -> dict[str, Element]:
        return {ele.id: ele for ele in self.elements}

    @property
    def window(self) -> Window:
        return self.parent_rc.window

    def __getitem__(self, index_or_id: Union[int, str]):
        try:
            return self.id_ele_map[index_or_id]
        except KeyError:
            pass
        try:
            return self.elements[index_or_id]
        except (IndexError, TypeError):
            pass
        raise KeyError(f'Invalid column / index / element ID: {index_or_id!r}')

    def __contains__(self, item: Union[Element, Widget]) -> bool:
        if isinstance(item, Widget):
            if self.frame is item:
                return True
            for element in self.elements:
                if element.widget is item:
                    return True
            return False
        else:
            return item in self.elements

    def pack_elements(self, debug: Bool = False):
        if debug:
            n_eles = len(self.elements)
            for i, ele in enumerate(self.elements):
                log.debug(f' > Packing element {i} / {n_eles}')
                try:
                    ele.pack_into_row(self, i)
                except Exception:
                    log.error(f'Encountered unexpected error packing element={ele} into row={self}', exc_info=True)
                    raise
        else:
            for i, ele in enumerate(self.elements):
                ele.pack_into_row(self, i)


class Row(RowBase):
    ignore_grab: bool = False
    frame: Optional[Frame] = None       # This satisfies the abstract property req while letting it be assigned in pack
    expand: Optional[bool] = None       # Set to True only for Column elements
    fill: Optional[bool] = None         # Changes for Column, Separator, StatusBar
    elements: tuple[Element, ...] = ()  # This satisfies the abstract property req while letting it be assigned in init

    def __init__(self, parent: RowContainer, elements: Iterable[Element], num: int):
        self.num = num
        self.parent = parent
        self.elements = tuple(elements)

    @property
    def parent_rc(self) -> RowContainer:
        return self.parent

    @property
    def anchor(self):
        return self.anchor_elements.value

    def pack(self, debug: Bool = False):
        # log.debug(f'Packing row {self.num} in {self.parent=} {self.parent.tk_container=}')
        self.frame = frame = Frame(self.parent.tk_container)
        self.pack_elements(debug)
        anchor = self.anchor
        center = anchor == tkc.CENTER or anchor is None
        if (expand := self.expand) is None:
            expand = center
        if (fill := self.fill) is None:
            fill = tkc.BOTH if center else tkc.NONE
        # log.debug(f'Packing row with {anchor=}, {center=}, {expand=}, {fill=}')
        frame.pack(side=tkc.TOP, anchor=anchor, padx=0, pady=0, expand=expand, fill=fill)
        if bg := self.style.base.bg.default:
            frame.configure(background=bg)

    def apply_style(self):
        if bg := self.style.base.bg.default:
            self.frame.configure(background=bg)
