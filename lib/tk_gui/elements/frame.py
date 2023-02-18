"""
Tkinter GUI Frames

:author: Doug Skrypa
"""

from __future__ import annotations

import logging
from abc import ABC
from tkinter import Frame as TkFrame, LabelFrame
from typing import TYPE_CHECKING, Optional, Union, Type, Literal, Any, Callable, Sequence

from tk_gui.enums import Anchor
from tk_gui.pseudo_elements.row import RowBase
from tk_gui.pseudo_elements.row_container import RowContainer
from tk_gui.styles import Style, StyleSpec
from tk_gui.utils import call_with_popped, extract_kwargs
from tk_gui.widgets.scroll import ScrollableFrame, ScrollableLabelFrame
from .element import Element, InteractiveMixin

if TYPE_CHECKING:
    from tk_gui.typing import Layout, Bool, XY, TkContainer
    from tk_gui.pseudo_elements.row import Row

__all__ = [
    'RowFrame', 'InteractiveRowFrame', 'BasicRowFrame', 'BasicInteractiveRowFrame',
    'Frame', 'InteractiveFrame',
    'ScrollFrame', 'InteractiveScrollFrame', 'YScrollFrame', 'XScrollFrame',
]
log = logging.getLogger(__name__)

TkFrameType = Type[Union[TkFrame, LabelFrame]]
FrameMode = Literal['inner', 'outer', 'both']
_Anchor = Union[str, Anchor]


class FrameMixin:
    # Element attributes / methods
    widget: Union[TkFrame, LabelFrame]
    size: Optional[XY]
    style: Style
    _style_config: dict[str, Any]
    allow_focus: bool
    pack_rows: Callable
    pack_widget: Callable
    grid_rows: Callable
    # Mixin-specific attributes
    border: Bool
    title: Optional[str]
    anchor_title: Anchor
    pack_propagate: Bool = None
    grid: Bool = False

    def init_frame(
        self,
        title: str = None,
        anchor_title: _Anchor = None,
        border: Bool = False,
        pack_propagate: Bool = None,
        grid: Bool = False,
    ):
        self.title = title
        self.anchor_title = Anchor(anchor_title)
        self.border = border
        if pack_propagate is not None:
            self.pack_propagate = pack_propagate
        if grid:
            self.grid = grid

    def init_frame_from_kwargs(self, kwargs: dict[str, Any]):
        call_with_popped(self.init_frame, ('title', 'anchor_title', 'border', 'pack_propagate', 'grid'), kwargs)

    @property
    def tk_container(self) -> Union[TkFrame, LabelFrame]:
        return self.widget

    @property
    def style_config(self) -> dict[str, Any]:
        style = self.style
        config = {
            **style.get_map('frame', bd='border_width', background='bg', relief='relief'),
            **self._style_config,
        }
        if self.border:
            config.setdefault('relief', 'groove')
            config.update(style.get_map('frame', highlightcolor='bg', highlightbackground='bg'))
        if self.title:
            config.update(style.get_map('frame', foreground='fg', font='font'))

        return config

    def _init_widget(self, tk_container: TkContainer):
        kwargs = self.style_config
        if title := self.title:
            kwargs['text'] = title
            if (anchor := self.anchor_title) != Anchor.NONE:
                kwargs['labelanchor'] = anchor.value
            frame_cls = LabelFrame
        else:
            frame_cls = TkFrame
        try:
            width, height = self.size
        except TypeError:
            pass
        else:
            kwargs['width'], kwargs['height'] = width, height

        self.widget = frame_cls(tk_container, takefocus=int(self.allow_focus), **kwargs)

    def pack_into(self, row: Row):
        self._init_widget(row.frame)
        if self.grid:
            self.grid_rows()
        else:
            self.pack_rows()
        self.pack_widget()
        if (pack_propagate := self.pack_propagate) is not None:
            frame = self.widget
            try:
                width, height = self.size
            except TypeError:
                width = height = None
            # Setting pack_propagate=False results in the frame retaining its configured size instead of shrinking
            # to fit the elements it contains, but it may cause undesirable results if the window size changes, etc.
            # More info: https://stackoverflow.com/a/566840/19070573
            if not pack_propagate:
                frame.update_idletasks()  # Required for the required height/width to be correct
                if width is None:
                    width = frame.winfo_reqwidth()
                if height is None:
                    height = frame.winfo_reqheight()
                frame.configure(width=width, height=height)
            frame.pack_propagate(pack_propagate)


# region RowFrame


class RowFrame(FrameMixin, RowBase, Element, ABC, base_style_layer='frame'):
    """
    A compound element that behaves both like a single :class:`.Element` and like a :class:`.Row` that contains other
    elements.  Compound elements that do not contain multiple rows can extend this instead of a Frame-like class that
    extends :class:`.RowContainer` to be lighter-weight since a RowContainer would contain at least one more additional
    nested Frame widget.
    """

    def __init__(self, **kwargs):
        self.init_frame_from_kwargs(kwargs)
        Element.__init__(self, **kwargs)
        # Note: self.parent is set in Element.pack_into_row

    def __repr__(self) -> str:
        key, size, visible, elements = self._key, self.size, self._visible, len(self.elements)
        key_str = f'{key=}, ' if key else ''
        return f'<{self.__class__.__name__}[id={self.id}, {key_str}{size=}, {visible=}, {elements=}]>'

    @property
    def parent_rc(self) -> RowContainer:
        return self.parent.parent_rc  # self.parent is a Row

    @property
    def frame(self) -> Union[TkFrame, LabelFrame]:
        return self.widget

    def pack_rows(self, debug: Bool = False):
        self.pack_elements(debug)

    def grid_rows(self):
        for c, ele in enumerate(self.elements):
            ele.grid_into_frame(self, 0, c)

        self.frame.grid_rowconfigure(1, weight=1)
        self.frame.grid_columnconfigure(1, weight=1)


class BasicRowFrame(RowFrame):
    elements: Sequence[Element] = None  # Necessary to satisfy the ABC

    def __init__(self, elements: Sequence[Element], **kwargs):
        super().__init__(**kwargs)
        self.elements = elements


class InteractiveRowFrame(InteractiveMixin, RowFrame, ABC):
    def __init__(self, **kwargs):
        self.init_interactive_from_kwargs(kwargs)
        super().__init__(**kwargs)

    def __repr__(self) -> str:
        key, size, visible, elements, disabled = self._key, self.size, self._visible, len(self.elements), self.disabled
        key_str = f'{key=}, ' if key else ''
        return f'<{self.__class__.__name__}[id={self.id}, {key_str}{size=}, {visible=}, {elements=}, {disabled=}]>'

    def enable(self):
        if not self.disabled:
            return

        for ele in self.elements:
            try:
                ele.enable()  # noqa
            except AttributeError:
                pass

        self.disabled = False

    def disable(self):
        if self.disabled:
            return

        for ele in self.elements:
            try:
                ele.disable()  # noqa
            except AttributeError:
                pass

        self.disabled = True


class BasicInteractiveRowFrame(InteractiveRowFrame):
    elements: Sequence[Element] = None  # Necessary to satisfy the ABC

    def __init__(self, elements: Sequence[Element], **kwargs):
        super().__init__(**kwargs)
        self.elements = elements


# endregion


class CustomLayoutRowContainer(RowContainer, ABC):
    def get_custom_layout(self) -> Layout:  # noqa
        """
        Intended to be overridden by subclasses to provide a standardized way of defining additional rows / a custom
        layout for compound elements.

        See :class:`InteractiveFrame` for the interactive version of this class.

        For single-row compound elements, the classes intended to be extended for this purpose are :class:`.RowFrame`
        and :class:`.InteractiveRowFrame`, and the equivalent method to this one is :meth:`.RowBase.elements`.
        """
        return []

    def pack_rows(self, debug: Bool = False):
        if layout := self.get_custom_layout():
            self.add_rows(layout)
        super().pack_rows(debug)

    def grid_rows(self):
        if layout := self.get_custom_layout():
            self.add_rows(layout)
        super().grid_rows()


class Frame(FrameMixin, Element, CustomLayoutRowContainer, base_style_layer='frame'):
    def __init__(self, layout: Layout = None, **kwargs):
        self.init_frame_from_kwargs(kwargs)
        self.init_container_from_kwargs(layout, kwargs=kwargs)
        Element.__init__(self, **kwargs)

    def __repr__(self) -> str:
        key, size, visible, rows = self._key, self.size, self._visible, len(self.rows)
        key_str = f'{key=}, ' if key else ''
        return f'<{self.__class__.__name__}[id={self.id}, {key_str}{size=}, {visible=}, {rows=}]>'


class InteractiveFrameMixin(InteractiveMixin):
    rows: list[Row]

    def enable(self):
        if not self.disabled:
            return

        for row in self.rows:
            for ele in row.elements:
                try:
                    ele.enable()  # noqa
                except AttributeError:
                    pass

        self.disabled = False

    def disable(self):
        if self.disabled:
            return

        for row in self.rows:
            for ele in row.elements:
                try:
                    ele.disable()  # noqa
                except AttributeError:
                    pass

        self.disabled = True


class InteractiveFrame(InteractiveFrameMixin, Frame, ABC):
    def __init__(self, layout: Layout = None, **kwargs):
        self.init_interactive_from_kwargs(kwargs)
        super().__init__(layout, **kwargs)

    def __repr__(self) -> str:
        key, size, visible, rows, disabled = self._key, self.size, self._visible, len(self.rows), self.disabled
        key_str = f'{key=}, ' if key else ''
        return f'<{self.__class__.__name__}[id={self.id}, {key_str}{size=}, {visible=}, {rows=}, {disabled=}]>'


class ScrollFrame(Element, CustomLayoutRowContainer, base_style_layer='frame'):
    widget: Union[ScrollableLabelFrame, ScrollableFrame]
    inner_frame: Union[TkFrame, LabelFrame]
    inner_style: Optional[Style] = None
    grid: Bool = False

    def __init__(
        self,
        layout: Layout = None,
        title: str = None,
        *,
        anchor_title: _Anchor = None,
        border: Bool = False,
        title_mode: FrameMode = 'outer',
        border_mode: FrameMode = 'outer',
        inner_style: StyleSpec = None,
        grid: Bool = False,
        **kwargs,
    ):
        self.init_container_from_kwargs(layout, kwargs=kwargs)
        Element.__init__(self, **kwargs)
        self.title = title
        self.title_mode = title_mode
        self.anchor_title = Anchor(anchor_title)
        self.border = border
        self.border_mode = border_mode
        if inner_style:
            self.inner_style = Style.get_style(inner_style)
        if grid:
            self.grid = grid

    def __repr__(self) -> str:
        key, size, visible, rows = self._key, self.size, self._visible, len(self.rows)
        scroll_x, scroll_y = self.x_config.scroll, self.y_config.scroll
        key_str = f'{key=}, ' if key else ''
        cls_name = self.__class__.__name__
        return f'<{cls_name}[id={self.id}, {key_str}{size=}, {visible=}, {rows=}, {scroll_x=}, {scroll_y=}]>'

    @property
    def tk_container(self) -> TkFrame:
        return self.inner_frame

    def _prepare_pack_kwargs(self) -> dict[str, Any]:
        style = self.style
        outer_kw: dict[str, Any] = style.get_map('frame', bd='border_width', background='bg', relief='relief')
        if inner_style := self.inner_style:
            inner_kw = inner_style.get_map('frame', bd='border_width', background='bg', relief='relief')
        else:
            inner_style = style
            inner_kw = outer_kw.copy()

        inner_kw['takefocus'] = outer_kw['takefocus'] = int(self.allow_focus)
        if self.border:
            if self.border_mode in {'outer', 'both'}:
                outer_kw.setdefault('relief', 'groove')
                outer_kw.update(style.get_map('frame', highlightcolor='bg', highlightbackground='bg'))
            if self.border_mode in {'inner', 'both'}:
                inner_kw.setdefault('relief', 'groove')
                inner_kw.update(inner_style.get_map('frame', highlightcolor='bg', highlightbackground='bg'))

        if title := self.title:
            common = {'text': title}
            if (anchor := self.anchor_title) != Anchor.NONE:
                common['labelanchor'] = anchor.value
                # labelwidget: The widget to use as the label

            if self.title_mode in {'outer', 'both'}:
                outer_kw.update(common)
                outer_kw.update(style.get_map('frame', foreground='fg', font='font'))
            if self.title_mode in {'inner', 'both'}:
                outer_kw['inner_cls'] = LabelFrame
                inner_kw.update(common)
                inner_kw.update(inner_style.get_map('frame', foreground='fg', font='font'))

        outer_kw['style'] = style
        outer_kw['inner_kwargs'] = inner_kw
        return outer_kw

    def _init_widget(self, tk_container: TkContainer):
        kwargs = self._prepare_pack_kwargs()
        labeled = self.title and self.title_mode in {'outer', 'both'}
        outer_cls = ScrollableLabelFrame if labeled else ScrollableFrame
        self.widget = outer_frame = outer_cls(
            self.parent.frame, x_config=self.x_config, y_config=self.y_config, **kwargs
        )
        self.inner_frame = outer_frame.inner_widget

    def pack_into(self, row: Row):
        self._init_widget(row.frame)
        outer_frame = self.widget
        if self.grid:
            self.grid_rows()
        else:
            self.pack_rows()
        outer_frame.resize_scroll_region(self.size)
        self.pack_widget()

    def update_scroll_region(self, size: Optional[XY] = None):
        self.widget.resize_scroll_region(size)


class InteractiveScrollFrame(InteractiveFrameMixin, ScrollFrame):
    def __init__(self, layout: Layout = None, title: str = None, **kwargs):
        self.init_interactive_from_kwargs(kwargs)
        super().__init__(layout, title, **kwargs)

    def __repr__(self) -> str:
        key, size, visible, rows, disabled = self._key, self.size, self._visible, len(self.rows), self.disabled
        scroll_x, scroll_y = self.x_config.scroll, self.y_config.scroll
        key_str = f'{key=}, ' if key else ''
        cls_name = self.__class__.__name__
        return (
            f'<{cls_name}[id={self.id}, {key_str}{size=}, {visible=}, {rows=}, {scroll_x=}, {scroll_y=}, {disabled=}]>'
        )


def YScrollFrame(layout: Layout = None, title: str = None, **kwargs) -> ScrollFrame:
    kwargs.setdefault('scroll_y', True)
    return ScrollFrame(layout, title, **kwargs)


def XScrollFrame(layout: Layout = None, title: str = None, **kwargs) -> ScrollFrame:
    kwargs.setdefault('scroll_x', True)
    return ScrollFrame(layout, title, **kwargs)
