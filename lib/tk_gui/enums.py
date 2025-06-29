"""
Enums for the Tkinter GUI package.

:author: Doug Skrypa
"""

from __future__ import annotations

import tkinter.constants as tkc
from enum import Enum, IntEnum
from platform import system
from typing import TYPE_CHECKING, Type

from .caching import cached_property

if TYPE_CHECKING:
    from .typing import TkFill

__all__ = [
    'Anchor', 'Justify', 'Side',
    'BindEvent', 'BindTargets', 'CallbackAction',
    'StyleState', 'ListBoxSelectMode', 'TreeSelectMode', 'ScrollUnit', 'ImageResizeMode',
]

# fmt: off
ANCHOR_ALIASES = {
    'center': 'MID_CENTER', 'top': 'TOP_CENTER', 'bottom': 'BOTTOM_CENTER', 'left': 'MID_LEFT', 'right': 'MID_RIGHT',
    'c': 'MID_CENTER', 't': 'TOP_CENTER', 'b': 'BOTTOM_CENTER', 'l': 'MID_LEFT', 'r': 'MID_RIGHT',
}
SIDE_STICKY_MAP = {tkc.LEFT: tkc.W, tkc.RIGHT: tkc.E, tkc.TOP: tkc.N, tkc.BOTTOM: tkc.S}
JUSTIFY_TO_ANCHOR = {tkc.LEFT: tkc.W, tkc.CENTER: tkc.CENTER, tkc.RIGHT: tkc.E}
# fmt: on

_ON_MAC = system().lower() == 'darwin'  # Cannot import from environment due to circular dependency


class MissingMixin:
    __aliases = None

    def __init_subclass__(cls, aliases: dict[str, str] = None):
        cls.__aliases = aliases

    @classmethod
    def _missing_(cls: Type[Enum], value: str):
        if aliases := cls.__aliases:  # noqa
            try:
                return cls[aliases[value.lower()]]
            except KeyError:
                pass
        try:
            return cls[value.upper().replace(' ', '_')]
        except KeyError:
            return None  # This is what the default implementation does to signal an exception should be raised

    def __bool__(self) -> bool:
        return self._value_ is not None  # noqa


# region Event Related


class BindEvent(MissingMixin, Enum):
    def __new__(cls, tk_event: str):
        # Defined __new__ to avoid juggling dicts for the event names, and to avoid conflicting event names from being
        # used to initialize incorrect BindEvents
        obj = object.__new__(cls)
        obj.event = tk_event
        obj._value_ = 2 ** len(cls.__members__)
        return obj

    POSITION_CHANGED = '<Configure>'
    SIZE_CHANGED = '<Configure>'
    LEFT_CLICK = '<ButtonRelease-1>'
    RIGHT_CLICK = '<ButtonRelease-2>' if _ON_MAC else '<ButtonRelease-3>'
    MENU_RESULT = '<<Custom:MenuCallback>>'
    BUTTON_CLICKED = '<<Custom:ButtonCallback>>'


class BindTargets(MissingMixin, Enum):
    EXIT = 'exit'
    INTERRUPT = 'interrupt'


class CallbackAction(MissingMixin, Enum):
    EXIT = 'exit'
    INTERRUPT = 'interrupt'


# endregion


# region Pack Related


class Side(MissingMixin, Enum, aliases={'l': 'LEFT', 'r': 'RIGHT', 't': 'TOP', 'b': 'BOTTOM'}):
    NONE = None
    LEFT = tkc.LEFT
    RIGHT = tkc.RIGHT
    TOP = tkc.TOP
    BOTTOM = tkc.BOTTOM

    def as_sticky(self) -> str:
        # TODO: It appears that sticky can use `ew` for horizontally centered, `ns` for vertically, `nsew` for both
        #  -> may correlate better with anchor?
        return SIDE_STICKY_MAP.get(self.value)


class Justify(MissingMixin, Enum, aliases={'c': 'CENTER', 'l': 'LEFT', 'r': 'RIGHT'}):
    NONE = None
    LEFT = tkc.LEFT
    CENTER = tkc.CENTER
    RIGHT = tkc.RIGHT

    def as_anchor(self):
        return JUSTIFY_TO_ANCHOR.get(self.value)


class Anchor(MissingMixin, Enum, aliases=ANCHOR_ALIASES):
    NONE = None
    TOP_LEFT = tkc.NW
    TOP_CENTER = tkc.N
    TOP_RIGHT = tkc.NE
    MID_LEFT = tkc.W
    MID_CENTER = tkc.CENTER
    MID_RIGHT = tkc.E
    BOTTOM_LEFT = tkc.SW
    BOTTOM_CENTER = tkc.S
    BOTTOM_RIGHT = tkc.SE

    def as_justify(self):
        if self.value is None:
            return None
        elif self.value in (tkc.NW, tkc.W, tkc.SW):
            return tkc.LEFT
        # elif self.value in (tkc.N, tkc.CENTER, tkc.S):
        #     return tkc.CENTER
        elif self.value in (tkc.NE, tkc.E, tkc.SE):
            return tkc.RIGHT
        return tkc.CENTER

    def as_side(self):
        if self.value == tkc.N:
            return tkc.TOP
        elif self.value == tkc.S:
            return tkc.BOTTOM
        elif self.value in (tkc.NW, tkc.W, tkc.SW):
            return tkc.LEFT
        elif self.value in (tkc.NE, tkc.E, tkc.SE):
            return tkc.RIGHT
        return None  # None or CENTER

    def as_sticky(self):
        return SIDE_STICKY_MAP.get(self.as_side())

    @cached_property
    def is_abs_center(self) -> bool:
        return self in (Anchor.NONE, Anchor.MID_CENTER)

    @cached_property
    def is_horizontal_center(self) -> bool:
        return self in (Anchor.NONE, Anchor.MID_CENTER, Anchor.TOP_CENTER, Anchor.BOTTOM_CENTER)

    @cached_property
    def is_vertical_center(self) -> bool:
        return self in (Anchor.NONE, Anchor.MID_CENTER, Anchor.MID_LEFT, Anchor.MID_RIGHT)

    @cached_property
    def is_any_center(self) -> bool:
        return self.is_horizontal_center or self.is_vertical_center

    @cached_property
    def fill_axis(self) -> TkFill:
        if self.is_abs_center:
            return tkc.BOTH  # noqa
        elif self.is_horizontal_center:
            return tkc.X  # noqa
        elif self.is_vertical_center:
            return tkc.Y  # noqa
        else:
            return tkc.NONE  # noqa

    @cached_property
    def abs_fill_axis(self) -> TkFill:
        if self.is_abs_center:
            return tkc.BOTH  # noqa
        else:
            return tkc.NONE  # noqa


class Compound(MissingMixin, Enum, aliases={'l': 'LEFT', 'r': 'RIGHT', 't': 'TOP', 'b': 'BOTTOM'}):
    NONE = None
    LEFT = tkc.LEFT
    RIGHT = tkc.RIGHT
    TOP = tkc.TOP
    BOTTOM = tkc.BOTTOM
    CENTER = tkc.CENTER


# endregion


class StyleState(MissingMixin, IntEnum):
    DEFAULT = 0
    DISABLED = 1
    INVALID = 2
    ACTIVE = 3
    HIGHLIGHT = 4


# region Element Selection / Display Modes


class ListBoxSelectMode(MissingMixin, Enum):
    BROWSE = tkc.BROWSE         #: Select 1 item; can drag mouse and selection will follow (tk default)
    SINGLE = tkc.SINGLE         #: Select 1 item; cannot drag mouse to move selection
    MULTIPLE = tkc.MULTIPLE     #: Select multiple items; each must be clicked individually
    EXTENDED = tkc.EXTENDED     #: Select multiple items; can drag mouse to select multiple items (lib default)


class TreeSelectMode(MissingMixin, Enum):
    NONE = tkc.NONE
    BROWSE = tkc.BROWSE         #: Select 1 item
    EXTENDED = tkc.EXTENDED     #: Select multiple items


class TreeShowMode(MissingMixin, Enum):
    TREE = 'tree'
    HEADINGS = 'headings'
    BOTH = 'tree headings'


# endregion


class ScrollUnit(MissingMixin, Enum):
    UNITS = 'units'     # Supports int values
    PAGES = 'pages'     # Supports int values
    PIXELS = 'pixels'   # Supports int and float values


class ImageResizeMode(MissingMixin, Enum):
    NONE = 'none'           # No special handling
    FIT_INSIDE = 'fit'      # Shrink to fit inside the given size if too large, otherwise take no action
    FILL = 'fill'           # Shrink if too large, or enlarge if too small


class DisplayServer(MissingMixin, Enum):
    # https://en.wikipedia.org/wiki/Windowing_system#Display_server
    X11 = 'X11'                                 # X11 on Linux
    WAYLAND = 'Wayland'                         # Wayland on Linux
    DWM = 'Desktop Window Manager'              # Windows
    QUARTZ_COMPOSITOR = 'Quartz Compositor'     # MacOS
    OTHER = 'OTHER'
