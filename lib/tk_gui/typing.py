"""
Type annotations for the Tkinter GUI package.

:author: Doug Skrypa
"""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, Protocol, TypeVar, Any, Union, Callable, Iterable, Optional, runtime_checkable
from typing import Hashable, Iterator, Literal

if TYPE_CHECKING:
    from pathlib import Path  # noqa
    from tkinter import Event, Toplevel, Frame, LabelFrame  # noqa
    from PIL.Image import Image as PILImage  # noqa
    from tk_gui.elements.element import Element, ElementBase  # noqa
    from tk_gui.enums import BindTargets, BindEvent, ScrollUnit, ImageResizeMode  # noqa
    from tk_gui.pseudo_elements import Row
    from tk_gui.widgets.scroll import ScrollableToplevel  # noqa
    from tk_gui.window import Window  # noqa

# fmt: off
__all__ = [
    'Bool', 'XY', 'HasSize', 'Key', 'HasParent', 'HasValue', 'Layout', 'Axis', 'Orientation', 'PathLike', 'OptInt',
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
ElementRow = Iterable[E]
Key = Hashable

PathLike = Union['Path', str]
OptStr = Optional[str]
OptInt = Optional[int]
OptFloat = Optional[float]
Bool = Union[bool, Any]
XY = tuple[int, int]
OptXY = tuple[OptInt, OptInt]
OptXYF = tuple[OptFloat, OptFloat]
SelectionPos = XY | tuple[XY, XY] | tuple[None, None] | tuple[str, str]
Axis = Literal['x', 'y']
Orientation = Literal['horizontal', 'vertical']
GrabAnywhere = Union[bool, Literal['control']]

TkFill = Union[Literal['none', 'x', 'y', 'both'], None, bool]
TkSide = Literal['left', 'right', 'top', 'bottom']
TkJustify = Literal['left', 'center', 'right']

TkScrollWhat = Literal['units', 'pages', 'pixels']
ScrollWhat = Union['ScrollUnit', TkScrollWhat]
ScrollAmount = TypeVar('ScrollAmount', int, float)
ImgResizeMode = Union['ImageResizeMode', str]

Top = Union['ScrollableToplevel', 'Toplevel']
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


@runtime_checkable
class HasValue(Protocol[T_co]):
    __slots__ = ()

    @property
    @abstractmethod
    def value(self) -> T_co:
        pass


@runtime_checkable
class HasSize(Protocol):
    __slots__ = ()

    @property
    @abstractmethod
    def size(self) -> XY:
        pass


@runtime_checkable
class ProvidesEventCallback(Protocol):
    __slots__ = ()

    @abstractmethod
    def as_callback(self) -> EventCallback:
        pass


class _Layout(Protocol[E]):
    __slots__ = ()

    @abstractmethod
    def __iter__(self) -> Iterator[ElementRow | Row[E]]:
        pass


# I thought just the Protocol should be enough, but PyCharm started to get confused by lists of lists of elements...
Layout = Union[_Layout, list[ElementRow | Row[E]]]


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


@runtime_checkable
class SupportsBind(Protocol):
    __slots__ = ()

    @abstractmethod
    def bind(self, event_pat: Bindable, cb: BindTarget, add: Bool = None):
        pass

    @abstractmethod
    def unbind(self, event_pat: Bindable, func_id: str = None):
        pass


@runtime_checkable
class ConfigContainer(Protocol):
    __slots__ = ()

    @property
    @abstractmethod
    def config_name(self) -> str | None:
        pass

    @property
    @abstractmethod
    def config_path(self) -> PathLike | None:
        pass

    @property
    @abstractmethod
    def config_defaults(self) -> dict[str, Any] | None:
        pass

    @property
    @abstractmethod
    def is_popup(self) -> bool:
        pass
