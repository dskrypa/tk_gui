"""
Choice GUI elements

:author: Doug Skrypa
"""

from __future__ import annotations

import logging
import tkinter.constants as tkc
from contextvars import ContextVar
from itertools import count
from tkinter import Radiobutton, Checkbutton, BooleanVar, IntVar, StringVar, Event, TclError
from tkinter.ttk import Combobox
from typing import TYPE_CHECKING, Optional, Union, Any, MutableMapping, Generic, Collection
from weakref import WeakValueDictionary

from ..enums import ListBoxSelectMode
from ..pseudo_elements.scroll import ScrollableListbox
from ..typing import Bool, T
from ..utils import max_line_len
from .element import Interactive
from .exceptions import NoActiveGroup, BadGroupCombo

if TYPE_CHECKING:
    from ..pseudo_elements import Row

__all__ = ['Radio', 'RadioGroup', 'CheckBox', 'Combo', 'ListBox']
log = logging.getLogger(__name__)

_NotSet = object()
_radio_group_stack = ContextVar('tk_gui.elements.choices.radio.stack', default=[])


# region Radio


class Radio(Interactive, Generic[T]):
    widget: Radiobutton

    def __init__(
        self, text: str, value: T = _NotSet, default: Bool = False, group: Union[RadioGroup, int] = None, **kwargs
    ):
        self.default = default
        self.text = text
        self._value = value
        self.group = RadioGroup.get_group(group)
        self.choice_id = self.group.register(self)
        kwargs.setdefault('anchor', 'nw')
        super().__init__(**kwargs)

    def __repr__(self) -> str:
        val_str = f', value={self._value!r}' if self._value is not _NotSet else ''
        def_str = ', default=True' if self.default else ''
        return f'<{self.__class__.__name__}({self.text!r}{val_str}{def_str}, group={self.group!r})>'

    def select(self):
        self.group.select(self)

    @property
    def value(self) -> Union[T, str]:
        if (value := self._value) is not _NotSet:
            return value
        return self.text

    def pack_into_row(self, row: Row, column: int):
        super().pack_into_row(row, column)
        group = self.group
        if not group._registered and (key := group.key):
            row.window.register_element(key, group)
        group._registered = True

    @property
    def style_config(self) -> dict[str, Any]:
        style = self.style
        return {
            'highlightthickness': 1,
            **style.get_map(
                'radio', self.style_state, bd='border_width', font='font', highlightcolor='fg', fg='fg',
                highlightbackground='bg', background='bg', activebackground='bg',
            ),
            **style.get_map('selected', self.style_state, selectcolor='fg'),
            **self._style_config,
        }

    def pack_into(self, row: Row, column: int):
        kwargs = {
            'text': self.text,
            'value': self.choice_id,
            'variable': self.group.get_selection_var(),
            'takefocus': int(self.allow_focus),
            **self.style_config,
        }
        try:
            kwargs['width'], kwargs['height'] = self.size
        except TypeError:
            pass
        """
        indicatoron: bool
        selectimage:
        """
        self.widget = Radiobutton(row.frame, **kwargs)
        self.pack_widget()
        if self.default:
            self.select()


class RadioGroup:
    _instances: MutableMapping[int, RadioGroup] = WeakValueDictionary()
    _counter = count()
    __slots__ = ('id', 'key', 'selection_var', 'choices', 'default', '_registered', '__weakref__')
    choices: dict[int, Radio]

    def __init__(self, key: str = None):
        self.id = next(self._counter)
        self.key = key
        self._instances[self.id] = self
        self.choices = {}
        self._registered = False
        self.default: Optional[Radio] = None

    def get_selection_var(self) -> IntVar:
        # The selection var cannot be initialized before a root window exists
        try:
            return self.selection_var
        except AttributeError:
            self.selection_var = var = IntVar()  # noqa
            return var

    @classmethod
    def get_group(cls, group: Union[RadioGroup, int, None]) -> RadioGroup:
        if group is None:
            return get_current_radio_group()
        elif isinstance(group, cls):
            return group
        return cls._instances[group]

    def register(self, choice: Radio) -> int:
        value = len(self.choices) + 1
        self.choices[value] = choice
        if choice.default:
            if self.default:
                raise BadGroupCombo(f'Found multiple choices marked as default: {self.default}, {choice}')
            self.default = choice
        return value

    def add_choice(self, text: str, value: Any = _NotSet, **kwargs) -> Radio:
        return Radio(text, value, group=self, **kwargs)

    def select(self, choice: Radio):
        self.selection_var.set(choice.choice_id)

    def reset(self, default: Bool = True):
        self.selection_var.set(self.default.choice_id if default and self.default else 0)

    def get_choice(self) -> Optional[Radio]:
        return self.choices.get(self.selection_var.get())

    @property
    def value(self) -> Any:
        if choice := self.get_choice():
            return choice.value
        return None

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}(key={self.key!r})[id={self.id}, choices={len(self.choices)}]>'

    def __getitem__(self, value: int) -> Radio:
        return self.choices[value]

    def __enter__(self) -> RadioGroup:
        _radio_group_stack.get().append(self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        _radio_group_stack.get().pop()


def get_current_radio_group(silent: bool = False) -> Optional[RadioGroup]:
    """
    Get the currently active RadioGroup.

    :param silent: If True, allow this function to return ``None`` if there is no active :class:`RadioGroup`
    :return: The active :class:`RadioGroup` object
    :raises: :class:`~.exceptions.NoActiveGroup` if there is no active RadioGroup and ``silent=False`` (default)
    """
    try:
        return _radio_group_stack.get()[-1]
    except (AttributeError, IndexError):
        if silent:
            return None
        raise NoActiveGroup('There is no active context') from None


# endregion


class CheckBox(Interactive):
    widget: Checkbutton
    tk_var: Optional[BooleanVar] = None

    def __init__(self, text: str, default: Bool = False, **kwargs):
        super().__init__(**kwargs)
        self.text = text
        self.default = default

    @property
    def value(self) -> bool:
        return self.tk_var.get()

    @property
    def style_config(self) -> dict[str, Any]:
        style = self.style
        return {
            'highlightthickness': 1,
            **style.get_map(
                'checkbox', self.style_state, bd='border_width', font='font', highlightcolor='fg', fg='fg',
                highlightbackground='bg', background='bg', activebackground='bg',
            ),
            **style.get_map('selected', self.style_state, selectcolor='fg'),
            **self._style_config,
        }

    def pack_into(self, row: Row, column: int):
        self.tk_var = tk_var = BooleanVar(value=self.default)
        kwargs = {'text': self.text, 'variable': tk_var, 'takefocus': int(self.allow_focus), **self.style_config}
        try:
            kwargs['width'], kwargs['height'] = self.size
        except TypeError:
            pass
        """
        underline: int index of char in text to underline
        textvariable: var for text
        indicatoron: bool
        offvalue: value to store when off
        onvalue: value to store when on
        selectimage:
        tristateimage:
        tristatevalue:
        """
        self.widget = Checkbutton(row.frame, **kwargs)
        self.pack_widget()


class Combo(Interactive):
    widget: Combobox
    tk_var: Optional[StringVar] = None

    def __init__(self, choices: Collection[str], default: str = None, read_only: Bool = False, **kwargs):
        super().__init__(**kwargs)
        self.choices = choices
        self.default = default
        self.read_only = read_only  # TODO: Handle
        # TODO: To register a callback on selection made: '<<ComboboxSelected>>'

    @property
    def value(self) -> Any:
        choice = self.tk_var.get()
        try:
            return self.choices[choice]  # noqa
        except TypeError:
            return choice

    def _prepare_ttk_style(self) -> str:
        style, state = self.style, self.style_state
        ttk_style_name, ttk_style = style.make_ttk_style('.TCombobox')
        style_kwargs = {
            **style.get_map('combo', state, foreground='fg', insertcolor='fg', fieldbackground='bg'),
            **style.get_map('arrows', state, arrowcolor='fg', background='bg'),
            **style.get_map('selected', state, selectforeground='fg', selectbackground='bg'),
        }
        ttk_style.configure(ttk_style_name, **style_kwargs)
        ttk_style.map(ttk_style_name, fieldbackground=[('readonly', style.combo.bg[state])])
        return ttk_style_name

    @property
    def style_config(self) -> dict[str, Any]:
        style, state = self.style, self.style_state
        return {
            **style.get_map('combo', state, font='font'),
            **self._style_config,
        }

    def pack_into(self, row: Row, column: int):
        self.tk_var = tk_var = StringVar()
        style, state = self.style, self.style_state
        kwargs = {
            'textvariable': tk_var,
            'style': self._prepare_ttk_style(),
            'values': list(self.choices),
            'takefocus': int(self.allow_focus),
            **self.style_config,
        }
        try:
            kwargs['width'], kwargs['height'] = self.size
        except TypeError:
            kwargs['width'] = max_line_len(self.choices) + 1

        self.widget = combo_box = Combobox(row.frame, **kwargs)
        fg, bg = style.combo.fg[state], style.combo.bg[state]
        if fg and bg:  # This sets colors for drop-down formatting
            combo_box.tk.eval(
                f'[ttk::combobox::PopdownWindow {combo_box}].f.l configure'
                f' -foreground {fg} -background {bg} -selectforeground {bg} -selectbackground {fg}'
            )

        self.pack_widget()
        if default := self.default:
            combo_box.set(default)


class ListBox(Interactive):
    widget: ScrollableListbox

    def __init__(
        self,
        choices: Collection[str],
        default: Union[str, Collection[str]] = None,
        select_mode: Union[str, ListBoxSelectMode] = ListBoxSelectMode.EXTENDED,
        scroll_y: Bool = True,
        scroll_x: Bool = False,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.choices = tuple(choices)
        self.defaults = {default} if isinstance(default, str) else set(default) if default else None
        self.select_mode = ListBoxSelectMode(select_mode)
        self.scroll_y = scroll_y
        self.scroll_x = scroll_x
        self._prev_selection: Optional[tuple[int]] = None
        self._last_selection: Optional[tuple[int]] = None

    @property
    def value(self) -> list[str]:
        list_box, choices = self.widget.inner_widget, self.choices
        try:
            return [choices[i] for i in list_box.curselection()]
        except TclError as e:
            log.debug(f'Using cached listbox selection due to error obtaining current selection: {e}')
            prev, last = self._prev_selection, self._last_selection
            if self.window.closed and prev and not last:
                # An empty selection is registered while closing, before anything can be set to indicate it is happening
                last = prev
            elif last is None:
                if defaults := self.defaults:
                    return [choice for choice in self.choices if choice in defaults]
                last = ()
            return [choices[i] for i in last]

    def _handle_selection_made(self, event: Event = None):
        """
        Stores the most recent selection so it can be used if the window is closed / the widget is destroyed before this
        element's value is accessed.
        """
        self._prev_selection = self._last_selection
        self._last_selection = self.widget.inner_widget.curselection()

    def reset(self, default: Bool = True):
        list_box = self.widget.inner_widget
        if default and (defaults := self.defaults):
            for i, choice in enumerate(self.choices):
                if choice in defaults:
                    list_box.selection_set(i)
        else:
            list_box.selection_clear(0, len(self.choices))

    @property
    def style_config(self) -> dict[str, Any]:
        style, state = self.style, self.style_state
        return {
            'highlightthickness': 0,
            **style.get_map('listbox', state, font='font', background='bg', fg='fg', ),
            **style.get_map('selected', state, font='font', selectbackground='bg', selectforeground='fg', ),
            **self._style_config,
        }

    def pack_into(self, row: Row, column: int):
        kwargs = {
            'exportselection': False,  # Prevent selections in this box from affecting others / the primary selection
            'selectmode': self.select_mode.value,
            'takefocus': int(self.allow_focus),
            **self.style_config,
        }
        try:
            kwargs['width'], kwargs['height'] = self.size
        except TypeError:
            kwargs['width'] = max_line_len(self.choices) + 1

        """
        activestyle: Literal["dotbox", "none", "underline"]
        setgrid: bool
        """
        self.widget = outer = ScrollableListbox(row.frame, self.scroll_y, self.scroll_x, self.style, **kwargs)
        list_box = outer.inner_widget
        if choices := self.choices:
            list_box.insert(tkc.END, *choices)
            self.reset(default=True)

        self.pack_widget()
        list_box.bind('<<ListboxSelect>>', self._handle_selection_made)
