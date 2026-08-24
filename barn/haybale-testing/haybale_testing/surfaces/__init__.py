"""Test-only surfaces and their Protocols.

Mirror the production surfaces with test-specific ids so test fixtures never
appear on a production surface. One file per surface, holding the surface and
the Protocol it names in ``provides``.
"""

from .canvas import TestCanvasActions, TestCanvasMenu
from .edge import TestEdgeActions, TestEdgeMenu
from .node import TestNodeActions, TestNodeMenu
from .selection import TestSelectionActions, TestSelectionMenu

__all__ = [
    "TestCanvasActions",
    "TestCanvasMenu",
    "TestEdgeActions",
    "TestEdgeMenu",
    "TestNodeActions",
    "TestNodeMenu",
    "TestSelectionActions",
    "TestSelectionMenu",
]
