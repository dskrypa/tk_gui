from __future__ import annotations

from tkinter.font import Font as TkFont
from typing import Any, Literal, Mapping, Union

from tk_gui.enums import StyleState

Layer = Literal[
    'base', 'insert', 'scroll', 'arrows', 'radio', 'checkbox', 'frame', 'combo', 'progress', 'image', 'tooltip', 'text',
    'button', 'listbox', 'link', 'selected', 'input', 'table', 'table_header', 'table_alt', 'slider', 'menu',
    'checkbox_label', 'tree', 'tree_header', 'path_tree'
]

StateName = Literal['default', 'disabled', 'invalid', 'active', 'highlight']
StyleAttr = Literal[
    'font', 'tk_font', 'fg', 'bg', 'border_width', 'relief',
    'frame_color', 'trough_color', 'arrow_color', 'arrow_width', 'bar_width',  # Scroll bar options
    'dir_color', 'file_color',  # path_tree
]
StyleOptions = Mapping[str, Any]
StyleSpec = Union[str, 'Style', StyleOptions, tuple[str, StyleOptions], None]
StyleStateVal = Union[StyleState, StateName, Literal[0, 1, 2]]
Relief = Literal['raised', 'sunken', 'flat', 'ridge', 'groove', 'solid'] | None

OptInt = int | None
OptStr = str | None

_OptStrTuple = Union[
    tuple[OptStr], tuple[(OptStr,) * 2], tuple[(OptStr,) * 3], tuple[(OptStr,) * 4], tuple[(OptStr,) * 5]
]
OptStrVals = Union[OptStr, Mapping[StyleStateVal, OptStr], _OptStrTuple]

_OptIntTuple = Union[
    tuple[OptInt], tuple[(OptInt,) * 2], tuple[(OptInt,) * 3], tuple[(OptInt,) * 4], tuple[(OptInt,) * 5]
]
OptIntVals = Union[OptInt, Mapping[StyleStateVal, OptInt], _OptIntTuple]

Font = Union[str, tuple[str, int], tuple[str, int, str, ...], None]
_FontValsTuple = Union[tuple[Font], tuple[(Font,) * 2], tuple[(Font,) * 3], tuple[(Font,) * 4], tuple[(Font,) * 5]]
FontValues = Union[Font, Mapping[StyleStateVal, Font], _FontValsTuple]
FontMetric = Literal['ascent', 'descent', 'linespace', 'fixed']

StyleValue = Union[OptStr, OptInt, Font]
FinalValue = Union[StyleValue, TkFont]
RawStateValues = Union[OptStrVals, OptIntVals, FontValues]

LayerValues = Union[FontValues, Mapping[StyleStateVal, StyleValue]]
