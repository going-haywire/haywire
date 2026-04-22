# Haystack entry ownership + dirty-removal confirmation

**Date:** 2026-04-15
**Status:** Design approved, ready for implementation plan
**Scope:** B — structural refactor + dirty-removal confirmation UX (breaking change)

## Problem

Today, opening a graph in Haywire goes through **two paths that feel muddled**:

1. Clicking a file in the `FileBrowserEditor` → calls `HaywireApp.open_graph_file` → calls `HaywireApp.open_graph_in_tab`.
2. Clicking a row / "+" in the `HaystackEditor` → calls `HaywireApp.create_new_graph` (or `open_graph_file`) → calls `HaywireApp.open_graph_in_tab`.

Both paths silently mutate shared state:

- The `Haystack` (the in-memory registry of open graphs) grows a new entry.
- Three helper methods live on `HaywireApp` — `open_graph_file`, `create_new_graph`, `open_graph_in_tab` — that mix per-session concerns (context updates, reveal events) with app-level concerns (entry creation, validation subscription). `HaywireApp` is shared across browser sessions, so the per-session parts are on the wrong class.

The user-visible mirror of this confusion: **removing a dirty graph from the Haystack discards unsaved work without asking.** `HaystackEditor._on_entry_delete` calls `haystack.remove_entry` directly, no prompt, no save path.

## Goal

Land three coordinated changes that fix both the architectural smell and the user-visible data-loss risk:

1. **Haystack owns graph-entry creation.** Inject the graph factory and the validation-subscribe callback at Haystack construction. Callers pass a `session_id`, not a factory.
2. **AppShell owns tab orchestration.** Replace `HaywireApp.open_graph_in_tab` with a new `ContextChangeType.OPEN_GRAPH_REQUESTED` event that `AppShell` (per-session) handles.
3. **Removing a dirty entry prompts.** `HaystackEditor._on_entry_delete` opens a Save / Save As / Discard / Cancel dialog when the entry is dirty (`unsaved=True` or `path=None`).

No backward-compat shims. The old methods are deleted outright.

## Non-goals

- **No renames.** The ubiquitous-language glossary (`docs/documentation/design/ubiquitous_terms.md` lines 117, 151, 243) explicitly rejects calling this concept "Workspace" or "Session"; `Haystack` stays `Haystack`, `HaystackEditor` stays `HaystackEditor`.
- **No beforeunload warning.** Warning the user before they close the browser tab with an unsaved Haystack is a worthwhile follow-up, but it has its own browser quirks (message customization limits, interaction gating) and deserves a separate spec.
- **No change to Haystack persistence.** Startup still loads `workspace_state.haystack`; unsaved in-memory entries (`__new_N__`, `__untitled__`) still do not survive restart. This matches standard text-editor behaviour.
- **No change to the file browser's click behaviour.** Clicking a `.haywire` file still adds it to the Haystack and opens a tab. Under the clearer mental model ("Haystack is the live registry, a saved haystack TOML is a separate artifact"), this is no longer a "silent add" to a persisted thing — it's expected.
- **No new factory flexibility.** Haystack holds one factory for its lifetime; nothing today suggests we need more.

## Architecture

```text
BEFORE                                           AFTER
──────                                           ─────
file_browser  haystack_editor  restore_tabs      file_browser  haystack_editor  restore_tabs
     │              │                │                │              │                │
     ▼              ▼                ▼                ▼              ▼                ▼
  HaywireApp.open_graph_file()                    haystack.open_graph(path, session_id)
  HaywireApp.create_new_graph()                   haystack.create_new(session_id)
  HaywireApp.open_graph_in_tab()                     │
     │                                                │ returns entry
     ▼                                                ▼
  Haystack (plain registry, factory-per-call)    session.notify_context_changed(
                                                     OPEN_GRAPH_REQUESTED, entry, editor_key)
                                                     │
                                                     ▼
                                                  AppShell._dispatch_event
                                                  → detach / attach / update context
                                                  → fire ACTIVE_GRAPH_CHANGED
```

### Ownership rules (after the refactor)

| Concern | Owner | Why |
| --- | --- | --- |
| Create/reuse `GraphEntry` for a file path | `Haystack` | File-centric registry; naturally app-wide / shared |
| Subscribe validation handler to new entries | `Haystack` (via injected callback) | Entry creation is the moment when wiring happens |
| Attach session → entry | `Haystack` | Pure registry bookkeeping |
| Detach session from previous entry | `AppShell._handle_open_graph_requested` | Per-session concern |
| Update `context.active_graph*` | `AppShell._handle_open_graph_requested` | Per-session concern |
| Reveal the tab | `AppShell._handle_open_graph_requested` → `ACTIVE_GRAPH_CHANGED` | Per-session UI orchestration |
| Ask before discarding dirty work | `HaystackEditor._open_remove_confirm_dialog` | UI-layer concern; dialog is a view |

## Components

### 1. `Haystack` changes

Construction takes three required arguments. No `Optional` / `= None` defaults — in production every Haystack has a workspace root and both callbacks; tests pass stub callables when they don't care about the behaviour.

```python
GraphFactory = Callable[[str, str], Tuple[BaseGraph, Editor]]
ValidationSubscriber = Callable[[GraphEntry], None]

class Haystack:
    def __init__(
        self,
        workspace_root: Path,
        graph_factory: GraphFactory,
        validation_subscriber: ValidationSubscriber,
    ):
        self._entries: Dict[str, GraphEntry] = {}
        self._new_counter: int = 0
        self._workspace_root = workspace_root
        self._graph_factory = graph_factory
        self._validation_subscriber = validation_subscriber
```

**Dead-code cleanup (same refactor).** Several Haystack methods have `if self._workspace_root is None` branches that cannot fire once `workspace_root` is required. Delete those branches in:

- `_haystacks_dir` — remove the `if self._workspace_root is None: return None` guard. Return type becomes `Path` (not `Optional[Path]`).
- `list_haystacks` — remove the `hdir is None` check.
- `save_haystack` — remove the `hdir is None` RuntimeError raise.
- `load_haystack` — remove the `hdir is None` RuntimeError raise.
- `list_graph_files` — remove the `if self._workspace_root is None: return []` guard.
- `delete_haystack` — remove the `hdir is None` check.
- `rename_haystack` — remove the `hdir is None` check.

**Method signature changes (all breaking):**

| Before | After | Behaviour change |
| --- | --- | --- |
| `open_graph(path, factory) -> GraphEntry` | `open_graph(path, session_id) -> GraphEntry` | Subscribes validation on first-time creation; attaches session before return |
| `create_new(factory) -> GraphEntry` | `create_new(session_id) -> GraphEntry` | Same — subscribes + attaches |
| `create_untitled(factory) -> GraphEntry` | **deleted** | No live callers (verified via grep) |
| `load_haystack(name, factory) -> (entries, active_rel)` | `load_haystack(name) -> (entries, active_rel)` | Subscribes each loaded entry via the injected callback |

`open_graph` reuses an existing entry if the path is already loaded; it still calls `session_attach` on reuse (idempotent set-add) so the returned entry always has the caller's session.

`create_new` always creates a fresh `__new_N__` entry (never reuses).

Both methods require `_graph_factory` and `_validation_subscriber` to be set; raising `RuntimeError` if called without them is fine (Haystack is always constructed with them in production; tests that skip callbacks can pass lambdas).

### 2. `HaywireApp` changes

**Deleted** from `packages/haywire-studio/src/haywire_studio/app.py`:

- `open_graph_file(path, session_id)` — lines 165-179
- `create_new_graph(session_id)` — lines 181-190
- `open_graph_in_tab(entry, context, editor_key)` — lines 196-249

**Updated** — Haystack construction in `setup_shared_services`:

```python
self.haystack = Haystack(
    workspace_root=Path(self.workspace_root),
    graph_factory=self._graph_factory,
    validation_subscriber=self._subscribe_entry_validation,
)
```

**Updated** — `restore_persisted_tabs` at [app.py:328](packages/haywire-studio/src/haywire_studio/app.py#L328):

```python
# before
self.open_graph_file(path, session_id)
# after
self.haystack.open_graph(path, session_id)
```

**Unchanged:** `_graph_factory` and `_subscribe_entry_validation` stay on `HaywireApp` — they close over `self.node_factory`, `self.undo_config`, `self.session_manager`, which are app-level.

### 3. New `OPEN_GRAPH_REQUESTED` event

Add to `packages/haywire-core/src/haywire/ui/context_events.py`:

```python
class ContextChangeType(Enum):
    # ...existing values...
    OPEN_GRAPH_REQUESTED = auto()  # caller asks AppShell to activate an entry + reveal its tab
```

**Payload:**

```python
session.notify_context_changed(
    ContextChangedEvent(
        change_type=ContextChangeType.OPEN_GRAPH_REQUESTED,
        source_editor=<caller name>,
        detail=entry,                  # GraphEntry
        reveal_editor=<editor_key>,    # e.g. GraphEditor.class_identity.registry_key
    )
)
```

Both `detail` and `reveal_editor` are already first-class fields on `ContextChangedEvent`.

### 4. `AppShell` handler

Added to the central `_dispatch_event` / event-routing method in `packages/haywire-core/src/haywire/ui/app/shell.py`, next to the existing `TAB_CLOSE_REQUESTED` / `GRAPH_REMOVED` branches at [shell.py:960](packages/haywire-core/src/haywire/ui/app/shell.py#L960):

```python
elif event.change_type == ContextChangeType.OPEN_GRAPH_REQUESTED:
    self._handle_open_graph_requested(event)
```

Handler implementation:

```python
def _handle_open_graph_requested(self, event: ContextChangedEvent) -> None:
    entry = event.detail
    editor_key = event.reveal_editor
    if entry is None or editor_key is None:
        return

    context = self.session.context
    haystack = context.app.haystack

    # Detach from previous active entry (if any, and different)
    prev_entry = None
    if context.active_graph_path is not None:
        prev_entry = haystack.get_by_path(context.active_graph_path)
    elif context.active_graph is not None:
        prev_entry = haystack.get_by_graph(context.active_graph)
    if prev_entry is not None and prev_entry is not entry:
        haystack.session_detach(prev_entry, self.session.session_id)

    # Attach (idempotent)
    haystack.session_attach(entry, self.session.session_id)

    # Update context
    context.active_graph = entry.graph
    context.active_graph_path = entry.path

    # Fire ACTIVE_GRAPH_CHANGED — the one that triggers tab reveal in downstream listeners
    self.session.notify_context_changed(
        ContextChangedEvent(
            change_type=ContextChangeType.ACTIVE_GRAPH_CHANGED,
            source_editor="app_shell",
            detail=entry,
            reveal_editor=editor_key,
            reveal_payload=entry.key,
            reveal_label=entry.display_name,
        )
    )
```

This is effectively the body of the deleted `HaywireApp.open_graph_in_tab`, relocated to the correct (per-session) class. Logic is unchanged.

### 5. Caller updates

Three files need updates. Every call site follows the same two-line pattern: register with Haystack, then fire the event.

**`barn/haybale-studio/haybale_studio/editors/file_browser.py`** — around line 179-180:

```python
entry = context.app.haystack.open_graph(path, session.session_id)
session.notify_context_changed(
    ContextChangedEvent(
        change_type=ContextChangeType.OPEN_GRAPH_REQUESTED,
        source_editor="file_browser",
        detail=entry,
        reveal_editor=GraphEditor.class_identity.registry_key,
    )
)
```

**`barn/haybale-studio/haybale_studio/editors/haystack_editor.py`** — three call sites:

- `_on_new` at line 521-522 (`+ New Graph`)
- `_on_select` at line 530 (clicking an entry)
- `_on_load_haystack` at line 655 (after loading a haystack)
- `_on_open_graph` at line 728-729 (the "Open Graph…" dialog)

All become the same `haystack.open_graph(...) + notify(OPEN_GRAPH_REQUESTED)` pattern. `_on_load_haystack` drops the `app._graph_factory` argument to `load_haystack` (factory now held by Haystack).

**`packages/haywire-studio/src/haywire_studio/app.py`** — `restore_persisted_tabs` swaps the one call (already covered above).

### 6. Dirty-removal confirmation dialog

Added to `HaystackEditor`. Today's `_on_entry_delete` at [haystack_editor.py:297-344](barn/haybale-studio/haybale_studio/editors/haystack_editor.py#L297-L344) is split:

```python
def _on_entry_delete(self, entry, context):
    if entry.is_executing:
        ui.notify("Stop execution before removing", type="warning")
        return

    is_dirty = entry.unsaved or entry.path is None
    if not is_dirty:
        self._remove_entry(entry, context)
        return

    self._open_remove_confirm_dialog(entry, context)
```

Where `_remove_entry` is the body of today's method from line 302 onward (stop execution, detach sessions, `remove_entry`, fire `GRAPH_REMOVED`, clear active if needed, notify).

**The dialog:**

```python
def _open_remove_confirm_dialog(self, entry, context):
    app = context.app
    can_save_in_place = entry.path is not None

    popup = Popup(
        title="Remove graph?",
        width="400px",
        closable=True,
        backdrop_click_close=True,
        escape_close=True,
    )
    with popup:
        msg = (f'"{entry.display_name}" has unsaved changes.'
               if can_save_in_place
               else "This graph has never been saved.")
        ui.label(msg).classes("text-sm")
        ui.label("What would you like to do?").classes("text-sm hw-text-dim")

        def _save_and_remove():
            if app.haystack.save_graph(entry):
                self._remove_entry(entry, context)
                popup.close()
            else:
                ui.notify("Save failed", type="negative")

        def _save_as_and_remove():
            popup.close()
            self._open_save_as_dialog(
                app, entry, context,
                on_success=lambda: self._remove_entry(entry, context),
            )

        def _discard_and_remove():
            self._remove_entry(entry, context)
            popup.close()

        with ui.row().classes("w-full justify-end gap-2 mt-3"):
            ui.button("Cancel", on_click=popup.close).props("flat dense")
            ui.button("Discard", on_click=_discard_and_remove).props("flat dense color=negative")
            ui.button("Save As…", on_click=_save_as_and_remove).props("dense")
            if can_save_in_place:
                ui.button("Save", on_click=_save_and_remove).props("color=positive dense")

    popup.open()
```

**Supporting change:** `_open_save_as_dialog` (at [haystack_editor.py:420](barn/haybale-studio/haybale_studio/editors/haystack_editor.py#L420)) gains an optional `on_success: Callable[[], None] | None = None` parameter. After a successful save, if `on_success` is set, call it before closing the popup. No other callers need to change — existing calls still work with the default `None`.

### UX rules for the dialog

Definition of "dirty" for this dialog: `entry.unsaved or entry.path is None`. Same condition `Haystack.has_unsaved()` uses today.

- **Clean entry** (`unsaved=False` and `path is not None`): remove immediately, no dialog. Today's behaviour for clean files.
- **File-backed + modified** (`unsaved=True`, `path is not None`): four buttons — Save, Save As…, Discard, Cancel.
- **Unnamed** (`path is None`, covers both `__untitled__` and `__new_N__` entries): three buttons — Save As…, Discard, Cancel. No plain "Save" because there is no target file.
- **Executing entry**: existing guard wins. User is told to stop execution first; the dialog never opens. This applies to the confirmation path and the clean-removal path identically.

## Data flow

### Opening a graph from the file browser (after the refactor)

1. User double-clicks `foo.haywire` in FileBrowserEditor.
2. `FileBrowserEditor._open_graph_file` calls `context.app.haystack.open_graph(path, session.session_id)`.
3. Haystack creates (or reuses) the `GraphEntry`, calls `validation_subscriber(entry)` on first creation, calls `session_attach(entry, session_id)`, returns the entry.
4. FileBrowserEditor fires `OPEN_GRAPH_REQUESTED` with `detail=entry`, `reveal_editor=GraphEditor key`.
5. AppShell receives the event in `_dispatch_event` → calls `_handle_open_graph_requested`.
6. Handler detaches session from previous active entry (if different), updates `context.active_graph*`, fires `ACTIVE_GRAPH_CHANGED` with reveal fields.
7. Downstream listeners (GraphEditor, HaystackEditor, MainArea tab manager) redraw.

### Removing a dirty graph from the HaystackEditor

1. User clicks overflow-menu → Remove on a dirty entry row.
2. `_on_entry_delete` checks `is_executing` (blocks if so), then branches on `is_dirty`.
3. Dirty → `_open_remove_confirm_dialog` opens the Popup.
4. User picks:
   - **Save** → `haystack.save_graph(entry)` → on success, call `_remove_entry` → close popup.
   - **Save As…** → close this popup → open `_open_save_as_dialog` with `on_success=_remove_entry`. After save-as succeeds, the existing save-as flow calls `on_success`, which removes the entry.
   - **Discard** → `_remove_entry` → close popup.
   - **Cancel** → close popup, no state change.
5. `_remove_entry` does the existing teardown: stop execution, detach sessions, `haystack.remove_entry`, fire `GRAPH_REMOVED`, clear active graph if this was it, fire `ACTIVE_GRAPH_CHANGED` if active cleared, notify DATA_MUTATED.

## Error handling

- **`OPEN_GRAPH_REQUESTED` with null detail or reveal_editor.** Handler logs a warning and returns without doing anything. Same defensive pattern as today's `open_graph_in_tab`.
- **Save failure in the dirty-removal dialog.** `app.haystack.save_graph` returns `False` on failure; we show a `ui.notify("Save failed", type="negative")` and keep the popup open so the user can pick a different action. The entry is not removed.
- **Save As failure.** Existing `_open_save_as_dialog` handles notify + keep-open on failure. When `on_success` is not called, `_remove_entry` is not called — entry stays.

## Testing

### Haystack unit tests — new file `tests/studio/test_haystack.py`

- `test_open_graph_first_time_calls_validation_subscriber` — subscriber called exactly once per new entry.
- `test_open_graph_reuse_does_not_resubscribe` — opening the same path twice calls subscriber once.
- `test_create_new_calls_validation_subscriber` — subscriber called on each `create_new`.
- `test_open_graph_attaches_session` — returned entry has `session_id` in `.sessions`.
- `test_open_graph_multiple_sessions_share_entry` — same path from two session_ids → one entry, both session_ids attached.
- `test_load_haystack_signature_no_factory` — `load_haystack("name")` works with no factory arg.
- `test_load_haystack_subscribes_each_entry` — every loaded entry gets `validation_subscriber` called.

### AppShell integration tests — extend `tests/ui/test_app_shell.py`

- `test_open_graph_requested_detaches_previous_entry` — fire with a prior active graph; assert `session_detach` on the prev entry.
- `test_open_graph_requested_attaches_target_entry` — `session_attach` called on target.
- `test_open_graph_requested_updates_context` — `context.active_graph` / `active_graph_path` match target.
- `test_open_graph_requested_fires_active_graph_changed` — downstream event emitted with `reveal_editor`, `reveal_payload`, `reveal_label` all populated from the entry.
- `test_open_graph_requested_null_detail_is_noop` — missing `detail` doesn't crash; no events fired.
- `test_open_graph_requested_same_entry_does_not_detach` — firing with the already-active entry skips the detach.

### HaystackEditor dirty-removal tests — new tests in `tests/ui/` against the UI harness

- `test_remove_clean_entry_removes_silently` — no dialog; entry gone from haystack; `GRAPH_REMOVED` fired.
- `test_remove_dirty_file_backed_entry_shows_dialog_with_save_button` — Popup has all 4 buttons (Cancel, Discard, Save As…, Save).
- `test_remove_untitled_entry_shows_dialog_without_save_button` — Popup has 3 buttons (Cancel, Discard, Save As…); no Save.
- `test_remove_dirty_save_button_saves_then_removes` — Save button → file written, entry removed.
- `test_remove_dirty_save_as_button_chains_into_save_as_then_removes` — Save As… opens save-as popup; completing it removes the entry.
- `test_remove_dirty_discard_removes_without_saving` — Discard → entry removed, file unchanged on disk.
- `test_remove_dirty_cancel_keeps_entry` — Cancel → entry still in haystack.
- `test_remove_dirty_save_failure_keeps_entry_and_popup` — if `save_graph` returns False, entry stays and popup stays open.
- `test_remove_executing_entry_blocked_before_dialog` — existing guard; dialog never opens for executing entries.

### Smoke path via UI harness

One end-to-end test that exercises the architectural change: open `foo.haywire` from FileBrowser → modify it → Remove from HaystackEditor → pick "Discard" → assert entry gone, active graph cleared, tab closed.

## Migration / breaking-change note

This refactor is **breaking** for any external code that reaches for these APIs:

- `HaywireApp.open_graph_file` — **removed**
- `HaywireApp.create_new_graph` — **removed**
- `HaywireApp.open_graph_in_tab` — **removed**
- `Haystack.open_graph(path, factory)` — signature changed to `(path, session_id)`
- `Haystack.create_new(factory)` — signature changed to `create_new(session_id)`
- `Haystack.create_untitled` — **removed**
- `Haystack.load_haystack(name, factory)` — signature changed to `load_haystack(name)`

A grep across the whole repo confirms no other callers exist beyond the three files updated in this design (`file_browser.py`, `haystack_editor.py`, `app.py`). External plugin libraries in `barn/haybale-*/` that implement their own editors and wanted to open graphs programmatically would need to update to the new pattern:

```python
entry = context.app.haystack.open_graph(path, session.session_id)
session.notify_context_changed(
    ContextChangedEvent(
        change_type=ContextChangeType.OPEN_GRAPH_REQUESTED,
        source_editor=<your editor name>,
        detail=entry,
        reveal_editor=<target editor key>,
    )
)
```

No deprecation period, no shim methods — this is the right pattern going forward and the old surface was always intended to be internal.

## Open decisions carried from prior inquisition

For traceability, the eight decisions this spec implements (from the 2026-04-15 inquisition session):

1. Q1-C — Haystack (class) is both live registry and TOML snapshot; no rename.
2. Q2 (user alt) — open auto-adds; closing tab ≠ removing; removal is explicit + dirty/save/save-as.
3. Q3-B — `HaystackEditor` is where removal UI lives.
4. Q4-A — Haystack is app-wide/shared across browser sessions.
5. Q5-B — file browser click still auto-adds (today's behaviour, re-framed under Q1-C).
6. Q6-A — entry creation moves onto Haystack.
7. Q7-B — tab orchestration moves to AppShell via new event type.
8. Q8-A — persistence unchanged; beforeunload deferred.
