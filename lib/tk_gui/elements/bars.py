"""
Separators, progress bars, and other bar-like GUI elements

:author: Doug Skrypa
"""

from __future__ import annotations

import logging
import tkinter.constants as tkc
from math import floor, ceil
from tkinter import Scale, IntVar, DoubleVar, TclError
from tkinter.ttk import Separator as TtkSeparator, Progressbar
from typing import TYPE_CHECKING, Iterable, Iterator, Union, Any

from ..exceptions import WindowClosed
from .element import ElementBase, Element, Interactive
from .mixins import DisableableMixin, CallbackCommandMixin

if TYPE_CHECKING:
    from ..pseudo_elements import Row
    from ..typing import Bool, Orientation, T, BindTarget, TkContainer

__all__ = ['Separator', 'HorizontalSeparator', 'VerticalSeparator', 'ProgressBar', 'Slider']
log = logging.getLogger(__name__)

# region Separators


class Separator(ElementBase, base_style_layer='separator'):
    widget: TtkSeparator

    def __init__(self, orientation: Orientation, **kwargs):
        super().__init__(**kwargs)
        self.orientation = orientation

    def _init_widget(self, tk_container: TkContainer):
        style = self.style
        name, ttk_style = style.make_ttk_style('.Line.TSeparator')
        ttk_style.configure(name, background=style.separator.bg.default)
        self.widget = TtkSeparator(tk_container, orient=self.orientation, style=name, takefocus=int(self.allow_focus))

    def pack_into(self, row: Row):
        self._init_widget(row.frame)
        fill, expand = (tkc.X, True) if self.orientation == tkc.HORIZONTAL else (tkc.Y, False)
        self.pack_widget(fill=fill, expand=expand)


class HorizontalSeparator(Separator):
    def __init__(self, **kwargs):
        super().__init__(tkc.HORIZONTAL, **kwargs)

    def pack_into(self, row: Row):
        if len(row.elements) == 1 and row.anchor.is_horizontal_center:
            row.expand = True
            row.fill = tkc.X
        super().pack_into(row)


class VerticalSeparator(Separator):
    def __init__(self, **kwargs):
        super().__init__(tkc.VERTICAL, **kwargs)


# endregion


class ProgressBar(Element, base_style_layer='progress'):
    widget: Progressbar

    def __init__(
        self,
        max_value: int,
        default: int = 0,
        orientation: Orientation = tkc.HORIZONTAL,
        max_on_exit: Bool = True,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.max_value = max_value
        self.default = default
        self.orientation = orientation
        self.max_on_exit = max_on_exit

    # region Value

    @property
    def value(self) -> int:
        return self.widget['value']

    @value.setter
    def value(self, value: int):
        bar = self.widget
        try:
            bar['value'] = value
            bar.update()  # Update is required to handle things like window close events - update_idletasks does not
        except TclError as e:
            if self.window.closed:
                raise WindowClosed(f'Interrupted while processing item {value} / {self.max_value}') from e
            raise

    def increment(self, amount: int = 1):
        bar = self.widget
        try:
            bar['value'] += amount
            bar.update()  # Update is required to handle things like window close events - update_idletasks does not
        except TclError as e:
            if self.window.closed:
                raise WindowClosed(f'Interrupted while processing item ? / {self.max_value}') from e
            raise

    def decrement(self, amount: int = 1):
        self.increment(-amount)

    # endregion

    def _prepare_ttk_style(self, thickness: int = None) -> str:
        style = self.style
        name, ttk_style = style.make_ttk_style(f'.{self.orientation.title()}.TProgressbar')
        kwargs = style.get_map(
            'progress', background='bg',
            troughcolor='trough_color', troughrelief='relief',
            borderwidth='border_width', thickness='bar_width',
        )
        kwargs.setdefault('troughrelief', 'groove')
        if thickness is not None:
            kwargs['thickness'] = thickness
        ttk_style.configure(name, **kwargs)
        return name

    def _init_widget(self, tk_container: TkContainer):
        horizontal = self.orientation == tkc.HORIZONTAL
        try:
            if horizontal:
                length, thickness = self.size
            else:
                thickness, length = self.size
        except TypeError:
            length = thickness = None

        kwargs = {
            'style': self._prepare_ttk_style(thickness),
            'orient': self.orientation,
            'value': self.default,
            'takefocus': int(self.allow_focus),
            'length': length,
            **self.style_config,
        }
        self.widget = Progressbar(tk_container, mode='determinate', **kwargs)

    def update(self, value: int, increment: Bool = True, max_value: int = None):
        if max_value is not None:
            self.max_value = max_value
            self.widget.configure(maximum=max_value)
        if increment:
            self.increment(value)
        else:
            self.value = value

    def __call__(self, iterable: Iterable[T], quiet_interrupt: bool = False) -> Iterator[T]:
        bar = self.widget
        for i, item in enumerate(iterable, bar['value'] + 1):
            yield item
            try:
                bar['value'] = i
                bar.update()  # Update is required to handle things like window close events - update_idletasks does not
            except TclError as e:
                if self.window.closed:
                    message = f'Interrupted while processing item {i} / {self.max_value}'
                    if quiet_interrupt:
                        log.debug(message)
                        break
                    raise WindowClosed(message) from e
                raise

    def __enter__(self) -> ProgressBar:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.max_on_exit:
            self.value = self.max_value


class Slider(DisableableMixin, CallbackCommandMixin, Interactive, base_style_layer='slider'):
    widget: Scale
    tk_var: Union[IntVar, DoubleVar]

    def __init__(
        self,
        min_value: float,
        max_value: float,
        default: float = None,
        *,
        interval: float = 1,
        tick_interval: float = None,
        show_values: Bool = True,
        orientation: Orientation = tkc.HORIZONTAL,
        callback: BindTarget = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.min_value = min_value
        self.max_value = max_value
        self.default = default
        self.interval = interval
        self.tick_interval = tick_interval
        self.show_values = show_values
        self.orientation = orientation
        self._callback = callback

    @property
    def value(self) -> float | None:
        try:
            return self.tk_var.get()
        except AttributeError:  # The tk_var has not been initialized yet
            return self.default

    @property
    def style_config(self) -> dict[str, Any]:
        config: dict[str, Any] = {
            'highlightthickness': 0,
            **self.style.get_map(
                'slider', self.style_state, bd='border_width', font='font', fg='fg', bg='bg',
                relief='relief', troughcolor='trough_color',
            ),
            **self._style_config,
        }
        config.setdefault('relief', tkc.FLAT)
        return config

    def _init_widget(self, tk_container: TkContainer):
        min_val, max_val, interval, default = self.min_value, self.max_value, self.interval, self.default
        if _is_int(min_val) and _is_int(max_val) and _is_int(interval):
            self.tk_var = tk_var = IntVar(value=int(default) if default is not None else default)
        else:
            self.tk_var = tk_var = DoubleVar(value=default)

        kwargs: dict[str, Any] = {
            'orient': self.orientation,
            'variable': tk_var,
            'from_': min_val,
            'to_': max_val,
            'resolution': interval,
            'tickinterval': self.tick_interval or interval,
            'takefocus': int(self.allow_focus),
            **self.style_config,
        }
        if (callback := self._callback) is not None:
            kwargs['command'] = self.normalize_callback(callback)
        try:
            kwargs['width'], kwargs['height'] = self.size
        except TypeError:
            pass
        if not self.show_values:
            kwargs['showvalue'] = 0
        if self.disabled:
            kwargs['state'] = 'disabled'

        """
        bigincrement:  digits:  label:  repeatdelay:  repeatinterval:  sliderlength:  sliderrelief:
        """
        self.widget = Scale(tk_container, **kwargs)


def _is_int(value: float) -> bool:
    return floor(value) == ceil(value)
