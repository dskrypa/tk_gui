"""

"""

from tk_gui.caching import cached_property
from tk_gui.environment import ON_WINDOWS
from .models import Monitor

if ON_WINDOWS:
    from ._windows import get_windows_monitors as get_monitors
else:
    from ._other import get_other_monitors as get_monitors

__all__ = ['MonitorManager', 'get_monitors', 'monitor_manager']


class MonitorManager:
    @cached_property
    def monitors(self) -> list[Monitor]:
        return get_monitors()

    def get_monitor(self, x: int, y: int) -> Monitor | None:
        if x is None or y is None:
            return None
        for m in self.monitors:
            if m.x <= x <= m.x + m.width and m.y <= y <= m.y + m.height:
                return m
        return None


monitor_manager: MonitorManager = MonitorManager()
