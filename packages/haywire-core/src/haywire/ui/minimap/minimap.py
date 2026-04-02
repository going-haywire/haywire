from __future__ import annotations

from typing import TYPE_CHECKING

from nicegui import ui

if TYPE_CHECKING:
    from haywire.ui.pan_zoom.zoom_pan_vue import ZoomPanContainer


class MinimapCanvas(ui.element, component="minimap_canvas.vue"):
    """
    A canvas-based minimap for the ZoomPanContainer.

    Renders as a custom Vue component (minimap_canvas.vue) that listens to
    'zoom-pan-state' DOM events from ZoomPanContainer for real-time viewport
    sync — no Python round-trip needed per frame.

    Features:
    - Canvas-based rendering for performance
    - Click-to-center and drag-to-pan navigation
    - Real-time viewport sync via DOM events
    - Fade in/out opacity transitions
    - Settings-driven: size, position, opacity, debug overlay
    """

    def __init__(
        self,
        zoom_container: ZoomPanContainer,
        width: int = 200,
        position: str = "top-right",
        visible: bool = True,
        opacity: float = 0.88,
        ghost_opacity: float = 0.15,
        debug_info: bool = False,
        **kwargs,  # absorbs legacy background_color / content_color / viewport_color
    ) -> None:
        super().__init__(**kwargs)

        self.zoom_container = zoom_container
        self.minimap_width  = width
        self.is_visible     = visible

        self._props["container-id"]   = zoom_container.container_id
        self._props["minimap-width"]  = width
        self._props["position"]       = position
        self._props["active-opacity"] = opacity
        self._props["ghost-opacity"]  = ghost_opacity
        self._props["debug-info"]     = debug_info
        self._props["visible"]        = visible

    # ── Public API (called by ZoomPanContainer._on_minimap_setting_changed) ────

    def set_enabled(self, enabled: bool) -> None:
        """Show or hide the minimap."""
        self.is_visible        = enabled
        self._props["visible"] = enabled
        self.update()

    def toggle_visibility(self) -> None:
        """Toggle minimap visibility."""
        self.set_enabled(not self.is_visible)

    def set_position(self, position: str) -> None:
        """Change the minimap corner position."""
        self._props["position"] = position
        self.update()

    def set_width(self, width: int) -> None:
        """Update minimap width; the Vue watcher recalculates height and scale."""
        self.minimap_width           = width
        self._props["minimap-width"] = width
        self.update()

    def set_opacity(self, opacity: float) -> None:
        """Set the active (blended-in) opacity."""
        self._props["active-opacity"] = opacity
        self.update()

    def set_ghost_opacity(self, opacity: float) -> None:
        """Set the resting (idle) opacity."""
        self._props["ghost-opacity"] = opacity
        self.update()

    def set_debug_info(self, enabled: bool) -> None:
        """Toggle the debug overlay on the minimap canvas."""
        self._props["debug-info"] = enabled
        self.update()

    def refresh_content(self) -> None:
        """Force a content re-scan and redraw."""
        self.run_method("scanContent")
