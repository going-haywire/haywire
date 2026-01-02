from enum import Enum


class ThemeKey(str, Enum):
    """
    Unified theme keys for all theme values.
    Organized by category for clarity.
    """

    # UI - Semantic colors
    UI_PRIMARY = 'ui.primary'
    UI_SECONDARY = 'ui.secondary'
    UI_ACCENT = 'ui.accent'

    # UI - Status colors
    UI_ERROR = 'ui.error'
    UI_WARNING = 'ui.warning'
    UI_SUCCESS = 'ui.success'
    UI_INFO = 'ui.info'

    # UI - Node/Port
    UI_NODE_BACKGROUND = 'ui.node_background'
    UI_NODE_BORDER = 'ui.node_border'
    UI_NODE_SELECTED_BORDER = 'ui.node_selected_border'
    UI_PORT_BORDER = 'ui.port_border'
    UI_PORT_DEFAULT = 'ui.port_default'

    # UI - Canvas
    UI_CANVAS_BACKGROUND = 'ui.canvas_background'
    UI_CANVAS_GRID_LINE = 'ui.canvas_grid_line'
    UI_CANVAS_GRID_DOT = 'ui.canvas_grid_dot'
    UI_SELECTION_BOX = 'ui.selection_box'
    UI_SELECTION_BOX_BORDER = 'ui.selection_box_border'

    # UI - Text
    UI_TEXT_PRIMARY = 'ui.text_primary'
    UI_TEXT_SECONDARY = 'ui.text_secondary'
    UI_TEXT_DISABLED = 'ui.text_disabled'
    UI_TEXT_HINT = 'ui.text_hint'

    # UI - Port Icons
    UI_PORT_ICON_IN_MULTI_COMPOUND = 'ui.port_icon_in_multi_compound_'
    UI_PORT_ICON_IN_MULTI_SINGLE = 'ui.port_icon_in_multi_single'
    UI_PORT_ICON_IN_COMPOUND = 'ui.port_icon_in_compound'
    UI_PORT_ICON_IN_SINGLE = 'ui.port_icon_in_single'
    UI_PORT_ICON_OUT_MULTI_COMPOUND = 'ui.port_icon_out_multi_compound'
    UI_PORT_ICON_OUT_MULTI_SINGLE = 'ui.port_icon_out_multi_single'
    UI_PORT_ICON_OUT_COMPOUND = 'ui.port_icon_out_compound'
    UI_PORT_ICON_OUT_SINGLE = 'ui.port_icon_out_single'