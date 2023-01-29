"""
Base View class

:author: Doug Skrypa
"""

from __future__ import annotations

import logging
from time import monotonic
from typing import TYPE_CHECKING, Any, Union, Optional, Type, Sequence, Mapping

from tk_gui.caching import cached_property
from tk_gui.enums import CallbackAction
from ..event_handling import HandlesEvents, event_handler, BindMap
from ..window import Window

if TYPE_CHECKING:
    from tkinter import Event
    from ..typing import Layout, Key

__all__ = ['View', 'ViewSpec']
log = logging.getLogger(__name__)

ViewSpec = tuple[Type['View'], Sequence[Any], Mapping[str, Any]]


class View(HandlesEvents):
    __next: Optional[ViewSpec] = None
    window_kwargs: Optional[dict[str, Any]] = None
    parent: Union[View, Window] = None
    title: str = None

    def __init_subclass__(cls, title: str = None, **kwargs):
        super().__init_subclass__(**kwargs)
        if title:
            cls.title = title

    def __init__(self, parent: Union[View, Window] = None):
        if parent is not None:
            self.parent = parent

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}[{self.title}][handlers: {len(self._event_handlers_)}]>'

    # region Layout / Window Creation Methods

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
        window_kwargs = window_kwargs.copy()  # Prevent mutating a shared dict stored on a View subclass
        if binds := BindMap.pop_and_normalize(window_kwargs) | self.event_handler_binds():
            window_kwargs['binds'] = binds
        return Window(self.get_pre_window_layout(), title=self.title, **window_kwargs)

    @cached_property
    def window(self) -> Window:
        return self.init_window()

    def finalize_window(self) -> Window:
        window = self.window
        if layout := self.get_post_window_layout():
            window.add_rows(layout, pack=window.was_shown)
            try:
                window._update_idle_tasks()
            except AttributeError:  # There was no init layout, so .show() was not called in Window.__init__
                window.show()
            else:                   # The scroll region only needs to be updated if the window was already shown
                try:
                    window.update_scroll_region()
                except TypeError:  # It was not scrollable
                    pass
        if parent := self.parent:
            if isinstance(parent, View):
                parent = parent.window
            window.move_to_center(parent)
        return window

    # endregion

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
        start = monotonic()
        window = self.finalize_window()
        elapsed = monotonic() - start
        log.debug(f'Rendered layout for {self.__class__.__name__} in seconds={elapsed:,.3f}')
        with window(take_focus=True):
            window.run()
            return self.get_results()

    def get_results(self):
        """
        Called by :meth:`.run` to provide the results of running this view.  May be overridden by subclasses to handle
        custom finalization / form submission logic.
        """
        return self.window.results

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
