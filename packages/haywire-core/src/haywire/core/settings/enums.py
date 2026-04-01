# haywire/core/settings/enums.py
"""
Enums for the settings system.
"""

from enum import Enum, auto

class FieldMode(Enum):
    """How a setting value should be resolved."""

    INHERIT = auto()  # No opinion — defer to next tier up
    EXPLICIT = auto()  # Deliberate value — wins unless OVERRIDEd
    OVERRIDE = auto()  # Forced — wins over everything below
