"""
Tkinter GUI Scroll Bar Utils

:author: Doug Skrypa
"""

from __future__ import annotations

import logging
import re
import tkinter.constants as tkc
from abc import ABC
from itertools import count
from tkinter import BaseWidget, Frame, LabelFrame, Canvas, Widget, Event, Toplevel, Text, Listbox, TclError
from tkinter.ttk import Scrollbar, Treeview
from typing import TYPE_CHECKING, Type, Mapping, Union, Optional, Any, Iterator, TypeVar, Generic

from tk_gui.caching import cached_property
from tk_gui.enums import ScrollUnit
from tk_gui.utils import ON_WINDOWS

if TYPE_CHECKING:
    from ..styles import Style
    from ..typing import Bool, BindCallback, Axis, XY, TkContainer, ScrollWhat, TkScrollWhat

__all__ = [
    'add_scroll_bar',
    'ScrollableToplevel', 'ScrollableFrame', 'ScrollableLabelFrame',
    'ScrollableTreeview', 'ScrollableText', 'ScrollableListbox',
]
log = logging.getLogger(__name__)

ScrollOuter = Union[BaseWidget, 'ScrollableBase', 'ScrollableContainer']
ScrollAmount = TypeVar('ScrollAmount', int, float)

AXIS_DIR_SIDE_ANCHOR = {'x': (tkc.HORIZONTAL, tkc.BOTTOM, tkc.S), 'y': (tkc.VERTICAL, tkc.RIGHT, tkc.E)}


class AxisConfig(Generic[ScrollAmount]):
    __slots__ = ('what', 'amount', 'scroll', 'fill')

    def __init__(
        self, scroll: bool = False, amount: ScrollAmount = 4, what: ScrollWhat = ScrollUnit.UNITS, fill: bool = False
    ):
        self.what = what = ScrollUnit(what)
        if not isinstance(amount, int) and what != ScrollUnit.PIXELS:
            raise TypeError(f'Invalid type={amount.__class__.__name__} for {amount=} with {what=}')
        self.scroll = scroll
        self.amount = amount
        self.fill = fill

    def view_scroll_args(self, positive: bool) -> tuple[ScrollAmount, TkScrollWhat]:
        amount = self.amount if positive else -self.amount
        return amount, self.what.value


def add_scroll_bar(
    outer: ScrollOuter,
    inner: Widget,
    axis: Axis,
    style: Style = None,
    pack_kwargs: Mapping[str, Any] = None,
) -> Scrollbar:
    direction, side, anchor = AXIS_DIR_SIDE_ANCHOR[axis]
    if style:
        name, ttk_style = style.make_ttk_style(f'scroll_bar.{direction.title()}.TScrollbar')
    else:
        name = ttk_style = None

    scroll_bar = Scrollbar(outer, orient=direction, command=getattr(inner, f'{axis}view'), style=name)

    if style:
        kwargs = style.get_map(
            'scroll',
            troughcolor='trough_color', framecolor='frame_color', bordercolor='frame_color',
            width='bar_width', arrowsize='arrow_width', relief='relief',
        )
        ttk_style.configure(name, **kwargs)
        if (bg := style.scroll.bg.default) and (ac := style.scroll.arrow_color.default):
            bg_list = [('selected', bg), ('active', ac), ('background', bg), ('!focus', bg)]
            ac_list = [('selected', ac), ('active', bg), ('background', bg), ('!focus', ac)]
            ttk_style.map(name, background=bg_list, arrowcolor=ac_list)

    inner.configure(**{f'{axis}scrollcommand': scroll_bar.set})

    kwargs = {'side': side, 'fill': axis, 'anchor': anchor}
    if pack_kwargs:
        # Additional possible kwargs: elementborderwidth, jump, repeatdelay, repeatinterval
        kwargs.update(pack_kwargs)
    # log.debug(f'Packing scrollbar with {kwargs=}')
    scroll_bar.pack(**kwargs)

    return scroll_bar


class ScrollableBase(ABC):
    _tk_w_cls_search = re.compile(r'^(.*?)\d*$').search
    _counter = count()
    _scrollable_cls_names = set()
    _scroll_id: int
    _tk_cls: Type[Union[Widget, Toplevel]] = None
    scroll_bar_y: Optional[Scrollbar] = None
    scroll_bar_x: Optional[Scrollbar] = None

    def __init_subclass__(cls, tk_cls: Type[Union[Widget, Toplevel]] = None):  # noqa
        cls._tk_cls = tk_cls
        cls._scrollable_cls_names.add(cls.__name__.lower())

    def __init__(self: Union[Widget, Toplevel, ScrollableBase], *args, **kwargs):
        if (parent := self._tk_cls) is not None:
            parent.__init__(self, *args, **kwargs)
        else:
            super().__init__(*args, **kwargs)
        self._scroll_id = c = next(self._counter)
        self.scroll_id = f'{self.__class__.__name__}#{c}'

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}[{self._scroll_id}, parent={self.scroll_parent!r}]>'

    @cached_property
    def scroll_parent(self: Union[ScrollableBase, BaseWidget]) -> Optional[ScrollableBase]:
        self_id: str = self._w  # noqa
        id_parts = self_id.split('.!')[:-1]
        for i, id_part in enumerate(reversed(id_parts)):
            if (m := self._tk_w_cls_search(id_part)) and m.group(1) in self._scrollable_cls_names:  # noqa
                return self.nametowidget('.!'.join(id_parts[:-i]))
        return None

    @cached_property
    def scroll_parents(self) -> list[ScrollableBase]:
        parents = []
        sc = self
        while parent := sc.scroll_parent:
            parents.append(parent)
            sc = parent
        return parents

    @cached_property
    def scroll_children(self: Union[ScrollableContainer, BaseWidget]) -> list[ScrollableBase]:
        children = []
        all_children = self.winfo_children()
        while all_children:
            child = all_children.pop()
            if isinstance(child, ScrollableBase):
                children.append(child)
            else:
                all_children.extend(child.winfo_children())
        return children

    def _widgets(self) -> Iterator[BaseWidget]:
        yield self
        if (scroll_bar_y := self.scroll_bar_y) is not None:
            yield scroll_bar_y
        if (scroll_bar_x := self.scroll_bar_x) is not None:
            yield scroll_bar_x

    @cached_property
    def widgets(self) -> tuple[BaseWidget]:
        return tuple(self._widgets())


def get_scrollable(widget: Widget) -> Optional[ScrollableBase]:
    while widget:
        if isinstance(widget, ScrollableBase):
            return widget

        try:
            if (parent_name := widget.winfo_parent()) == '.':
                break
        except AttributeError:  # event.widget may be a string when scrolling in a ttk Combobox
            return None

        widget = widget.nametowidget(parent_name)

    return None


def find_scroll_cb(event: Event, axis: Axis) -> Optional[BindCallback]:
    if not (scrollable := get_scrollable(event.widget)):  # Another window, or scrolling away from a scrollable area
        return None
    elif not isinstance(scrollable, ScrollableContainer):  # it's a ScrollableWidget
        # TODO: If the mouse is over a ScrollableWidget that has no scroll bar for this axis, but is inside a
        #  scrollable container, then that parent should be discovered here, and its scroll cb should be called
        return None
    elif not getattr(scrollable, f'scroll_bar_{axis}'):  # no scroll bar for this axis is configured
        return None
    # log.debug(f'Returning {axis} scroll func for {scrollable=}')
    return getattr(scrollable, f'scroll_{axis}')


def _scroll_y(event: Event):
    if cb := find_scroll_cb(event, 'y'):
        cb(event)


def _scroll_x(event: Event):
    if cb := find_scroll_cb(event, 'x'):
        cb(event)


# region Scrollable Container


class ScrollableContainer(ScrollableBase, ABC):
    _y_bind, _x_bind = ('<MouseWheel>', 'Shift-MouseWheel') if ON_WINDOWS else ('<4>', '<5>')
    canvas: Canvas
    inner_widget: TkContainer
    _x_config: AxisConfig
    _y_config: AxisConfig

    def __init__(
        self: Union[Widget, Toplevel, ScrollableContainer],
        parent: Optional[BaseWidget] = None,
        scroll_y: Bool = False,
        scroll_x: Bool = False,
        inner_cls: Type[TkContainer] = Frame,
        style: Style = None,
        inner_kwargs: dict[str, Any] = None,
        pad: XY = None,
        *,
        fill_x: Bool = False,
        fill_y: Bool = False,
        amount_x: ScrollAmount = 4,
        amount_y: ScrollAmount = 4,
        what_x: ScrollWhat = ScrollUnit.UNITS,
        what_y: ScrollWhat = ScrollUnit.UNITS,
        **kwargs,
    ):
        if 'relief' not in kwargs:
            kwargs.setdefault('borderwidth', 0)
        kwargs.setdefault('highlightthickness', 0)
        self._x_config = AxisConfig(scroll_x, amount_x, what_x, fill_x)
        self._y_config = AxisConfig(scroll_y, amount_y, what_y, fill_y)
        super().__init__(parent, **kwargs)
        self.init_canvas(style, pad)
        self.init_inner(inner_cls, scroll_x or scroll_y, **(inner_kwargs or {}))

    @cached_property
    def _parent_widget(self: ScrollableContainer | Widget | Toplevel) -> TkContainer | None:
        if (parent_name := self.winfo_parent()) == '.':
            return None
        return self.nametowidget(parent_name)

    def init_canvas(self: ScrollOuter, style: Style = None, pad: XY = None):
        kwargs = style.get_map('frame', background='bg') if style else {}
        self.canvas = canvas = Canvas(self, borderwidth=0, highlightthickness=0, **kwargs)
        if self._x_config.scroll:
            self.scroll_bar_x = add_scroll_bar(self, canvas, 'x', style, {'expand': 'false'})
        if self._y_config.scroll:
            self.scroll_bar_y = add_scroll_bar(self, canvas, 'y', style, {'fill': 'y', 'expand': True})

        kwargs = {'side': 'left', 'fill': 'both', 'expand': True}
        try:
            kwargs['padx'], kwargs['pady'] = pad
        except TypeError:
            pass
        canvas.pack(**kwargs)
        canvas.xview_moveto(0)
        canvas.yview_moveto(0)

    def init_inner(self: ScrollOuter, cls: Type[TkContainer], scroll_any: Bool = False, **kwargs):
        if 'relief' not in kwargs:
            kwargs.setdefault('borderwidth', 0)
        kwargs.setdefault('highlightthickness', 0)
        canvas = self.canvas
        self.inner_widget = inner_widget = cls(canvas, **kwargs)
        canvas.create_window(0, 0, window=inner_widget, anchor='nw')
        if scroll_any:
            canvas.bind_all(self._y_bind, _scroll_y, add='+')
            canvas.bind_all(self._x_bind, _scroll_x, add='+')
            self.bind('<Configure>', self.set_scroll_region, add=True)

    # def resize_inner(self, event: Event):
    #     log.debug(f'Resizing inner={self._inner_widget_id!r} to width={event.width}, height={event.height}')
    #     self.canvas.itemconfigure(self._inner_widget_id, width=event.width, height=event.height)

    def scroll_y(self, event: Event):
        if (event.num == 5 or event.delta < 0) and (canvas := self.canvas).yview() != (0, 1):
            # TODO: event.delta / 120 units?
            # canvas.yview_scroll(4, 'units')
            canvas.yview_scroll(*self._y_config.view_scroll_args(True))
        elif (event.num == 4 or event.delta > 0) and (canvas := self.canvas).yview() != (0, 1):
            # canvas.yview_scroll(-4, 'units')
            canvas.yview_scroll(*self._y_config.view_scroll_args(False))

    def scroll_x(self, event: Event):
        if event.num == 5 or event.delta < 0:
            # self.canvas.xview_scroll(4, 'units')
            self.canvas.xview_scroll(*self._x_config.view_scroll_args(True))
        elif event.num == 4 or event.delta > 0:
            # self.canvas.xview_scroll(-4, 'units')
            self.canvas.xview_scroll(*self._x_config.view_scroll_args(False))

    def set_scroll_region(self, event: Event = None):
        """
        Updates the inner region that is scrollable in response to the window/widget being resized / the contents
        changing.  Bound to the ``'<Configure>'`` event.
        """
        fill_x, fill_y = self._x_config.fill, self._y_config.fill
        if not (fill_x or fill_y):
            self._maybe_update_scroll_region()
            return

        inner_widget, parent_frame = self.inner_widget, self._parent_widget
        pf_pack_info = parent_frame.pack_info()
        try:
            iw_pack_info = inner_widget.pack_info()
        except TclError:  # Likely not packed yet
            iw_pack_info = {'ipadx': 0, 'ipady': 0, 'padx': 0, 'pady': 0}

        kwargs = {}
        if fill_x:
            pf_width = parent_frame.winfo_width() - pf_pack_info['ipadx'] - iw_pack_info['padx']
            if pf_width > inner_widget.winfo_width():
                kwargs['width'] = pf_width
        if fill_y:
            pf_height = parent_frame.winfo_height() - pf_pack_info['ipady'] - iw_pack_info['pady']
            if pf_height > inner_widget.winfo_height():
                kwargs['height'] = pf_height

        canvas = self.canvas
        canvas.configure(scrollregion=canvas.bbox('all'), **kwargs)

    def _maybe_update_scroll_region(self):
        canvas = self.canvas
        bbox = canvas.bbox('all')  # top left (x, y), bottom right (x, y) I think ==>> last 2 => (width, height)
        if canvas['scrollregion'] != '{} {} {} {}'.format(*bbox):
            # log.debug(f'Updating scroll region to {bbox=} != {canvas["scrollregion"]=} for {self}')
            canvas.configure(scrollregion=bbox)

    @cached_property
    def widgets(self) -> list[BaseWidget]:
        return [self.canvas, self.inner_widget, *self._widgets()]


class ScrollableToplevel(ScrollableContainer, Toplevel, tk_cls=Toplevel):
    pass


class ScrollableFrame(ScrollableContainer, Frame, tk_cls=Frame):
    pass


class ScrollableLabelFrame(ScrollableContainer, LabelFrame, tk_cls=LabelFrame):
    pass


# endregion

# region Scrollable Widget


class ScrollableWidget(ScrollableBase, ABC):
    _inner_cls: Type[Widget]

    def __init_subclass__(cls, inner_cls: Type[Widget], **kwargs):  # noqa
        super().__init_subclass__(**kwargs)
        cls._inner_cls = inner_cls

    def __init__(
        self, parent: BaseWidget = None, scroll_y: Bool = False, scroll_x: Bool = False, style: Style = None, **kwargs
    ):
        super().__init__(parent)
        self.inner_widget = inner_widget = self._inner_cls(self, **kwargs)
        if scroll_x:
            self.scroll_bar_x = add_scroll_bar(self, inner_widget, 'x', style)
        if scroll_y:
            self.scroll_bar_y = add_scroll_bar(self, inner_widget, 'y', style)
        inner_widget.pack(side='left', fill='both', expand=True, padx=0, pady=0)

    @cached_property
    def widgets(self) -> list[BaseWidget]:
        return [self.inner_widget, *self._widgets()]

    def configure_inner_widget(self, **kwargs):
        return self.inner_widget.configure(**kwargs)


class ScrollableTreeview(ScrollableWidget, Frame, tk_cls=Frame, inner_cls=Treeview):
    inner_widget: Treeview


class ScrollableText(ScrollableWidget, Frame, tk_cls=Frame, inner_cls=Text):
    inner_widget: Text

    def __init__(self, parent: BaseWidget = None, scroll_y: Bool = False, scroll_x: Bool = False, *args, **kwargs):
        super().__init__(parent, scroll_y, scroll_x, *args, **kwargs)
        self.inner_widget.configure(wrap=tkc.NONE if scroll_x else tkc.WORD)


class ScrollableListbox(ScrollableWidget, Frame, tk_cls=Frame, inner_cls=Listbox):
    inner_widget: Listbox


# endregion
