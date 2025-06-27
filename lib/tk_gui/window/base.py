from __future__ import annotations

import gc
import logging
import tkinter as tk
from queue import Queue, Empty as QueueEmpty
from time import monotonic
from tkinter import PhotoImage, TclError, Event, BaseWidget
from tkinter.ttk import Sizegrip, Scrollbar, Treeview
from typing import TYPE_CHECKING, Any, Iterable, Callable, Iterator, overload
from weakref import finalize, WeakSet

from PIL import ImageGrab

from ..assets import PYTHON_LOGO
from ..caching import cached_property
from ..config import GuiConfig, WindowConfigProperty
from ..elements.menu import Menu
from ..enums import BindTargets, Anchor, Justify, Side, BindEvent, CallbackAction, DisplayServer
from ..environment import DISPLAY_SERVER, ON_LINUX, ON_WINDOWS
from ..event_handling import BindMixin, BindMapping, BindMap, BindManager
from ..event_handling.decorators import delayed_event_handler, _tk_event_handler
from ..event_handling.utils import ENTER_KEYSYMS, MotionTracker, Interrupt
from ..exceptions import DuplicateKeyError
from ..monitors import Monitor, Rectangle, monitor_manager
from ..pseudo_elements.row_container import RowContainer
from ..styles import Style
from ..utils import ProgramMetadata, extract_kwargs
from ..widgets.utils import WidgetData, log_event_widget_data, get_root_widget, get_req_size  # noqa
from .init import HiddenRoot, InitConfig, WindowInitializer, ensure_tk_is_initialized
from .utils import WindowData  # noqa

if TYPE_CHECKING:
    from pathlib import Path
    from PIL.Image import Image as PILImage
    from ..elements.element import Element, ElementBase
    from ..styles.typing import StyleSpec
    from ..typing import XY, BindCallback, EventCallback, Key, BindTarget, Bindable, Layout, Bool, HasValue
    from ..typing import TkContainer, GrabAnywhere, Top, PathLike

__all__ = ['Window']
log = logging.getLogger(__name__)

_GRAB_ANYWHERE_IGNORE = (
    Sizegrip, Scrollbar, Treeview,
    tk.Scale, tk.Scrollbar, tk.Entry, tk.Text, tk.PanedWindow, tk.Listbox, tk.OptionMenu, tk.Button,
)
_INIT_OVERRIDE_KEYS = frozenset({'is_popup', 'keep_on_top', 'no_title_bar', 'modal', 'icon'})
_INIT_CFG_FIELDS = frozenset({
    'min_size', 'size', 'position', 'margins', 'resizable', 'can_minimize', 'scaling',
    'transparent_color', 'alpha_channel',
})


class Window(BindMixin, RowContainer):
    # region Class Attrs
    config: GuiConfig = WindowConfigProperty()
    tk_load_profile: Bool = False
    _tk_event_handlers: dict[str, str] = {}
    _always_bind_events: set[BindEvent] = set()
    _instances: WeakSet[Window] = WeakSet()
    # endregion
    # region Instance Attrs (with defaults)
    __focus_ele: ElementBase | None = None
    _config: tuple[str, str | Path | None, dict[str, Any] | None] = None
    _keep_on_top: bool = False
    _last_interrupt: Interrupt = Interrupt(time=0)
    _last_known_pos: XY | None = None
    _last_known_size: XY | None = None
    _last_run: float = 0
    _last_focus: float = 0
    _motion_tracker: MotionTracker = None
    _grab_anywhere_mgr: BindManager | None = None
    _grab_anywhere: GrabAnywhere = False  #: Whether the window should move on mouse click + movement
    root: Top | None = None  # Set via :meth:`WindowInitializer._init_root_widget`
    tk_container: TkContainer | None = None
    widget: Top = None
    is_popup: bool = False                              #: Whether the window is a popup
    closed: bool = False
    icon: bytes = PYTHON_LOGO
    no_title_bar: bool = False
    modal: bool = False
    global_cleanup_on_close: bool = True
    # endregion
    # region Pure Instance Attrs
    _finalizer: finalize
    _child_windows: WeakSet[Window]
    _task_queue: Queue
    element_map: dict[Key, Element]
    # endregion

    # region Init Overload

    @overload
    def __init__(
        self,
        layout: Layout = None,
        title: str = None,
        *,
        show: Bool = True,
        global_cleanup_on_close: Bool = True,
        # Init-only params
        min_size: XY = (200, 50),
        size: XY = None,
        position: XY = None,
        margins: XY = (10, 5),  # x, y
        resizable: Bool = True,
        can_minimize: Bool = True,
        scaling: float = None,
        transparent_color: str = None,
        alpha_channel: float = None,
        # Misc params
        keep_on_top: Bool = False,
        icon: bytes = None,
        modal: Bool = False,
        no_title_bar: Bool = False,
        # Style-related params
        style: StyleSpec = None,
        anchor_elements: str | Anchor = None,
        text_justification: str | Justify = None,
        element_side: str | Side = None,
        element_padding: XY = None,
        element_size: XY = None,
        # Bind-related params
        binds: BindMapping = None,
        exit_on_esc: Bool = False,
        close_cbs: Iterable[Callable] = None,
        right_click_menu: Menu = None,
        grab_anywhere: GrabAnywhere = False,
        # Scroll params
        scroll_y: Bool = False,
        scroll_x: Bool = False,
        scroll_y_div: float = 2,
        scroll_x_div: float = 1,
        # Config params
        is_popup: Bool = False,
        config_name: str = None,                            #: Name used in config files (defaults to title)
        config_path: PathLike = None,
        config: dict[str, Any] | GuiConfig = None,
    ):
        ...

    # endregion

    # region Init & Common Properties / Methods

    def __init__(
        self,
        layout: Layout = None,
        title: str = None,
        *,
        # Bind-related params
        binds: BindMapping = None,
        exit_on_esc: Bool = False,
        close_cbs: Iterable[Callable] = None,
        right_click_menu: Menu = None,
        grab_anywhere: GrabAnywhere = False,
        # Config params
        config_name: str = None,
        config_path: PathLike = None,
        config: dict[str, Any] | GuiConfig = None,
        # Other params
        style: StyleSpec = None,
        show: Bool = True,
        global_cleanup_on_close: Bool = True,
        **kwargs,
    ):
        self._instances.add(self)
        self._child_windows = WeakSet()
        self.title = title or ProgramMetadata('').name.replace('_', ' ').title()
        self._init_config = InitConfig(**extract_kwargs(kwargs, _INIT_CFG_FIELDS))

        if isinstance(config, GuiConfig) and (config_name or config_path):
            raise TypeError(
                f'Invalid config arg combo - cannot combine {config=} with non-None {config_name=} or {config_path=}'
            )
        self._config = (config_name, config_path, {} if config is None else config)

        for key, val in extract_kwargs(kwargs, _INIT_OVERRIDE_KEYS).items():
            setattr(self, key, val)  # This needs to happen before touching self.config to have is_popup set

        super().__init__(layout, style=style or self.config.style, **kwargs)
        self._event_cbs = BindMap()
        self._bound_for_events: set[str] = set()
        self._task_queue = Queue()
        self.element_map = {}
        self.close_cbs = list(close_cbs) if close_cbs is not None else []
        if binds:
            self.binds = binds
        if right_click_menu:
            self._right_click_menu = right_click_menu
            self.binds.add(BindEvent.RIGHT_CLICK, None)
        if exit_on_esc:
            self.binds.add('<Escape>', BindTargets.EXIT)
        if grab_anywhere:
            self.grab_anywhere = grab_anywhere
        if not global_cleanup_on_close:
            self.global_cleanup_on_close = global_cleanup_on_close
        if show and (self.rows or (isinstance(show, int) and show > 1)):
            self.show()

    @property
    def window(self) -> Window:
        return self

    def __repr__(self) -> str:
        modal, title, title_bar, rows = self.modal, self.title, not self.no_title_bar, len(self.rows)
        try:
            size, pos = self.true_size_and_pos
            has_focus = self.has_focus
        except (AttributeError, RuntimeError):  # No root or not in main thread
            size = pos = has_focus = None
        cls_name = self.__class__.__name__
        return f'<{cls_name}[{self._id}][{pos=}, {size=}, {has_focus=}, {modal=}, {title_bar=}, {rows=}, {title=}]>'

    def __format__(self, format_spec: str) -> str:
        if not format_spec:
            return repr(self)
        parts = []
        if 'w' in format_spec:
            parts.append(f'widget_id={self.root}')

        show = {key: key[0] in format_spec for key in ('pos', 'size', 'focus')}
        if any(show.values()):
            try:
                size, pos = self.true_size_and_pos
                has_focus = self.has_focus
            except (AttributeError, RuntimeError):  # No root or not in main thread
                size = pos = has_focus = None
            for key, val in {'pos': pos, 'size': size, 'focus': has_focus}.items():
                if show[key]:
                    parts.append(f'{key}={val!r}')

        if 't' in format_spec:
            parts.append(f'title={self.title!r}')

        return f'<{self.__class__.__name__}[{self._id}][{", ".join(parts)}]>'

    # endregion

    # region Run / Event Loop

    # TODO: Queue for higher level events, with an iterator method that yields them?  Different bind target to generate
    #  a high level event for window close / exit?  Subclass that uses that instead of the more direct exit, leaving
    #  this one without that or the higher level loop?

    def run(self, timeout: int = 0) -> Window:
        """
        :param timeout: Timeout in milliseconds.  If not specified or <= 0, then the mail loop will run until
          interrupted
        :return: Returns itself to allow chaining
        """
        # Force garbage collection to run now, so if previous windows had variables that need to be cleaned up,
        # that cleanup will happen before this window has a chance to create any threads that may have focus during
        # a gc run.  When a thread other than the main thread has focus during a gc run, and tkinter.Variable.__del__
        # is called, a `RuntimeError: main thread is not in main loop` ends up being raised.
        gc.collect()
        try:
            root = self.root
        except AttributeError:
            self.show()
            root = self.root

        if not self._last_run:
            root.after(100, self._init_fix_focus)  # noqa # Nothing else seemed to work...

        if timeout > 0:
            interrupt_id = root.after(timeout, self.interrupt)  # noqa
        else:
            interrupt_id = None

        self._last_run = monotonic()
        while not self.closed and self._last_interrupt.time < self._last_run:
            self._process_scheduled_tasks()
            # log.debug(f'{self:wt}: Running tk event loop', extra={'color': 14})
            root.mainloop()
            # log.debug(f'{self:wt}: Interrupted tk event loop', extra={'color': 11})

        if interrupt_id is not None:
            root.after_cancel(interrupt_id)

        # log.debug(f'Main loop exited for {self}')
        return self

    def interrupt(self, event: Event = None, element: ElementBase = None):
        self._last_interrupt = Interrupt(event, element)
        # log.debug(f'Interrupting {self} due to {event=}', extra={'color': (0, 9)})
        # try:
        self.root.quit()  # exit the TK main loop, but leave the window open
        # except AttributeError:  # May occur when closing windows out of order
        #     pass

    def update(self):
        try:
            self.root.update()
        except AttributeError:
            self.show()
            self.root.update()

        self._process_scheduled_tasks()

    def update_idle_tasks(self):
        self.root.update_idletasks()

    def schedule_task(self, func: Callable, after_ms: int = 1):
        # log.debug(f'Scheduling task in {self:wt} - adding to queue: {func=}', extra={'color': (0, 11)})
        self._task_queue.put((func, after_ms))
        self.root.quit()

    def _process_scheduled_tasks(self):
        while True:
            try:
                func, after_ms = self._task_queue.get_nowait()
            except QueueEmpty:
                break
            else:
                # log.debug(f'Scheduling task={func} after={after_ms} ms')
                self.root.after(after_ms, func)  # noqa

    def read(self, timeout: int) -> tuple[Key | None, dict[Key, Any], Event | None]:
        self.run(timeout)
        interrupt = self._last_interrupt
        if (element := interrupt.element) is not None:
            try:
                key = element.key
            except AttributeError:
                key = element.id
        else:
            key = None
        return key, self.results, interrupt.event

    def __call__(self, *, take_focus: Bool = False) -> Window:
        """
        Update settings for this window.  Intended as a helper for using this Window as a context manager.

        Example of the intended use case::

            with self.window(take_focus=True) as window:
                window.run()
        """
        if self.root is None:
            self.show()
        if take_focus:
            self.take_focus()
        return self

    def __enter__(self) -> Window:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    # endregion

    # region Results

    def __getitem__(self, item: Key | str | BaseWidget | tuple[int, int]) -> ElementBase | Element | HasValue:
        try:
            return self.element_map[item]
        except KeyError:
            pass
        return super().__getitem__(item)

    @property
    def results(self) -> dict[Key, Any]:
        return {key: ele.value for key, ele in self.element_map.items()}

    def get_result(self, key: Key) -> Any:
        return self.element_map[key].value

    def register_element(self, key: Key, element: Element | HasValue):
        ele_map = self.element_map
        try:
            old = ele_map[key]
        except KeyError:
            ele_map[key] = element
        else:
            raise DuplicateKeyError(key, old, element, self)

    def unregister_element(self, key: Key):
        try:
            del self.element_map[key]
        except KeyError:
            pass

    # endregion

    # region Size

    @property
    def size(self) -> XY:
        root = self.root
        root.update_idletasks()
        return root.winfo_width(), root.winfo_height()

    @size.setter
    def size(self, size: XY):
        self.root.geometry('{}x{}'.format(*size))

    @property
    def true_size(self) -> XY:
        width, height = self.root.geometry().split('+', 1)[0].split('x', 1)
        return int(width), int(height)

    @cached_property
    def title_bar_height(self) -> int:
        root = self.root
        return root.winfo_rooty() - root.winfo_y()

    @cached_property
    def visible_border_width(self) -> int:
        """
        The width of visible window borders, in pixels.  Full outer width = inner width + (outer_border_width * 2).
        """
        # Note: It is not possible to do this with tkinter alone.
        try:
            from ctypes import windll
        except ImportError:
            return 1  # TODO: Handle non-Windows
        # Docs: https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getsystemmetrics
        # SM_CXBORDER: The width of a window border. Equivalent to the SM_CXEDGE value for windows with the 3-D look.
        return windll.user32.GetSystemMetrics(5)  # 5 = SM_CXBORDER

    def set_min_size(self, width: int, height: int):
        root = self.root
        root.minsize(width, height)
        root.update_idletasks()

    def set_max_size(self, width: int, height: int):
        root = self.root
        root.maxsize(width, height)
        root.update_idletasks()

    def inner_rect(self) -> Rectangle:
        width, height, x, y = self._true_size_and_pos
        return Rectangle.from_pos_and_size(x, y, width, height)

    def outer_rect(self) -> Rectangle:
        width, height, x, y = self._true_size_and_pos
        if not self.no_title_bar:
            height += self.title_bar_height
        # Note: There seems to be an -8px offset between x and the actual distance from the edge of the screen, which
        # correlates with the value of (root.winfo_rootx() - root.winfo_x()), but including it below calculation
        # results in incorrect positioning.
        vis_bw = self.visible_border_width
        return Rectangle.from_pos_and_size(x, y, width + (2 * vis_bw), height)

    def resize_scroll_region(self, size: XY | None = None):
        outer, inner = self.root, self.tk_container
        if outer != inner:
            outer.resize_scroll_region(size)
        else:
            raise TypeError(f'Unable to update scroll region for non-scrollable window={self!r}')

    # endregion

    @property
    def _true_size_and_pos(self) -> tuple[int, int, int, int]:
        size, x, y = self.root.geometry().split('+', 2)
        w, h = size.split('x', 1)
        return int(w), int(h), int(x), int(y)

    @property
    def true_size_and_pos(self) -> tuple[XY, XY]:
        w, h, x, y = self._true_size_and_pos
        return (w, h), (x, y)

    # region Position

    @property
    def position(self) -> XY:
        return self.root.winfo_x(), self.root.winfo_y()

    @position.setter
    def position(self, pos: XY):
        try:
            self.root.geometry('+{}+{}'.format(*pos))
            self.root.update_idletasks()
        except AttributeError:  # root has not been created yet
            self._init_config.position = pos

    @property
    def true_position(self) -> XY:
        x, y = self.root.geometry().rsplit('+', 2)[1:]
        return int(x), int(y)

    @property
    def monitor(self) -> Monitor | None:
        return monitor_manager.get_monitor(*self.position)

    def move_to_center(self, other: Window = None):
        """
        Move this Window to the center of the monitor on which it is being displayed, or to the center of the specified
        other Window.

        :param other: A :class:`.Window`
        """
        win_rect = target_rect = self.outer_rect()
        try:
            parent_rect = target_rect = other.outer_rect()
        except (TypeError, AttributeError):
            parent_rect = None
        # log.debug(f'Moving {self=} with {win_rect=} to center relative to {other=} with {parent_rect=}')
        if not (monitor := monitor_manager.get_monitor(*target_rect.position)):
            return
        elif parent_rect:
            centered = parent_rect.center(win_rect)
            # log.debug(f'Centered {win_rect=} within {parent_rect=} => {centered=}')
            centered = monitor.work_area.lazy_center(centered)
            # log.debug(f'  > Final {centered=}')
        else:
            centered = monitor.work_area.center(win_rect)
            # log.debug(f'Centered {win_rect=} within {monitor.work_area=} => {centered=}')
        self.position = centered.position

    @property
    def mouse_position(self) -> XY:
        """The absolute position of the mouse cursor on the desktop"""
        return self.root.winfo_pointerxy()

    # endregion

    # region Window State Methods

    def hide(self):
        self.root.withdraw()

    def un_hide(self):
        self.root.deiconify()

    def minimize(self):
        self.root.iconify()

    def maximize(self):
        if ON_LINUX:
            self.root.attributes('-fullscreen', True)  # May be needed on Windows
        else:
            self.root.state('zoomed')  # Only available on Windows/macOS

    def normal(self):
        # Restore to a normal, non-maximized state from being maximized or minimized to the task bar
        if (state := self.root.state()) == 'iconic':
            self.root.deiconify()
        elif ON_LINUX:
            self.root.attributes('-fullscreen', False)
        elif state == 'zoomed':
            self.root.state('normal')
            # self.root.attributes('-fullscreen', False)

    @property
    def is_maximized(self) -> bool:
        return self.root.state() == 'zoomed'

    def bring_to_front(self):
        root = self.root
        if ON_WINDOWS:
            root.wm_attributes('-topmost', 0)
            root.wm_attributes('-topmost', 1)
            if not self._keep_on_top:
                root.wm_attributes('-topmost', 0)
        else:
            root.lift()

    def send_to_back(self):
        self.root.lower()

    def disable(self):
        self.root.attributes('-disabled', 1)

    def enable(self):
        self.root.attributes('-disabled', 0)

    def take_focus(self):
        self.root.focus_force()

    @property
    def has_focus(self) -> bool:
        try:
            focus_widget = self.root.focus_get()
        except KeyError:
            return False
        if focus_widget is None:  # focus_get may return None
            return False
        return get_root_widget(focus_widget) == self.root

    # endregion

    # region Title Bar

    def set_title(self, title: str):
        self.root.wm_title(title)

    def disable_title_bar(self):
        self.no_title_bar = True
        try:
            if DISPLAY_SERVER == DisplayServer.X11:
                # Note: It does not seem possible for windows without title bars to hold focus, so methods bound to key
                # presses will always be ignored.  Methods bound to mouse clicks will be handled, because the click
                # causes the window/widget to take focus.
                self._set_type_attr('dock')
            else:
                # Instruct the window manager to ignore this widget (on Windows/Mac: hides the title bar)
                self.root.wm_overrideredirect(True)
        except (TclError, RuntimeError):
            log.warning('Error while disabling title bar:', exc_info=True)

    def enable_title_bar(self):
        self.no_title_bar = False
        root = self.root
        root.wm_title(self.title)
        root.iconphoto(False, PhotoImage(data=self.icon))
        try:
            if DISPLAY_SERVER == DisplayServer.X11:
                self._set_type_attr('normal')
            else:
                # Instruct the window manager to stop ignoring this widget (on Windows/Mac: shows the title bar)
                root.wm_overrideredirect(False)
        except (TclError, RuntimeError):
            log.warning('Error while enabling title bar:', exc_info=True)

    def toggle_title_bar(self):
        if self.no_title_bar:
            self.enable_title_bar()
        else:
            self.disable_title_bar()

    # endregion

    # region Config / Update Methods

    def set_alpha(self, alpha: float):
        try:
            self.root.attributes('-alpha', alpha)
        except (TclError, RuntimeError):
            log.debug(f'Error setting window alpha color to {alpha!r}:', exc_info=True)

    def make_modal(self):
        parent = self.parent
        try:  # Apparently this does not work on macs...
            self.root.transient(parent.root if parent else None)  # This will have no effect if parent is not set
            if not self._init_config.can_minimize and DISPLAY_SERVER == DisplayServer.X11:
                self._set_type_attr('utility')  # This must happen after marking the Window as transient

            self.root.grab_set()
            self.root.focus_force()
        except (TclError, RuntimeError):
            log.error('Error configuring window to be modal:', exc_info=True)

    def _set_type_attr(self, window_type: str):
        if DISPLAY_SERVER != DisplayServer.X11:
            return  # This is only supported on Linux with X11

        # The title bar doesn't get re-drawn unless the window is withdrawn and then deiconified
        self.root.wm_attributes('-type', window_type)
        self.root.withdraw()
        self.root.deiconify()

    @property
    def keep_on_top(self) -> bool:
        return self._keep_on_top

    @keep_on_top.setter
    def keep_on_top(self, value: Bool):
        self._keep_on_top = bool(value)
        if (root := self.root) is not None:
            if value and not ON_WINDOWS:
                root.lift()  # Bring the window to the front first
            # if value:  # Bring the window to the front first
            #     if ON_WINDOWS:
            #         root.wm_attributes('-topmost', 0)
            #     else:
            #         root.lift()
            root.wm_attributes('-topmost', 1 if value else 0)

    def update_style(self, style: StyleSpec):
        self.style = Style.get_style(style)
        for element in self.all_elements():
            element.apply_style()

    # endregion

    # region Show Window Methods

    def show(self):
        ensure_tk_is_initialized()
        if self.root is not None:
            log.warning('Attempted to show window after it was already shown', stack_info=True)
            return

        # Note: self.root is set by `WindowInitializer._init_root_widget` when the following line is called
        root = WindowInitializer(self._init_config, self).initialize_window()
        self._finalizer = finalize(self, self._close, root)

    def _init_fix_focus(self):
        if (element := self.__focus_ele) is None:
            return
        try:
            focus_id: str = self.root.focus_get()._w  # noqa
        except AttributeError:
            return
        ele_id: str = element.widget._w  # noqa
        if not focus_id.startswith(ele_id):
            log.debug(f'Setting focus on {element}')
            element.take_focus()

    def maybe_set_focus(self, element: Element) -> bool:
        if self.__focus_ele is not None:
            return False
        element.take_focus()
        self.__focus_ele = element
        return True

    @property
    def was_shown(self) -> bool:
        return self.root is not None

    # endregion

    # region Grab Anywhere

    @property
    def grab_anywhere(self) -> GrabAnywhere:
        return self._grab_anywhere

    @grab_anywhere.setter
    def grab_anywhere(self, value: GrabAnywhere):
        if not value:
            self._grab_anywhere = False
            if bind_mgr := self._grab_anywhere_mgr:
                bind_mgr.unbind_all(self.root)
            return

        old_value = self._grab_anywhere
        if value is True:
            self._grab_anywhere = True
        else:
            try:
                is_control = value.lower() == 'control'
            except (AttributeError, TypeError) as e:
                raise TypeError(f'Unexpected type={value.__class__.__name__} for grab_anywhere {value=}') from e
            if is_control:
                self._grab_anywhere = 'control'
            else:
                raise ValueError(f'Unexpected grab_anywhere {value=}')

        if old_value != self._grab_anywhere and (root := self.root):
            if bind_mgr := self._grab_anywhere_mgr:
                bind_mgr.unbind_all(root)
            self._init_grab_anywhere()

    def _init_grab_anywhere(self):
        prefix = 'Control-' if self.grab_anywhere == 'control' else ''
        event_cb_map = {
            f'<{prefix}Button-1>': self._begin_grab_anywhere,
            f'<{prefix}B1-Motion>': self._handle_grab_anywhere_motion,
            f'<{prefix}ButtonRelease-1>': self._end_grab_anywhere,
        }
        self._grab_anywhere_mgr = bind_mgr = BindManager(event_cb_map)
        bind_mgr.bind_all(self.root)

    def _begin_grab_anywhere(self, event: Event):
        widget: BaseWidget = event.widget
        if isinstance(widget, _GRAB_ANYWHERE_IGNORE):
            return
        widget_id = widget._w  # noqa
        if (element := self.widget_id_element_map.get(widget_id)) and element.ignore_grab:
            return
        self._motion_tracker = MotionTracker(self.true_position, event)

    def _handle_grab_anywhere_motion(self, event: Event):
        try:
            self.position = self._motion_tracker.new_position(event)
        except AttributeError:  # grab anywhere already ended and _motion_tracker is None again
            pass

    def _end_grab_anywhere(self, event: Event):
        try:
            del self._motion_tracker
        except AttributeError:
            pass

    # endregion

    # region Bind Methods

    @property
    def _bind_widget(self) -> BaseWidget | None:
        return self.root

    def apply_binds(self):
        """Called by :meth:`.show` to apply all registered callback bindings"""
        super().apply_binds()
        for bind_event in self._always_bind_events:
            self._bind_event(bind_event, None)

        if self.grab_anywhere:
            self._init_grab_anywhere()

    def _bind(self, event_pat: Bindable, cb: BindTarget, add: bool = True):
        bind_event = _normalize_bind_event(event_pat)
        if isinstance(bind_event, BindEvent):
            self._bind_event(bind_event, cb, add=add)
        elif cb is not None:
            super()._bind(event_pat, self._normalize_bind_cb(cb), add)

    def _normalize_bind_cb(self, cb: BindTargets) -> BindCallback:
        if isinstance(cb, str):
            cb = BindTargets(cb)
        if isinstance(cb, BindTargets):
            if cb == BindTargets.EXIT:
                cb = self.close
            elif cb == BindTargets.INTERRUPT:
                cb = self.interrupt
            else:
                raise ValueError(f'Invalid {cb=} for {self}')

        return cb

    def _bind_event(self, bind_event: BindEvent, cb: EventCallback | None, add: bool = True):
        tk_event: str = getattr(bind_event, 'event', bind_event)
        try:
            window_method_name = self._tk_event_handlers[tk_event]
        except KeyError:
            if cb is None:
                raise TypeError(f'Invalid {cb=} for {bind_event=}')
            # log.debug(f'Binding event={tk_event!r} for {cb=} with {add=}')
            func_id = self.root.bind(tk_event, cb, add=add)
            log.debug(f'Bound event={tk_event!r} for {cb=} with {add=} -> {func_id=}')
        else:
            if tk_event not in self._bound_for_events:
                method = getattr(self, window_method_name)
                # log.debug(f'Binding event={tk_event!r} to {method=} with {add=}')
                func_id = self.root.bind(tk_event, method, add=add)
                log.debug(f'Bound event={tk_event!r} to method={window_method_name} with {add=} -> {func_id=}')
                self._bound_for_events.add(tk_event)
            if cb is not None:
                self._event_cbs.add(bind_event, cb)

    def _iter_event_callbacks(self, bind_event: BindEvent) -> Iterator[EventCallback]:
        if cbs := self._event_cbs.get(bind_event):
            yield from cbs

    def _maybe_bind_return_key(self, cb: BindCallback) -> bool:
        bound_any = False
        for tk_event in ENTER_KEYSYMS:
            if tk_event not in self._bound_for_events:
                self.bind(tk_event, cb)
                self._bound_for_events.add(tk_event)
                bound_any = True
        return bound_any

    # endregion

    # region Event Handling

    def _handle_callback_action(
        self, cb_result: CallbackAction | Any, event: Event = None, element: ElementBase = None
    ) -> bool:
        """
        :param cb_result: The result of a callback
        :param event: The event that triggered the callback that produced the given result
        :param element: The element that handled the event / returned the given result
        :return: True if this Window is closing due to the result, False otherwise
        """
        # log.debug(f'_handle_callback_action: {cb_result=} for {event=}')
        if isinstance(cb_result, CallbackAction):
            if cb_result == CallbackAction.EXIT:
                self.close(event)
                return True
            elif cb_result == CallbackAction.INTERRUPT:
                self.interrupt(event, element)

        return False

    @_tk_event_handler('<Configure>', True)
    @delayed_event_handler(widget_attr='root')
    def _handle_motion_stopped(self, event: Event):
        # log.debug(f'Motion stopped: {event=}')
        with self.config as config:
            new_size, new_pos = self.true_size_and_pos  # The event x/y/size are not the final pos/size
            if new_pos != self._last_known_pos:
                # log.debug(f'  Position changed: old={self._last_known_pos}, new={new_pos}')
                self._last_known_pos = new_pos
                for cb in self._iter_event_callbacks(BindEvent.POSITION_CHANGED):
                    cb(event, new_pos)
                # if not self.is_popup and config.remember_position:
                if config.remember_position:
                    config.position = new_pos
            # else:
            #     log.debug(f'  Position did not change: old={self._last_known_pos}, new={new_pos}')

            if new_size != self._last_known_size:
                # log.debug(f'  Size changed: old={self._last_known_size}, new={new_size}')
                self._last_known_size = new_size
                for cb in self._iter_event_callbacks(BindEvent.SIZE_CHANGED):
                    cb(event, new_size)
                # if not self.is_popup and config.remember_size:
                if config.remember_size:
                    config.size = new_size
            # else:
            #     log.debug(f'  Size did not change: old={self._last_known_size}, new={new_size}')

    # @_tk_event_handler(BindEvent.LEFT_CLICK, True)
    # def _handle_left_click(self, event: Event):
    #     log_event_widget_data(self, event, prefix='Tkinter Click', show_ttk_info=True)
    #     # log_event_widget_data(self, event, prefix='Tkinter Click', show_config=True)

    @_tk_event_handler(BindEvent.RIGHT_CLICK)
    def handle_right_click(self, event: Event):
        # WindowData(self).log(level=logging.INFO)
        # log_event_widget_data(self, event, prefix='Tkinter Click', show_ttk_info=True)
        # log_event_widget_data(self, event, prefix='Tkinter Click', show_config=True)
        try:
            if self.widget_id_element_map[event.widget._w].right_click_menu:
                # If the element that was clicked has its own right-click menu, it should override the window's
                return
        except (AttributeError, KeyError, TypeError):
            pass

        if menu := self._right_click_menu:
            menu.parent = self  # Needed for style inheritance
            menu.show(event, self.tk_container)

    @_tk_event_handler(BindEvent.MENU_RESULT, True)
    def _handle_menu_callback(self, event: Event):
        result = Menu.get_result(event)
        log.debug(f'Menu {result=}')
        if self._handle_callback_action(result, event):
            return

        for cb in self._iter_event_callbacks(BindEvent.MENU_RESULT):
            cb(event, result)

    @_tk_event_handler('<FocusIn>', True)
    def _handle_gain_focus(self, event: Event):
        self._last_focus = monotonic()

    # endregion

    # region Cleanup Methods

    @classmethod
    def _close(cls, root: Top):
        log.debug(f'Closing: {root}', extra={'color': 9})
        root.quit()
        try:
            root.update()  # Needed to actually close the window on Linux if user closed with X
        except Exception:  # noqa
            pass

        # if binds := root.bind_all():    # This seems to be necessary to avoid a bind leak across Windows when
        #     for bind in binds:          # rendering a series of windows/views
        #         root.unbind_all(bind)

        try:
            root.destroy()
            root.update()
        except Exception:  # noqa
            pass
        # log.debug(f'  Done closing {root}')

    def close(self, event: Event = None):
        self.closed = True
        # log.debug(f'Closing window={self:wt} due to {event=}', extra={'color': 13})
        try:
            obj, close_func, args, kwargs = self._finalizer.detach()
        except (TypeError, AttributeError):
            pass
        else:
            # log.debug(f'Closing window={self:wt}', extra={'color': 13})
            self._close_child_windows()
            close_func(*args, **kwargs)
            self.root = None
            for close_cb in self.close_cbs:
                # log.debug(f'Calling {close_cb=}')
                close_cb()

            if self.global_cleanup_on_close:
                HiddenRoot.maybe_schedule_close()

    def _close_child_windows(self):
        for window in tuple(self._child_windows):
            if window.is_popup and not window.closed:
                # log.debug(f'{self:wt}: Closing child={window:wt}')
                window.close()

    # endregion

    def get_screenshot(self) -> PILImage:
        return ImageGrab.grab(self.outer_rect().as_bbox())

    # region Window Instance Registration / Discovery

    @classmethod
    def _get_active_windows(cls, is_popup: Bool = None, *, sort_by_last_focus: bool = False) -> list[Window]:
        if is_popup is None:
            windows = [w for w in tuple(cls._instances) if not w.closed]
        else:
            windows = [w for w in tuple(cls._instances) if not w.closed and w.is_popup == is_popup]

        if sort_by_last_focus:
            windows.sort(key=lambda w: w._last_focus, reverse=True)

        return windows

    @classmethod
    def get_active_window(cls) -> Window | None:
        for w in tuple(cls._instances):
            if not w.closed and w.has_focus:
                return w

        return None

    def register_child_window(self, window: Window):
        # log.debug(f'{self}: Registering child: {window}')
        self._child_windows.add(window)

    @property
    def parent(self) -> Window | None:
        for window in self._get_active_windows():
            if self in window._child_windows:
                return window

        return None

    # endregion


def _normalize_bind_event(event_pat: Bindable) -> Bindable:
    try:
        return BindEvent(event_pat)
    except ValueError:
        return event_pat
