"""
Tkinter GUI button elements

:author: Doug Skrypa
"""

from __future__ import annotations

import logging
import tkinter.constants as tkc
from enum import Enum
from math import ceil
from time import monotonic
from tkinter import Event, Button as _Button
from typing import TYPE_CHECKING, Union, Optional, Any

from PIL.ImageTk import PhotoImage

from tk_gui.enums import Justify, Anchor
from tk_gui.event_handling import BindMap, BindMapping, CustomEventResultsMixin
from tk_gui.images.wrapper import SourceImage, ResizedImage
from tk_gui.utils import Inheritable
from .element import Interactive
from .mixins import DisableableMixin

if TYPE_CHECKING:
    from PIL.Image import Image as PILImage
    from ..typing import XY, BindCallback, Bool, ImageType, Key, TkContainer

__all__ = ['Button', 'OK', 'Cancel', 'Yes', 'No', 'Submit', 'EventButton']
log = logging.getLogger(__name__)


class ButtonAction(Enum):
    SUBMIT = 'submit'
    CALLBACK = 'callback'
    BIND_EVENT = 'bind_event'

    @classmethod
    def _missing_(cls, value: str):
        try:
            return cls[value.upper()]
        except KeyError:
            return None


class Button(CustomEventResultsMixin, DisableableMixin, Interactive, base_style_layer='button'):
    widget: _Button
    justify: Justify = Inheritable('text_justification', type=Justify)
    separate: bool = False
    anchor_info: Anchor = Anchor.NONE
    bind_enter: bool = False
    callback: BindCallback = None
    _action: ButtonAction | None = None
    _src_image: SourceImage
    __image: ResizedImage | SourceImage

    def __init__(
        self,
        text: str = '',
        image: ImageType = None,
        *,
        shortcut: str = None,
        anchor_info: Union[str, Anchor] = None,
        justify: Union[str, Justify, None] = Justify.CENTER,
        action: Union[ButtonAction, str] = None,
        binds: BindMapping = None,
        bind_enter: Bool = False,
        cb: BindCallback = None,
        separate: Bool = False,
        focus: Bool = None,
        **kwargs,
    ):
        binds = BindMap.normalize(binds)
        if separate:
            self.separate = True
            binds.add('<ButtonPress-1>', self.handle_press)
            binds.add('<ButtonRelease-1>', self.handle_release)
        if shortcut:  # TODO: This does not activate (without focus?)
            if len(shortcut) == 1:
                shortcut = f'<{shortcut}>'
            if not shortcut.startswith('<') or not shortcut.endswith('>'):
                raise ValueError(f'Invalid keyboard {shortcut=}')
            binds.add(shortcut, self.handle_activated)
        if bind_enter:
            self.bind_enter = True
            binds.add('<Return>', self.handle_activated)
        if focus is None:
            focus = bind_enter
        super().__init__(binds=binds, focus=focus, **kwargs)
        self.text = text
        self.image = image
        self.justify = justify
        if cb is not None:
            self.callback = cb
        if action is not None:
            self.action = action
        if anchor_info:
            self.anchor_info = Anchor(anchor_info)
        self._last_press = 0
        self._last_release = 0
        self._last_activated = 0

    @property
    def image(self) -> Optional[PILImage]:
        return self.__image.pil_image

    @image.setter
    def image(self, value: ImageType):
        self.__image = self._src_image = src_image = SourceImage.from_image(value)
        if not (image := src_image.pil_image) or not self.size:
            return
        iw, ih = image.size
        width, height = self.size
        if ih > height or iw > width:
            self.__image = src_image.as_size((width - 1, height - 1))
        # if text := self.text:
        #     style = self.style
        #     state = self.style_state
        #     tw, th = style.text_size(text, layer='button', state=state)
        #     if th <= height and tw < width:

    @property
    def value(self) -> bool:
        return bool(self._last_activated)

    @property
    def action(self) -> ButtonAction:
        if (action := self._action) is not None:
            return action
        elif self.callback is not None:
            return ButtonAction.CALLBACK
        else:
            return ButtonAction.SUBMIT

    @action.setter
    def action(self, action: ButtonAction | str | None):
        if action is None:
            if self._action is not None:  # Avoid creating an instance attr if it wasn't already stored
                self._action = None
            return

        action = ButtonAction(action)
        if self.callback is not None and action != ButtonAction.CALLBACK:
            raise ValueError(
                f'Invalid {action=} - when a callback is provided, the only valid action is {ButtonAction.CALLBACK}'
            )
        else:
            self._action = action

    def update(self, text: str):
        self.widget.configure(text=text)
        self.text = text

    # region Packing

    def _pack_size(self) -> XY:
        # Width is measured in pixels, but height is measured in characters
        # TODO: Width may not be correct yet
        try:
            width, height = self.size
        except TypeError:
            width, height = 0, 0
        if width and height:
            return width, height

        text, image = self.text, self.image
        if not text and not image:
            return width, height

        style = self.style
        if text and image:
            lines = text.splitlines()
            if not width:
                # width = int(ceil(image.width / style.char_width())) + len(text)
                text_width = max(len(line) for line in lines) * style.char_width('button')
                width = text_width + image.width
            if not height:
                text_height = len(lines) * style.char_height('button')
                # This needs testing - I would have thought it would make more sense to use max(img, txt)
                height = int(ceil(image.height / text_height))
                # height = style.char_height() + image.height
        elif text:
            lines = text.splitlines()
            if not width:
                width = max(len(line) for line in lines) + 1
                # width = len(text) + 1
                # width = style.char_width() * len(text)
            if not height:
                height = len(lines)
                # height = style.char_height()
        else:
            if not width:
                # width = int(ceil(image.width / style.char_width()))
                width = image.width
            if not height:
                # height = 1
                height = image.height

        return width, height

    @property
    def style_config(self) -> dict[str, Any]:
        style, state = self.style, self.style_state
        config = {
            **style.get_map('button', state, bd='border_width', font='font', foreground='fg', background='bg'),
            **style.get_map('button', 'active', activeforeground='fg', activebackground='bg'),
            **style.get_map('button', 'highlight', highlightcolor='fg', highlightbackground='bg'),
            **self._style_config,
        }
        if style.button.border_width[state] == 0:
            config['relief'] = tkc.FLAT  # May not work on mac

        return config

    def _init_widget(self, tk_container: TkContainer):
        # self.string_var = StringVar()
        # self.string_var.set(self._value)
        width, height = self._pack_size()
        kwargs = {
            'width': width,
            'height': height,
            'anchor': self.anchor_info.value,
            'justify': self.justify.value,
            'takefocus': int(self.allow_focus),
            **self.style_config,
        }
        if not self.separate:
            kwargs['command'] = self.handle_activated
        if self.text:
            kwargs['text'] = self.text
        if image := self.image:
            kwargs['image'] = image = PhotoImage(image)
            kwargs['compound'] = tkc.CENTER
            kwargs['highlightthickness'] = 0
        elif not self.pad or 0 in self.pad:
            kwargs['highlightthickness'] = 0
        if width:
            kwargs['wraplength'] = width * self.style.char_width('button', self.style_state)
        if self.disabled:
            kwargs['state'] = self._disabled_state

        self.widget = button = _Button(tk_container, **kwargs)
        if image:
            button.image = image

    # endregion

    # region Event Handling

    def _bind(self, event_pat: str, cb: BindCallback, add: Bool = True):
        if self.bind_enter and event_pat == '<Return>' and self.window._maybe_bind_return_key(cb):
            return  # Skip bind on the button itself when it was bound on the window to avoid double activation
        super()._bind(event_pat, cb, add)

    def handle_press(self, event: Event):
        self._last_press = monotonic()
        # log.info(f'handle_press: {event=}')

    def handle_release(self, event: Event):
        self._last_release = monotonic()
        # log.info(f'handle_release: {event=}')
        self.handle_activated(event)

    def handle_activated(self, event: Event = None):
        if self.disabled:  # When enter is bound, for example, this may be called despite the fact it is disabled.
            return
        self._last_activated = monotonic()
        log.debug(f'handle_activated: {event=}')
        if (action := self.action) == ButtonAction.SUBMIT:
            self.window.interrupt(event, self)
        elif action == ButtonAction.BIND_EVENT:
            num = self.add_result(self)
            self.widget.event_generate('<<Custom:ButtonCallback>>', state=num)
        elif (cb := self.callback) is not None:
            result = cb(event)
            self.window._handle_callback_action(result, event, self)
        else:
            log.warning(f'No action configured for button={self}')

    # endregion


def OK(text: str = 'OK', bind_enter: Bool = True, **kwargs) -> Button:
    return Button(text, bind_enter=bind_enter, **kwargs)


def Cancel(text: str = 'Cancel', **kwargs) -> Button:
    return Button(text, **kwargs)


def Yes(text: str = 'Yes', bind_enter: Bool = True, **kwargs) -> Button:
    return Button(text, bind_enter=bind_enter, **kwargs)


def No(text: str = 'No', **kwargs) -> Button:
    return Button(text, **kwargs)


def Submit(text: str = 'Submit', bind_enter: Bool = True, **kwargs) -> Button:
    return Button(text, bind_enter=bind_enter, **kwargs)


def EventButton(text: str = '', image: ImageType = None, *, key: Key = None, **kwargs) -> Button:
    kwargs.setdefault('action', ButtonAction.BIND_EVENT)
    if text and not key:
        key = text
    return Button(text, image, key=key, **kwargs)
