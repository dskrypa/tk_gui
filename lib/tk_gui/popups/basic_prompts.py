"""
Tkinter GUI popups: basic prompts

:author: Doug Skrypa
"""

from __future__ import annotations

import logging
from typing import Optional, Literal

from ..elements import Button, Text, Input
from .base import BasicPopup

__all__ = ['BoolPopup', 'TextPromptPopup', 'LoginPromptPopup', 'PasswordPromptPopup']
log = logging.getLogger(__name__)


class BoolPopup(BasicPopup):
    def __init__(
        self,
        text: str,
        true: str = 'OK',
        false: str = 'Cancel',
        order: Literal['TF', 'FT'] = 'FT',
        select: Optional[bool] = True,
        **kwargs,
    ):
        self.true_key = true
        self.false_key = false
        tf = order.upper() == 'TF'
        tside, fside = ('left', 'right') if tf else ('right', 'left')
        te, fe = (True, False) if select else (False, True) if select is False else (False, False)
        tb = Button(true, key=true, side=tside, bind_enter=te)
        fb = Button(false, key=false, side=fside, bind_enter=fe)
        buttons = (tb, fb) if tf else (fb, tb)
        super().__init__(text, buttons=buttons, **kwargs)

    def get_results(self) -> Optional[bool]:
        results = super().get_results()
        if results[self.true_key]:
            return True
        elif results[self.false_key]:
            return False
        return None  # exited without clicking either button


class SubmitOrCancelPopup(BasicPopup):
    submit_key = 'submit'

    def __init__(self, text: str, button_text: str = 'Submit', cancel_text: str = None, **kwargs):
        submit = Button(button_text, key=self.submit_key, bind_enter=True, focus=False, side='right')
        if cancel_text:
            # The order here is counter-intuitive - Submit will be to the left of Cancel because when both have
            # side=right, they are packed right-to-left, where earlier elements end up further right.
            buttons = (Button(cancel_text, side='right'), submit)
        else:
            buttons = (submit,)
        super().__init__(text, buttons=buttons, **kwargs)


class TextPromptPopup(SubmitOrCancelPopup):
    input_key = 'input'

    def get_pre_window_layout(self):
        yield from self.prepare_text()
        yield [Input(key=self.input_key, focus=True)]
        yield self.prepare_buttons()

    def get_results(self) -> Optional[str]:
        results = super().get_results()
        if results[self.submit_key]:
            return results[self.input_key]
        else:
            return None


class LoginPromptPopup(SubmitOrCancelPopup, title='Login'):
    user_key = 'username'
    pw_key = 'password'

    def __init__(
        self, text: str, button_text: str = 'Submit', password_char: str = '\u2b24', cancel_text: str = None, **kwargs
    ):
        super().__init__(text, button_text=button_text, cancel_text=cancel_text, **kwargs)
        self.password_char = password_char

    def get_pre_window_layout(self):
        yield from self.prepare_text()
        yield [Text('Username:'), Input(key=self.user_key, focus=True)]
        yield [Text('Password:'), Input(key=self.pw_key, password_char=self.password_char)]
        yield self.prepare_buttons()

    def get_results(self) -> tuple[Optional[str], Optional[str]]:
        results = super().get_results()
        if results[self.submit_key]:
            return results[self.user_key], results[self.pw_key]
        else:
            return None, None


class PasswordPromptPopup(SubmitOrCancelPopup, title='Password'):
    pw_key = 'password'

    def __init__(
        self, text: str, button_text: str = 'Submit', password_char: str = '\u2b24', cancel_text: str = None, **kwargs
    ):
        super().__init__(text, button_text=button_text, cancel_text=cancel_text, **kwargs)
        self.password_char = password_char

    def get_pre_window_layout(self):
        yield from self.prepare_text()
        yield [Text('Password:'), Input(key=self.pw_key, password_char=self.password_char, focus=True)]
        yield self.prepare_buttons()

    def get_results(self) -> Optional[str]:
        results = super().get_results()
        if results[self.submit_key]:
            return results[self.pw_key]
        else:
            return None
