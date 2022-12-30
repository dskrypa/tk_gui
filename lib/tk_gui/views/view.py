"""
Base View class

:author: Doug Skrypa
"""

from __future__ import annotations

import logging
from abc import ABCMeta, ABC
from contextvars import ContextVar
from functools import partial, update_wrapper, cached_property
from typing import TYPE_CHECKING, Any, Union, Optional, Callable, Type, Mapping

from ..window import Window

if TYPE_CHECKING:
    from tkinter import Event
    from ..typing import BindCallback, PathLike, Layout, Key

__all__ = []
log = logging.getLogger(__name__)

_view_stack = ContextVar('tk_gui.views.view.stack', default=[])


class EventHandler:
    def __init__(self, handler: BindCallback, binds: tuple[str, ...]):
        self.handler = handler
        self.binds = binds
        update_wrapper(self, handler)
        _view_stack.get()[-1].append(self)  # Store in the event_handlers list for the View class being defined

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}[{self.handler}, binds={self.binds!r}]>'


def event_handler(*binds: str) -> Callable[[BindCallback], EventHandler]:
    if not binds:
        raise ValueError('At least one tkinter event key is required to bind to')
    return partial(EventHandler, binds=binds)


class ViewMeta(ABCMeta, type):
    @classmethod
    def __prepare__(mcs, name: str, bases: tuple[type, ...], **kwargs) -> dict:
        """
        Called before ``__new__`` and before evaluating the contents of a class, which enables the establishment of a
        custom context to handle event handler registration.
        """
        _view_stack.get().append([])  # This list becomes the _event_handlers class attr for the View subclass
        return {}

    def __new__(mcs, name: str, bases: tuple[type, ...], namespace: dict[str, Any], **kwargs):
        cls = super().__new__(mcs, name, bases, namespace, **kwargs)
        cls._event_handlers = _view_stack.get().pop()
        return cls

    @classmethod
    def get_parent_view(mcs, cls: ViewMeta, include_abc: bool = True) -> Optional[ViewMeta]:
        for parent_cls in type.mro(cls)[1:]:
            if isinstance(parent_cls, mcs) and (include_abc or ABC not in parent_cls.__bases__):
                return parent_cls
        return None

    def event_handler_binds(cls: Type[View]) -> dict[str, BindCallback]:
        if parent := cls.__class__.get_parent_view(cls):
            bind_map = parent.event_handler_binds().copy()
        else:
            bind_map = {}

        for handler in cls._event_handlers:
            for bind in handler.binds:
                bind_map[bind] = handler.handler

        return bind_map


class View(metaclass=ViewMeta):
    _event_handlers: list[EventHandler]
    window_kwargs: Optional[dict[str, Any]] = None
    parent: Union[View, Window] = None
    primary: bool = True
    title: str = None

    def __init_subclass__(  # noqa
        cls,
        title: str,
        primary: bool = True,
        # config_path: PathLike = None,
        # config: Mapping[str, Any] = None,
    ):
        cls.title = title
        cls.primary = primary

    def __init__(self, parent: Union[View, Window] = None):
        if parent is not None:
            self.parent = parent

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}[{self.title}][{self.primary=!r}][handlers: {len(self._event_handlers)}]>'

    def get_init_layout(self) -> Layout:
        return []

    def get_layout(self) -> Layout:
        return []

    def init_window(self) -> Window:
        if (window_kwargs := self.window_kwargs) is None:
            window_kwargs = {}

        binds = window_kwargs.setdefault('binds', {})
        binds.update(self.__class__.event_handler_binds())
        return Window(self.get_init_layout(), title=self.title, **window_kwargs)

    @cached_property
    def window(self) -> Window:
        return self.init_window()

    def finalize_window(self) -> Window:
        window = self.window
        if layout := self.get_layout():
            window.add_rows(layout)
        if parent := self.parent:
            if isinstance(parent, View):
                parent = parent.window
            window.move_to_center(parent)
        return window

    def run(self) -> dict[Key, Any]:
        with self.window(take_focus=True) as window:
            window.run()
            return window.results


class TestView(View, title='Test'):
    @event_handler('<Ctrl-Button-1>')
    def handle_ctrl_left_click(self, event: Event):
        print(event)

    @event_handler('<Ctrl-Button-2>')
    def handle_ctrl_right_click(self, event: Event):
        print(event)
