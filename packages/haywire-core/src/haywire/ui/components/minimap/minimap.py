from __future__ import annotations

from typing import TYPE_CHECKING

from nicegui import ui

from haywire.ui.components.minimap.settings import MinimapSettings

if TYPE_CHECKING:
    from haywire.ui.components.zoom.pan import ZoomPanContainer


class MinimapCanvas(ui.element, component="minimap.vue"):
    """
    A canvas-based minimap for the ZoomPanContainer.

    Renders as a custom Vue component (minimap.vue) that listens to
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
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)

        self._settings      = MinimapSettings()
        self.zoom_container = zoom_container
        self.minimap_width  = self._settings.width
        self.is_visible     = self._settings.enabled

        mm = self._settings
        self._props["container-id"]   = zoom_container.container_id
        self._props["minimap-width"]  = mm.width
        self._props["position"]       = mm.position
        self._props["active-opacity"] = mm.opacity
        self._props["ghost-opacity"]  = mm.ghost_opacity
        self._props["debug-info"]     = mm.debug_info
        self._props["visible"]        = mm.enabled

        self._settings.subscribe(self._on_setting_changed)

    def _on_setting_changed(self, name: str, value, _old) -> None:
        """Apply a MinimapSettings change to this canvas instance."""
        if name == "enabled":
            self.set_enabled(value)
        elif name == "position":
            self.set_position(value)
        elif name == "width":
            self.set_width(value)
        elif name == "opacity":
            self.set_opacity(value)
        elif name == "ghost_opacity":
            self.set_ghost_opacity(value)
        elif name == "debug_info":
            self.set_debug_info(value)

    # ── Public API ────────────────────────────────────────────────────────────

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

    def set_canvas_size(self, width: int, height: int) -> None:
        """Update the canvas dimensions the minimap represents."""
        self._props["canvasSize"] = max(width, height)
        self.update()

    def refresh_content(self) -> None:
        """Force a content re-scan and redraw."""
        self.run_method("scanContent")
