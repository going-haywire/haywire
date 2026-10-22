"""Surfaces declared by the graph editor.

One file per surface (or per closely-related family), holding the surface and
the Protocol it names in ``provides`` — a convention, not machinery. A
surface's Protocol is its demand on whatever hosts it, and nothing inherits
one, so every surface states its own (docs/adr/0029-surface-model.md).
"""

from haybale_graph_editor.surfaces.edge import EdgeActions, EdgeEditMenu, EdgeInspector, EdgeMenu, EdgeStyle
from haybale_graph_editor.surfaces.graph import GraphInspector
from haybale_graph_editor.surfaces.graph_context import (
    GraphActions,
    GraphContext,
    GraphContextBody,
    GraphMoreActions,
    GraphToolBar,
)
from haybale_graph_editor.surfaces.node import NodeInspector, SettingsInspector
from haybale_graph_editor.surfaces.pin import PinEditMenu, PinMenu, PinWidgetMenu, PortActions
from haybale_graph_editor.surfaces.ports import PortInspector
from haybale_graph_editor.surfaces.selection import (
    SelectionActions,
    SelectionArrangeMenu,
    SelectionDetailMenu,
    SelectionEditMenu,
    SelectionMenu,
    SelectionRebuildMenu,
)
from haybale_graph_editor.surfaces.toolbar import NodeAppearance, SelectionToolbar

__all__ = [
    "EdgeActions",
    "EdgeEditMenu",
    "EdgeInspector",
    "EdgeMenu",
    "EdgeStyle",
    "GraphActions",
    "GraphContext",
    "GraphContextBody",
    "GraphInspector",
    "GraphMoreActions",
    "GraphToolBar",
    "NodeAppearance",
    "NodeInspector",
    "PinEditMenu",
    "PinMenu",
    "PinWidgetMenu",
    "PortActions",
    "PortInspector",
    "SelectionActions",
    "SelectionArrangeMenu",
    "SelectionMenu",
    "SelectionRebuildMenu",
    "SelectionDetailMenu",
    "SelectionEditMenu",
    "SelectionToolbar",
    "SettingsInspector",
]
