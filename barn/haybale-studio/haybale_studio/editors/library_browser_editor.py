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


def derive_provenance_label(haybale, mf) -> str | None:
    """Return a short provenance label for a haybale.

    Spec §7.4: shows direct subscriptions as 'from {host}' and transitive
    aggregator routing as 'via {host}'. Inline haybales (no `via`) return None.

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
                edit_file_btn.on("click", lambda c=context: self._on_edit_file_click(c))

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
        self._do_refresh(context, missing_state_severity="warning")

    def _on_add_source_click(self, context: "SessionContext") -> None:
        """Open the Add Source dialog. On a successful add, run refresh so the
        new source's packages land in the project marketplace cache before we
        re-render."""
        from .library_marketplace_dialog import show_add_source_dialog

        def _after_added() -> None:
            self._do_refresh(context, missing_state_severity="silent")

        show_add_source_dialog(on_added=_after_added)

    def _do_refresh(self, context: "SessionContext", *, missing_state_severity: str) -> None:
        """Refresh the marketplace and re-render.

        Shared by the toolbar Refresh button and the post-Add-Source auto-refresh.
        ``missing_state_severity`` is "warning" for explicit clicks (surface the
        problem) and "silent" for auto-flows (the user didn't ask for refresh —
        a missing state means we just skip and re-render).
        """
        from haywire.core.marketstall import MalformedMarketplaceError

        from haybale_studio.state.marketplace_state import MarketplaceState

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
        ui.notify(" · ".join(msg_parts), type="positive")
        self._render_list(context)

    def _on_edit_file_click(self, context: "SessionContext") -> None:
        """Open ~/.haywire/marketplace.toml in haybale-studio's CodeEditor.

        Mirrors the OpenInCodeEditorPanel pattern in
        ``haybale_studio.panels.context_menu.file_actions``: set
        ``ctx.active_file`` (the synthetic emit drives editors that follow it)
        then publish a ``Reveal`` so the CodeEditor opens, bound to this path.

        Tolerates ensure_global_config failures so the editor still opens when
        the marketplace.toml is malformed — its whole purpose here is to let
        the user repair such files. Click Refresh after saving to re-apply.
        """
        from haybale_studio.editors.code_editor import CodeEditor
        from haywire.core.session.signals import Reveal
        from haywire_studio.config import GLOBAL_CONFIG_DIR, ensure_global_config

        try:
            ensure_global_config()
        except Exception as exc:
            logger.warning(f"ensure_global_config failed, opening editor anyway: {exc}")

        mp = GLOBAL_CONFIG_DIR / "marketplace.toml"

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

        # Plan E Phase 4: surface refresh errors inline. Uses the design-guide
        # token pattern (--hw-danger / --hw-danger-bg + left border) instead of
        # Tailwind bg-red-* so the banner stays legible across themes.
        if self._refresh_error:
            with self._list_container:
                with (
                    ui.row()
                    .classes("p-2 gap-2 items-start w-full")
                    .style("border-left: 4px solid var(--hw-danger); background: var(--hw-danger-bg);")
                ):
                    ui.icon("error", size="18px").classes("hw-text-danger flex-shrink-0 mt-0.5")
                    ui.label(self._refresh_error).classes("text-xs hw-text-danger")

        # Plan E Phase 4: surface partial-failure (some sources unavailable).
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
        manager = app.library_manager

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
            # Required = some other installed library declares this one in its
            # @library(dependencies=[...]) decorator. Same signal the overview
            # editor uses to gate the Disable / Uninstall buttons, so the purple
            # badge and the disabled button always agree.
            if not hasattr(lib, "identity"):
                return False
            return bool(manager.get_installed_dependents(lib.identity.id))

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

        # Marketplace entries not yet installed — both refreshed [[caches]]
        # and [[heaps]] (path-based libraries the project knows about but
        # uv hasn't surfaced as importable libraries yet).
        available = []
        if self._filter_available:
            workspace_root = getattr(app, "workspace_root", None)
            marketplace_path = (
                Path(workspace_root) / ".haywire" / "marketplace.toml" if workspace_root else None
            )
            if marketplace_path:
                try:
                    from haywire.core.marketstall import Haybale, parse_project_marketplace

                    installed_names = {lib.distribution_name for lib in libraries if lib.distribution_name}
                    pm = parse_project_marketplace(marketplace_path)

                    candidates: list = list(pm.caches)
                    # Surface [[heaps]] not already loaded as installed libraries.
                    for raw in pm.heaps:
                        name = raw.get("name")
                        if not isinstance(name, str):
                            continue
                        candidates.append(
                            Haybale(
                                name=name,
                                min_version="",
                                label=raw.get("label", ""),
                                description=raw.get("description", ""),
                                source="local",
                                install_spec=str(raw.get("path", "")),
                            )
                        )
                    available = [e for e in candidates if e.name not in installed_names and matches(e)]
                    available.sort(key=lambda x: x.label or x.name)
                except Exception as e:
                    logger.warning(f"LibraryBrowser: failed to load marketplace: {e}")

        # installed_names available outside the "available" branch too, so
        # _library_item can decide whether a stale entry is user-removable.
        installed_names = {lib.distribution_name for lib in libraries if lib.distribution_name}

        with self._list_container:
            if required:
                hui.section_label("REQUIRED")
                for lib in required:
                    self._library_item(lib, "purple", context, installed_names)

            if enabled:
                hui.section_label("ENABLED")
                for lib in enabled:
                    self._library_item(lib, "green", context, installed_names)

            if disabled:
                hui.section_label("DISABLED")
                for lib in disabled:
                    self._library_item(lib, "orange", context, installed_names)

            if available:
                hui.section_label("AVAILABLE")
                for entry in available:
                    self._library_item(entry, "gray", context, installed_names)

            if not required and not enabled and not disabled and not available:
                hui.empty_state("No libraries found", icon=hui.icon.empty_no_results)

    def _library_item(
        self,
        lib,
        dot_color: str,
        context: "SessionContext",
        installed_names: set[str],
    ):
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

        # Provenance label per spec §7.4 — only for cache entries with a `via` URL.
        provenance = self._provenance_label_for(lib, context)
        if provenance:
            sublabel = f"{provenance} — {sublabel}" if sublabel else provenance

        row = hui.list_item(
            label,
            sublabel=sublabel,
            dot_color=dot_color,
            on_click=lambda entry=lib, ctx=context: self._select_library(entry, ctx),
        )
        if is_stale:
            last_seen = getattr(lib, "last_seen", "") or "unknown"
            entry_name = getattr(lib, "name", "") or getattr(lib, "distribution_name", "")
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

    def _provenance_label_for(self, lib, context: "SessionContext") -> str | None:
        """Look up the user's [[stalls]] list to derive 'from {host}' vs 'via {host}'."""
        from haybale_studio.state.marketplace_state import MarketplaceState

        if context.app_data is None or MarketplaceState not in context.app_data:
            return None
        state = context.app_data[MarketplaceState]
        mf = state.get_global()
        if mf is None:
            return None
        return derive_provenance_label(lib, mf)

    def _on_remove_stale_click(self, name: str, context: "SessionContext") -> None:
        """Drop a stale [[caches]] entry from the project marketplace, then re-render."""
        from haybale_studio.state.marketplace_state import MarketplaceState

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

    def _select_library(self, lib, context: "SessionContext"):
        # Assigning emits SessionContext.active_library / .active_component
        # synthetically on the bus; no manual signal emit needed.
        context.active_library = lib
        context.active_component = None

        session = context.session
        if session is not None:
            from haybale_studio.editors.library_overview_editor import LibraryOverviewEditor

            session.publish(Reveal(editor=LibraryOverviewEditor))
