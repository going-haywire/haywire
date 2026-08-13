from __future__ import annotations

from typing import TYPE_CHECKING

from nicegui import ui

from haywire.ui.components.debug_overlay.settings import DebugOverlaySettings

if TYPE_CHECKING:
    from haywire.ui.components.zoom.pan import ZoomPanContainer


class DebugOverlay(ui.element, component="debug_overlay.vue"):
    """
    A floating performance/debug HUD for the ZoomPanContainer.

    Renders as a custom Vue component (debug_overlay.vue) that measures FPS,
    frame time, worst-1% jank, main-thread long tasks and a live DOM census
    entirely client-side — no Python round-trip per frame. Zoom/pan/LOD are read
    directly from the container.

    Settings-driven: enabled (visibility) and corner position, both independent
    of the minimap so the overlay can sit in any corner.
    """

    def __init__(
        self,
        zoom_container: ZoomPanContainer,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)

        self._settings = DebugOverlaySettings()
        self.zoom_container = zoom_container
        self.is_visible = self._settings.enabled

        do = self._settings
        self._props["container-id"] = zoom_container.container_id
        self._props["position"] = do.position
        self._props["visible"] = do.enabled
        self._props["census-interval-ms"] = do.census_interval_ms

        self._settings.subscribe(self._on_setting_changed)

    def _on_setting_changed(self, name: str, value, _old) -> None:
        """Apply a DebugOverlaySettings change to this overlay instance."""
        if name == "enabled":
            self.set_enabled(value)
        elif name == "position":
            self.set_position(value)
        elif name == "census_interval_ms":
            self.set_census_interval(value)

    # ── Public API ────────────────────────────────────────────────────────────

    def set_enabled(self, enabled: bool) -> None:
        """Show or hide the debug overlay."""
        self.is_visible = enabled
        self._props["visible"] = enabled
        self.update()

    def toggle_visibility(self) -> None:
        """Toggle debug overlay visibility."""
        self.set_enabled(not self.is_visible)

    def set_position(self, position: str) -> None:
        """Change the debug overlay corner position."""
        self._props["position"] = position
        self.update()

    def set_census_interval(self, interval_ms: int) -> None:
        """Change how often the overlay recounts canvas DOM elements."""
        self._props["census-interval-ms"] = interval_ms
        self.update()
