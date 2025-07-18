"""
Tkinter GUI menus

:author: Doug Skrypa
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from functools import partial
from tkinter import Event, BaseWidget, Menu as TkMenu
from typing import TYPE_CHECKING, Any, Generic, Sequence, Type, TypeVar

from tk_gui.event_handling import CustomEventResultsMixin
from ..element import ElementBase, Element
from ..exceptions import CallbackError, CallbackAlreadyRegistered, NoCallbackRegistered
from .._utils import normalize_underline
from .utils import MenuMode, MenuModeCallback, Mode, ContainerMixin, MenuMeta
from .utils import get_current_menu_group, wrap_menu_cb, find_member, copy_menu_obj

if TYPE_CHECKING:
    from tk_gui.geometry.typing import XY
    from tk_gui.popups.base import PopupMixin
    from tk_gui.pseudo_elements.row import Row, RowBase
    from tk_gui.typing import Bool, EventCallback, ProvidesEventCallback, Top, HasFrame

__all__ = ['MenuEntry', 'MenuItem', 'MenuGroup', 'Menu', 'CustomMenuItem', 'MenuProperty']
log = logging.getLogger(__name__)

M = TypeVar('M', bound='Menu')
T = TypeVar('T')


class MenuEntry(ABC):
    """An entry in a cascading menu tree, which may be a button/choice, or it may have other entries nested under it."""

    __slots__ = (
        'parent', 'label', '_underline', 'enabled', 'show', 'keyword', '_format_label', '_enabled_cb', '_show_cb'
    )

    parent: MenuGroup | Menu | None
    label: str | None
    enabled: MenuMode
    show: MenuMode
    keyword: str | None
    _enabled_cb: MenuModeCallback | None
    _show_cb: MenuModeCallback | None

    def __init__(
        self,
        label: str = None,
        underline: str | int = None,
        enabled: Mode = MenuMode.ALWAYS,
        show: Mode = MenuMode.ALWAYS,
        keyword: str = None,
        format_label: Bool = False,
    ):
        """
        :param label: The label to be displayed for this menu entry.
        :param underline: The character(s) in the label to underline, or the index of the char to underline, if any.
        :param enabled: When / whether this entry should be enabled in the menu.
        :param show: When / whether this entry should be displayed in the menu.  Defaults to ``MenuMode.ALWAYS`` unless
          the ``keyword`` parameter is provided.
        :param keyword: The keyword in the context dictionary that would indicate that this entry should be shown /
          enabled if their respective modes are set to ``MenuMode.KEYWORD`` or ``MenuMode.TRUTHY``.  The ``show``
          parameter will default to ``MenuMode.KEYWORD`` if this parameter is provided.
        :param format_label: Whether the label should be treated as a format string to be used with the context
          dictionary of kwargs, or if it is a static label.  Defaults to static.
        """
        self.label = label
        self._underline = underline
        self.enabled, self._enabled_cb = MenuMode.normalize(enabled)
        self.show, self._show_cb = MenuMode.normalize(show)
        self.keyword = keyword
        self._format_label = format_label
        if group := get_current_menu_group(True):
            group.members.append(self)
            self.parent = group
        else:
            self.parent = None

    def __set_name__(self, owner: Type[Menu], name: str):
        if not self.label:
            self.label = name

    def __repr__(self) -> str:
        underline, enabled, show = self._underline, self.enabled, self.show
        return f'<{self.__class__.__name__}({self.label!r}, {underline=}, {enabled=}, {show=})>'

    def copy(self: T) -> T:
        return copy_menu_obj(self, None)

    @property
    def root_menu(self) -> Menu | None:
        parent = self.parent
        if parent is None or isinstance(parent, Menu):
            return parent
        return parent.parent

    @property
    def underline(self) -> int | None:
        # TODO: Register underlined char to activate when combined with [Alt] & ensure no conflicts exist
        return normalize_underline(self._underline, self.label)

    def format_label(self, kwargs: dict[str, Any] = None) -> str:
        if self._format_label and kwargs is not None:
            return self.label.format(**kwargs)
        return self.label

    def enabled_for(self, event: Event = None, kwargs: dict[str, Any] = None) -> bool:
        return self.enabled.enabled(self, kwargs, self.keyword, self._enabled_cb)

    def show_for(self, event: Event = None, kwargs: dict[str, Any] = None) -> bool:
        return self.show.show(self, kwargs, self.keyword, self._show_cb)

    @abstractmethod
    def maybe_add(
        self, menu: TkMenu, style: dict[str, Any], event: Event | None, kwargs: dict[str, Any] | None, cb_inst=None
    ) -> bool:
        """
        Used internally when building the TK widget(s) that represent this entry.

        :param menu: The :class:`python:tkinter.Menu` widget that is being built, which this entry should be added to
          if the configured conditions are met.
        :param style: The style arguments to use for nested :class:`python:tkinter.Menu` sub-menus.
        :param event: The :class:`python:tkinter.Event` that triggered this menu to be displayed.
        :param kwargs: Keyword arguments that were provided to :meth:`Menu.show` / :meth:`Menu.popup` to provide
          context and possibly result in items being hidden/shown, enabled/disabled, or formatted to include more info.
        :param cb_inst: If an item's callback was registered late via the :meth:`MenuItem.callback` method, this will
          be the instance of the callback method's class for which the callback is being called.
        :return: True if this entry was added and should be shown, False if it was not added and should not be shown.
        """
        raise NotImplementedError


class MenuItem(MenuEntry):
    """A button/choice in a menu."""
    __slots__ = ('_callback', 'use_kwargs', 'store_meta', '_method')

    def __init__(
        self,
        label: str,
        callback: EventCallback | ProvidesEventCallback | Type[PopupMixin] = None,
        *,
        underline: str | int = None,
        enabled: Mode = MenuMode.ALWAYS,
        show: Mode = None,
        keyword: str = None,
        use_kwargs: Bool = False,
        format_label: Bool = False,
        store_meta: Bool = False,
    ):
        """
        :param label: The label to be displayed for this menu item.
        :param callback: A callback function/method that accepts a :class:`python:tkinter.Event` as a positional
          argument, or a :class:`.Popup` or other object with a ``as_callback`` method (classmethod if a class is
          provided).  If not provided,
        :param underline: The character(s) in the label to underline, or the index of the char to underline, if any.
        :param enabled: When / whether this item should be enabled in the menu.
        :param show: When / whether this item should be displayed in the menu.  Defaults to ``MenuMode.ALWAYS`` unless
          the ``keyword`` parameter is provided.
        :param keyword: The keyword in the context dictionary that would indicate that this item should be shown /
          enabled if their respective modes are set to ``MenuMode.KEYWORD`` or ``MenuMode.TRUTHY``.  The ``show``
          parameter will default to ``MenuMode.KEYWORD`` if this parameter is provided.
        :param use_kwargs: Whether the context dictionary of kwargs should be included in the arguments when the
          callback is called.  Defaults to False.
        :param format_label: Whether the label should be treated as a format string to be used with the context
          dictionary of kwargs, or if it is a static label.  Defaults to static.
        :param store_meta: Whether the result of calling the callback should be stored in a :class:`.CallbackMetadata`
          wrapper or not.  Defaults to False.
        """
        if show is None:
            show = MenuMode.KEYWORD if keyword else MenuMode.ALWAYS
        super().__init__(label, underline, enabled, show, keyword, format_label)
        try:
            self._callback = callback.as_callback()
        except AttributeError:
            self._callback = callback
        self._method = False
        self.use_kwargs = use_kwargs
        self.store_meta = store_meta

    def callback(self, func: EventCallback, method: bool = True) -> EventCallback:
        if self._callback is not None:
            raise CallbackAlreadyRegistered(
                f'Unable to register {func=} as a callback for {self} - {self._callback} is already registered'
            )
        self._callback = func
        self._method = method
        return func

    def maybe_add(
        self, menu: TkMenu, style: dict[str, Any], event: Event | None, kwargs: dict[str, Any] | None, cb_inst=None
    ) -> bool:
        """
        Used internally when building the TK widget(s) that represent this entry.

        :param menu: The :class:`python:tkinter.Menu` widget that is being built, which this entry should be added to
          if the configured conditions are met.
        :param style: The style arguments to use for nested :class:`python:tkinter.Menu` sub-menus.
        :param event: The :class:`python:tkinter.Event` that triggered this menu to be displayed.
        :param kwargs: Keyword arguments that were provided to :meth:`Menu.show` / :meth:`Menu.popup` to provide
          context and possibly result in items being hidden/shown, enabled/disabled, or formatted to include more info.
        :param cb_inst: If the callback was registered late via the :meth:`.callback` method, this will be the instance
          of the callback method's class for which the callback is being called.
        :return: True if this entry was added and should be shown, False if it was not added and should not be shown.
        """
        if not self.show_for(event, kwargs):
            return False

        if (callback := self._callback) is None:
            raise NoCallbackRegistered(f'No callback was registered for {self}')
        if self._method:
            if cb_inst is None:
                raise CallbackError(
                    f'Invalid callback for {self} - menus containing items with methods registered as callbacks'
                    ' must be accessed through the MenuProperty descriptor'
                )
            else:
                callback = partial(callback, cb_inst)

        if self.use_kwargs and kwargs is not None:
            callback = wrap_menu_cb(self, callback, event, self.store_meta, kwargs=kwargs)
        else:
            callback = wrap_menu_cb(self, callback, event, self.store_meta)

        label = self.format_label(kwargs)
        menu.add_command(label=label, underline=self.underline, command=callback)
        if not self.enabled_for(event, kwargs):
            # log.debug(f'NOT enabled for {event=}, {kwargs=}: {self}')
            menu.entryconfigure(label, state='disabled')

        return True


class CustomMenuItem(MenuItem, ABC):
    __slots__ = ()
    _default_keyword: str = None
    _default_label: str = None

    def __init_subclass__(cls, keyword: str = None, label: str = None, **kwargs):
        """
        :param keyword: The default keyword to use for this menu item.  It may be overridden at the instance level.
        :param label: The default label to use for this menu item.  It may be overridden at the instance level.
        """
        super().__init_subclass__(**kwargs)
        if keyword:
            cls._default_keyword = keyword
        if label:
            cls._default_label = label

    def __init__(self, label: str, *, keyword: str = None, **kwargs):
        if keyword is None:
            keyword = self._default_keyword
        if label is None:
            label = self._default_label
        super().__init__(label, self.callback, keyword=keyword, **kwargs)

    @abstractmethod
    def callback(self, event: Event, **kwargs) -> Any:
        raise NotImplementedError


class MenuGroup(ContainerMixin, MenuEntry):
    """A group of menu entries that contains other nested entries."""
    __slots__ = ('members', 'hide_if_disabled')

    def __init__(
        self, label: str | None, underline: str | int = None, hide_if_disabled: Bool = True, **kwargs
    ):
        """
        :param label: The label to be displayed for this menu entry.
        :param underline: The character(s) in the label to underline, or the index of the char to underline, if any.
        :param hide_if_disabled: Whether this group of entries should be hidden when it is disabled or if no members
          within the group were shown.  Defaults to True.
        :param kwargs: Additional keyword arguments to pass thru to :meth:`MenuEntry.__init__`.
        """
        # TODO: Add a way to define a menu more like a Window's layout?
        super().__init__(label, underline, **kwargs)
        self.members: list[MenuMember] = []
        self.hide_if_disabled = hide_if_disabled

    def __repr__(self) -> str:
        label, underline, enabled, show = self.label, self.underline, self.enabled, self.show
        return f'<{self.__class__.__name__}({label!r}, {underline=}, {enabled=}, {show=})[members={len(self.members)}]>'

    def enabled_for(self, event: Event = None, kwargs: dict[str, Any] = None) -> bool:
        if not super().enabled_for(event, kwargs):
            return False
        return any(member.enabled_for(event, kwargs) for member in self.members)

    def maybe_add(
        self, menu: TkMenu, style: dict[str, Any], event: Event | None, kwargs: dict[str, Any] | None, cb_inst=None
    ) -> bool:
        """
        Used internally when building the TK widget(s) that represent this entry.

        :param menu: The :class:`python:tkinter.Menu` widget that is being built, which this entry should be added to
          if the configured conditions are met.
        :param style: The style arguments to use for nested :class:`python:tkinter.Menu` sub-menus.
        :param event: The :class:`python:tkinter.Event` that triggered this menu to be displayed.
        :param kwargs: Keyword arguments that were provided to :meth:`Menu.show` / :meth:`Menu.popup` to provide
          context and possibly result in items being hidden/shown, enabled/disabled, or formatted to include more info.
        :param cb_inst: If an item's callback was registered late via the :meth:`MenuItem.callback` method, this will
          be the instance of the callback method's class for which the callback is being called.
        :return: True if this entry was added and should be shown, False if it was not added and should not be shown.
        """
        if not self.show_for(event, kwargs):
            # log.debug(f'Not showing menu group={self!r}')
            return False

        sub_menu = TkMenu(menu, tearoff=0, **style)
        added_any = False
        for member in self.members:
            added_any |= member.maybe_add(sub_menu, style, event, kwargs, cb_inst)

        # log.debug(f'maybe_add: {added_any=} for group={self!r}')
        cascade_kwargs = {'label': self.format_label(kwargs)}
        if not added_any or not self.enabled_for(event, kwargs):
            if self.hide_if_disabled:
                return False
            cascade_kwargs['state'] = 'disabled'

        menu.add_cascade(menu=sub_menu, underline=self.underline, **cascade_kwargs)
        return True


MenuMember = MenuEntry | MenuItem | MenuGroup


class Menu(CustomEventResultsMixin, ContainerMixin, ElementBase, metaclass=MenuMeta, base_style_layer='menu'):
    """A menu bar or right-click menu"""

    widget: TkMenu
    parent: RowBase | HasFrame | Element | None
    members: Sequence[MenuMember]

    def __init__(self, members: Sequence[MenuMember] = None, cb_inst=None, **kwargs):
        """
        :param members: A sequence of menu entries that should be used as members in this menu.  Not required if this
          menu is defined as a class with groups / items defined as class members.
        :param cb_inst: If an item's callback was registered late via the :meth:`MenuItem.callback` method, this will
          be the instance of the callback method's class for which the callback is being called.
        :param kwargs: Additional keyword arguments to pass to :meth:`.ElementBase.__init__`
        """
        super().__init__(**kwargs)
        self.cb_inst = cb_inst
        if members is not None:
            if self.members:
                self.members = all_members = list(self.members)
                all_members.extend(members)
            else:
                self.members = members
        for member in self.members:
            member.parent = self

    def __enter__(self) -> Menu:
        super().__enter__()
        if self.members is self.__class__.members:
            self.members = list(self.members)
        return self

    # region Common Methods

    @property
    def style_config(self) -> dict[str, Any]:
        style = self.style
        return {
            **style.get_map('menu', font='font', fg='fg', bg='bg', bd='border_width', relief='relief'),
            **style.get_map('menu', 'disabled', disabledforeground='fg'),
            **style.get_map('menu', 'active', activeforeground='fg', activebackground='bg'),
            **self._style_config,
        }

    def prepare(self, parent: BaseWidget = None, event: Event = None, kwargs: dict[str, Any] = None) -> TkMenu:
        """Used to initialize / populate the tkinter Menu for both menu bars and popup/right-click menus."""
        style = self.style_config
        menu = TkMenu(parent, tearoff=0, takefocus=int(self.allow_focus), **style)
        cb_inst = self.cb_inst
        for member in self.members:
            # TODO: Add way to support separators (to be translated to `tkinter.Menu.add_separator(...)` calls)
            member.maybe_add(menu, style, event, kwargs, cb_inst)
            # log.debug(f'Menu.prepare: {added=} for {member=}')

        return menu

    # endregion

    # region Menu Bar Methods

    def _init_widget(self, tk_top_level: Top):
        self.widget = menu = self.prepare(tk_top_level)
        tk_top_level.configure(menu=menu)  # Only Tk and Toplevel support menu bars

    def pack_into(self, row: Row):
        self._init_widget(row.window.root)

    def grid_into(self, parent: HasFrame, row: int, column: int, **kwargs):
        self._init_widget(parent.window.root)

    # endregion

    # region Menu Popup Methods

    def show(self, event: Event, parent: BaseWidget = None, **kwargs):
        return self.popup((event.x_root, event.y_root), parent, event, **kwargs)

    def popup(self, position: XY = None, parent: BaseWidget = None, event: Event = None, **kwargs):
        menu = self.prepare(parent, event, kwargs)
        try:
            _x, _y = position
        except (TypeError, ValueError):
            position = self.window.mouse_position
        try:
            menu.tk_popup(*position)
        finally:
            menu.grab_release()

    # endregion


class MenuProperty(Generic[M]):
    __slots__ = ('menu_cls',)

    def __init__(self, menu_cls: Type[M], clone: Bool = True):
        self.menu_cls = menu_cls.clone() if clone else menu_cls
        # TODO: Refactor Menu callbacks to be more like button callbacks

    def __get__(self, instance, owner) -> MenuProperty | M:
        if instance is None:
            return self
        return self.menu_cls(cb_inst=instance)

    def __getitem__(self, index_or_label: int | str) -> MenuMember:
        return find_member(self.menu_cls.members, index_or_label)
