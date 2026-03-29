# haybale_core/settings/ui_node.py
"""Node layout and visibility settings for the haybale-core skin implementations."""

from haywire.core.settings.schema import LibrarySettings
from haywire.core.settings import setting
from haywire.core.settings.decorator import settings
from haywire.core.di.config import get_skin_registry


def _node_skin_choices():
    try:
        return {
            reg_key: reg_key
            for reg_key in get_skin_registry().list_names()
        }
    except Exception:
        return {}

def _default_skin():
    try:
        return get_skin_registry().get_default_skin_registry_key()
    except Exception:
        return "default"

@settings(namespace="ui.node.skin", label="Node Skin")
class NodeSkinSettings(LibrarySettings):
    """Settings controlling node layout, pin geometry, and element visibility.

    These settings are consumed directly by NodeSkin and its subclasses.
    All fields are wired to actual rendering logic.
    """

    # Visibility
    default_skin: str = setting(
        default=_default_skin,
        label="Default NodeSkin",
        description="Current default node skin",
        category="skins",
        read_only=True,
        order=0,
    )
    studio_skin: str = setting(
        default=_default_skin,
        label="Default Studio Skin",
        description="Studio default node skin",
        category="skins",
        choices=_node_skin_choices,
        order=5,
    )

    # Visibility
    show_labels: bool = setting(
        True,
        label="Show Port Labels",
        description="Display labels next to ports",
        category="visibility",
        order=10,
    )
    show_tooltips: bool = setting(
        True,
        label="Show Tooltips",
        description="Display tooltips on port hover",
        category="visibility",
        order=20,
    )
    show_resize_handle: bool = setting(
        True,
        label="Show Resize Handle",
        description="Display the drag handle for resizing nodes",
        category="visibility",
        order=30,
    )

    # Pin geometry
    pin_gutter: int = setting(
        20,
        label="Pin Gutter",
        description="Width of the pin column in pixels",
        category="layout",
        order=40,
        min=12,
        max=40,
    )
    pin_protrusion: int = setting(
        0,
        label="Pin Protrusion",
        description="How far the pin center sits outside the card edge (px). "
        "Positive = further out, negative = pulled inward",
        category="layout",
        order=50,
        min=-20,
        max=20,
    )
    content_gap: int = setting(
        -15,
        label="Content Gap",
        description="Offset between pin gutter edge and port label (px). "
        "Negative values overlap into the empty half of the gutter",
        category="layout",
        order=60,
        min=-20,
        max=20,
    )
    pin_row_height: int = setting(
        24,
        label="Pin Row Height",
        description="Height of each pin cell in pixels",
        category="layout",
        order=70,
        min=16,
        max=48,
    )
    card_padding: int = setting(
        16,
        label="Card Padding",
        description="Horizontal padding applied to the node card in pixels",
        category="layout",
        order=80,
        min=4,
        max=32,
    )
