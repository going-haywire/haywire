# Cross-Session Event Channel Redesign

**Date:** 2026-04-15
**Status:** Design approved, implementation plan pending

## Summary

Consolidate cross-session event broadcasting into a single honest channel owned
by `SessionManager`, move graph-validation side effects onto the owner that
already has the graph (`Haystack`), and delete the dead `entry.sessions`
bookkeeping that was never used for dispatch.

## Motivation

`HaywireApp._subscribe_entry_validation` ([app.py:252][app-subscribe]) currently
closes over three unrelated concerns that happen to all fire on graph
validation:

1. **Stop-on-reassembly** — if execution is running and the validation result
   requires graph reassembly, stop execution.
2. **Mark unsaved** — flip `entry.unsaved = True` on data-mutating validation.
3. **Cross-session broadcast** — call `session_manager.broadcast_data_mutation`
   so peer sessions refresh.

Only (3) is genuinely app-scoped. (1) and (2) operate on `GraphEntry` state and
belong with the entry's owner. Meanwhile the broadcast path itself is split
between `SessionManager.broadcast_data_mutation` (with a `graph_path` filter
nobody actually needs) and scattered local `notify_context_changed` calls at
producers that only want to tell their own session.

The producer-side inconsistency is the tell: today, saving a graph fires
`broadcast_data_mutation` *and* a separate local `notify_context_changed` at
adjacent lines, with different event shapes. Undo/redo fire local-only by
accident. Cross-session fan-out depends on which editor happens to remember to
call `broadcast_data_mutation`.

## Design

### New producer API: `Session.notify_cross_session_context_change`

`Session` gains a second notify method:

```python
def notify_context_changed(self, event):
    """Local fan-in: forward event to this session's orchestrator."""
    # unchanged

def notify_cross_session_context_change(self, event):
    """Fan event out to all sessions (including self) via SessionManager."""
    self._session_manager.broadcast(event)
```

Producers pick the method that describes what they mean:

- Selection changes, mode changes, local UI state → `notify_context_changed`
- Graph data mutations that peer sessions need to see →
  `notify_cross_session_context_change`

The originating session receives the event through fan-out (via the
`SessionManager.broadcast` loop), giving a single code path for all sessions
regardless of origin.

### `SessionManager.broadcast(event)`

Replaces `broadcast_data_mutation`:

```python
def broadcast(self, event: ContextChangedEvent) -> None:
    for session_id, session in list(self._sessions.items()):
        try:
            session.notify_context_changed(event)
        except Exception as e:
            logger.warning(f"broadcast failed for session {session_id[:8]}: {e}")
```

No filtering. Every consumer re-reads its own ground-truth state when notified,
so a session receiving an event for a graph it doesn't display no-ops. The
existing `graph_path` filter on `broadcast_data_mutation` was a premature
optimization — at typical session counts (1–3 browser tabs) the cost of a
spurious `notify_context_changed` is negligible, and the filter was arguably
wrong for the haystack-list consumer which wants to hear every graph's state.

### `Session` constructor injection

`Session.__init__` gains `session_manager`:

```python
def __init__(self, project_state, workspace_manager, session_manager):
    ...
    self._session_manager = session_manager
```

`SessionManager.create_session` injects `self`:

```python
def create_session(self, **session_kwargs) -> "Session":
    from haywire.ui.session import Session
    session = Session(session_manager=self, **session_kwargs)
    self._sessions[session.session_id] = session
    return session
```

No callers of `create_session` change — the injection is internal.

### `Haystack` owns validation wiring

`Haystack.__init__` gains `session_manager`. The external
`validation_subscriber` callback parameter is **removed** — `Haystack`
subscribes internally at entry-creation sites.

At each of the three entry-creation points in [haystack.py][haystack] —
`create_new` ([:150][haystack-create]), `open_graph` ([:173][haystack-open]),
and the graph loop in `load_haystack` ([:450][haystack-load]) — replace the
current `self._validation_subscriber(entry)` call with:

```python
entry.graph.subscribe_to_validation(
    lambda result, _entry=entry: self._on_entry_validation(_entry, result)
)
```

And `Haystack._on_entry_validation` absorbs all three concerns from the old
app-level handler:

```python
def _on_entry_validation(self, entry: GraphEntry, result: ValidationResult) -> None:
    """Handle a validation result on a graph entry.

    Three concerns, all rooted in the fact that a graph under this
    haystack's ownership just validated:

    1. Stop execution if the result requires graph reassembly.
    2. Mark the entry unsaved if the result mutated data.
    3. Broadcast DATA_MUTATED so peer sessions refresh.
    """
    if entry.is_executing and result.has_changes() and result.graph is not None:
        if result.graph.requires_graph_reassembly():
            entry.stop_execution()

    if bool(result.nodes or result.edges):
        entry.unsaved = True
        event = ContextChangedEvent(change_type=ContextChangeType.DATA_MUTATED)
        self._session_manager.broadcast(event)
```

`GraphEntry` stays a pure dataclass with no behavior beyond the existing
`start_execution`/`stop_execution` execution-lifecycle methods.

### Delete `entry.sessions` bookkeeping

`entry.sessions: Set[str]` is vestigial. Only two runtime usages exist
([haystack_editor.py:329][hs-editor-detach] and
[graph_editor.py:474][graph-editor-detach]), both of which just maintain the
set itself — nothing reads it for dispatch, lifecycle, or behavior.

Remove:

- `GraphEntry.sessions` field
- `Haystack.session_attach`, `session_detach`, `sessions_for_entry`
- Callers that invoked those methods

The `session_id` parameter on `Haystack.create_new(session_id)` and
`Haystack.open_graph(path, session_id)` also becomes dead — remove it from the
signatures and update call sites ([app.py:239][app-restore-open],
plus any new-graph creation paths in the studio editors).

### Producer migration

Five call sites change. Three currently use `broadcast_data_mutation`:

- [graph_editor.py:297][prod-save] — save path, existing graph
- [graph_editor.py:451][prod-save-as] — save-as path
- [haystack_editor.py:944][prod-haystack] — haystack editor's
  `_broadcast_mutation`

Two currently fire local-only `notify_context_changed(DATA_MUTATED)` and
should become cross-session:

- [graph_editor.py:243][prod-undo] — undo
- [graph_editor.py:258][prod-redo] — redo

All five become:

```python
session.notify_cross_session_context_change(
    ContextChangedEvent(
        change_type=ContextChangeType.DATA_MUTATED,
        source_editor="graph_editor",  # or appropriate origin
    )
)
```

**Behavior change (intentional):** undo/redo in one tab now re-syncs peer
tabs. This is the correct behavior — peer tabs viewing the same graph should
reflect the state change.

The [haystack_editor.py:918][prod-hs-notify] `_notify_data_mutated` helper —
currently local-only — should also become cross-session. Haystack-level
changes (add/remove graphs) are inherently peer-visible.

### `HaywireApp` cleanup

Remove from [app.py][app]:

- `_subscribe_entry_validation` (lines 252–265)
- `_on_graph_validation_for_entry` (lines 169–175)
- `_result_mutates_data` (lines 34–40)

Update the `Haystack` construction at [app.py:147–151][app-haystack]: pass
`session_manager` instead of `validation_subscriber`.

## Out of scope

- **Moving `GraphCanvasManager`'s `DATA_MUTATED` handling** off the cross-session
  channel. The canvas subscribes to validation directly
  ([graph_canvas_manager.py:103][canvas]), so it already handles local updates
  without going through `DATA_MUTATED`. The existing
  [graph_editor.py:49][consumer-canvas] `DATA_MUTATED` handler is only relevant
  for cross-session sync, which self-fanout preserves. No change needed; cleaning
  up any residual duplication is a follow-up.
- **Generalizing the filter mechanism.** `SessionManager.broadcast` takes only an
  event. If a future event type needs filtered dispatch, that's the time to
  introduce a filter — YAGNI for now.

## Testing

- `Session` instantiation in tests: `_FakeSession` in
  `tests/ui/test_app_shell.py` is already a test double, unaffected. No real
  `Session(...)` calls in the test suite.
- `Haystack` construction in tests changes signature — update fixtures to pass
  `session_manager` (a `MagicMock` suffices).
- Add/update tests asserting:
  - `SessionManager.broadcast(event)` calls `notify_context_changed` on every
    registered session
  - `Haystack._on_entry_validation` stops execution, marks unsaved, and
    broadcasts for a mutating result
  - `notify_cross_session_context_change` routes through `SessionManager`
  - Undo/redo now trigger cross-session broadcasts
- Full `pytest` run after migration.

## File inventory

**Modified:**

- `packages/haywire-core/src/haywire/ui/session.py` — constructor, new
  `notify_cross_session_context_change`
- `packages/haywire-core/src/haywire/ui/session_manager.py` — `broadcast`
  method, inject `session_manager` in `create_session`, delete
  `broadcast_data_mutation`
- `packages/haywire-studio/src/haywire_studio/haystack.py` — accept
  `session_manager`, own validation wiring, `_on_entry_validation`, remove
  `entry.sessions` machinery, drop `validation_subscriber` param, drop
  `session_id` params
- `packages/haywire-studio/src/haywire_studio/app.py` — delete three helpers,
  rewire `Haystack` construction
- `barn/haybale-studio/haybale_studio/editors/graph_editor.py` — 5 producer
  call sites, remove session_detach call
- `barn/haybale-studio/haybale_studio/editors/haystack_editor.py` — 2 producer
  call sites, remove session_detach loop

**Unmodified but worth noting:**

- `packages/haywire-core/src/haywire/ui/context_events.py` — no field changes;
  `graph_path` is not needed
- `packages/haywire-core/src/haywire/ui/graph_canvas/graph_canvas_manager.py`
  — direct validation subscription stays as-is

[app]: ../../packages/haywire-studio/src/haywire_studio/app.py
[app-subscribe]: ../../packages/haywire-studio/src/haywire_studio/app.py#L252
[app-haystack]: ../../packages/haywire-studio/src/haywire_studio/app.py#L147
[app-restore-open]: ../../packages/haywire-studio/src/haywire_studio/app.py#L239
[haystack]: ../../packages/haywire-studio/src/haywire_studio/haystack.py
[haystack-create]: ../../packages/haywire-studio/src/haywire_studio/haystack.py#L150
[haystack-open]: ../../packages/haywire-studio/src/haywire_studio/haystack.py#L173
[haystack-load]: ../../packages/haywire-studio/src/haywire_studio/haystack.py#L450
[canvas]: ../../packages/haywire-core/src/haywire/ui/graph_canvas/graph_canvas_manager.py#L103
[consumer-canvas]: ../../barn/haybale-studio/haybale_studio/editors/graph_editor.py#L49
[hs-editor-detach]: ../../barn/haybale-studio/haybale_studio/editors/haystack_editor.py#L329
[graph-editor-detach]: ../../barn/haybale-studio/haybale_studio/editors/graph_editor.py#L474
[prod-save]: ../../barn/haybale-studio/haybale_studio/editors/graph_editor.py#L297
[prod-save-as]: ../../barn/haybale-studio/haybale_studio/editors/graph_editor.py#L451
[prod-haystack]: ../../barn/haybale-studio/haybale_studio/editors/haystack_editor.py#L944
[prod-undo]: ../../barn/haybale-studio/haybale_studio/editors/graph_editor.py#L243
[prod-redo]: ../../barn/haybale-studio/haybale_studio/editors/graph_editor.py#L258
[prod-hs-notify]: ../../barn/haybale-studio/haybale_studio/editors/haystack_editor.py#L918
