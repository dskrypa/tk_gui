"""
Text GUI elements

:author: Doug Skrypa
"""

from __future__ import annotations

import logging
import tkinter.constants as tkc
import webbrowser
from abc import ABC, abstractmethod
from functools import cached_property, partial
from tkinter import StringVar, Label, Event, Entry, BaseWidget
from typing import TYPE_CHECKING, Optional, Union, Any

from tk_gui.constants import LEFT_CLICK
from tk_gui.enums import Justify, Anchor
from tk_gui.pseudo_elements.scroll import ScrollableText
from tk_gui.style import Style, Font, StyleState
from tk_gui.utils import max_line_len
from ..element import Element, Interactive
from .links import LinkTarget, _Link

if TYPE_CHECKING:
    from tk_gui.pseudo_elements import Row
    from tk_gui.typing import Bool, XY, BindTarget

__all__ = ['Text', 'Link', 'Input', 'Multiline']
log = logging.getLogger(__name__)


class TextValueMixin:
    string_var: Optional[StringVar] = None
    widget: Union[Label, Entry]
    size: XY
    _value: str
    _move_cursor: bool = False

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


class Text(TextValueMixin, Element):
    __link: Optional[LinkTarget] = None
    widget: Union[Label, Entry]

    def __init__(
        self,
        value: Any = '',
        link: _Link | LinkTarget = None,
        *,
        justify: Union[str, Justify] = None,
        anchor: Union[str, Anchor] = None,
        link_bind: str = None,
        selectable: Bool = True,
        auto_size: Bool = True,
        use_input_style: Bool = False,
        **kwargs,
    ):
        self._tooltip_text = kwargs.pop('tooltip', None)
        if justify is anchor is None:
            justify = Justify.LEFT
            if not selectable:
                anchor = Justify.LEFT.as_anchor()
        super().__init__(justify_text=justify, anchor=anchor, **kwargs)
        self.value = value
        self.link = (link_bind, link)
        self._selectable = selectable
        self._auto_size = auto_size
        self._use_input_style = use_input_style

    @property
    def pad_kw(self) -> dict[str, int]:
        try:
            x, y = self.pad
        except TypeError:
            if self._selectable:
                x, y = 5, 3
            else:
                x, y = 0, 3

        return {'padx': x, 'pady': y}

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
            return {
                **style.get_map('text', bd='border_width', fg='fg', bg='bg', font='font', relief='relief'),
                **self._style_config,
            }

    def pack_into(self, row: Row, column: int):
        self.init_string_var()
        if self._selectable:
            self._pack_entry(row)
        else:
            self._pack_label(row)

        self.pack_widget()
        if self.__link:
            self._enable_link()

    def _pack_label(self, row: Row):
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

        self.widget = label = Label(row.frame, **kwargs)
        if kwargs.get('height', 1) != 1:
            wrap_len = label.winfo_reqwidth()  # width in pixels
            label.configure(wraplength=wrap_len)

    def _pack_entry(self, row: Row):
        kwargs = {
            'highlightthickness': 0,
            'textvariable': self.string_var,
            'justify': self.justify_text.value,
            'state': 'readonly',
            'takefocus': int(self.allow_focus),
            **self.style_config,
        }
        if not self._use_input_style:
            kwargs.update(self.style.get_map('text', readonlybackground='bg'))
            kwargs.setdefault('relief', 'flat')
        try:
            kwargs['width'] = self._init_size(kwargs.get('font'))[0]
        except TypeError:
            pass
        self.widget = Entry(row.frame, **kwargs)

    def update(self, value: Any = None, link: Union[bool, str] = None):
        if value is not None:
            self.value = value
        if link is not None:
            self.update_link(link)

    @property
    def tooltip_text(self) -> str:
        try:
            return self.__link.tooltip
        except AttributeError:
            return self._tooltip_text

    def should_ignore(self, event: Event) -> bool:
        """Return True if the event ended with the cursor outside this element, False otherwise"""
        width, height = self.size_and_pos[0]
        return not (0 <= event.x <= width and 0 <= event.y <= height)

    # region Link Handling

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
            self.__link = LinkTarget.new(value, bind, self._tooltip_text, self._value)

    def update_link(self, link: Union[bool, str, BindTarget]):
        old = self.__link
        self.__link = new = LinkTarget.new(link, getattr(old, 'bind', None), self._tooltip_text, self._value)
        self.add_tooltip(new.tooltip if new else self._tooltip_text)
        if old and new and old.bind != new.bind:
            widget = self.widget
            widget.unbind(old.bind)
            widget.bind(new.bind, self._open_link)
        elif new and not old:
            self._enable_link()
        elif old and not new:
            self._disable_link(old.bind)

    def _enable_link(self):
        widget, link = self.widget, self.__link
        widget.bind(link.bind, self._open_link)
        if link.use_link_style:
            link_style = self.style.link
            widget.configure(cursor='hand2', fg=link_style.fg.default, font=link_style.font.default)
        else:
            widget.configure(cursor='hand2')

    def _disable_link(self, link_bind: str):
        widget, link = self.widget, self.__link
        widget.unbind(link_bind)
        if link.use_link_style:
            if self._use_input_style:
                input_style = self.style.input
                widget.configure(cursor='', fg=input_style.fg.disabled, font=input_style.font.disabled)
            else:
                text_style = self.style.text
                widget.configure(cursor='', fg=text_style.fg.default, font=text_style.font.default)
        else:
            widget.configure(cursor='')

    def _open_link(self, event: Event):
        if not (link := self.link) or self.should_ignore(event):
            return
        link.open(event)

    # endregion


class Link(Text):
    def __init__(self, value: Any = '', link: Union[bool, str] = True, link_bind: str = LEFT_CLICK, **kwargs):
        super().__init__(value, link=link, link_bind=link_bind, **kwargs)


class InteractiveText(Interactive, ABC):
    _disabled_state: str

    def __init_subclass__(cls, disabled_state: str, **kwargs):  # noqa
        super().__init_subclass__(**kwargs)
        cls._disabled_state = disabled_state

    def disable(self):
        if self.disabled:
            return
        self._update_state(True)

    def enable(self):
        if not self.disabled:
            return
        self._update_state(False)

    def _update_state(self, disabled: bool):
        self.widget['state'] = self._disabled_state if disabled else 'normal'
        self.disabled = disabled
        self._refresh_colors()

    @abstractmethod
    def _refresh_colors(self):
        raise NotImplementedError


class Input(TextValueMixin, InteractiveText, disabled_state='readonly', move_cursor=True):
    widget: Entry
    password_char: Optional[str] = None

    def __init__(
        self,
        value: Any = '',
        *,
        link: bool = None,
        password_char: str = None,
        justify_text: Union[str, Justify, None] = Justify.LEFT,
        callback: BindTarget = None,
        **kwargs
    ):
        super().__init__(justify_text=justify_text, **kwargs)
        self.value = value
        self._link = link or link is None
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

        entry.bind('<FocusOut>', partial(_clear_selection, entry))  # Prevents ghost selections
        if self._link:  # TODO: Unify with Text's link handling
            entry.bind('<Control-Button-1>', self._open_link)
            if (value := self._value) and value.startswith(('http://', 'https://')):
                entry.configure(cursor='hand2')
        if (callback := self._callback) is not None:
            entry.bind('<Key>', self.normalize_callback(callback))

    def update(self, value: Any = None, disabled: Bool = None, password_char: str = None):
        if disabled is not None:
            self._update_state(disabled)
        if value is not None:
            self.value = value
        if password_char is not None:
            self.widget.configure(show=password_char)
            self.password_char = password_char

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

    def _open_link(self, event):
        if (value := self.value) and value.startswith(('http://', 'https://')):
            webbrowser.open(value)


class Multiline(InteractiveText, disabled_state='disabled'):
    widget: ScrollableText

    def __init__(
        self,
        value: Any = '',
        *,
        scroll_y: bool = True,
        scroll_x: bool = False,
        auto_scroll: bool = False,
        rstrip: bool = False,
        justify_text: Union[str, Justify, None] = Justify.LEFT,
        callback: BindTarget = None,
        **kwargs,
    ):
        super().__init__(justify_text=justify_text, **kwargs)
        self._value = str(value)
        self.scroll_y = scroll_y
        self.scroll_x = scroll_x
        self.auto_scroll = auto_scroll
        self.rstrip = rstrip
        self._callback = callback

    @property
    def style_config(self) -> dict[str, Any]:
        style, state = self.style, self.style_state
        config: dict[str, Any] = {
            'highlightthickness': 0,
            **style.get_map('input', state, bd='border_width', fg='fg', bg='bg', font='font', relief='relief'),
            **style.get_map('text', 'highlight', selectforeground='fg', selectbackground='bg'),
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

        """
        maxundo:
        spacing1:
        spacing2:
        spacing3:
        tabs:
        undo:
        wrap:
        """
        self.widget = scroll_text = ScrollableText(row.frame, self.scroll_y, self.scroll_x, self.style, **kwargs)
        text = scroll_text.inner_widget
        if value:
            text.insert(1.0, value)
        if (justify := self.justify_text) != Justify.NONE:
            text.tag_add(justify.value, 1.0, 'end')  # noqa
        for pos in ('center', 'left', 'right'):
            text.tag_configure(pos, justify=pos)  # noqa

        self.pack_widget()
        if (callback := self._callback) is not None:
            text.bind('<Key>', self.normalize_callback(callback))

    def clear(self):
        self.widget.inner_widget.delete('1.0', tkc.END)

    def write(self, text: str, *, fg: str = None, bg: str = None, font: Font = None, append: Bool = False):
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

    @cached_property
    def widgets(self) -> list[BaseWidget]:
        return self.widget.widgets

    def _refresh_colors(self):
        kwargs = self.style.get_map('text', self.style_state, fg='fg', bg='bg')
        log.debug(f'Refreshing colors for {self} with {self.style_state=}: {kwargs}')
        self.widget.configure(**kwargs)


def _clear_selection(widget: Union[Entry, Text], event: Event = None):
    widget.selection_clear()
