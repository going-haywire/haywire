"""Tests for the chunked (background) graph load.

``sync_with_graph_chunked`` exists so opening a large graph does not block the
event loop for every session at once — mounting is ~12 ms per widget-heavy node
and scales linearly, so a 300-node graph was ~4 s of straight-line Python during
which a second session's HTTP request measured 4.3 s to be served.

What must hold, and is asserted here:
  * it mounts every node, exactly once, like the synchronous path;
  * it yields between nodes (that is the whole point — a version that mounted
    everything before its first await would pass a "did it mount?" test while
    fixing nothing);
  * edges still go out in ONE batched event, not one per edge;
  * cancelling mid-load stops it, so a closing editor does not keep mounting
    into a torn-down canvas.
"""

import asyncio

import pytest
from unittest.mock import MagicMock

from haybale_graph_editor.editors.graph_canvas.handlers.visual_layer import VisualLayerHandlers
from haywire.ui.components.graph.event_definitions import SyncAllEdgesEvent

pytestmark = pytest.mark.unit


@pytest.fixture
def anyio_backend() -> str:
    """Run async tests on the asyncio backend."""
    return "asyncio"


def _node_wrapper(node_id: str) -> MagicMock:
    w = MagicMock()
    w.node.node_id = node_id
    w.node.props.posX = 10.0
    w.node.props.posY = 20.0
    w.state.has_warning.return_value = False
    return w


@pytest.fixture
def graph():
    g = MagicMock()
    g.node_wrappers = {f"n{i}": _node_wrapper(f"n{i}") for i in range(5)}
    g.edge_wrappers = {}
    g.canvas_width = 8000
    g.canvas_height = 8000
    g.library_compatibility_findings = []
    return g


@pytest.fixture
def handler(graph):
    h = VisualLayerHandlers(
        graph=graph,
        editor=MagicMock(),
        skin_factory=MagicMock(),
        canvas_vue=MagicMock(),
    )
    # add_node_visual is NiceGUI-dependent; record calls and register the panel
    # the way the real one does, so the "already mounted" guard is exercised.
    mounted: list[str] = []

    def _add(node, position):
        mounted.append(node.node_id)
        h.node_panels[node.node_id] = MagicMock()
        return True

    h.add_node_visual = MagicMock(side_effect=_add)  # type: ignore[method-assign]
    h.mounted = mounted  # type: ignore[attr-defined]
    return h


@pytest.mark.anyio
async def test_mounts_every_node_once(handler, graph):
    await handler.sync_with_graph_chunked()

    assert handler.mounted == list(graph.node_wrappers)
    assert len(handler.node_panels) == len(graph.node_wrappers)


@pytest.mark.anyio
async def test_skips_nodes_already_mounted(handler, graph):
    handler.node_panels["n2"] = MagicMock()

    await handler.sync_with_graph_chunked()

    assert "n2" not in handler.mounted
    assert len(handler.mounted) == len(graph.node_wrappers) - 1


@pytest.mark.anyio
async def test_yields_between_nodes(handler, graph):
    """The load must be interleavable — not merely correct at the end.

    A competing task counts how many times it gets to run while the load is in
    flight. Mounting everything in one go before the first await would leave it
    at zero, which is exactly the bug this method exists to prevent.
    """
    ticks = 0

    async def competitor():
        nonlocal ticks
        while True:
            await asyncio.sleep(0)
            ticks += 1

    task = asyncio.create_task(competitor())
    await handler.sync_with_graph_chunked()
    task.cancel()

    # One fewer than the node count: the competitor is scheduled after the
    # first node's mount, so it interleaves in each of the remaining gaps.
    expected = len(graph.node_wrappers) - 1
    assert ticks >= expected, (
        f"competing task ran only {ticks}x while mounting {len(graph.node_wrappers)} nodes — "
        "the load is not yielding per node, so it still blocks every other session"
    )


@pytest.mark.anyio
async def test_edges_emit_one_batched_event(handler, graph):
    """Edges stay batched: one SyncAllEdgesEvent, never one message per edge."""
    edge = MagicMock()
    graph.edge_wrappers = {f"e{i}": edge for i in range(4)}
    graph.get_edge_wrapper.return_value = edge
    handler._register_edge_visual = MagicMock(return_value={"id": "e"})  # type: ignore[method-assign]

    await handler.sync_with_graph_chunked()

    edge_events = [
        c.args[0]
        for c in handler.canvas_vue.emit_sync_event.call_args_list
        if isinstance(c.args[0], SyncAllEdgesEvent)
    ]
    assert len(edge_events) == 1
    assert len(edge_events[0].edges) == 4


@pytest.mark.anyio
async def test_waits_for_the_client_to_draw_the_edges(handler, graph):
    """The load must not finish while the edge batch is still in flight.

    ``emit_sync_event`` only queues a websocket message, so returning as soon
    as Python is done released the overlay onto a canvas with every node and
    ZERO edges (measured: 0 edge paths at unlock, 198 a second later). The
    confirmation round-trip must happen, and must happen AFTER the emit.
    """
    graph.edge_wrappers = {"e0": MagicMock()}
    graph.get_edge_wrapper.return_value = MagicMock()
    handler._register_edge_visual = MagicMock(return_value={"id": "e"})  # type: ignore[method-assign]

    order: list[str] = []
    handler.canvas_vue.emit_sync_event.side_effect = lambda *_: order.append("emit")

    async def _confirm(edge_count):
        order.append("confirm")

    handler._await_client_drawn = _confirm  # type: ignore[method-assign]

    await handler.sync_with_graph_chunked()

    assert order == ["emit", "confirm"], f"expected the client confirmation after the edge emit, got {order}"


@pytest.mark.anyio
async def test_no_client_wait_when_there_are_no_edges(handler, graph):
    """An edge-free graph has nothing in flight — don't pay a round-trip."""
    graph.edge_wrappers = {}
    seen: list[int] = []

    async def _confirm(edge_count):
        seen.append(edge_count)

    handler._await_client_drawn = _confirm  # type: ignore[method-assign]

    await handler.sync_with_graph_chunked()

    assert seen == [0]


@pytest.mark.anyio
async def test_client_confirmation_failure_does_not_strand_the_load(handler, graph):
    """A dead client must not leave the caller (and its overlay) hanging.

    The overlay has no dismiss button, so an exception escaping the wait would
    strand the user behind it.
    """
    graph.edge_wrappers = {"e0": MagicMock()}
    graph.get_edge_wrapper.return_value = MagicMock()
    handler._register_edge_visual = MagicMock(return_value={"id": "e"})  # type: ignore[method-assign]
    handler.canvas_vue.client.run_javascript = MagicMock(side_effect=RuntimeError("client gone"))

    await handler.sync_with_graph_chunked()  # must not raise


@pytest.mark.anyio
async def test_cancellation_stops_the_load(graph):
    """Cancelling mid-load must propagate, leaving the rest unmounted."""
    h = VisualLayerHandlers(
        graph=graph,
        editor=MagicMock(),
        skin_factory=MagicMock(),
        canvas_vue=MagicMock(),
    )
    graph.node_wrappers = {f"n{i}": _node_wrapper(f"n{i}") for i in range(200)}

    def _add(node, position):
        h.node_panels[node.node_id] = MagicMock()
        return True

    h.add_node_visual = MagicMock(side_effect=_add)  # type: ignore[method-assign]

    task = asyncio.create_task(h.sync_with_graph_chunked())
    await asyncio.sleep(0)  # let it mount a little
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert len(h.node_panels) < 200, "cancellation did not stop the mount loop"
