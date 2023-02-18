"""
Tkinter GUI Scroll Bar Utils

:author: Doug Skrypa
"""

from __future__ import annotations

import logging
import re
import tkinter.constants as tkc
from abc import ABC
from tkinter import BaseWidget, Frame, LabelFrame, Canvas, Widget, Event, Toplevel, Text, Listbox
from tkinter.ttk import Scrollbar, Treeview
from typing import TYPE_CHECKING, Type, Mapping, Union, Optional, Any, Iterator

from tk_gui.caching import cached_property
from tk_gui.utils import ON_WINDOWS
from .config import AxisConfig
from .utils import get_parent_or_none

if TYPE_CHECKING:
    from tk_gui.styles import Style
    from tk_gui.typing import Bool, BindCallback, Axis, XY, TkContainer

__all__ = [
    'ScrollableToplevel', 'ScrollableFrame', 'ScrollableLabelFrame',
    'ScrollableTreeview', 'ScrollableText', 'ScrollableListbox',
]
log = logging.getLogger(__name__)

ScrollOuter = Union[BaseWidget, 'ScrollableBase', 'ScrollableContainer']

AXIS_DIR_SIDE_ANCHOR = {'x': (tkc.HORIZONTAL, tkc.BOTTOM, tkc.S), 'y': (tkc.VERTICAL, tkc.RIGHT, tkc.E)}


class ScrollableBase(BaseWidget, ABC):
    """Base class for scrollable widgets and containers."""
    _tk_w_cls_search = re.compile(r'^(.*?)\d*$').search
    _scrollable_cls_names = set()

    _w: str  # Inherited from BaseWidget
    scroll_bar_y: Optional[Scrollbar] = None
    scroll_bar_x: Optional[Scrollbar] = None

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls._scrollable_cls_names.add(cls.__name__.lower())

    def __repr__(self) -> str:
        # return f'<{self.__class__.__name__}[{id(self)}, parent={self.scroll_parent!r}]>'
        return f'<{self.__class__.__name__}[{self._w}]>'

    @cached_property
    def scroll_parent(self) -> Optional[ScrollableBase]:
        """The widget that is a subclass of :class:`ScrollableBase` that contains this widget, if any."""
        self_id: str = self._w
        id_parts = self_id.split('.!')[:-1]
        for i, id_part in enumerate(reversed(id_parts)):
            if (m := self._tk_w_cls_search(id_part)) and m.group(1) in self._scrollable_cls_names:  # noqa
                return self.nametowidget('.!'.join(id_parts[:-i]))
        return None

    @cached_property
    def scroll_parents(self) -> list[ScrollableBase]:
        """
        The scrollable widgets (instances of classes that extend :class:`ScrollableBase`) that contain this widget.
        Items in the returned list are sorted from inner-most first to outer-most last, such that the first item in is
        this widget's :attr:`.scroll_parent`, followed by that widget's scroll_parent, and so on.
        """
        parents = []
        sc = self
        while parent := sc.scroll_parent:
            parents.append(parent)
            sc = parent
        return parents

    @cached_property
    def scroll_children(self) -> list[ScrollableBase]:
        """
        All top-level scrollable descendants (instances of classes that extend :class:`ScrollableBase`) that are inside
        this widget.  If a scrollable widget is nested inside a non-scrollable widget inside this widget, then it will
        be included.  Scrollable widgets nested within other scrollable widgets will NOT be included.
        """
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
    def widgets(self) -> tuple[BaseWidget, ...]:
        return tuple(self._widgets())


# region Scrollable Widget


class ScrollableWidget(ScrollableBase, ABC):
    """Base class for scrollable widgets that do NOT contain other widgets."""
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
            self.scroll_bar_x = _add_scroll_bar(self, inner_widget, 'x', style)
        if scroll_y:
            self.scroll_bar_y = _add_scroll_bar(self, inner_widget, 'y', style)
        inner_widget.pack(side='left', fill='both', expand=True, padx=0, pady=0)

    @cached_property
    def widgets(self) -> list[BaseWidget]:
        return [self.inner_widget, *self._widgets()]

    def configure_inner_widget(self, **kwargs):
        return self.inner_widget.configure(**kwargs)


class ScrollableTreeview(ScrollableWidget, Frame, inner_cls=Treeview):
    inner_widget: Treeview


class ScrollableText(ScrollableWidget, Frame, inner_cls=Text):
    inner_widget: Text

    def __init__(self, parent: BaseWidget = None, scroll_y: Bool = False, scroll_x: Bool = False, *args, **kwargs):
        super().__init__(parent, scroll_y, scroll_x, *args, **kwargs)
        self.inner_widget.configure(wrap=tkc.NONE if scroll_x else tkc.WORD)


class ScrollableListbox(ScrollableWidget, Frame, inner_cls=Listbox):
    inner_widget: Listbox


# endregion


# region Scrollable Container


class ScrollableContainer(ScrollableBase, ABC):
    _y_bind, _x_bind = ('<MouseWheel>', 'Shift-MouseWheel') if ON_WINDOWS else ('<4>', '<5>')
    canvas: Canvas
    inner_widget: TkContainer
    _last_scroll_region: tuple[int, int, int, int] = ()
    _last_size: XY = ()
    _x_config: AxisConfig
    _y_config: AxisConfig

    # region Initialization

    def __init__(
        self: Union[Widget, Toplevel, ScrollableContainer],
        parent: Optional[BaseWidget] = None,
        inner_cls: Type[TkContainer] = Frame,
        style: Style = None,
        inner_kwargs: dict[str, Any] = None,
        pad: XY = None,
        *,
        x_config: AxisConfig = None,
        y_config: AxisConfig = None,
        **kwargs,
    ):
        if 'relief' not in kwargs:
            kwargs.setdefault('borderwidth', 0)
        kwargs.setdefault('highlightthickness', 0)
        self._x_config = x_config or AxisConfig('x')
        self._y_config = y_config or AxisConfig('y')
        super().__init__(parent, **kwargs)
        self.init_canvas(style, pad)
        self.init_inner(inner_cls, **(inner_kwargs or {}))
        if self._y_config.fill or self._x_config.fill:
            get_parent_or_none(self).bind('<Configure>', self._maybe_resize_scroll_region, add=True)

    def init_canvas(self: ScrollOuter, style: Style = None, pad: XY = None):
        kwargs = style.get_map('frame', background='bg') if style else {}
        self.canvas = canvas = Canvas(self, borderwidth=0, highlightthickness=0, **kwargs)
        if self._x_config.scroll:
            self.scroll_bar_x = _add_scroll_bar(self, canvas, 'x', style, {'expand': 'false'})
        if self._y_config.scroll:
            self.scroll_bar_y = _add_scroll_bar(self, canvas, 'y', style, {'fill': 'y', 'expand': True})

        kwargs = {'side': 'left', 'fill': 'both', 'expand': True}
        try:
            kwargs['padx'], kwargs['pady'] = pad
        except TypeError:
            pass
        canvas.pack(**kwargs)
        canvas.xview_moveto(0)
        canvas.yview_moveto(0)

    def init_inner(self: ScrollOuter, cls: Type[TkContainer], **kwargs):
        if 'relief' not in kwargs:
            kwargs.setdefault('borderwidth', 0)
        kwargs.setdefault('highlightthickness', 0)
        canvas = self.canvas
        self.inner_widget = inner_widget = cls(canvas, **kwargs)
        canvas.create_window(0, 0, window=inner_widget, anchor='nw')
        if self._y_config.scroll or self._x_config.scroll:
            canvas.bind_all(self._y_bind, _scroll_y, add='+')
            canvas.bind_all(self._x_bind, _scroll_x, add='+')
            self.bind('<Configure>', self._maybe_update_scroll_region, add=True)

    # endregion

    # def __repr__(self) -> str:
    #     x_config, y_config = self._x_config.arg_str('x'), self._y_config.arg_str('y')
    #     return f'<{self.__class__.__name__}[{self._w}]({x_config}, {y_config})>'

    # region Scroll Methods

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

    # endregion

    # def resize_inner(self, event: Event):
    #     log.debug(f'Resizing inner={self._inner_widget_id!r} to width={event.width}, height={event.height}')
    #     self.canvas.itemconfigure(self._inner_widget_id, width=event.width, height=event.height)

    def resize_scroll_region(self, size: XY | None, update_idletasks: Bool = True, force: Bool = False):
        inner = self.inner_widget
        if update_idletasks:
            inner.update_idletasks()  # Required for the required height/width to be correct
        try:
            width, height = size
        except TypeError:
            width = self._x_config.target_size(inner)
            height = self._y_config.target_size(inner)
            size = (width, height)

        if force or size != self._last_size:
            self.update_scroll_region(width, height)

    def update_scroll_region(self, width: int = None, height: int = None):
        canvas = self.canvas
        # log.debug(f'{self!r}.update_scroll_region: size=({width}, {height})')
        canvas.configure(scrollregion=canvas.bbox('all'), width=width, height=height)
        self._last_size = (width, height)

    def _maybe_resize_scroll_region(self, event: Event):
        size = (event.width if self._x_config.fill else None, event.height if self._y_config.fill else None)
        self.resize_scroll_region(size, False, False)

    def _maybe_update_scroll_region(self, event: Event = None):
        canvas = self.canvas
        bbox = canvas.bbox('all')  # top left (x, y), bottom right (x, y) I think ==>> last 2 => (width, height)
        if self._last_scroll_region != bbox:
            # log.debug(f'Updating scroll region to {bbox=} != {self._last_scroll_region=} for {self}')
            canvas.configure(scrollregion=bbox)
            self._last_scroll_region = bbox

    @cached_property
    def widgets(self) -> list[BaseWidget]:
        return [self.canvas, self.inner_widget, *self._widgets()]


class ScrollableToplevel(ScrollableContainer, Toplevel):
    pass


class ScrollableFrame(ScrollableContainer, Frame):
    pass


class ScrollableLabelFrame(ScrollableContainer, LabelFrame):
    pass


# endregion


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


def _add_scroll_bar(
    outer: ScrollOuter,
    inner: Widget,
    axis: Axis,
    style: Style = None,
    pack_kwargs: Mapping[str, Any] = None,
) -> Scrollbar:
    direction, side, anchor = AXIS_DIR_SIDE_ANCHOR[axis]
    scroll_bar = Scrollbar(
        outer,
        orient=direction,
        command=getattr(inner, f'{axis}view'),
        style=_prepare_scroll_bar_style(style, direction),
    )
    inner.configure({f'{axis}scrollcommand': scroll_bar.set})

    kwargs = {'side': side, 'fill': axis, 'anchor': anchor}
    if pack_kwargs:
        # Additional possible kwargs: elementborderwidth, jump, repeatdelay, repeatinterval
        kwargs.update(pack_kwargs)
    # log.debug(f'Packing scrollbar with {kwargs=}')
    scroll_bar.pack(kwargs)
    return scroll_bar


def _prepare_scroll_bar_style(style: Style | None, direction: str) -> str | None:
    if not style:
        return None

    name, ttk_style = style.make_ttk_style(f'scroll_bar.{direction.title()}.TScrollbar')
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

    return name
