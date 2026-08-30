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
from haywire.core.types.enums import LayoutDirection, NodeDetail


def _layout_direction_choices():
    """Static options — no registry lookup, so no try/except needed."""
    return {d.value: d.label for d in LayoutDirection}


def _node_skin_choices():
    try:
        from haywire.core.di.config import get_skin_registry

        registry = get_skin_registry()
        options = {}
        for reg_key in registry.list_visible_names():
            cls = registry.get(reg_key)
            label = cls.class_identity.label if cls is not None else reg_key
            options[reg_key] = label or reg_key
        return options
    except Exception:
        return {}


def _default_skin():
    try:
        from haywire.core.di.config import get_skin_registry

        return get_skin_registry().get_default_skin_registry_key()
    except Exception:
        return "default"


def _node_detail_choices():
    """Static options — no registry lookup, so no try/except needed."""
    return {d.value: d.label for d in NodeDetail}


def _node_theme_choices():
    """Registered node themes, plus an explicit "inherit" entry.

    The empty key is what makes the tier chain work: a graph or node whose
    ``node_theme`` is empty contributes no CSS vars at all, so the tier above
    it shows through. Without a selectable empty option there would be no way
    back to inheriting once a theme had been picked.
    """
    options = {"": "— Inherit —"}
    try:
        from haywire.core.di.config import get_theme_registry

        options.update({k: lbl for k, lbl in get_theme_registry().list_visible_node_themes()})
    except Exception:
        pass
    return options


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
    )
    studio_skin = setting[CHOICES](
        default=_default_skin,
        label="Default Studio Skin",
        description="Studio default node skin",
        category=CATEGORY_NODE_SKINS,
        widget_config={"options": _node_skin_choices},
    )
    studio_layout_direction = setting[CHOICES](
        LayoutDirection.LEFT_TO_RIGHT.value,
        label="Default Layout Direction",
        description="Direction flow reads across node cards in the studio",
        category=CATEGORY_NODE_SKINS,
        widget_config={"options": _layout_direction_choices},
    )
    # No framework counterpart for node COLLAPSE, deliberately: a studio-wide
    # fold would open every graph showing nothing, and the graph tier already
    # persists that answer in the .haywire file. See ADR 0032.
    studio_node_detail = setting[CHOICES](
        NodeDetail.FULL.value,
        label="Default Node Detail",
        description="How much of a node card is drawn, before a graph or node overrides it",
        category=CATEGORY_NODE_SKINS,
        widget_config={"options": _node_detail_choices},
    )
    studio_node_theme = setting[CHOICES](
        "",
        label="Default Node Theme",
        description="Node theme applied to every card in the studio",
        category=CATEGORY_NODE_SKINS,
        widget_config={"options": _node_theme_choices},
    )
