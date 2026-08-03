# Multi-step flows use the shared stepper, and only the last step may write

`haywire.ui.components.stepper` is the shell behind the Share Project wizard
and the Refresh Libraries flow. Full guide:
[docs/architecture/design/stepper-arch.md](../docs/architecture/design/stepper-arch.md).

Two things that bite if you don't know them:

## The plan/apply split is in the pipeline, not the UI

A stepper only earns its keep if the underlying operation can *stop* between
reading and writing. `marketstall.refresh()` originally did all seven steps in
one call, ending with the project-file write — so the UI could only report
what it had already done. The flow needed `fetch_sources()` / `resolve()` /
`apply()` in core first; the stepper came second.

So when you add a flow for install/update/uninstall, expect the same shape:
split the operation into read-only phases plus one terminal mutating phase, and
only then build panels over it. If every phase mutates, the stepper buys you
nothing but clicks.

`refresh()` still exists as the compose-all-three convenience — the farmhand
tool and the first-enable auto-refresh use it, and the phased path is for the
UI. Don't delete it.

## Click handlers must RETURN the coroutine

`advance()` and `busy_advance()` return the coroutine rather than scheduling
it. NiceGUI wraps a returned Awaitable with the parent slot before scheduling,
which is what keeps `ui.notify()` and element creation alive inside the step.
Calling `background_tasks.create()` instead hands the work a task with an empty
slot stack and `ui.notify()` crashes — see
[feedback_nicegui_async.md](feedback_nicegui_async.md).

## Smaller traps

- `Popup` has no `"close"` event; the API is `popup.on_close(cb)`. `show_step_flow`
  wires `on_done` through it, so a terminal panel's Done button must only
  dismiss — passing `on_done` to the panel *as well* fires it twice.
- `retry()` clears `error` but deliberately keeps `warnings`: a warning
  describes a condition a retry does not change.
- Type panels as `Panel[YourFlow]` (the alias is generic in the flow type) —
  otherwise every entry in the panel dict needs a `type: ignore`.
