"""
Harness route handlers for the Settings UI test harness.

Routes:
  GET  /status               — liveness probe, returns {"status": "ok"}
  GET  /node?class=...&bag=  — render a NodeSettings bag via render_reactive()
  GET  /schema?class=...     — render a LibrarySettings/FrameworkSettings via render_schema()
  GET  /copy-button          — a bare hui.code_snippet() with its copy button
  POST /api/set?key=&value=  — write a value to the SettingsRegistry workspace tier
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from fastapi import Request
from fastapi.responses import JSONResponse
from nicegui import app as nicegui_app
from nicegui import ui

from haywire.core.access import LevelMode
from haywire.ui import elements as hui
from haywire.ui.components.graph.canvas import GraphCanvasVue
from haywire.ui.components.zoom.pan import ZoomPanContainer
from haywire.ui.panel.render_utils import render_settings, render_schema

if TYPE_CHECKING:
    from haywire.core.settings.registry import SettingsRegistry


def _resolve_class(dotted: str):
    """Import a dotted class path like 'a.b.c.MyClass' and return the class."""
    parts = dotted.rsplit(".", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid class path: {dotted!r}")
    module_path, class_name = parts
    mod = importlib.import_module(module_path)
    return getattr(mod, class_name)


def _harness_graph(name: str):
    """A graph validated on the NiceGUI event loop, as in the running studio (``LoopScheduler``).

    On the default timer scheduler a validation pass ran on its own thread while NiceGUI
    serialised the page, which surfaced as "dictionary changed size during iteration" in
    ``build_response`` (F13). On the loop the two never overlap.
    """
    from haywire.core.graph.base import BaseGraph
    from haywire.core.graph.scheduler import LoopScheduler

    return BaseGraph(name, validation_scheduler=LoopScheduler())


def _stamp_synced() -> None:
    """Mark the page as fully synced, for Playwright's ``goto_ready``.

    Value writes during widget construction queue ``updateValue`` messages in
    the client outbox; they are only flushed once the websocket connects. An
    edit typed in the browser before that flush arrives gets stomped back to
    the server value (and the stomp re-emits the old value, reverting the
    edit server-side). This marker is queued LAST in the page build, so by
    outbox FIFO it executes only after every pending sync message has been
    applied — from then on user input is safe. See tests/ui/harness/nav.py.
    """
    ui.run_javascript("document.body.dataset.hwSynced = '1'")


# Two-node control graph used by the /graph-reconnect route: a Test Begin Play
# (event source, ``exec`` outlet) wired to a Test Print (control sink, ``exec``
# inlet). Built programmatically and round-tripped through a .haywire file at
# request time so the fixture can never drift from the current serialization
# format — if save_to_file/load_from_file break, the route (and its test) fail.
_RECONNECT_SOURCE_KEY = "haybale-testing:node:TestBeginPlayNode"
_RECONNECT_SINK_KEY = "haybale-testing:node:TestPrintNode"
_RECONNECT_OUTLET = "exec"
_RECONNECT_INLET = "exec"


def _write_reconnect_graph(node_factory, out_path) -> None:
    """Build the two-node/one-edge reconnect graph and serialize it to out_path.

    Round-tripping through the real serializer (rather than a committed file)
    keeps the fixture in lockstep with the save/load code on every run.
    """
    from haywire.core.graph.editor import Editor

    graph = _harness_graph("Reconnect Fixture")
    editor = Editor(graph, node_factory)

    source = graph.create_node_wrapper(_RECONNECT_SOURCE_KEY, position=(3600.0, 3700.0))
    sink = graph.create_node_wrapper(_RECONNECT_SINK_KEY, position=(3950.0, 3700.0))
    assert source is not None, f"could not create {_RECONNECT_SOURCE_KEY}"
    assert sink is not None, f"could not create {_RECONNECT_SINK_KEY}"

    ok = editor.create_edge(source.node_id, _RECONNECT_OUTLET, sink.node_id, _RECONNECT_INLET)
    assert ok, f"could not connect {_RECONNECT_OUTLET} -> {_RECONNECT_INLET}"

    assert graph.save_to_file(str(out_path)), f"save failed: {out_path}"


def _build_connect_graph(node_factory):
    """Two UNCONNECTED nodes with compatible free pins, for connect tests.

    A Test Begin Play (``exec`` control outlet, ``timestamp`` float outlet) and a
    Test Print (``exec`` control inlet, ``message`` string inlet). The exec pins
    form a valid control pair the user can wire up; leaving them unconnected lets
    the test drive the click-drag / click-click / proximity-snap entry paths.
    """
    from haywire.core.graph.editor import Editor

    graph = _harness_graph("Connect Fixture")
    editor = Editor(graph, node_factory)

    src = graph.create_node_wrapper(_RECONNECT_SOURCE_KEY, position=(3600.0, 3700.0))
    dst = graph.create_node_wrapper(_RECONNECT_SINK_KEY, position=(3950.0, 3700.0))
    assert src is not None and dst is not None, "could not create connect-fixture nodes"  # noqa: PT018
    return graph, editor


_DYNAMIC_KEY = "haybale-testing:node:DynamicPortTestNode"
_EDGE_LINK_KEY = "haybale-testing:node:EdgeLinkTestNode"
_DYNAMIC_OUTLET = "dynamic_outlet_0"
_EDGE_LINK_INLET = "int_inlet"


def _build_dynamic_graph(node_factory):
    """A DynamicPortTestNode wired to an EdgeLinkTestNode via a dynamic port.

    ``dynamic_outlet_0`` (TEST_INT, present while port_count >= 1) → ``int_inlet``.
    Lowering port_count to 0 removes the outlet; raising it restores the same id.
    The canvas should fall its edge back to the node's ghost outlet when the real
    pin disappears, and back onto the real pin when it returns. Returns
    (graph, editor, dyn_node) so the route can mutate port_count.
    """
    from haywire.core.graph.editor import Editor

    graph = _harness_graph("Dynamic Fixture")
    editor = Editor(graph, node_factory)

    dyn = graph.create_node_wrapper(_DYNAMIC_KEY, position=(3600.0, 3700.0))
    sink = graph.create_node_wrapper(_EDGE_LINK_KEY, position=(3980.0, 3700.0))
    assert dyn is not None and sink is not None, "could not create dynamic-fixture nodes"  # noqa: PT018

    ok = editor.create_edge(dyn.node_id, _DYNAMIC_OUTLET, sink.node_id, _EDGE_LINK_INLET)
    assert ok, f"could not connect {_DYNAMIC_OUTLET} -> {_EDGE_LINK_INLET}"
    return graph, editor, dyn


_PERF_KEY = "haybale-testing:node:PerformanceTester"


def _build_edge_batch_graph(node_factory, edge_count: int, wire: int | None = None):
    """Two PerformanceTesters wired outlet_i → inlet_i, ``edge_count`` times.

    ``port_count`` drives how many float pairs the node exposes, so the edge
    count varies while the NODE count stays at two. ``wire`` connects fewer
    pairs than there are ports, leaving spares a test can wire up later. That separation is the
    whole point: the test asserts the number of edge sync messages does not
    grow with the number of edges, and a fixture that added nodes alongside
    edges could not tell the two apart.
    """
    from haywire.core.graph.editor import Editor

    graph = _harness_graph("Edge Batch Fixture")
    editor = Editor(graph, node_factory)

    src = graph.create_node_wrapper(_PERF_KEY, position=(3600.0, 3700.0))
    dst = graph.create_node_wrapper(_PERF_KEY, position=(4300.0, 3700.0))
    assert src is not None and dst is not None, "could not create edge-batch nodes"  # noqa: PT018

    # Drives hb_reconfigure → rejig, giving float_outlet_0..N-1 / float_inlet_0..N-1.
    src.node.ports["port_count"].set_value(edge_count)
    dst.node.ports["port_count"].set_value(edge_count)

    for i in range(edge_count if wire is None else wire):
        ok = editor.create_edge(src.node_id, f"float_outlet_{i}", dst.node_id, f"float_inlet_{i}")
        assert ok, f"could not connect float_outlet_{i} -> float_inlet_{i}"

    return graph, editor


def _build_chunked_load_graph(node_factory, node_count: int):
    """A chain of ``node_count`` Test Prints, each wired to the next.

    Many NODES, unlike ``_build_edge_batch_graph``: the load overlay is only
    observable while the chunked loop has nodes left to mount, so a two-node
    fixture opens and closes it faster than a test can see it.
    """
    from haywire.core.graph.editor import Editor

    graph = _harness_graph("Chunked Load Fixture")
    editor = Editor(graph, node_factory)

    previous = None
    for i in range(node_count):
        wrapper = graph.create_node_wrapper(
            _RECONNECT_SINK_KEY, position=(3400.0 + (i % 20) * 260.0, 3400.0 + (i // 20) * 220.0)
        )
        assert wrapper is not None, "could not create chunked-load node"
        if previous is not None:
            assert editor.create_edge(previous.node_id, "done", wrapper.node_id, "exec")
        previous = wrapper

    return graph, editor


def _build_detail_graph(node_factory):
    """A node whose LINKED pin sits below several unlinked ones, for NodeDetail.

    ``EdgeLinkTestNode`` declares ``callback_inlet``, ``execute_inlet`` and
    ``bool_inlet`` ahead of ``int_inlet``, and only ``int_inlet`` is wired. That
    ordering is the whole fixture: at the PINS rank the three unlinked pins
    above it are ``display: none``, so the linked pin — which stays visible —
    MOVES. An edge that does not follow it is the defect under test.

    Returns (graph, editor, sink) so the route can flip the sink's detail rank.
    """
    from haywire.core.graph.editor import Editor

    graph = _harness_graph("Detail Fixture")
    editor = Editor(graph, node_factory)

    dyn = graph.create_node_wrapper(_DYNAMIC_KEY, position=(3600.0, 3700.0))
    sink = graph.create_node_wrapper(_EDGE_LINK_KEY, position=(3980.0, 3700.0))
    assert dyn is not None and sink is not None, "could not create detail-fixture nodes"  # noqa: PT018

    ok = editor.create_edge(dyn.node_id, _DYNAMIC_OUTLET, sink.node_id, _EDGE_LINK_INLET)
    assert ok, f"could not connect {_DYNAMIC_OUTLET} -> {_EDGE_LINK_INLET}"
    return graph, editor, sink


def _build_layout_graph(node_factory):
    """Two nodes wired outlet→inlet, for the LayoutDirection canvas tests.

    A real edge is the point: switching the graph's layout_direction re-renders
    both node cards, and the canvas must (a) re-read each pin's direction vector
    rather than reusing the one cached when the edge was created, and (b) redraw
    the edge on the redraw sync instead of waiting for an incidental hover.
    Returns (graph, editor) so the route can flip the graph-tier prop.
    """
    from haywire.core.graph.editor import Editor

    graph = _harness_graph("Layout Fixture")
    editor = Editor(graph, node_factory)

    src = graph.create_node_wrapper(_RECONNECT_SOURCE_KEY, position=(3600.0, 3700.0))
    dst = graph.create_node_wrapper(_RECONNECT_SINK_KEY, position=(3980.0, 3700.0))
    assert src is not None and dst is not None, "could not create layout-fixture nodes"  # noqa: PT018

    ok = editor.create_edge(src.node_id, "exec", dst.node_id, "exec")
    assert ok, "could not connect exec -> exec"
    return graph, editor


_ADD_FLOAT_KEY = "haybale-testing:node:TestAddFloatNode"
_LISTENER_KEY = "haybale-testing:node:TestCustomCallbackNode"
_EMITTER_KEY = "haybale-testing:node:TestEmitCallbackNode"
_ADD_PORT_KEY = "haybale-testing:node:AddPortTestNode"


def _build_edge_appearance_graph(node_factory):
    """One edge of each kind the edge-appearance tests read: data, control, callback, an invalid one,
    and a styled one on the test visual wire."""
    from haywire.core.graph.editor import Editor

    graph = _harness_graph("Edge Appearance Fixture")
    editor = Editor(graph, node_factory)

    def node(key: str, x: float, y: float):
        wrapper = graph.create_node_wrapper(key, position=(x, y))
        assert wrapper is not None, f"could not create {key}"
        return wrapper

    add_a, add_b = node(_ADD_FLOAT_KEY, 3600.0, 3600.0), node(_ADD_FLOAT_KEY, 3950.0, 3600.0)
    begin, printer = node(_RECONNECT_SOURCE_KEY, 3600.0, 3800.0), node(_RECONNECT_SINK_KEY, 3950.0, 3800.0)
    listener, emitter = node(_LISTENER_KEY, 3600.0, 4000.0), node(_EMITTER_KEY, 3950.0, 4000.0)
    slot_a, slot_b = node(_ADD_PORT_KEY, 3600.0, 4250.0), node(_ADD_PORT_KEY, 3950.0, 4250.0)

    assert editor.create_edge(add_a.node_id, "result", add_b.node_id, "value_a")
    assert editor.create_edge(begin.node_id, "exec", printer.node_id, "exec")
    assert editor.create_edge(listener.node_id, "listen_callback", emitter.node_id, "edge_callback")
    # Two bare ADD slots never link: the edge stays, and fails validation.
    graph.create_edge_wrapper(slot_a.node_id, "add_out_0", slot_b.node_id, "add_in_0")

    from haybale_testing.nodes.testbed.visual_probe import VisualProbeNode

    probe_key = VisualProbeNode.class_identity.registry_key
    note_a, note_b = node(probe_key, 3600.0, 4450.0), node(probe_key, 3950.0, 4450.0)
    assert editor.create_edge(note_a.node_id, "note_out", note_b.node_id, "note_in")
    return graph, editor


def _build_annotation_graph(node_factory):
    """Four annotation nodes for the annotation-skin tests.

    A (text "hello") and B are unlinked, side by side, for the hover, drag and
    double-click tests. C is linked to D twice (``right_0`` -> ``left_0``, then
    ``right_1`` -> ``left_1``) for the style and centring tests. Returns (graph,
    editor, ids) where *ids* maps "a".."d" to node ids.
    """
    from haywire.barn.builtin.nodes.annotation import AnnotationNode
    from haywire.core.graph.editor import Editor

    graph = _harness_graph("Annotation Fixture")
    editor = Editor(graph, node_factory)
    key = AnnotationNode.class_identity.registry_key
    ids = {}
    for name, x, y in (
        ("a", 3600.0, 3700.0),
        ("b", 3950.0, 3700.0),
        ("c", 3600.0, 3950.0),
        ("d", 3950.0, 3950.0),
    ):
        wrapper = graph.create_node_wrapper(key, position=(x, y))
        assert wrapper is not None, "could not create an annotation node"
        ids[name] = wrapper.node_id
    graph.node_wrappers[ids["a"]].node.annotation.text = "hello"  # type: ignore[attr-defined]
    assert editor.create_edge(ids["c"], "right_0", ids["d"], "left_0")
    # The first link grows the `_1` slots it connects to.
    graph.force_validation()
    assert editor.create_edge(ids["c"], "right_1", ids["d"], "left_1")
    return graph, editor, ids


def _build_error_skin_graph(node_factory):
    """One node pinned to the error skin, for the error-skin DOM tests.

    The error skin is normally reached only by a render failure, which is hard
    to provoke deterministically. `props.skin` takes a plain registry key, so
    pointing a healthy node at it renders the same DOM without needing a broken
    node. Backs test_error_skin.py.
    """
    from haywire.core.graph.editor import Editor

    graph = _harness_graph("Error Skin Fixture")
    editor = Editor(graph, node_factory)

    node = graph.create_node_wrapper(_RECONNECT_SOURCE_KEY, position=(3700.0, 3700.0))
    assert node is not None, f"could not create {_RECONNECT_SOURCE_KEY}"
    node.node.props.skin = "haybale-graph-editor:skin:ErrorNodeSkin"
    return graph, editor, node


def _build_swinglet_skins_graph(node_factory):
    """One swinglet pass probe per skin, plus a card of all three glyphs.

    Backs test_swinglet_skins.py. Returns (graph, editor, ids): *ids* maps
    "default" (no skin set), "split", "stacked", "error" to the probe's node id,
    and "glyphs" to a probe that also carries an `EXEC` and a `CALLBACK` swinglet.
    """
    from haybale_graph_editor.skins.error_skin import ErrorNodeSkin
    from haybale_graph_editor.skins.split_skin import SplitNodeSkin
    from haybale_graph_editor.skins.stacked_skin import StackedNodeSkin
    from haybale_testing.nodes.testbed.swinglet_probe import SwingletPassProbeNode
    from haywire.barn.builtin.types import CALLBACK, EXEC
    from haywire.core.graph.editor import Editor

    graph = _harness_graph("Swinglet Skins Fixture")
    editor = Editor(graph, node_factory)
    key = SwingletPassProbeNode.class_identity.registry_key
    skins = {
        "default": None,
        "split": SplitNodeSkin.class_identity.registry_key,
        "stacked": StackedNodeSkin.class_identity.registry_key,
        "error": ErrorNodeSkin.class_identity.registry_key,
        "glyphs": None,
    }
    ids = {}
    for index, (name, skin_key) in enumerate(skins.items()):
        wrapper = graph.create_node_wrapper(key, position=(3600.0 + 450.0 * index, 3700.0))
        assert wrapper is not None, f"could not create {key}"
        if skin_key is not None:
            wrapper.node.props.skin = skin_key
        if name == "glyphs":
            wrapper.node.add(EXEC.as_swinglet("flow"))
            wrapper.node.add(CALLBACK.as_swinglet("hook"))
        ids[name] = wrapper.node_id
    return graph, editor, ids


def _build_swinglet_graph(node_factory):
    """Unlinked swinglet probes and an Add node, for the swinglet connect tests.

    Backs test_graph_swinglet_connect.py. Returns (graph, editor, ids): *ids*
    maps "v1".."v3" to visual probes (`TEST_VISUAL` swinglet `note`), "p1" and
    "p2" to pass probes (`FLOAT` swinglet `s`) and "add" to a `TestAddFloatNode`.
    """
    from haybale_testing.nodes.testbed.math_op_node import TestAddFloatNode
    from haybale_testing.nodes.testbed.swinglet_probe import (
        SwingletPassProbeNode,
        SwingletVisualProbeNode,
    )
    from haywire.core.graph.editor import Editor

    graph = _harness_graph("Swinglet Fixture")
    editor = Editor(graph, node_factory)
    visual = SwingletVisualProbeNode.class_identity.registry_key
    passing = SwingletPassProbeNode.class_identity.registry_key
    add = TestAddFloatNode.class_identity.registry_key
    ids = {}
    for name, key, x, y in (
        ("v1", visual, 3600.0, 3700.0),
        ("v2", visual, 3950.0, 3800.0),
        ("v3", visual, 4300.0, 3700.0),
        ("p1", passing, 3600.0, 4000.0),
        ("p2", passing, 3950.0, 4100.0),
        ("add", add, 4300.0, 4000.0),
    ):
        wrapper = graph.create_node_wrapper(key, position=(x, y))
        assert wrapper is not None, f"could not create {key}"
        ids[name] = wrapper.node_id
    return graph, editor, ids


def _build_two_column_graph(node_factory):
    """One node on the two-column SplitNodeSkin, for the R2L column-order test.

    It is the only user-selectable in-repo skin whose horizontal layout is not
    the stacked skin's single column, so it is the place the "columns follow
    flow direction" rule is observable. Returns (graph, editor) so the route
    can flip the graph-tier layout_direction.
    """
    from haywire.core.graph.editor import Editor

    graph = _harness_graph("Two Column Fixture")
    editor = Editor(graph, node_factory)

    # TestPrintNode, not TestBeginPlayNode: the test needs BOTH an inlet and an
    # outlet to compare their columns, and a source node has no inlets.
    node = graph.create_node_wrapper(_RECONNECT_SINK_KEY, position=(3700.0, 3700.0))
    assert node is not None, f"could not create {_RECONNECT_SINK_KEY}"
    node.node.props.skin = "haybale-graph-editor:skin:SplitNodeSkin"
    return graph, editor


def _build_reroute_graph(node_factory):
    """Two nodes with their exec edge split by a reroute, for the reroute-skin test.

    The reroute is created the way the app creates one — by splitting a real
    edge — so it carries the typed inlet/outlet the split action owns rather
    than hand-stamped ports. Returns (graph, editor, reroute_id) so the route
    can drive size props on the reroute itself.
    """
    from haywire.core.graph.editor import Editor

    graph = _harness_graph("Reroute Fixture")
    editor = Editor(graph, node_factory)

    src = graph.create_node_wrapper(_RECONNECT_SOURCE_KEY, position=(3600.0, 3700.0))
    dst = graph.create_node_wrapper(_RECONNECT_SINK_KEY, position=(4000.0, 3700.0))
    assert src is not None and dst is not None, "could not create reroute-fixture nodes"  # noqa: PT018

    ok = editor.create_edge(src.node_id, "exec", dst.node_id, "exec")
    assert ok, "could not connect exec -> exec"

    # Discover the reroute type via the registry's `_is_reroute` flag, the way
    # the canvas handler does — a hardcoded key would drift from the registry.
    reroute_cls = node_factory.get_reroute_node()
    assert reroute_cls is not None, "no reroute node in the registry"

    edge_id = next(iter(graph.edge_wrappers))
    reroute_id = editor.split_edge_with_reroute(
        edge_id,
        position=(3800.0, 3700.0),
        registry_key=reroute_cls.class_identity.registry_key,
    )
    assert reroute_id is not None, "split_edge_with_reroute failed"
    return graph, editor, reroute_id


def _build_size_graph(node_factory):
    """A single node, for the node-sizing gadget/measure tests.

    One TestPrintNode is enough: the sizing feature is per-node and needs no
    edges. Returns (graph, editor, node) so the route can drive size props and
    the test can select/resize it. See test_node_size_measure / test_resize_gadget.
    """
    from haywire.core.graph.editor import Editor

    graph = _harness_graph("Size Fixture")
    editor = Editor(graph, node_factory)

    node = graph.create_node_wrapper(_RECONNECT_SINK_KEY, position=(3700.0, 3700.0))
    assert node is not None, f"could not create {_RECONNECT_SINK_KEY}"
    return graph, editor, node


class _HarnessProjectState:
    """Minimal IProjectState stand-in for harness routes that need a Session.

    The studio's HaywireApp is the real app_state; sessions read only a few
    attributes off it (``library_state_container`` and ``on_client_deleted`` on the
    session path, plus the factories on ``IProjectState``). This pulls those
    from the booted library_service so a session can be created without the full
    studio app.
    """

    def __init__(self, library_service) -> None:
        from haywire.core.di.context import get_workspace_root
        from haywire.core.state import LibraryStateContainer

        self.workspace_root = str(get_workspace_root())
        self.library_service = library_service
        self.node_registry = library_service.get_node_registry()
        self.node_factory = library_service.get_node_factory()
        self.panel_registry = library_service.get_panel_registry()
        self.skin_factory = library_service.get_skin_factory()
        self.widget_factory = library_service.get_widget_factory()
        self.library_state_container = library_service.injector.get(LibraryStateContainer)

    def on_client_deleted(self, *args, **kwargs) -> None:  # session teardown hook
        pass


def _build_stage_graph(node_factory):
    """One node on the stage at stage ``(0, 0)``, for the stage-origin tests.

    Returns (graph, editor, node).
    """
    from haywire.core.graph.editor import Editor

    graph = _harness_graph("Stage Fixture")
    editor = Editor(graph, node_factory)
    node = graph.create_node_wrapper(_RECONNECT_SINK_KEY, position=(300.0, 300.0))
    assert node is not None, f"could not create {_RECONNECT_SINK_KEY}"
    node.node.props.on_stage = True
    node.node.props.stage_x = 0.0
    node.node.props.stage_y = 0.0
    return graph, editor, node


def _build_stage_gate_graph(node_factory):
    """Two annotations on stage, for the stage edge-gate tests.

    Returns (graph, editor, ids) where *ids* maps "a" and "b" to node ids.
    """
    from haywire.barn.builtin.nodes.annotation import AnnotationNode
    from haywire.core.graph.editor import Editor

    graph = _harness_graph("Stage Gate Fixture")
    editor = Editor(graph, node_factory)
    ids = {}
    for name, (x, y) in (("a", (40.0, 60.0)), ("b", (420.0, 60.0))):
        wrapper = graph.create_node_wrapper(
            AnnotationNode.class_identity.registry_key, position=(x + 300.0, y)
        )
        assert wrapper is not None, "could not create an annotation node"
        wrapper.node.props.on_stage = True
        wrapper.node.props.stage_x = x
        wrapper.node.props.stage_y = y
        ids[name] = wrapper.node_id
    return graph, editor, ids


def _build_stack_graph(node_factory):
    """Two overlapping on-stage nodes, ``back`` (z 0) under ``front`` (z 1), in both views.

    ``front`` sits 80 right and 60 down of ``back``, so it covers ``back``'s lower right. It is
    made first, so it mounts first and only its z puts it on top.
    Returns (graph, editor, back, front).
    """
    from haywire.core.graph.editor import Editor

    graph = _harness_graph("Stack Fixture")
    editor = Editor(graph, node_factory)
    placed = {}
    for name, (x, y), z in (("front", (380.0, 360.0), 1), ("back", (300.0, 300.0), 0)):
        node = graph.create_node_wrapper(_RECONNECT_SINK_KEY, position=(x, y))
        assert node is not None, f"could not create {_RECONNECT_SINK_KEY}"
        props = node.node.props
        props.on_stage = True
        props.stage_x, props.stage_y = x - 300.0, y - 300.0
        props.z = props.stage_z = z
        placed[name] = node
    return graph, editor, placed["back"], placed["front"]


def _harness_session(library_service, graph):
    """Create a real Session over a harness app state, with ``graph`` as the active graph.

    Returns (session, app_state).
    """
    from haywire.core.di.context import get_workspace_root
    from haywire.core.session.session_manager import SessionManager
    from haywire.core.signals import SignalDispatcher
    from haywire.core.session.workspace.manager import WorkspaceManager
    from haybale_graph_editor.state.edit_state import EditState

    app_state = _HarnessProjectState(library_service)
    session_manager = SessionManager(
        dispatcher=SignalDispatcher(), container=app_state.library_state_container
    )
    workspace_manager = WorkspaceManager(project_path=get_workspace_root())
    session = session_manager.create_session(
        app_state=app_state,
        workspace_manager=workspace_manager,
    )
    # Context-menu providers resolve wrappers off active_graph.
    session.context.data[EditState].active_graph = graph
    return session, app_state


@dataclass
class _HarnessLevel:
    """The level mode a harness canvas's route reads; a page changes ``mode`` to move the canvas."""

    mode: LevelMode = LevelMode.EDIT


def _mount_graph_canvas(
    library_service,
    graph,
    editor,
    testid: str,
    sync: bool = True,
    channel=None,
    level: _HarnessLevel | None = None,
):
    """Boot a real GraphCanvasManager over (graph, editor) inside the page.

    Wires the full editor stack — session, handlers, context-menu provider —
    exactly as the studio does, so canvas interactions (connect, reconnect,
    context menus) run end-to-end. Returns the GraphCanvasManager.

    Args:
        sync: Mount the graph synchronously. Pass ``False`` for a page that
            drives ``start_chunked_sync`` itself.
        channel: The layout channel of the canvas; the patch when ``None``.
        level: The level whose ``mode`` the canvas's route reads; ``None`` is a level in
            ``EDIT``.
    """
    from haybale_graph_editor.editors.graph_canvas.graph_canvas_manager import GraphCanvasManager
    from haybale_graph_editor.state.edit_state import EditState
    from haywire.core.graph.edit_route import EditRoute

    session, _app_state = _harness_session(library_service, graph)
    level = level if level is not None else _HarnessLevel()
    route = EditRoute(lambda: editor, lambda: level.mode)
    # The level on screen, as the graph editor makes it: the context menu's forms write through it.
    session.context.data[EditState].active_route = route

    with ui.element("div").style("width: 800px; height: 600px; position: relative; border: 1px solid #666;"):
        manager = GraphCanvasManager(
            route=route,
            skin_factory=library_service.get_skin_factory(),
            node_factory=library_service.get_node_factory(),
            panel_registry=library_service.get_panel_registry(),
            session=session,
            **({"channel": channel} if channel is not None else {}),
        )
        manager.zoom_container.props(f'data-testid="{testid}-zoom"')
        manager.canvas_vue.props(f'data-testid="{testid}-canvas"')
        if sync:
            manager.sync_with_graph()
        manager.zoom_container._on_ready = manager.zoom_container.center_on_content
    return manager


def _build_enter_graph(library_service):
    """A graph holding one Group card whose interface inlet draws a number widget.

    Returns ``(graph, editor, card_id)``.
    """
    from haywire.core.graph.editor import Editor

    graph = _harness_graph("Enter Fixture")
    editor = Editor(graph, library_service.get_node_factory())
    # A float source feeds the adder's first inlet, so collapsing the adder gives
    # the Group card an interface inlet. Removing the edge afterwards leaves that
    # inlet unconnected, which is when a card draws its widget (a number field).
    source = graph.create_node_wrapper(_ADD_FLOAT_KEY, position=(3400.0, 3700.0))
    adder = graph.create_node_wrapper(_ADD_FLOAT_KEY, position=(3700.0, 3700.0))
    assert source is not None and adder is not None  # noqa: PT018
    assert editor.create_edge(source.node_id, "result", adder.node_id, "value_a")
    card_id, reason = editor.collapse_to_group(
        node_ids=[adder.node_id],
        card_registry_key="haywire-core:node:GraphNode",
        input_registry_key="haywire-core:node:SubgraphInputNode",
        output_registry_key="haywire-core:node:SubgraphOutputNode",
        label="Enter Fixture Group",
    )
    assert card_id is not None, reason
    assert editor.remove_elements([], [e.edge_id for e in editor.list_edges()], release_pins=False)
    return graph, editor, card_id


def _record_navigation(manager, log) -> None:
    """Write the node id of each signal ``manager``'s session publishes with one into ``log``."""
    session = manager._session
    publish = session.publish

    def _record(signal, *args, **kwargs):
        node_id = getattr(signal, "node_id", None)
        if node_id is not None:
            log.set_text(node_id)
        return publish(signal, *args, **kwargs)

    session.publish = _record


def _build_theme_css(registry: "SettingsRegistry", theme_registry) -> str:
    """The app's stylesheet: theme ``:root`` vars plus ``STATIC_CSS``.

    ``STATIC_CSS`` is what the studio itself injects (``shell.py``), and without
    it a harness page renders settings rows with none of the app's own field
    styling — compact-field heights, input framing, `.hw-panel` colour
    forwarding, the `.hw-optional-none` absence cell. A page that doesn't look
    like the app can't be used to check how the app looks, so both halves ship
    together here.
    """
    from haywire.ui.app.shell import STATIC_CSS

    valid_keys = [k for k in theme_registry.list_workbench_keys() if not k.startswith("__system__:")]
    if not valid_keys:
        return STATIC_CSS
    theme_key, _ = registry.resolve("workbench.theme")
    if theme_key not in valid_keys:
        theme_key = valid_keys[0]
    theme = theme_registry.get_workbench(theme_key)
    vars_str = " ".join(f"{k}: {v};" for k, v in theme.to_css_vars().items())
    return f":root {{ {vars_str} }}" + STATIC_CSS


def _harness_session_context(library_service):
    """A real ``SessionContext`` for routes that render settings outside a studio.

    ``render_settings`` / ``render_schema`` / ``render_keys`` take a context as
    their first argument — a row's context menu offers session-scoped actions
    (opening a component's source in this session's editor slot) that no bag can
    supply. A settings-rendering harness page has no studio session of its own,
    so it builds one the same way ``_mount_graph_canvas`` does: a real session
    over ``_HarnessProjectState``, not a mock, so a menu action that touches the
    context behaves here as it does in the app.
    """
    from haywire.core.di.context import get_workspace_root
    from haywire.core.session.session_manager import SessionManager
    from haywire.core.session.workspace.manager import WorkspaceManager
    from haywire.core.signals import SignalDispatcher

    app_state = _HarnessProjectState(library_service)
    session_manager = SessionManager(
        dispatcher=SignalDispatcher(), container=app_state.library_state_container
    )
    session = session_manager.create_session(
        app_state=app_state,
        workspace_manager=WorkspaceManager(project_path=get_workspace_root()),
    )
    return session.context


def register_routes(library_service) -> None:
    """Register all harness routes with NiceGUI/FastAPI."""

    registry: "SettingsRegistry" = library_service.get_settings_registry()
    theme_registry = library_service.get_theme_registry()
    theme_css = _build_theme_css(registry, theme_registry)

    # -------------------------------------------------------------------------
    # GET /status
    # -------------------------------------------------------------------------

    @nicegui_app.get("/status")
    async def status_page():
        return JSONResponse({"status": "ok"})

    # -------------------------------------------------------------------------
    # GET /node?class=<dotted.ClassName>&bag=<bag_name>
    # -------------------------------------------------------------------------

    @ui.page("/node")
    async def node_page(request: Request):
        params = dict(request.query_params)
        class_path = params.get("class", "")
        bag_name = params.get("bag", "")

        if theme_css:
            ui.add_css(theme_css)

        with ui.card().classes("w-full max-w-md mx-auto mt-8 p-4"):
            if not class_path or not bag_name:
                ui.label("Missing ?class= or ?bag= parameter").classes("text-red-400")
                return

            try:
                node_cls = _resolve_class(class_path)
                settings_cls = getattr(node_cls, bag_name)
                settings_instance = settings_cls(registry=registry)
                render_settings(_harness_session_context(library_service), settings_instance, route=None)
            except Exception as exc:
                ui.label(f"Error: {exc}").classes("text-red-400 text-xs")
        _stamp_synced()

    # -------------------------------------------------------------------------
    # GET /node-appearance
    #
    # NodeProperties' `appearance` category with a live server-side echo of each
    # model value. The echo is what makes a persistence bug visible: a widget can
    # show a colour the model never received. Backs test_appearance_props.py.
    # -------------------------------------------------------------------------

    @ui.page("/node-appearance")
    async def node_appearance_page():
        from haywire.core.node.properties import NodeProperties

        if theme_css:
            ui.add_css(theme_css)

        props = NodeProperties()
        fields = ("color_override",)

        with ui.card().classes("w-full max-w-md mx-auto mt-8 p-4"):
            render_settings(
                _harness_session_context(library_service), props, categories=("appearance",), route=None
            )

            # Echo the model, not the widget: a label per field, refreshed from
            # the bag itself. Emptiness IS the unset signal — a cleared colour
            # means "inherit the theme's", so the echo shows the raw value.
            echoes: dict[str, Any] = {}
            for name in fields:
                echoes[name] = ui.label().props(f'data-testid="echo-{name}"')

            def _refresh() -> None:
                for field_name, label in echoes.items():
                    value = getattr(props, field_name)
                    label.set_text(f"{value}|{'set' if value else 'unset'}")

            _refresh()
            for name in fields:
                props._subscribe_field(name, lambda *_: _refresh())

            ui.button("refresh", on_click=_refresh).props('data-testid="refresh"')
        _stamp_synced()

    # -------------------------------------------------------------------------
    # GET /fill-widget
    #
    # The example library's FILL type and its editor, on a node port. FILL is no
    # longer a framework prop (node colour is one COLOR field now — see
    # ADR-0030); it ships in haybale-example as a worked compound type, and this
    # route is what exercises its widget in a browser. Backs test_fill_widget.py.
    # -------------------------------------------------------------------------

    @ui.page("/fill-widget")
    async def fill_widget_page():
        from unittest.mock import MagicMock
        from uuid import uuid4

        from haybale_example.types.fill import FILL
        from haywire.core.node.data import NodeData
        from haywire.ui.panel.setting_widget_model import SettingWidgetModel

        if theme_css:
            ui.add_css(theme_css)

        # NodeData rather than a real node: BaseNode needs a live wrapper and
        # create_node_wrapper needs the ambient app context — neither of which a
        # widget test has any business booting. `add()` is what turns a PortSpec
        # into the DataPort the widget actually binds to.
        # A fresh node id PER PAGE LOAD: the widget factory registers widget
        # instances against node_id, so a constant would let one test's edits
        # survive into the next test's page — state leaking through the server.
        node = NodeData(f"fill-demo-{uuid4().hex[:8]}", MagicMock())
        port = node.add(FILL.as_config(id="fill", label="Fill"))

        with ui.card().classes("w-full max-w-md mx-auto mt-8 p-4"):
            # `data-field` is what render_settings stamps on each row and what
            # every harness test waits on; render_widget draws the control
            # alone, so the wrapper is supplied here.
            with ui.column().classes("w-full").props('data-field="fill"'):
                # The port carries its widget key (FILL declares one on the
                # type), so the factory is told which widget rather than
                # inferring it.
                # A port of no graph has no route, so the page hands the widget a model that writes the port.
                model = SettingWidgetModel(port.id, port.widget_config, port.data, port.set_value)
                library_service.get_widget_factory().render_widget(port.widget_key, model, node.node_id)

            echo = ui.label().props('data-testid="echo-fill"')

            def _refresh() -> None:
                value = port.get_value()
                echo.set_text(value.to_css() if hasattr(value, "to_css") else str(value))

            _refresh()
            # Polled rather than subscribed: the echo must reflect what the
            # MODEL holds after a browser edit, and a poll cannot accidentally
            # assert on the widget's own view the way a bound label could.
            ui.timer(0.2, _refresh)
            ui.button("refresh", on_click=_refresh).props('data-testid="refresh"')
        _stamp_synced()

    # -------------------------------------------------------------------------
    # GET /list-widget
    #
    # TextWidget's commit mode and ArrayWidget, each on a node port, with a
    # polled echo of what the model holds. The text echo also counts the
    # writes, so a commit that writes twice (or a blur that writes at all)
    # shows. Backs test_list_widget.py.
    # -------------------------------------------------------------------------

    @ui.page("/list-widget")
    async def list_widget_page():
        from unittest.mock import MagicMock
        from uuid import uuid4

        from haybale_core.types import ArrayType
        from haybale_core.widgets.array_widget import ArrayWidget
        from haywire.barn.builtin.types import FLOAT, INT, STRING
        from haywire.barn.builtin.widgets import TextWidget
        from haywire.core.node.data import NodeData
        from haywire.ui.panel.setting_widget_model import SettingWidgetModel

        if theme_css:
            ui.add_css(theme_css)

        array: Any = ArrayType  # subscripted with runtime values below
        # A fresh node id per page load, as on /fill-widget.
        node = NodeData(f"list-demo-{uuid4().hex[:8]}", MagicMock())
        ports = [
            node.add(
                STRING.as_config(
                    id="text_commit", label="Text", widget=TextWidget.config(properties={"commit": True})
                )
            ),
            *(
                node.add(
                    array[item].as_config(
                        id=pid, label=pid, default={"value": default}, widget=ArrayWidget.config()
                    )
                )
                for pid, item, default in (
                    ("strings", STRING, ["One", "Two", "Three"]),
                    ("ints", INT, [1, 2, 3]),
                    ("floats", FLOAT, [0.5, 1.5]),
                )
            ),
        ]
        writes: dict[str, int] = {port.id: 0 for port in ports}

        def _writer(port):
            def on_edit(value):
                writes[port.id] += 1
                return port.set_value(value)

            return on_edit

        with ui.card().classes("w-full max-w-md mx-auto mt-8 p-4"):
            echoes = {}
            for port in ports:
                with ui.column().classes("w-full").props(f'data-field="{port.id}"'):
                    model = SettingWidgetModel(port.id, port.widget_config, port.data, _writer(port))
                    library_service.get_widget_factory().render_widget(port.widget_key, model, node.node_id)
                echoes[port.id] = ui.label().props(f'data-testid="echo-{port.id}"')

            def _refresh() -> None:
                for port in ports:
                    value = port.get_value()
                    text = f"{value}|{writes[port.id]}" if port.id == "text_commit" else repr(value)
                    echoes[port.id].set_text(text)

            _refresh()
            ui.timer(0.2, _refresh)
        _stamp_synced()

    # -------------------------------------------------------------------------
    # GET /node-live?class=<dotted.ClassName>&bag=<bag_name>
    #
    # Like /node, but additionally mounts a server-side "external write" button
    # per field. Clicking a button does setattr(instance, field, value) WITHOUT
    # touching the rendered widget — simulating a change from another tab /
    # worker / mirror propagation. Backs test_external_sync.py.
    # -------------------------------------------------------------------------

    @ui.page("/node-live")
    async def node_live_page(request: Request):
        params = dict(request.query_params)
        class_path = params.get("class", "")
        bag_name = params.get("bag", "")

        if theme_css:
            ui.add_css(theme_css)

        with ui.card().classes("w-full max-w-md mx-auto mt-8 p-4"):
            if not class_path or not bag_name:
                ui.label("Missing ?class= or ?bag= parameter").classes("text-red-400")
                return
            try:
                node_cls = _resolve_class(class_path)
                settings_cls = getattr(node_cls, bag_name)
                settings_instance = settings_cls(registry=registry)
                render_settings(_harness_session_context(library_service), settings_instance, route=None)

                # External-write triggers. Each button mutates the model only.
                def _ext_set(field: str, value):
                    def _do():
                        setattr(settings_instance, field, value)

                    return _do

                ui.button("ext-string", on_click=_ext_set("example_string", "EXTERNAL")).props(
                    'data-testid="ext-string"'
                )
                ui.button("ext-float", on_click=_ext_set("persistent_value", 9.0)).props(
                    'data-testid="ext-float"'
                )
                ui.button("ext-bool", on_click=_ext_set("example_bool", True)).props(
                    'data-testid="ext-bool"'
                )
                ui.button("ext-choice", on_click=_ext_set("example_choices", "quality")).props(
                    'data-testid="ext-choice"'
                )
                ui.button("ext-mirror", on_click=_ext_set("intensity", 0.7)).props(
                    'data-testid="ext-mirror"'
                )
                ui.button("ext-vec", on_click=_ext_set("example_vec3f", (4.0, 5.0, 6.0))).props(
                    'data-testid="ext-vec"'
                )
            except Exception as exc:
                ui.label(f"Error: {exc}").classes("text-red-400 text-xs")
        _stamp_synced()

    # -------------------------------------------------------------------------
    # GET /node-attached?class=...&bag=...
    #
    # A settings bag belonging to a REAL graph node, unlike /node and /node-live
    # which build a standalone instance. Promotion entries are structural: they
    # render only for a bag with an owning node, drawn with a level's edit route,
    # so the "Promote to" flyout — and everything reachable through it — is
    # invisible on every other settings route. Backs test_promote_flyout.py.
    #
    # The flyout in particular CANNOT be covered in-process: a nested ui.menu
    # that never opens, or an anchor that greys itself, renders identically in
    # the NiceGUI element tree and only a browser shows the breakage. See
    # .insights/project_submenu_leaf_counting_traps.md.
    # -------------------------------------------------------------------------

    @ui.page("/node-attached")
    async def node_attached_page(request: Request):
        params = dict(request.query_params)
        class_path = params.get("class", "")
        bag_name = params.get("bag", "")

        if theme_css:
            ui.add_css(theme_css)

        with ui.card().classes("w-full max-w-md mx-auto mt-8 p-4"):
            if not class_path or not bag_name:
                ui.label("Missing ?class= or ?bag= parameter").classes("text-red-400")
                return
            try:
                node_cls = _resolve_class(class_path)
                graph = _harness_graph("Attached Fixture")
                wrapper = graph.create_node_wrapper(
                    node_cls.class_identity.registry_key, position=(0.0, 0.0)
                )
                assert wrapper is not None, "could not create the attached-fixture node"
                from haywire.core.graph.edit_route import EditRoute
                from haywire.core.graph.editor import Editor

                editor = Editor(graph, library_service.get_node_factory())
                route = EditRoute(lambda: editor, lambda: LevelMode.EDIT)
                render_settings(
                    _harness_session_context(library_service), getattr(wrapper.node, bag_name), route=route
                )
            except Exception as exc:
                ui.label(f"Error: {exc}").classes("text-red-400 text-xs")
        _stamp_synced()

    # -------------------------------------------------------------------------
    # GET /schema?class=<dotted.ClassName>
    # -------------------------------------------------------------------------

    @ui.page("/schema")
    async def schema_page(request: Request):
        params = dict(request.query_params)
        class_path = params.get("class", "")

        if theme_css:
            ui.add_css(theme_css)

        with ui.card().classes("w-full max-w-md mx-auto mt-8 p-4"):
            if not class_path:
                ui.label("Missing ?class= parameter").classes("text-red-400")
                return

            try:
                schema_cls = _resolve_class(class_path)
                render_schema(_harness_session_context(library_service), schema_cls, registry)
            except Exception as exc:
                ui.label(f"Error: {exc}").classes("text-red-400 text-xs")
        _stamp_synced()

    # -------------------------------------------------------------------------
    # GET /graph-context-menu
    # -------------------------------------------------------------------------

    @ui.page("/graph-context-menu")
    async def graph_context_menu_page():
        last_event = ui.label("none").props('id="last-event" data-testid="last-event"')
        last_coords = ui.label("-").props('id="last-coords" data-testid="last-coords"')
        # Dedicated latch for context-menu events only. A right-click emits BOTH
        # contextMenuCanvas and selectionBoundsHide as separate async events, so
        # the shared last-event label is a last-writer race. This label is
        # written solely by context-menu events, so the assertion is
        # deterministic regardless of event ordering.
        last_context_menu = ui.label("none").props('id="last-context-menu" data-testid="last-context-menu"')
        # surfaceId latch for contextMenuSurface only — lets a test tell WHICH
        # data-hw-menu-surface-id was chosen (canvas.vue's closest() picks the
        # innermost annotation when several are nested).
        last_surface_id = ui.label("none").props('id="last-surface-id" data-testid="last-surface-id"')

        def on_canvas_event(event) -> None:
            event_type = getattr(event, "event_type", event.__class__.event_type)
            canvas_x = getattr(event, "canvasX", None)
            canvas_y = getattr(event, "canvasY", None)
            last_event.set_text(event_type)
            last_coords.set_text(f"{canvas_x},{canvas_y}")
            if event_type.startswith("contextMenu"):
                last_context_menu.set_text(event_type)
            if event_type == "contextMenuSurface":
                last_surface_id.set_text(getattr(event, "surfaceId", "none"))

        with ui.element("div").style(
            "width: 800px; height: 600px; position: relative; border: 1px solid #666;"
        ):
            zoom = ZoomPanContainer(initial_zoom=1.0)
            zoom.props('data-testid="zoom-pan-test"')
            zoom.style("width: 100%; height: 100%; display: block;")
            zoom.set_canvas_size(400, 400)

            with zoom.content_container:
                canvas = GraphCanvasVue(
                    on_canvas_event=on_canvas_event,
                    zoom_container=zoom,
                    canvas_width=400,
                    canvas_height=400,
                )
                canvas.props('data-testid="graph-canvas-test"')
                canvas.set_level_mode(LevelMode.EDIT)
        _stamp_synced()

    # -------------------------------------------------------------------------
    # GET /graph-reconnect
    #
    # Boots a real graph editor (GraphCanvasManager + handlers + context-menu
    # provider) over a tiny two-node/one-edge fixture, so the full reconnect
    # pipeline runs end-to-end in a browser. Backs the edge-reconnect Playwright
    # regression test (the anchor end must stay glued to its pin even though the
    # node DOM is rebuilt during reconnect). See test_graph_reconnect.py.
    #
    # ?missing_inlet=1 saves the edge's inlet as a port the sink does not have,
    # so the edge loads kept and drawn to the sink's ghost pin.
    # -------------------------------------------------------------------------

    @ui.page("/graph-reconnect")
    async def graph_reconnect_page(missing_inlet: bool = False):
        import json
        import tempfile
        from pathlib import Path

        from haywire.core.graph.editor import Editor

        # Generate the fixture programmatically and round-trip it through a real
        # .haywire file so the test exercises the live serialization path.
        node_factory = library_service.get_node_factory()
        with tempfile.NamedTemporaryFile(suffix=".haywire", delete=False) as tmp:
            fixture = Path(tmp.name)
        _write_reconnect_graph(node_factory, fixture)
        if missing_inlet:
            saved = json.loads(fixture.read_text())
            for edge in saved["edges"].values():
                edge["inlet_port_id"] = "gone"
            fixture.write_text(json.dumps(saved))

        graph = _harness_graph("Reconnect Fixture")
        editor = Editor(graph, node_factory)
        assert graph.load_from_file(str(fixture)), f"could not load fixture: {fixture}"
        fixture.unlink(missing_ok=True)

        _mount_graph_canvas(library_service, graph, editor, testid="reconnect")
        _stamp_synced()

    # -------------------------------------------------------------------------
    # GET /graph-connect
    #
    # Two UNCONNECTED nodes with compatible free pins, on the full editor stack.
    # Backs the connection-interaction Playwright tests (click-drag, click-click,
    # proximity-snap, reverse drag) — the UI entry paths that live only in
    # canvas.vue. See test_graph_connect.py.
    # -------------------------------------------------------------------------

    @ui.page("/graph-connect")
    async def graph_connect_page():
        graph, editor = _build_connect_graph(library_service.get_node_factory())
        _mount_graph_canvas(library_service, graph, editor, testid="connect")
        _stamp_synced()

    # -------------------------------------------------------------------------
    # GET /graph-edge-batch?edges=N
    #
    # Two nodes wired by N edges, N from the query string. Backs the batching
    # cost test: a graph's edges must reach the client in a message count that
    # does not grow with N. See test_edge_batch_cost.py.
    # -------------------------------------------------------------------------

    @ui.page("/graph-edge-batch")
    async def graph_edge_batch_page(request: Request):
        edges = int(request.query_params.get("edges", 8))
        graph, editor = _build_edge_batch_graph(library_service.get_node_factory(), edges)
        _mount_graph_canvas(library_service, graph, editor, testid="edge-batch")
        _stamp_synced()

    # -------------------------------------------------------------------------
    # GET /graph-chunked-load?nodes=N
    #
    # A graph opened through start_chunked_sync, behind the blocking load
    # overlay, exactly as the studio opens a large one. Backs the overlay's
    # release: the edges reach the client from the validation timer DURING the
    # node loop, so a gate waiting for anything to happen after the loop waits
    # for its whole deadline. See test_graph_chunked_load_modal.py.
    # -------------------------------------------------------------------------

    @ui.page("/graph-chunked-load")
    async def graph_chunked_load_page(request: Request):
        nodes = int(request.query_params.get("nodes", 80))
        graph, editor = _build_chunked_load_graph(library_service.get_node_factory(), nodes)
        manager = _mount_graph_canvas(library_service, graph, editor, testid="chunked", sync=False)
        manager.start_chunked_sync(graph_name="chunked fixture")
        _stamp_synced()

    # -------------------------------------------------------------------------
    # GET /graph-hidden-level?edges=N
    #
    # A canvas mounted and synced inside a tab panel that is NOT the active one,
    # plus a button that reveals it. Reproduces the case the studio hits when a
    # Group's level is edited while another level is on screen: the edge batch
    # reaches a canvas whose pins have no layout (or are culled away entirely),
    # so the edges must be parked and drawn on reveal rather than dropped.
    # See test_graph_hidden_level_edges.py.
    # -------------------------------------------------------------------------

    @ui.page("/graph-hidden-level")
    async def graph_hidden_level_page(request: Request):
        edges = int(request.query_params.get("edges", 4))
        # One spare port pair, so a button can wire an edge while the panel is
        # hidden — which is what an edit in a background level does.
        graph, editor = _build_edge_batch_graph(library_service.get_node_factory(), edges + 1, wire=edges)

        panels = ui.tab_panels(value="other", animated=False).props("keep-alive").style("width: 100%;")
        with panels:
            with ui.tab_panel("other"):
                ui.label("another level").props('data-testid="other-level"')
            with ui.tab_panel("canvas") as canvas_panel:
                manager = _mount_graph_canvas(library_service, graph, editor, testid="hidden")

        ui.button("reveal", on_click=lambda: panels.set_value("canvas")).props('data-testid="reveal"')
        ui.button("hide", on_click=lambda: panels.set_value("other")).props('data-testid="hide"')
        # A zoom other than 1 is what makes a re-mount's measurement window
        # visible: the canvas starts at zoom 1 and divides by it.
        ui.button("zoom-out", on_click=lambda: manager.zoom_container.set_zoom(0.35)).props(
            'data-testid="zoom-out"'
        )

        source, sink = list(graph.node_wrappers.values())[:2]

        def _add_edge() -> None:
            editor.create_edge(source.node_id, f"float_outlet_{edges}", sink.node_id, f"float_inlet_{edges}")

        ui.button("add-edge", on_click=_add_edge).props('data-testid="add-edge"')

        def _rekey() -> None:
            """What a save-as does to a graph tab: the panel gets a new name."""
            canvas_panel._props["name"] = "canvas-renamed"
            canvas_panel.update()
            panels.set_value("canvas-renamed")

        ui.button("rekey", on_click=_rekey).props('data-testid="rekey"')
        _stamp_synced()

    # -------------------------------------------------------------------------
    # GET /graph-dynamic
    #
    # A DynamicPortTestNode wired to an EdgeLinkTestNode through a dynamic port,
    # with buttons to drop / restore the port via port_count. Backs the ghost-
    # fallback test: removing the linked outlet must reattach the edge to the
    # node's ghost outlet (not delete it); restoring the port reattaches it to
    # the real pin. See test_graph_dynamic_ports.py.
    # -------------------------------------------------------------------------

    @ui.page("/graph-dynamic")
    async def graph_dynamic_page():
        graph, editor, dyn = _build_dynamic_graph(library_service.get_node_factory())

        def _set_port_count(n: int) -> None:
            # Drives hb_reconfigure → rejig → validation → canvas sync.
            dyn.node.ports["port_count"].set_value(n)

        # Controls outside the canvas so they never intercept canvas gestures.
        ui.button("drop-port", on_click=lambda: _set_port_count(0)).props('data-testid="drop-port"')
        ui.button("restore-port", on_click=lambda: _set_port_count(2)).props('data-testid="restore-port"')

        _mount_graph_canvas(library_service, graph, editor, testid="dynamic")
        _stamp_synced()

    # -------------------------------------------------------------------------
    # GET /graph-detail
    #
    # An EdgeLinkTestNode whose only wired inlet sits below three unlinked ones,
    # plus buttons flipping its NodeDetail rank. Backs test_graph_node_detail.py:
    # a rank change is a CSS filter that neither rebuilds the card nor emits a
    # sync, yet it re-lays the card out — so the canvas has to notice the
    # attribute itself and repaint the edges of a pin that moved.
    # -------------------------------------------------------------------------

    @ui.page("/graph-detail")
    async def graph_detail_page():
        graph, editor, sink = _build_detail_graph(library_service.get_node_factory())

        def _set_detail(value: str) -> None:
            sink.node.props.detail = value

        # Outside the canvas so they never intercept canvas gestures.
        ui.button("set-pins", on_click=lambda: _set_detail("pins")).props('data-testid="set-pins"')
        ui.button("set-full", on_click=lambda: _set_detail("full")).props('data-testid="set-full"')

        _mount_graph_canvas(library_service, graph, editor, testid="detail")
        _stamp_synced()

    # -------------------------------------------------------------------------
    # GET /graph-detail-culled
    #
    # Same fixture as /graph-detail, plus a button that switches viewport
    # culling on (pan.vue arms it only on that reactive OFF->ON transition, or
    # on a completed drag/wheel gesture — never merely because the prop
    # started true, since the graph may still be mid-load at first render).
    # A culled node's card is fully unmounted (see cull.vue) — a detail-rank
    # change made while it is off screen never reaches canvas.vue's
    # data-node-props-detail MutationObserver, because there is no element
    # for it to observe. Backs test_graph_node_detail_culling.py: the edge
    # must still repaint once the node scrolls back into view, without any
    # incidental hover/drag.
    # -------------------------------------------------------------------------

    @ui.page("/graph-detail-culled")
    async def graph_detail_culled_page():
        from haywire.ui.components.zoom.settings import EditorPanZoomSettings

        pz = EditorPanZoomSettings()
        # pan.vue only arms culling on the reactive OFF->ON transition of
        # cull_enabled (see its `watch` block) — never merely because the prop
        # started true. cull_enabled is a process-global FrameworkSettings
        # value, so a previous test run in this same harness session can leave
        # it already True; force it back to False here so every page load
        # gets a genuine transition when the "enable-culling" button fires.
        pz.cull_enabled = False
        pz.cull_min_nodes = 1  # arm/apply regardless of this fixture's tiny node count
        pz.cull_min_zoom = 0.0  # arm/apply at any zoom level

        graph, editor, sink = _build_detail_graph(library_service.get_node_factory())

        def _set_detail(value: str) -> None:
            sink.node.props.detail = value

        def _enable_culling() -> None:
            pz.cull_enabled = True

        ui.button("set-pins", on_click=lambda: _set_detail("pins")).props('data-testid="set-pins"')
        ui.button("set-full", on_click=lambda: _set_detail("full")).props('data-testid="set-full"')
        ui.button("enable-culling", on_click=_enable_culling).props('data-testid="enable-culling"')

        manager = _mount_graph_canvas(library_service, graph, editor, testid="detail-culled")
        # Skip the harness's usual center_on_content: the test drives pan
        # itself (via _zoomPanControls.setPan) to move the sink node in and
        # out of the culled band on demand.
        manager.zoom_container._on_ready = None
        _stamp_synced()

    # -------------------------------------------------------------------------
    # GET /graph-layout
    #
    # Two connected nodes plus buttons flipping the GRAPH-tier layout_direction.
    # Backs test_graph_layout_direction.py: a direction switch must re-aim each
    # pin's direction vector on the existing edge, and must repaint the edge on
    # the redraw sync rather than waiting for a hover to trigger it.
    # -------------------------------------------------------------------------

    @ui.page("/graph-layout")
    async def graph_layout_page():
        graph, editor = _build_layout_graph(library_service.get_node_factory())

        def _set_direction(value: str) -> None:
            graph.props.layout_direction = value

        ui.button("set-r2l", on_click=lambda: _set_direction("r2l")).props('data-testid="set-r2l"')
        ui.button("set-l2r", on_click=lambda: _set_direction("l2r")).props('data-testid="set-l2r"')
        ui.button("set-t2b", on_click=lambda: _set_direction("t2b")).props('data-testid="set-t2b"')
        ui.button("set-b2t", on_click=lambda: _set_direction("b2t")).props('data-testid="set-b2t"')

        _mount_graph_canvas(library_service, graph, editor, testid="layout")
        _stamp_synced()

    # -------------------------------------------------------------------------
    # GET /graph-edge-appearance
    #
    # A data, a control, a callback and an invalid edge, plus buttons setting
    # the graph's edge defaults and re-sending the edges. Fixed token values
    # make colours assertable.
    # Backs test_edge_appearance.py.
    # -------------------------------------------------------------------------

    @ui.page("/graph-edge-appearance")
    async def graph_edge_appearance_page():
        graph, editor = _build_edge_appearance_graph(library_service.get_node_factory())
        ui.add_css(":root:root { --hw-danger: rgb(200, 10, 10); --hw-edge-default: rgb(10, 120, 200); }")

        for testid, field, value in (
            ("set-width-4", "edge_width", 4.0),
            ("set-arrow-open", "edge_arrow", "open"),
            ("set-arrow-ring", "edge_arrow", "circle_hollow"),
            ("set-arrow-none", "edge_arrow", "none"),
        ):
            ui.button(testid, on_click=lambda _, f=field, v=value: setattr(graph.props, f, v)).props(
                f'data-testid="{testid}"'
            )

        manager = _mount_graph_canvas(library_service, graph, editor, testid="edge-appearance")
        # Re-sends every edge as one batch, which the canvas follows with its geometry check.
        ui.button("resync-edges", on_click=lambda: manager.resync_edges()).props(
            'data-testid="resync-edges"'
        )

        def _styled_edge():
            return next(e for e in graph.edge_wrappers.values() if e.outlet_port_id == "note_out")

        for testid, field, value in (
            ("style-width-6", "width", 6.0),
            ("style-end-open", "arrow_end", "open"),
            ("style-end-none", "arrow_end", "none"),
            ("style-start-open", "arrow_start", "open"),
            ("style-color-red", "color", "#ff0000"),
            ("style-dash-dotted", "dash", "dotted"),
        ):
            on_click = lambda _, f=field, v=value: setattr(_styled_edge().style, f, v)  # noqa: E731
            ui.button(testid, on_click=on_click).props(f'data-testid="{testid}"')

        def _send_partial_style() -> None:
            # A crafted payload: only arrowEnd declared, so the start end falls through (Q76).
            from haybale_graph_editor.editors.graph_canvas.ui_edge import (
                edge_sync_payload,
                edge_visual_state,
            )

            from haywire.ui.components.graph.event_definitions import SyncAllEdgesEvent

            edge = _styled_edge()
            state = edge_visual_state(edge)
            state.style = {"arrowEnd": "open"}
            manager.canvas_vue.emit_sync_event(SyncAllEdgesEvent(edges=[edge_sync_payload(edge, state)]))

        ui.button("style-partial", on_click=_send_partial_style).props('data-testid="style-partial"')
        # Below the canvas, so the canvas keeps its place on the page.
        ui.button("set-arrow-size-xl", on_click=lambda: setattr(graph.props, "edge_arrow_size", "xl")).props(
            'data-testid="set-arrow-size-xl"'
        )
        _stamp_synced()

    # -------------------------------------------------------------------------
    # GET /graph-annotation
    #
    # Annotation nodes on their four-sided skin, with buttons that set the linked
    # pair's edge style and A's control-pin switch. Node ids are on
    # `note-<name>` labels. Backs test_annotation_node.py.
    # -------------------------------------------------------------------------

    @ui.page("/graph-annotation")
    async def graph_annotation_page():
        graph, editor, ids = _build_annotation_graph(library_service.get_node_factory())
        controls = ui.row().classes("items-center gap-2")
        with controls:
            for name, node_id in ids.items():
                ui.label(node_id).props(f'data-testid="note-{name}"')

        def _linked_edge():
            return next(
                e
                for e in graph.edge_wrappers.values()
                if (e.outlet_port_id, e.inlet_port_id) == ("right_0", "left_0")
            )

        for testid, field, value in (
            ("style-start-circle", "arrow_start", "circle"),
            ("style-color-red", "color", "#ff0000"),
        ):
            on_click = lambda _, f=field, v=value: setattr(_linked_edge().style, f, v)  # noqa: E731
            with controls:
                ui.button(testid, on_click=on_click).props(f'data-testid="{testid}" dense')

        def _show_control_pins() -> None:
            graph.node_wrappers[ids["a"]].node.annotation.show_control_pins = True  # type: ignore[attr-defined]

        with controls:
            ui.button("show-control", on_click=_show_control_pins).props('data-testid="show-control" dense')
        _mount_graph_canvas(library_service, graph, editor, testid="annotation")
        _stamp_synced()

    # -------------------------------------------------------------------------
    # GET /graph-two-column
    #
    # A node on the two-column SplitNodeSkin plus direction buttons. Backs the
    # column-order rule: under R2L the columns swap with the pins, so a pin and
    # its own label stay on the same side of the card.
    # -------------------------------------------------------------------------

    @ui.page("/graph-two-column")
    async def graph_two_column_page():
        graph, editor = _build_two_column_graph(library_service.get_node_factory())

        def _set_direction(value: str) -> None:
            graph.props.layout_direction = value

        ui.button("set-r2l", on_click=lambda: _set_direction("r2l")).props('data-testid="set-r2l"')
        ui.button("set-l2r", on_click=lambda: _set_direction("l2r")).props('data-testid="set-l2r"')

        _mount_graph_canvas(library_service, graph, editor, testid="two-column")
        _stamp_synced()

    # -------------------------------------------------------------------------
    # GET /graph-error-skin
    #
    # A single node pinned to the error skin. Backs test_error_skin.py: every
    # port id must appear exactly once in the DOM (a duplicate shadows the real
    # pin via getElementById), and the card must carry the literal `node-card`
    # class so a manual resize is not silently clamped.
    # -------------------------------------------------------------------------

    @ui.page("/graph-error-skin")
    async def graph_error_skin_page():
        graph, editor, _node = _build_error_skin_graph(library_service.get_node_factory())
        _mount_graph_canvas(library_service, graph, editor, testid="error-skin")
        _stamp_synced()

    # -------------------------------------------------------------------------
    # GET /graph-swinglet-skins
    #
    # One float-swinglet probe per skin. Backs test_swinglet_skins.py: each
    # card must draw its swinglet pin exactly once, on the inlet side. Node ids
    # are on `probe-<name>` labels.
    # -------------------------------------------------------------------------

    @ui.page("/graph-swinglet-skins")
    async def graph_swinglet_skins_page():
        graph, editor, ids = _build_swinglet_skins_graph(library_service.get_node_factory())
        with ui.row():
            for name, node_id in ids.items():
                ui.label(node_id).props(f'data-testid="probe-{name}"')
        _mount_graph_canvas(library_service, graph, editor, testid="swinglet-skins")
        _stamp_synced()

    # -------------------------------------------------------------------------
    # GET /graph-swinglet
    #
    # Unlinked swinglet probes and an Add node on the full editor stack. Backs
    # test_graph_swinglet_connect.py: drags, reverse drops and reconnects that
    # involve a swinglet. Node ids are on `probe-<name>` labels; `server-edges`
    # lists the graph's own edge ids, sorted and joined by `|`.
    # -------------------------------------------------------------------------

    @ui.page("/graph-swinglet")
    async def graph_swinglet_page():
        graph, editor, ids = _build_swinglet_graph(library_service.get_node_factory())
        with ui.row():
            for name, node_id in ids.items():
                ui.label(node_id).props(f'data-testid="probe-{name}"')
            server_edges = ui.label().props('data-testid="server-edges"')

        def _refresh() -> None:
            server_edges.set_text("|".join(sorted(graph.edge_wrappers)))

        # Polled: the label must show what the graph holds, whichever path changed it.
        ui.timer(0.2, _refresh)
        _mount_graph_canvas(library_service, graph, editor, testid="swinglet")
        _stamp_synced()

    # -------------------------------------------------------------------------
    # GET /graph-size
    #
    # A single node on the full editor stack, for the node-sizing feature:
    #   - the host slot applies per-axis MINIMUM size (UINode._apply_size);
    #     content needing more space expands the node — nothing clips
    #   - the ResizeObserver measures auto axes back into props
    #   - the single-node 8-handle resize gadget in canvas.vue
    # Server-side buttons set size props deterministically so a browser test can
    # assert the slot honors the minimum (manual) / hugs content (auto) without
    # reaching into the editor from JS. Backs test_node_sizing.py.
    # -------------------------------------------------------------------------

    @ui.page("/graph-stage")
    async def graph_stage_page(channel: str = "stage"):
        from haywire.core.node.layout import CHANNELS

        graph, editor, node = _build_stage_graph(library_service.get_node_factory())
        ui.label(node.node_id).props(
            f'id="stage-node-id" data-testid="stage-node-id" data-node="{node.node_id}"'
        )
        chosen = next(c for c in CHANNELS if c.name == channel)
        _mount_graph_canvas(library_service, graph, editor, testid="stage", channel=chosen)
        _stamp_synced()

    # -------------------------------------------------------------------------
    # GET /graph-stage-gate
    #
    # Two annotations on a stage canvas. Backs test_stage_edge_gate.py: a pin
    # off the on-stage wires starts no drag on stage, an annotation pin does. Node ids are on
    # `probe-<name>` labels; `server-edges` lists the graph's edge ids, sorted
    # and joined by `|`.
    # -------------------------------------------------------------------------

    @ui.page("/graph-stage-gate")
    async def graph_stage_gate_page():
        from haywire.core.node.layout import STAGE

        graph, editor, ids = _build_stage_gate_graph(library_service.get_node_factory())
        with ui.row():
            for name, node_id in ids.items():
                ui.label(node_id).props(f'data-testid="probe-{name}"')
            server_edges = ui.label().props('data-testid="server-edges"')

        def _refresh() -> None:
            server_edges.set_text("|".join(sorted(graph.edge_wrappers)))

        ui.timer(0.2, _refresh)
        _mount_graph_canvas(library_service, graph, editor, testid="stage-gate", channel=STAGE)
        _stamp_synced()

    @ui.page("/graph-stack")
    async def graph_stack_page(channel: str = "patch"):
        from haywire.core.node.layout import CHANNELS

        graph, editor, back, front = _build_stack_graph(library_service.get_node_factory())
        ui.label("stack").props(
            f'id="stack-ids" data-testid="stack-ids" data-back="{back.node_id}" data-front="{front.node_id}"'
        )
        chosen = next(c for c in CHANNELS if c.name == channel)
        _mount_graph_canvas(library_service, graph, editor, testid="stack", channel=chosen)
        _stamp_synced()

    @ui.page("/graph-size")
    async def graph_size_page():
        graph, editor, node = _build_size_graph(library_service.get_node_factory())
        node_id = node.node_id

        def _set_manual_width_140() -> None:
            editor.set_property(node_id, "size_adapt", "manual_width")
            editor.set_property(node_id, "width", 140.0)

        def _set_manual_width_500() -> None:
            editor.set_property(node_id, "size_adapt", "manual_width")
            editor.set_property(node_id, "width", 500.0)

        def _set_auto() -> None:
            editor.set_property(node_id, "size_adapt", "auto")

        # Controls outside the canvas so they never intercept canvas gestures.
        ui.button("size-manual-width", on_click=_set_manual_width_140).props(
            'data-testid="size-manual-width"'
        )
        ui.button("size-manual-width-wide", on_click=_set_manual_width_500).props(
            'data-testid="size-manual-width-wide"'
        )
        ui.button("size-auto", on_click=_set_auto).props('data-testid="size-auto"')
        # Expose the single node's id so the test can target it directly.
        ui.label(node_id).props(f'id="size-node-id" data-testid="size-node-id" data-node="{node_id}"')

        _mount_graph_canvas(library_service, graph, editor, testid="size")
        _stamp_synced()

    # -------------------------------------------------------------------------
    # GET /graph-lock
    #
    # One node on a canvas locked for the session, as GraphEditor locks a level
    # (the level mode drops to operate and ``GraphCanvasManager.refresh_mode`` pushes it).
    # ``lock-node-id`` carries the node id; ``lock-node-pos`` shows the model's
    # ``props.posX,posY``, polled so it reflects whichever path changed it.
    # ``?stale=true`` locks the server side only, as for a page the lock has not
    # reached yet. Backs test_canvas_lock.py.
    # -------------------------------------------------------------------------

    # -------------------------------------------------------------------------
    # GET /graph-views
    #
    # A real GraphEditor level over the annotation graph, with two of its
    # linked nodes on the stage, and the editor's own Patch | Stage switch. The
    # level's keep-alive panels, lazy stage mount and view switch all run for
    # real. Backs test_graph_views.py.
    # -------------------------------------------------------------------------

    @ui.page("/graph-views")
    async def graph_views_page(view: str = "patch"):
        from types import SimpleNamespace

        from haybale_graph_editor.editors.graph_editor import DOCUMENT_LEVEL, GraphEditor
        from haybale_graph_editor.protocols import GraphContainer

        if theme_css:
            ui.add_css(theme_css)
        graph, editor, ids = _build_annotation_graph(library_service.get_node_factory())
        for name, x in (("c", 40.0), ("d", 360.0)):
            props = graph.node_wrappers[ids[name]].node.props
            props.on_stage = True
            props.stage_x = x
            props.stage_y = 40.0

        class _Container(GraphContainer):
            binding_id = "graph::views"
            display_name = "views"
            path = None
            unsaved = False

            def __init__(self) -> None:
                self.editor = editor

            def save(self, save_as=None):
                return None

        graph_editor = GraphEditor(
            SimpleNamespace(_binding_id="graph::views", editor_binding_id="graph::views")
        )  # type: ignore[arg-type]
        session, app_state = _harness_session(library_service, graph)
        context = session.context
        graph_editor._context = context
        graph_editor._project_state = app_state  # type: ignore[assignment]
        level = graph_editor._new_level(context, DOCUMENT_LEVEL, _Container())
        level.view = view
        graph_editor._levels[DOCUMENT_LEVEL] = level

        def _mutate_stage() -> None:
            # Membership, stage position and deletion, applied through the editor while whichever
            # view is showing; ``views-expected`` then lists every on-stage node and its stage pos.
            import json

            from haywire.core.node.layout import STAGE

            assert editor.add_to_stage([ids["a"]])
            graph.force_validation()
            assert editor.create_edge(ids["a"], "right_0", ids["d"], "left_2")
            graph.force_validation()
            assert editor.move_nodes_to({ids["d"]: {"x": 300.0, "y": 120.0}}, STAGE)
            graph.force_validation()
            assert editor.remove_elements([ids["c"]], [])
            graph.force_validation()
            expected = {
                nid: list(w.node.props.get_position(STAGE))
                for nid, w in graph.node_wrappers.items()
                if w.node.props.on_stage
            }
            expected_label.set_text(json.dumps(expected))

        ui.button("views-mutate", on_click=_mutate_stage).props('data-testid="views-mutate"')
        expected_label = ui.label("").props('data-testid="views-expected"')

        graph_editor._draw_view_switch(context)
        graph_editor._level_panels = (
            ui.tab_panels(value=level.panel_name, animated=False)
            .props("keep-alive")
            .style("width: 800px; height: 600px; position: relative; border: 1px solid #666;")
        )
        graph_editor._mount_level(context, level)
        _stamp_synced()

    # -------------------------------------------------------------------------
    # GET /graph-slot
    #
    # A real TabSlot hosting a real GraphEditor document with edges. The
    # ``slot-repayload`` button re-payloads the document the way a Save-As does
    # (``Slot.repayload``), moving it in GraphAppState first. Backs
    # test_slot_repayload.py.
    # -------------------------------------------------------------------------

    @ui.page("/graph-slot")
    async def graph_slot_page(edges: int = 4):
        from haybale_graph_editor.editors.graph_editor import GraphEditor
        from haybale_graph_editor.protocols import GraphContainer
        from haybale_graph_editor.state.graph_app_state import GraphAppState
        from haywire.ui.app.tab_slot import TabSlot
        from haywire.ui.editor.identity import SlotName
        from haywire.ui.editor.registry import EditorTypeRegistry

        graph, editor = _build_edge_batch_graph(library_service.get_node_factory(), edges)
        session, _app_state = _harness_session(library_service, graph)

        class _Container(GraphContainer):
            display_name = "slot"
            path = None
            unsaved = False

            def __init__(self) -> None:
                self.editor = editor
                self.id = "graph::slot-before"

            @property
            def binding_id(self) -> str:  # type: ignore[override]
                return self.id

            def save(self, save_as=None):
                return None

        container = _Container()
        graph_state = session.context.app_data[GraphAppState]
        graph_state.register(container)

        slot = TabSlot(
            session=session,  # type: ignore[arg-type]
            name=SlotName.EDIT,
            registry=library_service.injector.get(EditorTypeRegistry),
        )
        wrapper = slot.add_binding(
            GraphEditor.class_identity.registry_key, GraphEditor, binding_id=container.id, activate=True
        )
        assert wrapper is not None
        with ui.element("div").style("width: 900px; height: 700px; position: relative;"):
            slot.render(ui.column().classes("w-full h-full"))

        def _repayload() -> None:
            graph_state.rekey(container.id, "graph::slot-after")
            container.id = "graph::slot-after"
            assert slot.repayload(wrapper, container.id)

        ui.button("slot-repayload", on_click=_repayload).props('data-testid="slot-repayload"')
        _stamp_synced()

    @ui.page("/graph-lock")
    async def graph_lock_page(stale: bool = False):
        graph, editor, node = _build_size_graph(library_service.get_node_factory())
        node_id = node.node_id
        ui.label(node_id).props(f'data-testid="lock-node-id" data-node="{node_id}"')
        pos = ui.label().props('data-testid="lock-node-pos"')

        def _refresh() -> None:
            pos.set_text(f"{node.node.props.posX:g},{node.node.props.posY:g}")

        _refresh()
        ui.timer(0.2, _refresh)
        level = _HarnessLevel()
        manager = _mount_graph_canvas(library_service, graph, editor, testid="lock", level=level)
        level.mode = LevelMode.OPERATE
        if not stale:
            manager.refresh_mode()
        _stamp_synced()

    # -------------------------------------------------------------------------
    # GET /graph-enter?mode=view|operate|edit
    #
    # One Group card (two TestPrintNodes collapsed) on a real GraphCanvasManager.
    # ``enter-card-id`` carries the card's id; ``enter-log`` shows the node id of
    # the last SubgraphNavigation the session published — what the canvas asks
    # an editor to open. ``mode`` is the canvas's level mode. Backs
    # test_enter_by_double_click.py.
    # -------------------------------------------------------------------------

    @ui.page("/graph-enter")
    async def graph_enter_page(mode: str = "edit"):
        graph, editor, card_id = _build_enter_graph(library_service)
        ui.label(card_id).props(f'data-testid="enter-card-id" data-node="{card_id}"')
        log = ui.label("").props('data-testid="enter-log"')
        level = _HarnessLevel(mode=LevelMode(mode))
        manager = _mount_graph_canvas(library_service, graph, editor, testid="enter", level=level)
        _record_navigation(manager, log)
        _stamp_synced()

    # -------------------------------------------------------------------------
    # GET /graph-inset?mode=view|operate|edit&size=auto|manual&cull=0|1&view=patch|stage
    #
    # The ``/graph-enter`` Group card drawn with the Inset skin, its interior
    # holding a Float Slider on stage at (20, 20) and an annotation at (20, 90),
    # on a canvas in level mode ``mode`` (the card is on stage too; ``view=stage``
    # mounts the stage canvas). ``size=manual`` sizes the card 600 x 400 in both views
    # by hand; ``cull=1`` adds an ``enable-culling`` button (culling for any node
    # count and zoom). ``inset-card-id`` / ``inset-slider-id`` carry the ids; polled
    # echoes show the slider's ``value`` (``echo-inset-value``) and whether the
    # host history can undo (``echo-undo``, cleared after setup).
    # Backs test_inset.py.
    # -------------------------------------------------------------------------

    @ui.page("/graph-inset")
    async def graph_inset_page(mode: str = "edit", size: str = "auto", cull: int = 0, view: str = "patch"):
        from haybale_core.nodes.widgets.slider import FloatSliderNode
        from haybale_graph_editor.skins.inset_skin import InsetSkin
        from haywire.barn.builtin.nodes.annotation import AnnotationNode

        if theme_css:
            ui.add_css(theme_css)

        graph, editor, card_id = _build_enter_graph(library_service)
        card = graph.get_node_wrapper(card_id)
        assert card is not None
        definition = card.node.resolve_definition()  # type: ignore[attr-defined]
        slider = definition.create_node_wrapper(FloatSliderNode.class_identity.registry_key)
        assert slider is not None
        slider.node.props.on_stage = True
        slider.node.props.stage_x = 20.0
        slider.node.props.stage_y = 20.0
        # An annotation's on-stage pins carry data-node-id inside the Inset body.
        note = definition.create_node_wrapper(AnnotationNode.class_identity.registry_key)
        assert note is not None
        note.node.props.on_stage = True
        note.node.props.stage_x = 20.0
        note.node.props.stage_y = 90.0
        card.node.props.skin = InsetSkin.class_identity.registry_key
        card.node.props.stage_skin = InsetSkin.class_identity.registry_key
        card.node.props.on_stage = True
        if size == "manual":
            card.node.props.size_adapt = "manual"
            card.node.props.width = 600
            card.node.props.height = 400
            card.node.props.stage_size_adapt = "manual"
            card.node.props.stage_width = 600
            card.node.props.stage_height = 400
        editor.history_manager.clear()
        if cull:
            from haywire.ui.components.zoom.settings import EditorPanZoomSettings

            pz = EditorPanZoomSettings()
            # Armed only on the OFF->ON transition; see /graph-detail-culled.
            pz.cull_enabled = False
            pz.cull_min_nodes = 1
            pz.cull_min_zoom = 0.0

            def _enable_culling() -> None:
                pz.cull_enabled = True

            ui.button("enable-culling", on_click=_enable_culling).props('data-testid="enable-culling"')

        ui.label(card_id).props(f'data-testid="inset-card-id" data-node="{card_id}"')
        ui.label(slider.node_id).props(f'data-testid="inset-slider-id" data-node="{slider.node_id}"')
        value = ui.label().props('data-testid="echo-inset-value"')
        undo = ui.label().props('data-testid="echo-undo"')
        selection = ui.label().props('data-testid="echo-selection"')
        managers: list = []

        def _refresh() -> None:
            value.set_text(repr(slider.node.ports["value"].get_value()))
            undo.set_text(str(editor.history_manager.can_undo()))
            if managers:
                selection.set_text(",".join(sorted(managers[0].selected_nodes)))

        _refresh()
        ui.timer(0.2, _refresh)
        from haywire.core.node.layout import PATCH, STAGE

        managers.append(
            _mount_graph_canvas(
                library_service,
                graph,
                editor,
                testid="inset",
                channel=STAGE if view == "stage" else PATCH,
                level=_HarnessLevel(mode=LevelMode(mode)),
            )
        )
        _stamp_synced()

    # -------------------------------------------------------------------------
    # GET /graph-level-mode?mode=view|operate|edit
    #
    # The ``/graph-enter`` Group card, whose interface inlet shows a number
    # widget, a Fold Probe card (stacked skin, with fold headers), and a plain
    # card with a comment and a warning (so it draws the comment and the
    # diagnostics badge), on a canvas in level mode ``mode``.
    # An annotation card with the text "Harness note" sits beside them.
    # ``level-card-id``, ``level-fold-id``, ``level-badge-id`` and ``level-note-id``
    # carry the card ids; ``enter-log`` records an Enter; F9 drops the level to ``operate``,
    # F10 lifts it back to ``edit``.
    # Backs test_level_mode_gate.py.
    # -------------------------------------------------------------------------

    @ui.page("/graph-level-mode")
    async def graph_level_mode_page(mode: str = "view"):
        from haybale_testing.nodes.testbed.fold_probe import FoldProbeNode

        from haywire.core.node.node_warning import NodeWarning

        graph, editor, card_id = _build_enter_graph(library_service)
        fold = graph.create_node_wrapper(
            FoldProbeNode.class_identity.registry_key, position=(3400.0, 3950.0)
        )
        assert fold is not None
        badged = graph.create_node_wrapper(_ADD_FLOAT_KEY, position=(3750.0, 3950.0))
        assert badged is not None
        badged.node.props.comment = "Harness comment"
        badged.state.add_warning(NodeWarning(message="Harness warning", source_version=None))
        from haywire.barn.builtin.nodes.annotation import AnnotationNode

        note_key = AnnotationNode.class_identity.registry_key
        note = graph.create_node_wrapper(note_key, position=(4100.0, 3950.0))
        assert note is not None
        note.node.annotation.text = "Harness note"  # type: ignore[attr-defined]
        # A look apart from Quasar's field defaults, so the editor's inheritance shows.
        note.node.annotation.font_size = 30  # type: ignore[attr-defined]
        note.node.annotation.text_color = "#ff0000"  # type: ignore[attr-defined]
        note.node.annotation.underline = True  # type: ignore[attr-defined]
        ui.label(note.node_id).props(f'data-testid="level-note-id" data-node="{note.node_id}"')
        ui.label(card_id).props(f'data-testid="level-card-id" data-node="{card_id}"')
        ui.label(fold.node_id).props(f'data-testid="level-fold-id" data-node="{fold.node_id}"')
        ui.label(badged.node_id).props(f'data-testid="level-badge-id" data-node="{badged.node_id}"')
        log = ui.label("").props('data-testid="enter-log"')
        level = _HarnessLevel(mode=LevelMode(mode))
        manager = _mount_graph_canvas(library_service, graph, editor, testid="level", level=level)
        _record_navigation(manager, log)

        def _lock(event) -> None:
            # A key, not a button: a click would end the gesture the lock has to interrupt.
            if event.key == "F9" and event.action.keydown:
                level.mode = LevelMode.OPERATE
                manager.refresh_mode()
            elif event.key == "F10" and event.action.keydown:
                level.mode = LevelMode.EDIT
                manager.refresh_mode()

        ui.keyboard(on_key=_lock)
        _stamp_synced()

    # -------------------------------------------------------------------------
    # GET /graph-reroute
    #
    # Two nodes whose exec edge is split by a reroute. A reroute is resizable
    # like any node, and its skin positions both pins against the card edges —
    # so the only way to observe that they TRACK those edges (rather than
    # sitting where they happened to land at the intrinsic dot size) is to
    # resize the card in a browser and measure. Backs test_reroute_skin.py.
    # -------------------------------------------------------------------------

    # -------------------------------------------------------------------------
    # GET /graph-boundary
    #
    # A Subgraph Input and a Subgraph Output, each carrying stamped interface
    # ports plus their growing slot, rendered by SubgraphIOSkin. Backs the rail
    # skin's pin-geometry and ghost-pin tests.
    # -------------------------------------------------------------------------

    @ui.page("/graph-boundary")
    async def graph_boundary_page():
        from haywire.core.graph.base import BaseGraph
        from haywire.core.graph.editor import Editor
        from haywire.core.graph.scheduler import SyncScheduler
        from haywire.core.graph.subgraph import SubgraphDefinition

        factory = library_service.get_node_factory()
        host = BaseGraph("Boundary Fixture", validation_scheduler=SyncScheduler())
        definition = host.add_subgraph(
            SubgraphDefinition(key="sg", label="Group", validation_scheduler=SyncScheduler())
        )
        editor = Editor(definition, factory)

        from haybale_testing.types.test_types import TEST_FLOAT
        from haywire.barn.builtin.nodes.subgraph_io import SubgraphInputNode, SubgraphOutputNode
        from haywire.core.types.enums import PortOrigin

        inp = definition.create_node_wrapper(
            SubgraphInputNode.class_identity.registry_key, position=(3600.0, 3700.0)
        )
        out = definition.create_node_wrapper(
            SubgraphOutputNode.class_identity.registry_key, position=(4000.0, 3700.0)
        )
        assert inp is not None and out is not None  # noqa: PT018
        # exclude the growing slot: a bare rejig() flags every port, so the
        # slot would be dropped rather than kept beside the stamped interface.
        with inp.node.rejig(exclude=[PortOrigin.DECLARED]):
            inp.node.add(TEST_FLOAT.as_outlet("value", label="Value"))
        with out.node.rejig(exclude=[PortOrigin.DECLARED]):
            out.node.add(TEST_FLOAT.as_inlet("result", label="Result"))
        definition.force_validation()

        ui.label(inp.node_id).props(f'id="boundary-in-id" data-node="{inp.node_id}"')
        ui.label(out.node_id).props(f'id="boundary-out-id" data-node="{out.node_id}"')

        _mount_graph_canvas(library_service, definition, editor, testid="boundary")
        _stamp_synced()

    @ui.page("/graph-reroute")
    async def graph_reroute_page():
        graph, editor, reroute_id = _build_reroute_graph(library_service.get_node_factory())

        def _set_manual(width: float, height: float) -> None:
            editor.set_property(reroute_id, "size_adapt", "manual")
            editor.set_property(reroute_id, "width", width)
            editor.set_property(reroute_id, "height", height)

        ui.button("reroute-grow", on_click=lambda: _set_manual(160.0, 120.0)).props(
            'data-testid="reroute-grow"'
        )
        ui.label(reroute_id).props(
            f'id="reroute-node-id" data-testid="reroute-node-id" data-node="{reroute_id}"'
        )

        _mount_graph_canvas(library_service, graph, editor, testid="reroute")
        _stamp_synced()

    # -------------------------------------------------------------------------
    # GET /graph-widget-box
    #
    # Three nodes hosting the SAME oversized (1280x720) <img> content, differing
    # only in what their widget declares: nothing (content-sized), min_width
    # alone (inline-axis containment, height follows the aspect ratio), or both
    # axes (fully contained box). The declaration is the only variable, so a
    # test can attribute any difference in the node's size floor to it.
    # Backs test_widget_size_box.py.
    # -------------------------------------------------------------------------

    @ui.page("/graph-widget-box")
    async def graph_widget_box_page():
        from haywire.core.graph.editor import Editor

        graph = _harness_graph("Widget Box Fixture")
        editor = Editor(graph, library_service.get_node_factory())

        content = graph.create_node_wrapper(
            "haybale-testing:node:SizeBoxContentNode", position=(3600.0, 3700.0)
        )
        aspect = graph.create_node_wrapper(
            "haybale-testing:node:SizeBoxAspectNode", position=(4100.0, 3700.0)
        )
        fixed = graph.create_node_wrapper("haybale-testing:node:SizeBoxFixedNode", position=(4600.0, 3700.0))
        # Individually asserted so mypy narrows each one (a tuple membership
        # test does not); a failure also names the node that could not be built.
        assert content is not None, "could not create SizeBoxContentNode"
        assert aspect is not None, "could not create SizeBoxAspectNode"
        assert fixed is not None, "could not create SizeBoxFixedNode"

        def _set_manual(node_id: str, width: float, height: float) -> None:
            editor.set_property(node_id, "size_adapt", "manual")
            editor.set_property(node_id, "width", width)
            editor.set_property(node_id, "height", height)

        ui.button("aspect-grow", on_click=lambda: _set_manual(aspect.node_id, 520.0, 420.0)).props(
            'data-testid="aspect-grow"'
        )
        ui.button("fixed-grow", on_click=lambda: _set_manual(fixed.node_id, 520.0, 420.0)).props(
            'data-testid="fixed-grow"'
        )
        for name, wrapper in (("content", content), ("aspect", aspect), ("fixed", fixed)):
            ui.label(wrapper.node_id).props(
                f'id="{name}-node-id" data-testid="{name}-node-id" data-node="{wrapper.node_id}"'
            )

        _mount_graph_canvas(library_service, graph, editor, testid="widgetbox")
        _stamp_synced()

    # -------------------------------------------------------------------------
    # GET /graph-list-widget
    #
    # A SettingsNode on a canvas with Example String List promoted to config, so
    # its ArrayWidget draws on the card. A polled echo shows the setting's value.
    # Backs the card test in test_list_widget.py.
    # -------------------------------------------------------------------------

    @ui.page("/graph-list-widget")
    async def graph_list_widget_page():
        from haywire.core.graph.editor import Editor
        from haywire.core.node.promotion import promote_setting
        from haywire.core.types.enums import PortType

        graph = _harness_graph("List Widget Fixture")
        editor = Editor(graph, library_service.get_node_factory())
        wrapper = graph.create_node_wrapper("haybale-testing:node:SettingsNode", position=(3600.0, 3700.0))
        assert wrapper is not None, "could not create SettingsNode"
        promote_setting(wrapper.node, "example", "example_string_list", direction=PortType.CONFIG)

        ui.label(wrapper.node_id).props(f'data-testid="node-id" data-node="{wrapper.node_id}"')
        echo = ui.label().props('data-testid="echo-list"')

        def _refresh() -> None:
            echo.set_text(repr(wrapper.node.example.example_string_list))

        _refresh()
        ui.timer(0.2, _refresh)
        _mount_graph_canvas(library_service, graph, editor, testid="listwidget")
        _stamp_synced()

    # -------------------------------------------------------------------------
    # GET /graph-widget-nodes
    #
    # A stage canvas in level mode operate: a Float Slider (Max promoted to an
    # inlet) and a Menu on stage, the slider wired into a Float Number off stage.
    # Polled echoes show what the number's inlet and the menu's outlet hold.
    # Backs test_widget_nodes.py.
    # -------------------------------------------------------------------------

    @ui.page("/graph-widget-nodes")
    async def graph_widget_nodes_page():
        from haybale_core.nodes.widgets.menu import MenuNode
        from haybale_core.nodes.widgets.number import FloatNumberNode
        from haybale_core.nodes.widgets.slider import FloatSliderNode
        from haywire.core.graph.editor import Editor
        from haywire.core.node.layout import STAGE
        from haywire.core.node.promotion import promote_setting
        from haywire.core.types.enums import PortType

        # The studio's static CSS: the face uses its settings-row rules.
        if theme_css:
            ui.add_css(theme_css)

        graph = _harness_graph("Widget Nodes Fixture")
        editor = Editor(graph, library_service.get_node_factory())

        def _make(cls, x: float, y: float):
            wrapper = graph.create_node_wrapper(cls.class_identity.registry_key, position=(x, y))
            assert wrapper is not None, f"could not create {cls.__name__}"
            return wrapper

        slider = _make(FloatSliderNode, 3600.0, 3700.0)
        menu = _make(MenuNode, 3600.0, 3800.0)
        number = _make(FloatNumberNode, 4000.0, 3700.0)
        narrow = _make(FloatSliderNode, 3600.0, 3900.0)
        styled = _make(FloatSliderNode, 3600.0, 4000.0)
        capped = _make(FloatSliderNode, 3600.0, 4100.0)
        capped_narrow = _make(FloatSliderNode, 3600.0, 4200.0)
        promote_setting(slider.node, "range", "max", direction=PortType.INLET)
        placed = (
            (slider, (40.0, 40.0)),
            (menu, (40.0, 200.0)),
            (narrow, (40.0, 280.0)),
            (styled, (480.0, 40.0)),
            (capped, (480.0, 200.0)),
            (capped_narrow, (480.0, 280.0)),
        )
        for wrapper, (sx, sy) in placed:
            wrapper.node.props.on_stage = True
            wrapper.node.props.stage_x = sx
            wrapper.node.props.stage_y = sy
        assert graph.create_edge_wrapper(slider.node_id, "value", number.node_id, "in") is not None
        # A manually sized stage card: the face is centred in it and split 50/50.
        slider.node.props.stage_size_adapt = "manual"
        slider.node.props.stage_width = 400
        slider.node.props.stage_height = 120
        narrow.node.props.stage_size_adapt = "manual"
        narrow.node.props.stage_width = 260
        narrow.node.props.stage_height = 40
        for wrapper, (w, h) in ((styled, (400, 120)), (capped, (400, 60)), (capped_narrow, (140, 60))):
            wrapper.node.props.stage_size_adapt = "manual"
            wrapper.node.props.stage_width = w
            wrapper.node.props.stage_height = h
        styled.node.style.label_position = "above"
        styled.node.style.bold = True
        styled.node.style.background = "#203040"
        capped.node.style.max_label_width = 80
        capped_narrow.node.style.max_label_width = 80

        named = (
            ("slider", slider),
            ("menu", menu),
            ("narrow", narrow),
            ("styled", styled),
            ("capped", capped),
            ("capped_narrow", capped_narrow),
        )
        for name, wrapper in named:
            ui.label(wrapper.node_id).props(f'data-testid="{name}-node-id" data-node="{wrapper.node_id}"')
        downstream = ui.label().props('data-testid="echo-downstream"')
        picked = ui.label().props('data-testid="echo-menu"')

        def _refresh() -> None:
            downstream.set_text(repr(number.node.ports["in"].get_value()))
            picked.set_text(str(menu.node.ports["value"].get_value()))

        _refresh()
        ui.timer(0.2, _refresh)
        _mount_graph_canvas(
            library_service,
            graph,
            editor,
            testid="widgetnodes",
            channel=STAGE,
            level=_HarnessLevel(mode=LevelMode.OPERATE),
        )
        _stamp_synced()

    # -------------------------------------------------------------------------
    # GET /keymap
    #
    # One KeymapListener (Control is Mod) over two editor roots, ed::one and
    # ed::two, in #hw-slot-edit. ed::one holds a text input and a pointer-local
    # hook answering [12, 34]. #fake-dialog (classed .q-dialog) holds a plain
    # button, #dialog-button. #last-command / #command-log record what reached
    # Python as "<command_id>@<binding_id>". Backs test_keymap_listener.py.
    # -------------------------------------------------------------------------

    @ui.page("/keymap")
    async def keymap_page():
        from haywire.ui.components.keymap import KeymapListener

        last_command = ui.label("none").props('id="last-command"')
        last_payload = ui.label("none").props('id="last-payload"')
        last_target = ui.label("none").props('id="last-target"')
        command_log = ui.label("").props('id="command-log"')
        ui.label("outside").props('id="outside"')
        log: list[str] = []

        def on_command(payload: dict) -> None:
            entry = f"{payload['command_id']}@{payload['binding_id']}"
            log.append(entry)
            last_command.set_text(entry)
            last_payload.set_text(f"{payload['position']}|{payload['text']}")
            command_log.set_text(",".join(log))

        def on_target(payload: dict) -> None:
            last_target.set_text(payload["binding_id"])

        listener = KeymapListener(on_command=on_command, on_target=on_target, platform="other")
        listener.set_keymap(
            {
                "editors": {
                    "ed": {
                        "Mod+A": "select_all",
                        "Delete": "delete",
                        "Mod+V": "paste",
                        "Mod+C": "copy",
                        "Mod+Alt+L": "alt_l",
                        "Mod+S": "save",
                    }
                },
                "native": {"paste": "paste"},
                "text_fields": ["save"],
            }
        )

        root_style = "width: 300px; min-height: 80px; padding: 16px; border: 1px solid #666;"
        with ui.element("div").props('id="hw-slot-edit"'):
            with ui.element("div").props('data-hw-binding="ed::one" data-hw-editor="ed"').style(root_style):
                ui.element("input").props('type="text"')
                ui.element("div").props("data-hw-pointer-local").style("width: 40px; height: 20px;")
                # A field that commits on blur, as a commit-mode TextWidget does; its blur reaches the log.
                commit_field = ui.element("textarea").props('id="commit-field"')

                def on_blur() -> None:
                    log.append("blur")
                    command_log.set_text(",".join(log))

                commit_field.on("blur", on_blur)
                ui.element("div").classes("cm-editor").props('contenteditable="true" id="code-field"').style(
                    "min-height: 20px;"
                )
            ui.element("div").props('data-hw-binding="ed::two" data-hw-editor="ed"').style(root_style)
        with ui.element("div").classes("q-dialog").props('id="fake-dialog"'):
            ui.element("button").props('id="dialog-button" type="button"')
        ui.run_javascript(
            "document.querySelector('[data-hw-pointer-local]').hwPointerLocal = () => [12, 34]"
        )
        _stamp_synced()

    # -------------------------------------------------------------------------
    # GET /graph-keymap
    #
    # One node on the full editor stack inside an editor root (graph::main),
    # under a KeymapListener (Control is Mod) holding the graph editor's keymap.
    # Standing in for the AppShell, the page runs a "copy" command as
    # copy_selection() and a "paste" command as paste(position, text) on the
    # canvas manager. #clipboard-json shows the session clipboard after a copy.
    # Backs test_keymap_listener.py.
    # -------------------------------------------------------------------------

    @ui.page("/graph-keymap")
    async def graph_keymap_page():
        import json

        from haywire.ui.components.keymap import KeymapListener
        from haywire.ui.keymap import build_keymap
        from haybale_graph_editor.editors.graph_editor import GraphEditor
        from haybale_graph_editor.state.edit_state import EditState

        graph, editor, _ = _build_size_graph(library_service.get_node_factory())
        clipboard_json = ui.label("").props('id="clipboard-json"').style("display: none")

        with ui.element("div").props('data-hw-binding="graph::main" data-hw-editor="graph"'):
            manager = _mount_graph_canvas(library_service, graph, editor, testid="keymap")

        def on_command(payload: dict) -> None:
            if payload["command_id"] == "copy":
                manager.copy_selection()
                clipboard = manager._session.context.data[EditState].clipboard
                clipboard_json.set_text(json.dumps(clipboard.payload) if clipboard is not None else "")
            elif payload["command_id"] == "paste" and payload["position"] is not None:
                x, y = payload["position"]
                manager.paste((x, y), payload["text"])

        listener = KeymapListener(on_command=on_command, on_target=lambda payload: None, platform="other")
        listener.set_keymap(build_keymap({"graph": GraphEditor}, lambda tier: True).to_client())
        _stamp_synced()

    # -------------------------------------------------------------------------
    # GET /copy-button
    #
    # A bare hui.code_snippet() with its default copy button. Backs the
    # copy-to-clipboard browser regression: localhost is a secure context, so
    # clicking the button exercises the navigator.clipboard.writeText() path
    # (not the execCommand fallback) and should raise a "Copied to clipboard"
    # ui.notify(). See test_copy_button_browser.py.
    # -------------------------------------------------------------------------

    @ui.page("/copy-button")
    async def copy_button_page():
        if theme_css:
            ui.add_css(theme_css)

        with ui.card().classes("w-full max-w-md mx-auto mt-8 p-4"):
            hui.code_snippet("copy-me")
        _stamp_synced()

    # -------------------------------------------------------------------------
    # POST /api/set?key=<key>&value=<value>
    # -------------------------------------------------------------------------

    @nicegui_app.post("/api/set")
    async def api_set(request: Request):
        params = dict(request.query_params)
        key = params.get("key", "")
        raw_value = params.get("value", "")
        if not key:
            return JSONResponse({"error": "missing key"}, status_code=400)
        try:
            defn = registry.get_definition(key)
            if defn is None:
                return JSONResponse({"error": f"unknown key: {key}"}, status_code=404)
            # Coerce to the field's Python value type. defn._type is an IType
            # (post widget-unification cutover); its element_type_cls is the
            # underlying Python type (FLOAT -> float, BOOL -> bool, ...).
            py_type = getattr(defn._type, "element_type_cls", None) or str
            coerced: Any
            if py_type is bool:
                coerced = raw_value.lower() in ("true", "1", "yes")
            else:
                coerced = py_type(raw_value)
            registry.set_global(key, coerced)
            return JSONResponse({"ok": True, "key": key, "value": coerced})
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=500)
