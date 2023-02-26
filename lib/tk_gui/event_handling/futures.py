"""
Extension of the Future class from concurrent.futures that facilitates tracking completion of a task asynchronously
submitted through a tkinter widget's ``after`` method.
"""

from __future__ import annotations

from concurrent.futures._base import Future, PENDING
from functools import partial
from typing import TYPE_CHECKING, Callable, TypeVar, ParamSpec, Generic

if TYPE_CHECKING:
    from threading import Condition
    from tkinter import BaseWidget

__all__ = ['TkFuture', 'run_func_in_future']

P = ParamSpec('P')
T = TypeVar('T')


class TkFuture(Generic[T], Future):
    _condition: Condition
    _state: str
    _cb_id: str
    _widget: BaseWidget

    @classmethod
    def submit(
        cls, widget: BaseWidget, func: Callable[P, T], args: P.args = (), kwargs: P.kwargs = None, after_ms: int = 1
    ) -> TkFuture[T]:
        self = cls()
        wrapped = partial(run_func_in_future, self, func, args, kwargs)
        self._widget = widget
        self._cb_id = widget.after(after_ms, wrapped)
        return self

    def cancel(self) -> bool:
        with self._condition:
            if self._state == PENDING:
                self._widget.after_cancel(self._cb_id)
            return super().cancel()

    def result(self, timeout=None) -> T:
        return super().result(timeout)


def run_func_in_future(future, func, args=(), kwargs=None):
    """
    Used by :class:`Future<concurrent.futures.Future>` as the :class:`Thread<threading.Thread>` target function, to wrap
    the execution of the given function and capture any exceptions / store its results.

    :param Future future: The :class:`Future<concurrent.futures.Future>` object in which the results of executing the
      given function should be stored
    :param func: The function to execute
    :param args: Positional arguments for the function
    :param kwargs: Keyword arguments for the function
    """
    kwargs = kwargs or {}
    if future.set_running_or_notify_cancel():   # True if state changes from PENDING to RUNNING, False if cancelled
        try:
            result = func(*args, **kwargs)
        except BaseException as e:
            future.set_exception(e)
        else:
            future.set_result(result)
