"""
Tkinter GUI Scroll Bar Utils

:author: Doug Skrypa
"""

from __future__ import annotations

import logging
import re
import tkinter.constants as tkc
from abc import ABC, abstractmethod
from tkinter import BaseWidget, Frame, LabelFrame, Canvas, Widget, Event, Toplevel, Text, Listbox, TclError
from tkinter.ttk import Scrollbar, Treeview
from typing import TYPE_CHECKING, Type, Mapping, Union, Optional, Any, Iterator, Callable, Literal

from tk_gui.caching import cached_property
from tk_gui.enums import ScrollUnit
from tk_gui.event_handling.decorators import delayed_event_handler
from tk_gui.geometry import Box
from tk_gui.utils import ON_WINDOWS
from .configuration import AxisConfig
from .utils import get_parent_or_none, get_root_widget

if TYPE_CHECKING:
    from tk_gui.styles import Style
    from tk_gui.typing import Bool, BindCallback, Axis, XY, TkContainer

__all__ = [
    'ScrollableToplevel', 'ScrollableFrame', 'ScrollableLabelFrame',
    'ScrollableTreeview', 'ScrollableText', 'ScrollableListbox',
]
log = logging.getLogger(__name__)

ScrollOuter = Union[BaseWidget, 'ScrollableBase', 'ScrollableContainer']
ScrollCommand = Callable[[Literal['moveto'], str | float], Any]

AXIS_DIR_SIDE_ANCHOR = {'x': (tkc.HORIZONTAL, tkc.BOTTOM, tkc.S), 'y': (tkc.VERTICAL, tkc.RIGHT, tkc.E)}


class ScrollableBase(BaseWidget, ABC):
    """Base class for scrollable widgets and containers."""
    _tk_w_cls_search = re.compile(r'^(.*?)\d*$').search
    _scrollable_container_cls_names = set()

    _w: str  # Inherited from BaseWidget
    scroll_bar_y: Optional[Scrollbar] = None
    scroll_bar_x: Optional[Scrollbar] = None

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}[{self._w}]>'

    # region Scroll Callback Handling

    @cached_property
    def scroll_parent_container(self) -> Optional[ScrollableContainer]:
        """The widget that is a subclass of :class:`ScrollableContainer` that contains this widget, if any."""
        id_parts = self._w.split('.!')[:-1]
        for i, id_part in enumerate(id_parts[::-1]):
            # Note: The below may break if a class extending ScrollableContainer has a numeric suffix in its name
            if (m := self._tk_w_cls_search(id_part)) and m.group(1) in self._scrollable_container_cls_names:
                return self.nametowidget('.!'.join(id_parts[:-i]))
        return None

    def scroll_ancestors(self) -> Iterator[ScrollableContainer]:
        """
        The scrollable widgets (instances of classes that extend :class:`ScrollableContainer`) that contain this widget.
        Items are yielded starting with the inner-most :attr:`.scroll_parent_container`, working outwards to provide
        that widget's scroll_parent_container, and so on.
        """
        widget = self
        while parent := widget.scroll_parent_container:
            yield parent
            widget = parent

    @abstractmethod
    def find_container_scroll_cb(self, scroll_bar_name: str, axis: Axis) -> Optional[BindCallback]:
        raise NotImplementedError

    def has_scrollable_bar(self, scroll_bar_name: str) -> bool:
        scroll_bar: Scrollbar
        if not (scroll_bar := getattr(self, scroll_bar_name)):
            return False
        # Even if it has a scroll bar, there may or may not be anything to scroll.
        # If pos == (0, 1), then the inner size matches the outer size, and the bar is essentially soft-disabled.
        try:
            pos = scroll_bar.get()
        except (AttributeError, TclError, TypeError):
            return False
        else:
            return pos != (0, 1)

    def find_ancestor_scroll_cb(self, scroll_bar_name: str, axis: Axis) -> Optional[BindCallback]:
        for ancestor in self.scroll_ancestors():
            if ancestor.has_scrollable_bar(scroll_bar_name):
                # log.debug(f'find_scroll_cb: [found bar for {ancestor=}] {axis=}, scrollable={self}')
                return getattr(ancestor, f'scroll_{axis}')
        return None

    # endregion

    # @cached_property
    # def scroll_children(self) -> list[ScrollableBase]:
    #     """
    #     All top-level scrollable descendants (instances of classes that extend :class:`ScrollableBase`) that are inside
    #     this widget.  If a scrollable widget is nested inside a non-scrollable widget inside this widget, then it will
    #     be included.  Scrollable widgets nested within other scrollable widgets will NOT be included.
    #     """
    #     children = []
    #     all_children = self.winfo_children()
    #     while all_children:
    #         child = all_children.pop()
    #         if isinstance(child, ScrollableBase):
    #             children.append(child)
    #         else:
    #             all_children.extend(child.winfo_children())
    #     return children

    def _widgets(self) -> Iterator[BaseWidget]:
        yield self
        if self.scroll_bar_y is not None:
            yield self.scroll_bar_y
        if self.scroll_bar_x is not None:
            yield self.scroll_bar_x

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

    def find_container_scroll_cb(self, scroll_bar_name: str, axis: Axis) -> Optional[BindCallback]:
        # A scrollable widget may or may not have been actually configured to scroll on this axis.
        if self.has_scrollable_bar(scroll_bar_name):
            # None is returned to skip the container callback because this
            # widget has a scroll action that will be triggered directly by Tk
            return None
        return self.find_ancestor_scroll_cb(scroll_bar_name, axis)


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


class ComplexScrollable(ScrollableBase, ABC):
    if ON_WINDOWS:
        _y_binds = ('<MouseWheel>',)
        _x_binds = ('<Shift-MouseWheel>',)
    else:
        _y_binds = ('<4>', '<5>')
        _x_binds = ('<Shift-4>', '<Shift-5>')

    canvas: Canvas
    _last_box: Box = Box(0, 0, 0, 0)
    _last_size: XY = ()
    _x_config: AxisConfig
    _y_config: AxisConfig

    # region Initialization

    def __init__(
        self: Union[Widget, Toplevel, ComplexScrollable],
        parent: Optional[BaseWidget] = None,
        style: Style = None,
        pad: XY = None,  # TODO: Clarify this is for the canvas
        *,
        x_config: AxisConfig = None,
        y_config: AxisConfig = None,
        resize_offset: int = 43,  # Not sure whether this value is dynamic
        verify: bool = False,
        **kwargs,
    ):
        if 'relief' not in kwargs:
            kwargs.setdefault('borderwidth', 0)
        kwargs.setdefault('highlightthickness', 0)
        self._x_config = x_config or AxisConfig('x')
        self._y_config = y_config or AxisConfig('y')
        super().__init__(parent, **kwargs)
        self.init_canvas(style, pad, verify)
        self.resize_offset = resize_offset
        self._init_binds()
        self.__last_event = None

    def init_canvas_kwargs(self, style: Style = None) -> dict[str, Any]:
        return style.get_map('frame', background='bg') if style else {}

    def init_canvas(self, style: Style = None, pad: XY = None, verify: bool = False):
        kwargs = self.init_canvas_kwargs(style)
        # Scroll increment values may be an int for pixels, or `{n}m` for millimeters, `{n}c` for cm, `{n}i` for inches
        if self._x_config.what == ScrollUnit.PIXELS:
            kwargs['xscrollincrement'] = 1
        if self._y_config.what == ScrollUnit.PIXELS:
            kwargs['yscrollincrement'] = 1

        self.canvas = canvas = Canvas(self, borderwidth=0, highlightthickness=0, **kwargs)
        if self._x_config.scroll:
            self.scroll_bar_x = _add_scroll_bar(self, canvas, 'x', style, {'expand': 'false'}, verify=verify)
        if self._y_config.scroll:
            self.scroll_bar_y = _add_scroll_bar(self, canvas, 'y', style, {'fill': 'y', 'expand': True}, verify=verify)

        kwargs = {'side': 'left', 'fill': 'both', 'expand': True}
        try:
            kwargs['padx'], kwargs['pady'] = pad
        except TypeError:
            pass
        canvas.pack(**kwargs)
        canvas.xview_moveto(0)
        canvas.yview_moveto(0)

    def _init_binds(self):
        y_config, x_config = self._y_config, self._x_config
        # TODO: Only register _scroll_y/_scroll_x once per window + key combo (or at least only when it hasn't been
        #  registered, if it persists across Windows), and have find_container_scroll_cb validate the key combo
        if y_config.scroll:
            # TODO: Handle Page[Up|Down]
            # self.canvas.bind_all('<Key-Prior>', _scroll_y, add='+')     # PageUp
            # self.canvas.bind_all('<Key-Next>', _scroll_y, add='+')      # PageDown
            for bind in self._y_binds:
                self.canvas.bind_all(bind, _scroll_y, add='+')
        if x_config.scroll:
            for bind in self._x_binds:
                self.canvas.bind_all(bind, _scroll_x, add='+')
        if y_config.scroll or x_config.scroll:
            self.bind('<Configure>', self._maybe_update_scroll_region, add=True)
        if y_config.fill or x_config.fill:
            # If this was bound to the window, it would not handle some events well (ends up not filling)
            get_parent_or_none(self).bind('<Configure>', self._maybe_fill_region, add=True)

    # endregion

    # region Bar Dimensions

    @cached_property
    def bar_height_x(self) -> int:
        try:
            return self.scroll_bar_x.winfo_reqheight()
        except AttributeError:
            return 0

    @cached_property
    def bar_width_y(self) -> int:
        try:
            return self.scroll_bar_y.winfo_reqwidth()
        except AttributeError:
            return 0

    # endregion

    # region Scroll Methods

    def scroll_y(self, event: Event):
        """
        Scroll the canvas along the Y axis (vertically).  Only called for scroll wheel events, not when the bar is
        clicked and dragged.
        """
        if self.__last_event and self.__last_event.serial == event.serial:
            # This is a hack to work around what I suspect is a bind leak, where the first canvas with a scroll bar
            # will have 1 callback executed (as expected), while subsequent ones end up having this called as many
            # times as the number of scrollable canvases previously existed...
            return
        self.__last_event = event
        # log.debug(f'scroll_y: {id(event)} {event=}, {self.canvas.yview()=}')
        if (event.num == 5 or event.delta < 0) and (canvas := self.canvas).yview() != (0, 1):
            # canvas.yview_scroll(4, 'units')
            canvas.yview_scroll(*self._y_config.view_scroll_args(True))
        elif (event.num == 4 or event.delta > 0) and (canvas := self.canvas).yview() != (0, 1):
            # canvas.yview_scroll(-4, 'units')
            canvas.yview_scroll(*self._y_config.view_scroll_args(False))

    def scroll_x(self, event: Event):
        """
        Scroll the canvas along the X axis (horizontally).  Only called for scroll wheel events, not when the bar is
        clicked and dragged.
        """
        if self.__last_event and self.__last_event.serial == event.serial:
            # This is a hack to work around what I suspect is a bind leak, where the first canvas with a scroll bar
            # will have 1 callback executed (as expected), while subsequent ones end up having this called as many
            # times as the number of scrollable canvases previously existed...
            return
        self.__last_event = event
        # log.debug(f'scroll_x: {event=}, {self.canvas.xview()=}')
        if (event.num == 5 or event.delta < 0) and (canvas := self.canvas).xview() != (0, 1):
            # canvas.xview_scroll(4, 'units')
            canvas.xview_scroll(*self._x_config.view_scroll_args(True))
        elif (event.num == 4 or event.delta > 0) and (canvas := self.canvas).xview() != (0, 1):
            # canvas.xview_scroll(-4, 'units')
            canvas.xview_scroll(*self._x_config.view_scroll_args(False))

    def find_container_scroll_cb(self, scroll_bar_name: str, axis: Axis) -> Optional[BindCallback]:
        # TODO: Accept the event (or at least the key combo from it) + verify that the key combo used matches the
        #  one configured for this widget + axis
        if self.has_scrollable_bar(scroll_bar_name):
            # This widget has a bar for this axis that is not soft-disabled
            # log.debug(f'find_scroll_cb: [found bar for scrollable={self}] {axis=}')
            return getattr(self, f'scroll_{axis}')
        else:
            return self.find_ancestor_scroll_cb(scroll_bar_name, axis)

    # endregion

    # region Widgets

    def _widgets(self) -> Iterator[BaseWidget]:
        yield self.canvas
        yield from super()._widgets()

    @cached_property
    def _top_level(self) -> Toplevel:
        return get_root_widget(self)

    # endregion

    # region Scroll Region: Update / Resize / Fill

    def resize_scroll_region(self, size: XY | None, *, force: Bool = False):
        try:
            width, height = size
        except TypeError:
            if size:
                raise
            return

        if force or size != self._last_size:
            self.update_canvas_size(width, height)

    def update_canvas_size(self, width: int = None, height: int = None, force: bool = False):
        size = (width, height)
        if force or self._last_size != size:
            self.update_scroll_region(True, width=width, height=height)
            self._last_size = size

    @delayed_event_handler(delay_ms=75)
    def _maybe_update_scroll_region(self, event: Event = None):
        self.update_scroll_region()

    def update_scroll_region(self, force: bool = False, **kwargs):
        canvas = self.canvas
        bbox = canvas.bbox('all')  # top left (x, y), bottom right (x, y) I think ==>> last 2 => (width, height)
        box = Box(*bbox)
        if force or self._last_box != box:
            # log.debug(f'Updating scroll region to {box=} != {self._last_box=} for {self} with {kwargs=}')
            canvas.configure(scrollregion=bbox, **kwargs)
            self._last_box = box
        # else:
        #     log.debug(f'{self!r}: Skipping scroll region update ({bbox=})')

    @delayed_event_handler(delay_ms=75)
    def _maybe_fill_region(self, event: Event = None):
        # log.debug(f'{self!r}._maybe_resize_scroll_region: {event=}')
        top = self._top_level
        resize_offset = self.resize_offset  # 43 by default; whether this is static or how to calculate is unknown
        # Without the offset, a resize storm will occur when the Window size is not stored
        size = (
            top.winfo_width() - resize_offset if self._x_config.fill else None,
            top.winfo_height() - resize_offset if self._y_config.fill else None,
        )
        # Note: event.width - 7 seems to work for Windows where the size is not stored, but causes continuous shrinking
        # for ones that store size.
        # size = (event.width - 7 if self._x_config.fill else None, event.height - 7 if self._y_config.fill else None)
        # log.debug(f'{self!r}._maybe_resize_scroll_region: {event=}, {size=}', extra={'color': 'yellow'})
        self.resize_scroll_region(size)

    # endregion


class ScrollableContainer(ComplexScrollable, ABC):
    inner_widget: TkContainer
    auto_resize: bool = True
    _inner_id: int = None

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls._scrollable_container_cls_names.add(cls.__name__.lower())

    # region Initialization

    def __init__(
        self: Union[Widget, Toplevel, ScrollableContainer],
        parent: Optional[BaseWidget] = None,
        inner_cls: Type[TkContainer] = Frame,
        inner_kwargs: dict[str, Any] = None,
        auto_resize: bool = True,
        **kwargs,
    ):
        super().__init__(parent, **kwargs)
        self.init_inner(inner_cls, **(inner_kwargs or {}))
        if not auto_resize:
            self.auto_resize = auto_resize

    def init_inner(self, cls: Type[TkContainer], **kwargs):
        if 'relief' not in kwargs:
            kwargs.setdefault('borderwidth', 0)
        kwargs.setdefault('highlightthickness', 0)
        self.inner_widget = inner_widget = cls(self.canvas, **kwargs)
        self._inner_id = self.canvas.create_window(0, 0, window=inner_widget, anchor='nw')

    # endregion

    def _widgets(self) -> Iterator[BaseWidget]:
        yield self.inner_widget
        yield from super()._widgets()

    # def __repr__(self) -> str:
    #     x_config, y_config = self._x_config.arg_str('x'), self._y_config.arg_str('y')
    #     return f'<{self.__class__.__name__}[{self._w}]({x_config}, {y_config})>'

    # def resize_inner(self, event: Event):
    #     log.debug(f'Resizing inner={self._inner_widget_id!r} to width={event.width}, height={event.height}')
    #     self.canvas.itemconfigure(self._inner_id, width=event.width, height=event.height)

    def resize_scroll_region(self, size: XY | None, *, update_idletasks: Bool = None, force: Bool = False):
        if not self.auto_resize and not force:
            return
        inner = self.inner_widget
        if update_idletasks is None:
            update_idletasks = size is None
        if update_idletasks:
            inner.update_idletasks()  # Required for the required height/width to be correct
        try:
            width, height = size
        except TypeError:
            width = self._x_config.target_size(inner)
            height = self._y_config.target_size(inner)
            size = (width, height)

        if force or size != self._last_size:
            self.update_canvas_size(width, height)


class ScrollableToplevel(ScrollableContainer, Toplevel):
    pass


class ScrollableFrame(ScrollableContainer, Frame):
    pass


class ScrollableLabelFrame(ScrollableContainer, LabelFrame):
    pass


# endregion


# region Scroll Callback Handling


def _find_container_scroll_cb(widget: BaseWidget, scroll_bar_name: str, axis: Axis) -> Optional[BindCallback]:
    while widget:
        if isinstance(widget, ScrollableBase):
            # This checks for ScrollableBase instead of ScrollableContainer because the container should not scroll
            # when a scrollable widget within it was under the mouse cursor - all cases are handled in find_scroll_cb
            return widget.find_container_scroll_cb(scroll_bar_name, axis)

        try:
            if (parent_name := widget.winfo_parent()) == '.':
                break
        except AttributeError:  # event.widget may be a string when scrolling in a ttk Combobox
            return None

        widget = widget.nametowidget(parent_name)

    return None


def _scroll_y(event: Event):
    if cb := _find_container_scroll_cb(event.widget, 'scroll_bar_y', 'y'):
        cb(event)


def _scroll_x(event: Event):
    if cb := _find_container_scroll_cb(event.widget, 'scroll_bar_x', 'x'):
        cb(event)


# endregion


def _make_scroll_command(widget: Widget, axis: Axis) -> ScrollCommand:
    axis_view = getattr(widget, f'{axis}view')

    def _scroll_command(action, fraction):
        if axis_view() != (0, 1):
            return axis_view(action, fraction)
        return None

    return _scroll_command


def _add_scroll_bar(
    outer: ScrollOuter,
    inner: Widget,
    axis: Axis,
    style: Style = None,
    pack_kwargs: Mapping[str, Any] = None,
    *,
    verify: bool = False,
    command: ScrollCommand = None,
) -> Scrollbar:
    direction, side, anchor = AXIS_DIR_SIDE_ANCHOR[axis]
    if verify:
        if command is not None:
            raise ScrollConfigError(f'A specific scroll {command=} cannot be combined with {verify=}')
        command = _make_scroll_command(inner, axis)
    elif command is None:
        command = getattr(inner, f'{axis}view')

    scroll_bar = Scrollbar(
        outer,
        orient=direction,
        command=command,
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
    # log.debug(f'Building scroll bar style={name!r} from {style=} with {kwargs=}')
    ttk_style.configure(name, **kwargs)
    # TODO: Handle hover color
    if (bg := style.scroll.bg.default) and (ac := style.scroll.arrow_color.default):
        bg_list = [('selected', bg), ('active', ac), ('background', bg), ('!focus', bg)]
        ac_list = [('selected', ac), ('active', bg), ('background', bg), ('!focus', ac)]
        ttk_style.map(name, background=bg_list, arrowcolor=ac_list)

    return name


class ScrollConfigError(Exception):
    """Raised when an invalid configuration is provided."""
