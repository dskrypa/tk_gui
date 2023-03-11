"""

"""

from screeninfo import get_monitors

from .models import Monitor, Rectangle

__all__ = ['get_other_monitors']


def get_other_monitors() -> list[Monitor]:
    return [
        Monitor(m.x, m.y, Rectangle.from_pos_and_size(m.x, m.y, m.width, m.height), None, m.name, m.is_primary)
        for m in get_monitors()
    ]
