"""
Exceptions related to TK GUI elements.
"""

from ..exceptions import TkGuiException

__all__ = [
    'ElementGroupError', 'NoActiveGroup', 'BadGroupCombo', 'MultilineContextError',
    'CallbackError', 'CallbackAlreadyRegistered', 'NoCallbackRegistered'
]


class ElementGroupError(TkGuiException):
    """Exceptions related to grouped Elements"""


class NoActiveGroup(ElementGroupError):
    """Exception raised when there is no active RadioGroup"""


class BadGroupCombo(ElementGroupError):
    """Exception raised when a bad combination of group members/choices are provided"""


class MultilineContextError(TkGuiException):
    """Raised when attempting to enter a Multiline element's context when it is already active."""


# region Callback Exceptions


class CallbackError(TkGuiException):
    """Base exception for callback-related errors."""


class CallbackAlreadyRegistered(CallbackError):
    """Exception raised when attempting to register a callback when one has already been registered."""


class NoCallbackRegistered(CallbackError):
    """Exception raised when a menu item was attempted to be used without having registered a callback target for it."""


# endregion
