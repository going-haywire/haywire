"""Popup entry point and step→panel wiring for the New Node flow."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from haywire.ui.components.stepper import Panel, show_step_flow

from ._state import NewNodeFlow, NewNodeHost
from .panels import _panel_details, _panel_planned, _panel_result, _panel_source

if TYPE_CHECKING:
    from haywire.core.node.factory import NodeFactory
    from haywire.core.session.context import SessionContext


class EditorNewNodeHost:
    """Adapts the canvas and the session to :class:`NewNodeHost`.

    ``place`` takes the canvas position captured when the wizard opened: the
    right-click point, or a point beside the cloned node.
    """

    def __init__(
        self,
        context: "SessionContext",
        position: tuple[float, float],
        create_node: Callable[[str, tuple[float, float]], None],
    ) -> None:
        self._context = context
        self._position = position
        self._create_node = create_node

    def place(self, registry_key: str) -> None:
        self._create_node(registry_key, self._position)

    def reveal_component(self, registry_key: str) -> None:
        from haywire.core.signals import RevealComponentSource

        self._context.session.publish(RevealComponentSource(registry_key=registry_key))

    def open_file(self, path: Path) -> None:
        from haywire.core.signals import RevealSource

        self._context.session.publish(RevealSource(binding_id=str(path), label=path.name))


def new_node_flow(
    host: NewNodeHost,
    library_system: Any,
    node_factory: "NodeFactory",
    workspace_root: Path | None,
    *,
    source_cls: Any = None,
) -> NewNodeFlow:
    """Build the flow over the live registries, without opening it.

    Offers only watched authoring targets: the wizard waits for the file
    watcher to register what it writes.
    """
    from haywire.core.authoring import authoring_targets, list_clone_sources
    from haywire.core.errors.ledger import get_error_ledger
    from haywire.core.node.registry import NodeRegistry

    targets = [t for t in authoring_targets(library_system, NodeRegistry, workspace_root) if t.is_watched]
    menu = node_factory.get_menu_structure()
    visible = [info for infos in menu.values() for info in infos]
    registry = node_factory.node_registry
    return NewNodeFlow(
        host=host,
        targets=targets,
        libraries=library_system.get_library_registry(),
        registry=registry,
        ledger=get_error_ledger(),
        templates=node_factory.list_templates(),
        clone_sources=list_clone_sources(visible, registry.get),
        resolve=registry.get,
        menu_paths=list(menu),
        source_cls=source_cls,
    )


def show_new_node_flow(flow: NewNodeFlow, *, on_done: Callable[[], None] | None = None) -> NewNodeFlow:
    """Open ``flow`` in a popup and return it."""
    panels: dict[str, Panel[NewNodeFlow]] = {
        "source": _panel_source,
        "details": _panel_details,
        "planned": _panel_planned,
        "result": _panel_result,
    }
    flow.popup = show_step_flow(flow, panels, title="New Node", width="640px", on_done=on_done)
    return flow
