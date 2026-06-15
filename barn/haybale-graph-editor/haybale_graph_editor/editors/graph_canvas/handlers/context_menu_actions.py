"""Action contracts for context-menu host (SessionContextMenuProvider).

Five Protocols, one per right-click context. Each Protocol declares only
the verbs valid in that context. The provider implements all five
structurally on a single class.
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
    """Marker Protocol for the skin/ extension point (on_custom_context).

    Empty by design — library authors register panels against this Protocol
    to surface them in menus triggered via data-hw-custom-menu-focus-id DOM
    attributes. The provider dispatches to NodeContextActions by default;
    panels that need a narrower scope declare a custom Focus instead.
    Mirrors PortContextActions.
    """


@runtime_checkable
class EdgeContextActions(Protocol):
    """Verbs available when the user right-clicks on an edge."""

    def delete_edge(self, edge_id: str) -> None: ...
    def reconnect_active_edge(self) -> None: ...


@runtime_checkable
class SelectionContextActions(Protocol):
    """Verbs available when the user right-clicks on a selection (one or many).

    The single command-menu Protocol after node/selection unification: every
    right-click command goes through here and acts on the whole selection
    (EditState.selected_nodes / selected_edges). The batch node verbs
    (redraw/revalidate/reset) emit the list-form Element* events.
    """

    def copy_selection(self) -> None: ...
    def paste_at_click(self) -> None: ...
    def delete_selection(self) -> None: ...
    def redraw_selection(self) -> None: ...
    def revalidate_selection(self) -> None: ...
    def reset_selection(self) -> None: ...


@runtime_checkable
class ToolbarActions(Protocol):
    """Verbs the floating toolbar's curated face invokes.

    The toolbar reuses SelectionContextActions for Copy/Delete (the provider
    implements both Protocols structurally). This Protocol adds only the
    toolbar-specific verb: opening the ⋯ overflow, which reaches back into the
    SelectionFocus right-click menu.
    """

    def open_overflow_menu(self) -> None: ...


@runtime_checkable
class PortContextActions(Protocol):
    """Marker Protocol for port-context panels.

    Empty by design — the only built-in port-context panel today is
    PortInfoPanel, which is display-only. Library authors can declare
    additional verbs here as needed.
    """
