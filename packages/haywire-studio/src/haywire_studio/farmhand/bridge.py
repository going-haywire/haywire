"""The Farmhand bridge: a stdio MCP server that connects an agent session to its own project's studio.

A harness starts it from the committed MCP config of a place of work
(``uv run haywire farmhand bridge``), so it runs in that place's Haywire
environment. It is up before any studio is: its server instructions and the
baked docs come from the installed Haywire. It finds the project's studio
through ``.haywire/studio.json``, connects when the studio comes up, forwards
the studio's tools and resources, announces every change with
``list_changed``, and drops them again when the studio stops. When the studio
requires a token it reads the Farmhand principal's from the roster itself, so
the token never reaches the agent.
"""

from __future__ import annotations

import io
import json
import logging
import os
import sys
import tomllib
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import anyio
import httpx
from mcp import types
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.server.lowlevel import NotificationOptions, Server
from mcp.server.lowlevel.helper_types import ReadResourceContents
from mcp.server.session import ServerSession
from mcp.server.stdio import stdio_server

from haywire.core.docs.tree import doc_manifest, list_docs, read_doc, served_docs
from haywire_studio.farmhand.identity import IDENTITY_FILENAME, identity_status, read_identity
from haywire_studio.security.document import load_document
from haywire_studio.security.errors import SecurityError

logger = logging.getLogger(__name__)

#: The agent principal whose token the bridge sends; ``FARMHAND_PRINCIPAL`` overrides it.
DEFAULT_PRINCIPAL = "farmhand"

STATUS_TOOL = "farmhand_studio_status"
CONNECT_TOOL = "farmhand_studio_connect"

_DOCS_PREFIX = "farmhand://docs/"
_MANIFEST_URI = "farmhand://docs/_manifest"
_DEV_PREFIX = "farmhand://dev/"


@dataclass(frozen=True)
class StudioTarget:
    """Where a studio answers and whether it wants a token.

    ``source`` says how the bridge found it: ``sidecar`` (a ``studio.json``),
    ``manual`` (``farmhand_studio_connect``) or ``env`` (``FARMHAND_URL``).
    """

    url: str
    auth_required: bool
    source: str
    project: Path | None = None


def find_project_root(start: Path) -> Path:
    """Return the nearest folder at or above ``start`` that holds a ``.haywire`` folder, else ``start``.

    A harness starts the bridge in the folder its session started in, which can
    be any folder below the project.
    """
    start = start.resolve()
    for folder in (start, *start.parents):
        if (folder / ".haywire").is_dir():
            return folder
    return start


def _mcp_url(ident: dict) -> str | None:
    base = ident.get("url")
    if not isinstance(base, str) or not base:
        port = ident.get("port")
        if not isinstance(port, int):
            return None
        base = f"http://127.0.0.1:{port}"
    base = base.rstrip("/")
    # The trailing slash matters: the studio answers POST /mcp with a 307 that no POST follows.
    return f"{base}/" if base.endswith("/mcp") else f"{base}/mcp/"


def locate_studio(project: Path) -> StudioTarget | None:
    """Return the running studio of ``project``, or of a project one folder below it, or ``None``.

    Only a sidecar whose process is alive counts. ``project`` itself wins over
    the folders below it; among those, the most recently started studio wins.
    """
    candidates = [project] + sorted(
        (p for p in project.iterdir() if p.is_dir() and not p.name.startswith(".")),
        key=lambda p: p.name,
    )
    found: list[tuple[float, Path, dict]] = []
    for folder in candidates:
        if not (folder / ".haywire" / IDENTITY_FILENAME).is_file():
            continue
        ident = read_identity(folder)
        if ident is None or identity_status(ident) != "alive":
            continue
        if folder == project:
            found = [(float("inf"), folder, ident)]
            break
        found.append((float(ident.get("started_at") or 0), folder, ident))
    if not found:
        return None
    _, folder, ident = max(found, key=lambda entry: entry[0])
    url = _mcp_url(ident)
    if url is None:
        return None
    return StudioTarget(
        url=url, auth_required=bool(ident.get("auth_required")), source="sidecar", project=folder
    )


def principal_token(name: str, document: Path | None = None) -> str | None:
    """Return the token of the agent principal ``name`` in the security document, or ``None``.

    Args:
        name: The principal's name, exactly as in the roster.
        document: The security document; ``None`` reads ``~/.haywire/security.json``.
    """
    try:
        roster = load_document(document).auth
    except SecurityError:
        logger.warning("The security document cannot be read; the bridge sends no token", exc_info=True)
        return None
    principal = roster.find(name)
    if principal is None or not principal.is_agent or not principal.token:
        return None
    return principal.token


def developer_docs(project: Path) -> Path | None:
    """Return the docs folder ``project`` declares for agent sessions, or ``None``.

    The declaration is ``developer-docs`` in the ``[tool.haywire.agents]`` table of the
    project's ``pyproject.toml``, a path relative to the project.
    """
    try:
        data = tomllib.loads((project / "pyproject.toml").read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return None
    declared = data.get("tool", {}).get("haywire", {}).get("agents", {}).get("developer-docs")
    if not isinstance(declared, str):
        return None
    folder = (project / declared).resolve()
    return folder if folder.is_dir() else None


def read_developer_doc(root: Path, rel_path: str) -> str:
    """Read one page of a declared developer docs folder; refuse a path that leaves it."""
    target = (root / rel_path).resolve()
    if not target.is_relative_to(root) or target.suffix != ".md" or not target.is_file():
        raise FileNotFoundError(f"No developer page at {rel_path!r}")
    return target.read_text(encoding="utf-8")


def product_index(developer_root: Path | None = None) -> str:
    """Return the bridge's server instructions: what this server is and which pages to read for what."""
    # A development repository may run a fuller studio than its own environment holds; its
    # workflow names the command.
    start = (
        f"as {_DEV_PREFIX}collaboration/workflow.md says (*Live check*)"
        if developer_root is not None
        else "with `uv run haywire studio start` in the project"
    )
    lines = [
        "This is Haywire's Farmhand bridge for this project. It is always connected; the running "
        f"studio's tools appear here when the studio is up (start it {start}) and disappear when it "
        f"stops. `{STATUS_TOOL}` says whether a studio is connected and, if not, why.",
        "",
        "Read the page that matches your task before acting (MCP resources of this server):",
    ]
    for entry in served_docs("product"):
        scope = f": {entry['scope']}" if entry["scope"] else ""
        lines.append(f"- {_DOCS_PREFIX}{entry['path']} ({entry['title']}){scope}")
    lines.append(f"- {_MANIFEST_URI}: every other page, by path and title.")
    if developer_root is not None:
        lines += ["", "This repository is developed by the going-haywire workflow; read before acting:"]
        for entry in served_docs("developer", developer_root):
            scope = f": {entry['scope']}" if entry["scope"] else ""
            lines.append(f"- {_DEV_PREFIX}{entry['path']} ({entry['title']}){scope}")
    return "\n".join(lines)


def _http_status(exc: BaseException) -> int | None:
    """Return the HTTP status inside ``exc`` (or the exception group around it), if any."""
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code
    for inner in getattr(exc, "exceptions", ()):
        status = _http_status(inner)
        if status is not None:
            return status
    return None


def _text(message: str) -> list[types.ContentBlock]:
    return [types.TextContent(type="text", text=message)]


class Bridge:
    """The bridge for one project: a stdio MCP server forwarding to that project's studio.

    Args:
        project: The project folder; its ``.haywire/studio.json`` names the studio.
        principal: The agent principal whose token is sent to a studio that requires one.
        document: The security document to read the token from; ``None`` is the user's.
        poll_s: How often to look for the studio and check the connection.
    """

    def __init__(
        self,
        project: Path,
        *,
        principal: str = DEFAULT_PRINCIPAL,
        document: Path | None = None,
        poll_s: float = 2.0,
    ) -> None:
        self.project = project
        self.principal = principal
        self.document = document
        self.poll_s = poll_s
        self.developer_root = developer_docs(project)
        self.server: Server = Server("farmhand", instructions=product_index(self.developer_root))
        self._downstream: ServerSession | None = None
        self._upstream: ClientSession | None = None
        self._upstream_tools: list[types.Tool] = []
        self._connected_to: StudioTarget | None = None
        self._manual: tuple[int, str | None] | None = None
        self._last_problem = "no studio is running for this project"
        self._register()

    # -- where to connect ----------------------------------------------

    def target(self) -> StudioTarget | None:
        """Return the studio to connect to now: ``FARMHAND_URL``, then a manual port, then the sidecar."""
        override = os.environ.get("FARMHAND_URL")
        if override:
            return StudioTarget(url=override, auth_required=False, source="env")
        if self._manual is not None:
            port, _ = self._manual
            return StudioTarget(url=f"http://127.0.0.1:{port}/mcp/", auth_required=False, source="manual")
        return locate_studio(self.project)

    def _token_for(self, target: StudioTarget) -> str | None:
        if target.source == "manual" and self._manual is not None and self._manual[1]:
            return self._manual[1]
        if target.auth_required or target.source != "sidecar":
            return principal_token(self.principal, self.document)
        return None

    # -- the upstream connection ---------------------------------------

    async def run_upstream(self) -> None:
        """Look for the studio, stay connected while it answers, and repeat; runs until cancelled."""
        while True:
            target = self.target()
            if target is None:
                self._last_problem = "no studio is running for this project"
            else:
                await self._connect(target)
            await anyio.sleep(self.poll_s)

    async def _connect(self, target: StudioTarget) -> None:
        token = self._token_for(target)
        if target.auth_required and token is None:
            self._last_problem = (
                f"the studio at {target.url} requires a token and the roster has no agent principal "
                f"named {self.principal!r}: ask the user to run `haywire user add {self.principal} --agent "
                "--tier edit` in their own terminal"
            )
            return
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        try:
            async with (
                httpx.AsyncClient(headers=headers, timeout=httpx.Timeout(30.0, read=300.0)) as http,
                streamable_http_client(target.url, http_client=http) as (read, write, _),
                ClientSession(read, write, message_handler=self._on_upstream_message) as session,
            ):
                await session.initialize()
                self._upstream = session
                self._connected_to = target
                await self._refresh_tools()
                await self._announce()
                logger.info("Connected to the studio at %s", target.url)
                while self.target() == target:
                    await anyio.sleep(self.poll_s)
                    await session.send_ping()
        except Exception as exc:
            # Boundary: any failure here means "not connected", which the status tool reports.
            status = _http_status(exc)
            if status == 401:
                self._last_problem = (
                    f"the studio at {target.url} refused the token of principal {self.principal!r} (401): "
                    "the principal may be scoped to another workspace, or its token was rotated"
                )
            elif self._connected_to is None:
                self._last_problem = f"no studio answered at {target.url}"
            else:
                self._last_problem = f"the studio at {target.url} went away"
            logger.debug("Studio connection ended", exc_info=True)
        finally:
            if self._upstream is not None:
                self._upstream = None
                self._connected_to = None
                self._upstream_tools = []
                await self._announce()

    async def _refresh_tools(self) -> None:
        if self._upstream is not None:
            self._upstream_tools = (await self._upstream.list_tools()).tools

    async def _on_upstream_message(self, message: object) -> None:
        if not isinstance(message, types.ServerNotification):
            return
        if isinstance(message.root, types.ToolListChangedNotification):
            await self._refresh_tools()
            await self._announce(resources=False)
        elif isinstance(message.root, types.ResourceListChangedNotification):
            await self._announce(tools=False)

    async def _announce(self, *, tools: bool = True, resources: bool = True) -> None:
        session = self._downstream
        if session is None:
            return
        try:
            if tools:
                await session.send_tool_list_changed()
            if resources:
                await session.send_resource_list_changed()
        except Exception:
            # Best effort: a harness that already closed the session needs no announcement.
            logger.debug("list_changed not delivered", exc_info=True)

    # -- the downstream server -----------------------------------------

    def _capture_session(self) -> None:
        self._downstream = self.server.request_context.session

    def _own_tools(self) -> list[types.Tool]:
        return [
            types.Tool(
                name=STATUS_TOOL,
                description="Report whether this project's Haywire studio is connected and, if not, why.",
                inputSchema={"type": "object", "properties": {}},
            ),
            types.Tool(
                name=CONNECT_TOOL,
                description=(
                    "Connect to a studio on an explicit port, for a studio of another project that this "
                    "bridge does not find on its own. For this session only."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "port": {"type": "integer", "description": "The studio's port, e.g. 8124."},
                        "token": {
                            "type": "string",
                            "description": "A roster agent token, if that studio needs one.",
                        },
                    },
                    "required": ["port"],
                },
            ),
        ]

    def status(self) -> str:
        """Return the status tool's text: the connected studio, or why there is none."""
        if self._connected_to is not None:
            target = self._connected_to
            return f"Connected to the studio at {target.url} (found via {target.source})."
        return f"Not connected: {self._last_problem}. Project: {self.project}."

    def _register(self) -> None:
        server = self.server

        @server.list_tools()
        async def list_tools() -> list[types.Tool]:
            self._capture_session()
            return self._own_tools() + self._upstream_tools

        @server.call_tool(validate_input=False)
        async def call_tool(name: str, arguments: dict) -> types.CallToolResult | list[types.ContentBlock]:
            self._capture_session()
            if name == STATUS_TOOL:
                return _text(self.status())
            if name == CONNECT_TOOL:
                port = arguments.get("port")
                if not isinstance(port, int) or not 0 < port < 65536:
                    return types.CallToolResult(
                        content=_text(f"'port' must be 1-65535, got {port!r}."), isError=True
                    )
                token = arguments.get("token")
                self._manual = (port, token if isinstance(token, str) and token else None)
                return _text(
                    f"Connecting to the studio on port {port}; call {STATUS_TOOL} to see the result."
                )
            if self._upstream is None:
                return types.CallToolResult(content=_text(self.status()), isError=True)
            return await self._upstream.call_tool(name, arguments)

        @server.list_resources()
        async def list_resources() -> list[types.Resource]:
            self._capture_session()
            own = self._developer_resources()
            if self._upstream is not None:
                return (await self._upstream.list_resources()).resources + own
            return _local_resources() + own

        @server.read_resource()
        async def read_resource(uri) -> Iterable[ReadResourceContents]:
            self._capture_session()
            text = str(uri)
            if text.startswith(_DEV_PREFIX) and self.developer_root is not None:
                page = read_developer_doc(self.developer_root, text[len(_DEV_PREFIX) :])
                return [ReadResourceContents(content=page, mime_type="text/markdown")]
            if self._upstream is not None:
                result = await self._upstream.read_resource(uri)
                return [
                    ReadResourceContents(content=c.text, mime_type=c.mimeType)
                    for c in result.contents
                    if isinstance(c, types.TextResourceContents)
                ]
            if text == _MANIFEST_URI:
                return [
                    ReadResourceContents(
                        content=json.dumps(doc_manifest(), indent=2), mime_type="application/json"
                    )
                ]
            if text.startswith(_DOCS_PREFIX):
                return [
                    ReadResourceContents(
                        content=read_doc(text[len(_DOCS_PREFIX) :]), mime_type="text/markdown"
                    )
                ]
            raise FileNotFoundError(f"No resource at {text!r}")

    def _developer_resources(self) -> list[types.Resource]:
        if self.developer_root is None:
            return []
        return [
            types.Resource(
                uri=f"{_DEV_PREFIX}{entry['path']}",  # type: ignore[arg-type]  # AnyUrl accepts the string
                name=entry["title"],
                description=entry["scope"] or None,
                mimeType="text/markdown",
            )
            for entry in served_docs("developer", self.developer_root)
        ]

    async def serve(self, read_stream, write_stream) -> None:
        """Serve one harness session on these streams until it closes, connected to the studio meanwhile."""
        options = self.server.create_initialization_options(
            NotificationOptions(tools_changed=True, resources_changed=True)
        )
        async with anyio.create_task_group() as tg:
            tg.start_soon(self.run_upstream)
            await self.server.run(read_stream, write_stream, options)
            tg.cancel_scope.cancel()


def _local_resources() -> list[types.Resource]:
    resources = [
        types.Resource(
            uri=_MANIFEST_URI,  # type: ignore[arg-type]  # AnyUrl accepts the string at runtime
            name="docs manifest (index of all doc paths + titles)",
            mimeType="application/json",
        )
    ]
    resources += [
        types.Resource(uri=f"{_DOCS_PREFIX}{rel}", name=rel, mimeType="text/markdown")  # type: ignore[arg-type]
        for rel in list_docs()
    ]
    return resources


def run_bridge(project: Path, *, principal: str, document: Path | None, poll_s: float) -> int:
    """Run the bridge on this process's stdin and stdout until the harness closes them; return the exit code.

    Anything the Haywire code prints goes to stderr: stdout carries only the
    MCP protocol.
    """
    protocol_out = sys.stdout
    sys.stdout = sys.stderr
    bridge = Bridge(project, principal=principal, document=document, poll_s=poll_s)

    async def main() -> None:
        stdout = anyio.wrap_file(io.TextIOWrapper(protocol_out.buffer, encoding="utf-8"))
        async with stdio_server(stdout=stdout) as (read_stream, write_stream):
            await bridge.serve(read_stream, write_stream)

    anyio.run(main)
    return 0
