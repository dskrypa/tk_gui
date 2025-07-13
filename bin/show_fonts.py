#!/usr/bin/env python

from __future__ import annotations

import logging
from functools import partial
from tkinter.font import Font, names, families

from cli_command_parser import Command, Counter, Option, Action, ParamGroup, main

from tk_gui.elements import Text, HorizontalSeparator, VerticalSeparator
from tk_gui.window import Window, ensure_tk_is_initialized

log = logging.getLogger(__name__)


class FontViewer(Command):
    action = Action(help='The action to take')
    verbose = Counter('-v', default=2, help='Increase logging verbosity (can specify multiple times)')
    mode = Option(
        '-m', choices=('names', 'families'), default='families', help='Whether font names or families should be used'
    )
    size = Option('-s', nargs='+', type=int, help='Font size(s) to use, in points (NOT pixels) (default: 10)')

    with ParamGroup('Filter'):
        include = Option('-i', nargs='+', help='Only include fonts that contain the specified text')
        include_mode = Option(
            '-im', choices=('or', 'and'), default='or',
            help='How include filters should be applied if multiple filters are provided'
        )
        exclude = Option('-x', nargs='+', help='Exclude fonts that contain the specified text')
        exclude_mode = Option(
            '-xm', choices=('or', 'and'), default='and',
            help='How exclude filters should be applied if multiple filters are provided'
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

        ensure_tk_is_initialized()

    @action(default=True, help='Show all fonts')
    def show(self):
        if fonts := self._get_font_names():
            Window(self._build_layout(fonts), 'Font Test', exit_on_esc=True, scroll_y=True).run()
        else:
            log.warning(f'No font {self.mode} matched the specified filter(s)')

    def _build_layout(self, fonts: list[str]):
        text = 'The quick brown fox jumps over the lazy dog.  Test 123,456,789.0: 안녕하세요!'
        chars = ''.join(chr(c) for c in range(65, 91))
        IText = partial(Text, use_input_style=True, justify='r')  # noqa

        sizes = self.size or (10,)
        family_mode = self.mode == 'families'

        for i, font_name in enumerate(fonts):
            if i:
                yield [HorizontalSeparator()]

            for size in sizes:
                font = Font(family=font_name, size=size) if family_mode else Font(name=font_name, size=size)
                metrics = font.metrics()
                widths = [font.measure(c) for c in chars]

                yield [
                    Text('Name:'), Text(font_name, use_input_style=True, size=(30, 1)),
                    Text('Size:'), IText(size, size=(4, 1)),
                    Text('Ascent:'), IText(metrics['ascent'], size=(4, 1)),
                    Text('Descent:'), IText(metrics['descent'], size=(4, 1)),
                    Text('Linespace:'), IText(metrics['linespace'], size=(4, 1)),
                    Text('Width Range:'), IText(f'{min(widths)} ~ {max(widths)}', size=(8, 1)),
                    Text('Avg Width:'), IText(f'{sum(widths) / 26:.2f}', size=(5, 1)),
                ]

                yield [Text(text, font=font, size=(80, 1))]

    @action(help='List all fonts')
    def list(self):
        for name in self._get_font_names():
            print(name)

    def _get_font_names(self) -> list[str]:
        fonts = sorted(set(names() if self.mode == 'names' else families()))

        if self.include:
            include_filters = [f.lower() for f in self.include]
            func = any if self.include_mode == 'or' else all
            fonts = [name for name in fonts if func(f in name.lower() for f in include_filters)]

        if self.exclude:
            exclude_filters = [f.lower() for f in self.exclude]
            func = any if self.exclude_mode == 'or' else all
            fonts = [name for name in fonts if func(f not in name.lower() for f in exclude_filters)]

        log.debug(f'Found {len(fonts)} matching font {self.mode}')
        return fonts


if __name__ == '__main__':
    main()
