"""
Utilities for working with text elements.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Union, Sequence

if TYPE_CHECKING:
    from .text import Text, Input


def normalize_text_ele_widths(rows: Sequence[Sequence[Union[Text, Input]]], column: int = 0):
    if not rows:
        return rows

    longest = max(row[column].expected_width for row in rows)
    if longest < 1:
        return rows

    for row in rows:
        ele = row[column]
        ele.size = (longest, ele.expected_height)

    return rows
