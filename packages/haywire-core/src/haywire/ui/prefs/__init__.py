# haywire/ui/prefs/__init__.py
"""
Edge-appearance preferences.

The convention elsewhere is that a ``FrameworkSettings`` schema lives beside
the subsystem it configures (``core/undo/settings.py``,
``ui/components/zoom/settings.py``, …). This package is what remains of an
older catch-all grouping; ``EdgeUISettings`` should move next to the edge
rendering code, at which point the package goes away.

Panels render these by schema, not by DI lookup:

    render_schema(EdgeUISettings, registry)
"""

from .edge_ui import EdgeUISettings

__all__ = [
    "EdgeUISettings",
]
