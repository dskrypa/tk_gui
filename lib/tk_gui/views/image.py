"""
Tkinter GUI Image View
"""

from __future__ import annotations

import logging
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Union, TypeVar, ParamSpec, Iterator

from PIL.Image import registered_extensions

from tk_gui.caching import cached_property
from tk_gui.elements import InfoBar, ScrollableImage, Text, Frame, Button
from tk_gui.elements.trees import Table, Column
from tk_gui.elements.menu import MenuProperty, Menu, MenuGroup, MenuItem, CloseWindow
from tk_gui.enums import MissingMixin, ImageResizeMode
from tk_gui.event_handling import EventState, event_handler, delayed_event_handler
from tk_gui.geometry import Box
from tk_gui.images.wrapper import ImageWrapper, SourceImage, ResizedImage
from tk_gui.popups.about import AboutPopup
from tk_gui.popups.common import popup_warning
from tk_gui.popups.paths import PickFile
from tk_gui.utils import readable_bytes
from .view import View

if TYPE_CHECKING:
    from tkinter import Event
    from tk_gui.typing import XY, Layout, ImageType, OptInt, ImgResizeMode, PathLike  # noqa
    from tk_gui.window import Window

__all__ = ['ImageView']
log = logging.getLogger(__name__)

P = ParamSpec('P')
T = TypeVar('T')
AnyImage = Union['ImageType', ImageWrapper]


# region Directories


class ImageDir:
    # _SUFFIXES = {'.png', '.jpg', '.jpeg', '.bmp', '.webp', '.svg'}
    _SUFFIXES = set(registered_extensions()) - {'.pdf'}
    path: Path

    def __new__(cls, image_dir: Path | ImageDir):
        if isinstance(image_dir, cls):
            return image_dir
        return super().__new__(cls)

    def __init__(self, image_dir: Path | ImageDir):
        if hasattr(self, 'path'):
            return
        path = image_dir.path if isinstance(image_dir, ImageDir) else image_dir
        if not path.is_dir():
            raise TypeError(f'Invalid image dir={path.as_posix()!r} - not a directory')
        self.path = path

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}[images={len(self.image_paths)}]({self.path.as_posix()!r})>'

    @cached_property(block=False)
    def _split_contents(self) -> tuple[list[Path], list[Path]]:
        ok_suffixes = self._SUFFIXES
        image_paths, sub_dirs = [], []
        for p in self.path.iterdir():
            if p.is_file():
                if p.suffix.lower() in ok_suffixes:
                    image_paths.append(p)
            elif p.is_dir():
                sub_dirs.append(p)
        return image_paths, sub_dirs

    @cached_property(block=False)
    def image_paths(self) -> list[Path]:
        image_paths = self._split_contents[0]
        image_paths.sort(key=lambda p: p.name.lower())
        return image_paths

    @cached_property(block=False)
    def sub_dirs(self) -> list[Path]:
        return self._split_contents[1]

    # region Container Methods

    def __len__(self) -> int:
        return len(self.image_paths)

    def __getitem__(self, item: int) -> Path:
        return self.image_paths[item]

    def __iter__(self) -> Iterator[Path]:
        yield from self.image_paths

    def __hash__(self) -> int:
        return hash(self.__class__) ^ hash(self.path)

    def __eq__(self, other: ImageDir) -> bool:
        try:
            return self.path == other.path
        except AttributeError:
            return False

    def __lt__(self, other: ImageDir) -> bool:
        try:
            return self.path < other.path
        except AttributeError:
            return False

    # endregion

    # region Index Methods

    def index(self, path: Path) -> int:
        return self.image_paths.index(path)

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
        elif (last_index := len(self.image_paths) - 1) == current_index:
            return None
        return dst_index if dst_index <= last_index else last_index

    # endregion


class EmptyImageDirError(Exception):
    def __init__(self, path: Path):
        self.path = path

    def __str__(self) -> str:
        return f'Directory has no images or subdirectories: {self.path.as_posix()}'


class DirPicker(View, is_popup=True):
    name_key, count_key = 'Folder', 'Image Files'
    submitted = go_to_parent = False

    def __init__(
        self, image_dir: ImageDir, title: str = None, last_dir: ImageDir = None, init_dir: ImageDir = None, **kwargs
    ):
        log.debug(f'Initializing {self.__class__.__name__} for {image_dir=}')
        kwargs.setdefault('margins', (0, 0))
        kwargs.setdefault('exit_on_esc', True)
        super().__init__(title=title or 'Browse Subfolders', **kwargs)
        self.image_dir: ImageDir = image_dir
        self.last_dir: ImageDir | None = last_dir
        self.init_dir = image_dir if init_dir is None else init_dir

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
        for path in sorted(self.image_dir.path.iterdir()):
            if path.is_dir():
                try:
                    yield path.name, len(ImageDir(path))
                except PermissionError:
                    pass

    @cached_property(block=False)
    def table(self) -> Table:
        nk, ck = self.name_key, self.count_key
        rows = [{nk: '..', ck: '?'}, {nk: '.', ck: len(self.image_dir)}, *({nk: n, ck: c} for n, c in self._dirs())]
        columns = (Column(nk, width=rows), Column(ck, anchor_values='e', width=rows))
        if (last_dir := self.last_dir) and last_dir.path != self.image_dir.path.parent:
            focus_row = (nk, last_dir.path.name)
        else:
            focus_row = (nk, '.')
        return Table(*columns, data=rows, key='table', select_mode='browse', focus=True, init_focus_row=focus_row)

    def get_path_selection(self, results=None) -> Path | None:
        if self.go_to_parent:
            dir_name = '..'
        else:
            table = self.window['table'].value if results is None else results['table']
            try:
                dir_name = table[0][self.name_key]
            except (IndexError, KeyError):
                return None

        log.debug(f'Selected {dir_name=}')
        img_dir_path = self.image_dir.path
        if dir_name == '.':
            return img_dir_path
        elif dir_name == '..':
            if img_dir_path == img_dir_path.parent:
                popup_warning(f'No valid parent directory exists for {img_dir_path.as_posix()}')
                log.warning(f'No valid parent directory exists for {img_dir_path.as_posix()}')
                return None
            return img_dir_path.parent
        else:
            return img_dir_path.joinpath(dir_name)

    def run(self, take_focus: bool = True):
        with self.finalize_window()(take_focus=take_focus) as window:
            while True:
                window.run()
                try:
                    results = self.get_results()
                except EmptyImageDirError as e:
                    error_msg = str(e)
                    log.warning(error_msg)
                    popup_warning(error_msg)
                    # TODO: Up/down arrows don't work after this, but left/right still works
                else:
                    break

            self.cleanup()
            return results

    def get_results(self) -> Path | ImageDir | None:
        results = super().get_results()
        chdir, submitted = self.submitted, results['submit']
        if not (chdir or submitted):
            # log.debug('No submission')
            return None
        elif not (next_path := self.get_path_selection(results)):
            # log.debug('No selection')
            return None
        elif next_path == self.image_dir.path:
            # log.debug('Same path')
            if not self.image_dir and self.image_dir != self.init_dir:
                raise EmptyImageDirError(next_path)
            return next_path
        elif (img_dir := ImageDir(next_path)) or img_dir.sub_dirs or chdir:
            # log.debug(f'Moving into {img_dir=}' if chdir else f'Returning {img_dir=}')
            return self._change_dir(img_dir) if chdir else img_dir
        else:
            raise EmptyImageDirError(next_path)

    def _change_dir(self, img_dir: Path | ImageDir) -> Path | None:  # noqa
        self.window.hide()
        # TODO: Update table in-place instead
        return DirPicker(ImageDir(img_dir), last_dir=self.image_dir, init_dir=self.init_dir).run()  # noqa

    @event_handler('<space>', '<Right>', '<Left>', '<Double-Button-1>')
    def handle_chdir_key(self, event: Event):
        self.go_to_parent = event.keysym == 'Left'
        self.submitted = True
        self.window.interrupt(event)


# endregion


# region Image Helpers


class InfoLoc(MissingMixin, Enum):
    NONE = 'none'
    TITLE_BAR = 'title_bar'
    FOOTER = 'footer'


class MenuBar(Menu):
    with MenuGroup('File'):
        MenuItem('Open')
        CloseWindow()
    with MenuGroup('Help'):
        MenuItem('About', AboutPopup)


class ActiveImage:
    src_image: SourceImage
    image_dir: ImageDir | None = None

    def __init__(self, image: AnyImage, new_size: XY = None, image_dir: ImageDir = None, standalone: bool = False):
        self.src_image = SourceImage.from_image(image)
        self.image = image = self.src_image.as_size(new_size)
        log.debug(f'Initialized ActiveImage with {image=}')
        if not standalone:
            self.image_dir = ImageDir(self.src_image.path.parent) if image_dir is None else image_dir

    @cached_property(block=False)
    def path(self) -> Path:
        return self.src_image.path

    @cached_property(block=False)
    def file_name(self) -> str:
        if path := self.src_image.path:
            return path.name
        return ''

    def title_parts(self, show_dir: bool = False) -> tuple[str, str]:
        prefix = f'{self.file_name} \u2014 ' if self.file_name else ''
        suffix = '' if self.image.size_percent == 1 else f' (Zoom: {self.image.size_str})'
        if show_dir and (img_dir := self.image_dir):
            suffix += f' (Folder: {img_dir.path.as_posix()})'
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

    def get_info_bar_data(self, show_dir: bool = True) -> dict[str, str]:
        image, src_image, img_dir = self.image, self.src_image, self.image_dir
        mod_time, file_b, raw_b = self._file_info
        data = {
            'size': f'{src_image.size_str} x {src_image.bits_per_pixel} BPP',
            'dir_pos': f'{self.dir_index}/{len(img_dir)}' if img_dir else '1/1',
            'size_pct': f'{image.size_percent:.0%}',
            'size_bytes': f'{file_b} / {raw_b}',
            'mod_time': mod_time,
        }
        if show_dir and img_dir:
            data['directory'] = img_dir.path.as_posix()
        return data

    def resize(self, size: XY | None, resize_mode: ImgResizeMode = ImageResizeMode.NONE) -> ResizedImage:
        self.image = image = self.src_image.as_size(size, resize_mode=resize_mode)
        return image

    def scale_percent(self, percent: float) -> ResizedImage:
        return self.resize(self.image.scale_percent(percent))


# endregion


class ImageView(View):
    menu = MenuProperty(MenuBar)
    _last_size: XY = (0, 0)
    active_image: ActiveImage
    dir_loc: InfoLoc
    standalone: bool = False

    def __init__(
        self,
        image: AnyImage,
        title: str = None,
        standalone: bool = False,
        dir_loc: InfoLoc | str = InfoLoc.FOOTER,
        *,
        add_save_as_menu: bool = True,
        save_as_init_dir: PathLike = None,
        **kwargs,
    ):
        kwargs.setdefault('margins', (0, 0))
        kwargs.setdefault('exit_on_esc', True)
        kwargs.setdefault('config_name', self.__class__.__name__)
        super().__init__(title=title or 'Image View', **kwargs)
        self._add_save_as_menu = add_save_as_menu
        self._save_as_init_dir = save_as_init_dir
        self.dir_loc = InfoLoc(dir_loc)
        self.standalone = standalone
        self.active_image = ActiveImage(SourceImage.from_image(image), standalone=standalone)
        self.window_kwargs['show'] = 2
        if size := self._new_window_size():
            self.window_kwargs['size'] = size

    def _show_dir(self, location: InfoLoc) -> bool:
        return self.dir_loc == location and not self.standalone

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
            prefix, suffix = self.active_image.title_parts(self._show_dir(InfoLoc.TITLE_BAR))
        except AttributeError:  # During init with no config_name
            return self._title
        else:
            return f'{prefix}{self._title}{suffix}'

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

    @cached_property(block=False)
    def _style(self):
        return self.window.style.sub_style(bg='#000000', border_width=0)

    def get_post_window_layout(self) -> Layout:
        if not self.standalone:
            yield [self.menu]
        yield [self.gui_image]
        yield self.info_bar

    @cached_property
    def info_bar(self) -> InfoBar:
        return InfoBar.from_dict(self.active_image.get_info_bar_data(self._show_dir(InfoLoc.FOOTER)))

    @cached_property
    def gui_image(self) -> ScrollableImage:
        kwargs = {'pad': (0, 0), 'style': self._style}
        if self._add_save_as_menu:
            class ImageMenu(Menu):
                MenuItem('Save As...', callback=self.handle_save_as)

            kwargs['right_click_menu'] = ImageMenu()

        # return ScrollableImage(None, size=self._window_box.size, anchor='c', **kwargs)
        return ScrollableImage(None, size=self._window_box.size, expand=True, fill='both', **kwargs)

    def finalize_window(self) -> Window:
        window = super().finalize_window()
        window.update()
        # By waiting until after the window has been shown before rendering the image, it avoids some initial jitter
        # while tk Configure events are triggered due to the window being rendered.
        self._update(self.active_image.resize(self._window_box.size, ImageResizeMode.FIT_INSIDE), True)
        return window

    # endregion

    # region Image Methods

    def update_active_image(self, image: AnyImage, image_dir: ImageDir = None):
        src_image = SourceImage.from_image(image)
        self.active_image = ActiveImage(src_image, src_image.fit_inside_size(self._window_box.size), image_dir)
        self._update(self.active_image.image)

    def resize_image(self, size: XY | None, resize_mode: ImgResizeMode = ImageResizeMode.NONE):
        self._update(self.active_image.resize(size, resize_mode))

    def update_image_dir(self, img_dir: Path | ImageDir):
        new_img_dir = img_dir if isinstance(img_dir, ImageDir) else ImageDir(img_dir)
        try:
            img_path = new_img_dir[0]
        except IndexError:
            log.warning(f'Selected directory={new_img_dir.path.as_posix()!r} has no images')
        else:
            log.debug(f'Moving to new directory={new_img_dir.path.as_posix()!r}')
            self.update_active_image(img_path, new_img_dir)

    def cycle_around(self):
        if (image_dir := self.active_image.image_dir) is None:
            return
        last_index = len(image_dir) - 1
        img_index = image_dir.index(self.active_image.path)
        index = last_index if img_index == 0 else 0
        self.update_active_image(image_dir[index], image_dir)

    # endregion

    def _update(self, image: ResizedImage, frame: bool = False):
        self.gui_image.update(image, image.size)
        self.window.set_title(self.title)
        info_bar_data = self.active_image.get_info_bar_data(self._show_dir(InfoLoc.FOOTER))
        self.info_bar.update(info_bar_data, auto_resize=True)
        if frame:
            # TODO: Why is this still needed with expand=True, fill=both?
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

    def handle_save_as(self, event: Event = None):
        return self.active_image.src_image.save_as_with_prompt(event, init_dir=self._save_as_init_dir)

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
    def open_file(self, event: Event):
        # if path := pick_file_popup(self.active_image.src_image.path.parent, title='Pick Image', parent=self.window):
        if path := PickFile(self.active_image.src_image.path.parent, title='Pick Image', parent=self.window).run():
            self.update_active_image(path)

    @event_handler(r'<\>')
    def handle_switch_dir_key_press(self, event: Event):
        if (image_dir := self.active_image.image_dir) is None:
            return

        new_img_dir: Path | ImageDir | None = DirPicker(image_dir).run()  # noqa
        log.debug(f'Selected {new_img_dir=}')
        if new_img_dir and new_img_dir != image_dir.path and new_img_dir != image_dir:
            self.update_image_dir(new_img_dir)

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
            new_img_dir: Path | ImageDir | None = DirPicker(image_dir).run()  # noqa
            log.debug(f'Selected {new_img_dir=}')
            if new_img_dir is None:
                pass
            elif new_img_dir == image_dir.path or new_img_dir == image_dir:
                self.cycle_around()
            else:
                self.update_image_dir(new_img_dir)

    # endregion
