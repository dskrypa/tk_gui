"""
GUI styles / themes

:author: Doug Skrypa
"""

from __future__ import annotations

# import logging
from itertools import count
from tkinter.font import Font as TkFont
from tkinter.ttk import Style as TtkStyle
from typing import TYPE_CHECKING, Union, Optional, Iterator

from tk_gui.caching import ClearableCachedPropertyMixin, cached_property
from tk_gui.enums import StyleState
from .layers import StyleLayer, StyleProperty, StyleLayerProperty

if TYPE_CHECKING:
    from tk_gui.typing import XY
    from .states import StateValues
    from .typing import StyleStateVal, Layer, StyleOptions, StyleSpec, FinalValue

__all__ = ['Style']
# log = logging.getLogger(__name__)

_NotSet = object()


class Style(ClearableCachedPropertyMixin):
    _count = count()
    _ttk_count = count()
    _layers: set[str] = set()                       # The names of all defined StyleLayerProperties
    _instances: dict[str, Style] = {}
    default_style: Optional[Style] = None

    name: str
    parent: Optional[Style]

    ttk_theme: Optional[str] = StyleProperty()

    base = StyleLayerProperty()

    arrows = StyleLayerProperty()                   # Arrows on forms, such as combo boxes
    button = StyleLayerProperty('base')
    checkbox = StyleLayerProperty('base')
    checkbox_label = StyleLayerProperty('base')
    combo = StyleLayerProperty('text')              # Combo box (dropdown) input
    frame = StyleLayerProperty('base')
    image = StyleLayerProperty('base')
    input = StyleLayerProperty('text')
    insert = StyleLayerProperty()
    link = StyleLayerProperty('text')               # Hyperlinks
    listbox = StyleLayerProperty('input')
    menu = StyleLayerProperty('base')
    progress = StyleLayerProperty('base')           # Progress bars
    radio = StyleLayerProperty('base')
    scroll = StyleLayerProperty()
    selected = StyleLayerProperty('base')           # Used in the choices, table, and scroll modules
    separator = StyleLayerProperty('base')          # Vertical / horizontal separator lines
    slider = StyleLayerProperty('base')
    table = StyleLayerProperty('base')              # Table elements
    table_alt = StyleLayerProperty('table')         # Alternate / even rows in tables
    table_header = StyleLayerProperty('table')      # Table headers
    text = StyleLayerProperty('base')
    tooltip = StyleLayerProperty('base')

    def __init__(self, name: str = None, *, parent: Union[str, Style] = None, ttk_theme: str = None, **kwargs):
        if not name:  # Anonymous styles won't be stored
            name = f'{self.__class__.__name__}#{next(self._count)}'
        else:
            self._instances[name] = self

        self.name = name
        self.parent = self._instances.get(parent, parent)
        self.ttk_theme = ttk_theme
        self._configure(kwargs)

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}[{self.name!r}, parent={self.parent.name if self.parent else None}]>'

    @classmethod
    def style_names(cls) -> list[str]:
        return [name for name in cls._instances if name and not name.startswith('_')]

    @cached_property
    def _family(self) -> set[Style]:
        ancestors = {self}
        style = self
        while style := style.parent:
            ancestors.add(style)
        return ancestors

    def __getitem__(self, layer_name: str) -> StyleLayer:
        if layer_name in self._layers:
            return getattr(self, layer_name)
        raise KeyError(layer_name)

    # region Configuration / Init

    def _configure(self, kwargs: StyleOptions):
        layers = {}
        layer_keys, layer_fields = self._layers, StyleLayer._fields
        for key, val in kwargs.items():
            if key in layer_keys:
                # log.info(f'{self}: Full layer configuration provided: {key}={val!r}', extra={'color': 11})
                setattr(self, key, val)
            elif key in layer_fields:
                layers.setdefault('base', {})[key] = val
            else:
                layer, attr = self._split_config_key(key)  # attr should be an attribute in StyleLayer
                # log.debug(f'{self}: in {layer=}, setting {attr} = {val!r}')
                layers.setdefault(layer, {})[attr] = val

        # log.info(f'{self}: Built layers: {layers!r}', extra={'color': 11})
        for name, layer in layers.items():
            setattr(self, name, layer)

    def _split_config_key(self, key: str) -> tuple[str, str]:
        for delim in '_.':
            try:
                layer, attr = key.split(delim, 1)
            except ValueError:
                continue
            else:
                if layer in self._layers and attr in StyleLayer._fields:
                    return layer, attr

        for layer_name, suffix_idx, delim_idx in self._compound_layer_names():
            if key.startswith(layer_name) and len(key) > suffix_idx and key[delim_idx] in '_.':
                if (attr := key[suffix_idx:]) in StyleLayer._fields:
                    # log.debug(f'Found layer={layer_name!r} for {attr=}')
                    return layer_name, attr

        raise KeyError(f'Invalid style option: {key!r}')

    @classmethod
    def _compound_layer_names(cls) -> list[tuple[str, int, int]]:
        try:
            return cls.__compound_layer_names  # noqa
        except AttributeError:
            names_and_lens = ((name, len(name)) for name in cls._layers if '_' in name)
            cls.__compound_layer_names = names = [(n, ln + 1, ln) for n, ln in names_and_lens]
            return names

    @classmethod
    def get_style(cls, style: StyleSpec) -> Style:
        if not style:
            return cls.default_style
        elif isinstance(style, cls):
            return style
        elif isinstance(style, str):
            return cls._instances[style]
        try:
            return cls(**style)
        except TypeError:
            pass
        try:
            name, kwargs = style
        except (ValueError, TypeError):
            raise TypeError(f'Invalid {style=}') from None
        return cls(name, **kwargs)

    def __class_getitem__(cls, name: str) -> Style:
        return cls._instances[name]

    def make_default(self):
        self.__class__.default_style = self

    def sub_style(self, name: str = None, **kwargs) -> Style:
        if name and name in self._instances:
            name = f'{self.name}:{name}'
        return self.__class__(name, parent=self, **kwargs)

    # endregion

    def as_dict(self) -> dict[str, Union[str, None, dict[str, StateValues]]]:
        get = self.__dict__.get
        style = {'name': self.name, 'parent': self.parent.name if self.parent else None, 'ttk_theme': get('ttk_theme')}
        layer: StyleLayer
        for name in self._layers:
            if layer := get(name):
                style[name] = layer.as_dict()
            else:
                style[name] = None
        return style

    def iter_layers(self) -> Iterator[tuple[str, StyleLayer]]:
        names = self._layers.copy()
        names.remove('base')
        names = ['base'] + sorted(names)
        get = self.__dict__.get
        for name in names:
            if layer := get(name):
                yield name, layer

    def get_map(
        self,
        layer: Layer = 'base',
        state: StyleStateVal = StyleState.DEFAULT,
        **dst_src_map
    ) -> dict[str, FinalValue]:
        # log.debug(f'{self}.get_map: {layer=}')
        layer: StyleLayer = getattr(self, layer)
        # log.debug(f'  > {layer=}')
        return {dst: val for dst, src in dst_src_map.items() if (val := getattr(layer, src)[state]) is not None}

    # def get_ttk_map_list(self, layer: Layer, attr: StyleAttr) -> list[tuple[str, str]]:
    #     layer: StyleLayer = getattr(self, layer)
    #     state_vals: StateValues = getattr(layer, attr)
    #     state_val_list = [
    #         # ('!focus', state_vals[StyleState.DEFAULT]),
    #         ('disabled', state_vals[StyleState.DISABLED]),
    #         ('invalid', state_vals[StyleState.INVALID]),
    #         ('active', state_vals[StyleState.ACTIVE]),
    #         ('selected', state_vals[StyleState.HIGHLIGHT]),
    #     ]
    #     return [sv for sv in state_val_list if sv[1] is not None]

    def make_ttk_style(self, name_suffix: str, theme: str | None = _NotSet) -> tuple[str, TtkStyle]:
        """
        :param name_suffix: Suffix for the theme name.  Should match the widget's ttk class name.
        :param theme: The theme that this style should use.  Defaults to this Style's default ttk_theme.  Use ``None``
          to skip the ``theme_use(...)`` call.
        :return: The name to use, and a :class:`ttk.Style` object.
        """
        name = f'{next(self._ttk_count)}__{name_suffix}'
        ttk_style = TtkStyle()
        if theme is not None:
            ttk_style.theme_use(self.ttk_theme if theme is _NotSet else theme)
        return name, ttk_style

    # region Font Methods

    def char_height(self, layer: Layer = 'base', state: StyleStateVal = StyleState.DEFAULT) -> int:
        tk_font: TkFont = getattr(self, layer).tk_font[state]
        return tk_font.metrics('linespace')

    def char_width(self, layer: Layer = 'base', state: StyleStateVal = StyleState.DEFAULT) -> int:
        tk_font: TkFont = getattr(self, layer).tk_font[state]
        return tk_font.measure('A')

    def measure(self, text: str, layer: Layer = 'base', state: StyleStateVal = StyleState.DEFAULT) -> int:
        """
        Char widths for the default font::

            {3: 'I', 6: 'J', 7: 'LTXZ', 8: 'F', 9: 'ABCDEHKNPRSUVY', 10: 'GOQ', 11: 'M', 13: 'W'}

        :param text: The text for which the width should be measured.
        :param layer: The style layer containing the font that should be used .
        :param state: The state of the specified style layer containing the font that should be used.
        :return: The width of the given text.
        """
        tk_font: TkFont = getattr(self, layer).tk_font[state]
        return tk_font.measure(text)

    def text_size(self, text: str, layer: Layer = 'base', state: StyleStateVal = StyleState.DEFAULT) -> XY:
        tk_font: TkFont = getattr(self, layer).tk_font[state]
        width = tk_font.measure(text)
        height = tk_font.metrics('linespace')
        return width, height

    # endregion
