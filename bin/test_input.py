#!/usr/bin/env python

import logging

from cli_command_parser import Command, Action, Counter, Option, main

from tk_gui.__version__ import __author_email__, __version__, __author__, __url__  # noqa
from tk_gui.elements import Text, InteractiveScrollFrame, InteractiveFrame, VerticalSeparator
from tk_gui.elements.choices import Radio, RadioGroup, Combo, ListBox
from tk_gui.elements.bars import ProgressBar, Slider
from tk_gui.elements.buttons import Button, ButtonAction
from tk_gui.elements.rating import Rating
from tk_gui.popups import Popup
from tk_gui.popups.raw import PickFolder, PickColor
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

    @action
    def styles(self):
        choices = [c * 10 for c in map(chr, range(97, 123))]
        with RadioGroup():
            radios = [[Radio(c, disabled=True)] for c in choices]

        toggle_button = Button('Enable Inputs', anchor='c', side='t')
        inputs = [
            Button('Example', disabled=True),
            ListBox(choices, size=(40, 5), disabled=True),
            Combo(choices, size=(40, 10), disabled=True),
            InteractiveScrollFrame(radios, size=(300, 100), scroll_y=True, disabled=True),
        ]

        def toggle_enabled(*args):
            for ele in inputs:
                ele.toggle_enabled()

            act_str = 'Enable' if toggle_button.text == 'Disable Inputs' else 'Disable'
            toggle_button.update(f'{act_str} Inputs')

        toggle_button.callback = toggle_enabled
        layout = [[toggle_button], *([ele] for ele in inputs)]
        results = Window(layout, 'Combo Test', exit_on_esc=True).run().results
        print(f'Results: {results}')

    @action(default=True)
    def state_comparison(self):
        choices = [c * 10 for c in map(chr, range(97, 123))]
        frames = []
        for disabled in (True, False):
            with RadioGroup():
                radios = [[Radio(c, disabled=disabled)] for c in choices]

            elements = [
                Text('Disabled' if disabled else 'Enabled', anchor='c', side='t'),
                Button('Example', disabled=disabled),
                Rating(show_value=True, disabled=disabled),
                Slider(0, 10, tick_interval=1, disabled=disabled),
                ListBox(choices, size=(40, 5), disabled=disabled),
                Combo(choices, size=(40, 10), disabled=disabled),
                InteractiveScrollFrame(radios, size=(300, 100), scroll_y=True, disabled=disabled),
            ]
            frames.append(InteractiveFrame([[ele] for ele in elements], disabled=disabled))

        layout = [[frames[0], VerticalSeparator(), frames[1]]]
        results = Window(layout, 'Input State Comparison', exit_on_esc=True).run().results
        print(f'Results: {results}')


if __name__ == '__main__':
    main()
