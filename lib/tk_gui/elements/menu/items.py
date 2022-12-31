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
from .._utils import get_selection_pos
from .menu import Mode, CustomMenuItem
from .utils import MenuMode, get_text, replace_selection, flip_name_parts, get_any_text, explore, launch

if TYPE_CHECKING:
    from ...typing import Bool

__all__ = [
    'CloseWindow',
    'SelectionMenuItem', 'CopySelection', 'PasteClipboard',
    'FlipNameParts', 'ToLowerCase', 'ToTitleCase', 'ToUpperCase',
    'OpenFileLocation', 'OpenFile', 'PlayFile',
    'SearchSelection', 'GoogleSelection', 'GoogleTranslate', 'SearchWikipedia',
    'SearchKpopFandom', 'SearchGenerasia', 'SearchDramaWiki',
]
log = logging.getLogger(__name__)

# TODO: Error popups


class CloseWindow(CustomMenuItem):
    __slots__ = ()

    def __init__(self, label: str = 'Exit', *, show: Mode = MenuMode.ALWAYS, enabled: Mode = MenuMode.ALWAYS, **kwargs):
        super().__init__(label, show=show, enabled=enabled, store_meta=False, **kwargs)

    def callback(self, event: Event, **kwargs):
        return CallbackAction.EXIT


# region Selection Menu Items


class SelectionMenuItem(CustomMenuItem, ABC):
    __slots__ = ()

    def __init__(self, *args, enabled: Mode = MenuMode.TRUTHY, keyword: str = 'selection', **kwargs):
        kwargs['use_kwargs'] = True
        super().__init__(*args, enabled=enabled, keyword=keyword, **kwargs)

    def maybe_add_selection(self, event: Event | None, kwargs: dict[str, Any] | None):
        if kwargs is None or self.keyword in kwargs:
            return
        try:
            widget: BaseWidget = event.widget
        except AttributeError:
            return
        try:
            if widget != widget.selection_own_get():
                return
            kwargs[self.keyword] = widget.selection_get()
        # except TclError as e:  # When no selection exists
        except TclError:
            # log.debug(f'Error getting selection: {e}')
            pass

    def maybe_add(
        self, menu: TkMenu, style: dict[str, Any], event: Event, kwargs: dict[str, Any] | None, cb_inst=None
    ) -> bool:
        self.maybe_add_selection(event, kwargs)
        return super().maybe_add(menu, style, event, kwargs, cb_inst)


class SelectionOrFullMenuItem(SelectionMenuItem, ABC):
    __slots__ = ()

    def maybe_add_selection(self, event: Event | None, kwargs: dict[str, Any] | None):
        if kwargs is None or self.keyword in kwargs:
            return
        try:
            widget: BaseWidget = event.widget
        except AttributeError:
            return
        try:
            if widget == widget.selection_own_get() and (selection := widget.selection_get()):
                kwargs[self.keyword] = selection
            else:
                element = self.root_menu.window[widget]
                if value := element.value:
                    kwargs[self.keyword] = value
        except (TclError, AttributeError, KeyError):
            pass


class CopySelection(SelectionOrFullMenuItem):
    __slots__ = ()

    def __init__(self, label: str = 'Copy', *, underline: Union[str, int] = 0, show: Mode = MenuMode.ALWAYS, **kwargs):
        super().__init__(label, underline=underline, show=show, store_meta=True, **kwargs)

    def callback(self, event: Event, **kwargs):
        if selection := kwargs.get(self.keyword):
            widget: BaseWidget = event.widget
            widget.clipboard_clear()
            widget.clipboard_append(selection)
            return selection  # provides confirmation of what was copied


class PasteClipboard(SelectionMenuItem):
    __slots__ = ()

    def __init__(
        self,
        label: str = 'Paste',
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

    def __init__(self, label: str, *, show: Mode = MenuMode.ALWAYS, enabled: Mode = MenuMode.ALWAYS, **kwargs):
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
        if text := get_any_text(event.widget):
            return self._normalize(text)
        return None

    def enabled_for(self, event: Event = None, kwargs: dict[str, Any] = None) -> bool:
        return self.get_path(event, kwargs) is not None


class OpenFileLocation(_PathMenuItem):
    __slots__ = ()

    def __init__(self, label: str = 'Open in File Manager', **kwargs):
        super().__init__(label, **kwargs)

    def callback(self, event: Event, **kwargs):
        if path := self.get_path(event, kwargs):
            explore(path)


class OpenFile(_PathMenuItem):
    __slots__ = ()

    def __init__(self, label: str = 'Open File', **kwargs):
        super().__init__(label, **kwargs)

    def callback(self, event: Event, **kwargs):
        if path := self.get_path(event, kwargs):
            launch(path)


class PlayFile(OpenFile):
    __slots__ = ()

    def __init__(self, label: str = 'Play File', **kwargs):
        super().__init__(label, **kwargs)


# endregion


# region Text Manipulation


class _UpdateTextMenuItem(SelectionMenuItem, ABC):
    __slots__ = ()

    _update_func: Optional[Callable[[str], str]] = None

    def __init_subclass__(cls, update_func: Callable[[str], str] = None):  # noqa
        if update_func is not None:
            cls._update_func = update_func

    def __init__(self, label: str, *, show: Mode = MenuMode.ALWAYS, enabled: Mode = MenuMode.ALWAYS, **kwargs):
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
        if selection := kwargs.get(self.keyword):
            first, last = get_selection_pos(widget, raw=True)
            if (updated := self.update_text(selection)) != selection:
                replace_selection(widget, updated, first, last)
        else:
            text = get_text(widget)
            if (updated := self.update_text(text)) != text:
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


class FlipNameParts(_UpdateTextMenuItem, update_func=flip_name_parts):
    __slots__ = ()

    def __init__(self, label: str = 'Flip name parts', **kwargs):
        super().__init__(label, **kwargs)


class ToUpperCase(_UpdateTextMenuItem, update_func=str.upper):
    __slots__ = ()

    def __init__(self, label: str = 'Change case: Upper', **kwargs):
        super().__init__(label, **kwargs)


class ToLowerCase(_UpdateTextMenuItem, update_func=str.lower):
    __slots__ = ()

    def __init__(self, label: str = 'Change case: Lower', **kwargs):
        super().__init__(label, **kwargs)


class ToTitleCase(_UpdateTextMenuItem, update_func=str.title):
    __slots__ = ()

    def __init__(self, label: str = 'Change case: Title', **kwargs):
        super().__init__(label, **kwargs)


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
