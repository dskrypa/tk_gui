"""
Node classes for Tree GUI elements

:author: Doug Skrypa
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from stat import S_ISDIR
from typing import TYPE_CHECKING, Any, Iterable, Self, Sequence, Hashable, TypeVar, Generic, Collection

from tk_gui.images.wrapper import ImageWrapper, SourceImage
from tk_gui.utils import readable_bytes

if TYPE_CHECKING:
    from PIL.Image import Image as PILImage
    from tk_gui.typing import ImageType
    from .utils import PathTreeIcons, PathTreeConfig

    Image = ImageType | ImageWrapper  # noqa

__all__ = ['TreeNode', 'PathNode']
log = logging.getLogger(__name__)

K = TypeVar('K', bound=Hashable)


class TreeNode(Generic[K]):
    __slots__ = ('parent', 'key', 'text', 'values', 'icon', 'children', 'iid')
    key: K
    children: dict[K, TreeNode[K]]
    icon: SourceImage
    iid: str

    def __init__(self, parent: Self | None, key: K, text: str = '', values: Sequence[Any] = (), icon: Image = None):
        self.parent = parent
        self.key = key
        self.text = text
        self.values = values
        self.icon = SourceImage.from_image(icon) if icon else None
        self.children = {}
        self.iid = ''

    def __repr__(self) -> str:
        return (
            f'<{self.__class__.__name__}(iid={self.iid!r}, key={self.key!r}, text={self.text!r}, values={self.values})>'
        )

    def add_child(self, key: K, text: str, values: Sequence[Any] = (), icon: Image = None) -> TreeNode:
        node = TreeNode(self, key, text, values, icon)
        self.children[key] = node
        return node

    def update_children(self, nodes: Iterable[TreeNode]):
        for node in nodes:
            self.children[node.key] = node

    @property
    def parent_iid(self) -> str:
        try:
            return self.parent.iid
        except AttributeError:
            return ''

    def has_any_ancestor(self, iids: Collection[str]) -> bool:
        if parent_iid := self.parent_iid:
            if parent_iid in iids:
                return True
            return self.parent.has_any_ancestor(iids)
        else:
            return False

    def has_ancestor(self, iid: str) -> bool:
        return self.has_any_ancestor({iid})


class RootPathNode(TreeNode[Path]):
    __slots__ = ()
    children: dict[Path, PathNode]

    def __init__(self, path: Path):
        if not path.exists():
            path = Path.cwd()
        elif not path.is_dir():
            path = path.parent
        super().__init__(None, path)

    @classmethod
    def with_dir_contents(cls, path: Path, pt_config: PathTreeConfig) -> RootPathNode:
        self = cls(path)
        self.add_dir_contents(pt_config)
        return self

    def add_dir_contents(self, pt_config: PathTreeConfig):
        self.children = PathNode._for_dir(self, self.key, pt_config)[0]


class PathNode(TreeNode[Path]):
    __slots__ = ('is_dir', '_pt_config', '_expanded')
    children: dict[Path, PathNode]
    values: list[str]
    is_dir: bool
    key: Path
    _expanded: bool

    def __init__(
        self, parent: RootPathNode | PathNode | None, path: Path, pt_config: PathTreeConfig, depth: int = 1
    ):
        is_dir, size, modified, icon = _path_info(path, pt_config.tree_icons)
        super().__init__(parent, path, path.name, [size, modified], icon=icon)
        self.is_dir = is_dir
        self._pt_config = pt_config
        self._expanded = False
        if is_dir and depth:
            self._refresh_children(depth - 1)

    @classmethod
    def _for_dir(
        cls, parent: RootPathNode | PathNode, directory: Path, pt_config: PathTreeConfig, depth: int = 1
    ) -> tuple[dict[Path, PathNode], int]:
        dirs, files = {}, {}
        # Paths were sorted by name by _dir_contents, so these dicts will be populated in already sorted order
        for path in _dir_contents(directory):
            node = cls(parent, path, pt_config, depth)
            if node.is_dir:
                dirs[path] = node
            else:
                files[path] = node

        entry_count = len(dirs) + len(files)
        if pt_config.files:
            # Both directories and files should be displayed, regardless of whether dirs are acceptable selections
            return dirs | files, entry_count  # Sort dirs above files
        else:
            return dirs, entry_count

    def add_child(self, *args, **kwargs):
        raise NotImplementedError

    def _refresh_children(self, depth: int = 1):
        self.children, entry_count = self._for_dir(self, self.key, self._pt_config, depth)
        self.values[0] = '1 item' if entry_count == 1 else f'{entry_count:,d} items'

    def expand(self) -> bool:
        if self._expanded or not self.is_dir:
            return False

        log.debug(f'Expanding {self}')
        self._expanded = True
        for child in self.children.values():
            if child.is_dir:
                child._refresh_children(0)

        return True

    def promote_to_root(self) -> Self:
        log.debug(f'Promoting to root: {self}')
        self.parent = None
        self.iid = ''
        self.expand()
        return self


def _path_info(path: Path, tree_icons: PathTreeIcons) -> tuple[bool, str, str, PILImage]:
    try:
        stat_obj = path.stat()
    except OSError as e:
        log.error(f'Error obtaining stat info for path={path.as_posix()!r}: {e}')
        return False, '???', '', tree_icons.error_icon

    modified = datetime.fromtimestamp(int(stat_obj.st_mtime)).isoformat(' ')
    if S_ISDIR(stat_obj.st_mode):
        return True, '? items', modified, tree_icons.dir_icon
    else:
        return False, readable_bytes(stat_obj.st_size), modified, tree_icons.file_icon


def _dir_contents(directory: Path) -> list[Path]:
    try:
        return sorted(directory.iterdir())
    except OSError as e:
        log.error(f'Error expanding directory={directory.as_posix()!r}: {e}')
        return []
