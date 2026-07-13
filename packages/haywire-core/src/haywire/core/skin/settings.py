# haywire/core/skin/settings.py
"""Node default skin settings.

A pure FrameworkSettings schema — it declares WHICH skin is the default,
not how a skin renders. The rendering machinery (nicegui-backed skin
classes, node card layout) lives in haywire.ui.skin; this module has no
dependency on it, which is exactly why it lives in core: NodeProperties
and GraphProperties (both core) shadow/graph-mirror these fields, and
core must never import from ui.
"""

from haywire.barn.builtin.types import CHOICES, STRING
from haywire.barn.builtin.widgets.basic_widgets import SimpleLabelWidget
from haywire.core.namespaces import CATEGORY_NODE_SKINS, NAMESPACE_UI_NODE_DEFAULT_SKIN
from haywire.core.settings.settings_framework import FrameworkSettings
from haywire.core.settings import setting


def _node_skin_choices():
    try:
        from haywire.core.di.config import get_skin_registry

        return {reg_key: reg_key for reg_key in get_skin_registry().list_visible_names()}
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
    default_skin = setting[STRING](
        default=_default_skin,
        label="Default NodeSkin",
        description="Current default node skin",
        category=CATEGORY_NODE_SKINS,
        widget=SimpleLabelWidget.config(),
        order=10,
    )
    studio_skin = setting[CHOICES](
        default=_default_skin,
        label="Default Studio Skin",
        description="Studio default node skin",
        category=CATEGORY_NODE_SKINS,
        widget_config={"options": _node_skin_choices},
        order=20,
    )
