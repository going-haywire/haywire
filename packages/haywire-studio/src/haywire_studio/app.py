"""
HaywireApp — main application entry point.

Manages shared services (graph manager, libraries) and per-session UI shells.
Each browser connection gets its own Session and AppShell; all sessions share
the same library registry and Haystack.

Execution is per-graph: each GraphEntry owns its own Interpreter,
started/stopped via entry.start_execution() / entry.stop_execution().

On startup the last-used haystack (if any) is auto-loaded from
``workspace_state.json``.  Otherwise the app starts with no graphs open.
"""

import os
import logging
from pathlib import Path

from nicegui import ui, app

# Core imports
from haywire.core.graph.editor import Editor
from haywire.core.graph.base import BaseGraph
from haywire.core.undo.config import DEVELOPMENT_CONFIG
from haywire.core.di.config import create_library_system_service, set_library_system, set_global_injector

# UI imports
from haywire.ui.console_bridge import get_bridge

logger = logging.getLogger(__name__)


class HaywireApp:
    """Main Haywire application."""

    def __init__(self, workspace_root: str = None):
        self.workspace_root = workspace_root or os.getcwd()
        print(f"Haywire workspace: {self.workspace_root}")
        print("Setting up Haywire application...")

        self.setup_library_system()
        self.setup_shared_services()

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

        # 1. Clean up all sessions
        print(f"  Cleaning up {self.session_manager.session_count} sessions...")
        self.session_manager.cleanup_all()

        # 2. Clean up graph manager (stops per-graph interpreters, clears entries)
        try:
            if hasattr(self, "haystack"):
                self.haystack.cleanup()
        except Exception as e:
            print(f"  Error cleaning up graph manager: {e}")

        # 3. Clean up console bridge
        try:
            bridge = get_bridge()
            bridge.log_elements.clear()
            bridge.clear_history()
        except Exception as e:
            print(f"  Error cleaning up console bridge: {e}")

        # 4. Cleanup library system
        try:
            if hasattr(self.library_service, "cleanup"):
                self.library_service.cleanup()
        except Exception as e:
            print(f"  Error cleaning up library system: {e}")

        print("Application shutdown complete")

    def on_disconnect(self, client):
        """Handle client disconnect."""
        if self._is_shutting_down:
            return
        session_id = getattr(client, "_haywire_session_id", None)
        if session_id:
            print(f"Client disconnected, cleaning up session {session_id[:8]}")
            self.session_manager.remove_session(session_id)

    # ------------------------------------------------------------------
    # Shared services setup
    # ------------------------------------------------------------------

    def setup_library_system(self):
        """Initialize the library system service (shared across sessions)."""
        self.undo_config = DEVELOPMENT_CONFIG

        library_paths = []
        workspace_libs = os.path.join(self.workspace_root, "barn")
        if os.path.isdir(workspace_libs):
            library_paths.append(workspace_libs)

        self.library_service = create_library_system_service(
            workspace_root=self.workspace_root,
            library_paths=library_paths if library_paths else None,
            enable_file_watching=True,
            watch_settings=False,
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
        self.panel_registry = self.library_service.get_panel_registry()

        # Graph manager — starts empty; graphs are created/opened on demand.
        # Haystack auto-load is deferred to main_page so it can guard against
        # multiple sessions reconnecting to an already-populated haystack.
        from .haystack import Haystack

        self.haystack = Haystack(
            workspace_root=Path(self.workspace_root),
            graph_factory=self._graph_factory,
            session_manager=self.session_manager,
        )

        from haywire.ui.workspace.manager import WorkspaceManager

        self.workspace_manager = WorkspaceManager(project_path=Path(self.workspace_root))

        # Library manager
        from .library_manager import LibraryManager

        library_registry = self.library_service.get_library_registry()
        self.library_manager = LibraryManager(
            library_registry,
            project_dir=self.workspace_root,
        )
        self.library_manager.apply_persisted_state()

        print("Shared services configured successfully.")

    # ------------------------------------------------------------------
    # Graph factory (shared by Haystack)
    # ------------------------------------------------------------------

    def _graph_factory(self, graph_id: str, name: str) -> tuple[BaseGraph, Editor]:
        """Standard factory producing (BaseGraph, Editor) pairs."""
        g = BaseGraph(graph_id, name)
        e = Editor(g, self.node_factory, undo_config=self.undo_config)
        return g, e

    # ------------------------------------------------------------------
    # Haystack auto-load
    # ------------------------------------------------------------------

    def try_load_startup_haystack(self) -> None:
        """Load the last-used haystack on startup (if configured)."""
        haystack_name = self.workspace_manager.snapshot.get("haystack")
        if not haystack_name:
            return
        if self.haystack.all_entries():
            return
        try:
            self.haystack.load_haystack(haystack_name)
            logger.info(f"Startup haystack '{haystack_name}' loaded")
        except Exception as exc:
            logger.warning(f"Failed to load startup haystack '{haystack_name}': {exc}")

    def save_workspace(self, shell=None, active_graph_path=None) -> None:
        """Save haystack and workspace snapshot atomically.

        Args:
            shell: The active AppShell. When provided, collects the current slot
                snapshot from it. When None, re-saves the existing snapshot.
            active_graph_path: Path of the currently active graph to store in
                the haystack TOML.
        """
        haystack_name = self.workspace_manager.snapshot.get("haystack") or "default"
        self.haystack.save_haystack(haystack_name, active_graph_path=active_graph_path)
        snapshot = self.workspace_manager.snapshot.copy()
        if shell is not None:
            slot_data = shell.collect_snapshot()
            snapshot.update(slot_data)
            snapshot["haystack"] = haystack_name
        self.workspace_manager.save(snapshot)

    # ------------------------------------------------------------------
    # UI creation
    # ------------------------------------------------------------------

    def setup_services(self):
        """Stub kept for compatibility."""
        pass

    def create_ui(self):
        """Register NiceGUI page routes."""

        @ui.page("/", title="Haywire")
        def main_page():
            from haywire.ui.app.shell import AppShell
            from haywire.ui.editor.registry import EditorTypeRegistry
            from nicegui import context

            print(f"Creating UI for session: {context.client.id[:8]}")

            editor_registry = self.library_service.injector.get(EditorTypeRegistry)

            # Only load haystack on first session connect
            if not self.haystack.all_entries():
                self.try_load_startup_haystack()

            haywire_session = self.session_manager.create_session(
                project_state=self,
                workspace_manager=self.workspace_manager,
            )

            # Store session ID on NiceGUI Client for disconnect lookup
            context.client._haywire_session_id = haywire_session.session_id

            # Set studio theme defaults on context before rendering
            haywire_session.context.active_workbench_theme_key = "core:theme:workbench:haywire-dark"
            haywire_session.context.active_node_theme_key = "core:theme:node:default"

            app_shell = AppShell(haywire_session, editor_registry=editor_registry)
            haywire_session.set_shell(app_shell)
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
    # logging.getLogger("haywire.ui.editor.graph_canvas_manager").setLevel(logging.DEBUG)
    # use DebugSettings.log_ui instead
    app_instance = HaywireApp()
    app.on_shutdown(app_instance.cleanup)
    app_instance.run()


def main():
    """Main entry point — routes CLI subcommands."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="haywire",
        description="Haywire visual programming system",
    )
    subparsers = parser.add_subparsers(dest="command")

    init_parser = subparsers.add_parser("init", help="Create a new haywire project")
    init_parser.add_argument("name", help="Project name")
    init_parser.add_argument(
        "--no-sync",
        action="store_true",
        help="Skip running uv sync after scaffolding",
    )
    init_parser.add_argument(
        "--dev",
        action="store_true",
        help="Use editable local sources from this dev repo instead of PyPI",
    )

    share_parser = subparsers.add_parser(
        "share", help="Generate a marketplace.toml snippet for sharing a library"
    )
    share_parser.add_argument(
        "library_path",
        nargs="?",
        default=None,
        help="Path to the library directory (e.g. libs/haybale-myproject). "
        "Auto-detected if libs/ contains exactly one library.",
    )

    args = parser.parse_args()

    if args.command == "init":
        from .init import init_project, _get_dev_repo_root

        dev_repo = _get_dev_repo_root() if args.dev else None
        init_project(args.name, auto_sync=not args.no_sync, dev_repo=dev_repo)
    elif args.command == "share":
        from .share import share_library

        share_library(args.library_path)
    else:
        run_app()


if __name__ in {"__main__", "__mp_main__"}:
    main()
