# FileWatcher: Move the Extension Filter to the Dispatcher

> **Status: LANDED**, 2026-08-09 — commits `236d1d0a`, `706946ab`, `1509b265`.
> The Task 1 blocking question was answered **B**: `_validate_python_file` returns
> `False` for both cases, and `event_dispatcher` distinguishes them — a non-`.py`
> returns silently at the top guard, a `.py` that will not parse raises so the
> ledger keeps its `CLASS_RELOAD_FAILED`.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** `LibraryFileHandler` stops asserting what kind of file matters. It routes
every non-directory event to whichever registries claim the folder; the `.py`
assertion moves to `BaseRegistry`, the consumer that actually only handles Python
modules. The `haybale.toml` metadata refresh stops being an escape hatch beside the
dispatch mechanism and becomes a normal `HotReloadRegistry` on the root fallback.

**Architecture:** Design B from the handoff note. Three commits, each green on its
own: (1) harden the downstream guard — a standalone bug fix; (2) delete `.py` from
the router; (3) replace the callback with an adapter registry.

**Tech Stack:** Python 3.12, watchdog, threading.Timer debounce, pytest.

## Source Documents

- Handoff: filewatcher-extension-filter-belongs-in-the-dispatcher.md
- The handoff's design A (per-mapping `extensions=` tuple) was considered and
  rejected there; this plan does not revisit it.

## Global Constraints

- Line length 109 (`uv run ruff check .` **and** `uv run ruff format --check .` — CI runs both).
- Type-check with the exact command in `CLAUDE.md`; `haybale-visiongraph` is excluded.
- Gate before every commit: `uv run pytest -m "not browser and not perf"` (~2.5 min).
- Never call `create_test_injector()` directly in a test — use the `test_injector` fixtures.
- The handler runs on the **watchdog observer thread**. Nothing added to it may block,
  and no callback may be allowed to take that thread down.

## Corrections to the handoff note

The handoff's stated premise for design B is wrong in one load-bearing place, and the
plan depends on the correction. Both must be fixed in the note itself (Task 0).

**1. `event_dispatcher` does NOT already guard itself.** The note says
`_validate_python_file` makes the handler's `.py` test "a cheap pre-filter, not a
correctness guarantee." It is not. At
`folder_scan.py:194-206`
the `try` wraps only the `open()`/`read()` for `OSError`. `ast.parse` sits **outside**
it. Given a `.toml` or a `.png`, `ast.parse` raises, the exception propagates into
`event_dispatcher`'s `except Exception` at
`registry/base.py:437`,
and that branch **manufactures a `CLASS_RELOAD_FAILED` lifecycle event** and pushes it
to subscribers. A non-`.py` file reaching a registry today surfaces as a fake reload
failure in the error ledger, not a quiet rejection.

**2. `resolve_module_name` does not reliably yield an absent module.** The note claims
a non-module "yields something absent from `sys.modules`." It strips the suffix via
`.stem` (`folder_scan.py:186`),
so `foo/nodes.toml` resolves to `pkg.foo.nodes` — colliding with the real `nodes.py`,
which *is* in `sys.modules`. That is a live mis-reload of the wrong module.

**Consequence for sequencing:** step 2 of the handoff (the explicit guard) is
load-bearing, not cosmetic. It must land **before or with** step 1, never after.
Doing step 1 first, on the note's stated reasoning that downstream is already safe,
opens exactly the two failures above across every library.

**3. Guard placement is constrained.** `event_dispatcher` calls `resolve_module_name`
**before** `_validate_python_file` (`:389` vs `:402`), and skips validation entirely
for `DELETED` (`:401`). So a validator-only guard would let a `haybale.toml` DELETE
sail into `_on_delete("pkg.haybale")`. The guard must sit at the **top** of
`event_dispatcher`, before `resolve_module_name`.

**4. No import cycle; skip the `HotReloadRegistry` extraction.** The note hedges about
moving `HotReloadRegistry` into `core/registry/hot_reload.py` to avoid a
`library.base` → `registry.base` cycle. There is no cycle:
`library/base.py:9-12`
already imports `BaseRegistry` and `FileEventType` from `registry.base`, and nothing in
`registry/base.py` imports `library.base`. Subclass it in place. No module move, no
compatibility re-export.

**5. Root fallback is the correct home for the adapter** (confirming the note, against
an early doubt). `_get_matching_registries` gives folder mappings priority and
exclusivity — if any folder mapping matches, root fallbacks are never consulted
(`file_watcher.py:124-125`).
That would starve a root-fallback adapter *if* a library registered its own root as a
component folder. None do: every `register_components()` registers **subfolders**
(`base_path / "nodes"`, `base_path / "types"`, …) — see
`haybale_testing/__init__.py:34-78`.
`haybale.toml` sits at the root, matches no folder mapping, and reaches the fallback.

> **Invariant this introduces:** a library must never register its own root via
> `add_folder_to_registry`. Task 5 adds the assertion that makes that explicit rather
> than tacit.

## Out of scope

- Design A (per-mapping extension tuples).
- Making `BaseLibrary` itself a `HotReloadRegistry` — rejected in the handoff; a
  library is a plugin host, not a registry.
- Any change to what `_reload_metadata` refreshes (`label`, `linked_libraries`,
  `on_reload`). Behaviour is preserved exactly; only the delivery path changes.
- Widening the adapter to other root files (`pyproject.toml`, `README.md`).

---

## Task 0: Correct the handoff note

- [x] Rewrite the "Why it is still not right" and "B — drop the filter entirely"
      sections of
      internals/handoff/filewatcher-extension-filter-belongs-in-the-dispatcher.md
      to carry corrections 1–5 above.
- [x] Add a `**Superseded by:** docs/superpowers/plans/2026-08-09-filewatcher-extension-filter-to-dispatcher.md`
      line under **Status**.

The note is the reasoning of record. Leaving "the correctness is already downstream"
in it invites the exact wrong sequencing on the next read.

---

## Commit 1 — Harden the downstream guard

Standalone bug fix. Green on its own, with the handler untouched.

### Task 1: `_validate_python_file` rejects instead of raising

- [x] In `folder_scan.py:194`,
      return `False` for a non-`.py` suffix before reading, and wrap `ast.parse` in
      `except SyntaxError: return False`.

```python
def _validate_python_file(self, file_path: str | Path) -> bool:
    """Check the file is a Python module that compiles.

    Returns False rather than raising: a caller uses this to *decide*, and a
    mid-keystroke syntax error is expected, not exceptional.
    """
    if Path(file_path).suffix != ".py":
        return False
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            source_code = f.read()
    except OSError as e:
        logger.error(f"Error reading {file_path}: {e}")
        return False
    try:
        ast.parse(source_code, filename=file_path)
    except SyntaxError as e:
        logger.error(f"Syntax error in {file_path}: {e}")
        return False
    return True
```

- [x] Check `Path` is imported in `folder_scan.py` (it is — used at `:159`).

**Note this is a live behaviour change independent of the refactor.** A syntax error
mid-edit currently escapes the validator and takes `event_dispatcher`'s exception
path; after this it takes the clean `return None` at `:407`. That is the intended
outcome — the `:402` call site already reads as "if not valid, skip" — but it means
an author saving a broken file now gets a logged skip rather than a
`CLASS_RELOAD_FAILED` in the ledger.

- [x] **Confirm with the user before proceeding** whether losing that ledger entry is
      acceptable, or whether the syntax-error case should keep producing a
      `CLASS_RELOAD_FAILED` (in which case `event_dispatcher` must raise it explicitly
      at the `:402` branch rather than relying on the validator to throw). This is the
      one genuinely ambiguous decision in the plan; everything else follows from it.

### Task 2: Guard the top of `event_dispatcher`

- [x] At the top of
      `registry/base.py:366`,
      before the `logger.info` and before `resolve_module_name`:

```python
if not event.file_path.endswith(".py"):
    # Not a Python module — nothing here to reload. The watcher is a router
    # and offers us every file under the folders we claimed; deciding that
    # only modules matter is this registry's business, not the router's.
    return None
```

Placement is not free choice — see correction 3. Before `resolve_module_name`, because
`DELETED` skips validation entirely.

### Task 3: Tests for the guard

- [x] New `tests/core/test_libraries/test_dispatcher_extension_guard.py`:
  - [x] a `.toml` MODIFIED event returns `None`, dispatches nothing, and pushes **no**
        lifecycle event to subscribers (the regression that correction 1 describes)
  - [x] a `.toml` DELETED event does not reach `_on_delete` (correction 3)
  - [x] a `.py` file whose stem collides with a `.toml` sibling still reloads normally
        (correction 2 — proves the collision path is closed)
  - [x] `_validate_python_file` returns `False`, not raises, for: a `.toml`, a
        syntactically broken `.py`, and a missing file
- [x] Run `uv run pytest tests/core/test_libraries/ -q`.

### Task 4: Gate and commit

- [x] `uv run ruff check packages/haywire-core/src/haywire/core/registry/ tests/core/test_libraries/`
- [x] `uv run ruff format --check .`
- [x] `uv run mypy` (full command from `CLAUDE.md`)
- [x] `uv run pytest -m "not browser and not perf" -q > /tmp/t1.log 2>&1; echo "exit=$?"`
- [x] Commit: `fix(registry): the dispatcher rejects non-Python files instead of failing on them`

---

## Commit 2 — The router stops knowing about `.py`

### Task 5: Assert the root-is-not-a-component-folder invariant

- [x] In `BaseLibrary.add_folder_to_registry`
      (`library/base.py:197`),
      raise if `Path(folder_path).resolve() == Path(self.identity.folder_path).resolve()`.

Correction 5 shows the adapter's delivery depends on this holding. It holds today by
convention across every library; the assertion turns a silent future breakage — the
metadata refresh quietly never firing — into an error at registration.

- [x] Test: registering the root raises; registering a subfolder does not.

### Task 6: Delete `.py` from the four callbacks

- [x] `file_watcher.py:158`
      (`on_modified`), `:171` (`on_created`), `:184` (`on_deleted`), `:216-217`
      (`on_moved`) — remove the `endswith(".py")` tests.
- [x] `on_moved` loses the `src_is_py`/`dest_is_py` split. The two branches are now
      distinguished by what they *are*, not by suffix:
  - true rename → DELETED + CREATED (source was tracked, i.e. in `_known_files`)
  - atomic write → MODIFIED (source was not tracked)

  Use `_known_files` membership of `src_path` as the discriminator, which is what the
  suffix test was standing in for. Preserve the `_atomic_write_suppress` window and the
  `logger.info(f"File moved: ...")` line.
- [x] Update the class docstring: the handler routes **every** non-directory event.

### Task 7: Seed `_known_files` for all files, with exclusions

- [x] `file_watcher.py:75`
      — `rglob("*.py")` becomes `rglob("*")`, filtered to files.

`rglob("*")` on a library containing `.venv/`, `node_modules/`, or `__pycache__/`
walks the whole tree on every `add_folder_mapping`. Add a module-level exclusion:

```python
#: Directory names never walked when seeding _known_files. These hold no
#: source a registry could claim, and a library with a local virtualenv makes
#: the unfiltered walk cost real time on the enable path.
_UNWALKED_DIRS = frozenset({"__pycache__", ".venv", "venv", "node_modules", ".git", ".mypy_cache"})
```

- [x] Implement as an explicit `os.walk` with in-place `dirnames[:] = [...]` pruning —
      `rglob` cannot prune, so it would descend before filtering.
- [x] Test: a folder with a `.venv/` subdir seeds nothing from inside it, and seeding a
      tree with a large excluded dir does not walk into it.

### Task 8: Quiet the downgrade log

- [x] `file_watcher.py:178`
      — demote the CREATE→MODIFIED downgrade from `logger.info` to `logger.debug`.

The handoff (line 135) suggests a filtered-extension list to log selectively. Prefer
the demotion: it is one line, needs no table to maintain, and the message is
diagnostic detail nobody reads at INFO. If a filtered list is wanted later it can be
added without unpicking this.

### Task 9: Update the routing tests

- [x] `tests/core/test_libraries/test_file_watcher.py` — `test_non_python_file_ignored`
      (`:163`) now asserts the **opposite**: a non-Python file **is** routed to the
      registry, and the registry rejects it. Rename to
      `test_non_python_file_is_routed_and_rejected_downstream` and assert against a real
      `BaseRegistry.event_dispatcher`, not a `MagicMock` — the point of the test is the
      seam between the two.
- [x] The `_known_files` tests (`:362-405`) that name `.py` files keep passing; add one
      proving a `.md` is now tracked and downgraded like any other file.
- [x] The `on_moved` tests (`:249`, `:440`, `:470`) exercise the branch Task 6 rewrote —
      verify each still describes the intended behaviour, and add an atomic-write case
      where **neither** path ends in `.py`.

### Task 10: Gate and commit

- [x] Same four gate commands as Task 4.
- [x] Commit: `refactor(watcher)!: the file handler routes every file, not only .py`

The `!` is warranted: any out-of-repo `HotReloadRegistry` implementation now receives
non-Python events and must tolerate them. Note it in the commit body.

---

## Commit 3 — The metadata refresh becomes a registry

### Task 11: Add `_HaybaleTomlWatcher`

- [x] In `library/base.py`,
      above `BaseLibrary`:

```python
class _HaybaleTomlWatcher(HotReloadRegistry):
    """Turns a haybale.toml write into a metadata refresh.

    An adapter, not a base class: a library is a plugin host, not a registry,
    and this interface is one method — cheap to delegate, misleading to inherit.
    It rides the ordinary root-fallback dispatch so metadata changes travel the
    same path as everything else the watcher sees, rather than a second
    mechanism beside it.
    """

    def __init__(self, library: "BaseLibrary") -> None:
        self._library = library

    def event_dispatcher(self, event: FileChangeEvent) -> None:
        path = Path(event.file_path)
        if path.name != HAYBALE_TOML:
            return
        if path.parent != Path(self._library.identity.folder_path):
            # A nested library's file, seen because the watch is recursive.
            # Its own library owns it.
            return
        self._library._reload_metadata()
```

- [x] Hold it on `BaseLibrary.__init__` as `self._toml_watcher = _HaybaleTomlWatcher(self)`.
- [x] Do **not** move `HotReloadRegistry` to a new module — correction 4.

### Task 12: Register it on the root fallback

- [x] `_attach_to_registries`
      (`library/base.py:303-309`)
      — append `self._toml_watcher` to the registries list passed to `add_root_fallback`.

DELETED events must keep the previous values (there is an existing test). The adapter
gets DELETED like any other event; `_reload_metadata` already handles a missing file
via `HaybaleTomlError` → warn → keep previous. Verify rather than assume.

### Task 13: Delete the callback mechanism

- [x] `FileEventCallback` (`file_watcher.py:17-25`)
- [x] `LibraryFileHandler._claimed` (`:134-151`) and `self._on_file_event` (`:41`)
- [x] the `_claimed` calls in `on_modified` (`:156`), `on_created` (`:169`), `on_moved` (`:213`)
- [x] the `on_file_event` parameter on `LibraryFileHandler.__init__` and `FileWatcher.__init__` (`:315`)
- [x] `BaseLibrary._on_watched_file` (`library/base.py:237-255`)
      and the `on_file_event=` argument at `:61`
- [x] `FileEventType` import in `library/base.py` if now unused

### Task 14: Migrate the metadata tests to the debounce

`tests/core/test_libraries/test_watcher_metadata_refresh.py` (11 tests).

- [x] **Delete** the four asserting the callback contract — they describe a mechanism
      that no longer exists: `test_the_handler_routes_unclaimed_events_normally` (`:170`),
      `test_a_raising_callback_does_not_stop_the_watcher` (`:184`),
      `test_a_handler_without_a_callback_behaves_as_before` (`:204`), and
      `test_other_files_are_not_claimed` (`:159`).
- [x] **Keep, driving the debounce** — these are behaviour that must survive unchanged:
      `test_edit_refreshes_label_and_linked_libraries`, `test_the_identity_is_mutated_in_place`,
      `test_a_metadata_edit_does_not_trigger_a_module_reload`, `test_atomic_write_paths_are_covered`,
      `test_a_malformed_edit_logs_and_keeps_the_previous_values`,
      `test_a_deleted_file_keeps_the_previous_values`, `test_a_nested_librarys_file_is_not_claimed`
      (rename to `..._is_not_refreshed` — nothing "claims" anything now).
- [x] Drain the debounce rather than `time.sleep(0.6)` in seven tests. Seven sleeps is
      four seconds of suite time and a flake surface; see
      `.insights/project_slow_test_outliers.md`.

  **Deviation:** this was first built as a public `LibraryFileHandler.flush_debounce()`,
  then removed. It had no production caller, and draining after cancelling the timers
  needed a `_pending_registries` dict — a second map kept in step at three mutation
  sites, carried by production code purely for a test. The tests now use a local
  `_drain()` helper that cancels the timers and calls the real
  `_process_debounced_event`, so the dispatch under test is still the shipped one.
- [x] Update the module docstring: the library no longer installs a callback.

**Behaviour change to record:** `haybale.toml` refresh is now debounced (0.5s), where
the callback path was synchronous. This is an improvement — an editor's write-burst
collapses into one reload — but it is a change, and any caller expecting a synchronous
refresh after a write must now wait.

### Task 15: Gate, docs, and commit

- [x] Grep for stale references: `rg "on_file_event|_on_watched_file|FileEventCallback|_claimed" --glob '!*.pyc'`
      across `packages/`, `barn/`, `tests/`, `docs/`, `internals/`. Consider the
      `check-rename` skill — string-based references (`patch("…")`, doc citations) are
      exactly what it catches.
- [x] Update `docs/architecture/` hot-reload page if it documents the callback.
- [x] Delete the handoff note, or mark it **Done** with a pointer to this plan.
- [x] Same four gate commands as Task 4.
- [x] Commit: `refactor(library)!: haybale.toml refresh rides the normal dispatch path`

---

## Verification

Beyond the gate, confirm in a running studio (`.claude/skills/haywire-live-studio`):

- [x] Edit a barn library's `haybale.toml` label; it updates within ~0.5s with no module
      reload in the log.
- [x] Edit a node `.py` in the same library; it hot-reloads as before.
- [x] Touch a `.md` in the library root; nothing reloads and no error reaches the ledger.
- [x] `barn/haybale-testing/` already contains a `.DS_Store` — confirm it produces no
      ledger entry and no INFO-level noise.

## Risks

| Risk | Mitigation |
| --- | --- |
| Task 1 changes syntax-error handling — a real behaviour change in the error ledger | Blocking question in Task 1; do not proceed on assumption |
| More events reach registries; each starts a debounce timer | Libraries are small dirs. Task 7's exclusions cap the walk. Measure if a library ever watches something large |
| An out-of-repo `HotReloadRegistry` breaks on non-`.py` events | Breaking-change commit message; the guard is in `BaseRegistry`, which every in-repo registry inherits |
| A future library registers its own root, silently starving the adapter | Task 5's assertion |
