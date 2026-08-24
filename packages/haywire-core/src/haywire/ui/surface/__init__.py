# packages/haywire-core/src/haywire/ui/surface/__init__.py
"""Surface system for the Haywire UI framework.

A Surface is a place Panels appear: a properties tab, a context menu, a
region within one, a flyout. See docs/adr/0029-surface-model.md for the full
model. This package provides only the Surface ABC, its Presentation chrome
dataclass, and registry lookups (surface_by_id / all_surfaces). Panels
reference surfaces via ``@panel(surface=…, hosts=…)`` and render them with
``BasePanel.render_surface`` — both live in ``haywire.ui.panel``, which
imports this package; never the reverse.
"""

from .presentation import Presentation
from .surface import Surface
from .tree import all_surfaces, surface_by_id

__all__ = [
    "Surface",
    "Presentation",
    "surface_by_id",
    "all_surfaces",
]
