"""Each surface's ``provides`` Protocol is runtime_checkable and states its own contract.

``render_surface`` validates a *chosen* host with ``isinstance``; it never
chooses one structurally. A Protocol that is not ``@runtime_checkable`` would
raise ``TypeError`` there — deep in a flyout, with no useful frame — which is
why ``Surface.__init_subclass__`` rejects one at class-definition time.
"""

from haybale_graph_editor.surfaces import (
    EdgeActions,
    GraphActions,
    PortActions,
    SelectionActions,
)


class _CompleteImpl:
    """Implements every Protocol — used to verify isinstance against all four."""

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
    def demote_setting(self, port_id: str) -> None: ...


def test_graph_actions_is_runtime_checkable():
    assert isinstance(_CompleteImpl(), GraphActions)


def test_edge_actions_is_runtime_checkable():
    assert isinstance(_CompleteImpl(), EdgeActions)


def test_selection_actions_is_runtime_checkable():
    assert isinstance(_CompleteImpl(), SelectionActions)


def test_port_actions_declares_the_demote_verb():
    """PortActions carries a real verb, which is why it survived the rename
    while the empty NodeContextActions marker did not."""

    class _PortImpl:
        def demote_setting(self, port_id: str) -> None: ...

    assert isinstance(_PortImpl(), PortActions)

    class _Missing:
        pass

    assert not isinstance(_Missing(), PortActions)


def test_no_empty_marker_protocol_survives():
    """NodeContextActions was an empty Protocol every object satisfied. It
    existed only to route the custom-menu attribute through the action fork,
    and that fork is gone — so nothing in the graph editor's surfaces can be
    satisfied by an arbitrary object."""

    class Anything:
        pass

    for protocol in (GraphActions, EdgeActions, SelectionActions, PortActions):
        assert not isinstance(Anything(), protocol), protocol.__name__


def test_selection_actions_includes_the_batch_verbs():
    class _SelImpl:
        def copy_selection(self) -> None: ...
        def paste_at_click(self) -> None: ...
        def delete_selection(self) -> None: ...
        def redraw_selection(self) -> None: ...
        def revalidate_selection(self) -> None: ...
        def reset_selection(self) -> None: ...
        def dissolve_reroute(self, node_id: str) -> None: ...

    assert isinstance(_SelImpl(), SelectionActions)


def test_selection_missing_a_batch_verb_does_not_satisfy_the_protocol():
    class _Partial:
        def copy_selection(self) -> None: ...
        def paste_at_click(self) -> None: ...
        def delete_selection(self) -> None: ...

        # missing redraw_selection / revalidate_selection / reset_selection

    assert not isinstance(_Partial(), SelectionActions)
