from __future__ import annotations

from tkinter.ttk import Style as TtkStyle
from unicodedata import normalize

from wcwidth import wcswidth


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
