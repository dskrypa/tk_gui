#!/usr/bin/env python

import logging
from pathlib import Path

from cli_command_parser import Command, Action, Counter, Option, main

from tk_gui.__version__ import __author_email__, __version__, __author__, __url__  # noqa
from tk_gui.elements import Table, Input, Button, Text, ScrollFrame, SizeGrip
from tk_gui.elements.choices import Radio, RadioGroup, CheckBox, Combo, ListBox
from tk_gui.elements.bars import HorizontalSeparator, VerticalSeparator, ProgressBar, Slider
from tk_gui.elements.images import Image, Animation, SpinnerImage, ClockImage
from tk_gui.elements.menu.menu import Menu, MenuGroup, MenuItem, MenuProperty
from tk_gui.elements.menu.items import CopySelection, GoogleSelection, SearchKpopFandom, SearchGenerasia, PasteClipboard
from tk_gui.elements.menu.items import ToUpperCase, ToTitleCase, ToLowerCase, OpenFileLocation, OpenFile
from tk_gui.elements.menu.items import CloseWindow
from tk_gui.elements.text import Multiline, gui_log_handler
from tk_gui.elements.rating import Rating
from tk_gui.images.utils import ICONS_DIR
from tk_gui.options import GuiOptions
from tk_gui.popups import ImagePopup, AnimatedPopup, SpinnerPopup, ClockPopup, BasicPopup, Popup
from tk_gui.popups.about import AboutPopup
from tk_gui.popups.base import TextPromptPopup, LoginPromptPopup
from tk_gui.popups.common import popup_warning, popup_error, popup_yes_no, popup_no_yes, popup_ok, popup_get_text
from tk_gui.popups.raw import PickFolder, PickColor, PickFile
from tk_gui.popups.style import StylePopup
from tk_gui.views.view import View
from tk_gui.window import Window


class GuiTest(Command):
    action = Action(help='The test to perform')
    verbose = Counter('-v', default=2, help='Increase logging verbosity (can specify multiple times)')
    color = Option('-c', help='The initial color to display when action=pick_color')

    def __init__(self):
        logging.getLogger('PIL.PngImagePlugin').setLevel(50)
        log_fmt = '%(asctime)s %(levelname)s %(name)s %(lineno)d %(message)s' if self.verbose > 1 else '%(message)s'
        level = logging.DEBUG if self.verbose else logging.INFO
        logging.basicConfig(level=level, format=log_fmt)

    @action
    def about(self):
        AboutPopup().run()

    # region Image Tests

    @action
    def spinner(self):
        SpinnerPopup(img_size=(400, 400)).run()

    @action
    def gif(self):
        gif_path = ICONS_DIR.joinpath('spinners', 'ring_gray_segments.gif')
        AnimatedPopup(gif_path).run()

    @action
    def image(self):
        png_path = ICONS_DIR.joinpath('exclamation-triangle-yellow.png')
        ImagePopup(png_path).run()

    @action
    def clock(self):
        ClockPopup(toggle_slim_on_click=True).run()

    # endregion

    @action
    def popup(self):
        # results = BasicPopup('This is a test', title='Test', buttons=('OK',)).run()
        results = BasicPopup('This is a test', title='Test', buttons=('Cancel', 'OK'), bind_esc=True).run()
        # results = BasicPopup('This is a test with more words', title='Test', buttons=('Cancel', 'Test', 'OK')).run()
        print(results)

    @action
    def scroll(self):
        frame_layout = [[Text(f'test_{i:03d}')] for i in range(100)]
        png_path = ICONS_DIR.joinpath('exclamation-triangle-yellow.png')

        layout = [
            [ScrollFrame(frame_layout, size=(100, 100), scroll_y=True)],
            # [ScrollFrame(frame_layout, scroll_y=True)],
            [Image(png_path, callback='popup', size=(150, 150))],
            [Multiline('\n'.join(map(chr, range(97, 123))), size=(40, 10))],
        ]

        Window(
            layout,
            'Scroll Test',
            size=(300, 500),
            exit_on_esc=True,
            scroll_y=True,
        ).run()

    @action
    def max_size(self):
        layout = [[Text(f'test_{i:03d}')] for i in range(100)]
        Window(layout, 'Auto Max Size Test', exit_on_esc=True).run()

    # region Input Tests

    @action
    def pick_folder(self):
        path = PickFolder().run()
        print(f'Picked: {path.as_posix() if path else path}')

    @action
    def pick_color(self):
        color = PickColor(self.color).run()
        print(f'Picked {color=}')

    @action
    def radio(self):
        b = RadioGroup('group 2')
        with RadioGroup('group 1'):
            layout = [
                [Radio('A1', default=True), Radio('B1', group=b)],
                [Radio('A2'), Radio('B2', 'b two', group=b)],
                [Radio('A3'), Radio('B3', group=b)],
            ]

        results = Window(layout, 'Radio Test', exit_on_esc=True).run().results
        print(f'Results: {results}')

    @action
    def combo(self):
        layout = [
            [Combo(['A', 'B', 'C', 'D'], key='A')],
            [Combo({'A': 1, 'B': 2, 'C': 3}, key='B', default='C')],
        ]
        results = Window(layout, 'Combo Test', exit_on_esc=True).run().results
        print(f'Results: {results}')

    @action
    def progress(self):
        bar = ProgressBar(100)
        window = Window([[Text('Processing...')], [bar]], 'Progress Test', exit_on_esc=True)
        for _ in bar(range(99)):
            window._root.after(50, window.interrupt)
            window.run()

    @action
    def slider(self):
        layout = [
            [Slider(0, 1, interval=0.05, key='A')],
            [Slider(0, 20, tick_interval=5, key='B')],
        ]
        results = Window(layout, 'Slider Test', exit_on_esc=True).run().results
        print(f'Results: {results}')

    @action
    def listbox(self):
        chars = list(map(chr, range(97, 123)))
        layout = [
            [ListBox(chars, key='A', size=(40, 10)), ListBox(chars, ['a', 'b'], key='B', size=(40, 10))]
        ]

        results = Popup(layout, 'ListBox Test', exit_on_esc=True).run()
        # results = Window(layout, 'ListBox Test', exit_on_esc=True).run().results
        print(f'Results: {results}')

    @action
    def rating(self):
        a, b = Rating(key='a'), Rating(key='b', show_value=True)

        def toggle_cb(event=None):
            for rating in (a, b):
                rating.toggle_enabled()

        layout = [[a], [b], [Button('Toggle', cb=toggle_cb)]]
        results = Window(layout, 'Rating Test', exit_on_esc=True).run().results
        print(f'Results: {results}')

    # endregion

    # region Test Popups

    @action
    def style(self):
        results = StylePopup(show_buttons=True).run()
        print(f'{results=}')

    @action
    def popup_multiline(self):
        filler = 'the quick brown fox jumped over the lazy dog'
        popup_ok(f'{filler}\n{filler}')

    @action
    def popup_warning(self):
        popup_warning('This is a test warning!')

    @action
    def popup_error(self):
        popup_error('This is a test error!')

    @action
    def popup_yes_no(self):
        result = popup_yes_no('This is a test!')
        print(f'{result=}')

    @action
    def popup_no_yes(self):
        result = popup_no_yes('This is a test!')
        print(f'{result=}')

    @action
    def popup_ok(self):
        popup_ok('This is a test!')

    @action
    def popup_text(self):
        result = TextPromptPopup('Enter a string').run()
        print(f'{result=}')

    @action
    def popup_text_cancel(self):
        result = TextPromptPopup('Enter a string', cancel_text='Cancel', bind_esc=True).run()
        print(f'{result=}')

    @action
    def popup_login(self):
        user, pw = LoginPromptPopup('Enter your login info', cancel_text='Cancel').run()
        print(f'{user=}, {pw=}')

    # endregion

    @action
    def menu_handler_methods(self):
        class MenuBar(Menu):
            with MenuGroup('File'):
                MenuItem('Select File')
                MenuItem('Settings')
                CloseWindow()
            with MenuGroup('Help'):
                MenuItem('About', AboutPopup)

        class TestView(View, title='Test'):
            menu = MenuProperty(MenuBar)

            @menu['File']['Select File'].callback
            def select_file_handler(self, event):
                path = PickFile(title='Pick a File').run()
                try:
                    path_str = path.as_posix()
                except AttributeError:
                    path_str = ''
                self.window['test_input'].update(path_str)  # noqa

            @menu['File']['Settings'].callback
            def settings(self, event):
                config = self.window.config
                options = GuiOptions(submit='Save', title=None)
                with options.next_row() as options:
                    options.add_bool('remember_pos', 'Remember Last Window Position', config.remember_position)
                    options.add_bool('remember_size', 'Remember Last Window Size', config.remember_size)
                with options.next_row() as options:
                    options.add_popup(
                        'style', 'Style', StylePopup, default=config.style, popup_kwargs={'show_buttons': True}
                    )
                with options.next_row() as options:
                    options.add_directory('output_dir', 'Output Directory')

                result = options.run_popup()
                return result

            def get_pre_window_layout(self):
                yield [self.menu]

            def get_post_window_layout(self):
                yield [Input(key='test_input', size=(40, 1))]

        TestView().run()

    @action(default=True)
    def window(self):
        table1 = Table.from_data([{'a': 1, 'b': 2}, {'a': 3, 'b': 4}], show_row_nums=True)
        table2 = Table.from_data(
            [{'a': n, 'b': n + 1, 'c': n + 2} for n in range(1, 21, 3)], show_row_nums=True, size=(4, 4)
        )
        inpt = Input('test', size=(15, 1))
        # inpt = Input('test', size=(15, 1), link='https://google.com')

        gif_path = ICONS_DIR.joinpath('spinners', 'ring_gray_segments.gif')
        png_path = ICONS_DIR.joinpath('exclamation-triangle-yellow.png')
        search_path = ICONS_DIR.joinpath('search.png')

        # layout = [
        #     [table1, table2],
        #     [inpt, Button('Submit', bind_enter=True), Button(image=search_path, shortcut='s', size=(30, 30))],
        #     [Animation(gif_path), SpinnerImage(), ClockImage()],
        #     [Text('test'), Text('link test', link='https://google.com')],
        #     [Image(png_path, callback='popup', size=(150, 150))],
        #     [Multiline('\n'.join(map(chr, range(97, 123))), size=(40, 10))],
        # ]

        class BaseRightClickMenu(Menu):
            MenuItem('Test A', print)
            CopySelection()
            PasteClipboard()
            with MenuGroup('Update'):
                ToLowerCase()
                ToUpperCase()
                ToTitleCase()

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
            [MenuBar()],
            [table1], [table2],
            [HorizontalSeparator()],
            [inpt, Button('Submit', bind_enter=True), Button(image=search_path, shortcut='s', size=(30, 30))],
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
        multiline = Multiline(size=(120, None), expand=True, read_only=True)
        # multiline = Multiline(size=(120, None), expand=True)
        # multiline = Multiline(size=(120, None), expand=True, read_only=True, read_only_style=True)

        layout = [
            # [ScrollFrame(frame_layout, size=(100, 100), scroll_y=True)],
            # [ScrollFrame(frame_layout, 'test frame', scroll_y=True, border=True, border_mode='inner', title_mode='inner')],
            # [ScrollFrame(frame_layout, 'test frame', scroll_y=True, border=True, border_mode='inner')],
            [ScrollFrame(frame_layout, scroll_y=True)],
            [CheckBox('A', key='A', default=True), CheckBox('B', key='B'), CheckBox('C', key='C')],
            [Image(png_path, callback='popup', size=(150, 150))],
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
            results = window.run().results
        print(f'Results: {results}')


if __name__ == '__main__':
    main()
