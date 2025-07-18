"""
Base View class

:author: Doug Skrypa
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Union

from tk_gui.caching import cached_property
from tk_gui.config import GuiConfigProperty
from tk_gui.event_handling import HandlesEvents, BindMap
from tk_gui.monitors import Monitor, monitor_manager
from tk_gui.styles.style import Style
from tk_gui.utils import timer
from tk_gui.window import Window

if TYPE_CHECKING:
    from tk_gui.styles.typing import StyleSpec
    from tk_gui.typing import Layout, Key, PathLike

__all__ = ['ViewWindowInitializer']
log = logging.getLogger(__name__)

_NotSet = object()


class ViewWindowInitializer(HandlesEvents, ABC):
    parent: Window | None = None
    title: str | None = None
    is_popup: bool = False
    _style: StyleSpec = None

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
        parent: ViewWindowInitializer | Window = _NotSet,
        *,
        title: str = None,
        config_name: str = None,
        config_path: PathLike = None,
        config_defaults: dict[str, Any] = None,
        is_popup: bool = None,
        style: StyleSpec = None,
        **kwargs,
    ):
        if parent is _NotSet:
            self.parent = Window.get_active_window()
        elif parent is not None:
            # log.debug(f'{self.__class__.__name__} parent was explicitly provided: {parent}', extra={'color': 13})
            self.parent = parent.window if isinstance(parent, ViewWindowInitializer) else parent
        # log.debug(f'Initializing {self.__class__.__name__} with parent={self.parent}', extra={'color': 13})
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
        if style is not None:
            self._style = style
        self.window_kwargs = kwargs

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}[{self.title}][handlers: {len(self._event_handlers_)}]>'

    def _get_bind_map(self) -> BindMap:
        return BindMap.pop_and_normalize(self.window_kwargs) | self.event_handler_binds()

    @cached_property
    def bind_map(self) -> BindMap:
        return self._get_bind_map()

    @cached_property
    def style(self) -> Style:
        # This matches the logic in Window.__init__ + RowContainer.__init__
        return Style.get_style(self._style or self.config.style)

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
        kwargs = self.window_kwargs
        if 'show' in kwargs:
            kwargs = kwargs.copy()
            show = kwargs.pop('show')
        else:
            show = True

        window = Window(
            self.get_pre_window_layout(),
            title=self.title,
            binds=self.bind_map,
            config=self.config,
            is_popup=self.is_popup,
            show=False,
            style=self._style,
            **kwargs,
        )
        if self._parent_window:
            self._parent_window.register_child_window(window)

        if show and (window.rows or (isinstance(show, int) and show > 1)):  # Matches logic in Window.__init__
            # This is deferred so the parent window can be registered before initialization code that depends on it
            window.show()

        return window

    @cached_property
    def window(self) -> Window:
        return self.init_window()

    @cached_property
    def _parent_window(self) -> Window | None:
        if self.parent is not None:
            return self.parent.window if isinstance(self.parent, ViewWindowInitializer) else self.parent
        return None

    def finalize_window(self) -> Window:
        with timer(f'Rendered layout for {self.__class__.__name__}'):
            window = self._finalize_window()
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

        if self._parent_window:
            try:
                window.move_to_center(self._parent_window)
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
