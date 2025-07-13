from .layers import StyleLayer
from .states import STATE_NAMES
from .style import Style
from .base import _base_, SystemDefault
from .light import _light_base
from .dark import _dark_base, DarkGrey10
from .fonts import FontLoader

DarkGrey10.make_default()
