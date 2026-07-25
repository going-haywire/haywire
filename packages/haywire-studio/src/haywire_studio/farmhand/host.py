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
from typing import Any, Optional

import mcp.types as types
from mcp.server.lowlevel import NotificationOptions, Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.server.transport_security import TransportSecuritySettings
from nicegui import app as nicegui_app

from haywire.core.docs.tree import doc_manifest, list_docs, read_doc
from haywire.core.farmhand import Farmhand, FarmhandContext, FarmhandError, FarmhandRegistry
from haywire.core.library.registry import LibraryRegistry
from haywire.core.registry.lifecycle_event import LifeCycleEvent, LifeCycleEventType

from .auth import BearerTokenMiddleware, connection_command, ensure_token

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


def _format_tool_error(exc: Exception) -> str:
    if isinstance(exc, FarmhandError):
        ids = ", ".join(f"{k}={v}" for k, v in exc.ids.items())
        suffix = f" ({ids})" if ids else ""
        return f"[{exc.code}] {exc.message}{suffix}"
    # HaywireException maps directly (spec §5 conventions): category is the stable code.
    category = getattr(exc, "category", None)
    message = getattr(exc, "message", None)
    if category and message:
        key = getattr(exc, "registry_key", None)
        suffix = f" (registry_key={key})" if key else ""
        return f"[haywire:{category}] {message}{suffix}"
    return f"[internal] {type(exc).__name__}: {exc}"


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

        # Libraries (including haybale-studio's studio_* baseline) enabled
        # before the host exists — seed from the registry, then follow events.
        self._seed_tools()
        self._registry.add_batch_event_subscriber(self._on_lifecycle_batch)
        self._register_handlers()

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
        # marshal onto the NiceGUI loop (ADR 0002 discipline).
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

    # -- MCP handlers ---------------------------------------------------

    def _register_handlers(self) -> None:
        @self._server.list_tools()
        async def list_tools() -> list[types.Tool]:
            self._track_session()
            return [
                types.Tool(
                    name=name,
                    description=cls.class_identity.description or cls.class_identity.label,
                    inputSchema=cls.input_schema(),
                    annotations=types.ToolAnnotations(**cls.class_identity.annotations.to_dict()),
                )
                for name, cls in sorted(self._tools.items())
            ]

        @self._server.call_tool()
        async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
            self._track_session()
            cls = self._tools.get(name)
            if cls is None:
                raise Exception(
                    _format_tool_error(
                        FarmhandError("unknown_tool", f"No tool named '{name}'", ids={"tool": name})
                    )
                )
            session = self._server.request_context.session

            async def reporter(message: str) -> None:
                try:
                    await session.send_log_message(level="info", data=message)
                except Exception:
                    pass

            ctx = FarmhandContext(progress_reporter=reporter)
            try:
                result = await cls().run(ctx, **arguments)
            except Exception as exc:
                raise Exception(_format_tool_error(exc)) from None
            if isinstance(result, dict) and "summary" not in result:
                result = {"summary": f"{name}: ok", **result}
            return [types.TextContent(type="text", text=json.dumps(result, default=str))]

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

    def mount(self, port: int, app_target: Any = None) -> None:
        target = app_target if app_target is not None else nicegui_app
        token = ensure_token(Path(self._workspace_root))
        security = TransportSecuritySettings(
            allowed_hosts=[f"127.0.0.1:{port}", f"localhost:{port}", "127.0.0.1", "localhost"],
            allowed_origins=[f"http://127.0.0.1:{port}", f"http://localhost:{port}"],
        )
        self._session_manager = StreamableHTTPSessionManager(app=self._server, security_settings=security)

        async def asgi(scope, receive, send):
            assert self._session_manager is not None
            await self._session_manager.handle_request(scope, receive, send)

        target.mount("/mcp", BearerTokenMiddleware(asgi, token))
        # The NiceGUI app drives the runner via its own lifespan hooks; a test
        # harness (FastAPI app_target) drives _on_startup/_on_shutdown itself.
        if target is nicegui_app:
            nicegui_app.on_startup(self._on_startup)
            nicegui_app.on_shutdown(self._on_shutdown)

        hint = connection_command(port, token)
        logger.info(f"Farmhand MCP server will serve at /mcp — connect with:\n  {hint}")
        print(f"🤝 Farmhand: {hint}")

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
