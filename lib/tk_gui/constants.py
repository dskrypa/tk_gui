LEFT_CLICK = '<ButtonRelease-1>'
CTRL_LEFT_CLICK = '<Control-ButtonRelease-1>'

STYLE_CONFIG_KEYS = frozenset({
    'activebackground',
    'activeforeground',
    'activerelief',
    'background',
    'bd',
    'bg',
    'border',
    'borderwidth',
    'buttonbackground',
    'buttoncursor',
    'buttondownrelief',
    'buttonuprelief',
    'cursor',
    'disabledbackground',
    'disabledforeground',
    'elementborderwidth',
    'fg',
    'font',
    'foreground',
    'highlightbackground',
    'highlightcolor',
    'highlightthickness',
    'insertbackground',
    'insertborderwidth',
    'insertwidth',
    'overrelief',
    'readonlybackground',
    'relief',
    'sashcursor',
    'sashrelief',
    'sashwidth',
    'selectbackground',
    'selectborderwidth',
    'selectcolor',
    'selectforeground',
    'sliderrelief',
    'troughcolor',
    'underline',
    'wraplength',
})

# fmt: off
IMAGE_MODE_TO_BPP = {
    '1': 1,         'L': 8,         'P': 8,         'RGB': 24,      'RGBA': 32,
    'CMYK': 32,     'YCbCr': 24,    'LAB': 24,      'HSV': 24,      'I': 32,        'F': 32,
    'I;16': 16,     'I;16B': 16,    'I;16L': 16,    'I;16S': 16,    'I;16BS': 16,   'I;16LS': 16,
    'I;32': 32,     'I;32B': 32,    'I;32L': 32,    'I;32S': 32,    'I;32BS': 32,   'I;32LS': 32,
}
# fmt: on
