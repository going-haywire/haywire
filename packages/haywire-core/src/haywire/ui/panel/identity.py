"""
PanelIdentity dataclass for the Haywire panel system.
"""

from dataclasses import dataclass, field
from typing import Optional

from haywire.core.registry.identity import BaseIdentity


@dataclass
class PanelIdentity(BaseIdentity):
    """
    Metadata attached to a panel class by the @panel decorator.

    Set once at class-definition time; survives hot-reload.

    Inherits from BaseIdentity:
        registry_id:  Short unique ID, e.g. 'node_transform'.
        registry_key: Fully-qualified key; set by decorator via reg_key().
        label:        Display label shown in the panel header.
        description:  Human-readable description.
        class_name:   Python class name — set by decorator.
        module:       Python module name — set by decorator.

    Additional attributes:
        editor_keys:  One or more editor registry keys this panel belongs to.
        scopes:       One or more scope IDs this panel appears under.
        icon:         Optional Material Design icon name.
        order:        Sort priority (lower = higher in the panel list).
        default_open: Whether the panel starts expanded.
    """

    editor_keys: list[str] = field(default_factory=list)
    scopes: list[str] = field(default_factory=list)
    icon: Optional[str] = None
    order: int = 100
    default_open: bool = True
