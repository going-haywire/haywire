# barn/haybale-studio/haybale_studio/editors/properties_editor.py
"""
PropertiesEditor — focus-driven properties sidebar.

Displays a left-hand icon toolbar (one button per Focus) and a content area
showing panels registered against the active Focus. The toolbar is sourced
from ``default_focus_ids ∪ registry.get_focuses_for(self)``. Panels are
mounted via the contract-keyed lookup
``get_panels_for(actions_provider, focus)``.

Active-focus state is held per-editor on ``self._active_focus_id`` (a
focus ``id`` string, or ``None`` if no focus is selected). The active
focus is never changed automatically once set — the user's last choice
is always preserved. While it remains ``None``, each refresh tries to
default to the lowest-order *available* focus (typically AppFocus).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, ClassVar, Optional

from nicegui import ui

from haybale_studio.state.edit_state import EditState
from haywire.ui import elements as hui
from haywire.ui.context_signals import (
    ActiveGraphMoved,
    GraphDataMutated,
    SelectionMoved,
)
from haywire.ui.editor.base import BaseEditor
from haywire.ui.editor.decorator import editor
from haywire.ui.panel.base import BasePanel
from haywire.ui.panel.layout import PanelLayout
from haywire.ui.panel.focus import Focus, focus_by_id
from haywire.ui.panel.registry import PanelRegistry

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext
    from haywire.ui.context_signals import ContextSignal
    from nicegui.element import Element

logger = logging.getLogger(__name__)


@editor(
    label="Properties",
    icon=hui.icon.node_settings,
    default_slot="right",
    description="Context-sensitive property panels for the active selection.",
)
class PropertiesEditor(BaseEditor):
    """
    Focus-driven properties editor.

    The left toolbar shows one icon button per Focus class (default_focus_ids
    plus any focuses contributed by registered panels). Clicking a button
    makes that Focus active and re-renders the content area with the
    panels belonging to that Focus.

    Focus availability is determined by ``Focus.available(ctx)``. Unavailable
    focuses are shown dimmed and are not clickable. The active focus is
    never changed automatically after initial selection.
    """

    # ------------------------------------------------------------------
    # Class-level configuration
    # ------------------------------------------------------------------

    #: Built-in focuses every PropertiesEditor instance shows in the toolbar
    #: regardless of which panels are registered. Library-contributed focuses
    #: are merged in at runtime via ``registry.get_focuses_for(self)``.
    #:
    #: Stored as ids (not class refs) so hot-reload of focuses.py — which
    #: replaces the Focus class objects in _FOCUS_BY_ID — doesn't leave this
    #: editor holding stale references. Resolved via ``focus_by_id`` at use.
    default_focus_ids: ClassVar[tuple[str, ...]] = (
        "app",
        "execution",
        "canvas",
        "graph",
        "node",
        "settings",
        "edge",
        "port",
    )

    _RELEVANT_SIGNALS = (SelectionMoved, ActiveGraphMoved, GraphDataMutated)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self, panel_registry: Optional[PanelRegistry] = None) -> None:
        # ``panel_registry`` is optional: production paths leave it None and
        # the registry is fetched from ``context.app.library_service`` in
        # ``draw``. Tests inject a registry directly.
        self._container: Element | None = None
        self._toolbar: Element | None = None
        self._content: Element | None = None
        self._panel_registry: Optional[PanelRegistry] = panel_registry
        self._context: SessionContext | None = None
        # Focus id of the currently-active toolbar tab; None when no
        # focus is selected (initial state, or no available focus).
        self._active_focus_id: str | None = None
        # Per-editor expansion-section state, keyed by panel_key. Survives
        # content rebuilds but stays scoped to this editor instance.
        self._expansion_state: dict[str, bool] = {}

    # ------------------------------------------------------------------
    # BaseEditor interface (poll/draw)
    # ------------------------------------------------------------------

    def poll(self, context: SessionContext, signal: ContextSignal) -> bool:
        return isinstance(signal, self._RELEVANT_SIGNALS)

    def draw(self, context: SessionContext, container: Element) -> None:
        self._container = container
        self._context = context
        if self._panel_registry is None:
            self._panel_registry = context.app.library_service.get_panel_registry()
        self._build_layout(context)

    # ------------------------------------------------------------------
    # PropertiesEditorActions Protocol implementation
    # ------------------------------------------------------------------

    def clear_selection(self) -> None:
        """Clear node/edge/port selection. Called by panels via the
        ``actions`` parameter."""
        if self._context is None:
            return
        edit_state = self._context.data[EditState]
        edit_state.active_node.value = None
        edit_state.active_edge.value = None
        edit_state.active_port.value = None

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

    def _compute_toolbar_focuses(self) -> list[type[Focus]]:
        """Compute toolbar focuses: default ∪ registry-discovered, sorted by Focus.order."""
        focuses: set[type[Focus]] = {
            cls for cls in (focus_by_id(fid) for fid in self.default_focus_ids) if cls is not None
        }
        if self._panel_registry is not None:
            focuses.update(self._panel_registry.get_focuses_for(actions_provider=self))
        return sorted(focuses, key=lambda f: f.order)

    # ------------------------------------------------------------------
    # Focus resolution
    # ------------------------------------------------------------------

    def _resolve_active_focus(self, context: SessionContext) -> None:
        """Set a default focus on first render only.

        After first render, the user's choice is preserved regardless of
        selection changes. Default selection picks the lowest-order focus
        that is currently ``available`` (typically AppFocus, order=10).
        """
        if self._active_focus_id is not None:
            return  # user's choice — never override

        for focus in self._compute_toolbar_focuses():
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

    def _active_focus(self) -> type[Focus] | None:
        """Return the currently-active Focus class, or None."""
        if self._active_focus_id is None:
            return None
        for focus in self._compute_toolbar_focuses():
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
            for focus in self._compute_toolbar_focuses():
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

    def _mount_panels_for_active_focus(self, focus: type[Focus]) -> list[type[BasePanel]]:
        """Mount panels matching the active focus via the contract-keyed lookup."""
        if self._panel_registry is None:
            return []
        return self._panel_registry.get_panels_for(actions_provider=self, focus=focus)

    def _rebuild_content(self, context: SessionContext) -> None:
        if self._content is None:
            return
        self._content.clear()

        focus = self._active_focus()
        if focus is None:
            with self._content:
                hui.empty_state("Nothing to show", icon=hui.icon.empty_no_selection)
            return

        if self._panel_registry is None:
            with self._content:
                hui.empty_state("No panel registry", icon=hui.icon.node_info)
            return

        panel_classes = self._mount_panels_for_active_focus(focus)

        has_panels = False
        with self._content:
            for panel_cls in panel_classes:
                try:
                    if not panel_cls.poll(context):
                        continue
                except Exception as exc:
                    logger.warning(f"PropertiesEditor: poll() error in {panel_cls.__name__}: {exc}")
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
                        panel_cls().draw(context, layout, self)
                    except Exception as exc:
                        logger.exception(f"PropertiesEditor: draw() error in {panel_cls.__name__}: {exc}")
                        hui.error_label(f"Error: {exc}")

            if not has_panels:
                hui.empty_state("No properties available", icon=hui.icon.node_info)
