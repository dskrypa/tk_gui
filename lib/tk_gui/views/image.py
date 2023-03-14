"""
Tkinter GUI Image View
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, TypeVar, ParamSpec, Iterator

from tk_gui.caching import cached_property
from tk_gui.elements import Image, Text, BasicRowFrame, ScrollFrame, SizeGrip
from tk_gui.elements.menu import MenuProperty, Menu, MenuGroup, MenuItem, CloseWindow
from tk_gui.event_handling import event_handler, delayed_event_handler
from tk_gui.images.wrapper import ImageWrapper, SourceImage, ResizedImage
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
        # TODO: Top/bottom spacers, or implement something using Canvas's create_image properly...
        yield [*self.spacers, self.__image]

    def update_spacer_width(self, width: int):
        left, right = self.spacers
        left.resize(width, 1)
        right.resize(width, 1)


class InfoBar(BasicRowFrame):
    element_map: dict[str, Text]

    def __init__(self, data: dict[str, str], side='b', fill='both', pad=(0, 0), **kwargs):
        self.element_map = element_map = self._init_element_map(data)
        super().__init__([*element_map.values(), SizeGrip(pad=(0, 0))], side=side, fill=fill, pad=pad, **kwargs)

    def _init_element_map(self, data: dict[str, str]) -> dict[str, Text]:  # noqa
        kwargs = {'use_input_style': True, 'justify': 'c', 'pad': (1, 0)}
        # TODO: Better auto-sizing of these fields
        return {
            'size': Text(data['size'], size=(20, 1), **kwargs),
            'dir_pos': Text(data['dir_pos'], size=(8, 1), **kwargs),
            'size_pct': Text(data['size_pct'], size=(6, 1), **kwargs),
            'size_bytes': Text(data['size_bytes'], size=(20, 1), **kwargs),
            'mod_time': Text(data['mod_time'], size=(20, 1), **kwargs),
        }

    def update_fields(self, data: dict[str, str]):
        element_map = self.element_map
        for key, val in data.items():
            element_map[key].update(val)


class ImageDir:
    _SUFFIXES = {'.png', '.jpg', '.jpeg', '.bmp', '.webp', '.svg'}  # TODO: Support more; support gif, etc

    def __init__(self, path: Path):
        if not path.is_dir():
            raise TypeError(f'Invalid image dir={path.as_posix()!r} - not a directory')
        self.path = path

    @cached_property
    def _image_paths(self) -> list[Path]:
        ok_suffixes = self._SUFFIXES
        image_paths = [p for p in self.path.iterdir() if p.is_file() and p.suffix.lower() in ok_suffixes]
        image_paths.sort(key=lambda p: p.name.lower())
        return image_paths

    # region Container Methods

    def __len__(self) -> int:
        return len(self._image_paths)

    def __getitem__(self, item: int) -> Path:
        return self._image_paths[item]

    def __iter__(self) -> Iterator[Path]:
        yield from self._image_paths

    # endregion

    # region Index Methods

    def index(self, path: Path) -> int:
        return self._image_paths.index(path)

    def get_prev_index(self, path: Path) -> int | None:
        try:
            index = self.index(path) - 1
        except IndexError:
            return None
        return None if index < 0 else index

    def get_next_index(self, path: Path) -> int | None:
        try:
            index = self.index(path) + 1
        except IndexError:
            return None
        return None if index >= len(self._image_paths) else index

    # endregion


class ActiveImage:
    src_image: SourceImage
    image_dir: ImageDir = None

    def __init__(self, image: ImageType | ImageWrapper, window_size: XY = None, image_dir: ImageDir = None):
        self.src_image = SourceImage.from_image(image)
        self.image = image = self.src_image.as_size(window_size)
        log.debug(f'Initialized ActiveImage with {image=}')
        if image_dir is None:
            self.image_dir = ImageDir(self.src_image.path.parent)
        else:
            self.image_dir = image_dir

    @cached_property
    def path(self) -> Path:
        return self.src_image.path

    @cached_property
    def file_name(self) -> str:
        if path := self.src_image.path:
            return path.name
        return ''

    def title_parts(self) -> tuple[str, str]:
        prefix = f'{self.file_name} - ' if self.file_name else ''
        suffix = '' if self.image.size_percent == 1 else f' (Zoom: {self.image.size_str})'
        return prefix, suffix

    @cached_property
    def _file_info(self) -> tuple[str, str, str]:
        try:
            stat_results = self.src_image.path.stat()
        except AttributeError:
            size_b, mod_time = 0, ''
        else:
            size_b = stat_results.st_size
            mod_time = datetime.fromtimestamp(stat_results.st_mtime).isoformat(' ', 'seconds')
        return mod_time, readable_bytes(size_b), readable_bytes(self.src_image.raw_size)

    @cached_property
    def dir_index(self) -> int:
        return self.image_dir.index(self.path) + 1

    def get_info_bar_data(self) -> dict[str, str]:
        image = self.image
        mod_time, file_b, raw_b = self._file_info
        return {
            'size': f'{image.size_str} x {image.bits_per_pixel} BPP',
            'dir_pos': f'{self.dir_index}/{len(self.image_dir)}',
            'size_pct': f'{image.size_percent:.0%}',
            'size_bytes': f'{file_b} / {raw_b}',
            'mod_time': mod_time,
        }

    def resize(self, size: XY) -> ResizedImage:
        self.image = image = self.src_image.as_size(size)
        return image

    def scale_percent(self, percent: float) -> ResizedImage:
        return self.resize(self.image.scale_percent(percent))


class ImageView(View):
    menu = MenuProperty(MenuBar)
    _last_size: XY = None
    active_image: ActiveImage
    image_dir: ImageDir

    def __init__(self, image: ImageType | ImageWrapper, title: str = None, **kwargs):
        kwargs.setdefault('margins', (0, 0))
        kwargs.setdefault('exit_on_esc', True)
        kwargs.setdefault('config_name', self.__class__.__name__)
        super().__init__(title=title or 'Image View', **kwargs)
        self._set_active_image(image)

    def _set_active_image(self, image: ImageType | ImageWrapper, image_dir: ImageDir = None):
        src_image = SourceImage.from_image(image)
        self.active_image = ActiveImage(src_image, self._init_size(src_image), image_dir)
        self.image_dir = self.active_image.image_dir

    # region Title

    @property
    def title(self) -> str:
        prefix, suffix = self.active_image.title_parts()
        return f'{prefix}{self._title}{suffix})'

    @title.setter
    def title(self, value: str):
        self._title = value

    # endregion

    def __repr__(self) -> str:
        src_image = self.active_image.src_image
        return f'<{self.__class__.__name__}[title={self._title!r}, {src_image=}]>'

    # def init_window(self):
    #     from tk_gui.event_handling import ClickHighlighter
    #     window = super().init_window()
    #     kwargs = {'window': window, 'show_config': True, 'show_pack_info': True}
    #     ClickHighlighter(level=0, log_event=True, log_event_kwargs=kwargs).register(window)
    #     return window

    # region Layout

    def get_pre_window_layout(self) -> Layout:
        yield [self.menu]

    def get_post_window_layout(self) -> Layout:
        yield [self.image_frame]
        yield [self.info_bar]

    @cached_property
    def info_bar(self) -> InfoBar:
        return InfoBar(self.active_image.get_info_bar_data())

    @cached_property
    def image_frame(self) -> ImageScrollFrame:
        return ImageScrollFrame(self.gui_image)

    @cached_property
    def gui_image(self) -> Image:
        image = self.active_image.resize(self._init_size(self.active_image.src_image))
        return Image(image, size=image.size, pad=(0, 0))

    def _init_size(self, src_image: SourceImage) -> XY:
        src_w, src_h = src_image.size
        try:
            win_w, win_h = self.window.true_size
        except AttributeError:  # Initial image
            pass
        else:
            src_w, src_h = min(win_w, src_w), min(win_h, src_h)
        if monitor := self.get_monitor():
            mon_w, mon_h = monitor.work_area.size
            # log.debug(f'_init_size: monitor size={(mon_w, mon_h)}')
            return min(mon_w - 60, src_w), min(mon_h - 60, src_h)
        return src_w, src_h

    # endregion

    def _update(self, image: ResizedImage):
        self.gui_image.update(image, image.size)
        self.window.set_title(self.title)
        self.info_bar.update_fields(self.active_image.get_info_bar_data())
        self._update_size()

    def _update_active_image(self, image: ImageType | ImageWrapper, image_dir: ImageDir = None):
        # TODO: Center and avoid over-zoom on new images
        # TODO: Horizontal scroll is not always registering correctly
        # TODO: Shrink to fit if larger than current window
        self._set_active_image(image, image_dir)
        # self._update(self.active_image.resize((self._init_size()))
        self._update(self.active_image.image)

    def _update_size(self, size: XY = None):
        # TODO: Resize creep on init sometimes
        try:
            win_w, win_h = size
        except TypeError:
            win_w, win_h = self.window.true_size
        to_fill = win_w - self.active_image.image.width - self._width_offset
        if (spacer_w := to_fill // 2) < 5:
            spacer_w = 1
        # log.debug(f'Using spacer {spc_w=} from {win_w=}, {self.image.width=}, {to_fill=}')
        self.image_frame.update_spacer_width(spacer_w)
        self.image_frame.resize_scroll_region((win_w, win_h - self._height_offset))

    # region Event Handling

    @menu['File']['Open'].callback
    def open_file(self, event):
        if path := pick_file_popup(self.active_image.src_image.path.parent, title='Pick Image', parent=self.window):
            self._update_active_image(path)

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
        # Needed for delayed_event_handler
        return self.window._root

    @event_handler('SIZE_CHANGED')
    def handle_size_changed(self, event: Event, size: XY):
        if self._last_size != size:
            self._last_size = size
            self._update_size(size)

    @event_handler('<Control-MouseWheel>')
    @delayed_event_handler(delay_ms=75, widget_attr='_widget')
    def handle_shift_scroll(self, event: Event):
        log.debug(f'handle_shift_scroll: {event=}')
        if event.num == 5 or event.delta < 0:  # Zoom out
            self._zoom_image(0.9)  # TODO: Use more consistent steps
        elif event.num == 4 or event.delta > 0:  # Zoom in
            self._zoom_image(1.1)

    def _zoom_image(self, percent: float):
        self._update(self.active_image.scale_percent(percent))
        # TODO: Add shortcut to reset zoom to 100%, to fit window, to a specified value, etc
        # TODO: Add way to grab image to drag the current view around

    @event_handler('<Left>')
    def handle_left_arrow(self, event: Event):
        image_dir = self.image_dir
        if (index := image_dir.get_prev_index(self.active_image.path)) is not None:
            self._update_active_image(image_dir[index], image_dir)
        # TODO: Popup dialog to pick next dir or wrap around upon hitting either end

    @event_handler('<Right>')
    def handle_right_arrow(self, event: Event):
        # TODO: Add support for ctrl+left/right to jump by (up to) 5 instead of 1
        image_dir = self.image_dir
        if (index := image_dir.get_next_index(self.active_image.path)) is not None:
            self._update_active_image(image_dir[index], image_dir)

    # endregion
