# barn/haybale-studio/haybale_studio/editors/properties_editor.py
"""
PropertiesEditor — focus-driven properties sidebar.

Displays a left-hand icon toolbar (one button per Focus) and a content area
showing display panels registered against the active Focus. The toolbar is
sourced from ``registry.get_display_focuses()``; panels are mounted via
``registry.get_panels_for_focus(focus)``.

Active-focus state is held per-editor on ``self._active_focus_id``. The
active focus is never changed automatically once set; while it remains
``None`` (initial state), the editor defaults to the lowest-order
*available* focus on each refresh.
"""

from __future__ import annotations

import logging
from typing import Callable, TYPE_CHECKING

from nicegui import ui

from haywire.core.errors.haywire_exception import HaywireException
from haywire.ui import elements as hui
from haywire.ui.editor.base import BaseEditor
from haywire.ui.editor.decorator import editor
from haywire.ui.panel.base import BasePanel
from haywire.ui.panel.layout import PanelLayout
from haywire.ui.panel.focus import Focus
from haywire.ui.panel.registry import PanelRegistry

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext
    from haywire.core.session.signals import Signal
    from nicegui.element import Element

logger = logging.getLogger(__name__)

# --8<-- [start:editor_example]


@editor(
    label="Properties",
    icon=hui.icon.node_settings,
    default_slot="right",
    description="Context-sensitive property panels for the active selection.",
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
        # Per-editor expansion-section state, keyed by panel_key. Survives
        # content rebuilds but stays scoped to this editor instance.
        self._expansion_state: dict[str, bool] = {}

        # Panel-driven event-bus subscriptions. PropertiesEditor owns these
        # because it's the only host that mounts registry panels with
        # persistent redraw semantics — context-menu hosts open a popup,
        # draw once, and dismiss; no subscription needed there.
        #
        # Populated in ``_subscribe_panel_event_handlers`` (called from
        # first ``draw()``); reconciled in ``_on_panel_registry_event``
        # when the catalog changes; drained in ``cleanup``.
        #
        # NB: held as a flat list of handles for now — same shape as the
        # original wrapper-side implementation. Migrating to per-panel
        # redraw will keep these per-(panel_class, event_type) so a single
        # event publish can target only the panels that asked for it.
        self._panel_bus_unsubscribes: list[Callable[[], None]] = []

        # PanelRegistry this editor is currently subscribed to (lifecycle
        # batch channel). Held so cleanup / catalog reconciliation can
        # detach. ``None`` before first ``draw()`` and after ``cleanup``.
        self._attached_panel_registry: PanelRegistry | None = None

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
    # Panel-contributed event-bus subscriptions
    # ------------------------------------------------------------------
    #
    # PropertiesEditor subscribes to every event type a display panel
    # contributes via ``redraw_on=`` on ``@panel(...)`` — across every
    # focus this editor's toolbar exposes. When such an event publishes,
    # the editor's wrapper redraws and panels re-mount with fresh state.
    # Panels do not have their own handler dispatch — they declare intent
    # on the decorator; the editor drives the redraw.
    #
    # The editor also subscribes to the panel registry's batch lifecycle
    # channel so it can reconcile its subscriptions when the catalog
    # changes (library install / uninstall / panel hot-reload).

    def _subscribe_panel_event_handlers(self, context: SessionContext) -> None:
        """Resolve the panel registry and wire panel-driven event subscriptions.

        No-op when the session's context does not expose a panel registry
        chain (test fixtures with stubbed context, hypothetical non-studio
        hosts). ``AttributeError`` along
        ``context.app.library_service.get_panel_registry()`` is caught
        explicitly; other exceptions log a warning.
        """
        try:
            registry = self._panel_registry(context)
        except AttributeError:
            # No panel registry reachable on this context — editor runs
            # without panel-driven redraws.
            return
        except Exception as exc:
            logger.warning(f"PropertiesEditor: resolving panel registry raised: {exc}")
            return
        if registry is None:
            return
        self._attach_panel_registry(registry)
        self._rebuild_panel_event_subscriptions()

    def _rebuild_panel_event_subscriptions(self) -> None:
        """Recompute the panel-contributed event-bus subscription set.

        Drops current subs, queries the registry for the union of
        redraw_on signals across display panels of every focus this
        editor exposes, and re-subscribes.
        """
        self._unsubscribe_panel_event_handlers()
        registry = self._attached_panel_registry
        context = self._context
        if registry is None or context is None:
            return
        signal_types: set[type[Signal]] = set()
        try:
            for focus in self._compute_toolbar_focuses(registry):
                signal_types |= registry.get_redraw_signals_for_focus(focus)
        except Exception as exc:
            logger.warning(f"PropertiesEditor: get_redraw_signals_for_focus raised: {exc}")
            return
        if not signal_types:
            return
        bus_subscribe = context.session.subscribe
        redraw_closure = self._make_panel_redraw_closure()
        for signal_type in signal_types:
            self._panel_bus_unsubscribes.append(bus_subscribe(signal_type, redraw_closure))

    def _make_panel_redraw_closure(self) -> Callable[["Signal"], None]:
        """Closure that, on any panel-contributed event publish, redraws the editor.

        Panel-contributed subscriptions have no editor-side handler body
        — the panel author already declared the intent via ``redraw_on=``
        on ``@panel(...)``. The closure just asks the wrapper to redraw
        so panels re-mount with fresh state.

        Future per-panel-redraw optimisation hooks in here: a richer
        closure could consult the (event_type → panel_classes) mapping
        and rebuild only the affected panels' DOM rather than the whole
        editor. Today it forwards to ``wrapper.redraw()`` for the same
        behaviour the framework previously provided.
        """

        def _redraw_on_panel_event(event: "Signal") -> None:
            del event  # forwarded, not inspected (yet)
            self.wrapper.redraw()

        return _redraw_on_panel_event

    def _unsubscribe_panel_event_handlers(self) -> None:
        """Drop the panel-contributed subscriptions.

        Used by the catalog-reconciliation path (registry lifecycle event)
        and by ``cleanup``.
        """
        for unsub in self._panel_bus_unsubscribes:
            try:
                unsub()
            except Exception as exc:
                logger.warning(f"PropertiesEditor: panel-bus unsubscribe raised: {exc}")
        self._panel_bus_unsubscribes.clear()

    def _attach_panel_registry(self, registry: PanelRegistry) -> None:
        """Bind to a panel registry's batch lifecycle channel.

        No-op if already attached to this registry. Replaces any prior
        attachment.
        """
        if self._attached_panel_registry is registry:
            return
        if self._attached_panel_registry is not None:
            self._detach_panel_registry()
        try:
            registry.add_batch_event_subscriber(self._on_panel_registry_event)
        except Exception as exc:
            logger.warning(f"PropertiesEditor: failed to subscribe to panel registry: {exc}")
            return
        self._attached_panel_registry = registry

    def _detach_panel_registry(self) -> None:
        """Unsubscribe from the panel registry's lifecycle channel, if attached."""
        registry = self._attached_panel_registry
        if registry is None:
            return
        try:
            registry.remove_batch_event_subscriber(self._on_panel_registry_event)
        except Exception as exc:
            logger.warning(f"PropertiesEditor: failed to unsubscribe from panel registry: {exc}")
        self._attached_panel_registry = None

    def _on_panel_registry_event(self, events) -> None:
        """Reconcile the panel-contributed subscription set on any catalog change.

        We don't inspect the event list: any event might change the
        union (a new panel registers, an old one unregisters, a panel
        reloads with a different ``redraw_on=``). Simplest correct
        behaviour: drop all panel-contributed subs and recompute.

        Also asks for a redraw — a catalog change can mean new event
        types appeared, so the current rendered state may be stale
        relative to what those events would have triggered.
        """
        del events  # consumed by interface; not used here
        self._rebuild_panel_event_subscriptions()
        self.wrapper.redraw()

    def draw(self, context: SessionContext, container: Element) -> None:
        self._container = container
        self._context = context
        # First draw of this instance: wire panel-driven event-bus
        # subscriptions. Idempotent — subsequent redraws via
        # ``wrapper.redraw()`` re-enter draw() but skip re-subscription
        # because ``_attached_panel_registry`` is already set. Hot-reload
        # discards the instance, so the next instance's first draw()
        # subscribes against the fresh class / current registry.
        if self._attached_panel_registry is None:
            self._subscribe_panel_event_handlers(context)
        self._build_layout(context)

    def cleanup(self) -> None:
        """Tear down panel-bus subscriptions when this editor instance goes away.

        Called by the framework on permanent removal and during hot-
        reload (before the new instance is built). Drops every panel-
        contributed subscription and detaches from the panel registry's
        lifecycle channel.
        """
        self._unsubscribe_panel_event_handlers()
        self._detach_panel_registry()

    # --8<-- [end:editor_example]

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

        has_panels = False
        with self._content:
            for panel_cls in panel_classes:
                try:
                    if not panel_cls.poll(context):
                        continue
                except Exception as exc:
                    HaywireException.from_exception(
                        exception=exc,
                        category="Panel Poll Error",
                        operation="panel_poll",
                        message=f"PropertiesEditor: poll() error in {panel_cls.__name__}",
                    ).log(logger)
                    continue

                has_panels = True
                default_open = getattr(panel_cls.class_identity, "default_open", True)
                icon = getattr(panel_cls.class_identity, "icon", None)
                panel_key = f"{focus.id}:{panel_cls.class_identity.registry_key}"

                with hui.expansion_section(
                    panel_cls.class_identity.label,
                    icon=icon,
                    default_open=default_open,
                    state=self._expansion_state,
                    panel_key=panel_key,
                ):
                    panel_container = ui.column().classes("w-full gap-1")
                    layout = PanelLayout(panel_container, expansion_state=self._expansion_state)
                    try:
                        panel_cls().draw(context, layout)
                    except Exception as exc:
                        HaywireException.from_exception(
                            exception=exc,
                            category="Panel Draw Error",
                            operation="panel_draw",
                            message=f"PropertiesEditor: draw() error in {panel_cls.__name__}",
                        ).log(logger)
                        hui.error_label(f"Error: {exc}")

            if not has_panels:
                hui.empty_state("No properties available", icon=hui.icon.node_info)
