"""
Base View class

:author: Doug Skrypa
"""

from __future__ import annotations

import logging
from functools import cached_property
from typing import TYPE_CHECKING, Any, Union, Optional, Mapping

from ..event_handling import HandlesEvents, event_handler, BindMap
from ..window import Window

if TYPE_CHECKING:
    from tkinter import Event
    from ..typing import PathLike, Layout, Key

__all__ = ['View']
log = logging.getLogger(__name__)


class View(HandlesEvents):
    window_kwargs: Optional[dict[str, Any]] = None
    parent: Union[View, Window] = None
    # primary: bool = True
    title: str = None

    def __init_subclass__(  # noqa
        cls,
        title: str = None,
        # primary: bool = True,
        # config_path: PathLike = None,
        # config: Mapping[str, Any] = None,
    ):
        if title:
            cls.title = title
        # cls.primary = primary

    def __init__(self, parent: Union[View, Window] = None):
        if parent is not None:
            self.parent = parent

    def __repr__(self) -> str:
        # return f'<{self.__class__.__name__}[{self.title}][{self.primary=!r}][handlers: {len(self._event_handlers_)}]>'
        return f'<{self.__class__.__name__}[{self.title}][handlers: {len(self._event_handlers_)}]>'

    def get_pre_window_layout(self) -> Layout:  # noqa
        """
        Intended to be overridden by subclasses to provide their layouts.

        Called by :meth:`.init_window` before the :class:`.Window` is initialized.
        """
        return []

    def get_post_window_layout(self) -> Layout:  # noqa
        """
        Intended to be overridden by subclasses to provide their layouts.

        Called by :meth:`.finalize_window` after the :class:`.Window` is initialized.  May be used for elements that
        need to obtain some information from the window before they can be initialized/rendered properly.
        """
        return []

    def init_window(self) -> Window:
        if (window_kwargs := self.window_kwargs) is None:
            window_kwargs = {}
        if binds := BindMap.pop_and_normalize(window_kwargs) | self.event_handler_binds():
            window_kwargs['binds'] = binds
        return Window(self.get_pre_window_layout(), title=self.title, **window_kwargs)

    @cached_property
    def window(self) -> Window:
        return self.init_window()

    def finalize_window(self) -> Window:
        window = self.window
        if layout := self.get_post_window_layout():
            window.add_rows(layout, pack=True)
            window._update_idle_tasks()
            try:
                window.update_scroll_region()
            except TypeError:  # It was not scrollable
                pass
        if parent := self.parent:
            if isinstance(parent, View):
                parent = parent.window
            window.move_to_center(parent)
        return window

    def get_results(self):
        """
        Called by :meth:`.run` to provide the results of running this view.  May be overridden by subclasses to handle
        custom finalization / form submission logic.
        """
        return self.window.results

    def run(self) -> dict[Key, Any]:
        window = self.finalize_window()
        with window(take_focus=True):
            window.run()
            return self.get_results()

    def get_next_view(self) -> View | None:  # noqa
        """
        Intended to be overwritten by subclasses.  If another view should be run after this one exits, this method
        should return that view.
        """
        return None

    @classmethod
    def run_all(cls, view: View = None, *args, **kwargs) -> Optional[dict[Key, Any]]:
        """
        Call the :meth:`.run` method for the specified view (or initialize this class and call it for this class, if no
        view object is provided), and on each subsequent view, if any view is returned by :meth:`.get_next_view`.

        :param view: The first :class:`View` to run.
        :param args: Positional arguments with which this View should be initialized if no ``view`` was provided.
        :param kwargs: Keyword arguments with which this View should be initialized if no ``view`` was provided.
        :return: The results from the last View that ran.
        """
        if view is None:
            view = cls(*args, **kwargs)

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
