# packages/haywire-core/src/haywire/ui/panel/__init__.py
"""
Panel system for the Haywire UI framework.

A Panel names one :class:`~haywire.ui.surface.Surface` via ``@panel(surface=…)``,
adds its own ``poll()``, and draws. A Panel may also *host* surfaces of its
own, declaring them with ``hosts=`` and rendering one with
``self.render_surface(S, ctx)`` — so one recursive rule (host → surface →
panel → host → …) covers menus, submenus, toolbars and inspector tabs alike
(docs/adr/0029-surface-model.md).

Three registry queries, all routing on ``Surface.id``:
  - PanelRegistry.get_panels(surface): the panels on one surface.
  - PanelRegistry.get_root_surfaces(): surfaces no panel hosts.
  - PanelRegistry.get_redraw_signals(surface): the ``redraw_on`` union across
    that surface's whole ``hosts=`` tree.
"""

from .identity import PanelIdentity
from .layout import PanelLayout
from .base import BasePanel
from .registry import PanelRegistry
from .redraw_coordinator import PanelRedrawCoordinator

# Import decorator last so the `panel` name resolves to the decorator function
# rather than the `.panel` submodule (the `from .panel import BasePanel` above
# binds `panel` as a submodule attribute on the package; importing the
# decorator after that shadows it back to the function).
from .decorator import panel  # noqa: E402

__all__ = [
    "PanelIdentity",
    "PanelLayout",
    "base",
    "BasePanel",
    "PanelRegistry",
    "PanelRedrawCoordinator",
    "panel",
]
