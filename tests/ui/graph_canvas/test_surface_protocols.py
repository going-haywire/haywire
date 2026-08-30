"""Each surface's ``provides`` Protocol is runtime_checkable and states its own contract.

``render_surface`` validates a *chosen* host with ``isinstance``; it never
chooses one structurally. A Protocol that is not ``@runtime_checkable`` would
raise ``TypeError`` there — deep in a flyout, with no useful frame — which is
why ``Surface.__init_subclass__`` rejects one at class-definition time.
"""

from tests.protocol_stubs import protocol_verbs, stub_for

from haybale_graph_editor.surfaces import (
    EdgeActions,
    GraphActions,
    PortActions,
    SelectionActions,
)


def _complete():
    """An object satisfying all four Protocols, derived from them.

    Hand-listing these verbs meant every Protocol widening broke this file —
    four times while SelectionActions grew the ADR-0032 card verbs. Deriving
    them keeps the assertions about ``@runtime_checkable`` rather than about
    whether someone remembered to update a list.
    """
    return stub_for(GraphActions, EdgeActions, SelectionActions, PortActions)


def test_graph_actions_is_runtime_checkable():
    assert isinstance(_complete(), GraphActions)


def test_edge_actions_is_runtime_checkable():
    assert isinstance(_complete(), EdgeActions)


def test_selection_actions_is_runtime_checkable():
    assert isinstance(_complete(), SelectionActions)


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


def test_selection_actions_declares_the_batch_and_card_verbs():
    """The Protocol's membership, asserted against the Protocol itself.

    Previously a stub listing each verb, which only ever restated the class
    body it was checking. Naming the verbs here instead makes the assertion
    about the CONTRACT: removing one is a decision that fails a test, not a
    stub that quietly keeps passing.
    """
    verbs = protocol_verbs(SelectionActions)
    assert {
        "copy_selection",
        "paste_at_click",
        "delete_selection",
        "redraw_selection",
        "revalidate_selection",
        "reset_selection",
        "dissolve_reroute",
        # ADR 0032 card axes — every host of SelectionMenu must satisfy these.
        "set_selection_collapsed",
        "selection_is_collapsed",
        "toggle_selection_collapsed",
        "set_selection_detail",
        "clear_selection_detail_overrides",
    } <= verbs


def test_selection_missing_a_batch_verb_does_not_satisfy_the_protocol():
    class _Partial:
        def copy_selection(self) -> None: ...
        def paste_at_click(self) -> None: ...
        def delete_selection(self) -> None: ...

        # missing redraw_selection / revalidate_selection / reset_selection

    assert not isinstance(_Partial(), SelectionActions)


def test_both_hosts_of_selection_menu_satisfy_its_protocol():
    """SelectionMenu has TWO hosts: the context-menu provider and the toolbar,
    whose ⋯ renders the same surface.

    ``render_surface`` isinstance-checks the host against ``provides``, so a
    verb added to ``SelectionActions`` and implemented on only one of them does
    not fail at the missing row — it fails the whole menu, at the other host.
    The toolbar delegates rather than reimplements, so keeping up is one line
    per verb; forgetting it is silent until someone opens that ⋯.
    """
    from haybale_graph_editor.editors.graph_canvas.handlers.context_menu import (
        SessionContextMenuProvider,
    )
    from haybale_graph_editor.editors.graph_canvas.handlers.selection_toolbar import (
        SelectionToolbarProvider,
    )

    verbs = protocol_verbs(SelectionActions)
    assert verbs, "SelectionActions declares no verbs — this test would be vacuous"

    for host in (SessionContextMenuProvider, SelectionToolbarProvider):
        missing = sorted(v for v in verbs if not hasattr(host, v))
        assert not missing, (
            f"{host.__name__} does not implement {missing} from SelectionActions — "
            f"every host of SelectionMenu must satisfy it or the menu fails to render"
        )
