"""
Base identity class for all registry components
"""

from dataclasses import dataclass, field


@dataclass
class BaseIdentity:
    """Base identity class containing common fields for all registry components"""

    registry_id: str  # Unique ID within library - set by user or defaulted to class name
    registry_key: str  # Full unique key including library ID - set by decorator
    label: str  # Human-readable display name
    description: str = ""  # Human-readable description
    deprecation_warning: str = ""  # Optional deprecation warning message
    hidden: bool = False  # Exclude from author-facing selection UIs (still registered/usable)
    class_name: str = ""  # Python class name - set by decorator
    module: str = ""  # Python module name - set by decorator
    # Machine classification that lists filter on (e.g. a skin's "stage-only"); not search words.
    tags: list[str] = field(default_factory=list)
