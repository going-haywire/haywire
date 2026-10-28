"""Opening a macro for editing, and entering a macro placement.

Entering a placement opens its live interior as a locked level that cannot be
unlocked. A Group's interior opens as an ordinary level. The macro document
opens for editing only when its library is editable (decision 18).
"""

import json
from typing import Any, cast

import pytest

pytestmark = pytest.mark.integration

_INPUT = "haywire-core:node:SubgraphInputNode"
_OUTPUT = "haywire-core:node:SubgraphOutputNode"
_MACRO = "testlib:macro:Blur"


def _identity(folder_path):
    from haywire.core.library.identity import LibraryIdentity

    return LibraryIdentity(label="testlib", name="testlib", folder_path=folder_path, module_name="testlib")


def _document():
    return {
        "format_version": 1,
        "meta": {"values": {"description": ""}, "promoted": {}},
        "nodes": {
            "b_in": {"node_id": "b_in", "registry_key": _INPUT},
            "b_out": {"node_id": "b_out", "registry_key": _OUTPUT},
        },
        "edges": {},
        "variables": {},
        "props": {},
        "subgraphs": {},
    }


@pytest.fixture
def macro_file(tmp_path, library_system):
    path = tmp_path / "Blur.hwm"
    path.write_text(json.dumps(_document()))
    registry = library_system.get_macro_registry()
    identity = _identity(str(tmp_path))
    registry.add_folder(str(tmp_path), identity)
    try:
        yield path, registry
    finally:
        registry.remove_folder(str(tmp_path), identity)


def test_a_placement_reports_the_document_it_came_from(macro_file, graph_with_library_system):
    """'Edit Macro…' needs the file behind the card."""
    from haywire.core.macro.source import macro_source_path
    from tests.conftest import make_node

    path, _registry = macro_file
    card = make_node(graph_with_library_system, _MACRO)

    assert macro_source_path(card.node.wrapper.registry_key) == path


def test_an_unregistered_key_has_no_source(library_system):
    from haywire.core.macro.source import macro_source_path

    assert macro_source_path("absent-lib:macro:Gone") is None


def test_a_node_key_has_no_macro_source(library_system):
    """The lookup is macro-only; a node's source is the source editor's business."""
    from haywire.core.macro.source import macro_source_path

    assert macro_source_path("haybale-testing:node:TestAddFloatNode") is None


def test_a_macro_from_an_uninstalled_library_is_not_editable(library_system):
    """Decision 18: refuse with the reason rather than opening nothing."""
    from haywire.core.macro.source import macro_edit_refusal

    refusal = macro_edit_refusal("absent-lib:macro:Gone", library_system)

    assert refusal is not None
    assert "absent-lib" in refusal


def test_an_editable_library_is_not_refused(macro_file, library_system, monkeypatch):
    """A macro whose library is a -e install opens for editing."""
    from haywire.core.library.install_type import InstallType
    from haywire.core.macro import source as source_module

    monkeypatch.setattr(
        source_module,
        "_install_type_of",
        lambda lib_id, system: InstallType.EDITABLE,
    )

    assert source_module.macro_edit_refusal(_MACRO, library_system) is None


def test_a_site_packages_library_is_refused_with_its_reason(macro_file, library_system, monkeypatch):
    from haywire.core.library.install_type import InstallType
    from haywire.core.macro import source as source_module

    monkeypatch.setattr(
        source_module,
        "_install_type_of",
        lambda lib_id, system: InstallType.REGULAR,
    )

    refusal = source_module.macro_edit_refusal(_MACRO, library_system)

    assert refusal is not None
    assert "installed" in refusal.lower()


def test_a_placement_is_descendable(macro_file, graph_with_library_system):
    """Entering a placement opens its live interior as a level."""
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from haybale_graph_editor.editors.graph_editor import DOCUMENT_LEVEL, GraphEditor
    from haywire.core.access import AccessTier
    from haywire.core.macro.source import is_macro_placement
    from tests.conftest import make_node

    graph = graph_with_library_system
    card = make_node(graph, _MACRO)
    assert is_macro_placement(card.node) is True
    definition = cast(Any, card.node).resolve_definition()
    assert definition is not None

    document = MagicMock()
    document.editor.graph = graph
    document.binding_id = "doc"
    wrapper = MagicMock()
    wrapper._binding_id = "doc"
    editor = GraphEditor(wrapper)
    editor._project_state = SimpleNamespace(node_factory=MagicMock())  # type: ignore[assignment]
    context = SimpleNamespace(
        principal=None,
        session_id="test",
        app_data=MagicMock(),
        session=MagicMock(),
        data=MagicMock(),
        can_edit=lambda: True,
        can_access=AccessTier.ADMIN.satisfies,
    )
    editor._levels[DOCUMENT_LEVEL] = editor._new_level(context, DOCUMENT_LEVEL, document)  # type: ignore[arg-type]
    for name in (
        "_mount_level",
        "_teardown_level",
        "_render_level_bar",
        "_update_header",
        "_claim_session_state",
    ):
        setattr(editor, name, MagicMock())

    assert editor.descend_into(context, card.node_id) is True  # type: ignore[arg-type]

    level = editor._levels[editor._active_level]
    assert level.container.definition is definition  # type: ignore[attr-defined]
    assert level.locked is True


def test_a_group_card_is_not_a_placement(graph_with_library_system):
    """A Group card is not a placement; its Subgraph opens as an ordinary level."""
    from haywire.barn.builtin.nodes.graph_node import GraphNode
    from haywire.core.graph.scheduler import SyncScheduler
    from haywire.core.graph.subgraph import SubgraphDefinition
    from haywire.core.macro.source import is_macro_placement
    from tests.conftest import make_node

    graph = graph_with_library_system
    graph.add_subgraph(SubgraphDefinition(key="g1", label="G", validation_scheduler=SyncScheduler()))
    card = make_node(graph, "haywire-core:node:GraphNode")
    cast(GraphNode, card.node).bind_subgraph("g1")

    assert is_macro_placement(card.node) is False


def test_an_ordinary_node_is_not_a_placement(graph_with_library_system):
    from haywire.core.macro.source import is_macro_placement
    from tests.conftest import make_node

    card = make_node(graph_with_library_system, "haybale-testing:node:TestAddFloatNode")

    assert is_macro_placement(card.node) is False
