"""
HaywireApp — main application entry point.

Manages shared services (libraries) and per-session UI shells.
Each browser connection gets its own Session and AppShell; all sessions share
the same library registry.

Execution is per-graph: each GraphEntry owns its own Interpreter,
started/stopped via entry.start_execution() / entry.stop_execution().

Haystack lifecycle (open graphs, auto-load on startup) is handled by
HaystackState, accessed via ctx.app_data[HaystackState].
"""

import os
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from nicegui import ui, app

if TYPE_CHECKING:
    from haywire.ui.app.shell import AppShell

# Core imports
from haywire.core.graph.editor import Editor
from haywire.core.graph.base import BaseGraph
from haywire.core.undo.config import DEVELOPMENT_CONFIG
from haywire.core.di.config import create_library_system_service, set_library_system, set_global_injector
from haywire.core.di.context import set_workspace_root

# UI imports
from haywire.ui.console_bridge import get_bridge

logger = logging.getLogger(__name__)


class HaywireApp:
    """Main Haywire application.

    Constructs shared services (library system, session manager, workspace manager)
    and registers per-session UI shells.  Graph/haystack lifecycle is delegated
    to HaystackState (accessed via ctx.app_data[HaystackState]).
    """

    def __init__(self, workspace_root: str | None = None):
        self.workspace_root = workspace_root or os.getcwd()
        set_workspace_root(self.workspace_root)
        print(f"Haywire workspace: {self.workspace_root}")
        print("Setting up Haywire application...")

        self.setup_library_system()
        self.setup_shared_services()

        self._is_shutting_down = False
        self._shells: dict[str, "AppShell"] = {}

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

        # 2. Clean up console bridge
        try:
            bridge = get_bridge()
            bridge.log_elements.clear()
            bridge.clear_history()
        except Exception as e:
            print(f"  Error cleaning up console bridge: {e}")

        # 3. Cleanup library system
        try:
            if hasattr(self.library_service, "cleanup"):
                self.library_service.cleanup()
        except Exception as e:
            print(f"  Error cleaning up library system: {e}")

        print("Application shutdown complete")

    def on_disconnect(self, client):
        """Handle client disconnect.

        Shell-upstream model (Q7A): tear down the AppShell first, then
        detach the session. SessionManager.remove_session does only state
        cleanup now — UI cleanup is the shell's responsibility.
        """
        if self._is_shutting_down:
            return
        session_id = getattr(client, "_haywire_session_id", None)
        if not session_id:
            return
        print(f"Client disconnected, cleaning up session {session_id[:8]}")

        shell = self._shells.pop(session_id, None)
        if shell is not None:
            try:
                shell.cleanup()
            except Exception as e:
                print(f"  Error cleaning up shell for session {session_id[:8]}: {e}")

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
        from haywire.core.state import LibraryStateContainer
        from haywire.core.session.session_manager import SessionManager

        # Registries and factories (from DI)
        self.node_registry = self.library_service.get_node_registry()
        self.node_factory = self.library_service.get_node_factory()
        self.skin_factory = self.library_service.get_skin_factory()
        self.adapter_factory = self.library_service.get_adapter_factory()
        self.panel_registry = self.library_service.get_panel_registry()
        self.library_state_container = self.library_service.injector.get(LibraryStateContainer)

        # SessionManager comes from the DI container; provide_session_manager()
        # also publishes it via set_session_manager() into the ambient context.
        self.session_manager = self.library_service.injector.get(SessionManager)

        from haywire.core.session.workspace.manager import WorkspaceManager

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
    # Graph factory
    # ------------------------------------------------------------------

    def _graph_factory(self, graph_id: str, name: str) -> tuple[BaseGraph, Editor]:
        """Standard factory producing (BaseGraph, Editor) pairs."""
        g = BaseGraph(graph_id, name)
        e = Editor(g, self.node_factory, undo_config=self.undo_config)
        return g, e

    def save_workspace(self, shell=None, active_graph_path=None) -> None:
        """Save workspace snapshot atomically.

        Args:
            shell: The active AppShell. When provided, collects the current slot
                snapshot from it. When None, re-saves the existing snapshot.
            active_graph_path: Path of the currently active graph (unused here;
                retained for call-site compatibility — callers that need to persist
                haystack state call persistence.dump_haystack before this).
        """
        snapshot = self.workspace_manager.snapshot.copy()
        if shell is not None:
            slot_data = shell.collect_snapshot()
            snapshot.update(slot_data)
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

            haywire_session = self.session_manager.create_session(
                project_state=self,
                workspace_manager=self.workspace_manager,
            )

            # Store session ID on NiceGUI Client for disconnect lookup
            context.client._haywire_session_id = haywire_session.session_id

            # Set studio theme defaults on context before rendering
            haywire_session.context.active_workbench_theme_key.value = "core:theme:workbench:haywire-dark"
            haywire_session.context.active_node_theme_key.value = "core:theme:node:default"

            app_shell = AppShell(haywire_session, editor_registry=editor_registry)
            self._shells[haywire_session.session_id] = app_shell
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
