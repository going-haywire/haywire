# S4 — Run Button, For Each File, Path Exists?, Output Path — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Batch building blocks in haybale-core: a click runs a flow, the flow iterates a folder's files,
skips files already done, and composes output paths — using only existing machinery (no VM change).

**Architecture:** Run Button is a TickEmit-shaped CONTROL node whose `Run` setting (BOOL, promoted as CONFIG,
new builtin `ButtonWidget`) is consumed by a node-owned thread that emits a callback to Tick Event listeners.
For Each File is a LOOPBACK node over a file list taken once at `execute`; it detects failed iterations by
`context.failures` (ADR 0066) growing between `loop_body` and re-entry. Path Exists? branches on a resolved
`PATH`; Output Path composes a `VolumePath` without touching the disk.

**Tech Stack:** Python 3.12, NiceGUI (widget only), haywire-core volumes (`resolve`, `VolumePath`),
`ProgressSettings`, pytest.

**Spec:** [2026-10-30-spandrel-haybale-design.md](2026-10-30-spandrel-haybale-design.md) §2.2 (decisions
S4-Q1–Q20 recorded there).

## Global Constraints

- No VM / assembly / interpreter change. S4 reads `ExecutionContext.failures` and uses existing hooks only.
- Barn code: absolute imports only (ruff TID252). Line length 109. Docstrings per `.claude/rules/python-docs.md`
  (node class docstrings are displayed → Markdown, UI words).
- Node files go under `barn/haybale-core/haybale_core/nodes/` (folder-scanned); non-node helpers go outside
  `nodes/`.
- Tests take node keys from `Cls.class_identity.registry_key` and `isinstance`-check the node (ErrorNode trap);
  barn classes imported at call time (`importlib.import_module`), never at module top.
- Tests never read repo `graphs/`; folders are built under `tmp_path` and exposed as volume
  `user:volume:scans` via `get_volume_store().add(...)` (see `tests/barn/test_path_demo_node.py`).
- No ADR, no glossary entry (S4-Q20).

## Decisions (S4-Q1–Q20, settled 2026-10-30)

| # | decision |
|---|---|
| Q1 | Run Button triggers a flow **in a running graph**; it never starts/stops the graph. |
| Q2 | The node gets its context TickEmit-style: `start` stores it, `stop`/`on_shutdown` drop it. |
| Q3 | Listener is the existing **Tick Event**; payload `{"delta_time": s since previous emit, 0.0 first}`; only Tick Event's description changes. |
| Q4 | Picked-up presses queue behind a running one (`BLOCK`, unchanged). |
| Q5 | The press is a BOOL setting promoted as CONFIG; a click writes `True` through the edit route (OPERATE gate server-side); the field subscription only sets a `threading.Event`; the node's thread does check → reset to `False` → emit. Clicks before pickup coalesce. `start` clears a stale press. Redo in EDIT mode fires a run (accepted). |
| Q5c | The thread stays (no nested write inside the press's own notification; the UI loop never waits on a full queue). |
| Q6 | `ButtonWidget` is a haywire-core builtin; key `BUTTON_WIDGET`. |
| Q7 | Ports mirror TickEmit: inlets `start`, `stop`, `callbacks`; outlets `started`, `stopped`. |
| Q8 | `pattern` = several name patterns separated by `;`, unioned, de-duplicated, sorted. |
| Q9 | Matching is always case-insensitive. |
| Q10 | Patterns match file **names** (a `/` or `\` in a pattern raises); `recursive` decides depth. |
| Q11 | Names starting with `.` are skipped at every depth. |
| Q12 | Symlinked folders are not entered; a symlinked file is listed only if it resolves inside the volume, else skipped with one warning. |
| Q13 | A folder that can't be listed (undefined volume, escape, missing, not a folder) raises. |
| Q14 | Outlets `loop_body`, `path`, `subdir`, `stem`, `extension`, `index`, `total`, `failed`, `completed`. |
| Q15 | `on_error` acts under `branch` bail only; `frame`/`run` abandon the loop. Nested failures count. |
| Q16 | `break_loop` inlet, as For Loop. `limit` 0 = all, applied after sorting. Listing taken once at `execute`. |
| Q17 | `on_frame_end` closes an abandoned loop's progress span and clears its state. |
| Q18 | Path Exists? uses plain `exists()`; an unresolvable path raises. |
| Q19 | Output Path validates its parts and raises naming the part; extension with or without dot; empty = none. |
| Q20 | Out of scope: macro, Save/Load, folder creation, double-click guard, the four optional toggles, any VM change. |

## Review Focus

1. **Run Button pressed while the graph is stopped**, then the graph started → the stale press must not fire
   (cleared by `start`); the button shows pending until then. → Task 2 test.
2. **Run Button `stop` → `start` again** (and graph Stop → Start: a new VM) → exactly one live thread, emitting
   on the new context; the old thread has exited. → Task 2 test.
3. **External-drive folder** with `._IMG_0001.JPG`, `.DS_Store`, `IMG_0002.JPG` and pattern `*.jpg` → only
   `IMG_0002.JPG`. → Task 5 test.
4. **For Each File run twice in one session** (second `execute` after a completed or abandoned loop) → `index`
   restarts at 0, `failed` holds only the second run's failures. → Task 6 test.
5. **Output Path fed from For Each File at the top level** (`subdir == ""`, `extension == ".JPG"`) →
   `out/IMG_0002_x4.JPG` with no `//` and case kept. → Task 3 test.

---

### Task 1: `ButtonWidget`

**Files:**
- Modify: `packages/haywire-core/src/haywire/barn/builtin/widget_keys.py` (add `BUTTON_WIDGET`)
- Modify: `packages/haywire-core/src/haywire/barn/builtin/widgets/basic_widgets.py` (add class after `SwitchWidget`)
- Modify: `packages/haywire-core/src/haywire/barn/builtin/widgets/__init__.py` (export)
- Test: `tests/barn/builtin/test_button_widget.py`; `tests/core/test_widget_keys.py` covers the key constant

**Interfaces:**
- Produces: `BUTTON_WIDGET = "haywire-core:widget:ButtonWidget"`; `ButtonWidget(BaseWidget)` for BOOL ports.
  Config `properties`: `text` (button label, default `"Run"`), `icon` (optional Material icon name).
  A click calls `self.set_value(True)`. While the model value is `True` the button shows pending
  (`loading` prop on); `False` shows it idle.

- [ ] **Step 1: Write the failing tests** (pattern: `tests/barn/builtin/test_widgets_hoisted.py` for building
  a widget against a port model)
  - `test_button_widget_key_matches_class` — add `BUTTON_WIDGET` to the parametrized cases in
    `tests/core/test_widget_keys.py`.
  - `test_click_writes_true` — render on a BOOL port at `False`; trigger the click handler →
    `port.get_value() is True`.
  - `test_pending_follows_model` — `on_model_changed(True)` → element prop `loading` truthy;
    `on_model_changed(False)` → falsy.
  - `test_refused_write_shows_model_value` — port whose `set_value` returns `False` → after click the
    button is not pending.
- [ ] **Step 2: Run** `uv run pytest tests/barn/builtin/test_button_widget.py tests/core/test_widget_keys.py`
  → FAIL (no `ButtonWidget`).
- [ ] **Step 3: Implement** `@widget(description="button widget") class ButtonWidget(BaseWidget)` with
  `build()` returning `ui.button(text, icon=...)` (`classes("w-full text-xs")`), `on("click")` →
  `set_value(True)`, and `on_model_changed(value)` toggling the `loading` prop. Docstring with config
  options and example, like `SwitchWidget`.
- [ ] **Step 4: Run** the same tests → PASS.
- [ ] **Step 5: Commit** `feat(widgets): ButtonWidget — a click writes true, pending while true`

---

### Task 2: Run Button (+ Tick Event description)

**Files:**
- Create: `barn/haybale-core/haybale_core/nodes/emits/run_button.py`
- Modify: `barn/haybale-core/haybale_core/nodes/events/tick_event.py` (description + docstring only)
- Modify: `barn/haybale-core/haybale_core/nodes/__init__.py` (export `RunButtonNode`)
- Test: `tests/core/test_execution/test_run_button.py`

**Interfaces:**
- Consumes: `BUTTON_WIDGET` (Task 1).
- Produces: `RunButtonNode` — `@node(label="Run Button", menu="core/emit", node_type=NodeType.CONTROL)`.
  - Inlets `start`, `stop` (EXEC); `callbacks` (`PooledType[CALLBACK]`, label "Trigger").
    Outlets `started`, `stopped` (EXEC).
  - Settings bag `button` (nested `NodeSettings`) with
    `run = setting[BOOL](False, label="Run", promotable=Promotable.CONFIG, promote_default=PortType.CONFIG,
    widget={"key": BUTTON_WIDGET})`.
  - `_consume(self) -> bool` — if `self.button.run` is `True`: set it `False`, emit
    `context.emit_callback(event_name=name, payload={"delta_time": d})` to every callback name, return `True`;
    else `False`. The thread's loop body; tests call it directly.
  - Thread name `RunButton-<node_id>`; lifecycle copied from `TickEmitNode` (`_lock`, per-thread stop
    `Event`, `_handle_start` / `_handle_stop` / `_stop_thread`, `on_shutdown`, `on_teardown`).
  - `post_init` subscribes `self.button._subscribe_field("run", ...)`; the callback only sets the wake
    `Event` when the new value is `True`.
  - `_handle_start`: clears `button.run` before starting the thread; already running → returns `"started"`
    without a second thread.

- [ ] **Step 1: Write the failing tests** (thread helpers as in `test_tick_emit_start_stop.py`; context is a
  `SimpleNamespace(control_pin=..., emit_callback=recorder)`)
  - `test_press_emits_once_to_every_callback` — two callback names wired; start; set `button.run = True` →
    within 1 s recorder has exactly one call per name, payload `{"delta_time": 0.0}`; `button.run is False`.
  - `test_second_press_reports_time_since_previous` — two presses ≥ 50 ms apart → second payload
    `delta_time >= 0.05`.
  - `test_presses_before_pickup_coalesce` — not started; `run = True` twice; `_consume()` → `True` once,
    then `False`.
  - `test_start_clears_a_stale_press` — `run = True` while stopped; start; wait 200 ms → recorder empty,
    `run is False`.
  - `test_stop_ends_the_thread_and_restart_has_one` — start, stop → no `RunButton-` thread alive; start
    twice → exactly one alive; `on_teardown` → none.
  - `test_press_while_stopped_emits_nothing` — never started; `run = True`; wait 200 ms → recorder empty,
    `run is True` (pending stays visible).
  - `test_promoted_as_config_with_button_widget` — node has a CONFIG port for `run` whose `widget_key` is
    `BUTTON_WIDGET`.
- [ ] **Step 2: Run** `uv run pytest tests/core/test_execution/test_run_button.py` → FAIL (no module).
- [ ] **Step 3: Implement** `RunButtonNode` per Interfaces. Displayed docstring explains the wiring
  (`BeginPlay → start`, `Tick Event.listen → Trigger`) and that a click while the graph is stopped waits
  and is cleared on `start`. Tick Event: description "Triggered by a connected emitter (Tick Emit, Run
  Button)"; docstring says `delta_time` is the time since the emitter's previous trigger.
- [ ] **Step 4: Run** the test file → PASS; also `uv run pytest tests/core/test_execution/test_tick_emit_start_stop.py`.
- [ ] **Step 5: Commit** `feat(core): Run Button — a button that triggers Tick Event flows in a running graph`

---

### Task 3: Output Path

**Files:**
- Create: `barn/haybale-core/haybale_core/nodes/output_path.py`
- Modify: `barn/haybale-core/haybale_core/nodes/__init__.py`
- Test: `tests/barn/test_output_path_node.py`

**Interfaces:**
- Produces: `OutputPathNode` — `@node(label="Output Path", menu="core/paths", node_type=NodeType.DATA)`.
  Inlets `folder` (`FOLDER_PATH`), `subdir`, `stem`, `suffix`, `extension` (`STRING`, default `""`).
  Outlet `path` (`FILE_PATH`). Worker raises `ValueError` naming the part.
- Rules: result volume = `folder.volume`; relative = `folder.relative / subdir / stem+suffix+ext` joined with
  `/`, empty segments dropped; `ext` = `""` if `extension` is empty or only dots, else `"." + extension.lstrip(".")`.
  Errors: empty `stem` → `"stem is empty"`; `/`, `\` or NUL in `stem`/`suffix`/`extension` →
  `"<part> contains '/'"` (etc.); `subdir` absolute (POSIX `/…` or Windows drive) → `"subdir is absolute"`;
  `..` segment in `subdir` → `"subdir contains '..'"`.

- [ ] **Step 1: Write the failing tests** (call `node.worker(MagicMock(), folder=..., subdir=..., ...)`, read
  `node.ports["path"].get_value()`)
  - `test_composes_folder_subdir_stem_suffix_extension` — `VolumePath(SCANS,"out")`, `"a/b"`, `"img"`,
    `"_x4"`, `"png"` → `VolumePath(SCANS, "out/a/b/img_x4.png")`.
  - `test_top_level_from_for_each` (Review Focus 5) — subdir `""`, stem `"IMG_0002"`, suffix `"_x4"`,
    extension `".JPG"` → `"out/IMG_0002_x4.JPG"`.
  - `test_extension_forms` — `"png"`, `".png"`, `"..png"` → `.png`; `""` → no extension.
  - `test_empty_segments_collapse` — folder relative `""`, subdir `"a//b/"` → `"a/b/img.png"`.
  - `test_rejects` — parametrized: empty stem, `"a/b"` stem, `"x\\y"` suffix, NUL in extension,
    subdir `"/abs"`, subdir `"C:/x"`, subdir `"a/../b"` → `pytest.raises(ValueError, match=<part>)`.
- [ ] **Step 2: Run** `uv run pytest tests/barn/test_output_path_node.py` → FAIL.
- [ ] **Step 3: Implement** `OutputPathNode`. Displayed docstring shows the mirror pattern
  (For Each File `subdir`/`stem`/`extension` → Output Path) and says nothing is created on disk.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(core): Output Path — compose a file path inside a folder's volume`

---

### Task 4: Path Exists?

**Files:**
- Create: `barn/haybale-core/haybale_core/nodes/path_exists.py`
- Modify: `barn/haybale-core/haybale_core/nodes/__init__.py`
- Test: `tests/barn/test_path_exists_node.py`

**Interfaces:**
- Produces: `PathExistsNode` — `@node(label="Path Exists?", menu="core/control/branch",
  node_type=NodeType.CONTROL)`. Inlets `exec` (EXEC), `path` (`PATH`). Outlets `exists`, `missing` (EXEC).
  Worker returns `"exists"` if `resolve(path).exists()` else `"missing"`; `VolumeError` propagates.

- [ ] **Step 1: Write the failing tests**
  - `test_file_exists` / `test_folder_exists` → `"exists"`; `test_missing` → `"missing"`.
  - `test_undefined_volume_raises` — `VolumePath("user:volume:nowhere","a")` → `VolumeUndefinedError`.
  - `test_escape_raises` — `VolumePath(SCANS,"../x")` → `VolumeEscapeError`.
  - `test_accepts_file_and_folder_path_wires` — an edge from Output Path's `path` (`FILE_PATH`) to `path`
    is created without an adapter.
- [ ] **Step 2: Run** `uv run pytest tests/barn/test_path_exists_node.py` → FAIL.
- [ ] **Step 3: Implement** `PathExistsNode`; docstring shows the resume pattern
  (`For Each File → Path Exists? →(missing)→ Save`).
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(core): Path Exists? — branch on whether a path is there`

---

### Task 5: File listing

**Files:**
- Create: `barn/haybale-core/haybale_core/file_listing.py` (outside `nodes/`: not a node)
- Test: `tests/barn/test_file_listing.py`

**Interfaces:**
- Produces: `list_files(root: Path, pattern: str, *, recursive: bool) -> list[PurePosixPath]` — the files
  under `root` (already resolved) whose name matches any pattern, as POSIX paths relative to `root`, sorted
  by their string form, de-duplicated. Raises `ValueError("pattern '<p>' contains '/'")` for a `/` or `\`
  in a pattern. An empty pattern string (after splitting on `;` and trimming) means `*`.
- Algorithm: own `os.scandir` walk. Skip any entry whose name starts with `.`. A symlinked folder is never
  entered. A symlinked file is listed only if `Path(entry).resolve().is_relative_to(root)`; otherwise skipped
  with one `logger.warning` naming it. Names match with `fnmatch.fnmatchcase(name.casefold(), p.casefold())`.
  An `OSError` on a subfolder skips that subfolder with a warning; on `root` itself it propagates.

- [ ] **Step 1: Write the failing tests** (build trees in `tmp_path`)
  - `test_patterns_union_sorted_deduped` — `a.png b.JPG c.txt`, pattern `"*.png; *.jpg;*.png"` →
    `["a.png", "b.JPG"]`.
  - `test_case_insensitive` — `IMG.JPG` matches `*.jpg`.
  - `test_recursive_flag` — `x/y/a.png`: `recursive=False` → `[]`; `True` → `["x/y/a.png"]`.
  - `test_dot_names_skipped` (Review Focus 3) — `._IMG_0001.JPG`, `.DS_Store`, `.hidden/a.jpg`,
    `IMG_0002.JPG`, pattern `*.jpg`, recursive → `["IMG_0002.JPG"]`.
  - `test_symlinked_folder_not_entered` — `link -> sub/` with `sub/a.png`, recursive → `["sub/a.png"]` only.
  - `test_outward_symlinked_file_skipped_with_warning` — `out.png -> <outside>/o.png` → not listed,
    `caplog` has one warning naming `out.png`; an inward file link is listed.
  - `test_slash_in_pattern_raises`; `test_empty_pattern_means_all`.
- [ ] **Step 2: Run** `uv run pytest tests/barn/test_file_listing.py` → FAIL.
- [ ] **Step 3: Implement** `list_files`.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(core): list a folder's files by name patterns, skipping hidden and outward links`

---

### Task 6: For Each File

**Files:**
- Create: `barn/haybale-core/haybale_core/nodes/for_each_file.py`
- Modify: `barn/haybale-core/haybale_core/nodes/__init__.py`
- Test: `tests/core/test_execution/test_for_each_file.py`

**Interfaces:**
- Consumes: `list_files` (Task 5); `ArrayType` from `haybale_core.types`; `ProgressSettings`,
  `progress_field` from `haywire.barn.builtin.progress`; `resolve`, `VolumePath` from `haywire.core.volumes`.
- Produces: `ForEachFileNode` — `@node(label="For Each File", menu="core/control/loops",
  node_type=NodeType.LOOPBACK)`.
  - Inlets: `execute`, `break_loop` (EXEC); `folder` (`FOLDER_PATH`); `pattern` (`STRING`, default `"*"`);
    `recursive` (`BOOL`, `False`); `limit` (`INT`, 0); `on_error` (`STRING` with `SelectWidget` options
    `["continue", "stop"]`, default `"continue"`).
  - Outlets: `loop_body` (EXEC, `needs_loopback=True`); `path` (`FILE_PATH`); `subdir`, `stem`, `extension`
    (`STRING`); `index`, `total` (`INT`); `failed` (`ArrayType[FILE_PATH]`); `completed` (EXEC).
  - `progress = bag(ForEachProgress)` with one `progress_field("Progress")`.
- Worker by `context.control_pin`:
  - `"execute"`: resolve `folder` (a `VolumeError` propagates); not a directory → `NotADirectoryError`
    (`"folder '<str(folder)>' does not exist"` / `"… is not a folder"`); list, apply `limit`; reset state
    (`failed=[]`, index 0); open a `ProgressSpan` (`busy("main", "<n> files")`); go to *emit*.
  - `"break_loop"`: *finish*.
  - `None` (loopback return): if `len(context.failures) > snapshot` append the current path to `failed`;
    if so and `on_error == "stop"` → *finish*; else advance; past the end → *finish*; else *emit*.
  - *emit*: write `path` (`VolumePath(folder.volume, folder.relative/rel)` with empty parts dropped),
    `subdir` (`str(rel.parent)` or `""`), `stem` (`rel.stem`), `extension` (`rel.suffix`), `index`,
    `total`; `span.step(index / total)`; snapshot `len(context.failures)`; return `"loop_body"`.
  - *finish*: write `failed`; close the span; clear state; return `"completed"`.
- `on_frame_end(context)`: if a loop is open, close the span and clear state (Q17).

- [ ] **Step 1: Write the failing tests** — reuse the `_Runner` / `_add` / `_edge` / `_record_runs` pattern
  from `tests/core/test_execution/test_exception_bail.py` (copy the helpers; BeginPlay → For Each File;
  body: `BenchSinkNode` fed from `path` or `index`; `completed` → a second sink). Folder: `tmp_path` as
  volume `user:volume:scans` with `a.png`, `b.png`, `sub/c.png`, `d.txt`.
  - `test_iterates_matching_files_in_order` — pattern `*.png`, recursive → body sees `a.png, b.png,
    sub/c.png`; `subdir` `"" "" "sub"`; `total == 3`; completed once.
  - `test_limit` — `limit=2` → two iterations, `total == 2`.
  - `test_continue_records_failed_and_goes_on` — body sink's worker raises for `b.png` → body runs for
    `a.png`, `sub/c.png`; `failed == [VolumePath(SCANS,"b.png")]`; completed once.
  - `test_stop_ends_at_first_failure` — `on_error="stop"` → body ran `a.png` only; `failed == [b.png]`;
    completed once.
  - `test_frame_bail_abandons_and_closes_progress` — `_Runner(..., bail="frame")`, raise on `b.png` →
    completed never; afterwards the progress field is idle (`active is False`).
  - `test_break_loop` — wire body sink's exec out → `break_loop` after first iteration → one iteration,
    completed.
  - `test_second_run_starts_fresh` (Review Focus 4) — fire once with a failure, fire again with none →
    second run's index starts at 0 and `failed == []`.
  - `test_unlistable_folder_raises` — undefined volume, missing folder, a file as folder → `ctx.failures`
    has the For Each node with `VolumeUndefinedError` / `NotADirectoryError`; body never ran.
- [ ] **Step 2: Run** `uv run pytest tests/core/test_execution/test_for_each_file.py` → FAIL.
- [ ] **Step 3: Implement** `ForEachFileNode`. Displayed docstring: what each inlet does (patterns are names,
  `;`-separated, case-insensitive; hidden names skipped; `on_error` acts when the graph's *On exception* is
  `branch`), the outlets, and the resume pattern.
- [ ] **Step 4: Run** → PASS; also `uv run pytest tests/core/test_execution/test_exception_bail.py`.
- [ ] **Step 5: Commit** `feat(core): For Each File — loop over a folder's files, collecting failures`

---

### Task 7: Docs, spec status, full suite

**Files:**
- Modify: `docs/architecture/execution/callbacks/callbacks-arch.md` — Tick Event is a generic callback
  listener (Tick Emit, Run Button); a callback emitted into a full `BLOCK` queue waits up to 5 s, so nodes
  emit from a thread they own, never from the UI loop.
- Modify: `docs/components/nodes/node-canon.md` — `on_frame_end` runs after a bail and after a stop's
  cancel too: the place to close per-frame state such as an open loop.
- Regenerate: `uv run haywire docs barn/haybale-core` (four new node pages + Tick Event).
- Modify: `docs/superpowers/plans/2026-10-30-spandrel-haybale-design.md` §3 — S4 row → `done` with merge
  commit hash and date; deviations, if any, under §2.2 "S4 deviations from plan".

- [ ] **Step 1:** Write the two docs edits; regenerate haybale-core docs; `uv run mkdocs build --strict`
  → no warnings from the touched pages.
- [ ] **Step 2:** Baseline gates: `uv run ruff check . && uv run ruff format --check .`; mypy command from
  CLAUDE.md → clean.
- [ ] **Step 3:** `uv run pytest -m "not browser and not perf" -n 4 -q > /tmp/t.log 2>&1; echo "exit=$?"`
  → `exit=0`; `uv run pytest -m browser -n 4` → pass.
- [ ] **Step 4:** Live check in the studio (`haywire-live-studio`): BeginPlay → Run Button.start; Tick Event
  → For Each File (`scans` volume) → Path Exists? (fed by Output Path) →(missing)→ Print. Start, click Run →
  the progress bar runs and each file takes `exists` or `missing` as the disk says (Save arrives in S5);
  click Run twice quickly → one run; click while stopped → pending, cleared on Start; in VIEW mode the
  button refuses.
- [ ] **Step 5:** Update the spec's §3 S4 row (`done`, hash, date) and deviations; commit
  `docs(batch): S4 nodes — callbacks, frame-end hook, generated node docs; S4 done`.
