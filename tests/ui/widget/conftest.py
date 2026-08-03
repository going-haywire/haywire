"""Shared fixtures/helpers for the widget perf tests.

The render-profile and cost-attribution perf tests both need a wide, edge-free
graph of identical widget-bearing nodes. They used to load a frozen
``graphs/10x200nodes.haywire`` file, but a frozen graph silently rots when a node
or type moves library (the primitive-type hoist into ``builtin`` re-keyed the
serialized port types to ``builtin:type:*`` and the load broke). Building the graph
fresh from the live registry keeps the same shape (200 PerformanceTester nodes, 0
edges, 11 NumberWidgets each) without tracking stale keys.
"""

from __future__ import annotations


from typing import Any, cast

import pytest

from haywire.core.graph.base import BaseGraph
from haywire.core.graph.scheduler import SyncScheduler


# Lazily-captured persistent NiceGUI default client (see nicegui_slot_context).
_CLIENT: list = []


def _noop_page() -> None:  # registration target for a headless Client
    pass


@pytest.fixture
def nicegui_slot_context():
    """Keep a valid NiceGUI default slot active for the test body.

    The autouse ``_reset_nicegui_globals`` clears ``Slot.stacks`` after every test,
    so the *second* perf test in a run finds an empty slot stack and the lazy
    re-init does not fire — any ``ui.element`` (or a node rejig that touches the
    slot) then raises "slot stack is empty". Building a graph fresh
    (``set_value`` -> ``rejig``) hits that path, where the old frozen-file load did
    not. Re-entering the persistent default client for the test body fixes that
    cross-test ordering pollution. Opt-in (not autouse) so it only touches the perf
    tests that need it (and only materializes the client on first use, so importing
    this conftest has no NiceGUI side effects).

    Materialization must go through ``Client(...)`` (passes ``_client=`` explicitly
    to its root ``Element``), not a bare ``ui.element(...)`` call — the latter reads
    ``context.client`` off whatever slot is already on the stack, so it only works
    by accident of ordering and raises "slot stack is empty" once no earlier test in
    the run happens to have left a slot open (see ``test_ui_state_row_state.py``,
    which materializes its own clients the same way).
    """
    from nicegui import Client

    if not _CLIENT:
        # Materialize NiceGUI's default client/slot once and cache it. The client
        # persists across the per-test Slot.stacks reset; only the stack is cleared.
        _CLIENT.append(Client(cast(Any, _noop_page), request=None))
    with _CLIENT[0]:
        yield


_PERF_NODE_COUNT = 200
# PerformanceTester.port_count drives dynamic FLOAT port generation (my_change):
# each unit adds one FLOAT inlet (a NumberWidget) + one FLOAT outlet. With 10 the
# node carries 11 NumberWidgets — the 10 inlets plus the port_count config widget —
# the widget-heavy shape the render/cost perf tests measure.
_PERF_PORT_COUNT = 10
_WIDGETS_PER_NODE = _PERF_PORT_COUNT + 1


def build_perf_graph(count: int = _PERF_NODE_COUNT) -> BaseGraph:
    """Build a wide, edge-free graph of ``count`` widget-heavy PerformanceTester nodes.

    Fresh-built (not loaded from a frozen file) so it can't go stale when a node or
    type changes library. The node type is referenced by its *class* (resolved to a
    registry_key at build time), so a move/rename fails loudly at import rather than
    silently producing a stale key. Each node has ``port_count`` set so it generates
    its full set of dynamic FLOAT ports (``_WIDGETS_PER_NODE`` NumberWidgets per
    node). Synchronous scheduler so validation + dynamic port rejig run inline.
    """
    from haybale_testing.nodes.testbed.test_performance import PerformanceTester

    key = PerformanceTester.class_identity.registry_key
    graph = BaseGraph(graph_id="perf", name="perf", validation_scheduler=SyncScheduler())
    for _ in range(count):
        nw = graph.create_node_wrapper(key, position=(0, 0))
        assert nw is not None, f"failed to create perf node {PerformanceTester.__name__} ({key!r})"
        # Setting port_count fires my_change -> adds the dynamic FLOAT ports.
        nw.node.ports["port_count"].set_value(_PERF_PORT_COUNT)
    graph.force_validation()
    assert len(graph.node_wrappers) == count, f"expected {count} nodes, got {len(graph.node_wrappers)}"
    assert len(graph.edge_wrappers) == 0, "perf graph is meant to be edge-free"
    return graph
