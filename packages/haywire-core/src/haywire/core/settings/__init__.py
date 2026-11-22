# haywire/core/settings/__init__.py
"""
Settings system — global registry, TOML persistence, and public node-author API.

Public API for node authors:
    from haywire.core.settings import Settings, setting, Color, Icon

    class filter(Settings):
        strength = setting[FLOAT](0.5, min=0.0, max=1.0, label='Strength')

Framework / library internals:
    SettingsRegistry    — TOML resolution chain + LibrarySettings
    FrameworkSettings   — base for haywire-core/studio built-in settings schemas only;
                          not for node or library authors
    LibrarySettings     — base for library-wide TOML settings
    @settings           — decorator for LibrarySettings auto-discovery
"""

from __future__ import annotations

from .base import SettingDescriptor
from .decorator import SettingsClassIdentity, settings
from .descriptor import Promotable, UiState, graph, setting, shadow, watch
from .registry import SettingsRegistry
from .settings import Settings, bag, settings_fields
from .settings_edge import EdgeSettings
from .settings_framework import FrameworkSettings
from .settings_graph import GraphSettings
from .settings_library import LibrarySettings
from .settings_node import NodeSettings
from .types import Color, Icon, Mat3, Mat4, Vec2f, Vec2i, Vec3f, Vec3i, Vec4f, Vec4i, get_vec_meta
from .value import SettingValue

__all__ = [
    # Node-author API
    "Settings",
    "NodeSettings",
    "GraphSettings",
    "EdgeSettings",
    "setting",
    "shadow",
    "watch",
    "graph",
    "Promotable",
    "UiState",
    "SettingDescriptor",
    "bag",
    "settings_fields",
    "Color",
    "Icon",
    "Vec2i",
    "Vec3i",
    "Vec4i",
    "Vec2f",
    "Vec3f",
    "Mat3",
    "Mat4",
    "Vec4f",
    "get_vec_meta",
    # Framework internals
    "SettingValue",
    "SettingsRegistry",
    "LibrarySettings",
    "FrameworkSettings",
    "SettingsClassIdentity",
    "settings",
]
