# packages/haywire-core/src/haywire/ui/editor_framework/identity.py
"""
EditorIdentity dataclass for the Haywire editor type system.
"""

from dataclasses import dataclass


@dataclass
class EditorIdentity:
    """
    Metadata attached to an editor class by the @editor decorator.

    Set once at class-definition time; survives hot-reload.
    Analogous to RendererIdentity / NodeIdentity in the existing registries.

    Attributes:
        registry_id: Short unique ID, e.g. 'graph_editor'.
        label: Human-readable display name, e.g. 'Graph Editor'.
        icon: Material Design icon name, e.g. 'account_tree'.
        default_area: Which workspace area this editor belongs in by default.
            One of: 'left', 'middle', 'right', 'bottom'.
        description: Human-readable description.
        registry_key: Fully-qualified registry key; set by decorator via reg_key().
    """
    registry_id: str
    label: str
    icon: str = 'extension'
    default_area: str = 'middle'
    description: str = ''
    registry_key: str = ''      # fully-qualified key; set by decorator via reg_key()
