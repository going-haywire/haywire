# haywire/core/settings/__init__.py
"""
Settings system — global registry, TOML persistence, and public node-author API.

Public API for node authors:
    from haywire.core.settings import Settings, setting, Color, Icon

    class filter(Settings):
        strength = setting[float](0.5, min=0.0, max=1.0, label='Strength')

Framework / library internals:
    SettingsRegistry    — TOML resolution chain + LibrarySettings
    FrameworkSettings   — base for haywire-core/studio built-in settings schemas only;
                          not for node or library authors
    LibrarySettings     — base for library-wide TOML settings
    @settings           — decorator for LibrarySettings auto-discovery
"""

from .settings import Settings
from .node_settings import NodeSettings
from .descriptor import setting, shadow, watch
from .base import FieldDescriptor
from .enums import FieldMode
from .value import FieldValue
from .types import Color, Icon, Vec2i, Vec3i, Vec4i, Vec2f, Vec3f, Vec4f, get_vec_meta
from .registry import SettingsRegistry
from .schema import LibrarySettings, FrameworkSettings
from .decorator import SettingsClassIdentity, settings

__all__ = [
    # Node-author API
    "Settings",
    "NodeSettings",
    "setting",
    "shadow",
    "watch",
    "FieldDescriptor",
    "Color",
    "Icon",
    "Vec2i",
    "Vec3i",
    "Vec4i",
    "Vec2f",
    "Vec3f",
    "Vec4f",
    "get_vec_meta",
    # Framework internals
    "FieldMode",
    "FieldValue",
    "SettingsRegistry",
    "LibrarySettings",
    "FrameworkSettings",
    "SettingsClassIdentity",
    "settings",
]
