"""
Gui options that can be used by a the GuiOptions parser
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, Collection, Iterator, Mapping, Type, TypeVar, Iterable, Callable

from tk_gui.caching import cached_property
from tk_gui.elements import Text, Element, Button, Input, BasicRowFrame
from tk_gui.elements.choices import Combo, ListBox, CheckBox
from tk_gui.popups.base import BasePopup
from tk_gui.popups import PickFolder
from .exceptions import SingleParsingError

if TYPE_CHECKING:
    from tkinter import Event
    from tk_gui.typing import TraceCallback, AnyEle, XY

__all__ = [
    'Opt', 'Option', 'BoolOption',
    'CheckboxOption', 'InputOption', 'DropdownOption', 'ListboxOption', 'SubmitOption',
    'PopupOption', 'PathOption', 'DirectoryOption',
]
log = logging.getLogger(__name__)

_NotSet = object()
COMMON_PARAMS = ('size', 'tooltip', 'pad', 'enable_events')
OptionTuples = Iterator[tuple[Optional[int], int, Element]]


class Option(ABC):
    opt_type: str = None
    _type_cls_map = {}

    name: str
    label: str
    disabled: bool
    required: bool

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
        label_size: XY = None,
        label_kw: dict[str, Any] = None,
        **kwargs
    ):
        self.name = name
        self.label = label
        self.default = default
        self.disabled = disabled
        self.required = required
        self.label_size = label_size
        self.label_kw = label_kw
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

    def validate(self, value):
        if isinstance(value, str):
            return value.strip()
        return value

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

    def _label_element(self) -> Text:
        if label_kwargs := self.label_kw:
            return Text(self.label, size=self.label_size, **label_kwargs)
        else:
            return Text(self.label, size=self.label_size)

    @abstractmethod
    def as_elements(self, disable_all: bool, change_cb: TraceCallback = None) -> Iterable[AnyEle]:
        raise NotImplementedError

    @property
    @abstractmethod
    def element_count(self) -> int:
        raise NotImplementedError

    def as_element(self, disable_all: bool, change_cb: TraceCallback = None) -> AnyEle | BasicRowFrame:
        if self.element_count == 1:
            return next(iter(self.as_elements(disable_all, change_cb)))
        return BasicRowFrame(list(self.as_elements(disable_all, change_cb)))


class CheckboxOption(Option, opt_type='checkbox'):
    element_count = 1

    def __init__(
        self, name: str, label: str, default: bool = False, *, disabled: bool = False, required: bool = False, **kwargs
    ):
        super().__init__(name, label, default, disabled=disabled, required=required, **kwargs)

    def as_elements(self, disable_all: bool, change_cb: TraceCallback = None) -> Iterator[CheckBox]:
        yield CheckBox(self.label, default=self.value, **self.common_kwargs(disable_all, change_cb))


class InputOption(Option, opt_type='input'):
    element_count = 2

    def __init__(
        self,
        name: str,
        label: str,
        default: Any = _NotSet,
        *,
        type: Callable = str,  # noqa
        disabled: bool = False,
        required: bool = False,
        **kwargs
    ):
        super().__init__(name, label, default, disabled=disabled, required=required, type=type, **kwargs)

    def as_elements(self, disable_all: bool, change_cb: TraceCallback = None) -> Iterator[Text | Input]:
        val = self.value
        yield self._label_element()
        yield Input('' if val is _NotSet else val, **self.common_kwargs(disable_all, change_cb))

    def validate(self, value):
        if isinstance(value, str):
            value = value.strip()
        if (type_func := self.kwargs['type']) is not str:
            try:
                return type_func(value)
            except Exception as e:
                raise SingleParsingError(
                    self.value_key, self, f'Error parsing {value=} for option={self.name!r}: {e}', value
                )


class DropdownOption(Option, opt_type='dropdown'):
    element_count = 2

    def __init__(
        self, name: str, label: str, default: Any = None, *, disabled: bool = False, required: bool = False, **kwargs
    ):
        super().__init__(name, label, default, disabled=disabled, required=required, **kwargs)

    def as_elements(self, disable_all: bool, change_cb: TraceCallback = None) -> Iterator[Text | Combo]:
        val = self.value
        yield self._label_element()
        yield Combo(self.kwargs['choices'], default=val, **self.common_kwargs(disable_all, change_cb))


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

    @property
    def element_count(self) -> int:
        return 3 if self.kwargs['extendable'] else 2

    def as_elements(self, disable_all: bool, change_cb: TraceCallback = None) -> Iterator[Text | ListBox | Button]:
        val = self.value
        yield self._label_element()
        kwargs = self.kwargs
        choices = kwargs['choices']
        yield ListBox(
            choices,
            default=val or choices,
            scroll_y=False,
            select_mode=kwargs['select_mode'],
            **self.common_kwargs(disable_all, change_cb),
        )
        if kwargs['extendable']:
            # TODO: This button needs to be handled here...
            yield Button('Add...', key=f'btn::{self.name}', disabled=disable_all or self.disabled)


class PopupOption(Option, opt_type='popup'):
    element_count = 3

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

    def as_elements(self, disable_all: bool, change_cb: TraceCallback = None) -> Iterator[Text | Input | Button]:
        val = self.value
        if val is _NotSet:
            val = None

        input_ele = Input('' if val is None else val, **self.common_kwargs(disable_all, change_cb))

        def update_value(event: Event):
            popup = self.popup_cls(**self.popup_kwargs)
            if (result := popup.run()) is not None:
                input_ele.update(result)

        yield self._label_element()
        yield input_ele
        # log.debug(f'Preparing popup button with text={self.button_text!r}')
        yield Button(self.button_text, cb=update_value)


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


class DirectoryOption(PathOption, opt_type='directory'):
    def __init__(
        self,
        name: str,
        label: str,
        popup_cls: Type[BasePopup] = PickFolder,
        button: str = 'Browse',
        default: Any = _NotSet,
        disabled: bool = False,
        must_exist: bool = False,
        **kwargs,
    ):
        super().__init__(name, label, popup_cls, button, default, disabled, must_exist, **kwargs)


class SubmitOption(Option, opt_type='button'):
    """Submit button that should be included when using GuiOptions as a popup"""
    element_count = 1

    def __init__(self, name: str = '__submit__', label: str = 'Submit', bind_enter: bool = False, **kwargs):
        super().__init__(name, label, **kwargs)
        self.bind_enter = bind_enter

    def common_kwargs(self, disable_all: bool, change_cb: TraceCallback = None) -> dict[str, Any]:
        kwargs = super().common_kwargs(disable_all, change_cb)
        kwargs['cb'] = kwargs.pop('change_cb')  # Button doesn't support change_cb
        return kwargs

    def as_elements(self, disable_all: bool, change_cb: TraceCallback = None) -> Iterator[Button]:
        yield Button(self.label, bind_enter=self.bind_enter, **self.common_kwargs(disable_all, change_cb))


Opt = TypeVar('Opt', bound=Option)
BoolOption = CheckboxOption
