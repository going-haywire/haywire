# haywire/core/settings/__init__.py
"""
Settings system with global/local resolution and TOML persistence.
"""

from .enums import SettingMode, SettingScope
from .value import SettingValue
from .definition import SettingDefinition
from .registry import GlobalSettingsRegistry
from .holder import SettingsHolder, SettingInfo
from .types import Color, Icon
from .descriptors import setting, shadow, watch, _SettingDescriptor
from .schema import NodeSettings, LibrarySettings, GlobalSettings, _EmptyNodeSettings
from .decorators import SettingsClassIdentity, library_settings

__all__ = [
    # Legacy
    'SettingMode',
    'SettingScope',
    'SettingValue',
    'SettingDefinition',
    'GlobalSettingsRegistry',
    'SettingsHolder',
    'SettingInfo',
    # New descriptor / schema API
    'Color',
    'Icon',
    'setting',
    'shadow',
    'watch',
    '_SettingDescriptor',
    'NodeSettings',
    'LibrarySettings',
    'GlobalSettings',
    '_EmptyNodeSettings',
    'SettingsClassIdentity',
    'library_settings',
]