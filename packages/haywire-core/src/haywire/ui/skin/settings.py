# haywire-core/haywire/ui/skin/settings.py
"""Node default skin settings."""

from haywire.core.namespaces import CATEGORY_NODE_SKINS, NAMESPACE_UI_NODE_DEFAULT_SKIN
from haywire.core.settings.schema import FrameworkSettings
from haywire.core.settings import setting


def _node_skin_choices():
    try:
        from haywire.core.di.config import get_skin_registry

        return {reg_key: reg_key for reg_key in get_skin_registry().list_names()}
    except Exception:
        return {}


def _default_skin():
    try:
        from haywire.core.di.config import get_skin_registry

        return get_skin_registry().get_default_skin_registry_key()
    except Exception:
        return "default"


class NodeDefaultSkinSettings(FrameworkSettings, namespace=NAMESPACE_UI_NODE_DEFAULT_SKIN):
    """Settings controlling node layout, pin geometry, and element visibility.

    These settings are referenced by Node properties.
    All fields are wired to actual rendering logic.
    """

    # Visibility
    default_skin = setting[str](
        default=_default_skin,
        label="Default NodeSkin",
        description="Current default node skin",
        category=CATEGORY_NODE_SKINS,
        widget="label",
        order=10,
    )
    studio_skin = setting[str](
        default=_default_skin,
        label="Default Studio Skin",
        description="Studio default node skin",
        category=CATEGORY_NODE_SKINS,
        choices=_node_skin_choices,
        order=20,
    )
