"""
haywire.ui.elements — Haywire Design System component wrappers.

Thin wrappers around NiceGUI / Quasar elements, pre-configured with the
Haywire visual language: correct CSS token usage, spacing, typography, and
interaction patterns.

Import as:

    from haywire.ui import elements as hui

    # or if you prefer the short alias:
    from haywire.ui.elements import panel_header, list_item, empty_state

Every function returns the outermost NiceGUI element so callers can still
chain .classes(), .style(), .props(), .on() for one-off overrides.  The goal
is to encode the 90% case — not to prevent customisation.

Design system reference:  docs/documentation/design/haywire-ui-design-guide.md
"""

from __future__ import annotations

import json as _json
from contextlib import contextmanager
from typing import Any, Callable, Optional, Sequence, TYPE_CHECKING

from nicegui import ui

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext

# ──────────────────────────────────────────────────────────────────────────────
# Colour & style constants (internal)
# ──────────────────────────────────────────────────────────────────────────────

_BORDER = "border-bottom: 1px solid var(--hw-border);"
_BORDER_RIGHT = "border-right: 1px solid var(--hw-border);"
_BORDER_LEFT = "border-left: 1px solid var(--hw-border);"
_BORDER_TOP = "border-top: 1px solid var(--hw-border);"
_BG_SURFACE = "background: var(--hw-bg-surface);"
_BG_PAGE = "background: var(--hw-bg-page);"
_BG_ELEVATED = "background: var(--hw-bg-elevated);"

_TRANSITION_BG = "transition: background-color 0.15s ease, color 0.15s ease;"

# Hover style for list items.  Uses bg-surface to stay theme-aware.
# Applied via a CSS class injected once, rather than Tailwind hover:bg-white/10.
_LIST_HOVER_CLASS = "hw-list-item-hover"

# ──────────────────────────────────────────────────────────────────────────────
# CSS injection (called once at app startup or first import)
# ──────────────────────────────────────────────────────────────────────────────

_CSS_INJECTED = False


def _ensure_css() -> None:
    """Inject hui-specific CSS rules once per page session."""
    global _CSS_INJECTED
    if _CSS_INJECTED:
        return
    _CSS_INJECTED = True
    ui.add_css(
        # Theme-aware hover for list items
        f" .{_LIST_HOVER_CLASS} {{"
        "   transition: background-color 0.15s ease;"
        " }"
        f" .{_LIST_HOVER_CLASS}:hover {{"
        "   background-color: var(--hw-bg-surface) !important;"
        " }"
        " .hw-list-item-active {"
        "   background-color: var(--hw-bg-active) !important;"
        " }"
        # Error and warning text via tokens
        " .hw-text-danger { color: var(--hw-danger) !important; }"
        " .hw-text-warning { color: var(--hw-warning) !important; }"
        " .hw-text-warning-dim { color: var(--hw-warning-dim) !important; }"
        " .hw-text-success { color: var(--hw-success) !important; }"
        " .hw-text-info { color: var(--hw-info) !important; }"
        " .hw-text-accent { color: var(--hw-accent) !important; }"
    )


# ──────────────────────────────────────────────────────────────────────────────
# 8.1  Panel Header
# ──────────────────────────────────────────────────────────────────────────────


@contextmanager
def panel_header(title: str, *, icon: str | None = None):
    """
    A slim bar at the top of a panel with title, optional icon, and space for
    action buttons.  Use as a context manager — place action buttons inside.

    Usage::

        with hui.panel_header("Files", icon="folder"):
            hui.icon_action("refresh", tooltip="Refresh", on_click=refresh)

    Yields the ui.row container so callers can further customise if needed.
    """
    _ensure_css()
    row = ui.row().classes("w-full items-center px-2 py-1.5 flex-shrink-0 gap-1").style(_BORDER)
    with row:
        if icon:
            ui.icon(icon, size="16px").classes("hw-text-dim")
        ui.label(title).classes("text-sm font-medium hw-text-body truncate flex-1")
        yield row


# ──────────────────────────────────────────────────────────────────────────────
# 8.2  Info Bar
# ──────────────────────────────────────────────────────────────────────────────


def info_bar(
    label: str,
    *,
    badge: str | None = None,
    badge_color: str = "blue-grey",
    suffix: str | None = None,
) -> ui.row:
    """
    A contextual metadata bar (file name + language badge + file size).

    Usage::

        hui.info_bar("main.py", badge="python", suffix="12,480 B")
    """
    _ensure_css()
    row = (
        ui.row()
        .classes("w-full items-center gap-2 px-3 py-1 flex-shrink-0")
        .style(f"{_BG_SURFACE} {_BORDER} min-height: 28px;")
    )
    with row:
        ui.label(label).classes("text-xs font-medium hw-text-body")
        if badge:
            ui.badge(badge).props(f"color={badge_color} rounded outline").classes("text-xs")
        if suffix:
            ui.label(suffix).classes("text-xs hw-text-dim ml-auto")
    return row


# ──────────────────────────────────────────────────────────────────────────────
# 8.3  Empty State
# ──────────────────────────────────────────────────────────────────────────────


def empty_state(
    message: str,
    *,
    icon: str = "folder_open",
    hint: str | None = None,
    icon_size: str = "40px",
) -> ui.column:
    """
    Centered placeholder for panels with no content.

    Usage::

        hui.empty_state("Select a file from the Files panel", icon="folder_open")
    """
    _ensure_css()
    col = ui.column().classes("w-full h-full items-center justify-center gap-3").style("padding: 72px 0;")
    with col:
        ui.icon(icon, size=icon_size).classes("hw-text-dim")
        ui.label(message).classes("text-sm hw-text-muted")
        if hint:
            ui.label(hint).classes("text-xs hw-text-dim")
    return col


# ──────────────────────────────────────────────────────────────────────────────
# 8.4  List Item
# ──────────────────────────────────────────────────────────────────────────────


def list_item(
    label: str,
    *,
    sublabel: str | None = None,
    dot_color: str | None = None,
    on_click: Callable | None = None,
) -> ui.row:
    """
    An interactive row for browsers and selection lists.

    Usage::

        hui.list_item("Visiongraph", sublabel="v0.0.1", dot_color="green",
                       on_click=lambda: select(lib))
    """
    _ensure_css()
    row = ui.row().classes(
        f"w-full px-2 py-1.5 cursor-pointer {_LIST_HOVER_CLASS} items-center gap-2 rounded"
    )
    if on_click:
        row.on("click", lambda _e=None, fn=on_click: fn())
    with row:
        if dot_color:
            ui.element("div").classes(f"w-2 h-2 rounded-full bg-{dot_color}-500 flex-shrink-0")
        with ui.column().classes("flex-1 gap-0 min-w-0"):
            ui.label(label).classes("text-sm font-medium truncate")
            if sublabel:
                ui.label(sublabel).classes("text-xs hw-text-dim")
    return row


# ──────────────────────────────────────────────────────────────────────────────
# 8.5  Section Label
# ──────────────────────────────────────────────────────────────────────────────


def section_label(text: str) -> ui.label:
    """
    An uppercase tracking label that separates groups within a list or panel.

    Usage::

        hui.section_label("REQUIRED")
    """
    return ui.label(text.upper()).classes("text-xs font-bold tracking-wider hw-text-dim px-2 pt-2 pb-1")


# ──────────────────────────────────────────────────────────────────────────────
# 8.6  Info Row
# ──────────────────────────────────────────────────────────────────────────────


def info_row(
    label: str,
    value: str,
    *,
    copy_value: str | None = None,
    label_width: str = "w-16",
) -> ui.row:
    """
    A key-value metadata row with optional copy-to-clipboard button.

    Usage::

        hui.info_row("Key", "visiongraph:node:WebcamFrame", copy_value=full_key)
    """
    _ensure_css()
    effective_copy = copy_value if copy_value is not None else value
    row = ui.row().classes("w-full items-center gap-1 py-0.5")
    with row:
        if copy_value is not None or True:  # always show copy for info rows
            _copy_button(effective_copy)
        ui.label(label).classes(f"text-xs hw-text-dim {label_width} flex-shrink-0")
        lbl = ui.label(value).classes("text-xs font-mono truncate flex-1 hw-text-body")
        # Add tooltip with full value if it's likely truncated
        if len(value) > 40:
            lbl.tooltip(effective_copy)
    return row


# ──────────────────────────────────────────────────────────────────────────────
# 8.7  Code Block
# ──────────────────────────────────────────────────────────────────────────────


def code_block(
    code: str,
    *,
    label: str | None = None,
    copyable: bool = True,
) -> ui.column:
    """
    A read-only code snippet with optional label and copy button.

    Usage::

        hui.code_block("from my_lib import MyNode", label="Import")
    """
    _ensure_css()
    col = ui.column().classes("w-full gap-0.5 py-1")
    with col:
        if label:
            ui.label(label).classes("text-xs hw-text-dim")
        with ui.row().classes("w-full items-center gap-1 overflow-hidden"):
            if copyable:
                _copy_button(code)
            with (
                ui.element("div")
                .classes("min-w-0 rounded px-2 py-1 overflow-hidden")
                .style(f"{_BG_SURFACE} border: 1px solid var(--hw-border);")
            ):
                ui.label(code).classes("text-xs font-mono hw-text-body")
    return col


# ──────────────────────────────────────────────────────────────────────────────
# 8.8  Icon Action
# ──────────────────────────────────────────────────────────────────────────────


def icon_action(
    icon: str,
    *,
    tooltip: str | None = None,
    on_click: Callable | None = None,
    size: str = "xs",
) -> ui.button:
    """
    A minimal icon-only button for inline actions (refresh, close, copy).

    Usage::

        hui.icon_action("refresh", tooltip="Refresh tree", on_click=refresh)
    """
    btn = ui.button(icon=icon).props(f"flat round dense size={size}")
    if tooltip:
        btn.tooltip(tooltip)
    if on_click:
        btn.on("click", lambda _e=None, fn=on_click: fn())
    return btn


# ──────────────────────────────────────────────────────────────────────────────
# 8.9  Toolbar Button
# ──────────────────────────────────────────────────────────────────────────────


def toolbar_button(
    icon: str,
    *,
    is_active: bool = False,
    tooltip: str | None = None,
    on_click: Callable | None = None,
) -> ui.button:
    """
    An icon button for the activity bar or context bar.

    Usage::

        hui.toolbar_button("folder", is_active=True, tooltip="Files", on_click=fn)
    """
    classes = "hw-shell-toolbar-btn w-10 h-10"
    if is_active:
        classes += " hw-shell-toolbar-btn-active"
    btn = ui.button(icon=icon).classes(classes).props("flat round")
    if tooltip:
        btn.tooltip(tooltip)
    if on_click:
        btn.on("click", lambda _e=None, fn=on_click: fn())
    return btn


# ──────────────────────────────────────────────────────────────────────────────
# 8.10  Scope Button
# ──────────────────────────────────────────────────────────────────────────────


def scope_button(
    icon: str,
    *,
    is_active: bool = False,
    available: bool = True,
    tooltip: str | None = None,
    on_click: Callable | None = None,
) -> ui.button:
    """
    A square button for the properties scope toolbar.

    Usage::

        hui.scope_button("settings", is_active=True, tooltip="Node Properties")
    """
    style = (
        "width: 36px; height: 36px; min-height: 36px; padding: 0;"
        "border-radius: 0; border: none; background: transparent;"
        "transition: background 0.15s;"
    )
    if is_active:
        style += "background: var(--hw-accent) !important;color: #ffffff !important;"
    if not available:
        style += "opacity: 0.3; pointer-events: none;"

    btn = ui.button(icon=icon).props("flat").style(style)
    if tooltip:
        btn.tooltip(tooltip)
    if on_click and available:
        btn.on("click", lambda _e=None, fn=on_click: fn())
    return btn


# ──────────────────────────────────────────────────────────────────────────────
# 8.11  Expansion Section
# ──────────────────────────────────────────────────────────────────────────────


@contextmanager
def expansion_section(
    label: str,
    *,
    icon: str | None = None,
    default_open: bool = True,
    context: Optional["SessionContext"] = None,
    panel_key: str | None = None,
):
    """
    A collapsible section for grouped content in property panels.

    If ``context`` and ``panel_key`` are provided, the expansion state is
    persisted in ``context.metadata`` across rebuilds.

    Usage::

        with hui.expansion_section("Node", icon="settings", context=ctx,
                                   panel_key="node:props"):
            # panel content
    """
    _ensure_css()

    # Resolve persisted state
    is_open = default_open
    exp_state: dict | None = None
    if context is not None and panel_key:
        exp_state = context.metadata.setdefault("_hui_expansion", {})
        is_open = exp_state.get(panel_key, default_open)

    exp = ui.expansion(label, icon=icon, value=is_open).classes("w-full").style(_BORDER)

    # Persist state changes
    if exp_state is not None and panel_key:
        exp.on(
            "update:modelValue",
            lambda e, k=panel_key, s=exp_state: s.update({k: e.args}),
        )

    with exp:
        yield exp


# ──────────────────────────────────────────────────────────────────────────────
# 8.12–8.13  Error / Warning / Status Labels
# ──────────────────────────────────────────────────────────────────────────────


def error_label(text: str) -> ui.label:
    """An error message label using ``--hw-danger``."""
    _ensure_css()
    return ui.label(text).classes("hw-text-danger text-sm p-4")


def warning_label(text: str) -> ui.label:
    """A warning message label using ``--hw-warning``."""
    _ensure_css()
    return ui.label(text).classes("hw-text-warning text-sm p-4")


def success_label(text: str) -> ui.label:
    """A success message label using ``--hw-success``."""
    _ensure_css()
    return ui.label(text).classes("hw-text-success text-sm p-4")


def info_label(text: str) -> ui.label:
    """An informational label using ``--hw-info``."""
    _ensure_css()
    return ui.label(text).classes("hw-text-info text-sm p-4")


# ──────────────────────────────────────────────────────────────────────────────
# 8.14  Tag / Badge
# ──────────────────────────────────────────────────────────────────────────────


def tag(text: str, *, color: str = "grey") -> ui.badge:
    """
    A small metadata tag / badge.

    Usage::

        hui.tag("vision")
        hui.tag("editable", color="green")
    """
    return ui.badge(text).props(f"outline color={color}").classes("text-xs")


# ──────────────────────────────────────────────────────────────────────────────
# 8.15  Input Field
# ──────────────────────────────────────────────────────────────────────────────


def input_field(
    *,
    label: str | None = None,
    placeholder: str | None = None,
    value: str = "",
    clearable: bool = False,
    on_change: Callable | None = None,
    **kwargs: Any,
) -> ui.input:
    """
    A standard text input, pre-configured for panel use.

    Usage::

        hui.input_field(placeholder="Search…", clearable=True,
                        on_change=lambda e: filter(e.value))
    """
    props = "dense outlined"
    if clearable:
        props += " clearable"

    inp = (
        ui.input(
            label=label,
            placeholder=placeholder,
            value=value,
            **kwargs,
        )
        .classes("w-full")
        .props(props)
    )

    if on_change:
        inp.on("update:model-value", on_change)

    return inp


def number_field(
    *,
    label: str | None = None,
    value: float = 0,
    **kwargs: Any,
) -> ui.number:
    """
    A standard number input, pre-configured for panel use.

    Usage::

        hui.number_field(label="posX", value=0)
    """
    return (
        ui.number(
            label=label,
            value=value,
            **kwargs,
        )
        .classes("w-full")
        .props("dense outlined")
    )


def select_field(
    *,
    options: list,
    value: Any = None,
    label: str | None = None,
    min_width: str = "160px",
    on_change: Callable | None = None,
    **kwargs: Any,
) -> ui.select:
    """
    A standard dropdown select, pre-configured for panel use.

    Usage::

        hui.select_field(options=["A", "B"], value="A", label="Choose")
    """
    sel = (
        ui.select(options=options, value=value, label=label, **kwargs)
        .props("dense outlined")
        .classes("text-sm")
        .style(f"min-width: {min_width};")
    )
    if on_change:
        sel.on_value_change(on_change)
    return sel


# ──────────────────────────────────────────────────────────────────────────────
# 8.16  Tabs
# ──────────────────────────────────────────────────────────────────────────────


def tabs(
    *tab_defs: tuple[str, str] | tuple[str, str, str],
    dense: bool = True,
) -> tuple[ui.tabs, list[ui.tab]]:
    """
    A tab bar, pre-configured with hw-tabs styling.

    Each ``tab_def`` is a tuple of ``(label, icon)`` or ``(name, label, icon)``.

    Returns ``(tabs_element, [tab_elements])`` so callers can build tab_panels.

    Usage::

        tabs_el, [t_graph, t_lib] = hui.tabs(
            ("Graph", "account_tree"),
            ("Library", "widgets"),
        )
        with ui.tab_panels(tabs_el, value=t_graph):
            ...
    """
    _ensure_css()
    props = "dense no-caps" if dense else "no-caps"
    tabs_el = ui.tabs().classes("w-full hw-tabs").props(props)
    tab_els = []
    with tabs_el:
        for td in tab_defs:
            if len(td) == 3:
                name, label, icon = td
                tab_els.append(ui.tab(name=name, label=label, icon=icon))
            else:
                label, icon = td
                tab_els.append(ui.tab(label, icon=icon))
    return tabs_el, tab_els


# ──────────────────────────────────────────────────────────────────────────────
# Additional helpers
# ──────────────────────────────────────────────────────────────────────────────


def separator() -> ui.separator:
    """A themed horizontal separator."""
    return ui.separator()


def section_divider(text: str | None = None):
    """
    A visual break between sections.  If text is given, renders a section_label.
    Otherwise renders a plain separator.
    """
    if text:
        section_label(text)
    else:
        ui.separator().classes("mt-3")


# ──────────────────────────────────────────────────────────────────────────────
# Category Group (settings expansion)
# ──────────────────────────────────────────────────────────────────────────────


@contextmanager
def category_group(label: str, *, default_open: bool = True):
    """
    A collapsible category header for settings field groups.

    Uses ``category == 'root'`` convention: if label is ``"root"`` (case-insensitive),
    renders a plain column without a header.

    Usage::

        with hui.category_group("Advanced"):
            # field rows
    """
    _ensure_css()
    if label.lower() == "root":
        with ui.column().classes("w-full gap-0") as col:
            yield col
        return

    display = label.replace("_", " ").replace(".", " / ").title()
    with (
        ui.expansion(display, value=default_open)
        .classes("w-full")
        .props(
            "dense dense-toggle"
            ' header-class="text-xs font-bold hw-text-muted uppercase tracking-wide'
            ' px-2 py-0 min-h-[24px]"'
        )
    ) as exp:
        yield exp


# ──────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────────────


def _copy_button(value: str) -> ui.button:
    """Small copy-to-clipboard button used internally by info_row and code_block."""
    return (
        ui.button(
            icon="content_copy",
            on_click=lambda _v=value: ui.run_javascript(f"navigator.clipboard.writeText({_json.dumps(_v)})"),
        )
        .props("flat round dense size=xs")
        .tooltip("Copy to clipboard")
    )
