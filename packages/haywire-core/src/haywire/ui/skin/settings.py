# haywire-core/haywire/ui/skin/settings.py
"""Node default skin settings."""

from haywire.core.settings.schema import FrameworkSettings
from haywire.core.settings import setting
from haywire.core.di.config import get_skin_registry


def _node_skin_choices():
    try:
        return {reg_key: reg_key for reg_key in get_skin_registry().list_names()}
    except Exception:
        return {}


def _default_skin():
    try:
        return get_skin_registry().get_default_skin_registry_key()
    except Exception:
        return "default"


class NodeDefaultSkinSettings(FrameworkSettings, namespace="ui.node.default.skin"):
    """Settings controlling node layout, pin geometry, and element visibility.

    These settings are referenced by Node properties.
    All fields are wired to actual rendering logic.
    """

    # Visibility
    default_skin: str = setting(
        default=_default_skin,
        label="Default NodeSkin",
        description="Current default node skin",
        category="skins",
        widget="label",
        order=10,
    )
    studio_skin: str = setting(
        default=_default_skin,
        label="Default Studio Skin",
        description="Studio default node skin",
        category="skins",
        choices=_node_skin_choices,
        order=20,
    )
