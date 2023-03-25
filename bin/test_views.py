#!/usr/bin/env python

import logging
from pathlib import Path

from cli_command_parser import Command, Action, Counter, Option, main

from tk_gui.__version__ import __author_email__, __version__, __author__, __url__  # noqa
from tk_gui.elements import Input, Text
from tk_gui.elements.buttons import Button, ButtonAction
from tk_gui.elements.menu.menu import Menu, MenuGroup, MenuItem, MenuProperty
from tk_gui.elements.menu.items import CopySelection, PasteClipboard
from tk_gui.elements.menu.items import ToUpperCase, ToTitleCase, ToLowerCase
from tk_gui.elements.menu.items import CloseWindow
from tk_gui.event_handling import button_handler
from tk_gui.options import GuiOptions, BoolOption, PopupOption, DirectoryOption, SubmitOption
from tk_gui.popups.about import AboutPopup
from tk_gui.popups.common import popup_ok
from tk_gui.popups.raw import PickFile, pick_folder_popup
from tk_gui.popups.style import StylePopup
from tk_gui.views.view import View


class BaseRightClickMenu(Menu):
    MenuItem('Test A', print)
    CopySelection()
    PasteClipboard()
    with MenuGroup('Update'):
        ToLowerCase()
        ToUpperCase()
        ToTitleCase()


class GuiViewTest(Command):
    action = Action(help='The test to perform')
    verbose = Counter('-v', default=2, help='Increase logging verbosity (can specify multiple times)')
    color = Option('-c', help='The initial color to display when action=pick_color')

    def _init_command_(self):
        logging.getLogger('PIL.PngImagePlugin').setLevel(50)
        try:
            from ds_tools.logging import init_logging
        except ImportError:
            log_fmt = '%(asctime)s %(levelname)s %(name)s %(lineno)d %(message)s' if self.verbose > 1 else '%(message)s'
            level = logging.DEBUG if self.verbose else logging.INFO
            logging.basicConfig(level=level, format=log_fmt)
        else:
            init_logging(self.verbose, log_path=None, names=None)

    @action
    def misc(self):
        MiscTestView().run()

    @action
    def dir_chain(self):
        DirChainView.run_all()


class MenuBar(Menu):
    with MenuGroup('File'):
        MenuItem('Select File')
        MenuItem('Settings')
        CloseWindow()
    with MenuGroup('Help'):
        MenuItem('About', AboutPopup)


class MiscTestView(View, title='Misc Test View'):
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
        kwargs = {'label_size': (16, 1), 'size': (30, None)}
        style_kwargs = {'popup_kwargs': {'show_buttons': True}} | kwargs
        layout = [
            [
                BoolOption('remember_pos', 'Remember Last Window Position', config.remember_position),
                BoolOption('remember_size', 'Remember Last Window Size', config.remember_size),
            ],
            [PopupOption('style', 'Style', StylePopup, default=config.style, **style_kwargs)],
            [DirectoryOption('output_dir', 'Output Directory', **kwargs)],
            [SubmitOption(label='Save')],
        ]
        results = GuiOptions(layout).run_popup()
        if results.pop('save', False):
            config.update(results, ignore_none=True, ignore_empty=True)
        return results

    def get_pre_window_layout(self):
        yield [self.menu]

    def get_post_window_layout(self):
        BE = ButtonAction.BIND_EVENT
        yield [Input(key='test_input', size=(40, 1))]
        yield [Button('A', key='A', action=BE), Button('B', key='B', action=BE)]

    @button_handler('A', 'B')
    def handle_button_clicked(self, event, key):
        popup_ok(f'You clicked the button with {key=}: {event}')


class DirChainView(View, title='Directory Chain Test View'):
    window_kwargs = {'exit_on_esc': True, 'right_click_menu': BaseRightClickMenu()}

    def __init__(self, path: Path = None, **kwargs):
        super().__init__(**kwargs)
        self.path = path

    def get_post_window_layout(self):
        path_str = self.path.as_posix() if self.path else 'N/A'
        yield [Text(f'Current path: {path_str}', size=(40, 1))]
        yield [Button('Open...', key='open', action=ButtonAction.BIND_EVENT)]

    @button_handler('open')
    def pick_next_dir(self, event, key=None):
        init_dir = self.path.parent if self.path else None
        if path := pick_folder_popup(init_dir, 'Pick A Directory', parent=self.window):
            return self.go_to_next_view(self.as_view_spec(path))
        return None


if __name__ == '__main__':
    main()
