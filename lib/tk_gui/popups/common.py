"""
Tkinter GUI popups: common popups

:author: Doug Skrypa
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from ..elements.buttons import OK
from ..images.utils import icon_path
from .base import BasicPopup
from .basic_prompts import BoolPopup, TextPromptPopup, LoginPromptPopup, PasswordPromptPopup

if TYPE_CHECKING:
    from ..typing import Bool, TkSide

__all__ = [
    'popup_ok', 'popup_error', 'popup_warning', 'popup_input_invalid',
    'popup_yes_no', 'popup_no_yes', 'popup_ok_cancel', 'popup_cancel_ok',
    'popup_get_text', 'popup_login', 'popup_get_password',
]
log = logging.getLogger(__name__)


def popup_ok(text: str, title: str = None, bind_esc: Bool = True, side: TkSide = 'right', **kwargs) -> None:
    BasicPopup(text, title=title, bind_esc=bind_esc, button=OK(side=side), **kwargs).run()


def popup_error(text: str, title: str = 'Error', bind_esc: Bool = True, side: TkSide = 'right', **kwargs) -> None:
    BasicPopup(text, title=title, bind_esc=bind_esc, button=OK(side=side), **kwargs).run()


def popup_warning(text: str, title: str = 'Warning', bind_esc: Bool = True, side: TkSide = 'right', **kwargs) -> None:
    img_path = icon_path('exclamation-triangle-yellow.png')
    BasicPopup(text, title=title, bind_esc=bind_esc, image=img_path, button=OK(side=side), **kwargs).run()


def popup_yes_no(text: str, title: str = None, bind_esc: Bool = False, **kwargs) -> Optional[bool]:
    return BoolPopup(text, 'Yes', 'No', 'TF', title=title, bind_esc=bind_esc, **kwargs).run()


def popup_no_yes(text: str, title: str = None, bind_esc: Bool = False, **kwargs) -> Optional[bool]:
    return BoolPopup(text, 'Yes', 'No', 'FT', title=title, bind_esc=bind_esc, **kwargs).run()


def popup_ok_cancel(text: str, title: str = None, bind_esc: Bool = False, **kwargs) -> Optional[bool]:
    return BoolPopup(text, 'OK', 'Cancel', 'TF', title=title, bind_esc=bind_esc, **kwargs).run()


def popup_cancel_ok(text: str, title: str = None, bind_esc: Bool = False, **kwargs) -> Optional[bool]:
    return BoolPopup(text, 'OK', 'Cancel', 'FT', title=title, bind_esc=bind_esc, **kwargs).run()


def popup_input_invalid(text: str = None, title: str = 'Invalid Input', logger: logging.Logger = None, **kwargs):
    if logger is None:
        logger = log
    logger.debug(f'Received invalid input - {text}' if text else 'Received invalid input')
    popup_ok(text, title=title, **kwargs)


def popup_get_text(
    text: str,
    title: str = None,
    *,
    bind_esc: Bool = False,
    button_text: str = 'Submit',
    cancel_text: str = None,
    **kwargs,
) -> Optional[str]:
    """A popup with a prompt and a text input field."""
    popup = TextPromptPopup(
        text, title=title, bind_esc=bind_esc, button_text=button_text, cancel_text=cancel_text, **kwargs
    )
    return popup.run()


def popup_login(
    text: str,
    title: str = None,
    *,
    bind_esc: Bool = False,
    button_text: str = 'Submit',
    cancel_text: str = None,
    **kwargs,
) -> tuple[Optional[str], Optional[str]]:
    """A popup with a prompt and user name / password input fields."""
    popup = LoginPromptPopup(
        text, title=title, bind_esc=bind_esc, button_text=button_text, cancel_text=cancel_text, **kwargs
    )
    return popup.run()


def popup_get_password(
    text: str,
    title: str = None,
    *,
    bind_esc: Bool = False,
    button_text: str = 'Submit',
    cancel_text: str = None,
    **kwargs,
) -> Optional[str]:
    """A popup with a prompt and a password input field."""
    popup = PasswordPromptPopup(
        text, title=title, bind_esc=bind_esc, button_text=button_text, cancel_text=cancel_text, **kwargs
    )
    return popup.run()
