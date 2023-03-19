"""
Tkinter GUI Image View
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, TypeVar, ParamSpec, Iterator

from tk_gui.caching import cached_property
from tk_gui.elements import InfoBar, ScrollableImage
from tk_gui.elements.menu import MenuProperty, Menu, MenuGroup, MenuItem, CloseWindow
from tk_gui.event_handling import event_handler, delayed_event_handler
from tk_gui.geometry import Box
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

    def __init__(self, image: ImageType | ImageWrapper, new_size: XY = None, image_dir: ImageDir = None):
        self.src_image = SourceImage.from_image(image)
        self.image = image = self.src_image.as_size(new_size)
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
        self.active_image = ActiveImage(SourceImage.from_image(image))
        self.image_dir = self.active_image.image_dir
        if size := self._new_window_size():
            self.window_kwargs['size'] = size

    # region Size

    def _new_window_size(self) -> XY | None:
        if self.config.size or self.window_kwargs.get('size'):
            return None

        img_box = self.active_image.src_image.box.with_size_offset(60)
        if monitor := self.get_monitor():
            work_area = monitor.work_area.with_size_offset(-60)
            if not img_box.fits_inside(work_area):
                return img_box.fit_inside_size(work_area.size)

        return img_box.size

    @cached_property
    def _height_offset(self) -> int:
        style = self.window.style
        # footer_req_height = self.info_bar.widget.winfo_reqheight()  # Usually 22
        footer_bd = style.input.border_width.disabled or 1
        footer_req_height = style.char_height() + (2 * footer_bd) + 4
        # scroll_x_height = self.gui_image.widget.scroll_bar_x.winfo_reqheight()  # Usually 12->15 / 14->17
        scroll = style.get_map('scroll', aw='arrow_width', bw='bar_width', bd='border_width')
        scroll_width = max(scroll.get('aw', 12), scroll.get('bw', 12))
        scroll_x_height = scroll_width + (2 * scroll.get('bd', 1)) + 1
        # log.debug(f'{footer_req_height=}, {scroll_x_height=}')
        return footer_req_height + scroll_x_height

    @cached_property
    def _width_offset(self) -> int:
        style = self.window.style
        # scroll_y_width = self.gui_image.widget.scroll_bar_y.winfo_reqwidth()  # usually 12->15 / 14->17
        scroll = style.get_map('scroll', aw='arrow_width', bw='bar_width', bd='border_width')
        scroll_width = max(scroll.get('aw', 12), scroll.get('bw', 12))
        scroll_y_width = scroll_width + (2 * scroll.get('bd', 1)) + 1
        return scroll_y_width

    @property
    def _window_box(self) -> Box:
        win_box = Box.from_pos_and_size(0, 0, *self.window.true_size)
        return win_box.with_size_offset((-self._width_offset, -self._height_offset))

    # endregion

    # region Title

    @property
    def title(self) -> str:
        try:
            prefix, suffix = self.active_image.title_parts()
        except AttributeError:  # During init with no config_name
            return self._title
        else:
            return f'{prefix}{self._title}{suffix})'

    @title.setter
    def title(self, value: str):
        self._title = value

    # endregion

    def __repr__(self) -> str:
        src_image = self.active_image.src_image
        return f'<{self.__class__.__name__}[title={self._title!r}, {src_image=}]>'

    def init_window(self):
        from tk_gui.event_handling import ClickHighlighter
        window = super().init_window()
        kwargs = {'window': window, 'show_config': True, 'show_pack_info': True}
        ClickHighlighter(level=0, log_event=True, log_event_kwargs=kwargs).register(window)
        return window

    # region Layout

    def get_pre_window_layout(self) -> Layout:
        yield [self.menu]

    def get_post_window_layout(self) -> Layout:
        yield [self.gui_image]
        yield [self.info_bar]

    @cached_property
    def info_bar(self) -> InfoBar:
        sizes = {'size': (20, 1), 'dir_pos': (8, 1), 'size_pct': (6, 1), 'size_bytes': (20, 1), 'mod_time': (20, 1)}
        data = {key: (val, sizes[key]) for key, val in self.active_image.get_info_bar_data().items()}
        return InfoBar.from_dict(data)

    @cached_property
    def gui_image(self) -> ScrollableImage:
        style = self.window.style.sub_style(bg='#000000', border_width=0)
        win_box = self._window_box
        src_image = self.active_image.src_image
        fit_size = src_image.box.fit_inside_size(win_box.size)
        image = self.active_image.resize(fit_size)
        # TODO: There's still some visible initial image position jitter where it shifts up and down 1-2x, which may
        #  also occur to a lesser degree when switching to another image, but nowhere near as noticeable.
        return ScrollableImage(
            image, size=win_box.size, pad=(0, 0), anchor='c', side='t', fill='both', expand=True, style=style
        )

    # endregion

    def _update(self, image: ResizedImage):
        self.gui_image.update(image, image.size)
        self.window.set_title(self.title)
        self.info_bar.update(self.active_image.get_info_bar_data())
        self._update_size()

    def _update_active_image(self, image: ImageType | ImageWrapper, image_dir: ImageDir = None):
        src_image = SourceImage.from_image(image)
        self.active_image = ActiveImage(src_image, src_image.box.fit_inside_size(self._window_box.size), image_dir)
        self.image_dir = self.active_image.image_dir
        self._update(self.active_image.image)

    def _update_size(self, size: XY = None):
        try:
            win_w, win_h = size
        except TypeError:
            win_w, win_h = self.window.true_size
            # win_w, win_h = self._window_box.size  # Note: Using this resulted in losing the info bar

        frame_height = win_h - self._height_offset
        log.debug(f'Using {frame_height=} from {win_h=}, {self._height_offset=}')
        self.gui_image.widget.resize(win_w, frame_height)

    # region Event Handling

    @cached_property
    def _widget(self):
        # Needed for delayed_event_handler
        return self.window.root

    @event_handler('SIZE_CHANGED')
    def handle_size_changed(self, event: Event, size: XY):
        # TODO: If image is <100% and the window is expanded to be able to show it closer to full size, resize image
        if self._last_size != size:
            self._last_size = size
            self._update_size(size)

    # endregion

    # region Zoom

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

    # endregion

    # region File Change / Directory Traversal

    @menu['File']['Open'].callback
    def open_file(self, event):
        if path := pick_file_popup(self.active_image.src_image.path.parent, title='Pick Image', parent=self.window):
            self._update_active_image(path)

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
