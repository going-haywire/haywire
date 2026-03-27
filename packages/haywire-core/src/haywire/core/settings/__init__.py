# haywire/core/settings/__init__.py
"""
Settings system — global registry, TOML persistence, and public node-author API.

Public API for node authors:
    from haywire.core.settings import Settings, setting, Color, Icon

    class filter(Settings):
        strength: float = setting(0.5, min=0.0, max=1.0, label='Strength')

Framework / library internals:
    GlobalSettingsRegistry  — TOML resolution chain + LibrarySettings
    GlobalSettings          — base for framework built-in settings schemas
    LibrarySettings         — base for library-wide TOML settings
    @settings               — decorator for LibrarySettings auto-discovery
"""

from .settings import Settings
from .node_settings import NodeSettings
from .descriptor import setting
from .base import FieldDescriptor
from .enums import SettingMode
from .value import SettingValue
from .types import Color, Icon
from .registry import GlobalSettingsRegistry
from .schema import LibrarySettings, GlobalSettings
from .decorator import SettingsClassIdentity, settings

__all__ = [
    # Node-author API
    "Settings",
    "NodeSettings",
    "setting",
    "FieldDescriptor",
    "Color",
    "Icon",
    # Framework internals
    "SettingMode",
    "SettingValue",
    "GlobalSettingsRegistry",
    "LibrarySettings",
    "GlobalSettings",
    "SettingsClassIdentity",
    "settings",
]
