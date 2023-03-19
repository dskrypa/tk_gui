"""
Tkinter GUI Image View
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, TypeVar, ParamSpec, Iterator

from PIL.Image import registered_extensions

from tk_gui.caching import cached_property
from tk_gui.elements import InfoBar, ScrollableImage, Text, Frame, Button
from tk_gui.elements.table import Table, TableColumn
from tk_gui.elements.menu import MenuProperty, Menu, MenuGroup, MenuItem, CloseWindow
from tk_gui.enums import ImageResizeMode
from tk_gui.event_handling import EventState, event_handler, delayed_event_handler
from tk_gui.geometry import Box
from tk_gui.images.wrapper import ImageWrapper, SourceImage, ResizedImage
from tk_gui.popups.about import AboutPopup
from tk_gui.popups import pick_file_popup
from tk_gui.utils import readable_bytes
from .view import View

if TYPE_CHECKING:
    from tkinter import Event
    from tk_gui.typing import XY, Layout, ImageType, OptInt, ImgResizeMode
    from tk_gui.window import Window

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
    # _SUFFIXES = {'.png', '.jpg', '.jpeg', '.bmp', '.webp', '.svg'}
    _SUFFIXES = set(registered_extensions())

    def __init__(self, path: Path):
        if not path.is_dir():
            raise TypeError(f'Invalid image dir={path.as_posix()!r} - not a directory')
        self.path = path

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}({self.path.as_posix()!r})>'

    @cached_property(block=False)
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

    def get_relative_index(self, path: Path, delta: int = 1) -> OptInt:
        if not delta:
            return None
        try:
            current_index = self.index(path)
        except IndexError:
            return None

        dst_index = current_index + delta
        if delta < 0:
            if current_index == 0:
                return None
            return dst_index if dst_index >= 0 else 0
        elif (last_index := len(self._image_paths) - 1) == current_index:
            return None
        return dst_index if dst_index <= last_index else last_index

    # endregion


class ActiveImage:
    src_image: SourceImage
    image_dir: ImageDir | None = None

    def __init__(
        self, image: ImageType | ImageWrapper, new_size: XY = None, image_dir: ImageDir = None, standalone: bool = False
    ):
        self.src_image = SourceImage.from_image(image)
        self.image = image = self.src_image.as_size(new_size)
        log.debug(f'Initialized ActiveImage with {image=}')
        if standalone:
            self.image_dir = None
        else:
            self.image_dir = ImageDir(self.src_image.path.parent) if image_dir is None else image_dir

    @cached_property(block=False)
    def path(self) -> Path:
        return self.src_image.path

    @cached_property(block=False)
    def file_name(self) -> str:
        if path := self.src_image.path:
            return path.name
        return ''

    def title_parts(self) -> tuple[str, str]:
        prefix = f'{self.file_name} - ' if self.file_name else ''
        suffix = '' if self.image.size_percent == 1 else f' (Zoom: {self.image.size_str})'
        return prefix, suffix

    @cached_property(block=False)
    def _file_info(self) -> tuple[str, str, str]:
        try:
            stat_results = self.src_image.path.stat()
        except AttributeError:
            size_b, mod_time = 0, ''
        else:
            size_b = stat_results.st_size
            mod_time = datetime.fromtimestamp(stat_results.st_mtime).isoformat(' ', 'seconds')
        return mod_time, readable_bytes(size_b), readable_bytes(self.src_image.raw_size)

    @cached_property(block=False)
    def dir_index(self) -> int:
        return self.image_dir.index(self.path) + 1

    def get_info_bar_data(self) -> dict[str, str]:
        image = self.image
        mod_time, file_b, raw_b = self._file_info
        width, height = image.size
        return {
            'size': f'{width} x {height} x {image.bits_per_pixel} BPP',
            'dir_pos': f'{self.dir_index}/{len(self.image_dir)}' if self.image_dir else '1/1',
            'size_pct': f'{image.size_percent:.0%}',
            'size_bytes': f'{file_b} / {raw_b}',
            'mod_time': mod_time,
        }

    def resize(self, size: XY | None, resize_mode: ImgResizeMode = ImageResizeMode.NONE) -> ResizedImage:
        self.image = image = self.src_image.as_size(size, resize_mode=resize_mode)
        return image

    def scale_percent(self, percent: float) -> ResizedImage:
        return self.resize(self.image.scale_percent(percent))


class DirPicker(View, is_popup=True):
    name_key, count_key = 'Folder', 'Image Files'
    submitted = go_to_parent = False

    def __init__(self, image_dir: ImageDir, title: str = None, **kwargs):
        log.debug(f'Initializing {self.__class__.__name__} for {image_dir=}')
        kwargs.setdefault('margins', (0, 0))
        kwargs.setdefault('exit_on_esc', True)
        super().__init__(title=title or 'Browse Subfolders', **kwargs)
        self.image_dir: ImageDir = image_dir

    def get_pre_window_layout(self) -> Layout:
        yield [Text('End of folder reached.  Do you want to continue in another folder?')]
        yield [Text('You are in folder:')]
        path_str = self.image_dir.path.as_posix()
        yield [Text(path_str, use_input_style=True, size=(len(path_str) + 5, 1))]
        buttons = [[Button('Use Folder', key='submit', bind_enter=True, side='t')], [Button('Cancel', side='t')]]
        yield [self.table, Frame(buttons, anchor='n')]
        yield [Text('-> or space', size=(12, 1)), Text('= enter the folder')]
        yield [Text('<-', size=(12, 1)), Text('= previous folder level (..)')]

    def _dirs(self) -> Iterator[str, int | str]:
        for path in sorted(self.image_dir.path.parent.iterdir()):
            if path.is_dir():
                try:
                    yield path.name, len(ImageDir(path))
                except PermissionError:
                    pass

    @cached_property(block=False)
    def table(self) -> Table:
        nk, ck = self.name_key, self.count_key
        rows = [{nk: '.', ck: len(self.image_dir)}, {nk: '..', ck: '?'}, *({nk: n, ck: c} for n, c in self._dirs())]
        columns = (TableColumn(nk, width=rows), TableColumn(ck, anchor_values='e', width=rows))
        return Table(*columns, data=rows, key='table', select_mode='browse', focus=True)

    def get_results(self) -> Path | None:
        results = super().get_results()
        img_dir_path = self.image_dir.path
        if self.go_to_parent:
            return self._go_to_parent(img_dir_path)
        elif not (self.submitted or results['submit']):
            return None
        try:
            dir_name = results['table'][0][self.name_key]
        except (IndexError, KeyError):
            return None
        else:
            if dir_name == '.':
                return img_dir_path
            elif dir_name == '..':
                return self._go_to_parent(img_dir_path)
            return img_dir_path.parent.joinpath(dir_name)

    def _go_to_parent(self, img_dir_path: Path) -> Path | None:  # noqa
        if img_dir_path == img_dir_path.parent:
            log.warning(f'No valid parent directory exists for {img_dir_path.as_posix()}')
            return None
        return DirPicker(ImageDir(img_dir_path.parent)).run()  # noqa

    @event_handler('<space>', '<Right>')
    def handle_submit(self, event: Event):
        self.submitted = True
        self.window.interrupt(event)

    @event_handler('<Left>')
    def handle_parent_dir(self, event: Event):
        self.go_to_parent = True
        self.window.interrupt(event)


class ImageView(View):
    menu = MenuProperty(MenuBar)
    _last_size: XY = (0, 0)
    active_image: ActiveImage
    standalone: bool = False

    def __init__(self, image: ImageType | ImageWrapper, title: str = None, standalone: bool = False, **kwargs):
        kwargs.setdefault('margins', (0, 0))
        kwargs.setdefault('exit_on_esc', True)
        kwargs.setdefault('config_name', self.__class__.__name__)
        super().__init__(title=title or 'Image View', **kwargs)
        self.standalone = standalone
        self.active_image = ActiveImage(SourceImage.from_image(image), standalone=standalone)
        self.window_kwargs['show'] = 2
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

    # def init_window(self):
    #     from tk_gui.event_handling import ClickHighlighter
    #     window = super().init_window()
    #     kwargs = {'window': window, 'show_config': True, 'show_pack_info': True}
    #     ClickHighlighter(level=0, log_event=True, log_event_kwargs=kwargs).register(window)
    #     return window

    # region Layout

    def get_post_window_layout(self) -> Layout:
        if not self.standalone:
            yield [self.menu]
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
        return ScrollableImage(None, size=self._window_box.size, pad=(0, 0), anchor='c', style=style)

    def finalize_window(self) -> Window:
        window = super().finalize_window()
        window.update()
        # By waiting until after the window has been shown before rendering the image, it avoids some initial jitter
        # while tk Configure events are triggered due to the window being rendered.
        self._update(self.active_image.resize(self._window_box.size, ImageResizeMode.FIT_INSIDE), True)
        return window

    # endregion

    # region Image Methods

    def update_active_image(self, image: ImageType | ImageWrapper, image_dir: ImageDir = None):
        src_image = SourceImage.from_image(image)
        self.active_image = ActiveImage(src_image, src_image.fit_inside_size(self._window_box.size), image_dir)
        self._update(self.active_image.image)

    def resize_image(self, size: XY | None, resize_mode: ImgResizeMode = ImageResizeMode.NONE):
        self._update(self.active_image.resize(size, resize_mode))

    # endregion

    def _update(self, image: ResizedImage, frame: bool = False):
        self.gui_image.update(image, image.size)
        self.window.set_title(self.title)
        self.info_bar.update(self.active_image.get_info_bar_data())
        if frame:
            self._update_frame_size(self.window.true_size)

    def _update_frame_size(self, size: XY):
        win_w, win_h = size
        self._last_size = size
        frame_height = win_h - self._height_offset
        # log.debug(f'Using {frame_height=} from {win_h=}, {self._height_offset=}')
        self.gui_image.update_frame_size(win_w, frame_height)

    # region Event Handling

    @event_handler('SIZE_CHANGED')
    def handle_size_changed(self, event: Event, size: XY):
        if (last_size := self._last_size) == size:
            return
        grew = Box.from_size_and_pos(*last_size).area < Box.from_size_and_pos(*size).area
        self._last_size = size
        self._update_frame_size(size)
        if grew and self.active_image.image.size_percent < 1:
            self.window.update_idle_tasks()
            self.resize_image(size, ImageResizeMode.FIT_INSIDE)

    # endregion

    # region Zoom

    @event_handler('<Control-MouseWheel>')
    @delayed_event_handler(delay_ms=75)
    def handle_shift_scroll(self, event: Event):
        if event.num == 5 or event.delta < 0:  # Zoom out
            self._zoom_image(0.9)  # TODO: Use more consistent steps?
        elif event.num == 4 or event.delta > 0:  # Zoom in
            self._zoom_image(1.1)

    def _zoom_image(self, percent: float):
        self._update(self.active_image.scale_percent(percent))
        # TODO: Add way to grab image to drag the current view around

    @event_handler('<Home>', '<End>', '<Prior>', '<Next>')
    def handle_zoom_key_press(self, event: Event):
        # TODO: Add menu button to do the same?  + to set to a specific value?
        if (key := event.keysym) == 'Home':
            self.resize_image(None)
        elif key == 'End':
            self.resize_image(self._window_box.size, ImageResizeMode.FILL)
        elif key in ('Prior', 'Next'):  # PageUp / PageDown
            self._zoom_image(1.1 if key == 'Prior' else 0.9)

    # endregion

    # region File Change / Directory Traversal

    @menu['File']['Open'].callback
    def open_file(self, event):
        if path := pick_file_popup(self.active_image.src_image.path.parent, title='Pick Image', parent=self.window):
            self.update_active_image(path)

    @event_handler('<Left>', '<Control-Left>', '<Right>', '<Control-Right>')
    def handle_arrow_key_press(self, event: Event):
        if (image_dir := self.active_image.image_dir) is None:
            return
        # TODO: If zoomed in, increment scroll instead?  + add Up/Down handlers for this?
        delta = 5 if event.state & EventState.Control else 1
        if event.keysym == 'Left':
            delta = -delta
        if (index := image_dir.get_relative_index(self.active_image.path, delta)) is not None:
            self.update_active_image(image_dir[index], image_dir)
        else:
            path: Path | None = DirPicker(image_dir).run()  # noqa
            log.debug(f'Selected {path=}')
            if not path:
                return
            new_img_dir = ImageDir(path)
            try:
                img_path = new_img_dir[0]
            except IndexError:
                log.warning(f'Selected directory={path.as_posix()!r} has no images')
            else:
                log.debug(f'Moving to new directory={path.as_posix()!r}')
                self.update_active_image(img_path, new_img_dir)

    # endregion
