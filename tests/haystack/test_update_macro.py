"""Update Macro…: a modified instance goes back to its macro, carrying its changes.

The card is swapped for a placement at once, as one undoable step. The macro's
own document opens in a macro tab holding the instance's contents, unsaved; the
user's Save writes the file, and the reload brings every placement up to date.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from haywire.core.graph.scheduler import SyncScheduler

from tests.conftest import make_node
from tests.core.test_macro.test_macro_reload import _ADD, _MACRO, _identity, _modified
from tests.core.test_macro.test_macro_reload import _document as _reload_document

pytestmark = pytest.mark.integration

_CARD = "haywire-core:node:GraphNode"
_PRINT = "haybale-testing:node:TestPrintNode"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _document(graph, interface_ports=("gain",)):
    """A macro document over ``interface_ports``, in the format a studio save writes."""
    document = _reload_document(graph, interface_ports=interface_ports)
    # The reload tests' flat ``meta`` is one the registry reads but a graph cannot load.
    document.pop("meta", None)
    return document


@pytest.fixture
def macro_file(tmp_path, library_system, graph_with_library_system):
    """One registered macro ``Blur`` with one interface port; yields (path, identity, registry)."""
    folder = tmp_path / "macros"
    folder.mkdir()
    path = folder / "Blur.hwm"
    path.write_text(json.dumps(_document(graph_with_library_system)))
    registry = library_system.get_macro_registry()
    identity = _identity(str(folder))
    registry.add_folder(str(folder), identity)
    try:
        yield path, identity, registry
    finally:
        registry.remove_folder(str(folder), identity)


@pytest.fixture
def haystack(library_system, tmp_path):
    """A HaystackState over the real node factory, with a graph registry."""
    from haybale_graph_editor.state.graph_app_state import GraphAppState
    from haybale_haystack.state.haystack_state import HaystackState

    state = HaystackState()
    state._dispatcher = MagicMock()
    state._dispatcher.return_value = state._dispatcher
    state._workspace_root = tmp_path
    state._node_factory = library_system.get_node_factory()
    state._graph_app_state = GraphAppState()
    yield state
    for entry in state.all_entries():
        state.remove_entry(entry)


def _open_graph(haystack, folder: Path, name: str):
    """Open an empty ``.haywire`` file as a haystack graph."""
    from haywire.core.graph.base import BaseGraph

    path = folder / f"{name}.haywire"
    BaseGraph(filestem=name).save_to_file(str(path))
    return haystack.open_graph(path)


def _modified_instance(entry, *, grow_pin: bool = False):
    """Place the macro in ``entry``, detach it, and change the instance.

    Adds an interior node, and with ``grow_pin`` an interface port ``radius``
    wired from a host node. Returns ``(card_id, added_node_id)``.
    """
    from haywire.barn.builtin.types import FLOAT

    graph, editor = entry.graph, entry.editor
    placement = make_node(graph, _MACRO)
    graph.force_validation()
    card_id, refusal = editor.detach_placement_from_macro(placement.node_id, _CARD)
    assert refusal is None
    card = graph.get_node_wrapper(card_id)
    interior = card.node.resolve_definition()
    added = make_node(interior, _PRINT)
    if grow_pin:
        boundary_in = interior.input_node.node
        with boundary_in.rejig(include=[]):
            boundary_in.add(FLOAT.as_outlet("radius", label="Radius"))
        interior.force_validation()
        graph.force_validation()
        assert "in_radius" in card.node.ports
        producer = make_node(graph, _ADD)
        graph.create_edge_wrapper(producer.node_id, "result", card_id, "in_radius")
    graph.force_validation()
    return card_id, added.node_id


def _ctx(haystack, entry, card_id):
    """A session with the instance's card active on ``entry``'s canvas."""
    from haybale_graph_editor.state.edit_state import EditState
    from haybale_graph_editor.state.graph_app_state import GraphAppState
    from haybale_haystack.state.haystack_state import HaystackState
    from haybale_graph_editor.access import level_mode
    from haywire.core.access import LevelMode
    from haywire.core.graph.edit_route import EditRoute

    edit = MagicMock()
    edit.active_graph = entry.graph
    edit.active_node = entry.graph.get_node_wrapper(card_id)
    edit.active_mode = LevelMode.EDIT
    # The level's route, reading the session's tier as a graph editor level does.
    edit.active_route = EditRoute(lambda: entry.editor, lambda: level_mode(ctx.can_access, False))
    edit.selected_nodes = {card_id}
    ctx = MagicMock()
    ctx.data = {EditState: edit}
    ctx.app_data = {HaystackState: haystack, GraphAppState: haystack._graph_app_state}
    ctx.can_access.return_value = True
    return ctx


def _editable():
    """Treat the test library as an editable install."""
    return patch("haywire.core.macro.source.macro_edit_refusal", return_value=None)


def _update(ctx, card_id):
    """Click Update Macro…, with ``ui`` mocked out; returns the ``ui.notify`` mock."""
    from haybale_haystack.panels.graph.menu.macro import _update_macro

    with (
        _editable(),
        patch("nicegui.ui.notify") as notify,
        patch("nicegui.ui.context"),
    ):
        _update_macro(ctx, card_id)
    return notify


def _placements(graph):
    from haywire.core.macro.source import is_macro_placement

    return [
        w for w in graph.node_wrappers.values() if w.registry_key == _MACRO and is_macro_placement(w.node)
    ]


# ---------------------------------------------------------------------------
# open_macro_with
# ---------------------------------------------------------------------------


def test_open_macro_with_opens_unsaved_with_the_document(haystack, macro_file, graph_with_library_system):
    from haybale_haystack.graph_entry import EntryKind

    path, _, _ = macro_file
    document = _document(graph_with_library_system, interface_ports=("gain", "radius"))
    on_disk = path.read_text()

    entry = haystack.open_macro_with(path, document)

    assert entry.kind is EntryKind.MACRO
    assert entry.unsaved is True
    assert entry.path == path
    assert haystack.get_by_path(path) is entry
    assert "radius" in entry.graph.get_node_wrapper(_input_id(entry.graph)).node.ports
    assert path.read_text() == on_disk, "nothing is written until the user saves"


def _input_id(graph):
    return next(
        nid for nid, w in graph.node_wrappers.items() if w.registry_key.endswith("SubgraphInputNode")
    )


def test_open_macro_with_replaces_a_clean_open_entry(haystack, macro_file, graph_with_library_system):
    from haywire.core.graph.types import ChangeReason

    path, _, _ = macro_file
    entry = haystack.open_macro(path)
    make_node(entry.graph, _PRINT)
    entry.graph.force_validation()
    entry.unsaved = False
    assert entry.editor.history_manager is not None
    # The canvas of an open tab learns of content through the graph's validation.
    seen: list = []
    entry.graph.subscribe_to_validation(seen.append)
    document = _document(graph_with_library_system, interface_ports=("gain", "radius"))
    haystack._dispatcher.broadcast.reset_mock()

    reopened = haystack.open_macro_with(path, document)
    entry.graph.force_validation()

    assert reopened is entry
    assert entry.unsaved is True
    assert entry.editor.history_manager.can_undo() is False
    assert set(entry.graph.node_wrappers) == set(document["nodes"])
    added = {nid for r in seen for nid, reason in r.nodes.items() if reason == ChangeReason.NODE_ADDED}
    assert set(document["nodes"]) <= added, "an open canvas is told about every new node"
    broadcast = {type(call.args[0]).__name__ for call in haystack._dispatcher.broadcast.call_args_list}
    assert {"GraphUnsavedChanged", "GraphDataMutated"} <= broadcast


def test_open_macro_with_refuses_an_unsaved_entry(haystack, macro_file, graph_with_library_system):
    path, _, _ = macro_file
    entry = haystack.open_macro(path)
    entry.unsaved = True
    before = set(entry.graph.node_wrappers)

    with pytest.raises(ValueError, match="unsaved edits"):
        haystack.open_macro_with(path, _document(graph_with_library_system))

    assert set(entry.graph.node_wrappers) == before


def test_saving_an_entry_opened_with_a_document_writes_its_path(
    haystack, macro_file, graph_with_library_system
):
    path, _, _ = macro_file
    entry = haystack.open_macro_with(path, _document(graph_with_library_system, ("gain", "radius")))

    assert haystack._save_entry(entry) is None

    assert entry.unsaved is False
    assert "radius" in path.read_text()


# ---------------------------------------------------------------------------
# The verb
# ---------------------------------------------------------------------------


def test_update_swaps_the_card_and_opens_the_document(haystack, macro_file, tmp_path):
    from haybale_graph_editor.editors.graph_editor import GraphEditor
    from haywire.core.signals import Reveal

    path, _, _ = macro_file
    host = _open_graph(haystack, tmp_path, "host")
    card_id, added_id = _modified_instance(host)
    ctx = _ctx(haystack, host, card_id)

    notify = _update(ctx, card_id)

    assert host.graph.get_node_wrapper(card_id) is None
    assert len(_placements(host.graph)) == 1
    assert host.editor.history_manager.get_undo_description() == "Update Macro"
    entry = haystack.get_by_path(path)
    assert entry is not None
    assert entry.unsaved is True
    assert added_id in entry.graph.node_wrappers
    reveal = ctx.session.publish.call_args.args[0]
    assert isinstance(reveal, Reveal)
    assert reveal.editor is GraphEditor
    assert reveal.binding_id == entry.binding_id
    messages = [call.args[0] for call in notify.call_args_list]
    assert messages == ["Save Blur to update 1 placements in 1 open graphs."]


def test_update_warns_when_the_macro_changed_since_the_detach(haystack, macro_file, tmp_path):
    path, _, _ = macro_file
    host = _open_graph(haystack, tmp_path, "host")
    card_id, _ = _modified_instance(host)
    definition = host.graph.get_node_wrapper(card_id).node.resolve_definition()
    from haywire.core.macro.origin import MacroOrigin

    definition.origin = MacroOrigin(key=_MACRO, hash="an older version")

    notify = _update(_ctx(haystack, host, card_id), card_id)

    warnings = [c.args[0] for c in notify.call_args_list if c.kwargs.get("type") == "warning"]
    assert warnings == ["Blur changed since this instance was made; saving replaces those changes."]


def test_update_is_refused_below_edit(haystack, macro_file, tmp_path):
    path, _, _ = macro_file
    host = _open_graph(haystack, tmp_path, "host")
    card_id, _ = _modified_instance(host)
    ctx = _ctx(haystack, host, card_id)
    ctx.can_access.return_value = False

    _update(ctx, card_id)

    assert host.graph.get_node_wrapper(card_id) is not None
    assert haystack.get_by_path(path) is None


def test_update_is_refused_while_the_macro_tab_is_unsaved(haystack, macro_file, tmp_path):
    """The row can be stale: the click re-checks, and nothing changes."""
    path, _, _ = macro_file
    host = _open_graph(haystack, tmp_path, "host")
    card_id, _ = _modified_instance(host)
    tab = haystack.open_macro(path)
    tab.unsaved = True
    before = set(tab.graph.node_wrappers)

    notify = _update(_ctx(haystack, host, card_id), card_id)

    assert host.graph.get_node_wrapper(card_id) is not None
    assert set(tab.graph.node_wrappers) == before
    assert notify.call_args.args[0] == "Blur has unsaved edits in its macro tab. Save them first."


def _prints(card) -> int:
    """Print nodes in a placement's interior; a placement re-keys the template's node ids."""
    interior = card.node.resolve_definition()
    return sum(1 for w in interior.node_wrappers.values() if w.registry_key == _PRINT)


def test_saving_the_opened_document_updates_the_placements(haystack, macro_file, tmp_path):
    from haywire.core.macro.source import is_macro_placement

    path, identity, registry = macro_file
    host = _open_graph(haystack, tmp_path, "host")
    other = _open_graph(haystack, tmp_path, "other")
    sibling = make_node(other.graph, _MACRO)
    other.graph.force_validation()
    card_id, _ = _modified_instance(host)
    assert _prints(sibling) == 0

    _update(_ctx(haystack, host, card_id), card_id)
    (placement,) = _placements(host.graph)
    assert _prints(placement) == 0, "before the save, the placement is the macro as it stands"
    entry = haystack.get_by_path(path)
    assert haystack._save_entry(entry) is None
    _modified(registry, path, identity)

    assert is_macro_placement(sibling.node)
    assert _prints(sibling) == 1, "the instance's added node reached the other graph"
    assert _prints(placement) == 1


def test_an_added_wired_pin_is_connected_after_the_save(haystack, macro_file, tmp_path):
    """The swap precedes the save, so the edge waits on a pin the reload brings.

    The host validates inline, so the card's structural flag is cleared inside
    each pass and the reload's new pin is still validated.
    """
    path, identity, registry = macro_file
    host = _open_graph(haystack, tmp_path, "host")
    other = _open_graph(haystack, tmp_path, "other")
    sibling = make_node(other.graph, _MACRO)
    other.graph.force_validation()
    card_id, _ = _modified_instance(host, grow_pin=True)
    host.graph._validation._scheduler = SyncScheduler()

    _update(_ctx(haystack, host, card_id), card_id)
    host.graph.force_validation()
    (before,) = [e for e in host.graph.edge_wrappers.values()]
    assert before.state.error_formal is not None, "the placement lacks the pin until the save"
    entry = haystack.get_by_path(path)
    assert haystack._save_entry(entry) is None
    _modified(registry, path, identity)
    host.graph.force_validation()

    (placement,) = _placements(host.graph)
    assert "in_radius" in placement.node.ports
    assert "in_radius" in sibling.node.ports
    (edge,) = [e for e in host.graph.edge_wrappers.values() if e.sink_node_id == placement.node_id]
    assert edge.inlet_port_id == "in_radius"
    assert not edge.state.error_formal
    assert edge.is_valid()


# ---------------------------------------------------------------------------
# The row
# ---------------------------------------------------------------------------


def _drawn_row(ctx):
    from haybale_haystack.panels.graph.menu.macro import UpdateMacroMenuPanel

    panel = UpdateMacroMenuPanel.__new__(UpdateMacroMenuPanel)
    panel.actions = MagicMock()  # type: ignore[attr-defined]
    with patch("haybale_haystack.panels.graph.menu.macro.hui.menu_row") as row:
        panel.draw(ctx, MagicMock())
    return row


def test_update_row_shows_only_on_a_modified_instance(haystack, macro_file, tmp_path):
    from haybale_haystack.panels.graph.menu.macro import UpdateMacroMenuPanel

    host = _open_graph(haystack, tmp_path, "host")
    placement = make_node(host.graph, _MACRO)
    host.graph.force_validation()
    card_id, _ = _modified_instance(host)

    assert UpdateMacroMenuPanel.class_identity.order == 40
    assert UpdateMacroMenuPanel.poll(_ctx(haystack, host, card_id)) is True
    assert UpdateMacroMenuPanel.poll(_ctx(haystack, host, placement.node_id)) is False


def test_update_row_acts_on_an_editable_macro(haystack, macro_file, tmp_path):
    host = _open_graph(haystack, tmp_path, "host")
    card_id, _ = _modified_instance(host)

    with _editable():
        row = _drawn_row(_ctx(haystack, host, card_id))

    assert row.call_args.args[0] == "Update Macro…"
    assert row.call_args.kwargs.get("enabled", True) is True


def test_update_row_disabled_while_the_macro_tab_is_unsaved(haystack, macro_file, tmp_path):
    path, _, _ = macro_file
    host = _open_graph(haystack, tmp_path, "host")
    card_id, _ = _modified_instance(host)
    haystack.open_macro(path).unsaved = True

    with _editable():
        row = _drawn_row(_ctx(haystack, host, card_id))

    assert row.call_args.args[0] == "Update Macro…"
    assert row.call_args.kwargs["enabled"] is False
    assert row.call_args.kwargs["tooltip"] == "Blur has unsaved edits in its macro tab. Save them first."


def test_update_row_disabled_on_a_read_only_install(haystack, macro_file, tmp_path):
    from haywire.core.library.install_type import InstallType
    from haywire.core.macro.source import macro_edit_refusal

    host = _open_graph(haystack, tmp_path, "host")
    card_id, _ = _modified_instance(host)
    library_system = MagicMock()
    library_system.get_library_registry.return_value.get_library_install_type.return_value = (
        InstallType.REGULAR
    )
    expected = macro_edit_refusal(_MACRO, library_system)
    assert expected is not None

    with patch("haywire.core.macro.source._install_type_of", return_value=InstallType.REGULAR):
        row = _drawn_row(_ctx(haystack, host, card_id))

    assert row.call_args.kwargs["enabled"] is False
    assert row.call_args.kwargs["tooltip"] == expected


def test_update_row_disabled_when_the_macro_is_gone(haystack, macro_file, tmp_path):
    path, identity, registry = macro_file
    host = _open_graph(haystack, tmp_path, "host")
    card_id, _ = _modified_instance(host)
    registry.remove_folder(str(path.parent), identity)
    try:
        with _editable():
            row = _drawn_row(_ctx(haystack, host, card_id))
    finally:
        registry.add_folder(str(path.parent), identity)

    assert row.call_args.kwargs["enabled"] is False
    assert row.call_args.kwargs["tooltip"] == "Blur is not installed."


def test_document_is_valid_json_for_the_registry(haystack, macro_file, tmp_path):
    """What Save writes parses as a macro: the reload does not refuse it."""
    path, identity, registry = macro_file
    host = _open_graph(haystack, tmp_path, "host")
    card_id, _ = _modified_instance(host)

    _update(_ctx(haystack, host, card_id), card_id)
    haystack._save_entry(haystack.get_by_path(path))
    _modified(registry, path, identity)

    json.loads(path.read_text())
    assert registry.get_lastevent(_MACRO).error is None
