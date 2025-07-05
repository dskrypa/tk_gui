#!/usr/bin/env python

import logging
import time

from cli_command_parser import Command, Action, Counter, main

from tk_gui.images.icons import Icons, ICONS_DIR
from tk_gui.popups import ImagePopup, AnimatedPopup, SpinnerPopup, ClockPopup, BasicPopup
from tk_gui.popups.about import AboutPopup
from tk_gui.popups.basic_prompts import TextPromptPopup, LoginPromptPopup
from tk_gui.popups.choices import ChooseImagePopup, choose_item
from tk_gui.popups.common import popup_warning, popup_error, popup_yes_no, popup_no_yes, popup_ok
from tk_gui.popups.paths import PathPopup, SaveAs, PickFile, PickFiles, PickDirectory, PickDirectories
from tk_gui.popups.style import StylePopup
from tk_gui.utils import tcl_version

log = logging.getLogger(__name__)


class GuiPopupTest(Command):
    action = Action(help='The test to perform')
    verbose = Counter('-v', default=2, help='Increase logging verbosity (can specify multiple times)')

    def _init_command_(self):
        logging.getLogger('PIL.PngImagePlugin').setLevel(50)
        try:
            from ds_tools.logging import init_logging, ENTRY_FMT_DETAILED
        except ImportError:
            log_fmt = '%(asctime)s %(levelname)s %(name)s %(lineno)d %(message)s' if self.verbose > 1 else '%(message)s'
            logging.basicConfig(level=logging.DEBUG if self.verbose else logging.INFO, format=log_fmt)
        else:
            init_logging(self.verbose, log_path=None, names=None, entry_fmt=ENTRY_FMT_DETAILED, millis=True)

        log.debug(f'Popup Test using tcl version: {tcl_version()}')

    @action
    def about(self):
        AboutPopup().run()

    @action
    def basic(self):
        # results = BasicPopup('This is a test', title='Test', buttons=('OK',)).run()
        results = BasicPopup('This is a test', title='Test', buttons=('Cancel', 'OK'), bind_esc=True).run()
        # results = BasicPopup('This is a test with more words', title='Test', buttons=('Cancel', 'Test', 'OK')).run()
        print(results)

    # region Image Popups

    @action
    def spinner(self):
        # SpinnerPopup(img_size=(400, 400), bind_esc=True).run()
        SpinnerPopup(img_size=(400, 400), bind_esc=True, no_title_bar=False).run()

    @action
    def spinner_thread(self):
        spinner = SpinnerPopup(img_size=(400, 400), bind_esc=True)
        spinner.run_task_in_thread(time.sleep, (10,))

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
    def style(self):
        results = StylePopup(show_buttons=True).run()
        print(f'{results=}')

    @action
    def multiline(self):
        filler = 'the quick brown fox jumped over the lazy dog'
        popup_ok(f'{filler}\n{filler}')

    @action
    def warning(self):
        popup_warning('This is a test warning!')

    @action
    def error(self):
        popup_error('This is a test error!')

    @action
    def yes_no(self):
        result = popup_yes_no('This is a test!')
        print(f'{result=}')

    @action
    def no_yes(self):
        result = popup_no_yes('This is a test!')
        print(f'{result=}')

    @action
    def ok(self):
        popup_ok('This is a test!')

    @action
    def text(self):
        result = TextPromptPopup('Enter a string').run()
        print(f'{result=}')

    @action
    def text_cancel(self):
        result = TextPromptPopup('Enter a string', cancel_text='Cancel', bind_esc=True).run()
        print(f'{result=}')

    @action
    def login(self):
        user, pw = LoginPromptPopup('Enter your login info', cancel_text='Cancel').run()
        print(f'{user=}, {pw=}')

    @action
    def image_choices(self):
        icons = Icons(500)
        items = {name: icons.draw(name) for name in tuple(icons.char_names)[:10]}
        # items = {name: ICONS_DIR.joinpath(name) for name in ('exclamation-triangle-yellow.png', 'search.png')}
        result = ChooseImagePopup.with_auto_prompt(items, img_title_fmt='Example image: {title}').run()
        print(f'{result=}')

    @action
    def choices(self):
        items = [f'Letter: {c}' for c in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ']
        result = choose_item(items, item_name='Letter')
        print(f'{result=}')

    @action
    def pick_paths(self):
        result = PathPopup(multiple=True).run()
        print(f'{result=}')

    @action
    def pick_file(self):
        result = PickFile().run()
        print(f'{result=}')

    @action
    def pick_files(self):
        result = PickFiles().run()
        print(f'{result=}')

    @action
    def pick_dir(self):
        result = PickDirectory().run()
        print(f'{result=}')

    @action
    def pick_dirs(self):
        result = PickDirectories().run()
        print(f'{result=}')

    @action
    def save_as(self):
        # result = SaveAs(style='SystemDefault').run()
        result = SaveAs(default_ext='.txt').run()
        # result = RawSaveAs().run()
        print(f'{result=}')


if __name__ == '__main__':
    main()
