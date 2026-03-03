"""
HaywireApp — main application entry point.

Manages shared services (graph manager, libraries, interpreter) and per-session
UI shells.  Each browser connection gets its own Session and AppShell; all
sessions share the same library registry, interpreter, and GraphManager.

No graph is loaded at startup.  The user creates a new graph via the
GraphManagerEditor ('+' button) or opens an existing file via the
FileBrowserEditor.
"""

import logging
import os
from pathlib import Path

from nicegui import ui, app

# Core imports
from haywire.core.graph.editor import Editor
from haywire.core.graph.base import BaseGraph
from haywire.core.graph.types import ValidationResult, ChangeReason
from haywire.core.undo.config import DEVELOPMENT_CONFIG
from haywire.core.execution import Interpreter
from haywire.core.execution.interpreter_loop_manager import InterpreterLoopManager
from haywire.core.di.config import create_library_system_service, set_library_system, set_global_injector

# UI imports
from haywire.ui.console_bridge import ConsoleBridge
from haywire.ui.themes import ThemePalette

# Change reasons that are pure UI state — they do NOT dirty the graph data.
_SELECTION_ONLY_REASONS = frozenset({
    ChangeReason.NODE_SELECTED,
    ChangeReason.NODE_DESELECTED,
    ChangeReason.EDGE_SELECTED,
    ChangeReason.EDGE_DESELECTED,
})


def _result_mutates_data(result: ValidationResult) -> bool:
    """Return True if the validation result contains changes that affect saved graph data."""
    return (
        any(r not in _SELECTION_ONLY_REASONS for r in result.nodes.values())
        or any(r not in _SELECTION_ONLY_REASONS for r in result.edges.values())
    )


class HaywireApp:
    """Main Haywire application."""

    def __init__(self, workspace_root: str = None):
        self.workspace_root = workspace_root or os.getcwd()
        print(f"Haywire workspace: {self.workspace_root}")
        print("Setting up Haywire application...")

        self.setup_library_system()
        self.setup_shared_services()

        # Per-client session bookkeeping (client_id → session_data dict)
        self.sessions: dict = {}
        self._is_shutting_down = False

        app.on_disconnect(self.on_disconnect)
        app.on_shutdown(self.on_app_shutdown)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_app_shutdown(self):
        """Clean up all resources on application shutdown."""
        if self._is_shutting_down:
            return
        self._is_shutting_down = True
        print("Application shutdown initiated...")

        # 1. Stop interpreter loop
        if self.loop_manager and self.loop_manager.is_running:
            print("  Stopping interpreter loop...")
            self.stop_interpreter()

        # 2. Clean up all sessions
        print(f"  Cleaning up {len(self.sessions)} sessions...")
        for client_id in list(self.sessions.keys()):
            try:
                self._cleanup_session(client_id)
            except Exception as e:
                print(f"  Error cleaning up session {client_id[:8]}: {e}")

        # 3. Clean up graph manager
        try:
            if hasattr(self, 'graph_manager'):
                self.graph_manager.cleanup()
        except Exception as e:
            print(f"  Error cleaning up graph manager: {e}")

        # 4. Unregister theme observer
        try:
            ThemePalette.unregister_observer(self._on_theme_changed)
        except Exception as e:
            print(f"  Error unregistering theme observer: {e}")

        # 5. Clean up console bridge
        try:
            bridge = ConsoleBridge.get_instance()
            bridge.log_elements.clear()
            bridge.clear_history()
        except Exception as e:
            print(f"  Error cleaning up console bridge: {e}")

        # 6. Shutdown interpreter
        try:
            if self.interpreter:
                self.interpreter.shutdown()
        except Exception as e:
            print(f"  Error shutting down interpreter: {e}")

        # 7. Cleanup library system
        try:
            if hasattr(self.library_service, 'cleanup'):
                self.library_service.cleanup()
        except Exception as e:
            print(f"  Error cleaning up library system: {e}")

        print("Application shutdown complete")

    def _cleanup_session(self, client_id: str):
        """Clean up a single session's resources."""
        if client_id not in self.sessions:
            return

        session_data = self.sessions[client_id]
        print(f"    Cleaning up session {client_id[:8]}...")

        # Cancel any lingering interpreter timer
        interpreter_timer = session_data.get('interpreter_timer')
        if interpreter_timer:
            try:
                interpreter_timer.cancel()
            except Exception as e:
                print(f"    Error canceling interpreter timer: {e}")

        # Unregister console log
        console_log = session_data.get('console_log')
        console_timer = session_data.get('console_timer')
        if console_log:
            try:
                bridge = ConsoleBridge.get_instance()
                bridge.unregister_log(console_log)
            except Exception as e:
                print(f"    Error unregistering console log: {e}")
        elif console_timer:
            try:
                console_timer.cancel()
            except Exception as e:
                print(f"    Error canceling console timer: {e}")

        # Clean up Haywire Session (editors, context subscribers)
        haywire_session = session_data.get('haywire_session')
        if haywire_session:
            haywire_session_id = session_data.get('haywire_session_id')
            if haywire_session_id and hasattr(self, 'session_manager'):
                try:
                    self.session_manager.remove_session(haywire_session_id)
                except Exception as e:
                    print(f"    Error removing session from manager: {e}")
            else:
                try:
                    haywire_session.cleanup()
                except Exception as e:
                    print(f"    Error cleaning up haywire session: {e}")

        del self.sessions[client_id]

    def on_disconnect(self, client):
        """Handle client disconnect."""
        if self._is_shutting_down:
            return
        client_id = getattr(client, 'id', None)
        if client_id and client_id in self.sessions:
            print(f"Client disconnected: {client_id[:8]}")
            self._cleanup_session(client_id)
            print(f"Session {client_id[:8]} cleaned up")

    def get_session_data(self):
        """Get or create per-client session bookkeeping data."""
        from nicegui import context

        client_id = context.client.id if context.client else 'default'
        if client_id not in self.sessions:
            print(f"Creating new session for client: {client_id}")
            self.sessions[client_id] = {
                'client': context.client,
                'ui_containers': {},
            }
        return self.sessions[client_id], client_id

    # ------------------------------------------------------------------
    # Shared services setup
    # ------------------------------------------------------------------

    def setup_library_system(self):
        """Initialize the library system service (shared across sessions)."""
        self.undo_config = DEVELOPMENT_CONFIG

        library_paths = []
        workspace_libs = os.path.join(self.workspace_root, 'barn')
        if os.path.isdir(workspace_libs):
            library_paths.append(workspace_libs)

        self.library_service = create_library_system_service(
            project_root=self.workspace_root,
            library_paths=library_paths if library_paths else None,
            enable_file_watching=True,
            watch_settings=False,
            undo_config=self.undo_config,
        )
        set_library_system(self.library_service)
        set_global_injector(self.library_service.injector)
        print("Library system initialized.")

    def setup_shared_services(self):
        """Setup services shared across all sessions."""
        from haywire.ui.session_manager import SessionManager

        self.session_manager = SessionManager()

        # Registries and factories (from DI)
        self.node_registry = self.library_service.get_node_registry()
        self.node_factory = self.library_service.get_node_factory()
        self.skin_factory = self.library_service.get_skin_factory()
        self.adapter_factory = self.library_service.get_adapter_factory()
        self.history_manager = self.library_service.get_history_manager()

        # Interpreter
        self.interpreter = Interpreter()
        self.loop_manager = InterpreterLoopManager(
            interpreter=self.interpreter,
            target_fps=60.0,
        )

        # Theme
        self.theme_palette = self.library_service.get_theme_palette()
        ThemePalette.register_observer(self._on_theme_changed)

        # Graph manager — starts empty; graphs are created/opened on demand
        from .graph_manager import GraphManager
        self.graph_manager = GraphManager()

        # Library manager
        from .library_manager import LibraryManager
        library_registry = self.library_service.get_library_registry()
        self.library_manager = LibraryManager(
            library_registry,
            project_dir=self.workspace_root,
        )
        self.library_manager.apply_persisted_state()

        # Register app-level editors into the shared EditorTypeRegistry
        from haywire.ui.editor.registry import EditorTypeRegistry
        from .editors.library_browser import LibraryBrowser
        from .editors.library_detail_editor import LibraryDetailEditor
        from .editors.component_detail_editor import ComponentDetailEditor
        from .editors.file_browser import FileBrowserEditor
        from .editors.file_viewer import FileViewerEditor
        from .editors.graph_manager_editor import GraphManagerEditor
        _editor_registry = self.library_service.injector.get(EditorTypeRegistry)
        for _cls in [
            LibraryBrowser, LibraryDetailEditor, ComponentDetailEditor,
            FileBrowserEditor, FileViewerEditor, GraphManagerEditor,
        ]:
            _editor_registry._register_class(_cls, library_identity=None)

        print("Shared services configured successfully.")

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------

    def _on_theme_changed(self, theme_name: str, theme):
        """Handle theme change — new-style sessions update themselves."""
        print(f"Theme changed to: {theme_name}")

    def switch_theme(self, theme_name: str):
        """Switch to a named theme."""
        ui.notify(f"Switching to {theme_name} theme...", type='info')
        def _do():
            if not ThemePalette.set_theme(theme_name):
                ui.notify(f"Failed to load {theme_name} theme", type='negative')
        ui.timer(0.05, _do, once=True)

    def reload_theme(self):
        """Reload the current theme from disk."""
        current_name = ThemePalette.get_theme_name()
        ui.notify(f"Reloading {current_name} theme...", type='info')
        def _do():
            if not ThemePalette.reload_current_theme():
                ui.notify("Failed to reload theme", type='negative')
        ui.timer(0.05, _do, once=True)

    # ------------------------------------------------------------------
    # Graph management (called by editors)
    # ------------------------------------------------------------------

    def open_graph_file(self, path: Path, session_id: str):
        """
        Open a .haywire file, creating or reusing a GraphEntry.

        Subscribes the validation/broadcast handler on first open.
        Attaches the session to the entry and returns it.
        """
        def _factory(graph_id: str, name: str):
            g = BaseGraph(graph_id, name)
            e = Editor(g)
            return g, e

        entry = self.graph_manager.open_graph(path, _factory)

        # Subscribe only the first time this file is opened
        if not entry.sessions:
            def _handler(result, _path=path, _entry=entry):
                self._on_graph_validation_for_interpreter(result)
                if _result_mutates_data(result):
                    _entry.unsaved = True
                    if hasattr(self, 'session_manager'):
                        try:
                            self.session_manager.broadcast_data_mutation(graph_path=_path)
                        except Exception as exc:
                            print(f"Error broadcasting for {_path.name}: {exc}")
            entry.graph.subscribe_to_validation(_handler)

        self.graph_manager.session_attach(entry, session_id)
        return entry

    def create_new_graph(self, session_id: str):
        """
        Create a new unnamed graph and attach a session to it.

        Produces a unique '__new_N__' entry in the GraphManager.
        """
        def _factory(graph_id: str, name: str):
            g = BaseGraph(graph_id, name)
            e = Editor(g)
            return g, e

        entry = self.graph_manager.create_new(_factory)

        def _handler(result, _entry=entry):
            self._on_graph_validation_for_interpreter(result)
            if _result_mutates_data(result):
                _entry.unsaved = True
                if hasattr(self, 'session_manager'):
                    try:
                        self.session_manager.broadcast_data_mutation(graph_path=_entry.path)
                    except Exception as exc:
                        print(f"Error broadcasting for new graph {_entry.key}: {exc}")

        entry.graph.subscribe_to_validation(_handler)
        self.graph_manager.session_attach(entry, session_id)
        return entry

    # ------------------------------------------------------------------
    # Interpreter
    # ------------------------------------------------------------------

    def _on_graph_validation_for_interpreter(self, result: ValidationResult):
        """Stop the interpreter when a graph change requires reassembly."""
        if not self.loop_manager or not self.loop_manager.is_running:
            return
        if (
            result.has_changes()
            and result.graph is not None
            and result.graph.requires_graph_reassembly()
        ):
            self.stop_interpreter()

    def stop_interpreter(self):
        """Stop the interpreter loop."""
        self.loop_manager.stop()
        try:
            self.interpreter.wait_all(timeout=2.0)
        except Exception as e:
            print(f"Error waiting for flows: {e}")
        print("Interpreter loop stopped")

    # ------------------------------------------------------------------
    # UI creation
    # ------------------------------------------------------------------

    def setup_services(self):
        """Stub kept for compatibility."""
        pass

    def create_ui(self):
        """Register NiceGUI page routes."""

        @ui.page('/libraries', title="Library Manager")
        def libraries_page():
            from .library_manager_ui import LibraryManagerPage
            marketplace_path = Path(self.workspace_root) / '.haywire' / 'marketplace.toml'
            page = LibraryManagerPage(
                self.library_manager,
                marketplace_path=str(marketplace_path) if marketplace_path.exists() else None,
                node_registry=self.node_registry,
                widget_registry=self.library_service.get_widget_registry(),
                type_registry=self.library_service.get_type_registry(),
                adapter_registry=self.library_service.get_adapter_registry(),
                skin_registry=self.library_service.get_skin_registry(),
            )
            page.create_page()

        @ui.page('/', title="Haywire")
        def main_page():
            from haywire.ui.app_shell import AppShell
            from haywire.ui.editor.registry import EditorTypeRegistry
            from haywire.ui.panel.registry import PanelRegistry

            session_data, client_id = self.get_session_data()
            print(f"Creating UI for session: {client_id[:8]}")

            haywire_session = self.session_manager.create_session(
                project_state=self,
                project_path=Path(self.workspace_root),
            )
            haywire_session.context.metadata['project_state'] = self
            haywire_session.context.metadata['panel_registry'] = (
                self.library_service.injector.get(PanelRegistry)
            )
            haywire_session.context.metadata['haywire_session'] = haywire_session

            session_data['haywire_session'] = haywire_session
            session_data['haywire_session_id'] = haywire_session.session_id

            # No graph is active at startup — context.active_graph and
            # context.active_graph_path both remain None.  The user opens or
            # creates a graph via GraphManagerEditor or FileBrowserEditor.

            editor_registry = self.library_service.injector.get(EditorTypeRegistry)
            app_shell = AppShell(haywire_session, editor_registry=editor_registry)
            app_shell.render()

    # ------------------------------------------------------------------
    # Run / cleanup
    # ------------------------------------------------------------------

    def cleanup(self):
        """Manual cleanup fallback."""
        self.on_app_shutdown()

    def run(self):
        """Run the application."""
        print("Starting Haywire...")
        self.create_ui()
        try:
            ui.run(
                port=8082,
                show=True,
                title="Haywire",
                reload=False,
            )
        except KeyboardInterrupt:
            print("\nKeyboard interrupt received")
        finally:
            if not self._is_shutting_down:
                self.cleanup()


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

def run_app():
    """Launch the Haywire application."""
    logging.getLogger('haywire.ui.editor.graph_canvas_manager').setLevel(logging.DEBUG)
    app_instance = HaywireApp()
    app.on_shutdown(app_instance.cleanup)
    app_instance.run()


def main():
    """Main entry point — routes CLI subcommands."""
    import argparse

    parser = argparse.ArgumentParser(
        prog='haywire',
        description='Haywire visual programming system',
    )
    subparsers = parser.add_subparsers(dest='command')

    init_parser = subparsers.add_parser('init', help='Create a new haywire project')
    init_parser.add_argument('name', help='Project name')
    init_parser.add_argument(
        '--no-sync', action='store_true',
        help='Skip running uv sync after scaffolding',
    )
    init_parser.add_argument(
        '--dev', action='store_true',
        help='Use editable local sources from this dev repo instead of PyPI',
    )

    share_parser = subparsers.add_parser(
        'share', help='Generate a marketplace.toml snippet for sharing a library'
    )
    share_parser.add_argument(
        'library_path', nargs='?', default=None,
        help='Path to the library directory (e.g. libs/haybale-myproject). '
             'Auto-detected if libs/ contains exactly one library.',
    )

    args = parser.parse_args()

    if args.command == 'init':
        from .init import init_project, _get_dev_repo_root
        dev_repo = _get_dev_repo_root() if args.dev else None
        init_project(args.name, auto_sync=not args.no_sync, dev_repo=dev_repo)
    elif args.command == 'share':
        from .share import share_library
        share_library(args.library_path)
    else:
        run_app()


if __name__ in {"__main__", "__mp_main__"}:
    main()
