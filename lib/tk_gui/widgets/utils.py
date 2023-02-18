"""
Widget-related utilities.
"""

from __future__ import annotations

import logging
from tkinter import BaseWidget, Misc, Event, TclError
from typing import TYPE_CHECKING, Any, Collection, Literal, Iterator, Mapping

from tk_gui.caching import cached_property

if TYPE_CHECKING:
    from tk_gui.elements import Element
    from tk_gui.typing import Bool
    from tk_gui.window import Window

__all__ = [
    'unbind', 'get_bound_events', 'log_bound_events',
    'get_config_str', 'log_config_str', 'WidgetData', 'log_event_widget_data', 'log_widget_data',
]
log = logging.getLogger(__name__)

ShowKey = Literal['config', 'event_attrs', 'event', 'element', 'pack_info']
ShowMap = dict[ShowKey, 'Bool']


# region Bind / Unbind / Bound Events


def unbind(widget: Misc, sequence: str, func_id: str = None):
    """
    Unbind for the specified widget for event ``sequence`` the function identified with ``func_id``.  If no ``func_id``
    is specified, then unbind all functions for event ``sequence``.

    Based on: https://github.com/python/cpython/issues/75666
    """
    widget_id = widget._w  # noqa
    if func_id:
        widget.deletecommand(func_id)
        funcs = widget.tk.call('bind', widget_id, sequence, None).split('\n')  # noqa
        skip = f'if {{"[{func_id}'
        bound = '\n'.join(f for f in funcs if not f.startswith(skip))
    else:
        bound = ''
    widget.tk.call('bind', widget_id, sequence, bound)


def get_bound_events(widget: Misc):
    return {event: list(filter(None, map(str.strip, widget.bind(event).splitlines()))) for event in widget.bind()}


def log_bound_events(widget: Misc, prefix: str = None, color: int | str = None, level: int = logging.DEBUG):
    bound_str = '\n'.join(f'  - {e}: {line}' for e, lines in get_bound_events(widget).items() for line in lines)
    intro = f'{prefix}, events' if prefix else 'Events'
    log.log(level, f'{intro} bound to {widget=}:\n{bound_str}', extra={'color': color})


# endregion


# region Widget Data


class WidgetData:
    show: ShowMap

    def __init__(
        self,
        widget: BaseWidget | None,
        element: Element | None = None,
        event: Event | None = None,
        *,
        config_keys: Collection[str] = None,
        show_config: Bool = False,
        show_event_attrs: Bool = False,
        show_element: Bool = None,
        show_event: Bool = None,
        show_pack_info: Bool = True,
        hide_event_unset: Bool = True,
    ):
        self.widget = widget
        self.element = element
        self.event = event
        self.config_keys = config_keys
        self.hide_event_unset = hide_event_unset
        self.show: ShowMap = {
            'config': show_config,
            'event_attrs': show_event_attrs,
            'event': (event is not None) if show_event is None else show_event,
            'element': (element is not None) if show_element is None else show_element,
            'pack_info': show_pack_info,
        }

    @classmethod
    def for_widget(cls, window: Window | None, widget: BaseWidget, *, parent: Bool = False, **kwargs):
        if parent:
            try:
                widget = widget.nametowidget(widget.winfo_parent())
            except (AttributeError, TclError):
                widget = None

        if widget and window:
            widget_id = widget._w  # noqa
            element = window.widget_id_element_map.get(widget_id)
        else:
            element = None

        return cls(widget, element, **kwargs)

    @classmethod
    def for_event(cls, window: Window | None, event: Event, *, parent: Bool = False, **kwargs):
        try:
            widget = event.widget
        except (AttributeError, TclError):
            widget = None
        return cls.for_widget(window, widget, event=event, parent=parent, **kwargs)

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
            return get_config_str(widget, self.config_keys)
        return '???'

    @cached_property
    def event_attrs(self) -> str:
        data = self.event.__dict__
        if self.hide_event_unset:
            return '<{}>'.format(', '.join(f'{k}={v!r}' for k, v in data.items() if v != '??'))
        return _mapping_repr(data)

    def __iter__(self) -> Iterator[str]:
        show, widget, state, geometry = self.show, self.widget, self.state, self.geometry
        yield '{'
        if show['event']:
            yield f'    event={self.event!r}'
        if show['event_attrs']:
            yield f'    event.__dict__={self.event_attrs}'
        if show['element']:
            yield f'    element={self.element!r}'
        yield f'    {widget=}'
        yield f'    {state=}, {geometry=}'
        if show['config']:
            yield f'    config={self.config_str}'
        if show['pack_info']:
            yield f'    pack_info={self.pack_info!r}'
        yield '}'

    def __str__(self) -> str:
        return '\n'.join(self)

    def log(self, prefix: str = '', level: int = logging.DEBUG):
        log.log(level, f'{prefix}{self}')


def log_event_widget_data(
    window: Window | None,
    event: Event,
    *,
    parent: Bool = False,
    show_config: Bool = False,
    show_event_attrs: Bool = False,
    prefix: str = 'Event Widget Info',
    level: int = logging.INFO,
    **kwargs,
):
    data = WidgetData.for_event(
        window, event, parent=parent, show_config=show_config, show_event_attrs=show_event_attrs, **kwargs
    )
    if parent:
        prefix += ' [parent widget]'
    data.log(prefix + ': ', level=level)


def log_widget_data(
    window: Window | None,
    widget: BaseWidget,
    *,
    parent: Bool = False,
    prefix: str = None,
    level: int = logging.DEBUG,
    **kwargs,
):
    data = WidgetData.for_widget(window, widget, parent=parent, **kwargs)
    if prefix and parent:
        prefix += ' [parent widget]'
    elif prefix is None:
        prefix = 'Parent Widget Info' if parent else 'Widget Info'
    data.log(prefix + ': ', level=level)


# endregion


# region Config Info


def get_config_str(widget: Misc, keys: Collection[str] = None) -> str:
    return _mapping_repr(widget.configure(), keys)


def log_config_str(widget: Misc, prefix: str = '', keys: Collection[str] = None, level: int = logging.DEBUG):
    log.log(level, f'{prefix}{widget!r} config={get_config_str(widget, keys)}')


# endregion


# region Ttk Widget / Style Info


def _iter_ele_names(layout):
    for name, data in layout:
        yield name
        for key, value in data.items():
            if not isinstance(value, str):
                yield from _iter_ele_names(value)


def dump_ttk_widget_info(widget: BaseWidget):
    """
    Print info about the given ttk widget and its style.

    Based on documentation:
    https://www.tcl.tk/man/tcl/TkCmd/ttk_widget.html
    https://www.tcl.tk/man/tcl/TkCmd/ttk_style.html
    https://stackoverflow.com/q/45389166/19070573
    """
    from tkinter.ttk import Style

    config = widget.configure()
    try:
        style_name = config['style'][-1] or widget.winfo_class()
    except Exception:  # noqa
        style_name = widget.winfo_class()

    print(f'Ttk info for {widget=}:')
    print('  - Config:')
    for key, val in sorted(config.items()):
        print(f'     - {key}: {val!r}')

    style = Style()
    layout = style.layout(style_name)
    print(f'  - Style {style_name!r} options:')
    print(f'     - Config: {style.configure(style_name)}')
    print(f'     - Base Layout: {layout}')
    _print_style_details(style, style_name, layout)


def _print_style_details(style, style_name, layout):
    for element_name, data in layout:
        print(f'     - {element_name}:')
        print(f'        - Layout: {data}')
        print(f'        - Options:')
        for option in style.element_options(element_name):
            values = {
                state or 'default': style.lookup(style_name, option, [state] if state else None)
                for state in (None, 'active', 'alternate', 'disabled', 'pressed', 'selected', 'readonly')
            }
            print(f'           - {option}: {values}')

        for key, value in data.items():
            if not isinstance(value, str):
                _print_style_details(style, style_name, value)


# endregion


def _mapping_repr(data: Mapping, keys: Collection[str] = None, sort: Bool = True) -> str:
    if keys:
        kv_pairs = (kv for kv in data.items() if kv[0] in keys)
    else:
        kv_pairs = data.items()
    if sort:
        kv_pairs = sorted(kv_pairs)
    return '{\n' + ',\n'.join(f'        {k!r}: {v!r}' for k, v in kv_pairs) + '\n}'
