#!/usr/bin/env python

import logging
from pathlib import Path

from cli_command_parser import Command, Action, Counter, main

from tk_gui.__version__ import __author_email__, __version__, __author__, __url__  # noqa
from tk_gui.elements import Table, Input, Text, ScrollFrame, SizeGrip
from tk_gui.elements.choices import CheckBox
from tk_gui.elements.bars import HorizontalSeparator, VerticalSeparator
from tk_gui.elements.buttons import Button
from tk_gui.elements.images import Image, Animation, SpinnerImage, ClockImage
from tk_gui.elements.menu.menu import Menu, MenuGroup, MenuItem
from tk_gui.elements.menu.items import CopySelection, GoogleSelection, SearchKpopFandom, SearchGenerasia, PasteClipboard
from tk_gui.elements.menu.items import ToUpperCase, ToTitleCase, ToLowerCase, OpenFileLocation, OpenFile
from tk_gui.elements.menu.items import CloseWindow
from tk_gui.elements.text import Multiline, gui_log_handler
from tk_gui.event_handling import ClickHighlighter
from tk_gui.images import IconSourceImage, Icons, ICONS_DIR
from tk_gui.popups.about import AboutPopup
from tk_gui.popups.raw import PickColor
from tk_gui.window import Window


class BaseRightClickMenu(Menu):
    MenuItem('Test A', print)
    CopySelection()
    PasteClipboard()
    with MenuGroup('Update'):
        ToLowerCase()
        ToUpperCase()
        ToTitleCase()


class GuiTest(Command):
    action = Action(help='The test to perform')
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

    @action
    def scroll(self):
        frame_content = [[Text(f'test_{i:03d}')] for i in range(100)]
        layout = [
            [ScrollFrame(frame_content, size=(100, 100), scroll_y=True)],
            [Image(ICONS_DIR.joinpath('exclamation-triangle-yellow.png'), popup=True, size=(150, 150))],
            [Multiline('\n'.join(map(chr, range(97, 123))), size=(40, 10))],
            [Multiline('\n'.join(map(chr, range(97, 105))), size=(40, 10))],
        ]

        window = Window(layout, 'Scroll Test', size=(300, 500), exit_on_esc=True, scroll_y=True)
        ClickHighlighter(log_event=True, log_event_kwargs={'window': window}).register(window)
        window.run()

    @action
    def max_size(self):
        layout = [[Text(f'test_{i:03d}')] for i in range(100)]
        Window(layout, 'Auto Max Size Test', exit_on_esc=True).run()

    @action
    def icons(self):
        icons = Icons(30)
        layout, row = [], []
        for i, (icon, name) in enumerate(icons.draw_many(icons.char_names)):
            if row and i % 5 == 0:
                layout.append(row[:-1])
                row = []

            iw = IconSourceImage(icons, name, icon, init_size=3000)
            row += [Image(iw, popup=True), Text(name, size=(30, 1)), VerticalSeparator()]

        if row:
            layout.append(row[:-1])

        config = {'remember_size': False, 'remember_position': False}
        Window(layout, 'Icon Test', exit_on_esc=True, scroll_y=True, config=config).run()

    @action(default=True)
    def window(self):
        table1 = Table.from_data([{'a': 1, 'b': 2}, {'a': 3, 'b': 4}], show_row_nums=True)
        table2 = Table.from_data(
            [{'a': n, 'b': n + 1, 'c': n + 2} for n in range(1, 21, 3)], show_row_nums=True, size=(4, 4)
        )
        inpt = Input('test', size=(15, 1), disabled=True)
        # inpt = Input('test', size=(15, 1), link='https://google.com')

        gif_path = ICONS_DIR.joinpath('spinners', 'ring_gray_segments.gif')
        png_path = ICONS_DIR.joinpath('exclamation-triangle-yellow.png')
        search_path = ICONS_DIR.joinpath('search.png')

        # layout = [
        #     [table1, table2],
        #     [inpt, Button('Submit', bind_enter=True), Button(image=search_path, shortcut='s', size=(30, 30))],
        #     [Animation(gif_path), SpinnerImage(), ClockImage()],
        #     [Text('test'), Text('link test', link='https://google.com')],
        #     [Image(png_path, popup=True, size=(150, 150))],
        #     [Multiline('\n'.join(map(chr, range(97, 123))), size=(40, 10))],
        # ]

        class RightClickMenu(BaseRightClickMenu):
            with MenuGroup('Search'):
                GoogleSelection()
                SearchKpopFandom()
                SearchGenerasia()
            with MenuGroup('Open'):
                OpenFileLocation()
                OpenFile()
            # MenuItem('Test B', print)

        class EleRightClickMenu(Menu):
            MenuItem('Test A', print)
            MenuItem('Test B', print)

        class MenuBar(Menu):
            with MenuGroup('File'):
                # MenuItem('Open', print)
                MenuItem('Pick Color', PickColor.as_callback('#1c1e23', title='Pick a Color'))
                CloseWindow()
            with MenuGroup('Help'):
                MenuItem('About', AboutPopup)

        frame_layout = [
            [MenuBar.clone()()],
            [table1], [table2],
            [HorizontalSeparator()],
            # [inpt, Button('Submit', bind_enter=True), Button(image=search_path, shortcut='s', size=(30, 30))],
            [
                inpt,
                Button('Submit', bind_enter=True),
                Button(image=search_path, shortcut='s', size=(30, 30)),
                Button(image=Icons(20).draw('arrow-repeat'), cb=lambda e: inpt.toggle_enabled()),
            ],
            [Animation(gif_path)], [SpinnerImage()], [ClockImage(right_click_menu=EleRightClickMenu())],
            [
                Text('test'),
                VerticalSeparator(),
                Text('link test', link='https://google.com'),
                VerticalSeparator(),
                Text('path link test', link=Path(__file__).resolve()),
            ],
            # [Text(f'test_{i:03d}')] for i in range(100)
        ]

        # multiline = Multiline(size=(40, 10), expand=True)
        multiline = Multiline(size=(120, None), expand=True, read_only=True, auto_scroll=True)
        # multiline = Multiline(size=(120, None), expand=True)
        # multiline = Multiline(size=(120, None), expand=True, read_only=True, read_only_style=True)

        layout = [
            # [ScrollFrame(frame_layout, size=(100, 100), scroll_y=True)],
            # [ScrollFrame(frame_layout, 'test frame', scroll_y=True, border=True, border_mode='inner', title_mode='inner')],
            # [ScrollFrame(frame_layout, 'test frame', scroll_y=True, border=True, border_mode='inner')],
            [ScrollFrame(frame_layout, scroll_y=True)],
            [CheckBox('A', key='A', default=True), CheckBox('B', key='B'), CheckBox('C', key='C')],
            [CheckBox('D', disabled=True), CheckBox('E', disabled=True, default=True)],
            [Image(png_path, popup=True, size=(150, 150))],
            [Text(Path(__file__).resolve().as_posix())],
            # [Multiline('\n'.join(map(chr, range(97, 123))), size=(40, 10)), SizeGrip()],
            [multiline, SizeGrip()],
        ]

        # Window(layout, size=(600, 600), anchor_elements='c').run()
        # Window(layout, anchor_elements='c', binds={'<Escape>': 'exit'}, kill_others_on_close=True).run()
        # Window(layout, anchor_elements='c', size=(300, 500), binds={'<Escape>': 'exit'}).run()
        # Window(layout, 'Test One', anchor_elements='c', binds={'<Escape>': 'exit'}).run()
        # results = Window(layout, binds={'<Escape>': 'exit'}, right_click_menu=RightClickMenu()).run().results
        window = Window(layout, 'Mixed Test', right_click_menu=RightClickMenu(), exit_on_esc=True, grab_anywhere=True)

        # log_event_kwargs = {'window': window, 'show_event_attrs': True, 'show_config': True, 'show_get_result': True}
        # ClickHighlighter(log_event=True, log_event_kwargs=log_event_kwargs).register(window)

        with gui_log_handler(multiline):
            results = window.run().results
        print(f'Results: {results}')


if __name__ == '__main__':
    main()
