from __future__ import annotations

import logging
from dataclasses import dataclass
from tkinter import Tk, Toplevel, TclError
from typing import TYPE_CHECKING
from weakref import finalize

from ..caching import cached_property
from ..enums import DisplayServer
from ..environment import ON_LINUX, DISPLAY_SERVER
from ..monitors import Monitor, monitor_manager
from ..styles.fonts import FontLoader
from ..utils import timer
from ..widgets.scroll import ScrollableToplevel
from ..widgets.utils import get_req_size

if TYPE_CHECKING:
    from tk_gui.geometry.typing import XY
    from ..typing import Bool, TkContainer, Top
    from ..widgets.configuration import AxisConfig
    from .base import Window

__all__ = ['InitConfig', 'WindowInitializer', 'HiddenRoot', 'ensure_tk_is_initialized']
log = logging.getLogger(__name__)


@dataclass
class InitConfig:
    min_size: XY = (200, 50)
    size: XY = None
    position: XY = None
    margins: XY = (10, 5)  # Padding values for the outer [Scrollable]Toplevel
    resizable: Bool = True
    can_minimize: Bool = True
    transparent_color: str = None
    alpha_channel: float = None
    scaling: float = None


class WindowInitializer:
    def __init__(self, init_config: InitConfig, window: Window):
        self.init_config = init_config
        self.window = window
        self.size: XY | None = init_config.size or window.config.size
        self.position: XY | None = init_config.position or window.config.position

    def initialize_window(self) -> Top:
        root = self._init_root_widget()
        self._configure_root(root)
        self.window.pack_rows()
        self._set_init_size_and_pos(root)
        self._finalize_root(root, self.init_config.alpha_channel)
        return root

    @cached_property
    def monitor(self) -> Monitor | None:
        if self.position:  # A specific position was saved or specified - use it
            x, y = self.position
        else:  # Otherwise, create the new window on the same screen as the mouse cursor's current location
            x, y = ensure_tk_is_initialized().root.winfo_pointerxy()

        # log.debug(f'Finding monitor for {x=}, {y=}; {self.position=}, {self.window.position=}')
        if not (monitor := monitor_manager.get_monitor(x, y)):
            log.debug(f'Could not find monitor for pos={x, y}')
        return monitor

    # region Initialize Widget

    def _init_root_widget(self) -> Top:
        window = self.window
        x_config, y_config = window.x_config, window.y_config
        if y_config.scroll or x_config.scroll:
            root = self._init_root_scrollable(x_config, y_config)
        else:
            root = self._init_root_normal()
        window.widget = window.root = root
        return root

    def _init_root_scrollable(self, x_config: AxisConfig, y_config: AxisConfig) -> ScrollableToplevel:
        style = self.window.style
        kwargs = style.get_map(background='bg')
        kwargs['inner_kwargs'] = kwargs.copy()  # noqa
        root = ScrollableToplevel(
            x_config=x_config, y_config=y_config, style=style, pad=self.init_config.margins, **kwargs
        )
        self.window.tk_container = root.inner_widget
        return root

    def _init_root_normal(self) -> Toplevel:
        pad_x, pad_y = self.init_config.margins
        self.window.tk_container = root = Toplevel(padx=pad_x, pady=pad_y, **self.window.style.get_map(background='bg'))
        return root

    # endregion

    def _configure_root(self, root: Top):
        # Docs for some items here: https://www.tcl-lang.org/man/tcl8.6.14/TkCmd/wm.html
        init_config = self.init_config
        self.window.set_alpha(0)  # Hide window while building it

        if not init_config.resizable:
            root.resizable(False, False)

        if not init_config.can_minimize:
            if DISPLAY_SERVER == DisplayServer.DWM:  # Windows
                try:
                    root.attributes('-toolwindow', 1)  # Only available on Windows
                except (TclError, RuntimeError) as e:
                    log.error(f'Unable to prevent window minimization: {e}')
            elif DISPLAY_SERVER == DisplayServer.X11:
                pass  # Handled in Window.make_modal
            else:
                log.debug(f'Unable to prevent window minimization with {DISPLAY_SERVER=}')

        if self.window._keep_on_top:
            root.attributes('-topmost', 1)

        if (transparent_color := init_config.transparent_color) is not None:
            try:
                root.attributes('-transparentcolor', transparent_color)
            except (TclError, RuntimeError):
                log.error('Transparent window color not supported on this platform (Windows only)')

        if (scaling := init_config.scaling) is not None:
            root.tk.call('tk', 'scaling', scaling)

    def _finalize_root(self, root: Top, alpha_channel: float = None):
        window = self.window
        # if ON_LINUX:
        #     root.wm_overrideredirect(False)  # Instruct the window manager to stop ignoring this widget

        if window.no_title_bar:
            window.disable_title_bar()
        else:
            window.enable_title_bar()

        window.set_alpha(1 if alpha_channel is None else alpha_channel)
        if window.no_title_bar:
            root.focus_force()
        if window.modal:
            window.make_modal()

        root.protocol('WM_DESTROY_WINDOW', window.close)
        root.protocol('WM_DELETE_WINDOW', window.close)
        window.apply_binds()
        root.update_idletasks()

    # region Size & Position

    def _set_init_size_and_pos(self, root: Top):
        if (inner := self.window.tk_container) != root:  # root is scrollable
            root.resize_scroll_region(self._get_init_inner_size(inner))
        if min_size := self.init_config.min_size:
            self.window.set_min_size(*min_size)
        if size := self._get_init_outer_size(root):
            self.window.size = size
        if pos := self.position:
            self.window.position = pos
        else:
            root.update_idletasks()
            self.window.move_to_center()

    def _get_init_inner_size(self, inner: TkContainer) -> XY | None:
        if size := self.size:
            return size

        y_div = self.window.y_config.size_div
        if y_div <= 1 or not (monitor := self.monitor):
            return None

        max_outer_height = monitor.work_area.height - 50

        with timer('Updated inner idle tasks to determine target window size', hide_below=0.4):
            # This step can be very slow if there are many images
            inner.update_idletasks()

        width = self.window.x_config.target_size(inner)
        if (height := inner.winfo_reqheight()) > max_outer_height / 3:
            max_inner_height = max_outer_height - 50
            height = min(max_inner_height, height // y_div)

        return width, height

    def _get_init_outer_size(self, root: Top) -> XY | None:
        if size := self.size:
            return size
        elif not (monitor := self.monitor):
            return None

        work_area = monitor.work_area
        max_width = work_area.width - 100
        max_height = work_area.height - 50

        root.update_idletasks()
        width, height = get_req_size(root)
        if width < max_width and height < max_height:
            return None

        if width > max_width:
            width = max_width
        if height > max_height:
            height = max_height
        return width, height

    # endregion


class HiddenRoot:
    __slots__ = ('root', '_close_cb_id', '_finalizer', '__weakref__')
    __active_hidden_root: HiddenRoot | None = None
    tk_load_profile: bool = False

    def __init__(self):
        FontLoader().load()  # This is a one-time step per process, and this class should only be initialized once
        tk_cls = Tk if self.tk_load_profile else NoProfileTk
        # log.debug('Initializing hidden root')
        self.root = root = tk_cls()
        root.attributes('-alpha', 0)  # Hide this window
        try:
            root.wm_overrideredirect(True)  # Instruct the window manager to ignore this widget
        except (TclError, RuntimeError):
            log.error('Error overriding redirect for hidden root:', exc_info=True)
        root.withdraw()
        self._finalizer = finalize(self, self._close, root)
        self._close_cb_id = None

    def close(self):
        if root := self.root:
            if cb_id := self._close_cb_id:
                try:
                    root.after_cancel(cb_id)
                except TclError:
                    pass
            self._close(root)
            self.root = None

    @classmethod
    def _close(cls, root: Tk | NoProfileTk):
        # log.debug(f'Closing hidden Tk {root=}')
        try:
            root.destroy()
        except (AttributeError, TclError):
            pass
        cls.__active_hidden_root = None

    def schedule_close(self):
        if not self._close_cb_id:
            try:
                self._close_cb_id = self.root.after(500, self.maybe_close)  # noqa
            except (AttributeError, TclError):  # hidden root was already destroyed
                pass

    def maybe_close(self):
        from .base import Window

        if not Window._get_active_windows():
            self.close()

    @classmethod
    def ensure_tk_is_initialized(cls) -> HiddenRoot:
        if cls.__active_hidden_root is None:
            cls.__active_hidden_root = cls()
        return cls.__active_hidden_root

    @classmethod
    def maybe_schedule_close(cls):
        try:
            cls.__active_hidden_root.schedule_close()
        except AttributeError:  # hidden root was already destroyed
            pass


ensure_tk_is_initialized = HiddenRoot.ensure_tk_is_initialized


class NoProfileTk(Tk):
    def readprofile(self, baseName: str, className: str):
        return
