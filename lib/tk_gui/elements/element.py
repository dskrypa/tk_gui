"""
Tkinter GUI core Row and Element classes

:author: Doug Skrypa
"""

from __future__ import annotations

import logging
import tkinter.constants as tkc
from abc import ABC, abstractmethod
from itertools import count
from typing import TYPE_CHECKING, Any, Callable, overload

from tk_gui.caching import ClearableCachedPropertyMixin, cached_property
from tk_gui.enums import StyleState, Anchor, Justify, Side, BindTargets
from tk_gui.event_handling import BindMixin, BindMapping
from tk_gui.pseudo_elements.tooltips import ToolTip
from tk_gui.styles import Style, StyleLayer
from tk_gui.utils import Inheritable, call_with_popped, extract_style
from tk_gui.widgets.utils import find_descendants

if TYPE_CHECKING:
    from tkinter import Widget, Event, BaseWidget
    from tk_gui.pseudo_elements.row import RowBase
    from tk_gui.styles.typing import StyleSpec, Layer
    from tk_gui.typing import XY, Bool, BindCallback, Key, TkFill, BindTarget, HasFrame, TkContainer
    from tk_gui.window import Window
    from .menu import Menu

__all__ = ['ElementBase', 'Element', 'Interactive', 'InteractiveMixin']
log = logging.getLogger(__name__)

_DIRECT_ATTRS = {'key', 'right_click_menu', 'left_click_cb', 'binds', 'data'}
_INHERITABLES = {'size', 'auto_size_text'}
_BASIC = frozenset({'anchor', 'style', 'pad', 'side', 'fill', 'expand', 'allow_focus', 'ignore_grab'})
_basic_keys = _BASIC.intersection

_Anchor = str | Anchor
_Justify = str | Justify
_Side = str | Side


class ElementBase(ClearableCachedPropertyMixin, ABC):
    _style_config: dict[str, Any]
    _base_style_layer: str = None
    id: str
    parent: RowBase | HasFrame | None = None
    widget: Widget | None = None
    fill: TkFill = None
    expand: bool = None
    allow_focus: bool = False
    ignore_grab: bool = False
    anchor: Anchor = Inheritable('anchor_elements', type=Anchor)
    pad: XY = Inheritable('element_padding')
    side: Side = Inheritable('element_side', type=Side)
    style: Style = Inheritable(type=Style.get_style)

    def __init_subclass__(cls, base_style_layer: Layer = None, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.__counter = count()
        if base_style_layer:
            cls._base_style_layer = base_style_layer

    def __init__(
        self,
        style: StyleSpec = None,
        pad: XY = None,
        side: _Side = None,
        fill: TkFill = None,
        expand: bool = None,
        ignore_grab: Bool = False,
        allow_focus: Bool = None,
        anchor: _Anchor = None,
        _style_config: dict[str, Any] = None,
        **kwargs,
    ):
        self.id = f'{self.__class__.__name__}#{next(self.__counter)}'
        self.anchor = anchor
        self.pad = pad
        self.side = side
        if _style_config:
            self._style_config = _style_config
        else:
            self._style_config = extract_style(kwargs) if kwargs else {}
        if allow_focus is not None:
            self.allow_focus = allow_focus
        if kwargs:
            raise TypeError(f'{self.__class__.__name__} received unexpected {kwargs=}')
        if expand is not None:
            self.expand = expand
        if fill:
            self.fill = fill
        if style:
            self.style = style  # noqa
        if ignore_grab:
            self.ignore_grab = ignore_grab

    # region Introspection

    @property
    def window(self) -> Window:
        return self.parent.window

    @property
    def size_and_pos(self) -> tuple[XY, XY]:
        size, pos = self.widget.winfo_geometry().split('+', 1)
        w, h = size.split('x', 1)
        x, y = pos.split('+', 1)
        return (int(w), int(h)), (int(x), int(y))

    @cached_property
    def widgets(self) -> list[BaseWidget]:
        return [self.widget, *find_descendants(self.widget)]

    @property
    def was_packed(self) -> bool:
        return self.widget is not None

    # endregion

    # region Pack Methods / Attributes

    @property
    def pad_kw(self) -> dict[str, int]:
        try:
            x, y = self.pad
        except TypeError:
            x, y = 5, 3
        return {'padx': x, 'pady': y}

    def pack_into_row(self, row: RowBase):
        self.parent = row
        self.pack_into(row)

    @abstractmethod
    def _init_widget(self, tk_container: TkContainer):
        raise NotImplementedError

    def pack_into(self, row: RowBase):
        self._init_widget(row.frame)
        self.pack_widget()

    def pack_widget(self, *, expand: bool = None, fill: TkFill = None, **kwargs):
        if expand is None:
            expand = self.expand
        if fill is None:
            fill = self.fill
        pack_kwargs = {  # Note: using pack_kwargs to allow things like padding overrides
            'anchor': self.anchor.value,
            'side': self.side.value,
            'expand': False if expand is None else expand,
            'fill': tkc.NONE if not fill else tkc.BOTH if fill is True else fill,
            **self.pad_kw,
            **kwargs,
        }
        self.widget.pack(**pack_kwargs)

    # endregion

    # region Grid Methods

    def grid_into_frame(self, parent: HasFrame, row: int, column: int, **kwargs):
        self.parent = parent
        self.grid_into(parent, row, column, **kwargs)

    def grid_into(self, parent: HasFrame, row: int, column: int, **kwargs):
        self._init_widget(parent.frame)
        self.grid_widget(row, column, **kwargs)

    def grid_widget(self, row: int, column: int, *, row_span: int = None, col_span: int = None, **kwargs):
        grid_kwargs = {
            'sticky': self.side.as_sticky(),
            **self.pad_kw,
            **kwargs,
        }
        self.widget.grid(row=row, column=column, rowspan=row_span, columnspan=col_span, **grid_kwargs)

    # endregion

    def configure_widget(self, outer: Bool = False, **kwargs):
        if outer:
            return self.widget.configure(**kwargs)

        try:
            config_func = self.widget.configure_inner_widget  # noqa  # ScrollableWidget
        except AttributeError:
            config_func = self.widget.configure

        return config_func(**kwargs)

    def take_focus(self, force: bool = False):
        if force:
            self.widget.focus_force()
        else:
            self.widget.focus_set()

    # region Style Methods / Attributes

    @property
    def style_config(self) -> dict[str, Any]:
        return self._style_config

    @property
    def base_style_layer_and_state(self) -> tuple[StyleLayer, StyleState]:
        if self._base_style_layer:
            return self.style[self._base_style_layer], StyleState.DEFAULT
        return self.style.base, StyleState.DEFAULT

    def apply_style(self):
        # log.debug(f'{self}: Updating style: {self.style_config}')
        self.configure_widget(**self.style_config)

    def update_style(self, style: StyleSpec = None, **kwargs):
        if style:
            self.style = style  # noqa
            self.configure_widget(**(self.style_config | kwargs))
        elif kwargs:
            self.configure_widget(**kwargs)

    # endregion


class Element(BindMixin, ElementBase, ABC):
    _key: Key | None = None
    _tooltip: ToolTip | None = None
    _pack_settings: dict[str, Any] = None
    tooltip_text: str | None = None
    right_click_menu: Menu | None = None
    left_click_cb: Callable | None = None
    data: Any = None                                            # Any data that needs to be stored with the element

    size: XY = Inheritable('element_size', default=None)
    auto_size_text: bool = Inheritable()

    @overload
    def __init__(
        self,
        *,
        key: Key = None,
        size: XY = None,
        pad: XY = None,
        style: StyleSpec = None,
        auto_size_text: Bool = None,
        anchor: _Anchor = None,
        side: _Side = Side.LEFT,
        expand: Bool = None,
        fill: TkFill = None,
        allow_focus: bool = False,
        visible: Bool = True,
        tooltip: str = None,
        right_click_menu: Menu = None,
        left_click_cb: Callable = None,
        binds: BindMapping = None,
        bind_clicks: Bool = None,
        data: Any = None,
    ):
        ...

    def __init__(self, *, visible: Bool = True, bind_clicks: Bool = None, tooltip: str = None, **kwargs):
        if kwargs:
            super().__init__(_style_config=extract_style(kwargs), **{k: kwargs.pop(k) for k in _basic_keys(kwargs)})
        else:
            super().__init__()
        self._visible = visible
        if tooltip:
            self.tooltip_text = tooltip

        for key, val in kwargs.items():
            if key in _DIRECT_ATTRS:
                if val is not None:
                    setattr(self, key, val)
            elif key in _INHERITABLES:
                setattr(self, key, val)
            else:
                # The number of times one or more invalid options will be provided is extremely low compared to how
                # often this exception will not need to be raised, so the re-iteration over kwargs is acceptable.
                # This also avoids creating the `bad` dict that would otherwise be thrown away on 99.9% of init calls.
                bad = {k: v for k, v in kwargs.items() if k not in _DIRECT_ATTRS and k not in _INHERITABLES}
                raise TypeError(f'Invalid options for {self.__class__.__name__}: {bad}')

        if bind_clicks or (bind_clicks is None and (kwargs.get('right_click_menu') or kwargs.get('left_click_cb'))):
            self.binds.add('<ButtonRelease-1>', self.handle_left_click, add=True)
            self.binds.add('<ButtonRelease-3>', self.handle_right_click, add=True)

    def __repr__(self) -> str:
        size, visible = self.size, self._visible
        key_str = f'key={self._key!r}' if self._key else ''
        return f'<{self.__class__.__name__}[id={self.id}, {key_str}{size=}, {visible=}]>'

    @property
    def key(self) -> Key:
        return self._key or self.id

    @key.setter
    def key(self, value: Key):
        self._key = value
        if self.parent:
            self.parent.window.register_element(value, self)

    @property
    def value(self) -> Any:
        return None

    # region Pack Methods / Attributes

    def pack_into_row(self, row: RowBase):
        self.parent = row
        if self._key:
            row.window.register_element(self._key, self)
        self.pack_into(row)
        self.apply_binds()
        if self.tooltip_text:
            self.add_tooltip(self.tooltip_text)

    def pack_widget(
        self, *, expand: bool = None, fill: TkFill = None, focus: bool = False, widget: Widget = None, **kwargs
    ):
        if not widget:
            widget = self.widget

        self._pack_widget(widget, expand, fill, kwargs)
        if focus:
            self.parent.window.maybe_set_focus(self)

    def _pack_widget(self, widget: Widget, expand: bool, fill: TkFill, kwargs: dict[str, Any]):
        if expand is None:
            expand = self.expand
        if fill is None:
            fill = self.fill

        pack_kwargs = {  # Note: using pack_kwargs to allow things like padding overrides
            'anchor': self.anchor.value,
            'side': self.side.value,
            'expand': False if expand is None else expand,
            'fill': tkc.NONE if not fill else tkc.BOTH if fill is True else fill,
            **self.pad_kw,
            **kwargs,
        }
        widget.pack(**pack_kwargs)
        if not self._visible:
            self._pack_settings = widget.pack_info()  # noqa
            # log.debug(f'Hiding {self} - saved pack settings={self._pack_settings}')
            widget.pack_forget()

    def add_tooltip(
        self, text: str, delay: int = ToolTip.DEFAULT_DELAY, style: StyleSpec = None, wrap_len_px: int = None
    ):
        if self._tooltip:
            del self._tooltip
        self._tooltip = ToolTip(self, text, delay=delay, style=style, wrap_len_px=wrap_len_px)

    def grid_into_frame(self, parent: HasFrame, row: int, column: int, **kwargs):
        self.parent = parent
        if self._key:
            parent.window.register_element(self._key, self)
        self.grid_into(parent, row, column, **kwargs)
        self.apply_binds()
        if self.tooltip_text:
            self.add_tooltip(self.tooltip_text)

    # endregion

    # region Visibility Methods

    @property
    def is_visible(self) -> bool:
        return self._visible

    def hide(self):
        self._pack_settings = self.widget.pack_info()  # noqa
        # log.debug(f'Hiding {self} - saved pack settings={self._pack_settings}')
        self.widget.pack_forget()
        self._visible = False

    def show(self):
        if (settings := self._pack_settings) is None:
            settings = {}
        if self.side == Side.RIGHT and 'after' not in settings and 'before' not in settings:
            row_elements = self.parent.elements
            index = row_elements.index(self)
            key, index = ('after', index - 1) if index else ('before', index + 1)
            try:
                settings[key] = row_elements[index].widget
            except IndexError:
                pass

        # log.debug(f'Showing {self} with {settings=}')
        self.widget.pack(**settings)
        self._visible = True

    def toggle_visibility(self, show: bool = None):
        if show is None:
            show = not self._visible
        if show:
            self.show()
        else:
            self.hide()

    # endregion

    # region Bind Methods

    @property
    def _bind_widget(self) -> BaseWidget | None:
        return self.widget

    def normalize_callback(self, cb: BindTarget) -> BindCallback:
        if isinstance(cb, str):
            cb = BindTargets(cb)
        if isinstance(cb, BindTargets):
            if cb == BindTargets.EXIT:
                return self.window.close
            elif cb == BindTargets.INTERRUPT:
                return self.trigger_interrupt
            else:
                raise ValueError(f'Invalid {cb=} for {self}')
        elif not isinstance(cb, Callable):
            raise TypeError(f'Invalid {cb=} for {self}')
        return cb

    # endregion

    # region Event Handling

    def trigger_interrupt(self, event: Event = None):
        self.window.interrupt(event, self)

    def handle_left_click(self, event: Event):
        # log.debug('Handling left click')
        if cb := self.left_click_cb:
            # log.debug(f'Passing {event=} to {cb=}')
            result = cb(event)
            self.window._handle_callback_action(result, event, self)

    def handle_right_click(self, event: Event):
        # log.debug('Handling right click')
        if menu := self.right_click_menu:
            # log.debug(f'Showing right-click {menu=}')
            menu.parent = self  # Needed for style inheritance
            menu.show(event, self.widget.master)  # noqa

    # endregion


class InteractiveMixin:
    widget: Widget | None
    style: Style
    _base_style_layer: str | None
    disabled: bool = False
    focus: bool = False
    valid: bool = True
    allow_focus: bool = True

    def init_interactive(self, disabled: Bool = False, focus: Bool = False, valid: Bool = True):
        self.disabled = disabled
        self.focus = focus
        self.valid = valid

    def init_interactive_from_kwargs(self, kwargs: dict[str, Any]):
        call_with_popped(self.init_interactive, ('disabled', 'focus', 'valid'), kwargs)

    @property
    def style_state(self) -> StyleState:
        if self.disabled:
            return StyleState.DISABLED
        elif not self.valid:
            return StyleState.INVALID
        return StyleState.DEFAULT

    @property
    def base_style_layer_and_state(self) -> tuple[StyleLayer, StyleState]:
        if self._base_style_layer:
            return self.style[self._base_style_layer], self.style_state
        return self.style.base, self.style_state

    def pack_widget(self, *, expand: bool = False, fill: TkFill = tkc.NONE, **kwargs):
        super().pack_widget(expand=expand, fill=fill, focus=self.focus, **kwargs)  # noqa

    def enable(self):
        raise NotImplementedError

    def disable(self):
        raise NotImplementedError

    def toggle_enabled(self, disable: Bool = None):
        if disable is None:
            disable = not self.disabled
        if disable:
            self.disable()
        else:
            self.enable()


class Interactive(InteractiveMixin, Element, ABC):
    @overload
    def __init__(
        self,
        disabled: Bool = False,
        focus: Bool = False,
        valid: Bool = True,
        *,
        key: Key = None,
        size: XY = None,
        pad: XY = None,
        style: StyleSpec = None,
        auto_size_text: Bool = None,
        anchor: _Anchor = None,
        side: _Side = Side.LEFT,
        expand: Bool = None,
        fill: TkFill = None,
        allow_focus: bool = False,
        visible: Bool = True,
        tooltip: str = None,
        right_click_menu: Menu = None,
        left_click_cb: Callable = None,
        binds: BindMapping = None,
        bind_clicks: Bool = None,
        data: Any = None,
    ):
        ...

    def __init__(self, disabled: Bool = False, focus: Bool = False, valid: Bool = True, **kwargs):
        super().__init__(**kwargs)
        self.init_interactive(disabled, focus, valid)

    def __repr__(self) -> str:
        size, visible, disabled = self.size, self._visible, self.disabled
        return f'<{self.__class__.__name__}[id={self.id}, {size=}, {visible=}, {disabled=}]>'
