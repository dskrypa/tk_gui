"""
Link handling for Text elements.
"""

from __future__ import annotations

import logging
import webbrowser
from abc import ABC, abstractmethod
from pathlib import Path
from stat import S_IFMT, S_IFDIR, S_IFREG
from typing import TYPE_CHECKING, Optional, Union

from tk_gui.constants import LEFT_CLICK, CTRL_LEFT_CLICK
from tk_gui.elements._utils import explore, launch

if TYPE_CHECKING:
    from tkinter import Event
    from tk_gui.typing import Bool, BindTarget

__all__ = ['LinkTarget', 'UrlLink', 'PathLink', 'CallbackLink']
log = logging.getLogger(__name__)

_Link = Union[bool, str, 'BindTarget', Path, None]


class LinkTarget(ABC):
    __slots__ = ('bind', '_tooltip', 'use_link_style')

    def __init__(self, bind: str, tooltip: str = None, use_link_style: Bool = True):
        self.bind = bind
        self._tooltip = tooltip
        self.use_link_style = use_link_style

    @property
    def tooltip(self) -> Optional[str]:
        return self._tooltip

    @abstractmethod
    def open(self, event: Event):
        raise NotImplementedError

    @classmethod
    def new(
        cls, value: _Link, bind: str = None, tooltip: str = None, text: str = None, use_link_style: Bool = True
    ) -> Optional[LinkTarget]:
        if not value:
            return None
        elif isinstance(value, LinkTarget):
            return value
        elif value is True:
            value = text

        if isinstance(value, str):
            if value.startswith(('http://', 'https://')):
                return UrlLink(value, bind, tooltip, use_link_style, url_in_tooltip=value != text)

            path = Path(value)
            try:
                exists = path.exists()
            except OSError:
                exists = False
            if exists:
                return PathLink(path, bind, tooltip, use_link_style, path_in_tooltip=path.as_posix() != text)

            log.debug(f'Ignoring invalid url={value!r}')
            return None
        elif isinstance(value, Path):
            return PathLink(value, bind, tooltip, use_link_style, path_in_tooltip=value.as_posix() != text)
        else:
            return CallbackLink(value, bind, tooltip, use_link_style)


class UrlLink(LinkTarget):
    __slots__ = ('url', 'url_in_tooltip')

    def __init__(
        self,
        url: str = None,
        bind: str = None,
        tooltip: str = None,
        use_link_style: Bool = True,
        url_in_tooltip: Bool = False,
    ):
        super().__init__(CTRL_LEFT_CLICK if not bind and url else bind, tooltip, use_link_style)
        self.url = url
        self.url_in_tooltip = url_in_tooltip

    @property
    def tooltip(self) -> str:
        tooltip = self._tooltip
        if not (url := self.url):
            return tooltip

        link_text = url if self.url_in_tooltip else 'link'
        prefix = f'{tooltip}; open' if tooltip else 'Open'
        suffix = ' with ctrl + click' if self.bind == CTRL_LEFT_CLICK else ''
        return f'{prefix} {link_text} in a browser{suffix}'

    def open(self, event: Event):
        if url := self.url:
            webbrowser.open(url)


class PathLink(LinkTarget):
    __slots__ = ('path', 'path_in_tooltip', 'in_file_manager')
    path: Path | None
    _mode_type_map = {S_IFREG: 'file', S_IFDIR: 'directory'}

    def __init__(
        self,
        path: str | Path = None,
        bind: str = None,
        tooltip: str = None,
        use_link_style: Bool = True,
        path_in_tooltip: Bool = False,
        in_file_manager: Bool = True,
    ):
        super().__init__(CTRL_LEFT_CLICK if not bind and path else bind, tooltip, use_link_style)
        self.path = Path(path).expanduser() if not isinstance(path, Path) else path
        self.path_in_tooltip = path_in_tooltip
        self.in_file_manager = in_file_manager

    def get_path_type(self) -> str:
        try:
            mode = S_IFMT(self.path.stat().st_mode)
        except OSError:
            return 'path'
        else:
            return self._mode_type_map.get(mode, 'path')  # noqa

    @property
    def tooltip(self) -> str:
        tooltip = self._tooltip
        if not (path := self.path):
            return tooltip

        path_type = self.get_path_type()
        link_text = path.as_posix() if self.path_in_tooltip else path_type
        prefix = f'{tooltip}; open' if tooltip else 'Open'
        suffix = ' with ctrl + click' if self.bind == CTRL_LEFT_CLICK else ''
        if not self.in_file_manager and path_type == 'file':
            return f'{prefix} file {link_text}{suffix}'
        else:
            return f'{prefix} {link_text} in file manager{suffix}'

    def open(self, event: Event):
        if path := self.path:
            if not self.in_file_manager and self.get_path_type() == 'file':
                launch(path)
            else:
                explore(path)


class CallbackLink(LinkTarget):
    __slots__ = ('callback',)

    def __init__(self, callback: BindTarget, bind: str = None, tooltip: str = None, use_link_style: Bool = True):
        super().__init__(bind or LEFT_CLICK, tooltip, use_link_style)
        self.callback = callback

    def open(self, event: Event):
        self.callback(event)
