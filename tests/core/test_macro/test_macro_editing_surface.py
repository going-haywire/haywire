"""Opening a macro for editing, and what happens when it cannot be opened.

Descending into a placement is refused (decision 12) — a placement's interior
is runtime state, and there is no read-only editor mode to show it in. The
macro document is opened instead, and only when its library is editable
(decision 18).
"""

import json
from typing import cast

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
        "meta": {"description": ""},
        "nodes": {
            "b_in": {"node_id": "b_in", "registry_key": _INPUT, "position": [0, 0]},
            "b_out": {"node_id": "b_out", "registry_key": _OUTPUT, "position": [200, 0]},
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


def test_a_placement_is_not_descendable(macro_file, graph_with_library_system):
    """Decision 12: a placement redirects to its document instead of descending."""
    from haywire.core.macro.source import is_macro_placement
    from tests.conftest import make_node

    card = make_node(graph_with_library_system, _MACRO)

    assert is_macro_placement(card.node) is True


def test_a_group_card_is_still_descendable(graph_with_library_system):
    """Only a placement redirects; a Group's own Subgraph opens as before."""
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
