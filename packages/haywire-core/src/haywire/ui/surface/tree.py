# packages/haywire-core/src/haywire/ui/surface/tree.py
"""Registry lookups over the Surface id -> class map.

The one place a surface id arriving from outside the process (a skin's
``data-hw-menu-surface-id``) is resolved, and so the one place it may not
resolve — ``surface_by_id`` returns ``None`` and the caller logs.
"""

from __future__ import annotations

from haywire.ui.surface.surface import Surface, _SURFACE_BY_ID


def surface_by_id(id: str) -> type[Surface] | None:
    """Return the Surface subclass whose id matches id, or None."""
    return _SURFACE_BY_ID.get(id)


def all_surfaces() -> list[type[Surface]]:
    """Return all registered Surface subclasses."""
    return list(_SURFACE_BY_ID.values())
