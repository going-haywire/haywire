"""Surfaces declared by the graph editor.

One file per surface (or per closely-related family), holding the surface and
the Protocol it names in ``provides`` — a convention, not machinery. A
surface's Protocol is its demand on whatever hosts it, and nothing inherits
one, so every surface states its own (docs/adr/0029-surface-model.md).
"""

from .edge import EdgeActions, EdgeInspector, EdgeMenu
from .graph import GraphInspector
from .graph_context import (
    GraphActions,
    GraphContext,
    GraphContextBody,
    GraphMoreActions,
    GraphToolBar,
)
from .node import NodeInspector, SettingsInspector
from .pin import PinMenu, PortActions
from .ports import PortInspector
from .selection import SelectionActions, SelectionMenu, SelectionRebuildMenu
from .toolbar import NodeAppearance, SelectionToolbar

__all__ = [
    "EdgeActions",
    "EdgeInspector",
    "EdgeMenu",
    "GraphActions",
    "GraphContext",
    "GraphContextBody",
    "GraphInspector",
    "GraphMoreActions",
    "GraphToolBar",
    "NodeAppearance",
    "NodeInspector",
    "PinMenu",
    "PortActions",
    "PortInspector",
    "SelectionActions",
    "SelectionMenu",
    "SelectionRebuildMenu",
    "SelectionToolbar",
    "SettingsInspector",
]
