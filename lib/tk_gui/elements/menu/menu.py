"""
Tkinter GUI menus

:author: Doug Skrypa
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from itertools import count
from tkinter import Event, BaseWidget, Menu as TkMenu
from typing import TYPE_CHECKING, Optional, Union, Type, Any, Sequence

from ..element import ElementBase
from .._utils import normalize_underline
from .utils import MenuMode, ContainerMixin, MenuMeta, get_current_menu_group, wrap_menu_cb

if TYPE_CHECKING:
    from tk_gui.pseudo_elements import Row
    from tk_gui.typing import Bool, XY, EventCallback, ProvidesEventCallback

__all__ = ['Mode', 'MenuEntry', 'MenuItem', 'MenuGroup', 'Menu', 'CustomMenuItem']

Mode = Union['MenuMode', str, bool, None]


class MenuEntry(ABC):
    """An entry in a cascading menu tree, which may be a button/choice, or it may have other entries nested under it."""
    __slots__ = ('parent', 'label', '_underline', 'enabled', 'show', 'keyword', '_format_label')

    def __init__(
        self,
        label: str = None,
        underline: Union[str, int] = None,
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
        self.enabled = MenuMode(enabled)
        self.show = MenuMode(show)
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

    @property
    def root_menu(self) -> Optional[Menu]:
        parent = self.parent
        if parent is None or isinstance(parent, Menu):
            return parent
        return parent.parent

    @property
    def underline(self) -> Optional[int]:
        # TODO: Register underlined char to activate when combined with [Alt] & ensure no conflicts exist
        return normalize_underline(self._underline, self.label)

    def format_label(self, kwargs: dict[str, Any] = None) -> str:
        if self._format_label and kwargs is not None:
            return self.label.format(**kwargs)
        return self.label

    def enabled_for(self, event: Event = None, kwargs: dict[str, Any] = None) -> bool:
        return self.enabled.enabled(kwargs, self.keyword)

    def show_for(self, event: Event = None, kwargs: dict[str, Any] = None) -> bool:
        return self.show.show(kwargs, self.keyword)

    @abstractmethod
    def maybe_add(
        self, menu: TkMenu, style: dict[str, Any], event: Event = None, kwargs: dict[str, Any] = None
    ) -> bool:
        """
        Used internally when building the TK widget(s) that represent this entry.

        :param menu: The :class:`python:tkinter.Menu` widget that is being built, which this entry should be added to
          if the configured conditions are met.
        :param style: The style arguments to use for nested :class:`python:tkinter.Menu` sub-menus.
        :param event: The :class:`python:tkinter.Event` that triggered this menu to be displayed.
        :param kwargs: Keyword arguments that were provided to :meth:`Menu.show` / :meth:`Menu.popup` to provide
          context and possibly result in items being hidden/shown, enabled/disabled, or formatted to include more info.
        :return: True if this entry was added and should be shown, False if it was not added and should not be shown.
        """
        raise NotImplementedError


class MenuItem(MenuEntry):
    """A button/choice in a menu."""
    __slots__ = ('_callback', 'use_kwargs', 'store_meta')

    def __init__(
        self,
        label: str,
        callback: EventCallback | ProvidesEventCallback,
        *,
        underline: Union[str, int] = None,
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
          provided).
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
        self.use_kwargs = use_kwargs
        self.store_meta = store_meta

    def maybe_add(
        self, menu: TkMenu, style: dict[str, Any], event: Event = None, kwargs: dict[str, Any] = None
    ) -> bool:
        """
        Used internally when building the TK widget(s) that represent this entry.

        :param menu: The :class:`python:tkinter.Menu` widget that is being built, which this entry should be added to
          if the configured conditions are met.
        :param style: The style arguments to use for nested :class:`python:tkinter.Menu` sub-menus.
        :param event: The :class:`python:tkinter.Event` that triggered this menu to be displayed.
        :param kwargs: Keyword arguments that were provided to :meth:`Menu.show` / :meth:`Menu.popup` to provide
          context and possibly result in items being hidden/shown, enabled/disabled, or formatted to include more info.
        :return: True if this entry was added and should be shown, False if it was not added and should not be shown.
        """
        if not self.show_for(event, kwargs):
            return False

        callback = self._callback
        if self.use_kwargs and kwargs is not None:
            callback = wrap_menu_cb(self, callback, event, self.store_meta, kwargs=kwargs)
        else:
            callback = wrap_menu_cb(self, callback, event, self.store_meta)

        label = self.format_label(kwargs)
        menu.add_command(label=label, underline=self.underline, command=callback)
        if not self.enabled_for(event, kwargs):
            menu.entryconfigure(label, state='disabled')

        return True


class CustomMenuItem(MenuItem, ABC):
    __slots__ = ()

    def __init__(self, label: str, **kwargs):
        super().__init__(label, self.callback, **kwargs)

    @abstractmethod
    def callback(self, event: Event, **kwargs) -> Any:
        raise NotImplementedError


class MenuGroup(ContainerMixin, MenuEntry):
    """A group of menu entries that contains other nested entries."""
    __slots__ = ('members', 'hide_if_disabled')

    def __init__(
        self, label: Optional[str], underline: Union[str, int] = None, hide_if_disabled: Bool = True, **kwargs
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
        self.members: list[Union[MenuEntry, MenuItem, MenuGroup]] = []
        self.hide_if_disabled = hide_if_disabled

    def __repr__(self) -> str:
        label, underline, enabled, show = self.label, self.underline, self.enabled, self.show
        return f'<{self.__class__.__name__}({label!r}, {underline=}, {enabled=}, {show=})[members={len(self.members)}]>'

    def enabled_for(self, event: Event = None, kwargs: dict[str, Any] = None) -> bool:
        if not super().enabled_for(event, kwargs):
            return False
        return any(member.enabled_for(event, kwargs) for member in self.members)

    def maybe_add(
        self, menu: TkMenu, style: dict[str, Any], event: Event = None, kwargs: dict[str, Any] = None
    ) -> bool:
        """
        Used internally when building the TK widget(s) that represent this entry.

        :param menu: The :class:`python:tkinter.Menu` widget that is being built, which this entry should be added to
          if the configured conditions are met.
        :param style: The style arguments to use for nested :class:`python:tkinter.Menu` sub-menus.
        :param event: The :class:`python:tkinter.Event` that triggered this menu to be displayed.
        :param kwargs: Keyword arguments that were provided to :meth:`Menu.show` / :meth:`Menu.popup` to provide
          context and possibly result in items being hidden/shown, enabled/disabled, or formatted to include more info.
        :return: True if this entry was added and should be shown, False if it was not added and should not be shown.
        """
        if not self.show_for(event, kwargs):
            return False

        sub_menu = TkMenu(menu, tearoff=0, **style)
        added_any = False
        for member in self.members:
            added_any |= member.maybe_add(sub_menu, style, event, kwargs)

        cascade_kwargs = {'label': self.format_label(kwargs)}
        if not added_any or not self.enabled_for(event, kwargs):
            if self.hide_if_disabled:
                return False
            cascade_kwargs['state'] = 'disabled'

        menu.add_cascade(menu=sub_menu, underline=self.underline, **cascade_kwargs)
        return True


class Menu(ContainerMixin, ElementBase, metaclass=MenuMeta):
    """A menu bar or right-click menu"""

    _result_counter = count()
    results = {}
    widget: TkMenu
    members: Sequence[Union[MenuEntry, MenuItem, MenuGroup]]

    def __init__(self, members: Sequence[Union[MenuEntry, MenuItem, MenuGroup]] = None, **kwargs):
        """
        :param members: A sequence of menu entries that should be used as members in this menu.  Not required if this
          menu is defined as a class with groups / items defined as class members.
        :param kwargs: Additional keyword arguments to pass to :meth:`.ElementBase.__init__`
        """
        super().__init__(**kwargs)
        if members is not None:
            if self.members:
                self.members = all_members = list(self.members)
                all_members.extend(members)
            else:
                self.members = members
        for member in self.members:
            member.parent = self

    def add_result(self, result: Any) -> int:
        num = next(self._result_counter)
        self.results[num] = result
        return num

    def __enter__(self) -> Menu:
        super().__enter__()
        if self.members is self.__class__.members:
            self.members = list(self.members)
        return self

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
        style = self.style_config
        menu = TkMenu(parent, tearoff=0, takefocus=int(self.allow_focus), **style)
        for member in self.members:
            member.maybe_add(menu, style, event, kwargs)

        return menu

    def pack_into(self, row: Row, column: int):
        root = row.window._root
        self.widget = menu = self.prepare(root)
        root.configure(menu=menu)

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
