#!/usr/bin/env python

import logging

from cli_command_parser import Command, Action, Counter, Option, main

from tk_gui.__version__ import __author_email__, __version__, __author__, __url__  # noqa
from tk_gui.images.icons import Icons
from tk_gui.images.utils import ICONS_DIR
from tk_gui.popups import ImagePopup, AnimatedPopup, SpinnerPopup, ClockPopup, BasicPopup
from tk_gui.popups.about import AboutPopup
from tk_gui.popups.basic_prompts import TextPromptPopup, LoginPromptPopup
from tk_gui.popups.choices import ChooseImagePopup, choose_item
from tk_gui.popups.common import popup_warning, popup_error, popup_yes_no, popup_no_yes, popup_ok
from tk_gui.popups.style import StylePopup


class GuiPopupTest(Command):
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
        SpinnerPopup(img_size=(400, 400), bind_esc=True).run()

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

    @action
    def popup_img_choice(self):
        icons = Icons(500)
        items = {name: icons.draw(name) for name in tuple(icons.char_names)[:10]}
        # items = {name: ICONS_DIR.joinpath(name) for name in ('exclamation-triangle-yellow.png', 'search.png')}
        result = ChooseImagePopup.with_auto_prompt(items, img_title_fmt='Example image: {title}').run()
        print(f'{result=}')

    @action
    def popup_choice(self):
        items = [f'Letter: {c}' for c in 'abcdefghijklmnopqrstuvwxyz']
        result = choose_item(items, item_name='Letter')
        print(f'{result=}')


if __name__ == '__main__':
    main()
