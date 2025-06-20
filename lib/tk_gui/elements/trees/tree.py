"""
Tree GUI elements

:author: Doug Skrypa
"""

from __future__ import annotations

import logging
from pathlib import Path
from tkinter import TclError
from tkinter.ttk import Treeview
from typing import TYPE_CHECKING, Iterable, Sequence, TypeVar, Generic, Collection, Hashable

from tk_gui.enums import Anchor
from tk_gui.widgets.scroll import ScrollableTreeview
from .base import TreeViewBase, Column
from .nodes import TreeNode, RootPathNode, PathNode
from .utils import PathTreeIcons

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
    _root: N

    def __init__(
        self,
        root: N,
        columns: Iterable[Column],
        rows: int,
        *,
        row_height: int = None,
        selected_row_color: tuple[str, str] = None,  # fg, bg
        select_mode: TreeSelectModes = None,
        scroll_y: bool = True,
        scroll_x: bool = False,
        init_focus_key: Hashable | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._root = root
        self.columns = {col.key: col for col in columns}
        self.num_rows = rows
        self.row_height = row_height
        self.selected_row_color = selected_row_color
        self.select_mode = select_mode
        self.scroll_x = scroll_x
        self.scroll_y = scroll_y
        self._init_focus_key = init_focus_key
        self._iid_node_map = {}
        self._key_node_map = {}
        self._image_cache = {}

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

    # region Insert / Update

    def _insert_node(self, node: N):
        try:
            parent_iid = node.parent.iid
        except AttributeError:
            parent_iid = ''

        node.iid = self.tree_view.insert(
            parent_iid, 'end', text=node.text, values=node.values, image=self._get_image(node)  # noqa
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
            if hasattr(node, 'iid'):
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

    # endregion

    def _get_selected_iids(self) -> Collection[str]:
        try:
            return self.tree_view.selection()
        except TclError as e:
            log.debug(f'Error determining tree view selection: {e}')
            return []

    def _get_selected_nodes(self) -> list[N]:
        return [self._iid_node_map[iid] for iid in self._get_selected_iids()]

    def _clear_nodes(self):
        for node in self._root.children.values():
            self.tree_view.delete(node.iid)

        self._root.children.clear()
        self._iid_node_map.clear()
        self._key_node_map.clear()


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
    _tree_icons: PathTreeIcons

    def __init__(self, path: Path, rows: int, *, binds: BindMapping = None, **kwargs):
        handlers = {
            '<<TreeviewSelect>>': self._handle_node_selected,
            '<Double-1>': self._handle_root_change,
            '<Return>': self._handle_root_change,
        }
        if not binds:
            binds = handlers
        else:
            binds |= handlers
        columns = [Column('#0', 'Name', width=30), Column('Size', width=20, anchor_values=Anchor.MID_RIGHT)]
        super().__init__(RootPathNode(path), columns, rows=rows, binds=binds, **kwargs)

    @property
    def value(self) -> list[Path]:
        return [node.key for node in self._get_selected_nodes()]

    def _populate_tree(self):
        self._tree_icons = PathTreeIcons(self.style)
        self._root.add_dir_contents(self._tree_icons)
        self._insert_nodes(self._root.children.values())

    def _handle_node_selected(self, event: Event):
        """
        This event is triggered by many conditions:
            - Single-click
            - Move selection via up/down arrow keys
            - Expand/collapse via left/right arrow keys
        """
        if nodes := self._get_selected_nodes():
            for node in nodes:
                if node.expand():
                    self._update_node(node)

    def _handle_root_change(self, event: Event):
        """Triggered by double-click or the Enter/Return key."""
        nodes = self._get_selected_nodes()
        if len(nodes) != 1:
            log.debug(f'Unable to change root dir - found {len(nodes)} selected nodes')
            return

        self._clear_nodes()
        self._root = nodes[0].promote_to_root()
        self._insert_nodes(self._root.children.values())
