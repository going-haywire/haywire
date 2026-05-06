"""ContextMenuActions Protocols are runtime_checkable; structural impl satisfies them."""

from haybale_studio.editors.graph_canvas.handlers.context_menu_actions import (
    CanvasContextActions,
    EdgeContextActions,
    NodeContextActions,
    PortContextActions,
    SelectionContextActions,
)


class _CompleteImpl:
    """Implements every Protocol — used to verify isinstance against all five."""

    def create_node_at_click(self, registry_key: str) -> None: ...
    def paste_at_click(self) -> None: ...
    def delete_node(self, node_id: str) -> None: ...
    def copy_node(self, node_id: str) -> None: ...
    def redraw_node(self, node_id: str) -> None: ...
    def revalidate_node(self, node_id: str) -> None: ...
    def reset_node(self, node_id: str) -> None: ...
    def delete_edge(self, edge_id: str) -> None: ...
    def reconnect_active_edge(self) -> None: ...
    def copy_selection(self) -> None: ...


def test_canvas_context_actions_is_runtime_checkable():
    assert isinstance(_CompleteImpl(), CanvasContextActions)


def test_node_context_actions_is_runtime_checkable():
    assert isinstance(_CompleteImpl(), NodeContextActions)


def test_edge_context_actions_is_runtime_checkable():
    assert isinstance(_CompleteImpl(), EdgeContextActions)


def test_selection_context_actions_is_runtime_checkable():
    assert isinstance(_CompleteImpl(), SelectionContextActions)


def test_port_context_actions_is_empty_marker_protocol():
    """PortContextActions has no methods; any class satisfies it."""

    class Anything:
        pass

    assert isinstance(Anything(), PortContextActions)


def test_partial_impl_does_not_satisfy_full_protocol():
    """A class missing methods does not satisfy a Protocol that requires them."""

    class _PartialImpl:
        def delete_node(self, node_id: str) -> None: ...

    assert not isinstance(_PartialImpl(), NodeContextActions)
