"""

"""

from __future__ import annotations

import logging
from tkinter import TclError, BaseWidget, Event
from typing import TYPE_CHECKING, Any

from tk_gui.caching import cached_property

if TYPE_CHECKING:
    from tk_gui.elements import Element
    from tk_gui.typing import Bool
    from tk_gui.window import Window

__all__ = ['EventWidgetData', 'log_widget_data']
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
    log.info(f'{prefix}: {data}')
