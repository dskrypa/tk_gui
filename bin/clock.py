#!/usr/bin/env python

import logging

from cli_command_parser import Command, Counter, Option, Flag, main

from tk_gui.__version__ import __author_email__, __version__, __author__, __url__  # noqa
from tk_gui.views.clock import ClockView


class Clock(Command):
    verbose = Counter('-v', help='Increase logging verbosity (can specify multiple times)')
    color = Option('-c', default='#FF0000', help='The color to use for numbers on the clock')
    background = Option('-b', default='#000000', help='The background color for the clock')
    no_seconds = Flag('-S', name_mode='-', help='Hide seconds')

    def __init__(self):
        logging.getLogger('PIL.PngImagePlugin').setLevel(50)
        log_fmt = '%(asctime)s %(levelname)s %(name)s %(lineno)d %(message)s' if self.verbose > 1 else '%(message)s'
        level = logging.DEBUG if self.verbose else logging.INFO
        logging.basicConfig(level=level, format=log_fmt)

    def main(self):
        ClockView(seconds=not self.no_seconds, fg=self.color, bg=self.background).run()


if __name__ == '__main__':
    main()
