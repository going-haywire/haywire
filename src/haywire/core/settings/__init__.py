# haywire/core/settings/__init__.py
"""
Settings system with global/local resolution and TOML persistence.
"""

from .enums import SettingMode, SettingScope
from .value import SettingValue
from .definition import SettingDefinition
from .registry import GlobalSettingsRegistry
from .holder import SettingsHolder, SettingInfo

__all__ = [
    'SettingMode',
    'SettingScope', 
    'SettingValue',
    'SettingDefinition',
    'GlobalSettingsRegistry',
    'SettingsHolder',
    'SettingInfo',
]