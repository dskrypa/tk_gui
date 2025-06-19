#!/usr/bin/env python

import logging

from cli_command_parser import Command, Counter, main

from tk_gui.elements import Text, VerticalSeparator, Image
from tk_gui.images import IconSourceImage, Icons
from tk_gui.window import Window


class IconViewer(Command):
    verbose = Counter('-v', default=2, help='Increase logging verbosity (can specify multiple times)')

    def _init_command_(self):
        logging.getLogger('PIL').setLevel(50)
        try:
            from ds_tools.logging import init_logging
        except ImportError:
            log_fmt = '%(asctime)s %(levelname)s %(name)s %(lineno)d %(message)s' if self.verbose > 1 else '%(message)s'
            logging.basicConfig(level=logging.DEBUG if self.verbose else logging.INFO, format=log_fmt)
        else:
            init_logging(self.verbose, log_path=None, names=None)

    def main(self):
        icons = Icons(30)
        layout, row = [], []
        for i, (icon, name) in enumerate(icons.draw_many(icons.char_names)):
            if row and i % 5 == 0:
                layout.append(row[:-1])
                row = []

            iw = IconSourceImage(icons, name, icon, popup_size=3000)
            row += [Image(iw, popup=True), Text(name, size=(30, 1)), VerticalSeparator()]

        if row:
            layout.append(row[:-1])

        config = {'remember_size': False, 'remember_position': False}
        Window(layout, 'Icon Test', exit_on_esc=True, scroll_y=True, config=config).run()


if __name__ == '__main__':
    main()
