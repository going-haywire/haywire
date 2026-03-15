# packages/haywire-core/src/haywire/ui/panel/identity.py
"""
PanelIdentity dataclass for the Haywire panel system.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class PanelIdentity:
    """
    Metadata attached to a panel class by the @panel decorator.

    Set once at class-definition time; survives hot-reload.

    Attributes:
        registry_id: Short unique ID, e.g. 'node_transform'.
        editor_key: Registry key of the editor this panel belongs to.
        context: Context filter string, e.g. 'node', 'graph', 'edge'.
        label: Display label shown in the panel header.
        icon: Optional Material Design icon name.
        order: Sort priority (lower = higher in the panel list).
        default_open: Whether the panel starts expanded.
        description: Human-readable description.
        registry_key: Fully-qualified key; set by decorator via reg_key().
    """
    registry_id: str
    editor_key: str
    context: str
    label: str
    icon: Optional[str] = None
    order: int = 100
    default_open: bool = True
    description: str = ''
    registry_key: str = ''      # fully-qualified key; set by decorator via reg_key()
