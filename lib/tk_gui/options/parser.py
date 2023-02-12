"""
Gui option rendering and parsing

:author: Doug Skrypa
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Optional, Collection, Iterator, Mapping, Union, Type, Iterable

from tk_gui.popups.base import BasePopup
from tk_gui.popups import PickFolder
from .exceptions import RequiredOptionMissing, MultiParsingError, SingleParsingError, NoSuchOptionError
from .options import CheckboxOption, InputOption, DropdownOption, ListboxOption, PopupOption, PathOption, Opt, _NotSet
from .layout import OldOptionLayout, OptionLayout, OptionComponent

if TYPE_CHECKING:
    from tk_gui.elements import InteractiveFrame
    from tk_gui.typing import Key, TraceCallback, Layout

__all__ = ['GuiOptions', 'OldGuiOptions']
log = logging.getLogger(__name__)


class GuiOptionsBase(ABC):
    options: dict[str, Opt]

    def __init__(self, title: Optional[str] = 'options', disable_on_parsed: bool = False):
        self.options = {}
        self.parsed = False
        self.title = title
        self.disable_on_parsed = disable_on_parsed

    # region Mapping / Parsed Value Methods

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

    def _should_disable_all(self, disable_all: bool = None) -> bool:
        if disable_all is None:
            disable_all = self.disable_on_parsed and self.parsed
        return disable_all

    @abstractmethod
    def get_layout(self, disable_all: bool = None, change_cb: TraceCallback = None) -> Layout:
        raise NotImplementedError

    def run_popup(self, **kwargs):
        from tk_gui.views.options import GuiOptionsView

        return GuiOptionsView(self, **kwargs).run()


class GuiOptions(GuiOptionsBase):
    def __init__(
        self,
        options: Iterable[Iterable[OptionComponent]],
        title: Optional[str] = 'options',
        disable_on_parsed: bool = False,
    ):
        super().__init__(title, disable_on_parsed)
        self.layout = OptionLayout(options)
        for option in self.layout.options():
            self.options[option.name] = option

    # region Render Methods

    def get_layout(self, disable_all: bool = None, change_cb: TraceCallback = None) -> Layout:
        disable_all = self._should_disable_all(disable_all)
        log.debug(f'Building option layout with {self.parsed=!r} {disable_all=!r}')
        yield from self.layout.layout(disable_all, change_cb)

    def as_frame(self, disable_all: bool = None, change_cb: TraceCallback = None, **kwargs) -> InteractiveFrame:
        disable_all = self._should_disable_all(disable_all)
        log.debug(f'Building option layout with {self.parsed=!r} {disable_all=!r}')
        return self.layout.as_frame(disable_all, change_cb, title=self.title, **kwargs)

    # endregion


class OldGuiOptions(GuiOptionsBase):
    def __init__(
        self,
        submit: Optional[str] = 'Submit',
        disable_on_parsed: bool = False,
        align_text: bool = True,
        align_checkboxes: bool = True,
        title: Optional[str] = 'options'
    ):
        super().__init__(title, disable_on_parsed)
        self.submit_text = submit
        self.layout = OldOptionLayout(align_text=align_text, align_checkboxes=align_checkboxes)

    # region Add Option Methods

    def add_bool(self, option: str, label: str, default: bool = False, **kwargs):
        self.options[option] = self.layout.add_option(CheckboxOption(option, label, default, **kwargs))

    def add_input(self, option: str, label: str, default: Any = _NotSet, *, type: Callable = str, **kwargs):  # noqa
        self.options[option] = self.layout.add_option(InputOption(option, label, default, type=type, **kwargs))

    def add_dropdown(self, option: str, label: str, choices: Collection[str], default: Any = None, **kwargs):
        self.options[option] = self.layout.add_option(
            DropdownOption(option, label, default, choices=choices, **kwargs)
        )

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
        self.options[option] = self.layout.add_option(
            ListboxOption(
                option, label, choices, default, size=size, select_mode=select_mode, extendable=extendable, **kwargs
            )
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
        self.options[option] = self.layout.add_option(
            PathOption(option, label, popup_cls, default=default, must_exist=must_exist, **kwargs)
        )

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
        self.options[option] = self.layout.add_option(
            PopupOption(option, label, popup_cls, default=default, button=button, popup_kwargs=popup_kwargs, **kwargs)
        )

    # endregion

    # region Render Methods

    def get_layout(
        self, submit_key: str = None, disable_all: bool = None, submit_row: int = None, change_cb: TraceCallback = None
    ) -> Layout:
        disable_all = self._should_disable_all(disable_all)
        log.debug(f'Building option layout with {self.parsed=!r} {submit_key=!r} {disable_all=!r}')
        yield from self.layout.layout(self.submit_text, submit_key, disable_all, submit_row, change_cb)

    def as_frame(
        self,
        submit_key: str = None,
        disable_all: bool = None,
        submit_row: int = None,
        change_cb: TraceCallback = None,
        **kwargs,
    ) -> InteractiveFrame:
        disable_all = self._should_disable_all(disable_all)
        log.debug(f'Building option layout with {self.parsed=!r} {submit_key=!r} {disable_all=!r}')
        return self.layout.as_frame(
            self.submit_text, submit_key, disable_all, submit_row, change_cb, title=self.title, **kwargs
        )

    # endregion
