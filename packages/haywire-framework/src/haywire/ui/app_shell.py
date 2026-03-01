# packages/haywire-framework/src/haywire/ui/app_shell.py
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

    def __init__(self, session: 'Session', editor_registry: Optional['EditorTypeRegistry'] = None):
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
        self._right_column = None  # stored for dynamic switching via _switch_right_area

    def render(self) -> None:
        """Build the complete workspace layout into the current NiceGUI page."""
        ws = self.session.workspace_manager.active

        # Remove NiceGUI's default content padding so the shell fills the viewport.
        # Area-level tab panels must not scroll — editors own their scroll behaviour.
        ui.add_css(
            '.nicegui-content { padding: 0 !important; max-width: none !important;'
            ' height: 100vh !important; overflow: hidden !important; }'
            ' .q-tab-panels > .q-panel-parent > .q-panel.scroll'
            ' { overflow: hidden !important; }'
        )

        with ui.column().classes('w-full gap-0').style('height: 100vh; overflow: hidden;'):
            # ----------------------------------------------------------------
            # TopBar
            # ----------------------------------------------------------------
            self._render_topbar()

            # ----------------------------------------------------------------
            # Main content row (ActivityBar + Left + Middle + Right + ContextBar)
            # ----------------------------------------------------------------
            with ui.row().classes('w-full gap-0').style('flex: 1; overflow: hidden; min-height: 0;'):

                # ActivityBar — narrow left icon strip
                self._render_activity_bar()

                # Left Area (collapsible)
                if ws.left.visible and ws.left.editor_key:
                    with ui.column().classes('gap-0').style(
                        f'width: {ws.left.size}px; min-width: {ws.left.size}px; '
                        f'height: 100%; overflow: hidden; border-right: 1px solid #333;'
                    ):
                        self._render_area('left', ws.left.editor_key)

                # Middle + optional Bottom (takes remaining space)
                with ui.column().classes('gap-0').style(
                    'flex: 1; height: 100%; overflow: hidden; min-width: 0;'
                ):
                    self._render_middle_area()

                # Right Area (collapsible)
                if ws.right.visible and ws.right.editor_key:
                    with ui.column().classes('gap-0').style(
                        f'width: {ws.right.size}px; min-width: {ws.right.size}px; '
                        f'height: 100%; overflow: hidden; border-left: 1px solid #333;'
                    ) as right_col:
                        self._right_column = right_col
                        self._render_area('right', ws.right.editor_key)

                # ContextBar — narrow right icon strip
                self._render_context_bar()

            # ----------------------------------------------------------------
            # StatusBar
            # ----------------------------------------------------------------
            self._render_statusbar()

        # Expose area-switching callbacks so editors can trigger panel changes.
        self.session.context.metadata['switch_right_area'] = self._switch_right_area

    def _render_topbar(self) -> None:
        """Render the top bar with workspace name and global controls."""
        wm = self.session.workspace_manager
        ws = wm.active
        with ui.row().classes('w-full items-center px-3 gap-3').style(
            'height: 48px; min-height: 48px; background: #1e1e2e; border-bottom: 1px solid #333;'
        ):
            ui.label('Haywire').classes('text-white font-bold text-lg')
            ui.label('|').classes('text-gray-600')

            # Workspace switcher
            preset_names = wm.get_preset_names()
            ws_select = ui.select(
                options=preset_names,
                value=ws.name,
                label=None,
            ).props('dense dark outlined').classes('text-sm').style('min-width: 160px;')

            def _on_workspace_switch(e):
                value = e.value if hasattr(e, 'value') else (e.args[0] if e.args else None)
                if not value:
                    return
                try:
                    wm.switch(value)
                    ui.notify(f'Workspace: {value}', position='top-right', type='positive')
                except KeyError:
                    pass

            ws_select.on_value_change(_on_workspace_switch)

            ui.button(
                icon='save',
                on_click=lambda: (wm.save_current(), ui.notify('Workspace saved', position='top-right')),
            ).props('flat round dense color=grey').tooltip('Save current workspace').classes('text-gray-400')

    def _render_activity_bar(self) -> None:
        """Render the activity bar (left icon strip) that drives the Left Area."""
        ws = self.session.workspace_manager.active

        # Collect editors suggested for 'left' area from registry
        left_editors = {}
        if self._editor_registry:
            left_editors = self._editor_registry.get_by_default_area('left')

        with ui.column().classes('items-center justify-start gap-1 py-2').style(
            'width: 48px; min-width: 48px; height: 100%; '
            'background: #181825; border-right: 1px solid #333; overflow: hidden;'
        ):
            if left_editors:
                for reg_key, editor_cls in left_editors.items():
                    icon = editor_cls.class_identity.icon
                    label = editor_cls.class_identity.label
                    is_active = (ws.left_bar_active == reg_key)
                    btn_classes = 'w-10 h-10' + (' text-blue-400' if is_active else ' text-gray-400')
                    ui.button(icon=icon, on_click=lambda k=reg_key: self._switch_left_area(k)) \
                        .classes(btn_classes) \
                        .props('flat round') \
                        .tooltip(label)
            else:
                # Placeholder when no editors are registered
                ui.icon('menu').classes('text-gray-600')

    def _render_context_bar(self) -> None:
        """Render the context bar (right icon strip) that drives the Right Area."""
        ws = self.session.workspace_manager.active

        right_editors = {}
        if self._editor_registry:
            right_editors = self._editor_registry.get_by_default_area('right')

        with ui.column().classes('items-center justify-start gap-1 py-2').style(
            'width: 48px; min-width: 48px; height: 100%; '
            'background: #181825; border-left: 1px solid #333; overflow: hidden;'
        ):
            if right_editors:
                for reg_key, editor_cls in right_editors.items():
                    icon = editor_cls.class_identity.icon
                    label = editor_cls.class_identity.label
                    is_active = (ws.right_bar_active == reg_key)
                    btn_classes = 'w-10 h-10' + (' text-blue-400' if is_active else ' text-gray-400')
                    ui.button(icon=icon, on_click=lambda k=reg_key: self._switch_right_area(k)) \
                        .classes(btn_classes) \
                        .props('flat round') \
                        .tooltip(label)
            else:
                ui.icon('tune').classes('text-gray-600')

    def _render_middle_area(self) -> None:
        """Render the middle area with tabs and optional bottom split."""
        ws = self.session.workspace_manager.active

        if ws.middle.tabs:
            # Build tab bar
            with ui.tabs().classes('w-full').style(
                'background: #1e1e2e; min-height: 36px; border-bottom: 1px solid #333;'
            ) as tabs:
                for tab in ws.middle.tabs:
                    ui.tab(name=tab.editor_key, label=tab.label)

            # Store tab element in session metadata so editors can switch tabs
            self.session.context.metadata['middle_tabs'] = tabs

            # Tab panels — each one gets an editor
            with ui.tab_panels(tabs, value=ws.middle.tabs[ws.middle.active_tab_index].editor_key) \
                    .classes('w-full').style('flex: 1; overflow: hidden; min-height: 0;'):
                for tab in ws.middle.tabs:
                    with ui.tab_panel(tab.editor_key).style('height: 100%; padding: 0;'):
                        self._render_area('middle', tab.editor_key)
        else:
            # No tabs — single middle area
            with ui.column().style('flex: 1; height: 100%; overflow: hidden;'):
                self._render_area('middle', None)

        # Bottom area split (optional)
        if ws.middle.bottom_visible and ws.middle.bottom_editor_key:
            with ui.column().style(
                f'height: {ws.middle.bottom_size}px; min-height: {ws.middle.bottom_size}px; '
                'border-top: 1px solid #333; overflow: hidden;'
            ):
                self._render_area('bottom', ws.middle.bottom_editor_key)

    def _render_statusbar(self) -> None:
        """Render the status bar at the bottom."""
        with ui.row().classes('w-full items-center px-3 gap-2').style(
            'height: 24px; min-height: 24px; background: #1e3a5f; border-top: 1px solid #333;'
        ):
            ui.label(f'Session: {self.session.session_id[:8]}...').classes('text-xs text-gray-300')

    def _render_area(self, slot: str, editor_key: Optional[str]) -> None:
        """Render a single area slot, instantiating the editor if available.

        Args:
            slot: Area slot identifier ('left', 'middle', 'right', 'bottom').
            editor_key: Registry key of the editor to render, or None.
        """
        if not editor_key:
            ui.label('No editor').classes('text-gray-500 p-4')
            return

        editor_cls = None
        if self._editor_registry:
            # WorkspaceState stores short registry_id values; look up by id not full key
            editor_cls = self._editor_registry.get_by_id(editor_key)

        if editor_cls is None:
            # Placeholder — no editor registered for this key yet
            with ui.column().classes('w-full h-full items-center justify-center'):
                ui.icon('extension').classes('text-gray-600 text-4xl')
                ui.label(f'Editor: {editor_key}').classes('text-gray-500')
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
            container_div = ui.element('div').style('width: 100%; height: 100%;')
            editor_instance.render(container_div, self.session.context)
        except Exception as e:
            logging.error(f"AppShell: Failed to render editor '{editor_key}' in slot '{slot}': {e}")
            ui.label(f'Error loading editor: {editor_key}').classes('text-red-400 p-4')

    def _switch_left_area(self, editor_key: str) -> None:
        """Switch the editor shown in the Left Area.

        Args:
            editor_key: Registry key of the editor to show.
        """
        ws = self.session.workspace_manager.active
        ws.left.editor_key = editor_key
        ws.left_bar_active = editor_key
        logging.info(f"AppShell: Switching left area to '{editor_key}'")
        # Notify context
        self.session.notify_context_changed(
            ContextChangedEvent(change_type=ContextChangeType.WORKSPACE_CHANGED)
        )
        ui.notify(f"Left panel: {editor_key}")

    def _switch_right_area(self, editor_key: str) -> None:
        """Switch the editor shown in the Right Area, re-rendering the column.

        Args:
            editor_key: Registry key of the editor to show.
        """
        ws = self.session.workspace_manager.active
        if ws.right.editor_key == editor_key:
            return  # already showing this editor

        # Unsubscribe and evict the old right-area editor instance.
        old_editor = self.session._editors.pop('right', None)
        if old_editor is not None:
            self.session.unsubscribe_context_changes(old_editor.on_context_changed)

        ws.right.editor_key = editor_key
        ws.right_bar_active = editor_key
        logging.info(f"AppShell: Switching right area to '{editor_key}'")

        # Re-render the right column with the new editor.
        if self._right_column is not None:
            self._right_column.clear()
            with self._right_column:
                self._render_area('right', editor_key)

        self.session.notify_context_changed(
            ContextChangedEvent(change_type=ContextChangeType.WORKSPACE_CHANGED)
        )
