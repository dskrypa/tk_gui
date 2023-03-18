"""
Tkinter GUI Clock

:author: Doug Skrypa
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tk_gui.caching import cached_property
from tk_gui.elements.images import ClockImage
from tk_gui.event_handling import event_handler
from tk_gui.styles import Style
from .view import View

if TYPE_CHECKING:
    from tkinter import Event
    from ..typing import XY, Color

__all__ = ['ClockView']


class ClockView(View, config_name='ClockView', title='Clock'):
    def __init__(
        self, img_size: XY = None, fg: Color = '#FF0000', bg: Color = '#000000', seconds: bool = True, **kwargs
    ):
        self._img_size = img_size
        self._last_size = img_size
        self._toggle_slim_on_click = '<Button-2>'
        self._clock_kwargs = {'fg': fg, 'bg': bg, 'seconds': seconds}
        kwargs |= {
            'exit_on_esc': True,
            'grab_anywhere': True,
            'no_title_bar': True,
            'margins': (0, 0),
            'style': Style(bg=bg),
            'alpha_channel': 0.8,
        }
        super().__init__(**kwargs)

    def get_pre_window_layout(self):
        return [[self.gui_image]]

    @cached_property
    def gui_image(self) -> ClockImage:
        kwargs = {'toggle_slim_on_click': self._toggle_slim_on_click, 'pad': (2, 2), **self._clock_kwargs}
        if img_size := self._img_size:
            if monitor := self.get_monitor():
                mon_w, mon_h = monitor.work_area.size
                img_w, img_h = img_size
                img_size = min(mon_w - 60, img_w or 0), min(mon_h - 60, img_h or 0)
            kwargs['img_size'] = img_size
        return ClockImage(**kwargs)

    @event_handler('<Button-3>')
    def toggle_title(self, event: Event):
        self.window.toggle_title_bar()

    @event_handler('<KeyPress-plus>')
    def increase_size(self, event: Event):
        width, height = self.window.size
        self.window.size = (width + 10, height + 10)

    @event_handler('<KeyPress-minus>')
    def decrease_size(self, event: Event):
        image = self.gui_image
        width, height = image.clock.time_size()
        image.resize(width, height - 10)

    @event_handler('SIZE_CHANGED')
    def handle_size_changed(self, event: Event, size: XY):
        if self._last_size == size or not (new_size := self._get_new_size(*size)):
            return
        self._last_size = size
        self.gui_image.resize(*new_size)
        self.window.set_title(self.title)

    def _get_new_size(self, new_w: int, new_h: int) -> XY | None:
        image = self.gui_image
        px, py = image.pad
        new_size = (new_w - px * 2 - 2, new_h - py * 2 - 2)
        new_img_size = image.target_size(*new_size)
        if new_img_size != image.size:
            return new_size
        return None


if __name__ == '__main__':
    ClockView().run()
