"""
Utilities for generating PIL images based on `Bootstrap <https://icons.getbootstrap.com/>`_ icons, using the
bootstrap-icons font.

:author: Doug Skrypa
"""

from __future__ import annotations

from base64 import b64encode
from io import BytesIO
from typing import TYPE_CHECKING, Optional, Union, TypeVar

from PIL.Image import Image as PILImage, new as new_image
from PIL.ImageDraw import ImageDraw, Draw
from PIL.ImageFont import FreeTypeFont, truetype

from .color import color_to_rgb, find_unused_color
from .utils import ICONS_DIR, calculate_resize

if TYPE_CHECKING:
    from ..typing import XY, Color, ImageType  # noqa

__all__ = ['Icons', 'PlaceholderCache', 'placeholder_icon_cache']

ICON_DIR = ICONS_DIR.joinpath('bootstrap')

Icon = Union[str, int]
IMG = TypeVar('IMG', bound='ImageType')


class Icons:
    __slots__ = ('font',)
    _font: Optional[FreeTypeFont] = None
    _names: Optional[dict[str, int]] = None

    def __init__(self, size: int = 10):
        if self._font is None:
            self.__class__._font = truetype(ICON_DIR.joinpath('bootstrap-icons.woff').as_posix())
        self.font: FreeTypeFont = self._font.font_variant(size=size)

    @property
    def char_names(self) -> dict[str, int]:
        if self._names is None:
            import json

            with ICON_DIR.joinpath('bootstrap-icons.json').open('r', encoding='utf-8') as f:
                self.__class__._names = json.load(f)

        return self._names

    def change_size(self, size: int):
        self.font = self.font.font_variant(size=size)

    def __getitem__(self, char_name: str) -> str:
        return chr(self.char_names[char_name])

    def _normalize(self, icon: Icon) -> str:
        if isinstance(icon, int):  # TODO: What is the use case for this / what is this supposed to result in?
            return chr(icon)
        try:
            return self[icon]
        except KeyError:
            return icon  # TODO: This may not be valid either...

    def _font_and_size(self, size: XY = None) -> tuple[FreeTypeFont, XY]:
        if size:
            font = self.font.font_variant(size=max(size))
        else:
            font = self.font
            size = (font.size, font.size)
        return font, size

    def draw(self, icon: Icon, size: XY = None, color: Color = '#000000', bg: Color = '#ffffff') -> PILImage:
        """
        :param icon: The name of the icon stored in :meth:`.char_names` to render.
        :param size: The font size to use, in pixels, if different from the size used to initialize this :class:`Icons`.
        :param color: The foreground color to use.
        :param bg: The background color to use.  For the background to be 100% transparent, the alpha value should be 0,
          e.g., ``#ffffff00`` or ``(255, 255, 255, 0)``.
        :return: The specified icon as a PIL Image object.  It will need to be wrapped in a :class:`.images.Image`
          element to be included in a layout.
        """
        icon = self._normalize(icon)
        font, size = self._font_and_size(size)
        image: PILImage = new_image('RGBA', size, color_to_rgb(bg))
        draw: ImageDraw = Draw(image)
        draw.text((0, 0), icon, fill=color_to_rgb(color), font=font)
        return image

    def draw_base64(self, *args, **kwargs) -> bytes:
        bio = BytesIO()
        self.draw(*args, **kwargs).save(bio, 'PNG')
        return b64encode(bio.getvalue())

    def draw_alpha_cropped(self, icon: Icon, size: XY = None, color: Color = '#000000', bg: Color = None) -> PILImage:
        """
        Draws the specified icon with an automatically selected background color that will be rendered transparent, and
        crops the image so that the visible icon will reach the edges of the canvas.

        :param icon: The name of the icon stored in :meth:`.char_names` to render.
        :param size: The font size to use, in pixels, if different from the size used to initialize this :class:`Icons`.
        :param color: The foreground color to use.
        :param bg: The background color to use.  For the background to be 100% transparent, the alpha value should be 0,
          e.g., ``#ffffff00`` or ``(255, 255, 255, 0)``.  If not specified, a value will automatically be chosen that
          is different than the specified foreground color.
        :return: The specified icon as a PIL Image object.  It will need to be wrapped in a :class:`.images.Image`
          element to be included in a layout.
        """
        if not bg:
            fg = tuple(color_to_rgb(color)[:3])  # Ensure rgb and not rgba
            bg = (*find_unused_color(fg), 0)
        else:
            bg = color_to_rgb(bg)
            if len(bg) != 3:
                bg = (*bg, 0)

        image = self.draw(icon, size, color, bg)
        # While the image will need to be drawn twice, the extra step is unavoidable to be able to produce an image
        # that matches the expected size due to differences in shapes between icons.
        target_size = _calculate_redraw_size(image, *self._font_and_size(size)[1])
        image = self.draw(icon, target_size, color, bg)
        bbox = image.getbbox()
        return image.crop(bbox)


def _calculate_redraw_size(image: PILImage, exp_width: int, exp_height: int) -> XY:
    # The dimensions that would have been the result of cropping the image from the initial size are used with the
    # expected size to calculate the larger target width/height necessary to produce an image that is as close as
    # possible to the expected size after it has been cropped.
    x1, y1, x2, y2 = image.getbbox()
    crp_width, crp_height = (x2 - x1), (y2 - y1)  # Cropped width/height
    trg_width = exp_width / (crp_width / exp_width)
    trg_height = exp_height / (crp_height / exp_height)
    target_size = calculate_resize(x2 - x1, y2 - y1, trg_width, trg_height)  # Necessary to stay within bounds
    # log.debug(f'Using {target_size=} {trg_width=} x {trg_height=}')
    return target_size


class PlaceholderCache:
    __slots__ = ('_cache', '_icon')

    def __init__(self, icon: Icon = 'x'):
        self._cache = {}
        self._icon = icon

    def get_placeholder(self, size: XY | float | int) -> PILImage:
        try:
            size = int(max(size))
        except TypeError:  # int/float is not iterable
            size = int(size)
        try:
            return self._cache[size]
        except KeyError:
            self._cache[size] = image = Icons(size).draw_alpha_cropped(self._icon)
            return image

    def image_or_placeholder(self, image: Optional[IMG], size: XY | float | int) -> IMG | PILImage:
        """
        :param image: An image or falsey value if a placeholder should be rendered instead
        :param size: The size of the placeholder image that should be rendered for use in place of the missing image
        :return: The provided image, unchanged, if it was truthy, otherwise a placeholder PIL Image
        """
        if image:
            return image
        return self.get_placeholder(size)


placeholder_icon_cache: PlaceholderCache = PlaceholderCache()
