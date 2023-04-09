"""
Base View class

:author: Doug Skrypa
"""

from __future__ import annotations

import logging
from abc import ABC
from typing import TYPE_CHECKING, Any, Optional, Union, Type, Sequence, Mapping, Literal

from tk_gui.enums import CallbackAction
from .base import WindowInitializer
from .spec import ViewSpec
from .state import GuiState, Direction, NoNextView

if TYPE_CHECKING:
    from ..typing import Key

__all__ = ['View']
log = logging.getLogger(__name__)

RawViewSpec = tuple[Type['View'], Sequence[Any], Mapping[str, Any]]
Dir = Union[Direction, Literal['reverse', 'forward', 'REVERSE', 'FORWARD', 0, 1]]


class View(WindowInitializer, ABC):
    gui_state: GuiState
    default_window_kwargs: Optional[dict[str, Any]] = None

    def __init__(self, *args, gui_state: GuiState = None, **kwargs):
        self.gui_state = gui_state or GuiState.init(ViewSpec(self.__class__, args, kwargs.copy()))
        if default_kwargs := self.default_window_kwargs:
            for key, value in default_kwargs.items():
                kwargs.setdefault(key, value)
        super().__init__(*args, **kwargs)

    # region Next View Methods

    @classmethod
    def as_view_spec(cls, *args, **kwargs) -> ViewSpec:
        return ViewSpec(cls, args, kwargs)

    def go_to_next_view(self, spec: ViewSpec, *, forget_last: bool = False) -> CallbackAction:
        self.gui_state.enqueue_view(spec, forget_last)
        return CallbackAction.EXIT

    def go_to_prev_view(self, forget_last: bool = False, **kwargs) -> CallbackAction | None:
        """
        :param forget_last: If True, then the ViewSpec for the View that the given ``spec`` follows will not be saved
          in the ViewSpec history.  Typically used if the View needed to be reloaded in-place.
        :param kwargs: Keyword arguments to override previously used keyword args from the previous View's ViewSpec.
        """
        if self.gui_state.enqueue_hist_view(Direction.REVERSE, forget_last, **kwargs):
            return CallbackAction.EXIT
        return None

    def go_to_hist_view(self, direction: Dir, forget_last: bool = False, **kwargs) -> CallbackAction | None:
        """
        :param direction: The history direction from which a ViewSpec should be enqueued
        :param forget_last: If True, then the ViewSpec for the View that the given ``spec`` follows will not be saved
          in the ViewSpec history.  Typically used if the View needed to be reloaded in-place.
        :param kwargs: Keyword arguments to override previously used keyword args from the selected View's ViewSpec.
        """
        if self.gui_state.enqueue_hist_view(Direction(direction), forget_last, **kwargs):
            return CallbackAction.EXIT
        return None

    def get_next_view_spec(self) -> ViewSpec | RawViewSpec | None:
        return self.gui_state.pop_next_view()

    def get_next_view(self) -> View | None:
        """
        If another view should be run after this one exits, this method should return that view.  By default, works
        with :meth:`.go_to_next_view`.
        """
        try:
            view_cls, args, kwargs = self.get_next_view_spec()
        except (TypeError, NoNextView):
            return None
        if 'gui_state' in kwargs:  # Not using setdefault to avoid mutating the stored kwargs
            return view_cls(*args, **kwargs)
        else:
            return view_cls(*args, gui_state=self.gui_state, **kwargs)

    # endregion

    # region Run Methods

    def run(self, take_focus: bool = True) -> dict[Key, Any]:
        with self.finalize_window()(take_focus=take_focus) as window:
            window.run()
            self.cleanup()
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
