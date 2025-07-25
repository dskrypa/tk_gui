"""
Text GUI elements

:author: Doug Skrypa
"""

from __future__ import annotations

import logging
import tkinter.constants as tkc
from abc import ABC, abstractmethod
from functools import partial
from pathlib import Path
from tkinter import StringVar, Event, Entry, Label as TkLabel, Text as TkText, Frame as TkFrame
from typing import TYPE_CHECKING, Optional, Union, Any, Callable, Generic, TypeVar

from tk_gui.caching import cached_property
from tk_gui.constants import LEFT_CLICK
from tk_gui.enums import Justify, Anchor, StyleState
from tk_gui.event_handling import BindManager
from tk_gui.styles import Style, StyleLayer
from tk_gui.utils import Inheritable, max_line_len, call_with_popped
from tk_gui.widgets.scroll import ScrollableText
from tk_gui.widgets.utils import unbind
from ..element import Element, Interactive
from ..exceptions import MultilineContextError
from ..mixins import DisableableMixin, TraceCallbackMixin
from .links import LinkTarget, _Link

if TYPE_CHECKING:
    from tkinter.ttk import Scrollbar
    from tk_gui.geometry.typing import XY
    from tk_gui.pseudo_elements import Row
    from tk_gui.styles.typing import Font
    from tk_gui.typing import Bool, BindTarget, TraceCallback, TkFill, HasFrame, TkContainer

__all__ = ['Text', 'Link', 'Input', 'Multiline', 'Label', 'ValidatedInput', 'NumericInput', 'FloatInput', 'IntInput']
log = logging.getLogger(__name__)

_Anchor = Union[str, Anchor]
_Justify = Union[str, Justify]
T = TypeVar('T')


class TextValueMixin(TraceCallbackMixin):
    string_var: Optional[StringVar] = None
    widget: Union[TkLabel, Entry]
    justify: Justify = Inheritable('text_justification', type=Justify)
    size: XY
    fill: TkFill
    expand: bool
    strip: bool = False
    _value: str
    _move_cursor: bool = False
    _auto_size: bool = True
    _pad_width: int = 0

    def __init_subclass__(cls, move_cursor: bool = False, **kwargs):
        super().__init_subclass__(**kwargs)
        if move_cursor:
            cls._move_cursor = move_cursor

    def init_text_value(
        self,
        value: Any = '',
        strip: Bool = False,
        justify: _Justify = None,
        change_cb: TraceCallback = None,
        auto_size: Bool = True,
        pad_width: int = 0,
    ):
        if strip:
            self.strip = strip
        self.value = value
        self.justify = justify
        if change_cb:
            self.var_change_cb = change_cb
        if pad_width:
            self._pad_width = pad_width
        if not auto_size:
            self._auto_size = auto_size

    @property
    def value(self) -> str:
        try:
            value = self.string_var.get()
        except AttributeError:  # The element has not been packed yet, so string_var is None
            return self._value
        else:
            return value.strip() if self.strip else value

    @value.setter
    def value(self, value: Any):
        if isinstance(value, Path):
            value = value.as_posix()
        else:
            value = str(value)
            if self.strip:
                value = value.strip()

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
        self._maybe_add_var_trace()

    @property
    def tk_var(self) -> StringVar | None:
        return self.string_var

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

    def _init_size(self, font: Font, multiline: bool = False) -> Optional[XY]:
        try:
            width, size = self.size
        except TypeError:
            pass
        else:
            return width, size

        if self._auto_size:
            return self._calc_size(font, multiline)
        else:
            return None

    def _calc_size(self, font: Font, multiline: bool = False) -> Optional[XY]:
        if not self._value:
            return None

        if multiline:
            lines = self._value.splitlines()
            width = max(map(len, lines))
            height = len(lines) + self._pad_width
        else:
            width = len(self._value) + self._pad_width
            height = 1

        if (font and 'bold' in font) or not (self.expand and self.fill in ('x', 'both', True)):
            # TODO: The expand/fill condition seems to only be necessary when the value contains a thin char like
            #  lower-case L
            width += 1

        return width, height


class LinkableMixin:
    __link: Optional[LinkTarget] = None
    __bound_id: str | None = None
    _tooltip_text: str | None
    _calc_size: Callable
    add_tooltip: Callable
    pack_widget: Callable
    grid_widget: Callable
    widget: Union[TkLabel, Entry]
    style: Style
    style_config: dict[str, Any]
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
            unbind(widget, old.bind, self.__bound_id)
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
        unbind(widget, link_bind, self.__bound_id)
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

    def update(self, value: Any = None, link: _Link = None, auto_resize: Bool = False):
        if value is not None:
            self.value = value
        if link is not None:
            self.update_link(link)
        if auto_resize and (size := self._calc_size(self.style_config.get('font'))):
            self.widget.configure(width=size[0])

    def _init_widget(self, tk_container: TkContainer):
        raise NotImplementedError

    def pack_into(self, row: Row):
        self._init_widget(row.frame)
        self.pack_widget()
        self.maybe_enable_link()

    def grid_into(self, parent: HasFrame, row: int, column: int, **kwargs):
        self._init_widget(parent.frame)
        self.grid_widget(row, column, **kwargs)
        self.maybe_enable_link()


class Label(TextValueMixin, LinkableMixin, Element, base_style_layer='text'):
    """A text element in which the text is NOT selectable."""
    widget: TkLabel
    anchor_info: Anchor = Anchor.NONE

    def __init__(
        self,
        value: Any = '',
        link: _Link | LinkTarget = None,
        *,
        justify: _Justify = None,
        anchor_info: _Anchor = None,
        link_bind: str = None,
        auto_size: Bool = True,
        pad_width: int = 0,
        strip: Bool = False,
        change_cb: TraceCallback = None,
        tooltip: str = None,
        **kwargs,
    ):
        if justify is anchor_info is None:
            justify = Justify.LEFT
            anchor_info = justify.as_anchor()
        self.init_text_value(value, strip, justify, change_cb, auto_size, pad_width)
        self.init_linkable(link, link_bind, tooltip)
        super().__init__(**kwargs)
        if anchor_info:
            self.anchor_info = Anchor(anchor_info)

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

    def _init_widget(self, tk_container: TkContainer):
        self.init_string_var()
        kwargs = {
            'textvariable': self.string_var,
            'anchor': self.anchor_info.value,
            'justify': self.justify.value,
            'wraplength': 0,
            'takefocus': int(self.allow_focus),
            **self.style_config,
        }
        try:
            kwargs['width'], kwargs['height'] = self._init_size(kwargs.get('font'), True)
        except TypeError:
            pass

        self.widget = label = TkLabel(tk_container, **kwargs)
        if kwargs.get('height', 1) != 1:
            wrap_len = label.winfo_reqwidth()  # width in pixels
            label.configure(wraplength=wrap_len)


class Text(TextValueMixin, LinkableMixin, Element):
    widget: Entry

    def __init__(
        self,
        value: Any = '',
        link: _Link | LinkTarget = None,
        *,
        justify: _Justify = None,
        link_bind: str = None,
        auto_size: Bool = True,
        pad_width: int = 0,
        use_input_style: Bool = False,
        strip: Bool = False,
        change_cb: TraceCallback = None,
        tooltip: str = None,
        **kwargs,
    ):
        self.init_text_value(value, strip, justify, change_cb, auto_size, pad_width)
        # TODO: Also bind link to middle click
        self.init_linkable(link, link_bind, tooltip)
        super().__init__(**kwargs)
        self._use_input_style = use_input_style

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
            style_cfg = {
                **style.get_map('text', bd='border_width', fg='fg', bg='bg', font='font', relief='relief'),
                **style.get_map('text', readonlybackground='bg'),
                **self._style_config,
            }
            style_cfg.setdefault('relief', 'flat')
            return style_cfg

    @property
    def base_style_layer_and_state(self) -> tuple[StyleLayer, StyleState]:
        if self._use_input_style:
            return self.style.input, StyleState.DISABLED
        else:
            return self.style.text, StyleState.DEFAULT

    def _init_widget(self, tk_container: TkContainer):
        self.init_string_var()
        kwargs = {
            'highlightthickness': 0,
            'textvariable': self.string_var,
            'justify': self.justify.value,
            'state': 'readonly',
            'takefocus': int(self.allow_focus),
            **self.style_config,
        }
        # TODO: On linux, text anchoring within box is equivalent to N instead of C...  Looks bad.
        try:
            kwargs['width'] = self._init_size(kwargs.get('font'))[0]
        except TypeError:
            pass
        self.widget = Entry(tk_container, **kwargs)


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
        self.apply_style()


# region Input Elements


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
        justify: Union[_Justify, None] = Justify.LEFT,
        callback: BindTarget = None,                                # Key press callback
        change_cb: TraceCallback = None,                            # Value change callback
        strip: Bool = False,
        auto_size: Bool = True,
        pad_width: int = 0,
        **kwargs,
    ):
        self.init_text_value(value, strip, justify, change_cb, auto_size, pad_width)
        self.init_linkable(link, link_bind, kwargs.pop('tooltip', None))
        super().__init__(**kwargs)
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

    def _init_widget(self, tk_container: TkContainer):
        self.init_string_var()
        kwargs = {
            'textvariable': self.string_var,
            'show': self.password_char,
            'justify': self.justify.value,
            'takefocus': int(self.allow_focus),
            **self.style_config,
        }
        try:
            kwargs['width'] = self._init_size(kwargs.get('font'))[0]
        except TypeError:
            pass
        if self.disabled:
            kwargs['state'] = self._disabled_state

        self.widget = entry = Entry(tk_container, **kwargs)
        entry.bind('<FocusOut>', partial(_clear_selection, entry), add=True)  # Prevents ghost selections
        if self._callback is not None:
            entry.bind('<Key>', self.normalize_callback(self._callback), add=True)

    def update(
        self,
        value: Any = None,
        disabled: Bool = None,
        password_char: str = None,
        link: _Link = None,
        auto_resize: Bool = False,
    ):
        if disabled is not None:
            self._update_state(disabled)
        if password_char is not None:
            self.widget.configure(show=password_char)
            self.password_char = password_char
        super().update(value, link, auto_resize)

    # region Update State

    def validated(self, valid: bool):
        if self.valid != valid:
            self.valid = valid
            self.apply_style()

    # endregion


class ValidatedInput(Input, ABC):
    def __init__(self, value: Any = '', **kwargs):
        if kwargs.pop('change_cb', None) is not None:
            raise TypeError(f"{self.__class__.__name__} doesn't support change_cb - use 'Input' with custom change_cbs")
        super().__init__(value, change_cb=self._validate, **kwargs)

    @abstractmethod
    def is_valid(self, value: str) -> bool:
        raise NotImplementedError

    def _validate(self, var_name, unknown, action):
        self.validated(self.is_valid(self.value))


class NumericInput(ValidatedInput, Generic[T], ABC):
    _num_func: Callable[[str], T] = None

    def __init_subclass__(cls, num_func: Callable[[str], T] = None, **kwargs):
        super().__init_subclass__(**kwargs)
        # TODO: Make the value property return the result of calling num_func on the raw value
        if num_func is not None:
            cls._num_func = num_func

    def __init__(self, value: Any = '', strip: Bool = True, **kwargs):
        super().__init__(value, strip=strip, **kwargs)

    def is_valid(self, value: str) -> bool:
        try:
            self._num_func(value)
        except (TypeError, ValueError):
            return False
        else:
            return True


class FloatInput(NumericInput, num_func=float):
    pass


class IntInput(NumericInput, num_func=int):
    pass


# endregion


class Multiline(InteractiveText, disabled_state='disabled'):
    widget: ScrollableText
    _read_only: Bool = False
    justify: Justify = Inheritable('text_justification', type=Justify)

    def __init__(
        self,
        value: Any = '',
        *,
        scroll_y: bool = True,
        scroll_x: bool = False,
        auto_scroll: bool = False,
        rstrip: bool = False,
        justify: Union[_Justify, None] = Justify.LEFT,
        input_cb: BindTarget = None,
        read_only: Bool = False,
        read_only_style: Bool = False,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.justify = justify
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

    # region State

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
        with self:
            self.apply_style()

    # endregion

    # region Style

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
            style_cfg = {
                'highlightthickness': 0,
                **style.get_map('text', bd='border_width', fg='fg', bg='bg', font='font', relief='relief'),
                **style.get_map('text', 'highlight', selectforeground='fg', selectbackground='bg'),
                **self._style_config,
            }
            style_cfg.setdefault('relief', 'flat')
        else:
            style_cfg: dict[str, Any] = {
                'highlightthickness': 0,
                **style.get_map('input', state, bd='border_width', fg='fg', bg='bg', font='font', relief='relief'),
                **style.get_map('input', 'highlight', selectforeground='fg', selectbackground='bg'),
                **style.get_map('insert', insertbackground='bg'),
                **self._style_config,
            }
            style_cfg.setdefault('relief', 'sunken')

        return style_cfg

    # endregion

    def _init_widget(self, tk_container: TkContainer):
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
        self.widget = scroll_text = ScrollableText(tk_container, self.scroll_y, self.scroll_x, self.style, **kwargs)
        text = scroll_text.inner_widget
        if value:
            text.insert(1.0, value)
        if (justify := self.justify) != Justify.NONE:
            text.tag_add(justify.value, 1.0, 'end')  # noqa
        for pos in ('center', 'left', 'right'):
            text.tag_configure(pos, justify=pos)  # noqa

        if self._read_only:
            self._bind_manager.bind('<Key>', _block_text_entry, text)
        elif (callback := self._input_cb) is not None:
            self._bind_manager.bind('<Key>', callback, text)

    def pack_into(self, row: Row):
        self._init_widget(row.frame)
        self.pack_widget()
        if self.disabled:
            # Note: This needs to occur after setting any text value, otherwise the text does not appear.
            self.widget.inner_widget.configure(state='disabled')

    def grid_into(self, parent: HasFrame, row: int, column: int, **kwargs):
        self._init_widget(parent.frame)
        self.grid_widget(row, column, **kwargs)
        if self.disabled:
            # Note: This needs to occur after setting any text value, otherwise the text does not appear.
            self.widget.inner_widget.configure(state='disabled')

    def __enter__(self) -> Multiline:
        if self.__entered:
            raise MultilineContextError(f'{self} does not support entering its context multiple times')
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
    def _bind_widget(self) -> TkText | None:
        try:
            return self.widget.inner_widget
        except AttributeError:  # self.widget is still None / hasn't been packed yet
            return None

    @cached_property
    def widgets(self) -> list[ScrollableText | TkText | TkFrame | Scrollbar]:
        return self.widget.widgets  # noqa


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
