# tests/ui/surface/_hot_reload_target.py
"""Dedicated reload target for surface hot-reload supersede tests.

Mirrors tests/core/test_signals/_hot_reload_target.py's role: a module whose
sole job is to be importlib.reload()'d so a test can assert the registry
picks up the fresh class object under the same id.
"""

from __future__ import annotations

from haywire.ui.surface.surface import Surface


class MySurface(Surface):
    id = "hot_reload_target_surface"
    order = 42

    @classmethod
    def poll(cls, ctx):
        return True
