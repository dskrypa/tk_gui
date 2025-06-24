from __future__ import annotations

from tkinter.ttk import Style as TtkStyle
from unicodedata import normalize
from typing import TYPE_CHECKING

from wcwidth import wcswidth

from tk_gui.caching import cached_property
from tk_gui.images.icons import Icons
from tk_gui.styles.colors import RED_MD_0

if TYPE_CHECKING:
    from pathlib import Path
    from PIL.Image import Image as PILImage
    from tk_gui.styles.style import Style
    from tk_gui.typing import XY


def _style_map_data(style: TtkStyle, name: str, query_opt: str, selected_color: str = None):
    # Based on the fix for setting text color for Tkinter 8.6.9 from: https://core.tcl.tk/tk/info/509cafafae
    base = _filtered_style_map_eles(style, 'Treeview', query_opt)
    rows = _filtered_style_map_eles(style, name, query_opt)
    if selected_color:
        rows.append(('selected', selected_color))
    return rows + base


def _filtered_style_map_eles(style: TtkStyle, name: str, query_opt: str):
    return [ele for ele in style.map(name, query_opt=query_opt) if '!' not in ele[0] and 'selected' not in ele[0]]


def mono_width(text: str) -> int:
    return wcswidth(normalize('NFC', text))


class PathTreeIcons:
    _error_icon_name = 'exclamation-circle-fill'
    _dir_icon_name = 'folder-fill'
    _default_file_icon_names = ('file-earmark-text', 'file-earmark-text-fill')
    _file_type_icon_name_map = {  # (light icon, dark icon)
        'image': ('file-earmark-image', 'file-earmark-image-fill'),  # card-image
        'audio': ('file-earmark-music', 'file-earmark-music-fill'),
        'video': ('file-earmark-play', 'file-earmark-play-fill'),
    }
    _file_type_suffixes_map = {
        'image': {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.ico', '.jfif', '.tif', '.tiff'},
        'audio': {'.flac', '.alac', '.ogg', '.mp3'},
        'video': {'.mkv', '.mp4', '.mov'},
    }

    def __init__(self, style: Style):
        self._style = style
        self._file_icons: dict[str, PILImage] = {}

    # region Internal Properties

    @cached_property(block=False)
    def _icons(self) -> Icons:
        return Icons()

    @cached_property(block=False)
    def _char_size(self) -> XY:
        max_dim = max(self._style.text_size('W', layer='tree'))
        return max_dim, max_dim

    # endregion

    # region Static Icons

    @cached_property(block=False)
    def error_icon(self) -> PILImage:
        return self._icons.draw_with_transparent_bg(self._error_icon_name, self._char_size, RED_MD_0)

    @cached_property(block=False)
    def dir_icon(self) -> PILImage:
        return self._icons.draw_with_transparent_bg(
            self._dir_icon_name, self._char_size, self._style.path_tree.dir_color.default
        )

    # endregion

    # region File Icons

    def get_file_icon(self, path: Path) -> PILImage:
        name = self._get_file_icon_name(path)
        try:
            return self._file_icons[name]
        except KeyError:
            pass
        # TODO: Improve colors
        icon = self._icons.draw_with_transparent_bg(name, self._char_size, self._style.path_tree.file_color.default)
        self._file_icons[name] = icon
        return icon

    def _get_file_icon_name(self, path: Path) -> str:
        try:
            file_type = self._suffix_file_type_map[path.suffix]
        except KeyError:
            return self._default_file_icon_names[self._file_icon_index]
        else:
            return self._file_type_icon_name_map.get(file_type, self._default_file_icon_names)[self._file_icon_index]

    @cached_property(block=False)
    def _suffix_file_type_map(self) -> dict[str, str]:
        return {ext: ft for ft, exts in self._file_type_suffixes_map.items() for ext in exts}

    @cached_property(block=False)
    def _file_icon_index(self) -> int:
        if any(s.name == '_dark_base' for s in self._style._family):
            return 1  # dark
        else:
            return 0  # light

    # endregion


class PathTreeConfig:
    __slots__ = ('files', 'dirs', 'tree_icons')
    files: bool
    dirs: bool
    tree_icons: PathTreeIcons

    def __init__(self, style: Style, files: bool = True, dirs: bool = True):
        if not files and not dirs:
            raise ValueError('At least one of files or dirs must be enabled/True')
        self.files = files
        self.dirs = dirs
        self.tree_icons = PathTreeIcons(style)
