import asyncio
import os
import logging
from pathlib import Path
from typing import Callable, Optional, TYPE_CHECKING

from fastapi import Request
from nicegui import ui, app

# Core imports
from haywire.core.undo.config import DEVELOPMENT_CONFIG
from haywire.core.di.config import create_library_system_service
from haywire.core.di.context import set_workspace_root
from haywire.core.errors.ledger import get_error_ledger
from haywire.core.host import HostStore
from haywire.core.session.signals import ErrorLogged, PresenceChanged

# UI imports
from haywire.ui.console_bridge import get_stdout_tee

from haywire.ui.extends.codemirror import register_code_intelligence_render_endpoint

from haywire_studio.auth.gate import PRINCIPAL_SCOPE_KEY

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

        Tears down the AppShell first, then detaches the session.
        SessionManager.remove_session does only state cleanup — UI cleanup
        is the shell's responsibility.
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
        self.session_manager.broadcast(PresenceChanged())

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

        # LibraryManager is published by haybale-marketplace as
        # LibraryManagerState. Persisted disabled-state is applied by the
        # library system during create_library_system_service.

        print("Shared services configured successfully.")

    def setup_farmhand(self, port: int, *, tls: bool = False) -> None:
        """Mount the Farmhand MCP server if enabled (flag read once; restart to apply)."""
        from haywire_studio.farmhand.host import FarmhandHost
        from haywire_studio.farmhand.settings import FarmhandSettings

        if not FarmhandSettings().enabled:
            logging.getLogger(__name__).info("Farmhand: disabled by settings (farmhand.enabled = false)")
            return
        self.farmhand_host = FarmhandHost(self.library_service, self.workspace_root)
        self.farmhand_host.mount(port, tls=tls)

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
        def main_page(request: Request):
            from haywire.ui.app.shell import AppShell
            from haywire.ui.editor.registry import EditorTypeRegistry
            from nicegui import context

            print(f"Creating UI for session: {context.client.id[:8]}")

            editor_registry = self.library_service.injector.get(EditorTypeRegistry)

            haywire_session = self.session_manager.create_session(
                project_state=self,
                workspace_manager=self.workspace_manager,
            )

            # The gate already verified the credential and stashed the principal
            # on the ASGI scope; `request.scope` IS that same dict. None means
            # authentication is off, which resolves to ADMIN.
            haywire_session.context.principal = request.scope.get(PRINCIPAL_SCOPE_KEY)
            haywire_session.publish(PresenceChanged())

            # Map this client to its session so on_disconnect can resolve
            # which session to tear down.
            self._client_to_session[context.client.id] = haywire_session.session_id

            # Set studio theme defaults on context before rendering
            haywire_session.context.active_workbench_theme_key = "haywire-core:theme:workbench:haywire-dark"
            haywire_session.context.active_node_theme_key = "haywire-core:theme:node:default"

            app_shell = AppShell(haywire_session, editor_registry=editor_registry)
            self._shells[haywire_session.session_id] = app_shell
            app_shell.render()

    # ------------------------------------------------------------------
    # Run / cleanup
    # ------------------------------------------------------------------

    def cleanup(self):
        """Manual cleanup fallback."""
        self.on_app_shutdown()

    def _install_auth(self) -> bool:
        """Install the gate, the login routes and the tier resolver, if enabled.

        Returns whether authentication is on. Everything here is skipped when the
        roster says disabled, so an auth-off install runs exactly the code it ran
        before this feature existed.
        """
        from nicegui import app as nicegui_app

        from haywire_studio.auth.cookies import load_or_create_secret
        from haywire_studio.auth.gate import AuthGateMiddleware
        from haywire_studio.auth.live import RosterCache, install_resolver
        from haywire_studio.auth.login import register_login_routes
        from haywire_studio.auth.roster import RosterError, load_roster

        cache = RosterCache()
        try:
            # RosterCache.roster() deliberately swallows RosterError to keep
            # serving the last-good copy once the studio is already running —
            # exactly the wrong behaviour for this first-ever read, where a
            # corrupt or unreadable file must fail startup loudly rather than
            # silently degrade to "no roster" (enabled=False). Read once
            # directly to surface that error, then let the cache take over.
            load_roster(cache.path)
        except RosterError as exc:
            print(f"ERROR: Haywire cannot start — the roster is unreadable.\n  {exc}")
            raise SystemExit(1) from exc
        roster = cache.roster()

        if not roster.enabled:
            return False

        if not roster.admins():
            print(
                "ERROR: Haywire cannot start — authentication is enabled but no admin exists.\n"
                "  Run 'haywire auth disable', add an admin with 'haywire user add <name> "
                "--tier admin', then 'haywire auth enable'."
            )
            raise SystemExit(1)

        secret = load_or_create_secret()
        install_resolver(cache)
        register_login_routes(cache=cache, secret=secret)
        nicegui_app.add_middleware(
            AuthGateMiddleware,
            cache=cache,
            secret=secret,
            workspace_root=self.workspace_root,
        )
        self._auth_cache = cache
        print(f"🔒 Authentication enabled — {len(roster.principals)} principal(s)")
        return True

    def run(self, *, open_browser: bool = True):
        """Run the application."""
        print("Starting Haywire...")
        self.create_ui()
        from haywire_studio.network.settings import NetworkSettings

        settings = NetworkSettings()
        port = settings.port
        host = "0.0.0.0" if settings.expose_to_network else "127.0.0.1"
        ssl_kwargs = _ssl_kwargs(settings.ssl_certfile, settings.ssl_keyfile)

        # Install the gate BEFORE the Farmhand mount so the root wrapper covers
        # /mcp too — one boundary, not a boundary with a documented hole beside it.
        auth_enabled = self._install_auth()

        self.setup_farmhand(port, tls=bool(ssl_kwargs))

        if settings.expose_to_network:
            self._install_ip_allowlist(settings)
            if not auth_enabled:
                logger.warning(
                    "Network: the studio is exposed beyond loopback with authentication OFF. "
                    "Anyone who can reach it is a full operator. Run 'haywire auth enable' to "
                    "require a login."
                )
            if not ssl_kwargs:
                logger.warning(
                    "Network: serving plain HTTP beyond loopback — session cookies and "
                    "passwords travel unencrypted and a captured cookie is a valid cookie. "
                    "Run 'haywire ssl setup' to serve HTTPS, or terminate TLS at a reverse proxy."
                )

        try:
            ui.run(
                host=host,
                port=port,
                show=open_browser,
                title="Haywire",
                reload=False,
                **ssl_kwargs,  # type: ignore[arg-type]
            )
        except KeyboardInterrupt:
            print("\nKeyboard interrupt received")
        finally:
            if not self._is_shutting_down:
                self.cleanup()

    @staticmethod
    def _install_ip_allowlist(settings) -> None:
        """Install IPAllowlistMiddleware on the root ASGI app (only called when
        expose_to_network is on — see run()).

        Uses ``nicegui.app.add_middleware`` (nicegui.app is a FastAPI instance):
        Starlette's middleware stack wraps the whole ASGI callable, including
        mounted sub-apps such as NiceGUI's Socket.IO mount at /_nicegui_ws/, so
        the wrapper sees `websocket` scopes for UI traffic too, not just the
        initial HTTP page load. Verified behaviorally against a FastAPI app with
        a mounted WebSocketRoute sub-app (mirrors NiceGUI's own mount pattern):
        a middleware installed via add_middleware saw scope["type"] == "websocket"
        for traffic through the mount, and a middleware-issued reject
        (websocket.close) took effect before the sub-app was ever reached.

        Invalid CIDR entries in allowed_remote_ranges/trusted_proxies raise
        ValueError from the constructor; that must never be swallowed into a
        silently-unprotected startup, so it is surfaced here as a clear error
        and a clean process exit rather than either a raw traceback or a
        fail-open skip.

        Note: Starlette's ``add_middleware`` only records ``(cls, args, kwargs)``
        — it does NOT instantiate the class immediately, so a bad-CIDR
        ValueError from the constructor would otherwise surface much later
        (on first request, via ``build_middleware_stack()``) or not at all if
        the server never received one before shutdown. We construct once here
        purely to validate eagerly at startup, then let ``add_middleware``
        install the (now known-good) class for Starlette to instantiate again
        when it builds the real middleware stack.
        """
        from haywire_studio.network.ip_filter import IPAllowlistMiddleware

        allowed_ranges = [
            entry.strip() for entry in settings.allowed_remote_ranges.split(",") if entry.strip()
        ]
        trusted_proxies = [entry.strip() for entry in settings.trusted_proxies.split(",") if entry.strip()]

        if not trusted_proxies:
            logger.warning(
                "Network: expose_to_network is on but trusted_proxies is empty — "
                "X-Forwarded-For headers will be ignored. If this studio sits behind "
                "a reverse proxy, add the proxy's own peer IP to allowed_remote_ranges "
                "or configure trusted_proxies, or every client will appear to be the proxy."
            )

        try:
            # Validate eagerly (see docstring) — the throwaway instance's inner
            # `app` (None) is never invoked; it exists only to run the same CIDR
            # parsing the real, Starlette-owned instance will run later.
            IPAllowlistMiddleware(None, allowed_ranges=allowed_ranges, trusted_proxies=trusted_proxies)
        except ValueError as e:
            print(
                "ERROR: Haywire cannot start — invalid network settings.\n"
                f"  {e}\n"
                "Check 'allowed_remote_ranges' and 'trusted_proxies' under Network "
                "settings (settings.json): every entry must be a valid CIDR range "
                "(e.g. '192.168.1.0/24')."
            )
            raise SystemExit(1) from e

        app.add_middleware(
            IPAllowlistMiddleware,
            allowed_ranges=allowed_ranges,
            trusted_proxies=trusted_proxies,
        )


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------


def _ssl_kwargs(certfile: str, keyfile: str) -> dict[str, str]:
    """Build the uvicorn TLS kwargs, or exit with a clear message.

    NiceGUI's ``ui.run(**kwargs)`` forwards these to uvicorn and recognises the
    pair explicitly — it uses them to build the ``https://`` URL for the
    ``show=True`` auto-open browser. So HTTPS needs no patching, only a
    passthrough.

    Exactly one of the pair is always a misconfiguration: silently serving plain
    HTTP when the operator believes TLS is on would leak every session cookie on
    the wire. Fail loudly at startup instead, matching ``_install_ip_allowlist``.
    """
    if not certfile and not keyfile:
        return {}

    if bool(certfile) != bool(keyfile):
        print(
            "ERROR: Haywire cannot start — incomplete TLS configuration.\n"
            "  Set BOTH 'ssl_certfile' and 'ssl_keyfile' under Network settings, or neither.\n"
            "  Run 'haywire ssl status' to see the current state."
        )
        raise SystemExit(1)

    for label, value in (("ssl_certfile", certfile), ("ssl_keyfile", keyfile)):
        if not Path(value).is_file():
            print(
                f"ERROR: Haywire cannot start — {label} does not point at a file: {value}\n"
                "  Run 'haywire ssl status' to see the current state."
            )
            raise SystemExit(1)

    return {"ssl_certfile": certfile, "ssl_keyfile": keyfile}


def run_app(*, open_browser: bool = True) -> int:
    """Launch the Haywire application. Returns the process exit code.

    Nothing reads the code today — it is the seam a future supervisor uses
    to distinguish "user quit" from "restart me".
    """
    # logging.getLogger("haywire.ui.editor.graph_canvas_manager").setLevel(logging.DEBUG)
    # use DebugSettings.log_ui instead

    # Install before HaywireApp() is constructed so the workspace banner and
    # library-system banner (printed during __init__) reach the Log panel too.
    # uvicorn also resolves ext://sys.stdout when it applies its logging config,
    # so this must happen before that config is built.
    get_stdout_tee().install()

    app_instance = HaywireApp()
    app.on_shutdown(app_instance.cleanup)
    app_instance.run(open_browser=open_browser)

    from haywire.core.update.confirmed import exit_code

    return exit_code()


def main():
    """Route ``haywire <subcommand>``, or launch the app when given none.

    Every subcommand registers its own parser and handler in
    :mod:`haywire_studio.cli`; this only wires them together, so adding one
    never touches this file. A top-level flag (not a subcommand) is a
    deliberate, documented exception — see ``--no-browser`` below.
    """
    import argparse

    from haywire_studio.cli import SUBCOMMANDS

    parser = argparse.ArgumentParser(
        prog="haywire",
        description="Haywire visual programming system",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not open a browser window on startup (headless/server use).",
    )
    subparsers = parser.add_subparsers(dest="command")
    for subcommand in SUBCOMMANDS:
        subcommand.register(subparsers)

    args = parser.parse_args()

    handler = getattr(args, "handler", None)
    if handler is None:
        raise SystemExit(run_app(open_browser=not args.no_browser))
    raise SystemExit(handler(args))


if __name__ in {"__main__", "__mp_main__"}:
    main()
