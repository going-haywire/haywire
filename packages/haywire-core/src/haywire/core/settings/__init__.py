# haywire/core/settings/__init__.py
"""
Settings system with global/local resolution and TOML persistence.
"""

from .enums import SettingMode
from .value import SettingValue
from .registry import GlobalSettingsRegistry
from .holder import SettingsHolder, SettingInfo
from .types import Color, Icon
from .descriptors import setting, shadow, watch, SettingDescriptor
from .schema import NodeSettings, LibrarySettings, GlobalSettings, _EmptyNodeSettings
from .decorator import SettingsClassIdentity, settings

__all__ = [
    'SettingMode',
    'SettingValue',
    'GlobalSettingsRegistry',
    'SettingsHolder',
    'SettingInfo',
    'Color',
    'Icon',
    'setting',
    'shadow',
    'watch',
    'SettingDescriptor',
    'NodeSettings',
    'LibrarySettings',
    'GlobalSettings',
    '_EmptyNodeSettings',
    'SettingsClassIdentity',
    'settings',
]