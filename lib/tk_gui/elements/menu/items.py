"""
Tkinter GUI custom menu items

:author: Doug Skrypa
"""

from __future__ import annotations

import logging
import tkinter.constants as tkc
from abc import ABC
from pathlib import Path
from tkinter import Event, BaseWidget, TclError, Menu as TkMenu, Entry, Text
from typing import TYPE_CHECKING, Union, Optional, Any, Callable
from urllib.parse import quote_plus, urlparse

from tk_gui.enums import CallbackAction
from tk_gui.elements._utils import get_selection_pos, explore, launch
from .menu import Mode, CustomMenuItem
from .utils import MenuMode, get_text, replace_selection, get_any_text

if TYPE_CHECKING:
    from ...typing import Bool

__all__ = [
    'CloseWindow',
    'SelectionMenuItem', 'CopySelection', 'PasteClipboard',
    'UpdateTextMenuItem', 'ToLowerCase', 'ToTitleCase', 'ToUpperCase',
    'OpenFileLocation', 'OpenFile', 'PlayFile',
    'SearchSelection', 'GoogleSelection', 'GoogleTranslate', 'SearchWikipedia',
    'SearchKpopFandom', 'SearchGenerasia', 'SearchDramaWiki',
]
log = logging.getLogger(__name__)

# TODO: Error popups


class CloseWindow(CustomMenuItem, label='Exit'):
    __slots__ = ()

    def __init__(self, label: str = None, *, show: Mode = MenuMode.ALWAYS, enabled: Mode = MenuMode.ALWAYS, **kwargs):
        super().__init__(label, show=show, enabled=enabled, store_meta=False, **kwargs)

    def callback(self, event: Event, **kwargs):
        return CallbackAction.EXIT


# region Selection Menu Items


class SelectionMenuItem(CustomMenuItem, ABC, keyword='selection'):
    __slots__ = ()

    def __init__(self, *args, enabled: Mode = MenuMode.TRUTHY, **kwargs):
        kwargs['use_kwargs'] = True
        super().__init__(*args, enabled=enabled, **kwargs)

    def get_widget(self, event: Event | None, kwargs: dict[str, Any]) -> BaseWidget:
        try:
            if self.keyword in kwargs:
                # log.debug(f'get_widget: skipping {keyword=} - {kwargs=}')
                raise _SkipSelection
        except TypeError:  # kwargs is None
            raise _SkipSelection from None

        try:
            widget: BaseWidget = event.widget
        except AttributeError:
            raise _SkipSelection from None
        else:
            return widget

    def maybe_add_selection(self, event: Event | None, kwargs: dict[str, Any] | None):
        try:
            widget = self.get_widget(event, kwargs)
        except _SkipSelection:
            return

        if selection := _get_selection(widget):
            kwargs[self.keyword] = selection

    def maybe_add(
        self, menu: TkMenu, style: dict[str, Any], event: Event, kwargs: dict[str, Any] | None, cb_inst=None
    ) -> bool:
        self.maybe_add_selection(event, kwargs)
        return super().maybe_add(menu, style, event, kwargs, cb_inst)


class SelectionOrFullMenuItem(SelectionMenuItem, ABC, keyword='permissive_selection'):
    __slots__ = ()

    def maybe_add_selection(self, event: Event | None, kwargs: dict[str, Any] | None):
        try:
            widget = self.get_widget(event, kwargs)
        except _SkipSelection:
            return

        # TODO: Add handling for things like table (Treeview) cells/rows?
        if selection := _get_selection(widget):
            kwargs[self.keyword] = selection
            # log.debug(f'maybe_add_selection: found {selection=}')
            return

        try:
            if text := get_any_text(widget):
                kwargs[self.keyword] = text
                # log.debug(f'maybe_add_selection: found full {text=}')
        except (TclError, AttributeError, KeyError):
            # log.debug(f'Could not add selection due to: {e}')
            pass


def _get_selection(widget: BaseWidget) -> Optional[str]:
    try:
        if widget == widget.selection_own_get():
            return widget.selection_get()
    except TclError:
        return None


class CopySelection(SelectionOrFullMenuItem, label='Copy'):
    __slots__ = ()

    def __init__(self, label: str = None, *, underline: Union[str, int] = 0, show: Mode = MenuMode.ALWAYS, **kwargs):
        super().__init__(label, underline=underline, show=show, store_meta=True, **kwargs)

    def callback(self, event: Event, **kwargs):
        if selection := kwargs.get(self.keyword):
            widget: BaseWidget = event.widget
            widget.clipboard_clear()
            widget.clipboard_append(selection)
            return selection  # provides confirmation of what was copied


class PasteClipboard(CustomMenuItem, label='Paste'):
    __slots__ = ()

    def __init__(
        self,
        label: str = None,
        *,
        underline: Union[str, int] = 0,
        show: Mode = MenuMode.ALWAYS,
        enabled: Mode = MenuMode.ALWAYS,
        **kwargs,
    ):
        super().__init__(label, underline=underline, show=show, store_meta=True, enabled=enabled, **kwargs)

    def enabled_for(self, event: Event = None, kwargs: dict[str, Any] = None) -> bool:
        widget: BaseWidget = event.widget
        try:
            if widget['state'] != 'normal':
                return False
        except TclError:
            return False
        return hasattr(widget, 'insert')

    def callback(self, event: Event, **kwargs):
        widget: BaseWidget = event.widget
        try:
            if widget['state'] != 'normal':
                return
        except TclError:
            return

        first, last = get_selection_pos(widget, raw=True)  # noqa
        try:
            text = widget.clipboard_get()
            if first is None:
                widget.insert('insert', text)  # noqa
            else:
                replace_selection(widget, text, first, last)  # noqa
        except (AttributeError, TclError):
            pass


# endregion


# region File Handling Menu Items


class _PathMenuItem(SelectionMenuItem, ABC):
    __slots__ = ()

    def __init__(self, label: str = None, *, show: Mode = MenuMode.ALWAYS, enabled: Mode = MenuMode.ALWAYS, **kwargs):
        super().__init__(label, show=show, enabled=enabled, store_meta=True, **kwargs)

    @classmethod
    def _normalize(cls, text: str) -> Optional[Path]:
        path = Path(text.strip())
        if path.exists():
            return path
        return None

    def get_path(self, event: Event, kwargs: dict[str, Any]) -> Optional[Path]:
        if selection := kwargs.get(self.keyword):
            if path := self._normalize(selection):
                return path
        # The below works with `SelectionMenuItem` in some cases where omitting the below and
        # using `SelectionOrFullMenuItem` does not work
        if text := get_any_text(event.widget):
            return self._normalize(text)
        return None

    def enabled_for(self, event: Event = None, kwargs: dict[str, Any] = None) -> bool:
        return self.get_path(event, kwargs) is not None


class OpenFileLocation(_PathMenuItem, label='Open in File Manager'):
    __slots__ = ()

    def callback(self, event: Event, **kwargs):
        if path := self.get_path(event, kwargs):
            explore(path)


class OpenFile(_PathMenuItem, label='Open File'):
    __slots__ = ()

    def callback(self, event: Event, **kwargs):
        if path := self.get_path(event, kwargs):
            launch(path)


class PlayFile(OpenFile, label='Play File'):
    __slots__ = ()


# endregion


# region Text Manipulation


class UpdateTextMenuItem(SelectionMenuItem, ABC):
    """
    Abstract base class for menu items that act on text selected in a given widget.  To define a new menu item that
    uses this functionality, this class should be extended, with the ``update_func`` class init parameter provided.

    See :class:`ToUpperCase`, :class:`ToLowerCase`, and :class:`ToTitleCase` for examples of how to do so.

    """
    __slots__ = ()

    _update_func: Optional[Callable[[str], str]] = None

    def __init_subclass__(cls, update_func: Callable[[str], str] = None, **kwargs):
        """
        :param update_func: Function that accepts a single str parameter and returns the str that should replace the
          provided text.
        """
        super().__init_subclass__(**kwargs)
        if update_func is not None:
            cls._update_func = update_func

    def __init__(self, label: str = None, *, show: Mode = MenuMode.ALWAYS, enabled: Mode = MenuMode.ALWAYS, **kwargs):
        super().__init__(label, show=show, enabled=enabled, store_meta=True, **kwargs)

    def show_for(self, event: Event = None, kwargs: dict[str, Any] = None) -> bool:
        widget: BaseWidget = event.widget
        try:
            if widget['state'] != 'normal':
                return False
        except TclError:
            return False
        return hasattr(widget, 'insert')

    @classmethod  # Must be a classmethod, otherwise str methods get confused
    def update_text(cls, text: str) -> str:
        if (func := cls._update_func) is not None:
            return func(text)
        raise NotImplementedError

    def _update_widget(self, widget: Union[Entry, Text], kwargs: dict[str, Any]):
        selection = kwargs.get(self.keyword)
        text = selection or get_text(widget)
        if (updated := self.update_text(text)) == text:
            return
        elif selection:
            first, last = get_selection_pos(widget, raw=True)
            if not (first is last is None):
                replace_selection(widget, updated, first, last)
                return

        # Either there was no selection, or there was no selection position
        widget.delete(0, tkc.END)
        widget.insert(0, updated)

    def callback(self, event: Event, **kwargs):
        widget: Union[Entry, Text] = event.widget
        try:
            if widget['state'] != 'normal':
                return
        except TclError:
            return
        try:
            self._update_widget(widget, kwargs)
        except (AttributeError, TclError):
            pass


class ToUpperCase(UpdateTextMenuItem, update_func=str.upper, label='Change case: Upper'):
    __slots__ = ()


class ToLowerCase(UpdateTextMenuItem, update_func=str.lower, label='Change case: Lower'):
    __slots__ = ()


class ToTitleCase(UpdateTextMenuItem, update_func=str.title, label='Change case: Title'):
    __slots__ = ()


# endregion


# region Search Engines


class SearchSelection(SelectionOrFullMenuItem, ABC):
    __slots__ = ('quote',)
    title: str
    url_fmt: str

    def __init_subclass__(cls, url: str, title: str = None):  # noqa
        expected = '{query}'
        if expected not in url:
            raise ValueError(f'Invalid {url=} - expected a format string with {expected!r} in place of the query')
        if title is None:
            title = urlparse(url).hostname
            if title.startswith('www.') and len(title) > 4:
                title = title[4:]

        cls.title = title
        cls.url_fmt = url

    def __init__(self, label: str = None, *, keyword: str = 'selection', quote: Bool = True, **kwargs):
        if label is None:
            label = f'Search {self.title} for {{{keyword}!r}}'
        kwargs['format_label'] = True
        super().__init__(label, keyword=keyword, **kwargs)
        self.quote = quote

    def callback(self, event: Event, **kwargs):
        if not (selection := kwargs.get(self.keyword)):
            return

        import webbrowser

        if self.quote:
            selection = quote_plus(selection)

        url = self.url_fmt.format(query=selection)
        log.debug(f'Opening {url=}')
        webbrowser.open(url)


class GoogleSelection(SearchSelection, title='Google', url='https://www.google.com/search?q={query}'):
    __slots__ = ()


class GoogleTranslate(SearchSelection, url='https://translate.google.com/?sl=auto&tl=en&text={query}&op=translate'):
    __slots__ = ()

    def __init__(self, label: str = None, *, keyword: str = 'selection', **kwargs):
        super().__init__(label or f'Translate {{{keyword}!r}}', keyword=keyword, **kwargs)


class SearchWikipedia(
    SearchSelection,
    title='Wikipedia',
    url='https://en.wikipedia.org/w/index.php?search={query}&title=Special%3ASearch&fulltext=Search&ns0=1',
):
    __slots__ = ()


class SearchKpopFandom(SearchSelection, url='https://kpop.fandom.com/wiki/Special:Search?scope=internal&query={query}'):
    __slots__ = ()


class SearchGenerasia(
    SearchSelection, url='https://www.generasia.com/w/index.php?title=Special%3ASearch&fulltext=Search&search={query}'
):
    __slots__ = ()


class SearchDramaWiki(SearchSelection, title='DramaWiki', url='https://wiki.d-addicts.com/index.php?search={query}'):
    __slots__ = ()


# endregion


class _SkipSelection(Exception):
    """Internal exception for selection-based menu items"""
