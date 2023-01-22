"""
Type annotations for the Tkinter GUI package.

:author: Doug Skrypa
"""

from abc import abstractmethod
from typing import TYPE_CHECKING, Protocol, TypeVar, Any, Union, Callable, Iterable, Optional, runtime_checkable
from typing import Literal, _ProtocolMeta  # noqa

if TYPE_CHECKING:
    from pathlib import Path
    from tkinter import Event, Toplevel, Frame, LabelFrame
    from PIL.Image import Image as PILImage
    from .elements import Element
    from .enums import BindTargets, BindEvent

# fmt: off
__all__ = [
    'Bool', 'XY', 'Key', 'HasParent', 'HasValue', 'Layout', 'Axis', 'Orientation', 'PathLike', 'OptInt',
    'BindCallback', 'EventCallback', 'TraceCallback', 'BindTarget', 'Bindable', 'ProvidesEventCallback',
    'TkFill', 'TkSide', 'TkJustify',
    'TkContainer',
]
# fmt: on

T = TypeVar('T')
T_co = TypeVar('T_co', covariant=True)

BindCallback = Callable[['Event'], Any]
EventCallback = Callable[['Event', ...], Any]
ButtonEventCB = Callable[['Event', 'Key'], Any]
TraceCallback = Callable[[str, str, str], Any]
Bindable = Union['BindEvent', str]
BindTarget = Union[BindCallback, EventCallback, ButtonEventCB, 'BindTargets', str, None]

Bool = Union[bool, Any]
XY = tuple[int, int]
Layout = Iterable[Iterable['Element']]
Axis = Literal['x', 'y']
Orientation = Literal['horizontal', 'vertical']
PathLike = Union['Path', str]
OptInt = Optional[int]

TkFill = Union[Literal['none', 'x', 'y', 'both'], None, bool]
TkSide = Literal['left', 'right', 'top', 'bottom']
TkJustify = Literal['left', 'center', 'right']

TkContainer = Union['Toplevel', 'Frame', 'LabelFrame']

RGB = HSL = tuple[int, int, int]
RGBA = tuple[int, int, int, int]
Color = Union[str, RGB, RGBA]
ImageType = Union['PILImage', bytes, PathLike, None]


@runtime_checkable
class HasParent(Protocol[T_co]):
    __slots__ = ()

    @property
    @abstractmethod
    def parent(self) -> T_co:
        pass


class KeyMeta(_ProtocolMeta):
    __slots__ = ()

    def __instancecheck__(self, instance) -> bool:
        if not instance:
            return False
        try:
            hash(instance)
        except TypeError:
            return False
        return True


@runtime_checkable
class Key(Protocol, metaclass=KeyMeta):
    __slots__ = ()


@runtime_checkable
class HasValue(Protocol[T_co]):
    __slots__ = ()

    @property
    @abstractmethod
    def value(self) -> T_co:
        pass


@runtime_checkable
class ProvidesEventCallback(Protocol):
    __slots__ = ()

    @abstractmethod
    def as_callback(self) -> EventCallback:
        pass
