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
from typing import Any, TYPE_CHECKING

from fastapi import Request
from fastapi.responses import JSONResponse
from nicegui import app as nicegui_app
from nicegui import ui

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
    from haywire.core.graph.base import BaseGraph
    from haywire.core.graph.editor import Editor

    graph = BaseGraph("Reconnect Fixture")
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
    from haywire.core.graph.base import BaseGraph
    from haywire.core.graph.editor import Editor

    graph = BaseGraph("Connect Fixture")
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
    from haywire.core.graph.base import BaseGraph
    from haywire.core.graph.editor import Editor

    graph = BaseGraph("Dynamic Fixture")
    editor = Editor(graph, node_factory)

    dyn = graph.create_node_wrapper(_DYNAMIC_KEY, position=(3600.0, 3700.0))
    sink = graph.create_node_wrapper(_EDGE_LINK_KEY, position=(3980.0, 3700.0))
    assert dyn is not None and sink is not None, "could not create dynamic-fixture nodes"  # noqa: PT018

    ok = editor.create_edge(dyn.node_id, _DYNAMIC_OUTLET, sink.node_id, _EDGE_LINK_INLET)
    assert ok, f"could not connect {_DYNAMIC_OUTLET} -> {_EDGE_LINK_INLET}"
    return graph, editor, dyn


def _build_size_graph(node_factory):
    """A single node, for the node-sizing gadget/measure tests.

    One TestPrintNode is enough: the sizing feature is per-node and needs no
    edges. Returns (graph, editor, node) so the route can drive size props and
    the test can select/resize it. See test_node_size_measure / test_resize_gadget.
    """
    from haywire.core.graph.base import BaseGraph
    from haywire.core.graph.editor import Editor

    graph = BaseGraph("Size Fixture")
    editor = Editor(graph, node_factory)

    node = graph.create_node_wrapper(_RECONNECT_SINK_KEY, position=(3700.0, 3700.0))
    assert node is not None, f"could not create {_RECONNECT_SINK_KEY}"
    return graph, editor, node


class _HarnessProjectState:
    """Minimal IProjectState stand-in for harness routes that need a Session.

    The studio's HaywireApp is the real app_state; sessions read only a few
    attributes off it (``library_state_container`` and ``on_disconnect`` on the
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
        self.widget_factory = library_service.get_widget_factory()
        self.library_state_container = library_service.injector.get(LibraryStateContainer)

    def on_disconnect(self, *args, **kwargs) -> None:  # session teardown hook
        pass


def _mount_graph_canvas(library_service, graph, editor, testid: str):
    """Boot a real GraphCanvasManager over (graph, editor) inside the page.

    Wires the full editor stack — session, handlers, context-menu provider —
    exactly as the studio does, so canvas interactions (connect, reconnect,
    context menus) run end-to-end. Returns the GraphCanvasManager.
    """
    from haywire.core.di.context import get_workspace_root
    from haywire.core.session.session_manager import SessionManager
    from haywire.core.signals import SignalDispatcher
    from haywire.core.session.workspace.manager import WorkspaceManager
    from haybale_graph_editor.editors.graph_canvas.graph_canvas_manager import GraphCanvasManager
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

    with ui.element("div").style("width: 800px; height: 600px; position: relative; border: 1px solid #666;"):
        manager = GraphCanvasManager(
            editor=editor,
            skin_factory=library_service.get_skin_factory(),
            node_factory=library_service.get_node_factory(),
            panel_registry=library_service.get_panel_registry(),
            session=session,
        )
        manager.zoom_container.props(f'data-testid="{testid}-zoom"')
        manager.canvas_vue.props(f'data-testid="{testid}-canvas"')
        manager.sync_with_graph()
        manager.zoom_container._on_ready = manager.zoom_container.center_on_content
    return manager


def _build_theme_css(registry: "SettingsRegistry", theme_registry) -> str:
    """Build :root CSS block from the first available workbench theme."""
    valid_keys = [k for k in theme_registry.list_workbench_keys() if not k.startswith("__system__:")]
    if not valid_keys:
        return ""
    theme_key, _ = registry.resolve("workbench.theme")
    if theme_key not in valid_keys:
        theme_key = valid_keys[0]
    theme = theme_registry.get_workbench(theme_key)
    vars_str = " ".join(f"{k}: {v};" for k, v in theme.to_css_vars().items())
    return f":root {{ {vars_str} }}"


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
                render_settings(settings_instance)
            except Exception as exc:
                ui.label(f"Error: {exc}").classes("text-red-400 text-xs")
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
                render_settings(settings_instance)

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
                render_schema(schema_cls, registry)
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

        def on_canvas_event(event) -> None:
            event_type = getattr(event, "event_type", event.__class__.event_type)
            canvas_x = getattr(event, "canvasX", None)
            canvas_y = getattr(event, "canvasY", None)
            last_event.set_text(event_type)
            last_coords.set_text(f"{canvas_x},{canvas_y}")
            if event_type.startswith("contextMenu"):
                last_context_menu.set_text(event_type)

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
        _stamp_synced()

    # -------------------------------------------------------------------------
    # GET /graph-reconnect
    #
    # Boots a real graph editor (GraphCanvasManager + handlers + context-menu
    # provider) over a tiny two-node/one-edge fixture, so the full reconnect
    # pipeline runs end-to-end in a browser. Backs the edge-reconnect Playwright
    # regression test (the anchor end must stay glued to its pin even though the
    # node DOM is rebuilt during reconnect). See test_graph_reconnect.py.
    # -------------------------------------------------------------------------

    @ui.page("/graph-reconnect")
    async def graph_reconnect_page():
        import tempfile
        from pathlib import Path

        from haywire.core.graph.base import BaseGraph
        from haywire.core.graph.editor import Editor

        # Generate the fixture programmatically and round-trip it through a real
        # .haywire file so the test exercises the live serialization path.
        node_factory = library_service.get_node_factory()
        with tempfile.NamedTemporaryFile(suffix=".haywire", delete=False) as tmp:
            fixture = Path(tmp.name)
        _write_reconnect_graph(node_factory, fixture)

        graph = BaseGraph("Reconnect Fixture")
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
        from haywire.core.graph.base import BaseGraph
        from haywire.core.graph.editor import Editor

        graph = BaseGraph("Widget Box Fixture")
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
