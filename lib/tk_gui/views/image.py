"""
Tkinter GUI Image View
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, TypeVar, ParamSpec

from tk_gui.caching import cached_property
from tk_gui.elements import Image, Text, BasicRowFrame, ScrollFrame, SizeGrip
from tk_gui.elements.menu import MenuProperty, Menu, MenuGroup, MenuItem, CloseWindow
from tk_gui.event_handling import event_handler, delayed_event_handler
from tk_gui.images.wrapper import ImageWrapper, SourceImage
from tk_gui.popups.about import AboutPopup
from tk_gui.popups import pick_file_popup
from tk_gui.utils import readable_bytes
from .view import View

if TYPE_CHECKING:
    from tkinter import Event
    from ..typing import XY, Layout, ImageType

__all__ = ['ImageView']
log = logging.getLogger(__name__)

P = ParamSpec('P')
T = TypeVar('T')


class MenuBar(Menu):
    with MenuGroup('File'):
        MenuItem('Open')
        CloseWindow()
    with MenuGroup('Help'):
        MenuItem('About', AboutPopup)


class ImageScrollFrame(ScrollFrame):
    def __init__(self, image: Image, **kwargs):
        kwargs.setdefault('pad', (0, 0))
        kwargs.setdefault('anchor', 'c')
        kwargs.setdefault('side', 't')
        kwargs.setdefault('scroll_y', True)
        kwargs.setdefault('scroll_x', True)
        kwargs.setdefault('scroll_y_amount', 1)
        kwargs.setdefault('style', {'bg': '#000000', 'border_width': 0})
        super().__init__(**kwargs)
        self.__image = image

    @cached_property
    def spacers(self) -> tuple[Image, Image]:
        kwargs = {'style': self.style, 'size': (1, 1), 'pad': (0, 0), 'keep_ratio': False}
        return Image(None, side='left', **kwargs), Image(None, side='right', **kwargs)

    def get_custom_layout(self) -> Layout:
        yield [*self.spacers, self.__image]

    def update_spacer_width(self, width: int):
        left, right = self.spacers
        left.resize(width, 1)
        right.resize(width, 1)


class ImageView(View):
    menu = MenuProperty(MenuBar)
    _last_size: XY = None
    src_image: SourceImage

    def __init__(self, image: ImageType | ImageWrapper, title: str = None, **kwargs):
        kwargs.setdefault('margins', (0, 0))
        kwargs.setdefault('exit_on_esc', True)
        # kwargs.setdefault('config_name', self.__class__.__name__)
        super().__init__(title=title or 'Image View', **kwargs)
        self.src_image = SourceImage.from_image(image)
        self.image = self.src_image

    # region Title

    @property
    def title(self) -> str:
        try:
            prefix = f'{self.src_image.path.name} - '
        except AttributeError:
            prefix = ''
        suffix = '' if self.image.size_percent == 1 else f' (Zoom: {self.image.size_str})'
        return f'{prefix}{self._title}{suffix})'

    @title.setter
    def title(self, value: str):
        self._title = value

    # endregion

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}[title={self._title!r}, src_image={self.src_image!r}]>'

    @property
    def image_name(self) -> str:
        if path := self.src_image.path:
            return path.name
        return ''

    # def init_window(self):
    #     from tk_gui.event_handling import ClickHighlighter
    #     window = super().init_window()
    #     kwargs = {'window': window, 'show_config': True, 'show_pack_info': True}
    #     ClickHighlighter(level=0, log_event=True, log_event_kwargs=kwargs).register(window)
    #     return window

    def get_pre_window_layout(self) -> Layout:
        yield [self.menu]
        yield [self.image_frame]
        yield [self.info_bar]

    def get_info_bar_data(self) -> dict[str, str]:
        image = self.image
        try:
            stat_results = self.src_image.path.stat()
        except AttributeError:
            size_b, mod_time = 0, ''
        else:
            size_b = stat_results.st_size
            mod_time = datetime.fromtimestamp(stat_results.st_mtime).isoformat(' ', 'seconds')

        file_b, raw_b = readable_bytes(size_b), readable_bytes(image.raw_size)
        return {
            'size': f'{image.size_str} x {image.bits_per_pixel} BPP',
            'dir_pos': '1/1',  # TODO
            'size_pct': f'{image.size_percent:.0%}',
            'size_bytes': f'{file_b} / {raw_b}',
            'mod_time': mod_time,
        }

    @cached_property
    def info_bar_elements(self) -> dict[str, Text]:
        data = self.get_info_bar_data()
        kwargs = {'use_input_style': True, 'justify': 'c', 'pad': (1, 0)}
        # TODO: Better auto-sizing of these fields
        return {
            'size': Text(data['size'], size=(20, 1), **kwargs),
            'dir_pos': Text(data['dir_pos'], size=(8, 1), **kwargs),
            'size_pct': Text(data['size_pct'], size=(6, 1), **kwargs),
            'size_bytes': Text(data['size_bytes'], size=(20, 1), **kwargs),
            'mod_time': Text(data['mod_time'], size=(20, 1), **kwargs),
        }

    @cached_property
    def info_bar(self) -> BasicRowFrame:
        pad = (0, 0)
        return BasicRowFrame([*self.info_bar_elements.values(), SizeGrip(pad=pad)], side='b', fill='both', pad=pad)

    @cached_property
    def image_frame(self) -> ImageScrollFrame:
        return ImageScrollFrame(self.gui_image)

    @cached_property
    def gui_image(self) -> Image:
        init_size = self._init_size()
        src = self.src_image
        if src.pil_image:
            log.debug(f'{self}: Using {init_size=} to display image={src!r} with {src.format=} mime={src.mime_type!r}')
        self.image = image = src.as_size(init_size)
        return Image(image, size=image.size, pad=(0, 0))

    def _init_size(self) -> XY:
        src_w, src_h = self.src_image.size
        if monitor := self.get_monitor():
            mon_w, mon_h = monitor.work_area.size
            # log.debug(f'_init_size: monitor size={(mon_w, mon_h)}')
            return min(mon_w - 60, src_w), min(mon_h - 60, src_h)
        return src_w, src_h

    @menu['File']['Open'].callback
    def open_file(self, event):
        if path := pick_file_popup(self.src_image.path.parent, title='Pick Image', parent=self.window):
            self.src_image = src_image = SourceImage(path)
            init_size = self._init_size()
            self.image = image = src_image.as_size(init_size)
            self.gui_image.update(image, image.size)
            self.window.set_title(self.title)
            for key, val in self.get_info_bar_data().items():
                self.info_bar_elements[key].update(val)

    @cached_property
    def _height_offset(self) -> int:
        footer_req_height = self.info_bar.widget.winfo_reqheight()
        scroll_x_height = self.image_frame.widget.scroll_bar_x.winfo_reqheight()
        return footer_req_height + scroll_x_height

    @cached_property
    def _width_offset(self) -> int:
        scroll_y_width = self.image_frame.widget.scroll_bar_y.winfo_reqwidth()
        return scroll_y_width

    @cached_property
    def _widget(self):
        return self.window._root

    @event_handler('SIZE_CHANGED')
    def handle_size_changed(self, event: Event, size: XY):
        if self._last_size != size:
            self._last_size = size
            win_w, win_h = size
            to_fill = win_w - self.image.width - self._width_offset
            if (spacer_w := to_fill // 2) < 5:
                spacer_w = 1
            # log.debug(f'Using spacer {spc_w=} from {win_w=}, {self.image.width=}, {to_fill=}')
            self.image_frame.update_spacer_width(spacer_w)
            self.image_frame.update_scroll_region((win_w, win_h - self._height_offset))

    @event_handler('<Control-MouseWheel>')
    @delayed_event_handler(delay_ms=75, widget_attr='_widget')
    def handle_shift_scroll(self, event: Event):
        log.debug(f'handle_shift_scroll: {event=}')
        if event.num == 5 or event.delta < 0:  # Zoom out
            self._zoom_image(0.9)  # TODO: Use more consistent steps
        elif event.num == 4 or event.delta > 0:  # Zoom in
            self._zoom_image(1.1)

    def _zoom_image(self, percent: float):
        self.image = image = self.src_image.as_size(self.image.scale_percent(percent))
        self.gui_image.update(image, image.size)
        self.window.set_title(self.title)
        for key, val in self.get_info_bar_data().items():
            self.info_bar_elements[key].update(val)
