from __future__ import annotations

from tkinter.ttk import Style as TtkStyle
from unicodedata import normalize
from typing import TYPE_CHECKING

from wcwidth import wcswidth

from tk_gui.caching import cached_property
from tk_gui.images.icons import Icons
from tk_gui.styles.colors import RED_MD_0

if TYPE_CHECKING:
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
    _dir_icon_name = 'folder-fill'
    _error_icon_name = 'exclamation-circle-fill'

    def __init__(self, style: Style):
        self._style = style

    @cached_property(block=False)
    def dir_icon(self) -> PILImage:
        return self._icons.draw_with_transparent_bg(
            self._dir_icon_name, self._char_size, self._style.path_tree.dir_color.default
        )

    @cached_property(block=False)
    def file_icon(self) -> PILImage:
        return self._icons.draw_with_transparent_bg(
            self._file_icon_name, self._char_size, self._style.path_tree.file_color.default
        )

    @cached_property(block=False)
    def error_icon(self) -> PILImage:
        return self._icons.draw_with_transparent_bg(self._error_icon_name, self._char_size, RED_MD_0)

    @cached_property(block=False)
    def _char_size(self) -> XY:
        max_dim = max(self._style.text_size('W', layer='tree'))
        return max_dim, max_dim

    @cached_property(block=False)
    def _icons(self) -> Icons:
        return Icons()

    @cached_property(block=False)
    def _file_icon_name(self) -> str:
        if any(s.name == '_dark_base' for s in self._style._family):
            return 'file-earmark-text-fill'
        else:
            return 'file-earmark-text'
