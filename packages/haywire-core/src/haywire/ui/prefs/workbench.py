# haywire/ui/prefs/workbench.py
"""Workbench and node theme selection preference singletons."""

from haywire.core.settings import Settings, setting


def _workbench_theme_choices():
    from haywire.core.di.config import get_theme_registry

    try:
        return {
            k: lbl
            for k, lbl in get_theme_registry().list_workbench_themes()
            if not k.startswith("__system__:")
        }
    except Exception:
        return {}


class WorkbenchSettings(Settings):
    """Global preferences controlling the active workbench theme."""

    theme: str = setting(
        "",
        label="Workbench Theme",
        description="Active workbench colour theme",
        category="workbench",
        order=10,
        choices=_workbench_theme_choices,
    )


class NodeThemeSettings(Settings):
    """Global preferences controlling the active node theme."""

    theme: str = setting(
        "default",
        label="Node Theme",
        description="Active node rendering theme",
        category="node_theme",
        order=10,
    )
