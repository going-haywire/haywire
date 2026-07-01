# Settings Single-Cell Unification (P4) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move a `Settings` instance's per-field value out of the untyped `_local_store: dict[str, Any]` and into a per-field **`DataField` cell** (the same cell a port uses), so a setting and a port become two views of one value. Re-express `__get__`/`__set__`/`to_dict`/`from_dict`/`reset`/`is_locally_set` against cells, and **collapse the `_registry is None` dual-mode** (idea #1) and **recompute-on-read** (idea #3) in the same pass.

**Architecture:** Today every `Settings` instance holds `_local_store: dict[str, Any]`; the `setting` descriptor's `__get__` either walks the registry chain (`_resolve`, extended mode) or reads `_local_store` by attr-name (simple mode), and `__set__` writes a raw value into `_local_store[storage_key]`. The UI bridges this with a throwaway `DataField` (`SettingWidgetModel._field`, `setting_widget_model.py:47`) it copies values into and out of. This plan replaces `_local_store` with `_cells: dict[str, DataField]` — one cell per declared field, created at `Settings.__init__` from the field's IType. The **value lives in the cell**; `__get__` returns `cell-if-set else default` where `default` is the existing per-kind strategy (plain literal / `registry.resolve` for shadow/watch); `__set__` writes the cell; serialization reads/writes the cell via its `to_dict`/`from_dict`. The registry tiers are **untouched** (P2/P3 already settled them); only the *instance-local* store changes. **No backward-compat constraint on graph JSON within this branch** — the on-disk `{accessor: {field: value}}` settings-block shape is preserved (per-field value, IType-serialized), so existing saved graphs still load.

**Tech Stack:** Python 3, `pytest`, `ruff`, `mypy`. Haywire monorepo (`uv run` for all tooling).

## Global Constraints

- Line length 109 (`ruff`, configured in repo).
- CI runs BOTH `ruff check` AND `ruff format --check` — run both locally; they catch disjoint problems.
- mypy scope for this plan: `uv run mypy packages/haywire-core/src/`.
- In test files, import `haywire.core.graph.editor` before other haywire modules to avoid circular import errors.
- Settings tests share a `conftest.py` autouse fixture (`_reset_framework_settings_registry`). Do NOT remove it; new tests inherit it automatically.
- Stay on branch `feat/type-floor-hoist`. Do NOT merge to master between plans. The gate is "committed + green on this branch" (pytest + ruff + ruff format + mypy clean).
- **Reference:** `internals/ideas/settings-datafield-unification-DECISIONS.md` (**§A** = the `cell ?? default` model, **§C2/C3** = the cell-mutation spine that governs *why* a cell is never structurally reset) and `internals/ideas/settings-datafield-unification.md` (cleanups **#1/#3/#4**, "what this retires"). `internals/ideas/settings-datafield-unification-ROADMAP.md` (P4 section). P1 (canonical key `storage_key`), P2 (tier collapse, set-or-unset), and P3 (TOML→JSON, the IType `to_dict`/`from_dict` seam) have all landed on this branch and P4 builds on them.

## SCOPE — value-into-cell + dual-mode removal ONLY

The ROADMAP explicitly suggests splitting P4 into **"value-into-cell"** and **"dual-mode removal"**; this plan does both but **stops before promotion/ports**, which are **P5**. Read this table before Task 1:

| In scope (this plan) | Out of scope (P5 / deferred / untouched) |
| --- | --- |
| `_local_store` dict → `_cells: dict[str, DataField]` (Tasks 2–4) | Promotion = field + direction; the direction-eligibility matrix (§B) — **P5** |
| `__get__`/`__set__` read/write the cell (Task 3) | `_promoted_port_id` read-tier branch removal (`descriptor.py:328-333`) — see Task 5 note |
| `cell ?? default` resolution, dual-mode collapse (idea #1, Task 3) | `is_linked_lazy` / watch→outlet emit (§C4) — **P5** |
| hold-the-cell instead of recompute-on-read (idea #3, Task 3) | The DECISIONS §D *tier-stored `to_dict` form* + `resolve()`-returns-raw-dict (P4-of-§D); P3 kept disk-edge serialization. See "§D coordination" below. |
| `to_dict`/`from_dict`/`reset`/`is_locally_set` re-expressed on cells (Task 4) | `SettingWidgetModel`'s throwaway field → bind-to-cell directly (idea "retires" #4) — **Task 6 (optional, gated)** |
| `_mirror_descriptor`/`_mirror_key` stay on the descriptor (they are *declaration* metadata, §C "stays") | Splitting `Settings` responsibilities (idea #7, declined) |
| Registry tiers, `save_to_json`/`load_from_json`, `persistent_setting` (Tasks: untouched) | `_stored`/`_validator`/`_metadata` attribute retirement (§C) — orthogonal, not here |

## §D coordination (read before Task 3)

DECISIONS §D-A says "a tier stores the IType's `to_dict`; `resolve()` returns the **raw serialized form**; the consuming **field rehydrates via `from_dict`** when materializing into its cell." **P3 deliberately deviated** (ADR 0012): the registry tier holds the **live** Python value and `resolve()` returns it live, with `to_dict`/`from_dict` only at the disk edge.

**This plan keeps P3's disk-edge contract.** The cell still materializes from a live value: `registry.resolve()` already returns a live value (P3), so `_cells[key].set_value(resolved_live_value)` needs **no** `from_dict` hop. The §D "field rehydrates from a raw dict" step would only be needed if `resolve()` returned raw dicts — which it does not, and which this plan does not change. **The cell IS the "field that holds the value" §D refers to; §D is satisfied in substance once the value lives in a cell.** Record this in the ADR (Task 8): P4 lands the cell; the literal "tier stores `to_dict`" representation was judged unnecessary churn given P3's disk-edge seam already gives "one serialization contract." If a future reviewer wants the literal tier-stored-dict form, that is a separate, behavior-neutral registry-internal change — not gated by P4.

---

## The real surface (grep by symbol; line numbers may have drifted)

- `Settings.__init__` creates `_local_store` (`settings.py:71`). → create `_cells` here.
- `Settings._resolve` (`settings.py:79`) — registry chain, reads `_local_store[field_key]`.
- `Settings._on_field_change` (`settings.py:115`) — `if field_key in self._local_store: continue`.
- `Settings.to_dict` (`settings.py:177`), `from_dict` (`settings.py:204`), `reset` (`settings.py:233`), `is_locally_set` (`settings.py:264`) — all key off `_local_store`.
- `setting.__get__` (`descriptor.py:320`) — extended vs simple branch; `_promoted_port_id` read-tier branch (`328-333`, **leave for P5**).
- `setting.__set__` (`descriptor.py:340`) — writes `obj._local_store[self.storage_key]`.
- `persistent_setting.__set__` (`descriptor.py:~408`) — registry write; its `super().__set__` fallback writes `_local_store` (Task 3 keeps this working via the cell).
- `PrimitiveField` (`types/fields.py:171`) — the cell: `get_value`/`set_value`/`reset`/`has_data`/`to_dict`/`from_dict`. `IType.create_field(default_override=...)` builds one (`setting_widget_model.py:47` shows the constructor).
- `NodeData.__init__` (`node/data.py:71`) — instantiates each settings bag; bags exist before any port (this is what makes P5 reference-binding order-independent — do not disturb).
- `NodeBase._to_dict` (`node/base.py:315`) / `_initialize_from_dict` (`base.py:381`) — orchestrate `bag.to_dict()`/`bag.from_dict()`. The promoted-port re-bind (`base.py:361-380`) must keep working.
- Test references to `_local_store`: `tests/core/test_settings/test_settings.py`, `test_canonical_key.py`, `test_persistent_setting.py` (Task 7 sweeps these).

---

## Pre-edit baseline (run once before Task 1)

```sh
uv run ruff check packages/haywire-core/src/haywire/core/settings packages/haywire-core/src/haywire/core/types/fields.py packages/haywire-core/src/haywire/core/node
uv run mypy packages/haywire-core/src/
uv run pytest tests/core/test_settings/ tests/core/test_node/ tests/core/types/ packages/haywire-core/src/haywire/core/di/ -q
```

Expected: all clean. If anything fails here, STOP and surface it — it is pre-existing.

---

### Task 1: Characterization tests — pin current behavior before refactor

This is a pure refactor of *where the value lives*; observable behavior must not change. Write tests that pin the current `_local_store`-backed behavior through the **public** API (`getattr`/`setattr`/`to_dict`/`from_dict`/`reset`/`is_locally_set`/`subscribe`), so the cell migration is provably behavior-preserving. No production code changes in this task.

**Files:**
- Test: `tests/core/test_settings/test_single_cell.py` (Create)

**Interfaces:**
- Consumes: the existing `Settings`/`setting` public API only. No `_local_store` / `_cells` access (those are the implementation detail under test).

- [ ] **Step 1: Write the characterization tests**

Create `tests/core/test_settings/test_single_cell.py` covering, at minimum (use plain `Settings` subclasses in simple mode AND a registry-backed bag in extended mode — mirror the fixtures in `test_settings.py`):

- **Simple mode:** default read; `setattr` then read; `to_dict` returns only changed-from-default; `from_dict(silent=True)` restores without firing callbacks; `from_dict(silent=False)` fires; `reset(name)` returns to default and fires; `reset_all`; `is_locally_set` true after set / false after reset.
- **Extended mode (registry-backed):** read resolves through the chain when no local override; a local `setattr` overrides; `reset` drops the override and re-resolves to the tier value; `to_dict` writes only the locally-set field (not the inherited one); shadow field tracks a global change when unset and ignores it when set ("unset tracks; set ignores", `_on_field_change`).
- **Complex IType (the payoff):** a `setting[VEC2I]` / `setting[COLOR]` field round-trips through `to_dict`/`from_dict` losslessly (this is what the cell buys — it exercises `PrimitiveField.to_dict`/`from_dict`, the P3 seam, end-to-end at the instance level).
- **`subscribe` callback** fires on a write with `(name, value, old)`.

- [ ] **Step 2: Run — all must PASS against current code**

Run: `uv run pytest tests/core/test_settings/test_single_cell.py -v`
Expected: **PASS** (this pins current behavior; it is the regression net for Tasks 2–4).

- [ ] **Step 3: Commit**

```bash
git add tests/core/test_settings/test_single_cell.py
git commit -m "test(settings): characterize Settings value behavior before single-cell refactor

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Add the `_cells` store alongside `_local_store` (no behavior change yet)

Introduce a per-field `DataField` cell store and a helper to lazily create a field's cell from its IType, **without** yet routing reads/writes through it. This isolates the "build the cell" mechanics (IType → `DataField`, default seeding, the `_type is object` simple-mode case) into one reviewable step. `_local_store` remains the source of truth after this task.

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/settings/settings.py`
- Test: `tests/core/test_settings/test_single_cell.py`

**Interfaces:**
- Produces:
  - `Settings.__init__` gains `self._cells: dict[str, DataField] = {}`.
  - `Settings._cell_for(self, descriptor: setting) -> DataField | None` — returns (creating on first call) the cell for a field, built via `descriptor._type.create_field(default_override=...)` seeded from `descriptor._default`. Returns `None` when `descriptor._type is object` (un-typed simple-mode field — no IType to build a cell from; these keep using a plain value path, see Task 3).
- Consumes: `setting._type` (the IType, or the `object` sentinel), `setting._default`, `IType.create_field` (`fields.py` / `setting_widget_model.py:47` shows the call shape).

- [ ] **Step 1: Add a failing test for `_cell_for`**

Append to `test_single_cell.py` a test that calls `bag._cell_for(descriptor)` for a typed field and asserts it returns a `DataField` whose `get_value()` equals the descriptor default; and that a second call returns the **same** cell object (lazily cached). For an `object`-typed field (a plain `setting("x")` with no IType subscript), assert `_cell_for` returns `None`.

- [ ] **Step 2: Run — FAIL** (`_cell_for` / `_cells` don't exist).

- [ ] **Step 3: Implement `_cells` + `_cell_for`**

- In `__init__`, add `self._cells: dict[str, DataField] = {}` next to `_local_store`.
- Add `_cell_for`. Resolve the IType from `descriptor._type`; if it is the `object` sentinel return `None`. Otherwise build the cell once per `storage_key`, seed it from `descriptor._default` (handle the callable-default case — call it), cache in `self._cells[descriptor.storage_key]`, and return it. Import `DataField` under `TYPE_CHECKING` and `create_field` at runtime as the existing code does.

- [ ] **Step 4: Run — PASS.** Then run the full Task 1 suite — still green (no behavior changed).

```sh
uv run pytest tests/core/test_settings/test_single_cell.py -q
```

- [ ] **Step 5: Lint/type-check + commit**

```sh
uv run ruff check packages/haywire-core/src/haywire/core/settings/settings.py tests/core/test_settings/test_single_cell.py
uv run ruff format packages/haywire-core/src/haywire/core/settings/settings.py tests/core/test_settings/test_single_cell.py
uv run mypy packages/haywire-core/src/haywire/core/settings/
```

```bash
git add packages/haywire-core/src/haywire/core/settings/settings.py tests/core/test_settings/test_single_cell.py
git commit -m "feat(settings): add per-field DataField cell store (dormant; _local_store still authoritative)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Route `__get__`/`__set__` through the cell; collapse dual-mode + recompute-on-read

Make the cell the source of truth for *instance-local* values. `setting.__set__` writes the cell (typed fields) instead of `_local_store`; `setting.__get__` returns the cell's value when **set**, else the per-kind default (plain literal, or `registry.resolve` for extended/shadow). This is where idea #1 (dual-mode) and idea #3 (recompute-on-read) collapse: there is one store (cells) and the cell *holds* its value rather than re-resolving every read for the local-override case.

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/settings/descriptor.py`
- Modify: `packages/haywire-core/src/haywire/core/settings/settings.py`
- Test: `tests/core/test_settings/test_single_cell.py` (the Task 1 suite is the net)

**Interfaces:**
- `setting.__set__(obj, value)`: typed field → `obj._cell_for(self).set_value(value)`; `object`-typed field → keep writing `obj._local_store[storage_key]` (un-typed simple-mode fallback). The echo-guard (`value == old`) and `_on_property_change` call are unchanged.
- `setting.__get__(obj, ...)`: "is this field locally set?" becomes "does the cell hold a non-default-distinct local value?" — see the **set-tracking** note below. Resolution order:
  1. extended + has a local override → return the cell value (the override);
  2. extended + no local override → `obj._resolve(...)` (registry chain; unchanged for shadow/watch);
  3. simple mode → cell value if the field has a cell, else the `_local_store`/default fallback.
- `Settings._resolve` / `_on_field_change` / `is_locally_set`: "locally set" is now "cell is set" — Task 4 finishes these; Task 3 introduces the **`_is_locally_set(descriptor)`** private predicate they all share.

**The set-tracking problem (read carefully):** `_local_store` encoded "is this field locally overridden?" by *key membership*. A `DataField` always holds *a* value (its default), so membership can't distinguish "unset / inheriting" from "set to the default value." Solution: track local-set-ness explicitly. Add `self._set_keys: set[str]` to `Settings`; `__set__` adds the key, `reset` discards it, `from_dict` adds restored keys. `is_locally_set(name)` ⇒ `storage_key in self._set_keys`. The cell carries the *value*; `_set_keys` carries the *opinion* (mirroring the registry's own set-or-unset design from P2 — keep the vocabulary aligned). Do **not** try to infer set-ness from `cell.get_value() != default`; that breaks "set to the default on purpose" and re-introduces the bug P2 fixed at the tier level.

- [ ] **Step 1: Implement the predicate + `__set__`**

- Add `Settings._set_keys: set[str]` in `__init__`.
- Add `Settings._is_locally_set(self, descriptor) -> bool` returning `descriptor.storage_key in self._set_keys`.
- `setting.__set__`: after the echo-guard, for a typed field write `obj._cell_for(self).set_value(value)` and `obj._set_keys.add(self.storage_key)`; for an `object`-typed field keep the `_local_store` write and still add to `_set_keys`. Then `obj._on_property_change(...)` as today.

- [ ] **Step 2: Implement `__get__`**

Rewrite the body to:
- extended mode (`self._setting_key and obj._registry is not None`): keep the `_promoted_port_id` branch **verbatim** (P5 owns it); then `if obj._is_locally_set(self): return obj._cell_for(self).get_value()` (typed) or the `_local_store` value (object-typed); else `return obj._resolve(...)`.
- simple mode: `if obj._is_locally_set(self):` return cell value (typed) / `_local_store` value (object-typed); else the descriptor default (`value() if callable else value`).

- [ ] **Step 3: Update `_resolve`'s local lookup**

In `Settings._resolve`, replace `field_key in self._local_store` / `self._local_store[field_key]` with the cell-backed read gated on `_set_keys`: when the field is locally set, pass `SettingValue.of(<cell value>)` as `local=`; else `local=None`. (Keep the registry call and the default-strategy logic identical.)

- [ ] **Step 4: Run the characterization suite — must stay PASS**

```sh
uv run pytest tests/core/test_settings/test_single_cell.py tests/core/test_settings/ -q
```
Expected: **all green.** If any Task 1 characterization test fails, the refactor changed observable behavior — fix the refactor, not the test.

- [ ] **Step 5: Lint/type/commit**

```sh
uv run ruff check packages/haywire-core/src/haywire/core/settings/
uv run ruff format packages/haywire-core/src/haywire/core/settings/
uv run mypy packages/haywire-core/src/haywire/core/settings/
```

```bash
git add packages/haywire-core/src/haywire/core/settings/descriptor.py packages/haywire-core/src/haywire/core/settings/settings.py tests/core/test_settings/test_single_cell.py
git commit -m "feat(settings): __get__/__set__ read/write the DataField cell; collapse dual-mode + recompute-on-read

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Re-express `to_dict`/`from_dict`/`reset`/`is_locally_set`/`_on_field_change` on cells; retire `_local_store`

Finish the migration: the four serialization/reset/introspection methods key off `_set_keys` + cells, and `_local_store` is removed from `Settings` entirely (typed fields use cells; the rare `object`-typed field keeps a small dedicated dict, see below). After this task `_local_store` no longer exists as the general value store.

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/settings/settings.py`
- Test: `tests/core/test_settings/test_single_cell.py`

**Interfaces:**
- `to_dict`: for each non-read-only, `_stored` field that is in `_set_keys` and whose value differs from default, emit the **IType-serialized** value (`cell.to_dict()` for typed fields → matches the on-disk `{accessor:{field:value}}` shape; the value is what `from_dict` expects). **Preserve the existing wire shape** — confirm whether the settings block stores the bare value or the `{"value": …}` dict by reading `node/base.py:315` + an existing saved graph fixture, and match it. (If today it stores the bare value, keep storing the bare value — call `cell.get_value()`, not `cell.to_dict()`; the IType round-trip is what the *cell* guarantees, not necessarily the settings-block shape. This is the one place to verify against a real fixture, Step 1.)
- `from_dict(data, silent=...)`: for each known field, write the cell (`cell.set_value(value)` / `cell.from_dict(...)` depending on the wire shape verified above) and add the key to `_set_keys`; `silent=False` routes through `setattr` (fires callbacks) as today.
- `reset(name)`: if `storage_key in _set_keys`, discard it, `cell.reset()` (back to default), fire `_on_property_change(name, default, old)` when changed.
- `is_locally_set`: `storage_key in _set_keys`.
- `_on_field_change`: replace `field_key in self._local_store` with `self._is_locally_set(descriptor)`.

- [ ] **Step 1: Verify the on-disk settings-block shape against a real fixture**

Find a saved graph that exercises a node setting (search `tests/` fixtures / `barn/haybale-example`), or save one via the app, and confirm exactly what `"settings": {accessor: {field: <X>}}` holds for a primitive and (if present) a complex type. Write down whether `<X>` is the bare value or `{"value": …}`. **Task 4's `to_dict`/`from_dict` must produce/consume that exact shape** so existing graphs load. Add a regression test loading that shape.

- [ ] **Step 2: Write failing tests for the cell-backed methods**

Extend `test_single_cell.py`: assert `to_dict` omits an inherited (unset) extended field; includes a locally-set one in the verified wire shape; `from_dict` populates cells and marks `_set_keys`; `reset` clears `_set_keys` + cell; a complex `setting[VEC2I]` round-trips bag→dict→bag.

- [ ] **Step 3: Implement; remove `_local_store`**

Re-express the five methods. Remove `self._local_store` from `__init__`. For the residual `object`-typed simple-mode field (no IType, `_cell_for` returns `None`), keep a minimal `self._plain: dict[str, Any]` used only by that fallback path (don't reintroduce the general dict — this is the narrow un-typed escape hatch). Update `__get__`/`__set__`/`to_dict`/`from_dict`/`reset` object-typed branches to use `_plain`.

- [ ] **Step 4: Run — full settings suite green**

```sh
uv run pytest tests/core/test_settings/ tests/core/test_node/ -q
```
Expected: **all green** (Task 1 characterization + new cell tests + the existing suites).

- [ ] **Step 5: Confirm `_local_store` is gone from `settings.py`**

Run: `grep -n "_local_store" packages/haywire-core/src/haywire/core/settings/settings.py`
Expected: **zero** hits (descriptor.py's object-typed fallback now uses `_plain`; confirm there too).

- [ ] **Step 6: Lint/type/commit**

```bash
git add packages/haywire-core/src/haywire/core/settings/settings.py tests/core/test_settings/test_single_cell.py
git commit -m "feat(settings): serialization/reset/introspection key off cells + _set_keys; drop _local_store

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Sweep remaining `_local_store` callers (descriptor object-path, UI panels, tests)

The store rename ripples to every caller. Grep the repo and fix each. Most are tests; the live ones are the descriptor's object-typed fallback (Task 3/4) and the panel introspection that reads `is_locally_set`.

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/settings/descriptor.py` (any residual `_local_store`)
- Modify: `packages/haywire-core/src/haywire/ui/panel/render_utils.py` (verify it uses `is_locally_set`/`reset`, not `_local_store` directly)
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/panels/properties/setting/node.py` (same)
- Modify: any test hit from the grep below.

**Interfaces:**
- Consumes: the public `is_locally_set`/`reset`/`to_dict`/`from_dict` API; no direct `_local_store` access anywhere.

- [ ] **Step 1: Find every caller**

```sh
grep -rn "_local_store" packages barn tests
```
Expected hits: only the descriptor `_plain` fallback (intentional), and tests asserting on `_local_store`. **Zero** in `settings.py`.

- [ ] **Step 2: Fix each**

- Tests that poke `_local_store` directly (`test_settings.py`, `test_canonical_key.py`, `test_persistent_setting.py`): rewrite to assert via the public API (`is_locally_set` / `to_dict` / `getattr`) or `_set_keys` where membership is the point. Do NOT assert on `_plain` unless the test specifically covers the un-typed fallback.
- Panels: confirm they call `is_locally_set(name)` / `reset(name)` (they should already — `render_utils.py` and the graph-editor node panel were in the Task-survey grep). If any reads `_local_store` directly, switch to the public predicate.

- [ ] **Step 3: Full suite + lint/type**

```sh
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy packages/haywire-core/src/
```
Expected: all green / clean.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "refactor(settings): sweep _local_store callers onto the public cell API

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6 (gated): Bind the settings widget directly to the cell

**Gate:** Do this ONLY if Task 5 left the suite green AND `SettingWidgetModel` can bind to the bag's cell without a port (verify the panel has the owning `Settings` instance + descriptor at bind time). If the widget model can't reach the live cell cleanly, **skip this task** and leave the throwaway-field adapter for P5 (where the port reaches the cell anyway). Record the skip in the Task 8 ADR.

Today `SettingWidgetModel` (`setting_widget_model.py:35-68`) builds a *throwaway* `DataField`, seeds it with the setting's current value, and copies edits back via the panel setter. With the value now living in a real cell on the bag, the widget can bind to **that** cell directly — removing the copy-in/copy-out adapter the idea doc lists under "what this retires."

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/panel/setting_widget_model.py`
- Modify: `packages/haywire-core/src/haywire/ui/panel/render_utils.py` (the wiring that constructs the model)
- Test: a UI/panel test if one exists for setting widgets; otherwise a model-level unit test.

**Interfaces:**
- `SettingWidgetModel` gains a path to use a **provided** `DataField` (the bag's cell) instead of always creating one. The `apply_external`/`set_value` semantics stay; they now operate on the shared cell.

- [ ] **Step 1:** Verify the panel can hand the model the bag's cell (`bag._cell_for(descriptor)`); if not, STOP and skip Task 6.
- [ ] **Step 2:** Add a failing test asserting an edit through the model lands in the bag's cell (and a write to the bag is reflected by the model).
- [ ] **Step 3:** Implement the bind-to-provided-cell path; keep the create-own-field path for the no-bag case (standalone widgets).
- [ ] **Step 4:** Run UI + settings suites; lint/type.
- [ ] **Step 5:** Commit `feat(ui): settings widget binds to the bag's cell directly (retire throwaway-field adapter)`.

---

### Task 7: Full-suite verification

**Files:** none (verification only).

- [ ] **Step 1: Behavior-equivalence check** — re-run the Task 1 characterization suite explicitly; every test must still pass (it is the contract that P4 changed *where* the value lives, not *what the API does*).
- [ ] **Step 2: Lint + format + type + full suite**

```sh
uv run ruff check .
uv run ruff format --check .
uv run mypy packages/haywire-core/src/
uv run pytest -q
```
Expected: all clean / all green.

- [ ] **Step 3:** Commit any fixups (skip if none).

---

### Task 8: Docs — settings-arch single-cell section + ADR-C + roadmap

**Files:**
- Modify: `docs/architecture/settings/settings-arch.md`
- Create: `docs/adr/0013-settings-single-cell.md` (confirm next number at write time)
- Modify: `internals/ideas/settings-datafield-unification-ROADMAP.md`

- [ ] **Step 1: Update `settings-arch.md`**

- Replace "simple mode / extended mode" dual-mode prose (§1 intro, §6.3) with the single-cell model: every field has a `DataField` cell on the bag; `__get__` returns `cell-if-set else default`; "locally set" is `_set_keys` membership.
- Update §7.4 Serialisation: `to_dict`/`from_dict` operate on cells via the IType `to_dict`/`from_dict` contract (the P3 seam), so complex types round-trip.
- Note the cell-mutation spine (§C3): no structural action resets the cell; value changes only by edit / edge-drive (P5) / explicit reset. Point at ADR 0013 and forward-reference P5 for promotion/direction.

- [ ] **Step 2: Find the next ADR number**

```sh
ls docs/adr/ | grep -E '^[0-9]{4}-' | sort | tail -3
```
Expected next: `0013` (0012 is P3's ADR).

- [ ] **Step 3: Write ADR-C** (match the prose style of `docs/adr/0011`/`0012`):
- **Status:** Accepted.
- **Context:** the `_local_store` dict + dual-mode (`_registry is None`) split + recompute-on-read; the UI's throwaway `DataField` bridge (`setting_widget_model.py`). Cite real lines.
- **Decision:** a setting's value lives in a per-field `DataField` cell on the bag (same cell a port uses); `cell ?? default` resolution; `_set_keys` carries the set-or-unset opinion (the value can't, since a cell always holds *a* value). Dual-mode and recompute-on-read collapse. Registry tiers unchanged (P2/P3).
- **§D coordination:** record that P4 satisfies §D's "field rehydrates into its cell" in substance (the cell IS that field) while keeping P3's disk-edge serialization; the literal "tier stores `to_dict`" form was judged unnecessary churn (see this plan's "§D coordination").
- **Deferred to P5:** promotion = field + direction, the `_promoted_port_id` read-tier branch, `is_linked_lazy`. This ADR is the cell; ADR for promotion-as-direction (DECISIONS §E's ADR-C-promotion) is P5.
- **Consequences:** one value model; complex ITypes round-trip at the instance level; the throwaway-field bridge retires (if Task 6 ran); P5 builds promotion on this cell.

- [ ] **Step 4: Build docs strict**

```sh
uv run mkdocs build --strict 2>&1 | tail -20
```
Expected: ADR picked up; **no NEW** warnings vs the pre-edit baseline (the repo has ~58 pre-existing strict warnings; confirm your edited files add none — capture the baseline first like P3's Task 8 did).

- [ ] **Step 5: Commit docs**

```bash
git add docs/architecture/settings/settings-arch.md docs/adr/0013-settings-single-cell.md
git commit -m "docs(adr): ADR 0013 settings single-cell unification; arch single-cell section

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

- [ ] **Step 6: Mark P4 landed in the roadmap**

In `internals/ideas/settings-datafield-unification-ROADMAP.md`, mark the P4 row **LANDED** (commit range + this plan's filename, mirroring the P1/P2/P3 rows) and add a `[LANDED]` marker + landing summary to the `## P4` section header (mirror P2/P3). Note the value-into-cell + dual-mode-removal scope, that promotion/ports are P5, and the §D coordination decision. Commit:

```bash
git add internals/ideas/settings-datafield-unification-ROADMAP.md
git commit -m "docs(roadmap): mark P4 (single-cell unification) landed

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review notes (for the executor)

- **This is a behavior-preserving refactor of *storage*, gated by a characterization suite (Task 1).** If any Task-1 test goes red during Tasks 2–5, the migration changed observable behavior — fix the code, not the test. That suite is the whole safety argument.
- **The set-tracking trap is the one real design subtlety:** a `DataField` always holds a value, so you cannot use cell-membership (the way `_local_store` did) to mean "locally overridden." `_set_keys` carries that opinion explicitly — same set-or-unset shape P2 gave the registry tiers. Do not infer set-ness from `value != default`.
- **`object`-typed (un-IType) simple-mode fields** can't get a cell (`create_field` needs an IType). They keep a narrow `_plain` dict — NOT a revived general `_local_store`. Most/all real fields are typed post-cutover; verify how many `object`-typed fields actually exist (grep `setting(` without a `[IType]` subscript) and, if zero in production, the `_plain` path is purely defensive.
- **Wire-shape fidelity (Task 4 Step 1) is mandatory before touching `to_dict`/`from_dict`** — match the existing `{accessor:{field:value}}` shape exactly against a real saved graph, or you silently break loading every existing graph. This is the highest-risk step; do it against a fixture, not from memory.
- **Do NOT touch in P4:** the `_promoted_port_id` read-tier branch (`descriptor.py:328-333` — keep verbatim, P5 owns it), the registry tiers / `save_to_json` / `persistent_setting` registry write (P2/P3), `NodeData.__init__` bag-creation order (P5 reference-binding depends on it), promotion/direction/`is_linked_lazy` (P5), and the `_stored`/`_validator`/`_metadata` attribute retirements (§C, orthogonal).
- **Order:** Tasks 1→5 are strictly ordered (each consumes the prior; the suite stays green throughout because of the characterization net — there is NO intentionally-red window, unlike P3). Task 6 is gated/optional. Tasks 7 (verify), 8 (docs/ADR/roadmap) follow.
- **If task count balloons in Tasks 3–4** (the ROADMAP warns this plan is large), the natural split point is: stop after Task 3 (cells back `__get__`/`__set__`, `_local_store` still present for serialization) as "P4a — value-into-cell", and make Tasks 4–8 "P4b — dual-mode/`_local_store` removal" as a follow-up plan. Both halves are independently green.
```
