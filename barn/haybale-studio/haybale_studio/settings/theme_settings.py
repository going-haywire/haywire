# haybale_studio/settings/workbench.py
"""Workbench and node theme selection settings."""

from haywire.core.settings.settings_library import LibrarySettings
from haywire.core.settings import setting
from haywire.core.settings.decorator import settings
from haywire.core.settings.descriptor import shadow
from haywire.core.di.config import get_theme_registry
from haywire.core.skin.settings import NodeDefaultSkinSettings, _node_theme_choices
from haywire.barn.builtin.types import CHOICES


def _workbench_theme_choices():
    try:
        return {
            k: lbl
            for k, lbl in get_theme_registry().list_visible_workbench_themes()
            if not k.startswith("__system__:")
        }
    except Exception:
        return {}


@settings(namespace="workbench", label="Workbench Theme")
class WorkbenchThemeSettings(LibrarySettings):
    """Global settings controlling the active workbench theme."""

    theme = setting[CHOICES](
        "",
        label="Workbench Theme",
        description="Active workbench colour theme",
        category="workbench",
        widget_config={"options": _workbench_theme_choices},
    )


@settings(namespace="node_theme", label="Node Theme")
class NodeThemeSettings(LibrarySettings):
    """Global settings controlling the active node theme.

    Shadows the framework's ``studio_node_theme``, which is what the graph and
    node tiers mirror in turn — so this one setting is the top of the chain
    ``framework < graph < node``. It used to be a free STRING defaulting to
    "default", resolved against nothing; a value picked here changed no pixel.
    """

    theme = shadow(
        src=NodeDefaultSkinSettings.studio_node_theme,
        label="Node Theme",
        description="Active node rendering theme",
        category="node_theme",
        widget_config={"options": _node_theme_choices},
    )
