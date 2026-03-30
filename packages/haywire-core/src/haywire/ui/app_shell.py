# packages/haywire-core/src/haywire/ui/app_shell.py
"""
AppShell renders the workspace layout using NiceGUI.

This is the top-level UI component that creates the ActivityBar, ContextBar,
Left/Middle/Right/Bottom areas, TopBar, and StatusBar.

It reads the current WorkspaceState to determine which editors go where,
instantiates them, and wires up context change notifications.

The AppShell is created once per browser session from within a NiceGUI page
handler. The haywire-app package is responsible for constructing the Session
and calling AppShell.render().
"""

import logging
from typing import Optional, TYPE_CHECKING

logger = logging.getLogger(__name__)

from nicegui import ui

from haywire.ui.context_events import ContextChangedEvent, ContextChangeType

if TYPE_CHECKING:
    from haywire.ui.session import Session
    from haywire.ui.editor.registry import EditorTypeRegistry


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
        self._area_containers: dict = {}  # area slot -> NiceGUI container ref
        self._left_column = None  # stored for dynamic switching via _switch_left_area
        self._right_column = None  # stored for dynamic switching via _switch_right_area
        self._left_divider = None  # drag handle between left and middle
        self._right_divider = None  # drag handle between middle and right
        self._bottom_container = None  # bottom split area column
        self._bottom_divider = None  # horizontal drag handle above bottom panel
        self._btn_left = None  # ActivityBar toggle button for left panel
        self._btn_bottom = None  # Tab-bar toggle button for bottom panel
        self._btn_right = None  # ContextBar toggle button for right panel

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
            # Middle-area tab bar
            " .hw-tabs .q-tab { color: var(--hw-text-muted) !important; }"
            " .hw-tabs .q-tab--active { color: var(--hw-text-body) !important; }"
            " .hw-tabs .q-tab__indicator { background: var(--hw-accent) !important; }"
            " .hw-tabs .q-tab__label { font-size: 12px; }"
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
        )
        ui.add_css(self._build_initial_theme_css() + _static_css)

        # React to workbench.theme setting changes (e.g. from the settings panel).
        settings_registry = self.session.context.app.library_service.get_settings_registry()
        settings_registry.add_listener(self._on_setting_changed)

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
  // Vertical (.hw-area-vdivider): resizes the bottom panel; the tab area
  //   (flex:1) fills remaining height automatically.
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
      var panel = document.getElementById(isLeft ? "hw-area-left" : "hw-area-right");
      if (!panel) return;
      var startW = panel.getBoundingClientRect().width;
      panel.style.flex = "none";
      panel.style.width = startW + "px";
      drag = { panel: panel, vertical: false, isLeft: isLeft,
               startPos: e.clientX, startSize: startW, minSize: 150 };
      document.body.style.cursor = "col-resize";
    } else {
      var panel = document.getElementById("hw-area-bottom");
      if (!panel) return;
      var startH = panel.getBoundingClientRect().height;
      panel.style.flex = "none";
      panel.style.minHeight = "0";
      panel.style.height = startH + "px";
      drag = { panel: panel, vertical: true,
               startPos: e.clientY, startSize: startH, minSize: 80 };
      document.body.style.cursor = "row-resize";
    }
    document.body.style.userSelect = "none";
  }, true);
  document.addEventListener("mousemove", function (e) {
    if (!drag) return;
    if (drag.vertical) {
      // Drag up → bottom panel grows (dy negative → bigger height)
      var dy = e.clientY - drag.startPos;
      var newH = Math.max(drag.minSize, drag.startSize - dy);
      drag.panel.style.height = newH + "px";
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
      // flex: 0 0 keeps exact height; no shrink (avoids fighting the parent flex layout).
      drag.panel.style.flex = "0 0 " + drag.panel.style.height;
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

        with ui.column().classes("w-full gap-0").style("height: 100vh; overflow: hidden;"):
            # ----------------------------------------------------------------
            # TopBar
            # ----------------------------------------------------------------
            self._render_topbar()

            # ----------------------------------------------------------------
            # Main content row (ActivityBar + Left + Middle + Right + ContextBar)
            # flex-wrap: nowrap is critical for drag-resize: without it, panels
            # wrap to the next line instead of shrinking when widths change.
            # ----------------------------------------------------------------
            with (
                ui.row()
                .classes("w-full gap-0 no-wrap")
                .style("flex: 1; overflow: hidden; min-height: 0; flex-wrap: nowrap;")
            ):
                # ActivityBar — narrow left icon strip
                self._render_activity_bar()

                # Left Area — always rendered if an editor is assigned so the
                # TopBar toggle can show/hide it without re-building the DOM.
                # id="hw-area-left" lets the JS drag handler find this element.
                if ws.left.editor_key:
                    with (
                        ui.column()
                        .classes("gap-0")
                        .style(
                            f"width: {ws.left.size}px; min-width: 150px; "
                            f"height: 100%; overflow: hidden; border-right: 1px solid var(--hw-border);"
                            " background: var(--hw-bg-page);"
                        ) as left_col
                    ):
                        self._left_column = left_col
                        self._render_area("left", ws.left.editor_key)
                    left_col._props["id"] = "hw-area-left"
                    left_col.set_visibility(ws.left.visible)

                    # Drag handle — left panel ↔ middle area
                    self._left_divider = (
                        ui.element("div")
                        .classes("hw-area-divider hw-area-divider-left flex-shrink-0")
                        .style("width: 5px; height: 100%; cursor: col-resize;")
                    )
                    self._left_divider.set_visibility(ws.left.visible)

                # Middle + optional Bottom (takes remaining space)
                # id="hw-area-middle" lets the JS find this element directly.
                with (
                    ui.column()
                    .classes("gap-0")
                    .style("flex: 1; height: 100%; overflow: hidden; min-width: 0;") as middle_col
                ):
                    self._render_middle_area()
                middle_col._props["id"] = "hw-area-middle"

                # Right Area — always rendered if an editor is assigned so the
                # TopBar toggle can show/hide it without re-building the DOM.
                # id="hw-area-right" lets the JS drag handler find this element.
                if ws.right.editor_key:
                    # Drag handle — middle area ↔ right panel
                    self._right_divider = (
                        ui.element("div")
                        .classes("hw-area-divider hw-area-divider-right flex-shrink-0")
                        .style("width: 5px; height: 100%; cursor: col-resize;")
                    )
                    self._right_divider.set_visibility(ws.right.visible)

                    with (
                        ui.column()
                        .classes("gap-0")
                        .style(
                            f"width: {ws.right.size}px; min-width: 150px; "
                            f"height: 100%; overflow: hidden; border-left: 1px solid var(--hw-border);"
                            " background: var(--hw-bg-page);"
                        ) as right_col
                    ):
                        self._right_column = right_col
                        self._render_area("right", ws.right.editor_key)
                    right_col._props["id"] = "hw-area-right"
                    right_col.set_visibility(ws.right.visible)

                # ContextBar — narrow right icon strip
                self._render_context_bar()

            # ----------------------------------------------------------------
            # StatusBar
            # ----------------------------------------------------------------
            self._render_statusbar()

        # Expose area-switching callbacks so editors can trigger panel changes.
        self.session.context.metadata["switch_right_area"] = self._switch_right_area

    def _render_topbar(self) -> None:
        """Render the top bar with workspace name and global controls."""
        wm = self.session.workspace_manager
        ws = wm.active
        with (
            ui.row()
            .classes("w-full items-center px-3 gap-3 hw-panel")
            .style(
                "height: 48px; min-height: 48px;"
                " background: var(--hw-bg-surface); border-bottom: 1px solid var(--hw-border);"
            )
        ):
            ui.label("Haywire").classes("font-bold text-lg hw-text-body")
            ui.label("|").classes("hw-text-muted")

            # Workspace switcher
            preset_names = wm.get_preset_names()
            ws_select = (
                ui.select(
                    options=preset_names,
                    value=ws.name,
                    label=None,
                )
                .props("dense outlined")
                .classes("text-sm hw-text-muted")
                .style("min-width: 160px;")
            )

            def _on_workspace_switch(e):
                value = e.value if hasattr(e, "value") else (e.args[0] if e.args else None)
                if not value:
                    return
                try:
                    wm.switch(value)
                    ui.notify(f"Workspace: {value}", position="top-right", type="positive")
                except KeyError:
                    pass

            ws_select.on_value_change(_on_workspace_switch)

            ui.button(
                icon="save",
                on_click=lambda: (wm.save_current(), ui.notify("Workspace saved", position="top-right")),
            ).props("flat round dense color=grey").tooltip("Save current workspace").classes("text-gray-400")

    def _render_activity_bar(self) -> None:
        """Render the activity bar (left icon strip) that drives the Left Area."""
        ws = self.session.workspace_manager.active

        # Collect editors suggested for 'left' area from registry
        left_editors = {}
        if self._editor_registry:
            left_editors = self._editor_registry.get_by_default_area("left")

        with (
            ui.column()
            .classes("items-center justify-start gap-1 py-2")
            .style(
                "width: 48px; min-width: 48px; height: 100%; "
                "background: var(--hw-bg-sidebar); border-right: 1px solid var(--hw-border); "
                "overflow: hidden;"
            )
        ):
            # Left panel toggle at the top of the bar.
            # Visible → mirrored login (fold in); hidden → plain logout (fold out).
            if ws.left.editor_key:
                fold_icon = "login" if ws.left.visible else "logout"
                self._btn_left = (
                    ui.button(icon=fold_icon, on_click=self._toggle_left_panel)
                    .props("flat round dense size=sm color=grey")
                    .tooltip("Toggle left panel")
                )
                if ws.left.visible:
                    self._btn_left.style("transform: scaleX(-1);")
                ui.separator().classes("w-full opacity-20")

            if left_editors:
                for reg_key, editor_cls in left_editors.items():
                    icon = editor_cls.class_identity.icon
                    label = editor_cls.class_identity.label
                    is_active = ws.left_bar_active == reg_key
                    btn_classes = "w-10 h-10" + (" text-blue-400" if is_active else " text-gray-400")
                    ui.button(icon=icon, on_click=lambda k=reg_key: self._switch_left_area(k)).classes(
                        btn_classes
                    ).props("flat round").tooltip(label)
            else:
                # Placeholder when no editors are registered
                ui.icon("menu").classes("text-gray-600")

    def _render_context_bar(self) -> None:
        """Render the context bar (right icon strip) that drives the Right Area."""
        ws = self.session.workspace_manager.active

        right_editors = {}
        if self._editor_registry:
            right_editors = self._editor_registry.get_by_default_area("right")

        with (
            ui.column()
            .classes("items-center justify-start gap-1 py-2")
            .style(
                "width: 48px; min-width: 48px; height: 100%; "
                "background: var(--hw-bg-sidebar); border-left: 1px solid var(--hw-border); "
                "overflow: hidden;"
            )
        ):
            # Right panel toggle at the top of the bar.
            # Visible → plain login (fold in); hidden → mirrored logout (fold out).
            if ws.right.editor_key:
                fold_icon = "login" if ws.right.visible else "logout"
                self._btn_right = (
                    ui.button(icon=fold_icon, on_click=self._toggle_right_panel)
                    .props("flat round dense size=sm color=grey")
                    .tooltip("Toggle right panel")
                )
                if not ws.right.visible:
                    self._btn_right.style("transform: scaleX(-1);")
                ui.separator().classes("w-full opacity-20")

            if right_editors:
                for reg_key, editor_cls in right_editors.items():
                    icon = editor_cls.class_identity.icon
                    label = editor_cls.class_identity.label
                    is_active = ws.right_bar_active == reg_key
                    btn_classes = "w-10 h-10" + (" text-blue-400" if is_active else " text-gray-400")
                    ui.button(icon=icon, on_click=lambda k=reg_key: self._switch_right_area(k)).classes(
                        btn_classes
                    ).props("flat round").tooltip(label)
            else:
                ui.icon("tune").classes("text-gray-600")

    def _render_middle_area(self) -> None:
        """Render the middle area with tabs and optional bottom split."""
        ws = self.session.workspace_manager.active

        if ws.middle.tabs:
            # Tab bar row — tabs on the left, optional bottom-panel toggle on the right
            with (
                ui.row()
                .classes("w-full items-center gap-0 flex-shrink-0")
                .style(
                    "background: var(--hw-bg-surface);"
                    " border-bottom: 1px solid var(--hw-border); min-height: 36px;"
                )
            ):
                with (
                    ui.tabs()
                    .props("dense align=left")
                    .classes("hw-tabs")
                    .style("flex: 1; min-height: 36px;") as tabs
                ):
                    for tab in ws.middle.tabs:
                        ui.tab(name=tab.editor_key, label=tab.label).props("no-caps")

                if ws.middle.bottom_editor_key:
                    bottom_icon = "expand_less" if ws.middle.bottom_visible else "expand_more"
                    self._btn_bottom = (
                        ui.button(icon=bottom_icon, on_click=self._toggle_bottom_panel)
                        .props("flat round dense size=sm color=grey")
                        .tooltip("Toggle bottom panel")
                        .classes("flex-shrink-0 mr-1")
                    )

            # Store tab element in session metadata so editors can switch tabs
            self.session.context.metadata["middle_tabs"] = tabs

            # Tab panels — each one gets an editor
            with (
                ui.tab_panels(tabs, value=ws.middle.tabs[ws.middle.active_tab_index].editor_key)
                .classes("w-full")
                .style("flex: 1; overflow: hidden; min-height: 0;")
            ):
                for tab in ws.middle.tabs:
                    with ui.tab_panel(tab.editor_key).style("height: 100%; padding: 0;"):
                        self._render_area("middle", tab.editor_key)
        else:
            # No tabs — single middle area
            with ui.column().style("flex: 1; height: 100%; overflow: hidden;"):
                self._render_area("middle", None)

        # Bottom area split — always rendered when an editor is assigned so the
        # TopBar toggle can show/hide it without re-building the DOM.
        # id="hw-area-bottom" lets the JS vertical drag handler find this element.
        if ws.middle.bottom_editor_key:
            self._bottom_divider = (
                ui.element("div")
                .classes("hw-area-vdivider w-full flex-shrink-0")
                .style("height: 5px; cursor: row-resize;")
            )
            self._bottom_divider.set_visibility(ws.middle.bottom_visible)

            with ui.column().style(
                f"height: {ws.middle.bottom_size}px; min-height: {ws.middle.bottom_size}px; "
                "overflow: hidden;"
            ) as bottom_col:
                self._render_area("bottom", ws.middle.bottom_editor_key)
            bottom_col._props["id"] = "hw-area-bottom"
            self._bottom_container = bottom_col
            bottom_col.set_visibility(ws.middle.bottom_visible)

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
            ui.label(f"Session: {self.session.session_id[:8]}...").classes("text-xs text-gray-300")

    def _render_area(self, slot: str, editor_key: Optional[str]) -> None:
        """Render a single area slot, instantiating the editor if available.

        Args:
            slot: Area slot identifier ('left', 'middle', 'right', 'bottom').
            editor_key: Registry key of the editor to render, or None.
        """
        if not editor_key:
            ui.label("No editor").classes("text-gray-500 p-4")
            return

        editor_cls = None
        if self._editor_registry:
            # WorkspaceState stores full registry_key values (e.g. 'studio:editor:graph_editor')
            editor_cls = self._editor_registry.get_by_key(editor_key)

        if editor_cls is None:
            # Placeholder — no editor registered for this key yet
            with ui.column().classes("w-full h-full items-center justify-center"):
                ui.icon("extension").classes("text-gray-600 text-4xl")
                ui.label(f"Editor: {editor_key}").classes("text-gray-500")
            return

        # Instantiate the editor and render it
        try:
            editor_instance = editor_cls()
            # Store in session for lifecycle management
            if slot not in self.session._editors:
                self.session._editors[slot] = editor_instance
            # Subscribe editor to context changes
            self.session.subscribe_context_changes(editor_instance.on_context_changed)
            # Render into current NiceGUI context
            container_div = (
                ui.element("div")
                .classes("hw-panel")
                .style(
                    "width: 100%; height: 100%; background: var(--hw-bg-page); color: var(--hw-text-body);"
                )
            )
            editor_instance.render(container_div, self.session.context)
        except Exception as e:
            logger.error(f"AppShell: Failed to render editor '{editor_key}' in slot '{slot}': {e}")
            ui.label(f"Error loading editor: {editor_key}").classes("text-red-400 p-4")

    def _toggle_left_panel(self) -> None:
        """Toggle the left area panel visibility."""
        ws = self.session.workspace_manager.active
        ws.left.visible = not ws.left.visible
        if self._left_column:
            self._left_column.set_visibility(ws.left.visible)
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

    def _toggle_right_panel(self) -> None:
        """Toggle the right area panel visibility."""
        ws = self.session.workspace_manager.active
        ws.right.visible = not ws.right.visible
        if self._right_column:
            self._right_column.set_visibility(ws.right.visible)
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

    def _toggle_bottom_panel(self) -> None:
        """Toggle the bottom split panel visibility."""
        ws = self.session.workspace_manager.active
        ws.middle.bottom_visible = not ws.middle.bottom_visible
        if self._bottom_divider:
            self._bottom_divider.set_visibility(ws.middle.bottom_visible)
        if self._bottom_container:
            self._bottom_container.set_visibility(ws.middle.bottom_visible)
        if self._btn_bottom:
            self._btn_bottom.props(f"icon={'expand_less' if ws.middle.bottom_visible else 'expand_more'}")

    def _switch_left_area(self, editor_key: str) -> None:
        """Switch the editor shown in the Left Area, re-rendering the column.

        Args:
            editor_key: Full registry_key of the editor to show.
        """
        ws = self.session.workspace_manager.active
        if ws.left.editor_key == editor_key:
            return  # already showing this editor

        # Unsubscribe and evict the old left-area editor instance.
        old_editor = self.session._editors.pop("left", None)
        if old_editor is not None:
            self.session.unsubscribe_context_changes(old_editor.on_context_changed)

        ws.left.editor_key = editor_key
        ws.left_bar_active = editor_key
        logger.info(f"AppShell: Switching left area to '{editor_key}'")

        # Re-render the left column with the new editor.
        if self._left_column is not None:
            self._left_column.clear()
            with self._left_column:
                self._render_area("left", editor_key)

        self.session.notify_context_changed(
            ContextChangedEvent(change_type=ContextChangeType.WORKSPACE_CHANGED)
        )

    def _switch_right_area(self, editor_key: str) -> None:
        """Switch the editor shown in the Right Area, re-rendering the column.

        Args:
            editor_key: Registry key of the editor to show.
        """
        ws = self.session.workspace_manager.active
        if ws.right.editor_key == editor_key:
            return  # already showing this editor

        # Unsubscribe and evict the old right-area editor instance.
        old_editor = self.session._editors.pop("right", None)
        if old_editor is not None:
            self.session.unsubscribe_context_changes(old_editor.on_context_changed)

        ws.right.editor_key = editor_key
        ws.right_bar_active = editor_key
        logger.info(f"AppShell: Switching right area to '{editor_key}'")

        # Re-render the right column with the new editor.
        if self._right_column is not None:
            self._right_column.clear()
            with self._right_column:
                self._render_area("right", editor_key)

        self.session.notify_context_changed(
            ContextChangedEvent(change_type=ContextChangeType.WORKSPACE_CHANGED)
        )
