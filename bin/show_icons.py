#!/usr/bin/env python

import logging

from cli_command_parser import Command, Counter, Option, Action, main

from tk_gui.elements import Text, VerticalSeparator, Image
from tk_gui.images import IconSourceImage, Icons
from tk_gui.window import Window


class IconViewer(Command):
    action = Action(help='The action to take')
    verbose = Counter('-v', default=2, help='Increase logging verbosity (can specify multiple times)')
    count_per_row: int = Option('-c', default=5, help='Number of icons to display in each row')
    filter = Option('-f', nargs='+', help='Only include icons that contain the specified text')
    filter_mode = Option(
        '-m', choices=('or', 'and'), default='or', help='How filters should be applied if multiple filters are provided'
    )

    def _init_command_(self):
        logging.getLogger('PIL').setLevel(50)
        try:
            from ds_tools.logging import init_logging
        except ImportError:
            log_fmt = '%(asctime)s %(levelname)s %(name)s %(lineno)d %(message)s' if self.verbose > 1 else '%(message)s'
            logging.basicConfig(level=logging.DEBUG if self.verbose else logging.INFO, format=log_fmt)
        else:
            init_logging(self.verbose, log_path=None, names=None)

    @action(default=True, help='Show all icons')
    def show(self):
        icons = Icons(30)
        layout, row = [], []
        for i, (icon, name) in enumerate(icons.draw_many(self._get_icon_names(icons))):
            if row and i % self.count_per_row == 0:
                layout.append(row[:-1])
                row = []

            iw = IconSourceImage(icons, name, icon, popup_size=3000)
            row += [Image(iw, popup=True), Text(name, size=(30, 1)), VerticalSeparator()]

        if row:
            layout.append(row[:-1])

        config = {'remember_size': False, 'remember_position': False}
        Window(layout, 'Icon Test', exit_on_esc=True, scroll_y=True, config=config).run()

    @action(help='List all icons')
    def list(self):
        for icon_name in self._get_icon_names(Icons(30)):
            print(icon_name)

    def _get_icon_names(self, icons: Icons):
        if not self.filter:
            return icons.char_names
        filters = self.filter
        func = any if self.filter_mode == 'or' else all
        return [name for name in icons.char_names if func(f in name for f in filters)]


if __name__ == '__main__':
    main()
