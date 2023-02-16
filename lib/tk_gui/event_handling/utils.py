"""
Utilities that are useful for debugging Tkinter / tk_gui GUIs.
"""

from __future__ import annotations

import logging
from functools import partial
from tkinter import TclError, BaseWidget, Misc, Event
from typing import TYPE_CHECKING, Any

from tk_gui.caching import cached_property
from tk_gui.utils import unbind

if TYPE_CHECKING:
    from tk_gui.elements import Element
    from tk_gui.typing import Bool, Color, SupportsBind
    from tk_gui.window import Window

__all__ = ['ClickHighlighter', 'EventWidgetData', 'log_widget_data', 'get_bound_events', 'log_bound_events']
log = logging.getLogger(__name__)


class EventWidgetData:
    def __init__(
        self,
        event: Event,
        widget: BaseWidget | None,
        element: Element | None,
        config: Bool = False,
        attrs: Bool = False,
    ):
        self.widget = widget
        self.element = element
        self.config = config
        self.event = event
        self.attrs = attrs

    @classmethod
    def for_event(cls, window: Window, event: Event, *, parent: Bool = False, config: Bool = False, attrs: Bool = False):
        try:
            widget = event.widget
            if parent:
                widget = widget.nametowidget(widget.winfo_parent())
        except (AttributeError, TclError):
            widget = element = None
        else:
            widget_id = widget._w
            element = window.widget_id_element_map.get(widget_id)

        return cls(event, widget, element, config, attrs)

    @cached_property
    def geometry(self) -> str:
        if widget := self.widget:
            return widget.winfo_geometry()
        return '???'

    @cached_property
    def pack_info(self) -> str | dict[str, Any]:
        try:
            return self.widget.pack_info()  # noqa
        except AttributeError:  # Toplevel does not extend Pack
            return '???'

    @cached_property
    def state(self) -> str:
        if widget := self.widget:
            try:
                return widget['state']
            except TclError:
                pass
        return '???'

    @cached_property
    def config_str(self) -> str:
        if widget := self.widget:
            config = widget.configure()
            return '{\n' + ',\n'.join(f'        {k!r}: {v!r}' for k, v in sorted(config.items())) + '\n}'
        return '???'

    def __str__(self) -> str:
        event, element, widget, state, geometry = self.event, self.element, self.widget, self.state, self.geometry
        lines = ['{', f'    {event=}', f'    {element=}', f'    {widget=}', f'    {state=}, {geometry=}']
        if self.attrs:
            lines.append(f'    {event.__dict__=}')
        if self.config:
            lines.append(f'    config={self.config_str}')
        pack_info = self.pack_info
        lines += [f'    {pack_info=}', '}']
        return '\n'.join(lines)


def log_widget_data(
    window: Window,
    event: Event,
    *,
    parent: Bool = False,
    config: Bool = False,
    attrs: Bool = False,
    prefix: str = 'Event Widget Info',
):
    data = EventWidgetData.for_event(window, event, parent=parent, config=config, attrs=attrs)
    if parent:
        prefix += ' [parent widget]'
    log.info(f'{prefix}: {data}')


class ClickHighlighter:
    """
    Highlights the clicked widget using the specified color while the specified mouse button is down, then restores the
    original color upon button release.  Uses the background, red, and button 1 (left click) by default.
    """
    __slots__ = ('modifier', 'button_num', 'color', 'attr', '_widget_data', '_bind_id')

    def __init__(self, color: Color = '#ff0000', button_num: int = 1, attr: str = 'background', modifier: str = None):
        self.modifier = modifier
        self.button_num = button_num
        self.color = color
        self.attr = attr
        self._widget_data = {}
        self._bind_id = None

    def register(self, supports_bind: SupportsBind):
        self._bind_id = supports_bind.bind(self.press_key, self.on_button_down, add=True)

    def unregister(self, supports_bind: SupportsBind):
        if bind_id := self._bind_id:
            # log.debug(f'Unbinding event={self.press_key!r} with {bind_id=}')
            if isinstance(supports_bind, Misc):
                unbind(supports_bind, self.press_key, bind_id)
            else:
                supports_bind.unbind(self.press_key, bind_id)
            self._bind_id = None

    def _key(self, action: str):
        if modifier := self.modifier:
            return f'<{modifier}-{action}-{self.button_num}>'
        return f'<{action}-{self.button_num}>'

    @property
    def press_key(self) -> str:
        return self._key('ButtonPress')

    @property
    def release_key(self) -> str:
        return self._key('ButtonRelease')

    def on_button_down(self, event: Event):
        try:
            widget: BaseWidget = event.widget
        except (AttributeError, TclError):
            return
        try:
            old_widget_color = widget.configure()[self.attr][-1]
        except KeyError:
            return
        widget.configure(**{self.attr: self.color})
        release_bind_id = widget.bind(self.release_key, partial(self.on_button_release, widget), add=True)
        self._widget_data[widget] = (old_widget_color, release_bind_id)

    def on_button_release(self, widget: BaseWidget, event: Event = None):
        try:
            old_widget_color, release_bind_id = self._widget_data.pop(widget)
        except KeyError:
            return
        widget.configure(**{self.attr: old_widget_color})
        # log_bound_events(widget, 'Before unbind', 14)
        # log.debug(f'Unbinding event={self.release_key!r} with {release_bind_id=}')
        unbind(widget, self.release_key, release_bind_id)
        # log_bound_events(widget, 'After unbind', 13)


def get_bound_events(widget: BaseWidget):
    return {event: list(filter(None, map(str.strip, widget.bind(event).splitlines()))) for event in widget.bind()}


def log_bound_events(widget: BaseWidget, prefix: str = None, color: int | str = None):
    bound_str = '\n'.join(f'  - {e}: {line}' for e, lines in get_bound_events(widget).items() for line in lines)
    intro = f'{prefix}, events' if prefix else 'Events'
    log.debug(f'{intro} bound to {widget=}:\n{bound_str}', extra={'color': color})
