# Farmhand — the Haywire MCP Server: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Farmhand, the in-process MCP server that lets AI-agent clients operate a running Haywire studio — 34 tools, 2 resource families, library-contributed via a new typed registry — per the settled spec at `.scratch/mcp-server/spec.md`.

**Architecture:** An SDK-free contribution seam in haywire-core (a tenth typed registry `FarmhandRegistry`, `Farmhand` component classes in each library's `farmhands/` folder, a `FarmhandContext` handler facade) plus a host in haywire-studio (low-level `mcp` SDK server mounted at `/mcp` on the studio's existing FastAPI app, single-runner-task lifespan, live-session registry driving `list_changed`, bearer-token auth). Three mandated core work items land first: the error ledger, the undoable `SetPropertyAction` Editor primitive, and canon packaging into the haywire-core wheel.

**Tech Stack:** Python 3.11+, official `mcp` SDK v1.x (protocol 2025-11-25), NiceGUI/FastAPI/uvicorn, hatchling, pytest (existing `unit`/`integration` markers).

## Global Constraints

Every task's requirements implicitly include this section.

- **SDK pin:** `mcp>=1.28,<2` — declared in **haywire-studio only**. haywire-core must never import from the `mcp` package (SDK-free seam).
- **Protocol:** 2025-11-25; advertise `listChanged: true` for tools/prompts/resources via low-level `NotificationOptions(tools_changed=True, prompts_changed=True, resources_changed=True)` — the SDK's default advertises `false` (confirmed empirically; the fix is subclassing `create_initialization_options`, see Task 8).
- **Endpoint:** `/mcp` on the studio's port; SDK internal path `/`, full prefix in the mount (307-trap avoidance, python-sdk#951). **No SSE endpoint.**
- **Lifespan:** single long-lived runner task (prototype-proven). NEVER the AsyncExitStack-across-handlers shape — it crashes NiceGUI shutdown (`.insights/feedback_nicegui_lifespan_task_scope.md`). `StreamableHTTPSessionManager.run()` may be entered exactly once per process.
- **Auth:** bind 127.0.0.1; explicit `TransportSecuritySettings` (SDK DNS-rebinding protection is OFF when unset); static bearer token auto-generated per workspace, stored gitignored under `<workspace>/.haywire/`; 401 on mismatch. No OAuth.
- **Naming:** MCP-visible tool name is `{lib_id}_{name}`; registry key is `{lib_id}:farmhand:{name}`; `studio` is a reserved lib-id prefix only host baseline tools may claim (enforced at registration).
- **Handlers:** every `Farmhand.run()` is `async` (the SDK thread-offloads sync functions, breaking loop affinity). Blocking work goes through `ctx.offload()`.
- **Undo:** one shared timeline; each mutating graph tool call opens exactly one undo fence (one call = one undo gesture).
- **Signals:** core `Editor` calls and `LibraryManager` do NOT broadcast; the tool wrapper broadcasts (`GraphDataMutated` after graph mutations, `LibraryCatalogChanged` after install/uninstall) via `ctx.broadcast(...)` — inventory gap 5.
- **Results:** structured JSON + one-line human summary per tool; list tools take `limit`/`offset` and return `total`; failures are MCP tool errors with stable code + actionable message + offending ids, never stack traces.
- **Tests:** existing `unit`/`integration` markers; NO browser tests; never call `create_test_injector()` directly in a test (use the snapshot/restore fixture idiom); tests clean up haystack entries they create.
- **Quality gates per task:** `uv run ruff check <touched paths>`, `uv run ruff format <touched paths>` (CI runs `ruff format --check`), `uv run mypy <touched packages per CLAUDE.md's mypy invocation>`. Line length 109. Before any multi-file task, run the lint/type baseline on the area first (CLAUDE.md pre-edit baseline rule); the codebase is error-free — anything new is yours.
- **Commit style:** one commit per green task, message given in each task; end every commit message body with `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.

**Known spec deviations (deliberate, user-decided):**

1. The spec says the studio settings UI shows the ready-made `claude mcp add …` line. v1 of this plan prints that line to the studio console at startup and returns it from `studio_status`; a dedicated settings-panel widget is recorded as later work (Task 15 notes it).
2. **Baseline tools live in barn/haybale-studio, not the haywire-studio package** (revised 2026-07-19, user decision superseding spec §2's packaging line). haybale-studio's library id is literally `studio`, so its `farmhands/` folder yields the spec's `studio_*` names through the normal `{lib_id}_{name}` rule — one folder-scan mechanism for ALL tools, no host-side registration path. Consequences: haywire-studio's pyproject gains `haybale-studio` as a declared dependency (packaging-enforces "exists on a bare studio"); the `studio` prefix reservation is enforced by library-id uniqueness at discovery (no registry guard — decided); "bare studio" means builtin + haybale-studio only.
3. **Vocabulary: a "farmhand" IS a haywire MCP tool** (renamed 2026-07-19, superseding spec §3's names). Library folder `farmhands/` (not `mcp/`), registry keys `{lib_id}:farmhand:{name}` (not `:mcp:`), decorator `@farmhand`, base class `Farmhand`, registry `FarmhandRegistry`, identity `FarmhandIdentity` (extends `BaseIdentity`, the established identity pattern), error `FarmhandError`. Comments/docstrings may still say "tool"/"MCP tool" for clarity; concrete tool subclasses keep `XXXTool` names; `FarmhandContext`/`FarmhandHost` and `farmhand://` URIs unchanged.

Everything else in the spec is covered by a task below.

**Key reference files an implementer will keep open:**

- `.scratch/mcp-server/spec.md` — the binding spec.
- `.scratch/mcp-server/assets/wrappable-operations-inventory.md` — exact signatures of every wrapped operation.
- `.scratch/mcp-server/assets/mcp-sdk-research.md` — SDK API facts with primary-source citations.
- `.scratch/mcp-server/prototype/farmhand_mount_prototype.py` — the proven runner-task lifespan pattern (throwaway code; lift patterns, not lines).

---

### Task 1: Error ledger (mandated core work item 3)

**Files:**
- Create: `packages/haywire-core/src/haywire/core/errors/ledger.py`
- Modify: `packages/haywire-core/src/haywire/core/errors/haywire_exception.py` (the `log()` method, line ~903)
- Test: `tests/core/test_errors/test_ledger.py`

**Interfaces:**
- Consumes: `HaywireException` (`haywire/core/errors/haywire_exception.py`) — dataclass with fields `message`, `category`, `severity: ErrorSeverity`, `operation`, `registry_key`, `library_identity: LibraryIdentity | None`, `filename`, `line_number`, `timestamp`, `tags`.
- Produces (later tasks rely on these exact names):
  - `haywire.core.errors.ledger.ErrorLedger` with `record(exc: "HaywireException") -> int`, `query(since_seq: int | None = None, library: str | None = None, registry_key: str | None = None, limit: int = 50, offset: int = 0) -> LedgerPage`, `current_seq: int` (property).
  - `LedgerPage` dataclass: `entries: list[dict]`, `total: int`, `cursor: int`.
  - Module-level `get_error_ledger() -> ErrorLedger` and `set_error_ledger(ledger: ErrorLedger | None) -> None` (module-level global, NOT ContextVar — see `.insights/project_di_context.md`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/core/test_errors/test_ledger.py
"""Unit tests for the bounded, sequence-numbered error ledger."""

import pytest

from haywire.core.errors.haywire_exception import HaywireException
from haywire.core.errors.ledger import ErrorLedger, get_error_ledger, set_error_ledger

pytestmark = pytest.mark.unit


@pytest.fixture()
def ledger():
    fresh = ErrorLedger(max_entries=5)
    set_error_ledger(fresh)
    yield fresh
    set_error_ledger(None)


def _exc(msg: str, **kwargs) -> HaywireException:
    return HaywireException.create(msg, **kwargs)


def test_record_assigns_monotonic_sequence(ledger):
    first = ledger.record(_exc("one"))
    second = ledger.record(_exc("two"))
    assert second == first + 1
    assert ledger.current_seq == second


def test_query_returns_entries_with_cursor(ledger):
    ledger.record(_exc("boom", registry_key="testing:node:foo"))
    page = ledger.query()
    assert page.total == 1
    assert page.cursor == ledger.current_seq
    entry = page.entries[0]
    assert entry["message"] == "boom"
    assert entry["registry_key"] == "testing:node:foo"
    assert entry["seq"] == ledger.current_seq


def test_query_since_seq_excludes_older(ledger):
    ledger.record(_exc("old"))
    marker = ledger.current_seq
    ledger.record(_exc("new"))
    page = ledger.query(since_seq=marker)
    assert page.total == 1
    assert page.entries[0]["message"] == "new"


def test_query_filters_by_library_and_registry_key(ledger):
    from haywire.core.library.identity import LibraryIdentity

    ident = LibraryIdentity(label="T", id="testing")
    ledger.record(_exc("a", library_identity=ident))
    ledger.record(_exc("b", registry_key="other:node:bar"))
    assert ledger.query(library="testing").total == 1
    assert ledger.query(registry_key="other:node:bar").total == 1
    assert ledger.query(library="nope").total == 0


def test_bounded_drops_oldest(ledger):
    for i in range(8):  # max_entries=5
        ledger.record(_exc(f"e{i}"))
    page = ledger.query(limit=100)
    assert page.total == 5
    assert page.entries[0]["message"] == "e3"  # oldest surviving
    # Sequence numbers keep climbing even though entries drop.
    assert ledger.current_seq == 8


def test_query_pagination(ledger):
    for i in range(5):
        ledger.record(_exc(f"e{i}"))
    page = ledger.query(limit=2, offset=2)
    assert page.total == 5
    assert [e["message"] for e in page.entries] == ["e2", "e3"]


def test_log_registers_in_ambient_ledger(ledger):
    exc = _exc("logged error")
    exc.log()
    assert ledger.query().total == 1
    assert ledger.query().entries[0]["message"] == "logged error"


def test_log_without_ledger_does_not_crash():
    set_error_ledger(None)
    _exc("no ledger").log()  # must not raise
```

Note: check `LibraryIdentity`'s constructor before writing the identity test — it lives at `packages/haywire-core/src/haywire/core/library/identity.py:5` and takes `label`, `id` among other defaulted fields; pass only keyword args that exist.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/test_errors/test_ledger.py -v`
Expected: FAIL / ERROR with `ModuleNotFoundError: No module named 'haywire.core.errors.ledger'`

- [ ] **Step 3: Implement the ledger**

```python
# packages/haywire-core/src/haywire/core/errors/ledger.py
"""Bounded, sequence-numbered in-memory error ledger.

Every HaywireException registers here at .log() time. Registry-scan import
errors flow through the same path because the scan failure handlers .log()
their exceptions. First consumers: Farmhand's studio_get_errors and
studio_verify_component tools.

The ambient accessor is a module-level global (not a ContextVar) to match
the DI-context idiom — see .insights/project_di_context.md.
"""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from haywire.core.errors.haywire_exception import HaywireException


@dataclass
class LedgerPage:
    """One page of ledger entries plus the current cursor."""

    entries: list[dict]
    total: int
    cursor: int


class ErrorLedger:
    """Bounded collection of serialized HaywireException snapshots."""

    def __init__(self, max_entries: int = 500):
        self._entries: deque[dict] = deque(maxlen=max_entries)
        self._seq = 0
        self._lock = threading.Lock()  # .log() fires from watchdog/timer threads too

    @property
    def current_seq(self) -> int:
        return self._seq

    def record(self, exc: "HaywireException") -> int:
        with self._lock:
            self._seq += 1
            self._entries.append(
                {
                    "seq": self._seq,
                    "timestamp": exc.timestamp,
                    "message": exc.message,
                    "category": exc.category,
                    "severity": exc.severity.value if exc.severity else None,
                    "operation": exc.operation,
                    "registry_key": exc.registry_key,
                    "library": exc.library_identity.id if exc.library_identity else None,
                    "filename": exc.filename,
                    "line_number": exc.line_number,
                    "tags": list(exc.tags),
                }
            )
            return self._seq

    def query(
        self,
        since_seq: Optional[int] = None,
        library: Optional[str] = None,
        registry_key: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> LedgerPage:
        with self._lock:
            rows = list(self._entries)
        if since_seq is not None:
            rows = [r for r in rows if r["seq"] > since_seq]
        if library is not None:
            rows = [r for r in rows if r["library"] == library]
        if registry_key is not None:
            rows = [r for r in rows if r["registry_key"] == registry_key]
        return LedgerPage(entries=rows[offset : offset + limit], total=len(rows), cursor=self._seq)


_error_ledger: Optional[ErrorLedger] = None


def get_error_ledger() -> ErrorLedger:
    """Return the ambient ledger, lazily creating the process-wide default."""
    global _error_ledger
    if _error_ledger is None:
        _error_ledger = ErrorLedger()
    return _error_ledger


def set_error_ledger(ledger: Optional[ErrorLedger]) -> None:
    """Replace the ambient ledger (tests use this for isolation)."""
    global _error_ledger
    _error_ledger = ledger
```

Check the exact field names against the `HaywireException` dataclass before finalizing `record()` — the fields listed in Interfaces above were verified (message/category/severity/operation/registry_key/library_identity/filename/line_number/timestamp/tags exist around `haywire_exception.py:520` and the query-methods section), but if any differ, follow the dataclass.

- [ ] **Step 4: Hook `HaywireException.log()`**

In `packages/haywire-core/src/haywire/core/errors/haywire_exception.py`, the existing method is:

```python
    def log(self, logger=None) -> "HaywireException":
        """Log to console (fallback when UI not available)"""
        import logging

        logger = logger or logging.getLogger()
        logger.error(self.format_detailed())
        return self
```

Change it to:

```python
    def log(self, logger=None) -> "HaywireException":
        """Log to console (fallback when UI not available) and register in the error ledger."""
        import logging

        from haywire.core.errors.ledger import get_error_ledger

        try:
            get_error_ledger().record(self)
        except Exception:
            pass  # the ledger must never break error reporting itself
        logger = logger or logging.getLogger()
        logger.error(self.format_detailed())
        return self
```

(Import inside the method mirrors the existing local `import logging` and avoids an import cycle with the errors package.)

- [ ] **Step 5: Verify registry-scan import errors reach the ledger**

Run: `grep -n "\.log()" packages/haywire-core/src/haywire/core/registry/base.py`

Expected: the scan/reload failure handlers (`_on_creation` / reload-failure paths around lines 437–467) call `.log()` on the `HaywireException` they build. If a scan-failure `except` block only calls `logger.error(...)` on a plain string and never constructs/logs a `HaywireException`, do NOT restructure it in this task — note the gap in the commit message; `studio_verify_component` (Task 9) reads the ledger for whatever does flow through. (Spot-check found `catch_exception → log` and multiple validation paths already calling `.log()`.)

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_errors/test_ledger.py -v`
Expected: all PASS.

- [ ] **Step 7: Lint, type-check, full fast suite, commit**

```bash
uv run ruff check packages/haywire-core/src/haywire/core/errors/ tests/core/test_errors/
uv run ruff format packages/haywire-core/src/haywire/core/errors/ tests/core/test_errors/
uv run pytest -m "not browser and not perf" -q
git add packages/haywire-core/src/haywire/core/errors/ tests/core/test_errors/
git commit -m "feat(errors): bounded sequence-numbered error ledger, registered on HaywireException.log()"
```

---

### Task 2: `SetPropertyAction` + `Editor.set_property` (mandated core work item 1)

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/undo/actions/graph_actions.py` (append the new action beside the nine existing ones)
- Modify: `packages/haywire-core/src/haywire/core/graph/editor.py` (new method after `move_nodes_to`, ~line 143; new import)
- Test: `tests/core/test_undo/test_set_property_action.py`

**Interfaces:**
- Consumes: `ActionBase` (`haywire/core/undo/base_action.py:17` — subclasses implement `_execute_impl()` / `_undo_impl()`; `undo()` resets `_executed` so redo re-runs `execute()`); `Editor.history_manager.add_action(action)` (executes immediately); `NodeWrapper.node -> BaseNode` property; `node.ports: dict[str, DataPort]`; `DataPort.get_value()` / `DataPort.set_value(new_value)`; settings bags via `type(node)._settings_bags` (list of accessor attr names) and `type(bag)._property_settings()` (dict of field-name → descriptor) — exactly the traversal `promote_setting` uses (`haywire/core/node/promotion.py:154-159`).
- Produces: `SetPropertyAction(graph, node_id, name, value)` and `Editor.set_property(node_id: str, name: str, value: Any) -> bool`. `name` resolves to a **port id first**, then a **settings-bag field name**. Task 13's `graph_editor_set_property` tool calls `editor.set_property(...)`.

- [ ] **Step 1: Write the failing tests**

Model the fixture usage on the existing action suite `tests/core/test_undo/test_paste_action.py` and on `make_node_with_setting` (`tests/conftest.py:448`, integration-marked because it needs `library_system` for builtin types). Read both before writing; then write:

```python
# tests/core/test_undo/test_set_property_action.py
"""SetPropertyAction: undoable set of a port value or settings-bag field by (node_id, name)."""

import pytest

pytestmark = pytest.mark.integration  # needs library_system for builtin types/nodes


@pytest.fixture()
def graph_and_editor(library_system):
    from haywire.core.graph.base import BaseGraph
    from haywire.core.graph.scheduler import SyncScheduler
    from haywire.core.graph.editor import Editor

    graph = BaseGraph("g", "g", validation_scheduler=SyncScheduler())
    editor = Editor(graph, library_system.get_node_factory())
    yield graph, editor
    graph.cleanup()


def _add_node(editor, registry_key="haybale_core:node:add"):
    wrapper = editor.create_wrapper(registry_key)
    assert wrapper is not None
    return wrapper


def test_set_port_value_and_undo_redo(graph_and_editor):
    graph, editor = graph_and_editor
    wrapper = _add_node(editor)
    node = wrapper.node
    port_id = next(pid for pid, p in node.ports.items() if p.is_inlet())
    before = node.ports[port_id].get_value()

    assert editor.set_property(wrapper.node_id, port_id, 42.0) is True
    assert node.ports[port_id].get_value() == 42.0

    assert editor.undo() is True
    assert node.ports[port_id].get_value() == before

    assert editor.redo() is True
    assert node.ports[port_id].get_value() == 42.0


def test_set_settings_field_and_undo(graph_and_editor, make_node_with_setting):
    graph, editor = graph_and_editor
    # make_node_with_setting yields (wrapper, accessor, field) — read the fixture
    # at tests/conftest.py:448 and adapt this unpacking to its actual return shape.
    wrapper, accessor, field = make_node_with_setting(editor)
    bag = getattr(wrapper.node, accessor)
    before = getattr(bag, field)
    new_value = before + 1 if isinstance(before, (int, float)) else "changed"

    assert editor.set_property(wrapper.node_id, field, new_value) is True
    assert getattr(bag, field) == new_value

    assert editor.undo() is True
    assert getattr(bag, field) == before


def test_unknown_node_returns_false(graph_and_editor):
    _, editor = graph_and_editor
    assert editor.set_property("no_such_node", "x", 1) is False


def test_unknown_name_returns_false(graph_and_editor):
    _, editor = graph_and_editor
    wrapper = _add_node(editor)
    assert editor.set_property(wrapper.node_id, "no_such_property", 1) is False
    assert editor.can_undo() is False or editor.undo() is not None  # nothing half-applied


def test_action_serializes(graph_and_editor):
    from haywire.core.undo.actions.graph_actions import SetPropertyAction

    graph, editor = graph_and_editor
    wrapper = _add_node(editor)
    port_id = next(pid for pid, p in wrapper.node.ports.items() if p.is_inlet())
    action = SetPropertyAction(graph, wrapper.node_id, port_id, 1.0)
    action.execute()
    d = action.to_dict()
    assert d["action_type"] == "SetPropertyAction"
    assert d["executed"] is True
```

Adapt the two marked spots to reality before running: (a) the `make_node_with_setting` fixture's exact signature/return, (b) a registry key that exists in the test barn (`haybale_core:node:add` — verify with `grep -rn "menu=" barn/haybale-core/haybale_core/nodes/ | head` or use `editor.get_available_node_regkeys()` interactively; any node with a float inlet works).

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/test_undo/test_set_property_action.py -v`
Expected: FAIL with `ImportError: cannot import name 'SetPropertyAction'` / `AttributeError: 'Editor' object has no attribute 'set_property'`

- [ ] **Step 3: Implement the action**

Append to `packages/haywire-core/src/haywire/core/undo/actions/graph_actions.py` (match the file's existing style — read one neighbor like `MoveNodesToAction` at line 258 first):

```python
class SetPropertyAction(ActionBase):
    """Undoable set of a node property addressed by (node_id, name).

    ``name`` resolves against the node's ports first (port id -> port value),
    then against its settings bags (field name -> settings-bag write). This is
    the one deliberate new core mutation surface mandated by the Farmhand spec:
    the raw settings/port write paths are non-undoable and not id-addressable.
    """

    def __init__(self, graph, node_id: str, name: str, value):
        super().__init__(description=f"Set '{name}' on {node_id}")
        self.graph = graph
        self.node_id = node_id
        self.name = name
        self.new_value = value
        self._old_value = None

    def _resolve(self):
        """Return (node, kind, accessor) where kind is 'port' or 'setting'."""
        wrapper = self.graph.get_node_wrapper(self.node_id)
        if wrapper is None:
            raise ValueError(f"Node '{self.node_id}' not found")
        node = wrapper.node
        if self.name in node.ports:
            return node, "port", None
        for accessor in type(node)._settings_bags:
            bag = getattr(node, accessor)
            if self.name in type(bag)._property_settings():
                return node, "setting", accessor
        raise ValueError(
            f"Node '{self.node_id}' has no port or setting named '{self.name}'"
        )

    def _execute_impl(self) -> None:
        node, kind, accessor = self._resolve()
        if kind == "port":
            self._old_value = node.ports[self.name].get_value()
            node.ports[self.name].set_value(self.new_value)
        else:
            bag = getattr(node, accessor)
            self._old_value = getattr(bag, self.name)
            setattr(bag, self.name, self.new_value)

    def _undo_impl(self) -> None:
        node, kind, accessor = self._resolve()
        if kind == "port":
            node.ports[self.name].set_value(self._old_value)
        else:
            setattr(getattr(node, accessor), self.name, self._old_value)
```

Note on redo semantics: `ActionBase.undo()` resets `_executed = False`, and the history manager redoes by calling `execute()` again — `_execute_impl` re-reads `_old_value` at that moment, which is the just-restored original. Correct by construction.

- [ ] **Step 4: Implement `Editor.set_property`**

In `packages/haywire-core/src/haywire/core/graph/editor.py`, add `SetPropertyAction` to the existing `graph_actions` import, then insert after `move_nodes_to` (line ~143):

```python
    def set_property(self, node_id: str, name: str, value: Any) -> bool:
        """Set a port value or settings-bag field on a node, undo-recorded.

        ``name`` resolves to a port id first, then a settings-bag field name.
        Returns False (without mutating) if the node or name is unknown.
        """
        try:
            action = SetPropertyAction(self.graph, node_id, name, value)
            self.history_manager.add_action(action)
            logger.info(f"Set property {name!r} on node {node_id}")
            return True
        except Exception as e:
            logger.error(f"Error setting property {name!r} on {node_id}: {e}")
            return False
```

(`Any` is already imported in the file's `typing` import; verify.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_undo/test_set_property_action.py -v`
Expected: all PASS.

- [ ] **Step 6: Lint, type-check, full suite, commit**

```bash
uv run ruff check packages/haywire-core/src/haywire/core/undo/ packages/haywire-core/src/haywire/core/graph/editor.py tests/core/test_undo/
uv run ruff format packages/haywire-core/src/haywire/core/undo/ packages/haywire-core/src/haywire/core/graph/editor.py tests/core/test_undo/
uv run mypy packages/haywire-core/src/
uv run pytest -m "not browser and not perf" -q
git add -A packages/haywire-core tests/core/test_undo/
git commit -m "feat(undo): SetPropertyAction + Editor.set_property — undoable (node_id, name) property writes"
```

---

### Task 3: Canon packaging into the haywire-core wheel (mandated core work item 2)

**Files:**
- Create: `packages/haywire-core/src/haywire/core/docs/__init__.py` (empty)
- Create: `packages/haywire-core/src/haywire/core/docs/canons.py`
- Modify: `packages/haywire-core/pyproject.toml`
- Test: `tests/core/test_docs/test_canons.py`

**Interfaces:**
- Consumes: repo layout `docs/components/<area>/<area>-canon.md` (areas include: nodes, types, ports, adapters, settings, widgets, themes, editors, panels, states, libraries, haybale-package).
- Produces: `haywire.core.docs.canons` with `canons_dir() -> Path`, `list_canon_areas() -> list[str]`, `read_canon(area: str) -> str` (raises `FileNotFoundError` with the list of valid areas on a miss). Task 14 serves these as `farmhand://docs/canon/{area}` resources; Task 9's scaffold tool cites them.

- [ ] **Step 1: Write the failing tests**

```python
# tests/core/test_docs/test_canons.py
"""Canon packaging: the component canons ship inside haywire-core and are readable at runtime."""

import pytest

from haywire.core.docs.canons import canons_dir, list_canon_areas, read_canon

pytestmark = pytest.mark.unit


def test_canons_dir_exists():
    assert canons_dir().is_dir()


def test_list_areas_contains_nodes():
    areas = list_canon_areas()
    assert "nodes" in areas
    assert areas == sorted(areas)


def test_read_canon_returns_markdown():
    text = read_canon("nodes")
    assert "worker" in text  # the node canon documents worker()


def test_read_canon_unknown_area_raises_with_choices():
    with pytest.raises(FileNotFoundError) as exc_info:
        read_canon("definitely-not-an-area")
    assert "nodes" in str(exc_info.value)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/test_docs/test_canons.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'haywire.core.docs'`

- [ ] **Step 3: Implement the accessor with packaged-path + dev fallback**

```python
# packages/haywire-core/src/haywire/core/docs/canons.py
"""Runtime access to the component canons (docs/components/*-canon.md).

In a built wheel the canons are force-included at haywire/docs/canons/
(see pyproject.toml). In a dev/editable checkout that directory does not
exist, so we fall back to the monorepo's docs/components/ found by walking
up from this file. Farmhand serves these as version-matched authoring
resources (farmhand://docs/canon/{area}).
"""

from __future__ import annotations

from pathlib import Path

import haywire


def canons_dir() -> Path:
    packaged = Path(haywire.__file__).resolve().parent / "docs" / "canons"
    if packaged.is_dir():
        return packaged
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "docs" / "components"
        if (candidate / "nodes" / "nodes-canon.md").exists():
            return candidate
    raise FileNotFoundError(
        "Component canons not found: neither the packaged haywire/docs/canons "
        "nor a monorepo docs/components directory exists."
    )


def list_canon_areas() -> list[str]:
    root = canons_dir()
    return sorted(
        child.name for child in root.iterdir() if child.is_dir() and _canon_file(root, child.name)
    )


def read_canon(area: str) -> str:
    path = _canon_file(canons_dir(), area)
    if path is None:
        raise FileNotFoundError(
            f"No canon for area '{area}'. Valid areas: {', '.join(list_canon_areas())}"
        )
    return path.read_text(encoding="utf-8")


def _canon_file(root: Path, area: str) -> Path | None:
    path = root / area / f"{area}-canon.md"
    return path if path.exists() else None
```

**Verify the actual canon filename convention first** — CLAUDE.md says `docs/components/<area>/<area>-canon.md`; run `ls docs/components/nodes/` to confirm whether the file is `nodes-canon.md` or `node-canon.md` (the operations inventory cites `docs/components/nodes/node-canon.md`, singular). If it's singular per-directory-plural (`nodes/node-canon.md`), change `_canon_file` to glob: `next(iter((root / area).glob("*-canon.md")), None)` — and mirror that in the fallback check inside `canons_dir()`.

- [ ] **Step 4: Add the wheel force-include**

In `packages/haywire-core/pyproject.toml`, after `[tool.hatch.build.targets.wheel]`:

```toml
[tool.hatch.build.targets.wheel.force-include]
"../../docs/components" = "haywire/docs/canons"
```

- [ ] **Step 5: Run tests, verify the wheel really contains the canons**

Run: `uv run pytest tests/core/test_docs/test_canons.py -v`
Expected: all PASS (dev fallback path).

Run: `cd packages/haywire-core && uv build --wheel && unzip -l dist/*.whl | grep canons | head -5; cd ../..`
Expected: lines like `haywire/docs/canons/nodes/node-canon.md`. Delete the `dist/` directory afterwards (`rm -rf packages/haywire-core/dist`).

- [ ] **Step 6: Lint, commit**

```bash
uv run ruff check packages/haywire-core/src/haywire/core/docs/ tests/core/test_docs/
uv run ruff format packages/haywire-core/src/haywire/core/docs/ tests/core/test_docs/
uv run mypy packages/haywire-core/src/
git add packages/haywire-core/src/haywire/core/docs/ packages/haywire-core/pyproject.toml tests/core/test_docs/
git commit -m "feat(docs): package component canons into the haywire-core wheel with runtime accessor"
```

---

### Task 4: `Farmhand` base, `@farmhand` decorator, schema derivation (core seam, part 1)

**Files:**
- Create: `packages/haywire-core/src/haywire/core/farmhand/__init__.py`
- Create: `packages/haywire-core/src/haywire/core/farmhand/identity.py`
- Create: `packages/haywire-core/src/haywire/core/farmhand/base.py`
- Create: `packages/haywire-core/src/haywire/core/farmhand/decorator.py`
- Create: `packages/haywire-core/src/haywire/core/farmhand/schema.py`
- Modify: `packages/haywire-core/src/haywire/core/library/utils.py` (add `FARMHAND = "farmhand"` kind constant beside `NODE` — copy the existing constants' style)
- Test: `tests/core/test_farmhand/test_decorator.py`, `tests/core/test_farmhand/test_schema.py`

**Interfaces:**
- Consumes: `derive_library_identity(cls)` and `reg_key(lib_id, kind, name)` from `haywire/core/library/utils.py` (the `@state` decorator idiom, `haywire/core/state/decorator.py:43-64`); `LibraryIdentity`.
- Produces (SDK-free; Tasks 5–14 rely on these exact names):
  - `ToolAnnotations` dataclass: `read_only_hint: bool = False`, `destructive_hint: bool = False`, `idempotent_hint: bool = False`, `open_world_hint: bool = False`; method `to_dict() -> dict` with camelCase MCP keys (`readOnlyHint`, …).
  - `FarmhandIdentity(BaseIdentity)` — extends `BaseIdentity` (`haywire/core/registry/identity.py:9`) like every sibling identity, adding only `annotations: ToolAnnotations` (so `registry_id/registry_key/label/description/deprecation_warning/hidden/class_name/module` are inherited).
  - `Farmhand` base class: ClassVars `class_identity`, `class_library`, `input_schema_override: dict | None = None`; `async def run(self, ctx, **kwargs) -> dict`; classmethods `mcp_name() -> str` (`{lib_id}_{registry_id}`), `input_schema() -> dict`.
  - `@farmhand(**kwargs)` — the `@node` decorator shape (freeform `**kwargs` splatted into `FarmhandIdentity`, `setdefault` for `registry_id`/`label`/`annotations` from the class name, kind constant `FARMHAND`). Accepts any `FarmhandIdentity` field (`label`, `description`, `registry_id`, `annotations`, `hidden`, `deprecation_warning`); unknown keys raise in the dataclass constructor. Identity always derives from the defining library module. The `studio_*` baseline needs no special path: it lives in barn/haybale-studio, whose library id is `studio` (header deviation note 2).
  - `derive_input_schema(fn) -> dict` in `schema.py` — JSON Schema from the `run()` signature.
  - All of the above re-exported from `haywire/core/farmhand/__init__.py`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/core/test_farmhand/test_schema.py
"""JSON-Schema derivation from Farmhand.run() signatures."""

import pytest

from haywire.core.farmhand.schema import derive_input_schema

pytestmark = pytest.mark.unit


def test_types_defaults_and_required():
    async def run(self, ctx, path: str, count: int = 10, deep: bool = False):
        ...

    schema = derive_input_schema(run)
    assert schema["type"] == "object"
    assert schema["properties"]["path"] == {"type": "string"}
    assert schema["properties"]["count"] == {"type": "integer", "default": 10}
    assert schema["properties"]["deep"] == {"type": "boolean", "default": False}
    assert schema["required"] == ["path"]


def test_optional_and_containers():
    async def run(self, ctx, name: str | None = None, ids: list[str] = [], meta: dict = {}):
        ...

    schema = derive_input_schema(run)
    assert schema["properties"]["name"]["type"] == "string"
    assert schema["properties"]["ids"] == {"type": "array", "items": {"type": "string"}, "default": []}
    assert schema["properties"]["meta"]["type"] == "object"
    assert schema["required"] == []


def test_float_and_unannotated():
    async def run(self, ctx, x: float, anything=None):
        ...

    schema = derive_input_schema(run)
    assert schema["properties"]["x"] == {"type": "number"}
    assert schema["properties"]["anything"] == {"default": None}
```

```python
# tests/core/test_farmhand/test_decorator.py
"""@farmhand stamps identity; naming and annotations follow the spec."""

import pytest

from haywire.core.farmhand import Farmhand, ToolAnnotations, farmhand

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _stub_library_identity(monkeypatch):
    """These unit tests run outside any library module, so stub the derivation
    (patch the name the decorator module imported, not the utils original)."""
    from haywire.core.farmhand import decorator as decorator_module
    from haywire.core.library.identity import LibraryIdentity

    monkeypatch.setattr(
        decorator_module,
        "derive_library_identity",
        lambda cls: LibraryIdentity(label="Studio", id="studio"),
    )


def _make_tool():
    @farmhand(
        label="Status",
        description="Report studio status.",
        registry_id="status",
        annotations=ToolAnnotations(read_only_hint=True),
    )
    class StatusTool(Farmhand):
        async def run(self, ctx) -> dict:
            return {}

    return StatusTool


def test_identity_and_mcp_name():
    tool = _make_tool()
    assert tool.class_identity.registry_key == "studio:farmhand:status"
    assert tool.class_library.id == "studio"
    assert tool.mcp_name() == "studio_status"
    assert tool.class_identity.annotations.read_only_hint is True


def test_registry_id_defaults_to_class_name():
    # Established pattern (@node/@state): verbatim class name, no transformation.
    @farmhand()
    class ListOpenGraphs(Farmhand):
        async def run(self, ctx) -> dict:
            return {}

    assert ListOpenGraphs.class_identity.registry_key == "studio:farmhand:ListOpenGraphs"


def test_sync_run_rejected():
    with pytest.raises(TypeError, match="async"):

        @farmhand()
        class BadTool(Farmhand):
            def run(self, ctx) -> dict:  # type: ignore[override]
                return {}


def test_non_subclass_rejected():
    with pytest.raises(TypeError):

        @farmhand()
        class NotATool:
            async def run(self, ctx) -> dict:
                return {}


def test_input_schema_uses_override_when_present():
    @farmhand()
    class Overridden(Farmhand):
        input_schema_override = {"type": "object", "properties": {"q": {"type": "string"}}}

        async def run(self, ctx, q: str) -> dict:
            return {}

    assert Overridden.input_schema() == Overridden.input_schema_override


def test_annotations_to_dict_camelcase():
    d = ToolAnnotations(read_only_hint=True, destructive_hint=True).to_dict()
    assert d == {
        "readOnlyHint": True,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": False,
    }


def test_inherited_baseidentity_field_passes_through():
    # @node's **kwargs shape means BaseIdentity fields flow through for free.
    @farmhand(hidden=True)
    class HiddenTool(Farmhand):
        async def run(self, ctx) -> dict:
            return {}

    assert HiddenTool.class_identity.hidden is True


def test_unknown_kwarg_raises():
    with pytest.raises(TypeError):

        @farmhand(not_a_field="oops")
        class BadFieldTool(Farmhand):
            async def run(self, ctx) -> dict:
                return {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/test_farmhand/ -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'haywire.core.farmhand'`

- [ ] **Step 3: Implement identity + annotations**

```python
# packages/haywire-core/src/haywire/core/farmhand/identity.py
"""Class identity for Farmhand (MCP tool) components — extends BaseIdentity
like every sibling identity (NodeIdentity, EditorIdentity, LibraryStateClassIdentity)."""

from __future__ import annotations

from dataclasses import dataclass, field

from haywire.core.registry.identity import BaseIdentity


@dataclass
class ToolAnnotations:
    """SDK-free mirror of the MCP spec's tool annotations (consent hints)."""

    read_only_hint: bool = False
    destructive_hint: bool = False
    idempotent_hint: bool = False
    open_world_hint: bool = False

    def to_dict(self) -> dict:
        return {
            "readOnlyHint": self.read_only_hint,
            "destructiveHint": self.destructive_hint,
            "idempotentHint": self.idempotent_hint,
            "openWorldHint": self.open_world_hint,
        }


@dataclass
class FarmhandIdentity(BaseIdentity):
    """Inherits registry_id/registry_key/label/description/deprecation_warning/
    hidden/class_name/module from BaseIdentity; adds the MCP consent annotations."""

    annotations: ToolAnnotations = field(default_factory=ToolAnnotations)
```

- [ ] **Step 4: Implement the base class**

```python
# packages/haywire-core/src/haywire/core/farmhand/base.py
"""Farmhand — one class per MCP tool, contributed from a library's farmhands/ folder."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, Optional

from haywire.core.farmhand.schema import derive_input_schema

if TYPE_CHECKING:
    from haywire.core.farmhand.context import FarmhandContext
    from haywire.core.farmhand.identity import FarmhandIdentity
    from haywire.core.library.identity import LibraryIdentity


class Farmhand:
    """Base class for MCP tools.

    Subclass, decorate with @farmhand, implement one async run(ctx, ...).
    The input schema derives from run()'s signature (type hints + defaults);
    set input_schema_override for constraints hints can't express.
    """

    class_identity: ClassVar["FarmhandIdentity"]
    class_library: ClassVar["LibraryIdentity"]
    input_schema_override: ClassVar[Optional[dict]] = None

    async def run(self, ctx: "FarmhandContext", **kwargs: Any) -> dict:
        raise NotImplementedError

    @classmethod
    def mcp_name(cls) -> str:
        lib_id, _, registry_id = cls.class_identity.registry_key.split(":")
        return f"{lib_id}_{registry_id}"

    @classmethod
    def input_schema(cls) -> dict:
        if cls.input_schema_override is not None:
            return cls.input_schema_override
        return derive_input_schema(cls.run)
```

- [ ] **Step 5: Implement schema derivation**

```python
# packages/haywire-core/src/haywire/core/farmhand/schema.py
"""JSON Schema derivation from a Farmhand.run() signature.

The node-worker() signature-analysis idiom applied to MCP input schemas:
type hints + defaults become the schema; self and ctx are skipped.
"""

from __future__ import annotations

import inspect
import types
import typing
from typing import Any

_PRIMITIVES: dict[Any, dict] = {
    str: {"type": "string"},
    int: {"type": "integer"},
    float: {"type": "number"},
    bool: {"type": "boolean"},
    dict: {"type": "object"},
    list: {"type": "array"},
}


def derive_input_schema(fn) -> dict:
    sig = inspect.signature(fn)
    hints = typing.get_type_hints(fn)
    properties: dict[str, dict] = {}
    required: list[str] = []

    for name, param in sig.parameters.items():
        if name in ("self", "ctx") or param.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue
        prop = dict(_annotation_to_schema(hints.get(name)))
        if param.default is inspect.Parameter.empty:
            required.append(name)
        else:
            prop["default"] = param.default
        properties[name] = prop

    return {"type": "object", "properties": properties, "required": required}


def _annotation_to_schema(annotation: Any) -> dict:
    if annotation is None or annotation is inspect.Parameter.empty:
        return {}
    if annotation in _PRIMITIVES:
        return _PRIMITIVES[annotation]

    origin = typing.get_origin(annotation)
    args = typing.get_args(annotation)

    # Optional[X] / X | None -> schema of X (presence is handled by required=)
    if origin in (typing.Union, types.UnionType):
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            return _annotation_to_schema(non_none[0])
        return {}
    if origin is list:
        item = _annotation_to_schema(args[0]) if args else {}
        return {"type": "array", "items": item}
    if origin is dict:
        return {"type": "object"}
    return {}  # unknown types: accept anything (schema evolution convention, spec §5)
```

- [ ] **Step 6: Implement the decorator**

```python
# packages/haywire-core/src/haywire/core/farmhand/decorator.py
"""@farmhand — stamps FarmhandIdentity. Follows the @node decorator shape
(node/decorator.py:70): freeform **kwargs splatted into the identity dataclass,
class-name defaults via setdefault, kind constant from library/utils."""

from __future__ import annotations

import inspect
from typing import Any, Callable, Type, TypeVar

from haywire.core.farmhand.base import Farmhand
from haywire.core.farmhand.identity import FarmhandIdentity, ToolAnnotations
from haywire.core.library.utils import FARMHAND, derive_library_identity, reg_key

T = TypeVar("T")


def farmhand(**kwargs: Any) -> Callable[[Type[T]], Type[T]]:
    """
    Decorator to register a class as a Farmhand (a haywire MCP tool).

    Always invoked with parentheses — `@farmhand(...)` or `@farmhand()`.
    Accepts FarmhandIdentity fields as keyword arguments; unknown keys raise
    in the dataclass constructor.

    Identity Fields (metadata):
        label (str): Human-readable display name. Default: registry_id
        description (str): Tool description shown to MCP clients. Default: ""
        registry_id (str): Unique identifier within library. Default: class name.
            The MCP-visible tool name is {lib_id}_{registry_id}, so pass a
            snake_case registry_id (e.g. registry_id="save_graph").
        annotations (ToolAnnotations): MCP consent hints
            (read_only_hint/destructive_hint/...). Default: ToolAnnotations()
        hidden (bool): Exclude from author-facing selection UIs. Default: False
        deprecation_warning (str): Advisory message. Default: ""

    The library identity derives from the defining module; the studio_*
    baseline is simply barn/haybale-studio's farmhands/ folder — its library
    id IS 'studio', so no special registration path exists.

    Example:

    .. code-block:: python

        @farmhand(
            label="Save graph",
            description="Save an open graph; save_as writes to a new path.",
            registry_id="save_graph",
            annotations=ToolAnnotations(),
        )
        class SaveGraphTool(Farmhand):
            async def run(self, ctx, binding_id: str, save_as: str | None = None) -> dict:
                ...
    """

    def decorator(inner_cls: Type[T]) -> Type[T]:
        if not (inspect.isclass(inner_cls) and issubclass(inner_cls, Farmhand)):
            raise TypeError(f"@farmhand can only be applied to Farmhand subclasses, got {inner_cls}")
        if not inspect.iscoroutinefunction(inner_cls.run):
            raise TypeError(
                f"{inner_cls.__name__}.run must be async — the MCP SDK thread-offloads "
                f"sync functions, breaking loop affinity."
            )

        identity_kwargs: dict[str, Any] = dict(kwargs)

        # Set defaults from class name if not provided (the @node idiom)
        identity_kwargs.setdefault("registry_id", inner_cls.__name__)
        identity_kwargs.setdefault("label", identity_kwargs["registry_id"])
        identity_kwargs.setdefault("annotations", ToolAnnotations())

        # Get library identity (survives hot-reload)
        library_identity = derive_library_identity(inner_cls)

        # Auto-derive registry_key
        identity_kwargs["registry_key"] = reg_key(
            library_identity.id, FARMHAND, identity_kwargs["registry_id"]
        )

        # Set source info from the class itself
        identity_kwargs["class_name"] = inner_cls.__name__
        identity_kwargs["module"] = inner_cls.__module__

        inner_cls.class_identity = FarmhandIdentity(**identity_kwargs)
        inner_cls.class_library = library_identity
        return inner_cls

    return decorator
```

Verify `reg_key`'s argument order and the kind-constant style in `haywire/core/library/utils.py` (`@node` uses the `NODE` constant; add `FARMHAND = "farmhand"` beside it), and check what `derive_library_identity` does for a class defined outside any library — the test fixture stubs it, but the error path for a stray module should be a clear exception, not a silent bogus id.

- [ ] **Step 7: Wire the package exports**

```python
# packages/haywire-core/src/haywire/core/farmhand/__init__.py
"""Farmhand contribution seam (SDK-free): tools, registry, context."""

from haywire.core.farmhand.decorator import farmhand
from haywire.core.farmhand.identity import FarmhandIdentity, ToolAnnotations
from haywire.core.farmhand.schema import derive_input_schema
from haywire.core.farmhand.base import Farmhand

__all__ = [
    "Farmhand",
    "FarmhandIdentity",
    "ToolAnnotations",
    "derive_input_schema",
    "farmhand",
]
```

(Task 5 appends `FarmhandRegistry`, Task 6 appends `FarmhandContext`.)

- [ ] **Step 8: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_farmhand/ -v`
Expected: all PASS.

- [ ] **Step 9: Lint, type-check, commit**

```bash
uv run ruff check packages/haywire-core/src/haywire/core/farmhand/ tests/core/test_farmhand/
uv run ruff format packages/haywire-core/src/haywire/core/farmhand/ tests/core/test_farmhand/
uv run mypy packages/haywire-core/src/
git add packages/haywire-core/src/haywire/core/farmhand/ tests/core/test_farmhand/
git commit -m "feat(farmhand): Farmhand base, @farmhand decorator, signature-derived input schemas"
```

---

### Task 5: `FarmhandRegistry` — the tenth typed registry, DI-wired (core seam, part 2)

**Files:**
- Create: `packages/haywire-core/src/haywire/core/farmhand/registry.py`
- Modify: `packages/haywire-core/src/haywire/core/farmhand/__init__.py` (export)
- Modify: `packages/haywire-core/src/haywire/core/di/config.py` (provider + eager-get + `add_class_registry` link)
- Modify: `packages/haywire-core/src/haywire/core/library/base.py` (scan-order comment, line ~200)
- Test: `tests/core/test_farmhand/test_registry.py`

**Interfaces:**
- Consumes: `BaseRegistry` (`haywire/core/registry/base.py:79` — subclasses implement `_class_filter(cls)` and `_register_class(cls, library_identity)`; `NodeRegistry` at `haywire/core/node/registry.py:16` is the model); `LibraryRegistry.add_class_registry(cls, instance)` (`library/registry.py:127`); the DI wiring block in `LibrarySystemService.initialize()` (`di/config.py:349-382`).
- Produces:
  - `FarmhandRegistry(BaseRegistry[Farmhand])` with kind constant `KIND = "farmhand"`, standard folder-scan/hot-reload/eviction inherited. No special registration paths: the `studio` baseline is just haybale-studio's `farmhands/` folder, and the prefix reservation is enforced by library-id uniqueness at discovery (decided — no registry guard).
  - DI: `HaywireModule.provide_farmhand_registry()` singleton; linked in `initialize()` via `add_class_registry(FarmhandRegistry, farmhand_registry)`.
  - Subscription surface used by the host (Task 8): `registry.add_batch_event_subscriber(callback)` (`registry/base.py:896`), events are `LifeCycleEvent` with `LifeCycleEventType.CLASS_ADDED` / `CLASS_REMOVED` (`registry/lifecycle_event.py:19,32`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/core/test_farmhand/test_registry.py
"""FarmhandRegistry: class filter, register/lookup, lifecycle event surface."""

import pytest

from haywire.core.farmhand import Farmhand, FarmhandRegistry, ToolAnnotations
from haywire.core.library.identity import LibraryIdentity
from haywire.core.registry.lifecycle_event import LifeCycleEventType

pytestmark = pytest.mark.unit


def _library_tool(lib_id: str = "testing", name: str = "echo"):
    """Build a tool class with a hand-stamped identity (no library import machinery)."""
    from haywire.core.farmhand.identity import FarmhandIdentity

    class EchoTool(Farmhand):
        async def run(self, ctx, text: str) -> dict:
            return {"echo": text}

    EchoTool.class_identity = FarmhandIdentity(
        registry_id=name,
        registry_key=f"{lib_id}:farmhand:{name}",
        label=name,
        description="",
        class_name="EchoTool",
        module=__name__,
        annotations=ToolAnnotations(read_only_hint=True),
    )
    EchoTool.class_library = LibraryIdentity(label=lib_id, id=lib_id)
    return EchoTool


def test_class_filter_accepts_decorated_tools_only():
    registry = FarmhandRegistry()
    assert registry._class_filter(_library_tool()) is True
    assert registry._class_filter(Farmhand) is False
    assert registry._class_filter(dict) is False

    class Undecorated(Farmhand):
        async def run(self, ctx) -> dict:
            return {}

    assert registry._class_filter(Undecorated) is False  # no class_identity


def test_register_and_lookup():
    registry = FarmhandRegistry()
    tool = _library_tool()
    key = registry._register_class(tool, tool.class_library)
    assert key == "testing:farmhand:echo"
    assert registry.get("testing:farmhand:echo") is tool


def test_unregister_removes_class():
    registry = FarmhandRegistry()
    tool = _library_tool()
    registry._register_class(tool, tool.class_library)
    registry._unregister_class("testing:farmhand:echo")
    assert registry.get("testing:farmhand:echo") is None


def test_lifecycle_event_types_exist():
    # The host (Task 8) keys its pipeline on these two event types.
    assert LifeCycleEventType.CLASS_ADDED is not None
    assert LifeCycleEventType.CLASS_REMOVED is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/test_farmhand/test_registry.py -v`
Expected: FAIL with `ImportError: cannot import name 'FarmhandRegistry'`

- [ ] **Step 3: Implement the registry (model: `NodeRegistry`)**

Before writing, read `BaseRegistry._register` and `_unregister` signatures in `packages/haywire-core/src/haywire/core/registry/base.py` (NodeRegistry calls `super()._register(registry_key, cls, library_identity)` and `super()._unregister(registry_key)` — mirror exactly).

```python
# packages/haywire-core/src/haywire/core/farmhand/registry.py
"""FarmhandRegistry — typed class registry for Farmhand (MCP tool) components (kind 'farmhand')."""

from __future__ import annotations

import inspect
import logging
from typing import Optional

from haywire.core.farmhand.base import Farmhand
from haywire.core.library.identity import LibraryIdentity
from haywire.core.registry.base import BaseRegistry

logger = logging.getLogger(__name__)


class FarmhandRegistry(BaseRegistry[Farmhand]):
    """Registry for Farmhand classes using {lib_id}:farmhand:{name} keys.

    The 'studio' prefix belongs to barn/haybale-studio (library id 'studio',
    home of the baseline tools); the reservation is enforced by library-id
    uniqueness at discovery, not by this registry (user decision 2026-07-19).
    """

    KIND = "farmhand"

    def _class_filter(self, cls) -> bool:
        try:
            return (
                inspect.isclass(cls)
                and issubclass(cls, Farmhand)
                and cls is not Farmhand
                and hasattr(cls, "class_identity")
            )
        except TypeError:
            return False

    def _register_class(
        self, cls: type[Farmhand], library_identity: Optional[LibraryIdentity] = None
    ) -> str | None:
        return super()._register(cls.class_identity.registry_key, cls, library_identity)

    def _unregister_class(self, registry_key: str) -> type[Farmhand] | None:
        return super()._unregister(registry_key)
```

Add to `packages/haywire-core/src/haywire/core/farmhand/__init__.py`:

```python
from haywire.core.farmhand.registry import FarmhandRegistry
```

and append `"FarmhandRegistry"` to `__all__`.

- [ ] **Step 4: DI wiring**

In `packages/haywire-core/src/haywire/core/di/config.py`:

1. Import `from haywire.core.farmhand.registry import FarmhandRegistry` alongside the other registry imports at the top.
2. Add a provider to `HaywireModule` (beside `provide_panel_registry`, ~line 214):

```python
    @provider
    @singleton
    def provide_farmhand_registry(self) -> FarmhandRegistry:
        """Provide singleton FarmhandRegistry (Farmhand/MCP-tool components, kind 'farmhand')."""
        return FarmhandRegistry()
```

3. In `LibrarySystemService.initialize()`, add an eager get beside the others (~line 362):

```python
        farmhand_registry = self.injector.get(FarmhandRegistry)
```

4. Add the link in the `add_class_registry` block (~line 382, after `LibraryStateRegistry`):

```python
        library_registry.add_class_registry(FarmhandRegistry, farmhand_registry)
```

- [ ] **Step 5: Document the scan order**

In `packages/haywire-core/src/haywire/core/library/base.py`, update the canonical-scan-order comment (line ~200):

```python
    # Canonical scan order: settings → state → farmhands → (types/nodes/adapters/widgets/skins/themes)
    # → panels → editors. State must exist before editor CLASS_ADDED events fire;
    # farmhands/ scans after state/ because tools may reference library states (Farmhand spec §3).
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_farmhand/test_registry.py -v`
Expected: all PASS.

Also run the DI provider suite to confirm the module still assembles: `uv run pytest packages/haywire-core/src/haywire/core/di/test_config.py -v`
Expected: PASS.

- [ ] **Step 7: Lint, type-check, full fast suite, commit**

```bash
uv run ruff check packages/haywire-core/src/haywire/core/farmhand/ packages/haywire-core/src/haywire/core/di/config.py tests/core/test_farmhand/
uv run ruff format packages/haywire-core/src/haywire/core/farmhand/ packages/haywire-core/src/haywire/core/di/config.py tests/core/test_farmhand/
uv run mypy packages/haywire-core/src/
uv run pytest -m "not browser and not perf" -q
git add -A packages/haywire-core tests/core/test_farmhand/
git commit -m "feat(farmhand): FarmhandRegistry as the tenth typed registry, DI-wired"
```

---

### Task 6: `FarmhandContext` (core seam, part 3)

**Files:**
- Create: `packages/haywire-core/src/haywire/core/farmhand/context.py`
- Modify: `packages/haywire-core/src/haywire/core/farmhand/__init__.py` (export)
- Test: `tests/core/test_farmhand/test_context.py`

**Interfaces:**
- Consumes: ambient DI getters from `haywire/core/di/context.py` — `get_library_state_container()`, `get_session_manager()`, `get_workspace_root()`, `get_settings_registry()`; `haywire/core/di/config.py` globals for the injector (check for a `get_global_injector()` getter next to `set_global_injector`; if only the setter exists, read the module global `_global_injector` via a small helper added here-adjacent — do NOT add new module APIs without checking first); `SessionManager.broadcast(signal)` (`session/session_manager.py:99`).
- Produces: `FarmhandContext` with:
  - `state(state_cls: type[T]) -> T` — resolve an AppState (e.g. `HaystackState`) from the container.
  - `registry(registry_cls: type[R]) -> R` — resolve a typed registry from the global injector.
  - `broadcast(signal) -> None` — `SessionManager.broadcast` (cross-session signals; caller-owned emission per inventory gap 5).
  - `async offload(fn, *args, **kwargs)` — `asyncio.to_thread` for blocking work.
  - `async progress(message: str) -> None` — no-op unless the host injected a reporter.
  - `fence(editor) -> None` — `editor.add_fence()`; mutating graph tools call this exactly once, first.
  - `workspace_root() -> Path`.
  - Constructor: `FarmhandContext(progress_reporter: Callable[[str], Awaitable[None]] | None = None)`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/core/test_farmhand/test_context.py
"""FarmhandContext: DI accessors, broadcast, offload, fence, progress."""

import asyncio
import threading

import pytest

from haywire.core.farmhand import FarmhandContext

pytestmark = pytest.mark.unit


def test_offload_runs_off_the_calling_thread():
    ctx = FarmhandContext()

    async def scenario():
        return await ctx.offload(lambda: threading.current_thread().name)

    worker_thread = asyncio.run(scenario())
    assert worker_thread != threading.main_thread().name


def test_progress_is_noop_without_reporter():
    ctx = FarmhandContext()
    asyncio.run(ctx.progress("hello"))  # must not raise


def test_progress_calls_injected_reporter():
    seen: list[str] = []

    async def reporter(message: str) -> None:
        seen.append(message)

    ctx = FarmhandContext(progress_reporter=reporter)
    asyncio.run(ctx.progress("step 1"))
    assert seen == ["step 1"]


def test_fence_delegates_to_editor():
    class FakeEditor:
        def __init__(self):
            self.fences = 0

        def add_fence(self):
            self.fences += 1

    editor = FakeEditor()
    FarmhandContext().fence(editor)
    assert editor.fences == 1


def test_broadcast_uses_ambient_session_manager(monkeypatch):
    from haywire.core.di import context as di_context

    class FakeManager:
        def __init__(self):
            self.signals = []

        def broadcast(self, signal):
            self.signals.append(signal)

    fake = FakeManager()
    monkeypatch.setattr(di_context, "_session_manager", fake)
    sentinel = object()
    FarmhandContext().broadcast(sentinel)
    assert fake.signals == [sentinel]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/test_farmhand/test_context.py -v`
Expected: FAIL with `ImportError: cannot import name 'FarmhandContext'`

- [ ] **Step 3: Implement**

First verify the injector getter: `grep -n "def get_global_injector\|_global_injector" packages/haywire-core/src/haywire/core/di/config.py`. If `get_global_injector()` exists, use it; otherwise `registry()` reads `di_config._global_injector` directly with a clear error when None.

```python
# packages/haywire-core/src/haywire/core/farmhand/context.py
"""FarmhandContext — the facade every Farmhand.run() receives.

Turns the codebase's conventions into methods: ambient-DI resolution,
caller-owned cross-session signal emission (inventory gap 5), thread
offload for blocking work (handlers share the NiceGUI loop in-process),
MCP progress bridging, and the one-call-one-undo-fence rule (ticket 06).
Future enforcement point for guardrails — add locks/policies here, not
in tools.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional, TypeVar

from haywire.core.di.context import (
    get_library_state_container,
    get_session_manager,
    get_workspace_root,
)

T = TypeVar("T")


class FarmhandContext:
    def __init__(self, progress_reporter: Optional[Callable[[str], Awaitable[None]]] = None):
        self._progress_reporter = progress_reporter

    def state(self, state_cls: type[T]) -> T:
        """Resolve an AppState instance (e.g. HaystackState) from the DI container."""
        return get_library_state_container().get(state_cls)

    def registry(self, registry_cls: type[T]) -> T:
        """Resolve a framework singleton (registries, factories) from the global injector."""
        from haywire.core.di import config as di_config

        injector = getattr(di_config, "_global_injector", None)
        if injector is None:
            raise RuntimeError("Global injector not set — is the library system initialized?")
        return injector.get(registry_cls)

    def broadcast(self, signal: Any) -> None:
        """Emit a cross-session signal so open browser UIs update (caller-owned, gap 5)."""
        get_session_manager().broadcast(signal)

    async def offload(self, fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Run blocking work off the shared NiceGUI loop."""
        return await asyncio.to_thread(fn, *args, **kwargs)

    async def progress(self, message: str) -> None:
        """Stream a progress line to the MCP client (no-op outside a request)."""
        if self._progress_reporter is not None:
            await self._progress_reporter(message)

    def fence(self, editor: Any) -> None:
        """Open the undo fence for this tool call: one call = one undo gesture."""
        editor.add_fence()

    def workspace_root(self) -> Path:
        return Path(get_workspace_root())
```

If `get_global_injector()` turned out to exist in step 3's grep, replace the `getattr(di_config, "_global_injector", None)` body with a plain call to it.

**Cancellation (spec §3):** no explicit API is needed in v1 — handlers are `async` and run as tasks the SDK cancels when the client cancels a request, so `await` points (including `offload`) are the cancellation points. State this in the module docstring so the omission reads as a decision, not a gap.

Export from `__init__.py` (add import + `"FarmhandContext"` to `__all__`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_farmhand/test_context.py -v`
Expected: all PASS.

- [ ] **Step 5: Lint, type-check, commit**

```bash
uv run ruff check packages/haywire-core/src/haywire/core/farmhand/ tests/core/test_farmhand/
uv run ruff format packages/haywire-core/src/haywire/core/farmhand/ tests/core/test_farmhand/
uv run mypy packages/haywire-core/src/
git add packages/haywire-core/src/haywire/core/farmhand/ tests/core/test_farmhand/
git commit -m "feat(farmhand): FarmhandContext handler facade (DI accessors, broadcast, offload, fence, progress)"
```

---

### Task 7: Studio-side settings flag, bearer token, auth middleware

**Files:**
- Create: `packages/haywire-studio/src/haywire_studio/farmhand/__init__.py` (empty)
- Create: `packages/haywire-studio/src/haywire_studio/farmhand/settings.py`
- Create: `packages/haywire-studio/src/haywire_studio/farmhand/auth.py`
- Test: `tests/farmhand/test_auth_unit.py`

**Interfaces:**
- Consumes: `FrameworkSettings` (`haywire/core/settings/settings_framework.py:33` — subclass with `namespace=`, fields via `setting[BOOL](...)`, registration automatic; model: `CanvasSettings` at `haywire/ui/components/graph/settings.py:9`); `BOOL` from `haywire.barn.builtin.types`.
- Produces:
  - `FarmhandSettings(FrameworkSettings, namespace="farmhand")` with `enabled` (BOOL, default True). Read once at startup (Task 8); changes take effect on restart.
  - `ensure_token(workspace_root: Path) -> str` — creates/reads `<workspace>/.haywire/farmhand_token` (0600) and guarantees `<workspace>/.haywire/.gitignore` covers it; delete-file-to-rotate.
  - `BearerTokenMiddleware(app, token)` — pure ASGI wrapper, 401 JSON on missing/wrong `Authorization: Bearer <token>`.
  - `connection_command(port: int, token: str) -> str` — the ready-made `claude mcp add` line.

- [ ] **Step 1: Write the failing tests**

```python
# tests/farmhand/test_auth_unit.py
"""Token file lifecycle and bearer middleware (no server needed)."""

import asyncio

import pytest

from haywire_studio.farmhand.auth import BearerTokenMiddleware, connection_command, ensure_token

pytestmark = pytest.mark.unit


def test_token_created_stable_and_gitignored(tmp_path):
    token = ensure_token(tmp_path)
    assert len(token) >= 32
    token_file = tmp_path / ".haywire" / "farmhand_token"
    assert token_file.exists()
    assert ensure_token(tmp_path) == token  # stable across calls
    gitignore = (tmp_path / ".haywire" / ".gitignore").read_text()
    assert "farmhand_token" in gitignore


def test_token_rotates_when_file_deleted(tmp_path):
    first = ensure_token(tmp_path)
    (tmp_path / ".haywire" / "farmhand_token").unlink()
    assert ensure_token(tmp_path) != first


def test_connection_command_contains_endpoint_and_header():
    line = connection_command(8082, "sekrit")
    assert "claude mcp add --transport http farmhand http://127.0.0.1:8082/mcp" in line
    assert 'Authorization: Bearer sekrit' in line


def _run_middleware(headers: list[tuple[bytes, bytes]]) -> int:
    """Drive the ASGI middleware with a fake downstream app; return the status sent."""
    sent: dict = {}

    async def downstream(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    async def send(message):
        if message["type"] == "http.response.start":
            sent["status"] = message["status"]

    async def receive():
        return {"type": "http.request"}

    middleware = BearerTokenMiddleware(downstream, token="sekrit")
    scope = {"type": "http", "headers": headers, "path": "/mcp"}
    asyncio.run(middleware(scope, receive, send))
    return sent["status"]


def test_missing_token_is_401():
    assert _run_middleware([]) == 401


def test_wrong_token_is_401():
    assert _run_middleware([(b"authorization", b"Bearer wrong")]) == 401


def test_correct_token_passes_through():
    assert _run_middleware([(b"authorization", b"Bearer sekrit")]) == 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/farmhand/test_auth_unit.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'haywire_studio.farmhand'`

- [ ] **Step 3: Implement settings**

```python
# packages/haywire-studio/src/haywire_studio/farmhand/settings.py
"""Farmhand framework settings (read once at studio startup; restart to apply)."""

from haywire.barn.builtin.types import BOOL
from haywire.core.settings import setting
from haywire.core.settings.settings_framework import FrameworkSettings


class FarmhandSettings(FrameworkSettings, namespace="farmhand"):
    """The Farmhand MCP server's framework-level switches."""

    enabled = setting[BOOL](
        True,
        label="Enable Farmhand MCP server",
        description=(
            "Serve the MCP endpoint at /mcp on the studio port so AI-agent clients "
            "can operate this studio. Read once at startup; restart to apply."
        ),
        category="farmhand",
    )
```

(Confirm the `setting` import path used by `CanvasSettings`: `from haywire.core.settings import setting` — copy whatever that file does.)

- [ ] **Step 4: Implement token + middleware**

```python
# packages/haywire-studio/src/haywire_studio/farmhand/auth.py
"""Static bearer-token auth for the Farmhand mount.

Token lives gitignored at <workspace>/.haywire/farmhand_token; delete the
file to rotate. Layered with 127.0.0.1 binding and the SDK's
TransportSecuritySettings (host task) per spec §4.
"""

from __future__ import annotations

import json
import secrets
from pathlib import Path

TOKEN_FILENAME = "farmhand_token"


def ensure_token(workspace_root: Path) -> str:
    haywire_dir = Path(workspace_root) / ".haywire"
    haywire_dir.mkdir(parents=True, exist_ok=True)

    gitignore = haywire_dir / ".gitignore"
    if not gitignore.exists() or TOKEN_FILENAME not in gitignore.read_text(encoding="utf-8"):
        with gitignore.open("a", encoding="utf-8") as fh:
            fh.write(f"{TOKEN_FILENAME}\n")

    token_file = haywire_dir / TOKEN_FILENAME
    if token_file.exists():
        return token_file.read_text(encoding="utf-8").strip()
    token = secrets.token_urlsafe(32)
    token_file.write_text(token, encoding="utf-8")
    token_file.chmod(0o600)
    return token


def connection_command(port: int, token: str) -> str:
    return (
        f"claude mcp add --transport http farmhand http://127.0.0.1:{port}/mcp "
        f'--header "Authorization: Bearer {token}"'
    )


class BearerTokenMiddleware:
    """Pure-ASGI bearer check wrapping the Farmhand mount only."""

    def __init__(self, app, token: str):
        self.app = app
        self.token = token

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        auth = ""
        for key, value in scope.get("headers", []):
            if key == b"authorization":
                auth = value.decode("latin-1")
                break
        if auth != f"Bearer {self.token}":
            body = json.dumps({"error": "unauthorized"}).encode()
            await send(
                {
                    "type": "http.response.start",
                    "status": 401,
                    "headers": [(b"content-type", b"application/json")],
                }
            )
            await send({"type": "http.response.body", "body": body})
            return
        await self.app(scope, receive, send)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/farmhand/test_auth_unit.py -v`
Expected: all PASS.

- [ ] **Step 6: Lint, type-check, commit**

```bash
uv run ruff check packages/haywire-studio/src/haywire_studio/farmhand/ tests/farmhand/
uv run ruff format packages/haywire-studio/src/haywire_studio/farmhand/ tests/farmhand/
uv run mypy packages/haywire-studio/src/
git add packages/haywire-studio/src/haywire_studio/farmhand/ tests/farmhand/
git commit -m "feat(farmhand): studio settings flag, workspace bearer token (gitignored), ASGI auth middleware"
```

---

### Task 8: Farmhand host — low-level MCP server, mount, lifespan, session registry, change pipeline

**Files:**
- Create: `packages/haywire-core/src/haywire/core/farmhand/errors.py` (SDK-free tool-error type)
- Create: `packages/haywire-studio/src/haywire_studio/farmhand/host.py`
- Modify: `packages/haywire-core/src/haywire/core/farmhand/__init__.py` (export `FarmhandError`)
- Modify: `packages/haywire-studio/pyproject.toml` (add `"mcp>=1.28,<2"` to dependencies)
- Modify: `packages/haywire-studio/src/haywire_studio/app.py` (wire `setup_farmhand(port)` into `main()` before `ui.run`)
- Test: `tests/farmhand/test_host_unit.py`

**Interfaces:**
- Consumes: `FarmhandRegistry` (`.list_names()`, `.get(key)`, `.add_batch_event_subscriber(cb)`); `LifeCycleEvent`/`LifeCycleEventType` (`haywire/core/registry/lifecycle_event.py`); `Farmhand.mcp_name()/input_schema()/class_identity.annotations`; `FarmhandContext`; Task 7's `FarmhandSettings`, `ensure_token`, `BearerTokenMiddleware`, `connection_command`; the runner-task lifespan pattern (`.scratch/mcp-server/prototype/farmhand_mount_prototype.py:83-110`); SDK: `mcp.server.lowlevel.Server`, `mcp.server.lowlevel.NotificationOptions`, `mcp.server.streamable_http_manager.StreamableHTTPSessionManager`, `mcp.server.transport_security.TransportSecuritySettings`, `mcp.types`.
- Produces:
  - `FarmhandError(Exception)` in core: `FarmhandError(code: str, message: str, ids: dict[str, str] | None = None)` — the stable-code error every tool raises for expected failures.
  - `FarmhandHost(library_service, workspace_root)` with `.mount(port: int) -> None` (token, security settings, ASGI mount at `/mcp`, `app.on_startup`/`on_shutdown` hooks, prints the `claude mcp add` line), `._notify_list_changed()`, `._tools: dict[str, type[Farmhand]]`. The host holds NO baseline list — all tools (including `studio_*` from haybale-studio, Task 9) arrive via the registry: `_seed_tools()` at construction (libraries enabled before the host exists) plus lifecycle events afterwards.
  - `HaywireApp.setup_farmhand(port: int) -> None` — no-op when `FarmhandSettings().enabled` is False (flag read once here).
  - Resource serving hooks land in Task 14; this task wires tools only (list_tools/call_tool) but the notifier already sends both tool and resource list_changed.

- [ ] **Step 1: Verify SDK API shapes against the installed package (mcp 1.28.1 is already in the venv)**

```bash
uv run python - <<'EOF'
import inspect
from mcp.server.lowlevel import Server, NotificationOptions
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.server.transport_security import TransportSecuritySettings
import mcp.types as types
print(inspect.signature(StreamableHTTPSessionManager.__init__))
print(inspect.signature(Server.create_initialization_options))
print([f for f in types.Tool.model_fields])
print([f for f in types.ToolAnnotations.model_fields])
from mcp.server.session import ServerSession
print([m for m in dir(ServerSession) if "list_changed" in m or "log_message" in m])
EOF
```

Expected: `StreamableHTTPSessionManager.__init__` accepts `app`, `event_store`, `json_response`, `stateless`, `security_settings`; `types.Tool` has `name`, `description`, `inputSchema`, `annotations`; `ServerSession` has `send_tool_list_changed`, `send_resource_list_changed`, `send_prompt_list_changed`, `send_log_message`. If `security_settings` is NOT a manager parameter, wrap the ASGI adapter with `mcp.server.transport_security.TransportSecurityMiddleware(app, settings)` instead — same effect, and note which variant you used in the commit message. Also run `grep -n "class LifeCycleEvent" -A 15 packages/haywire-core/src/haywire/core/registry/lifecycle_event.py` and confirm the event's attribute names (`event_type`, `registry_key`) used below.

- [ ] **Step 2: Write the failing unit tests**

```python
# tests/farmhand/test_host_unit.py
"""Host mechanics that need no transport: capability advertisement, tool table, error format."""

import pytest

from haywire.core.farmhand import Farmhand, FarmhandError
from haywire_studio.farmhand.host import FarmhandHost, _FarmhandServer, _format_tool_error

pytestmark = pytest.mark.unit


def test_initialization_options_advertise_list_changed():
    server = _FarmhandServer("farmhand")
    options = server.create_initialization_options()
    caps = options.capabilities
    assert caps.tools.listChanged is True
    assert caps.resources.listChanged is True
    assert caps.prompts.listChanged is True


def test_format_tool_error_stable_code_no_traceback():
    err = FarmhandError("graph_not_found", "No open graph 'x'", ids={"binding_id": "x"})
    text = _format_tool_error(err)
    assert "[graph_not_found]" in text
    assert "No open graph 'x'" in text
    assert "binding_id=x" in text
    assert "Traceback" not in text


def test_format_tool_error_wraps_unexpected_exceptions():
    text = _format_tool_error(ValueError("boom"))
    assert "[internal]" in text
    assert "boom" in text
    assert "Traceback" not in text


def test_tool_table_seed_and_evict():
    from haywire.core.farmhand import FarmhandRegistry, ToolAnnotations
    from haywire.core.farmhand.identity import FarmhandIdentity
    from haywire.core.library.identity import LibraryIdentity

    registry = FarmhandRegistry()

    class PingTool(Farmhand):
        async def run(self, ctx) -> dict:
            return {}

    PingTool.class_identity = FarmhandIdentity(
        registry_id="ping",
        registry_key="studio:farmhand:ping",
        label="Ping",
        description="",
        class_name="PingTool",
        module=__name__,
        annotations=ToolAnnotations(),
    )
    PingTool.class_library = LibraryIdentity(label="Studio", id="studio")
    registry._register_class(PingTool, PingTool.class_library)

    host = FarmhandHost.__new__(FarmhandHost)  # table mechanics only, no service needed
    host._tools = {}
    host._registry = registry
    host._seed_tools()
    assert host._tools == {"studio_ping": PingTool}

    host._remove_tool_by_key("studio:farmhand:ping")
    assert host._tools == {}
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/farmhand/test_host_unit.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'haywire_studio.farmhand.host'`

- [ ] **Step 4: Add the core error type**

```python
# packages/haywire-core/src/haywire/core/farmhand/errors.py
"""SDK-free tool error contract: stable code + actionable message + offending ids."""

from __future__ import annotations

from typing import Optional


class FarmhandError(Exception):
    """Expected tool failure. The host renders it as an MCP tool error;
    clients see '[code] message (id=..., ...)' — never a stack trace."""

    def __init__(self, code: str, message: str, ids: Optional[dict[str, str]] = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.ids = ids or {}
```

Export `FarmhandError` from `haywire/core/farmhand/__init__.py`.

- [ ] **Step 5: Add the SDK dependency**

In `packages/haywire-studio/pyproject.toml`, add `"mcp>=1.28,<2",` to the `dependencies` list, then run `uv sync` and confirm it resolves (1.28.1 is already installed from the prototype).

- [ ] **Step 6: Implement the host**

```python
# packages/haywire-studio/src/haywire_studio/farmhand/host.py
"""Farmhand host: low-level MCP server mounted at /mcp on the studio app.

Design anchors (spec §2, §3; SDK facts in .scratch/mcp-server/assets/mcp-sdk-research.md):
- ONE StreamableHTTPSessionManager per process; run() entered exactly once by a
  single long-lived runner task (AsyncExitStack-across-handlers crashes NiceGUI
  shutdown — .insights/feedback_nicegui_lifespan_task_scope.md).
- The SDK advertises listChanged:false by default; _FarmhandServer overrides
  create_initialization_options so the manager's no-arg call gets
  NotificationOptions(tools_changed=True, prompts_changed=True, resources_changed=True).
- No stack auto-notifies on the hot-reload path: we track live ServerSessions in
  a WeakSet (captured per request) and send list_changed ourselves.
- One change pipeline: FarmhandRegistry CLASS_ADDED/CLASS_REMOVED batch events
  drive add/remove + notify; baseline tools register through the same registry.
"""

from __future__ import annotations

import asyncio
import json
import logging
import weakref
from typing import Any, Optional

import mcp.types as types
from mcp.server.lowlevel import NotificationOptions, Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.server.transport_security import TransportSecuritySettings
from nicegui import app as nicegui_app

from haywire.core.farmhand import FarmhandContext, Farmhand, FarmhandError, FarmhandRegistry
from haywire.core.registry.lifecycle_event import LifeCycleEvent, LifeCycleEventType

from .auth import BearerTokenMiddleware, connection_command, ensure_token

logger = logging.getLogger(__name__)

PROTOCOL_VERSION = "2025-11-25"


class _FarmhandServer(Server):
    """Low-level Server that always advertises listChanged capabilities.

    StreamableHTTPSessionManager calls create_initialization_options() with no
    arguments, which would advertise listChanged:false (SDK default quirk).
    """

    def create_initialization_options(self, notification_options=None, experimental_capabilities=None):
        return super().create_initialization_options(
            notification_options=notification_options
            or NotificationOptions(tools_changed=True, prompts_changed=True, resources_changed=True),
            experimental_capabilities=experimental_capabilities,
        )


def _format_tool_error(exc: Exception) -> str:
    if isinstance(exc, FarmhandError):
        ids = ", ".join(f"{k}={v}" for k, v in exc.ids.items())
        suffix = f" ({ids})" if ids else ""
        return f"[{exc.code}] {exc.message}{suffix}"
    # HaywireException maps directly (spec §5 conventions): category is the stable code.
    category = getattr(exc, "category", None)
    message = getattr(exc, "message", None)
    if category and message:
        key = getattr(exc, "registry_key", None)
        suffix = f" (registry_key={key})" if key else ""
        return f"[haywire:{category}] {message}{suffix}"
    return f"[internal] {type(exc).__name__}: {exc}"


class FarmhandHost:
    def __init__(self, library_service: Any, workspace_root: str):
        self._library_service = library_service
        self._workspace_root = workspace_root
        self._registry: FarmhandRegistry = library_service.injector.get(FarmhandRegistry)
        self._tools: dict[str, type[Farmhand]] = {}
        self._sessions: "weakref.WeakSet" = weakref.WeakSet()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._server = _FarmhandServer("farmhand")
        self._session_manager: Optional[StreamableHTTPSessionManager] = None
        self._started: Optional[asyncio.Event] = None
        self._stop: Optional[asyncio.Event] = None
        self._runner: Optional[asyncio.Task] = None

        # Libraries (including haybale-studio's studio_* baseline) enabled
        # before the host exists — seed from the registry, then follow events.
        self._seed_tools()
        self._registry.add_batch_event_subscriber(self._on_lifecycle_batch)
        self._register_handlers()

    # -- tool table -----------------------------------------------------

    def _seed_tools(self) -> None:
        for key in self._registry.list_names():
            cls = self._registry.get(key)
            if cls is not None:
                self._tools[cls.mcp_name()] = cls

    def _remove_tool_by_key(self, registry_key: str) -> None:
        lib_id, _, name = registry_key.split(":")
        self._tools.pop(f"{lib_id}_{name}", None)

    def _on_lifecycle_batch(self, events: list[LifeCycleEvent]) -> None:
        relevant = [
            e
            for e in events
            if e.event_type in (LifeCycleEventType.CLASS_ADDED, LifeCycleEventType.CLASS_REMOVED)
        ]
        if not relevant:
            return
        if self._loop is None or not self._loop.is_running():
            self._apply_events(relevant)  # startup enable path: no live sessions yet
            return
        # Hot-reload/enable/disable events arrive on watchdog/timer threads —
        # marshal onto the NiceGUI loop (ADR 0002 discipline).
        self._loop.call_soon_threadsafe(
            lambda: asyncio.ensure_future(self._apply_and_notify(relevant))
        )

    def _apply_events(self, events: list[LifeCycleEvent]) -> None:
        for event in events:
            if event.event_type == LifeCycleEventType.CLASS_ADDED:
                cls = self._registry.get(event.registry_key)
                if cls is not None:
                    self._tools[cls.mcp_name()] = cls
            else:
                self._remove_tool_by_key(event.registry_key)

    async def _apply_and_notify(self, events: list[LifeCycleEvent]) -> None:
        self._apply_events(events)
        await self._notify_list_changed()

    async def _notify_list_changed(self) -> None:
        for session in list(self._sessions):
            try:
                await session.send_tool_list_changed()
                await session.send_resource_list_changed()
            except Exception as exc:  # dead session — WeakSet will drop it
                logger.debug(f"Farmhand: list_changed notification failed: {exc}")

    # -- MCP handlers ---------------------------------------------------

    def _register_handlers(self) -> None:
        @self._server.list_tools()
        async def list_tools() -> list[types.Tool]:
            self._track_session()
            return [
                types.Tool(
                    name=name,
                    description=cls.class_identity.description or cls.class_identity.label,
                    inputSchema=cls.input_schema(),
                    annotations=types.ToolAnnotations(**cls.class_identity.annotations.to_dict()),
                )
                for name, cls in sorted(self._tools.items())
            ]

        @self._server.call_tool()
        async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
            self._track_session()
            cls = self._tools.get(name)
            if cls is None:
                raise Exception(_format_tool_error(FarmhandError("unknown_tool", f"No tool named '{name}'", ids={"tool": name})))
            session = self._server.request_context.session

            async def reporter(message: str) -> None:
                try:
                    await session.send_log_message(level="info", data=message)
                except Exception:
                    pass

            ctx = FarmhandContext(progress_reporter=reporter)
            try:
                result = await cls().run(ctx, **arguments)
            except (FarmhandError, Exception) as exc:
                raise Exception(_format_tool_error(exc)) from None
            if isinstance(result, dict) and "summary" not in result:
                result = {"summary": f"{name}: ok", **result}
            return [types.TextContent(type="text", text=json.dumps(result, default=str))]

    def _track_session(self) -> None:
        try:
            self._sessions.add(self._server.request_context.session)
        except Exception:
            pass

    # -- mount + lifespan ----------------------------------------------

    def mount(self, port: int) -> None:
        token = ensure_token(__import__("pathlib").Path(self._workspace_root))
        security = TransportSecuritySettings(
            allowed_hosts=[f"127.0.0.1:{port}", f"localhost:{port}", "127.0.0.1", "localhost"],
            allowed_origins=[f"http://127.0.0.1:{port}", f"http://localhost:{port}"],
        )
        self._session_manager = StreamableHTTPSessionManager(
            app=self._server, security_settings=security
        )

        async def asgi(scope, receive, send):
            assert self._session_manager is not None
            await self._session_manager.handle_request(scope, receive, send)

        nicegui_app.mount("/mcp", BearerTokenMiddleware(asgi, token))
        nicegui_app.on_startup(self._on_startup)
        nicegui_app.on_shutdown(self._on_shutdown)

        hint = connection_command(port, token)
        logger.info(f"Farmhand MCP server will serve at /mcp — connect with:\n  {hint}")
        print(f"🤝 Farmhand: {hint}")

    async def _runner_main(self) -> None:
        assert self._session_manager is not None and self._started is not None and self._stop is not None
        async with self._session_manager.run():
            self._started.set()
            await self._stop.wait()

    async def _on_startup(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._started, self._stop = asyncio.Event(), asyncio.Event()
        self._runner = asyncio.create_task(self._runner_main())
        await self._started.wait()
        logger.info("Farmhand: MCP session manager running (single runner task)")

    async def _on_shutdown(self) -> None:
        if self._stop is not None:
            self._stop.set()
        if self._runner is not None:
            await self._runner
```

Cleanups while implementing (keep the shape, fix the smells): move the `pathlib` import to the top of the file (`from pathlib import Path`; `ensure_token(Path(self._workspace_root))`); split the over-long `call_tool` unknown-tool line to fit 109 cols; the broad `except (FarmhandError, Exception)` is intentionally just `except Exception` — write it that way.

- [ ] **Step 7: Wire into the app**

In `packages/haywire-studio/src/haywire_studio/app.py`:

1. Add a method to `HaywireApp` (after `setup_shared_services`):

```python
    def setup_farmhand(self, port: int) -> None:
        """Mount the Farmhand MCP server if enabled (flag read once; restart to apply)."""
        from haywire_studio.farmhand.host import FarmhandHost
        from haywire_studio.farmhand.settings import FarmhandSettings

        if not FarmhandSettings().enabled:
            logger.info("Farmhand: disabled by settings (farmhand.enabled = false)")
            return
        self.farmhand_host = FarmhandHost(self.library_service, self.workspace_root)
        self.farmhand_host.mount(port)
```

2. In `main()` (app.py:266-355), locate where the port is resolved and `ui.run(port=...)` is called; insert `app_instance.setup_farmhand(port)` after the `HaywireApp` instance is constructed and before `ui.run`.

3. **Ordering note:** the `studio_*` baseline arrives via haybale-studio's `farmhands/` folder in Task 9 — nothing to pre-create here. A studio built at this task simply serves an empty tool list (valid: the host is tool-source-agnostic).

- [ ] **Step 8: Run tests to verify they pass**

Run: `uv run pytest tests/farmhand/test_host_unit.py -v`
Expected: all PASS.

Manual smoke (optional but cheap): `uv run haywire` in a scratch workspace, confirm the `🤝 Farmhand:` line prints and the app still boots/shuts down cleanly (Ctrl-C, no cancel-scope traceback).

- [ ] **Step 9: Lint, type-check, full fast suite, commit**

```bash
uv run ruff check packages/haywire-studio/src/haywire_studio/farmhand/ packages/haywire-core/src/haywire/core/farmhand/ tests/farmhand/
uv run ruff format packages/haywire-studio/src/haywire_studio/farmhand/ packages/haywire-core/src/haywire/core/farmhand/ tests/farmhand/
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/
uv run pytest -m "not browser and not perf" -q
git add -A packages/haywire-core packages/haywire-studio tests/farmhand/ uv.lock
git commit -m "feat(farmhand): studio host — low-level MCP server at /mcp, runner-task lifespan, session registry, registry-driven change pipeline"
```

---

### Task 9: The nine `studio_*` baseline tools (in barn/haybale-studio)

**Files:**
- Create: `barn/haybale-studio/haybale_studio/farmhands/__init__.py` (empty)
- Create: `barn/haybale-studio/haybale_studio/farmhands/_helpers.py`
- Create: `barn/haybale-studio/haybale_studio/farmhands/status.py`
- Create: `barn/haybale-studio/haybale_studio/farmhands/catalog.py` (list_libraries, list_components, describe_component)
- Create: `barn/haybale-studio/haybale_studio/farmhands/authoring.py` (scaffold, read_source, write_source, verify)
- Create: `barn/haybale-studio/haybale_studio/farmhands/errors.py` (get_errors)
- Modify: `barn/haybale-studio/haybale_studio/__init__.py` (register `farmhands/` folder AFTER its `state/` registration; import `FarmhandRegistry`)
- Modify: `packages/haywire-studio/pyproject.toml` (declare `haybale-studio` as a required dependency — decided; makes "baseline exists on every studio" packaging-enforced)
- Test: `tests/farmhand/test_baseline_tools.py`

**Interfaces:**
- Consumes: `Farmhand`/`farmhand`/`ToolAnnotations`/`FarmhandError`/`FarmhandContext`; `LibraryRegistry` (`list_names()`, `get_library_identity(id)`, `is_library_enabled(id)`, `get_library_install_type(id)`, `get_library_source(id)`), `InstallType` (`haywire/core/library/install_type.py:8`); the ten component registries (each has `list_names()`, `get(key)`); `NodeFactory.get_node_info(key)`; `get_error_ledger()`; `canons_dir`/`read_canon` (Task 3); `BaseNode.on_testrun() -> tuple[bool, str | None]` (`node/base.py:96`); `BaseGraph` + `SyncScheduler` for trial instantiation.
- Produces: nine folder-scanned tool classes with registry keys `studio:farmhand:{status,list_libraries,list_components,describe_component,scaffold_component,read_component_source,write_component_source,verify_component,get_errors}` — haybale-studio's library id is `studio`, so the plain `@farmhand` decorator yields these keys and the spec's `studio_*` MCP names with no special path. No `BASELINE_TOOLS` list exists anywhere; the host discovers these via `_seed_tools()` / lifecycle events like every other library's tools.

- [ ] **Step 1: Write the failing tests**

Tools are host-independent — test them directly against a `FarmhandContext` under `library_system` (integration tier, no server). Prerequisite check: confirm `library_system`'s `test_library_path` (tests/conftest.py) loads barn/haybale-studio; if it points elsewhere, extend the fixture request with the barn path the same way `farmhand_server` does in Task 10.

```python
# tests/farmhand/test_baseline_tools.py
"""Baseline studio_* tools, driven directly (no MCP transport)."""

import asyncio

import pytest

from haywire.core.farmhand import FarmhandContext, FarmhandError

pytestmark = pytest.mark.integration


def run_tool(tool_cls, **kwargs):
    return asyncio.run(tool_cls().run(FarmhandContext(), **kwargs))


@pytest.fixture(autouse=True)
def _ambient(library_system):
    """All baseline tools resolve services from the ambient DI context."""
    yield


def test_status_reports_basics():
    from haybale_studio.farmhands.status import StudioStatusTool

    result = run_tool(StudioStatusTool)
    assert "workspace_root" in result
    assert result["enabled_libraries"] >= 1
    assert result["protocol_version"] == "2025-11-25"


def test_list_libraries_paginates():
    from haybale_studio.farmhands.catalog import StudioListLibrariesTool

    result = run_tool(StudioListLibrariesTool, limit=1, offset=0)
    assert result["total"] >= 1
    assert len(result["libraries"]) == 1
    row = result["libraries"][0]
    assert {"id", "label", "version", "enabled"} <= set(row)


def test_list_components_filters_by_library_and_kind():
    from haybale_studio.farmhands.catalog import StudioListComponentsTool

    result = run_tool(StudioListComponentsTool, library="testing", kind="node")
    assert result["total"] >= 1
    assert all(k.startswith("testing:node:") for k in [c["registry_key"] for c in result["components"]])


def test_describe_component_returns_identity_and_doc():
    from haybale_studio.farmhands.catalog import (
        StudioDescribeComponentTool,
        StudioListComponentsTool,
    )

    listing = run_tool(StudioListComponentsTool, library="testing", kind="node", limit=1)
    key = listing["components"][0]["registry_key"]
    result = run_tool(StudioDescribeComponentTool, registry_key=key)
    assert result["registry_key"] == key
    assert "label" in result


def test_describe_unknown_component_is_stable_error():
    from haybale_studio.farmhands.catalog import StudioDescribeComponentTool

    with pytest.raises(FarmhandError) as exc_info:
        run_tool(StudioDescribeComponentTool, registry_key="nope:node:missing")
    assert exc_info.value.code == "component_not_found"


def test_read_component_source_is_line_numbered():
    from haybale_studio.farmhands.catalog import StudioListComponentsTool
    from haybale_studio.farmhands.authoring import StudioReadComponentSourceTool

    listing = run_tool(StudioListComponentsTool, library="testing", kind="node", limit=1)
    key = listing["components"][0]["registry_key"]
    result = run_tool(StudioReadComponentSourceTool, registry_key=key)
    assert result["source"].splitlines()[0].startswith("1\t")
    assert result["path"].endswith(".py")


def test_write_component_source_rejects_non_project_library():
    from haybale_studio.farmhands.authoring import StudioWriteComponentSourceTool

    with pytest.raises(FarmhandError) as exc_info:
        run_tool(
            StudioWriteComponentSourceTool,
            library="testing",  # barn test library is not a project-local library target
            kind="node",
            filename="hacked.py",
            source="print('no')",
        )
    assert exc_info.value.code in ("not_project_library", "no_project_library")


def test_scaffold_requires_a_project_library():
    from haybale_studio.farmhands.authoring import StudioScaffoldComponentTool

    with pytest.raises(FarmhandError) as exc_info:
        run_tool(StudioScaffoldComponentTool, kind="node", name="my_node")
    assert exc_info.value.code == "no_project_library"  # test workspace has none -> haywire init hint
    assert "haywire init" in exc_info.value.message


def test_verify_component_ok_for_registered_node():
    from haybale_studio.farmhands.catalog import StudioListComponentsTool
    from haybale_studio.farmhands.authoring import StudioVerifyComponentTool

    listing = run_tool(StudioListComponentsTool, library="testing", kind="node", limit=1)
    key = listing["components"][0]["registry_key"]
    result = run_tool(StudioVerifyComponentTool, registry_key=key)
    assert result["registered"] is True
    assert result["stage_reached"] in ("registered", "instantiated", "testrun")


def test_get_errors_returns_ledger_page():
    from haywire.core.errors.haywire_exception import HaywireException
    from haybale_studio.farmhands.errors import StudioGetErrorsTool

    HaywireException.create("baseline tool test error").log()
    result = run_tool(StudioGetErrorsTool)
    assert result["total"] >= 1
    assert "cursor" in result


def test_registry_holds_exactly_nine_studio_tools(library_system):
    from haywire.core.farmhand import FarmhandRegistry

    registry = library_system.injector.get(FarmhandRegistry)
    studio_keys = {k for k in registry.list_names() if k.startswith("studio:farmhand:")}
    assert studio_keys == {
        "studio:farmhand:status",
        "studio:farmhand:list_libraries",
        "studio:farmhand:list_components",
        "studio:farmhand:describe_component",
        "studio:farmhand:scaffold_component",
        "studio:farmhand:read_component_source",
        "studio:farmhand:write_component_source",
        "studio:farmhand:verify_component",
        "studio:farmhand:get_errors",
    }
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/farmhand/test_baseline_tools.py -v`
Expected: FAIL with `ModuleNotFoundError` on the tool modules.

- [ ] **Step 3: Implement helpers**

```python
# barn/haybale-studio/haybale_studio/farmhands/_helpers.py
"""Shared helpers for baseline tools: pagination, kind maps, target-library resolution."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from haywire.core.farmhand import FarmhandContext, FarmhandError
from haywire.core.library.install_type import InstallType
from haywire.core.library.registry import LibraryRegistry


def page(items: list, limit: int, offset: int) -> tuple[list, int]:
    return items[offset : offset + limit], len(items)


def kind_registry_map() -> dict[str, type]:
    """Registry-key kind segment -> registry class (the ten registries + farmhand)."""
    from haywire.core.adapter.registry import AdapterRegistry
    from haywire.core.farmhand import FarmhandRegistry
    from haywire.core.node.registry import NodeRegistry
    from haywire.core.settings.registry import SettingsRegistry
    from haywire.core.state import LibraryStateRegistry
    from haywire.core.types.registry import TypeRegistry
    from haywire.ui.editor.registry import EditorTypeRegistry
    from haywire.ui.panel.registry import PanelRegistry
    from haywire.ui.skin.registry import SkinRegistry
    from haywire.ui.themes.registry import ThemeRegistry
    from haywire.ui.widget.registry import WidgetRegistry

    return {
        "node": NodeRegistry,
        "type": TypeRegistry,
        "adapter": AdapterRegistry,
        "widget": WidgetRegistry,
        "skin": SkinRegistry,
        "setting": SettingsRegistry,
        "theme": ThemeRegistry,
        "panel": PanelRegistry,
        "editor": EditorTypeRegistry,
        "state": LibraryStateRegistry,
        "farmhand": FarmhandRegistry,
    }


KIND_FOLDERS = {
    "node": "nodes",
    "type": "types",
    "adapter": "adapters",
    "widget": "widgets",
    "skin": "skins",
    "setting": "settings",
    "theme": "themes",
    "panel": "panels",
    "editor": "editors",
    "state": "state",
    "farmhand": "farmhands",
}


def resolve_component_class(ctx: FarmhandContext, registry_key: str) -> Any:
    parts = registry_key.split(":")
    if len(parts) != 3 or parts[1] not in kind_registry_map():
        raise FarmhandError(
            "bad_registry_key",
            f"Registry keys look like '{{lib_id}}:{{kind}}:{{name}}' with kind one of "
            f"{sorted(kind_registry_map())}; got '{registry_key}'.",
            ids={"registry_key": registry_key},
        )
    registry = ctx.registry(kind_registry_map()[parts[1]])
    cls = registry.get(registry_key)
    if cls is None:
        raise FarmhandError(
            "component_not_found",
            f"No component registered under '{registry_key}'.",
            ids={"registry_key": registry_key},
        )
    return cls


def project_local_libraries(ctx: FarmhandContext) -> list[str]:
    """Libraries installed from a folder inside this workspace (haywire init layout)."""
    registry = ctx.registry(LibraryRegistry)
    workspace = str(ctx.workspace_root())
    result = []
    for lib_id in registry.list_names():
        install_type = registry.get_library_install_type(lib_id)
        source = registry.get_library_source(lib_id) or ""
        if install_type == InstallType.FOLDER and source.startswith(workspace):
            result.append(lib_id)
    return sorted(result)


def resolve_target_library(ctx: FarmhandContext, library: str | None) -> str:
    locals_ = project_local_libraries(ctx)
    if library is not None:
        if library not in locals_:
            raise FarmhandError(
                "not_project_library",
                f"'{library}' is not a project-local library (project-local: {locals_ or 'none'}). "
                f"Farmhand writes source only into project-local libraries.",
                ids={"library": library},
            )
        return library
    if not locals_:
        raise FarmhandError(
            "no_project_library",
            "No project-local library exists in this workspace — create one with 'haywire init'.",
        )
    if len(locals_) > 1:
        raise FarmhandError(
            "ambiguous_project_library",
            f"Several project-local libraries exist; pass library= explicitly: {locals_}.",
        )
    return locals_[0]


def library_folder(ctx: FarmhandContext, lib_id: str) -> Path:
    registry = ctx.registry(LibraryRegistry)
    identity = registry.get_library_identity(lib_id)
    return Path(identity.folder_path)
```

Verify `LibraryRegistry.get_library_identity(lib_id)` exists (it is called in `di/config.py:524`); confirm the `EditorTypeRegistry`/`PanelRegistry` import paths by grepping their imports in `di/config.py`'s header and copying them verbatim.

- [ ] **Step 4: Implement status + catalog tools**

```python
# barn/haybale-studio/haybale_studio/farmhands/status.py
"""studio_status — orientation floor for a connecting agent."""

from __future__ import annotations

from importlib.metadata import version as pkg_version

from haywire.core.farmhand import FarmhandContext, Farmhand, ToolAnnotations, farmhand
from haywire.core.library.registry import LibraryRegistry


def _version(dist: str) -> str:
    try:
        return pkg_version(dist)
    except Exception:
        return "unknown"


@farmhand(
    label="Studio status",
    description="Versions, workspace root, enabled-library and open-graph counts, docs URL.",
    registry_id="status",
    annotations=ToolAnnotations(read_only_hint=True),
)
class StudioStatusTool(Farmhand):
    async def run(self, ctx: FarmhandContext) -> dict:
        registry = ctx.registry(LibraryRegistry)
        enabled = [lib for lib in registry.list_names() if registry.is_library_enabled(lib)]
        open_graphs = 0
        try:  # haystack is a library, absent on a bare studio
            from haybale_haystack.state.haystack_state import HaystackState

            open_graphs = len(ctx.state(HaystackState).all_entries())
        except Exception:
            pass
        return {
            "summary": f"Haywire studio at {ctx.workspace_root()}: "
            f"{len(enabled)} libraries enabled, {open_graphs} graphs open.",
            "haywire_core_version": _version("haywire-core"),
            "haywire_studio_version": _version("haywire-studio"),
            "protocol_version": "2025-11-25",
            "workspace_root": str(ctx.workspace_root()),
            "enabled_libraries": len(enabled),
            "open_graphs": open_graphs,
            "docs_url": "https://github.com/going-haywire/haywire",
        }
```

```python
# barn/haybale-studio/haybale_studio/farmhands/catalog.py
"""studio_list_libraries / studio_list_components / studio_describe_component."""

from __future__ import annotations

import inspect

from haywire.core.farmhand import FarmhandContext, Farmhand, ToolAnnotations, farmhand
from haywire.core.library.registry import LibraryRegistry

from ._helpers import kind_registry_map, page, resolve_component_class

_READ_ONLY = ToolAnnotations(read_only_hint=True)


@farmhand(
    label="List libraries",
    description="Installed libraries: id, label, version, description, tags, enabled.",
    registry_id="list_libraries",
    annotations=_READ_ONLY,
)
class StudioListLibrariesTool(Farmhand):
    async def run(self, ctx: FarmhandContext, limit: int = 50, offset: int = 0) -> dict:
        registry = ctx.registry(LibraryRegistry)
        rows = []
        for lib_id in sorted(registry.list_names()):
            identity = registry.get_library_identity(lib_id)
            rows.append(
                {
                    "id": lib_id,
                    "label": identity.label,
                    "version": identity.version,
                    "description": identity.description,
                    "tags": list(identity.tags or []),
                    "enabled": registry.is_library_enabled(lib_id),
                }
            )
        rows, total = page(rows, limit, offset)
        return {"summary": f"{total} libraries installed.", "libraries": rows, "total": total}


@farmhand(
    label="List components",
    description="Component catalog, filterable by library and/or kind (registry prefix-scan).",
    registry_id="list_components",
    annotations=_READ_ONLY,
)
class StudioListComponentsTool(Farmhand):
    async def run(
        self,
        ctx: FarmhandContext,
        library: str | None = None,
        kind: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict:
        kinds = kind_registry_map()
        selected = {kind: kinds[kind]} if kind in kinds else kinds
        rows = []
        for seg, registry_cls in selected.items():
            registry = ctx.registry(registry_cls)
            for key in registry.list_names():
                parts = key.split(":")
                if len(parts) != 3 or parts[1] != seg:
                    continue  # e.g. library-level keys in mixed registries
                if library is not None and parts[0] != library:
                    continue
                rows.append({"registry_key": key, "library": parts[0], "kind": seg, "name": parts[2]})
        rows.sort(key=lambda r: r["registry_key"])
        rows, total = page(rows, limit, offset)
        return {"summary": f"{total} components match.", "components": rows, "total": total}


@farmhand(
    label="Describe component",
    description="One component's identity and docstring. For nodes: read before graph_editor_add_node.",
    registry_id="describe_component",
    annotations=_READ_ONLY,
)
class StudioDescribeComponentTool(Farmhand):
    async def run(self, ctx: FarmhandContext, registry_key: str) -> dict:
        cls = resolve_component_class(ctx, registry_key)
        identity = getattr(cls, "class_identity", None)
        return {
            "summary": f"{registry_key}: {getattr(identity, 'label', cls.__name__)}",
            "registry_key": registry_key,
            "class_name": cls.__name__,
            "label": getattr(identity, "label", cls.__name__),
            "description": getattr(identity, "description", ""),
            "docstring": inspect.getdoc(cls) or "",
        }
```

- [ ] **Step 5: Implement authoring tools**

```python
# barn/haybale-studio/haybale_studio/farmhands/authoring.py
"""studio_scaffold_component / studio_read_component_source /
studio_write_component_source / studio_verify_component.

Authoring is self-contained through Farmhand (no client filesystem access
assumed) and kind-generic. Writes are project-local-library-only; git is the
source-level undo. Hot-reload registers new/changed files (file_watcher=True
libraries) with zero further calls.
"""

from __future__ import annotations

import inspect
from pathlib import Path

from haywire.core.errors.ledger import get_error_ledger
from haywire.core.farmhand import (
    FarmhandContext,
    Farmhand,
    FarmhandError,
    ToolAnnotations,
    farmhand,
)

from ._helpers import (
    KIND_FOLDERS,
    library_folder,
    project_local_libraries,
    resolve_component_class,
    resolve_target_library,
)

_NODE_TEMPLATE = '''"""{name} — scaffolded by Farmhand. Authoring reference: farmhand://docs/canon/nodes"""

from haywire.core.node import BaseNode
from haywire.core.node.decorator import node
from haywire.barn.builtin.types import FLOAT


@node(label="{label}", description="TODO", menu="Custom")
class {class_name}(BaseNode):
    def init(self):
        self.add(FLOAT.as_inlet("x"))
        self.add(FLOAT.as_outlet("result"))

    def worker(self, context, x):
        self.out("result", x)
'''

_GENERIC_TEMPLATE = '''"""{name} — scaffolded by Farmhand.

Kind: {kind}. Authoring reference: farmhand://docs/canon/{canon_area}
Replace this stub with a {kind} component per the canon; the library's
folder scan registers it automatically once the class is decorated.
"""
'''


def _template(kind: str, name: str) -> str:
    class_name = "".join(part.capitalize() for part in name.split("_"))
    if kind == "node":
        return _NODE_TEMPLATE.format(name=name, label=class_name, class_name=class_name)
    return _GENERIC_TEMPLATE.format(name=name, kind=kind, canon_area=KIND_FOLDERS[kind])


@farmhand(
    label="Scaffold component",
    description="Write a canon-conformant skeleton for any component kind into a project-local "
    "library; returns the path and expected registry key. Read farmhand://docs/canon/{kind} first.",
    registry_id="scaffold_component",
    annotations=ToolAnnotations(),
)
class StudioScaffoldComponentTool(Farmhand):
    async def run(
        self, ctx: FarmhandContext, kind: str, name: str, library: str | None = None
    ) -> dict:
        if kind not in KIND_FOLDERS:
            raise FarmhandError(
                "bad_kind", f"kind must be one of {sorted(KIND_FOLDERS)}", ids={"kind": kind}
            )
        lib_id = resolve_target_library(ctx, library)
        folder = library_folder(ctx, lib_id) / KIND_FOLDERS[kind]
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{name}.py"
        if path.exists():
            raise FarmhandError("file_exists", f"{path} already exists.", ids={"path": str(path)})
        path.write_text(_template(kind, name), encoding="utf-8")
        expected_key = f"{lib_id}:{kind}:{name}"
        return {
            "summary": f"Scaffolded {expected_key} at {path}.",
            "path": str(path),
            "expected_registry_key": expected_key,
            "next": "Edit via studio_write_component_source, then studio_verify_component.",
        }


@farmhand(
    label="Read component source",
    description="Line-numbered source of any installed component.",
    registry_id="read_component_source",
    annotations=ToolAnnotations(read_only_hint=True),
)
class StudioReadComponentSourceTool(Farmhand):
    async def run(self, ctx: FarmhandContext, registry_key: str) -> dict:
        cls = resolve_component_class(ctx, registry_key)
        path = Path(inspect.getfile(cls))
        lines = path.read_text(encoding="utf-8").splitlines()
        numbered = "\n".join(f"{i + 1}\t{line}" for i, line in enumerate(lines))
        return {
            "summary": f"{registry_key}: {len(lines)} lines at {path}.",
            "registry_key": registry_key,
            "path": str(path),
            "source": numbered,
        }


@farmhand(
    label="Write component source",
    description="Full-source write into a project-local library only. Existing components are "
    "hot-reloaded by the file watcher; follow with studio_verify_component.",
    registry_id="write_component_source",
    annotations=ToolAnnotations(destructive_hint=True),
)
class StudioWriteComponentSourceTool(Farmhand):
    async def run(
        self,
        ctx: FarmhandContext,
        source: str,
        registry_key: str | None = None,
        library: str | None = None,
        kind: str | None = None,
        filename: str | None = None,
    ) -> dict:
        if registry_key is not None:
            cls = resolve_component_class(ctx, registry_key)
            path = Path(inspect.getfile(cls))
            lib_id = registry_key.split(":")[0]
            if lib_id not in project_local_libraries(ctx):
                raise FarmhandError(
                    "not_project_library",
                    f"'{lib_id}' is not project-local; Farmhand only writes project-local sources.",
                    ids={"registry_key": registry_key},
                )
        else:
            if kind not in KIND_FOLDERS or not filename:
                raise FarmhandError(
                    "bad_arguments",
                    "Pass either registry_key=, or library=/kind=/filename= for a new file.",
                )
            lib_id = resolve_target_library(ctx, library)
            path = library_folder(ctx, lib_id) / KIND_FOLDERS[kind] / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
        return {
            "summary": f"Wrote {len(source.splitlines())} lines to {path} (hot-reload will pick it up).",
            "path": str(path),
            "library": lib_id,
        }


@farmhand(
    label="Verify component",
    description="Staged verification: registered -> (nodes) trial instantiation -> on_testrun(); "
    "error-ledger entries from the failing stage are attached.",
    registry_id="verify_component",
    annotations=ToolAnnotations(read_only_hint=True),
)
class StudioVerifyComponentTool(Farmhand):
    async def run(self, ctx: FarmhandContext, registry_key: str) -> dict:
        ledger = get_error_ledger()
        start_seq = ledger.current_seq
        result: dict = {"registry_key": registry_key, "registered": False, "stage_reached": "none"}

        cls = resolve_component_class(ctx, registry_key)  # raises component_not_found
        result["registered"] = True
        result["stage_reached"] = "registered"

        if registry_key.split(":")[1] == "node":
            from haywire.core.graph.base import BaseGraph
            from haywire.core.graph.scheduler import SyncScheduler

            graph = BaseGraph("farmhand_verify", "verify", validation_scheduler=SyncScheduler())
            try:
                wrapper = graph.create_node_wrapper(registry_key)
                if wrapper is None:
                    raise FarmhandError(
                        "instantiation_failed",
                        f"Trial NodeWrapper instantiation failed for '{registry_key}'.",
                        ids={"registry_key": registry_key},
                    )
                result["stage_reached"] = "instantiated"
                ok, message = wrapper.node.on_testrun()
                result["stage_reached"] = "testrun"
                result["testrun_ok"] = ok
                if message:
                    result["testrun_message"] = message
            finally:
                graph.cleanup()

        errors = ledger.query(since_seq=start_seq, limit=20)
        result["errors"] = errors.entries
        result["summary"] = (
            f"{registry_key}: verified through stage '{result['stage_reached']}' "
            f"({len(errors.entries)} ledger entries)."
        )
        return result
```

```python
# barn/haybale-studio/haybale_studio/farmhands/errors.py
"""studio_get_errors — query the error ledger."""

from __future__ import annotations

from haywire.core.errors.ledger import get_error_ledger
from haywire.core.farmhand import FarmhandContext, Farmhand, ToolAnnotations, farmhand


@farmhand(
    label="Get errors",
    description="Query the studio's error ledger (since_seq/library/registry_key filters); "
    "results carry the current cursor for incremental polling.",
    registry_id="get_errors",
    annotations=ToolAnnotations(read_only_hint=True),
)
class StudioGetErrorsTool(Farmhand):
    async def run(
        self,
        ctx: FarmhandContext,
        since_seq: int | None = None,
        library: str | None = None,
        registry_key: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        result = get_error_ledger().query(
            since_seq=since_seq, library=library, registry_key=registry_key, limit=limit, offset=offset
        )
        return {
            "summary": f"{result.total} ledger entries match (cursor {result.cursor}).",
            "errors": result.entries,
            "total": result.total,
            "cursor": result.cursor,
        }
```

- [ ] **Step 6: Register the folder + declare the dependency**

1. Create the empty `barn/haybale-studio/haybale_studio/farmhands/__init__.py`. In `barn/haybale-studio/haybale_studio/__init__.py` (read it first — same shape as haybale-testing's), add `from haywire.core.farmhand import FarmhandRegistry` to the imports and register the folder AFTER its `state/` registration (canonical order: farmhands after state):

```python
        # Register MCP tools — the studio_* baseline (canonical order: after state)
        self.add_folder_to_registry(
            folder_path=str(base_path / "farmhands"),
            registry_cls=FarmhandRegistry,
        )
```

2. In `packages/haywire-studio/pyproject.toml`, add `"haybale-studio",` to the `dependencies` list (decided: the baseline's presence is packaging-enforced), then `uv sync` — the workspace member resolves locally; confirm the lockfile updates cleanly.

3. Adjust the `@node` decorator import path inside `_NODE_TEMPLATE` to whatever `barn/haybale-example/haybale_example/nodes/math_op.py` (the canon's live example) actually imports — copy that file's imports verbatim into the template.

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest tests/farmhand/test_baseline_tools.py -v`
Expected: all PASS. Fix any drift between assumed registry APIs and reality (the Interfaces block lists the verified ones).

- [ ] **Step 8: Lint, type-check, full fast suite, commit**

```bash
uv run ruff check barn/haybale-studio/ tests/farmhand/
uv run ruff format barn/haybale-studio/ tests/farmhand/
uv run mypy barn/haybale-studio/haybale_studio/
uv run pytest -m "not browser and not perf" -q
git add -A barn/haybale-studio packages/haywire-studio/pyproject.toml uv.lock tests/farmhand/
git commit -m "feat(farmhand): nine studio_* baseline tools in haybale-studio's farmhands/ folder (status, catalog, authoring loop, error ledger)"
```

---

### Task 10: Test fixtures, haybale-testing MCP components, server integration suite

**Files:**
- Create: `barn/haybale-testing/haybale_testing/farmhands/__init__.py` (empty)
- Create: `barn/haybale-testing/haybale_testing/farmhands/echo_tool.py`
- Create: `barn/haybale-testing/haybale_testing/farmhands/fail_tool.py`
- Create: `barn/haybale-testing/haybale_testing/farmhands/affinity_tool.py`
- Create: `barn/haybale-testing/haybale_testing/farmhands/blocking_tool.py`
- Modify: `barn/haybale-testing/haybale_testing/__init__.py` (register `farmhands/` folder — AFTER the `state/` block, per canonical order)
- Modify: `packages/haywire-studio/src/haywire_studio/farmhand/host.py` (add `app_target` parameter to `mount`)
- Create: `tests/farmhand/conftest.py`
- Test: `tests/farmhand/test_server_integration.py`, `tests/farmhand/test_bare_studio.py`

**Interfaces:**
- Consumes: `create_test_library_system`, `set_library_system`, `set_global_injector` (`haywire/core/di/config.py`); `_snapshot_ambient_di`/`_restore_ambient_di` (`tests/conftest.py:238-253` — import them, do not duplicate); SDK client: `mcp.client.streamable_http.streamablehttp_client`, `mcp.client.session.ClientSession`; `FarmhandHost` (Task 8); haybale-studio's `farmhands/` folder (Task 9) supplies the `studio_*` tools through the normal scan.
- Produces (Tasks 11–14's tests rely on these):
  - `farmhand_server` — session-scoped fixture yielding a namespace with `.base_url` (e.g. `http://127.0.0.1:<port>/mcp`), `.token`, `.service` (the LibrarySystemService), `.port`.
  - `farmhand_call(farmhand_server)` — function-scoped helper fixture: `farmhand_call(async_fn)` runs `async_fn(session)` against a fresh initialized `ClientSession` in its own `asyncio.run` (no parked-loop hazard; NOT browser-marked).
  - `call_tool_json(result) -> dict` module-level helper parsing a `CallToolResult`'s structured-JSON text content.
  - `farmhand_bare_server` — module-scoped bare-studio variant (builtin + haybale-studio only, via a symlinked library root → exactly the `studio_*` baseline).
  - Test tools registered by haybale-testing: `testing_echo`, `testing_fail`, `testing_affinity`, `testing_block`.

- [ ] **Step 1: Small host refactor for non-NiceGUI mounting**

In `host.py`, change `mount` to `def mount(self, port: int, app_target=None) -> None:` where `app_target = app_target or nicegui_app`; use `app_target.mount(...)`, and only register `nicegui_app.on_startup/on_shutdown` when `app_target is nicegui_app` (the test fixture drives `_on_startup`/`_on_shutdown` from its own lifespan). Run `uv run pytest tests/farmhand/test_host_unit.py -q` — still green.

- [ ] **Step 2: Write the haybale-testing MCP components**

```python
# barn/haybale-testing/haybale_testing/farmhands/echo_tool.py
"""Canned read tool for Farmhand integration tests."""

from haywire.core.farmhand import FarmhandContext, Farmhand, ToolAnnotations, farmhand


@farmhand(
    label="Echo",
    description="Echo text back (canned read tool).",
    registry_id="echo",
    annotations=ToolAnnotations(read_only_hint=True),
)
class EchoTool(Farmhand):
    async def run(self, ctx: FarmhandContext, text: str) -> dict:
        return {"echo": text}
```

```python
# barn/haybale-testing/haybale_testing/farmhands/fail_tool.py
"""Canned failing tool: exercises the structured error contract."""

from haywire.core.farmhand import FarmhandContext, Farmhand, FarmhandError, farmhand


@farmhand(label="Fail", description="Always fails with a stable code.", registry_id="fail")
class FailTool(Farmhand):
    async def run(self, ctx: FarmhandContext) -> dict:
        raise FarmhandError("testing_failure", "This tool always fails.", ids={"tool": "fail"})
```

```python
# barn/haybale-testing/haybale_testing/farmhands/affinity_tool.py
"""Instrumented tool: reports which thread/loop the handler ran on (ticket 06 evidence)."""

import asyncio
import threading

from haywire.core.farmhand import FarmhandContext, Farmhand, ToolAnnotations, farmhand


@farmhand(
    label="Affinity",
    description="Report handler thread and loop.",
    registry_id="affinity",
    annotations=ToolAnnotations(read_only_hint=True),
)
class AffinityTool(Farmhand):
    async def run(self, ctx: FarmhandContext) -> dict:
        try:
            on_loop = asyncio.get_running_loop() is not None
        except RuntimeError:
            on_loop = False
        return {"thread": threading.current_thread().name, "on_event_loop": on_loop}
```

```python
# barn/haybale-testing/haybale_testing/farmhands/blocking_tool.py
"""Blocking tool routed through ctx.offload(): must not stall concurrent requests."""

import time

from haywire.core.farmhand import FarmhandContext, Farmhand, farmhand


@farmhand(label="Block", description="Sleep off-loop for `seconds`.", registry_id="block")
class BlockTool(Farmhand):
    async def run(self, ctx: FarmhandContext, seconds: float = 1.0) -> dict:
        start = time.monotonic()
        await ctx.offload(time.sleep, seconds)
        return {"slept": round(time.monotonic() - start, 3)}
```

In `barn/haybale-testing/haybale_testing/__init__.py`, add the import at the top (`from haywire.core.farmhand import FarmhandRegistry`) and register AFTER the existing `state/` block (keep the adversarial state-last comment intact; farmhands/ goes after it):

```python
        # Register MCP tools (canonical order: after state — tools may reference states)
        self.add_folder_to_registry(
            folder_path=str(base_path / "farmhands"),
            registry_cls=FarmhandRegistry,
        )
```

- [ ] **Step 3: Write the fixtures**

```python
# tests/farmhand/conftest.py
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
    from haywire.core.di.config import (
        create_test_library_system,
        set_global_injector,
        set_library_system,
    )
    from haywire_studio.farmhand.host import FarmhandHost

    snap = _snapshot_ambient_di()
    service = create_test_library_system(
        workspace_root=str(tmp_root),
        library_paths=library_paths,
        load_libraries=True,
        enable_file_watching=False,
    )
    set_library_system(service)
    set_global_injector(service.injector)

    host = FarmhandHost(service, str(tmp_root))
    port = _free_port()

    @asynccontextmanager
    async def lifespan(app):
        await host._on_startup()
        yield
        await host._on_shutdown()

    app = FastAPI(lifespan=lifespan)
    host.mount(port, app_target=app)

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 15
    while not server.started:
        if time.monotonic() > deadline:
            raise RuntimeError("Farmhand test server failed to start")
        time.sleep(0.05)

    from haywire_studio.farmhand.auth import ensure_token

    handle = SimpleNamespace(
        base_url=f"http://127.0.0.1:{port}/mcp",
        token=ensure_token(tmp_root),
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
    scan loads it without the rest of the barn (its @library dependencies=[] —
    verified). No plugin libraries -> exactly the nine studio_* tools.
    """
    workspace = tmp_path_factory.mktemp("farmhand_bare_ws")
    libs = tmp_path_factory.mktemp("farmhand_bare_libs")
    (libs / "haybale-studio").symlink_to(project_root / "barn" / "haybale-studio")
    handle, teardown = _make_server(workspace, [str(libs)])
    yield handle
    teardown()


def call_tool_json(result) -> dict:
    """Parse a CallToolResult's structured-JSON text content."""
    assert result.content and result.content[0].type == "text"
    return json.loads(result.content[0].text)


def make_caller(handle):
    from mcp.client.session import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    def farmhand_call(async_fn, message_handler=None):
        async def runner():
            headers = {"Authorization": f"Bearer {handle.token}"}
            async with streamablehttp_client(handle.base_url, headers=headers) as (read, write, _):
                kwargs = {"message_handler": message_handler} if message_handler else {}
                async with ClientSession(read, write, **kwargs) as session:
                    init = await session.initialize()
                    return await async_fn(session, init)

        return asyncio.run(runner())

    return farmhand_call


@pytest.fixture()
def farmhand_call(farmhand_server):
    return make_caller(farmhand_server)
```

Verify against the installed SDK before finalizing: `streamablehttp_client`'s import path and yield shape (`uv run python -c "import inspect, mcp.client.streamable_http as m; print(inspect.signature(m.streamablehttp_client))"`), and `ClientSession`'s `message_handler` kwarg name. Adjust to reality — the shapes above match the 1.28 docs but the SDK is the authority. Also confirm `tests/conftest.py`'s `project_root` fixture points at the repo root (it feeds `barn/`).

- [ ] **Step 4: Write the integration suite (the coverage table rows owned by this task)**

```python
# tests/farmhand/test_server_integration.py
"""Served-app integration: capabilities, round-trip, errors, list_changed, affinity, offload, auth."""

import asyncio
import json
import time
import urllib.error
import urllib.request

import pytest

from tests.farmhand.conftest import call_tool_json

pytestmark = pytest.mark.integration


def test_initialize_advertises_list_changed(farmhand_call):
    async def scenario(session, init):
        return init

    init = farmhand_call(scenario)
    assert init.capabilities.tools.listChanged is True


def test_tool_round_trip_structured_json(farmhand_call):
    async def scenario(session, init):
        return await session.call_tool("testing_echo", {"text": "hi"})

    result = farmhand_call(scenario)
    payload = call_tool_json(result)
    assert payload["echo"] == "hi"
    assert "summary" in payload


def test_error_contract_stable_code_no_traceback(farmhand_call):
    async def scenario(session, init):
        return await session.call_tool("testing_fail", {})

    result = farmhand_call(scenario)
    assert result.isError is True
    text = result.content[0].text
    assert "[testing_failure]" in text
    assert "tool=fail" in text
    assert "Traceback" not in text


def test_mutating_tool_runs_on_event_loop(farmhand_call):
    async def scenario(session, init):
        return await session.call_tool("testing_affinity", {})

    payload = call_tool_json(farmhand_call(scenario))
    assert payload["on_event_loop"] is True


def test_blocking_tool_does_not_stall_concurrent_request(farmhand_call):
    async def scenario(session, init):
        started = time.monotonic()

        async def timed_echo():
            await session.call_tool("testing_echo", {"text": "quick"})
            return time.monotonic() - started

        block = asyncio.create_task(session.call_tool("testing_block", {"seconds": 1.5}))
        echo_elapsed = await timed_echo()
        await block
        return echo_elapsed

    assert farmhand_call(scenario) < 1.0  # echo finished while block still sleeping


def test_disable_enable_shrinks_and_grows_tool_list(farmhand_server, farmhand_call):
    from haywire.core.library.registry import LibraryRegistry

    registry = farmhand_server.service.injector.get(LibraryRegistry)

    async def scenario(session, init):
        names = {t.name for t in (await session.list_tools()).tools}
        assert "testing_echo" in names
        registry.disable_library("testing")
        try:
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                names = {t.name for t in (await session.list_tools()).tools}
                if "testing_echo" not in names:
                    break
                await asyncio.sleep(0.1)
            assert "testing_echo" not in names
        finally:
            registry.enable_library("testing")
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            names = {t.name for t in (await session.list_tools()).tools}
            if "testing_echo" in names:
                return True
            await asyncio.sleep(0.1)
        return False

    assert farmhand_call(scenario) is True


def _post(url: str, headers: dict) -> int:
    body = json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": "ping"}
    ).encode()
    request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", **headers})
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status
    except urllib.error.HTTPError as exc:
        return exc.code


def test_missing_token_is_401(farmhand_server):
    assert _post(farmhand_server.base_url, {}) == 401


def test_wrong_token_is_401(farmhand_server):
    assert _post(farmhand_server.base_url, {"Authorization": "Bearer wrong"}) == 401


def test_disallowed_origin_rejected(farmhand_server):
    status = _post(
        farmhand_server.base_url,
        {"Authorization": f"Bearer {farmhand_server.token}", "Origin": "http://evil.example"},
    )
    assert status in (400, 403, 421)


def test_token_file_created_gitignored_on_first_start(farmhand_server):
    """ensure_token ran during server mount against the session workspace."""
    from pathlib import Path

    from haywire_studio.farmhand.auth import TOKEN_FILENAME

    workspace = Path(farmhand_server.host._workspace_root)
    assert (workspace / ".haywire" / TOKEN_FILENAME).exists()
    assert TOKEN_FILENAME in (workspace / ".haywire" / ".gitignore").read_text()
```

```python
# tests/farmhand/test_bare_studio.py
"""A bare studio (builtin + haybale-studio only, no plugin libraries) serves exactly
the nine studio_* baseline tools."""

import pytest

from tests.farmhand.conftest import make_caller

pytestmark = pytest.mark.integration


def test_bare_studio_serves_exactly_the_baseline(farmhand_bare_server):
    farmhand_call = make_caller(farmhand_bare_server)

    async def scenario(session, init):
        return {t.name for t in (await session.list_tools()).tools}

    names = farmhand_call(scenario)
    assert names == {
        "studio_status",
        "studio_list_libraries",
        "studio_list_components",
        "studio_describe_component",
        "studio_scaffold_component",
        "studio_read_component_source",
        "studio_write_component_source",
        "studio_verify_component",
        "studio_get_errors",
    }
```

- [ ] **Step 5: Run, iterate, pass**

Run: `uv run pytest tests/farmhand/ -v`
Expected: all PASS. The likely friction points, in order: SDK client import paths (fix from step 3's inspection), the `list_changed`/session-manager `security_settings` variance (Task 8 step 1 fallback), and the `initialize` capabilities model attribute names (`init.capabilities.tools.listChanged` — print the object and adjust).

- [ ] **Step 6: Lint, full suite, commit**

```bash
uv run ruff check barn/haybale-testing/ tests/farmhand/ packages/haywire-studio/src/haywire_studio/farmhand/
uv run ruff format barn/haybale-testing/ tests/farmhand/ packages/haywire-studio/src/haywire_studio/farmhand/
uv run mypy packages/haywire-studio/src/ barn/haybale-testing/haybale_testing/
uv run pytest -m "not browser and not perf" -q
git add -A barn/haybale-testing tests/farmhand/ packages/haywire-studio
git commit -m "test(farmhand): served-app integration harness, haybale-testing farmhand components, coverage rows for transport/auth/lifecycle"
```

---

### Task 11: `marketplace` tools (6)

**Files:**
- Create: `barn/haybale-marketplace/haybale_marketplace/farmhands/__init__.py` (empty)
- Create: `barn/haybale-marketplace/haybale_marketplace/farmhands/catalog_tools.py` (list_available, refresh, get_library_docs)
- Create: `barn/haybale-marketplace/haybale_marketplace/farmhands/install_tools.py` (dry_run_install, install_library, uninstall_library)
- Modify: `barn/haybale-marketplace/haybale_marketplace/__init__.py` (register `farmhands/` folder after its `state/` registration; import `FarmhandRegistry`)
- Test: `tests/farmhand/test_marketplace_tools.py`

**Interfaces:**
- Consumes (verified signatures in the operations inventory §1): `MarketplaceState.get_project_haybales() -> list[Haybale]`, `refresh() -> RefreshReport` (BLOCKING network — must go through `ctx.offload`), `async fetch_overview(pkg: Haybale) -> str | None`; `LibraryManager`: `async dry_run(install_spec) -> list[str]`, `async install(install_spec, on_output, source_pkg=None) -> tuple[bool, str, PostInstallHints]`, `async uninstall_streaming(library_id, on_output) -> tuple[bool, str, PostInstallHints]`, `get_missing_dependencies(lib_id, require_enabled)`; `LibraryRegistry.get_library_identity(lib_id)` for installed docs (`Path(identity.folder_path) / "OVERVIEW.md"` etc.); `LibraryCatalogChanged` signal (`haywire/core/session/signals/vocabulary.py:81`, `cross_session=True`).
- Produces: tool classes `MarketplaceListAvailableTool`, `MarketplaceRefreshTool`, `MarketplaceGetLibraryDocsTool`, `MarketplaceDryRunInstallTool`, `MarketplaceInstallLibraryTool`, `MarketplaceUninstallLibraryTool` → MCP names `marketplace_list_available` etc. (library id of haybale-marketplace — verify with `grep -n "id=" barn/haybale-marketplace/haybale_marketplace/__init__.py`; if the id is `marketplace` the names match the spec table; if it is something else, e.g. `haybale_marketplace`, the `{lib_id}_{name}` rule wins and the spec table's short names mean the registry_ids must be chosen so the VISIBLE name matches the spec, i.e. spec names are normative).

**Shared bits (put at top of `catalog_tools.py`, import in `install_tools.py`):**

```python
def _marketplace_state(ctx):
    from haybale_marketplace.state.marketplace_state import MarketplaceState

    return ctx.state(MarketplaceState)


def _library_manager(ctx):
    from haybale_marketplace.state.library_manager_state import LibraryManagerState

    state = ctx.state(LibraryManagerState)
    manager = getattr(state, "library_manager", None) or getattr(state, "manager", None)
    if manager is None:
        raise FarmhandError(
            "marketplace_unavailable", "LibraryManager is not initialized on this studio."
        )
    return manager


def _progress_cb(ctx):
    """Bridge LibraryManager's sync on_output callback to async ctx.progress."""
    import asyncio

    loop = asyncio.get_running_loop()

    def on_output(line: str) -> None:
        loop.create_task(ctx.progress(line))

    return on_output
```

Verify the `LibraryManagerState` attribute that holds the manager (`grep -n "self\." barn/haybale-marketplace/haybale_marketplace/state/library_manager_state.py | head -20`) and replace the `getattr` chain with the real attribute.

- [ ] **Step 1: Write the failing tests (offline rows only — refresh/install/uninstall/dry-run are network/destructive and stay untested in CI; state that in the module docstring)**

```python
# tests/farmhand/test_marketplace_tools.py
"""Offline-testable marketplace tools. Network/destructive tools (refresh, dry_run,
install, uninstall) are exercised manually, not in CI — they run `uv`/urllib."""

import asyncio

import pytest

from haywire.core.farmhand import FarmhandContext, FarmhandError

pytestmark = pytest.mark.integration


def run_tool(tool_cls, **kwargs):
    return asyncio.run(tool_cls().run(FarmhandContext(), **kwargs))


@pytest.fixture(autouse=True)
def _ambient(library_system):
    yield


def test_list_available_returns_paginated_catalog():
    from haybale_marketplace.farmhands.catalog_tools import MarketplaceListAvailableTool

    result = run_tool(MarketplaceListAvailableTool, limit=10, offset=0)
    assert "total" in result and "haybales" in result  # may be empty in a test workspace


def test_get_library_docs_for_installed_library():
    from haybale_marketplace.farmhands.catalog_tools import MarketplaceGetLibraryDocsTool

    # haybale-marketplace itself is installed in the barn; any doc file counts.
    try:
        result = run_tool(MarketplaceGetLibraryDocsTool, library="testing")
        assert result["source"] == "installed"
        assert result["text"]
    except FarmhandError as exc:
        assert exc.code == "docs_not_found"  # acceptable if the test lib ships no docs


def test_get_library_docs_unknown_library_is_stable_error():
    from haybale_marketplace.farmhands.catalog_tools import MarketplaceGetLibraryDocsTool

    with pytest.raises(FarmhandError) as exc_info:
        run_tool(MarketplaceGetLibraryDocsTool, library="does_not_exist")
    assert exc_info.value.code == "library_not_found"
```

Run: `uv run pytest tests/farmhand/test_marketplace_tools.py -v` — Expected: FAIL (`ModuleNotFoundError: haybale_marketplace.farmhands`).

- [ ] **Step 2: Implement catalog tools**

```python
# barn/haybale-marketplace/haybale_marketplace/farmhands/catalog_tools.py
"""marketplace_list_available / marketplace_refresh / marketplace_get_library_docs."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from haywire.core.farmhand import (
    FarmhandContext,
    Farmhand,
    FarmhandError,
    ToolAnnotations,
    farmhand,
)
from haywire.core.library.registry import LibraryRegistry

# ... _marketplace_state / _library_manager / _progress_cb helpers from the task brief ...

_DOC_FILES = ("OVERVIEW.md", "QUICKREF.md", "README.md")


@farmhand(
    label="List available",
    description="Merged AVAILABLE catalog (not-installed libraries) from the marketplace cache.",
    registry_id="list_available",
    annotations=ToolAnnotations(read_only_hint=True),
)
class MarketplaceListAvailableTool(Farmhand):
    async def run(self, ctx: FarmhandContext, limit: int = 50, offset: int = 0) -> dict:
        haybales = [asdict(h) for h in _marketplace_state(ctx).get_project_haybales()]
        total = len(haybales)
        return {
            "summary": f"{total} haybales available.",
            "haybales": haybales[offset : offset + limit],
            "total": total,
        }


@farmhand(
    label="Refresh catalog",
    description="Re-fetch all subscribed markets/stalls (network; rewrites the project cache).",
    registry_id="refresh",
    annotations=ToolAnnotations(open_world_hint=True),
)
class MarketplaceRefreshTool(Farmhand):
    async def run(self, ctx: FarmhandContext) -> dict:
        state = _marketplace_state(ctx)
        report = await ctx.offload(state.refresh)  # blocking urllib — never on the loop
        return {
            "summary": f"Refreshed: {report.haybales_resolved} haybales resolved.",
            "report": {k: v for k, v in vars(report).items() if not k.startswith("_")},
        }


@farmhand(
    label="Get library docs",
    description="Docs for an installed library (OVERVIEW/QUICKREF/README from its folder) or an "
    "available one (network fetch of its docs_url).",
    registry_id="get_library_docs",
    annotations=ToolAnnotations(read_only_hint=True, open_world_hint=True),
)
class MarketplaceGetLibraryDocsTool(Farmhand):
    async def run(self, ctx: FarmhandContext, library: str) -> dict:
        registry = ctx.registry(LibraryRegistry)
        if library in registry.list_names():
            folder = Path(registry.get_library_identity(library).folder_path)
            for name in _DOC_FILES:
                path = folder / name
                if path.exists():
                    return {
                        "summary": f"{library}: {name} ({path.stat().st_size} bytes).",
                        "source": "installed",
                        "file": name,
                        "text": path.read_text(encoding="utf-8"),
                    }
            raise FarmhandError(
                "docs_not_found", f"'{library}' ships no OVERVIEW/QUICKREF/README.", ids={"library": library}
            )
        for pkg in _marketplace_state(ctx).get_project_haybales():
            if pkg.name == library:
                text = await _marketplace_state(ctx).fetch_overview(pkg)
                if not text:
                    raise FarmhandError(
                        "docs_not_found", f"No remote docs found for '{library}'.", ids={"library": library}
                    )
                return {"summary": f"{library}: remote docs.", "source": "available", "text": text}
        raise FarmhandError(
            "library_not_found", f"'{library}' is neither installed nor in the catalog.", ids={"library": library}
        )
```

- [ ] **Step 3: Implement install tools**

```python
# barn/haybale-marketplace/haybale_marketplace/farmhands/install_tools.py
"""marketplace_dry_run_install / marketplace_install_library / marketplace_uninstall_library."""

from __future__ import annotations

from haywire.core.farmhand import (
    FarmhandContext,
    Farmhand,
    FarmhandError,
    ToolAnnotations,
    farmhand,
)
from haywire.core.session.signals.vocabulary import LibraryCatalogChanged

from .catalog_tools import _library_manager, _progress_cb


@farmhand(
    label="Dry-run install",
    description="Resolve what an install would remove/upgrade, without installing (informational valve).",
    registry_id="dry_run_install",
    annotations=ToolAnnotations(read_only_hint=True, open_world_hint=True),
)
class MarketplaceDryRunInstallTool(Farmhand):
    async def run(self, ctx: FarmhandContext, install_spec: str) -> dict:
        try:
            affected = await _library_manager(ctx).dry_run(install_spec)
        except RuntimeError as exc:
            raise FarmhandError("resolver_failed", str(exc), ids={"install_spec": install_spec})
        return {
            "summary": f"Install of '{install_spec}' would touch {len(affected)} distributions.",
            "affected_distributions": affected,
        }


@farmhand(
    label="Install library",
    description="Install a library via uv pip (streams progress). Destructive: changes the venv. "
    "Run marketplace_dry_run_install first.",
    registry_id="install_library",
    annotations=ToolAnnotations(destructive_hint=True, open_world_hint=True),
)
class MarketplaceInstallLibraryTool(Farmhand):
    async def run(self, ctx: FarmhandContext, install_spec: str) -> dict:
        manager = _library_manager(ctx)
        ok, message, hints = await manager.install(install_spec, _progress_cb(ctx))
        if not ok:
            raise FarmhandError("install_failed", message, ids={"install_spec": install_spec})
        ctx.broadcast(LibraryCatalogChanged())  # caller-owned signal, gap 5
        return {
            "summary": f"Installed '{install_spec}'. {message}",
            "needs_refresh": hints.needs_refresh,
            "needs_restart": hints.needs_restart,
        }


@farmhand(
    label="Uninstall library",
    description="Uninstall an installed library via uv pip (streams progress). Destructive.",
    registry_id="uninstall_library",
    annotations=ToolAnnotations(destructive_hint=True),
)
class MarketplaceUninstallLibraryTool(Farmhand):
    async def run(self, ctx: FarmhandContext, library_id: str) -> dict:
        manager = _library_manager(ctx)
        ok, message, hints = await manager.uninstall_streaming(library_id, _progress_cb(ctx))
        if not ok:
            raise FarmhandError("uninstall_failed", message, ids={"library_id": library_id})
        ctx.broadcast(LibraryCatalogChanged())
        return {
            "summary": f"Uninstalled '{library_id}'. {message}",
            "needs_restart": hints.needs_restart,
        }
```

Check `LibraryCatalogChanged`'s constructor (fields at `vocabulary.py:81-95`) and `PostInstallHints` attribute names (`library_manager.py:258`) — adjust the two call sites if fields differ. Register the `farmhands/` folder in `barn/haybale-marketplace/haybale_marketplace/__init__.py` after its `state/` registration, same shape as haybale-testing's.

- [ ] **Step 4: Run tests, lint, commit**

```bash
uv run pytest tests/farmhand/test_marketplace_tools.py -v          # expect PASS
uv run pytest tests/farmhand/ -q                                   # server suite still green
uv run ruff check barn/haybale-marketplace/ tests/farmhand/ && uv run ruff format barn/haybale-marketplace/ tests/farmhand/
uv run pytest -m "not browser and not perf" -q
git add -A barn/haybale-marketplace tests/farmhand/
git commit -m "feat(farmhand): marketplace farmhand tools — catalog, docs, dry-run, install/uninstall with progress streaming"
```

---

### Task 12: `haystack` tools (9)

**Files:**
- Create: `barn/haybale-haystack/haybale_haystack/farmhands/__init__.py` (empty)
- Create: `barn/haybale-haystack/haybale_haystack/farmhands/graph_tools.py`
- Modify: `barn/haybale-haystack/haybale_haystack/__init__.py` (register `farmhands/` folder; import `FarmhandRegistry`)
- Test: `tests/farmhand/test_haystack_tools.py`

**Interfaces:**
- Consumes (inventory §2): `HaystackState` — `create_new()`, `open_graph(path)`, `save_graph(entry, save_as=None)`, `rename_graph(entry, new_name)`, `remove_entry(entry)` (never deletes files), `start_execution(entry) -> CompileResult`, `stop_execution(entry)`, `get_by_id(binding_id)`, `all_entries()`; `GraphEntry` — `binding_id`, `display_name`, `unsaved`, `is_executing`, `path`, `compile() -> CompileResult`; `GraphDataMutated` signal. Note: `HaystackState` mutators broadcast `GraphDataMutated` themselves; only start/stop need a `ctx.broadcast(GraphDataMutated())` from the tool (they don't broadcast).
- Produces: tools with registry_ids `list_graphs`, `create_graph`, `open_graph`, `save_graph`, `rename_graph`, `close_graph`, `compile_graph`, `start_graph`, `stop_graph` (MCP names `haystack_*` given lib id `haystack` — verify the id in `barn/haybale-haystack/haybale_haystack/__init__.py`'s `@library(id=...)`; spec names are normative, adjust registry_ids if the lib id differs). Shared helper `_entry(ctx, binding_id)`.

Full implementation (one module; entry serialization helper at top):

```python
# barn/haybale-haystack/haybale_haystack/farmhands/graph_tools.py
"""haystack_* MCP tools: graph lifecycle + execution control (spec §5)."""

from __future__ import annotations

from pathlib import Path

from haywire.core.farmhand import (
    FarmhandContext,
    Farmhand,
    FarmhandError,
    ToolAnnotations,
    farmhand,
)
from haywire.core.session.signals.vocabulary import GraphDataMutated

_READ_ONLY = ToolAnnotations(read_only_hint=True)
_MUTATING = ToolAnnotations()


def _state(ctx: FarmhandContext):
    from haybale_haystack.state.haystack_state import HaystackState

    return ctx.state(HaystackState)


def _entry(ctx: FarmhandContext, binding_id: str):
    entry = _state(ctx).get_by_id(binding_id)
    if entry is None:
        raise FarmhandError(
            "graph_not_found", f"No open graph '{binding_id}'.", ids={"binding_id": binding_id}
        )
    return entry


def _entry_row(entry) -> dict:
    return {
        "binding_id": entry.binding_id,
        "display_name": entry.display_name,
        "path": str(entry.path) if entry.path else None,
        "unsaved": entry.unsaved,
        "is_executing": entry.is_executing,
    }


def _compile_row(result) -> dict:
    # CompileResult's exact fields: verify at its definition (grep "class CompileResult"
    # in packages/haywire-core/src/haywire/core/execution/) and list the real ones here.
    row = {}
    for field in ("success", "errors", "warnings", "node_count"):
        if hasattr(result, field):
            value = getattr(result, field)
            row[field] = [str(v) for v in value] if isinstance(value, list) else value
    return row


@farmhand(
    label="List graphs",
    description="Open haystack entries plus .haywire files on disk in the workspace.",
    registry_id="list_graphs",
    annotations=_READ_ONLY,
)
class HaystackListGraphsTool(Farmhand):
    async def run(self, ctx: FarmhandContext, limit: int = 100, offset: int = 0) -> dict:
        open_rows = [_entry_row(e) for e in _state(ctx).all_entries()]
        root = ctx.workspace_root()
        on_disk = sorted(
            str(p.relative_to(root))
            for p in root.rglob("*.haywire")
            if not any(part.startswith(".") for part in p.relative_to(root).parts)
        )
        total = len(on_disk)
        return {
            "summary": f"{len(open_rows)} graphs open, {total} .haywire files on disk.",
            "open": open_rows,
            "files": on_disk[offset : offset + limit],
            "total": total,
        }


@farmhand(
    label="Create graph",
    description="Create a new untitled graph (appears in open browser sessions).",
    registry_id="create_graph",
    annotations=_MUTATING,
)
class HaystackCreateGraphTool(Farmhand):
    async def run(self, ctx: FarmhandContext) -> dict:
        entry = _state(ctx).create_new()  # broadcasts GraphDataMutated itself
        return {"summary": f"Created {entry.binding_id}.", **_entry_row(entry)}


@farmhand(
    label="Open graph",
    description="Open a .haywire file (idempotent per path).",
    registry_id="open_graph",
    annotations=_MUTATING,
)
class HaystackOpenGraphTool(Farmhand):
    async def run(self, ctx: FarmhandContext, path: str) -> dict:
        target = (ctx.workspace_root() / path).resolve()
        if not target.exists():
            raise FarmhandError("file_not_found", f"No file at {target}.", ids={"path": path})
        entry = _state(ctx).open_graph(target)
        return {"summary": f"Opened {entry.binding_id}.", **_entry_row(entry)}


@farmhand(
    label="Save graph",
    description="Save an open graph; save_as writes to a new path.",
    registry_id="save_graph",
    annotations=_MUTATING,
)
class HaystackSaveGraphTool(Farmhand):
    async def run(self, ctx: FarmhandContext, binding_id: str, save_as: str | None = None) -> dict:
        entry = _entry(ctx, binding_id)
        target = (ctx.workspace_root() / save_as).resolve() if save_as else None
        ok = _state(ctx).save_graph(entry, target)
        if not ok:
            raise FarmhandError("save_failed", f"Saving '{binding_id}' failed.", ids={"binding_id": binding_id})
        return {"summary": f"Saved {entry.binding_id}.", **_entry_row(entry)}


@farmhand(
    label="Rename graph",
    description="Rename an open graph's file on disk and rekey it.",
    registry_id="rename_graph",
    annotations=_MUTATING,
)
class HaystackRenameGraphTool(Farmhand):
    async def run(self, ctx: FarmhandContext, binding_id: str, new_name: str) -> dict:
        entry = _entry(ctx, binding_id)
        ok = _state(ctx).rename_graph(entry, new_name)
        if not ok:
            raise FarmhandError("rename_failed", f"Renaming '{binding_id}' failed.", ids={"binding_id": binding_id})
        return {"summary": f"Renamed to {entry.display_name}.", **_entry_row(entry)}


@farmhand(
    label="Close graph",
    description="Close an open graph entry. NEVER deletes the file on disk.",
    registry_id="close_graph",
    annotations=_MUTATING,
)
class HaystackCloseGraphTool(Farmhand):
    async def run(self, ctx: FarmhandContext, binding_id: str) -> dict:
        entry = _entry(ctx, binding_id)
        _state(ctx).remove_entry(entry)
        return {"summary": f"Closed {binding_id} (file kept).", "binding_id": binding_id}


@farmhand(
    label="Compile graph",
    description="Compile without starting; returns compile diagnostics.",
    registry_id="compile_graph",
    annotations=_READ_ONLY,
)
class HaystackCompileGraphTool(Farmhand):
    async def run(self, ctx: FarmhandContext, binding_id: str) -> dict:
        result = _entry(ctx, binding_id).compile()
        return {"summary": f"Compiled {binding_id}.", "compile": _compile_row(result)}


@farmhand(
    label="Start graph",
    description="Compile and start execution. Destructive: nodes perform real I/O.",
    registry_id="start_graph",
    annotations=ToolAnnotations(destructive_hint=True),
)
class HaystackStartGraphTool(Farmhand):
    async def run(self, ctx: FarmhandContext, binding_id: str) -> dict:
        entry = _entry(ctx, binding_id)
        result = _state(ctx).start_execution(entry)
        ctx.broadcast(GraphDataMutated())  # start/stop don't broadcast themselves
        return {"summary": f"Started {binding_id}.", "compile": _compile_row(result), **_entry_row(entry)}


@farmhand(
    label="Stop graph",
    description="Stop a running graph (bounded grace, then teardown).",
    registry_id="stop_graph",
    annotations=_MUTATING,
)
class HaystackStopGraphTool(Farmhand):
    async def run(self, ctx: FarmhandContext, binding_id: str) -> dict:
        entry = _entry(ctx, binding_id)
        _state(ctx).stop_execution(entry)
        ctx.broadcast(GraphDataMutated())
        return {"summary": f"Stopped {binding_id}.", **_entry_row(entry)}
```

- [ ] **Steps (same rhythm):**
  1. Write failing tests first:

```python
# tests/farmhand/test_haystack_tools.py
"""haystack_* tools driven directly under the served-app's library system."""

import asyncio

import pytest

from haywire.core.farmhand import FarmhandContext, FarmhandError

pytestmark = pytest.mark.integration


def run_tool(tool_cls, **kwargs):
    return asyncio.run(tool_cls().run(FarmhandContext(), **kwargs))


@pytest.fixture(autouse=True)
def _ambient(library_system):
    yield


@pytest.fixture()
def open_entry():
    """Create a graph via the tool, always close it after the test (cleanup rule)."""
    from haybale_haystack.farmhands.graph_tools import HaystackCloseGraphTool, HaystackCreateGraphTool

    created = run_tool(HaystackCreateGraphTool)
    yield created
    try:
        run_tool(HaystackCloseGraphTool, binding_id=created["binding_id"])
    except FarmhandError:
        pass  # already closed by the test


def test_create_list_close_round_trip(open_entry):
    from haybale_haystack.farmhands.graph_tools import HaystackListGraphsTool

    listing = run_tool(HaystackListGraphsTool)
    assert any(row["binding_id"] == open_entry["binding_id"] for row in listing["open"])


def test_compile_start_stop_empty_graph(open_entry):
    from haybale_haystack.farmhands.graph_tools import (
        HaystackCompileGraphTool,
        HaystackStartGraphTool,
        HaystackStopGraphTool,
    )

    bid = open_entry["binding_id"]
    assert "compile" in run_tool(HaystackCompileGraphTool, binding_id=bid)
    run_tool(HaystackStartGraphTool, binding_id=bid)
    run_tool(HaystackStopGraphTool, binding_id=bid)


def test_save_and_reopen(open_entry, tmp_path):
    from haybale_haystack.farmhands.graph_tools import HaystackSaveGraphTool

    # save_as is workspace-relative; write into graphs/ under the ambient workspace root.
    result = run_tool(
        HaystackSaveGraphTool, binding_id=open_entry["binding_id"], save_as="graphs/farmhand_t12.haywire"
    )
    assert result["path"] and result["unsaved"] is False


def test_unknown_binding_id_is_stable_error():
    from haybale_haystack.farmhands.graph_tools import HaystackCompileGraphTool

    with pytest.raises(FarmhandError) as exc_info:
        run_tool(HaystackCompileGraphTool, binding_id="__nope__")
    assert exc_info.value.code == "graph_not_found"
```

  2. Run → fail (`ModuleNotFoundError: haybale_haystack.farmhands`). 3. Implement the module above; fill `_compile_row`'s real field list from `CompileResult`'s definition. 4. Register `farmhands/` in the library `__init__.py`. 5. Run → pass; note: the save test writes into the session workspace — delete the file in the test's teardown (`(root / "graphs/farmhand_t12.haywire").unlink(missing_ok=True)` via the state's workspace root). 6. Lint/format both dirs, `uv run pytest -m "not browser and not perf" -q`, then:

```bash
git add -A barn/haybale-haystack tests/farmhand/
git commit -m "feat(farmhand): haystack farmhand tools — graph lifecycle + execution control"
```

---

### Task 13: `graph_editor` tools (10) — including the fence contract

**Files:**
- Create: `barn/haybale-graph-editor/haybale_graph_editor/farmhands/__init__.py` (empty)
- Create: `barn/haybale-graph-editor/haybale_graph_editor/farmhands/editor_tools.py`
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/__init__.py` (register `farmhands/`; import `FarmhandRegistry`)
- Test: `tests/farmhand/test_graph_editor_tools.py`

**Interfaces:**
- Consumes: `GraphAppState.get(binding_id) -> GraphContainer` (`graph_app_state.py:48`) → `.editor` (the sanctioned graph-id → mutation route); `Editor` API incl. Task 2's `set_property`; `promote_setting(node, accessor, field, direction: PortType)` / `demote_setting(node, port_id)` (`haywire/core/node/promotion.py:174,259`); `PortType` enum; `ctx.fence(editor)`; `GraphDataMutated`.
- Produces: `GraphEditorQueryGraphTool`, `GraphEditorAddNodeTool`, `GraphEditorConnectTool`, `GraphEditorRemoveElementsTool`, `GraphEditorMoveNodesTool`, `GraphEditorSetPropertyTool`, `GraphEditorPromoteSettingTool`, `GraphEditorDemoteSettingTool`, `GraphEditorUndoTool`, `GraphEditorRedoTool` (registry_ids `query_graph`, `add_node`, `connect`, `remove_elements`, `move_nodes`, `set_property`, `promote_setting`, `demote_setting`, `undo`, `redo`; verify lib id gives `graph_editor_*` visible names). Every mutating tool: `ctx.fence(editor)` FIRST, `ctx.broadcast(GraphDataMutated())` after success.

Task 12's `graph_tools.py` is the structural template for this module — identical decorator/annotation/helper/error shape; only the wrapped calls differ. Write the full module; the helpers and the per-tool contracts (exact params, wrapped call, error codes, fence/broadcast) are:

```python
def _editor(ctx, binding_id):
    from haybale_graph_editor.state.graph_app_state import GraphAppState

    container = ctx.state(GraphAppState).get(binding_id)
    if container is None:
        raise FarmhandError(
            "graph_not_found", f"No open graph '{binding_id}'.", ids={"binding_id": binding_id}
        )
    return container.editor


def _node(editor, node_id):
    wrapper = editor.get_node_wrapper(node_id)
    if wrapper is None:
        raise FarmhandError("node_not_found", f"No node '{node_id}'.", ids={"node_id": node_id})
    return wrapper
```

- `query_graph(binding_id, limit=100, offset=0)` (read-only, no fence): iterate `editor.list_node_wrappers()` → rows `{node_id, registry_key, ports: [{id, direction, flow_type}]}` (registry key via `wrapper.node.class_identity.registry_key`; port direction via `port.is_inlet()/is_outlet()`; `port.flow_type.value` NOT `str(port.flow_type)` — `.insights/project_graph_canvas_connection.md`); edges via `editor.list_edges()` → `{edge_id, source_node, outlet, sink_node, inlet}` (read `EdgeWrapper`'s attribute names at `haywire/core/edge/edge_wrapper.py` before writing this row). Paginate nodes; return `total` node count.
- `add_node(binding_id, registry_key, x=3750.0, y=3750.0)`: fence → `editor.create_wrapper(registry_key, (x, y))` → None ⇒ `FarmhandError("add_node_failed", ...)`; else broadcast + return `{node_id}`. Description tells agents to `studio_describe_component` first.
- `connect(binding_id, source_node_id, outlet, sink_node_id, inlet)`: fence → `editor.create_edge(...)`; False ⇒ `connect_failed` with all four ids; else broadcast.
- `remove_elements(binding_id, nodes=[], edges=[])`: fence → `editor.remove_elements(nodes, edges)`; False ⇒ `remove_failed` (Editor validated ids — message says which list to re-check); else broadcast. Description notes this is also "disconnect".
- `move_nodes(binding_id, positions: dict)`: positions `{node_id: {"x": .., "y": ..}}` (already `move_nodes_to`'s shape); fence → call → broadcast.
- `set_property(binding_id, node_id, name, value)`: leave `value` unannotated (schema `{}` = any JSON); fence → `editor.set_property(node_id, name, value)`; False ⇒ `set_property_failed` naming node/name; else broadcast.
- `promote_setting(binding_id, node_id, accessor, field, direction="inlet")`: map direction string → `PortType[direction.upper()]` (KeyError ⇒ `bad_direction`); call `promote_setting(_node(editor, node_id).node, accessor, field, port_type)`; `ValueError` ⇒ `FarmhandError("not_promotable", str(exc), ...)` (eligibility errors surfaced verbatim); broadcast. NOT undo-routed — say so in the tool description (UI parity; later-work note).
- `demote_setting(binding_id, node_id, port_id)`: call `demote_setting(_node(editor, node_id).node, port_id)`; broadcast.
- `undo(binding_id)` / `redo(binding_id)`: no fence (they navigate fences); `editor.undo()`/`editor.redo()` → `{"performed": bool}`; broadcast when performed (UI parity: `graph_editor.py:302-310` does the same after UI undo). Descriptions MUST state these drive the SHARED human+agent timeline.

- [ ] **Step 1: failing tests** (the fence row lives here):

```python
# tests/farmhand/test_graph_editor_tools.py
"""graph_editor_* tools; includes the one-call-one-undo-fence contract."""

import asyncio

import pytest

from haywire.core.farmhand import FarmhandContext, FarmhandError

pytestmark = pytest.mark.integration


def run_tool(tool_cls, **kwargs):
    return asyncio.run(tool_cls().run(FarmhandContext(), **kwargs))


@pytest.fixture(autouse=True)
def _ambient(library_system):
    yield


@pytest.fixture()
def graph_binding():
    from haybale_haystack.farmhands.graph_tools import HaystackCloseGraphTool, HaystackCreateGraphTool

    created = run_tool(HaystackCreateGraphTool)
    yield created["binding_id"]
    run_tool(HaystackCloseGraphTool, binding_id=created["binding_id"])


NODE_KEY = "haybale_core:node:add"  # verify: any registered node key with data pins works


def test_add_query_remove(graph_binding):
    from haybale_graph_editor.farmhands.editor_tools import (
        GraphEditorAddNodeTool,
        GraphEditorQueryGraphTool,
        GraphEditorRemoveElementsTool,
    )

    node_id = run_tool(GraphEditorAddNodeTool, binding_id=graph_binding, registry_key=NODE_KEY)["node_id"]
    query = run_tool(GraphEditorQueryGraphTool, binding_id=graph_binding)
    assert any(n["node_id"] == node_id for n in query["nodes"])
    assert query["total"] == 1
    run_tool(GraphEditorRemoveElementsTool, binding_id=graph_binding, nodes=[node_id])
    assert run_tool(GraphEditorQueryGraphTool, binding_id=graph_binding)["total"] == 0


def test_one_tool_call_is_one_undo_gesture(graph_binding):
    from haybale_graph_editor.farmhands.editor_tools import (
        GraphEditorAddNodeTool,
        GraphEditorQueryGraphTool,
        GraphEditorUndoTool,
    )

    run_tool(GraphEditorAddNodeTool, binding_id=graph_binding, registry_key=NODE_KEY)
    run_tool(GraphEditorAddNodeTool, binding_id=graph_binding, registry_key=NODE_KEY)
    assert run_tool(GraphEditorQueryGraphTool, binding_id=graph_binding)["total"] == 2
    assert run_tool(GraphEditorUndoTool, binding_id=graph_binding)["performed"] is True
    # exactly ONE call reverted, not both:
    assert run_tool(GraphEditorQueryGraphTool, binding_id=graph_binding)["total"] == 1


def test_set_property_and_undo(graph_binding):
    from haybale_graph_editor.farmhands.editor_tools import (
        GraphEditorAddNodeTool,
        GraphEditorSetPropertyTool,
        GraphEditorUndoTool,
    )

    node_id = run_tool(GraphEditorAddNodeTool, binding_id=graph_binding, registry_key=NODE_KEY)["node_id"]
    # discover an inlet id from the query tool rather than hardcoding one:
    from haybale_graph_editor.farmhands.editor_tools import GraphEditorQueryGraphTool

    node = next(
        n for n in run_tool(GraphEditorQueryGraphTool, binding_id=graph_binding)["nodes"]
        if n["node_id"] == node_id
    )
    inlet = next(p["id"] for p in node["ports"] if p["direction"] == "inlet")
    run_tool(GraphEditorSetPropertyTool, binding_id=graph_binding, node_id=node_id, name=inlet, value=7.0)
    assert run_tool(GraphEditorUndoTool, binding_id=graph_binding)["performed"] is True


def test_connect_failure_is_stable_error(graph_binding):
    from haybale_graph_editor.farmhands.editor_tools import GraphEditorConnectTool

    with pytest.raises(FarmhandError) as exc_info:
        run_tool(
            GraphEditorConnectTool,
            binding_id=graph_binding,
            source_node_id="ghost",
            outlet="out",
            sink_node_id="ghost2",
            inlet="in",
        )
    assert exc_info.value.code == "connect_failed"


def test_unknown_graph_is_stable_error():
    from haybale_graph_editor.farmhands.editor_tools import GraphEditorQueryGraphTool

    with pytest.raises(FarmhandError) as exc_info:
        run_tool(GraphEditorQueryGraphTool, binding_id="__nope__")
    assert exc_info.value.code == "graph_not_found"
```

- [ ] **Step 2:** run → fail (`ModuleNotFoundError`). **Step 3:** implement `editor_tools.py` fully per the sketch (every tool follows the fence→call→broadcast pattern shown; port rows use `{"id": pid, "direction": "inlet"|"outlet"|"config", "flow_type": port.flow_type.value}`). **Step 4:** register `farmhands/` in the library `__init__.py`. **Step 5:** run → pass. **Step 6:**

```bash
uv run ruff check barn/haybale-graph-editor/ tests/farmhand/ && uv run ruff format barn/haybale-graph-editor/ tests/farmhand/
uv run pytest -m "not browser and not perf" -q
git add -A barn/haybale-graph-editor tests/farmhand/
git commit -m "feat(farmhand): graph_editor farmhand tools — query, structural edits, set_property, promotion, shared undo/redo"
```

---

### Task 14: Resources — library docs + component canons

**Files:**
- Modify: `packages/haywire-studio/src/haywire_studio/farmhand/host.py` (`_register_handlers` gains list_resources/read_resource)
- Create: `barn/haybale-testing/haybale_testing/OVERVIEW.md` (two short paragraphs describing the testing library) — docs live INSIDE the library folder (`identity.folder_path`); this makes the library-docs resource family integration-testable.
- Test: `tests/farmhand/test_resources.py`

**Interfaces:**
- Consumes: `read_canon`/`list_canon_areas` (Task 3); `LibraryRegistry.list_names()/get_library_identity()/is_library_enabled()`; SDK `types.Resource`; `@server.list_resources()` / `@server.read_resource()` decorators (verify handler signatures against the installed SDK: `uv run python -c "from mcp.server.lowlevel import Server; import inspect; s=Server('x'); print(inspect.signature(s.read_resource))"`).
- Produces: URI families `farmhand://docs/canon/{area}` and `farmhand://library/{lib_id}/overview|quickref`. `resources/list_changed` already rides Task 8's notifier.

- [ ] **Step 1: failing tests**

```python
# tests/farmhand/test_resources.py
"""Resource families: component canons and installed-library docs."""

import pytest

pytestmark = pytest.mark.integration


def test_canon_resources_listed_and_readable(farmhand_call):
    async def scenario(session, init):
        listing = await session.list_resources()
        uris = [str(r.uri) for r in listing.resources]
        assert "farmhand://docs/canon/nodes" in uris
        content = await session.read_resource("farmhand://docs/canon/nodes")
        return content

    content = farmhand_call(scenario)
    text = content.contents[0].text
    assert "worker" in text


def test_library_overview_resource(farmhand_call):
    async def scenario(session, init):
        listing = await session.list_resources()
        uris = [str(r.uri) for r in listing.resources]
        assert "farmhand://library/testing/overview" in uris
        content = await session.read_resource("farmhand://library/testing/overview")
        return content.contents[0].text

    assert len(farmhand_call(scenario)) > 0
```

(`read_resource` may require an `AnyUrl` — pass `pydantic.AnyUrl("farmhand://...")` if the plain string is rejected; adjust from the first failure message.)

- [ ] **Step 2:** run → fail (resources list empty). **Step 3:** implement in `_register_handlers`:

```python
        @self._server.list_resources()
        async def list_resources() -> list[types.Resource]:
            self._track_session()
            from haywire.core.docs.canons import list_canon_areas
            from haywire.core.library.registry import LibraryRegistry
            from pathlib import Path

            resources = [
                types.Resource(
                    uri=f"farmhand://docs/canon/{area}",
                    name=f"{area} authoring canon",
                    mimeType="text/markdown",
                )
                for area in list_canon_areas()
            ]
            registry = self._library_service.injector.get(LibraryRegistry)
            for lib_id in registry.list_names():
                if not registry.is_library_enabled(lib_id):
                    continue
                folder = Path(registry.get_library_identity(lib_id).folder_path)
                for slug, filename in (("overview", "OVERVIEW.md"), ("quickref", "QUICKREF.md")):
                    if (folder / filename).exists():
                        resources.append(
                            types.Resource(
                                uri=f"farmhand://library/{lib_id}/{slug}",
                                name=f"{lib_id} {slug}",
                                mimeType="text/markdown",
                            )
                        )
            return resources

        @self._server.read_resource()
        async def read_resource(uri) -> str:
            self._track_session()
            from haywire.core.docs.canons import read_canon
            from haywire.core.library.registry import LibraryRegistry
            from pathlib import Path

            text = str(uri)
            if text.startswith("farmhand://docs/canon/"):
                return read_canon(text.rsplit("/", 1)[1])
            if text.startswith("farmhand://library/"):
                _, _, rest = text.partition("farmhand://library/")
                lib_id, _, slug = rest.partition("/")
                filename = {"overview": "OVERVIEW.md", "quickref": "QUICKREF.md"}.get(slug)
                registry = self._library_service.injector.get(LibraryRegistry)
                if filename and lib_id in registry.list_names():
                    path = Path(registry.get_library_identity(lib_id).folder_path) / filename
                    if path.exists():
                        return path.read_text(encoding="utf-8")
            raise Exception(f"[resource_not_found] No resource at '{text}'")
```

(Hoist the repeated imports to module level while implementing.) Create `barn/haybale-testing/haybale_testing/OVERVIEW.md`. **Step 4:** run → pass. **Step 5:**

```bash
uv run ruff check packages/haywire-studio/ tests/farmhand/ && uv run ruff format packages/haywire-studio/ tests/farmhand/
uv run pytest tests/farmhand/ -q && uv run pytest -m "not browser and not perf" -q
git add -A packages/haywire-studio barn/haybale-testing tests/farmhand/
git commit -m "feat(farmhand): canon + installed-library-docs resource families with list_changed"
```

---

### Task 15: Final verification, glossary touch, follow-up ledger

**Files:**
- Modify: `docs/reference/glossary.md` (line ~174: drop the "*(planned — spec effort …)*" marker from the Farmhand section header; the entries themselves are already accurate)
- Test: everything

- [ ] **Step 1: Full quality gates (the /verify set)**

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-TEST_A/haybale_test_a/
uv run pytest
```

Expected: all clean/green, including the browser harness (Farmhand added no browser tests but must not have broken the ordering rules).

- [ ] **Step 2: Manual end-to-end smoke against a real client**

Start `uv run haywire` in a scratch workspace; run the printed `claude mcp add …` line; in Claude Code run `/mcp` and confirm the farmhand server connects, `studio_status` answers, and `@farmhand:farmhand://docs/canon/nodes` resolves. This is the spec's copilot-first acceptance moment — do it once, note the result in the commit message.

- [ ] **Step 3: Glossary + follow-ups, final commit**

Update the glossary header, and revise the **MCP tool** entry to record the settled vocabulary: canonical term **farmhand** (a library-contributed MCP tool; `farmhands/` folder, `{lib_id}:farmhand:{name}` keys, `@farmhand` decorator), with "MCP tool" kept as the protocol-facing synonym. Record the deliberate leftovers where the team tracks later work (spec §8 already lists them; add the one new item): **settings-UI display of the connection command** (this plan prints it to console + `studio_status` instead). Then:

```bash
git add docs/reference/glossary.md
git commit -m "docs(farmhand): glossary status — Farmhand implemented; note connection-hint UI follow-up"
```

---

## Task dependency order

1 → 2 → 3 are independent of each other (any order) but all precede 4. Then strictly: 4 → 5 → 6 → 7 → 8 → 9 → 10. Tasks 11, 12, 13 depend on 10 (fixtures) and are mutually independent (13's tests import 12's create/close tools — run 12 before 13, or 12 ∥ 11). 14 depends on 10 (and 3). 15 last.



