#!/usr/bin/env python

import logging
import time

from cli_command_parser import Command, Counter, main

from tk_gui.__version__ import __author_email__, __version__, __author__, __url__  # noqa
from tk_gui.popups import SpinnerPopup
from tk_gui.popups.choices import choose_item


class GuiPopupTest(Command):
    verbose = Counter('-v', default=2, help='Increase logging verbosity (can specify multiple times)')

    def _init_command_(self):
        logging.getLogger('PIL.PngImagePlugin').setLevel(50)
        try:
            from ds_tools.logging import init_logging
        except ImportError:
            log_fmt = '%(asctime)s %(levelname)s %(name)s %(lineno)d %(message)s' if self.verbose > 1 else '%(message)s'
            logging.basicConfig(level=logging.DEBUG if self.verbose else logging.INFO, format=log_fmt)
        else:
            init_logging(self.verbose, log_path=None, names=None)

    def main(self):
        spinner = SpinnerPopup(img_size=(400, 400), bind_esc=True)
        result = spinner.run_task_in_thread(_task)
        print(f'main: task finished with {result=}')


def _task():
    time.sleep(0.2)
    result = choose_item(['foo', 'bar', 'baz'], keep_on_top=True)
    print(f'_task: received {result=} but waiting before ending task')
    time.sleep(0.3)
    return result


if __name__ == '__main__':
    main()
