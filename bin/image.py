#!/usr/bin/env python

import logging
from pathlib import Path

from cli_command_parser import Command, Positional, Counter, Option, Flag, main, inputs

from tk_gui.__version__ import __author_email__, __version__, __author__, __url__  # noqa
from tk_gui.views.image import ImageView


class ImageViewer(Command):
    path: Path = Positional(type=inputs.Path(type='file', exists=True), help='Path to the image to view')
    verbose = Counter('-v', help='Increase logging verbosity (can specify multiple times)')

    def __init__(self):
        logging.getLogger('PIL.PngImagePlugin').setLevel(50)
        logging.getLogger('PIL.TiffImagePlugin').setLevel(50)
        log_fmt = '%(asctime)s %(levelname)s %(name)s %(lineno)d %(message)s' if self.verbose > 1 else '%(message)s'
        level = logging.DEBUG if self.verbose else logging.INFO
        logging.basicConfig(level=level, format=log_fmt)

    def main(self):
        ImageView(self.path).run()


if __name__ == '__main__':
    main()
