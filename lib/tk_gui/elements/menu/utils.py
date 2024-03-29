"""
Tkinter GUI menu utils

:author: Doug Skrypa
"""

from __future__ import annotations

import logging
from abc import ABCMeta
from contextvars import ContextVar
from copy import copy
from enum import Enum
from tkinter import Event, Entry, Text, BaseWidget, TclError, StringVar
from typing import TYPE_CHECKING, Optional, Union, Any, Mapping, Iterator, Sequence, TypeVar, Callable

from tk_gui.widgets.utils import NoWidgetFound, get_root_widget
from ..exceptions import NoActiveGroup

if TYPE_CHECKING:
    from tk_gui.typing import Bool, EventCallback
    from .menu import MenuItem, MenuGroup, MenuEntry

__all__ = ['MenuMode', 'CallbackMetadata', 'MenuModeCallback', 'Mode']
log = logging.getLogger(__name__)

_NotSet = object()
_menu_group_stack = ContextVar('tk_gui.elements.menu.stack', default=[])

MenuModeCallback = Callable[['MenuEntry'], bool | Any]
Mode = Union['MenuMode', MenuModeCallback, str, bool, None]
T = TypeVar('T')


class MenuMode(Enum):
    ALWAYS = 'always'
    NEVER = 'never'         #
    KEYWORD = 'keyword'     # Enable when the specified keyword is present
    TRUTHY = 'truthy'       # Enable when the specified keyword's value is truthy
    CALLBACK = 'callback'   # Enable when the registered callback returns a truthy value

    @classmethod
    def _missing_(cls, value: Union[str, bool]):
        if value is True:
            return cls.ALWAYS
        elif value is False:
            return cls.NEVER
        try:
            return cls[value.upper().replace(' ', '_')]
        except (KeyError, AttributeError, TypeError):
            return None  # This is what the default implementation does to signal an exception should be raised

    @classmethod
    def normalize(cls, mode: Mode) -> tuple[MenuMode, MenuModeCallback | None]:
        try:
            return cls(mode), None
        except ValueError:
            if callable(mode):
                return cls.CALLBACK, mode
            raise

    def enabled(
        self, menu_entry: MenuEntry, kwargs: Mapping[str, Any] = None, keyword: str = None, cb: MenuModeCallback = None
    ) -> bool:
        try:
            return _MODE_TRUTH_MAP[self]
        except KeyError:
            pass
        if self == self.CALLBACK:
            if cb is None:
                log.warning(f'No show/enabled callback was registered for {menu_entry=}')
                return False
            return cb(menu_entry)
        elif not kwargs or not keyword:
            return False
        try:
            value = kwargs[keyword]
        except KeyError:
            return False
        if self == self.KEYWORD:
            return True
        else:
            return bool(value)

    show = enabled


_MODE_TRUTH_MAP = {MenuMode.ALWAYS: True, MenuMode.NEVER: False}


class ContainerMixin:
    members: list[Union[MenuEntry, MenuItem, MenuGroup]]

    def __enter__(self) -> ContainerMixin:
        _menu_group_stack.get().append(self)
        return self

    def __exit__(self, exc_type=None, exc_val=None, exc_tb=None):
        _menu_group_stack.get().pop()

    def __getitem__(self, index_or_label: int | str) -> Union[MenuEntry, MenuItem, MenuGroup]:
        return find_member(self.members, index_or_label)

    def __iter__(self) -> Iterator[Union[MenuEntry, MenuItem, MenuGroup]]:
        yield from self.members

    def copy(self: T) -> T:
        return copy_menu_obj(self)


def copy_menu_obj(menu_obj, parent=_NotSet):
    clone = copy(menu_obj)
    try:
        clone.members = [copy_menu_obj(m, clone) for m in clone.members]
    except AttributeError:
        pass
    if parent is not _NotSet:
        clone.parent = parent
    return clone


def find_member(
    members: Sequence[Union[MenuEntry, MenuItem, MenuGroup]], index_or_label: int | str
) -> Union[MenuEntry, MenuItem, MenuGroup]:
    try:
        return members[index_or_label]
    except TypeError:
        pass

    for member in members:
        if index_or_label == member.label:
            return member

    raise KeyError(index_or_label)


class EntryContainer(ContainerMixin):
    __slots__ = ('members',)

    def __init__(self):
        self.members: list[Union[MenuEntry, MenuItem, MenuGroup]] = []


def get_current_menu_group(silent: bool = False) -> Optional[ContainerMixin]:
    """
    Get the currently active MenuGroup.

    :param silent: If True, allow this function to return ``None`` if there is no active :class:`MenuGroup`
    :return: The active :class:`MenuGroup` object
    :raises: :class:`~.exceptions.NoActiveGroup` if there is no active MenuGroup and ``silent=False`` (default)
    """
    try:
        return _menu_group_stack.get()[-1]
    except (AttributeError, IndexError):
        if silent:
            return None
        raise NoActiveGroup('There is no active context') from None


class MenuMeta(ABCMeta, type):
    _containers: dict[tuple[str, tuple[type, ...]], EntryContainer] = {}

    @classmethod
    def __prepare__(mcs, name: str, bases: tuple[type, ...], **kwargs) -> dict:
        """
        Called before ``__new__`` and before evaluating the contents of a class, which facilitates the creation of an
        :class:`EntryContainer` that unnamed :class:`MenuEntry` instances can register themselves with.  That
        container's members are transferred to the new :class:`Menu` subclass when the subclass is created in
        :meth:`.__new__`.
        """
        mcs._containers[(name, bases)] = container = EntryContainer()
        container.__enter__()
        return {}

    def __new__(mcs, name: str, bases: tuple[type, ...], namespace: dict[str, Any], **kwargs):
        container = mcs._containers.pop((name, bases))
        container.__exit__()
        cls = super().__new__(mcs, name, bases, namespace)
        members = [m.copy() for mems in (base.members for base in bases if isinstance(base, mcs)) for m in mems]  # noqa
        cls.members = members + container.members
        del container
        return cls

    def clone(cls):
        ns = cls.__dict__.copy()
        members = ns.pop('members')
        clone = super().__new__(cls.__class__, cls.__name__, cls.__bases__, ns)  # Skip container handling
        clone.members = [m.copy() for m in members]
        return clone


class CallbackMetadata:
    __slots__ = ('menu_item', 'result', 'event', 'args', 'kwargs')

    def __init__(
        self,
        menu_item: MenuItem,
        result: Any,
        event: Event = None,
        args: Sequence[Any] = (),
        kwargs: dict[str, Any] = None,
    ):
        self.menu_item = menu_item
        self.result = result
        self.event = event
        self.args = args
        self.kwargs = kwargs

    def __repr__(self) -> str:
        content = ',\n    '.join(f'{k}={getattr(self, k)!r}' for k in self.__slots__)
        return f'<{self.__class__.__name__}(\n    {content}\n)>'


def wrap_menu_cb(
    menu_item: MenuItem,
    func: EventCallback,
    event: Event = None,
    store_meta: Bool = False,
    args: Sequence[Any] = (),
    kwargs: dict[str, Any] = None,
):
    kwargs = kwargs or {}

    def run_menu_cb():
        result = func(event, *args, **kwargs)
        if store_meta:
            result = CallbackMetadata(menu_item, result, event, args, kwargs)

        widget = event.widget if event else menu_item.root_menu.widget
        num = menu_item.root_menu.add_result(result)
        try:
            get_root_widget(widget).event_generate('<<Custom:MenuCallback>>', state=num)
        except NoWidgetFound as e:
            log.debug(f'Unable to generate menu callback event - window may have already closed: {e}')

    return run_menu_cb


# region Menu Item Text Helpers


def _ensure_str(value) -> str:
    if isinstance(value, str):
        return value
    else:
        raise TypeError(f'Unexpected type={value.__class__.__name__!r}')


def get_text(widget: Union[Entry, Text]) -> str:
    try:
        value = widget.get()
    except TypeError:
        value = widget.get(0)
    return _ensure_str(value)


def get_any_text(widget: BaseWidget) -> Optional[str]:
    try:
        return get_text(widget)  # noqa
    except (AttributeError, TypeError, TclError):
        pass

    try:
        return _ensure_str(widget['text'])
    except (TclError, TypeError):
        pass

    try:
        var: StringVar = widget['textvariable']
    except TclError:
        return None
    try:
        return _ensure_str(var.get())
    except TypeError:
        return None


def replace_selection(widget: Union[Entry, Text], text: str, first: Union[str, int], last: Union[str, int]):
    try:
        widget.replace(first, last, text)
    except AttributeError:
        widget.delete(first, last)
        widget.insert(first, text)


# endregion
