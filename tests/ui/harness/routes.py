"""
Harness route handlers for the Settings UI test harness.

Routes:
  GET  /status               — liveness probe, returns {"status": "ok"}
  GET  /node?class=...&bag=  — render a NodeSettings bag via render_reactive()
  GET  /schema?class=...     — render a LibrarySettings/FrameworkSettings via render_schema()
  POST /api/set?key=&value=  — write a value to the SettingsRegistry workspace tier
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

from fastapi import Request
from fastapi.responses import JSONResponse
from nicegui import app as nicegui_app
from nicegui import ui

from haywire.ui.components.graph.canvas import GraphCanvasVue
from haywire.ui.components.zoom.pan import ZoomPanContainer
from haywire.ui.panel.render_utils import render_settings, render_schema
from haywire.core.settings.enums import SettingMode

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

    # -------------------------------------------------------------------------
    # GET /graph-context-menu
    # -------------------------------------------------------------------------

    @ui.page("/graph-context-menu")
    async def graph_context_menu_page():
        last_event = ui.label("none").props('id="last-event" data-testid="last-event"')
        last_coords = ui.label("-").props('id="last-coords" data-testid="last-coords"')

        def on_canvas_event(event) -> None:
            event_type = getattr(event, "event_type", event.__class__.event_type)
            canvas_x = getattr(event, "canvasX", None)
            canvas_y = getattr(event, "canvasY", None)
            last_event.set_text(event_type)
            last_coords.set_text(f"{canvas_x},{canvas_y}")

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
            # Coerce to the correct type
            type_ = defn._type or str
            if type_ is bool:
                coerced = raw_value.lower() in ("true", "1", "yes")
            else:
                coerced = type_(raw_value)
            registry.set_global(key, coerced, SettingMode.EXPLICIT)
            return JSONResponse({"ok": True, "key": key, "value": coerced})
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=500)
