from .style import Style, StyleSpec, STATE_NAMES, StyleLayer, Layer, StyleState, Font
from .base import _base_, SystemDefault
from .light import _light_base
from .dark import _dark_base, DarkGrey10

DarkGrey10.make_default()
