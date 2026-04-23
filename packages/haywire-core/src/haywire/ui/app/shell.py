# packages/haywire-core/src/haywire/ui/app/shell.py
"""
AppShell renders the workspace layout using NiceGUI.

Top-level UI component that builds the ActivityBar, ContextBar, Left / Main
/ Right / Bottom slots, TopBar, and StatusBar.

Each of the four slots is a managed :class:`Slot` (see ``slot.py``) that
owns its editor bindings, area container, and active-binding lifecycle.
The shell's role is layout chrome (bars, dividers, visibility toggles) and
orchestration: on every ContextChangedEvent it calls
``handle_context_event`` on each managed slot, and on hot-reload events
from EditorTypeRegistry it forwards ``replace_class`` / ``remove_bindings``.
Editor instance caching, draw/poll gating, and fresh-draw on reload live
inside :class:`Slot`, not here.

The AppShell is created once per browser session from within a NiceGUI
page handler. The haywire-app package is responsible for constructing the
Session and calling AppShell.render().
"""

import logging
from pathlib import Path
from typing import Callable, Optional, TYPE_CHECKING
from nicegui import ui

from haywire.ui import elements as hui
from haywire.ui.context_events import ContextChangedEvent, ContextChangeType
from haywire.ui.app.slot import EditorBinding, Slot
from haywire.ui.workspace.workspace_state import TabState

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext
    from haywire.ui.editor.base import BaseEditor
    from haywire.ui.editor.registry import EditorTypeRegistry
    from haywire.ui.session import Session
    from haywire.core.registry.lifecycle_event import LifeCycleEvent


class AppShell:
    """
    Renders the workspace layout for a single browser session.

    Structure:
        TopBar          → ui.header or fixed top row
        ActivityBar     → ui.column, fixed left, icon buttons
        Left Area       → ui.column, resizable width
        Middle Area     → ui.column with ui.tabs for multiple editors
          Bottom Area   → ui.column, split from middle (optional)
        Right Area      → ui.column, resizable width
        ContextBar      → ui.column, fixed right, icon buttons
        StatusBar       → ui.footer or fixed bottom row

    The AppShell does NOT contain business logic. It delegates to:
        - Session for context and state management
        - WorkspaceManager for layout state
        - EditorTypeRegistry for editor instantiation
        - Individual editors for their content
    """

    def __init__(self, session: "Session", editor_registry: Optional["EditorTypeRegistry"] = None):
        """
        Create the AppShell.

        Args:
            session: The per-session Session object.
            editor_registry: Optional EditorTypeRegistry for looking up and
                instantiating editor types. If None, areas show placeholders.
        """
        self.session = session
        self._editor_registry = editor_registry

        # Poll/draw orchestrator state — every slot (left, right, main,
        # bottom) is a managed :class:`Slot` that owns its area and bindings.
        self._managed_slots: dict[str, Slot] = {}

        # DOM references -------------------------------------------------------
        self._left_slot_parent = None  # parent container the left Slot renders its area into
        self._right_slot_parent = None  # parent container the right Slot renders its area into
        self._activity_bar = None  # left slot's bar (vertical icons)
        self._context_bar = None  # right slot's bar (vertical icons)
        self._main_bar = None  # main slot's bar (horizontal tabs)
        self._bottom_bar = None  # bottom slot's bar (horizontal tabs + chevron)
        self._left_divider = None  # drag handle between left and main slots
        self._right_divider = None  # drag handle between main and right slots
        self._bottom_container = None  # bottom slot area (hidden when retracted)
        self._bottom_divider = None  # horizontal drag handle above BottomTabBar
        self._btn_left = None  # ActivityBar toggle button for left slot
        self._btn_bottom = None  # Chevron in BottomTabBar row (retract toggle)
        self._btn_right = None  # ContextBar toggle button for right slot

    @staticmethod
    def _toolbar_button_classes(is_active: bool) -> str:
        """Return toolbar button classes for active and inactive editor icons."""
        base_classes = "hw-shell-toolbar-btn w-10 h-10"
        if is_active:
            return f"{base_classes} hw-shell-toolbar-btn-active"
        return base_classes

    def _build_initial_theme_css(self) -> str:
        """Build the :root CSS block from the active WorkbenchTheme."""
        context = self.session.context
        settings_registry = context.app.library_service.get_settings_registry()
        theme_registry = context.app.library_service.get_theme_registry()
        wb_theme_key, _ = settings_registry.resolve("workbench.theme")
        valid_keys = [k for k in theme_registry.list_workbench_keys() if not k.startswith("__system__:")]
        if wb_theme_key not in valid_keys:
            wb_theme_key = valid_keys[0]
            settings_registry.set_global("workbench.theme", wb_theme_key)
        context.active_workbench_theme_key = wb_theme_key
        theme = theme_registry.get_workbench(context.active_workbench_theme_key)
        vars_str = " ".join(f"{k}: {v};" for k, v in theme.to_css_vars().items())
        return f" :root {{ {vars_str} }}"

    def _on_setting_changed(self, name: str, value) -> None:
        """React to global setting changes that the shell cares about."""
        if name == "workbench.theme" and value.value:
            self.apply_workbench_theme(value.value)

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
            self.session.notify_context_changed(
                ContextChangedEvent(
                    change_type=ContextChangeType.WORKBENCH_THEME_CHANGED,
                    source_editor="app_shell",
                )
            )
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to apply workbench theme '{registry_key}': {e}")

    def render(self) -> None:
        """Build the complete workspace layout into the current NiceGUI page."""
        ws = self.session.workspace_manager.active

        # Remove NiceGUI's default content padding so the shell fills the viewport.
        # Area-level tab panels must not scroll — editors own their scroll behaviour.
        # CSS vars are injected from the active WorkbenchTheme (no body.body--dark block).
        _static_css = (
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
            # Activity/context bar buttons
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
        )
        ui.add_css(self._build_initial_theme_css() + _static_css)

        # React to workbench.theme setting changes (e.g. from the settings panel).
        settings_registry = self.session.context.app.library_service.get_settings_registry()
        settings_registry.subscribe(None, self._on_setting_changed)

        # Register as the single orchestrator for context-change → poll/draw.
        self.session.set_orchestrator(self._on_context_changed)

        # Subscribe to editor hot-reload events so cached instances are evicted.
        if self._editor_registry:
            self._editor_registry.add_batch_event_subscriber(self._on_editor_lifecycle)

        # Drag-resize handlers for left/middle/right/bottom panels. These use JavaScript
        # to set inline styles on the fly for immediate response and to avoid conflicts
        # with NiceGUI's re-rendering.
        # The dividers are only visible when their adjacent panel is visible,
        # so they won't interfere with mouse events when not needed.
        ui.add_head_html("""<script>
(function () {
  var drag = null;
  // Use capture phase (true) so this handler runs before the graph canvas JS,
  // which may call stopImmediatePropagation() on document-level mousedown events.
  //
  // Horizontal (.hw-area-divider): resizes the left or right panel; the middle
  //   (flex:1) fills remaining space automatically.
  // Vertical (.hw-area-vdivider): resizes the bottom content panel; the middle
  //   tab area (flex:1) fills remaining height automatically. If the bottom
  //   is retracted (hidden) when drag starts, mousedown auto-expands it by
  //   dispatching a custom event the Python side listens for.
  // After drag, flex:"0 1 Xpx" (horizontal) / "0 0 Xpx" (vertical) keeps the
  // panel at its dragged size while still allowing window-resize compression.
  document.addEventListener("mousedown", function (e) {
    var hdiv = e.target.closest ? e.target.closest(".hw-area-divider") : null;
    var vdiv = e.target.closest ? e.target.closest(".hw-area-vdivider") : null;
    if (!hdiv && !vdiv) return;
    e.preventDefault();
    e.stopPropagation();
    if (hdiv) {
      var isLeft = hdiv.classList.contains("hw-area-divider-left");
      var panel = document.getElementById(isLeft ? "hw-slot-left" : "hw-slot-right");
      if (!panel) return;
      var startW = panel.getBoundingClientRect().width;
      panel.style.flex = "none";
      panel.style.width = startW + "px";
      drag = { panel: panel, vertical: false, isLeft: isLeft,
               startPos: e.clientX, startSize: startW, minSize: 150 };
      document.body.style.cursor = "col-resize";
    } else {
      var panel = document.getElementById("hw-slot-bottom");
      if (!panel) return;
      // Auto-expand from retracted: if the panel is currently hidden,
      // dispatch an event so the Python side can flip bottom.visible=true
      // and show the container, then continue the drag from zero height.
      var wasHidden = (panel.style.display === "none");
      if (wasHidden) {
        emitEvent("hw-bottom-auto-expand");
        panel.style.display = "";
      }
      var startH = wasHidden ? 0 : panel.getBoundingClientRect().height;
      panel.style.flex = "none";
      panel.style.minHeight = "0";
      panel.style.height = startH + "px";
      drag = { panel: panel, vertical: true,
               startPos: e.clientY, startSize: startH, minSize: 80,
               snapThreshold: 40 };
      document.body.style.cursor = "row-resize";
    }
    document.body.style.userSelect = "none";
  }, true);
  document.addEventListener("mousemove", function (e) {
    if (!drag) return;
    if (drag.vertical) {
      // Drag up → bottom panel grows (dy negative → bigger height)
      var dy = e.clientY - drag.startPos;
      var rawH = drag.startSize - dy;
      // Allow temporarily dragging below min so the snap-to-retracted gesture
      // feels responsive. Clamp only on release.
      var newH = Math.max(0, rawH);
      drag.panel.style.height = newH + "px";
      drag.lastRawH = rawH;
    } else {
      var dx = e.clientX - drag.startPos;
      // Left panel grows rightward (+dx); right panel grows leftward (-dx).
      var newW = Math.max(drag.minSize, drag.startSize + (drag.isLeft ? dx : -dx));
      drag.panel.style.width = newW + "px";
    }
  }, true);
  document.addEventListener("mouseup", function () {
    if (!drag) return;
    if (drag.vertical) {
      var finalH = drag.lastRawH != null ? drag.lastRawH : drag.startSize;
      if (finalH < drag.snapThreshold) {
        // Snap to retracted: hide the panel and tell the Python side.
        drag.panel.style.display = "none";
        drag.panel.style.flex = "none";
        drag.panel.style.height = "";
        emitEvent("hw-bottom-snap-retract");
      } else {
        var clamped = Math.max(drag.minSize, finalH);
        drag.panel.style.height = clamped + "px";
        // flex: 0 0 keeps exact height; no shrink (avoids fighting the parent flex layout).
        drag.panel.style.flex = "0 0 " + clamped + "px";
        emitEvent("hw-bottom-resize", clamped);
      }
    } else {
      // flex-shrink:1 lets the panel compress when the window gets smaller.
      drag.panel.style.flex = "0 1 " + drag.panel.style.width;
    }
    drag = null;
    document.body.style.cursor = "";
    document.body.style.userSelect = "";
  }, true);
})();
</script>""")

        # Bottom-area drag events emitted by the JS handler above.
        ui.on("hw-bottom-auto-expand", lambda _e: self._on_bottom_drag_auto_expand())
        ui.on("hw-bottom-snap-retract", lambda _e: self._on_bottom_drag_snap_retract())
        ui.on("hw-bottom-resize", lambda e: self._on_bottom_drag_resize(e))

        with ui.column().classes("w-full gap-0").style("height: 100vh; overflow: hidden;"):
            # ----------------------------------------------------------------
            # TopBar
            # ----------------------------------------------------------------
            self._render_topbar()

            # ----------------------------------------------------------------
            # Main content row (ActivityBar + Left slot + Main slot + Right slot + ContextBar)
            # flex-wrap: nowrap is critical for drag-resize: without it, slots
            # wrap to the next line instead of shrinking when widths change.
            # ----------------------------------------------------------------
            with (
                ui.row()
                .classes("w-full gap-0 no-wrap")
                .style("flex: 1; overflow: hidden; min-height: 0; flex-wrap: nowrap;")
            ):
                # ActivityBar — the left slot's bar (vertical icons)
                self._render_activity_bar()

                # Left slot — always rendered if an editor is assigned so the
                # TopBar toggle can show/hide it without re-building the DOM.
                # id="hw-slot-left" lets the JS drag handler find this element.
                if ws.left.active_tab_key:
                    left_slot = self._build_managed_slot("left", ws.left.active_tab_key)
                    left_slot.set_visible(ws.left.visible)
                    with (
                        ui.column()
                        .classes("gap-0")
                        .style(
                            f"width: {ws.left.size}px; min-width: 150px; "
                            f"height: 100%; overflow: hidden; border-right: 1px solid var(--hw-border);"
                            " background: var(--hw-bg-page);"
                        ) as left_col
                    ):
                        self._left_slot_parent = left_col
                        left_slot.render_area(left_col)
                    left_col._props["id"] = "hw-slot-left"
                    left_col.set_visibility(ws.left.visible)

                    # Drag handle — left slot ↔ main slot
                    self._left_divider = (
                        ui.element("div")
                        .classes("hw-area-divider hw-area-divider-left flex-shrink-0")
                        .style("width: 5px; height: 100%; cursor: col-resize;")
                    )
                    self._left_divider.set_visibility(ws.left.visible)

                # Main slot + optional Bottom slot (takes remaining space)
                # id="hw-slot-main" lets the JS find this element directly.
                with (
                    ui.column()
                    .classes("gap-0")
                    .style("flex: 1; height: 100%; overflow: hidden; min-width: 0;") as main_col
                ):
                    self._render_main_slot()
                main_col._props["id"] = "hw-slot-main"

                # Right slot — always rendered if an editor is assigned so the
                # TopBar toggle can show/hide it without re-building the DOM.
                # id="hw-slot-right" lets the JS drag handler find this element.
                if ws.right.active_tab_key:
                    # Drag handle — main slot ↔ right slot
                    self._right_divider = (
                        ui.element("div")
                        .classes("hw-area-divider hw-area-divider-right flex-shrink-0")
                        .style("width: 5px; height: 100%; cursor: col-resize;")
                    )
                    self._right_divider.set_visibility(ws.right.visible)

                    right_slot = self._build_managed_slot("right", ws.right.active_tab_key)
                    right_slot.set_visible(ws.right.visible)
                    with (
                        ui.column()
                        .classes("gap-0")
                        .style(
                            f"width: {ws.right.size}px; min-width: 150px; "
                            f"height: 100%; overflow: hidden; border-left: 1px solid var(--hw-border);"
                            " background: var(--hw-bg-page);"
                        ) as right_col
                    ):
                        self._right_slot_parent = right_col
                        right_slot.render_area(right_col)
                    right_col._props["id"] = "hw-slot-right"
                    right_col.set_visibility(ws.right.visible)

                # ContextBar — the right slot's bar (vertical icons)
                self._render_context_bar()

            # ----------------------------------------------------------------
            # StatusBar
            # ----------------------------------------------------------------
            self._render_statusbar()

    def _render_topbar(self) -> None:
        """Render the top bar with global controls."""
        wm = self.session.workspace_manager
        with (
            ui.row()
            .classes("w-full items-center px-3 gap-3 hw-panel")
            .style(
                "height: 48px; min-height: 48px;"
                " background: var(--hw-bg-surface); border-bottom: 1px solid var(--hw-border);"
            )
        ):
            ui.label("Haywire").classes("font-bold text-lg hw-text-body")

            ui.button(
                icon=hui.icon.save,
                on_click=lambda: (wm.save(), ui.notify("Workspace saved", position="top-right")),
            ).props("flat round dense").tooltip("Save workspace layout")

    def _render_activity_bar(self) -> None:
        """Render the activity bar wrapper and its current contents."""
        with (
            ui.column()
            .classes("items-center justify-start gap-1 py-2")
            .style(
                "width: 48px; min-width: 48px; height: 100%; "
                "background: var(--hw-bg-sidebar); border-right: 1px solid var(--hw-border); "
                "overflow: hidden;"
            ) as activity_bar
        ):
            self._activity_bar = activity_bar
            self._render_activity_bar_contents()

    def _render_activity_bar_contents(self) -> None:
        """Render the current ActivityBar contents inside the existing wrapper."""
        ws = self.session.workspace_manager.active

        left_editors = {}
        if self._editor_registry:
            left_editors = self._editor_registry.get_by_default_slot("left")

        # Left slot toggle at the top of the bar.
        # Visible → mirrored login (fold in); hidden → plain logout (fold out).
        if ws.left.active_tab_key:
            fold_icon = "login" if ws.left.visible else "logout"
            self._btn_left = (
                ui.button(icon=fold_icon, on_click=self._toggle_left_slot)
                .props("flat round dense size=sm")
                .tooltip("Toggle left slot")
            )
            if ws.left.visible:
                self._btn_left.style("transform: scaleX(-1);")
            ui.separator().classes("w-full opacity-20")

        if left_editors:
            for reg_key, editor_cls in left_editors.items():
                icon = editor_cls.class_identity.icon
                label = editor_cls.class_identity.label
                is_active = ws.left.active_tab_key == reg_key
                ui.button(icon=icon, on_click=lambda k=reg_key: self._switch_left_slot(k)).classes(
                    self._toolbar_button_classes(is_active)
                ).props("flat round").tooltip(label)
        else:
            ui.icon("menu").classes("hw-text-dim")

    def _render_context_bar(self) -> None:
        """Render the context bar wrapper and its current contents."""
        with (
            ui.column()
            .classes("items-center justify-start gap-1 py-2")
            .style(
                "width: 48px; min-width: 48px; height: 100%; "
                "background: var(--hw-bg-sidebar); border-left: 1px solid var(--hw-border); "
                "overflow: hidden;"
            ) as context_bar
        ):
            self._context_bar = context_bar
            self._render_context_bar_contents()

    def _render_context_bar_contents(self) -> None:
        """Render the current ContextBar contents inside the existing wrapper."""
        ws = self.session.workspace_manager.active

        right_editors = {}
        if self._editor_registry:
            right_editors = self._editor_registry.get_by_default_slot("right")

        # Right slot toggle at the top of the bar.
        # Visible → plain login (fold in); hidden → mirrored logout (fold out).
        if ws.right.active_tab_key:
            fold_icon = "login" if ws.right.visible else "logout"
            self._btn_right = (
                ui.button(icon=fold_icon, on_click=self._toggle_right_slot)
                .props("flat round dense size=sm")
                .tooltip("Toggle right slot")
            )
            if not ws.right.visible:
                self._btn_right.style("transform: scaleX(-1);")
            ui.separator().classes("w-full opacity-20")

        if right_editors:
            for reg_key, editor_cls in right_editors.items():
                icon = editor_cls.class_identity.icon
                label = editor_cls.class_identity.label
                is_active = ws.right.active_tab_key == reg_key
                ui.button(icon=icon, on_click=lambda k=reg_key: self._switch_right_slot(k)).classes(
                    self._toolbar_button_classes(is_active)
                ).props("flat round").tooltip(label)
        else:
            ui.icon("tune").classes("hw-text-dim")

    def _render_main_slot(self) -> None:
        """Render the main slot (MainTabBar + area) plus the bottom slot.

        Both main and bottom are managed :class:`Slot` instances. The bar
        for each renders a row of tabs whose click handler calls
        :meth:`_switch_main_slot` / :meth:`_switch_bottom_slot`. The area
        below the bar is the :class:`Slot`'s own container, and only the
        active binding is mounted in the DOM at any time.
        """
        ws = self.session.workspace_manager.active

        # ---------- Main slot ----------
        # Rendered as flex-items directly inside the caller's ``main_col``
        # (the outer flex column). The bar is flex-shrink:0 and the area
        # takes ``flex: 1`` of the remaining height. An intermediate wrapper
        # breaks flex sizing when the bottom slot is a sibling below.
        if ws.main.tabs:
            main_slot = self._build_managed_slot("main", ws.main.active_tab_key)
            self._render_main_bar()
            with (
                ui.column()
                .classes("gap-0 w-full")
                .style("flex: 1; min-height: 0; overflow: hidden;") as main_area_parent
            ):
                main_slot.render_area(main_area_parent)
        else:
            # No tabs — empty placeholder.
            with ui.column().classes("w-full").style("flex: 1; min-height: 0; overflow: hidden;"):
                ui.label("No editor").classes("hw-text-muted p-4")

        # ---------- Bottom slot ----------
        if ws.bottom.tabs:
            self._render_bottom_slot()

    def _render_main_bar(self) -> None:
        """Render the main slot's tab bar wrapper plus its current contents."""
        with (
            ui.row()
            .classes("w-full items-center gap-0 flex-shrink-0 hw-slot-bar")
            .style(
                "background: var(--hw-bg-surface);"
                " border-bottom: 1px solid var(--hw-border); min-height: 36px;"
            ) as main_bar
        ):
            self._main_bar = main_bar
            self._render_main_bar_contents()

    def _render_main_bar_contents(self) -> None:
        """Render the clickable tabs for the main slot."""
        ws = self.session.workspace_manager.active
        self._render_slot_tabs(
            tabs=ws.main.tabs,
            active_tab_key=ws.main.active_tab_key,
            on_select=self._switch_main_slot,
            on_close=self._close_main_tab_by_id,
        )

    def _close_main_tab_by_id(self, tab_id: str) -> None:
        """Handler for the × button on a main tab.

        Emits a ``TAB_CLOSE_REQUESTED`` event so both the shell (which
        actually closes the tab) and host apps (which do domain cleanup)
        run through the same path.
        """
        editor_key, payload = self._split_tab_id(tab_id)
        self.session.notify_context_changed(
            ContextChangedEvent(
                change_type=ContextChangeType.TAB_CLOSE_REQUESTED,
                source_editor="app_shell",
                detail={
                    "slot_name": "main",
                    "editor_key": editor_key,
                    "payload": payload,
                },
            )
        )

    def _tab_close_visible(self, tab) -> bool:
        """Return True if the tab should render a close (×) button.

        Rule: every tab whose editor class declares ``opens != REQUIRED``
        is closeable. ``required`` tabs are always-present singletons and
        have no close button.

        Unknown editor classes default to closeable — better to let the
        user remove a tab whose class is gone than strand it.
        """
        from haywire.ui.editor.identity import OpenBehavior

        if tab.editor_key is None:
            return False
        cls = self._editor_registry.get_by_key(tab.editor_key) if self._editor_registry else None
        if cls is None:
            return True
        opens = getattr(cls.class_identity, "opens", OpenBehavior.REQUIRED)
        return opens is not OpenBehavior.REQUIRED

    def _render_slot_tabs(
        self,
        tabs: list,
        active_tab_key: Optional[str],
        on_select: Callable[[str], None],
        on_close: Optional[Callable[[str], None]] = None,
    ) -> None:
        """Render a Quasar-styled ``ui.tabs`` row wired to ``on_select``.

        The selection is one-way: clicks fire ``on_select(tab_id)`` and the
        shell's switch helper updates the Slot. ``tab_id`` equals ``editor_key``
        for single-instance tabs and ``editor_key::payload`` for multi-instance
        tabs; the switch helper decomposes it before calling into the Slot.
        The ``ui.tabs`` value prop is set only for initial styling; the bar row
        is cleared and re-rendered on every switch.

        When ``on_close`` is supplied every multi-instance tab (one with a
        payload) renders a trailing ``×`` button that fires ``on_close(tab_id)``.
        Single-instance tabs stay close-less — closing a registry-backed tab
        like FileBrowser wouldn't make sense.
        """
        ids = [t.tab_id for t in tabs]
        initial = active_tab_key if active_tab_key in ids else (ids[0] if ids else None)

        with (
            ui.tabs(value=initial, on_change=lambda e: on_select(e.value))
            .props("dense align=left")
            .classes("hw-slot-bar-tabs")
            .style("flex: 1; min-height: 36px;")
        ):
            for tab in tabs:
                # Pass label="" so Quasar's q-tab doesn't auto-render the
                # ``name`` (which is our composite editor_key::payload id)
                # when custom slot content is used.
                tab_el = ui.tab(name=tab.tab_id, label="").props("no-caps")
                with tab_el:
                    with ui.row().classes("items-center gap-1 no-wrap"):
                        ui.label(tab.label)
                        if on_close is not None and self._tab_close_visible(tab):
                            tab_id = tab.tab_id
                            (
                                ui.button(
                                    icon="close",
                                    on_click=lambda _e, tid=tab_id: on_close(tid),
                                )
                                .props("flat round dense size=xs")
                                .classes("hw-tab-close -mr-1")
                                .on("click.stop", lambda _e: None)
                            )

    def _render_bottom_slot(self) -> None:
        """Render the bottom slot below the main slot.

        Structure:
            [vertical drag divider] — visibility follows ``bottom.visible``
            [BottomTabBar]          — always visible (retracted state)
            [bottom area]           — visibility follows ``bottom.visible``

        The area is given ``id="hw-slot-bottom"`` so the JS vertical drag
        handler can find it.
        """
        ws = self.session.workspace_manager.active

        # Vertical drag handle above the BottomTabBar.
        self._bottom_divider = (
            ui.element("div")
            .classes("hw-area-vdivider w-full flex-shrink-0")
            .style("height: 5px; cursor: row-resize;")
        )
        self._bottom_divider.set_visibility(ws.bottom.visible)

        bottom_slot = self._build_managed_slot("bottom", ws.bottom.active_tab_key)

        self._render_bottom_bar()

        with (
            ui.column()
            .classes("gap-0")
            .style(
                f"height: {ws.bottom.size}px; min-height: 0; width: 100%; overflow: hidden;"
            ) as bottom_col
        ):
            bottom_slot.render_area(bottom_col)
        bottom_col._props["id"] = "hw-slot-bottom"
        self._bottom_container = bottom_col
        bottom_col.set_visibility(ws.bottom.visible)

    def _render_bottom_bar(self) -> None:
        """Render the bottom slot's tab bar wrapper plus its current contents."""
        with (
            ui.row()
            .classes("w-full items-center gap-0 flex-shrink-0 hw-slot-bar")
            .style(
                "background: var(--hw-bg-surface);"
                " border-top: 1px solid var(--hw-border);"
                " border-bottom: 1px solid var(--hw-border); min-height: 36px;"
            ) as bottom_bar
        ):
            self._bottom_bar = bottom_bar
            self._render_bottom_bar_contents()

    def _render_bottom_bar_contents(self) -> None:
        """Render the clickable tabs + retract chevron for the bottom slot."""
        ws = self.session.workspace_manager.active
        self._render_slot_tabs(
            tabs=ws.bottom.tabs,
            active_tab_key=ws.bottom.active_tab_key,
            on_select=self._switch_bottom_slot,
        )
        chevron_icon = "expand_less" if ws.bottom.visible else "expand_more"
        self._btn_bottom = (
            ui.button(icon=chevron_icon, on_click=self._toggle_bottom_slot)
            .props("flat round dense size=sm")
            .tooltip("Toggle bottom slot")
            .classes("flex-shrink-0 mr-1")
        )

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

    def _build_managed_slot(self, slot_name: str, active_key: Optional[str]) -> Slot:
        """Construct and cache a managed :class:`Slot` for ``slot_name``.

        * Left/right bindings come from the editor registry's
          ``get_by_default_slot`` lookup.
        * Main/bottom bindings come from the workspace state's persisted
          tab list, resolving each tab's ``editor_key`` against the
          registry. Tabs whose class can't be resolved are skipped. The
          tab's ``metadata["payload"]`` flows into the binding so persisted
          multi-instance tabs round-trip correctly across restart.
        """
        bindings: list[EditorBinding] = []
        if slot_name in ("left", "right"):
            editors = self._editor_registry.get_by_default_slot(slot_name) if self._editor_registry else {}
            bindings = [
                EditorBinding(editor_key=key, editor_cls=cls, payload=None) for key, cls in editors.items()
            ]
        else:
            ws = self.session.workspace_manager.active
            tabs = ws.main.tabs if slot_name == "main" else ws.bottom.tabs
            for tab in tabs:
                if tab.editor_key is None:
                    continue
                cls = self._editor_registry.get_by_key(tab.editor_key) if self._editor_registry else None
                if cls is None:
                    logger.warning(
                        f"AppShell: slot '{slot_name}' tab '{tab.editor_key}' "
                        "has no registered editor class; skipping binding"
                    )
                    continue
                bindings.append(
                    EditorBinding(editor_key=tab.editor_key, editor_cls=cls, payload=tab.payload)
                )

        if slot_name in ("main", "bottom") and active_key is not None:
            initial_editor_key, initial_payload = self._split_tab_id(active_key)
        else:
            initial_editor_key, initial_payload = active_key, None

        slot = Slot(
            session=self.session,
            name=slot_name,
            initial_bindings=bindings,
            active_key=initial_editor_key,
            active_payload=initial_payload,
        )
        self._managed_slots[slot_name] = slot
        self._mirror_active_key_to_workspace(slot_name, slot.active_binding_id or slot.active_key)
        return slot

    def _mirror_active_key_to_workspace(self, slot_name: str, active_key: Optional[str]) -> None:
        """Reconcile the workspace's persisted ``active_tab_key`` with the slot's resolved key.

        Why: a persisted key may point to an editor class that is no longer
        in the registry. ``Slot._resolve_initial_active`` silently falls back
        to the first binding in that case — without this mirror the bar/icon
        highlight would still read the stale key and desync from the drawn
        editor.
        """
        if active_key is None:
            return
        ws = self.session.workspace_manager.active
        if slot_name == "left":
            ws.left.active_tab_key = active_key
        elif slot_name == "right":
            ws.right.active_tab_key = active_key
        elif slot_name == "main":
            ws.main.active_tab_key = active_key
        elif slot_name == "bottom":
            ws.bottom.active_tab_key = active_key

    # ------------------------------------------------------------------
    # Poll / draw orchestrator
    # ------------------------------------------------------------------

    def _reveal_editor(
        self,
        editor_key: str,
        payload: Optional[str] = None,
        label: Optional[str] = None,
    ) -> None:
        """Ensure ``(editor_key, payload)`` is the active editor in its default slot.

        Resolves the target slot from the editor's ``class_identity.default_slot``
        and calls the matching pure-switch helper so no nested WORKSPACE_CHANGED
        event is fired. If the editor is unknown to the registry, or targets a
        slot that does not exist in the active workspace, a warning is logged
        and the reveal is skipped — the caller's own event still propagates
        normally.

        For main/bottom targets a reveal with a ``payload`` that has no matching
        binding is treated as a tab-open: a new tab is created via
        :meth:`open_in_tab` using ``label`` (or the editor class label when
        omitted) as the tab's display label.

        Args:
            editor_key: Full registry_key of the editor to reveal.
            payload: Optional disambiguator for multi-instance editors. When
                omitted, the slot falls back to the first binding matching
                ``editor_key`` (preserves pre-multi-instance callers).
            label: Optional tab label for newly-created multi-instance tabs.
        """
        if self._editor_registry is None:
            logger.warning(f"AppShell: cannot reveal '{editor_key}' — no editor registry")
            return

        editor_cls = self._editor_registry.get_by_key(editor_key)
        if editor_cls is None:
            logger.warning(f"AppShell: reveal_editor '{editor_key}' not found in registry, skipping reveal")
            return

        slot_name = getattr(editor_cls.class_identity, "default_slot", None)
        if slot_name not in self._managed_slots:
            logger.warning(
                f"AppShell: reveal_editor '{editor_key}' targets slot '{slot_name}' "
                "which is not hostable in the active workspace, skipping reveal"
            )
            return

        from haywire.ui.editor.identity import OpenBehavior

        opens = getattr(editor_cls.class_identity, "opens", OpenBehavior.REQUIRED)

        if opens is OpenBehavior.ON_PAYLOAD and payload is None:
            logger.warning(
                f"AppShell: reveal of opens='on_payload' editor '{editor_key}' requires a payload; dropping."
            )
            return

        if opens is OpenBehavior.ON_CONTEXT and slot_name in ("main", "bottom"):
            slot = self._managed_slots[slot_name]
            if slot.find_binding(editor_key, None) is None:
                tab_label = label or getattr(editor_cls.class_identity, "label", editor_key)
                self.open_in_tab(slot_name, editor_key, None, tab_label)

        # For tabbed slots, auto-create a tab when payload has no match.
        if slot_name in ("main", "bottom") and payload is not None:
            slot = self._managed_slots[slot_name]
            if slot.find_binding(editor_key, payload) is None:
                tab_label = label or getattr(editor_cls.class_identity, "label", editor_key)
                self.open_in_tab(slot_name, editor_key, payload, tab_label)
                return

        self._apply_managed_slot_switch(slot_name, editor_key, payload)

    def _on_context_changed(self, event: ContextChangedEvent, context: "SessionContext") -> None:
        """Orchestrator callback: run the poll/draw cycle on every managed slot."""
        if event.change_type == ContextChangeType.TAB_CLOSE_REQUESTED:
            self._handle_tab_close_requested(event)
        elif event.change_type == ContextChangeType.TAB_REPAYLOAD_REQUESTED:
            self._handle_tab_repayload_requested(event)
        elif event.change_type == ContextChangeType.GRAPH_REMOVED:
            self._handle_graph_removed(event)

        if event.reveal_editor is not None:
            self._reveal_editor(event.reveal_editor, event.reveal_payload, event.reveal_label)

        for slot in self._managed_slots.values():
            slot.handle_context_event(event)

    def _handle_tab_close_requested(self, event: ContextChangedEvent) -> None:
        """Carry ``TAB_CLOSE_REQUESTED`` through to :meth:`close_tab`.

        ``event.detail`` is expected to be a dict with the keys
        ``slot_name``, ``editor_key`` and ``payload``. Missing keys are
        treated as a silent no-op so malformed events don't crash the
        orchestrator.
        """
        detail = event.detail if isinstance(event.detail, dict) else {}
        slot_name = detail.get("slot_name")
        editor_key = detail.get("editor_key")
        if not slot_name or not editor_key:
            return
        self.close_tab(slot_name, editor_key, detail.get("payload"))

    def _handle_tab_repayload_requested(self, event: ContextChangedEvent) -> None:
        """Carry ``TAB_REPAYLOAD_REQUESTED`` through to :meth:`repayload_tab`.

        ``event.detail`` keys: ``slot_name``, ``editor_key``, ``old_payload``,
        ``new_payload``, optional ``new_label``.
        """
        detail = event.detail if isinstance(event.detail, dict) else {}
        slot_name = detail.get("slot_name")
        editor_key = detail.get("editor_key")
        if not slot_name or not editor_key:
            return
        self.repayload_tab(
            slot_name,
            editor_key,
            detail.get("old_payload"),
            detail.get("new_payload"),
            detail.get("new_label"),
        )

    def _handle_graph_removed(self, event: ContextChangedEvent) -> None:
        """Close every tab bound to the removed graph entry.

        ``event.detail`` may be the entry's key string, or a dict with a
        ``payload`` key carrying it.
        """
        detail = event.detail
        payload = detail if isinstance(detail, str) else (detail or {}).get("payload")
        if not payload:
            return
        self.close_tabs_for_payload(payload)

    def _on_editor_lifecycle(self, events: "list[LifeCycleEvent]") -> None:
        """Handle editor class hot-reload events from EditorTypeRegistry."""
        from haywire.core.registry.lifecycle_event import LifeCycleEventType

        def _cleanup(instance: "BaseEditor") -> None:
            try:
                instance.cleanup()
            except Exception as e:
                logger.warning(f"AppShell: cleanup error: {e}")

        for evt in events:
            if evt.event_type not in (
                LifeCycleEventType.CLASS_RELOADED,
                LifeCycleEventType.CLASS_REMOVED,
            ):
                continue

            for managed in self._managed_slots.values():
                if evt.event_type == LifeCycleEventType.CLASS_RELOADED and evt.affected_class is not None:
                    managed.replace_class(evt.registry_key, evt.affected_class, cleanup_old=_cleanup)
                elif evt.event_type == LifeCycleEventType.CLASS_REMOVED:
                    managed.remove_bindings(evt.registry_key, cleanup=_cleanup)

    def _toggle_left_slot(self) -> None:
        """Toggle the left slot visibility."""
        ws = self.session.workspace_manager.active
        ws.left.visible = not ws.left.visible
        if self._left_slot_parent:
            self._left_slot_parent.set_visibility(ws.left.visible)
        left_slot = self._managed_slots.get("left")
        if left_slot is not None:
            left_slot.set_visible(ws.left.visible)
        if self._left_divider:
            self._left_divider.set_visibility(ws.left.visible)
        if self._btn_left:
            # Visible → mirrored login (fold in); hidden → plain logout (fold out)
            if ws.left.visible:
                self._btn_left.props("icon=login")
                self._btn_left.style("transform: scaleX(-1);")
            else:
                self._btn_left.props("icon=logout")
                self._btn_left.style("transform: none;")

    def _toggle_right_slot(self) -> None:
        """Toggle the right slot visibility."""
        ws = self.session.workspace_manager.active
        ws.right.visible = not ws.right.visible
        if self._right_slot_parent:
            self._right_slot_parent.set_visibility(ws.right.visible)
        right_slot = self._managed_slots.get("right")
        if right_slot is not None:
            right_slot.set_visible(ws.right.visible)
        if self._right_divider:
            self._right_divider.set_visibility(ws.right.visible)
        if self._btn_right:
            # Visible → plain login (fold in); hidden → mirrored logout (fold out)
            if ws.right.visible:
                self._btn_right.props("icon=login")
                self._btn_right.style("transform: none;")
            else:
                self._btn_right.props("icon=logout")
                self._btn_right.style("transform: scaleX(-1);")

    def _toggle_bottom_slot(self) -> None:
        """Toggle the bottom content panel's visibility (retract ↔ expand).

        The tab bar row itself stays visible in both states; only the
        divider and content panel change visibility. The chevron icon
        flips between expand_less (expanded) and expand_more (retracted).
        """
        ws = self.session.workspace_manager.active
        ws.bottom.visible = not ws.bottom.visible
        self._apply_bottom_visibility(ws.bottom.visible)

    def _apply_bottom_visibility(self, visible: bool) -> None:
        """Sync divider, container, and chevron icon to ``visible``.

        Shared by the chevron click path and the JS-driven drag auto-expand /
        snap-retract paths so all three entry points produce the same UI
        state without duplicating set-visibility logic.
        """
        if self._bottom_divider:
            self._bottom_divider.set_visibility(visible)
        if self._bottom_container:
            self._bottom_container.set_visibility(visible)
        if self._btn_bottom:
            self._btn_bottom.props(f"icon={'expand_less' if visible else 'expand_more'}")

    def _on_bottom_drag_auto_expand(self) -> None:
        """Handle the ``hw-bottom-auto-expand`` event from the drag JS.

        Fired when the user starts dragging the vertical divider while the
        bottom is retracted. Flips ``bottom.visible = True`` and syncs the
        Python-side UI state (chevron icon, element visibility flags) so
        subsequent mouse moves happen in the expanded state.
        """
        ws = self.session.workspace_manager.active
        if not ws.bottom.visible:
            ws.bottom.visible = True
            self._apply_bottom_visibility(True)

    def _on_bottom_drag_snap_retract(self) -> None:
        """Handle the ``hw-bottom-snap-retract`` event from the drag JS.

        Fired when the user drags the divider below the snap threshold on
        release. Flips ``bottom.visible = False`` and syncs the UI.
        """
        ws = self.session.workspace_manager.active
        if ws.bottom.visible:
            ws.bottom.visible = False
            self._apply_bottom_visibility(False)

    def _on_bottom_drag_resize(self, event) -> None:
        """Handle the ``hw-bottom-resize`` event from the drag JS.

        Fired on drag release with the final pixel height. Stores the new
        size in ``bottom.size`` so it survives across future save/load
        cycles (NiceGUI ``GenericEventArguments`` carries the value in
        ``args``).
        """
        ws = self.session.workspace_manager.active
        args = getattr(event, "args", None)
        if isinstance(args, (int, float)):
            ws.bottom.size = int(args)
        elif isinstance(args, list) and args and isinstance(args[0], (int, float)):
            ws.bottom.size = int(args[0])

    def _refresh_activity_bar(self) -> None:
        """Re-render the left activity bar so the active icon highlight stays in sync."""
        if self._activity_bar is None:
            return

        self._activity_bar.clear()
        with self._activity_bar:
            self._render_activity_bar_contents()

    def _refresh_context_bar(self) -> None:
        """Re-render the right context bar so the active icon highlight stays in sync."""
        if self._context_bar is None:
            return

        self._context_bar.clear()
        with self._context_bar:
            self._render_context_bar_contents()

    def _refresh_main_bar(self) -> None:
        """Re-render the main slot's tab bar so the active tab stays in sync."""
        if self._main_bar is None:
            return
        self._main_bar.clear()
        with self._main_bar:
            self._render_main_bar_contents()

    def _refresh_bottom_bar(self) -> None:
        """Re-render the bottom slot's tab bar so the active tab stays in sync."""
        if self._bottom_bar is None:
            return
        self._bottom_bar.clear()
        with self._bottom_bar:
            self._render_bottom_bar_contents()

    @staticmethod
    def _split_tab_id(tab_id: str) -> tuple[str, Optional[str]]:
        """Decompose a ``tab_id`` into ``(editor_key, payload)``.

        ``tab_id`` equals ``editor_key`` for single-instance tabs and
        ``editor_key::payload`` for multi-instance tabs. The main/bottom tab
        bars emit ``tab_id`` on click; the switch helpers use this to recover
        the payload before calling into the Slot.
        """
        if "::" in tab_id:
            editor_key, payload = tab_id.split("::", 1)
            return editor_key, payload
        return tab_id, None

    def _apply_managed_slot_switch(
        self,
        slot_name: str,
        editor_key: str,
        payload: Optional[str] = None,
    ) -> bool:
        """Switch the editor in a managed slot without broadcasting.

        Delegates to ``Slot.switch_to`` for the draw, updates workspace
        state, and refreshes the slot's bar. Does NOT fire a
        WORKSPACE_CHANGED event — the reveal path calls this helper
        directly so a single poll/draw pass can cover both the reveal and
        the originating event.

        ``payload`` disambiguates multi-instance tabs (e.g. a graph path).
        Callers pre-dating multi-instance bindings may omit it; the slot
        then falls back to the first binding matching ``editor_key``.

        For left/right slots ``active_tab_key`` is the plain ``editor_key``
        (those slots have no payloads). For main/bottom it is the composite
        ``tab_id`` so the tab bar can round-trip the selection through
        :meth:`_render_slot_tabs`.

        Returns:
            True if the slot was actually switched.
        """
        slot = self._managed_slots.get(slot_name)
        if slot is None:
            return False
        if not slot.switch_to(editor_key, payload):
            return False

        ws = self.session.workspace_manager.active
        tab_id = f"{editor_key}::{payload}" if payload else editor_key
        if slot_name == "left":
            ws.left.active_tab_key = editor_key
            self._refresh_activity_bar()
        elif slot_name == "right":
            ws.right.active_tab_key = editor_key
            self._refresh_context_bar()
        elif slot_name == "main":
            ws.main.active_tab_key = tab_id
            self._refresh_main_bar()
        elif slot_name == "bottom":
            ws.bottom.active_tab_key = tab_id
            self._refresh_bottom_bar()
        return True

    def _switch_left_slot(self, editor_key: str) -> None:
        """Switch the Left Slot editor and broadcast WORKSPACE_CHANGED."""
        if not self._apply_managed_slot_switch("left", editor_key):
            return
        self.session.notify_context_changed(
            ContextChangedEvent(change_type=ContextChangeType.WORKSPACE_CHANGED)
        )

    def _switch_right_slot(self, editor_key: str) -> None:
        """Switch the Right Slot editor and broadcast WORKSPACE_CHANGED."""
        if not self._apply_managed_slot_switch("right", editor_key):
            return
        self.session.notify_context_changed(
            ContextChangedEvent(change_type=ContextChangeType.WORKSPACE_CHANGED)
        )

    def _switch_main_slot(self, tab_id: str) -> None:
        """Switch the Main Slot editor and broadcast WORKSPACE_CHANGED.

        Receives the composite ``tab_id`` emitted by the main tab bar; splits
        it back to ``(editor_key, payload)`` before delegating.
        """
        editor_key, payload = self._split_tab_id(tab_id)
        if not self._apply_managed_slot_switch("main", editor_key, payload):
            return
        self._follow_main_tab_context(payload)
        self.session.notify_context_changed(
            ContextChangedEvent(change_type=ContextChangeType.WORKSPACE_CHANGED)
        )

    def _switch_bottom_slot(self, tab_id: str) -> None:
        """Switch the Bottom Slot editor and broadcast WORKSPACE_CHANGED.

        Receives the composite ``tab_id`` emitted by the bottom tab bar; splits
        it back to ``(editor_key, payload)`` before delegating.
        """
        editor_key, payload = self._split_tab_id(tab_id)
        if not self._apply_managed_slot_switch("bottom", editor_key, payload):
            return
        self.session.notify_context_changed(
            ContextChangedEvent(change_type=ContextChangeType.WORKSPACE_CHANGED)
        )

    # ------------------------------------------------------------------
    # Tab creation (multi-instance entry point)
    # ------------------------------------------------------------------

    def open_in_tab(
        self,
        slot_name: str,
        editor_key: str,
        payload: Optional[str],
        label: str,
    ) -> bool:
        """Ensure a tab for ``(editor_key, payload)`` exists in ``slot_name``
        and make it active.

        The core, editor-agnostic entry point for opening multi-instance tabs.
        Host apps (e.g. HaywireApp) wrap this with domain-aware helpers that
        resolve the payload + label from their own objects.

        Behavior:

        * If a tab with the same ``(editor_key, payload)`` is already present,
          it is simply activated — no duplicate tab, no duplicate binding.
        * Otherwise a new ``TabState`` is appended to the slot's tab list,
          a matching ``EditorBinding`` is added to the managed slot, and the
          slot is switched to the new tab.
        * The tab bar is re-rendered so the new tab is visible.
        * Does NOT broadcast a WORKSPACE_CHANGED or ACTIVE_GRAPH_CHANGED event;
          callers decide what domain event (if any) to emit.

        Args:
            slot_name: Target slot. Only ``"main"`` and ``"bottom"`` host
                multi-instance tabs today; left/right are rejected.
            editor_key: Full registry key of the editor class.
            payload: Multi-instance disambiguator (e.g. a graph path or a
                haystack-entry key). ``None`` means single-instance.
            label: Display label for the tab.

        Returns:
            ``True`` iff the active tab actually changed (a new tab was
            created or an inactive existing tab became active).
        """
        if slot_name not in ("main", "bottom"):
            logger.warning(f"AppShell.open_in_tab: slot '{slot_name}' is not tabbed; refusing to open tab")
            return False
        if self._editor_registry is None:
            logger.warning("AppShell.open_in_tab: no editor registry configured")
            return False
        editor_cls = self._editor_registry.get_by_key(editor_key)
        if editor_cls is None:
            logger.warning(f"AppShell.open_in_tab: editor '{editor_key}' not found in registry")
            return False

        slot = self._managed_slots.get(slot_name)
        if slot is None:
            logger.warning(f"AppShell.open_in_tab: slot '{slot_name}' is not managed")
            return False

        ws = self.session.workspace_manager.active
        slot_state = ws.main if slot_name == "main" else ws.bottom

        existing = slot.find_binding(editor_key, payload)
        if existing is not None:
            return self._apply_managed_slot_switch(slot_name, editor_key, payload)

        # Clean up the seed placeholder tab (editor_key=None) that default
        # MainSlotState carries when nothing has been opened yet.
        slot_state.tabs = [t for t in slot_state.tabs if t.editor_key is not None]

        metadata = {"payload": payload} if payload else {}
        slot_state.tabs.append(TabState(editor_key=editor_key, label=label, metadata=metadata))
        slot.add_binding(
            EditorBinding(editor_key=editor_key, editor_cls=editor_cls, payload=payload),
            activate=True,
        )

        tab_id = f"{editor_key}::{payload}" if payload else editor_key
        slot_state.active_tab_key = tab_id
        if slot_name == "main":
            self._refresh_main_bar()
        else:
            self._refresh_bottom_bar()
        self._persist_workspace()
        return True

    def close_tab(
        self,
        slot_name: str,
        editor_key: str,
        payload: Optional[str],
    ) -> bool:
        """Close one multi-instance tab in ``slot_name``.

        Removes the binding from the Slot (cleanup runs on the editor
        instance), drops the matching ``TabState`` from workspace state,
        and refreshes the tab bar. When the closed tab was active the
        Slot promotes the next binding; workspace ``active_tab_key`` is
        mirrored back from the slot so the bar highlight stays consistent.

        Does NOT notify the haystack — domain-level bookkeeping (session
        detach, entry lifecycle) is the caller's responsibility. Host apps
        wrap this with a domain-aware helper. Returns ``True`` iff a tab
        was actually removed.
        """
        if slot_name not in ("main", "bottom"):
            logger.warning(f"AppShell.close_tab: slot '{slot_name}' is not tabbed")
            return False
        slot = self._managed_slots.get(slot_name)
        if slot is None:
            return False

        def _cleanup(instance: "BaseEditor") -> None:
            try:
                instance.cleanup()
            except Exception as exc:
                logger.warning(f"AppShell.close_tab: cleanup error: {exc}")

        removed = slot.remove_binding(editor_key, payload, cleanup=_cleanup)
        if removed is None:
            return False

        ws = self.session.workspace_manager.active
        slot_state = ws.main if slot_name == "main" else ws.bottom
        tab_id = removed.binding_id
        slot_state.tabs = [t for t in slot_state.tabs if t.tab_id != tab_id]
        slot_state.active_tab_key = slot.active_binding_id

        if slot_name == "main":
            self._refresh_main_bar()
            self._follow_main_tab_context(slot.active_binding.payload if slot.active_binding else None)
        else:
            self._refresh_bottom_bar()
        self._persist_workspace()
        return True

    def repayload_tab(
        self,
        slot_name: str,
        editor_key: str,
        old_payload: Optional[str],
        new_payload: Optional[str],
        new_label: Optional[str] = None,
    ) -> bool:
        """Re-key a multi-instance tab in place (e.g. after Save-As).

        Updates the Slot's binding payload, the workspace ``TabState``
        (``metadata["payload"]`` + optional ``label``), and the mirrored
        ``active_tab_key`` when the repayloaded tab is the active one.
        The editor *instance* is preserved — it keeps its in-memory state
        and its canvas DOM. Returns ``False`` when no matching tab exists
        or when the new id collides with a sibling.
        """
        if slot_name not in ("main", "bottom"):
            logger.warning(f"AppShell.repayload_tab: slot '{slot_name}' is not tabbed")
            return False
        slot = self._managed_slots.get(slot_name)
        if slot is None:
            return False
        if not slot.repayload_binding(editor_key, old_payload, new_payload):
            return False

        ws = self.session.workspace_manager.active
        slot_state = ws.main if slot_name == "main" else ws.bottom
        old_tab_id = f"{editor_key}::{old_payload}" if old_payload else editor_key
        new_tab_id = f"{editor_key}::{new_payload}" if new_payload else editor_key
        for tab in slot_state.tabs:
            if tab.tab_id == old_tab_id:
                if new_payload:
                    tab.metadata["payload"] = new_payload
                else:
                    tab.metadata.pop("payload", None)
                if new_label is not None:
                    tab.label = new_label
                break
        if slot_state.active_tab_key == old_tab_id:
            slot_state.active_tab_key = new_tab_id
        if slot_name == "main":
            self._refresh_main_bar()
        else:
            self._refresh_bottom_bar()
        self._persist_workspace()
        return True

    def close_tabs_for_payload(self, payload: str) -> int:
        """Close every main/bottom tab whose binding payload matches ``payload``.

        Used by the ``GRAPH_REMOVED`` handler when a haystack entry is
        dropped — any editor tab pointing at that entry must go away. Returns
        the number of tabs closed.
        """
        closed = 0
        for slot_name in ("main", "bottom"):
            slot = self._managed_slots.get(slot_name)
            if slot is None:
                continue
            matches = [b for b in slot.bindings if b.payload == payload]
            for binding in matches:
                if self.close_tab(slot_name, binding.editor_key, binding.payload):
                    closed += 1
        return closed

    def _persist_workspace(self) -> None:
        """Write workspace state to disk after a tab mutation.

        Called from ``open_in_tab`` / ``close_tab`` / ``repayload_tab`` so
        the persisted tab list tracks the live layout without requiring an
        explicit Save. Swallows errors — a transient I/O failure should
        not crash the UI mutation that triggered it.
        """
        try:
            self.session.workspace_manager.save()
        except Exception as exc:
            logger.warning(f"AppShell: workspace auto-save failed: {exc}")

    def _follow_main_tab_context(self, payload: Optional[str]) -> None:
        """Mirror the active main tab's binding payload into the session context.

        The target attribute is chosen by the active editor's
        ``EditorIdentity.context_field``:

        * ``"active_graph_path"`` — legacy haystack path: look up the entry
          via ``app.haystack.get_by_key`` and set both ``active_graph`` and
          ``active_graph_path``; broadcast ``ACTIVE_GRAPH_CHANGED``.
        * ``"active_file"`` — mirror ``Path(payload)`` (or ``None``) into
          ``context.active_file`` and broadcast ``FILE_SELECTED``.
        * ``None`` — the editor manages its own context; this hook is a
          no-op for that editor.

        Unknown ``context_field`` values are logged and ignored so a
        future editor typo never silently trashes session state.
        """
        slot = self._managed_slots.get("main")
        if slot is None:
            return
        active_binding = getattr(slot, "active_binding", None)
        if active_binding is None:
            return
        editor_cls = getattr(active_binding, "editor_cls", None)
        if editor_cls is None:
            return
        class_identity = getattr(editor_cls, "class_identity", None)
        context_field = getattr(class_identity, "context_field", None) if class_identity else None
        if context_field is None:
            return

        context = self.session.context

        if context_field == "active_graph_path":
            # Legacy haystack-driven path: resolve payload → entry, update
            # both active_graph and active_graph_path, broadcast
            # ACTIVE_GRAPH_CHANGED so panels that still consume the graph
            # object can refresh.
            if payload is None:
                return
            app = context.app
            if app is None or not hasattr(app, "haystack"):
                return
            entry = app.haystack.get_by_key(payload)
            if entry is None:
                return
            if context.active_graph is entry.graph and context.active_graph_path == entry.path:
                return
            context.active_graph = entry.graph
            context.active_graph_path = entry.path
            self.session.notify_context_changed(
                ContextChangedEvent(
                    change_type=ContextChangeType.ACTIVE_GRAPH_CHANGED,
                    source_editor="app_shell",
                    detail=entry,
                )
            )
            return

        # Generic mirror: context.<context_field> = Path(payload) | None.
        new_value = Path(payload) if payload else None
        current_value = getattr(context, context_field, None)
        if current_value == new_value:
            return
        setattr(context, context_field, new_value)

        if context_field == "active_file":
            change_type = ContextChangeType.FILE_SELECTED
        else:
            logger.warning(
                f"AppShell._follow_main_tab_context: unknown context_field "
                f"{context_field!r}; emitting CUSTOM context event"
            )
            change_type = ContextChangeType.CUSTOM

        self.session.notify_context_changed(
            ContextChangedEvent(
                change_type=change_type,
                source_editor="app_shell",
                detail=new_value,
            )
        )
