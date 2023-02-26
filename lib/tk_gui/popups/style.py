"""
Tkinter GUI popup: Style

:author: Doug Skrypa
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Optional

from ..elements import Text, HorizontalSeparator, Combo, Button, Label
from ..images.color import pick_fg
from ..styles import Style, StyleSpec, STATE_NAMES
from .base import Popup

if TYPE_CHECKING:
    from tkinter import Event
    from ..typing import Layout

__all__ = ['StylePopup']


class StylePopup(Popup):
    def __init__(self, show_style: StyleSpec = None, show_buttons: bool = False, **kwargs):
        kwargs.setdefault('bind_esc', True)
        kwargs.setdefault('scroll_y', True)
        kwargs.setdefault('title', 'Style')
        kwargs.setdefault('style', show_style)
        kwargs['show'] = False
        super().__init__(**kwargs)
        self.show_style = Style.get_style(show_style)
        self._selected_style = None
        self._show_buttons = show_buttons

    # region Layout

    def get_pre_window_layout(self) -> Layout:
        style = self.show_style
        if parent := style.parent:
            def parent_cb(event=None):
                self.__class__(parent).run()

            parent_kwargs = {'value': parent.name, 'link': parent_cb, 'tooltip': f'View style: {parent.name}'}
        else:
            parent_kwargs = {}

        yield [
            Label('Style:', size=(10, 1), anchor='e'),
            Combo(Style.style_names(), style.name, callback=self._style_selected),
            Button('Select', key='select', visible=self._show_buttons),
            Button('Cancel', key='cancel', visible=self._show_buttons),
        ]
        yield [Label('Parent:', size=(10, 1), anchor='e'), Text(**parent_kwargs)]
        yield [Label('TTK Theme:', size=(10, 1), anchor='e'), Text(style.ttk_theme)]

    def get_post_window_layout(self) -> Layout:
        style = self.window.style
        styles = {}
        text_keys = {'font', 'border_width', 'arrow_width', 'bar_width'}
        state_nums = range(len(STATE_NAMES))
        name_style = style.sub_style(text_font=style.text.sub_font('default', None, None, 'bold'))
        header_style = style.sub_style(text_font=style.text.sub_font('default', None, None, 'bold', 'underline'))

        IText = partial(Text, size=(15, 1), justify='c')
        HText = partial(Text, size=(15, 1), justify='c', style=header_style)

        for name, layer in self.show_style.iter_layers():
            if not (layer_vals := layer.as_dict(False)):
                continue

            yield [HorizontalSeparator()]
            yield [Label('Layer:', size=(10, 1)), Text(name, style=name_style)]
            yield [HText('field'), *(HText(state) for state in STATE_NAMES)]

            for key, values in layer_vals.items():
                row = [IText(key)]
                if key in text_keys:
                    row.extend(IText(values[state]) for state in state_nums)
                    yield row
                else:
                    for state in state_nums:
                        color = values[state]
                        try:
                            ele_style = styles[color]
                        except KeyError:
                            styles[color] = ele_style = style.sub_style(color, text_bg=color, text_fg=pick_fg(color))

                        row.append(IText(color, style=ele_style))

                    yield row

    # endregion

    # region Run & Results

    def _run(self):
        with self.finalize_window()(take_focus=True) as window:
            window.run()
            if style := self._selected_style:
                popup = self.__class__(style, show_buttons=self._show_buttons)
            else:
                return self.get_results()
        return popup._run()

    def get_results(self) -> Optional[str]:
        results = super().get_results()
        if (style_name := self._selected_style) and results['select']:
            return style_name
        return None

    # endregion

    def _style_selected(self, event: Event):
        if (choice := event.widget.get()) != self.show_style.name:
            self._selected_style = choice
            self.window.interrupt()
