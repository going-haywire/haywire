"""
ComponentDocsEditor — shows detail info for the selected component.

Renders in the right area and reacts to ACTIVE_COMPONENT_CHANGED events.
Displays identifiers with copy buttons, usage snippets, and a Docs tab (markdown).
"""

import inspect
from typing import TYPE_CHECKING

from haywire.core.library.utils import split_reg_key
from nicegui import ui

from haywire.ui import elements as hui

from haywire.ui.editor.decorator import editor
from haywire.ui.editor.identity import SlotName
from haywire.ui.editor.base import BaseEditor
from haywire.core.session.context import SessionContext
from haywire.core.session.handlers import redraw_on
from haywire.core.signals import SelectionMoved

if TYPE_CHECKING:
    from nicegui.element import Element


class _WidgetPreviewPort:
    """Minimal mock port used to render a live widget preview without a real binding."""

    id = "preview"
    widget_config: dict = {}


@editor(
    label="Component Detail",
    icon=hui.icon.library_component,
    default_slot=SlotName.CONTEXT,
    description="Detailed documentation for the selected component.",
    order=30,
)
class ComponentDocsEditor(BaseEditor):
    """
    Displays documentation and port information for the selected component.
    Rebuilds on ACTIVE_COMPONENT_CHANGED context events.
    """

    def __init__(self, wrapper):
        super().__init__(wrapper)
        self._container = None

    @redraw_on(
        SessionContext.active_component,
        SelectionMoved,
    )
    def _refresh_on_relevant_event(self, context: "SessionContext", event) -> None:
        # Empty body — the decorator triggers wrapper.redraw() after return.
        pass

    def draw(self, context: "SessionContext", container: "Element") -> None:
        self._container = container
        self._rebuild(context)

    _COMP_ICONS = {
        "nodes": hui.icon.node,
        "widgets": hui.icon.widget,
        "types": hui.icon.type,
        "adapters": hui.icon.adapter,
        "skins": hui.icon.skin,
        "settings": hui.icon.node_settings,
        "states": hui.icon.state,
        "themes": hui.icon.theme,
        "panels": hui.icon.panel,
        "editors": hui.icon.editor,
        "farmhands": hui.icon.farmhand,
    }

    def _rebuild(self, context: "SessionContext") -> None:
        if self._container is None:
            return
        registry_key = context.active_component
        with self._container:
            if not registry_key:
                hui.empty_state(
                    "Click a node or widget",
                    icon=hui.icon.library_docs,
                    hint="to view its documentation",
                )
                return

            app = context.app
            lib_id, comp_singular, class_name = split_reg_key(registry_key)
            comp_type = f"{comp_singular}s"

            cls = app.library_service.lookup_component_class(registry_key)
            identity = getattr(cls, "class_identity", None) if cls else None

            label = getattr(identity, "label", None) or class_name or "?"
            description = getattr(identity, "description", None) or ""
            deprecation_warning = getattr(identity, "deprecation_warning", "") or ""
            tags = getattr(identity, "tags", []) or []
            icon = self._COMP_ICONS.get(comp_type, "extension")
            actual_name = getattr(cls, "__name__", class_name) if cls else class_name
            module_path = getattr(cls, "__module__", None) if cls else None
            menu = getattr(identity, "menu", None) if identity else None

            # Resolve docs file via library service
            doc_file = app.library_service.get_component_doc_path(registry_key)

            # height:100% + flex column so tab_panels can fill remaining space
            with ui.column().classes("w-full p-4 gap-0").style("height: 100%;"):
                # ── Header bar ─────────────────────────────────────────────
                with ui.row().classes("w-full items-center justify-between mb-3"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon(icon).classes("text-xl hw-use-props-color").props("color=purple")
                        ui.label(comp_singular.upper()).classes(
                            "text-xs hw-text-dim font-bold tracking-wider"
                        )
                    hui.icon_action("close", tooltip="Close", on_click=lambda ctx=context: self._close(ctx))

                # ── Label + description ────────────────────────────────────
                with ui.column().classes("w-full gap-0.5 mb-2"):
                    ui.label(label).classes("text-base font-bold")
                    if description:
                        ui.label(description).classes("text-xs hw-text-muted")

                # ── Deprecation banner ────────────────────────────────────
                if deprecation_warning:
                    with (
                        ui.row()
                        .classes("items-start gap-2 mb-2 p-2 rounded")
                        .style("background: rgba(245,158,11,0.1); border: 1px solid rgba(245,158,11,0.4);")
                    ):
                        ui.icon("warning").classes("text-amber-500 text-base mt-0.5")
                        with ui.column().classes("gap-0"):
                            ui.label("Deprecated").classes("text-xs font-bold text-amber-500")
                            ui.label(deprecation_warning).classes("text-xs hw-text-body whitespace-normal")

                # ── Tags ──────────────────────────────────────────────────
                if tags:
                    with ui.row().classes("gap-1 flex-wrap mb-2"):
                        for tag in tags:
                            hui.tag(str(tag), color="purple")

                # ── Identifiers ────────────────────────────────────────────
                hui.section_label("Identifiers")
                hui.info_row("Key", registry_key)
                hui.info_row("Class", actual_name)
                if module_path:
                    short = (module_path[:48] + "…") if len(module_path) > 50 else module_path
                    hui.info_row("Module", short, copy_value=module_path)
                if comp_type == "nodes" and menu:
                    hui.info_row("Menu", menu)

                # ── Usage snippets ─────────────────────────────────────────
                if comp_type == "types":
                    hui.section_label("Usage")
                    if module_path:
                        hui.code_snippet(f"from {module_path} import {actual_name}", label="Import")
                    hui.code_snippet(
                        f"self.add({actual_name}.as_inlet('id', label='Label'))", label="Inlet port"
                    )
                    hui.code_snippet(
                        f"self.add({actual_name}.as_outlet('id', label='Label'))", label="Outlet port"
                    )
                    hui.code_snippet(
                        f"self.add({actual_name}.as_config('id', label='Label', default=...))",
                        label="Config port",
                    )
                elif comp_type == "widgets":
                    hui.section_label("Usage")
                    if module_path:
                        hui.code_snippet(f"from {module_path} import {actual_name}", label="Import")
                    hui.code_snippet(f"widget={actual_name}.config(properties={{}})", label="Widget config")
                elif comp_type == "nodes" and module_path:
                    hui.section_label("Import")
                    hui.code_snippet(f"from {module_path} import {actual_name}")

                # ── Tabs: View (widgets only) / Docs ──────────────────────
                ui.separator().classes("mt-3")
                with ui.tabs().classes("w-full hw-tabs").props("dense no-caps") as tabs:
                    t_view = ui.tab("View", icon=hui.icon.library_view) if comp_type == "widgets" else None
                    t_docs = ui.tab("Docs", icon=hui.icon.library_docs)

                default_tab = t_view if t_view else t_docs
                # flex:1 fills remaining vertical space; panels handle their own scroll
                with (
                    ui.tab_panels(tabs, value=default_tab)
                    .classes("w-full")
                    .style("flex: 1; min-height: 0; overflow: hidden;")
                ):
                    if t_view:
                        with ui.tab_panel(t_view).style("height: 100%; overflow-y: auto; padding: 1rem;"):
                            self._render_widget_view(cls)

                    with ui.tab_panel(t_docs).style("height: 100%; overflow-y: auto; padding: 0;"):
                        with ui.column().classes("w-full gap-0 p-4"):
                            if doc_file and doc_file.exists():
                                doc_text = doc_file.read_text()
                                lines = doc_text.split("\n")
                                if lines and lines[0].startswith("<!--"):
                                    doc_text = "\n".join(lines[2:])
                                ui.markdown(doc_text).classes("w-full text-sm")
                            else:
                                docstring = inspect.getdoc(cls) if cls else None
                                if docstring:
                                    ui.markdown(docstring).classes("w-full text-sm")
                                else:
                                    ui.label("No documentation available.").classes(
                                        "hw-text-muted text-sm italic"
                                    )

    @staticmethod
    def _render_widget_view(cls) -> None:
        """Render a live preview of the widget class in the View tab."""
        if cls is None:
            ui.label("Widget class not found.").classes("hw-text-muted text-sm italic")
            return
        if not hasattr(cls, "create_element"):
            with ui.column().classes("items-center gap-2 py-6"):
                ui.icon("videocam_off").classes("text-3xl hw-text-dim")
                ui.label("Live preview only").classes("hw-text-muted text-sm italic")
                ui.label("This widget renders only when bound to a live port.").classes(
                    "hw-text-dim text-xs"
                )
            return
        try:
            mock_port = _WidgetPreviewPort()
            instance = cls(mock_port)
            instance.create_element()
        except Exception as exc:
            with ui.column().classes("gap-1"):
                ui.label("Preview failed").classes("text-sm hw-text-muted")
                ui.label(str(exc)).classes("text-xs font-mono hw-text-dim")

    def _close(self, context: "SessionContext") -> None:
        """Clear active component and notify listeners."""
        # Assigning emits SessionContext.active_component on the bus.
        context.active_component = None
