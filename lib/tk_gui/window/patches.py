"""
This module simply needs to be imported in ``window.__init__`` to take effect.
"""

from __future__ import annotations

import logging
from os import environ
from tkinter import CallWrapper, Variable

__all__ = ['patch_call_wrapper', 'patch_variable_del']
log = logging.getLogger(__name__)


def patch_call_wrapper():
    """Patch CallWrapper.__call__ to prevent it from suppressing KeyboardInterrupt"""

    def _cw_call(self, *args):
        # log.debug(f'CallWrapper({self!r}, {args=})')
        try:
            if subst := self.subst:
                args = subst(*args)
            return self.func(*args)
        except Exception:  # noqa
            # The original implementation re-raises SystemExit, but uses a bare `except:` here
            # log.error('Error encountered during tkinter call:', exc_info=True)
            self.widget._report_exception()

    CallWrapper.__call__ = _cw_call


def patch_variable_del():
    """
    Patch Variable.__del__ to prevent running outside of the main thread.  The official implementation has remained the
    same in Python 3.7 through 3.13.
    """

    def _var_del(self):
        """Unset the variable in Tcl."""
        if self._tk is None:
            return

        try:
            if self._tk.getboolean(self._tk.call('info', 'exists', self._name)):
                self._tk.globalunsetvar(self._name)
        except RuntimeError as e:  # RuntimeError: main thread is not in main loop
            # TODO: Maybe put the var in a global queue for the main thread window to process?
            log.warning(f'Error deleting {self.__class__.__name__} with name={self._name!r}: {e}')
            raise

        if self._tclCommands is not None:
            for name in self._tclCommands:
                # log.debug(f'Tkinter: deleting command={name!r}')
                self._tk.deletecommand(name)
            self._tclCommands = None

    Variable.__del__ = _var_del

    # real_var_init = Variable.__init__
    #
    # def _var_init(self, *args, **kwargs):
    #     real_var_init(self, *args, **kwargs)
    #     log.debug(f'Initialized {self.__class__.__name__}[{self._name}]', extra={'color': 12})
    #
    # Variable.__init__ = _var_init


if environ.get('TK_GUI_NO_CALL_WRAPPER_PATCH', '0') != '1':
    patch_call_wrapper()

if environ.get('TK_GUI_NO_VARIABLE_DEL_PATCH', '0') != '1':
    patch_variable_del()
