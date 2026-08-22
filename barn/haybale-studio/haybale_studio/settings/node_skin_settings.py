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

    Every field here must be READ by rendering logic. This bag renders straight
    into a settings panel, so an unread field is worse than a missing one: the
    user toggles it and nothing happens, which reads as a broken feature rather
    than an absent one. ``show_node_ids`` / ``show_port_ids`` sat unread from
    introduction until they were deleted — under a docstring asserting the
    opposite. ``test_node_skin_settings.py`` now checks this by grepping the
    skins, so the claim cannot rot again.
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
