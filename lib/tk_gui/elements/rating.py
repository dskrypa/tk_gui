"""
Tkinter GUI Rating Element

:author: Doug Skrypa
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable, Iterator, Literal

from PIL.Image import Image as PILImage, new as new_image

from tk_gui.caching import cached_property
from ..event_handling import BindManager
from .frame import InteractiveRowFrame
from .images import Image
from .text import Text, Input

if TYPE_CHECKING:
    from tkinter import Event

    from ..typing import Bool, XY
    from .element import Element

__all__ = ['Rating']
log = logging.getLogger(__name__)

RATING_RANGES = [(1, 31, 15), (32, 95, 64), (96, 159, 128), (160, 223, 196), (224, 255, 255)]

Color = Literal['black', 'gold']
RatingColor = Literal['black', 'gold', 'mix']
FillAmount = Literal['empty', 'full', 'half']


class Rating(InteractiveRowFrame):
    def __init__(
        self,
        rating: int = None,
        color: RatingColor = 'mix',
        star_size: XY = None,
        show_value: Bool = False,
        change_cb: Callable = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._rating = rating or 0
        self._valid_value = 0 <= self._rating <= 10
        self._color = color
        width, height = self._star_size = star_size or (12, 12)
        self._star_full_size = (width * 5 + 4, height)
        self._show_value = show_value
        self._last_cb_rating = self._rating
        self._button_down = False
        self._change_cb = change_cb

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}({self.rating}, key={self._key!r}, {self._show_value=}, {self.disabled=})>'

    # @property
    # def is_valid(self) -> bool:
    #     return 0 <= self._rating <= 10

    @property
    def value(self) -> int:
        return self.rating

    @property
    def rating(self) -> int:
        # return self._rating if self.is_valid else 0
        return self._rating if self._valid_value else 0

    @rating.setter
    def rating(self, value: int):
        self._rating = 10 if value > 10 else 0 if value < 0 else value

    # region Star Image

    @property
    def color(self) -> Color:
        if (color := self._color) != 'mix':
            return color  # noqa
        return 'gold' if self.rating else 'black'

    @cached_property
    def _star_images(self) -> dict[Color, dict[FillAmount, PILImage]]:
        from ..images.icons import Icons

        colors = {'gold': '#F2D250', 'black': '#000000'}
        names = {'empty': 'star', 'half': 'star-half', 'full': 'star-fill'}
        icons = Icons(max(self._star_size))
        images = {
            color: {name: icons.draw(icon, color=rgb, bg='#ffffff00') for name, icon in names.items()}
            for color, rgb in colors.items()
        }
        return images  # noqa

    def _iter_star_images(self) -> Iterator[PILImage]:
        images = self._star_images[self.color]
        for key, num in zip(('full', 'half', 'empty'), star_fill_counts(self.rating, half=True)):
            if num:
                image = images[key]  # noqa
                for _ in range(num):
                    yield image

    def _combined_stars(self) -> PILImage:
        width, height = self._star_size
        combined = new_image('RGBA', self._star_full_size)
        for i, image in enumerate(self._iter_star_images()):
            combined.paste(image, (width * i + i, 0))
        return combined

    @cached_property
    def star_element(self) -> Image:
        return Image(self._combined_stars(), size=self._star_full_size, pad=(0, 0))

    # endregion

    @cached_property
    def rating_input(self) -> Input | None:
        if not self._show_value:
            return None
        return Input(self._rating, disabled=self.disabled, size=(5, 1), tooltip=self.tooltip_text)

    @property
    def elements(self) -> tuple[Element, ...]:
        if rating_input := self.rating_input:
            return rating_input, Text('(out of 10)', size=(8, 1)), self.star_element
        return (self.star_element,)  # noqa

    def pack_elements(self, debug: Bool = False):
        super().pack_elements(debug)
        if not self.disabled:
            self.disabled = True    # Due to the `if not self.disabled` check
            self.enable()           # Apply binds and maybe add the input var trace
        if (rating_input := self.rating_input) and not self._valid_value:
            rating_input.validated(False)

    # region Event Handling

    def _handle_star_clicked(self, event: Event):
        self._button_down = True
        self.rating = round(int(100 * event.x / self.star_element.widget.winfo_width()) / 10)
        self._update()

    def _handle_value_changed(self, tk_var_name: str, index, operation: str):
        rating_input = self.rating_input
        if value := rating_input.value:
            try:
                value = int(value)
                stars_to_256(value, 10)
            except (ValueError, TypeError) as e:
                log.warning(f'Invalid rating: {e}')
                # TODO: error popup
                self.validated(False)
                # popup_error(f'Invalid rating:\n{e}', auto_size=True)
            else:
                self.validated(True)
        else:
            self.validated(True)
            value = 0

        self._rating = value
        self.star_element.image = self._combined_stars()
        self._maybe_callback()

    def _handle_button_released(self, event):
        self._button_down = False
        self._maybe_callback()

    def _maybe_callback(self):
        if self._change_cb is not None and not self._button_down:
            if self._last_cb_rating != self._rating and self._valid_value:
                self._last_cb_rating = self._rating
                self._change_cb(self)

    # endregion

    def validated(self, valid: bool):
        if self._valid_value != valid:
            self._valid_value = valid
        if rating_input := self.rating_input:
            rating_input.validated(valid)

    def update(self, rating: int = None, disabled: Bool = None):
        if disabled is not None:
            self.toggle_enabled(disabled)
        if rating is not None:
            if not (0 <= rating <= 10):
                raise ValueError(f'Invalid {rating=} - value must be between 0 and 10, inclusive')
            self._rating = rating
            self._update()

    def _update(self):
        if rating_input := self.rating_input:
            rating_input.update(self.rating)
            rating_input.validated(True)
            # The rating input value change will trigger _handle_value_changed to update the star element
        else:
            self.star_element.image = self._combined_stars()

    @cached_property
    def _bind_manager(self) -> BindManager:
        binds = {
            '<Button-1>': self._handle_star_clicked,
            '<ButtonRelease-1>': self._handle_button_released,
            '<B1-Motion>': self._handle_star_clicked,
        }
        return BindManager(binds)

    def enable(self):
        if not self.disabled:
            return
        self._bind_manager.bind_all(self.star_element.widget)
        if rating_input := self.rating_input:
            rating_input.enable()
            rating_input.var_change_cb = self._handle_value_changed

        self.disabled = False

    def disable(self):
        if self.disabled:
            return
        self._bind_manager.unbind_all(self.star_element.widget)
        if rating_input := self.rating_input:
            del rating_input.var_change_cb
            rating_input.disable()
        self.disabled = True


def star_fill_counts(
    rating: int | float, out_of: int = 10, num_stars: int = 5, half=None
) -> tuple[int, int, int]:
    if out_of < 1:
        raise ValueError('out_of must be > 0')

    filled, remainder = map(int, divmod(num_stars * rating, out_of))
    if half and remainder:
        empty = num_stars - filled - 1
        half = 1
    else:
        empty = num_stars - filled
        half = 0
    return filled, half, empty


def stars_to_256(rating: int | float, out_of: int = 5) -> int | None:
    """
    This implementation uses the same values specified in the following link, except for 1 star, which uses 15
    instead of 1: https://en.wikipedia.org/wiki/ID3#ID3v2_rating_tag_issue

    :param rating: The number of stars to set (out of 5/10/256)
    :param out_of: The max value to use for mapping from 0-`out_of` to 0-255.  Only supports 5, 10, and 256.
    :return: The rating mapped to a value between 0 and 255
    """
    if not (0 <= rating <= out_of):
        raise ValueError(f'{rating=} is outside the range of 0-{out_of}')
    elif out_of == 256:
        return int(rating)
    elif out_of not in (5, 10):
        raise ValueError(f'{out_of=} is invalid - must be 5, 10, or 256')
    elif rating == 0:
        return None
    elif (int_rating := int(rating)) == (0 if out_of == 5 else 1):
        return 1
    elif out_of == 5:
        base, extra = int_rating, int(int_rating != rating)
        if extra and int_rating + 0.5 != rating:
            raise ValueError(f'Star ratings {out_of=} must be a multiple of 0.5; invalid value: {rating}')
    else:
        base, extra = divmod(int_rating, 2)

    return RATING_RANGES[base - 1][2] + extra
