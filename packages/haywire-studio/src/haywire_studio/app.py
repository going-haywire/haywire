import asyncio
import os
import logging
from pathlib import Path
from typing import Callable, Optional, TYPE_CHECKING

from nicegui import ui, app

# Core imports
from haywire.core.undo.config import DEVELOPMENT_CONFIG
from haywire.core.di.config import create_library_system_service
from haywire.core.di.context import set_workspace_root
from haywire.core.errors.ledger import get_error_ledger
from haywire.core.host import HostStore
from haywire.core.session.signals import ErrorLogged

# UI imports
from haywire.ui.console_bridge import get_stdout_tee

from haywire.ui.extends.codemirror import register_code_intelligence_render_endpoint

from .code_intelligence import register_code_intelligence_endpoints

if TYPE_CHECKING:
    from haywire.ui.app.shell import AppShell

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

        # Patch NiceGUI internals (e.g. cache expects_arguments) before any
        # rendering. See haywire.ui.nicegui_patches.
        # apply_nicegui_patches()

        register_code_intelligence_endpoints()
        register_code_intelligence_render_endpoint()

        self.setup_library_system()
        self.setup_shared_services()

        self._is_shutting_down = False
        self._shells: dict[str, "AppShell"] = {}
        # Maps NiceGUI client.id → haywire session_id so on_disconnect can
        # resolve which session to tear down without monkey-patching the
        # Client object.
        self._client_to_session: dict[str, str] = {}

        # Bridge: process-wide error ledger → cross-session ErrorLogged signal.
        # Wired in on_startup (first moment a running loop exists), torn down in
        # on_app_shutdown. Holds the listener ref so remove_listener can undo it.
        self._error_ledger_listener: Optional[Callable[[], None]] = None

        app.on_disconnect(self.on_disconnect)
        app.on_shutdown(self.on_app_shutdown)
        app.on_startup(self._wire_error_ledger_broadcast)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _wire_error_ledger_broadcast(self) -> None:
        """Bridge the process-wide error ledger to a cross-session ErrorLogged signal.

        Runs once from ``app.on_startup`` — the first lifecycle callback inside
        the running event loop, so ``get_running_loop()`` is valid here (DI /
        setup_shared_services ran before ``ui.run()`` and had no loop). The
        ledger's zero-arg listener fires on any thread (watchdog/scan); we hop
        back onto the loop with ``call_soon_threadsafe`` before touching the
        single-threaded SignalBus via ``SessionManager.broadcast``.
        """
        loop = asyncio.get_running_loop()

        def _on_error_logged() -> None:
            loop.call_soon_threadsafe(lambda: self.session_manager.broadcast(ErrorLogged()))

        self._error_ledger_listener = _on_error_logged
        get_error_ledger().add_listener(_on_error_logged)

    def on_app_shutdown(self):
        """Clean up all resources on application shutdown."""
        if self._is_shutting_down:
            return
        self._is_shutting_down = True
        print("Application shutdown initiated...")

        # 1. Clean up all sessions
        print(f"  Cleaning up {self.session_manager.session_count} sessions...")
        self.session_manager.cleanup_all()

        # 2. Clean up stdout tee history (sinks are detached by each editor's own cleanup())
        try:
            get_stdout_tee().clear_history()
        except Exception as e:
            print(f"  Error clearing stdout tee history: {e}")

        # 3. Unwire the error-ledger → ErrorLogged bridge (mirrors console bridge).
        if self._error_ledger_listener is not None:
            try:
                get_error_ledger().remove_listener(self._error_ledger_listener)
            except Exception as e:
                print(f"  Error removing error-ledger listener: {e}")
            self._error_ledger_listener = None

        print("Application shutdown complete")

    def on_disconnect(self, client):
        """Handle client disconnect.

        Shell-upstream model (Q7A): tear down the AppShell first, then
        detach the session. SessionManager.remove_session does only state
        cleanup now — UI cleanup is the shell's responsibility.
        """
        if self._is_shutting_down:
            return
        session_id = self._client_to_session.pop(client.id, None)
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

        # HostStore — engine bootstrap persistence the LibraryRegistry uses
        # to remember which libraries the user has disabled. File-backed
        # because this is a real workspace; an embedded / headless host
        # could pass HostStore.in_memory() or omit the argument entirely.
        host_store = HostStore(Path(self.workspace_root) / ".haywire" / "host.toml")

        # create_library_system_service.initialize() publishes both the
        # service (via set_library_system) and the injector (via
        # set_global_injector) BEFORE the enable phase, so AppState.on_enable
        # hooks can resolve framework services from the ambient context.
        self.library_service = create_library_system_service(
            workspace_root=self.workspace_root,
            library_paths=library_paths if library_paths else None,
            enable_file_watching=True,
            watch_settings=False,
            host_store=host_store,
        )
        print("Library system initialized.")

    def setup_shared_services(self):
        """Setup services shared across all sessions."""
        from haywire.core.state import LibraryStateContainer
        from haywire.core.session.session_manager import SessionManager

        # Registries and factories (from DI)
        self.node_registry = self.library_service.get_node_registry()
        self.node_factory = self.library_service.get_node_factory()
        self.skin_factory = self.library_service.get_skin_factory()
        self.widget_factory = self.library_service.get_widget_factory()
        self.adapter_factory = self.library_service.get_adapter_factory()
        self.panel_registry = self.library_service.get_panel_registry()
        self.library_state_container = self.library_service.injector.get(LibraryStateContainer)

        # SessionManager comes from the DI container; provide_session_manager()
        # also publishes it via set_session_manager() into the ambient context.
        self.session_manager = self.library_service.injector.get(SessionManager)

        from haywire.core.session.workspace.manager import WorkspaceManager

        self.workspace_manager = WorkspaceManager(project_path=Path(self.workspace_root))

        # LibraryManager is now published by haybale-marketplace as
        # LibraryManagerState. Persisted disabled-state is applied by the
        # library system during create_library_system_service. See ADR-0001.

        print("Shared services configured successfully.")

    def setup_farmhand(self, port: int) -> None:
        """Mount the Farmhand MCP server if enabled (flag read once; restart to apply)."""
        from haywire_studio.farmhand.host import FarmhandHost
        from haywire_studio.farmhand.settings import FarmhandSettings

        if not FarmhandSettings().enabled:
            logging.getLogger(__name__).info("Farmhand: disabled by settings (farmhand.enabled = false)")
            return
        self.farmhand_host = FarmhandHost(self.library_service, self.workspace_root)
        self.farmhand_host.mount(port)

        # Write the sidecar identity file so a later process (the farmhand4claude
        # plugin startup script) can identify which project owns this studio on
        # this port. Must never break studio launch.
        from pathlib import Path

        from haywire_studio.farmhand.identity import write_identity

        try:
            write_identity(Path(self.workspace_root), port)
        except Exception:
            logging.getLogger(__name__).warning(
                "Farmhand: failed to write studio identity sidecar", exc_info=True
            )

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

            # Map this client to its session so on_disconnect can resolve
            # which session to tear down.
            self._client_to_session[context.client.id] = haywire_session.session_id

            # Set studio theme defaults on context before rendering
            haywire_session.context.active_workbench_theme_key = "core:theme:workbench:haywire-dark"
            haywire_session.context.active_node_theme_key = "core:theme:node:default"

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
        from haywire_studio.network.settings import NetworkSettings

        port = NetworkSettings().port
        # Mount the Farmhand MCP server on the same port before ui.run (flag read once).
        self.setup_farmhand(port)
        try:
            ui.run(
                port=port,
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

    # Install before HaywireApp() is constructed so the workspace banner and
    # library-system banner (printed during __init__) reach the Log panel too.
    # uvicorn also resolves ext://sys.stdout when it applies its logging config,
    # so this must happen before that config is built.
    get_stdout_tee().install()

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
        "share",
        help="Publish this project: bump every barn library, regenerate docs, "
        "rebuild marketstall.toml, commit, tag, and push",
    )
    share_parser.add_argument(
        "--yes",
        action="store_true",
        help="Non-interactive full run using flag-supplied answers. Requires --bump.",
    )
    share_parser.add_argument(
        "--bump",
        type=str,
        default=None,
        metavar="VERSION",
        help="Version to publish: patch|minor|major, or an explicit X.Y.Z. Every "
        "barn/* library is set to it (lockstep).",
    )
    share_parser.add_argument(
        "--message",
        type=str,
        default=None,
        help="Commit message. Defaults to 'chore: share v<version>'.",
    )

    rename_parser = subparsers.add_parser(
        "rename", help="Rename a project library (run with studio stopped)"
    )
    rename_parser.add_argument("old_library", help="Current library dir, e.g. haybale-foo")
    rename_parser.add_argument("new_name", help="New name (without the haybale- prefix)")
    rename_parser.add_argument(
        "--apply",
        action="store_true",
        help="Perform the rename. Without this flag, only a dry-run preview is printed.",
    )

    deps_parser = subparsers.add_parser("deps", help="Dependency-manifest tooling")
    deps_subparsers = deps_parser.add_subparsers(dest="deps_command")
    deps_subparsers.add_parser(
        "check",
        help="Report dependency-manifest drift for every barn/* library (CI-shaped, never writes)",
    )

    docs_parser = subparsers.add_parser("docs", help="Generate deterministic docs for a haybale library")
    docs_parser.add_argument(
        "library",
        nargs="?",
        default=None,
        help=(
            "Path to the library package root, or (with --all) the repo root to scan"
            " — default: current directory"
        ),
    )
    docs_parser.add_argument(
        "--all",
        action="store_true",
        help="Generate docs for every in-repo library (barn/* + builtin) in one load",
    )
    docs_parser.add_argument(
        "--json",
        type=str,
        default=None,
        metavar="PATH",
        help="Write the coverage report to PATH as JSON ({library_id: [lines]}). "
        "A file sink rather than stdout, because a library-system boot prints "
        "freely to stdout and not all of it is ours.",
    )

    args = parser.parse_args()

    if args.command == "init":
        from .init import init_project, _get_dev_repo_root

        dev_repo = _get_dev_repo_root() if args.dev else None
        init_project(args.name, auto_sync=not args.no_sync, dev_repo=dev_repo)
    elif args.command == "share":
        from pathlib import Path

        from haywire_studio.share.cli import run_share_cli

        raise SystemExit(
            run_share_cli(
                repo_root=Path.cwd(),
                yes=args.yes,
                bump=args.bump,
                message=args.message,
            )
        )
    elif args.command == "rename":
        from pathlib import Path

        from haywire_studio.rename import run_rename_cli

        raise SystemExit(
            run_rename_cli(
                old_library=args.old_library,
                new_name=args.new_name,
                workspace_root=Path.cwd(),
                apply=args.apply,
            )
        )
    elif args.command == "deps":
        from pathlib import Path

        from haywire_studio.deps_cli import run_deps_check_cli

        if args.deps_command == "check":
            raise SystemExit(run_deps_check_cli(Path.cwd()))
        deps_parser.print_help()
        raise SystemExit(2)
    elif args.command == "docs":
        import json as _json
        from pathlib import Path as _Path

        def _write_coverage_json(coverage: dict[str, list[str]]) -> None:
            """Write the coverage map to --json's path, creating parent dirs."""
            if args.json is None:
                return
            out = _Path(args.json)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(_json.dumps(coverage, indent=2), encoding="utf-8")

        if args.all:
            from haywire_studio.docs_gen.generate import generate_all_docs

            results = generate_all_docs(args.library)
            total_gaps = sum(len(gaps) for gaps in results.values())
            print(f"Generated docs for {len(results)} libraries.")
            for lib_id in sorted(results):
                gaps = results[lib_id]
                marker = f"{len(gaps)} coverage gap(s)" if gaps else "clean"
                print(f"  • {lib_id}: {marker}")
                for line in gaps:
                    print(f"      - {line}")
            print(f"Total coverage gaps: {total_gaps}.")
            _write_coverage_json(results)
            return

        from haywire_studio.docs_gen.generate import generate_docs

        coverage = generate_docs(args.library)
        if coverage:
            print("Documentation coverage gaps:")
            for line in coverage:
                print(f"  - {line}")
        else:
            print("Docs generated. No coverage gaps.")
        # The single-library form has no library id to key by, so the path the
        # user named is the key. Keeps --json's shape identical for both forms.
        _write_coverage_json({str(args.library or _Path.cwd()): coverage})
        return
    else:
        run_app()


if __name__ in {"__main__", "__mp_main__"}:
    main()
