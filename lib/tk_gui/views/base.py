"""
Base View class

:author: Doug Skrypa
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from time import monotonic
from typing import TYPE_CHECKING, Any, Union

from tk_gui.caching import cached_property
from tk_gui.config import GuiConfigProperty
from tk_gui.event_handling import HandlesEvents, BindMap
from tk_gui.monitors import Monitor, monitor_manager
from tk_gui.window import Window

if TYPE_CHECKING:
    from tk_gui.typing import Layout, Key, PathLike

__all__ = ['WindowInitializer']
log = logging.getLogger(__name__)

_NotSet = object()


class WindowInitializer(HandlesEvents, ABC):
    parent: Window | None = None
    title: str | None = None
    is_popup: bool = False

    config = GuiConfigProperty()
    config_name: str = None
    config_path: PathLike = None
    config_defaults: dict[str, Any] = None

    def __init_subclass__(
        cls,
        title: str = None,
        config_name: str = None,
        config_path: PathLike = None,
        config_defaults: dict[str, Any] = None,
        is_popup: bool = None,
        **kwargs,
    ):
        super().__init_subclass__(**kwargs)
        if title:
            cls.title = title
        if config_name:
            cls.config_name = config_name
        if config_path:
            cls.config_path = config_path
        if config_defaults is not None:
            cls.config_defaults = config_defaults
        if is_popup is not None:
            cls.is_popup = is_popup

    def __init__(
        self,
        parent: Union[WindowInitializer, Window] = _NotSet,
        *,
        title: str = None,
        config_name: str = None,
        config_path: PathLike = None,
        config_defaults: dict[str, Any] = None,
        is_popup: bool = None,
        **kwargs,
    ):
        if parent is _NotSet:
            try:
                self.parent = Window.get_active_windows(sort_by_last_focus=True)[0]
            except IndexError:
                pass
        elif parent is not None:
            self.parent = parent.window if isinstance(parent, WindowInitializer) else parent
        if title is not None:
            self.title = title
        if config_name:
            self.config_name = config_name
        if config_path:
            self.config_path = config_path
        if config_defaults is not None:
            self.config_defaults = config_defaults
        if is_popup is not None:
            self.is_popup = is_popup
        self.window_kwargs = kwargs

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}[{self.title}][handlers: {len(self._event_handlers_)}]>'

    def _get_bind_map(self) -> BindMap:
        return BindMap.pop_and_normalize(self.window_kwargs) | self.event_handler_binds()

    @cached_property
    def bind_map(self) -> BindMap:
        return self._get_bind_map()

    @property
    def window_kwargs(self) -> dict[str, Any]:
        return self._window_kwargs

    @window_kwargs.setter
    def window_kwargs(self, value: dict[str, Any]):
        self._window_kwargs = value

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
        return Window(
            self.get_pre_window_layout(),
            title=self.title,
            binds=self.bind_map,
            config=self.config,
            is_popup=self.is_popup,
            **self.window_kwargs,
        )

    @cached_property
    def window(self) -> Window:
        return self.init_window()

    def finalize_window(self) -> Window:
        start = monotonic()
        window = self._finalize_window()
        elapsed = monotonic() - start
        log.debug(f'Rendered layout for {self.__class__.__name__} in seconds={elapsed:,.3f}')
        return window

    def _finalize_window(self) -> Window:
        window = self.window
        if layout := self.get_post_window_layout():
            window.add_rows(layout, pack=window.was_shown)
            try:
                window.update_idle_tasks()
            except AttributeError:  # There was no init layout, so .show() was not called in Window.__init__
                window.show()
            else:  # The scroll region only needs to be updated if the window was already shown
                try:
                    window.resize_scroll_region()
                except TypeError:  # It was not scrollable
                    pass
        if parent := self.parent:
            if isinstance(parent, WindowInitializer):
                parent = parent.window
            parent.register_child_window(window)
            try:
                window.move_to_center(parent)
            except AttributeError:
                pass
        return window

    # endregion

    def get_monitor(self) -> Monitor | None:
        if window := self.__dict__.get('window'):
            return monitor_manager.get_monitor(*window.position)
        elif parent := self.parent:
            return monitor_manager.get_monitor(*parent.position)
        else:
            return monitor_manager.get_monitor(0, 0)

    # region Run Methods

    @abstractmethod
    def run(self):
        raise NotImplementedError

    def get_results(self) -> dict[Key, Any]:
        """
        Called by :meth:`.run` to provide the results of running this view.  May be overridden by subclasses to handle
        custom finalization / form submission logic.
        """
        return self.window.results

    # endregion

    def cleanup(self):
        """
        Intended to be overridden by subclasses to handle cleanup actions, such as canceling ``after`` callbacks,
        before the window is closed.

        Called by :meth:`.View.run` and :meth:`.Popup._run` after :meth:`.Window.run` returns, before calling
        :meth:`.get_results`.
        """
        pass
