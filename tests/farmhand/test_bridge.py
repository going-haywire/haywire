"""The Farmhand bridge: discovery, token lookup, and a session against a real Farmhand server."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import anyio
import psutil
import pytest
from mcp import types
from mcp.client.session import ClientSession
from mcp.shared.memory import create_client_server_memory_streams

from haywire.core.access import AccessTier
from haywire.core.docs.tree import front_matter, served_docs
from haywire_studio.auth.operations import add_agent
from haywire_studio.farmhand.bridge import (
    CONNECT_TOOL,
    STATUS_TOOL,
    Bridge,
    developer_docs,
    find_project_root,
    locate_studio,
    principal_token,
    product_index,
    read_developer_doc,
)

DEAD_PID = 2**22 + 12345  # above every default pid_max, so never a live process


def _sidecar(folder: Path, *, port: int, pid: int | None = None, auth_required: bool = False) -> None:
    haywire = folder / ".haywire"
    haywire.mkdir(parents=True, exist_ok=True)
    ident = {
        "pid": os.getpid() if pid is None else pid,
        "port": port,
        "url": f"http://127.0.0.1:{port}",
        "started_at": psutil.Process(os.getpid()).create_time() if pid is None else time.time(),
        "auth_required": auth_required,
    }
    (haywire / "studio.json").write_text(json.dumps(ident), encoding="utf-8")


def test_project_root_is_the_nearest_folder_holding_haywire(tmp_path):
    (tmp_path / ".haywire").mkdir()
    deep = tmp_path / "barn" / "lib"
    deep.mkdir(parents=True)
    assert find_project_root(deep) == tmp_path.resolve()


def test_project_root_falls_back_to_the_start_folder(tmp_path):
    assert find_project_root(tmp_path) == tmp_path.resolve()


def test_locate_studio_reads_the_project_sidecar(tmp_path):
    _sidecar(tmp_path, port=8130, auth_required=True)
    target = locate_studio(tmp_path)
    assert target is not None
    assert target.url == "http://127.0.0.1:8130/mcp/"
    assert target.auth_required is True
    assert target.source == "sidecar"


def test_locate_studio_ignores_a_dead_studio(tmp_path):
    _sidecar(tmp_path, port=8130, pid=DEAD_PID)
    assert locate_studio(tmp_path) is None


def test_locate_studio_finds_a_project_one_folder_down(tmp_path):
    _sidecar(tmp_path / "demo", port=8131)
    _sidecar(tmp_path / "old", port=8132, pid=DEAD_PID)
    target = locate_studio(tmp_path)
    assert target is not None
    assert target.url == "http://127.0.0.1:8131/mcp/"
    assert target.project == tmp_path / "demo"


def test_the_project_itself_wins_over_folders_below(tmp_path):
    _sidecar(tmp_path, port=8133)
    _sidecar(tmp_path / "demo", port=8134)
    target = locate_studio(tmp_path)
    assert target is not None
    assert target.url == "http://127.0.0.1:8133/mcp/"


def test_principal_token_reads_an_agent_principal(tmp_path):
    document = tmp_path / "security.json"
    agent = add_agent("farmhand", AccessTier.EDIT, path=document)
    assert principal_token("farmhand", document) == agent.token


def test_principal_token_is_none_without_that_principal(tmp_path):
    document = tmp_path / "security.json"
    add_agent("someone-else", AccessTier.EDIT, path=document)
    assert principal_token("farmhand", document) is None


def test_front_matter_reads_scalar_fields():
    text = "---\nstatus: draft\nserve: product\nsee-also:\n  - a.md\nscope: 'One line'\n---\n# Title\n"
    assert front_matter(text) == {"status": "draft", "serve": "product", "scope": "One line"}


def test_front_matter_is_empty_without_a_leading_block():
    assert front_matter("# Title\n---\nserve: product\n---\n") == {}


def test_the_index_lists_the_pages_served_to_every_project():
    index = product_index()
    assert STATUS_TOOL in index
    assert "farmhand://docs/components/nodes/node-canon.md" in index
    assert "farmhand://docs/_manifest" in index
    assert "start it with `uv run haywire studio start` in the project" in index


def _bridge_session(bridge: Bridge, scenario):
    """Run ``scenario(session, notes)`` against ``bridge`` over in-memory streams; return its result."""

    async def runner():
        notes: list[str] = []

        async def on_message(message):
            if isinstance(message, types.ServerNotification):
                notes.append(type(message.root).__name__)

        async with create_client_server_memory_streams() as (client_streams, server_streams):
            async with anyio.create_task_group() as tg:
                tg.start_soon(bridge.serve, *server_streams)
                async with ClientSession(*client_streams, message_handler=on_message) as session:
                    await session.initialize()
                    result = await scenario(session, notes)
                tg.cancel_scope.cancel()
        return result

    return anyio.run(runner)


async def _wait_for(predicate, timeout_s: float = 20.0) -> None:
    with anyio.fail_after(timeout_s):
        while not await predicate():
            await anyio.sleep(0.05)


def test_without_a_studio_the_bridge_serves_its_own_tools_and_the_docs(tmp_path):
    bridge = Bridge(tmp_path, poll_s=0.05)

    async def scenario(session, _notes):
        tools = {t.name for t in (await session.list_tools()).tools}
        status = (await session.call_tool(STATUS_TOOL, {})).content[0].text
        resources = {str(r.uri) for r in (await session.list_resources()).resources}
        manifest = await session.read_resource("farmhand://docs/_manifest")
        return tools, status, resources, manifest

    tools, status, resources, manifest = _bridge_session(bridge, scenario)
    assert tools == {STATUS_TOOL, CONNECT_TOOL}
    assert status.startswith("Not connected: no studio is running for this project")
    assert "farmhand://docs/components/nodes/node-canon.md" in resources
    assert json.loads(manifest.contents[0].text)


def test_the_bridge_reports_a_studio_that_wants_a_missing_principal(tmp_path):
    _sidecar(tmp_path, port=8135, auth_required=True)
    bridge = Bridge(tmp_path, document=tmp_path / "security.json", poll_s=0.05)

    async def scenario(session, _notes):
        async def reported():
            text = (await session.call_tool(STATUS_TOOL, {})).content[0].text
            return "haywire user add farmhand --agent" in text

        await _wait_for(reported)
        return True

    assert _bridge_session(bridge, scenario)


@pytest.mark.timeout(120)
def test_the_studio_s_tools_appear_when_it_comes_up_and_go_when_it_stops(tmp_path, farmhand_server):
    bridge = Bridge(tmp_path, poll_s=0.05)

    async def scenario(session, notes):
        before = {t.name for t in (await session.list_tools()).tools}
        _sidecar(tmp_path, port=farmhand_server.port)

        async def studio_tools_listed():
            return "haybale-studio_status" in {t.name for t in (await session.list_tools()).tools}

        await _wait_for(studio_tools_listed)
        result = await session.call_tool("haybale-studio_status", {})
        connected = (await session.call_tool(STATUS_TOOL, {})).content[0].text

        (tmp_path / ".haywire" / "studio.json").unlink()

        async def studio_tools_gone():
            return "haybale-studio_status" not in {t.name for t in (await session.list_tools()).tools}

        await _wait_for(studio_tools_gone)
        return before, result, connected, list(notes)

    before, result, connected, notes = _bridge_session(bridge, scenario)
    assert before == {STATUS_TOOL, CONNECT_TOOL}
    assert not result.isError
    assert connected.startswith(f"Connected to the studio at http://127.0.0.1:{farmhand_server.port}/mcp/")
    assert notes.count("ToolListChangedNotification") >= 2


def _developer_project(tmp_path: Path) -> Path:
    project = tmp_path / "repo"
    pages = project / "docs" / "collaboration"
    pages.mkdir(parents=True)
    (project / "pyproject.toml").write_text(
        '[tool.haywire.agents]\ndeveloper-docs = "docs"\n', encoding="utf-8"
    )
    (pages / "workflow.md").write_text(
        "---\nserve: developer\nscope: Read before a commit\n---\n# The workflow\nRule.\n", encoding="utf-8"
    )
    (pages / "notes.md").write_text("# Notes\n", encoding="utf-8")
    return project


def test_developer_docs_come_from_the_project_s_declaration(tmp_path):
    project = _developer_project(tmp_path)
    assert developer_docs(project) == (project / "docs").resolve()
    assert developer_docs(tmp_path) is None


def test_the_index_lists_the_declared_developer_pages(tmp_path):
    index = product_index(developer_docs(_developer_project(tmp_path)))
    assert "- farmhand://dev/collaboration/workflow.md (The workflow): Read before a commit" in index
    assert "notes.md" not in index
    assert "start it as farmhand://dev/collaboration/workflow.md says (*Live check*)" in index
    assert "uv run haywire studio start" not in index


def test_a_developer_page_is_read_from_its_folder_and_never_outside_it(tmp_path):
    root = developer_docs(_developer_project(tmp_path))
    assert root is not None
    assert "Rule." in read_developer_doc(root, "collaboration/workflow.md")
    with pytest.raises(FileNotFoundError):
        read_developer_doc(root, "../pyproject.toml")


def test_the_bridge_serves_developer_pages_without_a_studio(tmp_path):
    bridge = Bridge(_developer_project(tmp_path), poll_s=0.05)

    async def scenario(session, _notes):
        init_resources = {str(r.uri) for r in (await session.list_resources()).resources}
        page = await session.read_resource("farmhand://dev/collaboration/workflow.md")
        return init_resources, page.contents[0].text

    resources, text = _bridge_session(bridge, scenario)
    assert "farmhand://dev/collaboration/workflow.md" in resources
    assert "Rule." in text


def test_core_declares_its_workflow_page():
    core = Path(__file__).resolve().parents[2]
    root = developer_docs(core)
    assert root is not None
    entries = {e["path"] for e in served_docs("developer", root)}
    assert "collaboration/workflow.md" in entries
