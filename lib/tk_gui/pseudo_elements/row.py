"""
Tkinter GUI core Row class

:author: Doug Skrypa
"""

from __future__ import annotations

import logging
import tkinter.constants as tkc
from abc import ABC, abstractmethod
from tkinter import Frame, LabelFrame, BaseWidget
from typing import TYPE_CHECKING, Optional, Union, Iterable, Sequence, Generic

from tk_gui.caching import cached_property
from tk_gui.enums import Anchor, Justify, Side
from tk_gui.styles import Style
from tk_gui.utils import Inheritable
from tk_gui.typing import Bool, XY, TkFill, E

if TYPE_CHECKING:
    from tk_gui.elements.element import Element, ElementBase  # noqa
    from tk_gui.styles.typing import StyleSpec
    from tk_gui.window import Window
    from .row_container import RowContainer

__all__ = ['Row']
log = logging.getLogger(__name__)

_NotSet = object()
_CENTER_ANCHORS = {tkc.CENTER, None}
_HORIZONTAL_CENTER_ANCHORS = {tkc.CENTER, tkc.N, tkc.S, None}
_VERTICAL_CENTER_ANCHORS = {tkc.CENTER, tkc.W, tkc.E, None}


class RowBase(Generic[E], ABC):
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
    def elements(self) -> Sequence[E]:
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
        return [self.frame, *(w for element in self.elements for w in element.widgets)]  # noqa

    @cached_property
    def widget_id_element_map(self) -> dict[str, Union[RowBase, E]]:
        """Used to populate this row's parent's :attr:`RowContainer.widget_id_element_map`."""
        widget_ele_map = {self.frame._w: self}  # noqa
        setdefault = widget_ele_map.setdefault
        for ele in self.elements:
            try:
                nested_map = ele.widget_id_element_map  # noqa
            except AttributeError:
                for widget in ele.widgets:  # noqa
                    setdefault(widget._w, ele)  # noqa
            else:
                widget_ele_map.update(nested_map)
                setdefault(ele.widget._w, ele)  # noqa

        return widget_ele_map

    @cached_property
    def id_ele_map(self) -> dict[str, E]:
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
                    ele.pack_into_row(self)
                except Exception:
                    log.error(f'Encountered unexpected error packing element={ele} into row={self}', exc_info=True)
                    raise
        else:
            for ele in self.elements:
                ele.pack_into_row(self)


class Row(RowBase[E]):
    _anchor: Optional[Anchor] = None
    ignore_grab: bool = False
    frame: Optional[Frame] = None       # This satisfies the abstract property req while letting it be assigned in pack
    expand: Optional[bool] = None       # Set to True only for Column elements
    fill: Optional[bool] = None         # Changes for Column, Separator, StatusBar
    elements: tuple[E, ...] = ()        # This satisfies the abstract property req while letting it be assigned in init

    def __init__(self, parent: RowContainer, elements: Iterable[E]):
        self.parent = parent
        self.elements = tuple(elements)

    def __str__(self) -> str:
        return self.repr(False)

    def __repr__(self) -> str:
        return self.repr(True)

    def repr(self, include_index: bool = True) -> str:
        parent = self.parent
        parent_cls = parent.__class__.__name__
        n_eles = len(self.elements)
        anchor, expand, fill = self._anchor_expand_and_fill()
        if include_index:
            # In some cases, including the index can result in an infinite loop
            try:
                index = parent.rows.index(self)
            except (IndexError, ValueError, AttributeError):
                index = '?'
        else:
            index = '?'
        return f'<{self.__class__.__name__}[{parent_cls=!s}, {index=}, {n_eles=}, {anchor=}, {expand=}, {fill=}]>'

    @classmethod
    def custom(
        cls,
        parent: RowContainer,
        elements: Iterable[E],
        *,
        anchor: Union[str, Anchor] = _NotSet,
        expand: bool = None,
        fill: TkFill = None,
        style: StyleSpec = None,
    ) -> Row:
        self = cls(parent, elements)
        if anchor is not _NotSet:
            self._anchor = Anchor(anchor)
        if expand is not None:
            self.expand = expand
        if fill is not None:
            self.fill = fill
        if style:
            self.style = Style.get_style(style)
        return self

    @property
    def parent_rc(self) -> RowContainer:
        return self.parent

    @property
    def anchor(self) -> Anchor:
        if (anchor := self._anchor) is not None:
            return anchor
        return self.anchor_elements

    def _anchor_expand_and_fill(self) -> tuple[Anchor, bool, TkFill]:
        anchor, expand, fill = self.anchor, self.expand, self.fill
        if expand is fill is None:
            # if anchor.is_abs_center:
            #     return anchor, True, tkc.BOTH
            return anchor, anchor.is_any_center, anchor.abs_fill_axis

        if expand is None:
            if fill and fill != tkc.NONE:
                expand = True
            else:
                expand = anchor.is_abs_center
        if fill is None:
            fill = anchor.abs_fill_axis if expand else tkc.NONE
        return anchor, expand, fill

    def pack(self, debug: Bool = False):
        # log.debug(f'Packing row {self.num} in {self.parent=} {self.parent.tk_container=}')
        if bg := self.style.base.bg.default:
            kwargs = {'background': bg}
        else:
            kwargs = {}
        self.frame = frame = Frame(self.parent.tk_container, **kwargs)
        self.pack_elements(debug)

        anchor, expand, fill = self._anchor_expand_and_fill()
        # anchor = self.anchor
        # if (expand := self.expand) is None:
        #     expand = anchor.is_abs_center
        # if (fill := self.fill) is None:
        #     fill = anchor.abs_fill_axis

        # log.debug(f'Packing row with {anchor=}, {center=}, {expand=}, {fill=}')
        # log.debug(f'Packing {self!r}', extra={'color': 14})
        frame.pack(side=tkc.TOP, anchor=anchor.value, padx=0, pady=0, expand=expand, fill=fill)

    def apply_style(self):
        if bg := self.style.base.bg.default:
            self.frame.configure(background=bg)
