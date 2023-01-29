"""
Choice GUI elements

:author: Doug Skrypa
"""

from __future__ import annotations

import logging
import tkinter.constants as tkc
from contextvars import ContextVar
from itertools import count
from tkinter import Radiobutton, Checkbutton, BooleanVar, IntVar, StringVar, Event, TclError, BaseWidget
from tkinter.ttk import Combobox
from typing import TYPE_CHECKING, Optional, Union, Any, MutableMapping, Generic, Collection, TypeVar, Sequence, Iterable
from weakref import WeakValueDictionary

from tk_gui.caching import cached_property
from tk_gui.enums import ListBoxSelectMode
from tk_gui.pseudo_elements.scroll import ScrollableListbox
from tk_gui.typing import Bool, T, BindTarget, BindCallback, TraceCallback
from tk_gui.utils import max_line_len
from ._utils import normalize_underline
from .element import Interactive
from .exceptions import NoActiveGroup, BadGroupCombo
from .mixins import DisableableMixin, CallbackCommandMixin, TraceCallbackMixin

if TYPE_CHECKING:
    from tk_gui.pseudo_elements import Row

__all__ = ['Radio', 'RadioGroup', 'CheckBox', 'Combo', 'ListBox', 'make_checkbox_grid']
log = logging.getLogger(__name__)

_NotSet = object()
_radio_group_stack = ContextVar('tk_gui.elements.choices.radio.stack', default=[])
A = TypeVar('A')
B = TypeVar('B')


# region Radio


class Radio(DisableableMixin, CallbackCommandMixin, Interactive, Generic[T], base_style_layer='radio'):
    widget: Radiobutton

    def __init__(
        self,
        label: str,
        value: T = _NotSet,
        default: Bool = False,
        *,
        group: Union[RadioGroup, int] = None,
        callback: BindTarget = None,
        **kwargs,
    ):
        self.default = default
        self.label = label
        self._value = value
        self._callback = callback
        self.group = RadioGroup.get_group(group)
        self.choice_id = self.group.register(self)
        kwargs.setdefault('anchor', 'nw')
        super().__init__(**kwargs)

    def __repr__(self) -> str:
        val_str = f', value={self._value!r}' if self._value is not _NotSet else ''
        def_str = ', default=True' if self.default else ''
        return f'<{self.__class__.__name__}({self.label!r}{val_str}{def_str}, group={self.group!r})>'

    def select(self):
        self.group.select(self)

    def select_as_callback(self) -> BindCallback:
        def select_callback(event: Event):
            self.select()

        return select_callback

    @property
    def value(self) -> Union[T, str]:
        if (value := self._value) is not _NotSet:
            return value
        return self.label

    def pack_into_row(self, row: Row):
        super().pack_into_row(row)
        group = self.group
        if not group._registered and (key := group.key):
            row.window.register_element(key, group)
        group._registered = True

    @property
    def style_config(self) -> dict[str, Any]:
        style = self.style
        return {
            'highlightthickness': 1,
            # **style.get_map(
            #     'radio', self.style_state, bd='border_width', font='font', highlightcolor='fg', fg='fg',
            #     highlightbackground='bg', background='bg', activebackground='bg',
            # ),
            **style.get_map('radio', self.style_state, bd='border_width', font='font', fg='fg', background='bg'),
            **style.get_map('radio', 'active', activebackground='bg', activeforeground='fg'),
            **style.get_map('radio', 'highlight', highlightbackground='bg', highlightcolor='fg'),
            **style.get_map('selected', self.style_state, selectcolor='fg'),
            **self._style_config,
        }

    def pack_into(self, row: Row):
        kwargs = {
            'text': self.label,
            'value': self.choice_id,
            'variable': self.group.get_selection_var(),
            'takefocus': int(self.allow_focus),
            **self.style_config,
        }
        if (callback := self._callback) is not None:
            kwargs['command'] = self.normalize_callback(callback)
        try:
            kwargs['width'], kwargs['height'] = self.size
        except TypeError:
            pass
        if self.disabled:
            kwargs['state'] = self._disabled_state

        self.widget = Radiobutton(row.frame, **kwargs)
        self.pack_widget()
        if self.default:
            self.select()


class RadioGroup(TraceCallbackMixin):
    _instances: MutableMapping[int, RadioGroup] = WeakValueDictionary()
    _counter = count()
    choices: dict[int, Radio]

    def __init__(self, key: str = None, *, change_cb: BindTarget = None, include_label: Bool = False):
        """
        :param key: Key to use in Window results for the result of this radio group
        :param change_cb: Callback that should be called when a selection is made in this group.  If the currently
          selected item is clicked again, then the callback will be called again, even though the selection did not
          change.
        :param include_label: If True, :meth:`.value` will return a tuple of (label, value) for the selected member,
          otherwise only the selected member's value will be returned.
        """
        self.id = next(self._counter)
        self.key = key
        self._instances[self.id] = self
        self.choices = {}
        self._registered = False
        self.default: Optional[Radio] = None
        if change_cb:
            self.var_change_cb = change_cb
        self.include_label = include_label

    @property
    def tk_var(self) -> IntVar | None:
        try:
            return self.selection_var
        except AttributeError:
            return None

    def get_selection_var(self) -> IntVar:
        # The selection var cannot be initialized before a root window exists
        try:
            return self.selection_var  # noqa
        except AttributeError:
            self.selection_var = tk_var = IntVar()  # noqa
            self._maybe_add_var_trace()
            return tk_var

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
            return (choice.label, choice.value) if self.include_label else choice.value
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

# region CheckBox


class CheckBox(DisableableMixin, CallbackCommandMixin, TraceCallbackMixin, Interactive, base_style_layer='checkbox'):
    widget: Checkbutton
    tk_var: Optional[BooleanVar] = None
    _values: Optional[tuple[B, A]] = None

    def __init__(
        self,
        label: str,
        default: Bool = False,
        *,
        true_value: A = None,
        false_value: B = None,
        underline: Union[str, int] = None,
        callback: BindTarget = None,
        change_cb: TraceCallback = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.label = label
        self.default = default
        self._underline = underline
        self._callback = callback
        if change_cb:
            self.var_change_cb = change_cb
        if not (true_value is false_value is None):
            self._values = (false_value, true_value)

    # region Value-related Methods

    @property
    def value(self) -> Union[bool, A, B]:
        result = self.tk_var.get()
        if values := self._values:
            return values[result]
        return result

    @value.setter
    def value(self, value: Union[bool, A, B]):
        if (values := self._values) and value in values:
            self.tk_var.set(values[0] != value)
        else:
            self.tk_var.set(value)

    def toggle(self) -> bool:
        """
        Toggle the value, and return the new value.
        Only returns the boolean value, not the custom ones, if custom ones were provided.
        """
        tk_var = self.tk_var
        new_val = not tk_var.get()
        tk_var.set(new_val)
        return new_val

    def toggle_as_callback(self) -> BindCallback:
        """Helper method that returns a callback that can be used by other elements to toggle this checkbox's value."""

        def toggle_callback(event: Event):
            self.toggle()

        return toggle_callback

    # endregion

    # region Style Methods

    @property
    def underline(self) -> Optional[int]:
        return normalize_underline(self._underline, self.label)

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

    # endregion

    def pack_into(self, row: Row):
        self.tk_var = tk_var = BooleanVar(value=self.default)
        kwargs = {
            'text': self.label,
            'variable': tk_var,
            'takefocus': int(self.allow_focus),
            'underline': self.underline,
            # 'tristatevalue': 2,  # A different / user-specified value could be used
            # 'tristateimage': '-',  # needs to be an image; may need `image` (+ selectimage) as well to be used
            **self.style_config,
        }
        # Note: The default tristate icon on Win10 / Py 3.10.5 / Tcl 8.6.12 appears to be the same as the checked icon
        try:
            kwargs['width'], kwargs['height'] = self.size
        except TypeError:
            pass
        if self.disabled:
            kwargs['state'] = self._disabled_state
        if (callback := self._callback) is not None:
            kwargs['command'] = self.normalize_callback(callback)

        self._maybe_add_var_trace()
        self.widget = Checkbutton(row.frame, **kwargs)
        self.pack_widget()


def make_checkbox_grid(rows: list[Sequence[CheckBox]]):
    if len(rows) > 1 and len(rows[-1]) == 1:
        last_row = rows[-1]
        rows = rows[:-1]
    else:
        last_row = None

    shortest_row = min(map(len, (row for row in rows)))
    longest_boxes = [max(map(len, (row[column].label for row in rows))) for column in range(shortest_row)]
    for row in rows:
        for column, width in enumerate(longest_boxes):
            row[column].size = (width, 1)

    if last_row is not None:
        rows.append(last_row)
    return rows


# endregion


class Combo(
    DisableableMixin, TraceCallbackMixin, Interactive,
    disabled_state='disable', enabled_state='enable', base_style_layer='combo',
):
    """A form element that provides a drop down list of items to select.  Only 1 item may be selected."""
    widget: Combobox
    tk_var: Optional[StringVar] = None

    def __init__(
        self,
        choices: Collection[str],
        default: str = None,
        *,
        read_only: Bool = False,
        callback: BindTarget = None,
        change_cb: TraceCallback = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.choices = choices
        self.default = default
        self.read_only = read_only
        self._callback = callback
        if change_cb:
            self.var_change_cb = change_cb

    @property
    def value(self) -> Any:
        choice = self.tk_var.get()
        try:
            return self.choices[choice]  # noqa
        except TypeError:
            return choice

    # region Style Methods

    def _prepare_ttk_style(self) -> str:
        style, state = self.style, self.style_state
        ttk_style_name, ttk_style = style.make_ttk_style('.TCombobox')
        style_kwargs = {
            **style.get_map('combo', state, foreground='fg', insertcolor='fg', fieldbackground='bg'),
            **style.get_map('arrows', state, arrowcolor='fg', background='bg'),
            **style.get_map('selected', state, selectforeground='fg', selectbackground='bg'),
        }
        ttk_style.configure(ttk_style_name, **style_kwargs)
        if ro_bg := style.combo.bg[state]:
            ttk_style.map(ttk_style_name, fieldbackground=[('readonly', ro_bg)])
        return ttk_style_name

    @property
    def style_config(self) -> dict[str, Any]:
        style, state = self.style, self.style_state
        return {
            **style.get_map('combo', state, font='font'),
            **self._style_config,
        }

    # endregion

    @property
    def callback(self) -> BindTarget | None:
        return self._callback

    @callback.setter
    def callback(self, callback: BindTarget | None):
        self._callback = callback
        if widget := self.widget:
            widget.bind('<<ComboboxSelected>>', self.normalize_callback(callback))

    def pack_into(self, row: Row):
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

        if self.disabled:
            kwargs['state'] = self._disabled_state
        elif self.read_only:
            kwargs['state'] = 'readonly'

        self._maybe_add_var_trace()
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
        if (callback := self._callback) is not None:
            combo_box.bind('<<ComboboxSelected>>', self.normalize_callback(callback))

    def enable(self):
        if not self.disabled:
            return
        self.widget['state'] = 'readonly' if self.read_only else self._enabled_state
        self.disabled = False


class ListBox(DisableableMixin, Interactive, base_style_layer='listbox'):
    widget: ScrollableListbox

    def __init__(
        self,
        choices: Collection[str],
        default: Union[str, Collection[str]] = None,
        select_mode: Union[str, ListBoxSelectMode] = ListBoxSelectMode.EXTENDED,
        *,
        scroll_y: Bool = True,
        scroll_x: Bool = False,
        callback: BindTarget = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.choices = tuple(choices)
        self.defaults = {default} if isinstance(default, str) else set(default) if default else None
        self.select_mode = ListBoxSelectMode(select_mode)
        self.scroll_y = scroll_y
        self.scroll_x = scroll_x
        self._callback = callback
        self._prev_selection: Optional[tuple[int]] = None
        self._last_selection: Optional[tuple[int]] = None

    # region Selection Methods

    @property
    def value(self) -> list[str]:
        list_box, choices = self.widget.inner_widget, self.choices
        try:
            return [choices[i] for i in list_box.curselection()]
        except TclError as e:
            log.log(9, f'Using cached listbox selection due to error obtaining current selection: {e}')
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
        if (cb := self.callback) is not None:
            cb(event)

    def get_selection_indices(self) -> list[int]:
        return self.widget.inner_widget.curselection()

    def set_selection_indices(self, index_or_indices: int | Iterable[int]):
        if isinstance(index_or_indices, int):
            index_or_indices = (index_or_indices,)

        list_box = self.widget.inner_widget
        for i in index_or_indices:
            list_box.selection_set(i)

    def append_choice(self, value: str, select: Bool = False, resize: Bool = True):
        list_box = self.widget.inner_widget
        list_box.insert(tkc.END, value)
        self.choices = (*self.choices, value)
        num_choices = len(self.choices)
        if select:
            list_box.selection_set(num_choices - 1)
        if resize and num_choices != list_box.cget('height'):
            list_box.configure(height=num_choices)

    def reset(self, default: Bool = True):
        list_box = self.widget.inner_widget
        if default and (defaults := self.defaults):
            for i, choice in enumerate(self.choices):
                if choice in defaults:
                    list_box.selection_set(i)
        else:
            list_box.selection_clear(0, len(self.choices))

    # endregion

    @property
    def style_config(self) -> dict[str, Any]:
        style, state = self.style, self.style_state
        return {
            'highlightthickness': 0,
            **style.get_map('listbox', state, font='font', background='bg', fg='fg', ),
            **style.get_map('selected', state, font='font', selectbackground='bg', selectforeground='fg', ),
            **self._style_config,
        }

    @property
    def callback(self) -> BindTarget | None:
        return self._callback

    @callback.setter
    def callback(self, callback: BindTarget | None):
        if self.widget:
            self._callback = self.normalize_callback(callback)
        else:
            self._callback = callback

    def pack_into(self, row: Row):
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
        if self.disabled:
            kwargs['state'] = self._disabled_state

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
        if (callback := self._callback) is not None:
            self._callback = self.normalize_callback(callback)

    @cached_property
    def widgets(self) -> list[BaseWidget]:
        return self.widget.widgets
