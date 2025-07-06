"""
Utilities for generating PIL images based on `Bootstrap <https://icons.getbootstrap.com/>`_ icons, using the
bootstrap-icons font.

:author: Doug Skrypa
"""

from __future__ import annotations

import logging
from base64 import b64encode
from importlib.resources import files
from io import BytesIO
from typing import TYPE_CHECKING, TypeVar, Iterator, Iterable

from PIL.Image import Image as PILImage, new as new_image, core as pil_image_core
from PIL.ImageFont import FreeTypeFont, truetype

from tk_gui.environment import ON_LINUX
from tk_gui.geometry import Box, Padding
from .color import color_to_rgb, find_unused_color

if TYPE_CHECKING:
    from pathlib import Path
    from PIL.Image.core import ImagingCore
    from tk_gui.typing import XY, Color, RGB, RGBA, ImageType  # noqa

__all__ = ['Icons', 'PlaceholderCache', 'placeholder_icon_cache', 'icon_path']
log = logging.getLogger(__name__)

ICONS_DIR = files('tk_gui.icons')
ICON_DIR = ICONS_DIR.joinpath('bootstrap')
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)

Icon = str | int
IMG = TypeVar('IMG', bound='ImageType')

_core_draw = pil_image_core.draw
_core_fill = pil_image_core.fill


class Icons:
    __slots__ = ('font', '_text_font')
    font: FreeTypeFont
    _font: FreeTypeFont | None = None
    _text_font: FreeTypeFont | None
    _names: dict[str, int] | None = None

    def __init__(self, size: int = 10, text_font: str | None = None):
        if self._font is None:
            self.__class__._font = truetype(ICON_DIR.joinpath('bootstrap-icons.woff2').as_posix())  # noqa
        self.font = self._font.font_variant(size=size)
        if ON_LINUX and text_font is None:
            try:
                self._text_font = truetype('DejaVuSans.ttf', size)
            except OSError as e:
                log.warning(f'Unable to load default font: {e}')
                self._text_font = None
        else:
            self._text_font = truetype(text_font, size) if text_font else None

    @property
    def char_names(self) -> dict[str, int]:
        """
        Mapping of icon name to the character used to represent it.  Characters are stored in `bootstrap-icons.json`
        as integers, then converted in :meth:`.__getitem__` / :meth:`._normalize`.
        """
        if self._names is None:
            import json

            with ICON_DIR.joinpath('bootstrap-icons.json').open('r', encoding='utf-8') as f:
                self.__class__._names = {k: v for k, v in sorted(json.load(f).items())}

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
        return draw_icon(size, self._normalize(icon), font, color_to_rgb(color), color_to_rgb(bg))

    def draw_with_transparent_bg(
        self,
        icon: Icon,
        size: XY = None,
        color: Color = BLACK,
        bg: Color = None,
        *,
        rotate_angle: int = None,
        pad: Padding = None,
    ) -> PILImage:
        bg = pick_transparent_bg(color, bg)
        image = self.draw(icon, size, color, bg)
        return _rotate_and_pad(image, bg, rotate_angle, pad)

    def draw_many(
        self, icons: Iterable[Icon], size: XY = None, color: Color = BLACK, bg: Color = WHITE
    ) -> Iterator[tuple[PILImage, Icon]]:
        font, size = self._font_and_size(size)
        bg, fg = color_to_rgb(bg), color_to_rgb(color)
        for icon in icons:
            yield draw_icon(size, self._normalize(icon), font, fg, bg), icon

    def draw_base64(self, *args, **kwargs) -> bytes:
        bio = BytesIO()
        self.draw(*args, **kwargs).save(bio, 'PNG')
        return b64encode(bio.getvalue())

    def draw_alpha_cropped(
        self,
        icon: Icon,
        size: XY = None,
        color: Color = BLACK,
        bg: Color = None,
        *,
        rotate_angle: int = None,
        pad: Padding = None,
    ) -> PILImage:
        """
        Draws the specified icon with an automatically selected background color that will be rendered transparent, and
        crops the image so that the visible icon will reach the edges of the canvas.

        :param icon: The name of the icon stored in :meth:`.char_names` to render.
        :param size: The font size to use, in pixels, if different from the size used to initialize this :class:`Icons`.
        :param color: The foreground color to use.
        :param bg: The background color to use.  For the background to be 100% transparent, the alpha value should be 0,
          e.g., ``#ffffff00`` or ``(255, 255, 255, 0)``.  If not specified, a value will automatically be chosen that
          is different than the specified foreground color.
        :param rotate_angle: Degrees to rotate, if any.  Applied before padding, if specified.
        :param pad: A Padding object providing top/left/bottom/right pad values to apply to the final image
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
        # Note about bbox here: `Icons(30).font.getbbox(icons._normalize('house-door'))` => (0, 2, 30, 30)
        #  but `Icons(30).draw_with_transparent_bg('house-door').getbbox()` => (3, 2, 28, 28)
        image = self.draw(icon, target_size, color, bg)
        return _rotate_and_pad(image.crop(image.getbbox()), bg, rotate_angle, pad)

    def draw_with_text(
        self,
        icon: Icon,
        text: str,
        fg: Color = BLACK,
        bg: Color = None,
        *,
        transparent_bg: bool = False,
        it_pad_x: int = 0,  # padding between the image and text along the x-axis
    ) -> PILImage:
        # TODO: Add support for padding around the content; separate icon/text sizes
        fg = color_to_rgb(fg)
        if transparent_bg:
            bg = pick_transparent_bg(fg, bg)
        else:
            bg = WHITE if bg is None else color_to_rgb(bg)

        icon = self._normalize(icon)
        iw, ih = self.font.getbbox(icon)[2:]
        tw, th = self._text_font.getbbox(text)[2:]
        image: PILImage = new_image('RGBA', (iw + tw + it_pad_x, max(ih, th)), bg)
        _draw_icon(image, icon, self.font, fg)
        _draw_icon(image, text, self._text_font, fg, x_offset=iw + it_pad_x)
        return image


def _rotate_and_pad(image: PILImage, bg: RGBA, rotate_angle: int = None, pad: Padding = None) -> PILImage:
    if rotate_angle:
        image = image.rotate(rotate_angle)

    if pad:
        padded_image: PILImage = new_image('RGBA', pad.size_for(image), bg)  # noqa
        log.debug(f'Padding image with size={image.size} -> {padded_image.size} using {pad=}')
        padded_image.paste(image, (pad.left, pad.top))
        return padded_image
    else:
        return image


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


def draw_icon(
    size: XY,
    text: str,
    font: FreeTypeFont,
    fg: RGB | RGBA,
    bg: RGB | RGBA,
) -> PILImage:
    """
    Optimized version of the following::

        from PIL.ImageDraw import ImageDraw
        image: PILImage = new_image('RGBA', size, color_to_rgb(bg))
        ImageDraw(image).text((0, 0), icon, fill=color_to_rgb(color), font=font)
        return image
    """
    # TODO: Automatically detect changes to the functions that this is replacing?
    return _draw_icon(new_image('RGBA', size, bg), text, font, fg)


def _draw_icon(
    image: PILImage,
    text: str,
    font: FreeTypeFont,
    fg: RGB | RGBA = (0, 0, 0),
    x_offset: int = 0,
) -> PILImage:
    # ImageDraw.__init__(...):
    draw = _core_draw(image.im, 0)  # This would happen in ImageDraw.__init__, but it does many other unnecessary steps
    # self.fontmode = '1' if mode in '1PIF' else 'L' => (font)mode=L used for remaining steps, since RGBA was used above

    # ImageDraw.text(...):
    ink = draw.draw_ink(fg)         # replaces a call to the ImageDraw._getink helper that normalizes to this

    # ImageDraw.text(...).draw_text: (nested function)
    # mode = self.fontmode (L); xy = (0, 0) => coord = start = (0, 0)
    # mask, offset = font.getmask2(...) is used by the original method because `FreeTypeFont.getmask2` exists

    # ImageFont.FreeTypeFont.getmask2(...):
    mask, offset = font.font.render(       # This step was performed in `PIL.ImageFont.FreeTypeFont.getmask2`
        text,               # text
        _render_fill,       # fill
        'L',                # mode
        None,               # direction
        None,               # features
        None,               # language
        0,                  # stroke_width
        False,              # stroke_filled (added in 11.2.x)
        None,               # anchor
        ink,                # ink
        (0, 0),             # start (changed from expecting x/y separately in 11.2.x)
    )

    # Back in ImageDraw.text(...).draw_text:
    coord = (x_offset, offset[1]) if x_offset else offset
    # The original used `coord = (start[0] + offset[0], start[1] + offset[1])`, but that produces very poor results
    # for start points != (0, 0)
    # This will probably only work for drawing a single row of images - refactoring will be necessary to draw a grid
    # log.info(f'Drawing rendered mask for {text=} with {image.size=}, {x_offset=}, {offset=}, {coord=}, {mask.size=}')
    draw.draw_bitmap(coord, mask, ink)
    return image


def _render_fill(width: int, height: int) -> ImagingCore:
    # Replaces the `fill` function defined/nested in `PIL.ImageFont.FreeTypeFont.getmask2(...)`
    # Original uses `'RGBA' if mode == 'RGBA' else 'L'` where mode == ImageDraw.fontmode == 'L' when image mode = RGBA
    # The width/height passed to this func can also be obtained via `f_size, offset = font.font.getsize(text, 'L')`
    # The returned value is treated as a mask, and is passed through in `self.font.render(...)`'s return value
    return _core_fill('L', (width, height))


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

    def image_or_placeholder(self, image: IMG | None, size: XY | float | int) -> IMG | PILImage:
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
