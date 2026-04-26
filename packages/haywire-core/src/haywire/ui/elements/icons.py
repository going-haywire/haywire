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

    # ── Graph ────────────────────────────────────────────────────────────────
    haystack: Final[str] = "storage"
    """Multi-graph file browser."""

    # ── Library  ───────────────────────────────────────────────────────────
    library: Final[str] = "extension"
    """Library icon."""
    registry_key: Final[str] = "key"
    """Registry key or identifier."""
    module: Final[str] = "webhook"
    """Module reference."""

    # ── Console / terminal ────────────────────────────────────────────────────
    terminal: Final[str] = "terminal"
    """Console or script output panel."""

    # -- Core Classes ───────────────────────────────────────────────────────────────

    graph: Final[str] = "polyline"
    """Graph main icon."""
    node: Final[str] = "account_tree"
    """Node main icon."""
    edge: Final[str] = "cable"
    """Edge main icon."""
    widget: Final[str] = "widgets"
    """Widget main icon."""
    skin: Final[str] = "preview"
    """Skins main icon."""
    adapter: Final[str] = "electrical_services"
    """Adapters main icon."""
    type: Final[str] = "category"
    """Types main icon."""
    panel: Final[str] = "dashboard_customize"
    """Panels main icon."""
    editor: Final[str] = "space_dashboard"
    """Editors main icon."""
    theme: Final[str] = "style"
    """Theme and appearance main icon."""

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
    node_settings: Final[str] = "tune"
    """Node settings scope (only available when node has setting bags)."""

    # ── Library / editor tabs ────────────────────────────────────────────────
    library_component: Final[str] = "description"
    """Component detail editor."""
    library_docs: Final[str] = "menu_book"
    """Component documentation tab."""
    library_source: Final[str] = "code"
    """Component source tab."""
    library_view: Final[str] = "visibility"
    """Component preview tab."""
    node_source: Final[str] = "code"
    """Node source editor (source of the currently selected graph node)."""

    # ── Edge panels ───────────────────────────────────────────────────────────
    edge_statistics: Final[str] = "linear_scale"
    """Edge execution statistics and connection path panels."""

    # ── General actions and states ─────────────────────────────────────────────────
    debug: Final[str] = "bug_report"
    """Debug / dev tools scope."""

    # ── File system ───────────────────────────────────────────────────────────
    folder: Final[str] = "folder"
    """Closed folder / file browser editor."""
    folder_open: Final[str] = "folder_open"
    """Open folder / file selected state."""

    # ── UI chrome ────────────────────────────────────────────────────────────
    pause: Final[str] = "pause"
    """Pause icon."""
    resume: Final[str] = "play_arrow"
    """Resume icon."""
    download: Final[str] = "download"
    """Download icon."""
    find_replace: Final[str] = "find_replace"
    """Find and replace icon."""
    locked: Final[str] = "lock"
    """Locked / read-only state."""
    unlocked: Final[str] = "lock_open"
    """Unlocked / editable state."""
    close: Final[str] = "close"
    """Dismiss / close a panel or popup."""
    dropdown: Final[str] = "arrow_drop_down"
    """Dropdown chevron / expand menu."""
    expand_full: Final[str] = "open_in_full"
    """Expand to full / modal view."""
    open_external: Final[str] = "open_in_new"
    """Open in external editor or browser."""

    # ── Data types (haybale) ──────────────────────────────────────────────────
    database: Final[str] = "database"
    """Database / tabular data type."""
    list: Final[str] = "list"
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
    suggestion: Final[str] = "lightbulb"
    """Suggestion or hint."""
    traceback: Final[str] = "search"
    """Traceback / stack trace inspection."""
    arrow_forward: Final[str] = "arrow_right"
    """Forward navigation indicator (traceback frames, breadcrumbs)."""
    operation: Final[str] = "build"
    """Operation or build step."""
    message: Final[str] = "message"
    """Generic message or log entry."""
    severity: Final[str] = "shield"
    """Severity level indicator."""
    context: Final[str] = "code"
    """Code or context type indicator."""
    label: Final[str] = "label"
    """Label or tag identifier."""
    line_number: Final[str] = "tag"
    """Line number or numeric reference."""
    palette: Final[str] = "palette"
    """Color indicator."""

    # ── Empty states ─────────────────────────────────────────────────────────
    empty_no_results: Final[str] = "search_off"
    """Empty state: no search results found."""
    empty_binary: Final[str] = "block"
    """Empty state: binary or unreadable file."""
    empty_no_selection: Final[str] = "select_all"
    """Empty state: nothing selected."""
