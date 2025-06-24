"""
Gui option rendering and parsing

:author: Doug Skrypa
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Optional, Iterator, Mapping, Iterable

from .exceptions import RequiredOptionMissing, MultiParsingError, SingleParsingError, NoSuchOptionError
from .options import Opt, _NotSet
from .layout import OptionLayout, OptionComponent

if TYPE_CHECKING:
    from tk_gui.elements import InteractiveFrame
    from tk_gui.typing import Key, TraceCallback, Layout

__all__ = ['GuiOptions']
log = logging.getLogger(__name__)


class GuiOptions:
    options: dict[str, Opt]

    def __init__(
        self,
        options: Iterable[Iterable[OptionComponent]],
        title: Optional[str] = 'options',
        disable_on_parsed: bool = False,
    ):
        self.layout = OptionLayout(options)
        self.options = {option.name: option for option in self.layout.options()}
        self.options.pop('__submit__', None)
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

    def update(self, options: Mapping[str, Any] | GuiOptions | None):
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
        # log.debug(f'Parsing GUI options from {data=}')
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
        # TODO: Respect disable_on_parsed
        if errors:
            raise errors[0] if len(errors) == 1 else MultiParsingError(errors)

        for name in defaults:
            parsed[name] = self.options[name].default

        # log.debug(f'Parsed GUI options: {parsed}')
        return parsed

    def _should_disable_all(self, disable_all: bool = None) -> bool:
        if disable_all is None:
            disable_all = self.disable_on_parsed and self.parsed
        return disable_all

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

    def run_popup(self, **kwargs) -> dict[str, Any]:
        from tk_gui.views.options import GuiOptionsView

        return GuiOptionsView(self, **kwargs).run()
