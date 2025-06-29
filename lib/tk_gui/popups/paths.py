"""
Tkinter GUI popups: Path-related prompts

:author: Doug Skrypa
"""

from __future__ import annotations

import logging
from functools import cached_property, partial
from pathlib import Path
from typing import TYPE_CHECKING, Any

from tk_gui.enums import TreeSelectMode
from tk_gui.event_handling import ENTER_KEYSYMS, event_handler, button_handler
from tk_gui.images.icons import Icons
from tk_gui.styles.colors import WHITE, BLACK
from ..elements import Button, EventButton as EButton, Input, Text, PathTree, VerticalSeparator
from ..elements.trees.nodes import PathNode
from .base import Popup
from .common import popup_error

if TYPE_CHECKING:
    from ..typing import Layout, PathLike

__all__ = ['PathPopup', 'PickDirectory', 'PickDirectories', 'PickFile', 'PickFiles', 'SaveAs']
log = logging.getLogger(__name__)


class PathPopup(Popup):
    def __init__(
        self,
        initial_dir: PathLike = None,
        *,
        multiple: bool = False,
        allow_files: bool = True,
        allow_dirs: bool = True,
        title: str = None,
        rows: int = 25,
        submit_text: str = 'Submit',
        cancel_text: str = '\U0001f6ab Cancel',  # No entry sign
        bind_esc: bool = True,
        **kwargs,
    ):
        if not allow_files and not allow_dirs:
            raise ValueError('At least one of allow_files or allow_dirs must be enabled/True')
        super().__init__(title=title, bind_esc=bind_esc, **kwargs)
        # TODO: Add support for file_types filter (default: All Files / All Types)
        # TODO: Add Places left panel (Home, desktop, documents, etc), with custom places/bookmarks param
        self.initial_dir = Path(initial_dir) if initial_dir else Path.home()
        self.allow_multiple = multiple
        self.allow_files = allow_files
        self.allow_dirs = allow_dirs
        self._tree_rows = rows
        # Note: Unicode codepoints are used for the default text values because mixing an icon with text produces bad
        # alignment in buttons...
        self._submit_text = submit_text
        self._cancel_text = cancel_text
        self._submitted = False
        self._history: list[Path] = [self.initial_dir]
        self._history_index: int = 0
        self._preserve_history: bool = False

    @cached_property
    def _icons(self) -> Icons:
        return Icons(15)

    # region Elements

    @cached_property
    def _path_field(self) -> Text:
        return Text(self.initial_dir, anchor='sw')

    @cached_property
    def _path_tree(self) -> PathTree:
        return PathTree(
            self.initial_dir,
            self._tree_rows,
            key='path_tree',
            root_changed_cb=self._handle_root_changed,
            files=self.allow_files,
            dirs=self.allow_dirs,
            select_mode=TreeSelectMode.EXTENDED if self.allow_multiple else TreeSelectMode.BROWSE,
            focus=True,
            fill=True,
            expand=True,
            **self._path_tree_kwargs()
        )

    def _path_tree_kwargs(self) -> dict[str, Any]:
        return {}

    @cached_property
    def _submit_button(self) -> Button:
        return EButton(self._submit_text, key='submit', side='right')

    # endregion

    def get_pre_window_layout(self) -> Layout:
        yield from self._get_pre_window_layout()
        # TODO: Include location / full path text field in all path popups to accept a path to navigate to?
        # TODO: File types filter: funnel-fill; funnel
        # These buttons end up in the opposite order since both have side=right
        yield [self._submit_button, EButton(self._cancel_text, key='cancel', side='right')]

    def _build_places_frame(self):
        # Home: house-door-fill; house-door; house-fill; house
        # Desktop: window-desktop; archive-fill; archive; calendar3-fill (flip 180); laptop-fill; laptop;
        # Documents: file-earmark; files;
        # Downloads: download; chevron-bar-down
        # Music: music-note-beamed; music-note
        # Pictures: card-image; image; image-fill; images;
        # Videos: film
        # (disk): hdd-network; hdd-network-fill; hdd; hdd-fill; hdd-stack-fill; hdd-stack; hdd-rack-fill; hdd-rack
        # Bookmarks: bookmark; bookmark-fill; bookmark-star-fill; bookmark-star
        pass

    def _get_pre_window_layout(self) -> Layout:
        # TODO: Places left panel will result in most of the other elements here needing to be in a frame
        fg = WHITE if self.style.is_dark_mode else BLACK
        draw_icon = partial(self._icons.draw_with_transparent_bg, size=(20, 20), color=fg)
        yield [
            EButton('', draw_icon('chevron-left'), key='back'),
            EButton('', draw_icon('chevron-right'), key='forward'),
            EButton('', draw_icon('chevron-up'), key='up'),
            EButton('', draw_icon('arrow-repeat'), key='refresh'),
            VerticalSeparator(),
            self._path_field,
        ]
        yield [self._path_tree]

    # region Event Handling

    # @event_handler('<Key>')
    # def _handle_any(self, event):
    #     log.info(f'Event: {event}')

    @event_handler('<Alt-Left>', '<Mod1-Left>')
    @button_handler('back')
    def _handle_back(self, event=None, key=None):
        index = self._history_index - 1
        if index >= 0:
            # log.debug(f'History now has {len(self._history)} entries; going back to {index=}')
            self._history_index = index
            self._preserve_history = True
            self._path_tree.root_dir = self._history[index]

    @event_handler('<Alt-Right>', '<Mod1-Right>')
    @button_handler('forward')
    def _handle_forward(self, event=None, key=None):
        index = self._history_index + 1
        try:
            path = self._history[index]
        except IndexError:
            pass
        else:
            # log.debug(f'History now has {len(self._history)} entries; going forward to {index=}')
            self._history_index = index
            self._preserve_history = True
            self._path_tree.root_dir = path

    @event_handler('<Alt-Up>', '<Mod1-Up>')
    @button_handler('up')
    def _handle_up(self, event=None, key=None):
        self._path_tree.root_dir = self._path_tree.root_dir.parent

    @event_handler('<F5>')
    @button_handler('refresh')
    def _handle_refresh(self, event=None, key=None):
        self._preserve_history = True
        self._path_tree.root_dir = self._path_tree.root_dir

    def _handle_root_changed(self, path: Path):
        self._path_field.update(path.as_posix(), auto_resize=True)
        # History navigation (back/forward) events should not modify history, but other root changes should
        preserve_history = self._preserve_history
        self._preserve_history = False
        if preserve_history:
            return

        # TODO: Disable forward/back buttons when there's nothing in history to go forward/back to
        index = self._history_index + 1
        # log.debug(f'Truncating history from {len(self._history)} to {index} entries')
        history = self._history[:index]
        history.append(path)
        self._history = history
        self._history_index = len(history) - 1
        # log.debug(f'History now has {len(history)} entries with index={self._history_index}')

    @button_handler('submit')
    def _handle_submit(self, event, key=None):
        if self.allow_dirs and self.allow_files:
            self._submitted = True
            # Need to call this instead of returning CallbackAction.INTERRUPT to support both binds and buttons
            self.window.interrupt(event, self._path_tree)
            return

        paths = self._path_tree.value
        if not paths:
            self._submitted = True
            self.window.interrupt(event, self._path_tree)
            return
        elif self.allow_files and (n_dirs := sum(p.is_dir() for p in paths)):
            if self.allow_multiple:
                d_str = 'a directory' if n_dirs == 1 else f'{n_dirs} directories'
                popup_error(f'Only files are expected, but you selected {d_str}')
            else:
                popup_error('A file is expected, but you selected a directory')
        elif self.allow_dirs and (n_files := sum(not p.is_dir() for p in paths)):
            if self.allow_multiple:
                f_str = 'a file' if n_files == 1 else f'{n_files} files'  # noqa
                popup_error(f'Only directories are expected, but you selected {f_str}')
            else:
                popup_error('A directory is expected, but you selected a file')
        else:
            self._submitted = True
            self.window.interrupt(event, self._path_tree)

    @button_handler('cancel')
    def _handle_cancel(self, event, key=None):
        self.window.interrupt(event, self._path_tree)

    # endregion

    def get_results(self) -> list[Path]:
        return self._path_tree.get_values(self._submitted, root_fallback=True)


class PickDirectory(PathPopup):
    def __init__(
        self, initial_dir: PathLike = None, *, submit_text: str = 'Open', title: str = 'Open Directory', **kwargs,
    ):
        super().__init__(
            initial_dir,
            multiple=False,
            allow_files=False,
            allow_dirs=True,
            submit_text=submit_text,
            title=title,
            **kwargs,
        )

    def get_results(self) -> Path | None:
        paths = self._path_tree.get_values(self._submitted, root_fallback=True)
        try:
            return paths[0]
        except IndexError:
            return None


class PickDirectories(PathPopup):
    def __init__(
        self, initial_dir: PathLike = None, *, submit_text: str = 'Open', title: str = 'Open Directories', **kwargs,
    ):
        super().__init__(
            initial_dir,
            multiple=True,
            allow_files=False,
            allow_dirs=True,
            submit_text=submit_text,
            title=title,
            **kwargs,
        )


class PickFile(PathPopup):
    def __init__(
        self, initial_dir: PathLike = None, *, submit_text: str = 'Open', title: str = 'Open File', **kwargs,
    ):
        super().__init__(
            initial_dir,
            multiple=False,
            allow_files=True,
            allow_dirs=False,
            submit_text=submit_text,
            title=title,
            **kwargs,
        )

    def get_results(self) -> Path | None:
        paths = self._path_tree.get_values(self._submitted, root_fallback=False)
        try:
            return paths[0]
        except IndexError:
            return None


class PickFiles(PathPopup):
    def __init__(
        self, initial_dir: PathLike = None, *, submit_text: str = 'Open', title: str = 'Open Files', **kwargs,
    ):
        super().__init__(
            initial_dir,
            multiple=True,
            allow_files=True,
            allow_dirs=False,
            submit_text=submit_text,
            title=title,
            **kwargs,
        )


class SaveAs(PathPopup):
    default_ext: str | None = None

    def __init__(
        self,
        initial_dir: PathLike = None,
        initial_name: str | None = None,
        default_ext: str | None = None,
        *,
        submit_text: str = '\U0001f4be Save',  # Floppy disk icon
        title: str = 'Save As',
        **kwargs,
    ):
        super().__init__(
            initial_dir,
            multiple=False,
            allow_files=True,
            allow_dirs=True,
            submit_text=submit_text,
            title=title,
            **kwargs,
        )
        self.initial_name = initial_name or ''
        if default_ext:
            self.default_ext = default_ext if default_ext.startswith('.') else f'.{default_ext}'
        self.__last_selection = []

    @cached_property
    def _name_input(self) -> Input:
        binds = {key: self._handle_submit for key in ENTER_KEYSYMS}
        return Input(
            self.initial_name, key='filename', size=(60, 1), change_cb=self._handle_name_input_changed, binds=binds
        )

    @cached_property
    def _submit_button(self) -> Button:
        # return EButton(self._submit_text, self._icons.draw_alpha_cropped('floppy'), key='submit', side='right')
        return EButton(self._submit_text, key='submit', side='right')

    def _path_tree_kwargs(self) -> dict[str, Any]:
        return {'selection_changed_cb': self._handle_selection_changed, 'include_children': False}

    def _get_pre_window_layout(self) -> Layout:
        yield from super()._get_pre_window_layout()
        yield [Text('Name:'), self._name_input]

    def _handle_name_input_changed(self, *args):
        # log.debug(f'_handle_name_input_changed: {args}')
        if nodes := self.__last_selection:
            name = self._name_input.value
            if not any(name == node.text for node in nodes):
                self._path_tree.set_selection(None)

    def _handle_selection_changed(self, nodes: list[PathNode]):
        self.__last_selection = nodes
        if not len(nodes) == 1:
            return
        node = nodes[0]
        if node.is_dir:
            return
        self._name_input.update(node.text)

    def get_results(self) -> Path | None:
        if not (name := self._name_input.value):
            return None
        try:
            path = self._path_tree.get_values(self._submitted, root_fallback=True)[0]
        except IndexError:
            return None

        if path.is_dir():
            path /= name
        else:
            path = path.parent.joinpath(name)

        if self.default_ext and not path.suffix:
            return path.with_suffix(self.default_ext)
        return path
