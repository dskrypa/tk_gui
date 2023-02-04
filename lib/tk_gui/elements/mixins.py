"""

"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Callable

if TYPE_CHECKING:
    from tkinter import Widget, Button, Checkbutton, Menu, Radiobutton, Scale, Scrollbar, Text, OptionMenu, Spinbox
    from tkinter import Variable
    from tk_gui.typing import BindTarget, BindCallback, TraceCallback

__all__ = ['DisableableMixin', 'CallbackCommandMixin', 'TraceCallbackMixin']


class DisableableMixin:
    configure_widget: Callable
    apply_style: Callable
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
        self.configure_widget(state=self._enabled_state)
        self.disabled = False
        self.apply_style()

    def disable(self):
        if self.disabled:
            return
        self.configure_widget(state=self._disabled_state)
        self.disabled = True
        self.apply_style()


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


class TraceCallbackMixin:
    __change_cb_name: str | None = None
    __var_change_cb: TraceCallback | None = None
    tk_var: Variable | None

    @property
    def var_change_cb(self) -> TraceCallback | None:
        return self.__var_change_cb

    @var_change_cb.setter
    def var_change_cb(self, value: TraceCallback | None):
        self.__var_change_cb = value
        if value is None:
            self._maybe_remove_var_trace()
        else:
            self._maybe_add_var_trace()

    @var_change_cb.deleter
    def var_change_cb(self):
        self._maybe_remove_var_trace()
        self.__var_change_cb = None

    def _maybe_add_var_trace(self):
        if (var_change_cb := self.__var_change_cb) and (tk_var := self.tk_var):
            self.__change_cb_name = tk_var.trace_add('write', var_change_cb)

    def _maybe_remove_var_trace(self):
        if (cb_name := self.__change_cb_name) and (tk_var := self.tk_var):
            tk_var.trace_remove('write', cb_name)
            self.__change_cb_name = None
