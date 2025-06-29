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
from typing import TYPE_CHECKING, Any

from PIL.ImageTk import PhotoImage

from tk_gui.enums import Justify, Anchor, Compound
from tk_gui.event_handling import ENTER_KEYSYMS, BindMap, BindMapping, CustomEventResultsMixin
from tk_gui.images.wrapper import SourceImage, ResizedImage
from tk_gui.utils import Inheritable
from .element import Interactive
from .mixins import DisableableMixin

if TYPE_CHECKING:
    from PIL.Image import Image as PILImage
    from ..styles.style import Style
    from ..typing import XY, BindCallback, Bool, ImageType, Key, TkContainer, OptStr, IterStrs

__all__ = ['Button', 'OK', 'Cancel', 'Yes', 'No', 'Submit', 'EventButton']
log = logging.getLogger(__name__)

_NotSet = object()


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
    compound: Compound
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
        shortcut: OptStr = None,
        shortcuts: IterStrs = (),
        anchor_info: str | Anchor = None,
        justify: str | Justify | None = Justify.CENTER,
        compound: str | Compound | None = _NotSet,
        action: ButtonAction | str = None,
        binds: BindMapping = None,
        bind_enter: Bool = False,
        cb: BindCallback = None,
        separate: Bool = False,
        focus: Bool = None,
        **kwargs,
    ):
        binds = self._prepare_binds(binds, bind_enter, separate, shortcut=shortcut, shortcuts=shortcuts)
        super().__init__(binds=binds, focus=bind_enter if focus is None else focus, **kwargs)
        self.text = text
        self.image = image
        self.justify = justify
        if compound is _NotSet:
            self.compound = Compound.LEFT if text and image else Compound.CENTER
        else:
            self.compound = compound if isinstance(compound, Compound) else Compound(compound)
        if cb is not None:
            self.callback = cb
        if action is not None:
            self.action = action
        if anchor_info:
            self.anchor_info = Anchor(anchor_info)
        self._last_press = 0
        self._last_release = 0
        self._last_activated = 0

    def _prepare_binds(
        self, binds: BindMapping | None, bind_enter: Bool, separate: Bool, *, shortcut: OptStr, shortcuts: IterStrs,
    ) -> BindMap:
        binds = BindMap.normalize(binds)
        if separate:
            self.separate = True
            binds.add('<ButtonPress-1>', self.handle_press)
            binds.add('<ButtonRelease-1>', self.handle_release)

        if shortcut:  # TODO: This does not activate (without focus?)
            binds.add(_normalize_shortcut(shortcut), self.handle_activated)

        for shortcut in shortcuts:
            binds.add(_normalize_shortcut(shortcut), self.handle_activated)

        if bind_enter:
            self.bind_enter = True
            for key in ENTER_KEYSYMS:
                binds.add(key, self.handle_activated)

        return binds

    @property
    def image(self) -> PILImage | None:
        return self.__image.pil_image

    @image.setter
    def image(self, value: ImageType):
        self.__image = self._src_image = src_image = SourceImage.from_image(value)
        if not (image := src_image.pil_image) or not self.size:
            return
        iw, ih = image.size
        width, height = self.size
        if (ih > height or iw > width) and (height > 1 and width > 1):
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

    @property
    def style_config(self) -> dict[str, Any]:
        style, state = self.style, self.style_state
        style_cfg = {
            **style.get_map('button', state, bd='border_width', font='font', foreground='fg', background='bg'),
            **style.get_map('button', 'active', activeforeground='fg', activebackground='bg'),
            **style.get_map('button', 'highlight', highlightcolor='fg', highlightbackground='bg'),
            **self._style_config,
        }
        if style.button.border_width[state] == 0:
            style_cfg['relief'] = tkc.FLAT  # May not work on mac

        return style_cfg

    def _init_widget(self, tk_container: TkContainer):
        # self.string_var = StringVar()
        # self.string_var.set(self._value)
        width, height = PackSizeCalculator(self.text, self.image, self.size, self.style).get_pack_size()
        kwargs = {
            'width': width,
            'height': height,
            'anchor': self.anchor_info.value,
            'justify': self.justify.value,
            'takefocus': int(self.allow_focus),
            'compound': self.compound.value,
            **self.style_config,
        }
        if not self.separate:
            kwargs['command'] = self.handle_activated
        if self.text:
            kwargs['text'] = self.text
        if image := self.image:
            kwargs['image'] = image = PhotoImage(image)
            kwargs['highlightthickness'] = 0
        elif not self.pad or 0 in self.pad:
            kwargs['highlightthickness'] = 0
        if width:
            kwargs['wraplength'] = width * self.style.char_width('button', self.style_state)
        if self.disabled:
            kwargs['state'] = self._disabled_state

        # log.debug(f'Packing Button with {kwargs=}')
        self.widget = button = _Button(tk_container, **kwargs)
        if image:
            button.image = image

    # endregion

    # region Event Handling

    def _bind(self, event_pat: str, cb: BindCallback, add: Bool = True):
        if self.bind_enter and event_pat in ENTER_KEYSYMS and self.window._maybe_bind_return_key(cb):
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


class PackSizeCalculator:
    __slots__ = ('text', 'image', 'size', 'style')

    def __init__(self, text: str | None, image: PILImage | None, size: XY, style: Style):
        self.text = text
        self.image = image
        self.size = size
        self.style = style

    def get_pack_size(self) -> XY:
        # When only text is present, width is measured in pixels, but height is measured in characters
        # When a mix is present, height is measured in pixels
        try:
            width, height = self.size
        except TypeError:
            width, height = 0, 0

        if width and height:
            return width, height
        elif self.text:
            if self.image:
                return self._combo_pack_size(width, height)
            return self._text_pack_size(width, height)
        elif self.image:
            return self._image_pack_size(width, height)
        else:
            return width, height

    def _combo_pack_size(self, width: int | None, height: int | None) -> XY:
        lines = self.text.splitlines()
        if not width:
            # width = int(ceil(image.width / style.char_width())) + len(text)
            text_width = max(len(line) for line in lines) * self.style.char_width('button')
            width = text_width + self.image.width

        if not height:
            text_height = len(lines) * self.style.char_height('button')
            height = max(text_height, self.image.height)
            # height = int(ceil(self.image.height / text_height))  # On Windows, apparently this was needed instead?
            # log.debug(f'Combo button {text_height=}, image height={self.image.height} => {height=}')
            # height = style.char_height() + image.height

        return width, height

    def _text_pack_size(self, width: int | None, height: int | None) -> XY:
        lines = self.text.splitlines()
        if not width:
            width = max(len(line) for line in lines) + 1
            # width = len(text) + 1
            # width = style.char_width() * len(text)

        if not height:
            height = len(lines)
            # height = style.char_height()

        return width, height

    def _image_pack_size(self, width: int | None, height: int | None) -> XY:
        if not width:
            # width = int(ceil(image.width / style.char_width()))
            width = self.image.width

        if not height:
            # height = 1
            height = self.image.height

        return width, height


def _normalize_shortcut(shortcut: str) -> str:
    if len(shortcut) == 1:
        return f'<{shortcut}>'
    elif shortcut.startswith('<') and shortcut.endswith('>'):
        return shortcut
    raise ValueError(f'Invalid keyboard {shortcut=}')


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
