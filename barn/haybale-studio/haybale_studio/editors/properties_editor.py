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
from haywire.ui.panel.focus import Focus
from haywire.ui.panel.registry import PanelRegistry
from haywire.ui.panel.host_rendering import render_panel, visible_panels
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
    Focus-driven properties editor.

    The left toolbar shows one icon button per Focus class contributed by
    registered panels. Clicking a button makes that Focus active and
    re-renders the content area with the panels belonging to that Focus.

    Focus availability is determined by ``Focus.available(ctx)``. Unavailable
    focuses are shown dimmed and are not clickable. The active focus is
    never changed automatically after initial selection.
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
        # Focus id of the currently-active toolbar tab; None when no
        # focus is selected (initial state, or no available focus).
        self._active_focus_id: str | None = None
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
                    focus_provider=lambda: self._compute_toolbar_focuses(registry),
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
        """Build the two-column layout: focus toolbar + content area."""
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
        """Recompute the active focus and redraw both toolbar and content."""
        self._resolve_active_focus(context)
        self._rebuild_toolbar(context)
        self._rebuild_content(context)

    # ------------------------------------------------------------------
    # Toolbar discovery
    # ------------------------------------------------------------------

    def _compute_toolbar_focuses(self, panel_registry: PanelRegistry) -> list[type[Focus]]:
        """Compute toolbar focuses from the panel registry, sorted by Focus.order."""
        focuses = panel_registry.get_display_focuses()
        return sorted(focuses, key=lambda f: f.order)

    # ------------------------------------------------------------------
    # Focus resolution
    # ------------------------------------------------------------------

    def _resolve_active_focus(self, context: SessionContext) -> None:
        """Set a default focus on first render only.

        After first render, the user's choice is preserved regardless of
        selection changes. Default selection picks the lowest-order focus
        that is currently ``available``.
        """
        if self._active_focus_id is not None:
            return  # user's choice — never override

        for focus in self._compute_toolbar_focuses(self._panel_registry(context)):
            try:
                if focus.available(context):
                    self._active_focus_id = focus.id
                    return
            except Exception as exc:  # defensive: a buggy available() shouldn't crash startup
                logger.warning(f"PropertiesEditor: Focus.available() error in {focus.__name__}: {exc}")

    def _set_active_focus(self, focus_id: str, context: SessionContext) -> None:
        """Called when the user clicks a toolbar button."""
        self._active_focus_id = focus_id
        self._rebuild_toolbar(context)
        self._rebuild_content(context)

    def _active_focus(self, context: SessionContext) -> type[Focus] | None:
        """Return the currently-active Focus class, or None."""
        if self._active_focus_id is None:
            return None
        for focus in self._compute_toolbar_focuses(self._panel_registry(context)):
            if focus.id == self._active_focus_id:
                return focus
        return None

    # ------------------------------------------------------------------
    # Toolbar rendering
    # ------------------------------------------------------------------

    def _rebuild_toolbar(self, context: SessionContext) -> None:
        if self._toolbar is None:
            return
        self._toolbar.clear()

        active_focus_id = self._active_focus_id

        with self._toolbar:
            for focus in self._compute_toolbar_focuses(self._panel_registry(context)):
                try:
                    available = focus.available(context)
                except Exception as exc:
                    logger.warning(f"PropertiesEditor: Focus.available() error in {focus.__name__}: {exc}")
                    available = False
                is_active = focus.id == active_focus_id
                focus_id_capture = focus.id
                hui.scope_button(
                    focus.icon,
                    is_active=is_active,
                    available=available,
                    tooltip=focus.label,
                    on_click=lambda fid=focus_id_capture: self._set_active_focus(fid, context),
                )

    # ------------------------------------------------------------------
    # Content rendering
    # ------------------------------------------------------------------

    def _mount_panels_for_active_focus(
        self, panel_registry: PanelRegistry, focus: type[Focus]
    ) -> list[type[BasePanel]]:
        """Mount panels matching the active focus (display panels only)."""
        return panel_registry.get_panels_for_focus(focus)

    def _rebuild_content(self, context: SessionContext) -> None:
        if self._content is None:
            return
        self._content.clear()

        focus = self._active_focus(context)
        if focus is None:
            with self._content:
                hui.empty_state("Nothing to show", icon=hui.icon.empty_no_selection)
            return

        panel_registry = self._panel_registry(context)
        panel_classes = self._mount_panels_for_active_focus(panel_registry, focus)

        visible = visible_panels(panel_classes, context)
        with self._content:
            for panel_cls in visible:
                identity = panel_cls.class_identity
                panel_key = f"{focus.id}:{identity.registry_key}"

                with hui.expansion_section(
                    identity.label,
                    icon=identity.icon,
                    default_open=identity.default_open,
                    state=self._state_bag,
                    panel_key=panel_key,
                ):
                    panel_container = ui.column().classes("w-full gap-1")
                    layout = PanelLayout(panel_container, state_bag=self._state_bag)
                    render_panel(panel_cls, context, layout)

            if not visible:
                hui.empty_state("No properties available", icon=hui.icon.node_info)


