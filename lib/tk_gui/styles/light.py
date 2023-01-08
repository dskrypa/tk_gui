from .colors import BLACK
from .style import Style

_light_base = Style('_light_base', parent='__base__', insert_bg=BLACK)

# States: (default, disabled, invalid, active, highlight (may be interpreted as 'selected' for some uses))
