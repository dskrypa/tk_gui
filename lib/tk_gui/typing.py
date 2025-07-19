"""
Type annotations for the Tkinter GUI package.

:author: Doug Skrypa
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if not TYPE_CHECKING:
    raise RuntimeError('This module is not expected to be imported while not type checking')

import tkinter.constants as tkc
from abc import abstractmethod
from pathlib import Path
from tkinter import Event, Toplevel, Frame, LabelFrame
from typing import Any, Callable, Collection, Hashable, Iterable, Iterator, Protocol, TypeVar, runtime_checkable
from typing import Literal, Mapping

from PIL.Image import Image as PILImage

from tk_gui.elements.element import Element, ElementBase
from tk_gui.enums import BindTargets, BindEvent, ScrollUnit, ImageResizeMode, TreeSelectMode, CallbackAction
from tk_gui.enums import TreeShowMode
from tk_gui.geometry.typing import XY
from tk_gui.pseudo_elements import Row
from tk_gui.widgets.scroll import ScrollableToplevel
from tk_gui.window import Window

# fmt: off
__all__ = [
    'Bool', 'HasSize', 'Key', 'HasParent', 'HasValue', 'Layout', 'Axis', 'Orientation', 'PathLike', 'OptInt',
    'BindCallback', 'EventCallback', 'TraceCallback', 'BindTarget', 'Bindable', 'ProvidesEventCallback',
    'TkFill', 'TkSide', 'TkJustify',
    'TkContainer', 'HasFrame', 'FrameLike',
]
# fmt: on

T = TypeVar('T')
T_co = TypeVar('T_co', covariant=True)

Key = Hashable
BindCallback = Callable[[Event], Any]
EventCallback = BindCallback | Callable[[Event, ...], Any]
ButtonEventCB = Callable[[Event, Key], CallbackAction | None]
TraceCallback = Callable[[str, str, str], Any]
Bindable = BindEvent | str
BindTarget = BindCallback | EventCallback | ButtonEventCB | BindTargets | str | None
AnyBindTarget = BindTarget | Collection[BindTarget]
BindMapping = Mapping[Bindable, AnyBindTarget]

AnyEle = ElementBase | Element
E = TypeVar('E', bound=AnyEle)
ElementRow = Iterable[E]

PathLike = Path | str
OptStr = str | None
IterStrs = Iterable[str]
OptInt = int | None
OptFloat = float | None
Bool = bool | Any

Axis = Literal['x', 'y']
# Orientation = Literal['horizontal', 'vertical']
Orientation = Literal[tkc.HORIZONTAL, tkc.VERTICAL]  # noqa
GrabAnywhere = bool | Literal['control']
TreeSelectModes = TreeSelectMode | Literal['none', 'browse', 'extended']
TreeShowModes = TreeShowMode | str

# TkFill = Literal['none', 'x', 'y', 'both'] | None | bool
# TkSide = Literal['left', 'right', 'top', 'bottom']
# TkJustify = Literal['left', 'center', 'right']
TkFill = Literal[tkc.NONE, tkc.X, tkc.Y, tkc.BOTH] | None | bool  # noqa
TkSide = Literal[tkc.LEFT, tkc.RIGHT, tkc.TOP, tkc.BOTTOM]  # noqa
TkJustify = Literal[tkc.LEFT, tkc.CENTER, tkc.RIGHT]  # noqa

TkScrollWhat = Literal['units', 'pages', 'pixels']
ScrollWhat = ScrollUnit | TkScrollWhat
ScrollAmount = TypeVar('ScrollAmount', int, float)
ImgResizeMode = ImageResizeMode | str

Top = ScrollableToplevel | Toplevel
TkContainer = Toplevel | Frame | LabelFrame
FrameLike = TypeVar('FrameLike', bound=TkContainer)

RGB = HSL = tuple[int, int, int]
RGBA = tuple[int, int, int, int]
Color = str | RGB | RGBA
ImageType = PILImage | bytes | PathLike | None


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


HasSize.register(PILImage)  # noqa  # PyCharm doesn't recognize that Protocol has ABCMeta as its parent metaclass


@runtime_checkable
class ProvidesEventCallback(Protocol):
    __slots__ = ()

    @abstractmethod
    def as_callback(self) -> EventCallback:
        pass


class Layout(Protocol[E]):
    __slots__ = ()

    @abstractmethod
    def __iter__(self) -> Iterator[ElementRow | Row[E]]:
        pass


# if TYPE_CHECKING:
#     Layout = Iterable[ElementRow | Row[E]]
# else:
#     Layout = Iterable[ElementRow]


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
