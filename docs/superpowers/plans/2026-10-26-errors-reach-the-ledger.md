# Errors Reach the Ledger Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every failure on the studio's main editing and running pathways, and every detected loss of user work, lands in the error ledger with the context to act on it; refusals stay out (backlog #47).

**Architecture:** Inner code keeps raising plain exceptions. A new core `Refusal` type marks expected outcomes. One helper, `report_failure`, is called in the `except` block of a short, named list of error boundaries: it lets a `Refusal` through, reuses an existing `HaywireException`, otherwise wraps, enriches and `.log()`s. The ledger dedups repeats by fingerprint while unseen. The studio app installs the UI safety net and the last-resort hooks.

**Tech Stack:** Python 3.12, NiceGUI 3.13 (`app.on_exception`), pytest, the haywire DI/ambient accessors.

**Spec:** the decisions table below (inquisition of 2026-10-26, Q1–Q15) and the handoff `internals/handoff/haywire-exception-at-boundaries.md`.

## Decisions (the spec)

| Q | Decision |
|---|---|
| 1 | The ledger takes **failures** and **detected losses** (`WARNING`). Refusals stay out. |
| 2 | New `Refusal` exception in core; `FarmhandError` subclasses it. Any other exception, `ValueError` included, is a failure. |
| 3 | Pathways in scope: editing, running, load/save, hot reload, Farmhand; feature handlers on them (Update Macro first). |
| 4 | UI safety net: failure → ledger + toast "Something went wrong — see Errors"; a leaked `Refusal` → toast with its own message, no ledger entry. |
| 5 | Ledger dedup: same fingerprint while the entry is unseen → bump `count` and `last_seen_at`, no new entry. |
| 6 | Detected losses → ledger only (`WARNING`). `NodeWarning` unchanged. The Inset message is out of scope. |
| 7 | Farmhand: an unexpected failure → ledger + agent error with `ledger_seq=<n>` appended. |
| 8 | Signal bus: failure → ledger only, no toast; a `Refusal` in a subscriber counts as a failure. |
| 9 | `Editor._apply` / `_apply_value` / `reset_nodes`: failure → ledger + `False`; `Refusal` → `False`, unrecorded. `bool` API unchanged. |
| 10 | Validation loops: ledger only, nothing new on the card. |
| 11 | The studio app installs `threading.excepthook`, `sys.excepthook` and the asyncio loop handler; record, then chain to the previous hook. Core, CLI and tests never install them. |
| 12 | `report_failure(e, operation=..., **context)` called in each `except`; returns the logged `HaywireException`, or `None` for a `Refusal`. |
| 13 | Sorting rule: a raise correct code can reach (user input, a stale id from another session's edit, a name collision) becomes `Refusal`; one only a bug can reach stays a failure. Only on Q3's pathways. |
| 14 | A plain `Refusal` reaching Farmhand renders as `[refused] <message>`, no ledger entry. |
| 15 | ADR 0061, `docs/architecture/errors/` page, glossary entries (Refusal, Failure, Error boundary) and an amended Error ledger entry, landing with the code. |

**Out of scope:** the other ~300 `except` sites; refusal messages from `Editor` verbs; card badges for losses or validation failures; hooks outside the studio; the Inset message (backlog #4); per-boundary throttles; implementing #46 itself (this plan only unblocks it).

## Global Constraints

- `Refusal` subclasses `Exception`, not `ValueError`: a converted raise must not change which `except ValueError` blocks catch it silently. When a task converts a `raise ValueError` to `raise Refusal`, grep that function's callers for `except ValueError` and widen each to `except (ValueError, Refusal)` or narrow it to `Refusal`, whichever matches the intent at that site.
- `report_failure` never raises. Anything going wrong inside it is swallowed with `logger.debug(..., exc_info=True)`, like `HaywireException.log`.
- Boundary context fills only fields the exception does not already hold: an existing `HaywireException` keeps its `node_id`, `graph_id`, `registry_key`, `operation`.
- `graph_id` context is always `graph.graph_id` (the runtime uuid), as the edge and node sites do today.
- Fingerprint, exactly: `(operation, registry_key, graph_id, node_id, edge_id, category, filename, line_number, re.sub(r"\d+", "#", message))` (source location added by ruling R8).
- Toast copy, exactly: failure `"Something went wrong — see Errors"` (`type="negative"`); refusal `str(exc)` (`type="warning"`, `multi_line=True`).
- Farmhand suffix, exactly: `" (ledger_seq=<n>)"` appended to the existing formatted error line; refusal format `"[refused] <message>"`.
- The studio app (`haywire_studio`) must not import any barn library (`.insights/project_app_library_dependency_direction.md`): the safety net enriches with `principal` and `session_id` only.
- No relative imports under `barn/` (ruff TID252). Line length 109. Tests never read repo `graphs/`.
- Handlers in the UI net must follow `.insights/feedback_nicegui_async.md`: capture the client first, `ui.notify` under `with client:`.

## Review Focus

1. **A boundary catches a `HaywireException` that was already logged** (e.g. a node build stage inside `Editor._apply`): expect no second entry and no overwritten context. Pinned in Task 1.
2. **`report_failure` itself fails** (an exception whose `__str__` raises, a broken ledger): expect the boundary's own fallback to still run. Pinned in Task 1.
3. **The same failure after the user marked it seen, or deleted it**: expect a new entry, not a silent bump on an entry nobody looks at. Pinned in Task 2.
4. **A failure from a watchdog thread while the loop records the same one**: expect one entry with `count == 2`, no lost bump. Pinned in Task 2.
5. **A failure in a timer with no slot context, or after the client was deleted**: expect a ledger entry and no crash in the net. Pinned in Task 3.

---

### Task 1: `Refusal` and `report_failure`

**Files:**
- Create: `packages/haywire-core/src/haywire/core/errors/refusal.py`
- Create: `packages/haywire-core/src/haywire/core/errors/boundary.py`
- Modify: `packages/haywire-core/src/haywire/core/errors/__init__.py` (export both)
- Modify: `packages/haywire-core/src/haywire/core/farmhand/errors.py` (`class FarmhandError(Refusal)`)
- Modify: `packages/haywire-core/src/haywire/core/errors/haywire_exception.py:~489` (the `graph_id` field docstring: it holds the graph's runtime `graph_id`, a uuid4 minted per `BaseGraph`, not its binding id; say so, and drop the HaystackState/GraphAppState sentence)
- Test: `tests/core/test_errors/test_boundary.py`

**Interfaces:**
- Produces: `class Refusal(Exception)` with `__init__(self, message: str)` and `.message: str`.
- Produces: `report_failure(exc: BaseException, *, operation: str, message: str | None = None, severity: ErrorSeverity = ErrorSeverity.ERROR, **context: Any) -> HaywireException | None`. `context` keys are `HaywireException.enrich` keywords (`graph_id`, `node_id`, `edge_id`, `registry_key`, `library_identity`) plus anything else, which goes into `error_context`.
- Produces: `report_loss(message: str, *, operation: str, **context: Any) -> HaywireException` — `HaywireException.create(message, severity=WARNING, operation=...)`, enriched, logged. The detected-loss path (Q6).

- [ ] **Step 1: Write the failing tests**

```python
def test_a_refusal_is_not_recorded(ledger):
    assert report_failure(Refusal("stale"), operation="Apply edit") is None
    assert ledger.query().total == 0

def test_a_plain_exception_is_wrapped_enriched_and_recorded(ledger):
    logged = report_failure(KeyError("x"), operation="Apply edit", graph_id="g1", node_id="n1", action="Move")
    assert logged is not None and logged.ledger_seq > 0
    assert (logged.operation, logged.graph_id, logged.node_id) == ("Apply edit", "g1", "n1")
    assert logged.error_context["action"] == "Move"

def test_an_existing_haywire_exception_is_reused_not_wrapped(ledger):
    inner = HaywireException.create("build failed", node_id="n1", operation="build")
    assert report_failure(inner, operation="Apply edit", node_id="n2", graph_id="g1") is inner
    assert (inner.node_id, inner.operation, inner.graph_id) == ("n1", "build", "g1")

def test_an_already_logged_exception_adds_no_entry(ledger):
    inner = HaywireException.create("build failed").log()
    report_failure(inner, operation="Apply edit")
    assert ledger.query().total == 1

def test_report_failure_never_raises(ledger, monkeypatch):
    monkeypatch.setattr(HaywireException, "log", lambda self, logger=None: 1 / 0)
    assert report_failure(RuntimeError("x"), operation="Apply edit") is None

def test_a_farmhand_error_is_a_refusal():
    assert isinstance(FarmhandError("code", "msg"), Refusal)

def test_report_loss_records_a_warning(ledger):
    loss = report_loss("setup lost", operation="Hot reload", graph_id="g1")
    assert loss.severity is ErrorSeverity.WARNING and ledger.query().total == 1
```

`ledger` is a fixture installing a fresh `ErrorLedger` with `set_error_ledger` and restoring the previous one after (see `tests/core/test_errors/test_ledger.py` for the existing pattern).

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/core/test_errors/test_boundary.py -q`
Expected: FAIL, `ImportError` on `Refusal` / `report_failure`.

- [ ] **Step 3: Implement `Refusal`, `report_failure`, `report_loss`; make `FarmhandError` subclass `Refusal`; correct the `graph_id` docstring**

`report_failure`: `isinstance(exc, Refusal)` → `None`; a `HaywireException` → fill only its empty context fields, `.log()` (idempotent); else `HaywireException.from_exception(exc, message or f"{operation} failed", operation=operation, severity=severity)`, `.enrich(**known)`, unknown keys into `error_context`, `.log()`. Wrap the whole body in `try/except Exception` → `logger.debug(..., exc_info=True)`, return `None`. `FarmhandError.__init__` must still call through to `Exception.__init__` with its message so `str(exc)` is unchanged.

- [ ] **Step 4: Run to verify they pass**

Run: `uv run pytest tests/core/test_errors/ tests/core/test_farmhand/ tests/farmhand/ -q`
Expected: PASS, no regressions in Farmhand tests.

- [ ] **Step 5: Commit** — `feat(errors) Refusal and report_failure, the error-boundary helper (#47)`

---

### Task 2: Ledger dedup by fingerprint

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/errors/haywire_exception.py` (fields `count: int = 1`, `last_seen_at: Optional[float] = None`; `fingerprint()` method; `to_dict` adds `"count"` and `"last_seen_at"`)
- Modify: `packages/haywire-core/src/haywire/core/errors/ledger.py` (`record` merges)
- Modify: `barn/haybale-studio/haybale_studio/editors/errors_editor.py:~206` (show `×{count}` after the message when `count > 1`)
- Test: `tests/core/test_errors/test_ledger.py`, `tests/core/test_execution/` (VM flood)

**Interfaces:**
- Produces: `HaywireException.fingerprint() -> tuple` per Global Constraints.
- Produces: `ErrorLedger.record(exc)` returns the seq of the entry that now holds the occurrence. A merged duplicate gets `exc.ledger_seq` set to that seq; the listener still fires; `current_seq` does not advance.

- [ ] **Step 1: Write the failing tests**

```python
def test_a_repeat_while_unseen_bumps_the_entry(ledger):
    first, again = _err("Node 3 failed"), _err("Node 7 failed")   # same fingerprint after digit normalizing
    seq = ledger.record(first)
    assert ledger.record(again) == seq
    assert ledger.query().total == 1 and first.count == 2 and first.last_seen_at == again.timestamp

def test_a_repeat_after_seen_starts_a_new_entry(ledger):
    ledger.mark_seen(ledger.record(_err("x")))
    ledger.record(_err("x"))
    assert ledger.query().total == 2

def test_a_repeat_after_delete_starts_a_new_entry(ledger): ...

def test_a_merge_fires_the_listener_but_keeps_the_cursor(ledger): ...

def test_concurrent_repeats_from_threads_all_count(ledger):
    # 8 threads x 50 records of the same fingerprint
    assert ledger.query().total == 1 and ledger.query().entries[0].count == 400

def test_a_node_failing_every_run_leaves_one_entry(...):
    # VM.catch_exception called 1000 times for one node -> one entry, count == 1000
```

`_err(message)` builds `HaywireException.create(message, operation="execute", node_id="n1")`.

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/core/test_errors/test_ledger.py -q`
Expected: FAIL on the dedup tests.

- [ ] **Step 3: Implement the fields, `fingerprint()`, and the merge inside `record`'s lock**

Scan `self._entries` newest first for an unseen entry with an equal fingerprint. The scan runs under the existing lock.

- [ ] **Step 4: Run to verify they pass, plus the Errors editor and Farmhand error tests**

Run: `uv run pytest tests/core/test_errors/ tests/farmhand/ tests/studio/ -q -k "error or ledger"`
Expected: PASS.

- [ ] **Step 5: Commit** — `feat(errors) the ledger merges repeats while unseen (#47)`

---

### Task 3: The UI safety net and last-resort hooks (studio app)

**Files:**
- Create: `packages/haywire-studio/src/haywire_studio/error_hooks.py`
- Modify: `packages/haywire-studio/src/haywire_studio/app.py` (`_register_lifecycle`: `app.on_exception(...)`; `_wire_store_broadcasts` or a sibling `app.on_startup` callback installs the hooks; `on_app_shutdown` restores the previous ones)
- Test: `tests/studio/test_error_hooks.py`

**Interfaces:**
- Consumes: `report_failure`, `Refusal` (Task 1).
- Produces: `class ErrorHooks` with `__init__(self, session_of: Callable[[str], Session | None])` (maps a NiceGUI `client.id` to its haywire session; the app passes a lambda over `_client_to_session` and `session_manager.get_session`), `on_ui_exception(self, exc: Exception) -> None`, `install(self) -> None`, `uninstall(self) -> None`.

- [ ] **Step 1: Write the failing tests**

```python
def test_a_ui_failure_is_recorded_with_session_context_and_toasted(ledger, notify): ...
    # inside a Client context: on_ui_exception(RuntimeError) -> 1 entry, error_context has principal and
    # session_id, operation == "UI handler"; notify called with "Something went wrong — see Errors", type="negative"
def test_a_leaked_refusal_is_toasted_and_not_recorded(ledger, notify): ...
def test_a_failure_without_a_client_is_recorded_and_not_toasted(ledger, notify): ...
def test_a_toast_into_a_deleted_client_does_not_raise(ledger): ...
def test_install_chains_and_uninstall_restores_the_previous_hooks(ledger): ...
    # threading.excepthook / sys.excepthook replaced, previous one still called, restored after uninstall
def test_a_thread_failure_is_recorded(ledger): ...
    # threading.Thread(target=lambda: 1/0).start(); join -> 1 entry, operation == "Thread"
def test_an_asyncio_loop_failure_is_recorded(ledger): ...
    # handler(loop, {"exception": RuntimeError(), "message": "x"}) -> 1 entry, previous/default handler called
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/studio/test_error_hooks.py -q`
Expected: FAIL, `ModuleNotFoundError: haywire_studio.error_hooks`.

- [ ] **Step 3: Implement `ErrorHooks` and wire it into `HaywireApp`**

Client: `nicegui.context.client` when `context.slot_stack` is non-empty, else `None`. Operations: `"UI handler"`, `"Thread"`, `"Asyncio"`, `"Uncaught"`. The asyncio handler is installed with `asyncio.get_running_loop().set_exception_handler` from the startup callback; its previous handler (or `loop.default_exception_handler`) is chained. A context without `"exception"` is passed through unrecorded.

- [ ] **Step 4: Run to verify they pass**

Run: `uv run pytest tests/studio/ -q`
Expected: PASS.

- [ ] **Step 5: Commit** — `feat(studio) a UI safety net and last-resort hooks record failures (#47)`

---

### Task 4: `Editor` writes and the validation loops

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/graph/editor.py:420-466` (`_apply_value`, `_apply`, `reset_nodes`)
- Modify: `packages/haywire-core/src/haywire/core/graph/validation.py:357`, `:393`
- Test: `tests/core/test_graph/test_editor_boundary.py`, `tests/core/test_graph/test_validation_boundary.py`

**Interfaces:**
- Consumes: `report_failure`, `Refusal`.
- Context: `_apply`/`_apply_value` → `operation="Apply edit"`, `graph_id=self.graph.graph_id`, `action=action.description`, plus `node_id` when the action has a `node_id` attribute. `reset_nodes` → `operation="Reset nodes"`, `node_ids=node_ids`. Validation → `operation="Validate node"` / `"Validate edge"`, `graph_id`, `node_id` or `edge_id`, `reason=reason.name`, and `registry_key` from the wrapper when found.

- [ ] **Step 1: Write the failing tests**

```python
def test_a_failing_action_is_recorded_and_returns_false(ledger, editor): ...   # action.execute raises KeyError
def test_a_refusing_action_returns_false_unrecorded(ledger, editor): ...       # raises Refusal
def test_a_failing_value_write_is_recorded(ledger, editor): ...
def test_a_node_failing_validation_is_recorded_and_the_loop_continues(ledger, graph): ...
    # monkeypatch one wrapper's validation step to raise; the other node still validates
def test_an_edge_failing_validation_is_recorded(ledger, graph): ...
```

Use `force_immediate_validation()` or a `SyncScheduler` graph (ADR 0002); take node keys from `Cls.class_identity.registry_key`.

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/core/test_graph/test_editor_boundary.py tests/core/test_graph/test_validation_boundary.py -q`
Expected: FAIL, nothing recorded.

- [ ] **Step 3: Replace each `logger.error` in those `except` blocks with `report_failure(...)`, keeping the fallback (`return False` / continue)**

- [ ] **Step 4: Run to verify they pass, plus the graph and undo suites**

Run: `uv run pytest tests/core/test_graph tests/core/test_undo -n 4 -q`
Expected: PASS.

- [ ] **Step 5: Commit** — `feat(graph) Editor writes and validation record their failures (#47)`

---

### Task 5: `Refusal` sorting on the editing pathway

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/undo/actions/graph_actions.py` (34 `raise ValueError`)
- Modify: `packages/haywire-core/src/haywire/core/graph/base.py`, `packages/haywire-core/src/haywire/core/node/data.py`, `packages/haywire-core/src/haywire/core/node/promotion.py` (their `raise ValueError` reached from `Editor` verbs)
- Test: `tests/core/test_undo/test_refusals.py`

**Interfaces:**
- Consumes: `Refusal`.

- [ ] **Step 1: List every `raise ValueError` in the four files and classify each by Q13's rule in a table in the commit message** (`file:line`, message, Refusal or failure, one-word reason). Stale/unknown ids (`"Node '…' not found"`, `"Edge '…' not found"`), name collisions and user-typed input become `Refusal`; invariants (`"Cannot amend a value step from a write of another run"`, `"Must specify at least one node or edge to remove"`) stay `ValueError`.

- [ ] **Step 2: Write the failing tests** — one per refusal kind through the `Editor` verb that reaches it, asserting `False` and an empty ledger; one invariant raise asserting `False` and one ledger entry.

- [ ] **Step 3: Run to verify they fail**

Run: `uv run pytest tests/core/test_undo/test_refusals.py -q`
Expected: FAIL, refusals recorded.

- [ ] **Step 4: Convert the classified raises; widen callers' `except ValueError` per Global Constraints**

- [ ] **Step 5: Run the pre-commit gate**

Run: `uv run pytest -m "not browser and not perf" -n 4 -q > /tmp/t.log 2>&1; echo "exit=$?"`
Expected: `exit=0`.

- [ ] **Step 6: Commit** — `refactor(undo) stale ids and collisions raise Refusal (#47)`, with the classification table in the body.

---

### Task 6: Signal bus and broadcast

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/signals/bus.py:101-110`, `packages/haywire-core/src/haywire/core/signals/dispatcher.py:85-92`
- Test: `tests/core/signals/test_bus_boundary.py`

**Interfaces:**
- Context: bus → `operation="Signal handler"`, `signal=type(signal).__name__`, `handler=getattr(handler, "__qualname__", repr(handler))`. Broadcast → `operation="Signal broadcast"`, `signal`, `peer=peer_id[:8]`. A `Refusal` here counts as a failure (Q8): wrap it as `RuntimeError(f"Refusal in a signal handler: {exc.message}")` before calling `report_failure`.

- [ ] **Step 1: Write the failing tests** — a raising handler is recorded and the next handler still runs; a handler raising `Refusal` is recorded; a handler raising on every publish of 100 publishes leaves one entry with `count == 100`.

- [ ] **Step 2: Run to verify they fail** — `uv run pytest tests/core/signals/test_bus_boundary.py -q`, FAIL.

- [ ] **Step 3: Replace the `logger.exception` / `logger.warning` with `report_failure`, keeping the continue**

- [ ] **Step 4: Run to verify they pass** — `uv run pytest tests/core/signals -q`, PASS.

- [ ] **Step 5: Commit** — `feat(signals) subscriber failures reach the ledger (#47)`

---

### Task 7: Farmhand runner

**Files:**
- Modify: `packages/haywire-studio/src/haywire_studio/farmhand/host.py` (`_format_tool_error`, the `except Exception as exc` in `call_tool` at ~`:307`)
- Test: `tests/farmhand/test_host_errors.py`

**Interfaces:**
- Consumes: `report_failure`, `Refusal`.
- Context: `operation="Farmhand tool"`, `tool=name`, `principal=principal`, `arguments=sorted(arguments)` (names only, never values).

- [ ] **Step 1: Write the failing tests**

```python
def test_a_failing_tool_is_recorded_and_the_agent_sees_its_seq(...):
    # tool raises KeyError -> 1 ledger entry; error text ends with f" (ledger_seq={seq})"
def test_a_farmhand_error_is_not_recorded(...):     # unchanged "[code] message" text, empty ledger
def test_a_plain_refusal_renders_as_refused(...):   # text == "[refused] stale id", empty ledger
def test_a_haywire_exception_from_a_tool_keeps_its_category_and_gains_the_seq(...)
```

- [ ] **Step 2: Run to verify they fail** — `uv run pytest tests/farmhand/test_host_errors.py -q`, FAIL.

- [ ] **Step 3: Implement** — in `call_tool`'s `except`, `logged = report_failure(exc, ...)`, then format; `_format_tool_error(exc, ledger_seq: int | None = None) -> str` adds the suffix when given, and renders a non-`FarmhandError` `Refusal` as `[refused] {exc.message}`. The activity tracker records the same text.

- [ ] **Step 4: Run to verify they pass** — `uv run pytest tests/farmhand -n 4 -q`, PASS.

- [ ] **Step 5: Commit** — `feat(farmhand) tool failures reach the ledger, the agent gets the seq (#47)`

---

### Task 8: Load and save

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/graph/base.py` (`load_from_dict` per-subgraph `:1105`, per-node `:1122`, per-edge `:1146`, whole `:1156`; `save_to_file` `:1288`; `load_from_file` `:1322`)
- Test: `tests/core/test_graph/test_load_save_boundary.py`

**Interfaces:**
- Context: `operation="Load graph"` / `"Save graph"`, `graph_id=self.graph_id`, `path=filepath` where known, and `node_id` / `edge_id` / `subgraph=key` in the per-item loops. Fallbacks unchanged (skip the item / `return False`).

- [ ] **Step 1: Write the failing tests** — an unreadable file, a node whose build raises in a loaded dict (other nodes still load), an edge whose build raises, a save into a read-only directory (`tmp_path` with `chmod 0o500`): each `False` or skipped, each one ledger entry with the path or item id. Fixture graphs live under `tmp_path`, never `graphs/`.

- [ ] **Step 2: Run to verify they fail** — `uv run pytest tests/core/test_graph/test_load_save_boundary.py -q`, FAIL.

- [ ] **Step 3: Replace the `logger.error` calls with `report_failure`**

- [ ] **Step 4: Run to verify they pass** — `uv run pytest tests/core/test_graph -n 4 -q`, PASS.

- [ ] **Step 5: Commit** — `feat(graph) load and save failures reach the ledger (#47)`

---

### Task 9: Hot-reload pathway

**Files:**
- Modify (only sites that end in `logger.*` without `.log()` and without a documented deliberate fallback): `packages/haywire-core/src/haywire/core/registry/base.py` (`:212`, `:268`, `:387`, `:592`, `:747`), `registry/component.py:224`, `registry/document.py:148`, `:208`, `registry/folder_scan.py:134`, `registry/dependency_graph.py:338`, `:426`
- Test: `tests/core/test_registry/test_reload_boundary.py`

**Interfaces:**
- Context: `operation="Hot reload"`, `registry_key` / `library_identity` / `module_name` where the site holds them.

- [ ] **Step 1: For each listed site, record in the commit body whether it converts or stays** (stays only when it already `.log()`s or is a documented fallback such as the "logging error" guard at `base.py:436`).

- [ ] **Step 2: Write a failing test per converted site class** — a component whose registration raises during a reload batch produces one ledger entry with `operation == "Hot reload"` and its registry key; the batch continues with the next component.

- [ ] **Step 3: Run to verify they fail** — `uv run pytest tests/core/test_registry/test_reload_boundary.py -q`, FAIL.

- [ ] **Step 4: Convert the sites**

- [ ] **Step 5: Run the reload suites** — `uv run pytest tests/core/test_libraries tests/core/test_registry -n 4 -q`, PASS. Commit `barn/haybale-testing` edits first if any (its docs test reverts the directory).

- [ ] **Step 6: Commit** — `feat(registry) hot-reload failures reach the ledger (#47)`

---

### Task 10: Update Macro

**Files:**
- Modify: `barn/haybale-haystack/haybale_haystack/panels/graph/menu/macro.py:247-253`
- Test: `tests/haystack/test_update_macro.py` (extend the existing Update Macro tests; find them with `rg -l "Update Macro" tests`)

- [ ] **Step 1: Write the failing test** — `open_macro_with` raising `OSError` leaves one ledger entry (`operation="Update Macro"`, `path` in context) and the existing toast text unchanged.

- [ ] **Step 2: Run to verify it fails**, then **Step 3:** replace `logger.warning` with `report_failure(exc, operation="Update Macro", path=str(template.path), node_id=node_id)`, keeping the toast; **Step 4:** run `uv run pytest tests/haystack -q`, PASS.

- [ ] **Step 5: Commit** — `fix(haystack) an Update Macro failure reaches the ledger (#21, #47)`

---

### Task 11: Documentation, and release #46

**Files:**
- Create: `docs/adr/0061-errors-reach-the-ledger-at-named-boundaries.md` (context: the 2026-10-23 handoff; decision: Q1–Q14; considered: per-site wrapping, `ValueError` as refusal, result objects for `Editor` verbs, boundary throttles, core-installed hooks; consequences: refusal messages from `Editor` verbs are dropped, card shows nothing new for validation failures, the dedup key)
- Create: `docs/architecture/errors/index.md` (current solution only: Refusal vs Failure, `report_failure` / `report_loss`, the boundary list with file links, dedup rule, the studio's hooks; front matter and nav per `docs/reference/doc-authoring.md`)
- Modify: `docs/reference/glossary.md` — add **Refusal**, **Failure**, **Error boundary**; amend **Error ledger** with "repeats merge into the unseen entry with the same fingerprint (`count`)"
- Modify: `docs/superpowers/plans/2026-10-22-open-follow-ups.md` — #47 **DONE**; #46 "on hold" → "unblocked: its warning is a detected loss, ledger only (`report_loss`, ADR 0061)"
- Modify: `internals/handoff/reload-without-history-loses-setup.md` — status `open`; its option (a) part 2 uses `report_loss`, ledger only (no `NodeWarning`)
- Modify: `internals/handoff/haywire-exception-at-boundaries.md` — status `landed`, link ADR 0061

- [ ] **Step 1: Write the pages**

- [ ] **Step 2: Build the docs** — `uv run mkdocs build --strict`, expected: no warnings for the new pages.

- [ ] **Step 3: Full verification** — `uv run ruff check . && uv run ruff format --check .`, the CI mypy command from `CLAUDE.md`, `uv run pytest -m "not browser and not perf" -n 4`, `uv run pytest -m browser -n 4`; all exit 0.

- [ ] **Step 4: Commit** — `docs(errors) ADR 0061, the errors architecture page and glossary terms (#47)`
