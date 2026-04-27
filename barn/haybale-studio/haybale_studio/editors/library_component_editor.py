# packages/haywire-app/src/haywire_studio/editors/component_detail_editor.py
"""
ComponentDetailEditor — shows detail info for the selected node component.

Renders in the right area and reacts to ACTIVE_COMPONENT_CHANGED events.
Displays identifiers with copy buttons, usage snippets, a Docs tab (markdown),
and a Source tab (CodeMirror with optional save for editable libraries).
"""

import inspect
from pathlib import Path
from typing import TYPE_CHECKING

from haywire.core.library.info import LibraryInfo
from nicegui import ui

from haywire.ui import elements as hui

from haywire.ui.editor.decorator import editor
from haywire.ui.editor.base import BaseEditor
from haywire.ui.context_signals import (
    ActiveComponentMoved,
    SelectionMoved,
    ThemeMoved,
)

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext
    from haywire.ui.context_signals import ContextSignal
    from nicegui.element import Element


class _WidgetPreviewPort:
    """Minimal mock port used to render a live widget preview without a real binding."""

    id = "preview"
    widget_config = {}


@editor(
    label="Component Detail",
    icon=hui.icon.library_component,
    default_slot="right",
    description="Detailed documentation for the selected node component.",
)
class LibraryComponentEditor(BaseEditor):
    """
    Displays documentation and port information for the selected library component.
    Rebuilds on ACTIVE_COMPONENT_CHANGED context events.
    """

    def __init__(self):
        self._container = None
        self._code_editor = None  # ui.codemirror reference for live theme updates

    def poll(self, context: "SessionContext", signal: "ContextSignal") -> bool:
        return isinstance(signal, (ActiveComponentMoved, SelectionMoved, ThemeMoved))

    def draw(self, context: "SessionContext", container: "Element") -> None:
        self._container = container
        self._code_editor = None
        self._rebuild(context)

    _COMP_ICONS = {
        "nodes": "account_tree",
        "widgets": "widgets",
        "types": "category",
        "adapters": "swap_horiz",
        "skins": "brush",
        "settings": "tune",
        "themes": "palette",
        "panels": "view_sidebar",
        "editors": "tab",
    }

    def _rebuild(self, context: "SessionContext") -> None:
        if self._container is None:
            return
        registry_key = context.active_component
        if not registry_key and context.active_node is not None:
            registry_key = context.active_node.registry_key
        with self._container:
            if not registry_key:
                hui.empty_state(
                    "Click a node or widget",
                    icon=hui.icon.library_docs,
                    hint="to view its documentation",
                )
                return

            app = context.app
            lib_id, comp_singular, class_name = registry_key.split(":", 2)
            comp_type = f"{comp_singular}s"
            lib: LibraryInfo | None = (
                app.library_manager.get_installed_library(lib_id)
                if app and getattr(app, "library_manager", None)
                else None
            )

            cls = self._lookup_class(app, lib_id, comp_type, registry_key)
            identity = getattr(cls, "class_identity", None) if cls else None

            label = getattr(identity, "label", None) or class_name or "?"
            description = getattr(identity, "description", None) or ""
            tags = getattr(identity, "tags", []) or []
            icon = self._COMP_ICONS.get(comp_type, "extension")
            actual_name = getattr(cls, "__name__", class_name) if cls else class_name
            module_path = getattr(cls, "__module__", None) if cls else None
            menu = getattr(identity, "menu", None) if identity else None

            # Resolve docs and source files
            _source_path = (lib.identity.folder_path if lib and hasattr(lib, "identity") else None) or (
                getattr(lib, "source_path", None) if lib else None
            )
            source = Path(_source_path) if _source_path else None
            doc_file = source / "docs" / comp_type / f"{class_name}.md" if source else None
            src_file: Path | None = None
            if cls:
                try:
                    src_file = Path(inspect.getfile(cls))
                except (TypeError, OSError):
                    pass
            _install_type = getattr(lib, "install_type", None) if lib else None
            is_editable = (
                _install_type.name == "EDITABLE"
                if hasattr(_install_type, "name")
                else _install_type == "EDITABLE"
            )

            # height:100% + flex column so tab_panels can fill remaining space
            with ui.column().classes("w-full p-4 gap-0").style("height: 100%;"):
                # ── Phase 5: Header bar ────────────────────────────────────
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

                # ── Tags ──────────────────────────────────────────────────
                if tags:
                    with ui.row().classes("gap-1 flex-wrap mb-2"):
                        for tag in tags:
                            hui.tag(str(tag), color="purple")

                # ── Phase 1: Identifiers ──────────────────────────────────
                hui.section_label("Identifiers")
                hui.info_row("Key", registry_key)
                hui.info_row("Class", actual_name)
                if module_path:
                    short = (module_path[:48] + "…") if len(module_path) > 50 else module_path
                    hui.info_row("Module", short, copy_value=module_path)
                if comp_type == "nodes" and menu:
                    hui.info_row("Menu", menu)

                # ── Phase 2: Usage snippets ───────────────────────────────
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

                # ── Tabs: View (widgets only) / Docs / Source ─────────────
                ui.separator().classes("mt-3")
                with ui.tabs().classes("w-full hw-tabs").props("dense no-caps") as tabs:
                    t_view = ui.tab("View", icon=hui.icon.library_view) if comp_type == "widgets" else None
                    t_docs = ui.tab("Docs", icon=hui.icon.library_docs)
                    t_source = (
                        ui.tab("Source", icon=hui.icon.library_source)
                        if src_file and src_file.exists()
                        else None
                    )

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
                                ui.separator().classes("my-3")
                                with ui.row().classes("w-full items-start gap-2"):
                                    ui.icon("info").classes("hw-text-dim text-sm mt-0.5 flex-shrink-0")
                                    with ui.column().classes("gap-0.5 min-w-0"):
                                        ui.label("Generate richer docs").classes(
                                            "text-xs font-bold hw-text-dim"
                                        )
                                        ui.label(
                                            "Run /haybale-gen-docs to produce per-component Markdown files,"
                                            " or add a detailed docstring directly to the class."
                                        ).classes("text-xs hw-text-dim")

                    if t_source:
                        with ui.tab_panel(t_source).style(
                            "height: 100%; padding: 0;"
                            " display: flex; flex-direction: column; overflow: hidden;"
                        ):
                            ui.label(src_file.name).classes("text-xs font-mono hw-text-dim").style(
                                "flex-shrink: 0; padding-bottom: 8px;"
                            )
                            # .hw-cm-isolate prevents .hw-panel * from cascading into
                            # CodeMirror's token spans (see app_shell.py static CSS).
                            with (
                                ui.element("div")
                                .classes("hw-cm-isolate")
                                .style("flex: 1; min-height: 0; width: 100%; display: flex;")
                            ):
                                self._code_editor = ui.codemirror(
                                    src_file.read_text(),
                                    language="Python",
                                    theme=self._codemirror_theme(context),
                                ).style("flex: 1; min-height: 0; width: 100%; height: 100%;")
                            if is_editable:

                                def _save(p=src_file, ed=self._code_editor):
                                    try:
                                        p.write_text(ed.value)
                                        ui.notify("Saved.", type="positive")
                                    except Exception as exc:
                                        ui.notify(f"Save failed: {exc}", type="negative")

                                ui.button("Save", icon=hui.icon.save, on_click=_save).props(
                                    "color=positive size=sm"
                                ).style("flex-shrink: 0; margin-top: 8px;")

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

    @staticmethod
    def _codemirror_theme(context: "SessionContext") -> str:
        """Return a CodeMirror theme name that matches the active Haywire workbench theme."""
        theme_key = getattr(context, "active_workbench_theme_key", "core:theme:workbench:haywire-dark")
        return "vscodeLight" if "light" in theme_key else "vscodeDark"

    def _close(self, context: "SessionContext") -> None:
        """Clear active component and notify listeners."""
        self._code_editor = None
        context.active_component = None
        session = context.session
        if session is not None:
            session.signal(ActiveComponentMoved())

    @staticmethod
    def _lookup_class(app, lib_id: str, comp_type: str, registry_key: str):
        """Look up the component class from the appropriate registry."""
        if not lib_id or not app:
            return None
        try:
            svc = app.library_service
            reg = {
                "nodes": svc.get_node_registry,
                "widgets": svc.get_widget_registry,
                "types": svc.get_type_registry,
                "adapters": svc.get_adapter_registry,
                "skins": svc.get_skin_registry,
                "themes": svc.get_theme_registry,
                "settings": svc.get_settings_registry,
                "panels": svc.get_panel_registry,
                "editors": svc.get_editor_registry,
            }.get(comp_type, lambda: None)()
            return reg.get(registry_key) if reg else None
        except Exception:
            return None
