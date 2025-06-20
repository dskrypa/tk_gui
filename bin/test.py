#!/usr/bin/env python

import logging
from functools import cached_property
from pathlib import Path

from cli_command_parser import Command, Action, Counter, Flag, main

from tk_gui.elements import Table, Input, Text, ScrollFrame, SizeGrip, CheckBox, Button
from tk_gui.elements.bars import HorizontalSeparator, VerticalSeparator
from tk_gui.elements.images import Image, Animation, SpinnerImage, ClockImage
from tk_gui.elements.menu.menu import Menu, MenuGroup, MenuItem
from tk_gui.elements.menu.items import CopySelection, GoogleSelection, SearchKpopFandom, SearchGenerasia, PasteClipboard
from tk_gui.elements.menu.items import ToUpperCase, ToTitleCase, ToLowerCase, OpenFileLocation, OpenFile
from tk_gui.elements.menu.items import CloseWindow
from tk_gui.elements.text import Multiline, gui_log_handler
from tk_gui.elements.trees.tree import Tree, Column, TreeNode
from tk_gui.event_handling import ClickHighlighter
from tk_gui.images import Icons, ICONS_DIR
from tk_gui.popups.about import AboutPopup
from tk_gui.popups.raw import PickColor
from tk_gui.styles.colors import BLU_ML_0, WHITE
from tk_gui.window import Window
from tk_gui.utils import readable_bytes


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
    highlight_clicks = Flag('-c', help='Use ClickHighlighter to highlight clicked elements')

    def _init_command_(self):
        logging.getLogger('PIL').setLevel(50)
        try:
            from ds_tools.logging import init_logging
        except ImportError:
            log_fmt = '%(asctime)s %(levelname)s %(name)s %(lineno)d %(message)s' if self.verbose > 1 else '%(message)s'
            logging.basicConfig(level=logging.DEBUG if self.verbose else logging.INFO, format=log_fmt)
        else:
            init_logging(self.verbose, log_path=None, names=None)

    def _run_window(self, window: Window):
        if not self.highlight_clicks:
            return window.run()

        # log_event_kwargs = {'window': window, 'show_event_attrs': True, 'show_config': True, 'show_get_result': True}
        ClickHighlighter(log_event=True, log_event_kwargs={'window': window}).register(window)
        return window.run()

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
        self._run_window(window)

    @action
    def max_size(self):
        layout = [[Text(f'test_{i:03d}')] for i in range(100)]
        window = Window(layout, 'Auto Max Size Test', exit_on_esc=True)
        self._run_window(window)

    @cached_property
    def _dir_and_file_icons(self):
        icons = Icons(14)
        dir_icon = icons.draw_alpha_cropped('folder-fill', color=BLU_ML_0)
        file_icon = icons.draw_alpha_cropped('file-earmark-fill', color=WHITE)
        return dir_icon, file_icon

    @action
    def file_tree(self):
        dir_icon, file_icon = self._dir_and_file_icons
        cwd = Path.cwd()
        contents = sorted(cwd.iterdir())
        root = TreeNode(None, key=cwd.as_posix(), text=cwd.name, values=[f'{len(contents)} items'], icon=dir_icon)
        self._add_dir(root, contents, 3)

        tree = Tree(root, [Column('#0', 'Name', width=30), Column('Size', width=20)], rows=20)
        window = Window([[tree]], 'File Tree Test', exit_on_esc=True)
        self._run_window(window)

    def _add_dir(self, root: TreeNode, dir_items: list[Path], recurse: int = 0):
        dir_icon, file_icon = self._dir_and_file_icons
        for path in dir_items:
            if path.is_dir():
                if recurse:
                    child_items = sorted(path.iterdir())
                    child = root.add_child(path.as_posix(), path.name, [f'{len(child_items)} items'], icon=dir_icon)
                    self._add_dir(child, child_items, recurse - 1)
                else:
                    root.add_child(path.as_posix(), path.name, ['? items'], icon=dir_icon)
            else:
                root.add_child(path.as_posix(), path.name, [readable_bytes(path.stat().st_size)], icon=file_icon)

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

        with gui_log_handler(multiline):
            results = self._run_window(window).results
        print(f'Results: {results}')


if __name__ == '__main__':
    main()
