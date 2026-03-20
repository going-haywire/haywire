# haywire/ui/prefs/workbench.py
"""Workbench and node theme selection preference singletons."""

from haywire.core.reactive import Reactive, prop


def _workbench_theme_choices():
    from haywire.core.di.config import get_theme_registry
    try:
        return {k: lbl for k, lbl in get_theme_registry().list_workbench_themes()
                if not k.startswith('__system__:')}
    except Exception:
        return {}


class WorkbenchSettings(Reactive):
    """Global preferences controlling the active workbench theme."""

    theme: str = prop(
        '',
        label='Workbench Theme',
        description='Active workbench colour theme',
        category='workbench',
        order=10,
        choices=_workbench_theme_choices,
    )


class NodeThemeSettings(Reactive):
    """Global preferences controlling the active node theme."""

    theme: str = prop(
        'default',
        label='Node Theme',
        description='Active node rendering theme',
        category='node_theme',
        order=10,
    )
