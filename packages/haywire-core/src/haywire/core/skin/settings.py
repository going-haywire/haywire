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
from haywire.core.types.enums import LayoutDirection


#: Label for the empty choice offered by every inheritable tier.
#:
#: An explicit entry rather than relying on the panel's reset button: the
#: select then *shows* that a value comes from somewhere else, instead of
#: leaving the user to notice a • prefix and find reset in a menu.
INHERIT_LABEL = "— Inherit —"


def _inheritable(options: dict[str, str]) -> dict[str, str]:
    """*options* with the empty "inherit from the tier above" choice in front.

    Only for tiers that HAVE a tier above them — the graph and node bags. The
    framework settings (``studio_*``) are the floor of every chain, so offering
    them an inherit entry would promise a fallback that does not exist.
    """
    return {"": INHERIT_LABEL, **options}


def _layout_direction_choices():
    """Static options — no registry lookup, so no try/except needed."""
    return {d.value: d.label for d in LayoutDirection}


def _layout_direction_choices_inheritable():
    return _inheritable(_layout_direction_choices())


def _node_skin_choices():
    try:
        from haywire.core.di.config import get_skin_registry

        return {reg_key: reg_key for reg_key in get_skin_registry().list_visible_names()}
    except Exception:
        return {}


def _node_skin_choices_inheritable():
    return _inheritable(_node_skin_choices())


def _default_skin():
    try:
        from haywire.core.di.config import get_skin_registry

        return get_skin_registry().get_default_skin_registry_key()
    except Exception:
        return "default"


def _node_theme_choices():
    """Registered node themes. No inherit entry — see the *_inheritable pair.

    At the framework tier the empty key still means "no node theme at all",
    which is a real choice: the workbench theme's node tokens then stand
    unmodified. That is not *inheritance*, so it is not labelled as such here.
    """
    options: dict[str, str] = {"": "— None —"}
    try:
        from haywire.core.di.config import get_theme_registry

        options.update({k: lbl for k, lbl in get_theme_registry().list_visible_node_themes()})
    except Exception:
        pass
    return options


def _node_theme_choices_inheritable():
    """Node themes for the graph and node tiers.

    The empty entry reads "— Inherit —" rather than "— None —" because that is
    what it does here: a tier with no theme of its own contributes no CSS vars,
    so whatever the tier above resolved to shows through unchanged.
    """
    themes = {k: v for k, v in _node_theme_choices().items() if k}
    return _inheritable(themes)


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
    studio_node_theme = setting[CHOICES](
        "",
        label="Default Node Theme",
        description="Node theme applied to every card in the studio",
        category=CATEGORY_NODE_SKINS,
        widget_config={"options": _node_theme_choices},
    )
