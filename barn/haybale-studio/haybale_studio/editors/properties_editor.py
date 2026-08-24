# barn/haybale-studio/haybale_studio/editors/properties_editor.py

from __future__ import annotations

import logging
from typing import Any, TYPE_CHECKING

from nicegui import ui

from haywire.ui import elements as hui
from haywire.ui.editor.base import BaseEditor
from haywire.ui.editor.decorator import editor
from haywire.ui.editor.identity import SlotName
from haywire.ui.panel.base import BasePanel
from haywire.ui.panel.layout import PanelLayout
from haywire.ui.panel.registry import PanelRegistry
from haywire.ui.panel.host_rendering import _poll_surface, render_panel, visible_panels
from haywire.ui.surface import Surface
from haywire.ui.panel.redraw_coordinator import PanelRedrawCoordinator

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext
    from nicegui.element import Element

logger = logging.getLogger(__name__)


@editor(
    label="Properties",
    icon=hui.icon.node_settings,
    default_slot=SlotName.CONTEXT,
    description="Context-sensitive property panels for the active selection.",
    order=10,
)
class PropertiesEditor(BaseEditor):
    """
    Surface-driven properties editor.

    The left SurfaceToolbar shows one icon button per **root surface that
    declares a ``presentation``** — surfaces named by some registered panel's
    ``surface=``, named by no panel's ``hosts=``, and carrying chrome for a
    host to draw. Every other host names the surface it opens; only this one
    discovers its list, so the filter lives here rather than in the registry
    (ADR-0029, Presentation). Clicking a button makes that surface active and
    re-renders the content area with its panels.

    A surface whose ``poll()`` is false keeps its tab in place, greyed, and
    its content is dropped: stable position is what makes a tab learnable,
    and the editor drew that chrome so the editor greys it. The active
    surface is never changed automatically after initial selection.
    """

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self, wrapper) -> None:
        super().__init__(wrapper)
        self._container: Element | None = None
        self._toolbar: Element | None = None
        self._content: Element | None = None
        self._context: SessionContext | None = None
        # Surface id of the currently-active toolbar tab; None when no
        # surface is selected (initial state, or none applies).
        self._active_surface_id: str | None = None
        # Per-editor UI state bag (collapse state, scroll position, form state, etc.),
        # keyed by namespaced panel keys. Survives content rebuilds but stays scoped
        # to this editor instance.
        self._state_bag: dict[str, Any] = {}

        # Panel-driven redraw subscriptions, fully owned by the coordinator.
        # Constructed lazily on first draw() once a panel registry resolves;
        # stays None when no registry is reachable (so each redraw retries).
        self._coordinator: PanelRedrawCoordinator | None = None

    # ------------------------------------------------------------------
    # BaseEditor interface (draw + panel registry hook)
    # ------------------------------------------------------------------

    def _panel_registry(self, context: SessionContext) -> PanelRegistry:
        """Return the registry whose panels appear in this editor.

        Resolved via the same path used by the panel-bus wiring below, so
        the toolbar / content paths render against exactly the panel
        catalog this editor subscribes to.
        """
        return context.app.library_service.get_panel_registry()

    # ------------------------------------------------------------------
    # Panel-driven redraw subscriptions
    # ------------------------------------------------------------------
    #
    # Delegated wholesale to a PanelRedrawCoordinator (haywire.ui.panel).
    # The editor only owns registry *resolution* — the part that can fail
    # on a stubbed / non-studio context. Once a registry resolves, the
    # coordinator owns every subscription (per-signal redraw subs + the
    # registry lifecycle channel) and its own teardown.

    def draw(self, context: SessionContext, container: Element) -> None:
        self._container = container
        self._context = context
        # First draw of this instance: resolve the panel registry and hand
        # it to a coordinator. Subsequent redraws re-enter draw() but skip
        # this because _coordinator is already set. If no registry resolves
        # (stubbed context, non-studio host, lookup raises) _coordinator
        # stays None and the next redraw retries — same as the pre-extraction
        # behaviour. Hot-reload discards the instance; the next instance's
        # first draw() builds a fresh coordinator against the current registry.
        if self._coordinator is None:
            registry = self._resolve_panel_registry(context)
            if registry is not None:
                self._coordinator = PanelRedrawCoordinator(
                    registry=registry,
                    session=context.session,
                    on_redraw=self.wrapper.redraw,
                    surface_provider=lambda: self._compute_toolbar_surfaces(registry),
                )
                self._coordinator.start()
        self._build_layout(context)

    def _resolve_panel_registry(self, context: SessionContext) -> PanelRegistry | None:
        """Resolve the panel registry for subscription wiring, or None.

        Returns None (no panel-driven redraws) when the session's context
        does not expose a panel registry chain: AttributeError along
        ``context.app.library_service.get_panel_registry()`` (stubbed
        context / non-studio host) is treated as absent; any other
        exception is logged and also treated as absent.
        """
        try:
            registry = self._panel_registry(context)
        except AttributeError:
            return None
        except Exception as exc:
            logger.warning(f"PropertiesEditor: resolving panel registry raised: {exc}")
            return None
        return registry

    def cleanup(self) -> None:
        """Tear down panel-driven redraw subscriptions on instance removal.

        Called by the framework on permanent removal and during hot-reload
        (before the new instance is built). Delegates to the coordinator,
        which drops every subscription and detaches from the registry
        lifecycle channel.
        """
        if self._coordinator is not None:
            self._coordinator.cleanup()
            self._coordinator = None

    # ------------------------------------------------------------------
    # Layout construction (called once on render)
    # ------------------------------------------------------------------

    def _build_layout(self, context: SessionContext) -> None:
        """Build the two-column layout: SurfaceToolbar + content area."""
        assert self._container is not None
        with self._container:
            with ui.row().classes("w-full h-full gap-0").style("overflow: hidden;"):
                self._toolbar = (
                    ui.column()
                    .classes("gap-0")
                    .style(
                        "width: 36px; min-width: 36px; overflow-y: auto;"
                        "border-right: 1px solid var(--hw-border);"
                    )
                )
                self._content = (
                    ui.column()
                    .classes("flex-1 gap-0")
                    .style("overflow-y: auto; min-width: 0; min-height: 0; height: 100%;")
                )
        self._refresh(context)

    # ------------------------------------------------------------------
    # Refresh (called on every relevant context change)
    # ------------------------------------------------------------------

    def _refresh(self, context: SessionContext) -> None:
        """Recompute the active surface and redraw both toolbar and content."""
        self._resolve_active_surface(context)
        self._rebuild_toolbar(context)
        self._rebuild_content(context)

    # ------------------------------------------------------------------
    # Toolbar discovery
    # ------------------------------------------------------------------

    def _compute_toolbar_surfaces(self, panel_registry: PanelRegistry) -> list[type[Surface]]:
        """Root surfaces that declare a ``presentation``, sorted by order.

        Root-ness comes from the registry; the ``presentation`` filter is the
        strip's own discovery policy — a root surface with no chrome to draw
        (a menu, the floating toolbar) is not a tab, and a surface some panel
        hosts is drawn by that panel rather than here.
        """
        surfaces = [s for s in panel_registry.get_root_surfaces() if s.presentation is not None]
        return sorted(surfaces, key=lambda s: s.order)

    # ------------------------------------------------------------------
    # Surface resolution
    # ------------------------------------------------------------------

    def _resolve_active_surface(self, context: SessionContext) -> None:
        """Set a default surface on first render only.

        After first render, the user's choice is preserved regardless of
        selection changes. Default selection picks the lowest-order surface
        whose ``poll()`` currently passes.
        """
        if self._active_surface_id is not None:
            return  # user's choice — never override

        for surface in self._compute_toolbar_surfaces(self._panel_registry(context)):
            if _poll_surface(surface, context):
                self._active_surface_id = surface.id
                return

    def _set_active_surface(self, surface_id: str, context: SessionContext) -> None:
        """Called when the user clicks a toolbar button."""
        self._active_surface_id = surface_id
        self._rebuild_toolbar(context)
        self._rebuild_content(context)

    def _active_surface(self, context: SessionContext) -> type[Surface] | None:
        """Return the currently-active Surface class, or None."""
        if self._active_surface_id is None:
            return None
        for surface in self._compute_toolbar_surfaces(self._panel_registry(context)):
            if surface.id == self._active_surface_id:
                return surface
        return None

    # ------------------------------------------------------------------
    # Toolbar rendering
    # ------------------------------------------------------------------

    def _rebuild_toolbar(self, context: SessionContext) -> None:
        if self._toolbar is None:
            return
        self._toolbar.clear()

        active_surface_id = self._active_surface_id

        with self._toolbar:
            for surface in self._compute_toolbar_surfaces(self._panel_registry(context)):
                # A false poll() greys the tab in place rather than removing
                # it — the editor drew this chrome, so the editor greys it.
                applies = _poll_surface(surface, context)
                presentation = surface.presentation
                assert presentation is not None  # filtered on above
                surface_id_capture = surface.id
                hui.surface_button(
                    presentation.icon,
                    is_active=surface.id == active_surface_id,
                    available=applies,
                    tooltip=presentation.label,
                    on_click=lambda sid=surface_id_capture: self._set_active_surface(sid, context),
                )

    # ------------------------------------------------------------------
    # Content rendering
    # ------------------------------------------------------------------

    def _mount_panels_for_active_surface(
        self, panel_registry: PanelRegistry, surface: type[Surface]
    ) -> list[type[BasePanel]]:
        """Panels on the active surface, in order."""
        return panel_registry.get_panels(surface)

    def _rebuild_content(self, context: SessionContext) -> None:
        if self._content is None:
            return
        self._content.clear()

        surface = self._active_surface(context)
        if surface is None:
            with self._content:
                hui.empty_state("Nothing to show", icon=hui.icon.empty_no_selection)
            return

        # A greyed tab drops its content: the surface gate runs once, here,
        # and the shared panel filter does not re-check it.
        if not _poll_surface(surface, context):
            with self._content:
                hui.empty_state("Nothing to show", icon=hui.icon.empty_no_selection)
            return

        panel_registry = self._panel_registry(context)
        panel_classes = self._mount_panels_for_active_surface(panel_registry, surface)

        # Inspector panels implement no draw_disabled() — a greyed accordion
        # is noise where a greyed tab is a navigation target — so this host
        # takes only the applicable half.
        visible = visible_panels(panel_classes, context)
        with self._content:
            for panel_cls in visible:
                identity = panel_cls.class_identity
                panel_key = f"{surface.id}:{identity.registry_key}"

                with hui.expansion_section(
                    identity.label,
                    icon=identity.icon,
                    default_open=identity.default_open,
                    state=self._state_bag,
                    panel_key=panel_key,
                ):
                    panel_container = ui.column().classes("w-full gap-1")
                    layout = PanelLayout(panel_container, state_bag=self._state_bag)
                    render_panel(panel_cls, context, layout, registry=panel_registry)

            if not visible:
                hui.empty_state("No properties available", icon=hui.icon.node_info)
