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
        order=10,
    )
    show_tooltips = setting[BOOL](
        True,
        label="Show Tooltips",
        description="Display tooltips on port hover",
        category="visibility",
        order=20,
    )
    show_resize_handle = setting[BOOL](
        True,
        label="Show Resize Handle",
        description="Display the drag handle for resizing nodes",
        category="visibility",
        order=30,
    )

    # Pin geometry
    pin_gutter = setting[INT](
        20,
        label="Pin Gutter",
        description="Width of the pin column in pixels",
        category="layout",
        order=40,
        min=12,
        max=40,
    )
    pin_protrusion = setting[INT](
        0,
        label="Pin Protrusion",
        description="How far the pin center sits outside the card edge (px). "
        "Positive = further out, negative = pulled inward",
        category="layout",
        order=50,
        min=-20,
        max=20,
    )
    content_gap = setting[INT](
        -15,
        label="Content Gap",
        description="Offset between pin gutter edge and port label (px). "
        "Negative values overlap into the empty half of the gutter",
        category="layout",
        order=60,
        min=-20,
        max=20,
    )
    pin_row_height = setting[INT](
        24,
        label="Pin Row Height",
        description="Height of each pin cell in pixels",
        category="layout",
        order=70,
        min=16,
        max=48,
    )
    card_padding = setting[INT](
        16,
        label="Card Padding",
        description="Horizontal padding applied to the node card in pixels",
        category="layout",
        order=80,
        min=4,
        max=32,
    )
    # --- debug ---
    show_node_ids = setting[BOOL](
        False, label="Show Node IDs", description="Display internal node IDs", category="debug", order=21
    )
    show_port_ids = setting[BOOL](
        False, label="Show Port IDs", description="Display internal port IDs", category="debug", order=22
    )
    inspect_on_click = setting[BOOL](
        False,
        label="Inspect on Click",
        description="Show data inspector when clicking ports",
        category="debug",
        order=41,
    )
