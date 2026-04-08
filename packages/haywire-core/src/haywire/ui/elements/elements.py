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
from typing import Any, Callable, Optional, TYPE_CHECKING

from nicegui import ui

from haywire.ui.elements.icons import AppIcon

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

# Hover style for list items — CSS defined in shell.py _static_css.
_LIST_HOVER_CLASS = "hw-list-item-hover"


# ──────────────────────────────────────────────────────────────────────────────
# 8.1  Panel Header
# ──────────────────────────────────────────────────────────────────────────────


@contextmanager
def panel_header(title: str, *, icon: str | None = None):
    """
    A slim bar at the top of a panel with title, optional icon, and space for
    action buttons.  Use as a context manager — place action buttons inside.

    Anatomy::

        ┌─[icon 16px]─[title text-sm font-medium]────────────[action buttons]─┐
        │                         border-b                                      │

    Visual rules:
    - Padding: ``px-2 py-1.5``
    - Background: inherited from parent (transparent)
    - Bottom border: ``1px solid var(--hw-border)``
    - ``flex-shrink-0`` to prevent compression
    - Icon: 16px, ``hw-text-dim``
    - Title: ``text-sm font-medium hw-text-body truncate flex-1``
    - Actions: ``hui.icon_action()`` buttons floated right

    Usage::

        with hui.panel_header("Files", icon="folder") as header:
            hui.icon_action("refresh", tooltip="Refresh", on_click=self._refresh)

    Yields the ui.row container so callers can further customise if needed.
    """
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
    A contextual metadata bar (e.g. showing the open file name + language + size).

    Visual rules:
    - Height: ``min-height: 28px``
    - Padding: ``px-3 py-1``
    - Background: ``var(--hw-bg-surface)``
    - Bottom border: ``1px solid var(--hw-border)``
    - ``flex-shrink-0``
    - Label: ``text-xs font-medium hw-text-body``
    - Badge (optional): Quasar badge with ``color=blue-grey rounded outline text-xs``
    - Suffix (optional): ``text-xs hw-text-dim ml-auto``

    Usage::

        hui.info_bar("main.py", badge="python", suffix="12,480 B")
    """
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

    Visual rules:
    - Centred vertically and horizontally
    - Vertical padding: ``60–80px`` top (pushes content into upper-centre)
    - Icon: ``36–48px``, ``hw-text-dim``
    - Primary message: ``text-sm hw-text-muted``
    - Hint (optional): ``text-xs hw-text-dim``
    - Gap between icon and text: ``gap-3``

    Usage::

        hui.empty_state("Select a file from the Files panel", icon="folder_open")
        hui.empty_state("No results", icon="search", hint="Try a different query")
    """
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

    Visual rules:
    - Padding: ``px-2 py-1.5``
    - Full width, ``rounded`` (4px)
    - Hover: ``var(--hw-bg-hover)`` background — never ``bg-white/10``
    - Cursor: ``pointer``
    - Gap: ``gap-2``
    - Status dot (optional): ``w-2 h-2 rounded-full``, Quasar named colour
    - Label: ``text-sm font-medium truncate``
    - Sublabel: ``text-xs hw-text-dim``
    - Parent text column: ``flex-1 gap-0 min-w-0``

    Usage::

        hui.list_item("Visiongraph", sublabel="v0.0.1", dot_color="green",
                       on_click=lambda: select(lib))
    """
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


def label(text: str) -> ui.label:
    """
    A body-tier text label.

    Visual rules:
    - Text: ``text-sm hw-text-body``

    Usage::

        hui.label("No settings available.")
    """
    return ui.label(text).classes("text-sm hw-text-body truncate")


def section_label(text: str) -> ui.label:
    """
    An uppercase tracking label that separates groups within a list or panel.

    Visual rules:
    - Text: ``text-xs font-bold tracking-wider uppercase hw-text-dim``
    - Padding: ``px-2 pt-2 pb-1``
    - These labels are structural markers, not content — they should be the
      dimmest text in the panel.

    Usage::

        hui.section_label("REQUIRED")
    """
    return ui.label(text.upper()).classes(
        "text-xs font-bold tracking-wider hw-text-dim px-2 pt-2 pb-1 truncate"
    )


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

    Visual rules:
    - Row: ``w-full items-center gap-1 py-0.5``
    - Copy button (if ``copy_value`` provided): ``hui.icon_action("content_copy")``
    - Label: ``text-xs hw-text-dim``, fixed width ``w-16 flex-shrink-0``
    - Value: ``text-xs font-mono truncate flex-1 hw-text-body``
    - Long values (>40 chars) get a full-value tooltip automatically

    Tip: for very long values, pass the short display string as ``value`` and
    the full string as ``copy_value``::

        short = (full_key[:48] + "…") if len(full_key) > 50 else full_key
        hui.info_row("Key", short, copy_value=full_key)

    Usage::

        hui.info_row("Key", "visiongraph:node:WebcamFrame", copy_value=full_key)
    """
    effective_copy = copy_value if copy_value is not None else value
    row = ui.row().classes("w-full items-center gap-1 py-0.5 min-w-0")
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
# 8.7  Code Snippet
# ──────────────────────────────────────────────────────────────────────────────


def code_snippet(
    code: str,
    *,
    label: str | None = None,
    copyable: bool = True,
) -> ui.column:
    """
    A read-only code snippet with optional label and copy button.

    Visual rules:
    - Outer column: ``w-full gap-0.5 py-1``
    - Label (optional): ``text-xs hw-text-dim``
    - Code container: ``var(--hw-bg-surface)`` background, ``rounded`` (4px),
      ``px-2 py-1``, ``1px solid var(--hw-border)``
    - Code text: ``text-xs font-mono hw-text-body``
    - Copy button inline (``copyable=True`` by default)

    Usage::

        hui.code_block("from my_lib import MyNode", label="Import")
    """
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
# 8.8a  Button (labelled action)
# ──────────────────────────────────────────────────────────────────────────────


def button(
    label: str,
    *,
    icon: str | None = None,
    tooltip: str | None = None,
    on_click: Callable | None = None,
    disabled: bool = False,
) -> ui.button:
    """
    A flat labelled action button for use inside panels.

    Distinct from ``hui.icon_action`` (icon-only) and ``hui.dialog_actions``
    (confirm/cancel pair). Use this when you need a visible text label,
    optionally with a leading icon.

    Visual rules:
    - Props: ``flat dense``
    - Classes: ``text-sm``
    - Colour: inherited — never use Quasar ``color=`` prop
    - Disabled: ``opacity: 0.5; pointer-events: none``
    - Transition: ``color 0.15s ease``

    Usage::

        hui.button("Delete Node", icon="delete", on_click=self._delete)
        hui.button("Refresh", icon="refresh", on_click=self._refresh)
    """
    btn = ui.button(label, icon=icon).props("flat dense align=left no-wrap").classes("text-sm w-full")
    if disabled:
        btn.style("opacity: 0.5; pointer-events: none;")
    if tooltip:
        btn.tooltip(tooltip)
    if on_click and not disabled:
        btn.on("click", lambda fn=on_click: fn())
    return btn


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

    Visual rules:
    - Props: ``flat round dense size={size}``
    - Colour: inherited (theme-aware); no Quasar ``color=`` prop
    - Disabled: use ``opacity: 0.4; pointer-events: none`` — never a grey fill
    - Tooltip applied if provided

    Standard icon vocabulary: ``refresh``, ``close``, ``content_copy``,
    ``add``, ``delete``, ``edit``, ``expand_more``, ``expand_less``.

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

    Visual rules:
    - Size: ``w-10 h-10`` (40×40px)
    - Border-radius: ``10px`` (``lg`` tier) — do not flatten to 0 or round to full
    - Classes: ``hw-shell-toolbar-btn``, plus ``hw-shell-toolbar-btn-active`` when active
    - Props: ``flat round``
    - States: rest → muted icon, hover → elevated bg + body colour,
      active → elevated bg + accent colour + inset ring
    - Transition: ``background-color 0.15s ease, color 0.15s ease``

    Usage::

        hui.toolbar_button("folder", is_active=True, tooltip="Files", on_click=switch)
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

    Visual rules:
    - Size: ``36×36px``
    - Border-radius: ``0`` — tiles vertically; any radius creates visual gaps
    - Active: ``var(--hw-accent)`` background, ``#ffffff`` text
    - Unavailable (``available=False``): ``opacity: 0.3; pointer-events: none``
    - Transition: ``background 0.15s``

    Usage::

        hui.scope_button("settings", is_active=True, tooltip="Node Properties")
        hui.scope_button("tune", available=False, tooltip="Not available")
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

    Visual rules:
    - Bottom border: ``1px solid var(--hw-border)``
    - Header label colour: ``--hw-text-expansion`` (special-purpose token, set per theme)
    - Header label size/weight: Quasar's default — ``text-sm font-medium``

    Rule: Do not use ``ui.expansion()`` directly in property panels. Header
    styling is only guaranteed correct via this wrapper. For settings category
    groups use ``hui.category_group()`` instead.

    Usage::

        with hui.expansion_section("Node", icon="settings", context=ctx,
                                   panel_key="node:props"):
            # panel content
    """

    # Resolve persisted state
    is_open = default_open
    exp_state: dict | None = None
    if context is not None and panel_key:
        exp_state = context.metadata.setdefault("_hui_expansion", {})
        is_open = exp_state.get(panel_key, default_open)

    exp = (
        ui.expansion(label, icon=icon, value=is_open)
        .classes("w-full")
        .style(_BORDER)
        .props('header-class="truncate"')
    )

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
    """
    An error message label using ``--hw-danger``.

    Visual rules: ``text-sm p-4``, ``color: var(--hw-danger)``.
    Never use ``text-red-400`` — it is theme-unaware.
    """
    return ui.label(text).classes("hw-text-danger text-sm p-4")


def warning_label(text: str) -> ui.label:
    """
    A warning message label using ``--hw-warning``.

    Visual rules: ``text-sm p-4``, ``color: var(--hw-warning)``.
    Never use ``text-yellow-400`` — it is theme-unaware.
    """
    return ui.label(text).classes("hw-text-warning text-sm p-4 truncate")


def success_label(text: str) -> ui.label:
    """
    A success message label using ``--hw-success``.

    Visual rules: ``text-sm p-4``, ``color: var(--hw-success)``.
    """
    return ui.label(text).classes("hw-text-success text-sm p-4 truncate")


def info_label(text: str) -> ui.label:
    """
    An informational label using ``--hw-info``.

    Visual rules: ``text-sm p-4``, ``color: var(--hw-info)``.
    """
    return ui.label(text).classes("hw-text-info text-sm p-4 truncate")


# ──────────────────────────────────────────────────────────────────────────────
# 8.14  Tag / Badge
# ──────────────────────────────────────────────────────────────────────────────


def tag(text: str, *, color: str = "grey") -> ui.badge:
    """
    A small metadata tag / badge.

    Visual rules:
    - Quasar badge with ``outline`` prop and ``.text-xs``
    - Named colour via Quasar ``color=`` prop — acceptable exception to the
      no-hardcoded rule because Quasar semantic names map to theme colours

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
    autofocus: bool = False,
    on_change: Callable | None = None,
    **kwargs: Any,
) -> ui.input:
    """
    A standard text input, pre-configured for panel use.

    Visual rules:
    - Props: ``dense`` (standard variant — no ``outlined`` or ``filled``)
    - Classes: ``w-full``
    - Background: ``var(--hw-bg-input)`` (automatic via global CSS)
    - Border: ``var(--hw-border)`` at rest, ``var(--hw-border-strong)`` on hover/focus
    - Focus ring: ``2px solid var(--hw-accent)`` via ``:focus-visible`` (keyboard only)
    - Disabled: pass Quasar ``:disable="True"`` — renders ``opacity: 0.5`` automatically
    - Validation: pass Quasar ``:rules=`` and ``lazy-rules="ondemand"`` — error text
      appears below using ``var(--hw-danger)``; do not use ``hui.error_label()`` inline
    - ``autofocus=True``: focuses the field after a short delay, required for dynamically
      shown containers (e.g. popups) where the HTML autofocus attribute does not fire

    Usage::

        hui.input_field(placeholder="Search…", clearable=True,
                        on_change=lambda e: filter(e.value))
        hui.input_field(label="Port", rules=[lambda v: v.isdigit() or "Must be a number"])
    """
    props = "dense"
    if clearable:
        props += " clearable"

    inp = (
        ui.input(
            label=label,
            placeholder=placeholder,
            value=value,
            on_change=on_change,
            **kwargs,
        )
        .classes("w-full")
        .props(props)
    )

    if autofocus:
        ui.timer(
            0.1, lambda: ui.run_javascript(f'document.getElementById("c{inp.id}")?.focus();'), once=True
        )

    return inp


def number_field(
    *,
    label: str | None = None,
    value: float = 0,
    **kwargs: Any,
) -> ui.number:
    """
    A standard number input, pre-configured for panel use.

    Visual rules: same as ``hui.input_field`` — ``dense`` (standard variant), ``w-full``.

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
        .props("dense")
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

    Visual rules:
    - Props: ``dense`` (standard variant — no ``outlined`` or ``filled``)
    - Classes: ``text-sm``
    - ``min-width: 160px`` by default (override via ``min_width=``)

    Usage::

        hui.select_field(options=["A", "B"], value="A", label="Mode")
    """
    sel = (
        ui.select(options=options, value=value, label=label, **kwargs)
        .props("dense")
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
    A tab bar, pre-configured with ``hw-tabs`` styling.

    Each ``tab_def`` is a tuple of ``(label, icon)`` or ``(name, label, icon)``.

    Returns ``(tabs_element, [tab_elements])`` so callers can build tab_panels.

    Visual rules:
    - Classes: ``w-full hw-tabs``
    - Props: ``dense no-caps``
    - Tab label font: ``text-xs``
    - Active indicator: ``2px solid var(--hw-accent)`` (bottom bar)
    - Active tab label: ``--hw-text-body``
    - Inactive tab label: ``--hw-text-muted``
    - Tab bar bottom border: ``1px solid var(--hw-border)``
    - Tab hover: ``--hw-bg-hover`` background
    - Overflow: tabs scroll horizontally (QTabs default) — do not truncate or wrap

    Usage::

        tabs_el, [t_graph, t_lib] = hui.tabs(
            ("Graph", "account_tree"),
            ("Library", "widgets"),
        )
        with ui.tab_panels(tabs_el, value=t_graph):
            ...
    """
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
    """
    A plain themed horizontal rule.

    Use when you need a divider without a label and without the top margin
    added by ``hui.section_divider()``. Prefer ``hui.section_divider()`` in
    most contexts; use this only where the extra margin would break a tight layout.
    """
    return ui.separator()


def section_divider(text: str | None = None):
    """
    A visual break between sections.

    If ``text`` is given, renders a ``hui.section_label`` (uppercase tracking label).
    Otherwise renders a plain ``ui.separator`` with ``mt-3`` top margin.

    Usage::

        hui.section_divider("ADVANCED")  # labelled divider
        hui.section_divider()            # plain separator
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
    A collapsible category header for settings field groups inside a
    ``compact-fields`` container.

    This is distinct from ``hui.expansion_section`` (which is for property
    panel scopes with state persistence). Use this for settings field grouping
    only — not for general panel sections.

    If label is ``"root"`` (case-insensitive), renders a plain column without a
    header (the root category convention).

    Visual rules:
    - Props: ``dense dense-toggle``
    - Header class: ``text-xs font-bold hw-text-muted uppercase tracking-wide px-2 py-0 min-h-[24px]``
    - Default open: ``True``
    - No state persistence (categories always reset to open on rebuild)

    Usage::

        with hui.category_group("Advanced"):
            # field rows
        with hui.category_group("root"):
            # rendered without a header
    """
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
            ' px-2 py-0 min-h-[24px] truncate"'
        )
    ) as exp:
        yield exp


# ──────────────────────────────────────────────────────────────────────────────
# 8.23  Dialog Chrome
# ──────────────────────────────────────────────────────────────────────────────


@contextmanager
def dialog_card(width: str | None = None):
    """
    A themed modal card for use inside ``ui.dialog()``.

    Applies the correct dialog chrome: elevated background, strong border,
    md border-radius, and popup shadow — all via ``--hw-*`` tokens so the card
    is theme-aware.

    Use as the second context manager in the NiceGUI dialog idiom::

        with ui.dialog() as dlg, hui.dialog_card("w-[480px]"):
            # content here

    Args:
        width: Optional Tailwind width class (e.g. ``"w-[480px]"``).
               If omitted the card is sized by its content.

    Visual rules (§8.23):
    - Background: ``var(--hw-bg-elevated)``
    - Border: ``1px solid var(--hw-border-strong)``
    - Border-radius: 8px (``md`` tier)
    - Shadow: ``var(--hw-popup-shadow)``

    The card carries the ``hw-panel`` class, so all ``.hw-text-*`` utility
    classes and Quasar field colour overrides defined in the shell CSS apply
    inside it exactly as they do in regular panels.
    """
    classes = f"hw-panel {width}" if width else "hw-panel"
    with (
        ui.card()
        .classes(classes)
        .style(
            "background: var(--hw-bg-elevated);"
            " border: 1px solid var(--hw-border-strong);"
            " border-radius: 8px;"
            " box-shadow: var(--hw-popup-shadow);"
        ) as card
    ):
        yield card


def dialog_actions(
    on_confirm: Callable,
    on_cancel: Callable,
    *,
    confirm_label: str = "OK",
    cancel_label: str = "Cancel",
) -> None:
    """
    A standardised action row for modal dialogs.

    Renders a right-aligned row with a Cancel button and a confirm button.
    The confirm button is styled with ``var(--hw-positive)`` for theme-aware
    positive emphasis. Both buttons are ``flat dense``.

    Call this inside a ``hui.dialog_card()`` context::

        with ui.dialog() as dlg, hui.dialog_card("w-[480px]"):
            # ... content ...
            hui.dialog_actions(on_confirm=dlg.close, on_cancel=dlg.close)

    Args:
        on_confirm: Callback for the confirm (OK) button.
        on_cancel:  Callback for the cancel button.
        confirm_label: Label for the confirm button (default ``"OK"``).
        cancel_label:  Label for the cancel button (default ``"Cancel"``).
    """
    with ui.row().classes("w-full justify-end gap-2 mt-2"):
        ui.button(cancel_label, on_click=on_cancel).props("flat dense")
        ui.button(confirm_label, on_click=on_confirm).props("flat dense").style("color: var(--hw-positive);")


# ──────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────────────


def _copy_button(value: str) -> ui.button:
    """Small copy-to-clipboard button used internally by info_row and code_block."""
    return (
        ui.button(
            icon=AppIcon.copy,
            on_click=lambda _v=value: ui.run_javascript(f"navigator.clipboard.writeText({_json.dumps(_v)})"),
        )
        .props("flat round dense size=xs")
        .tooltip("Copy to clipboard")
    )
