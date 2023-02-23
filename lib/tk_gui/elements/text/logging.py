"""
Helpers for writing logs to GUI elements.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from datetime import datetime
from tkinter import TclError
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .text import Multiline

__all__ = ['GuiTextHandler', 'gui_log_handler']
log = logging.getLogger(__name__)

_NotSet = object()


class GuiTextHandler(logging.Handler):
    def __init__(self, element: Multiline, level: int = logging.NOTSET):
        super().__init__(level)
        self.element = element

    def emit(self, record):
        try:
            msg = self.format(record)
            self.element.write(msg + '\n', append=True)
        except RecursionError:  # See issue 36272
            raise
        except TclError:
            pass  # The element was most likely destroyed
        except Exception:  # noqa
            self.handleError(record)


class DatetimeFormatter(logging.Formatter):
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
    logger_name: str | None = _NotSet,
    *,
    level: int = logging.DEBUG,
    entry_fmt: str = None,
    detail: bool = False,
    logger: logging.Logger = None,
):
    handler = GuiTextHandler(element, level)
    if detail and entry_fmt:
        raise ValueError(f'Unable to combine {detail=} with {entry_fmt=} - choose one or the other')
    if detail:
        entry_fmt = '%(asctime)s %(levelname)s %(threadName)s %(name)s %(lineno)d %(message)s'
        # handler.setFormatter(DatetimeFormatter(entry_fmt, '%Y-%m-%d %H:%M:%S %Z'))
        handler.setFormatter(DatetimeFormatter(entry_fmt, '%Y-%m-%d %H:%M:%S'))
    elif entry_fmt:
        handler.setFormatter(logging.Formatter(entry_fmt))

    loggers = [logger] if logger is not None else []
    if (name := None if logger_name is not _NotSet and not loggers else logger_name) is not _NotSet:
        loggers.append(logging.getLogger(name))
    for logger in loggers:
        logger.addHandler(handler)
    try:
        yield handler
    finally:
        for logger in loggers:
            logger.removeHandler(handler)
