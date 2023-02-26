"""
Base View class

:author: Doug Skrypa
"""

from __future__ import annotations

import logging
from abc import ABC
from time import monotonic
from typing import TYPE_CHECKING, Any, Optional, Type, Sequence, Mapping

from tk_gui.enums import CallbackAction
from tk_gui.event_handling import event_handler
from .base import WindowInitializer

if TYPE_CHECKING:
    from tkinter import Event
    from ..typing import Key

__all__ = ['View', 'ViewSpec']
log = logging.getLogger(__name__)

ViewSpec = tuple[Type['View'], Sequence[Any], Mapping[str, Any]]


class View(WindowInitializer, ABC):
    __next: Optional[ViewSpec] = None
    default_window_kwargs: Optional[dict[str, Any]] = None

    def __init__(self, *args, **kwargs):
        if default_kwargs := self.default_window_kwargs:
            for key, value in default_kwargs.items():
                kwargs.setdefault(key, value)
        super().__init__(*args, **kwargs)

    # region Next View Methods

    def set_next_view(self, *args, view_cls: Type[View] = None, **kwargs) -> CallbackAction:
        """
        Set the next view that should be displayed.  From a Button callback, ``return self.set_next_view(...)`` can be
        used to trigger the advancement to that view immediately.  If that behavior is not desired, then it can simply
        be called without returning the value that is returned by this method.

        :param args: Positional arguments to use when initializing the next view
        :param view_cls: The class for the next View that should be displayed (defaults to the current class)
        :param kwargs: Keyword arguments to use when initializing the next view
        :return: The ``CallbackAction.EXIT`` callback action
        """
        if view_cls is None:
            view_cls = self.__class__
        self.__next = (view_cls, args, kwargs)
        return CallbackAction.EXIT

    def get_next_view_spec(self) -> ViewSpec | None:
        return self.__next

    def get_next_view(self) -> View | None:
        """
        If another view should be run after this one exits, this method should return that view.  By default, works
        with :meth:`.set_next_view`.
        """
        try:
            view_cls, args, kwargs = self.get_next_view_spec()
        except TypeError:
            return None
        return view_cls(*args, **kwargs)

    # endregion

    # region Run Methods

    def run(self) -> dict[Key, Any]:
        with self.finalize_window()(take_focus=True) as window:
            window.run()
            return self.get_results()

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

    # endregion


class TestView(View, title='Test'):
    @event_handler('<Control-Button-1>')
    def handle_ctrl_left_click(self, event: Event):
        print(f'ctrl + left click: {self=}, {event=}')

    @event_handler('<Control-Button-3>')
    def handle_ctrl_right_click(self, event: Event):
        print(f'ctrl + right click: {self=}, {event=}')
