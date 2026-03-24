"""
Base identity class for all registry components
"""

from dataclasses import dataclass


@dataclass
class BaseIdentity:
    """Base identity class containing common fields for all registry components"""

    registry_id: str = ""  # Set by user for unique ID within library - fallback to class name
    registry_key: str = ""  # Full unique key including library ID - set by decorator
    label: str = ""  # Human-readable display name
    description: str = ""  # Human-readable description
    deprecation_warning: str = ""  # Optional deprecation warning message
