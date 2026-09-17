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
from haywire.ui.components.graph.event_definitions import CanvasMountedEvent, SyncAllEdgesEvent

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


@pytest.mark.anyio
async def test_nodes_mounted_fires_after_the_last_node_and_before_the_edges(handler, graph):
    """The viewport is placed over content that exists, and the edges draw into it."""
    graph.edge_wrappers = {"e0": MagicMock()}
    order: list[str] = []
    handler.canvas_vue.emit_sync_event.side_effect = lambda event: order.append(type(event).__name__)

    await handler.sync_with_graph_chunked(
        on_progress=lambda mounted, total: order.append(f"node{mounted}"),
        on_nodes_mounted=lambda: order.append("centre"),
    )

    assert order.index("centre") > order.index(f"node{len(graph.node_wrappers)}")
    assert order.index("centre") < order.index(SyncAllEdgesEvent.__name__)


@pytest.mark.anyio
async def test_a_load_cancelled_before_the_last_node_centres_nothing(handler, graph):
    called: list[int] = []

    def _cancel_midway(mounted: int, _total: int) -> None:
        if mounted == 2:
            raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await handler.sync_with_graph_chunked(
            on_progress=_cancel_midway,
            on_nodes_mounted=lambda: called.append(1),
        )

    assert called == []


class TestResyncEdges:
    """A canvas that came back without its edges gets the batch again."""

    def test_it_re_emits_the_batch(self, handler, graph):
        graph.edge_wrappers = {"e0": MagicMock(), "e1": MagicMock()}

        handler.resync_edges()

        events = [c.args[0] for c in handler.canvas_vue.emit_sync_event.call_args_list]
        batches = [e for e in events if isinstance(e, SyncAllEdgesEvent)]
        assert len(batches) == 1
        assert len(batches[0].edges) == 2

    def test_a_graph_with_no_edges_sends_nothing(self, handler, graph):
        graph.edge_wrappers = {}

        handler.resync_edges()

        handler.canvas_vue.emit_sync_event.assert_not_called()

    def test_it_does_not_re_mount_the_nodes(self, handler, graph):
        """Nodes are server-side elements; they survived whatever lost the edges."""
        graph.edge_wrappers = {"e0": MagicMock()}
        before = dict(handler.node_panels)

        handler.resync_edges()

        assert handler.node_panels == before


class TestTheEdgeDrawGate:
    """What the load overlay waits for, and what it must NOT wait for.

    Waiting for one drawn path per edge is what made the overlay sit on its
    full 20 s deadline: an edge whose node is culled off-viewport, or whose
    pins have not mounted, is parked by the canvas and drawn later, so the
    count it was waiting for never arrives.
    """

    def _replies(self, handler, result, recorded: list | None = None):
        """Stub the confirmation round-trip, which the loader awaits."""

        async def _run(script, **_kwargs):
            if recorded is not None:
                recorded.append(script)
            return result

        handler.canvas_vue.client.run_javascript = _run

    @pytest.mark.anyio
    async def test_it_waits_on_what_the_canvas_accounted_for(self, handler):
        recorded: list[str] = []
        self._replies(handler, None, recorded)

        await handler._await_client_drawn(3)

        (script,) = recorded
        assert "hwEdgeDrawn" in script
        assert "hwEdgeParked" in script
        # Not a DOM path count: parked edges make that total unreachable.
        assert "path[data-edge-id]" not in script
        # Not "a new batch since I started": the batch has usually gone out
        # already, emitted by the validation timer during the node loop.
        assert "seen" not in script

    @pytest.mark.anyio
    async def test_it_scopes_the_lookup_to_this_canvas(self, handler):
        """By attribute, not by id: the canvas's containerId never reaches the DOM."""
        recorded: list[str] = []
        handler.canvas_vue.dom_selector = '[data-hw-canvas-id="graph-canvas-42"]'
        self._replies(handler, None, recorded)

        await handler._await_client_drawn(1)

        assert """querySelector('[data-hw-canvas-id="graph-canvas-42"]')""" in recorded[0]
        assert "getElementById" not in recorded[0]

    @pytest.mark.anyio
    async def test_a_timeout_is_reported_and_not_raised(self, handler, caplog):
        self._replies(handler, {"drawn": 0, "parked": 0, "timedOut": True})

        with caplog.at_level("WARNING"):
            await handler._await_client_drawn(2)

        assert "accounted for 0 of 2 edges" in caplog.text

    @pytest.mark.anyio
    async def test_parked_edges_are_reported_and_release_the_load(self, handler, caplog):
        """Culled nodes leave edges parked; that is normal, not a failure."""
        self._replies(handler, {"drawn": 120, "parked": 440, "timedOut": False})

        with caplog.at_level("INFO"):
            await handler._await_client_drawn(560)

        assert "440 waiting" in caplog.text


class TestCanvasMounted:
    """A re-mounted canvas holds no edges; the server is the only one who can say."""

    def test_mounting_re_sends_the_edges(self, handler, graph):
        graph.edge_wrappers = {"e0": MagicMock(), "e1": MagicMock()}

        handler.process_canvas_mounted(CanvasMountedEvent())

        events = [c.args[0] for c in handler.canvas_vue.emit_sync_event.call_args_list]
        batches = [e for e in events if isinstance(e, SyncAllEdgesEvent)]
        assert len(batches) == 1
        assert len(batches[0].edges) == 2

    def test_it_re_sends_edges_the_server_already_recorded_as_drawn(self, handler, graph):
        """The guard on_validated uses would swallow every one of them."""
        graph.edge_wrappers = {"e0": MagicMock()}
        handler.edge_states["e0"] = MagicMock()  # already "sent" once

        handler.process_canvas_mounted(CanvasMountedEvent())

        assert handler.canvas_vue.emit_sync_event.called

    def test_it_is_wired_to_the_event(self):
        from haybale_graph_editor.editors.graph_canvas.event_handlers import build_event_handler_map

        handlers = build_event_handler_map(
            [
                VisualLayerHandlers(
                    graph=MagicMock(), editor=MagicMock(), skin_factory=MagicMock(), canvas_vue=MagicMock()
                )
            ]
        )

        assert CanvasMountedEvent.event_type in handlers


class TestTheValidationTimerBeatsTheLoop:
    """The edge batch normally goes out DURING the node loop, not after it.

    ``ThreadingTimerScheduler`` is a daemon timer, so the validation pass a file
    load schedules fires on its own thread ~50 ms in, while the chunked loop is
    still mounting. Its result carries every edge, so the loop's own pass at the
    end finds them all registered and emits nothing at all — which is why a load
    gate waiting for a batch to arrive after it starts waits for ever.
    """

    def test_a_validation_pass_emits_the_edges(self, handler, graph):
        graph.edge_wrappers = {"e0": MagicMock(), "e1": MagicMock()}
        graph.get_edge_wrapper.return_value = MagicMock()
        handler._register_edge_visual = MagicMock(  # type: ignore[method-assign]
            side_effect=lambda w: handler.edge_states.setdefault("e", MagicMock()) and {"id": "e"}
        )

        handler.on_validated(handler._full_add_result(include_nodes=False))

        assert handler.canvas_vue.emit_sync_event.called

    @pytest.mark.anyio
    async def test_the_loops_own_pass_then_emits_nothing(self, handler, graph):
        graph.edge_wrappers = {"e0": MagicMock(), "e1": MagicMock()}
        graph.get_edge_wrapper.return_value = MagicMock()
        # What the timer thread already did: every edge recorded as sent.
        handler.edge_states.update({"e0": MagicMock(), "e1": MagicMock()})
        handler._await_client_drawn = _noop_confirm  # type: ignore[method-assign]

        await handler.sync_with_graph_chunked()

        events = [c.args[0] for c in handler.canvas_vue.emit_sync_event.call_args_list]
        assert [e for e in events if isinstance(e, SyncAllEdgesEvent)] == []


async def _noop_confirm(edge_count):
    return None
