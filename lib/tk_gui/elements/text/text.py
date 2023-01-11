"""
Text GUI elements

:author: Doug Skrypa
"""

from __future__ import annotations

import logging
import tkinter.constants as tkc
from abc import ABC, abstractmethod
from functools import partial
from tkinter import StringVar, Event, Entry, BaseWidget, Label as TkLabel
from typing import TYPE_CHECKING, Optional, Union, Any, Callable

from tk_gui.caching import cached_property
from tk_gui.constants import LEFT_CLICK
from tk_gui.enums import Justify, Anchor
from tk_gui.event_handling import BindManager
from tk_gui.pseudo_elements.scroll import ScrollableText
from tk_gui.styles import Style, Font, StyleState, StyleLayer
from tk_gui.utils import max_line_len, call_with_popped
from ..element import Element, Interactive
from ..mixins import DisableableMixin
from .links import LinkTarget, _Link

if TYPE_CHECKING:
    from tk_gui.pseudo_elements import Row
    from tk_gui.typing import Bool, XY, BindTarget

__all__ = ['Text', 'Link', 'Input', 'Multiline', 'Label']
log = logging.getLogger(__name__)


class TextValueMixin:
    string_var: Optional[StringVar] = None
    widget: Union[TkLabel, Entry]
    size: XY
    _value: str
    _move_cursor: bool = False
    _auto_size: bool = True

    def __init_subclass__(cls, move_cursor: bool = False, **kwargs):
        super().__init_subclass__(**kwargs)
        if move_cursor:
            cls._move_cursor = move_cursor

    @property
    def value(self) -> str:
        try:
            return self.string_var.get()
        except AttributeError:  # The element has not been packed yet, so string_var is None
            return self._value

    @value.setter
    def value(self, value: Any):
        value = str(value)
        self._value = value
        try:
            self.string_var.set(value)
        except AttributeError:  # The element has not been packed yet, so string_var is None
            pass
        else:
            if self._move_cursor:
                self.widget.icursor(tkc.END)

    def init_string_var(self):
        self.string_var = StringVar()
        self.string_var.set(self._value)

    @property
    def expected_width(self) -> int:
        try:
            return self.size[0]
        except TypeError:
            return len(self.value)

    @property
    def expected_height(self) -> int:
        try:
            return self.size[1]
        except TypeError:
            return 1

    def _init_size(self, font: Font) -> Optional[XY]:
        try:
            width, size = self.size
        except TypeError:
            pass
        else:
            return width, size
        if not self._auto_size or not self._value:
            return None
        lines = self._value.splitlines()
        width = max(map(len, lines))
        height = len(lines)
        if font and 'bold' in font:
            width += 1
        return width, height


class LinkableMixin:
    __link: Optional[LinkTarget] = None
    __bound_id: str | None = None
    _tooltip_text: str | None
    add_tooltip: Callable
    widget: Union[TkLabel, Entry]
    style: Style
    base_style_layer_and_state: tuple[StyleLayer, StyleState]
    size_and_pos: tuple[XY, XY]
    value: str

    def init_linkable(self, link: _Link | LinkTarget = None, link_bind: str = None, tooltip_text: str = None):
        self._tooltip_text = tooltip_text
        self.link = (link_bind, link)

    def init_linkable_from_kwargs(self, kwargs: dict[str, Any]):
        call_with_popped(self.init_linkable, ('link', 'link_bind', 'tooltip_text'), kwargs)

    @property
    def tooltip_text(self) -> str:
        try:
            return self.link.tooltip
        except AttributeError:
            return self._tooltip_text

    def should_ignore(self, event: Event) -> bool:
        """Return True if the event ended with the cursor outside this element, False otherwise"""
        width, height = self.size_and_pos[0]
        return not (0 <= event.x <= width and 0 <= event.y <= height)

    @property
    def link(self) -> Optional[LinkTarget]:
        return self.__link

    @link.setter
    def link(self, value: Union[LinkTarget, _Link, tuple[Optional[str], _Link]]):
        if isinstance(value, tuple):
            bind, value = value
        else:
            bind = getattr(self.__link, 'bind', None)

        if isinstance(value, LinkTarget):
            if bind is not None:
                raise TypeError(f'The link={value!r} should be initialized with {bind=} instead of providing both')
            self.__link = value
        else:
            self.__link = LinkTarget.new(value, bind, self._tooltip_text, self.value)

    def update_link(self, link: Union[bool, str, BindTarget]):
        old = self.__link
        self.__link = new = LinkTarget.new(link, getattr(old, 'bind', None), self._tooltip_text, self.value)
        self.add_tooltip(new.tooltip if new else self._tooltip_text)
        if old and new and old.bind != new.bind:
            widget = self.widget
            widget.unbind(old.bind, self.__bound_id)
            self.__bound_id = widget.bind(new.bind, self._open_link, add=True)
        elif new and not old:
            self._enable_link()
        elif old and not new:
            self._disable_link(old.bind)

    def maybe_enable_link(self):
        if self.__link:
            self._enable_link()

    def _enable_link(self):
        widget, link = self.widget, self.__link
        self.__bound_id = widget.bind(link.bind, self._open_link, add=True)
        if link.use_link_style:
            link_style = self.style.link
            widget.configure(cursor='hand2', fg=link_style.fg.default, font=link_style.font.default)
        else:
            widget.configure(cursor='hand2')

    def _disable_link(self, link_bind: str):
        widget, link = self.widget, self.__link
        widget.unbind(link_bind, self.__bound_id)
        self.__bound_id = None
        if link.use_link_style:
            style_layer, state = self.base_style_layer_and_state
            widget.configure(cursor='', fg=style_layer.fg[state], font=style_layer.font[state])
        else:
            widget.configure(cursor='')

    def _open_link(self, event: Event):
        if not (link := self.link) or self.should_ignore(event):
            return
        link.open(event)


class Label(TextValueMixin, LinkableMixin, Element, base_style_layer='text'):
    """A text element in which the text is NOT selectable."""
    widget: TkLabel

    def __init__(
        self,
        value: Any = '',
        link: _Link | LinkTarget = None,
        *,
        justify: Union[str, Justify] = None,
        anchor: Union[str, Anchor] = None,
        link_bind: str = None,
        auto_size: Bool = True,
        **kwargs,
    ):
        self.value = value
        self.init_linkable(link, link_bind, kwargs.pop('tooltip', None))
        if justify is anchor is None:
            justify = Justify.LEFT
            anchor = Justify.LEFT.as_anchor()
        super().__init__(justify_text=justify, anchor=anchor, **kwargs)
        self._auto_size = auto_size

    @property
    def pad_kw(self) -> dict[str, int]:
        try:
            x, y = self.pad
        except TypeError:
            x, y = 0, 3
        return {'padx': x, 'pady': y}

    @property
    def style_config(self) -> dict[str, Any]:
        return {
            **self.style.get_map('text', bd='border_width', fg='fg', bg='bg', font='font', relief='relief'),
            **self._style_config,
        }

    def pack_into(self, row: Row, column: int):
        self.init_string_var()
        kwargs = {
            'textvariable': self.string_var,
            'justify': self.justify_text.value,
            'wraplength': 0,
            'takefocus': int(self.allow_focus),
            **self.style_config,
        }
        try:
            kwargs['width'], kwargs['height'] = self._init_size(kwargs.get('font'))
        except TypeError:
            pass

        self.widget = label = TkLabel(row.frame, **kwargs)
        if kwargs.get('height', 1) != 1:
            wrap_len = label.winfo_reqwidth()  # width in pixels
            label.configure(wraplength=wrap_len)

        self.pack_widget()
        self.maybe_enable_link()

    def update(self, value: Any = None, link: _Link = None):
        if value is not None:
            self.value = value
        if link is not None:
            self.update_link(link)


class Text(TextValueMixin, LinkableMixin, Element):
    widget: Entry

    def __init__(
        self,
        value: Any = '',
        link: _Link | LinkTarget = None,
        *,
        justify: Union[str, Justify] = None,
        anchor: Union[str, Anchor] = None,
        link_bind: str = None,
        auto_size: Bool = True,
        use_input_style: Bool = False,
        **kwargs,
    ):
        self.value = value
        self.init_linkable(link, link_bind, kwargs.pop('tooltip', None))
        if justify is anchor is None:
            justify = Justify.LEFT
        super().__init__(justify_text=justify, anchor=anchor, **kwargs)
        self._auto_size = auto_size
        self._use_input_style = use_input_style

    @property
    def pad_kw(self) -> dict[str, int]:
        try:
            x, y = self.pad
        except TypeError:
            x, y = 5, 3
        return {'padx': x, 'pady': y}

    @property
    def style_config(self) -> dict[str, Any]:
        style, state = self.style, StyleState.DISABLED
        if self._use_input_style:
            return {
                **style.get_map('input', state, bd='border_width', fg='fg', bg='bg', font='font', relief='relief'),
                **style.get_map('input', 'disabled', readonlybackground='bg'),
                **style.get_map('insert', state, insertbackground='bg'),  # Insert cursor (vertical line) color
                **self._style_config,
            }
        else:
            config = {
                **style.get_map('text', bd='border_width', fg='fg', bg='bg', font='font', relief='relief'),
                **style.get_map('text', readonlybackground='bg'),
                **self._style_config,
            }
            config.setdefault('relief', 'flat')
            return config

    @property
    def base_style_layer_and_state(self) -> tuple[StyleLayer, StyleState]:
        if self._use_input_style:
            return self.style.input, StyleState.DISABLED
        else:
            return self.style.text, StyleState.DEFAULT

    def pack_into(self, row: Row, column: int):
        self.init_string_var()
        kwargs = {
            'highlightthickness': 0,
            'textvariable': self.string_var,
            'justify': self.justify_text.value,
            'state': 'readonly',
            'takefocus': int(self.allow_focus),
            **self.style_config,
        }
        try:
            kwargs['width'] = self._init_size(kwargs.get('font'))[0]
        except TypeError:
            pass
        self.widget = Entry(row.frame, **kwargs)
        self.pack_widget()
        self.maybe_enable_link()

    def update(self, value: Any = None, link: _Link = None):
        if value is not None:
            self.value = value
        if link is not None:
            self.update_link(link)


class Link(Text):
    def __init__(self, value: Any = '', link: Union[bool, str] = True, link_bind: str = LEFT_CLICK, **kwargs):
        super().__init__(value, link=link, link_bind=link_bind, **kwargs)


class InteractiveText(DisableableMixin, Interactive, ABC):
    @property
    def base_style_layer_and_state(self) -> tuple[StyleLayer, StyleState]:
        return self.style.input, self.style_state

    def disable(self):
        if self.disabled:
            return
        self._update_state(True)

    def enable(self):
        if not self.disabled:
            return
        self._update_state(False)

    def _update_state(self, disabled: bool):
        self.widget['state'] = self._disabled_state if disabled else self._enabled_state
        self.disabled = disabled
        self._refresh_colors()

    @abstractmethod
    def _refresh_colors(self):
        raise NotImplementedError


class Input(TextValueMixin, LinkableMixin, InteractiveText, disabled_state='readonly', move_cursor=True):
    widget: Entry  # Default relief: sunken
    password_char: Optional[str] = None

    def __init__(
        self,
        value: Any = '',
        *,
        link: _Link | LinkTarget = None,
        link_bind: str = None,
        password_char: str = None,
        justify_text: Union[str, Justify, None] = Justify.LEFT,
        callback: BindTarget = None,
        **kwargs,
    ):
        self.value = value
        self.init_linkable(link, link_bind, kwargs.pop('tooltip', None))
        super().__init__(justify_text=justify_text, **kwargs)
        self._callback = callback
        if password_char:
            self.password_char = password_char

    @property
    def style_config(self) -> dict[str, Any]:
        style, state = self.style, self.style_state
        return {
            'highlightthickness': 0,
            **style.get_map('input', state, bd='border_width', fg='fg', bg='bg', font='font', relief='relief'),
            **style.get_map('input', 'disabled', readonlybackground='bg'),
            **style.get_map('insert', state, insertbackground='bg'),  # Insert cursor (vertical line) color
            **self._style_config,
        }

    def pack_into(self, row: Row, column: int):
        self.init_string_var()
        kwargs = {
            'textvariable': self.string_var,
            'show': self.password_char,
            'justify': self.justify_text.value,
            'takefocus': int(self.allow_focus),
            **self.style_config,
        }
        try:
            kwargs['width'] = self.size[0]
        except TypeError:
            pass

        self.widget = entry = Entry(row.frame, **kwargs)
        self.pack_widget()
        self.maybe_enable_link()
        entry.bind('<FocusOut>', partial(_clear_selection, entry), add=True)  # Prevents ghost selections
        if (callback := self._callback) is not None:
            entry.bind('<Key>', self.normalize_callback(callback), add=True)

    def update(self, value: Any = None, disabled: Bool = None, password_char: str = None, link: _Link = None):
        if disabled is not None:
            self._update_state(disabled)
        if value is not None:
            self.value = value
        if password_char is not None:
            self.widget.configure(show=password_char)
            self.password_char = password_char
        if link is not None:
            self.update_link(link)

    # region Update State

    def validated(self, valid: bool):
        if self.valid != valid:
            self.valid = valid
            self._refresh_colors()

    def _refresh_colors(self):
        bg_key = 'readonlybackground' if self.disabled else 'bg'
        kwargs = self.style.get_map('input', self.style_state, fg='fg', **{bg_key: 'bg'})
        log.debug(f'Refreshing colors for {self} with {self.style_state=}: {kwargs}')
        self.widget.configure(**kwargs)

    # endregion


class Multiline(InteractiveText, disabled_state='disabled'):
    widget: ScrollableText
    _read_only: Bool = False

    def __init__(
        self,
        value: Any = '',
        *,
        scroll_y: bool = True,
        scroll_x: bool = False,
        auto_scroll: bool = False,
        rstrip: bool = False,
        justify_text: Union[str, Justify, None] = Justify.LEFT,
        input_cb: BindTarget = None,
        read_only: Bool = False,
        read_only_style: Bool = False,
        **kwargs,
    ):
        super().__init__(justify_text=justify_text, **kwargs)
        self.__entered = False
        self._value = str(value)
        self.scroll_y = scroll_y
        self.scroll_x = scroll_x
        self.auto_scroll = auto_scroll
        self.rstrip = rstrip
        self._input_cb = self.normalize_callback(input_cb) if input_cb is not None else input_cb
        self._read_only = read_only
        self._read_only_style = read_only_style
        self._bind_manager = BindManager()

    @property
    def read_only(self) -> Bool:
        return self._read_only

    @read_only.setter
    def read_only(self, value: Bool):
        if self.__entered:
            raise RuntimeError(f'{self} does not support changing read-only status while in its context')
        old = self._read_only
        self._read_only = value
        if self.disabled:
            return
        if ((old and not value) or (not old and value)) and (widget := self.widget):
            callback = _block_text_entry if value else self._input_cb
            self._bind_manager.replace('<Key>', callback, widget.inner_widget)
            # widget.inner_widget.configure(state='disabled' if value else 'normal')  # noqa

    def disable(self):
        if self.__entered:
            raise RuntimeError(f'{self} does not support changing disabled status while in its context')
        super().disable()

    def enable(self):
        if self.__entered:
            raise RuntimeError(f'{self} does not support changing disabled status while in its context')
        super().enable()

    def _update_state(self, disabled: bool):
        old_state = 'disabled' if self.disabled or self._read_only else 'normal'
        new_state = 'disabled' if disabled or self._read_only else 'normal'
        if old_state != new_state:
            self.widget.inner_widget.configure(state=new_state)  # noqa
        self.disabled = disabled
        self._refresh_colors()

    @property
    def base_style_layer_and_state(self) -> tuple[StyleLayer, StyleState]:
        if self._read_only_style:
            return self.style.text, StyleState.DISABLED
        else:
            return self.style.input, self.style_state

    @property
    def style_config(self) -> dict[str, Any]:
        style, state = self.style, self.style_state
        if self._read_only_style:
            config = {
                'highlightthickness': 0,
                **style.get_map('text', bd='border_width', fg='fg', bg='bg', font='font', relief='relief'),
                **style.get_map('text', 'highlight', selectforeground='fg', selectbackground='bg'),
                **self._style_config,
            }
            config.setdefault('relief', 'flat')
        else:
            config: dict[str, Any] = {
                'highlightthickness': 0,
                **style.get_map('input', state, bd='border_width', fg='fg', bg='bg', font='font', relief='relief'),
                **style.get_map('input', 'highlight', selectforeground='fg', selectbackground='bg'),
                **style.get_map('insert', insertbackground='bg'),
                **self._style_config,
            }
            config.setdefault('relief', 'sunken')

        return config

    def pack_into(self, row: Row, column: int):
        kwargs = self.style_config
        kwargs['takefocus'] = int(self.allow_focus)
        try:
            kwargs['width'], kwargs['height'] = self.size
        except TypeError:
            pass

        value = self._value
        if self.rstrip:
            lines = [line.rstrip() for line in value.splitlines()]
            value = '\n'.join(lines)
            if 'width' not in kwargs:
                kwargs['width'] = max_line_len(lines)
        elif 'width' not in kwargs:
            kwargs['width'] = max_line_len(value.splitlines())

        # Other keys:  maxundo:  spacing1:  spacing2:  spacing3:  tabs:  undo:  wrap:
        self.widget = scroll_text = ScrollableText(row.frame, self.scroll_y, self.scroll_x, self.style, **kwargs)
        text = scroll_text.inner_widget
        if value:
            text.insert(1.0, value)
        if (justify := self.justify_text) != Justify.NONE:
            text.tag_add(justify.value, 1.0, 'end')  # noqa
        for pos in ('center', 'left', 'right'):
            text.tag_configure(pos, justify=pos)  # noqa

        self.pack_widget()
        if self.disabled:
            # Note: This needs to occur after setting any text value, otherwise the text does not appear.
            text.configure(state='disabled')

        if self._read_only:
            self._bind_manager.bind('<Key>', _block_text_entry, text)
        elif (callback := self._input_cb) is not None:
            self._bind_manager.bind('<Key>', callback, text)

    def __enter__(self) -> Multiline:
        if self.__entered:
            raise RuntimeError(f'{self} does not support entering its context multiple times')
        self.__entered = True
        # if self._read_only and not self.disabled:
        #     self.widget.inner_widget.configure(state='normal')
        if self._read_only:  # TODO: This bind may not need to be toggled off/on the way the state did...
            self._bind_manager.replace('<Key>', self._input_cb, self.widget.inner_widget)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.__entered = False
        # if self._read_only and not self.disabled:
        #     self.widget.inner_widget.configure(state='disabled')
        if self._read_only:
            self._bind_manager.replace('<Key>', _block_text_entry, self.widget.inner_widget)

    def clear(self):
        with self:
            self.widget.inner_widget.delete('1.0', tkc.END)

    def write(self, text: str, *, fg: str = None, bg: str = None, font: Font = None, append: Bool = False):
        with self:
            widget = self.widget.inner_widget
            # TODO: Handle justify
            if fg or bg or font:
                style = Style(parent=self.style, text_fg=fg, text_bg=bg, text_font=font)
                tag = f'{self.__class__.__name__}({fg},{bg},{font})'
                widget.tag_configure(tag, **style.get_map('text', background='bg', foreground='fg', font='font'))
                args = ((None, tag),)
            else:
                args = ()

            if not append:
                self.clear()

            if self.rstrip:
                text = '\n'.join(line.rstrip() for line in text.splitlines())

            widget.insert(tkc.END, text, *args)
            if self.auto_scroll:
                widget.see(tkc.END)

    @property
    def _bind_widget(self) -> BaseWidget | None:
        try:
            return self.widget.inner_widget
        except AttributeError:  # self.widget is still None / hasn't been packed yet
            return None

    @cached_property
    def widgets(self) -> list[BaseWidget]:
        return self.widget.widgets

    def _refresh_colors(self):
        with self:
            kwargs = self.style.get_map('text', self.style_state, fg='fg', bg='bg')
            log.debug(f'Refreshing colors for {self} with {self.style_state=}: {kwargs}')
            self.widget.configure(**kwargs)


def _clear_selection(widget: Union[Entry, Text], event: Event = None):
    widget.selection_clear()


def _block_text_entry(event: Event = None):
    """
    Used by read-only Multiline elements as a workaround for tkinter not supporting proper read-only multi-line text
    widgets.  Based on: https://stackoverflow.com/questions/3842155
    """
    # print(f'_block_text_entry: {event=}')
    if event.keysym == 'v':  # ctrl+v results in event.char being \x1b
        return 'break'
    char = event.char
    return 'break' if char and (char.isprintable() or char.isspace()) else None
