"""
Widget-related utilities.
"""

from __future__ import annotations

import logging
from tkinter import BaseWidget, Misc, Event, TclError, Entry, Text, Tk
from tkinter.ttk import Style
from typing import TYPE_CHECKING, Any, Collection, Literal, Iterator, Mapping, Callable, Sequence

from tk_gui.caching import cached_property

if TYPE_CHECKING:
    from tk_gui.elements import Element
    from tk_gui.typing import Bool, SelectionPos, Top, XY
    from tk_gui.window import Window

__all__ = [
    'get_parent_or_none', 'get_root_widget', 'get_widget_ancestor', 'find_descendants',
    'unbind', 'get_bound_events', 'log_bound_events',
    'get_config_str', 'log_config_str', 'WidgetData', 'log_event_widget_data', 'log_widget_data',
    'get_selection_pos', 'get_size_and_pos', 'get_req_size',
]
log = logging.getLogger(__name__)

ShowKey = Literal['config', 'event_attrs', 'event', 'element', 'pack_info', 'get_result', 'ttk_info']
ShowMap = dict[ShowKey, 'Bool']


# region Widget Ancestors & Descendants


def get_parent_or_none(widget: BaseWidget) -> BaseWidget | None:
    # if (parent_name := widget.winfo_parent()) == '.':
    #     return None
    # return widget.nametowidget(parent_name)
    parent_parts = widget._w.split('.!')[:-1]  # noqa
    if len(parent_parts) < 2:
        return None
    return widget.nametowidget('.!'.join(parent_parts))


def get_root_widget(widget: BaseWidget | Misc | Top | Tk) -> Top | Tk:
    """
    Return the top-level widget that contains the given widget.  This function is necessary because
    :meth:`python:tkinter.Misc.winfo_toplevel` does not always return the true root widget.
    """
    w_id: str = widget._w  # noqa
    root_id = '.!'.join(w_id.split('.!')[:2])
    if root_id == w_id:
        return widget
    return widget.nametowidget(root_id)


def get_widget_ancestor(widget: BaseWidget, level: int = 1, permissive: Bool = True) -> BaseWidget:
    if level < 1:
        if permissive:
            return widget
        raise ValueError(f'Invalid {level=} for {widget=} - must be greater than 0')

    parts = widget._w.split('.!')  # noqa
    ancestor_parts = parts[:-level]
    if len(ancestor_parts) < 2:
        if not permissive:
            raise ValueError(f'Invalid {level=} for {widget=} - it only has {len(parts) - 2} ancestors')
        ancestor_parts = parts[:2]

    return widget.nametowidget('.!'.join(ancestor_parts))


# def get_widget_ancestor(widget: BaseWidget, level: int = 1, permissive: Bool = True) -> BaseWidget:
#     while level > 0:
#         try:
#             widget = widget.nametowidget(widget.winfo_parent())
#         except (AttributeError, TclError):
#             if permissive:
#                 return widget
#             else:
#                 raise
#         level -= 1
#
#     return widget


def find_descendants(widget: BaseWidget) -> Iterator[BaseWidget]:
    for child in widget.children.values():
        yield child
        yield from find_descendants(child)


# endregion


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
        show_get_result: Bool = True,
        show_ttk_info: Bool = False,
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
            'get_result': show_get_result,
            'ttk_info': show_ttk_info,
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
    def for_event(
        cls, window: Window | None, event: Event, *, parent: Bool = False, widget: BaseWidget = None, **kwargs
    ):
        if widget is None:
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
        except (AttributeError, TclError):  # Toplevel does not extend Pack
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
    def _config(self):
        return self.widget.configure()

    @cached_property
    def config_str(self) -> str:
        if self.widget:
            return _mapping_repr(self._config, self.config_keys, indent=4)
        return '???'

    @cached_property
    def event_attrs(self) -> str:
        data = self.event.__dict__
        if self.hide_event_unset:
            return '<{}>'.format(', '.join(f'{k}={v!r}' for k, v in data.items() if v != '??'))
        return _mapping_repr(data, indent=4)

    @cached_property
    def get_result(self) -> str:
        if widget := self.widget:
            try:
                return repr(widget.get())  # noqa
            except (AttributeError, TclError, TypeError):
                pass
        return '???'

    @cached_property
    def ttk_info(self) -> str:
        if widget := self.widget:
            widget_config = self._config
            try:
                style_name = widget_config['style'][-1] or widget.winfo_class()
            except Exception:  # noqa
                style_name = widget.winfo_class()

            style = Style()
            try:
                layout = style.layout(style_name)
            except TclError:
                return '???'
            elements = dict(_get_style_details(style, style_name, layout, indent=8))
            data = {
                'style_name': repr(style_name),
                'style_config': style.configure(style_name),
                'style_layout': _sequence_repr(layout, indent=8) if layout else layout,
                'elements': _mapping_repr(elements, val_repr=str, indent=8),
            }
            return _mapping_repr(data, val_repr=str, indent=4, sort=False)
        return '???'

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
        if show['get_result']:
            yield f'    get_result={self.get_result}'
        if show['ttk_info']:
            yield f'    ttk_info={self.ttk_info}'
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


def get_size_and_pos(widget: Misc) -> tuple[int, int, int, int]:
    size, x, y = widget.winfo_geometry().split('+', 2)
    w, h = size.split('x', 1)
    return int(w), int(h), int(x), int(y)


def get_req_size(widget: Misc) -> XY:
    w_id: str = widget._w  # noqa
    call = widget.tk.call
    width = int(call('winfo', 'reqwidth', w_id))
    height = int(call('winfo', 'reqheight', w_id))
    return width, height


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
    widget_config = widget.configure()
    try:
        style_name = widget_config['style'][-1] or widget.winfo_class()
    except Exception:  # noqa
        style_name = widget.winfo_class()

    print(f'Ttk info for {widget=}:')
    print('  - Config:')
    for key, val in sorted(widget_config.items()):
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


def _get_style_details(style, name, layout, indent: int = 0):
    states = (None, 'active', 'alternate', 'disabled', 'pressed', 'selected', 'readonly')
    for element_name, data in layout:
        options = {
            opt: {state or 'default': style.lookup(name, opt, [state] if state else None) for state in states}
            for opt in style.element_options(element_name)
        }
        options_str = _mapping_repr(options, indent=indent + 8)
        ele_str = _mapping_repr({'layout': repr(data), 'options': options_str}, indent=indent + 4, val_repr=str)
        yield element_name, ele_str

        for key, value in data.items():
            if not isinstance(value, str):
                yield from _get_style_details(style, name, value, indent)


# endregion


def get_selection_pos(widget: Entry | Text, raw: Bool = False) -> SelectionPos:
    try:
        first, last = widget.index('sel.first'), widget.index('sel.last')
    except (AttributeError, TclError):
        return None, None
    if raw:
        return first, last
    try:
        return int(first), int(last)
    except ValueError:
        pass
    first_line, first_index = map(int, first.split('.', 1))
    last_line, last_index = map(int, last.split('.', 1))
    return (first_line, first_index), (last_line, last_index)


def _mapping_repr(
    data: Mapping,
    keys: Collection[str] = None,
    sort: Bool = True,
    indent: int = 0,
    val_repr: Callable[[Any], str] = repr,
) -> str:
    if keys:
        kv_pairs = (kv for kv in data.items() if kv[0] in keys)
    else:
        kv_pairs = data.items()
    if sort:
        kv_pairs = sorted(kv_pairs)

    inner = ' ' * (indent + 4)
    outer = ' ' * indent
    return '{\n' + ',\n'.join(f'{inner}{k!r}: {val_repr(v)}' for k, v in kv_pairs) + f'\n{outer}}}'


def _sequence_repr(data: Sequence, sort: Bool = False, indent: int = 0, val_repr: Callable[[Any], str] = repr) -> str:
    if sort:
        data = sorted(data)
    inner = ' ' * (indent + 4)
    outer = ' ' * indent
    return '[\n' + ',\n'.join(f'{inner}{val_repr(v)}' for v in data) + f'\n{outer}]'
