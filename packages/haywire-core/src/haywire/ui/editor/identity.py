"""
EditorIdentity dataclass for the Haywire editor type system.
"""

from dataclasses import dataclass

from haywire.core.registry.identity import BaseIdentity


@dataclass
class EditorIdentity(BaseIdentity):
    """
    Metadata attached to an editor class by the @editor decorator.

    Set once at class-definition time; survives hot-reload.

    Inherits from BaseIdentity:
        registry_id: Short unique ID, e.g. 'graph_editor'.
        registry_key: Fully-qualified registry key; set by decorator via reg_key().
        label: Human-readable display name, e.g. 'Graph Editor'.
        description: Human-readable description.
        class_name: Python class name — set by decorator.
        module: Python module name — set by decorator.

    Additional attributes:
        icon: Material Design icon name, e.g. 'account_tree'.
        default_slot: Which workspace slot this editor belongs in by default.
            One of: 'left', 'right', 'main', 'bottom'.
    """

    icon: str = "extension"
    default_slot: str = "main"
