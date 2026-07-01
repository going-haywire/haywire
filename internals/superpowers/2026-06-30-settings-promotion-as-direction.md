# Promotion = Field + Direction (P5) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Revised after a second inquisition pass (2026-07-01).** This revision supersedes DECISIONS §B
> (the config direction and the eligibility matrix) and §C4 (the `is_linked_lazy` scope) in the
> specifics called out below. The corrections are grounded in code reads recorded inline. Net effect:
> **the model is simpler than the original plan** — one mechanism (`bind_field` + `on_changed →
> propagate`) governed by **two orthogonal flag checks**. See "The unified model" immediately below.

**Goal:** Generalize promotion from *setting→inlet* (the Plan-3 inlet-only implementation) to **"assign a direction to a value-bearing field."** A promoted port and the setting it binds become **one cell, two views**: the port borrows the setting's `DataField` cell (landed in P4) **by reference** (via a new `bind_field`), so there is no second value, no `_promoted_port_id` descriptor flag, no `field_data` on the port, and no read-tier bridge. Land **two directions** — **inlet / outlet** (config dropped, see below) — governed by one invariant (read-only ⇒ outlet-only), with **two verbs only** (`promote(direction)` + `demote`). Add the general-purpose **`is_linked_lazy`** port flag so an out-of-frame outlet re-emits on its next consumer frame. Make the **mirror-field cell authoritative in the setting** (new Task 2.5) so the shared cell always holds the resolved value. Retire the `_promoted_port_id` read-tier branch (kept verbatim in P4) and the `SettingWidgetModel` throwaway-field adapter (skipped in P4's Task 6).

**The unified model (the whole plan in one paragraph).** A promoted port `bind_field`s the setting's `DataField` by reference — the *same object swap* `_add_link` already performs at `port.py:380` when two ports share a cell. The field's `on_changed` event is the single fan-out: whenever the value changes (widget edit, edge drive, or registry sync), every observer reacts. **Two orthogonal flag checks govern the entire matrix — there is no per-kind propagation logic:**

1. **`descriptor._read_only`** (set by `watch()`; `shadow()`/plain are writable) ⇒ **outlet-only**. A read-only field has no write path *in*, so it can only be a read path *out*.
2. **direction = outlet** ⇒ the port sets **`is_linked_lazy`** *and* subscribes `on_changed → self._pipes.propagate()`. This holds for **every** promoted outlet — plain, shadow, watch alike — because a promoted outlet is *never* worker-`out()`-driven; it is written by widget / registry / edge, all of which fire **outside the scheduler frame** (there is no "apply between frames" mechanism — verified). An eager propagate from an out-of-frame write is the §C4 hazard; lazy defers the pull to the consumer's next execution.

Everything else (mirror vs plain, set vs unset, which node writes the cell) is handled by that one mechanism. Promoted **inlets** borrow the cell but do **not** subscribe-to-propagate (nothing downstream to drive; the edge/widget writes *in*, the node reads).

**Architecture:** Today `promote_setting` (`node/promotion.py`) creates a *separate* DATA inlet with `StoreStrategy.NEVER` + `ShowWidgetStrategy.NEVER`, and stamps `descriptor._promoted_port_id = pid`; `setting.__get__` has a read-tier branch (`descriptor.py`, the block P4 kept verbatim) that, when the promoted port is linked, returns `port.get_value()` instead of resolving the setting. That is a **two-value** design: the port has its own `_data`, and the descriptor bridges reads. P5 replaces it with **reference-sharing**: on promote (and on load via a `from_spec` promoted branch) the port's `_data` is set to the *same object* as `bag._cell_for(descriptor)` — the P4 cell — through a new `DataPort.bind_field(field)` primitive. The setting descriptor stays **oblivious to ports** (no port flag) — but note "oblivious" means *unaware a port exists*, **not** *passive about its own value*: keeping the cell correct (including syncing a tracking mirror field to the resolved global) is the setting's own responsibility (Task 2.5). The port carries the entire binding signal as `promoted=True` + an `id` that *equals the setting key* (`setting__<accessor>__<field>`, already the canonical key). Because `_data` is shared, `setting.__get__` needs **no** read-tier branch — reading the setting and reading the port hit the same cell. Direction is expressed through the existing `ShowWidgetStrategy` per-direction defaults (inlet `NOT_LINKED`, outlet `NEVER`) plus, for outlets, the `is_linked_lazy` flag.

**Why config was dropped (supersedes DECISIONS §B).** DECISIONS §B specified three directions with config = "widget always on card; edge drives when linked." Two code facts kill it: (1) an *unlinked inlet already shows its widget* (`ShowWidgetStrategy.NOT_LINKED` is the inlet default — `enums.py:84`), so config's "always-on widget" selling point is just what a promoted inlet does for free once we stop overriding `show_widget=NEVER`; and (2) the existing `as_config` factory sets `flow_type=NONE` (`interface.py`, "Config ports are never linked") — a *pinless* port, the opposite of edge-drivable. So §B's config row is internally contradictory against the code it names. An "always-visible even while linked" editable widget would also fight the cell-mutation spine (§C3: wiring owns the cell). **Resolution:** two directions, inlet + outlet. The matrix becomes plain/shadow → inlet | outlet; watch → outlet-only.

**Tech Stack:** Python 3, `pytest`, `ruff`, `mypy`. Haywire monorepo (`uv run` for all tooling).

## Global Constraints

- Line length 109 (`ruff`, configured in repo).
- CI runs BOTH `ruff check` AND `ruff format --check` — run both locally; they catch disjoint problems.
- mypy scope for this plan: `uv run mypy packages/haywire-core/src/ barn/haybale-graph-editor/haybale_graph_editor/` (the UI verbs live in barn; CI's mypy line lists the barn packages — match it).
- In test files, import `haywire.core.graph.editor` before other haywire modules to avoid circular import errors.
- Promotion tests exercise the full node/edge machinery; several are `@pytest.mark.integration`. Run `uv run pytest -m "not integration"` for the fast loop, the full suite before each commit.
- Stay on branch `feat/type-floor-hoist`. This is the **final** plan of the arc; do NOT merge to master until it lands green (pytest + ruff + ruff format + mypy clean). At that point the arc (P1–P5) is complete and the branch is a merge candidate — see the finishing task.
- **Reference:** `internals/ideas/settings-datafield-unification-DECISIONS.md` (**§B** = the direction-eligibility matrix + per-direction cell ownership, **§C2** = field↔port binding & serialization by shared reference, **§C3** = the two-verbs cell-mutation spine, **§C4** = `is_linked_lazy`, **§C5** = hot-reload) and `internals/ideas/settings-datafield-unification-ROADMAP.md` (P5 section + "Retires"). P1–P4 have all landed on this branch; **P4 (single cell, ADR 0013) is the load-bearing prerequisite** — the port borrows *that* cell.

## SCOPE — promotion-as-direction + is_linked_lazy + adapter retirement

| In scope (this plan) | Out of scope (deferred / untouched) |
| --- | --- |
| `promote(direction)` for **inlet / outlet** (config dropped — see header); `demote` (Tasks 3–5) | Idle-liveness (registry edit → rippling to an *idle* downstream immediately). §C4 fixes freshness-as-of-next-execution only. |
| `bind_field`/`unbind_field`: port `_data` **is** the setting's P4 cell by reference (Task 2) | New tiers / registry changes (P2/P3 settled; untouched) |
| **Mirror-field cell authoritative in the setting** (`_on_field_change` writes the cell; reads come from it) (Task 2.5) | Splitting `Settings` responsibilities (idea #7, declined) |
| Retire `_promoted_port_id` + the `__get__` read-tier branch (Task 6) | `_stored`/`_validator` descriptor-attr retirement (§C, orthogonal — a separate cleanup) |
| Serialization: `promoted:true` + id, no `recipe`, no `field_data`; `from_spec` promoted branch; **settings-first load order** (Task 4) | `_mirror_key`/`_mirror_descriptor`/`_read_only`/`_metadata` — **stay** (§C "stays") |
| `is_linked_lazy` port flag; **every promoted outlet sets it** (Task 5) | `StoreStrategy.NEVER` as an explicit bolt-on — **retires naturally** (nothing to store), not removed by hand |
| Direction eligibility = **two flag checks** (`_read_only`→outlet-only; direction=outlet→lazy) (Task 3) | Reworking `ShowWidgetStrategy` — reuse the per-direction defaults, do not reinvent (retires idea #5) |
| UI verbs: extend the inlet-only menu to inlet/outlet per eligibility (Task 7) | Graph-JSON back-compat for *pre-P5* promoted nodes (see "Back-compat" below) |
| Retire `SettingWidgetModel.create_field` throwaway adapter → **read** the shared cell, **write** through `__set__` (Task 8) | Config direction (dropped this revision) and any `flow_type=NONE` promotion |

## Back-compat note (read before Task 4)

Plan-3 promoted nodes on this branch serialize the inlet with its own `field_data` + `recipe` and rely on `_promoted_port_id` re-binding at load (`node/base.py` `_initialize_from_dict`, the promoted re-bind block). **There is no external release of the Plan-3 format** — it exists only on `feat/type-floor-hoist`. This plan changes the on-disk promoted-port shape (drops `recipe`/`field_data`, adds `promoted:true`). Decision to confirm at Task 4 Step 1: since Plan-3's format never shipped, P5 does a **clean cutover** — a `from_spec` promoted branch reads the new shape; old-shape promoted ports in any local test graph are re-saved on next write. Record this in the ADR (Task 10). If a saved-graph fixture in `tests/` encodes the old shape, migrate the fixture in Task 4.

## The real surface (grep by symbol; line numbers may have drifted)

- `node/promotion.py` — the whole module reworks. `promote_setting` (creates a separate inlet + sets `_promoted_port_id` + hardcodes `show_widget=NEVER` at ~line 80 — **delete that override** so a promoted inlet inherits `NOT_LINKED`), `demote_setting`, `_metadata_to_port_kwargs`, the `encode/decode/is_promoted_port_id` helpers (id scheme **stays** — it already equals the setting key). The blanket `if _mirror_key: raise "not promotable"` guard (~line 72) → **split into the two flag checks** (`_read_only`→outlet-only; else inlet|outlet).
- `settings/descriptor.py` — `setting.__get__` promoted read-tier branch (the block P4 kept verbatim, `if self._promoted_port_id is not None: ... port.get_value()`) → **deleted** in Task 6. For a **tracking mirror field** (unset), `__get__`/`_resolve` must read the **cell** (Task 2.5), not live-resolve-and-bypass. `SettingDescriptor._promoted_port_id` (`settings/base.py`) → **deleted**. `shadow`/`watch` factories (`descriptor.py:436/441`) — `watch` = mirror + `read_only=True`; `shadow` = mirror, writable. **The only difference is writability.**
- `settings/settings.py` — **Task 2.5's home.** `_on_field_change` (~194) currently *notifies only*; make it **write the resolved value into the cell** (`cell.set_value(...)`) for unset mirror fields, and **seed the cell** at subscribe / first `_cell_for` access so a freshly-loaded headless graph is correct before any change fires. `cleanup()` (~336) — add `registry.unsubscribe`. Node bags already subscribe eagerly (`node/data.py:73` calls `_subscribe_settings()`), so this works headless — the subscription is NOT UI-gated.
- `types/port.py` — **new `bind_field(field)` / `unbind_field()` pair** (the reference-share swap `self._data = field`, same move `_add_link` already does at ~380 — optionally DRY `_add_link` onto it). `bind_field` on an **outlet** also subscribes `field.on_changed → self._pipes.propagate()`; `unbind_field` removes it (called by demote + cleanup). Plus: `from_spec` (promoted branch: skip type-resolution/`_data`-create/`field_data`), `to_dict` (skip `recipe`/`field_data` for promoted; emit `promoted`/`is_linked_lazy`), the `DataPort` dataclass (add `promoted: bool` + `is_linked_lazy: bool` fields), `set_value` outlet path, `is_linked`/`_add_link` (force lazy when `is_linked_lazy`). Watch `_is_set_by_node` (~304): a promoted outlet is setting-driven, not `out()`-driven.
- `types/fields.py` — `DataField.on_changed` (Event, ~48) fires on `set_value` (~116/124) — **this already exists**; it is the fan-out `bind_field` subscribes to. `remove_source` (~106) is a **no-op except for `PooledField`** — so a shared *primitive/base* cell with two writers (settings layer + edge) is safe; only a `PooledField`-typed promotion would need source-tracking care (exotic; test-guard, likely out of scope).
- `types/pipe.py` — `Pipe.is_lazy`/`pull()` (the always-latest mechanism `is_linked_lazy` rides): a lazy pipe pulls **only after its sink is marked dirty via `propagate()`** — which is why the outlet's `on_changed → propagate` (above) is **required**, not optional. The plan's original "verify no change needed beyond forcing the flag at link" is **false**; the propagate trigger is the missing half.
- `edge/edge_wrapper.py` — `is_lazy` plumbing; `link()` / `_add_link` are where a port can force `is_lazy=True`.
- `types/enums.py` — `ShowWidgetStrategy` per-direction defaults already exist (inlet `NOT_LINKED`, outlet `NEVER`) — **reuse**. (config `ALWAYS` is irrelevant now — config dropped.)
- `node/data.py` — the settings bag holds the cells (`NodeData.__init__`, ~71); the bag exists before any port. `node/base.py` `_to_dict` (~312, pure-read dict literal — **save order is irrelevant**) / `_initialize_from_dict` (~356) orchestrate bag + port restore. **Change the restore order to settings-first** (Task 4): restore settings bags → deserialize ports (promoted `from_spec` calls `bind_field` on a cell already at its loaded value → no propagate-during-load). Delete the `_promoted_port_id` re-bind loop (~361-378).
- `ui/panel/setting_widget_model.py` — the throwaway `DataField` adapter (`create_field(default_override=...)`, ~47) → **read** the shared cell (`bag._cell_for(descriptor)`) for display, **write** through the descriptor `setattr` (Task 8, to preserve `_set_keys`).
- **UI verbs (barn):** `panels/graph/menu/node/promote.py` (inlet-only "Promote Setting" submenu → inlet/outlet-per-eligibility submenu; `promotable_fields` at ~41 reads `_promoted_port_id` → switch to the port-id check), `panels/graph/menu/port/port.py` ("Detach from setting"), `editors/graph_canvas/handlers/context_menu_actions.py` (`SelectionContextActions.promote_setting` / `PortContextActions`).
- **Existing tests to extend:** `tests/core/node/test_promotion_id.py`, `test_promote_demote.py`, `test_promotion_serialization.py`, `test_promotion_e2e.py`; `tests/core/settings/test_promoted_read_tier.py` (**the read-tier test — rewrites to reference-sharing in Task 6**); `tests/ui/menu/test_promote_demote_menu.py`, `test_promotion_e2e.py`; `tests/ui/panel/test_promoted_row_state.py`.

---

## Pre-edit baseline (run once before Task 1)

```sh
uv run ruff check packages/haywire-core/src/haywire/core/node packages/haywire-core/src/haywire/core/types packages/haywire-core/src/haywire/core/settings barn/haybale-graph-editor/haybale_graph_editor
uv run mypy packages/haywire-core/src/ barn/haybale-graph-editor/haybale_graph_editor/
uv run pytest tests/core/node/ tests/core/settings/test_promoted_read_tier.py tests/core/types/ tests/ui/menu/ tests/ui/panel/test_promoted_row_state.py -q
```

Expected: all clean/green. If anything fails here, STOP and surface it — it is pre-existing.

---

### Task 1: Characterization tests — pin current promotion behavior before the rework

Promotion is behaviour that already works (inlet-only). Pin it through the **public** surface (`promote_setting`/`demote_setting`, node `to_dict`/`from_dict` round-trip, the reading of a linked promoted inlet) so the reference-sharing rework is provably behaviour-preserving for the inlet case, and so the new outlet direction extends a green base.

**Files:**
- Test: `tests/core/node/test_promotion_single_cell.py` (Create)

- [ ] **Step 1: Write characterization tests** covering, at minimum, the current inlet path:
  - `promote_setting(node, accessor, field)` adds a port whose id is `encode_promoted_port_id(accessor, field)`; `demote_setting` removes it.
  - A promoted inlet, when **linked and driven**, makes `getattr(bag, field)` observe the driven value; when **unlinked**, the setting resolves normally (its own cell value / default).
  - `shadow()`/`watch()` fields are rejected by `promote_setting` today (`ValueError`).
  - A node with a promoted inlet round-trips `to_dict`→`from_dict` and the binding is restored (the promoted port exists and reads the setting after load).
- [ ] **Step 2: Run — all PASS against current code.** `uv run pytest tests/core/node/test_promotion_single_cell.py -v`
- [ ] **Step 3: Commit** `test(promotion): characterize inlet promotion before promotion-as-direction rework`.

---

### Task 2: Reference-sharing spine — `bind_field` / `unbind_field`

Introduce the core mechanism with the value now in a P4 cell: on promote, bind the new port's `_data` to `bag._cell_for(descriptor)` (the same object), instead of the port owning its own field. Keep this **inlet-only** in this task (direction handling is Task 3) so the spine is reviewed in isolation. After this task, a promoted inlet and its setting share one cell — but `setting.__get__` still has its read-tier branch (removed in Task 6); both must agree because they now read the same object.

**Naming:** the method is `bind_field` / `unbind_field` (NOT `bind_cell`) — the code noun for this object is *field* (`_data`, `create_field`, `field_data`); "cell" is design-doc vocabulary. Match the surrounding code.

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/node/promotion.py`
- Modify: `packages/haywire-core/src/haywire/core/types/port.py` (the `bind_field`/`unbind_field` pair)
- Test: `tests/core/node/test_promotion_single_cell.py`

**Interfaces:**
- `DataPort.bind_field(field)` swaps `self._data = field` (the shared reference — the *same swap* `_add_link` already performs at `port.py:~380`; optionally refactor `_add_link` to call it). `DataPort.unbind_field()` reverses it. The subscribe-to-propagate half is **outlet-only** and lands in Task 5 (`bind_field` on an outlet subscribes `field.on_changed → self._pipes.propagate()`; `unbind_field` removes it). In *this* task, inlet-only, `bind_field` is just the reference swap.
- `promote_setting` calls `port.bind_field(bag._cell_for(descriptor))` after `node.add(spec)`. The setting cell is authoritative; the port shares it. Keep the invariant (shared reference, `is_dirty` semantics) on the port, not in promotion.py.
- `unbind_field` is called by **demote** and by port **cleanup** (symmetric lifecycle — this is why subscribe/unsubscribe both live on the pair).

- [ ] **Step 1: Add a failing test** — after `promote_setting`, assert `node.ports[pid]._data is bag._cell_for(descriptor)` (identity), and that a `setattr(bag, field, X)` is observed by `port.get_value()` **without** any copy step.
- [ ] **Step 2: Run — FAIL** (port owns its own field today).
- [ ] **Step 3: Implement** `bind_field`/`unbind_field` + the `promote_setting` binding. Leave the `_promoted_port_id` stamp in place for now (Task 6 removes it) so the existing read-tier branch keeps working alongside the shared cell.
- [ ] **Step 4: Run — PASS**, then the Task 1 suite — still green.
- [ ] **Step 5: Lint/type/commit** `feat(promotion): promoted inlet borrows the setting's DataField via bind_field`.

---

### Task 2.5: Make the mirror-field cell authoritative in the setting

> **New task, added this revision.** P4 left an unset mirror field's cell holding only the descriptor
> default while `_resolve` live-resolved from the registry and *bypassed the cell*. For "one cell,
> two views" to be true, the shared cell must hold the resolved value — that is the **setting's**
> responsibility, not the port's. This is also what closes the display gap P4's Task 6 was skipped
> for. Land it before Task 4 (serialization) and Task 6 (read-tier retirement). Supersedes the
> implicit "port bridges the mirror value" reading of DECISIONS §C2.

Both `shadow` and `watch` keep the cell synced to the resolved global; the *only* difference is writability (`watch` = read-only; `shadow` = user may override, `reset` re-seeds from global and resumes tracking). Make the setting maintain that:

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/settings/settings.py` (`_on_field_change`, cell seeding, `cleanup`)
- Modify: `packages/haywire-core/src/haywire/core/settings/descriptor.py` (`__get__`/`_resolve` read the cell for the unset-mirror case)
- Test: `tests/core/settings/` (new: mirror-cell-authoritative unit test)

**Interfaces:**
- `_on_field_change` **writes** the resolved value into the field's cell (`cell.set_value(...)`) for an unset mirror field — today it only notifies. (Its "unset tracks; set ignores" guard stays: a locally-set field is skipped.)
- The cell is **seeded** with the resolved value at subscribe time / first `_cell_for` access — not only on the next change — so a freshly-loaded **headless** graph is correct immediately. Node bags subscribe eagerly (`node/data.py:73`), so no UI is required.
- `__get__`/`_resolve` for an **unset mirror field** read the **cell** (which now holds the resolved value), not a live-resolve-and-bypass. Live-resolve is demoted to "compute the value to store in the cell."
- `cleanup()` adds `registry.unsubscribe(descriptor._mirror_key, self._on_field_change)` (existing tolerated leak; fix it here).

- [ ] **Step 1: Failing test** — construct a node bag with a `watch` field; change the watched global via the registry; assert `bag._cell_for(desc).get_value()` equals the new global (not the default) **with no UI subscriber** (headless). Assert an unset `shadow` field tracks; a set one ignores; a `reset` re-seeds from the global.
- [ ] **Step 2: Run — FAIL** (cell holds only the default today).
- [ ] **Step 3: Implement** the cell-write in `_on_field_change`, the seed, the `__get__`/`_resolve` cell-read, and the `cleanup` unsubscribe.
- [ ] **Step 4: Run** the settings suite — green. Confirm `setattr` on a `shadow` still marks `_set_keys` and stops tracking (regression guard for Task 8).
- [ ] **Step 5: Lint/type/commit** `feat(settings): mirror-field cell holds the resolved global (authoritative, headless-correct)`.

---

### Task 3: promote(direction) — inlet / outlet, governed by two flag checks

Generalize `promote_setting` to take a **direction ∈ {inlet, outlet}** (config dropped — see header). Eligibility is **two orthogonal flag checks**, not a per-kind matrix:
1. `descriptor._read_only` (watch) ⇒ **outlet-only** (else `ValueError`); writable (shadow/plain) ⇒ inlet or outlet.
2. `direction == outlet` ⇒ the port is `is_linked_lazy` **and** subscribes `on_changed → propagate` (wired in Task 5). Applies to *every* outlet (plain included) — a promoted outlet is never `out()`-driven.
Direction selects the port factory (`as_inlet`/`as_outlet`) and thus the `ShowWidgetStrategy` per-direction default. `demote` stays a single verb; redirect = demote + re-promote (§C3), re-checking eligibility.

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/node/promotion.py`
- Modify: `packages/haywire-core/src/haywire/core/types/enums.py` (only if a `PromotionDirection` enum is added — see below)
- Test: `tests/core/node/test_promote_demote.py`, `tests/core/node/test_promotion_single_cell.py`

**Interfaces:**
- `promote_setting(node, accessor, field, direction)` where `direction ∈ {inlet, outlet}` (an enum, e.g. `PromotionDirection`, or reuse an existing port-facing enum — decide at Step 1 by grepping for a pre-existing direction concept; do NOT invent a parallel one if `PortType`/`FlowType` already expresses it cleanly).
- Eligibility guard = the two flag checks above. This **replaces** the old blanket `if _mirror_key: raise "shadow()/watch() not promotable"` — `_mirror_key` no longer blocks promotion; it only decides `is_linked_lazy` (which now follows from direction=outlet anyway, so mirror-ness is not even consulted for the flag).
- Each direction picks its factory: inlet→`as_inlet` (`show_widget=NOT_LINKED`), outlet→`as_outlet` (`NEVER`). Do **not** pass `show_widget` explicitly — let the factory default apply (this is what makes a promoted **inlet** show its widget when unlinked; delete the old `show_widget=NEVER` inlet override).

- [ ] **Step 1: Decide the direction representation** — grep `enums.py`/`port.py` for an existing inlet/outlet discriminator. Add a minimal `PromotionDirection` only if none fits. Document the choice in the commit body.
- [ ] **Step 2: Write failing tests** — promote a plain field to inlet and to outlet; assert the port's `show_widget` matches the per-direction default (inlet `NOT_LINKED` → widget shows when unlinked; outlet `NEVER`) and the cell is shared (Task 2 invariant holds per direction). Assert `watch→inlet` raises; `watch→outlet` succeeds; `shadow→{inlet,outlet}` succeed. Assert every promoted **outlet** (plain/shadow/watch) has `is_linked_lazy` set.
- [ ] **Step 3: Implement** the two flag checks + direction→factory dispatch (`as_inlet`/`as_outlet`, no explicit `show_widget`). Keep `demote` direction-agnostic (removes whatever port id encodes, calls `unbind_field`, cell survives per §C3).
- [ ] **Step 4: Run** the promotion suites — green. Confirm the cell-mutation spine: `demote` after a driven value **keeps** the cell value (assert `getattr(bag, field)` unchanged across demote).
- [ ] **Step 5: Lint/type/commit** `feat(promotion): promote(direction) — inlet/outlet, read-only⇒outlet-only`.

---

### Task 4: Serialization — promoted ports are value-less (`promoted:true`, no recipe/field_data)

Re-express promoted-port serialization per §C2: a promoted port serializes as `{kwargs:{id, port_type, promoted:true, ...display}}` — **NO `recipe`** (type derived from the setting at `id`), **NO `field_data`** (value round-trips through the settings block only, written by the bag's `to_dict`). `from_spec` gains a promoted branch that skips type-resolution + `_data` creation + `field_data` restore, and instead **`bind_field`s the port to the setting cell by reference** (the Task 2 spine, now on the load path).

**Load order flips to settings-first (this revision).** The original plan said "reference-binding makes load-order irrelevant — verify no fix needed." That is only half true: the *value* lands correctly regardless of order (both `_write_local` and `reset` mutate the cell **in place** — verified `settings.py`, they never replace the dict entry, so a port bound early sees the later restore). But the **subscription** matters: once `bind_field` subscribes an outlet to `on_changed` (Task 5), a `bag.from_dict` running *after* the bind fires `on_changed` and would **propagate through a half-built graph mid-load**. Fix by construction: restore **settings bags first, then ports**, so the restore-write predates the port's subscription — no spurious load-time propagation, no load-phase flag. The current order (ports-first, then settings) exists only to feed the `_promoted_port_id` re-bind loop, which this task deletes.

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/types/port.py` (`to_dict`, `from_spec`, add `promoted` field)
- Modify: `packages/haywire-core/src/haywire/core/node/base.py` (**reorder** `_initialize_from_dict` to settings→ports; add the promoted bind via `from_spec`; delete the old `_promoted_port_id` re-bind block ~361-378)
- Test: `tests/core/node/test_promotion_serialization.py`, `tests/core/node/test_promotion_e2e.py`

**Interfaces:**
- `DataPort.to_dict`: when `self.promoted`, emit `promoted:true` + `id` + `port_type` + display kwargs; omit `recipe` and `field_data` entirely. (Save-side note: `_to_dict` is a pure-read dict literal — the `ports`/`settings` write *order* is irrelevant; only single-writer matters — the value is written by `settings`, skipped by the port.)
- `DataPort.from_spec`: when `spec["kwargs"].get("promoted")`, derive `type_cls` from the setting at `id` (decode id → accessor/field → `descriptor._type`), do NOT create a fresh `_data`, `bind_field` to `bag._cell_for(descriptor)`, skip `field_data`. No throwaway field.
- `node/base.py`: `_initialize_from_dict` order becomes **restore settings bags → `_deserialize_ports`** (promoted `from_spec` binds a cell already at its loaded value). Assert no `from_spec` (promoted or plain) reads a settings value expecting ports-first (grep says none do — assert it holds). Delete the `is_promoted_port_id` re-bind loop.

- [ ] **Step 1: Verify the wire shape + prescribe the order.** Save a node with a promoted port (inlet + outlet), inspect the `ports` + `settings` blocks. Confirm the value lives in `settings`, the port block is value-less. Reorder `_initialize_from_dict` to settings-first. Migrate any old-shape fixture (see Back-compat note).
- [ ] **Step 2: Write failing tests** — (a) promoted port `to_dict` has `promoted:true`, no `recipe`/`field_data`; (b) **driven-then-saved** promoted port round-trip restores the binding by reference (`port._data is bag._cell_for(desc)` after load) and the value, for inlet + outlet; (c) **unset** promoted field round-trips: the `settings` entry is *empty* and the value resolves from the registry/default on load (no persisted value).
- [ ] **Step 3: Implement** `to_dict`/`from_spec` promoted branches + the settings-first reorder + re-bind-loop deletion.
- [ ] **Step 4: Run** serialization + e2e suites — green. Assert no propagation fires during load (a spy on the consumer's execution count across a load with a linked promoted outlet).
- [ ] **Step 5: Lint/type/commit** `feat(promotion): value-less promoted-port serialization; settings-first load binds by reference`.

---

### Task 5: `is_linked_lazy` + the outlet's `on_changed → propagate` (the two-part freshness mechanism)

> **Corrected this revision.** The original plan said "verify no change needed beyond forcing the flag
> at link." That is **false** — verified against `pipe.py`/`port.py`: a lazy pipe pulls **only after
> its sink is marked dirty**, and `resolve_dirty_data` drains only pipes queued by `propagate()`
> (`port.py:322` reads `_pending_lazy_pipes`, populated only via `_mark_as_data_dirty(pipe=…)`).
> An out-of-frame registry change triggers **nothing** — so `is_linked_lazy` alone is inert. The
> freshness mechanism has **two parts**: (1) `is_linked_lazy` makes the pull safe/deferred; (2) an
> `on_changed → propagate` subscription on the outlet is what *triggers* that pull. Both are needed.

Two-part mechanism, both landing here:

**Part 1 — `is_linked_lazy` (all promoted outlets, not just watch).** A promoted outlet is written by widget / registry / edge — **never** by the worker's `out()` — and all those writes fire **outside the scheduler frame** (there is no "apply between frames" mechanism). An eager propagate from an out-of-frame write is the §C4 hazard. So **every promoted outlet** (plain, shadow, watch) sets `is_linked_lazy`; it forces linked edges to `is_lazy=True`, deferring each consumer's pull to its next execution. (This *supersedes* §C4/Q8's "mirror⇒lazy" — the real discriminator is "setting-driven ⇒ out-of-frame," true of all promoted outlets.)

**Part 2 — the outlet self-propagates on cell change, without the setting knowing about the port.** `bind_field` on an **outlet** subscribes `field.on_changed → self._pipes.propagate()`. When anything writes the shared cell (widget, or the Task-2.5 registry sync), `DataField.on_changed` (already exists, `fields.py:48`) fires, and the **port** propagates its own pipes — lazy, so it just queues the sink pipe + marks it dirty; the consumer pulls on its next frame. The **setting stays oblivious to the port**: it writes its cell; the port reacts to *its* cell. `unbind_field` removes the subscription (demote/cleanup).

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/types/port.py` (add `is_linked_lazy` field; force lazy in the link path; the outlet `on_changed → propagate` subscription inside `bind_field`/`unbind_field`)
- Modify: `packages/haywire-core/src/haywire/core/node/promotion.py` (direction=outlet sets `is_linked_lazy` — for any kind)
- Modify: `packages/haywire-core/src/haywire/core/edge/edge_wrapper.py` (only if the force point lives on the edge side)
- Test: `tests/core/node/test_promotion_e2e.py` (or a new `test_is_linked_lazy.py`)

**Interfaces:**
- `DataPort.is_linked_lazy: bool = False`, serialized (round-trips). When a port with the flag is linked (`_add_link`/`link()`), the edge's `is_lazy` is forced `True`.
- `promote_setting(..., direction=outlet)` sets `is_linked_lazy=True` on the outlet spec **regardless of field kind** (plain included).
- `bind_field` (outlet only): `field.on_changed.append(self._on_shared_field_changed)`, where `_on_shared_field_changed` calls `self._pipes.propagate()` if `_pipes` is set. `unbind_field` removes it.
- Freshness contract (document in the port docstring): downstream is "fresh as of the consumer's next execution." Idle-liveness (rippling to an *idle* consumer immediately) is out of scope.

- [ ] **Step 1: Write a failing test** — a `watch→outlet` linked to a consumer inlet; edit the watched global via the registry (Task 2.5 writes the cell); assert `on_changed` fired, the sink was marked dirty, and the consumer pulls the new value on its next execution (drive one frame). Add the same for a **plain→outlet** whose widget value changes out of frame. Assert the linked edge is `is_lazy`.
- [ ] **Step 2: Confirm the mechanism** against `pipe.py`/`port.py`: lazy pull needs a `propagate()` to queue the pipe; the outlet's `on_changed → propagate` is that trigger. (This replaces the original "no new propagation path" claim — the path is *reused* from the settings-change hook, not invented, but it IS required.)
- [ ] **Step 3: Implement** the flag + link-time force + the outlet `on_changed → propagate` in `bind_field`/`unbind_field` + the direction=outlet wiring.
- [ ] **Step 4: Run** e2e — green. Confirm a promoted **inlet** does NOT subscribe-to-propagate (nothing downstream). Confirm demote/`unbind_field` removes the subscription (no dangling handler on the shared cell).
- [ ] **Step 5: Lint/type/commit** `feat(ports): is_linked_lazy + outlet self-propagates on shared-cell change`.

---

### Task 6: Retire `_promoted_port_id` + the `__get__` read-tier branch

With the port sharing the setting's cell (Tasks 2 & 4), `setting.__get__` no longer needs its promoted read-tier branch — reading the setting and reading the port hit the same object. Remove the branch and the `_promoted_port_id` descriptor attribute; the `promoted:true`+id on the port is the entire binding signal (§C2 "kills cleanup #4").

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/settings/descriptor.py` (delete the read-tier branch in `setting.__get__` — the block P4 kept verbatim)
- Modify: `packages/haywire-core/src/haywire/core/settings/base.py` (delete `_promoted_port_id`)
- Modify: `packages/haywire-core/src/haywire/core/node/promotion.py` (stop stamping/clearing `_promoted_port_id`)
- Modify: `barn/haybale-graph-editor/.../panels/graph/menu/node/promote.py` (`promotable_fields` reads `_promoted_port_id` to skip already-promoted — switch to "is there a port whose id encodes this field?")
- Test: `tests/core/settings/test_promoted_read_tier.py` (**rewrite** to assert reference-sharing, not the read-tier bridge), promotion suites.

**Interfaces:**
- "Already promoted?" becomes `encode_promoted_port_id(accessor, field) in node.ports` (the id is the truth), everywhere `_promoted_port_id` was consulted.
- `test_promoted_read_tier.py` no longer tests a *bridge*; it tests that a linked promoted port and its setting return the same value **because they share the cell**. Rename/retarget it (e.g. `test_promoted_shared_cell.py`) — the read-tier concept is gone.

- [ ] **Step 1: Grep every `_promoted_port_id` reader** (`grep -rn "_promoted_port_id" packages barn tests`) and list them. Expected: the `__get__` branch, `base.py` decl, promotion.py stamp/clear, `promotable_fields`, and tests.
- [ ] **Step 2: Rewrite the read-tier test** to the shared-cell assertion; run — it should pass on the Task 2/4 code even before the branch is deleted (the shared cell already makes them agree).
- [ ] **Step 3: Delete** the `__get__` branch, the `_promoted_port_id` attribute, the stamp/clear, and switch `promotable_fields` to the port-id check.
- [ ] **Step 4: Run** the full settings + node + ui-menu suites — green. `grep -rn "_promoted_port_id" packages barn` → **zero** hits.
- [ ] **Step 5: Lint/type/commit** `refactor(promotion): retire _promoted_port_id + the __get__ read-tier branch (shared cell replaces the bridge)`.

---

### Task 7: UI verbs — extend the inlet-only menu to inlet/outlet per eligibility

The node right-click "Promote Setting" submenu (`promote.py`) currently promotes to an inlet only. Extend the verbs to offer the eligible directions per field (§B matrix), and keep "Detach from setting" (`port.py`) as the single demote verb. Per Plan-3 deviations, the menu uses `SelectionContextActions`/`PortContextActions`, NOT `NodeFocus`.

**Files:**
- Modify: `barn/haybale-graph-editor/.../panels/graph/menu/node/promote.py`
- Modify: `barn/haybale-graph-editor/.../panels/graph/menu/port/port.py`
- Modify: `barn/haybale-graph-editor/.../editors/graph_canvas/handlers/context_menu_actions.py` (`promote_setting` action gains a direction arg)
- Test: `tests/ui/menu/test_promote_demote_menu.py`, `tests/ui/menu/test_promotion_e2e.py`

**Interfaces:**
- `SelectionContextActions.promote_setting(node_id, accessor, field, direction)`.
- The submenu lists, per promotable field, the eligible directions (plain/shadow: inlet | outlet; watch: outlet only). `promotable_fields` returns eligibility (the `_read_only` check) so the menu doesn't offer an illegal direction.
- Demote verb unchanged (single verb; direction-agnostic).

- [ ] **Step 1: Write failing menu tests** — the submenu offers inlet + outlet for a plain/shadow field, outlet only for a watch field; clicking each calls `promote_setting` with the right direction; demote works from any direction.
- [ ] **Step 2: Implement** the menu + action changes.
- [ ] **Step 3: Run** the ui-menu suites — green.
- [ ] **Step 4: Lint/type/commit** `feat(ui): promote-to-direction submenu (inlet/outlet per eligibility)`.

---

### Task 8: Retire the `SettingWidgetModel` throwaway-field adapter (the P4-skipped Task 6)

With the value in the bag's cell (and, after Task 2.5, the cell holding the *resolved* global for mirror fields — the exact gap P4 skipped this task for), `SettingWidgetModel` can bind to that cell for **display** instead of a throwaway `DataField` it copies in/out. **But writes must NOT go raw to the cell.** A widget edit must go through the descriptor `setattr` so `_set_keys` set-vs-unset bookkeeping stays correct — a raw `cell.set_value` would change the value while leaving the field marked "unset/tracking," and the next registry sync (Task 2.5) would **overwrite the user's edit** (data loss; also breaks `shadow`'s "user override stops tracking"). So: **read the shared cell, write through `__set__`.** The setting stays the write-authority; the cell is shared for reads only.

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/panel/setting_widget_model.py`
- Modify: `packages/haywire-core/src/haywire/ui/panel/render_utils.py` (thread the owning `Settings` bag + descriptor down to `_resolve_widget_instance` so it can pass the cell for display + a setter that routes through `setattr`)
- Test: a model-level unit test + the existing panel tests (`tests/ui/panel/`).

**Interfaces:**
- `SettingWidgetModel` accepts a **provided** `DataField` (the bag's cell) for **display/read** (`apply_external` refreshes from it; the `on_changed` sync shows registry/edge changes live). Widget **edits** call the descriptor `setattr` (`setattr(obj, attr_name, v)`), NOT `cell.set_value` — so `_set_keys` is maintained and tracking stops on user override. Keep the create-own-field path only for standalone widgets with no bag.
- `render_utils._resolve_widget_instance` receives the bag + descriptor (currently only the descriptor); pass `bag._cell_for(descriptor)` for display and a setter closed over `(obj, attr_name)`.
- No reentrancy loop: an edit → `setattr` → `cell.set_value` → `on_changed` → `apply_external` no-ops on equal value (`setting_widget_model.py:67` already guards `if value != self._field.get_value()`); a registry sync → `cell.set_value` → `on_changed` → `apply_external` refreshes display but does NOT re-enter the registry. Add a reentrancy test.

- [ ] **Step 1: Confirm the panel reaches the cell + the descriptor** at bind time (thread `obj` through `_build_field_widget`→`_resolve_widget_instance`). Task 2.5 guarantees the cell holds the resolved value for mirror fields, so the display gap P4 flagged is already closed — no per-direction seeding needed here.
- [ ] **Step 2: Add failing tests** — (a) a widget edit lands via `setattr` and marks the field locally-set (`_set_keys`); (b) a write to the bag / a registry sync is reflected by the model's display; (c) reentrancy: neither path loops.
- [ ] **Step 3: Implement** read-from-cell + write-through-`setattr`; keep the standalone fallback.
- [ ] **Step 4: Run** UI + settings + panel suites — green.
- [ ] **Step 5: Lint/type/commit** `feat(ui): settings widget reads the shared cell, writes through the descriptor (retire throwaway adapter)`.

---

### Task 9: Full-suite verification

- [ ] **Step 1: Behavior-equivalence** — re-run the Task 1 characterization suite; the inlet path must still pass.
- [ ] **Step 2: Lint + format + type + full suite**
  ```sh
  uv run ruff check .
  uv run ruff format --check .
  uv run mypy packages/haywire-core/src/ barn/haybale-graph-editor/haybale_graph_editor/
  uv run pytest -q
  ```
  Expected: all clean/green.
- [ ] **Step 3:** Commit any fixups (skip if none).

---

### Task 10: Docs — settings-arch promotion section + ADR-C + glossary + roadmap

**Files:**
- Modify: `docs/architecture/settings/settings-arch.md` (a promotion-as-direction section; forward-ref from §6.4)
- Modify: `docs/components/nodes/` and/or `docs/components/settings/` promotion authoring guide (extend the inlet-only guide to inlet/outlet + the two-flag eligibility)
- Create: `docs/adr/0014-promotion-as-direction.md` (confirm next number at write time — 0013 is P4)
- Modify: `docs/reference/glossary.md` (add `promotion` / `inlet|outlet` / `is_linked_lazy`; the DECISIONS "Cross-cutting reminders" flag this)
- Modify: `internals/ideas/settings-datafield-unification-ROADMAP.md`
- Modify: `internals/ideas/settings-datafield-unification-DECISIONS.md` (annotate §B "config dropped" and §C4 "all outlets lazy" as superseded-by-this-plan, so the design doc doesn't contradict the landed code)

- [ ] **Step 1: Capture the mkdocs-strict warning baseline** (`uv run mkdocs build --strict 2>&1 | grep -i warning | sort > /tmp/mkdocs_baseline.txt`) BEFORE editing, like P4's Task 8 did, so you can prove your edits add none.
- [ ] **Step 2: Update `settings-arch.md`** — add a "Promotion = field + direction" section: a setting and a promoted port are one cell, two views; **two directions** (inlet/outlet) governed by two flag checks (read-only⇒outlet-only; outlet⇒lazy + self-propagate); the two verbs; the mirror-cell-authoritative rule. Point §6.4's "Deferred to P5" forward-ref at it and at ADR 0014.
- [ ] **Step 3: Find the next ADR number** (`ls docs/adr/ | grep -E '^[0-9]{4}-' | sort | tail -3` → expect `0014`).
- [ ] **Step 4: Write ADR-C** (`0014`, match `0011`/`0012`/`0013` prose; cite real lines):
  - **Status:** Accepted.
  - **Context:** the Plan-3 two-cell + `_promoted_port_id` read-tier bridge; cite the (now-deleted) `__get__` branch + `promotion.py` as they were.
  - **Decision:** promotion = field + direction; a setting and a port are one shared cell, two views (port `bind_field`s the P4 cell by reference); `promoted:true`+id is the whole binding signal; two directions (inlet/outlet), two verbs; eligibility = two flag checks; every promoted outlet is `is_linked_lazy` and self-propagates on `on_changed`; the mirror-field cell is authoritative in the setting.
  - **Record the design-doc deviations:** config direction dropped (unlinked inlet already shows its widget; `as_config` is pinless); `is_linked_lazy` generalized from watch-only to all-outlets. These supersede DECISIONS §B/§C4 — cite why (code facts).
  - **Supersedes** the Plan-3 two-cell + read-tier-bridge design (DECISIONS §E ADR-C). Trade-off: single shared cell + freeze-on-disconnect vs. the two-cell "preserve typed-earlier value" safety.
  - **Consequences:** `_promoted_port_id`, the read-tier branch, `StoreStrategy.NEVER`-as-bolt-on, and the `SettingWidgetModel` throwaway adapter all retire; the settings↔DataField arc (P1–P5) is complete.
- [ ] **Step 5: Update the glossary** — add the promotion/direction/`is_linked_lazy` vocabulary (two directions); if the `Settings` entry still describes an old chain, reconcile it with the landed model.
- [ ] **Step 6: Build docs strict** — no NEW warnings vs the Step 1 baseline.
- [ ] **Step 7: Commit docs** `docs(adr): ADR 0014 promotion-as-direction; arch promotion section; glossary`.
- [ ] **Step 8: Mark P5 landed in the roadmap** — mark the P5 row **LANDED** (commit range + this plan's filename) and add a `[LANDED]` header + landing summary to the `## P5` section (mirror P4). Note that this **completes the arc** (P1–P5). Commit `docs(roadmap): mark P5 (promotion-as-direction) landed — arc complete`.

---

## Self-Review notes (for the executor)

- **The reference-sharing spine (Task 2) is the whole idea.** The port does not own a value; it *is* a second view of the setting's P4 cell. Every later task (serialization, read-tier retirement, widget-adapter retirement) falls out of "one cell, two views." If you find yourself copying a value between a port and a setting, stop — that is the two-cell design P5 exists to kill.
- **Do NOT reset the cell on any structural action (§C3).** Promote, demote, link, unlink, redirect — none touch the value. Only edit / edge-drive / explicit reset change it. `demote` keeps the (possibly edge-driven) value; recovery is reset-to-default. Test this explicitly (Task 3 Step 4).
- **Two verbs only.** No in-place redirect. Redirect = demote + re-promote; the cell survives both and eligibility is re-checked. Don't add a third verb.
- **Inherit `ShowWidgetStrategy`, don't reinvent.** Direction → factory → per-direction `show_widget` default. Passing `show_widget` explicitly per promote is a smell. (This is also what makes a promoted inlet show its widget when unlinked — delete the old `show_widget=NEVER` inlet override.)
- **The matrix is two flag checks, not per-kind logic.** `_read_only` ⇒ outlet-only; direction=outlet ⇒ lazy + `on_changed→propagate`. Every other case (mirror vs plain, set vs unset) rides the one `on_changed → propagate` mechanism. If you find yourself branching on field-kind inside propagation, stop.
- **`is_linked_lazy` = every promoted outlet, plain included** (corrects the original "watch-specific" framing). The discriminator is "setting-driven ⇒ out-of-frame," true of all promoted outlets. And the lazy flag alone is inert — the **outlet's `on_changed → propagate` is what triggers the pull** (verified `pipe.py`/`port.py`); it is required, not optional. The setting writes its cell (oblivious to ports); the *port* reacts to *its* cell.
- **"Setting oblivious" = oblivious to PORTS, not passive about value.** The setting keeps its own mirror cell synced to the resolved global (Task 2.5). The port never appears in settings code; the setting's value-correctness never depends on a port.
- **Back-compat is a clean cutover** (Task 4) — the Plan-3 promoted format never shipped off this branch, so P5 changes the shape freely and migrates any local fixture. Confirm no old-shape graph is relied on.
- **Load order is settings-FIRST** (corrects the original "non-issue, no fix needed" note). The *value* lands correctly either way (in-place cell mutation), but binding the outlet's `on_changed` subscription *before* `bag.from_dict` would propagate mid-load. Restore settings → then ports, so the value is in the cell before the port subscribes. Save order is genuinely irrelevant (pure-read dict literal).
- **This closes the arc.** After Task 10, P1–P5 have all landed on `feat/type-floor-hoist`; the branch becomes a merge candidate (finishing-a-development-branch). Do NOT merge mid-plan.
- **If task count balloons** (11 tasks now, with 2.5 added), the natural split is: Tasks 1–6 (core: `bind_field` + mirror-cell authority + matrix + serialization + read-tier retirement) as "P5a", Tasks 7–8 (UI verbs + widget-adapter retirement) as "P5b". Both halves are independently green; the ADR (Task 10) lands with P5b.
