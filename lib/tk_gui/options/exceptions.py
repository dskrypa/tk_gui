"""
Exceptions for gui option rendering and parsing
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .options import Option

__all__ = ['GuiOptionError', 'NoSuchOptionError', 'SingleParsingError', 'RequiredOptionMissing', 'MultiParsingError']


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
