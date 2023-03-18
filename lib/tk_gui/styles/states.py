from __future__ import annotations

from collections import namedtuple
from typing import TYPE_CHECKING, Union, Optional, Type, Iterator, Generic, TypeVar
from typing import overload

from tk_gui.enums import StyleState

if TYPE_CHECKING:
    from tk_gui.typing import OptInt, OptStr
    from .style import StyleLayer, Style
    from .typing import StateName, FontValues, Font, OptStrVals, OptIntVals, StyleStateVal, RawStateValues

__all__ = ['STATE_NAMES', 'StateValueTuple', 'StateValue', 'StateValues', 'LayerStateValues', 'FontStateValues']

STATE_NAMES = ('default', 'disabled', 'invalid', 'active', 'highlight')

T_co = TypeVar('T_co', covariant=True)


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
        if values is None:
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
