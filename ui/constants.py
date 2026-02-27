"""
UI Constants
Shared dimensions and values for the Prism Desktop UI.
"""

# Grid Layout
DEFAULT_COLS = 4
GRID_MARGIN_LEFT = 12
GRID_MARGIN_RIGHT = 12
GRID_MARGIN_TOP = 12
GRID_MARGIN_BOTTOM = 8

# Button Dimensions
BUTTON_WIDTH = 90   # Standard single-column button width
BUTTON_HEIGHT = 80  # Standard grid button height
BUTTON_SPACING = 8  # Spacing between buttons

# Footer Dimensions
FOOTER_HEIGHT = 26
FOOTER_MARGIN_BOTTOM = 12

# Animation Timings
ANIM_DURATION_ENTRANCE = 1500
ANIM_DURATION_HEIGHT = 400
ANIM_DURATION_WIDTH = 400
ANIM_DURATION_BORDER = 1500

# Root layout margins (each side)
ROOT_MARGIN = 10
RESIZE_MARGIN = 20 # Width of invisible resize handles (increased for better grip)


def calculate_width(cols: int) -> int:
    """Calculate the total window width for a given number of columns.
    
    Layout: root margin (10) + grid margin left (12) + buttons + spacing + grid margin right (12) + root margin (10)
    Buttons: cols * BUTTON_WIDTH + (cols - 1) * BUTTON_SPACING
    """
    inner = cols * BUTTON_WIDTH + (cols - 1) * BUTTON_SPACING
    return inner + GRID_MARGIN_LEFT + GRID_MARGIN_RIGHT + (ROOT_MARGIN * 2)


def calculate_footer_btn_width(cols: int) -> int:
    """Calculate footer button width for a given number of columns.
    
    Two footer buttons split the available grid width with one spacing gap.
    """
    grid_inner = cols * BUTTON_WIDTH + (cols - 1) * BUTTON_SPACING
    return (grid_inner - BUTTON_SPACING) // 2


WINDOW_WIDTH = calculate_width(DEFAULT_COLS)
