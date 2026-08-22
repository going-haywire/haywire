# haybale_core/settings/ui_node.py
"""Node layout and visibility settings for the haybale-core skin implementations."""

from haywire.core.settings.settings_library import LibrarySettings
from haywire.core.settings import setting
from haywire.core.settings.decorator import settings
from haywire.barn.builtin.types import BOOL, INT


@settings(namespace="ui.node.skin", label="Node Skin")
class NodeSkinSettings(LibrarySettings):
    """Settings controlling node layout, pin geometry, and element visibility.

    These settings are consumed directly by NodeSkin and its subclasses.
    All fields are wired to actual rendering logic.
    """

    # Visibility
    show_labels = setting[BOOL](
        True,
        label="Show Port Labels",
        description="Display labels next to ports",
        category="visibility",
    )
    show_tooltips = setting[BOOL](
        True,
        label="Show Tooltips",
        description="Display tooltips on port hover",
        category="visibility",
    )
    # Pin geometry
    pin_gutter = setting[INT](
        20,
        label="Pin Gutter",
        description="Width of the pin column in pixels",
        category="layout",
        min=12,
        max=40,
    )
    pin_protrusion = setting[INT](
        0,
        label="Pin Protrusion",
        description="How far the pin center sits outside the card edge (px). "
        "Positive = further out, negative = pulled inward",
        category="layout",
        min=-20,
        max=20,
    )
    content_gap = setting[INT](
        -15,
        label="Content Gap",
        description="Offset between pin gutter edge and port label (px). "
        "Negative values overlap into the empty half of the gutter",
        category="layout",
        min=-20,
        max=20,
    )
    pin_row_height = setting[INT](
        24,
        label="Pin Row Height",
        description="Height of each pin cell in pixels",
        category="layout",
        min=16,
        max=48,
    )
    pin_column_width = setting[INT](
        24,
        label="Pin Column Width",
        description="Width of each pin cell in a vertical pin strip (px)",
        category="layout",
        min=16,
        max=48,
    )
    card_padding = setting[INT](
        16,
        label="Card Padding",
        description="Horizontal padding applied to the node card in pixels",
        category="layout",
        min=4,
        max=32,
    )
    # Both axes are declared because LayoutDirection resolves PER NODE while
    # this bag is library-global: one graph can hold a T2B node beside an L2R
    # one, so there is no single "current direction" to reinterpret one value
    # against. Each node picks the pair matching its own direction.
    card_padding_block = setting[INT](
        16,
        label="Card Padding (vertical)",
        description="Vertical padding applied to the node card in pixels. Used as the "
        "pin offset baseline when the node's layout direction is T2B or B2T",
        category="layout",
        min=4,
        max=32,
    )
    # --- debug ---
    show_node_ids = setting[BOOL](
        False, label="Show Node IDs", description="Display internal node IDs", category="debug"
    )
    show_port_ids = setting[BOOL](
        False, label="Show Port IDs", description="Display internal port IDs", category="debug"
    )
