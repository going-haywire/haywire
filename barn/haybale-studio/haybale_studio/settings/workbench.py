# haybale_studio/settings/workbench.py
"""Workbench and node theme selection settings."""

from haywire.core.settings.schema import LibrarySettings
from haywire.core.settings import setting
from haywire.core.settings.decorator import settings
from haywire.core.di.config import get_theme_registry

def _workbench_theme_choices():
    try:
        return {
            k: lbl
            for k, lbl in get_theme_registry().list_workbench_themes()
            if not k.startswith("__system__:")
        }
    except Exception:
        return {}
    
@settings(namespace="workbench", label="Workbench")
class WorkbenchSettings(LibrarySettings):
    """Global settings controlling the active workbench theme."""

    theme: str = setting(
        "",
        label="Workbench Theme",
        description="Active workbench colour theme",
        category="workbench",
        order=10,
        choices=_workbench_theme_choices,
    )


@settings(namespace="node_theme", label="Node Theme")
class NodeThemeSettings(LibrarySettings):
    """Global settings controlling the active node theme."""

    theme: str = setting(
        "default",
        label="Node Theme",
        description="Active node rendering theme",
        category="node_theme",
        order=10,
    )
