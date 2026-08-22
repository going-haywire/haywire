"""Integration: loading a graph applies Compatibility Warnings to node state."""

import pytest

from haywire.core.graph.base import BaseGraph
from haywire.core.graph.scheduler import SyncScheduler
from haywire.core.library.compatibility import CompatibilityWarning

from tests.conftest import make_node


def _wrapper(graph, node_id):
    """``get_node_wrapper`` narrowed — a missing node is a broken precondition."""
    found = graph.get_node_wrapper(node_id)
    assert found is not None, f"no node wrapper {node_id!r}"
    return found


@pytest.mark.integration
def test_load_applies_node_compatibility_warning(library_system, monkeypatch):
    reg = library_system.get_node_registry()
    disp_key = next(k for k in reg.list_names() if k == "haybale-testing:node:DisplayNode")

    # Author a warning on the testing library, landing in a FUTURE version
    # relative to whatever the live library is, so a saved-below-version node fires.
    lib_registry = library_system.get_library_registry()
    testing_lib = lib_registry._libraries["haybale-testing"]
    live_version = testing_lib.identity.version

    # Pick a warning version strictly ABOVE the saved version we will fake below.
    warning = CompatibilityWarning(
        version="999.0.0",
        component=disp_key,  # registry_key string is accepted
        message="frame inlet widget strategy became author-declared",
    )
    monkeypatch.setattr(type(testing_lib), "compatibility_warnings", lambda self: [warning], raising=False)

    # Build a one-node graph, serialize, then force the saved library.version low.
    g1 = BaseGraph(name="g1", validation_scheduler=SyncScheduler())
    a = make_node(g1, disp_key, position=(100, 100))
    data = g1.to_dict(include_data=False)
    # Stamp an OLD saved version on the node's library block.
    data["nodes"][a.node_id]["node_data"]["library"]["version"] = "0.0.1"

    g2 = BaseGraph(name="g2", validation_scheduler=SyncScheduler())
    assert g2.load_from_dict(data) is True

    state = _wrapper(g2, a.node_id).state
    assert state.has_warning() is True
    assert any(w.kind == "compatibility" and "author-declared" in w.message for w in state.warnings)
    assert live_version  # sanity: live version was readable


@pytest.mark.integration
def test_load_does_not_warn_when_saved_version_current(library_system, monkeypatch):
    reg = library_system.get_node_registry()
    disp_key = next(k for k in reg.list_names() if k == "haybale-testing:node:DisplayNode")
    lib_registry = library_system.get_library_registry()
    testing_lib = lib_registry._libraries["haybale-testing"]

    warning = CompatibilityWarning(version="0.0.2", component=disp_key, message="x")
    monkeypatch.setattr(type(testing_lib), "compatibility_warnings", lambda self: [warning], raising=False)

    g1 = BaseGraph(name="g1", validation_scheduler=SyncScheduler())
    a = make_node(g1, disp_key, position=(100, 100))
    data = g1.to_dict(include_data=False)
    data["nodes"][a.node_id]["node_data"]["library"]["version"] = "9.9.9"  # newer than warning

    g2 = BaseGraph(name="g2", validation_scheduler=SyncScheduler())
    g2.load_from_dict(data)
    assert _wrapper(g2, a.node_id).state.has_warning() is False


@pytest.mark.integration
def test_library_wide_finding_lands_on_graph(library_system, monkeypatch):
    reg = library_system.get_node_registry()
    disp_key = next(k for k in reg.list_names() if k == "haybale-testing:node:DisplayNode")
    lib_registry = library_system.get_library_registry()
    testing_lib = lib_registry._libraries["haybale-testing"]

    warning = CompatibilityWarning(
        version="999.0.0", component=None, message="A library-wide convention changed."
    )
    monkeypatch.setattr(type(testing_lib), "compatibility_warnings", lambda self: [warning], raising=False)

    g1 = BaseGraph(name="g1", validation_scheduler=SyncScheduler())
    a = make_node(g1, disp_key, position=(100, 100))
    data = g1.to_dict(include_data=False)
    data["nodes"][a.node_id]["node_data"]["library"]["version"] = "0.0.1"

    g2 = BaseGraph(name="g2", validation_scheduler=SyncScheduler())
    g2.load_from_dict(data)

    # Library-wide finding stashed on the graph; node itself has no per-node badge.
    assert "A library-wide convention changed." in g2.library_compatibility_findings
    assert _wrapper(g2, a.node_id).state.has_warning() is False


@pytest.mark.integration
def test_reset_clears_compatibility_warning(library_system, monkeypatch):
    """Resetting a node rebuilds it from current code, so the advisory
    compatibility warning (derived from the saved file) must clear."""
    reg = library_system.get_node_registry()
    disp_key = next(k for k in reg.list_names() if k == "haybale-testing:node:DisplayNode")
    lib_registry = library_system.get_library_registry()
    testing_lib = lib_registry._libraries["haybale-testing"]

    warning = CompatibilityWarning(
        version="999.0.0", component=disp_key, message="frame inlet widget strategy changed"
    )
    monkeypatch.setattr(type(testing_lib), "compatibility_warnings", lambda self: [warning], raising=False)

    g1 = BaseGraph(name="g1", validation_scheduler=SyncScheduler())
    a = make_node(g1, disp_key, position=(100, 100))
    data = g1.to_dict(include_data=False)
    data["nodes"][a.node_id]["node_data"]["library"]["version"] = "0.0.1"

    g2 = BaseGraph(name="g2", validation_scheduler=SyncScheduler())
    g2.load_from_dict(data)
    wrapper = _wrapper(g2, a.node_id)
    assert wrapper.state.has_warning() is True

    # Reset = full rebuild from current code (what request_node_reset triggers).
    wrapper.build()
    assert wrapper.state.has_warning() is False
