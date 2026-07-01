"""ContextMenuActions Protocols are runtime_checkable; structural impl satisfies them."""

from haybale_graph_editor.editors.graph_canvas.handlers.context_menu_actions import (
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
    def delete_edge(self, edge_id: str) -> None: ...
    def reconnect_active_edge(self) -> None: ...
    def split_edge_with_reroute(self, edge_id: str) -> None: ...
    def copy_selection(self) -> None: ...
    def delete_selection(self) -> None: ...
    def redraw_selection(self) -> None: ...
    def revalidate_selection(self) -> None: ...
    def reset_selection(self) -> None: ...
    def dissolve_reroute(self, node_id: str) -> None: ...
    def promote_setting(self, node_id: str, accessor: str, field: str) -> None: ...
    def demote_setting(self, port_id: str) -> None: ...


def test_canvas_context_actions_is_runtime_checkable():
    assert isinstance(_CompleteImpl(), CanvasContextActions)


def test_edge_context_actions_is_runtime_checkable():
    assert isinstance(_CompleteImpl(), EdgeContextActions)


def test_selection_context_actions_is_runtime_checkable():
    assert isinstance(_CompleteImpl(), SelectionContextActions)


def test_port_context_actions_declares_demote_verb():
    """PortContextActions declares demote_setting (backs the 'Detach from setting' panel)."""

    class _PortImpl:
        def demote_setting(self, port_id: str) -> None: ...

    assert isinstance(_PortImpl(), PortContextActions)

    class _Missing:
        pass

    assert not isinstance(_Missing(), PortContextActions)


def test_node_context_actions_is_empty_marker_protocol():
    """NodeContextActions has no methods; any class satisfies it (skin extension point)."""

    class Anything:
        pass

    assert isinstance(Anything(), NodeContextActions)


def test_selection_context_actions_includes_batch_verbs():
    """SelectionContextActions declares the batch verbs plus promote_setting."""

    class _SelImpl:
        def copy_selection(self) -> None: ...
        def paste_at_click(self) -> None: ...
        def delete_selection(self) -> None: ...
        def redraw_selection(self) -> None: ...
        def revalidate_selection(self) -> None: ...
        def reset_selection(self) -> None: ...
        def dissolve_reroute(self, node_id: str) -> None: ...
        def promote_setting(self, node_id: str, accessor: str, field: str) -> None: ...

    assert isinstance(_SelImpl(), SelectionContextActions)


def test_selection_missing_batch_verb_does_not_satisfy_protocol():
    """A class missing a batch verb does not satisfy SelectionContextActions."""

    class _Partial:
        def copy_selection(self) -> None: ...
        def paste_at_click(self) -> None: ...
        def delete_selection(self) -> None: ...

        # missing redraw_selection / revalidate_selection / reset_selection

    assert not isinstance(_Partial(), SelectionContextActions)
