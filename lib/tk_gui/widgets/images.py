"""
Tkinter GUI Scrollable Images
"""

from __future__ import annotations

import logging
from tkinter import BaseWidget, Frame, Image as TkBaseImage
from typing import TYPE_CHECKING, Union, Optional, Any, Iterator

from PIL.ImageTk import PhotoImage

from .scroll import ComplexScrollable
from .utils import get_size_and_pos

if TYPE_CHECKING:
    from tk_gui.styles import Style
    from tk_gui.typing import Bool, XY

__all__ = ['ScrollableImage']
log = logging.getLogger(__name__)

TkImage = Union[TkBaseImage, PhotoImage]


class ScrollableImage(ComplexScrollable, Frame):
    inner_widget: TkImage
    _inner_id: int | None = None

    # region Initialization

    def __init__(
        self,
        image: TkImage,
        width: int,
        height: int,
        *,
        parent: Optional[BaseWidget] = None,
        padx: int = 0,
        pady: int = 0,
        verify: bool = True,
        **kwargs,
    ):
        self.__size = size = (width, height)
        super().__init__(parent, width=width, height=height, padx=padx, pady=pady, verify=verify, **kwargs)
        self.set_image(image, size)

    def init_canvas_kwargs(self, style: Style = None) -> dict[str, Any]:
        kwargs = super().init_canvas_kwargs(style)
        kwargs['width'], kwargs['height'] = self.__size
        return kwargs

    # endregion

    def set_image(self, image: TkImage, size: XY):
        self.inner_widget = image
        try:
            del self.__dict__['widgets']  # Clear the cached property
        except KeyError:
            pass
        width, height = size
        center_w, center_h = width // 2, height // 2
        self._inner_id = self.canvas.create_image(center_w, center_h, image=image, anchor='center')
        log.debug(f'Created image={self._inner_id!r} @ {center_w=}, {center_h=}')

    def del_image(self):
        if (inner_id := self._inner_id) is not None:
            log.debug(f'Deleting image={inner_id!r}')
            self.canvas.delete(inner_id)
            self._inner_id = None

    def replace_image(self, image: TkImage, size: XY):
        self.del_image()
        self.set_image(image, size)

    def resize_scroll_region(self, size: XY | None, *, force: Bool = False):
        # if not self.auto_resize and not force:
        #     return
        canvas = self.canvas
        try:
            width, height = size
        except TypeError:
            width, height, x, y = get_size_and_pos(canvas)
            size = (width, height)

        if force or size != self._last_size:
            self.update_canvas_size(width, height)
            center_w, center_h = width // 2, height // 2
            log.debug(f'Moving image={self._inner_id!r} to {center_w=}, {center_h=}')
            canvas.moveto(self._inner_id, center_w, center_h)
        else:
            log.debug(f'No action necessary for {size=} == {self._last_size=}')

    def resize(self, width: int = None, height: int = None):
        self.configure(width=width, height=height)
        self.update_canvas_size(width=width, height=height)

        # center_w, center_h = width // 2, height // 2
        # log.debug(f'Moving image={self._inner_id!r} to {center_w=}, {center_h=}')
        # self.canvas.moveto(self._inner_id, center_w, center_h)

        # self.canvas.configure(width=width, height=height)
        # self.update_idletasks()
        # self.canvas.update_idletasks()
        # self.maybe_update_scroll_region()

    def _widgets(self) -> Iterator[BaseWidget]:
        yield self.inner_widget
        yield from super()._widgets()
