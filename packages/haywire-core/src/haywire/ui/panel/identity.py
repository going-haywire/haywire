"""
PanelIdentity dataclass for the Haywire panel system.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional, Tuple

from haywire.core.registry.identity import BaseIdentity

if TYPE_CHECKING:
    from haywire.core.session.signals import Signal


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

    Additional attributes (legacy form — string-keyed):
        editor_keys:  One or more editor registry keys this panel belongs to.
        scopes:       One or more scope IDs this panel appears under.
        icon:         Optional Material Design icon name.
        order:        Sort priority (lower = higher in the panel list).
        default_open: Whether the panel starts expanded.

    New-contract attributes (set when @panel(action=..., focus=...) is used):
        action: The action Protocol/ABC class this panel is typed against.
                Hosts use this to dispatch the right actions object to draw().
        focus:  The Focus subclass discriminator this panel applies to.
        redraw_on: Tuple of Signal subclasses the panel wants its host
                editor to redraw on. Panels do not have their own handler
                dispatch — when one of these signals publishes, the editor
                redraws (and the panel re-mounts as part of that redraw).
                Empty tuple means the panel contributes no subscriptions.
    """

    editor_keys: list[str] = field(default_factory=list)
    scopes: list[str] = field(default_factory=list)
    icon: Optional[str] = None
    order: int = 100
    default_open: bool = True
    action: Optional[type] = None
    focus: Optional[type] = None
    redraw_on: Tuple[type["Signal"], ...] = ()
