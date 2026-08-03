# Stepper — multi-step flows

`haywire.ui.components.stepper` is the shell for operations that are worth
breaking into steps: the ones that take seconds, touch the network, or write
something the user would want to see coming.

The Share Project wizard established the shape; Refresh Libraries and
Uninstall Library followed. Anything with the same profile (installing and
updating libraries, adding a marketplace source) should use it rather than
grow its own sequence of modals.

A stepper is also how you replace a confirm modal whose warning is a *claim*.
The old uninstall modal asserted that "any graph nodes using this library will
show as errors" without checking; the flow's impact step greps every
`*.haywire` in the workspace for `"<library_id>:"` and reports what it finds.
If a modal is telling the user something the app could verify, that is the
signal to make it a step.

## Why steps

Three properties, in order of importance:

1. **Plan before apply.** Every mutation has a preceding step that only reads
   and reports. The user sees what a step would change *before* it changes
   anything, and abandoning the flow early leaves nothing behind. This is a
   property of how the flow is decomposed, not of the shell — a flow that
   writes in its first step gets no benefit from being a stepper.
2. **The wait is attributed.** Blocking work runs in a thread with its own
   step's button in a loading state, so the progress label always names what
   is being waited on. A single "Refreshing…" spinner over four different
   operations tells the user nothing.
3. **Failure is local.** A failed step stays put with an inline error and a
   Retry button. Nothing is rolled back, because nothing was mutated past the
   point of failure.

## The pieces

| Piece | What it gives you |
|---|---|
| `StepFlow` | `step`/`error`/`warnings`/`log_lines`, `retry()`, `fail()`, `push_log()` |
| `show_step_flow(flow, panels, …)` | the popup, progress bar, error banner, warning rows, step dispatch |
| `advance` / `busy_advance` | coroutine wrappers that re-render, the second with a loading button |

You write: a `StepFlow` subclass with `STEPS`, `STEP_TITLES`, and one
`advance_from_<step>` coroutine each; one panel function per step; a `copy.py`
holding the step vocabulary.

## Writing a flow

```python
# copy.py — the vocabulary lives apart from the logic
STEPS = ("sources", "fetched", "resolved", "applied")
STEP_TITLES = {"sources": "Sources", "fetched": "Fetch", ...}

# _state.py — no NiceGUI imports, so it is testable without a browser
class RefreshFlow(StepFlow):
    STEPS = STEPS
    STEP_TITLES = STEP_TITLES

    async def advance_from_sources(self) -> None:
        self.retry()                       # 1. clear the previous error
        try:
            # 2. blocking work goes to a thread — on the event loop it
            #    starves NiceGUI's heartbeat and the browser drops the
            #    connection
            self.fetched = await asyncio.to_thread(self.state.fetch_sources)
        except MalformedMarketplaceError as exc:
            self.fail(exc)                 # 3. record and stay put
            return
        self.step = "fetched"              # 4. advance only on success

# chrome.py — wiring
flow.popup = show_step_flow(
    flow, panels, title="Refresh Libraries", on_done=..., error_detail=...,
)
```

Panels render one step's body and end with the button that advances it:

```python
def _panel_sources(flow: RefreshFlow, rerender: Callable[[], None]) -> None:
    ui.label("These sources will be contacted:").classes("text-xs hw-text-dim")
    ...
    with ui.row().classes("w-full justify-end gap-2"):
        fetch = ui.button("Fetch").props("flat dense").style("color: var(--hw-positive);")
        fetch.on_click(lambda: busy_advance(rerender, fetch, flow.advance_from_sources))
```

## Rules that are load-bearing

- **Return the coroutine from a click handler; never schedule it.** `advance`
  and `busy_advance` both return rather than call `background_tasks.create`.
  NiceGUI wraps a returned Awaitable with the parent slot before scheduling,
  which is what keeps `ui.notify()` and element creation working inside the
  step. See [feedback_nicegui_async.md](../../../.insights/feedback_nicegui_async.md).
- **`busy_advance` for anything that can take a second**, `advance` for
  in-memory transitions. Without the loading state a threaded step looks dead.
- **Keep the state machine free of NiceGUI imports.** Every flow's tests drive
  `advance_from_*` directly and assert on `step`/`error`; that only stays
  possible if rendering lives in the panels.
- **Depend on a Protocol, not the concrete state class**, when the flow only
  needs a few methods — see `RefreshSource` in the refresh flow. It keeps DI
  and the workspace root out of the tests.
- **`error_detail` is for structured failures.** Both existing flows use it:
  the share wizard renders one message/remedy row per `PreconditionFailure`,
  the refresh flow swaps in an Edit File button for the one error a retry
  cannot fix. Return `False` to fall back to the plain message.

## Inform, or block?

An impact step can either refuse to advance or show what it found and let the
user decide. Both exist:

- **Block** when the operation is *guaranteed* to break something and the app
  can say so unambiguously — the share wizard's preconditions step, or the
  `@library` dependents gate on the Uninstall button (which lives upstream of
  the flow, in `LibraryOverviewEditor`, and is why the uninstall flow never
  re-checks dependents: they are empty by construction by the time it opens).
- **Inform + explicit confirm** when the consequence is real but the call is
  the user's — graphs that reference a library, or pip packages that require
  it. The uninstall flow always advances from `impact` to `confirm`; the
  danger-coloured button on `confirm` is the gate.

Prefer informing. A block the user cannot override turns into a dead end when
the app's model is wrong, and the flow's whole value is that the user now has
the facts.

## Warnings vs errors

`retry()` clears the error but deliberately keeps warnings. An error is a
condition a retry might change; a warning describes something that stays true
(a stale `uv.lock`, libraries that went stale on this refresh). Warnings
accumulate down the flow and render above the current panel.
