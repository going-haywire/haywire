"""Action contracts for context-menu host (SessionContextMenuProvider).

Five Protocols, one per right-click context. Each Protocol declares only
the verbs valid in that context. The provider implements all five
structurally on a single class.

Phase 1.5 of the panel-contract migration. See
internals/superpowers/plans/2026-05-04-panel-contract-phase-1-5.md.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class CanvasContextActions(Protocol):
    """Verbs available when the user right-clicks on empty canvas space."""

    def create_node_at_click(self, registry_key: str) -> None: ...
    def paste_at_click(self) -> None: ...


@runtime_checkable
class NodeContextActions(Protocol):
    """Verbs available when the user right-clicks on a node."""

    def delete_node(self, node_id: str) -> None: ...
    def copy_node(self, node_id: str) -> None: ...
    def redraw_node(self, node_id: str) -> None: ...
    def revalidate_node(self, node_id: str) -> None: ...
    def reset_node(self, node_id: str) -> None: ...


@runtime_checkable
class EdgeContextActions(Protocol):
    """Verbs available when the user right-clicks on an edge."""

    def delete_edge(self, edge_id: str) -> None: ...
    def reconnect_active_edge(self) -> None: ...


@runtime_checkable
class SelectionContextActions(Protocol):
    """Verbs available when the user right-clicks on a multi-element selection."""

    def copy_selection(self) -> None: ...
    def paste_at_click(self) -> None: ...


@runtime_checkable
class PortContextActions(Protocol):
    """Marker Protocol for port-context panels.

    Empty by design — the only built-in port-context panel today is
    PortInfoPanel, which is display-only. Library authors can declare
    additional verbs here as needed.
    """
