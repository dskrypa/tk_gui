"""
Gui option rendering and parsing

:author: Doug Skrypa
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Optional, Collection, Iterator, Mapping, Union, Type, ContextManager

from tk_gui.caching import cached_property
from .elements.choices import Combo, ListBox, CheckBox, make_checkbox_grid
from .elements import Text, Element, Button, Input, Submit, Frame
from .elements.text import normalize_text_ele_widths
from .popups.base import BasePopup
from .popups import PickFolder

if TYPE_CHECKING:
    from tkinter import Event
    from .typing import Key, TraceCallback, Layout, E

__all__ = [
    'GuiOptions',
    'GuiOptionError', 'NoSuchOptionError', 'SingleParsingError', 'RequiredOptionMissing', 'MultiParsingError',
]
log = logging.getLogger(__name__)

_NotSet = object()
COMMON_PARAMS = ('size', 'tooltip', 'pad', 'enable_events')
OptionTuples = Iterator[tuple[Optional[int], int, Element]]


# region Option Types


class Option(ABC):
    opt_type: str = None
    _type_cls_map = {}

    name: str
    label: str
    disabled: bool
    required: bool
    row: int
    col: int

    def __init_subclass__(cls, opt_type: str, **kwargs):  # noqa
        super().__init_subclass__(**kwargs)
        cls.opt_type = opt_type
        cls._type_cls_map[opt_type] = cls

    def __init__(
        self,
        name: str,
        label: str,
        default: Any = _NotSet,
        *,
        disabled: bool = False,
        required: bool = False,
        row: int = _NotSet,
        col: Optional[int] = _NotSet,
        **kwargs
    ):
        self.name = name
        self.label = label
        self.default = default
        self.disabled = disabled
        self.required = required
        self.row = row
        self.col = col
        self.kwargs = kwargs

    @classmethod
    def for_type(cls, opt_type: str):
        return cls._type_cls_map[opt_type]

    @property
    def value(self):
        return self.kwargs.get('value', self.default)

    @cached_property
    def value_key(self) -> str:
        return f'opt::{self.name}'

    def common_kwargs(self, disable_all: bool, change_cb: TraceCallback = None) -> dict[str, Any]:
        disabled = disable_all or self.disabled
        common = {'key': self.value_key, 'disabled': disabled, 'change_cb': change_cb}
        if kwargs := self.kwargs:
            if opt_kwargs := kwargs.get('kwargs'):
                common.update(opt_kwargs)
            for param in COMMON_PARAMS:
                try:
                    common[param] = kwargs[param]
                except KeyError:
                    pass
        return common

    @abstractmethod
    def prepare_layout(self, disable_all: bool, change_cb: TraceCallback = None) -> OptionTuples:
        raise NotImplementedError

    def validate(self, value):
        if isinstance(value, str):
            return value.strip()
        return value


class CheckboxOption(Option, opt_type='checkbox'):
    def prepare_layout(self, disable_all: bool, change_cb: TraceCallback = None) -> OptionTuples:
        yield self.col, self.row, CheckBox(self.label, default=self.value, **self.common_kwargs(disable_all, change_cb))


class InputOption(Option, opt_type='input'):
    def prepare_layout(self, disable_all: bool, change_cb: TraceCallback = None) -> OptionTuples:
        col_num, row_num, val = self.col, self.row, self.value
        yield col_num, row_num, Text(self.label, key=f'lbl::{self.name}')
        yield col_num, row_num, Input('' if val is _NotSet else val, **self.common_kwargs(disable_all, change_cb))

    def validate(self, value):
        if isinstance(value, str):
            value = value.strip()
        if (type_func := self.kwargs['type']) is not str:
            try:
                return type_func(value)
            except Exception as e:
                raise SingleParsingError(
                    self.value_key, self, f'Error parsing {value=!r} for option={self.name!r}: {e}', value
                )


class DropdownOption(Option, opt_type='dropdown'):
    def prepare_layout(self, disable_all: bool, change_cb: TraceCallback = None) -> OptionTuples:
        col_num, row_num, val = self.col, self.row, self.value
        yield col_num, row_num, Text(self.label, key=f'lbl::{self.name}')
        yield col_num, row_num, Combo(
            self.kwargs['choices'], default_value=val, **self.common_kwargs(disable_all, change_cb)
        )


class ListboxOption(Option, opt_type='listbox'):
    def __init__(
        self,
        name: str,
        label: str,
        choices: Collection[str],
        default: Any = _NotSet,
        *,
        size: tuple[int, int] = None,
        select_mode: str = 'extended',
        extendable: bool = False,
        **kwargs,
    ):
        try:
            size = size or (max(map(len, choices)) + 3, len(choices))
        except ValueError:  # max() arg is an empty sequence
            size = (15, 1)
        super().__init__(
            name,
            label,
            choices if default is _NotSet else default,
            size=size,
            select_mode=select_mode,
            choices=choices,
            extendable=extendable,
            **kwargs
        )

    def common_kwargs(self, disable_all: bool, change_cb: TraceCallback = None) -> dict[str, Any]:
        kwargs = super().common_kwargs(disable_all, change_cb)
        kwargs['callback'] = kwargs.pop('change_cb')  # ListBox is the only one that doesn't support change_cb
        return kwargs

    def prepare_layout(self, disable_all: bool, change_cb: TraceCallback = None) -> OptionTuples:
        col_num, row_num, val = self.col, self.row, self.value
        yield col_num, row_num, Text(self.label, key=f'lbl::{self.name}')
        kwargs = self.kwargs
        choices = kwargs['choices']
        yield col_num, row_num, ListBox(
            choices,
            default=val or choices,
            # scroll_y=False,
            select_mode=kwargs['select_mode'],
            **self.common_kwargs(disable_all, change_cb),
        )
        if kwargs['extendable']:
            yield col_num, row_num, Button('Add...', key=f'btn::{self.name}', disabled=disable_all or self.disabled)


class PopupOption(Option, opt_type='popup'):
    def __init__(
        self,
        name: str,
        label: str,
        popup_cls: Type[BasePopup],
        button: str = 'Choose...',
        default: Any = _NotSet,
        popup_kwargs: Mapping[str, Any] = None,
        disabled: bool = True,
        **kwargs,
    ):
        super().__init__(name, label, default, disabled=disabled, **kwargs)
        self.popup_cls = popup_cls
        self.popup_kwargs = popup_kwargs or {}
        self.button_text = button

    def prepare_layout(self, disable_all: bool, change_cb: TraceCallback = None) -> OptionTuples:
        col_num, row_num, val = self.col, self.row, self.value
        if val is _NotSet:
            val = None

        yield col_num, row_num, Text(self.label, key=f'lbl::{self.name}')

        input_ele = Input('' if val is None else val, **self.common_kwargs(disable_all, change_cb))
        yield col_num, row_num, input_ele

        def update_value(event: Event):
            popup = self.popup_cls(**self.popup_kwargs)
            if (result := popup.run()) is not None:
                input_ele.update(result)

        log.debug(f'Preparing popup button with text={self.button_text!r}')
        yield col_num, row_num, Button(self.button_text, cb=update_value)


class PathOption(PopupOption, opt_type='path'):
    def __init__(
        self,
        name: str,
        label: str,
        popup_cls: Type[BasePopup],
        button: str = 'Browse',
        default: Any = _NotSet,
        disabled: bool = False,
        must_exist: bool = False,
        **kwargs,
    ):
        super().__init__(name, label, default=default, popup_cls=popup_cls, button=button, disabled=disabled, **kwargs)
        self.must_exist = must_exist
        try:
            self.popup_kwargs.setdefault('initial_dir', self.value)
        except AttributeError:
            pass

    @property
    def value(self) -> str | None:
        val = self.kwargs.get('value', self.default)
        if isinstance(val, Path):
            return val.as_posix()
        elif val is _NotSet:
            return None
        else:
            return val

    def validate(self, value) -> str:
        if isinstance(value, str):
            value = value.strip()
        path = Path(value)
        if self.popup_cls is PickFolder:
            if (self.must_exist and not path.is_dir()) or (path.exists() and not path.is_dir()):
                raise SingleParsingError(
                    self.value_key, self, f'Invalid {path=} for option={self.name!r} (not a directory)', path
                )
        elif self.must_exist and not path.is_file():
            raise SingleParsingError(
                self.value_key, self, f'Invalid {path=} for option={self.name!r} (not a file)', path
            )
        return path.as_posix()


# endregion


class GuiOptions:
    options: dict[str, Option]

    def __init__(
        self,
        submit: Optional[str] = 'Submit',
        disable_on_parsed: bool = False,
        align_text: bool = True,
        align_checkboxes: bool = True,
        title: Optional[str] = 'options'
    ):
        self.options = {}
        self.parsed = False
        self.disable_on_parsed = disable_on_parsed
        self.submit_text = submit
        self.align_text = align_text
        self.align_checkboxes = align_checkboxes
        self.title = title
        self._rows_per_column = {}
        self._max_row = -1
        self._default_row = 0
        self._default_col = 0

    def __getitem__(self, name: str):
        try:
            option = self.options[name]
        except KeyError:
            raise NoSuchOptionError(f'Invalid option={name!r}') from None
        try:
            return option.kwargs['value']
        except KeyError:
            default = option.default
            if default is not _NotSet:
                return default
            raise

    def __setitem__(self, name: str, value: Any):
        try:
            option = self.options[name]
        except KeyError:
            raise NoSuchOptionError(f'Invalid option={name!r}') from None
        # option['value'] = value
        option.kwargs['value'] = value

    def get(self, name: str, default=_NotSet):
        try:
            return self[name]
        except KeyError:
            if default is _NotSet:
                raise KeyError(f'No value or default has been provided for option={name!r}') from None
            return default

    def update(self, options: Optional[Mapping[str, Any]]):
        """Update the selected options based on previous input"""
        if options is None:
            return
        for key, val in options.items():
            try:
                self[key] = val
            except NoSuchOptionError:
                pass

    def items(self) -> Iterator[tuple[str, Any]]:
        for name in self.options:
            try:
                yield name, self[name]
            except KeyError:
                pass

    # region Add Option Methods

    def _update_row_and_col(self, kwargs: dict[str, Any]):
        row = kwargs.setdefault('row', self._default_row)
        col = kwargs.setdefault('col', self._default_col)
        col_rows = self._rows_per_column.get(col, 0)
        self._rows_per_column[col] = max(col_rows, row + 1)
        self._max_row = max(self._max_row, row)

    def add_bool(self, option: str, label: str, default: bool = False, **kwargs):
        self._update_row_and_col(kwargs)
        self.options[option] = CheckboxOption(option, label, default, **kwargs)

    def add_input(self, option: str, label: str, default: Any = _NotSet, *, type: Callable = str, **kwargs):  # noqa
        self._update_row_and_col(kwargs)
        self.options[option] = InputOption(option, label, default, type=type, **kwargs)

    def add_dropdown(self, option: str, label: str, choices: Collection[str], default: Any = None, **kwargs):
        self._update_row_and_col(kwargs)
        self.options[option] = DropdownOption(option, label, default, choices=choices, **kwargs)

    def add_listbox(
        self,
        option: str,
        label: str,
        choices: Collection[str],
        default: Any = _NotSet,
        *,
        size: tuple[int, int] = None,
        select_mode: str = 'extended',
        extendable: bool = False,
        **kwargs
    ):
        self._update_row_and_col(kwargs)
        self.options[option] = ListboxOption(
            option, label, choices, default, size=size, select_mode=select_mode, extendable=extendable, **kwargs
        )

    def _add_path(
        self,
        option: str,
        label: str,
        popup_cls: Type[BasePopup],
        default: Union[Path, str] = _NotSet,
        *,
        must_exist: bool = False,
        **kwargs
    ):
        self._update_row_and_col(kwargs)
        self.options[option] = PathOption(option, label, popup_cls, default=default, must_exist=must_exist, **kwargs)

    def add_directory(
        self, option: str, label: str, default: Union[Path, str] = _NotSet, *, must_exist: bool = False, **kwargs
    ):
        self._add_path(option, label, PickFolder, default, must_exist=must_exist, **kwargs)

    def add_popup(
        self,
        option: str,
        label: str,
        popup_cls: Type[BasePopup],
        button: str = 'Choose...',
        default: Any = _NotSet,
        popup_kwargs: Mapping[str, Any] = None,
        **kwargs,
    ):
        self._update_row_and_col(kwargs)
        self.options[option] = PopupOption(
            option, label, popup_cls, default=default, button=button, popup_kwargs=popup_kwargs, **kwargs
        )

    # endregion

    # region Render Methods

    def _generate_layout(self, disable_all: bool, change_cb: TraceCallback = None) -> OptionTuples:
        for name, opt in self.options.items():
            yield from opt.prepare_layout(disable_all, change_cb)

    def _pack(self, layout: list[list[E]], columns: list[Layout]) -> list[list[E]]:
        if self.align_text or self.align_checkboxes:
            if columns:
                row_sets = [layout + columns[0], columns[1:]] if len(columns) > 1 else [layout + columns[0]] # noqa
            else:
                row_sets = [layout]

            for row_set in row_sets:
                if self.align_text and (rows_with_text := [r for r in row_set if r and isinstance(r[0], Text)]):
                    normalize_text_ele_widths(rows_with_text)  # noqa
                if self.align_checkboxes:
                    if box_rows := [r for r in row_set if r and all(isinstance(e, CheckBox) for e in r)]:
                        log.info(f'Processing checkboxes into grid: {box_rows}')
                        make_checkbox_grid(box_rows)  # noqa

        if not layout and len(columns) == 1:
            layout = columns[0]
        else:
            column_objects = [
                Frame(column, key=f'col::options::{i}', pad=(0, 0), expand_x=True) for i, column in enumerate(columns)
            ]
            layout.append(column_objects)

        return layout

    def layout(
        self, submit_key: str = None, disable_all: bool = None, submit_row: int = None, change_cb: TraceCallback = None
    ) -> Layout:
        if disable_all is None:
            disable_all = self.disable_on_parsed and self.parsed
        log.debug(f'Building option layout with {self.parsed=!r} {submit_key=!r} {disable_all=!r}')

        rows_per_column = sorted(((col, val) for col, val in self._rows_per_column.items() if col is not None))
        layout = [[] for _ in range(none_cols)] if (none_cols := self._rows_per_column.get(None)) else []
        columns = [[[] for _ in range(r)] for c, r in rows_per_column]
        for col_num, row_num, ele in self._generate_layout(disable_all, change_cb):
            if col_num is None:
                layout[row_num].append(ele)
            else:
                columns[col_num][row_num].append(ele)

        layout = self._pack(layout, columns)

        if self.submit_text:
            submit_ele = Submit(self.submit_text, disabled=disable_all, key=submit_key or self.submit_text)
            if submit_row is None:
                layout.append([submit_ele])
            else:
                while len(layout) < (submit_row + 1):
                    layout.append([])
                layout[submit_row].append(submit_ele)

        return layout

    def as_frame(
        self,
        submit_key: str = None,
        disable_all: bool = None,
        submit_row: int = None,
        change_cb: TraceCallback = None,
        **kwargs,
    ) -> Frame:
        return Frame(self.layout(submit_key, disable_all, submit_row, change_cb), title=self.title, **kwargs)

    # endregion

    def parse(self, data: dict[Key, Any]) -> dict[str, Any]:
        errors = []
        parsed = {}
        defaults = []
        for name, opt in self.options.items():
            val_key = opt.value_key
            try:
                val = data[val_key]
            except KeyError:
                if opt.required:
                    errors.append(RequiredOptionMissing(val_key, opt))
                elif opt.default is _NotSet:
                    pass
                else:
                    defaults.append(name)
            else:
                try:
                    parsed[name] = opt.validate(val)
                except SingleParsingError as e:
                    errors.append(e)

        for name, val in parsed.items():
            self.options[name].kwargs['value'] = parsed[name]  # Save the value even if an exception will be raised

        self.parsed = True
        if errors:
            raise errors[0] if len(errors) == 1 else MultiParsingError(errors)

        for name in defaults:
            parsed[name] = self.options[name].default

        return parsed

    @contextmanager
    def column(self, col: Optional[int]) -> ContextManager[GuiOptions]:
        old = self._default_col
        self._default_col = col
        try:
            yield self
        finally:
            self._default_col = old

    @contextmanager
    def row(self, row: int) -> ContextManager[GuiOptions]:
        old = self._default_row
        self._default_row = row
        try:
            yield self
        finally:
            self._default_row = old

    @contextmanager
    def next_row(self) -> ContextManager[GuiOptions]:
        old = self._default_row
        self._default_row = self._max_row + 1
        try:
            yield self
        finally:
            self._default_row = old

    @contextmanager
    def column_and_row(self, col: Optional[int], row: int) -> ContextManager[GuiOptions]:
        old_col, old_row = self._default_col, self._default_row
        self._default_col = col
        self._default_row = row
        try:
            yield self
        finally:
            self._default_col = old_col
            self._default_row = old_row

    def run_popup(self, **kwargs):
        from .views.options import GuiOptionsView

        return GuiOptionsView(self, **kwargs).run()


class GuiOptionError(Exception):
    """Base exception for parsing exceptions"""


class NoSuchOptionError(GuiOptionError):
    """Exception to be raised when attempting to access/set an option that does not exist"""


class SingleParsingError(GuiOptionError):
    def __init__(self, key: str, option: Option, message: str = None, value: Any = None):
        self.key = key
        self.option = option
        self.message = message
        self.value = value

    def __str__(self) -> str:
        return self.message


class RequiredOptionMissing(SingleParsingError):
    def __str__(self) -> str:
        return f'Missing value for required option={self.option.name}'


class MultiParsingError(GuiOptionError):
    def __init__(self, errors: list[SingleParsingError]):
        self.errors = errors

    def __str__(self) -> str:
        return '\n'.join(map(str, self.errors))
