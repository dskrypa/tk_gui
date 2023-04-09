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
from typing import TYPE_CHECKING, Optional, Union, Any, Generic, Collection, TypeVar, Sequence, Iterable
from typing import Mapping, MutableMapping
from weakref import WeakValueDictionary

from tk_gui.caching import cached_property
from tk_gui.enums import ListBoxSelectMode, Anchor
from tk_gui.typing import Bool, T, BindTarget, BindCallback, TraceCallback, TkContainer, HasFrame, XY
from tk_gui.utils import max_line_len, extract_kwargs
from tk_gui.widgets.scroll import ScrollableListbox
from ._utils import normalize_underline
from .element import Interactive
from .exceptions import NoActiveGroup, BadGroupCombo
from .mixins import DisableableMixin, CallbackCommandMixin, TraceCallbackMixin

if TYPE_CHECKING:
    from tkinter import Scrollbar, Listbox as TkListbox, Frame as TkFrame
    from tkinter.ttk import Style as TtkStyle
    from tk_gui.pseudo_elements import Row
    from tk_gui.window import Window

__all__ = ['Radio', 'RadioGroup', 'CheckBox', 'Combo', 'ComboMap', 'Dropdown', 'ListBox', 'make_checkbox_grid']
log = logging.getLogger(__name__)

_NotSet = object()
_radio_group_stack = ContextVar('tk_gui.elements.choices.radio.stack', default=[])
A = TypeVar('A')
B = TypeVar('B')
_Anchor = Union[str, Anchor]

# region Radio


class Radio(DisableableMixin, CallbackCommandMixin, Interactive, Generic[T], base_style_layer='radio'):
    widget: Radiobutton
    anchor_info: Anchor = Anchor.NONE

    def __init__(
        self,
        label: str,
        value: T = _NotSet,
        default: Bool = False,
        *,
        anchor_info: _Anchor = None,
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
        if anchor_info:
            self.anchor_info = Anchor(anchor_info)

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

    def _init_widget(self, tk_container: TkContainer):
        kwargs = {
            'text': self.label,
            'value': self.choice_id,
            'anchor': self.anchor_info.value,
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

        self.widget = Radiobutton(tk_container, **kwargs)

    def pack_into(self, row: Row):
        self._init_widget(row.frame)
        self.pack_widget()
        if self.default:
            self.select()

    def grid_into(self, parent: HasFrame, row: int, column: int, **kwargs):
        self._init_widget(parent.frame)
        self.grid_widget(row, column, **kwargs)
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

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}(key={self.key!r})[id={self.id}, choices={len(self.choices)}]>'

    # region Tk Variable

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

    # endregion

    # region Radio Registration & Related Methods

    @classmethod
    def get_group(cls, group: Union[RadioGroup, int, None]) -> RadioGroup:
        if group is None:
            return get_current_radio_group()
        elif isinstance(group, cls):
            return group
        return cls._instances[group]

    def __enter__(self) -> RadioGroup:
        _radio_group_stack.get().append(self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        _radio_group_stack.get().pop()

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

    # endregion

    @cached_property
    def window(self) -> Window:
        return next(radio.window for radio in self.choices.values())

    # region Set or Get Selected Choice

    def select(self, choice: Radio | int | str):
        if isinstance(choice, int):
            choice = self.choices[choice]
        elif isinstance(choice, str):
            if (from_key := next((c for c in self.choices.values() if c.key == choice), None)) is not None:
                choice = from_key
            elif (from_label := next((c for c in self.choices.values() if c.label == choice), None)) is not None:
                choice = from_label
            else:
                raise ValueError(f'Invalid {choice=} - expected a valid Radio key, label, or index')

        self.selection_var.set(choice.choice_id)

    def reset(self, default: Bool = True):
        self.selection_var.set(self.default.choice_id if default and self.default else 0)

    def __getitem__(self, value: int) -> Radio:
        return self.choices[value]

    def get_choice(self) -> Optional[Radio]:
        return self.choices.get(self.selection_var.get())

    @property
    def value(self) -> tuple[str, T | str] | T | str | None:
        if choice := self.get_choice():
            return (choice.label, choice.value) if self.include_label else choice.value
        return None

    # endregion


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
    anchor_info: Anchor = Anchor.NONE
    # TODO: Helper for initializing custom checkbox with a locked/unlocked padlock icon?

    def __init__(
        self,
        label: str,
        default: Bool = False,
        *,
        true_value: A = None,
        false_value: B = None,
        anchor_info: _Anchor = None,
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
        if anchor_info:
            self.anchor_info = Anchor(anchor_info)

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

    def update(self, value: Union[bool, A, B] = _NotSet, disabled: Bool = None):
        if value is not _NotSet:
            self.value = value
        if disabled is not None:
            self.toggle_enabled(disabled)

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

    # @cached_property
    # def _ttk_style(self) -> tuple[str, TtkStyle]:
    #     name, ttk_style = self.style.make_ttk_style('.TCheckbutton', theme=None)
    #     indicator = ('Checkbutton.indicator', {'side': 'left', 'sticky': ''})
    #     label = ('Checkbutton.label', {'sticky': 'nswe'})
    #     focus = ('Checkbutton.focus', {'side': 'left', 'sticky': 'w', 'children': [label]})
    #     padding = ('Checkbutton.padding', {'sticky': 'nswe', 'children': [indicator, focus]})
    #     ttk_style.layout(name, [padding])
    #     return name, ttk_style
    #
    # def _prepare_ttk_style(self) -> str:
    #     style, state = self.style, self.style_state
    #     ttk_style_name, ttk_style = self._ttk_style
    #     style_kwargs = {
    #         # 'indicatorcolor': '', 'indicatorbackground': '',
    #         **style.get_map('checkbox_label', state, font='font', foreground='fg', background='bg'),
    #         **style.get_map('checkbox', state, indicatorcolor='fg', indicatorbackground='bg'),
    #     }
    #     ttk_style.configure(ttk_style_name, **style_kwargs)
    #     ttk_style.map(
    #         ttk_style_name,
    #         foreground=style.get_ttk_map_list('checkbox_label', 'fg'),
    #         background=style.get_ttk_map_list('checkbox_label', 'bg'),
    #         # indicatorcolor=[(None, ''), ('active', ''), ('alternate', ''), ('disabled', ''), ('pressed', ''), ('selected', ''), ('readonly', '')],
    #         # indicatorbackground=[(None, ''), ('active', ''), ('alternate', ''), ('disabled', ''), ('pressed', ''), ('selected', ''), ('readonly', '')],
    #     )
    #     return ttk_style_name
    #
    # def apply_style(self):
    #     super().apply_style()
    #     self._prepare_ttk_style()

    @property
    def style_config(self) -> dict[str, Any]:
        """
        Notes for :class:`tkinter.Checkbutton` style:
            - selectcolor: The actual check box background; matches background when disabled
            - fg / foreground: Label text
            - bg / background: Outer frame background
            - disabledforeground: fg color when disabled
            - activeforeground: fg color while mouse button is down
            - activebackground: bg color while mouse button is down
            - highlightcolor / highlightbackground: Unknown
            - offrelief: default = raised
            - overrelief: default = n/a
            - relief: default = flat
        """
        style, state = self.style, self.style_state
        return {
            'highlightthickness': 1,
            **style.get_map(
                'checkbox_label', state, bd='border_width', font='font', fg='fg', bg='bg',
                activeforeground='fg', activebackground='bg', disabledforeground='fg',
            ),
            **style.get_map('checkbox', state, selectcolor='bg'),
            **self._style_config,
        }

    # endregion

    def _init_widget(self, tk_container: TkContainer):
        self.tk_var = tk_var = BooleanVar(value=self.default)
        kwargs = {
            'text': self.label,
            'variable': tk_var,
            'anchor': self.anchor_info.value,
            'takefocus': int(self.allow_focus),
            'underline': self.underline,
            # 'style': self._prepare_ttk_style(),
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
        self.widget = Checkbutton(tk_container, **kwargs)
        # from tk_gui.widgets.utils import dump_ttk_widget_info
        # dump_ttk_widget_info(self.widget)


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


TTK_STYLE_COMBO_KEY_MAP = {'active': 'active', 'alternate': 'default', 'disabled': 'disabled', 'readonly': 'default'}


class Combo(
    DisableableMixin, TraceCallbackMixin, Interactive,
    disabled_state='disable', enabled_state='enable', base_style_layer='combo',
):
    """A form element that provides a drop down list of items to select.  Only 1 item may be selected."""
    widget: Combobox
    tk_var: Optional[StringVar] = None
    allow_any: Bool

    def __init__(
        self,
        choices: Collection[str],
        default: str = None,
        *,
        read_only: Bool = False,
        callback: BindTarget = None,
        change_cb: TraceCallback = None,
        allow_any: Bool = False,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.choices = tuple(choices)
        self.default = default
        self.read_only = read_only  # TODO: Doesn't seem to do anything
        self.allow_any = allow_any
        self._callback = callback
        if change_cb:
            self.var_change_cb = change_cb

    # region Selection Methods

    @property
    def value(self) -> str | None:
        # TODO: Automatically mark invalid when an invalid value is manually typed?
        # TODO: Auto-filter to prefixed values on starting to type?
        choice = self.tk_var.get()
        if choice and (self.allow_any or choice in self.choices):
            return choice
        return None

    def select(self, value: str | int | None):
        if isinstance(value, int):
            try:
                choice = self.choices[value]
            except IndexError:
                raise ValueError(f'Invalid selection index={value} - pick from choices={self.choices}')
            else:
                self.widget.set(choice)
        elif not value:
            self.widget.set('')
        elif not self.allow_any and value not in self.choices:
            raise ValueError(f'Invalid selection {value=} - pick from choices={self.choices}')
        else:
            self.widget.set(value)

    def update_choices(self, choices: Collection[str], replace: Bool = False):
        if not self.was_packed:
            if replace:
                self.choices = tuple(choices)
                if (default := self.default) and default not in choices:
                    self.default = None
            else:
                self.choices = tuple(*self.choices, *choices)
            return

        if replace:
            selected = self.value
            self.choices = tuple(choices)
            if selected and selected not in choices:
                self.widget.set('')
        else:
            self.choices = tuple(*self.choices, *choices)

        self.widget['values'] = self.choices

    def update(
        self,
        selection: str | int | None = _NotSet,
        *,
        choices: Collection[str] = None,
        replace: Bool = False,
        disabled: Bool = None,
    ):
        if choices is not None:
            self.update_choices(choices, replace)
        if selection is not _NotSet:
            self.select(selection)
        if disabled is not None:
            self.toggle_enabled(disabled)

    def reset(self, default: Bool = True):
        if default:
            self.select(self.default)  # if the default is None, this will clear the selection
        else:
            self.widget.set('')

    # endregion

    # region Style Methods

    @cached_property
    def _ttk_style(self) -> tuple[str, TtkStyle]:
        return self.style.make_ttk_style('.TCombobox')

    def _prepare_ttk_style(self) -> str:
        style, state = self.style, self.style_state
        ttk_style_name, ttk_style = self._ttk_style
        combo, arrows = style.combo, style.arrows
        fg, bg, arrow_fg, arrow_bg = combo.fg, combo.bg, arrows.fg, arrows.bg
        style_kwargs = {
            'foreground': fg.default,
            'fieldbackground': bg.default,
            'arrowcolor': arrow_fg.default,
            'background': arrow_bg.default,
            **style.get_map('combo', state, insertcolor='fg'),
        }
        ttk_style.configure(ttk_style_name, **style_kwargs)

        keys = TTK_STYLE_COMBO_KEY_MAP.items()
        ttk_style.map(
            ttk_style_name,
            foreground=[(ttk_key, fg[s_key]) for ttk_key, s_key in keys],
            fieldbackground=[(ttk_key, bg[s_key]) for ttk_key, s_key in keys],
            arrowcolor=[(ttk_key, arrow_fg[s_key]) for ttk_key, s_key in keys],
            background=[(ttk_key, arrow_bg[s_key]) for ttk_key, s_key in keys],
        )
        return ttk_style_name

    def _apply_ttk_style(self):
        # This sets colors for drop-down formatting
        style, state = self.style, self.style_state
        fg, bg = style.combo.fg[state], style.combo.bg[state]
        # sel_fg, sel_bg = style.selected.fg[state], style.selected.bg[state]
        if fg and bg:
            widget = self.widget
            widget.tk.eval(
                f'[ttk::combobox::PopdownWindow {widget}].f.l configure'
                f' -foreground {fg} -background {bg} -selectforeground {bg} -selectbackground {fg}'
                # f' -foreground {fg} -background {bg} -selectforeground {sel_fg} -selectbackground {sel_bg}'
            )

    def apply_style(self):
        super().apply_style()
        self._prepare_ttk_style()
        self._apply_ttk_style()

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

    def _init_widget(self, tk_container: TkContainer):
        self.tk_var = tk_var = StringVar()
        kwargs = {
            'textvariable': tk_var,
            'style': self._prepare_ttk_style(),
            'values': self.choices,
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
        self.widget = combo_box = Combobox(tk_container, **kwargs)
        self._apply_ttk_style()
        if (callback := self._callback) is not None:
            combo_box.bind('<<ComboboxSelected>>', self.normalize_callback(callback))

    def pack_into(self, row: Row):
        self._init_widget(row.frame)
        self.pack_widget()
        if default := self.default:
            self.widget.set(default)

    def grid_into(self, parent: HasFrame, row: int, column: int, **kwargs):
        self._init_widget(parent.frame)
        self.grid_widget(row, column, **kwargs)
        if default := self.default:
            self.widget.set(default)

    def enable(self):
        if not self.disabled:
            return
        self.widget['state'] = 'readonly' if self.read_only else self._enabled_state
        self.disabled = False
        self.apply_style()


Dropdown = Combo


class ComboMap(Generic[T], Combo):
    def __init__(self, choices: Mapping[str, T], default: str = None, **kwargs):
        if kwargs.get('allow_any', False):
            raise TypeError(
                f'Unable to initialize {self.__class__.__name__} with allow_any=True - selections must match choices'
            )
        super().__init__(choices, default, **kwargs)
        self._choice_map = choices

    @property
    def value(self) -> T | None:
        choice = self.tk_var.get()
        try:
            return self._choice_map[choice]
        except (TypeError, KeyError):
            return None

    def update_choices(self, choices: Mapping[str, T], replace: Bool = False):
        self._choice_map = choice_map = choices if replace else {**self._choice_map, **choices}
        super().update_choices(choice_map, replace)


class ListBox(DisableableMixin, Interactive, base_style_layer='listbox'):
    widget: ScrollableListbox
    defaults: set[str]

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

    def select(self, value: str | int | Iterable[int] | None):
        if value is None:
            self.reset(False)
        elif isinstance(value, str):
            try:
                index = self.choices.index(value)
            except ValueError as e:
                raise ValueError(f'Invalid selection={value!r} - pick from choices={self.choices}') from e
            else:
                self.set_selection_indices(index)
        else:
            self.set_selection_indices(value)

    def update_choices(
        self, choices: Collection[str], replace: Bool = False, select: Bool = False, resize: Bool = True
    ):
        if replace and self.was_packed:
            self.widget.inner_widget.delete(0, len(self.choices))
        self._set_choices(choices if replace else (*self.choices, *choices), choices, select, resize)

    def _set_choices(
        self, values: Collection[str], new_values: Collection[str], select: Bool = False, resize: Bool = True
    ):
        self.choices = tuple(values)
        try:
            list_box = self.widget.inner_widget
        except AttributeError:  # Widget has not been initialized/packed yet
            return
        list_box.insert(tkc.END, *new_values)
        num_choices = len(self.choices)
        if select:
            for i in range(num_choices - len(new_values), num_choices):
                list_box.selection_set(i)
        if resize and num_choices != list_box.cget('height'):
            list_box.configure(height=num_choices)

    def append_choices(self, values: Collection[str], select: Bool = False, resize: Bool = True):
        self._set_choices((*self.choices, *values), values, select, resize)

    def append_choice(self, value: str, select: Bool = False, resize: Bool = True):
        self._set_choices((*self.choices, value), (value,), select, resize)

    def reset(self, default: Bool = True):
        try:
            list_box = self.widget.inner_widget
        except AttributeError:  # Widget has not been initialized/packed yet
            return
        if default and (defaults := self.defaults):
            for i, choice in enumerate(self.choices):
                if choice in defaults:
                    list_box.selection_set(i)
        else:
            list_box.selection_clear(0, len(self.choices))

    def update(
        self,
        selection: str | int | None = _NotSet,
        *,
        choices: Collection[str] = None,
        disabled: Bool = None,
        **kwargs,
    ):
        if choices is not None:
            self.update_choices(choices, **extract_kwargs(kwargs, {'replace', 'select', 'resize'}))
        if selection is not _NotSet:
            self.select(selection)
        if disabled is not None:
            self.toggle_enabled(disabled)

    # endregion

    @property
    def callback(self) -> BindTarget | None:
        return self._callback

    @callback.setter
    def callback(self, callback: BindTarget | None):
        if self.widget:
            self._callback = self.normalize_callback(callback)
        else:
            self._callback = callback

    @property
    def style_config(self) -> dict[str, Any]:
        style, state = self.style, self.style_state
        fg, bg = style.listbox.fg[state], style.listbox.bg[state]
        return {
            'highlightthickness': 0,
            'background': bg,
            'fg': fg,
            'selectbackground': fg,  # Intentionally using the inverse of fg/bg
            'selectforeground': bg,
            **style.get_map('listbox', state, font='font'),
            **style.get_map('listbox', 'disabled', disabledforeground='fg'),
            # **style.get_map('selected', state, font='font', selectbackground='bg', selectforeground='fg'),
            **self._style_config,
        }

    def _init_size(self) -> XY:
        try:
            width, height = self.size
        except TypeError:
            width = max_line_len(self.choices) + 1
            height = len(self.choices) or 3
        else:
            if width is None:
                width = max_line_len(self.choices) + 1
            if height is None:
                height = len(self.choices) or 3

        return width, height

    def _init_widget(self, tk_container: TkContainer):
        width, height = self._init_size()
        kwargs = {
            'exportselection': False,  # Prevent selections in this box from affecting others / the primary selection
            'selectmode': self.select_mode.value,
            'takefocus': int(self.allow_focus),
            'width': width,
            'height': height,
            **self.style_config,
        }
        """
        activestyle: Literal["dotbox", "none", "underline"]
        setgrid: bool
        """
        self.widget = outer = ScrollableListbox(tk_container, self.scroll_y, self.scroll_x, self.style, **kwargs)
        list_box = outer.inner_widget
        if choices := self.choices:
            list_box.insert(tkc.END, *choices)
            self.reset(default=True)

        list_box.bind('<<ListboxSelect>>', self._handle_selection_made)
        if (callback := self._callback) is not None:
            self._callback = self.normalize_callback(callback)

    def pack_into(self, row: Row):
        self._init_widget(row.frame)
        self.pack_widget()
        if self.disabled:
            # Note: This needs to occur after inserting any values, otherwise they do not appear.
            self.widget.inner_widget.configure(state='disabled')

    def grid_into(self, parent: HasFrame, row: int, column: int, **kwargs):
        self._init_widget(parent.frame)
        self.grid_widget(row, column, **kwargs)
        if self.disabled:
            # Note: This needs to occur after inserting any values, otherwise they do not appear.
            self.widget.inner_widget.configure(state='disabled')

    @cached_property
    def widgets(self) -> list[ScrollableListbox | TkListbox | TkFrame | Scrollbar]:
        return self.widget.widgets  # noqa
