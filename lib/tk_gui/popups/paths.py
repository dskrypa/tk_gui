"""
Tkinter GUI popups: Path-related prompts

:author: Doug Skrypa
"""

from __future__ import annotations

import logging
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, Any

from tk_gui.enums import TreeSelectMode
from tk_gui.event_handling import ENTER_KEYSYMS, event_handler, button_handler
from tk_gui.images.icons import Icons
from ..elements import Button, Input, Text, PathTree, ButtonAction
from ..elements.trees.nodes import PathNode
from .base import Popup
from .common import popup_error

if TYPE_CHECKING:
    from ..typing import Layout, PathLike

__all__ = ['PathPopup']
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
        bind_esc: bool = True,
        **kwargs,
    ):
        if not allow_files and not allow_dirs:
            raise ValueError('At least one of allow_files or allow_dirs must be enabled/True')
        super().__init__(title=title, bind_esc=bind_esc, **kwargs)
        self.initial_dir = Path(initial_dir) if initial_dir else Path.home()
        self.allow_multiple = multiple
        self.allow_files = allow_files
        self.allow_dirs = allow_dirs
        self._tree_rows = rows
        self._submit_text = submit_text
        self._submitted = False

    @cached_property
    def _path_field(self) -> Text:
        return Text(self.initial_dir)

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
            **self._path_tree_kwargs()
        )

    def _path_tree_kwargs(self) -> dict[str, Any]:
        return {}

    @cached_property
    def _submit_button(self) -> Button:
        return Button(self._submit_text, key='submit', side='right', action=ButtonAction.BIND_EVENT)

    def get_pre_window_layout(self) -> Layout:
        icon = Icons(15).draw_with_transparent_bg('caret-left-fill')
        yield [Button('', icon, cb=self._handle_back), self._path_field]
        yield [self._path_tree]
        yield [self._submit_button]

    # @event_handler('<Key>')
    # def _handle_any(self, event):
    #     log.info(f'Event: {event}')

    @event_handler('<Alt-Left>', '<Mod1-Left>')
    def _handle_back(self, event=None):
        self._path_tree.root_dir = self._path_tree.root_dir.parent

    def _handle_root_changed(self, path: Path):
        self._path_field.update(path.as_posix(), auto_resize=True)

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

    def get_results(self) -> list[Path]:
        return super().get_results().get('path_tree', [])


class SaveAsPopup(PathPopup):
    def __init__(
        self,
        initial_dir: PathLike = None,
        initial_name: str = '',
        *,
        submit_text: str = 'Save',
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
        self.initial_name = initial_name
        self.__last_selection = []

    @cached_property
    def _name_input(self) -> Input:
        binds = {key: self._handle_submit for key in ENTER_KEYSYMS}
        return Input(
            self.initial_name, key='filename', size=(40, 1), change_cb=self._handle_name_input_changed, binds=binds
        )

    def _path_tree_kwargs(self) -> dict[str, Any]:
        return {
            'selection_changed_cb': self._handle_selection_changed,
            'include_children': False,
        }

    def get_pre_window_layout(self) -> Layout:
        icon = Icons(15).draw_with_transparent_bg('caret-left-fill')
        yield [Button('', icon, cb=self._handle_back), self._path_field]
        yield [self._path_tree]
        yield [Text('Name:'), self._name_input, self._submit_button]

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
        paths = self._path_tree.get_values(self._submitted, root_fallback=True)
        try:
            path = paths[0]
        except IndexError:
            return None

        if path.is_dir():
            return path.joinpath(self._name_input.value)
        else:
            return path.parent.joinpath(self._name_input.value)
