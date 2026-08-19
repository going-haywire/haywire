"""Farmhand host: low-level MCP server mounted at /mcp on the studio app.

Design anchors (spec §2, §3; SDK facts verified against mcp 1.28.1):
- ONE StreamableHTTPSessionManager per process; run() entered exactly once by a
  single long-lived runner task (AsyncExitStack-across-handlers crashes NiceGUI
  shutdown — .insights/feedback_nicegui_lifespan_task_scope.md).
- The SDK advertises listChanged:false by default; _FarmhandServer overrides
  create_initialization_options so the manager's no-arg call gets
  NotificationOptions(tools_changed=True, prompts_changed=True, resources_changed=True).
- No stack auto-notifies on the hot-reload path: we track live ServerSessions in
  a WeakSet (captured per request) and send list_changed ourselves.
- One change pipeline: FarmhandRegistry CLASS_ADDED/CLASS_REMOVED batch events
  drive add/remove + notify; baseline tools register through the same registry.
"""

from __future__ import annotations

import asyncio
import json
import logging
import weakref
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

import mcp.types as types
from mcp.server.lowlevel import NotificationOptions, Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.server.transport_security import TransportSecuritySettings
from nicegui import app as nicegui_app

from haywire.core.access import AccessTier, required_access
from haywire.core.docs.tree import doc_manifest, list_docs, read_doc
from haywire.core.farmhand import Farmhand, FarmhandContext, FarmhandError, FarmhandRegistry
from haywire.core.library.registry import LibraryRegistry
from haywire.core.registry.lifecycle_event import LifeCycleEvent, LifeCycleEventType
from haywire.core.session.signals import FarmhandActivity

from .activity import activity_tracker
from .auth import connection_command

if TYPE_CHECKING:
    from haywire_studio.auth.live import RosterCache

logger = logging.getLogger(__name__)

PROTOCOL_VERSION = "2025-11-25"


class _FarmhandServer(Server):
    """Low-level Server that always advertises listChanged capabilities.

    StreamableHTTPSessionManager calls create_initialization_options() with no
    arguments, which would advertise listChanged:false (SDK default quirk).
    """

    def create_initialization_options(self, notification_options=None, experimental_capabilities=None):
        return super().create_initialization_options(
            notification_options=notification_options
            or NotificationOptions(tools_changed=True, prompts_changed=True, resources_changed=True),
            experimental_capabilities=experimental_capabilities,
        )


def _origin_scheme(*, tls: bool) -> str:
    """The scheme the MCP DNS-rebinding check should expect for its own origin.

    ``allowed_origins`` used to hardcode ``http://``. Under TLS that makes /mcp
    reject its own origin, because the browser or client sends ``https://``.
    """
    return "https" if tls else "http"


def _format_tool_error(exc: Exception) -> str:
    if isinstance(exc, FarmhandError):
        ids = ", ".join(f"{k}={v}" for k, v in exc.ids.items())
        suffix = f" ({ids})" if ids else ""
        # The recovery hint goes on its own line so an agent reading the error
        # gets the fixing command without parsing the message prose.
        hint = f"\nhelp: {exc.help}" if exc.help else ""
        return f"[{exc.code}] {exc.message}{suffix}{hint}"
    # HaywireException maps directly (spec §5 conventions): category is the stable code.
    category = getattr(exc, "category", None)
    message = getattr(exc, "message", None)
    if category and message:
        key = getattr(exc, "registry_key", None)
        suffix = f" (registry_key={key})" if key else ""
        return f"[haywire:{category}] {message}{suffix}"
    return f"[internal] {type(exc).__name__}: {exc}"


def tools_for_tier(tools: dict[str, Any], tier: AccessTier) -> list[str]:
    """Tool names visible at ``tier``.

    Uses the same ``required_access`` lookup as the panel and editor gates, so a
    tool with no declared access is VIEW here for exactly the reason it is VIEW
    there.
    """
    return [name for name, cls in tools.items() if tier.satisfies(required_access(cls))]


def caller_principal(request: Any) -> str | None:
    """The principal name behind this MCP call, or ``None``.

    The gate stamped the resolved principal onto the ASGI scope, and the MCP
    SDK's ``RequestContext.request`` carries that same scope through. ``None``
    means authentication is off — the resolver then answers ADMIN, which is what
    keeps Farmhand behaving exactly as it did before authentication existed.
    """
    from haywire_studio.auth.gate import PRINCIPAL_SCOPE_KEY

    scope = getattr(request, "scope", None)
    if isinstance(scope, dict):
        principal = scope.get(PRINCIPAL_SCOPE_KEY)
        return principal if isinstance(principal, str) else None
    return None


def caller_tier(request: Any) -> AccessTier:
    """The tier of whoever is making this MCP call."""
    from haywire.core.access import resolve_tier

    return resolve_tier(caller_principal(request))


class FarmhandHost:
    def __init__(self, library_service: Any, workspace_root: str):
        self._library_service = library_service
        self._workspace_root = workspace_root
        self._registry: FarmhandRegistry = library_service.injector.get(FarmhandRegistry)
        self._tools: dict[str, type[Farmhand]] = {}
        self._sessions: "weakref.WeakSet" = weakref.WeakSet()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._server = _FarmhandServer("farmhand")
        self._session_manager: Optional[StreamableHTTPSessionManager] = None
        self._started: Optional[asyncio.Event] = None
        self._stop: Optional[asyncio.Event] = None
        self._runner: Optional[asyncio.Task] = None
        self._roster_cache: Optional["RosterCache"] = None
        self._roster_stamp: tuple[float, int] | None = None

        # Libraries (including haybale-studio's studio_* baseline) enabled
        # before the host exists — seed from the registry, then follow events.
        self._seed_tools()
        self._registry.add_batch_event_subscriber(self._on_lifecycle_batch)
        self._register_handlers()

    # -- roster freshness -----------------------------------------------------

    def add_roster_cache(self, cache: "RosterCache") -> None:
        """Wire in the auth roster cache so a live tier edit can push list_changed.

        Optional: this adds the proactive nudge that refreshes a connected client's tool list.
        """
        self._roster_cache = cache
        self._roster_stamp = cache.stamp()

    async def _check_roster_freshness(self) -> None:
        """Piggyback on in-flight traffic to notice a roster edit and push list_changed.
        """
        if self._roster_cache is None:
            return
        stamp = self._roster_cache.stamp()
        if stamp == self._roster_stamp:
            return
        self._roster_stamp = stamp
        await self._notify_list_changed()

    # -- tool table -----------------------------------------------------

    def _seed_tools(self) -> None:
        for key in self._registry.list_names():
            cls = self._registry.get(key)
            if cls is not None:
                self._tools[cls.mcp_name()] = cls

    def _remove_tool_by_key(self, registry_key: str) -> None:
        lib_id, _, name = registry_key.split(":")
        self._tools.pop(f"{lib_id}_{name}", None)

    def _on_lifecycle_batch(self, events: list[LifeCycleEvent]) -> None:
        relevant = [
            e
            for e in events
            if e.event_type in (LifeCycleEventType.CLASS_ADDED, LifeCycleEventType.CLASS_REMOVED)
        ]
        if not relevant:
            return
        if self._loop is None or not self._loop.is_running():
            self._apply_events(relevant)  # startup enable path: no live sessions yet
            return
        # Hot-reload/enable/disable events arrive on watchdog/timer threads —
        # marshal onto the NiceGUI loop.
        self._loop.call_soon_threadsafe(lambda: asyncio.ensure_future(self._apply_and_notify(relevant)))

    def _apply_events(self, events: list[LifeCycleEvent]) -> None:
        for event in events:
            if event.event_type == LifeCycleEventType.CLASS_ADDED:
                cls = self._registry.get(event.registry_key)
                if cls is not None:
                    self._tools[cls.mcp_name()] = cls
            else:
                self._remove_tool_by_key(event.registry_key)

    async def _apply_and_notify(self, events: list[LifeCycleEvent]) -> None:
        self._apply_events(events)
        await self._notify_list_changed()

    async def _notify_list_changed(self) -> None:
        for session in list(self._sessions):
            try:
                await session.send_tool_list_changed()
                await session.send_resource_list_changed()
            except Exception as exc:  # dead session — WeakSet will drop it
                logger.debug(f"Farmhand: list_changed notification failed: {exc}")

    def _request(self) -> Any:
        """The in-flight MCP request, or ``None`` outside a request context."""
        try:
            return self._server.request_context.request
        except Exception:
            return None

    def _caller_tier(self) -> AccessTier:
        """Tier of the in-flight MCP request; ADMIN when there is no request context."""
        return caller_tier(self._request())

    def _caller_principal(self) -> str | None:
        """Principal of the in-flight MCP request; ``None`` when auth is off."""
        return caller_principal(self._request())

    def _publish_activity(self) -> None:
        """Nudge every open browser session to re-read the activity tracker.

        Best-effort by design: a studio with no SessionManager (tests, headless
        embedding) or a subscriber that raises must never turn into a failed
        tool call. ``FarmhandActivity`` carries no payload, so a dropped one
        costs a stale chip until the next call, not a wrong one.
        """
        try:
            from haywire.core.di.context import get_session_manager

            get_session_manager().broadcast(FarmhandActivity())
        except Exception as exc:
            logger.debug(f"Farmhand: activity broadcast skipped: {exc}")

    # -- MCP handlers ---------------------------------------------------

    def _register_handlers(self) -> None:
        @self._server.list_tools()
        async def list_tools() -> list[types.Tool]:
            self._track_session()
            await self._check_roster_freshness()
            tier = self._caller_tier()
            visible = set(tools_for_tier(self._tools, tier))
            return [
                types.Tool(
                    name=name,
                    description=cls.class_identity.instructions,
                    inputSchema=cls.input_schema(),
                    annotations=types.ToolAnnotations(**cls.class_identity.annotations.to_dict()),
                )
                for name, cls in sorted(self._tools.items())
                if name in visible
            ]

        @self._server.call_tool()
        async def call_tool(name: str, arguments: dict) -> tuple[list[types.TextContent], dict[str, Any]]:
            self._track_session()
            await self._check_roster_freshness()
            cls = self._tools.get(name)
            if cls is None:
                raise Exception(
                    _format_tool_error(
                        FarmhandError(
                            "unknown_tool",
                            f"No tool named '{name}'",
                            ids={"tool": name},
                            help="Re-list the server's tools; the tool set changes as libraries are "
                            "enabled, disabled, or hot-reloaded.",
                        )
                    )
                )
            tier = self._caller_tier()
            if name not in tools_for_tier({name: cls}, tier):
                raise Exception(
                    _format_tool_error(
                        FarmhandError(
                            "access_denied",
                            f"'{name}' requires a higher access tier than this token holds",
                            ids={"tool": name},
                            help="Ask an admin for a token at the required tier, or use a "
                            "read-only tool instead.",
                        )
                    )
                )
            session = self._server.request_context.session

            async def reporter(message: str) -> None:
                try:
                    await session.send_log_message(level="info", data=message)
                except Exception:
                    pass

            principal = self._caller_principal()
            ctx = FarmhandContext(progress_reporter=reporter, principal=principal)

            # Attribution for open browser sessions. Every mutating tool already
            # broadcasts its own data signal (GraphDataMutated and friends), so
            # the UI refreshes without this — what this adds is *who*, plus the
            # only visibility read-only tools ever get. Recorded here rather than
            # per-tool: see the module docstring in activity.py.
            tracker = activity_tracker()
            token = tracker.start(principal, name, arguments)
            self._publish_activity()
            try:
                try:
                    result = await cls().run(ctx, **arguments)
                except Exception as exc:
                    tracker.finish(token, ok=False, error=_format_tool_error(exc))
                    raise Exception(_format_tool_error(exc)) from None
                if isinstance(result, dict) and "summary" not in result:
                    result = {"summary": f"{name}: ok", **result}
                # Return BOTH halves (the SDK's CombinationContent form): the
                # text block keeps text-only clients working, while
                # structuredContent hands structure-aware ones the object
                # without a string parse.
                #
                # We serialize the text ourselves rather than letting the SDK's
                # dict-only branch do it, because that branch calls plain
                # json.dumps() — a non-serializable value (a mesh, a frame)
                # would raise there. `default=str` degrades it to a repr
                # instead, which is the documented contract tools are written
                # against (canon §168).
                text = json.dumps(result, default=str)
                tracker.finish(token, ok=True, result=result)
                # structuredContent must be JSON-safe too; round-trip through
                # the text we just built so both halves carry identical values.
                return [types.TextContent(type="text", text=text)], json.loads(text)
            finally:
                # Catches the one path neither branch above covers: a cancelled
                # request (client disconnect) unwinds straight past both, and
                # would otherwise strand the call as forever-running. A no-op
                # whenever the call already recorded its own outcome.
                tracker.finish_if_running(token)
                # One publish per call, on every exit path — success, failure
                # and cancellation alike.
                self._publish_activity()

        @self._server.list_resources()
        async def list_resources() -> list[types.Resource]:
            self._track_session()
            # The full baked docs tree: a manifest index plus one resource per
            # file. The manifest lets the agent survey the corpus (path + title)
            # without reading every file.
            resources = [
                types.Resource(
                    uri="farmhand://docs/_manifest",  # type: ignore[arg-type]
                    name="docs manifest (index of all doc paths + titles)",
                    mimeType="application/json",
                )
            ]
            resources += [
                types.Resource(
                    uri=f"farmhand://docs/{rel_path}",  # type: ignore[arg-type]
                    name=rel_path,
                    mimeType="text/markdown",
                )
                for rel_path in list_docs()
            ]
            registry = self._library_service.injector.get(LibraryRegistry)
            for lib_id in registry.list_names():
                if not registry.is_library_enabled(lib_id):
                    continue
                folder = Path(registry.get_library_identity(lib_id).folder_path)
                for slug, filename in (("overview", "OVERVIEW.md"), ("quickref", "QUICKREF.md")):
                    if (folder / filename).exists():
                        resources.append(
                            types.Resource(
                                uri=f"farmhand://library/{lib_id}/{slug}",  # type: ignore[arg-type]
                                name=f"{lib_id} {slug}",
                                mimeType="text/markdown",
                            )
                        )
            return resources

        @self._server.read_resource()
        async def read_resource(uri) -> str:
            self._track_session()
            text = str(uri)
            if text == "farmhand://docs/_manifest":
                return json.dumps(doc_manifest(), indent=2)
            if text.startswith("farmhand://docs/"):
                rel_path = text[len("farmhand://docs/") :]
                return read_doc(rel_path)
            if text.startswith("farmhand://library/"):
                _, _, rest = text.partition("farmhand://library/")
                lib_id, _, slug = rest.partition("/")
                filename = {"overview": "OVERVIEW.md", "quickref": "QUICKREF.md"}.get(slug)
                registry = self._library_service.injector.get(LibraryRegistry)
                if filename and lib_id in registry.list_names():
                    path = Path(registry.get_library_identity(lib_id).folder_path) / filename
                    if path.exists():
                        return path.read_text(encoding="utf-8")
            raise Exception(f"[resource_not_found] No resource at '{text}'")

    def _track_session(self) -> None:
        try:
            self._sessions.add(self._server.request_context.session)
        except Exception:
            pass

    # -- mount + lifespan ----------------------------------------------

    def mount(self, port: int, document, app_target: Any = None, *, tls: bool = False) -> None:
        """Mount /mcp on the studio app.

        No bearer middleware of its own: the root ``AuthGateMiddleware`` covers
        this mount, and a second token check beneath it would be a settings flag
        acting as a security control — the exact shape ADR 0027 set out to avoid.
        """
        target = app_target if app_target is not None else nicegui_app
        policy = document.farmhand

        if policy.restrict_to_loopback:
            allowed_hosts = [f"127.0.0.1:{port}", f"localhost:{port}", "127.0.0.1", "localhost"]
            scheme = _origin_scheme(tls=tls)
            allowed_origins = [f"{scheme}://127.0.0.1:{port}", f"{scheme}://localhost:{port}"]

            public_hostname = document.network.public_hostname
            if public_hostname:
                allowed_hosts.append(public_hostname)
                if ":" not in public_hostname:
                    allowed_hosts.append(f"{public_hostname}:{port}")
                allowed_origins.append(f"http://{public_hostname}")
                allowed_origins.append(f"https://{public_hostname}")

            security = TransportSecuritySettings(
                allowed_hosts=allowed_hosts,
                allowed_origins=allowed_origins,
            )
        else:
            security = TransportSecuritySettings(enable_dns_rebinding_protection=False)
        self._session_manager = StreamableHTTPSessionManager(app=self._server, security_settings=security)

        async def asgi(scope, receive, send):
            assert self._session_manager is not None
            await self._session_manager.handle_request(scope, receive, send)

        target.mount("/mcp", asgi)
        # The NiceGUI app drives the runner via its own lifespan hooks; a test
        # harness (FastAPI app_target) drives _on_startup/_on_shutdown itself.
        if target is nicegui_app:
            nicegui_app.on_startup(self._on_startup)
            nicegui_app.on_shutdown(self._on_shutdown)

        hint = self._connection_hint(port, document, tls=tls)
        logger.info(f"Farmhand MCP server will serve at /mcp — connect with:\n  {hint}")
        print(f"🤝 Farmhand: {hint}")

    @staticmethod
    def _connection_hint(port: int, document, *, tls: bool) -> str:
        """The connect line, naming a real agent token when one exists.

        With authentication on, printing a header-less command would hand the
        operator something that returns 401. Printing the *first* agent
        principal's token is right far more often than not — most studios have
        exactly one — and when there is none, saying so beats a command that
        cannot work.
        """
        if not document.auth.enabled:
            return connection_command(port, None, tls=tls)
        agents = [p for p in document.auth.principals if p.is_agent]
        if not agents:
            return (
                "authentication is on but no agent principal exists — create one with:\n"
                "  haywire user add <name> --agent --tier edit"
            )
        return connection_command(port, agents[0].token, tls=tls)

    async def _runner_main(self) -> None:
        assert self._session_manager is not None and self._started is not None and self._stop is not None
        async with self._session_manager.run():
            self._started.set()
            await self._stop.wait()

    async def _on_startup(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._started, self._stop = asyncio.Event(), asyncio.Event()
        self._runner = asyncio.create_task(self._runner_main())
        await self._started.wait()
        logger.info("Farmhand: MCP session manager running (single runner task)")

    async def _on_shutdown(self) -> None:
        if self._stop is not None:
            self._stop.set()
        if self._runner is not None:
            await self._runner
