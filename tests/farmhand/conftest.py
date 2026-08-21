"""Farmhand integration harness: app-shaped server (FastAPI + uvicorn thread), SDK client.

Mirrors the library_system idiom (full barn libraries, ambient-DI snapshot/
restore, never create_test_injector directly). One server per session; each
test gets a fresh ClientSession in its own asyncio.run (Playwright parked-loop
trap does not apply — these are not browser tests).
"""

from __future__ import annotations

import asyncio
import json
import socket
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
import uvicorn
from fastapi import FastAPI

from tests.conftest import _restore_ambient_di, _snapshot_ambient_di


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _make_server(tmp_root: Path, library_paths: list[str]):
    from haywire.core.di.config import set_global_injector, set_library_system
    from haywire.core.di.context import set_workspace_root
    from haywire.core.di.test_config import create_test_library_system
    from haywire_studio.farmhand.host import FarmhandHost
    from haywire_studio.security.document import SecurityDocument

    snap = _snapshot_ambient_di()
    # Set the ambient workspace_root BEFORE building the library system: AppState
    # on_enable (e.g. HaystackState) fires during service.initialize() and reads
    # get_workspace_root(), so it must already be set.
    set_workspace_root(str(tmp_root))
    service = create_test_library_system(
        workspace_root=str(tmp_root),
        library_paths=library_paths,
        load_libraries=True,
        enable_file_watching=False,
    )
    set_library_system(service)
    set_global_injector(service.injector)
    set_workspace_root(str(tmp_root))

    from haywire.core.signals import SignalDispatcher

    host = FarmhandHost(service, str(tmp_root), SignalDispatcher())
    port = _free_port()

    @asynccontextmanager
    async def lifespan(app):
        await host._on_startup()
        yield
        await host._on_shutdown()

    app = FastAPI(lifespan=lifespan)
    document = SecurityDocument()
    host.mount(port, document, app_target=app)

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 15
    while not server.started:
        if time.monotonic() > deadline:
            raise RuntimeError("Farmhand test server failed to start")
        time.sleep(0.05)

    handle = SimpleNamespace(
        base_url=f"http://127.0.0.1:{port}/mcp",
        token=None,
        service=service,
        port=port,
        host=host,
    )

    def teardown():
        server.should_exit = True
        thread.join(timeout=10)
        set_library_system(None)
        set_global_injector(None)
        _restore_ambient_di(snap)

    return handle, teardown


@pytest.fixture(scope="session")
def farmhand_server(project_root: Path, tmp_path_factory):
    workspace = tmp_path_factory.mktemp("farmhand_ws")
    handle, teardown = _make_server(workspace, [str(project_root / "barn")])
    yield handle
    teardown()


@pytest.fixture(scope="module")
def farmhand_bare_server(project_root: Path, tmp_path_factory):
    """Bare studio = builtin + haybale-studio only (the baseline's home; deviation note 2).

    haybale-studio is symlinked into an otherwise-empty library root so the
    scan loads it without the rest of the barn (its @library linked_libraries=[] —
    verified). No plugin libraries -> exactly the ten studio_* tools.
    """
    workspace = tmp_path_factory.mktemp("farmhand_bare_ws")
    libs = tmp_path_factory.mktemp("farmhand_bare_libs")
    (libs / "haybale-studio").symlink_to(project_root / "barn" / "haybale-studio")
    handle, teardown = _make_server(workspace, [str(libs)])
    yield handle
    teardown()


def call_tool_json(result) -> dict:
    """Parse a CallToolResult's structured-JSON text content."""
    assert result.content
    assert result.content[0].type == "text"
    return json.loads(result.content[0].text)


def make_caller(handle):
    from mcp.client.session import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    def farmhand_call(async_fn, message_handler=None):
        async def runner():
            headers = {"Authorization": f"Bearer {handle.token}"} if handle.token else {}
            async with streamablehttp_client(handle.base_url, headers=headers) as (read, write, _):
                kwargs = {"message_handler": message_handler} if message_handler else {}
                async with ClientSession(read, write, **kwargs) as session:
                    init = await session.initialize()
                    return await async_fn(session, init)

        return asyncio.run(runner())

    return farmhand_call


@pytest.fixture
def farmhand_call(farmhand_server):
    return make_caller(farmhand_server)
