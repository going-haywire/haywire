"""
haywire.ui.elements.icons — Semantic icon registry for Haywire UI.

Usage via the hui module-level alias:

    from haywire.ui import elements as hui

    icon=hui.icon.canvas
    icon=hui.icon.add
"""

from __future__ import annotations

from typing import Final


class AppIcon:
    """
    Semantic icon names for Haywire UI concepts.

    Each Material icon string appears at most once — one icon, one concept.
    Use via the module-level alias:  hui.icon.canvas, hui.icon.edge, etc.

    Raw Material icon reference: https://fonts.google.com/icons?icon.set=Material%20Icons
    """

    # ── Scope tabs (Properties sidebar) ──────────────────────────────────────
    app: Final[str] = "home"
    """Application-wide settings scope."""
    execution: Final[str] = "rocket_launch"
    """Execution behaviour scope."""
    canvas: Final[str] = "grid_on"
    """Canvas & nodes scope."""
    debug: Final[str] = "bug_report"
    """Debug / dev tools scope."""

    # -- Core Classes ───────────────────────────────────────────────────────────────

    graph: Final[str] = "polyline"
    """Active graph info scope."""
    node: Final[str] = "account_tree"
    """Selected node properties scope."""
    node_settings: Final[str] = "tune"
    """Node settings scope (only available when node has setting bags)."""
    edge: Final[str] = "cable"
    """Selected edge info scope."""
    widget: Final[str] = "widgets"
    """Selected widget info scope."""
    skin: Final[str] = "brush"
    """Skins in library overview."""
    adapter: Final[str] = "electrical_services"
    """Adapters tab in library overview."""
    type: Final[str] = "category"
    """Types in library overview."""
    panel: Final[str] = "dashboard_customize"
    """Panels in library overview."""
    editor: Final[str] = "space_dashboard"
    """Editors in library overview."""
    theme: Final[str] = "palette"
    """Theme and appearance settings."""

    
    # ── Canvas sub-panels ────────────────────────────────────────────────────
    canvas_grid: Final[str] = "grid_4x4"
    """Grid display settings panel."""
    canvas_node_skins: Final[str] = "format_shapes"
    """Node dimensions and typography panel."""
    canvas_zoom_pan: Final[str] = "settings_overscan"
    """Pan and zoom behaviour panel."""
    canvas_minimap: Final[str] = "map"
    """Minimap visibility and position panel."""

    # ── Node panel sections ──────────────────────────────────────────────────
    node_info: Final[str] = "info"
    """Node identity and metadata panel."""
    node_ports: Final[str] = "device_hub"
    """Node port list panel."""
    node_status: Final[str] = "check_circle"
    """Node validation and runtime status panel."""

    # ── Graph ────────────────────────────────────────────────────────────────
    graph_manager: Final[str] = "apps"
    """Multi-graph file browser."""

    # ── Library / editor tabs ────────────────────────────────────────────────
    library_browser: Final[str] = "extension"
    """Library browser editor."""
    library_component: Final[str] = "description"
    """Component detail editor."""
    library_docs: Final[str] = "menu_book"
    """Component documentation tab."""
    library_source: Final[str] = "code"
    """Component source tab."""
    library_view: Final[str] = "visibility"
    """Component preview tab."""

    # ── Edge panels ───────────────────────────────────────────────────────────
    edge_statistics: Final[str] = "linear_scale"
    """Edge execution statistics and connection path panels."""

    # ── File system ───────────────────────────────────────────────────────────
    folder: Final[str] = "folder"
    """Closed folder / file browser editor."""
    folder_open: Final[str] = "folder_open"
    """Open folder / file selected state."""

    # ── Console / terminal ────────────────────────────────────────────────────
    terminal: Final[str] = "terminal"
    """Console or script output panel."""

    # ── Library lifecycle ─────────────────────────────────────────────────────
    library_pause: Final[str] = "pause"
    """Suspend / pause a library."""
    library_resume: Final[str] = "play_arrow"
    """Resume / start a library (distinct from execution scope icon)."""
    library_install: Final[str] = "download"
    """Install / download a library."""
    library_find_replace: Final[str] = "find_replace"
    """Search and replace within a library."""

    # ── Lock / permission ─────────────────────────────────────────────────────
    locked: Final[str] = "lock"
    """Locked / read-only state."""
    unlocked: Final[str] = "lock_open"
    """Unlocked / editable state."""

    # ── UI chrome ────────────────────────────────────────────────────────────
    close: Final[str] = "close"
    """Dismiss / close a panel or popup."""
    dropdown: Final[str] = "arrow_drop_down"
    """Dropdown chevron / expand menu."""
    expand_full: Final[str] = "open_in_full"
    """Expand to full / modal view."""
    open_external: Final[str] = "open_in_new"
    """Open in external editor or browser."""

    # ── Empty states ─────────────────────────────────────────────────────────
    empty_no_results: Final[str] = "search_off"
    """Empty state: no search results found."""
    empty_binary: Final[str] = "block"
    """Empty state: binary or unreadable file."""
    empty_no_selection: Final[str] = "select_all"
    """Empty state: nothing selected."""

    # ── Data types (haybale) ──────────────────────────────────────────────────
    type_database: Final[str] = "database"
    """Database / tabular data type."""
    type_list: Final[str] = "list"
    """List / sequence data type."""

    # ── Actions ──────────────────────────────────────────────────────────────
    add: Final[str] = "add"
    """Add / create action."""
    delete: Final[str] = "delete"
    """Remove / destroy action."""
    copy: Final[str] = "content_copy"
    """Duplicate / copy to clipboard action."""
    paste: Final[str] = "content_paste"
    """Paste action."""
    refresh: Final[str] = "refresh"
    """Reload / revalidate action."""
    save: Final[str] = "save"
    """Persist to disk action."""
    edit: Final[str] = "edit"
    """Open for editing action."""
    reset: Final[str] = "restart_alt"
    """Reset to default / restart action."""

    # ── Status ───────────────────────────────────────────────────────────────
    ok: Final[str] = "task_alt"
    """Generic success / pass state."""
    error: Final[str] = "error"
    """Error state."""
    warning: Final[str] = "warning"
    """Warning state."""
