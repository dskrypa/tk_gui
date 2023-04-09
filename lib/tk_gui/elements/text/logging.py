"""
Helpers for writing logs to GUI elements.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from logging import NOTSET, DEBUG, Handler, Formatter, Logger, getLogger
from tkinter import TclError
from typing import TYPE_CHECKING, ContextManager

from ..exceptions import MultilineContextError

if TYPE_CHECKING:
    from .text import Multiline

__all__ = ['GuiTextHandler', 'gui_log_handler']
log = getLogger(__name__)

_NotSet = object()


class GuiTextHandler(Handler):
    def __init__(self, element: Multiline, level: int = NOTSET):
        super().__init__(level)
        self.element = element

    def emit(self, record):
        try:
            msg = self.format(record)
            self.element.write(msg + '\n', append=True)
        except RecursionError:  # See issue 36272
            raise
        except (TclError, MultilineContextError):
            pass  # The element was most likely destroyed
        except Exception:  # noqa
            self.handleError(record)


class DatetimeFormatter(Formatter):
    """Enables use of ``%f`` (micro/milliseconds) in datetime formats."""

    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created)
        if datefmt:
            return dt.strftime(datefmt)
        else:
            t = dt.strftime(self.default_time_format)
            return self.default_msec_format % (t, record.msecs)


@contextmanager
def gui_log_handler(
    element: Multiline,
    *loggers: str | Logger | None,
    level: int = DEBUG,
    entry_fmt: str = None,
    detail: bool = False,
) -> ContextManager[GuiTextHandler]:
    gui_handler = GuiTextHandler(element, level)
    if detail and entry_fmt:
        raise ValueError(f'Unable to combine {detail=} with {entry_fmt=} - choose one or the other')
    if detail:
        entry_fmt = '%(asctime)s %(levelname)s %(threadName)s %(name)s %(lineno)d %(message)s'
        # handler.setFormatter(DatetimeFormatter(entry_fmt, '%Y-%m-%d %H:%M:%S %Z'))
        gui_handler.setFormatter(DatetimeFormatter(entry_fmt, '%Y-%m-%d %H:%M:%S'))
    elif entry_fmt:
        gui_handler.setFormatter(Formatter(entry_fmt))

    if loggers:
        loggers = [logger if isinstance(logger, Logger) else getLogger(logger) for logger in loggers]
    else:
        loggers = [getLogger(None)]

    for logger in loggers:
        logger.addHandler(gui_handler)
    try:
        yield gui_handler
    finally:
        for logger in loggers:
            logger.removeHandler(gui_handler)
