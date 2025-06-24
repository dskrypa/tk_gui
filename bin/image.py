#!/usr/bin/env python

import logging

from cli_command_parser import Command, Positional, Counter, main, inputs

from tk_gui.popups.common import popup_error
from tk_gui.popups.paths import PickFile
from tk_gui.views.image import ImageView


class ImageViewer(Command):
    path = Positional(type=inputs.Path(type='file', exists=True), nargs='?', help='Path to the image to view')
    verbose = Counter('-v', help='Increase logging verbosity (can specify multiple times)')

    def __init__(self):
        logging.getLogger('PIL').setLevel(50)
        try:
            from ds_tools.logging import init_logging
        except ImportError:
            log_fmt = '%(asctime)s %(levelname)s %(name)s %(lineno)d %(message)s' if self.verbose > 1 else '%(message)s'
            logging.basicConfig(level=logging.DEBUG if self.verbose else logging.INFO, format=log_fmt)
        else:
            init_logging(self.verbose, log_path=None, names=None)

    def main(self):
        if not (path := self.path):
            path = PickFile().run()
            if not path:
                popup_error('No image was selected')
                return

        ImageView(path).run()


if __name__ == '__main__':
    main()
