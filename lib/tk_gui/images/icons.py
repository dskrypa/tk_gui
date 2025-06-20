"""
Utilities for generating PIL images based on `Bootstrap <https://icons.getbootstrap.com/>`_ icons, using the
bootstrap-icons font.

:author: Doug Skrypa
"""

from __future__ import annotations

from base64 import b64encode
from importlib.resources import files
from io import BytesIO
from typing import TYPE_CHECKING, Optional, Union, TypeVar, Iterator, Iterable

from PIL.Image import Image as PILImage, new as new_image, core as pil_image_core
from PIL.ImageFont import FreeTypeFont, truetype

from tk_gui.geometry import Box
from .color import color_to_rgb, find_unused_color

if TYPE_CHECKING:
    from pathlib import Path
    from PIL.Image.core import ImagingCore
    from tk_gui.typing import XY, Color, RGB, RGBA, ImageType  # noqa

__all__ = ['Icons', 'PlaceholderCache', 'placeholder_icon_cache', 'icon_path']

ICONS_DIR = files('tk_gui.icons')
ICON_DIR = ICONS_DIR.joinpath('bootstrap')
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)

Icon = Union[str, int]
IMG = TypeVar('IMG', bound='ImageType')

_core_draw = pil_image_core.draw
_core_fill = pil_image_core.fill


class Icons:
    __slots__ = ('font',)
    _font: Optional[FreeTypeFont] = None
    _names: Optional[dict[str, int]] = None

    def __init__(self, size: int = 10):
        if self._font is None:
            self.__class__._font = truetype(ICON_DIR.joinpath('bootstrap-icons.woff').as_posix())  # noqa
        self.font: FreeTypeFont = self._font.font_variant(size=size)

    @property
    def char_names(self) -> dict[str, int]:
        """
        Mapping of icon name to the character used to represent it.  Characters are stored in `bootstrap-icons.json`
        as integers, then converted in :meth:`.__getitem__` / :meth:`._normalize`.
        """
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
        if isinstance(icon, int):  # No lookup is necessary - assume it matches a char defined in bootstrap-icons.json
            return chr(icon)
        try:
            return self[icon]
        except KeyError:
            return icon  # assume it is a single-character string that matches an already-normalized char

    def _font_and_size(self, size: XY = None) -> tuple[FreeTypeFont, XY]:
        font = self.font
        font_size = font.size
        if size and (new_size := max(size)) != font_size:
            font = font.font_variant(size=new_size)
        else:
            size = (font_size, font_size)
        return font, size

    def draw(self, icon: Icon, size: XY = None, color: Color = BLACK, bg: Color = WHITE) -> PILImage:
        """
        :param icon: The name of the icon stored in :meth:`.char_names` to render.
        :param size: The font size to use, in pixels, if different from the size used to initialize this :class:`Icons`.
        :param color: The foreground color to use.
        :param bg: The background color to use.  For the background to be 100% transparent, the alpha value should be 0,
          e.g., ``#ffffff00`` or ``(255, 255, 255, 0)``.
        :return: The specified icon as a PIL Image object.  It will need to be wrapped in a :class:`.images.Image`
          element to be included in a layout.
        """
        font, size = self._font_and_size(size)
        return draw_icon(size, self._normalize(icon), color_to_rgb(color), color_to_rgb(bg), font)

    def draw_with_transparent_bg(self, icon: Icon, size: XY = None, color: Color = BLACK, bg: Color = None) -> PILImage:
        return self.draw(icon, size, color, pick_transparent_bg(color, bg))

    def draw_many(
        self, icons: Iterable[Icon], size: XY = None, color: Color = BLACK, bg: Color = WHITE
    ) -> Iterator[tuple[PILImage, Icon]]:
        font, size = self._font_and_size(size)
        bg, fg = color_to_rgb(bg), color_to_rgb(color)
        for icon in icons:
            yield draw_icon(size, self._normalize(icon), fg, bg, font), icon

    def draw_base64(self, *args, **kwargs) -> bytes:
        bio = BytesIO()
        self.draw(*args, **kwargs).save(bio, 'PNG')
        return b64encode(bio.getvalue())

    def draw_alpha_cropped(self, icon: Icon, size: XY = None, color: Color = BLACK, bg: Color = None) -> PILImage:
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
        bg = pick_transparent_bg(color, bg)
        # While the image will need to be drawn twice, the extra step is unavoidable to be able to produce an image
        # that matches the expected size due to differences in shapes between icons.
        image = self.draw(icon, size, color, bg)
        # The dimensions that would have been the result of cropping the image from the initial size are used with the
        # expected size to calculate the larger target width/height necessary to produce an image that is as close as
        # possible to the expected size after it has been cropped.
        target_size = Box(*image.getbbox()).scale_size(self._font_and_size(size)[1])
        image = self.draw(icon, target_size, color, bg)
        bbox = image.getbbox()
        return image.crop(bbox)


def pick_transparent_bg(fg: Color, bg: Color = None) -> RGBA:
    """
    :param fg: The foreground being used.
    :param bg: The background color to use.  For the background to be 100% transparent, the alpha value should be 0,
      e.g., ``#ffffff00`` or ``(255, 255, 255, 0)``.  If not specified, a value will automatically be chosen that
      is different than the specified foreground color.
    """
    if not bg:
        fg = tuple(color_to_rgb(fg)[:3])  # Ensure rgb and not rgba
        bg = (*find_unused_color(fg), 0)
    else:
        bg = color_to_rgb(bg)
        if len(bg) != 3:
            bg = (*bg, 0)

    return bg


def draw_icon(size: XY, text: str, fg: RGB | RGBA, bg: RGB | RGBA, font: FreeTypeFont) -> PILImage:
    """
    Optimized version of the following::

        from PIL.ImageDraw import ImageDraw
        image: PILImage = new_image('RGBA', size, color_to_rgb(bg))
        ImageDraw(image).text((0, 0), icon, fill=color_to_rgb(color), font=font)
        return image
    """
    # TODO: Automatically detect changes to the functions that this is replacing?
    image: PILImage = new_image('RGBA', size, bg)
    draw = _core_draw(image.im, 0)  # This would happen in ImageDraw.__init__, but it does many other unnecessary steps
    # mode=L is used for the remaining steps, matching the `fontmode` that would be set in __init__,
    # since `new_image` was called with mode=RGBA

    # The remaining steps replace the call to `ImageDraw.text`
    ink = draw.draw_ink(fg)         # replaces a call to the ImageDraw._getink helper that normalizes to this
    # The remaining steps replace the `draw_text` function defined inside `ImageDraw.text`
    # They also replace the call to `FreeTypeFont.getmask2` inside `draw_text`, which defines a `fill` function
    f_size, offset = font.font.getsize(text, 'L')  # noqa  # replaces a step performed in font.render
    mask: ImagingCore = _core_fill('L', f_size, 0)  # replaces the `fill` func defined inside `FreeTypeFont.getmask2`
    font.font.render(
        text,               # text
        lambda *a: mask,    # noqa  # fill (expects callable that accepts mode(str) + size(2-tuple))
        'L',                # mode
        None,               # direction
        None,               # features
        None,               # language
        0,                  # stroke_width
        False,              # stroke_filled (added in 11.2.x)
        None,               # anchor
        ink,                # ink
        (0, 0),             # Changed from expecting x/y separately in 11.2.x
    )
    draw.draw_bitmap(offset, mask, ink)  # replaces the last line of `draw_text`
    return image


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


def icon_path(rel_path: str) -> Path:
    return ICONS_DIR.joinpath(rel_path)  # noqa
