"""
Tkinter GUI core Row class

:author: Doug Skrypa
"""

from __future__ import annotations

import logging
import tkinter.constants as tkc
from abc import ABC, abstractmethod
from tkinter import Frame, LabelFrame, BaseWidget
from typing import TYPE_CHECKING, Optional, Union, Iterable, Sequence

from tk_gui.caching import cached_property, clear_cached_properties
from tk_gui.enums import Anchor, Justify, Side
from tk_gui.styles import Style
from tk_gui.utils import Inheritable

if TYPE_CHECKING:
    from tk_gui.elements.element import Element, ElementBase
    from tk_gui.typing import Bool, XY
    from tk_gui.window import Window
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

    # region Abstract Properties

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

    # endregion

    @cached_property
    def widgets(self) -> list[BaseWidget]:
        return [self.frame, *(w for element in self.elements for w in element.widgets)]

    @cached_property
    def widget_id_element_map(self) -> dict[str, Union[RowBase, ElementBase]]:
        """Used to populate this row's parent's :attr:`RowContainer.widget_id_element_map`."""
        widget_ele_map = {self.frame._w: self}  # noqa
        setdefault = widget_ele_map.setdefault
        for ele in self.elements:
            try:
                nested_map = ele.widget_id_element_map  # noqa
            except AttributeError:
                for widget in ele.widgets:
                    setdefault(widget._w, ele)  # noqa
            else:
                widget_ele_map.update(nested_map)
                setdefault(ele.widget._w, ele)  # noqa

        return widget_ele_map

    @cached_property
    def id_ele_map(self) -> dict[str, Element]:
        return {ele.id: ele for ele in self.elements}

    @property
    def window(self) -> Window:
        return self.parent_rc.window

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
