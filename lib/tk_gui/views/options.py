"""
View generated to manage gui options
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .view import View

if TYPE_CHECKING:
    from tk_gui.options import GuiOptions

__all__ = ['GuiOptionsView']


class GuiOptionsView(View, title='Options', primary=False):
    window_kwargs = {'exit_on_esc': True}

    def __init__(self, gui_options: GuiOptions, **kwargs):
        super().__init__(**kwargs)
        self.gui_options = gui_options

    def get_pre_window_layout(self):
        return self.gui_options.layout()

    def run(self):
        data = super().run()
        return self.gui_options.parse(data)  # noqa
