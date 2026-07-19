"""PROTOTYPE — wayfinder ticket 09 (mount prototype). THROWAWAY, do not ship.

Question this answers: does an official-SDK (mcp 1.28.1) Streamable HTTP MCP
server mounted at /mcp on the REAL studio's NiceGUI/FastAPI app coexist with
socket.io/uvicorn, with tools reading and mutating HaystackState via the
ambient DI context — and does the parent-lifespan session-manager trick work
as the SDK research (ticket 02) predicted?

Branch assumption (prototype skill): logic/integration spike, not UI.

Run:    uv run python .scratch/mcp-server/prototype/farmhand_mount_prototype.py
Check:  uv run python .scratch/mcp-server/prototype/client_check.py
"""

import asyncio
import contextlib
import threading

from nicegui import app, ui

from mcp.server.fastmcp import FastMCP

PORT = 8099  # prototype port — leaves a real studio on 8082 untouched

# --- MCP server (the Farmhand stand-in) -----------------------------------
# streamable_http_path="/" + full prefix in the mount = the 307-trap avoidance
# from ticket 02 / python-sdk #951.
mcp_server = FastMCP("farmhand-prototype", streamable_http_path="/")


def _affinity() -> dict:
    """Where is this tool actually running? (ticket 06 loop-affinity evidence)"""
    try:
        loop_running = asyncio.get_running_loop() is not None
    except RuntimeError:
        loop_running = False
    return {"thread": threading.current_thread().name, "on_event_loop": loop_running}


@mcp_server.tool()
async def studio_list_graphs() -> dict:
    """List open haystack entries (read tool)."""
    from haywire.core.di.context import get_library_state_container
    from haybale_haystack.state.haystack_state import HaystackState

    state = get_library_state_container().get(HaystackState)
    entries = [
        {
            "binding_id": e.binding_id,
            "display_name": e.display_name,
            "unsaved": e.unsaved,
            "is_executing": e.is_executing,
        }
        for e in state._entries.values()  # private access — prototype only
    ]
    return {"count": len(entries), "entries": entries, "affinity": _affinity()}


@mcp_server.tool()
async def haystack_create_graph() -> dict:
    """Create a new untitled graph (mutating tool — fires GraphDataMutated)."""
    from haywire.core.di.context import get_library_state_container
    from haybale_haystack.state.haystack_state import HaystackState

    state = get_library_state_container().get(HaystackState)
    entry = state.create_new()  # broadcasts GraphDataMutated itself
    return {
        "created": entry.binding_id,
        "display_name": entry.display_name,
        "affinity": _affinity(),
    }


# --- Mount + parent-lifespan wiring (the ticket-02 mandatory trick) --------
app.mount("/mcp", mcp_server.streamable_http_app())

# FINDING (first run): the obvious AsyncExitStack shape — enter in on_startup,
# aclose in on_shutdown — dies with "Attempted to exit cancel scope in a
# different task than it was entered in": NiceGUI runs each handler in its own
# task, and the session manager's anyio task group must be entered and exited
# in the SAME task. Fix: one long-lived runner task, signaled to stop.

_started: asyncio.Event | None = None
_stop: asyncio.Event | None = None
_runner: asyncio.Task | None = None


async def _mcp_runner():
    async with mcp_server.session_manager.run():
        print("PROTOTYPE: MCP session manager running (single runner task)")
        assert _started is not None and _stop is not None
        _started.set()
        await _stop.wait()
    print("PROTOTYPE: MCP session manager closed cleanly")


@app.on_startup
async def _start_mcp_session_manager():
    global _started, _stop, _runner
    _started, _stop = asyncio.Event(), asyncio.Event()
    _runner = asyncio.create_task(_mcp_runner())
    await _started.wait()


@app.on_shutdown
async def _stop_mcp_session_manager():
    if _stop is not None:
        _stop.set()
    if _runner is not None:
        await _runner


# --- Boot the REAL studio --------------------------------------------------
if __name__ in {"__main__", "__mp_main__"}:
    from haywire_studio.app import HaywireApp

    app_instance = HaywireApp()  # workspace root = cwd (monorepo, barn/ libraries)
    app.on_shutdown(app_instance.cleanup)
    app_instance.create_ui()
    ui.run(port=PORT, show=False, title="Haywire (MCP mount PROTOTYPE)", reload=False)
