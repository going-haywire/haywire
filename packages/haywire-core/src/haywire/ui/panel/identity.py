"""
PanelIdentity dataclass for the Haywire panel system.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, Tuple

from haywire.core.access import AccessTier
from haywire.core.registry.identity import BaseIdentity

if TYPE_CHECKING:
    from haywire.core.signals import Signal
    from haywire.ui.surface import Surface


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

    ``label`` and ``icon`` are *component identity* — what listings, the
    generated panel docs, and the properties editor's expansion header read.
    They are not chrome a host reads to place the panel; that is a Surface's
    ``presentation`` (ADR-0029).

    Placement attributes:
        icon:         Optional Material Design icon name.
        order:        Sort priority (lower = higher in the panel list).
        default_open: Whether the panel starts expanded.

    Contract attributes:
        surface: The Surface subclass this panel appears on. Routing is by
                ``surface.id``, never by class object (ADR-0009).
        hosts:  Surface subclasses this panel may itself render, via
                ``self.render_surface(S, ctx)`` inside ``draw()``. The
                declaration is what the registry reads without rendering:
                the redraw union, the root/nested split, and cycle
                detection all walk these edges. Rendering a surface not
                named here is an authoring error. Empty tuple means the
                panel is a *leaf*.
        redraw_on: Tuple of Signal subclasses the panel wants its host
                editor to redraw on. Panels do not have their own handler
                dispatch — when one of these signals publishes, the editor
                redraws (and the panel re-mounts as part of that redraw).
                Empty tuple means the panel contributes no subscriptions.
        access: Minimum AccessTier a principal needs to see this panel.
                Below it, the panel is filtered out of visible_panels() —
                it vanishes rather than rendering disabled, and never
                renders ``draw_disabled()`` either. Default VIEW, i.e.
                visible to every authenticated principal.
    """

    icon: Optional[str] = None
    order: int = 100
    default_open: bool = True
    surface: Optional[type["Surface"]] = None
    hosts: Tuple[type["Surface"], ...] = ()
    redraw_on: Tuple[type["Signal"], ...] = ()
    access: AccessTier = AccessTier.VIEW
