# haywire/core/settings/builtins/workbench.py
"""Workbench and node theme selection settings."""

from ..schema import GlobalSettings
from ..descriptors import setting


class WorkbenchSettings(GlobalSettings, namespace='workbench'):
    """Global settings controlling workbench appearance and active themes."""

    theme: str = setting(
        'haywire-dark', 
        label='Workbench Theme',
        description='Active workbench colour theme',
        category='workbench', 
        order=10,
        choices=['haywire-dark', 'haywire-light'])


class NodeThemeSettings(GlobalSettings, namespace='node'):
    """Global settings controlling active node theme."""

    theme: str = setting(
        'default', 
        label='Node Theme',
        description='Active node rendering theme',
        category='node', 
        order=10)
