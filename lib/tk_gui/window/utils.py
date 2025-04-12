from __future__ import annotations

import logging
from tkinter import TclError
from typing import TYPE_CHECKING, Iterator, Type

from tk_gui.utils import mapping_repr

if TYPE_CHECKING:
    from tk_gui.typing import Bool
    from .base import Window

__all__ = ['WindowData']
log = logging.getLogger(__name__)


class WindowDataProperty:
    def __init__(self, is_mapping: bool = False):
        self.is_mapping = is_mapping

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, instance: WindowData, owner: Type[WindowData]):
        if instance is None:
            return self

        try:
            value = getattr(instance.root, owner._SHOW_METHOD_MAP[self.name])()
        except (AttributeError, TclError):  # Toplevel does not extend Pack
            value = '???'
        else:
            if self.is_mapping:
                value = mapping_repr(value, indent=4)

        instance.__dict__[self.name] = value
        return value


class WindowData:
    """Window equivalent of :class:`~.widgets.utils.WidgetData`"""

    frame = WindowDataProperty()
    attrs = WindowDataProperty()
    focus_model = WindowDataProperty()
    geometry = WindowDataProperty()
    override_redirect = WindowDataProperty()
    resizable = WindowDataProperty()
    # Potential state values: normal, iconic, withdrawn; icon (cannot be set); Win/Mac-only: zoomed
    state = WindowDataProperty()
    title = WindowDataProperty()
    transient = WindowDataProperty()

    _SHOW_METHOD_MAP = {
        'frame': 'wm_frame',
        'attrs': 'wm_attributes',
        'focus_model': 'wm_focusmodel',
        'geometry': 'wm_geometry',
        'override_redirect': 'wm_overrideredirect',
        'resizable': 'wm_resizable',
        'state': 'wm_state',
        'title': 'wm_title',
        'transient': 'wm_transient',
    }

    def __init__(
        self,
        window: Window,
        *,
        show_frame: Bool = True,
        show_attrs: Bool = True,
        show_focus_model: Bool = True,
        show_geometry: Bool = True,
        show_override_redirect: Bool = True,
        show_resizable: Bool = True,
        show_state: Bool = True,
        show_title: Bool = True,
        show_transient: Bool = True,
    ):
        self.window = window
        self.root = window.root
        self.show = {
            'frame': show_frame,
            'attrs': show_attrs,
            'focus_model': show_focus_model,
            'geometry': show_geometry,
            'override_redirect': show_override_redirect,
            'resizable': show_resizable,
            'state': show_state,
            'title': show_title,
            'transient': show_transient,
        }

    def __iter__(self) -> Iterator[str]:
        cls = self.__class__
        yield '{'
        for key, show in self.show.items():
            if show:
                value = getattr(self, key)
                if not getattr(cls, key).is_mapping:
                    value = repr(value)
                yield f'    {key}={value}'
        yield '}'

    def __str__(self) -> str:
        return '\n'.join(self)

    def log(self, prefix: str = 'Window info:', level: int = logging.DEBUG):
        log.log(level, f'{prefix}{self}')
