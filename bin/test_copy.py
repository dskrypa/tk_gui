#!/usr/bin/env python

import logging

from cli_command_parser import Command, Counter, Positional, main
from cli_command_parser.inputs import Path as IPath

from tk_gui.popups.copy_files import CopyFilesPopup


class GuiCopyFilesPopupTest(Command):
    src_dir = Positional(type=IPath(type='dir', exists=True), help='Source directory')
    dst_dir = Positional(type=IPath(type='dir', exists=False), help='Destination directory')
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
        CopyFilesPopup.copy_dir(self.src_dir, self.dst_dir).run()


if __name__ == '__main__':
    main()
