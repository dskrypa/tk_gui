from .colors import BLACK, GREY_L_1, CYAN_0, YLW_L_0
from .style import Style

DEFAULT_FONT = ('Helvetica', 10)

# States: (default, disabled, invalid, active, highlight (may be interpreted as 'selected' for some uses))
_common = {
    'font': DEFAULT_FONT,
    'ttk_theme': 'default',
    'border_width': 1,
    'link_fg': CYAN_0,
    'link_font': (*DEFAULT_FONT, 'underline'),
    'scroll_bar_width': 14,     # [ttk default: 12] If < arrow_width, it is automatically set to arrow_width by tk
    'scroll_arrow_width': 14,   # Note: This should match the bar_width value, otherwise it will look weird
}
# Style('SystemDefault', **_common, table_alt_bg='#cccdcf')
SystemDefault = Style(
    'SystemDefault',
    **_common,
    table_alt_bg=GREY_L_1,
    # fg=('SystemButtonText', 'SystemDisabledText', None, 'SystemButtonText', 'SystemHighlightText'),
    # bg=('SystemButtonFace', 'SystemButtonFace', None, 'SystemButtonFace', 'SystemHighlight'),
    # radio_fg=('SystemWindowText', 'SystemDisabledText', None, 'SystemWindowText', 'SystemWindowFrame'),
    # radio_bg=('SystemButtonFace', 'SystemButtonFace', None, 'SystemButtonFace', 'SystemButtonFace'),
    # selected_fg='SystemHighlightText',
    # selected_bg='SystemHighlight',
    # listbox_bg='SystemWindow',
    # input_fg=('SystemWindowText', 'SystemDisabledText', None, None, 'SystemWindowFrame'),
    # input_bg=('SystemWindow', 'SystemButtonFace', None, None, 'SystemButtonFace'),
    # # text_fg=('SystemButtonText', 'SystemDisabledText', None, 'SystemButtonText', 'SystemWindowFrame'),  # Label
    # checkbox_fg=('SystemWindowText', 'SystemDisabledText', None, 'SystemWindowText', 'SystemWindowFrame'),
    # # checkbox_bg=('SystemButtonFace', None, None, 'SystemButtonFace', 'SystemButtonFace',),
    # scroll_trough_color='SystemScrollbar',
)
_base_ = Style(
    '__base__',
    tooltip_fg=BLACK,
    tooltip_bg=YLW_L_0,   # light yellow
    **_common,
)
