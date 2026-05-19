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
from haywire.core.session.context import SessionContext
from haywire.core.session.handlers import redraw_on
from haywire.core.session.signals import (
    LibraryCatalogChanged,
    Reveal,
)

if TYPE_CHECKING:
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

    def __init__(self, wrapper):
        super().__init__(wrapper)
        self._container = None
        self._list_container = None
        self._search_query: str = ""
        self._filter_required: bool = True
        self._filter_enabled: bool = True
        self._filter_disabled: bool = True
        self._filter_available: bool = True
        # Plan E Phase 4: refresh-button error surfacing.
        self._refresh_error: str | None = None

    @redraw_on(SessionContext.active_library, LibraryCatalogChanged)
    def _refresh_on_library_change(self, context: "SessionContext", event) -> None:
        # Empty body — the decorator triggers wrapper.redraw() after return.
        pass

    def draw(self, context: "SessionContext", container: "Element") -> None:
        self._container = container
        with container:
            self._build_ui(context)

    def _build_ui(self, context: "SessionContext") -> None:
        with ui.column().classes("w-full h-full gap-0"):
            # Toolbar (Refresh, Add Source, Edit File)
            with ui.row().classes("p-2 gap-2 border-b flex-shrink-0 items-center"):
                with (
                    ui.button()
                    .props("flat dense size=sm")
                    .tooltip("Refresh marketplace from subscribed sources") as refresh_btn
                ):
                    ui.icon("refresh").classes("hw-use-props-color").props("color=blue")
                    ui.label("Refresh").classes("text-xs ml-1")
                refresh_btn.on("click", lambda c=context: self._on_refresh_click(c))

                with (
                    ui.button()
                    .props("flat dense size=sm")
                    .tooltip("Add a marketplace or marketstall source") as add_source_btn
                ):
                    ui.icon("add_circle").classes("hw-use-props-color").props("color=green")
                    ui.label("Add Source").classes("text-xs ml-1")
                add_source_btn.on("click", lambda c=context: self._on_add_source_click(c))

                with (
                    ui.button()
                    .props("flat dense size=sm")
                    .tooltip("Open ~/.haywire/marketplace.toml in your text editor") as edit_file_btn
                ):
                    ui.icon("edit").classes("hw-use-props-color").props("color=gray")
                    ui.label("Edit File").classes("text-xs ml-1")
                edit_file_btn.on("click", lambda: self._on_edit_file_click())

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

    def _on_refresh_click(self, context: "SessionContext") -> None:
        """Run MarketplaceState.refresh(), surface result via ui.notify + inline banner."""
        from haywire.core.marketplace_errors import MalformedGlobalMarketplaceError

        from haybale_studio.state.marketplace_state import MarketplaceState

        if context.app_data is None or MarketplaceState not in context.app_data:
            ui.notify("Marketplace state not available", type="warning")
            return

        state = context.app_data[MarketplaceState]
        try:
            report = state.refresh()
        except MalformedGlobalMarketplaceError as exc:
            self._refresh_error = (
                f"Global marketplace is malformed: {exc}. "
                f"Click Edit File to repair, then click Refresh again."
            )
            ui.notify("Refresh failed: global marketplace is malformed", type="negative")
            self._render_list(context)
            return
        except Exception as exc:
            logger.warning(f"LibraryBrowser: refresh failed: {exc}")
            self._refresh_error = f"Refresh failed: {exc}"
            ui.notify(f"Refresh failed: {exc}", type="negative")
            self._render_list(context)
            return

        # Success — clear any previous error and notify with summary.
        self._refresh_error = None
        msg_parts = [f"Refreshed {report.packages_resolved} package(s)"]
        if report.sources_unavailable:
            msg_parts.append(f"{report.sources_unavailable} source(s) unavailable")
        if report.new_stale:
            msg_parts.append(f"{report.new_stale} newly stale")
        ui.notify(" · ".join(msg_parts), type="positive")
        self._render_list(context)

    def _on_add_source_click(self, context: "SessionContext") -> None:
        """Open the Add Source dialog. On a successful add, the dialog closes and
        the on_added callback triggers a refresh + re-render."""
        from .library_marketplace_dialog import show_add_source_dialog

        def _after_added() -> None:
            # Re-running refresh would surface the new source's packages in the cache.
            # For Task 26 the handlers are placeholders, so this is just a render bump.
            self._render_list(context)

        show_add_source_dialog(on_added=_after_added)

    def _on_edit_file_click(self) -> None:
        """Open ~/.haywire/marketplace.toml in the OS default text editor."""
        import platform
        import subprocess

        from haywire_studio.config import GLOBAL_CONFIG_DIR, ensure_global_config

        ensure_global_config()
        mp = GLOBAL_CONFIG_DIR / "marketplace.toml"
        try:
            if platform.system() == "Darwin":
                subprocess.run(["open", str(mp)], check=False)
            elif platform.system() == "Windows":
                subprocess.run(["start", "", str(mp)], shell=True, check=False)
            else:
                subprocess.run(["xdg-open", str(mp)], check=False)
            ui.notify(
                f"Opened {mp}. Save your changes, then click Refresh to apply.",
                type="info",
            )
        except Exception as exc:
            logger.exception("Failed to open marketplace.toml")
            ui.notify(f"Failed to open editor: {exc}", type="negative")

    def _get_unavailable_urls(self, context: "SessionContext") -> list[str]:
        """Return unavailable_urls from the last RefreshReport, or [] if no refresh has run."""
        from haybale_studio.state.marketplace_state import MarketplaceState

        if context.app_data is None or MarketplaceState not in context.app_data:
            return []
        state = context.app_data[MarketplaceState]
        if state.last_report is None:
            return []
        return list(state.last_report.unavailable_urls)

    def _show_unavailable_dialog(self, urls: list[str]) -> None:
        """Modal listing the unavailable source URLs with a fallback-cache hint."""
        with ui.dialog() as dialog, hui.dialog_card():
            with ui.column().classes("p-4 gap-2"):
                ui.label("Sources unavailable").classes("text-sm font-medium")
                ui.label(
                    "These sources couldn't be fetched. Cached responses (if any) were used as fallback."
                ).classes("text-xs hw-text-dim")
                for url in urls:
                    ui.label(url).classes("text-xs hw-text-default font-mono")
                with ui.row().classes("w-full justify-end mt-2"):
                    ui.button("Close", on_click=dialog.close).props("flat")
        dialog.open()

    def _render_list(self, context: "SessionContext") -> None:
        if self._list_container is None:
            return
        self._list_container.clear()

        # Plan E Phase 4: surface refresh errors inline.
        if self._refresh_error:
            with self._list_container:
                with ui.row().classes("p-2 gap-1 items-center bg-red-50 border-l-4 border-red-400 w-full"):
                    ui.icon("error").classes("hw-use-props-color").props("color=red")
                    ui.label(self._refresh_error).classes("text-xs hw-text-default")

        # Plan E Phase 4: surface partial-failure (some sources unavailable).
        unavailable = self._get_unavailable_urls(context)
        if unavailable:
            with self._list_container:
                with ui.row().classes(
                    "p-2 gap-1 items-center bg-yellow-50 border-l-4 border-yellow-400 w-full"
                ):
                    ui.icon("warning").classes("hw-use-props-color").props("color=orange")
                    n = len(unavailable)
                    ui.label(f"{n} source{'s' if n != 1 else ''} unavailable").classes(
                        "text-xs hw-text-default font-medium"
                    )
                    with (
                        ui.button()
                        .props("flat dense size=xs")
                        .tooltip("Show unavailable sources") as detail_btn
                    ):
                        ui.icon("info").classes("hw-use-props-color").props("color=gray")
                    detail_btn.on(
                        "click",
                        lambda urls=list(unavailable): self._show_unavailable_dialog(urls),
                    )

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
                Path(workspace_root) / ".haywire" / "marketplace.toml" if workspace_root else None
            )
            if marketplace_path:
                try:
                    from haywire.core.marketplace_runtime import parse_project_marketplace

                    installed_names = {lib.distribution_name for lib in libraries if lib.distribution_name}
                    pm = parse_project_marketplace(marketplace_path)
                    available = [e for e in pm.packages if e.name not in installed_names and matches(e)]
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

        is_stale = bool(getattr(lib, "stale", False))
        sublabel = f"v{version}" if version else None
        if is_stale:
            sublabel = f"{sublabel} (stale)" if sublabel else "(stale)"

        row = hui.list_item(
            label,
            sublabel=sublabel,
            dot_color=dot_color,
            on_click=lambda entry=lib, ctx=context: self._select_library(entry, ctx),
        )
        if is_stale:
            last_seen = getattr(lib, "last_seen", "") or "unknown"
            with row:
                stale_dot = ui.element("div").classes("w-2 h-2 rounded-full bg-red-500 flex-shrink-0")
                stale_dot.tooltip(f"Stale — last seen {last_seen}")

    def _select_library(self, lib, context: "SessionContext"):
        # Assigning emits SessionContext.active_library / .active_component
        # synthetically on the bus; no manual signal emit needed.
        context.active_library = lib
        context.active_component = None

        session = context.session
        if session is not None:
            from haybale_studio.editors.library_overview_editor import LibraryOverviewEditor

            session.publish(Reveal(editor=LibraryOverviewEditor))
