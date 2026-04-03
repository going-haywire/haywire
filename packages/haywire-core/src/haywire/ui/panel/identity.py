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
        registry_id:  Short unique ID, e.g. 'node_transform'.
        editor_keys:  One or more editor registry keys this panel belongs to,
                      e.g. ['properties'] or ['properties', 'context_menu'].
                      Always stored as a list (normalised by the decorator).
        scopes:       One or more scope IDs this panel appears under,
                      e.g. ['node'] or ['my_lib', 'node'].
                      Always stored as a list (normalised by the decorator).
        label:        Display label shown in the panel header.
        icon:         Optional Material Design icon name.
        order:        Sort priority (lower = higher in the panel list).
        default_open: Whether the panel starts expanded.
        description:  Human-readable description.
        registry_key: Fully-qualified key; set by decorator via reg_key().
    """

    registry_id: str
    editor_keys: list[str]
    scopes: list[str]
    label: str
    icon: Optional[str] = None
    order: int = 100
    default_open: bool = True
    description: str = ""
    registry_key: str = ""
