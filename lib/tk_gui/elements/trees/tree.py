"""
Tree GUI elements

:author: Doug Skrypa
"""

from __future__ import annotations

import logging
from pathlib import Path
from tkinter import TclError, EventType
from tkinter.ttk import Treeview
from typing import TYPE_CHECKING, Callable, Iterable, Sequence, TypeVar, Generic, Collection, Hashable

from tk_gui.enums import Anchor, TreeSelectMode
from tk_gui.widgets.scroll import ScrollableTreeview
from tk_gui.event_handling.utils import ENTER_KEYSYMS
from .base import TreeViewBase, Column
from .nodes import TreeNode, RootPathNode, PathNode
from .utils import PathTreeConfig

if TYPE_CHECKING:
    from tkinter import Event
    from PIL.ImageTk import PhotoImage
    from tk_gui.event_handling.containers import BindMapping
    from tk_gui.typing import TkContainer, TreeSelectModes

__all__ = ['Tree', 'PathTree']
log = logging.getLogger(__name__)

N = TypeVar('N', bound=TreeNode)


class BaseTree(TreeViewBase, Generic[N], base_style_layer='tree'):
    _iid_node_map: dict[str, N]
    _key_node_map: dict[Hashable, N]
    _iid_open_map: dict[str, bool]
    _root: N
    _enter_submits: bool = False

    def __init__(
        self,
        root: N,
        columns: Iterable[Column],
        rows: int,
        *,
        row_height: int = None,
        selected_row_color: tuple[str, str] = None,  # fg, bg
        select_mode: TreeSelectModes = TreeSelectMode.EXTENDED.value,
        binds: BindMapping = None,
        enter_submits: bool = False,
        scroll_y: bool = True,
        scroll_x: bool = False,
        init_focus_key: Hashable | None = None,
        allow_shift_select_all: bool = False,
        **kwargs,
    ):
        binds = self._prepare_binds(binds, enter_submits)
        super().__init__(binds=binds, **kwargs)
        self._root = root
        self.columns = {col.key: col for col in columns}
        self.num_rows = rows
        self.row_height = row_height
        self.selected_row_color = selected_row_color
        self.select_mode = select_mode.value if isinstance(select_mode, TreeSelectMode) else select_mode
        self.scroll_x = scroll_x
        self.scroll_y = scroll_y
        self._init_focus_key = init_focus_key
        self._iid_node_map = {}
        self._key_node_map = {}
        self._iid_open_map = {}
        self._image_cache = {}
        self.__shift_is_active = [False, False]
        self.__previous_selection = None
        self._allow_shift_select_all = allow_shift_select_all
        self._submitted = False

    # region Focus

    def take_focus(self, force: bool = False):
        if force:
            self.tree_view.focus_force()
        else:
            self.tree_view.focus_set()

        if self._init_focus_key is not None:
            self.set_focus_on_key(self._init_focus_key)

    def set_focus_on_key(self, key: Hashable):
        if node := self._key_node_map.get(key):
            self.tree_view.selection_set(node.iid)
            self.tree_view.focus(node.iid)

    # endregion

    # region Initialize Widget

    def _init_widget(self, tk_container: TkContainer):
        style = self.style
        columns = [col for key, col in self.columns.items() if key != '#0']  # Skip #0 here to avoid an extra column
        kwargs = {
            'columns': [col.key for col in columns],
            'displaycolumns': [col.key for col in columns if col.show],
            'height': self.num_rows if self.num_rows else self.size[1] if self.size else len(self.data),
            'show': 'tree headings',
            'selectmode': self.select_mode,
            'takefocus': int(self.allow_focus),
            **self.style_config,
        }
        if self.scroll_y or self.scroll_x:
            self.widget = outer = ScrollableTreeview(tk_container, self.scroll_y, self.scroll_x, style, **kwargs)
            self.tree_view = tree_view = outer.inner_widget
        else:
            self.widget = self.tree_view = tree_view = Treeview(tk_container, **kwargs)

        char_width = style.char_width('tree')
        for col in self.columns.values():  # Include #0 here to change its settings
            tree_view.heading(col.key, text=col.title, anchor=col.anchor_header.value)  # noqa
            tree_view.column(
                col.key, width=col.width_for(char_width), minwidth=10, stretch=False, anchor=col.anchor_values.value
            )

        self._populate_tree()

        tree_view.configure(style=self._ttk_style()[0])

    def _populate_tree(self):
        self._insert_nodes(self._root.children.values())

    # endregion

    # region Insert / Update

    def _insert_node(self, node: N):
        node.iid = self.tree_view.insert(
            node.parent_iid, 'end', text=node.text, values=node.values, image=self._get_image(node), open=False  # noqa
        )
        self._iid_node_map[node.iid] = node
        self._key_node_map[node.key] = node
        if node.children:
            self._insert_nodes(node.children.values())

    def _update_node(self, node: N):
        self.tree_view.item(node.iid, text=node.text, values=node.values, image=self._get_image(node))  # noqa
        if node.children:
            self._insert_or_update_nodes(node.children.values())

    def _insert_nodes(self, nodes: Iterable[N]):
        # A path/file-specific tree type is likely necessary, with on-select callbacks
        # to populate/cache children of directories
        for node in nodes:
            self._insert_node(node)

    def _update_nodes(self, nodes: Iterable[N]):
        for node in nodes:
            self._update_node(node)

    def _insert_or_update_nodes(self, nodes: Iterable[N]):
        for node in nodes:
            if node.iid:
                self._update_node(node)
            else:
                self._insert_node(node)

    def _get_image(self, node: N) -> PhotoImage | None:
        if not node.icon:
            return None
        try:
            return self._image_cache[node.icon.sha256sum]
        except KeyError:
            pass
        self._image_cache[node.icon.sha256sum] = image = node.icon.as_tk_image()
        return image

    def _clear_nodes(self):
        for node in self._root.children.values():
            self.tree_view.delete(node.iid)

        self._root.children.clear()
        self._iid_node_map.clear()
        self._key_node_map.clear()
        self._iid_open_map.clear()

    # endregion

    # region Selection

    def _get_selected_iids(self) -> Collection[str]:
        try:
            if self._allow_shift_select_all:
                return self.tree_view.selection()
            return self.__get_selected_iids()
        except TclError as e:
            log.debug(f'Error determining tree view selection: {e}')
            return []

    def __get_selected_iids(self) -> Collection[str]:
        """
        After clicking a single item, then holding down shift, and clicking the same item again, ttk seems to interpret
        that as the user wanting to select (nearly) everything below that item.  This method seeks to work around that
        behavior.
        """
        previous: list[str] = self.__previous_selection
        self.__previous_selection = iids = self.tree_view.selection()
        if not any(self.__shift_is_active) or len(iids) <= 2:
            # Shift was not active, or the number of selected items doesn't warrant further attention
            return iids
        elif not (mouse_iid := self.tree_view.identify_row(self.relative_mouse_position[1])):
            # No item could be identified at the current mouse position
            return iids
        elif mouse_iid == iids[-1]:  # The last selected item matches the one under the mouse cursor
            return iids
        elif previous and (previous[-1] == iids[-1] or previous[0] == iids[-1]):
            # iids[-1] is the bottom selected item.
            # When the previous bottom selected item matches, it indicates that the latest selected item is above the
            # previous/initial selection.
            # When the previous top selected item matches, it indicates that the previous selection was top->down, and
            # that with shift still held, a different selection was made with an entry above the initial selection.
            # In either case, it is not the problematic behavior that this method is attempting to work around.
            return iids

        try:
            index = iids.index(mouse_iid)
        except ValueError:
            return iids
        else:
            log.debug('Detected bad shift selection - resetting selection')
            self.__previous_selection = iids = iids[:index + 1]
            self.tree_view.selection_set(*iids)
            return iids

    def _get_selected_nodes(self) -> list[N]:
        """
        When multiple items are selected while holding down shift, the children of closed items end up being included
        in the raw selection.  This method translates the selected iids into node objects, and filters out the children
        of nodes that were closed.
        """
        keep = {}
        for iid in self._get_selected_iids():
            node = self._iid_node_map[iid]
            if not node.has_any_ancestor(keep) or self._iid_open_map.get(node.parent_iid, False):  # noqa
                # It is a top-level node, or its parent and all ancestors are open
                keep[iid] = node

        return list(keep.values())

    def _selection_is_submissible(self) -> bool:
        return True

    # endregion

    # region Event Handling

    def _prepare_binds(self, binds: BindMapping | None, enter_submits: bool = False):
        handlers = {
            '<<TreeviewOpen>>': self._handle_node_opened,
            '<<TreeviewClose>>': self._handle_node_closed,
            '<KeyPress-Shift_L>': self._handle_shift,
            '<KeyRelease-Shift_L>': self._handle_shift,
            '<KeyPress-Shift_R>': self._handle_shift,
            '<KeyRelease-Shift_R>': self._handle_shift,
        }
        if enter_submits:
            self._enter_submits = enter_submits
            for key in ENTER_KEYSYMS:
                handlers[key] = self._handle_return

        if not binds:
            return handlers
        else:
            return binds | handlers  # noqa

    def _handle_node_opened(self, event: Event):
        iid = self.tree_view.focus()
        # node = self._iid_node_map.get(iid)
        # log.debug(f'_handle_node_opened: {event}, {iid=}, {node=}', extra={'color': 10})
        if not self._submitted:  # Prevent enter used to submit from toggling open status
            self._iid_open_map[iid] = True

    def _handle_node_closed(self, event: Event):
        iid = self.tree_view.focus()
        # node = self._iid_node_map.get(iid)
        # log.debug(f'_handle_node_closed: {event}, {iid=}, {node=}', extra={'color': 11})
        if not self._submitted:  # Prevent enter used to submit from toggling open status
            self._iid_open_map[iid] = False

    def _handle_shift(self, event: Event):
        # This event won't be triggered until the first time the tree view event receives focus
        # log.debug(f'_handle_shift: {event}, {event.__dict__}')
        # Shift_L = 65505, Shift_R = 65506; type = EventType.KeyPress (2) or EventType.KeyRelease (3)
        self.__shift_is_active[event.keysym_num - 65505] = event.type == EventType.KeyPress

    def _handle_return(self, event: Event):
        # log.debug(f'_handle_return: {event}', extra={'color': 9})
        if self._enter_submits:
            if self._selection_is_submissible():
                self._submitted = True
                self.window.interrupt(event, self)
            else:
                log.debug('Skipping submit - selection is not submissible')

    # endregion


class Tree(BaseTree[N]):
    @classmethod
    def from_nodes(cls, nodes: Sequence[N], columns: Iterable[Column], **kwargs):
        root = TreeNode(None, '__root__')
        root.update_children(nodes)
        return cls(root, columns, **kwargs)

    @property
    def value(self) -> list[Path]:
        return [node.key for node in self._get_selected_nodes()]

    def update_nodes(self, nodes: Sequence[N]):
        self._clear_nodes()
        self._insert_nodes(nodes)
        self._root.update_children(nodes)


class PathTree(BaseTree[PathNode]):
    _root: RootPathNode | PathNode
    _pt_config: PathTreeConfig

    def __init__(
        self,
        path: Path,
        rows: int,
        *,
        files: bool = True,
        dirs: bool = True,
        root_changed_cb: Callable[[Path], ...] = None,
        **kwargs,
    ):
        columns = [Column('#0', 'Name', width=30), Column('Size', width=20, anchor_values=Anchor.MID_RIGHT)]
        super().__init__(RootPathNode(path), columns, rows=rows, enter_submits=True, **kwargs)
        self._root_changed_cb = root_changed_cb
        self._files = files
        self._dirs = dirs

    @property
    def value(self) -> list[Path]:
        return [node.key for node in self._get_selected_nodes()]

    def get_values(self, submitted: bool, root_fallback: bool = False) -> list[Path]:
        if not submitted and not self._submitted:
            # This element did not trigger form submission, and the parent window didn't either, so treat it as a
            # cancel / exit via escape/close.
            return []
        elif nodes := self._get_selected_nodes():
            return [node.key for node in nodes]
        elif root_fallback:
            return [self.root_dir]
        else:
            return []

    # region Initialize Widget

    def _populate_tree(self):
        self._pt_config = PathTreeConfig(self.style, self._files, self._dirs)
        self._root.add_dir_contents(self._pt_config)
        self._insert_nodes(self._root.children.values())

    # endregion

    # region Get/Set Root Dir

    @property
    def root_dir(self) -> Path:
        return self._root.key

    @root_dir.setter
    def root_dir(self, path: Path):
        self.change_root_dir(path)

    def change_root_dir(self, path: Path):
        if self.widget is None:  # Element not been displayed yet
            self._root.key = path
            return

        self._clear_nodes()
        self._change_root_node(RootPathNode.with_dir_contents(path, self._pt_config))

    def _change_root_node(self, node: PathNode | RootPathNode):
        # Note: self._clear_nodes must be called before promoting a node to root, so it must be called before
        # calling this method
        self._root = node
        self._insert_nodes(self._root.children.values())
        if self._root_changed_cb is not None:
            self._root_changed_cb(self._root.key)

    def _promote_to_root(self, node: PathNode):
        self._clear_nodes()
        self._change_root_node(node.promote_to_root())

    # endregion

    # region Event Handling

    def _prepare_binds(self, binds: BindMapping | None, enter_submits: bool = False):
        binds = super()._prepare_binds(binds, enter_submits)
        handlers = {
            '<<TreeviewSelect>>': self._handle_node_selected,
            '<Double-1>': self._handle_double_click,
            '<space>': self._handle_chdir,
        }
        return binds | handlers

    def _get_selected_node(self, action: str) -> PathNode | None:
        nodes = self._get_selected_nodes()
        if len(nodes) == 1:
            return nodes[0]
        else:
            log.debug(f'Ignoring {action} - found {len(nodes)} selected nodes')
            return None

    def _selection_is_submissible(self) -> bool:
        # Note: single/multiple is handled via select_mode
        if self._pt_config.files and self._pt_config.dirs:
            return True
        elif self._pt_config.files:
            return all(not node.is_dir for node in self._get_selected_nodes())
        else:
            return all(node.is_dir for node in self._get_selected_nodes())

    def _handle_node_selected(self, event: Event):
        """
        This event is triggered by many conditions:
            - Single-click
            - Move selection via up/down arrow keys
            - Expand/collapse via left/right arrow keys
        """
        # log.debug(f'_handle_node_selected: {event}', extra={'color': 14})
        if nodes := self._get_selected_nodes():
            for node in nodes:
                if node.expand():
                    self._update_node(node)

    def _handle_double_click(self, event: Event):
        if node := self._get_selected_node('double-click'):
            if node.is_dir:
                self._promote_to_root(node)
            elif self._pt_config.files:
                self.trigger_interrupt(event)

    def _handle_chdir(self, event: Event):
        """Triggered by space"""
        if node := self._get_selected_node(f'chdir via {event}'):
            if node.is_dir:
                self._promote_to_root(node)

    # endregion