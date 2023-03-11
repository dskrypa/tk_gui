"""
Documentation:
https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-enumdisplaymonitors
https://docs.microsoft.com/en-us/windows/win32/api/winuser/ns-winuser-monitorinfo
"""

from __future__ import annotations

from ctypes import Structure, sizeof, POINTER, byref, c_uint
from enum import IntEnum
try:
    from ctypes import WinError, WINFUNCTYPE, windll
    from ctypes.wintypes import DWORD, RECT, WCHAR, BOOL, HMONITOR, HDC, LPARAM, LPRECT
except ImportError:  # Not on Windows
    WinError = WINFUNCTYPE = windll = DWORD = RECT = WCHAR = BOOL = HMONITOR = HDC = LPRECT = LPARAM = None

from .models import Monitor, Rectangle

__all__ = ['MonitorInfo', 'ProcessDPIAwareness', 'get_windows_monitors', 'get_all_monitor_info']


class ProcessDPIAwareness(IntEnum):
    UNAWARE = 0             # Typically the default
    SYSTEM_AWARE = 1
    PER_MONITOR_AWARE = 2   # Ensures the actual (non-virtualized) resolution is returned for MonitorInfo


def get_windows_monitors(
    dpi_awareness: ProcessDPIAwareness = ProcessDPIAwareness.PER_MONITOR_AWARE, restore: bool = True
) -> list[Monitor]:
    return [
        Monitor(full.left, full.top, full, monitor_info.work_area, monitor_info.name, full.is_primary)
        for monitor_info in get_all_monitor_info(dpi_awareness, restore)
        if (full := monitor_info.full_area)
    ]


class MonitorInfo(Structure):
    """Technically a MONITORINFOEX structure due to the inclusion of the ``name`` field."""
    _fields_ = [('_struct_size', DWORD), ('_rect', RECT), ('_work_area', RECT), ('flags', DWORD), ('name', WCHAR * 32)]
    name: str

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._struct_size = sizeof(self)
        self.flags = 0x01  # MONITORINFOF_PRIMARY

    @classmethod
    def for_handle(cls, handle) -> MonitorInfo:
        self = cls()
        if not windll.user32.GetMonitorInfoW(handle, byref(self)):
            raise WinError()
        return self

    def __repr__(self) -> str:
        full_area, work_area, flags, name = self.full_area, self.work_area, self.flags, self.name
        return f'<MonitorInfo[{name=}, {full_area=}, {work_area=}, {flags=}]>'

    @property
    def full_area(self) -> Rectangle:
        """Virtual screen coordinates that specify the bounding box for this monitor."""
        rect = self._rect
        return Rectangle(rect.left, rect.top, rect.right, rect.bottom)

    @property
    def work_area(self) -> Rectangle:
        """Portion of the screen that isn't obscured by the taskbar / app desktop toolbars (virt screen coordinates)."""
        rect = self._work_area
        return Rectangle(rect.left, rect.top, rect.right, rect.bottom)


def get_all_monitor_info(
    dpi_awareness: ProcessDPIAwareness = ProcessDPIAwareness.PER_MONITOR_AWARE, restore: bool = True
) -> list[MonitorInfo]:
    handles = []

    def _callback(handle: HMONITOR, dev_ctx_handle: HDC, rect: LPRECT, data: LPARAM):
        handles.append(handle)
        return True  # continue enumeration

    old_awareness = get_dpi_awareness()
    if old_awareness != dpi_awareness:
        windll.shcore.SetProcessDpiAwareness(dpi_awareness)

    try:
        callback = WINFUNCTYPE(BOOL, HMONITOR, HDC, POINTER(RECT), LPARAM)(_callback)
        if not windll.user32.EnumDisplayMonitors(0, 0, callback, 0):
            raise WinError()
    finally:
        if restore and old_awareness != dpi_awareness:
            windll.shcore.SetProcessDpiAwareness(old_awareness)

    return [MonitorInfo.for_handle(hmonitor) for hmonitor in handles]


def get_dpi_awareness() -> ProcessDPIAwareness:
    dpi_awareness = c_uint()
    if windll.shcore.GetProcessDpiAwareness(None, byref(dpi_awareness)):
        raise WinError()
    return ProcessDPIAwareness(dpi_awareness.value)
