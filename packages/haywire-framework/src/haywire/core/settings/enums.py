# haywire/core/settings/enums.py
"""
Enums for the settings system.
"""

from enum import Enum, auto


class SettingMode(Enum):
    """How a setting value should be resolved."""
    AUTO = auto()      # Inherit from parent level (global or default)
    SET = auto()       # Use this explicit value
    OVERRIDE = auto()  # Force this value on all children (global only)


