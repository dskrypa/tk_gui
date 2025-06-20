#!/usr/bin/env python

import logging

from cli_command_parser import Command, Counter, Positional, main

from tk_gui.elements import Text, VerticalSeparator, Image
from tk_gui.images import IconSourceImage, Icons
from tk_gui.window import Window


class IconColorTest(Command):
    icon_name = Positional(help='The name of the icon to display')
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
        icon_name = self.icon_name
        icons = Icons(20)
        layout, row = [], []
        i = -1
        for red in range(0, 255, 25):
            for green in range(0, 255, 25):
                for blue in range(0, 255, 25):
                    i += 1
                    if row and i % 10 == 0:
                        layout.append(row[:-1])
                        row = []

                    rgb = (red, green, blue)
                    icon = icons.draw_alpha_cropped(icon_name, color=rgb)
                    rgb_hex = f'#{red:02X}{green:02X}{blue:02X}'
                    iw = IconSourceImage(icons, icon_name, icon, popup_size=3000, color=rgb)
                    row += [Image(iw, popup=True), Text(rgb_hex, size=(20, 1)), VerticalSeparator()]

        if row:
            layout.append(row[:-1])

        config = {'remember_size': False, 'remember_position': False}
        # Window(layout, 'Icon Test', exit_on_esc=True, scroll_y=True, config=config).run()
        Window(layout, 'Icon Test', exit_on_esc=True, scroll_y=True, config=config, style='SystemDefault').run()


if __name__ == '__main__':
    main()
