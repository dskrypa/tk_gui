"""
Type annotations for the Tkinter GUI package.

:author: Doug Skrypa
"""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, Protocol, TypeVar, Any, Union, Callable, Iterable, Optional, runtime_checkable
from typing import Iterator, Literal, _ProtocolMeta  # noqa

if TYPE_CHECKING:
    from pathlib import Path  # noqa
    from tkinter import Event, Toplevel, Frame, LabelFrame  # noqa
    from PIL.Image import Image as PILImage  # noqa
    from .elements.element import Element, ElementBase  # noqa
    from .enums import BindTargets, BindEvent  # noqa
    from .pseudo_elements import Row
    from .window import Window  # noqa

# fmt: off
__all__ = [
    'Bool', 'XY', 'Key', 'HasParent', 'HasValue', 'Layout', 'Axis', 'Orientation', 'PathLike', 'OptInt',
    'BindCallback', 'EventCallback', 'TraceCallback', 'BindTarget', 'Bindable', 'ProvidesEventCallback',
    'TkFill', 'TkSide', 'TkJustify',
    'TkContainer', 'HasFrame', 'FrameLike',
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

AnyEle = Union['ElementBase', 'Element']
E = TypeVar('E', bound=AnyEle)

Bool = Union[bool, Any]
XY = tuple[int, int]
Axis = Literal['x', 'y']
Orientation = Literal['horizontal', 'vertical']
PathLike = Union['Path', str]
OptInt = Optional[int]

TkFill = Union[Literal['none', 'x', 'y', 'both'], None, bool]
TkSide = Literal['left', 'right', 'top', 'bottom']
TkJustify = Literal['left', 'center', 'right']

TkContainer = Union['Toplevel', 'Frame', 'LabelFrame']
FrameLike = TypeVar('FrameLike', bound=TkContainer)

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


class Layout(Protocol[E]):
    __slots__ = ()

    @abstractmethod
    def __iter__(self) -> Iterator[Iterable[E] | Row[E]]:
        pass


@runtime_checkable
class HasFrame(Protocol[FrameLike]):
    __slots__ = ()

    @property
    @abstractmethod
    def frame(self) -> FrameLike:
        pass

    @property
    @abstractmethod
    def window(self) -> Window:
        pass
