"""
GUI styles / themes

:author: Doug Skrypa
"""

from __future__ import annotations

# import logging
from collections import namedtuple
from itertools import count
from tkinter.font import Font as TkFont
from tkinter.ttk import Style as TtkStyle
from typing import TYPE_CHECKING, Union, Optional, Literal, Type, Mapping, Iterator, Any, Generic, TypeVar, Iterable
from typing import overload

from tk_gui.caching import ClearableCachedPropertyMixin, cached_property
from tk_gui.enums import StyleState

if TYPE_CHECKING:
    from tk_gui.typing import XY, Bool

__all__ = ['Style', 'StyleSpec', 'STATE_NAMES', 'StyleLayer', 'Layer', 'StyleState', 'Font']
# log = logging.getLogger(__name__)

DEFAULT_FONT = ('Helvetica', 10)
STATE_NAMES = ('default', 'disabled', 'invalid', 'active', 'highlight')

# region Typing

StateName = Literal['default', 'disabled', 'invalid', 'active', 'highlight']
StyleAttr = Literal[
    'font', 'tk_font', 'fg', 'bg', 'border_width', 'relief',
    'frame_color', 'trough_color', 'arrow_color', 'arrow_width', 'bar_width',
]
StyleOptions = Mapping[str, Any]
StyleSpec = Union[str, 'Style', StyleOptions, tuple[str, StyleOptions], None]
StyleStateVal = Union[StyleState, StateName, Literal[0, 1, 2]]
Relief = Optional[Literal['raised', 'sunken', 'flat', 'ridge', 'groove', 'solid']]
T = TypeVar('T')
T_co = TypeVar('T_co', covariant=True)

OptStr = Optional[str]
_OptStrTuple = Union[
    tuple[OptStr], tuple[(OptStr,) * 2], tuple[(OptStr,) * 3], tuple[(OptStr,) * 4], tuple[(OptStr,) * 5]
]
OptStrVals = Union[OptStr, Mapping[StyleStateVal, OptStr], _OptStrTuple]

OptInt = Optional[int]
_OptIntTuple = Union[
    tuple[OptInt], tuple[(OptInt,) * 2], tuple[(OptInt,) * 3], tuple[(OptInt,) * 4], tuple[(OptInt,) * 5]
]
OptIntVals = Union[OptInt, Mapping[StyleStateVal, OptInt], _OptIntTuple]

Font = Union[str, tuple[str, int], tuple[str, int, str, ...], None]
_FontValsTuple = Union[tuple[Font], tuple[(Font,) * 2], tuple[(Font,) * 3], tuple[(Font,) * 4], tuple[(Font,) * 5]]
FontValues = Union[Font, Mapping[StyleStateVal, Font], _FontValsTuple]

StyleValue = Union[OptStr, OptInt, Font]
FinalValue = Union[StyleValue, TkFont]
RawStateValues = Union[OptStrVals, OptIntVals, FontValues]

LayerValues = Union[FontValues, Mapping[StyleStateVal, StyleValue]]

# endregion

# region State Values

StateValueTuple = namedtuple('StateValueTuple', STATE_NAMES)


class StateValue(Generic[T_co]):
    """Allows state-based component values to be accessed by name"""

    __slots__ = ('name',)

    def __set_name__(self, owner: Type[StateValues], name: StateName):
        self.name = name

    def __get__(self, instance: Optional[StateValues], owner: Type[StateValues]) -> Union[StateValue, Optional[T_co]]:
        if instance is None:
            return self
        return instance[self.name]

    def __set__(self, instance: StateValues, value: Optional[T_co]):
        instance[self.name] = value


class StateValues(Generic[T_co]):
    __slots__ = ('values', 'layer', 'name')

    default = StateValue()
    disabled = StateValue()
    invalid = StateValue()
    active = StateValue()       # Only used for button, radio, and menu elements
    highlight = StateValue()    # Only used for button, radio, and multiline elements

    def __init__(
        self,
        layer: StyleLayer,
        name: str,
        default: Optional[T_co] = None,
        disabled: Optional[T_co] = None,
        invalid: Optional[T_co] = None,
        active: Optional[T_co] = None,
        highlight: Optional[T_co] = None,
    ):
        self.name = name
        self.layer = layer
        self.values = StateValueTuple(default, disabled, invalid, active, highlight)

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}[{self.layer.prop.name}.{self.name}: {self.values}]>'

    # region Overloads

    @classmethod
    @overload
    def new(cls, layer: StyleLayer, name: str, values: FontValues) -> StateValues[Font]:
        ...

    @classmethod
    @overload
    def new(cls, layer: StyleLayer, name: str, values: OptStrVals) -> StateValues[OptStr]:
        ...

    @classmethod
    @overload
    def new(cls, layer: StyleLayer, name: str, values: OptIntVals) -> StateValues[OptInt]:
        ...

    # endregion

    @classmethod
    def new(
        cls, layer: StyleLayer, name: str, values: Union[RawStateValues, StateValues[T_co]] = None
    ) -> StateValues[T_co]:
        if not values:
            return cls(layer, name)
        elif isinstance(values, cls):
            return values.copy(layer, name)
        elif isinstance(values, (str, int)):
            return cls(layer, name, values)
        try:
            return cls(layer, name, **values)
        except TypeError:
            pass

        match values:  # noqa
            case (str(), int(), *_):  # easier than checking len + a chain of isinstance checks
                return cls(layer, name, values)

        try:
            return cls(layer, name, *values)
        except TypeError:
            pass

        raise TypeError(f'Invalid type={values.__class__.__name__!r} to initialize {cls.__name__}')

    def copy(self: StateValues[T_co], layer: StyleLayer = None, name: str = None) -> StateValues[T_co]:
        return self.__class__(layer or self.layer, name or self.name, *self.values)

    def __call__(self, state: StyleStateVal = StyleState.DEFAULT) -> Optional[T_co]:
        state = StyleState(state)
        value = self.values[state]
        if not value and state != StyleState.DEFAULT:
            return self.values[StyleState.DEFAULT]
        return value

    def __getitem__(self, state: StyleStateVal) -> Optional[T_co]:
        state = StyleState(state)
        value = self.values[state]
        if not value and state != 0:  # StyleState.DEFAULT
            return self.values[0]
        return value

    def __setitem__(self, state: StyleStateVal, value: Optional[T_co]):
        state = StyleState(state)
        self.values = StateValues(*(value if i == state else v for i, v in enumerate(self.values)))

    def __iter__(self) -> Iterator[Optional[T_co]]:
        yield from self.values


class LayerStateValues(Generic[T_co]):
    __slots__ = ('name',)

    def __set_name__(self, owner: Type[StyleLayer], name: str):
        self.name = name
        owner._fields.add(name)

    def get_values(self, style: Optional[Style], layer_name: str) -> Optional[StateValues[T_co]]:
        if layer := style.__dict__.get(layer_name):  # type: StyleLayer
            return getattr(layer, self.name)
        return None

    def get_parent_values(self, style: Optional[Style], layer_name: str) -> Optional[StateValues[T_co]]:
        while style:
            if state_values := self.get_values(style, layer_name):
                return state_values

            style = style.parent

        return None

    def __get__(
        self, layer: Optional[StyleLayer], layer_cls: Type[StyleLayer]
    ) -> Union[LayerStateValues, Optional[StateValues[T_co]]]:
        if layer is None:
            return self

        # print(f'{layer.style}.{layer.prop.name}.{self.name}...')
        if state_values := layer.__dict__.get(self.name):
            return state_values

        layer_name = layer.prop.name
        style = layer.style
        if state_values := self.get_parent_values(style.parent, layer_name):
            return state_values
        # elif (default_style := Style.default_style) and style not in default_style._family:
        #     if state_values := self.get_values(default_style, layer_name):
        #         return state_values

        if layer_parent := layer.prop.parent:
            return getattr(getattr(style, layer_parent), self.name)
        # elif not style.parent or style is default_style:
        #     layer.__dict__[self.name] = state_values = StateValues(layer, self.name)
        #     return state_values
        layer.__dict__[self.name] = state_values = StateValues(layer, self.name)
        return state_values

    def __set__(self, layer: StyleLayer, value: RawStateValues):
        if value is None:
            layer.__dict__[self.name] = None
        else:
            layer.__dict__[self.name] = StateValues.new(layer, self.name, value)


class FontStateValues(LayerStateValues):
    __slots__ = ()

    def __set__(self, instance: StyleLayer, value: FontValues):
        match value:  # noqa
            case None:
                instance.__dict__[self.name] = None
            case (str(_name), int(_size)):
                instance.__dict__[self.name] = StateValues(instance, self.name, value)
            case _:
                instance.__dict__[self.name] = StateValues.new(instance, self.name, value)

        try:
            del instance._tk_font
        except AttributeError:
            pass


# endregion


class StyleLayer:
    _fields: set[str] = set()
    font: StateValues[Font] = FontStateValues()             # Font to use
    fg: StateValues[OptStr] = LayerStateValues()            # Foreground / text color
    bg: StateValues[OptStr] = LayerStateValues()            # Background color
    border_width: StateValues[OptInt] = LayerStateValues()  # Border width
    # border_color: StateValues[OptStr] = LayerStateValues()  # Border color
    relief: StateValues[OptStr] = LayerStateValues()        # Visually differentiate the edges of some elements
    # Scroll bar options
    frame_color: StateValues[OptStr] = LayerStateValues()   # Frame color
    trough_color: StateValues[OptStr] = LayerStateValues()  # Trough (area where scroll bars can travel) color
    arrow_color: StateValues[OptStr] = LayerStateValues()   # Color for the arrows at either end of scroll bars
    arrow_width: StateValues[OptInt] = LayerStateValues()   # Width of scroll bar arrows in px
    bar_width: StateValues[OptInt] = LayerStateValues()     # Width of scroll bars in px

    @overload
    def __init__(
        self,
        style: Style,
        prop: StyleLayerProperty,
        *,
        font: FontValues = None,
        fg: OptStrVals = None,
        bg: OptStrVals = None,
        border_width: OptIntVals = None,
        # border_color: OptStrVals = None,
        frame_color: OptStrVals = None,
        trough_color: OptStrVals = None,
        arrow_color: OptStrVals = None,
        arrow_width: OptIntVals = None,
        bar_width: OptIntVals = None,
        relief: OptStrVals = None,
    ):
        ...

    def __init__(self, style: Style, prop: StyleLayerProperty, **kwargs):
        self.style = style
        self.prop = prop
        fields = self._fields
        for key, val in kwargs.items():
            if key in fields:
                setattr(self, key, val)
            else:
                # The number of times one or more invalid options will be provided is extremely low compared to how
                # often this exception will not need to be raised, so the re-iteration over kwargs is acceptable.
                # This also avoids creating the `bad` dict that would otherwise be thrown away on 99.9% of init calls.
                bad = {k: v for k, v in kwargs.items() if k not in fields}
                raise TypeError(f'Invalid style layer options: {bad}')

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}[{self.style.name}: {self.prop.name}]>'

    @classmethod
    def new(cls, style: Style, prop: StyleLayerProperty, values: LayerValues = None) -> StyleLayer:
        if not values:
            return cls(style, prop)
        try:
            return cls(style, prop, **values)
        except TypeError:
            pass
        raise TypeError(f'Invalid type={values.__class__.__name__!r} to initialize {cls.__name__}')

    @property
    def tk_font(self) -> StateValues[Optional[TkFont]]:
        try:
            return self._tk_font  # noqa
        except AttributeError:
            pass

        parts = (_font_or_none(font) for font in self.font)
        self._tk_font = tk_font = StateValues(self, 'tk_font', *parts)  # noqa
        return tk_font

    def sub_font(self, state: StateName = 'default', name: str = None, size: int = None, *attrs: str) -> Font:
        font = self.font[state]
        try:
            _name, _size, *_attrs = font
        except (TypeError, ValueError):
            _name, _size, _attrs = font, None, ()

        return (name or _name), (size or _size), *(attrs or _attrs)  # noqa

    def _iter_values(self) -> Iterator[tuple[str, Optional[StateValues]]]:
        fields = self._fields
        for key, val in self.__dict__.items():
            if key in fields:
                yield key, getattr(val, 'values', None)

    def as_dict(self, include_none: Bool = True) -> dict[str, StateValues]:
        return dict(self._iter_values() if include_none else self.iter_values())

    def iter_values(self) -> Iterator[tuple[str, StateValues]]:
        for key, values in self._iter_values():
            if values is not None:
                yield key, values


def _font_or_none(font: Font) -> TkFont | None:
    if not font:
        return None
    try:
        return TkFont(font=font)
    except RuntimeError:  # Fonts require the hidden root to have been initialized first
        pass

    from tk_gui.window import Window

    Window._ensure_tk_is_initialized()
    return TkFont(font=font)


class StyleProperty(Generic[T]):
    __slots__ = ('name', 'default')

    def __init__(self, default: Optional[T] = None):
        self.default = default

    def __set_name__(self, owner: Type[Style], name: str):
        self.name = name

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}[{self.name}]>'

    def get_parent_part(self, style: Optional[Style]) -> Optional[T]:
        while style:
            if part := style.__dict__.get(self.name):
                # log.debug(f'get_parent_part: found {part=} for {self.name=} from {style=}')
                return part

            style = style.parent

        # log.debug(f'get_parent_part: returning None for property={self.name!r} for {style=}')
        return None

    def __get__(self, instance: Optional[Style], owner: Type[Style]) -> Union[StyleProperty, T, None]:
        if instance is None:
            return self
        elif part := self.get_parent_part(instance):
            # log.debug(f'__get__: Found {part=} for {self.name=} from a parent of {instance=}')
            return part
        # elif (default_style := owner.default_style) and default_style is not instance:
        #     if part := default_style.__dict__.get(self.name):
        #         log.debug(f'__get__: Found {part=} for {self.name=} from {default_style=}')
        #         return part
        #     log.debug(f'__get__: No part found for {self.name=} from {default_style=}')
        # log.debug(f'__get__: Returning {self.default=} for {self.name=}')
        return self.default

    def __set__(self, instance: Style, value: T):
        instance.__dict__[self.name] = value

    def __delete__(self, instance: Style):
        del instance.__dict__[self.name]


class StyleLayerProperty(StyleProperty[StyleLayer]):
    __slots__ = ('parent',)

    def __init__(self, parent: str = None):
        super().__init__(None)
        self.parent = parent

    def __set_name__(self, owner: Type[Style], name: str):
        self.name = name
        owner._layers.add(name)

    def __get__(self, instance: Optional[Style], owner: Type[Style]) -> Union[StyleLayerProperty, StyleLayer, None]:
        if instance is None:
            return self
        elif part := super().__get__(instance, owner):
            # log.debug(f'  > Using {part=} from super().__get__')
            return part
        # elif not instance.parent or not (default := owner.default_style) or instance is default:  # noqa
        #     print(f'Creating a new layer for {self.name=} on {instance=}')
        #     instance.__dict__[self.name] = part = StyleLayer(instance, self)
        #     return part
        else:
            # log.debug(f'Creating a new layer for {self.name=} on {instance=}')
            instance.__dict__[self.name] = part = StyleLayer(instance, self)
            return part

        # log.debug(f'Returning None for layer={self.name!r} for {instance=}')
        # return None

    def __set__(self, instance: Style, value: LayerValues):
        instance.__dict__[self.name] = StyleLayer.new(instance, self, value)


Layer = Literal[
    'base', 'insert', 'scroll', 'arrows', 'radio', 'checkbox', 'frame', 'combo', 'progress', 'image', 'tooltip', 'text',
    'button', 'listbox', 'link', 'selected', 'input', 'table', 'table_header', 'table_alt', 'slider', 'menu',
]


class Style(ClearableCachedPropertyMixin):
    _count = count()
    _ttk_count = count()
    _layers: set[str] = set()
    _instances: dict[str, Style] = {}
    default_style: Optional[Style] = None

    name: str
    parent: Optional[Style]

    ttk_theme: Optional[str] = StyleProperty()

    base = StyleLayerProperty()

    arrows = StyleLayerProperty()                   # Arrows on forms, such as combo boxes
    button = StyleLayerProperty('base')
    checkbox = StyleLayerProperty('base')
    combo = StyleLayerProperty('text')              # Combo box (dropdown) input
    frame = StyleLayerProperty('base')
    image = StyleLayerProperty('base')
    input = StyleLayerProperty('text')
    insert = StyleLayerProperty()
    link = StyleLayerProperty('text')               # Hyperlinks
    listbox = StyleLayerProperty('text')
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
                # log.info(f'{self}: Full layer config provided: {key}={val!r}', extra={'color': 11})
                setattr(self, key, val)
            elif key in layer_fields:
                layers.setdefault('base', {})[key] = val
            else:
                layer, attr = self._split_config_key(key)
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

            if layer in self._layers and attr in StyleLayer._fields:
                return layer, attr

        for layer_name, suffix_idx, delim_idx in self._compound_layer_names():
            if key.startswith(layer_name) and len(key) > suffix_idx and key[delim_idx] in '_.':
                if (attr := key[suffix_idx:]) in StyleLayer._fields:
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

    def make_ttk_style(self, name_suffix: str) -> tuple[str, TtkStyle]:
        name = f'{next(self._ttk_count)}__{name_suffix}'
        ttk_style = TtkStyle()
        ttk_style.theme_use(self.ttk_theme)
        return name, ttk_style

    # region Font Methods

    def char_height(self, layer: Layer = 'base', state: StyleStateVal = StyleState.DEFAULT) -> int:
        tk_font: TkFont = getattr(self, layer).tk_font[state]
        return tk_font.metrics('linespace')

    def char_width(self, layer: Layer = 'base', state: StyleStateVal = StyleState.DEFAULT) -> int:
        tk_font: TkFont = getattr(self, layer).tk_font[state]
        return tk_font.measure('A')

    def measure(self, text: str, layer: Layer = 'base', state: StyleStateVal = StyleState.DEFAULT) -> int:
        tk_font: TkFont = getattr(self, layer).tk_font[state]
        return tk_font.measure(text)

    def text_size(self, text: str, layer: Layer = 'base', state: StyleStateVal = StyleState.DEFAULT) -> XY:
        tk_font: TkFont = getattr(self, layer).tk_font[state]
        width = tk_font.measure(text)
        height = tk_font.metrics('linespace')
        return width, height

    # endregion
