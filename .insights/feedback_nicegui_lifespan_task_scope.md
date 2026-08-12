---
name: NiceGUI startup/shutdown handlers run in different tasks — anyio contexts must not span them
description: Entering an anyio-task-group-backed async context manager in app.on_startup and exiting it in app.on_shutdown crashes shutdown with a cancel-scope error. Use a single long-lived runner task instead.
type: feedback
---

# NiceGUI startup/shutdown handlers run in different tasks — anyio contexts must not span them

## The trap

Entering an anyio-task-group-backed async context manager in `app.on_startup` and
exiting it in `app.on_shutdown` crashes shutdown with:

```
RuntimeError: Attempted to exit cancel scope in a different task than it was entered in
```

NiceGUI awaits each startup/shutdown handler as its own task, and anyio cancel
scopes must be entered and exited in the same task. The obvious
`AsyncExitStack` shape — `stack.enter_async_context(cm)` at startup,
`stack.aclose()` at shutdown — is therefore structurally wrong under NiceGUI,
even though it is the documented pattern for the MCP SDK's
`StreamableHTTPSessionManager.run()` (and reads perfectly innocently).

The failure only appears at shutdown ("Application shutdown failed. Exiting."),
so it survives normal dev runs and reviews.

## The safe pattern: one long-lived runner task

Enter and exit the context inside a single task; signal it to stop:

```python
_started, _stop, _runner = asyncio.Event(), asyncio.Event(), None

async def _runner_fn():
    async with session_manager.run():   # enter + exit in THIS task
        _started.set()
        await _stop.wait()

@app.on_startup
async def _start():
    global _runner
    _runner = asyncio.create_task(_runner_fn())
    await _started.wait()

@app.on_shutdown
async def _shutdown():
    _stop.set()
    await _runner
```

## Where this was found

Wayfinder ticket `.scratch/mcp-server/issues/09-mount-prototype.md` (Farmhand
MCP mount prototype, 2026-07-19): mounting the official `mcp` SDK's Streamable
HTTP app on the studio's FastAPI instance. Applies to ANY anyio/task-group
context wired across NiceGUI lifecycle handlers, not just MCP.
