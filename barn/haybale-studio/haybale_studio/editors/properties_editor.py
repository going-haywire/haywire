# barn/haybale-studio/haybale_studio/editors/properties_editor.py
"""
PropertiesEditor — scoped properties sidebar.

Displays a left-hand icon toolbar (one button per scope) and a content area
showing panels registered to the active scope.  Scope tabs are registered via
PanelRegistry.register_scope(); panels are registered with @panel(scope=...).

Scope state is stored in context.metadata['properties_scope'] (a scope_id
string).  The active scope is never changed automatically — the user's last
choice is always preserved.  The only exception is the very first render, when
no scope has been set yet and the first registered scope is used as the default.

No hardcoded scope IDs or SessionContext field names live in this file —
all context coupling is in ScopeDescriptor.poll callables registered by
libraries.
"""

import logging

from typing import TYPE_CHECKING, Optional

from nicegui import ui

from haywire.ui import elements as hui
from haywire.ui.editor.decorator import editor
from haywire.ui.editor.base import BaseEditor
from haywire.ui.context_events import ContextChangeType
from haywire.ui.panel.base import PanelLayout
from haywire.ui.panel.registry import PanelRegistry

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext
    from haywire.ui.context_events import ContextChangedEvent
    from nicegui.element import Element

logger = logging.getLogger(__name__)

_SCOPE_KEY = "properties_scope"


@editor(
    registry_id="properties",
    label="Properties",
    icon="tune",
    default_area="right",
    description="Context-sensitive property panels for the active selection.",
)
class PropertiesEditor(BaseEditor):
    """
    Scoped properties editor.

    The left toolbar shows one icon button per registered scope.  Clicking a
    button makes that scope active and re-renders the content area with the
    panels belonging to that scope.

    Scope availability is determined by ScopeDescriptor.poll(context).
    Unavailable scopes are shown dimmed and are not clickable.  The active
    scope is never changed automatically after initial selection.
    """

    def __init__(self):
        self._container: "Element | None" = None
        self._toolbar: "Element | None" = None
        self._content: "Element | None" = None
        self._panel_registry: Optional[PanelRegistry] = None

    # ------------------------------------------------------------------
    # BaseEditor interface
    # ------------------------------------------------------------------

    def render(self, container: "Element", context: "SessionContext") -> None:
        self._container = container
        self._panel_registry = context.app.library_service.get_panel_registry()
        self._build_layout(context)

    def on_context_changed(self, event: "ContextChangedEvent", context: "SessionContext") -> None:
        relevant = {
            ContextChangeType.SELECTION_CHANGED,
            ContextChangeType.ACTIVE_GRAPH_CHANGED,
            ContextChangeType.DATA_MUTATED,
        }
        if event.change_type in relevant and self._container is not None:
            self._refresh(context)

    # ------------------------------------------------------------------
    # Layout construction (called once on render)
    # ------------------------------------------------------------------

    def _build_layout(self, context: "SessionContext") -> None:
        """Build the two-column layout: scope toolbar + content area."""
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

    def _refresh(self, context: "SessionContext") -> None:
        """Recompute active scope and redraw both toolbar and content."""
        self._resolve_active_scope(context)
        self._rebuild_toolbar(context)
        self._rebuild_content(context)

    # ------------------------------------------------------------------
    # Scope resolution
    # ------------------------------------------------------------------

    def _resolve_active_scope(self, context: "SessionContext") -> None:
        """
        Set a default scope on first render only.  After that the user's
        choice is always preserved regardless of selection changes.
        Writes result to context.metadata only when no scope has been set.
        """
        if _SCOPE_KEY in context.metadata:
            return  # user's choice — never override

        # First render: default to the first registered scope
        all_scopes = self._panel_registry.get_scopes("properties") if self._panel_registry else []
        context.metadata[_SCOPE_KEY] = all_scopes[0].scope_id if all_scopes else None

    def _set_active_scope(self, scope_id: str, context: "SessionContext") -> None:
        """Called when the user clicks a toolbar button."""
        context.metadata[_SCOPE_KEY] = scope_id
        self._rebuild_toolbar(context)
        self._rebuild_content(context)

    # ------------------------------------------------------------------
    # Toolbar rendering
    # ------------------------------------------------------------------

    def _rebuild_toolbar(self, context: "SessionContext") -> None:
        if self._toolbar is None:
            return
        self._toolbar.clear()

        all_scopes = self._panel_registry.get_scopes("properties") if self._panel_registry else []
        active_scope_id = context.metadata.get(_SCOPE_KEY)

        with self._toolbar:
            for scope in all_scopes:
                available = scope.poll(context)
                is_active = scope.scope_id == active_scope_id
                scope_id_capture = scope.scope_id
                hui.scope_button(
                    scope.icon,
                    is_active=is_active,
                    available=available,
                    tooltip=scope.label,
                    on_click=lambda sid=scope_id_capture: self._set_active_scope(sid, context),
                )

    # ------------------------------------------------------------------
    # Content rendering
    # ------------------------------------------------------------------

    def _rebuild_content(self, context: "SessionContext") -> None:
        if self._content is None:
            return
        self._content.clear()

        active_scope_id = context.metadata.get(_SCOPE_KEY)
        if active_scope_id is None:
            with self._content:
                hui.empty_state("Nothing to show", icon="select_all")
            return

        if self._panel_registry is None:
            with self._content:
                hui.empty_state("No panel registry", icon="info")
            return

        panel_classes = self._panel_registry.get_panels("properties", active_scope_id)

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
                panel_key = f"{active_scope_id}:{panel_cls.class_identity.registry_key}"

                with hui.expansion_section(
                    panel_cls.class_identity.label,
                    icon=icon,
                    default_open=default_open,
                    context=context,
                    panel_key=panel_key,
                ):
                    panel_container = ui.column().classes("w-full gap-1")
                    layout = PanelLayout(panel_container)
                    try:
                        panel_instance = panel_cls()
                        panel_instance.draw(context, layout)
                    except Exception as exc:
                        logger.exception(f"PropertiesEditor: draw() error in {panel_cls.__name__}: {exc}")
                        hui.error_label(f"Error: {exc}")

            if not has_panels:
                hui.empty_state("No properties available", icon="info")
