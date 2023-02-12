"""
Helper function for running a long-running task in a thread with a spinner, while allowing popups produced by that
thread to be processed.
"""

from __future__ import annotations

from collections import defaultdict
from concurrent.futures import Future
from itertools import count
from queue import Empty
from threading import Thread
from typing import TYPE_CHECKING, Callable, TypeVar, ParamSpec

from .popups.base import POPUP_QUEUE
from .popups.image import SpinnerPopup

if TYPE_CHECKING:
    from .typing import XY

__all__ = ['run_task_with_spinner']

_names = defaultdict(count)
P = ParamSpec('P')
T = TypeVar('T')


def run_task_with_spinner(
    func: Callable[P, T], args: P.args = (), kwargs: P.kwargs = None, spinner_size: XY = (200, 200), **spin_kwargs
) -> T:
    spinner = SpinnerPopup(size=spinner_size, **spin_kwargs)
    spin_future, spin_thread = _as_future(spinner.run)
    func_future, func_thread = _as_future(func, args, kwargs, cb=lambda *a: spinner.window.interrupt())
    spin_thread.join(0.05)
    func_thread.join(0.05)
    while func_thread.is_alive():
        try:
            future, func, args, kwargs = POPUP_QUEUE.get(timeout=0.05)
        except Empty:
            pass
        else:
            if future.set_running_or_notify_cancel():
                try:
                    result = func(*args, **kwargs)
                except Exception as e:
                    future.set_exception(e)
                else:
                    future.set_result(result)

    return func_future.result()


def _as_future(func: Callable[P, T], args: P.args = (), kwargs: P.kwargs = None, daemon=None, cb=None):
    """
    Executes the given function in a separate thread.  Returns a :class:`Future<concurrent.futures.Future>` object
    immediately.

    :param func: The function to execute
    :param args: Positional arguments for the function
    :param kwargs: Keyword arguments for the function
    :param bool daemon: Whether the :class:`Thread<threading.Thread>` that the function runs in should be a daemon or
      not (default: see :attr:`daemon<threading.Thread.daemon>`)
    :param cb: A callback function that accepts one positional argument to be called when the future is complete.  The
      function will be called with the future object that completed.
    :return: A :class:`Future<concurrent.futures.Future>` object that will hold the results of executing the given
      function
    """
    future = Future()
    if cb is not None:
        future.add_done_callback(cb)
    func_name = func.__name__
    name = 'future:{}#{}'.format(func_name, next(_names[func_name]))
    thread = Thread(target=_run_func, args=(future, func, args, kwargs), name=name, daemon=daemon)
    thread.start()
    return future, thread


def _run_func(future, func, args=(), kwargs=None):
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
