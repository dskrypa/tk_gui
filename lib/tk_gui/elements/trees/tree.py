"""
Tree GUI elements

:author: Doug Skrypa
"""

from __future__ import annotations

import logging
from pathlib import Path
from tkinter.ttk import Treeview
from typing import TYPE_CHECKING, Any, Iterable, Self, Sequence

from tk_gui.images.wrapper import ImageWrapper, SourceImage
from tk_gui.widgets.scroll import ScrollableTreeview
from .base import TreeViewBase, Column

if TYPE_CHECKING:
    from PIL.ImageTk import PhotoImage
    from tk_gui.typing import TkContainer, TreeSelectModes, ImageType

    Image = ImageType | ImageWrapper  # noqa

__all__ = ['TreeNode', 'Tree']
log = logging.getLogger(__name__)


class TreeNode:
    __slots__ = ('parent', 'key', 'text', 'values', 'icon', 'children')
    icon: SourceImage

    def __init__(self, parent: Self | None, key: str, text: str = '', values: Sequence[Any] = (), icon: Image = None):
        self.parent = parent
        self.key = key
        self.text = text
        self.values = values
        self.icon = SourceImage.from_image(icon) if icon else None
        self.children = []

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}(key={self.key!r}, text={self.text!r}, values={self.values})>'

    def get_parent(self) -> Self | None:
        return self.parent

    def add_child(self, key: str, text: str, values: Sequence[Any] = (), icon: Image = None) -> TreeNode:
        node = TreeNode(self, key, text, values, icon)
        self.children.append(node)
        return node


class PathNode(TreeNode):
    """
    Icon candidates for related things?
    file-earmark-fill, file-earmark-text-fill, file-earmark-music-fill, file-earmark-zip-fill
    file-earmark, file-earmark-text, file-earmark-music, file-earmark-zip
    folder, folder-fill, folder-symlink-fill, folder-symlink, folder2-open
    funnel-fill, funnel
    music-note-beamed, music-note
    arrow-90deg-left, arrow-left, arrow-left-circle, arrow-left-short
    """

    __slots__ = ('path',)

    def __init__(self, parent: PathNode | None, path: Path, icon: ImageType = None):
        super().__init__(parent, path.as_posix(), path.name, icon)
        self.path = path

    def get_parent(self) -> Self | None:
        if self.parent:
            return self.parent

        parent = self.path.parent
        if parent.parent == parent:
            return None
        else:
            return PathNode(None, self.path.parent)


class Tree(TreeViewBase, base_style_layer='tree'):
    def __init__(
        self,
        root: TreeNode,
        columns: Iterable[Column],
        *,
        rows: int = None,
        row_height: int = None,
        selected_row_color: tuple[str, str] = None,  # fg, bg
        select_mode: TreeSelectModes = None,
        scroll_y: bool = True,
        scroll_x: bool = False,
        init_focus_row: int | tuple[str, str | int] | None = 0,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.root = root
        self.columns = {col.key: col for col in columns}
        self.num_rows = rows
        self.row_height = row_height
        self.selected_row_color = selected_row_color
        self.select_mode = select_mode
        self.scroll_x = scroll_x
        self.scroll_y = scroll_y
        self._init_focus_row = init_focus_row
        self._iid_node_map = {}
        self._key_iid_map = {}
        self._image_cache = {}

    def set_focus_on_value(self, key: str, value: str | int):
        # for i, row in enumerate(self.data):
        #     if row[key] == value:
        #         self.set_focus_on_row(i)
        #         return
        raise ValueError(f'Unable to find row with {key=} {value=}')

    def _init_widget(self, tk_container: TkContainer):
        columns, style = self.columns, self.style
        kwargs = {
            'columns': [col.key for col in columns.values()],
            'displaycolumns': [col.key for col in columns.values() if col.show],
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
        for col in columns.values():
            tree_view.heading(col.key, text=col.title, anchor=col.anchor_header.value)  # noqa
            tree_view.column(
                col.key, width=col.width_for(char_width), minwidth=10, stretch=False, anchor=col.anchor_values.value
            )

        self._insert_nodes(self.root.children)

        tree_view.configure(style=self._ttk_style()[0])

    def _insert_nodes(self, nodes: Iterable[TreeNode]):
        # A path/file-specific tree type is likely necessary, with on-select callbacks
        # to populate/cache children of directories
        for node in nodes:
            parent_iid = self._key_iid_map.get(node.parent.key, '')
            iid = self.tree_view.insert(
                parent_iid, 'end', text=node.text, values=node.values, image=self._get_image(node)  # noqa
            )
            self._iid_node_map[iid] = node
            self._key_iid_map[node.key] = iid
            if node.children:
                self._insert_nodes(node.children)

    def _get_image(self, node: TreeNode) -> PhotoImage | None:
        if not node.icon:
            return None
        try:
            return self._image_cache[node.icon.sha256sum]
        except KeyError:
            pass
        self._image_cache[node.icon.sha256sum] = image = node.icon.as_tk_image()
        return image
