from .colors import (
    BLACK, WHITE, GREY_ML_0, GREY_MD_0, GREY_D_0, GREY_D_1, GREY_L_0, GREY_L_1, RED_MD_0, BLU_ML_0, BLU_MD_0
)
from .style import Style

_dark_base = Style('_dark_base', parent='__base__', insert_bg=WHITE)

# States: (default, disabled, invalid, active, highlight (may be interpreted as 'selected' for some uses))

DarkGrey10 = Style(
    'DarkGrey10',
    parent='_dark_base',
    # fg=(GREY_L_1, BLACK, WHITE, None, GREY_D_0),
    # bg=(GREY_D_0, GREY_ML_0, RED_MD_0, None, GREY_L_1),
    fg=(GREY_L_1, GREY_MD_0, RED_MD_0, GREY_L_1, GREY_L_1),
    bg=(GREY_D_0, GREY_D_0, GREY_D_0, GREY_D_0, GREY_D_0),
    input_fg=(BLU_ML_0, BLACK, WHITE, None, GREY_D_1),
    input_bg=(GREY_D_1, GREY_ML_0, RED_MD_0, None, BLU_ML_0),
    menu_fg=(BLU_ML_0, GREY_MD_0, None, BLU_ML_0),
    menu_bg=(GREY_D_1, GREY_D_1, None, BLACK),
    button_fg=(GREY_L_0, None, None, BLACK),
    button_bg=(BLU_MD_0, None, None, BLU_ML_0),
    selected_fg=(GREY_D_0, GREY_ML_0, RED_MD_0),
    selected_bg=(GREY_L_1, BLACK, WHITE),
    # checkbox_bg=(GREY_D_0, GREY_D_0, GREY_D_0),
    # checkbox_label_fg=(GREY_L_1, GREY_MD_0, RED_MD_0, GREY_L_1, GREY_L_1),
    # checkbox_label_bg=(GREY_D_0, GREY_D_0, GREY_D_0, GREY_D_0, GREY_D_0),
    # TODO: Scroll bars seem to be using default grey
    arrows_fg=(GREY_L_0, BLACK, None, None),
    arrows_bg=(BLU_MD_0, GREY_ML_0, None, None),
    combo_fg=(BLU_ML_0, BLACK, WHITE, None, GREY_D_1),
    combo_bg=(GREY_D_1, GREY_ML_0, RED_MD_0, None, BLU_ML_0),
    # slider_fg=(GREY_L_1, GREY_MD_0, RED_MD_0, None, GREY_D_0),
    # slider_bg=(GREY_D_0, GREY_D_0, GREY_D_0, GREY_D_0, GREY_D_0),
    table_alt_fg=BLU_ML_0,
    table_alt_bg=GREY_D_1,
    scroll_trough_color=BLU_MD_0,
    scroll_bg=GREY_D_1,
    scroll_arrow_color=GREY_L_0,
)
