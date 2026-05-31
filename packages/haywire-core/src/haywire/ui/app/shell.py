# packages/haywire-core/src/haywire/ui/app/shell.py
"""
AppShell renders the workspace layout for a single browser session.

It is a layout container that hosts four :class:`Slot` subclass instances
(left/right as :class:`IconSlot`, main/bottom as :class:`TabSlot`). The shell
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
from typing import Callable, Literal, TYPE_CHECKING
from nicegui import ui

from haywire.ui import elements as hui
from haywire.core.session.signals import (
    BroadcastClose,
    Close,
    Reveal,
)
from haywire.ui.app.slot import Slot

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from haywire.ui.editor.registry import EditorTypeRegistry
    from haywire.core.session.session import Session


class AppShell:
    """
    Renders the workspace layout for a single browser session.

    Structure:
        TopBar          → fixed top row
        Left Area       → IconSlot (left side, vertical icon buttons + active editor)
        Main Area       → TabSlot (center, tabbed editors)
        Bottom Area     → TabSlot (split from main, optional, with fold toggle)
        Right Area      → IconSlot (right side, vertical icon buttons + active editor)
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

        # Poll/draw orchestrator state — every slot (left, right, main,
        # bottom) is a managed :class:`Slot` that owns its area and wrappers.
        self._managed_slots: dict[str, Slot] = {}

        # DOM references -------------------------------------------------------
        self._left_divider: ui.element | None = None  # drag handle between left and main slots
        self._right_divider: ui.element | None = None  # drag handle between main and right slots
        self._bottom_divider: ui.element | None = None  # horizontal drag handle above BottomTabBar

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

        # Subscription to Workspace-mutation handlers.
        self._lifecycle_unsubs.append(self.session.subscribe(Reveal, self._reveal_editor))
        self._lifecycle_unsubs.append(self.session.subscribe(Close, self._close_payload))
        self._lifecycle_unsubs.append(self.session.subscribe(BroadcastClose, self._close_payload))

        # Drag-resize handlers for left/middle/right/bottom panels. These use JavaScript
        # to set inline styles on the fly for immediate response and to avoid conflicts
        # with NiceGUI's re-rendering.
        # The dividers are only visible when their adjacent panel is visible,
        # so they won't interfere with mouse events when not needed.
        ui.add_head_html("""<script>
(function () {
  var drag = null;
  // Horizontal (.hw-area-divider) resizes left or right slot; middle fills
  // remaining space. Vertical (.hw-area-vdivider) resizes the bottom slot.
  // Dividers are only present in the DOM when their slot is visible, so
  // retracted slots are unreachable by drag — re-open an icon slot by
  // clicking any of its icons, or the bottom slot via its chevron toggle.
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
      drag = { panel: panel, vertical: false, slotName: isLeft ? "left" : "right",
               isLeft: isLeft, startPos: e.clientX, startSize: startW, minSize: 150 };
      document.body.style.cursor = "col-resize";
    } else {
      var panel = document.getElementById("hw-slot-bottom");
      if (!panel) return;
      var startH = panel.getBoundingClientRect().height;
      panel.style.flex = "none";
      panel.style.minHeight = "0";
      panel.style.height = startH + "px";
      drag = { panel: panel, vertical: true, slotName: "bottom",
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
</script>""")

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
                # ---------------- Left slot ----------------
                left_data = snapshot.get("left", {})
                if left_data.get("active_key") or self._editor_registry.get_by_default_slot("left"):
                    left_slot = self._build_managed_slot("left", bar_place="left")
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
                    main_col._props["id"] = "hw-slot-main-container"
                    main_data = snapshot.get("main", {})
                    if main_data.get("editors") or self._editor_registry.get_by_default_slot("main"):
                        main_slot = self._build_managed_slot("main", bar_place="top")
                        main_slot.render(main_col)
                    else:
                        ui.label("No editor").classes("hw-text-muted p-4")

                    bottom_data = snapshot.get("bottom", {})
                    if bottom_data.get("editors") or self._editor_registry.get_by_default_slot("bottom"):
                        self._bottom_divider = (
                            ui.element("div")
                            .classes("hw-area-vdivider w-full flex-shrink-0")
                            .style("height: 5px; cursor: row-resize;")
                        )
                        bottom_slot = self._build_managed_slot(
                            "bottom", bar_place="top", show_fold_toggle=True
                        )
                        self._bottom_divider.set_visibility(bottom_slot.visible)
                        bottom_slot.render(main_col)
                        bottom_slot._on_visibility_change = self._bottom_divider.set_visibility

                # ---------------- Right slot ----------------
                right_data = snapshot.get("right", {})
                if right_data.get("active_key") or self._editor_registry.get_by_default_slot("right"):
                    self._right_divider = (
                        ui.element("div")
                        .classes("hw-area-divider hw-area-divider-right flex-shrink-0")
                        .style("width: 5px; height: 100%; cursor: col-resize;")
                    )
                    right_slot = self._build_managed_slot("right", bar_place="right")
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
                self.session.project_state.save_workspace(shell=self)
                ui.notify("Workspace saved", position="top-right")

            ui.button(
                icon=hui.icon.save,
                on_click=_on_save,
            ).props("flat round dense").tooltip("Save workspace layout")

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

    def _build_managed_slot(
        self,
        slot_name: str,
        bar_place: Literal["left", "right", "top", "bottom"] = "left",
        show_fold_toggle: bool = False,
        on_visibility_change=None,
    ) -> Slot:
        """Construct and cache a Slot for ``slot_name`` from the workspace snapshot.

        Left / right → IconSlot. Main / bottom → TabSlot.
        """
        from haywire.ui.app.icon_slot import IconSlot
        from haywire.ui.app.tab_slot import TabSlot

        snapshot = self.session.workspace_manager.snapshot
        data = snapshot.get(slot_name, {})

        cls = IconSlot if slot_name in ("left", "right") else TabSlot
        slot = cls(
            session=self.session,
            name=slot_name,
            registry=self._editor_registry,
            bar_place=bar_place,
            show_fold_toggle=show_fold_toggle,
            on_visibility_change=on_visibility_change,
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

        The JS emits ``{slot: "left"|"right"|"bottom", size: int}``. NiceGUI
        delivers the binding_id in ``event.args`` as a dict. Unknown or malformed
        payloads are ignored silently — a drag gesture that races a slot
        removal shouldn't raise.
        """
        args = getattr(event, "args", None)
        if not isinstance(args, dict):
            return
        slot_name = args.get("slot")
        size = args.get("size")
        if not slot_name or not isinstance(size, (int, float)):
            return
        slot = self._managed_slots.get(slot_name)
        if slot is None:
            return
        slot.set_size(int(size))
