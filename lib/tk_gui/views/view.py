"""
Base View class

:author: Doug Skrypa
"""

from __future__ import annotations

import logging
from functools import cached_property
from typing import TYPE_CHECKING, Any, Union, Optional, Mapping

from ..event_handling import HandlesEvents, event_handler
from ..window import Window

if TYPE_CHECKING:
    from tkinter import Event
    from ..typing import PathLike, Layout, Key

__all__ = ['View']
log = logging.getLogger(__name__)


class View(HandlesEvents):
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
        return f'<{self.__class__.__name__}[{self.title}][{self.primary=!r}][handlers: {len(self._event_handlers_)}]>'

    def get_init_layout(self) -> Layout:
        return []

    def get_layout(self) -> Layout:
        return []

    def init_window(self) -> Window:
        if (window_kwargs := self.window_kwargs) is None:
            window_kwargs = {}

        binds = window_kwargs.setdefault('binds', {})
        binds.update(self.event_handler_binds())
        return Window(self.get_init_layout(), title=self.title, **window_kwargs)

    @cached_property
    def window(self) -> Window:
        return self.init_window()

    def finalize_window(self) -> Window:
        window = self.window
        if layout := self.get_layout():
            window.add_rows(layout)
            # TODO: Need to trigger an update after this or something
        if parent := self.parent:
            if isinstance(parent, View):
                parent = parent.window
            window.move_to_center(parent)
        return window

    def run(self) -> dict[Key, Any]:
        with self.window(take_focus=True) as window:
            window.run()
            return window.results

    def get_next_view(self) -> View | None:
        """
        Intended to be overwritten by subclasses.  If another view should be run after this one exits, this method
        should return that view.
        """
        return None

    @classmethod
    def run_all(cls, view: View = None) -> Optional[dict[Key, Any]]:
        """
        Call the :meth:`.run` method for the specified view (or initialize this class and call it for this class, if no
        view object is provided), and on each subsequent view, if any view is returned by :meth:`.get_next_view`.

        :param view: The first :class:`View` to run.
        :return: The results from the last View that ran.
        """
        if view is None:
            view = cls()

        results = None
        while view is not None:
            results = view.run()
            view = view.get_next_view()
            log.debug(f'Next {view=}')

        return results


class TestView(View, title='Test'):
    @event_handler('<Control-Button-1>')
    def handle_ctrl_left_click(self, event: Event):
        print(f'ctrl + left click: {self=}, {event=}')

    @event_handler('<Control-Button-3>')
    def handle_ctrl_right_click(self, event: Event):
        print(f'ctrl + right click: {self=}, {event=}')
