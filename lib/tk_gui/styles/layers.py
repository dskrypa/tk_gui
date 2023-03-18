from __future__ import annotations

# import logging
from tkinter.font import Font as TkFont
from typing import TYPE_CHECKING, Union, Optional, Type, Iterator, Generic, TypeVar, overload

from .states import StateValues, LayerStateValues, FontStateValues

if TYPE_CHECKING:
    from tk_gui.typing import Bool, OptInt, OptStr
    from .style import Style
    from .typing import StateName, FontValues, Font, OptStrVals, OptIntVals, LayerValues

__all__ = ['StyleLayer', 'StyleProperty', 'StyleLayerProperty']
# log = logging.getLogger(__name__)

T = TypeVar('T')


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
