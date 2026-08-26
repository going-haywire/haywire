# packages/haywire-core/src/haywire/ui/app/shell.py
"""
AppShell renders the workspace layout for a single browser session.

It is a layout container that hosts four :class:`Slot` subclass instances
(ACTION/CONTEXT as :class:`IconSlot`, EDIT/INFO as :class:`TabSlot`). The shell
orchestrates editor reveal/open operations across them, handles workspace
layout DOM construction (TopBar, StatusBar, resizable dividers), and delegates
context-change events to each slot for their independent poll/draw cycles.

Each slot owns its own editor wrappers, area container, and active-wrapper
lifecycle. The shell's role is layout chrome and orchestration only; business
logic lives inside the slots themselves.

The AppShell is created once per browser session from within a NiceGUI page
handler. The haywire-studio package is responsible for constructing the
Session and calling AppShell.render().
"""

import logging
from pathlib import Path
from typing import Callable, Literal, TYPE_CHECKING
from nicegui import ui

from haywire.ui import elements as hui
from haywire.core.signals import (
    AgentConnected,
    AgentDisconnected,
    BroadcastClose,
    Close,
    FarmhandActivity,
    PresenceChanged,
    Reveal,
)
from haywire.ui.app.slot import Slot
from haywire.ui.editor.identity import SlotName

logger = logging.getLogger(__name__)


def _pygments_doc_css() -> str:
    """Pygments token CSS for code blocks inside the .hw-cm-doc panel.

    markdown2's fenced-code-blocks extra emits `.codehilite` wrappers with
    pygments token classes. These tooltips are raw-DOM (not ui.markdown), so
    NiceGUI's per-element codehilite CSS never applies — generate it here.
    """
    try:
        from pygments.formatters import HtmlFormatter

        return HtmlFormatter(nobackground=True).get_style_defs(".hw-cm-doc .codehilite")
    except Exception:  # pragma: no cover - pygments always present via markdown2
        return ""


if TYPE_CHECKING:
    from haywire.ui.editor.registry import EditorTypeRegistry
    from haywire.core.session.session import Session
    from haywire.core.access import AccessTier


def identity_text(principal: "str | None", tier: "AccessTier") -> str:
    """StatusBar label — ``alice · admin``, or empty when authentication is off.

    This label is what makes the vanish-on-denial behaviour humane rather than
    mysterious: a principal who cannot see an editor has one place that explains
    why, instead of a padlock on every control (ADR 0027).
    """
    return f"{principal} · {tier.value}" if principal else ""


def last_seen_text(seconds: float) -> str:
    """Relative recency for an agent chip.

    Deliberately relative rather than a green dot: MCP's ``ping`` is optional,
    so a binary indicator can be wrong while "last seen 40s ago" cannot.
    """
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{int(seconds // 60)}m ago"
    return f"{int(seconds // 3600)}h ago"


"""Static, theme-independent CSS for every haywire surface.

Module-level so surfaces that are NOT the shell can reuse it verbatim —
the panel harness in barn/haybale-share is one. Duplicating it there
meant the harness rendered Quasar dropdowns with browser defaults
(white menu, white text) and unstyled fields, i.e. it misreported the
very thing it exists to show.
"""
STATIC_CSS = (
    # Z-index layers for the Quasar-overlay tier. NOT theme tokens:
    # stacking order is structural, not a user-swappable colour.
    # Quasar's own dialogs and QMenus both default to 6000, which is
    # why the haywire Popup card sits above them at 7001 and menus
    # opened from inside a popup need 7100 to clear it.
    " :root { --hw-z-popup: 7001; --hw-z-popup-menu: 7100; }"
    # Page background
    " body, .q-page, .q-tab-panels { background: var(--hw-bg-page) !important; }"
    # Layout
    " .nicegui-content { padding: 0 !important; max-width: none !important;"
    " height: 100vh !important; overflow: hidden !important; }"
    " .q-tab-panels > .q-panel-parent > .q-panel.scroll"
    " { overflow: hidden !important; }"
    # Tab-style slot bar (main and bottom slots)
    " .hw-slot-bar-tabs .q-tab { color: var(--hw-text-muted) !important; }"
    " .hw-slot-bar-tabs .q-tab--active { color: var(--hw-text-body) !important; }"
    " .hw-slot-bar-tabs .q-tab__indicator { background: var(--hw-accent) !important; }"
    " .hw-slot-bar-tabs .q-tab__label { font-size: 12px; }"
    # Generic toolbar buttons (hui.toolbar_button helper).
    " .hw-shell-toolbar-btn {"
    "   color: var(--hw-text-muted) !important;"
    "   border-radius: 10px;"
    "   transition: background-color 0.15s ease, color 0.15s ease, box-shadow 0.15s ease;"
    " }"
    " .hw-shell-toolbar-btn:hover {"
    "   background: var(--hw-bg-elevated) !important;"
    "   color: var(--hw-text-body) !important;"
    " }"
    " .hw-shell-toolbar-btn .q-icon { color: inherit !important; }"
    " .hw-shell-toolbar-btn-active {"
    "   background: var(--hw-bg-elevated) !important;"
    "   color: var(--hw-accent) !important;"
    "   box-shadow: inset 0 0 0 1px var(--hw-accent);"
    " }"
    # Vertical icon-bar tabs (IconSlot) — Quasar q-tabs in vertical
    # orientation. Uses the same muted/body/accent palette as the
    # horizontal tab bar (.hw-slot-bar-tabs above). The indicator
    # side (left vs right edge of the active tab) is controlled by
    # the q-tabs `indicator-color` and `align` props plus a class
    # variant on the bar itself.
    # Force vertical layout: NiceGUI's q-tabs in vertical mode
    # leaves q-tabs__content with `row no-wrap` flex classes, so
    # the tabs render horizontally clipped inside a narrow bar.
    # We override to a column and center each tab horizontally.
    " .hw-icon-bar-tabs.q-tabs--vertical {"
    "   flex-direction: column !important;"
    "   align-items: stretch !important;"
    " }"
    " .hw-icon-bar-tabs.q-tabs--vertical .q-tabs__content {"
    "   flex-direction: column !important;"
    "   align-items: stretch !important;"
    "   width: 100%;"
    " }"
    " .hw-icon-bar-tabs .q-tab { color: var(--hw-text-muted) !important;"
    "   min-height: 40px; padding: 0;"
    "   width: 100%;"
    " }"
    " .hw-icon-bar-tabs .q-tab__content {"
    "   justify-content: center !important;"
    "   width: 100%;"
    " }"
    # An empty q-tab__label still occupies layout space inside the
    # `row no-wrap` content, shifting the icon left of true centre.
    # Remove it from the flow when we render icon-only tabs.
    " .hw-icon-bar-tabs .q-tab__label { display: none !important; }"
    " .hw-icon-bar-tabs .q-tab:hover { color: var(--hw-text-body) !important; }"
    " .hw-icon-bar-tabs .q-tab--active { color: var(--hw-text-body) !important; }"
    " .hw-icon-bar-tabs .q-tab__indicator { background: var(--hw-accent) !important; }"
    # Size both Quasar's own tab icon (the `icon=` arg path) and a
    # child `.q-icon` an editor draws via `draw_tab` — the latter
    # lacks the `q-tab__icon` class, so without this it would fall
    # back to the default (smaller) ui.icon size.
    " .hw-icon-bar-tabs .q-tab__icon,"
    " .hw-icon-bar-tabs .q-tab__content .q-icon { font-size: 22px; }"
    # All editor area containers and their child text.
    # .hw-cm-isolate wrappers (CodeMirror editors) are excluded so that
    # the CodeMirror theme controls all token colours uncontested.
    " .hw-panel, .hw-panel *:not(.hw-cm-isolate):not(.hw-cm-isolate *)"
    " { color: var(--hw-text-body); }"
    # Make CodeMirror fill its flex container so height is flexible.
    " .hw-cm-isolate .cm-editor { height: 100%; }"
    # Expansion items inside area editors (PropertiesEditor, etc.)
    " .hw-panel .q-expansion-item {"
    "   background: var(--hw-panel-header-0-bg, transparent);"
    " }"
    " .hw-panel .q-expansion-item__header { color: var(--hw-text-expansion) !important; }"
    " .compact-fields .q-expansion-item {"
    "   background: var(--hw-panel-header-1-bg, transparent);"
    " }"
    " .hw-panel .q-expansion-item__content {"
    "   padding: 0.25rem 0.5rem !important;"
    "   gap: 0 !important;"
    " }"
    # NiceGUI 3.x wraps expansion content in .nicegui-expansion-content which
    # sits INSIDE q-expansion-item__content and independently gets padding:1rem
    # from nicegui.css. Override it across all hw-panel expansions so the inner
    # wrapper doesn't add its own indent on top of the Quasar container's padding.
    " .hw-panel .nicegui-expansion-content {"
    "   padding: 0 !important;"
    "   gap: 0 !important;"
    " }"
    # In compact-fields contexts, also zero the Quasar container so indentation
    # does not compound across nested expansion levels.
    " .compact-fields .q-expansion-item__content {"
    "   padding: 0 !important;"
    "   gap: 0 !important;"
    " }"
    " .hw-panel .q-expansion-item__content::before,"
    " .hw-panel .q-expansion-item__content::after {"
    "   display: none !important;"
    " }"
    # hw-use-props-color opts a q-icon out of the dim rule so Quasar color= prop works freely
    " .hw-panel .q-icon:not(.connection-pin):not(.hw-use-props-color)"
    " { color: var(--hw-text-dim) !important; }"
    # Semantic text helpers — use these instead of fixed Tailwind grays in UI chrome
    " .hw-text-body  { color: var(--hw-text-body) !important; }"
    " .hw-text-muted { color: var(--hw-text-muted) !important; }"
    " .hw-text-dim   { color: var(--hw-text-dim) !important; }"
    # Drag-resize handles between areas
    " .hw-area-divider { background: transparent; transition: background-color 0.15s; }"
    " .hw-area-divider:hover { background-color: var(--hw-accent) !important; }"
    " .hw-area-vdivider { background: transparent; transition: background-color 0.15s; }"
    " .hw-area-vdivider:hover { background-color: var(--hw-accent) !important; }"
    # Outlined select borders — Quasar uses a pseudo-element, not color inheritance
    " .hw-panel .q-field--outlined .q-field__control:before"
    " { border-color: var(--hw-border) !important; }"
    " .hw-panel .q-field--outlined:hover .q-field__control:before"
    " { border-color: var(--hw-border-strong) !important; }"
    " .hw-panel .q-field__control { background: var(--hw-bg-input) !important; }"
    # Selection chips (use-chips selects) — Quasar's default grey chip is
    # too low-contrast on the elevated field background. Paint the whole
    # chip with the accent colour and on-accent text so it reads as a
    # clear 'selected' token. Target the chip, its content wrapper, and
    # the remove icon; Quasar colours each separately.
    " .hw-panel .q-field .q-chip,"
    " .hw-panel .q-field .q-chip .q-chip__content {"
    "   background: var(--hw-accent) !important;"
    "   color: var(--hw-text-on-accent) !important;"
    " }"
    " .hw-panel .q-field .q-chip .q-chip__icon,"
    " .hw-panel .q-field .q-chip .q-icon {"
    "   color: var(--hw-text-on-accent) !important;"
    " }"
    # Field label — dim it so an empty field's label doesn't read like an
    # entered value (both inherit body colour otherwise). Brighten to the
    # accent when the field is focused, matching the focus underline.
    " .hw-panel .q-field__label { color: var(--hw-text-muted) !important; }"
    " .hw-panel .q-field--highlighted .q-field__label"
    " { color: var(--hw-accent) !important; }"
    # Standard (non-outlined) field underline — override currentColor to use border token
    " .hw-panel .q-field--standard .q-field__control:before"
    " { border-bottom-color: var(--hw-border) !important; }"
    " .hw-panel .q-field--standard:hover .q-field__control:before"
    " { border-bottom-color: var(--hw-border-strong) !important; }"
    # Focus: accent underline animation + elevated background (matches NumberDrag)
    " .hw-panel .q-field--standard.q-field--highlighted .q-field__control:after"
    " { background: var(--hw-accent) !important; }"
    " .hw-panel .q-field--standard.q-field--highlighted .q-field__control"
    " { background: var(--hw-bg-elevated) !important; }"
    # Dropdown menus — portal outside their parent, so must be targeted globally
    " .q-menu { background: var(--hw-bg-elevated) !important;"
    " border: 1px solid var(--hw-border-strong) !important; }"
    " .q-menu .q-item { color: var(--hw-text-body) !important; }"
    " .q-menu .q-item--active { color: var(--hw-accent) !important; }"
    " .q-menu .q-item:hover { background: var(--hw-bg-surface) !important; }"
    # ── Menu rows: the ONE place a menu command's text style and colour live ──
    # `hui.menu_row` carries `.hw-menu-row`, and `hui.submenu_row` IS one, so a
    # command and the submenu row beside it cannot drift. Every value reads a
    # `--hw-menu-row-*` token with a semantic fallback, so a WorkbenchTheme
    # restyles every menu in the app without touching element code.
    #
    # Keyed on the row's own class, never on an ancestor: a flyout QMenu portals
    # to <body>, so a `.hw-panel`-scoped rule (the q-icon dim rule above) styles
    # a row inside a popup and misses the identical row inside a flyout — which
    # is how one menu ended up with three different colours.
    " .hw-menu-row {"
    "   padding: 0.25rem 0.5rem;"
    "   border-radius: 4px;"
    "   cursor: pointer;"
    "   flex-wrap: nowrap;"
    # A command reads as one line or not at all — the same reason QBtn menu
    # rows carried Quasar's `no-wrap` prop. Without it a label wraps to two
    # lines the moment the menu's intrinsic width lands a pixel short.
    "   white-space: nowrap;"
    "   font-size: var(--hw-menu-row-font-size, 0.875rem);"
    "   font-weight: var(--hw-menu-row-font-weight, 400);"
    "   text-transform: var(--hw-menu-row-text-transform, none);"
    "   color: var(--hw-menu-row-text, var(--hw-text-body));"
    " }"
    " .hw-menu-row:hover {"
    "   background: var(--hw-menu-row-hover-bg, var(--hw-bg-hover));"
    " }"
    # Same specificity as the `.hw-panel .q-icon:not()…` dim rule above and
    # declared after it, so a menu row's icon follows the menu token in a panel
    # and in a portalled flyout alike.
    " .hw-menu-row .q-icon.hw-menu-row-icon:not(.hw-use-props-color) {"
    "   color: var(--hw-menu-row-icon, var(--hw-text-dim)) !important;"
    "   font-size: var(--hw-menu-row-icon-size, 1.125rem);"
    " }"
    " .hw-menu-row.hw-disabled { opacity: 0.4; pointer-events: none; }"
    # ── compact-fields utility class ──
    # Apply to any container (panel, node widget area) that needs tight
    # Quasar field rendering.  CSS custom properties allow themes to
    # adjust the values without overriding selectors.
    " :root {"
    "   --hw-compact-gap: 0.25rem;"
    "   --hw-compact-field-h: 26px;"
    "   --hw-compact-row-min-h: 28px;"
    " }"
    " .compact-fields { --nicegui-default-gap: var(--hw-compact-gap); }"
    " .compact-fields .nicegui-row {"
    "   min-height: var(--hw-compact-row-min-h) !important;"
    "   padding-top: 0 !important; padding-bottom: 0 !important;"
    " }"
    " .compact-fields .q-field {"
    "   padding: 0 !important; margin: 0 !important;"
    "   align-items: center !important;"
    " }"
    " .compact-fields .q-field__inner { align-self: center !important; }"
    " .compact-fields .q-field__control {"
    "   height: var(--hw-compact-field-h) !important;"
    "   min-height: var(--hw-compact-field-h) !important;"
    " }"
    " .compact-fields .q-field__control::before,"
    " .compact-fields .q-field__control::after { border: none !important; }"
    " .compact-fields .q-field:not(.q-field--outlined) .q-field__control {"
    "   border: 1px solid var(--hw-border, rgba(255,255,255,0.10)) !important;"
    "   border-radius: 4px !important;"
    " }"
    " .compact-fields .q-field:not(.q-field--outlined) .q-field__control:hover {"
    "   border-color: var(--hw-border-strong, rgba(255,255,255,0.25)) !important;"
    " }"
    " .compact-fields .q-field__marginal {"
    "   height: var(--hw-compact-field-h) !important;"
    " }"
    " .compact-fields .q-field__native {"
    "   padding: 0 4px !important;"
    "   min-height: var(--hw-compact-field-h) !important;"
    "   height: var(--hw-compact-field-h) !important;"
    " }"
    " .compact-fields .q-field__bottom { display: none !important; }"
    " .compact-fields .q-toggle {"
    "   margin: 0 !important; padding: 0 !important;"
    " }"
    " .compact-fields .q-expansion-item__content {"
    "   padding: 0 0 0 0.5rem !important;"
    " }"
    # ── node-card text/widget color forwarding ──
    #
    # Mirrors the .hw-panel color-forwarding block above, rooted at
    # .ui-node-slot instead: a node card's skin sets `color:
    # var(--hw-node-text-color)` on its own root, which reaches plain
    # elements (ui.label) through ordinary inheritance but NOT Quasar's
    # q-field internals (q-field__native, q-field__label, ...) — those paint
    # their own color/background from Quasar's SASS defaults regardless of
    # an ancestor's `color`. Without this block every widget inside a node
    # card (TextWidget, NumberDrag, selects, ...) renders black-on-white,
    # untouched by any theme tier.
    #
    # The text colour falls back through --hw-node-text-color (the skin's own
    # card-root declaration) to --hw-text-body: a bare `var(--hw-text-body)`
    # here would OUTRANK the card's inline `color: var(--hw-node-text-color)`
    # for every descendant — a matched class rule beats plain inheritance
    # regardless of how the ancestor's own value was derived — which would
    # silently flip the node title back onto the workbench token the moment
    # this block exists. The fallback form keeps both live: an explicit
    # node/graph-tier --hw-node-text-color wins here too, and anything that
    # doesn't set it (most Quasar widget internals otherwise have nothing
    # to inherit) falls through to the same body-text token panels use.
    # Every other token below has no node-specific counterpart, so those read
    # the plain semantic var directly — CSS resolves it to whatever tier
    # last declared it at this DOM position (global, graph, or node), since
    # a NodeTheme may now override any token in _CSS_TOKEN_MAP, not just the
    # node_* subset. Scoped strictly to .ui-node-slot, never bare
    # .graph-canvas: a Popup/context menu already carries .hw-panel and may
    # render inside .graph-canvas (e.g. the canvas right-click menu) but
    # outside any .ui-node-slot, so it never matches this block and stays on
    # the workbench tier exclusively.
    " .ui-node-slot, .ui-node-slot *:not(.hw-cm-isolate):not(.hw-cm-isolate *)"
    " { color: var(--hw-node-text-color, var(--hw-text-body)); }"
    " .ui-node-slot .q-field--outlined .q-field__control:before"
    " { border-color: var(--hw-border) !important; }"
    " .ui-node-slot .q-field--outlined:hover .q-field__control:before"
    " { border-color: var(--hw-border-strong) !important; }"
    " .ui-node-slot .q-field__control { background: var(--hw-bg-input) !important; }"
    " .ui-node-slot .q-field .q-chip,"
    " .ui-node-slot .q-field .q-chip .q-chip__content {"
    "   background: var(--hw-accent) !important;"
    "   color: var(--hw-text-on-accent) !important;"
    " }"
    " .ui-node-slot .q-field .q-chip .q-chip__icon,"
    " .ui-node-slot .q-field .q-chip .q-icon {"
    "   color: var(--hw-text-on-accent) !important;"
    " }"
    " .ui-node-slot .q-field__label { color: var(--hw-text-muted) !important; }"
    " .ui-node-slot .q-field--highlighted .q-field__label"
    " { color: var(--hw-accent) !important; }"
    " .ui-node-slot .q-field--standard .q-field__control:before"
    " { border-bottom-color: var(--hw-border) !important; }"
    " .ui-node-slot .q-field--standard:hover .q-field__control:before"
    " { border-bottom-color: var(--hw-border-strong) !important; }"
    " .ui-node-slot .q-field--standard.q-field--highlighted .q-field__control:after"
    " { background: var(--hw-accent) !important; }"
    " .ui-node-slot .q-field--standard.q-field--highlighted .q-field__control"
    " { background: var(--hw-bg-elevated) !important; }"
    " .ui-node-slot .q-icon:not(.connection-pin):not(.hw-use-props-color)"
    " { color: var(--hw-text-dim) !important; }"
    # ── settings-field row spacing ──
    # One explicit, uniform vertical gap between field rows, applied at the
    # list container so every field (scalar or multi-row vector) is spaced
    # identically by construction — independent of each control's intrinsic
    # height or the .nicegui-row min-height. Field rows must NOT add their
    # own margins, or the gaps compound unevenly.
    " :root { --hw-field-gap: 0.15rem; }"
    " .sf-field-list { display: flex !important; flex-direction: column;"
    "   gap: var(--hw-field-gap, 0.15rem) !important; }"
    " .sf-field-list > .nicegui-row { min-height: 0 !important; }"
    # ── settings-field responsive layout ──
    # .sf-label / .sf-widget respond to their @container settings-panel.
    # Below 280px: 50/50 split.  Above: label is fixed 8rem, widget grows.
    " .sf-label  { width: 50%; flex: none; }"
    " .sf-widget { width: 50%; }"
    " @container settings-panel (min-width: 320px) {"
    "   .sf-label  { width: 9rem; flex: none; }"
    "   .sf-widget { width: auto; flex: 1; }"
    " }"
    # ── hui list-item hover + semantic text utilities ──
    " .hw-list-item-hover { transition: background-color 0.15s ease; }"
    " .hw-list-item-hover:hover { background-color: var(--hw-bg-surface) !important; }"
    " .hw-list-item-active { background-color: var(--hw-bg-active) !important; }"
    " .hw-text-danger  { color: var(--hw-danger) !important; }"
    " .hw-text-warning { color: var(--hw-warning) !important; }"
    " .hw-text-warning-dim { color: var(--hw-warning-dim) !important; }"
    " .hw-text-success { color: var(--hw-success) !important; }"
    " .hw-text-info    { color: var(--hw-info) !important; }"
    " .hw-text-accent  { color: var(--hw-accent) !important; }"
    # ── hw-tree: quiet, theme-aware Quasar q-tree ──
    # Opt-in via .classes("... hw-tree") on any ui.tree. Quasar draws
    # the connector lines (elbow + vertical guides) as pseudo-element
    # borders using `currentColor` (the bright text colour); recolour
    # them to the faint theme border token so they read as quiet guides
    # instead of stark white lines. Also tightens row density.
    " .hw-tree .q-tree__node-header {"
    "   padding-top: 2px; padding-bottom: 3px;"
    " }"
    " .hw-tree .q-tree__node-collapsible,"
    " .hw-tree .q-tree__node-header {"
    "   border-color: var(--hw-border);"
    " }"
    " .hw-tree .q-tree__node:after,"
    " .hw-tree .q-tree__node-header:before,"
    " .hw-tree .q-tree__node--parent"
    "   > .q-tree__node-collapsible > .q-tree__node-body:after {"
    "   border-color: var(--hw-border);"
    " }"
    # CodeMirror completion/hover doc panel — portals to body, so target
    # globally (like .q-menu above). Content is markdown2-rendered HTML.
    " .hw-cm-doc {"
    "   max-width: 480px;"
    "   max-height: 320px;"
    "   overflow: auto;"
    "   padding: 8px 12px;"
    "   font-size: 12px;"
    "   line-height: 1.45;"
    "   color: var(--hw-text-body);"
    " }"
    # Tighten markdown block spacing inside the panel.
    " .hw-cm-doc > :first-child { margin-top: 0; }"
    " .hw-cm-doc > :last-child { margin-bottom: 0; }"
    " .hw-cm-doc p { margin: 0.4em 0; }"
    " .hw-cm-doc h1, .hw-cm-doc h2, .hw-cm-doc h3, .hw-cm-doc h4 {"
    "   margin: 0.6em 0 0.3em; font-size: 12px; font-weight: 600;"
    "   color: var(--hw-text-body);"
    " }"
    # Inline + fenced code: monospace, subtle surface, theme tokens.
    " .hw-cm-doc code {"
    "   font-family: var(--hw-font-mono, monospace);"
    "   font-size: 11.5px;"
    " }"
    " .hw-cm-doc pre {"
    "   margin: 0.4em 0;"
    "   padding: 6px 8px;"
    "   background: var(--hw-bg-input);"
    "   border: 1px solid var(--hw-border);"
    "   border-radius: 4px;"
    "   overflow-x: auto;"
    "   white-space: pre;"
    " }"
    " .hw-cm-doc :not(pre) > code {"
    "   padding: 1px 4px;"
    "   background: var(--hw-bg-input);"
    "   border-radius: 3px;"
    " }"
    # The doc panel's own padding replaces the tooltip wrapper's.
    " .cm-tooltip.cm-completionInfo { padding: 0; }"
)


class AppShell:
    """
    Renders the workspace layout for a single browser session.

    Structure:
        TopBar          → fixed top row
        Action Area     → IconSlot (left side, vertical icon buttons + active editor)
        Edit Area       → TabSlot (center, tabbed editors)
        Info Area       → TabSlot (split from edit, optional, with fold toggle)
        Context Area    → IconSlot (right side, vertical icon buttons + active editor)
        StatusBar       → fixed bottom row

    The AppShell does NOT contain business logic. It delegates to:
        - Session for context and state management
        - WorkspaceManager for layout state
        - EditorTypeRegistry for editor instantiation
        - Individual Slot subclasses for their own editor lifecycle
    """

    def __init__(self, session: "Session", editor_registry: "EditorTypeRegistry"):
        """
        Create the AppShell.

        Args:
            session: The per-session Session object.
            editor_registry: EditorTypeRegistry for looking up and
                instantiating editor types.
        """
        self.session = session
        self._editor_registry = editor_registry

        # Poll/draw orchestrator state — every slot (ACTION, CONTEXT, EDIT,
        # INFO) is a managed :class:`Slot` that owns its area and wrappers.
        self._managed_slots: dict[SlotName, Slot] = {}

        # DOM references -------------------------------------------------------
        self._left_divider: ui.element | None = None  # drag handle between left and main slots
        self._right_divider: ui.element | None = None  # drag handle between main and right slots
        self._bottom_divider: ui.element | None = None  # horizontal drag handle above BottomTabBar
        self._presence_row: ui.element | None = None  # TopBar connected-principal chips
        self._account_menu: object | None = None  # AccountMenuProvider, built lazily

        # Bus subscriptions for workspace-mutation commands.
        self._lifecycle_unsubs: list[Callable[[], None]] = []

    def _build_initial_theme_css(self) -> str:
        """Build the :root CSS block from the active WorkbenchTheme.

        Returns an empty string when the ``workbench.theme`` setting isn't
        registered (no library declares it) or no workbench themes are
        registered. The app then renders without theme CSS variables —
        visually broken but navigable, so the config issue is surfaced
        in the UI rather than crashing on the first page load.
        """
        context = self.session.context
        settings_registry = context.app.library_service.get_settings_registry()
        theme_registry = context.app.library_service.get_theme_registry()
        try:
            wb_theme_key, _ = settings_registry.resolve("workbench.theme")
        except KeyError:
            logger.warning(
                "AppShell: 'workbench.theme' setting is not registered — "
                "no library declares it. Skipping theme CSS variables; "
                "the app will render with browser defaults."
            )
            return ""
        valid_keys = [k for k in theme_registry.list_workbench_keys() if not k.startswith("__system__:")]
        if not valid_keys:
            logger.warning(
                "AppShell: no workbench themes registered. Skipping theme "
                "CSS variables; the app will render with browser defaults."
            )
            return ""
        if wb_theme_key not in valid_keys:
            wb_theme_key = valid_keys[0]
            settings_registry.set_global("workbench.theme", wb_theme_key)
        context.active_workbench_theme_key = wb_theme_key
        theme = theme_registry.get_workbench(context.active_workbench_theme_key)
        css_vars = theme.to_css_vars()
        # The global node theme overrides the workbench's node tokens. Merged
        # here rather than emitted as a second :root block: one block with the
        # node theme's values already applied is what a later-wins cascade
        # would produce anyway, and it cannot be reordered by accident.
        css_vars.update(self._global_node_theme_vars())
        vars_str = " ".join(f"{k}: {v};" for k, v in css_vars.items())
        return f" :root {{ {vars_str} }}"

    def _global_node_theme_vars(self) -> dict[str, str]:
        """Tier-1 vars from the globally selected node theme, or {} if unset."""
        try:
            context = self.session.context
            settings_registry = context.app.library_service.get_settings_registry()
            theme_registry = context.app.library_service.get_theme_registry()
            key, _ = settings_registry.resolve("ui.node.default.skin.studio_node_theme")
            if not key:
                return {}
            theme = theme_registry.get_node_theme(key)
        except Exception:
            logger.warning("Global node theme could not be resolved; using workbench values")
            return {}
        return theme.to_css_vars()

    def _on_setting_changed(self, name: str, value) -> None:
        """React to global setting changes that the shell cares about."""
        if name == "workbench.theme" and value.value:
            self.apply_workbench_theme(value.value)
        elif name == "ui.node.default.skin.studio_node_theme":
            self.apply_node_theme(value.value or "")

    def apply_node_theme(self, registry_key: str) -> None:
        """Switch the global node theme by rewriting its CSS variables on :root.

        Clear-then-set, deliberately: ``setProperty`` only ever writes what the
        new theme mentions, so switching to a theme that omits a token would
        otherwise leave the PREVIOUS theme's value stranded on :root — a bug
        invisible until someone authors a partial theme, and then only in one
        switch direction. Removing every token first (all of ``_CSS_TOKEN_MAP``,
        not a node-specific subset — a NodeTheme may now override any of them)
        makes the workbench theme's own stylesheet value show through for
        anything the new theme is silent on: this only ever touches the
        inline style on ``documentElement``, never the ``:root {}`` rule
        ``_build_initial_theme_css`` writes into the page's stylesheet, so the
        workbench baseline is always there to fall back to.
        """
        try:
            from haywire.ui.themes.workbench import BaseTheme

            context = self.session.context
            theme_registry = context.app.library_service.get_theme_registry()

            for css_var in BaseTheme._CSS_TOKEN_MAP.values():
                ui.run_javascript(f"document.documentElement.style.removeProperty('{css_var}')")

            if not registry_key:
                return
            theme = theme_registry.get_node_theme(registry_key)
            for css_var, value in theme.to_css_vars().items():
                safe_value = value.replace("'", "\\'")
                ui.run_javascript(f"document.documentElement.style.setProperty('{css_var}', '{safe_value}')")
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to apply node theme '{registry_key}': {e}")

    def apply_workbench_theme(self, registry_key: str) -> None:
        """
        Dynamically switch the active workbench theme by updating CSS variables.

        Uses JavaScript setProperty on :root for zero-flash switching.
        Also updates context.active_workbench_theme_key for persistence.
        """
        try:
            context = self.session.context
            theme_registry = context.app.library_service.get_theme_registry()
            theme = theme_registry.get_workbench(registry_key)
            context.active_workbench_theme_key = registry_key
            for css_var, value in theme.to_css_vars().items():
                safe_value = value.replace("'", "\\'")
                ui.run_javascript(f"document.documentElement.style.setProperty('{css_var}', '{safe_value}')")
            # The assignment above emits SessionContext.active_workbench_theme_key
            # synthetically; subscribers via @redraw_on(SessionContext.active_workbench_theme_key)
            # rebuild on that signal.
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to apply workbench theme '{registry_key}': {e}")

    def render(self) -> None:
        """Build the complete workspace layout into the current NiceGUI page."""
        # Remove NiceGUI's default content padding so the shell fills the viewport.
        # Area-level tab panels must not scroll — editors own their scroll behaviour.
        # CSS vars are injected from the active WorkbenchTheme (no body.body--dark block).
        ui.add_css(self._build_initial_theme_css() + STATIC_CSS + _pygments_doc_css())

        # React to workbench.theme setting changes (e.g. from the settings panel).
        # Exact-key subscription — the shell only cares about this one key.
        settings_registry = self.session.context.app.library_service.get_settings_registry()
        settings_registry.subscribe("workbench.theme", self._on_setting_changed)
        settings_registry.subscribe("ui.node.default.skin.studio_node_theme", self._on_setting_changed)

        # Subscription to Workspace-mutation handlers.
        self._lifecycle_unsubs.append(self.session.subscribe(Reveal, self._reveal_editor))
        self._lifecycle_unsubs.append(self.session.subscribe(Close, self._close_payload))
        self._lifecycle_unsubs.append(self.session.subscribe(BroadcastClose, self._close_payload))
        self._lifecycle_unsubs.append(
            self.session.subscribe(PresenceChanged, lambda _s: self._render_presence())
        )
        # An agent principal starting or finishing a tool call. Same row, same
        # redraw: FarmhandActivity carries no payload precisely so that both
        # signals can share one "re-read and repaint" handler.
        self._lifecycle_unsubs.append(
            self.session.subscribe(FarmhandActivity, lambda _s: self._render_presence())
        )
        # An agent arriving or aging out. The row is rebuilt from live state,
        # so the principal payload goes unused here.
        self._lifecycle_unsubs.append(
            self.session.subscribe(AgentConnected, lambda _s: self._render_presence())
        )
        self._lifecycle_unsubs.append(
            self.session.subscribe(AgentDisconnected, lambda _s: self._render_presence())
        )

        # Drag-resize handlers for left/middle/right/bottom panels. These use JavaScript
        # to set inline styles on the fly for immediate response and to avoid conflicts
        # with NiceGUI's re-rendering.
        # The dividers are only visible when their adjacent panel is visible,
        # so they won't interfere with mouse events when not needed.
        #
        # The slot id/name tokens the JS uses (DOM ids `hw-slot-<value>` and the
        # `slot:` field emitted back) are derived from SlotName so JS and Python
        # agree by construction — the JS never hand-types a slot string. The
        # inbound `slot` value is re-validated in _on_slot_resize via SlotName(...).
        _slot_js_consts = (
            f'var HW_SLOT_ACTION = "{SlotName.ACTION.value}";'
            f'var HW_SLOT_CONTEXT = "{SlotName.CONTEXT.value}";'
            f'var HW_SLOT_INFO = "{SlotName.INFO.value}";'
        )
        ui.add_head_html(
            """<script>
(function () {
  """
            + _slot_js_consts
            + """
  var drag = null;
  // Horizontal (.hw-area-divider) resizes the action or context slot; the edit
  // slot fills remaining space. Vertical (.hw-area-vdivider) resizes the info slot.
  // Dividers are only present in the DOM when their slot is visible, so
  // retracted slots are unreachable by drag — re-open an icon slot by
  // clicking any of its icons, or the info slot via its chevron toggle.
  document.addEventListener("mousedown", function (e) {
    var hdiv = e.target.closest ? e.target.closest(".hw-area-divider") : null;
    var vdiv = e.target.closest ? e.target.closest(".hw-area-vdivider") : null;
    if (!hdiv && !vdiv) return;
    e.preventDefault();
    e.stopPropagation();
    if (hdiv) {
      var isLeft = hdiv.classList.contains("hw-area-divider-left");
      var slotName = isLeft ? HW_SLOT_ACTION : HW_SLOT_CONTEXT;
      var panel = document.getElementById("hw-slot-" + slotName);
      if (!panel) return;
      var startW = panel.getBoundingClientRect().width;
      panel.style.flex = "none";
      panel.style.width = startW + "px";
      drag = { panel: panel, vertical: false, slotName: slotName,
               isLeft: isLeft, startPos: e.clientX, startSize: startW, minSize: 150 };
      document.body.style.cursor = "col-resize";
    } else {
      var panel = document.getElementById("hw-slot-" + HW_SLOT_INFO);
      if (!panel) return;
      var startH = panel.getBoundingClientRect().height;
      panel.style.flex = "none";
      panel.style.minHeight = "0";
      panel.style.height = startH + "px";
      drag = { panel: panel, vertical: true, slotName: HW_SLOT_INFO,
               startPos: e.clientY, startSize: startH, minSize: 80 };
      document.body.style.cursor = "row-resize";
    }
    document.body.style.userSelect = "none";
  }, true);
  document.addEventListener("mousemove", function (e) {
    if (!drag) return;
    if (drag.vertical) {
      var dy = e.clientY - drag.startPos;
      var newH = Math.max(drag.minSize, drag.startSize - dy);
      drag.panel.style.height = newH + "px";
    } else {
      var dx = e.clientX - drag.startPos;
      var newW = Math.max(drag.minSize, drag.startSize + (drag.isLeft ? dx : -dx));
      drag.panel.style.width = newW + "px";
    }
  }, true);
  document.addEventListener("mouseup", function () {
    if (!drag) return;
    if (drag.vertical) {
      var finalH = parseInt(drag.panel.style.height, 10) || drag.startSize;
      drag.panel.style.flex = "0 0 " + finalH + "px";
      emitEvent("hw-slot-resize", { slot: drag.slotName, size: finalH });
    } else {
      var finalW = parseInt(drag.panel.style.width, 10) || drag.startSize;
      drag.panel.style.flex = "0 1 " + finalW + "px";
      emitEvent("hw-slot-resize", { slot: drag.slotName, size: finalW });
    }
    drag = null;
    document.body.style.cursor = "";
    document.body.style.userSelect = "";
  }, true);
})();
</script>"""
        )

        # Drag-resize event emitted by the JS handler above.
        ui.on("hw-slot-resize", lambda e: self._on_slot_resize(e))

        snapshot = self.session.workspace_manager.snapshot

        with ui.column().classes("w-full gap-0").style("height: 100vh; overflow: hidden;"):
            # ----------------------------------------------------------------
            # TopBar
            # ----------------------------------------------------------------
            self._render_topbar()

            # ----------------------------------------------------------------
            # Main content row (Left slot + Main slot + Right slot)
            # flex-wrap: nowrap is critical for drag-resize: without it, slots
            # wrap to the next line instead of shrinking when widths change.
            # ----------------------------------------------------------------
            with (
                ui.row()
                .classes("w-full gap-0 no-wrap")
                .style("flex: 1; overflow: hidden; min-height: 0; flex-wrap: nowrap;")
            ):
                # ---------------- Action slot (left edge) ----------------
                left_slot = self._build_managed_slot(SlotName.ACTION, bar_place="left")
                # Slot wrapper lives inside main_content_row; slot renders bar + area into it.
                left_wrapper = ui.element("div").style("height: 100%;")
                left_slot.render(left_wrapper)

                self._left_divider = (
                    ui.element("div")
                    .classes("hw-area-divider hw-area-divider-left flex-shrink-0")
                    .style("width: 5px; height: 100%; cursor: col-resize;")
                )
                self._left_divider.set_visibility(left_slot.visible)
                left_slot._on_visibility_change = self._left_divider.set_visibility

                # ---------------- Main + Bottom ----------------
                with (
                    ui.column()
                    .classes("gap-0")
                    .style("flex: 1; height: 100%; overflow: hidden; min-width: 0;") as main_col
                ):
                    main_col._props["id"] = "hw-slot-edit-container"
                    main_data = snapshot.get(SlotName.EDIT, {})
                    if main_data.get("editors") or self._editor_registry.get_by_default_slot(SlotName.EDIT):
                        main_slot = self._build_managed_slot(SlotName.EDIT, bar_place="top")
                        main_slot.render(main_col)
                    else:
                        ui.label("No editor").classes("hw-text-muted p-4")

                    bottom_data = snapshot.get(SlotName.INFO, {})
                    if bottom_data.get("editors") or self._editor_registry.get_by_default_slot(
                        SlotName.INFO
                    ):
                        self._bottom_divider = (
                            ui.element("div")
                            .classes("hw-area-vdivider w-full flex-shrink-0")
                            .style("height: 5px; cursor: row-resize;")
                        )
                        bottom_slot = self._build_managed_slot(
                            SlotName.INFO, bar_place="top", show_fold_toggle=True
                        )
                        self._bottom_divider.set_visibility(bottom_slot.visible)
                        bottom_slot.render(main_col)
                        bottom_slot._on_visibility_change = self._bottom_divider.set_visibility

                # ---------------- Context slot (right edge) ----------------
                right_data = snapshot.get(SlotName.CONTEXT, {})
                if right_data.get("active_key") or self._editor_registry.get_by_default_slot(
                    SlotName.CONTEXT
                ):
                    self._right_divider = (
                        ui.element("div")
                        .classes("hw-area-divider hw-area-divider-right flex-shrink-0")
                        .style("width: 5px; height: 100%; cursor: col-resize;")
                    )
                    right_slot = self._build_managed_slot(SlotName.CONTEXT, bar_place="right")
                    self._right_divider.set_visibility(right_slot.visible)
                    right_wrapper = ui.element("div").style("height: 100%;")
                    right_slot.render(right_wrapper)
                    right_slot._on_visibility_change = self._right_divider.set_visibility

            # ----------------------------------------------------------------
            # StatusBar
            # ----------------------------------------------------------------
            self._render_statusbar()

    def _render_topbar(self) -> None:
        """Render the top bar with global controls."""
        with (
            ui.row()
            .classes("w-full items-center px-3 gap-3 hw-panel")
            .style(
                "height: 48px; min-height: 48px;"
                " background: var(--hw-bg-surface); border-bottom: 1px solid var(--hw-border);"
            )
        ):
            ui.label("Haywire").classes("font-bold text-lg hw-text-body")

            def _on_save() -> None:
                self.session.app_state.save_workspace(shell=self)
                ui.notify("Workspace saved", position="top-right")

            ui.button(
                icon=hui.icon.save,
                on_click=_on_save,
            ).props("flat round dense").tooltip("Save workspace layout")

            def _on_check_updates() -> None:
                from haywire.ui.modals.update_dialog import open_update_dialog

                open_update_dialog(Path.cwd())

            ui.button(
                icon="autorenew",
                on_click=_on_check_updates,
            ).props("flat round dense").tooltip("Check for Haywire updates")

            ui.space()

            self._presence_row = ui.row().classes("items-center gap-1")
            self._render_presence()

            self._render_account_icon()

    def _render_statusbar(self) -> None:
        """Render the status bar at the bottom."""
        with (
            ui.row()
            .classes("w-full items-center px-3 gap-2")
            .style(
                "height: 24px; min-height: 24px; background: var(--hw-statusbar-bg);"
                " border-top: 1px solid var(--hw-border);"
            )
        ):
            ui.label(f"Session: {self.session.session_id[:8]}...").classes("text-xs hw-text-muted")

            from haywire.core.update import startup_mismatch

            notice = startup_mismatch(Path.cwd() / "pyproject.toml")
            if notice:
                ui.label(notice).classes("text-xs").style("color: var(--hw-warning);")

            from haywire.core.access import resolve_tier

            principal = self.session.context.principal
            label = identity_text(principal, resolve_tier(principal))
            if label:
                ui.space()
                ui.label(label).classes("hw-text-muted text-xs px-2")

    def _render_account_icon(self) -> None:
        """The ``account_circle`` button in the ACTION bar footer."""
        from haywire.ui.app.account_menu import AccountMenuProvider

        provider = AccountMenuProvider(
            context=self.session.context,
            session=self.session,
            panel_registry=self.session.context.app.library_service.get_panel_registry(),
        )
        self._account_menu = provider

        button = (
            ui.button(icon="account_circle")
            .props("flat round dense")
            .classes("hw-account-icon")
            .tooltip("Account")
        )
        button.on(
            "click",
            lambda event: provider.open(
                (event.args.get("clientX", 0), event.args.get("clientY", 0) + 20)
                if isinstance(event.args, dict)
                else (0, 0)
            ),
        )

    def _render_presence(self) -> None:
        """Chips for every connected principal — users first, then agents.

        Visible to everyone, not admin-only: in a crew setting, knowing who else
        is connected is useful to all, and it discloses nothing beyond "these
        roster entries are online" to people already inside the trust boundary.
        """
        if self._presence_row is None:
            return

        try:
            from haywire_studio.auth.live import RosterCache
            from haywire_studio.auth.presence import collect_presence
        except ImportError:
            return

        # DI accessor, not self.session._session_manager — reaching into a
        # private attribute of Session would couple the shell to its internals.
        from haywire.core.di.context import get_session_manager

        self._presence_row.clear()
        with self._presence_row:
            for entry in collect_presence(get_session_manager(), RosterCache()):
                icon = "smart_toy" if entry.kind == "agent" else "person"
                detail = (
                    last_seen_text(entry.last_seen_seconds)
                    if entry.kind == "agent"
                    else (f"{entry.sessions} tabs" if entry.sessions > 1 else "connected")
                )
                with ui.row().classes("items-center gap-1 px-2 hw-presence-chip"):
                    ui.icon(icon).classes("text-xs")
                    ui.label(entry.name).classes("text-xs")
                    # Only while a tool is actually in flight. An idle agent's
                    # chip stays exactly as wide as it was before this feature,
                    # so the TopBar does not reflow on every call.
                    if entry.running_tool:
                        ui.label(entry.running_tool).classes("text-xs hw-text-dim")
                    # The tooltip stays a one-liner: identity and liveness only.
                    # Anything list-shaped goes to the activity editor, reached
                    # from the account menu — the chip is core's and must not
                    # know which library owns that editor.
                    ui.tooltip(f"{entry.tier.value} · {detail}")

    def _build_managed_slot(
        self,
        slot_name: SlotName,
        bar_place: Literal["left", "right", "top", "bottom"] = "left",
        show_fold_toggle: bool = False,
        on_visibility_change=None,
    ) -> Slot:
        """Construct and cache a Slot for ``slot_name`` from the workspace snapshot.

        ACTION / CONTEXT → IconSlot. EDIT / INFO → TabSlot.
        """
        from haywire.ui.app.icon_slot import IconSlot
        from haywire.ui.app.tab_slot import TabSlot

        snapshot = self.session.workspace_manager.snapshot
        data = snapshot.get(slot_name, {})

        cls = IconSlot if slot_name in (SlotName.ACTION, SlotName.CONTEXT) else TabSlot
        # The ACTION slot is always built (its bar carries the account
        # footer icon even with zero editor bindings) but its area starts
        # collapsed unless the snapshot or registry actually has something
        # to show, so an idle ACTION slot doesn't reserve empty space.
        initial_visible = True
        if slot_name is SlotName.ACTION:
            initial_visible = bool(
                data.get("active_key") or self._editor_registry.get_by_default_slot(slot_name)
            )
        slot = cls(
            session=self.session,
            name=slot_name,
            registry=self._editor_registry,
            bar_place=bar_place,
            show_fold_toggle=show_fold_toggle,
            on_visibility_change=on_visibility_change,
            visible=initial_visible,
        )
        slot.populate_from_snapshot(data)
        self._managed_slots[slot_name] = slot
        return slot

    def cleanup(self) -> None:
        """Detach all managed slots and drop bus subscriptions.

        Called by the session when the browser disconnects so that slot
        lifecycle subscribers and the shell's own workspace-mutation
        subscriptions don't leak across sessions.
        """
        for unsub in self._lifecycle_unsubs:
            unsub()
        self._lifecycle_unsubs.clear()
        for slot in self._managed_slots.values():
            slot.cleanup()
        self._managed_slots.clear()

    def collect_snapshot(self) -> dict:
        """Collect current slot state into a snapshot dict for persistence."""
        return {slot_name: slot.to_snapshot() for slot_name, slot in self._managed_slots.items()}

    # ------------------------------------------------------------------
    # Workspace-mutation handlers (bus subscribers)
    # ------------------------------------------------------------------

    def _reveal_editor(self, command: Reveal) -> None:
        """Ensure the editor described by ``command`` is active in its default slot.

        Resolves the target slot from the editor's ``class_identity.default_slot``
        and delegates to :meth:`Slot.reveal`, which does find-or-add-then-activate
        uniformly across IconSlot and TabSlot. Does NOT broadcast
        WORKSPACE_CHANGED (the reveal is in response to another event already
        propagating).
        """
        from haywire.ui.editor.identity import OpenBehavior

        editor_cls = command.editor
        editor_key = editor_cls.class_identity.registry_key

        slot_name = editor_cls.class_identity.default_slot

        slot = self._managed_slots.get(slot_name) if slot_name else None
        if slot is None:
            logger.warning(
                f"AppShell: reveal_editor '{editor_key}' targets slot '{slot_name}' "
                "which is not hostable in the active workspace, skipping reveal"
            )
            return

        opens = editor_cls.class_identity.opens
        if opens is OpenBehavior.ON_PAYLOAD and command.binding_id is None:
            logger.warning(
                f"AppShell: reveal of opens='on_payload' editor '{editor_key}' "
                f"requires a binding_id; dropping."
            )
            return

        slot.reveal(command)

    def _close_payload(self, command: Close) -> None:
        """Close every wrapper bound to ``command.binding_id`` across all slots.

        Subscribed to both :class:`Close` (local) and :class:`BroadcastClose`
        (cross-session) — both carry a ``binding_id`` field.
        """
        binding_id = command.binding_id
        if not binding_id:
            return
        for slot in self._managed_slots.values():
            slot.close_tabs_for(binding_id)

    def _on_slot_resize(self, event) -> None:
        """Dispatch ``hw-slot-resize`` events from the drag JS to the target slot.

        The JS emits ``{slot: SlotName.value, size: int}`` (action/context/info).
        NiceGUI delivers the payload in ``event.args`` as a dict. The raw slot
        string is the JS bridge's only untyped boundary, so it is coerced back
        to :class:`SlotName` here — an unknown value raises ``ValueError`` and is
        treated as malformed. Unknown or malformed payloads are ignored silently:
        a drag gesture that races a slot removal shouldn't raise.
        """
        args = getattr(event, "args", None)
        if not isinstance(args, dict):
            return
        raw_slot = args.get("slot")
        size = args.get("size")
        if not raw_slot or not isinstance(size, (int, float)):
            return
        try:
            slot_name = SlotName(raw_slot)
        except ValueError:
            return
        slot = self._managed_slots.get(slot_name)
        if slot is None:
            return
        slot.set_size(int(size))
