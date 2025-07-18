"""
Tkinter GUI Scrollable Images
"""

from __future__ import annotations

import logging
from tkinter import BaseWidget, Frame, Image as TkBaseImage
from typing import TYPE_CHECKING, Union, Optional, Any, Iterator

from PIL.ImageTk import PhotoImage as PilPhotoImage

from tk_gui.geometry import BBox
from .scroll import ComplexScrollable
from .utils import get_size_and_pos

if TYPE_CHECKING:
    from tk_gui.geometry.typing import XY
    from tk_gui.styles import Style

__all__ = ['ScrollableImage']
log = logging.getLogger(__name__)

TkImage = Union[TkBaseImage, PilPhotoImage]


class ScrollableImage(ComplexScrollable, Frame):
    __initializing: bool = True
    inner_widget: TkImage
    _inner_id: int | None = None
    _last_img_box = BBox(0, 0, 0, 0)

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
        self.__initializing = False

    def init_canvas_kwargs(self, style: Style = None) -> dict[str, Any]:
        kwargs = super().init_canvas_kwargs(style)
        kwargs['width'], kwargs['height'] = self.__size
        return kwargs

    # endregion

    def get_boxes(self):
        return {
            'frame': BBox.from_size_and_pos(*get_size_and_pos(self)),
            'canvas': BBox.from_size_and_pos(*get_size_and_pos(self.canvas)),
            'bar_x': BBox.from_size_and_pos(*get_size_and_pos(self.scroll_bar_x)),
            'bar_y': BBox.from_size_and_pos(*get_size_and_pos(self.scroll_bar_y)),
            'image': self._last_img_box,
        }

    def _center_image_box(self, size: XY) -> BBox:
        if self.__initializing:
            return BBox.from_pos_and_size(0, 0, *size)

        canvas_box = BBox.from_size_and_pos(*get_size_and_pos(self.canvas))
        # log.debug(f'Centering image within {canvas_box=}')
        return canvas_box.center(size)

    def set_image(self, image: TkImage, size: XY):
        self.inner_widget = image
        try:
            del self.__dict__['widgets']  # Clear the cached property
        except KeyError:
            pass

        self._last_img_box = img_box = self._center_image_box(size)
        x, y = img_box.min_xy
        # Note: Using anchor=center was not working as intended.  Using anchor=nw + a calculated position seems to
        # produce more consistent results.
        self._inner_id = self.canvas.create_image(x, y, image=image, anchor='nw')
        # log.debug(f'Created image={self._inner_id!r} @ {img_box}')

    def del_image(self):
        if (inner_id := self._inner_id) is not None:
            # log.debug(f'Deleting image={inner_id!r}')
            self.canvas.delete(inner_id)
            self._inner_id = None

    def replace_image(self, image: TkImage, size: XY):
        self.del_image()
        self.set_image(image, size)
        self.update_scroll_region()

    def update_scroll_region(self, force: bool = False, **kwargs):
        super().update_scroll_region(force, **kwargs)
        img_box = self._center_image_box(self._last_img_box.size)
        # if force or self._last_img_box != img_box:
        if self._last_img_box != img_box:
            self._last_img_box = img_box
            # log.debug(f'[{force=}] Moving image={self._inner_id!r} to center={img_box}')
            # log.debug(f'Moving image={self._inner_id!r} to center={img_box}')
            self.canvas.moveto(self._inner_id, *img_box.min_xy)

    def resize(self, width: int = None, height: int = None, force: bool = False):
        size = (width, height)
        if force or self._last_size != size:
            self.configure(width=width, height=height)
            self.update_canvas_size(width=width, height=height, force=force)
        else:
            self.update_scroll_region()

    def _widgets(self) -> Iterator[BaseWidget]:
        yield self.inner_widget  # noqa
        yield from super()._widgets()
