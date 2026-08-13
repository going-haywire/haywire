# packages/haywire-app/src/haywire_studio/editors/library_browser.py
"""
LibraryBrowser — searchable library list editor for the left area.

Displays installed and marketplace libraries in a compact scrollable list.
Selecting a library updates context.active_library and fires LIBRARY_STATE_CHANGED.
"""

import logging

from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from nicegui import ui

from haywire.core.library.info import LibraryInfo
from haywire.core.library.haybale import Haybale
from haywire.ui import elements as hui
from haywire.ui.editor.decorator import editor
from haywire.ui.editor.identity import SlotName
from haywire.ui.editor.base import BaseEditor
from haywire.core.session.context import SessionContext
from haywire.core.session.handlers import redraw_on
from haywire.core.session.signals import (
    LibraryCatalogChanged,
    Reveal,
)

from haybale_marketplace.library_origin import compute_library_origin

if TYPE_CHECKING:
    from nicegui.element import Element

logger = logging.getLogger(__name__)


def derive_provenance_label(haybale, mf) -> str | None:
    """Return a short provenance label for a haybale.

    Shows direct subscriptions as 'from {host}' and transitive aggregator routing
    as 'via {host}'. Inline haybales (no `via`) return None.

    `mf` is the parsed MarketplaceFile (global). `haybale.via` is the URL that
    supplied this haybale during the most recent refresh.
    """
    via = getattr(haybale, "via", "") or ""
    if not via:
        return None

    if via.startswith("file://"):
        # Pasted TOML block — don't surface the user's filesystem path.
        return "from pasted"

    hostname = (urlsplit(via).hostname or via).lower()

    # Is this URL one of the user's direct [[stalls]] subscriptions?
    stall_urls = {sub.url for sub in getattr(mf, "stalls", [])}
    if via in stall_urls:
        return f"from {hostname}"

    # Otherwise it arrived via a [[markets]] aggregator.
    return f"via {hostname}"


@editor(
    label="Libraries",
    icon=hui.icon.library,
    default_slot=SlotName.ACTION,
    description="Searchable list of installed and available libraries.",
    order=30,
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
        # Slot holding the search field — rebuilt when _filter_search toggles.
        self._search_container: "Element | None" = None
        self._search_query: str = ""
        self._filter_required: bool = True
        self._filter_enabled: bool = True
        self._filter_disabled: bool = True
        self._filter_available: bool = True
        # Search field hidden until the user enables the search toggle.
        self._filter_search: bool = False
        # Refresh-button error surfacing.
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
            # Header: editor icon + title + overflow (burger) menu, with the
            # standard panel separator beneath — matches the Haystack editor.
            with hui.panel_header("Marketplace", icon=hui.icon.library):
                # Burger menu — actions that used to live in the toolbar:
                # Refresh, Add Source, Edit File.
                with ui.button(icon="more_vert").props("flat round dense size=sm").classes("flex-shrink-0"):
                    with ui.menu():
                        ui.menu_item(
                            "Refresh",
                            on_click=lambda c=context: self._on_refresh_click(c),
                        )
                        ui.menu_item(
                            "Add Source…",
                            on_click=lambda c=context: self._on_add_source_click(c),
                        )
                        ui.separator()
                        ui.menu_item(
                            "Edit File…",
                            on_click=lambda c=context: self._on_edit_file_click(c),
                        )

            # Filter row: "Show:" toggles + search toggle. Uses the same
            # full-width 1px var(--hw-border) separator as panel_header so the
            # line matches the header and the main-slot editor's tab divider.
            with (
                ui.column()
                .classes("w-full px-2 py-1.5 gap-1 flex-shrink-0")
                .style("border-bottom: 1px solid var(--hw-border);")
            ):
                with ui.row().classes("items-center gap-0.5 w-full"):
                    ui.label("Show:").classes("text-xs hw-text-dim mr-1")
                    self._make_toggle("required", "purple", "lock", "Required (cannot be disabled)", context)
                    self._make_toggle("enabled", "green", "check_circle", "Enabled", context)
                    self._make_toggle("disabled", "orange", "pause_circle", "Disabled", context)
                    self._make_toggle(
                        "available", "blue", "cloud_download", "Available in marketplace", context
                    )
                    self._make_search_toggle(context)

                # Search field — rendered only when the search toggle is on.
                self._search_container = ui.column().classes("w-full gap-0")
                self._render_search_field(context)

            # Scrollable list
            with ui.scroll_area().classes("flex-1 w-full"):
                self._list_container = ui.column().classes("w-full gap-0 p-0")
                self._render_list(context)

    def _render_search_field(self, context: "SessionContext") -> None:
        """(Re)build the search field slot based on _filter_search."""
        if self._search_container is None:
            return
        self._search_container.clear()
        if not self._filter_search:
            return
        with self._search_container:
            search = hui.input_field(
                placeholder="Search libraries…",
                value=self._search_query,
                clearable=True,
                autofocus=True,
            )
            search.on(
                "update:model-value",
                lambda e: self._on_search(e.args, context),
            )
            search.on("clear", lambda e: self._on_search("", context))

    def _make_toggle(self, attr: str, color: str, icon: str, tooltip: str, context: "SessionContext"):
        active = getattr(self, f"_filter_{attr}")
        with ui.button().props("flat round dense size=xs").tooltip(tooltip) as btn:
            icon_el = ui.icon(icon).classes("hw-use-props-color")
            icon_el.props(f"color={color if active else 'grey'}")
        btn.on("click", lambda a=attr, ie=icon_el, c=color, ctx=context: self._toggle(a, ie, c, ctx))

    def _toggle(self, attr: str, icon_el, color: str, context: "SessionContext"):
        current = getattr(self, f"_filter_{attr}")
        setattr(self, f"_filter_{attr}", not current)
        icon_el.props(f"color={color if not current else 'grey'}")
        self._render_list(context)

    def _make_search_toggle(self, context: "SessionContext"):
        """Toggle that shows/hides the search field (rather than filtering the list)."""
        active = self._filter_search
        with ui.button().props("flat round dense size=xs").tooltip("Search libraries") as btn:
            icon_el = ui.icon("search").classes("hw-use-props-color")
            icon_el.props(f"color={'blue' if active else 'grey'}")
        btn.on("click", lambda ie=icon_el, ctx=context: self._toggle_search(ie, ctx))

    def _toggle_search(self, icon_el, context: "SessionContext"):
        self._filter_search = not self._filter_search
        icon_el.props(f"color={'blue' if self._filter_search else 'grey'}")
        if not self._filter_search:
            # Hiding the search clears the query so a hidden filter never
            # silently narrows the list.
            self._search_query = ""
            self._render_list(context)
        self._render_search_field(context)

    def _on_search(self, args, context: "SessionContext"):
        if isinstance(args, (list, tuple)):
            value = args[0] if args else ""
        else:
            value = args
        self._search_query = value or ""
        self._render_list(context)

    def _on_refresh_click(self, context: "SessionContext") -> None:
        """Open the Refresh Libraries flow.

        Stepped rather than one-shot: fetching is a network round-trip per
        source and the write overwrites the project's cached library list, so
        the user gets to see the per-source outcome and the resulting deltas
        before anything is written. The silent post-Add-Source path still
        calls :meth:`_do_refresh` directly — there the user didn't ask for a
        refresh, so there is no decision to present.
        """
        from haybale_marketplace.state.marketplace_state import MarketplaceState

        from ._refresh_flow import show_refresh_flow

        if context.app_data is None or MarketplaceState not in context.app_data:
            ui.notify("Marketplace state not available", type="warning")
            return

        show_refresh_flow(
            context.app_data[MarketplaceState],
            on_done=lambda: self._after_refresh_flow(context),
            on_edit_global=lambda: self._on_edit_file_click(context),
        )

    def _after_refresh_flow(self, context: "SessionContext") -> None:
        """Re-render once the flow closes — an applied refresh rewrote the cache."""
        self._refresh_error = None
        self._render_list(context)

    def _on_add_source_click(self, context: "SessionContext") -> None:
        """Open the Add Source flow.

        Stepped rather than a dialog: the flow probes the source and settles
        any name collisions *before* writing the subscription, where the old
        dialog wrote first and asked afterwards. It also owns the refresh, so
        there is no silent post-add refresh to run here — only a re-render
        once the popup closes.
        """
        from ._add_source_flow import build_target, show_add_source_flow

        target = build_target(context)
        if target is None:
            ui.notify("Marketplace state not available", type="warning")
            return

        show_add_source_flow(target, on_done=lambda: self._after_refresh_flow(context))

    # Publishing lives in haybale-share's ShareEditor, not here. This editor
    # CONSUMES feeds; producing one is a different concern from the
    # per-library view this browser presents.

    def _do_refresh(self, context: "SessionContext", *, missing_state_severity: str) -> None:
        """Refresh the marketplace in one shot and re-render.

        The auto-flow path (post-Add-Source), where the user didn't ask for a
        refresh and so has no decision to make — the explicit toolbar button
        opens the stepped flow instead. ``missing_state_severity`` is
        "warning" when a caller wants a missing state surfaced and "silent"
        when it should just skip and re-render.
        """
        from haywire.core.marketstall import MalformedMarketplaceError

        from haybale_marketplace.state.marketplace_state import MarketplaceState

        if context.app_data is None or MarketplaceState not in context.app_data:
            if missing_state_severity == "warning":
                ui.notify("Marketplace state not available", type="warning")
            else:
                self._render_list(context)
            return

        state = context.app_data[MarketplaceState]
        try:
            report = state.refresh()
        except MalformedMarketplaceError as exc:
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

        self._refresh_error = None
        msg_parts = [f"Refreshed {report.haybales_resolved} package(s)"]
        if report.sources_unavailable:
            msg_parts.append(f"{report.sources_unavailable} source(s) unavailable")
        if report.new_stale:
            msg_parts.append(f"{report.new_stale} newly stale")
        if report.updates_available:
            msg_parts.append(f"{report.updates_available} update(s) available")
        ui.notify(" · ".join(msg_parts), type="positive")
        self._render_list(context)

    def _on_edit_file_click(self, context: "SessionContext") -> None:
        """Open the global marketplace.toml in haybale-studio's CodeEditor.

        Mirrors the OpenInCodeEditorPanel pattern in
        ``haybale_studio.panels.context_menu.file_actions``: set
        ``ctx.active_file`` (the synthetic emit drives editors that follow it)
        then publish a ``Reveal`` so the CodeEditor opens, bound to this path.

        the marketplace.toml is malformed — its whole purpose here is to let
        the user repair such files. Click Refresh after saving to re-apply.
        """
        from haybale_studio.editors.code_editor import CodeEditor
        from haywire.core.session.signals import Reveal
        from haybale_marketplace.config import GLOBAL_MARKETPLACE_DIR

        mp = GLOBAL_MARKETPLACE_DIR / "marketplace.toml"

        session = context.session
        if session is None:
            ui.notify("No active session — cannot open marketplace.toml", type="negative")
            return

        # Synthetic emit on SessionContext.active_file drives editors that follow it.
        context.active_file = mp
        session.publish(Reveal(editor=CodeEditor, binding_id=str(mp), label=mp.name))
        ui.notify("Save your changes, then click Refresh to apply.", type="info")

    def _get_unavailable_urls(self, context: "SessionContext") -> list[str]:
        """Return unavailable_urls from the last RefreshReport, or [] if no refresh has run."""
        from haybale_marketplace.state.marketplace_state import MarketplaceState

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

        # Surface refresh errors inline. Uses the design-guide token pattern
        # (--hw-danger / --hw-danger-bg + left border) instead of Tailwind
        # bg-red-* so the banner stays legible across themes.
        if self._refresh_error:
            with self._list_container:
                with (
                    ui.row()
                    .classes("p-2 gap-2 items-start w-full")
                    .style("border-left: 4px solid var(--hw-danger); background: var(--hw-danger-bg);")
                ):
                    ui.icon("error", size="18px").classes("hw-text-danger flex-shrink-0 mt-0.5")
                    ui.label(self._refresh_error).classes("text-xs hw-text-danger")

        # Surface partial-failure (some sources unavailable).
        # No --hw-warning-bg token exists; use the warning token for the border
        # accent and rely on hw-text-warning for the foreground.
        unavailable = self._get_unavailable_urls(context)
        if unavailable:
            with self._list_container:
                with (
                    ui.row()
                    .classes("p-2 gap-2 items-center w-full")
                    .style("border-left: 4px solid var(--hw-warning);")
                ):
                    ui.icon("warning", size="18px").classes("hw-text-warning flex-shrink-0")
                    n = len(unavailable)
                    ui.label(f"{n} source{'s' if n != 1 else ''} unavailable").classes(
                        "text-xs hw-text-warning font-medium"
                    )
                    with (
                        ui.button()
                        .props("flat dense size=xs")
                        .classes("ml-auto")
                        .tooltip("Show unavailable sources") as detail_btn
                    ):
                        ui.icon("info").classes("hw-text-warning")
                    detail_btn.on(
                        "click",
                        lambda urls=list(unavailable): self._show_unavailable_dialog(urls),
                    )

        from haybale_marketplace.state.library_manager_state import LibraryManagerState

        manager_state = context.app_data.get(LibraryManagerState)
        manager = manager_state.manager if manager_state is not None else None
        if manager is None:
            with self._list_container:
                ui.label("Library manager not available").classes("text-xs hw-text-dim p-2")
            return

        try:
            libraries = manager.list_installed()
        except Exception as e:
            logger.warning(f"LibraryBrowser: failed to list libraries: {e}")
            with self._list_container:
                ui.label("Error loading libraries").classes("text-xs hw-text-danger p-2")
            return

        q = self._search_query.lower().strip()

        # Needed by is_required() below (compute_library_origin) as well as
        # the available/updates_available block further down.
        workspace_root = getattr(context.app, "workspace_root", None)
        marketplace_path = Path(workspace_root) / ".haywire" / "marketplace.toml" if workspace_root else None

        def _label(info: LibraryInfo) -> str:
            return info.row.label or info.row.name

        def _enabled(info: LibraryInfo) -> bool:
            return info.enabled

        def matches(info: LibraryInfo) -> bool:
            if not q:
                return True
            row = info.row
            return (
                q in (row.label or row.name).lower()
                or bool(row.description and q in row.description.lower())
                or any(q in t.lower() for t in row.tags)
            )

        # Built once per render, reused by is_required() below — matches the
        # Haybale rows already parsed for the Available/updates_available
        # block further down, just indexed by distribution_name for lookup.
        _catalog_by_dist_name: dict[str, Haybale] = {}
        if marketplace_path and marketplace_path.exists():
            try:
                from haywire.core.marketstall import parse_project_marketplace as _parse_pm

                for entry in _parse_pm(marketplace_path).caches:
                    if entry.name:
                        _catalog_by_dist_name[entry.name] = entry
            except Exception:
                pass

        def _catalog_entry_for(info: LibraryInfo):
            return _catalog_by_dist_name.get(info.row.name)

        def is_required(lib: LibraryInfo) -> bool:
            # Required if origin.is_protected (framework-owned or this
            # workspace's own project-local library) OR some other installed
            # library declares this one in its haybale.toml's
            # linked_libraries. These are independent reasons for the same
            # badge — see LibraryOrigin.is_protected's docstring and the
            # glossary entry "required" vs "dependent".
            if not lib.installed:
                return False
            origin = compute_library_origin(
                lib,
                str(marketplace_path) if marketplace_path else None,
                catalog_entry=_catalog_entry_for(lib),
            )
            if origin.is_protected:
                return True
            return bool(manager.get_installed_dependents(lib.identity.name))

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

        # installed_names is needed both for available-package filtering and for
        # _library_item to decide whether a stale entry is user-removable.
        installed_names = {lib.row.name for lib in libraries if lib.row.name}

        # Parse marketplace.toml once to build both `available` (packages not yet
        # installed) and `updates_available` (dist names with newer cached versions).
        # workspace_root / marketplace_path computed earlier, above is_required().
        available: list[LibraryInfo] = []
        updates_available: set[str] = set()
        if marketplace_path and marketplace_path.exists():
            try:
                from packaging.version import Version
                from haywire.core.marketstall import parse_project_marketplace

                pm = parse_project_marketplace(marketplace_path)

                # Updates available — compare caches vs installed versions.
                for entry in pm.caches:
                    if not entry.version or not entry.name:
                        continue
                    lib = next((x for x in libraries if x.row.name == entry.name), None)
                    if lib and lib.row.version:
                        try:
                            if Version(entry.version) > Version(lib.row.version):
                                updates_available.add(entry.name)
                        except Exception:
                            pass

                # Available (not yet installed) — both [[caches]] and [[heaps]].
                if self._filter_available:
                    candidates: list[Haybale] = list(pm.caches)
                    # Surface [[heaps]] not already loaded as installed libraries.
                    for raw in pm.heaps:
                        name = raw.get("name")
                        if not isinstance(name, str):
                            continue
                        candidates.append(
                            Haybale(
                                name=name,
                                version="0.0.0",
                                label=raw.get("label", ""),
                                description=raw.get("description", ""),
                                source="local",
                                install_spec=str(raw.get("path", "")),
                                linked_libraries=list(raw.get("linked_libraries", [])),
                            )
                        )
                    # Wrapped as not-installed LibraryInfos so every list below
                    # holds one type and the item renderer needs no probing.
                    available = [
                        info
                        for info in (manager.entry_for_haybale(e) for e in candidates)
                        if info.row.name not in installed_names and matches(info)
                    ]
                    available.sort(key=_label)
            except Exception as e:
                logger.warning(f"LibraryBrowser: failed to load marketplace: {e}")

        with self._list_container:
            if required:
                hui.section_label("REQUIRED")
                for lib in required:
                    self._library_item(
                        lib,
                        "purple",
                        context,
                        installed_names,
                        has_update=lib.row.name in updates_available,
                    )

            if enabled:
                hui.section_label("ENABLED")
                for lib in enabled:
                    self._library_item(
                        lib,
                        "green",
                        context,
                        installed_names,
                        has_update=lib.row.name in updates_available,
                    )

            if disabled:
                hui.section_label("DISABLED")
                for lib in disabled:
                    self._library_item(
                        lib,
                        "orange",
                        context,
                        installed_names,
                        has_update=lib.row.name in updates_available,
                    )

            if available:
                hui.section_label("AVAILABLE")
                for info in available:
                    self._library_item(info, "gray", context, installed_names)

            if not required and not enabled and not disabled and not available:
                hui.empty_state("No libraries found", icon=hui.icon.empty_no_results)

    def _library_item(
        self,
        lib: LibraryInfo,
        dot_color: str,
        context: "SessionContext",
        installed_names: set[str],
        has_update: bool = False,
    ):
        # ``haybale_row`` rather than ``row``: the list-item element below already
        # owns that name in this scope.
        haybale_row = lib.row
        label = haybale_row.label or haybale_row.name or "?"
        version = haybale_row.version

        is_stale = haybale_row.stale
        sublabel = f"v{version}" if version else None
        if is_stale:
            sublabel = f"{sublabel} (stale)" if sublabel else "(stale)"

        # Provenance label — only for cache entries with a `via` URL.
        provenance = self._provenance_label_for(lib, context)
        if provenance:
            sublabel = f"{provenance} — {sublabel}" if sublabel else provenance

        row = hui.list_item(
            label,
            sublabel=sublabel,
            dot_color=dot_color,
            on_click=lambda entry=lib, ctx=context: self._select_library(entry, ctx),
        )
        if has_update:
            with row:
                ui.icon("arrow_upward", size="14px").classes(
                    "hw-use-props-color hw-text-warning ml-auto flex-shrink-0"
                ).tooltip("Update available")
        if is_stale:
            last_seen = haybale_row.last_seen or "unknown"
            entry_name = haybale_row.name
            is_uninstalled = bool(entry_name) and entry_name not in installed_names
            with row:
                stale_dot = ui.element("div").classes("w-2 h-2 rounded-full bg-red-500 flex-shrink-0")
                stale_dot.tooltip(f"Stale — last seen {last_seen}")
                if is_uninstalled:
                    with (
                        ui.button()
                        .props("flat round dense size=xs")
                        .classes("ml-auto")
                        .tooltip("Remove from cache") as trash_btn
                    ):
                        ui.icon("delete_outline").classes("hw-use-props-color").props("color=red")
                    trash_btn.on(
                        "click.stop",
                        lambda name=entry_name, ctx=context: self._on_remove_stale_click(name, ctx),
                    )

    def _provenance_label_for(self, lib: LibraryInfo, context: "SessionContext") -> str | None:
        """Look up the user's [[stalls]] list to derive 'from {host}' vs 'via {host}'."""
        from haybale_marketplace.state.marketplace_state import MarketplaceState

        if context.app_data is None or MarketplaceState not in context.app_data:
            return None
        state = context.app_data[MarketplaceState]
        mf = state.get_global()
        if mf is None:
            return None
        return derive_provenance_label(lib.row, mf)

    def _on_remove_stale_click(self, name: str, context: "SessionContext") -> None:
        """Drop a stale [[caches]] entry from the project marketplace, then re-render."""
        from haybale_marketplace.state.marketplace_state import MarketplaceState

        if context.app_data is None or MarketplaceState not in context.app_data:
            ui.notify("Marketplace state not available", type="warning")
            return

        state = context.app_data[MarketplaceState]
        try:
            removed = state.remove_stale_haybale(name)
        except Exception as exc:
            logger.warning(f"LibraryBrowser: remove_stale_haybale({name!r}) failed: {exc}")
            ui.notify(f"Failed to remove {name}: {exc}", type="negative")
            return

        if removed:
            ui.notify(f"Removed {name} from cache", type="positive")
        else:
            ui.notify(f"{name} was already gone from cache", type="info")
        self._render_list(context)

    def _select_library(self, lib: LibraryInfo, context: "SessionContext"):
        # Assigning emits SessionContext.active_library / .active_component
        # synthetically on the bus; no manual signal emit needed.
        context.active_library = lib
        context.active_component = None

        session = context.session
        if session is not None:
            from haybale_marketplace.editors.library_overview_editor import LibraryOverviewEditor

            session.publish(Reveal(editor=LibraryOverviewEditor))
