"""
GraphCanvasVue - Vue-based graph canvas component for NiceGUI

This component provides a clean Python wrapper around a Vue component that handles
all client-side graph canvas interactions with the enhanced event system.

"""

import logging
from typing import Any, Callable, Mapping, Optional
from pathlib import Path

from nicegui import ui

from haywire.core.access import LevelMode
from haywire.core.edge.settings import EdgeDefaultSettings
from haywire.ui.components.graph.event_definitions import BaseGraphEvent, GRAPH_EVENT_REGISTRY
from haywire.ui.components.graph.settings import CanvasSettings
from haywire.ui.components.zoom.settings import EditorPanZoomSettings

_GRAPH_EVENTS_JS = Path(__file__).parent / "generated" / "graph_events.js"
_ARROW_HEADS_JS = Path(__file__).parent / "generated" / "arrow_heads.js"

logger = logging.getLogger(__name__)

_CANVAS_SETTING_PROPS: dict[str, str] = {
    "bg_pattern": "bg-pattern",
    "grid_color": "grid-color",
    "grid_enabled": "grid-enabled",
    "grid_size": "grid-size",
    "grid_subdivisions": "grid-subdivisions",
    "snap_to_grid": "snap-to-grid",
    "snap_scale_to_grid": "snap-scale-to-grid",
}

# Studio-wide edge settings → Vue prop names. The graph-overridable edge defaults
# arrive through set_edge_defaults instead.
_EDGE_SETTING_PROPS: dict[str, str] = {
    "hit_padding": "edge-hit-padding",
}

# Hover-magnifier settings → Vue prop names. The magnifier lives in canvas.vue
# (graph-aware: it owns per-node hover hooks, edge refresh and zoomState), so the
# settings are routed here rather than to the generic ZoomPanContainer.
_HOVER_SETTING_PROPS: dict[str, str] = {
    "hover_scale_enabled": "hover-scale-enabled",
    "hover_scale_max": "hover-scale-max",
    "hover_scale_cutoff_zoom": "hover-scale-cutoff-zoom",
    "hover_enter_delay": "hover-enter-delay",
    "hover_exit_delay": "hover-exit-delay",
}


# list[Path] vs ui.element's invariant list[str | Path]; a list of paths is a valid dependencies arg.
class GraphCanvasVue(ui.element, component="canvas.vue", dependencies=[_GRAPH_EVENTS_JS, _ARROW_HEADS_JS]):  # ty: ignore[invalid-argument-type]
    """Vue-based graph canvas component with ONLY unified event handling."""

    def __init__(
        self,
        on_canvas_event: Optional[Callable[[BaseGraphEvent], None]] = None,
        zoom_container=None,
        canvas_width: int = 8000,
        canvas_height: int = 8000,
        origin: float = 0.0,
        stage: bool = False,
    ):
        """Create the canvas element.

        Args:
            origin: Canvas position, on both axes, of the stage origin. ``0`` draws no marker.
            stage: Whether this canvas shows a stage view. A stage canvas paints its cards by
                stacking order alone: hovering, selecting or dragging a card does not raise it.
                It never magnifies a card on hover, whatever the hover-magnifier settings say.
        """
        super().__init__()

        self._on_canvas_event = on_canvas_event
        self.zoom_container = zoom_container

        # Props for Vue component
        self._props["containerId"] = f"graph-canvas-{id(self)}"
        # The same value as an attribute that actually survives to the DOM.
        # The template's ``:id="containerId"`` does not: NiceGUI stamps its own
        # element id on the component root, so the id never lands and a
        # ``getElementById`` on it finds nothing.
        self._props["data-hw-canvas-id"] = self._props["containerId"]
        self._props["canvasWidth"] = canvas_width
        self._props["canvasHeight"] = canvas_height
        self._props["originX"] = origin
        self._props["originY"] = origin
        self._stage = stage
        if stage:
            self._props["data-hw-stage"] = True
        self._props["data-graph_canvas"] = True
        # The sibling ZoomPanContainer broadcasts ``zoom-pan-state`` events on
        # ``document``; canvas.vue uses this id to ignore events from other
        # canvases' pan/zoom containers (otherwise panning editor B would
        # corrupt editor A's zoomState and render edges with wrong coords).
        self._props["zoomContainerId"] = zoom_container.container_id if zoom_container else ""
        # Until set_gesture_requires, every gesture is refused: no entry means no mode reaches it.
        self._props["gestureRequires"] = {}

        # Canvas appearance settings: push initial values and live-update on change.
        self._canvas_settings = CanvasSettings()
        self._apply_canvas_setting_props()
        self._canvas_settings._subscribe(self._on_canvas_setting_changed)

        self._edge_settings = EdgeDefaultSettings()
        for name, prop in _EDGE_SETTING_PROPS.items():
            self._props[prop] = getattr(self._edge_settings, name)
        self._edge_settings._subscribe(self._on_edge_setting_changed)

        # Hover-magnifier settings: push initial values and live-update on change.
        self._pz_settings = EditorPanZoomSettings()
        self._apply_hover_setting_props()
        self._pz_settings._subscribe(self._on_setting_changed)

        # Register single unified event handler
        self.on("canvasEvent", self._handle_canvas_event)

    @property
    def container_id(self) -> str:
        """This canvas's unique value for ``data-hw-canvas-id``.

        Every mounted canvas repeats the same template, so ids inside it
        (``connection-svg``, ``node-container``) are duplicated wherever two
        canvases are on screen at once. Reach the right one with
        :attr:`dom_selector`, never with ``getElementById``.
        """
        return str(self._props["containerId"])

    @property
    def dom_selector(self) -> str:
        """CSS selector matching this canvas's root element, and no other's."""
        return f'[data-hw-canvas-id="{self.container_id}"]'

    def _apply_canvas_setting_props(self) -> None:
        """Push current canvas appearance settings to Vue props."""
        for name, prop in _CANVAS_SETTING_PROPS.items():
            self._props[prop] = getattr(self._canvas_settings, name)

    def set_edge_defaults(self, arrow: str, arrow_size: str, width: float) -> None:
        """Push the graph's computed-edge arrow head (a head name or ``none``), its size (a key of
        ``HEAD_SIZES``) and width in pixels."""
        self._props["edge-arrow"] = arrow
        self._props["edge-arrow-size"] = arrow_size
        self._props["edge-width"] = width
        self.update()

    def _on_canvas_setting_changed(self, name: str, value, _old) -> None:
        """Propagate a canvas appearance settings change to the Vue component."""
        prop = _CANVAS_SETTING_PROPS.get(name)
        if prop is not None:
            self._props[prop] = value
            self.update()

    def _on_edge_setting_changed(self, name: str, value, _old) -> None:
        """Propagate a studio-wide edge settings change to the Vue component."""
        prop = _EDGE_SETTING_PROPS.get(name)
        if prop is not None:
            self._props[prop] = value
            self.update()

    def _apply_hover_setting_props(self) -> None:
        """Push current hover-magnifier settings to Vue props."""
        for name, prop in _HOVER_SETTING_PROPS.items():
            self._props[prop] = self._hover_value(name, getattr(self._pz_settings, name))

    def _on_setting_changed(self, name: str, value, old) -> None:
        """Propagate a hover-magnifier settings change to the Vue component."""
        prop = _HOVER_SETTING_PROPS.get(name)
        if prop is not None:
            self._props[prop] = self._hover_value(name, value)
            self.update()

    def _hover_value(self, name: str, value: Any) -> Any:
        """The value a hover-magnifier setting takes on this canvas: off on a stage."""
        return False if self._stage and name == "hover_scale_enabled" else value

    def _handle_canvas_event(self, event_data):
        """Unified canvas event handler - routes to GraphCanvasManager"""
        if self._on_canvas_event and hasattr(event_data, "args"):
            event = event_data.args
            event_type = event.get("event_type")

            # Log for debugging
            logger.debug(f"🔄 Vue→Python Event: {event_type} | Data: {event.get('data', {})}")

            # Create event instance from registry
            if event_type in GRAPH_EVENT_REGISTRY:
                event_class = GRAPH_EVENT_REGISTRY[event_type]
                try:
                    event_instance = event_class.from_dict(event)
                    self._on_canvas_event(event_instance)
                except Exception as e:
                    logger.error(f"Error creating event instance for {event_type}: {e}")
            else:
                logger.warning(f"Unknown event type: {event_type}")

    def set_canvas_size(self, width: int, height: int) -> None:
        """Push new canvas dimensions to the Vue component."""
        self._props["canvasWidth"] = width
        self._props["canvasHeight"] = height
        self.update()

    def set_level_mode(self, mode: LevelMode) -> None:
        """Show the canvas in level mode ``mode`` in the browser.

        A gesture starts only when ``mode`` reaches the level mode its event
        type needs (see ``set_gesture_requires``). Click, Shift-click and box
        select work in every mode. Card content takes no pointer input below
        ``EDIT`` except elements whose ``data-hw-requires`` ``mode`` satisfies.
        A canvas that was never given a mode shows ``VIEW``.
        """
        self._props["levelMode"] = mode.value
        self.update()

    def set_gesture_requires(self, requires: Mapping[str, LevelMode]) -> None:
        """Tell the browser the level mode each gesture's event type needs.

        A gesture whose event type has no entry is refused in every mode and
        logged in the browser console.

        Args:
            requires: Event type (``BaseGraphEvent.event_type``) to the lowest
                level mode that may emit it.
        """
        self._props["gestureRequires"] = {event_type: mode.value for event_type, mode in requires.items()}
        self.update()

    def emit_sync_event(self, event: BaseGraphEvent):
        """
        Send sync event to Vue component - THE ONLY COMMUNICATION METHOD
        """
        # Don't send events if component is being cleaned up
        if getattr(self, "_is_cleanup", False):
            return

        event_dict = event.to_dict()
        event_type = event_dict.get("event_type")
        data = event_dict.get("data", {})

        logger.debug(f"🔄 Python→Vue Event: {event_type} | Data: {data}")

        # Send to Vue component via handleSyncEvent - the ONLY run_method call
        self.run_method("handleSyncEvent", event_dict)

    def cleanup(self):
        """Cleanup resources and references."""
        self._is_cleanup = True
        # Drop the settings subscriptions so this instance isn't kept alive (and
        # doesn't fire into a torn-down component) across hot-reload / tab close.
        try:
            self._canvas_settings._unsubscribe(self._on_canvas_setting_changed)
        except Exception:
            pass
        try:
            self._edge_settings._unsubscribe(self._on_edge_setting_changed)
        except Exception:
            pass
        try:
            self._pz_settings._unsubscribe(self._on_setting_changed)
        except Exception:
            pass
        self._on_canvas_event = None
        self.zoom_container = None
