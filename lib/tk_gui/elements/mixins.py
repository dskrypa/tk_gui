"""

"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Callable

if TYPE_CHECKING:
    from tkinter import Widget, Button, Checkbutton, Menu, Radiobutton, Scale, Scrollbar, Text, OptionMenu, Spinbox
    from tk_gui.typing import BindTarget, BindCallback

__all__ = ['DisableableMixin', 'CallbackCommandMixin']


class DisableableMixin:
    widget: Optional[Widget]
    disabled: bool
    _disabled_state: str = 'disabled'
    _enabled_state: str = 'normal'

    def __init_subclass__(cls, disabled_state: str = None, enabled_state: str = None, **kwargs):
        super().__init_subclass__(**kwargs)
        if disabled_state:
            cls._disabled_state = disabled_state
        if enabled_state:
            cls._enabled_state = enabled_state

    def enable(self):
        if not self.disabled:
            return
        self.widget['state'] = self._enabled_state
        self.disabled = False

    def disable(self):
        if self.disabled:
            return
        self.widget['state'] = self._disabled_state
        self.disabled = True


class CallbackCommandMixin:
    widget: Button | Checkbutton | Menu | Radiobutton | Scale | Scrollbar | Text | OptionMenu | Spinbox
    _callback: BindTarget | None
    normalize_callback: Callable[[BindTarget], BindCallback]

    @property
    def callback(self) -> BindTarget | None:
        return self._callback

    @callback.setter
    def callback(self, callback: BindTarget | None):
        self._callback = callback
        if widget := self.widget:
            widget.configure(command=self.normalize_callback(callback))
