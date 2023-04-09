"""
Tkinter GUI Exceptions

:author: Doug Skrypa
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from .elements import Element
    from .typing import Key, HasValue
    from .window import Window

__all__ = ['TkGuiException', 'DuplicateKeyError', 'WindowClosed']


class TkGuiException(Exception):
    """Base exception for errors in Tkinter GUI"""


class DuplicateKeyError(TkGuiException):
    """Raised when a duplicate key is used for an Element"""

    def __init__(self, key: Key, old: Union[Element, HasValue], new: Union[Element, HasValue], window: Window):
        self.key = key
        self.old = old
        self.new = new
        self.window = window

    def __str__(self) -> str:
        key, window, new, old = self.key, self.window, self.new, self.old
        return f'Invalid {key=} for element={new!r} in {window=} - it is already associated with element={old!r}'


class WindowClosed(TkGuiException):
    """Raised when an action could not be completed because the window was closed."""
