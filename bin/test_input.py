#!/usr/bin/env python

import logging
import time

from cli_command_parser import Command, Action, Counter, Option, main

from tk_gui.__version__ import __author_email__, __version__, __author__, __url__  # noqa
from tk_gui.elements import Text, Input, Multiline, Frame, InteractiveScrollFrame, InteractiveFrame, VerticalSeparator
from tk_gui.elements.choices import Radio, RadioGroup, Combo, ListBox, CheckBox
from tk_gui.elements.bars import ProgressBar, Slider
from tk_gui.elements.buttons import Button, EventButton
from tk_gui.elements.element import Interactive
from tk_gui.elements.rating import Rating
from tk_gui.event_handling import button_handler
from tk_gui.popups import Popup
from tk_gui.popups.raw import PickFolder, PickColor
from tk_gui.views.view import View
from tk_gui.window import Window


class GuiInputTest(Command):
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
            # time.sleep(0.3)

    @action
    def progress_view(self):
        ProgressView().run()

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

    @action(default=True)
    def state_comparison(self):
        window = _state_comparison_window()
        results = window.run().results
        print(f'Results: {results}')


# region State Comparison Helpers


def _state_comparison_window():
    row = []
    for n, disabled in enumerate((True, False, True, False)):
        toggleable = n >= 2
        if n:
            row.append(VerticalSeparator())
        elements = list(_prep_input_eles(disabled, not toggleable))
        if toggleable:
            row.append(Frame([[_prep_toggle_button(disabled, elements)], *_labeled(elements)]))
        else:
            row.append(InteractiveFrame(_labeled(elements), disabled=disabled))

    return Window([row], 'Input State Comparison', exit_on_esc=True)


def _prep_input_eles(disabled: bool, include_label: bool = True):
    choices = [c * 10 for c in map(chr, range(97, 123))]
    with RadioGroup():
        radios = [[Radio(c, disabled=disabled)] for c in choices]

    if include_label:
        yield Text('Disabled' if disabled else 'Enabled', anchor='c', side='t')

    yield Button('Example', disabled=disabled)
    yield Input('foo bar', disabled=disabled)
    yield CheckBox('Check Box', disabled=disabled)
    yield Rating(show_value=True, disabled=disabled)
    yield Slider(0, 10, tick_interval=2, disabled=disabled)
    yield ListBox(choices, size=(40, 5), disabled=disabled)
    yield Combo(choices, size=(40, 10), disabled=disabled)
    yield InteractiveScrollFrame(radios, size=(284, 100), scroll_y=True, disabled=disabled)
    yield Multiline('\n'.join(choices), size=(40, 5), disabled=disabled)


def _prep_toggle_button(disabled: bool, elements: list[Interactive]):
    def toggle_all(event=None):
        for ele in elements:
            ele.toggle_enabled()
        button.update('Enable Inputs' if button.text == 'Disable Inputs' else 'Disable Inputs')

    button = Button('Enable Inputs' if disabled else 'Disable Inputs', anchor='c', side='t', cb=toggle_all)
    return button


def _labeled(elements: list[Interactive]):
    for element in elements:
        if (cls_name := element.__class__.__name__) == 'InteractiveScrollFrame':
            cls_name = 'Radio'
        yield [Text(cls_name, size=(10, 1)), element]


# endregion


class ProgressView(View, title='Progress Bar Test View'):
    window_kwargs = {'exit_on_esc': True}
    progress_bar: ProgressBar

    def get_post_window_layout(self):
        self.progress_bar = ProgressBar(100)
        yield [Text('Processing...')]
        yield [self.progress_bar]
        yield [EventButton('Run', key='run')]

    @button_handler('run')
    def run_progress_test(self, event, key=None):
        # for _ in self.progress_bar(range(99), True):
        for _ in self.progress_bar(range(99)):
            # window._root.after(50, window.interrupt)
            time.sleep(0.3)


if __name__ == '__main__':
    main()
