# packages/haywire-app/src/haywire_studio/editors/library_browser.py
"""
LibraryBrowser — searchable library list editor for the left area.

Displays installed and marketplace libraries in a compact scrollable list.
Selecting a library updates context.active_library and fires LIBRARY_STATE_CHANGED.
"""

import logging

from pathlib import Path
from typing import TYPE_CHECKING

from nicegui import ui

from haywire.ui import elements as hui
from haywire.ui.editor.decorator import editor
from haywire.ui.editor.base import BaseEditor
from haywire.core.session.signals_and_lifecycle import (
    ActiveLibraryMoved,
    LibraryCatalogChanged,
    Reveal,
)

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext
    from haywire.core.session.signals_and_lifecycle import ContextSignal
    from nicegui.element import Element

logger = logging.getLogger(__name__)


@editor(
    label="Libraries",
    icon=hui.icon.library,
    default_slot="left",
    description="Searchable list of installed and available libraries.",
)
class LibraryBrowserEditor(BaseEditor):
    """
    Shows a searchable list of installed (enabled/disabled) libraries.

    On selection, updates context.active_library and notifies subscribers
    via LIBRARY_STATE_CHANGED. The library_manager is retrieved from
    context.app.library_manager.
    """

    def __init__(self):
        self._container = None
        self._list_container = None
        self._search_query: str = ""
        self._filter_required: bool = True
        self._filter_enabled: bool = True
        self._filter_disabled: bool = True
        self._filter_available: bool = True

    def redraw_on_signal(self, context: "SessionContext", signal: "ContextSignal") -> bool:
        # Today's LIBRARY_STATE_CHANGED filter widens to both replacement
        # signal classes during migration (§11.2 editorial decision #6).
        return isinstance(signal, (ActiveLibraryMoved, LibraryCatalogChanged))

    def draw(self, context: "SessionContext", container: "Element") -> None:
        self._container = container
        with container:
            self._build_ui(context)

    def _build_ui(self, context: "SessionContext") -> None:
        with ui.column().classes("w-full h-full gap-0"):
            # Search bar
            with ui.column().classes("p-2 gap-1 border-b flex-shrink-0"):
                search = hui.input_field(
                    placeholder="Search libraries…",
                    clearable=True,
                )
                search.on(
                    "update:model-value",
                    lambda e: self._on_search(e.args, context),
                )
                search.on("clear", lambda e: self._on_search("", context))

                # Filter toggles
                with ui.row().classes("items-center gap-0.5"):
                    ui.label("Show:").classes("text-xs hw-text-dim mr-1")
                    self._make_toggle("required", "purple", "lock", "Required (cannot be disabled)", context)
                    self._make_toggle("enabled", "green", "check_circle", "Enabled", context)
                    self._make_toggle("disabled", "orange", "pause_circle", "Disabled", context)
                    self._make_toggle(
                        "available", "blue", "cloud_download", "Available in marketplace", context
                    )

            # Scrollable list
            with ui.scroll_area().classes("flex-1 w-full"):
                self._list_container = ui.column().classes("w-full gap-0 p-0")
                self._render_list(context)

    def _make_toggle(self, attr: str, color: str, icon: str, tooltip: str, context: "SessionContext"):
        active = getattr(self, f"_filter_{attr}")
        with ui.button().props("flat round dense size=sm").tooltip(tooltip) as btn:
            icon_el = ui.icon(icon).classes("hw-use-props-color")
            icon_el.props(f"color={color if active else 'grey'}")
        btn.on("click", lambda a=attr, ie=icon_el, c=color, ctx=context: self._toggle(a, ie, c, ctx))

    def _toggle(self, attr: str, icon_el, color: str, context: "SessionContext"):
        current = getattr(self, f"_filter_{attr}")
        setattr(self, f"_filter_{attr}", not current)
        icon_el.props(f"color={color if not current else 'grey'}")
        self._render_list(context)

    def _on_search(self, args, context: "SessionContext"):
        if isinstance(args, (list, tuple)):
            value = args[0] if args else ""
        else:
            value = args
        self._search_query = value or ""
        self._render_list(context)

    def _render_list(self, context: "SessionContext") -> None:
        if self._list_container is None:
            return
        self._list_container.clear()

        app = context.app
        if app is None or not hasattr(app, "library_manager"):
            with self._list_container:
                ui.label("Library manager not available").classes("text-xs hw-text-dim p-2")
            return

        try:
            libraries = app.library_manager.list_installed()
        except Exception as e:
            logger.warning(f"LibraryBrowser: failed to list libraries: {e}")
            with self._list_container:
                ui.label("Error loading libraries").classes("text-xs hw-text-danger p-2")
            return

        q = self._search_query.lower().strip()

        from haywire_studio.library_manager import LibraryManager

        def _label(lib) -> str:
            # LibraryInfo wraps identity; MarketplaceEntry has label/name directly
            if hasattr(lib, "identity"):
                return lib.identity.label or ""
            return getattr(lib, "label", "") or getattr(lib, "name", "")

        def _enabled(lib) -> bool:
            if hasattr(lib, "identity"):
                return lib.enabled
            return getattr(lib, "enabled", True)

        def matches(lib) -> bool:
            if not q:
                return True
            label = _label(lib)
            if hasattr(lib, "identity"):
                desc = lib.identity.description or ""
                tags = lib.identity.tags or []
            else:
                desc = getattr(lib, "description", "") or ""
                tags = getattr(lib, "tags", []) or []
            return (
                q in label.lower() or bool(desc and q in desc.lower()) or any(q in t.lower() for t in tags)
            )

        def is_required(lib) -> bool:
            dist = getattr(lib, "distribution_name", "")
            return bool(dist and LibraryManager.is_required_by_another_package(dist))

        # Always compute the exclusion set so required libs never bleed into ENABLED,
        # even when the required filter toggle is off.
        _all_required = [lib for lib in libraries if _enabled(lib) and is_required(lib)]
        required_set = {id(lib) for lib in _all_required}
        required = [lib for lib in _all_required if matches(lib)] if self._filter_required else []
        enabled = (
            [lib for lib in libraries if id(lib) not in required_set and _enabled(lib) and matches(lib)]
            if self._filter_enabled
            else []
        )
        disabled = (
            [lib for lib in libraries if not _enabled(lib) and matches(lib)] if self._filter_disabled else []
        )
        required.sort(key=_label)
        enabled.sort(key=_label)
        disabled.sort(key=_label)

        # Marketplace entries not yet installed
        available = []
        if self._filter_available:
            workspace_root = getattr(app, "workspace_root", None)
            marketplace_path = (
                str(Path(workspace_root) / ".haywire" / "marketplace.toml") if workspace_root else None
            )
            if marketplace_path:
                try:
                    installed_names = {lib.distribution_name for lib in libraries if lib.distribution_name}
                    entries = LibraryManager.load_marketplace(marketplace_path)
                    available = [e for e in entries if e.name not in installed_names and matches(e)]
                    available.sort(key=lambda x: x.label or x.name)
                except Exception as e:
                    logger.warning(f"LibraryBrowser: failed to load marketplace: {e}")

        with self._list_container:
            if required:
                hui.section_label("REQUIRED")
                for lib in required:
                    self._library_item(lib, "purple", context)

            if enabled:
                hui.section_label("ENABLED")
                for lib in enabled:
                    self._library_item(lib, "green", context)

            if disabled:
                hui.section_label("DISABLED")
                for lib in disabled:
                    self._library_item(lib, "orange", context)

            if available:
                hui.section_label("AVAILABLE")
                for entry in available:
                    self._library_item(entry, "gray", context)

            if not required and not enabled and not disabled and not available:
                hui.empty_state("No libraries found", icon=hui.icon.empty_no_results)

    def _library_item(self, lib, dot_color: str, context: "SessionContext"):
        if hasattr(lib, "identity"):
            label = lib.identity.label or "?"
            version = lib.identity.version or ""
        else:
            label = getattr(lib, "label", None) or getattr(lib, "name", "?")
            version = getattr(lib, "version", "")
        hui.list_item(
            label,
            sublabel=f"v{version}" if version else None,
            dot_color=dot_color,
            on_click=lambda entry=lib, ctx=context: self._select_library(entry, ctx),
        )

    def _select_library(self, lib, context: "SessionContext"):
        context.active_library.value = lib
        context.active_component.value = None

        session = context.session
        if session is not None:
            from haybale_studio.editors.library_overview_editor import LibraryOverviewEditor

            session.signal(ActiveLibraryMoved())
            session.lifecycle(Reveal(editor=LibraryOverviewEditor))
