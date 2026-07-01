# Settings ↔ DataField Unification — Plan Roadmap (P1–P5)

> **Pick-up doc for a fresh session.** The full *design* is in
> [`settings-datafield-unification-DECISIONS.md`](settings-datafield-unification-DECISIONS.md)
> (resolved via the inquisition interview). The original idea is
> [`settings-datafield-unification.md`](settings-datafield-unification.md). This file is the
> *sequencing*: what each plan covers, its prerequisites, the exact code sites, and the traps —
> enough for the next session to write P2 (then P3…) without re-deriving anything.

## How to use this doc

1. **Branch:** the whole arc lands on one feature branch (`feat/type-floor-hoist` at time of
   writing). Stay on it across all five plans — do NOT merge to master between plans. The gate
   between plans is "previous plan committed and **green on this branch**" (tests + ruff + mypy
   clean), not a merge.
2. Open `DECISIONS.md` for the *why* of every choice (sections A–E are cross-referenced below).
3. Write the plan with the **writing-plans** skill, saving to
   `internals/superpowers/YYYY-MM-DD-<name>.md` (this repo keeps plans under
   `internals/superpowers/`, not `docs/`). Read the cited code sites first (they may have
   shifted line numbers — grep by symbol, not line).
4. ADRs are the **final task of whichever plan lands each decision** (DECISIONS.md §E) — never
   written up-front.

## Status

| Plan | Name | Status | Plan file |
| --- | --- | --- | --- |
| **P1** | Canonical key (`storage_key`) | **LANDED** (540b8a8c..ff02354a, feat/type-floor-hoist) | `internals/superpowers/2026-06-30-settings-canonical-key.md` |
| **P2** | Tier collapse / drop OVERRIDE | **LANDED** (14e9f04e..HEAD, feat/type-floor-hoist) | `internals/superpowers/2026-06-30-settings-tier-collapse.md` |
| **P3** | TOML → JSON persistence cutover | **LANDED** (85c881d5..HEAD, feat/type-floor-hoist) | `internals/superpowers/2026-06-30-settings-toml-json-cutover.md` |
| **P4** | Single-cell unification (+ dual-mode dissolution) | **LANDED** (d3bd20e8..HEAD, feat/type-floor-hoist) | `internals/superpowers/2026-06-30-settings-single-cell-unification.md` |
| **P5** | Promotion = field + direction (+ `is_linked_lazy`) | **LANDED** (889cd93c..HEAD, feat/type-floor-hoist) | `internals/superpowers/2026-06-30-settings-promotion-as-direction.md` |

Dependency order is strict: **P1 → P2 → P3 → P4 → P5.** (P3 can in principle swap with P2, but
P2 first is cleaner: collapsing tiers shrinks what P3 has to serialise.)

---

## P1 — Canonical key (`storage_key`)  [LANDED]

- **Decision:** DECISIONS.md C (footprint, idea #2). **Scope:** idea #2 ONLY — local-store
  keying unified behind `setting.storage_key`. **No-op refactor.**
- **Explicitly deferred to P4:** idea #1 (remove `_registry is None` "simple mode") — it's
  behavioural (NodeProperties + test fixtures use simple mode) and dissolves naturally once the
  single cell lands. Do NOT bundle it here.
- **Key trap (already handled in the P1 plan):** do not make `_setting_key` always-non-empty —
  three registry guards (`registry.py:166/188/242`) use the empty sentinel to mean "not
  namespaced → not registry-eligible." `storage_key` returns `_setting_key or _attr_name` and
  unifies *local-store* keying only.
- Plan file: `internals/superpowers/2026-06-30-settings-canonical-key.md`. Landed as 4 commits
  (540b8a8c..ff02354a) on `feat/type-floor-hoist`; final whole-branch review: Ready to merge.
- **Carried forward from P1's final review (apply when relevant below):**
  - `settings.py:93` (`_resolve`'s local-store read) is keyed directly by `_setting_key`, NOT
    routed through `storage_key` — a 7th, read-only, un-unified local-store site. Harmless today
    (the key only differs from `storage_key` when unreachable), but P4 (single-cell) MUST migrate
    this read in lockstep with the cell-mutation spine or read/write keys can diverge.
  - `test_canonical_key.py`'s extended-mode case proves `storage_key == _setting_key` key
    equality for `persistent_setting`, but does NOT exercise the 5 refactored container methods
    in extended mode (persistent_setting never touches `_local_store`). That coverage instead
    lives in `tests/core/node/` + `test_persistent_setting.py`. Don't treat
    `test_canonical_key.py` as the container-method extended-mode guard in later plans.

---

## P2 — Tier collapse / drop OVERRIDE  [LANDED]

> Landed on `feat/type-floor-hoist` (14e9f04e..HEAD) via
> `internals/superpowers/2026-06-30-settings-tier-collapse.md`. `SettingValue` is now
> set-or-unset (`is_set`), `resolve()` is the 4-case highest-set-wins walk, `SettingMode`
> and the `{override=true}` TOML form are gone, and the "unset tracks; set ignores" rule
> is live in `_on_field_change`. Rationale: `docs/adr/0011-collapse-settings-tiers.md`.

- **Decision:** DECISIONS.md **A**. Two tiers (global="user" + workspace); drop `OVERRIDE`
  mode; `SettingMode` becomes vestigial; resolution becomes `cell ?? default` where `default`
  is a per-kind strategy (plain=literal, shadow/watch=`registry.resolve(global<workspace)`).
- **Reactive-default rule (shadow):** "unset tracks; set ignores" (DECISIONS.md A). When the
  cell is unset the field re-resolves on a global change and fires `on_change`; when set, the
  value is unchanged but the reset-target moves silently.
- **Prerequisite:** P1 (uses `storage_key`).
- **Code sites:**
  - `settings/value.py` — `SettingValue(mode, value)`; `mode` and `is_inherit/is_explicit/
    is_override` helpers all collapse. Likely reduce `SettingValue` to a bare value or a
    "set/unset" marker.
  - `settings/enums.py` — `SettingMode` (INHERIT/EXPLICIT/OVERRIDE). Remove OVERRIDE; decide if
    the enum survives at all.
  - `settings/registry.py` — `resolve()` six-case chain → two-case; `set_global(mode=…)` loses
    the mode param; `_global_tier_values`/`_workspace_tier_values` entries lose mode;
    `save_to_toml` (line ~663-666) drops the `{override:true, value:…}` inline-table branch.
  - `settings/settings.py` — `_resolve()` (lines ~79-107) collapses; `_on_field_change`
    (line ~120-141) drops the `value.mode != OVERRIDE` suppression check → becomes the
    "unset tracks / set ignores" rule.
  - **UI blast radius (don't miss):** `ui/panel/render_utils.py` and `ui/widget/binding.py`
    read `.mode` / the override affordance. The "• overridden + reset" panel UI currently keys
    off mode; rework to key off "cell is set" (`is_locally_set`).
  - `resolve()`'s `source` return values (`global_override`/`workspace_override`) shrink.
- **Traps:** `SettingsTestContext.set_override` (test_config.py:254) and any test asserting
  OVERRIDE precedence must be deleted/rewritten. The settings-arch doc §1-4 and §3 (the
  "five claims, one wins" + OVERRIDE TOML form) must be rewritten to the 2-tier model.
- **ADR-A** is the final task (supersedes settings-arch §1-4; loses admin-force-on-lab-machine).
- **Glossary:** the `Settings` entry was flagged stale during the interview — rewrite it to the
  collapsed ladders when P2 lands (it currently still describes the 6-tier chain).

## P3 — TOML → JSON persistence cutover  [LANDED]

> Landed on `feat/type-floor-hoist` (85c881d5..HEAD) via
> `internals/superpowers/2026-06-30-settings-toml-json-cutover.md`. Both tiers persist as JSON
> (`~/.haywire/settings.json`, `<workspace>/.haywire/settings.json`); each value serializes
> through its IType's `to_dict`/`from_dict` via the `_value_to_jsonable`/`_value_from_jsonable`
> seam, with `COLOR` + the six `VEC*` `from_dict` overrides fixed first. Hard cutover, no
> migration — old `.toml` is ignored. Rationale: `docs/adr/0012-settings-json-persistence.md`.
>
> **Deliberate deviation from DECISIONS.md §D:** P3 serializes **at the disk edge** only — the
> in-memory tier keeps the live Python value and `resolve()` is unchanged. The §D tier-value-form
> (tier stores the `to_dict` dict; `resolve()` returns the raw dict; the field `from_dict`s it) is
> **deferred to P4**, where the `DataField` cell + field-rehydration hook make it green. See the
> ADR's "Deliberate scoping vs DECISIONS.md §D" section.

- **Decision:** DECISIONS.md **D** + the tier-value-form answer: **A — the tier stores the
  IType's `to_dict`; `resolve()` returns the raw dict; the consuming field `from_dict`s it.**
  Registry stays a type-agnostic JSON store. "One serialization contract everywhere" — the same
  `to_dict`/`from_dict` a field uses for graph JSON.
- **Why it's needed:** complex ITypes ALREADY live in `LibrarySettings` today (`testing.py` has
  `setting[COLOR]`, `setting[VEC2I]`, `setting[VEC3F]`) and TOML can't cleanly represent their
  nested `to_dict`.
- **Prerequisite:** P2 (no OVERRIDE inline-table to port).
- **Code sites (the ~6 TOML read/write points, all in `settings/registry.py`):**
  - `import toml` (line 21) → `json`.
  - `load_from_toml` (line ~325) → `load_from_json`; `toml.load` at lines 357, 410.
  - `save_to_toml` / `save_to_toml_debounced` (lines ~623, 645); `toml.dump` at line 673.
  - Paths: `~/.haywire/settings.toml` → `.json`, `<ws>/.haywire/settings.toml` → `.json`
    (lines 7-8, 57-58, 331-332 docstrings + the path constants).
- **Hard cutover, no migration** (DECISIONS.md D): existing `.toml` NOT read/converted. **Must
  surface the data drop at ship time** (changelog / first-run notice) — make this a plan task.
- **ADR-B** is the final task (supersedes the deliberate "TOML for hand-editability" choice).

## P4 — Single-cell unification (+ dual-mode dissolution)  [LANDED]

> Landed on `feat/type-floor-hoist` (d3bd20e8..HEAD) via
> `internals/superpowers/2026-06-30-settings-single-cell-unification.md`. A setting's per-instance
> value lives in a per-field `DataField` cell (`Settings._cell_for` → `self._cells`, keyed by
> `storage_key`) — the same cell a port uses. `setting.__get__`/`__set__` read/write the cell;
> `cell ?? default` resolution collapses the `_registry is None` dual-mode (idea #1) and the
> local-override recompute-on-read (idea #3). `_set_keys` carries the set-or-unset opinion (the
> cell always holds a value, so membership can't). `to_dict`/`from_dict`/`reset`/`is_locally_set`/
> `_on_field_change` all key off `_set_keys` + cells; `_local_store` is removed (a narrow `_plain`
> dict remains only for the object-typed escape hatch). Wire shape unchanged — `bag.to_dict()`
> emits the bare value per field, so existing graphs load. Rationale:
> `docs/adr/0013-settings-single-cell.md`.
>
> **Scope: value-into-cell + dual-mode removal only.** Promotion (field + direction), the
> `_promoted_port_id` read-tier branch (kept verbatim), and `is_linked_lazy` / watch→outlet emit
> are **P5**. The optional Task 6 (bind `SettingWidgetModel` to the bag's cell) was **skipped**:
> an unset extended/mirror field's cell holds only the descriptor default, not the resolved global
> the widget must display — reconciling that gap is P5's promotion-as-direction work, where the
> port reaches the cell cleanly. The throwaway-field bridge stays until then.
>
> **§D coordination:** P4 satisfies DECISIONS §D's "field rehydrates into its cell" *in substance*
> (the cell IS that field) while keeping P3's disk-edge serialization. The literal "tier stores
> `to_dict`" form was judged unnecessary churn given P3's disk-edge seam already gives one
> serialization contract. See the ADR's "Coordination with DECISIONS.md §D" section.

- **Decision:** DECISIONS.md **A (cell ?? default), C2 (binding/serialization), C3 (the
  cell-mutation spine), idea #1 + #3 + #4.** This is the core: a setting's value LIVES in a
  `DataField`, not `_local_store`.
- **The cell-mutation spine (DECISIONS.md C3):** no structural action ever resets the cell;
  value changes only by (a) widget/panel edit, (b) edge drive while linked, (c) explicit
  reset-to-default. This resolves demote/unwire/direction-change/hot-reload at once.
- **Brings in (now dissolve by construction):**
  - idea #1 — `_registry is None` dual-mode collapses (one cell, no "simple vs extended").
  - idea #3 — recompute-on-read → hold-the-cell, invalidate via `_on_field_change`.
  - idea #4 — `_promoted_port_id`/`_mirror_*` instance-state-on-class-descriptor moves onto the
    field/instance.
- **Prerequisite:** P1, P2, P3.
- **Code sites:**
  - `settings/settings.py` — `_local_store` dict → per-field `DataField` cells; `_resolve`,
    `to_dict`/`from_dict`, `reset`, `is_locally_set` re-expressed against cells. The 32
    dual-mode/`_local_store` references found across `settings/` collapse here.
  - `settings/descriptor.py` — `setting.__get__`/`__set__` read/write the cell; the
    `_registry is None` branches (lines 309, 384) go; `_resolve` simplifies.
  - `core/types/fields.py` — `DataField` is the cell; confirm `to_dict`/`from_dict` round-trip
    is the same contract P3 relies on.
  - `core/node/data.py` — the settings bag holds cells; bag created at `__init__` (lines 70-78,
    incl. the `_node` back-ref) — cell exists before any port (this is what makes P5's
    reference-binding order-independent).
- **Note:** this plan is large; consider splitting into "value-into-cell" + "dual-mode removal"
  sub-plans if task count balloons.

## P5 — Promotion = field + direction (+ `is_linked_lazy`)  [LANDED]

> Landed on `feat/type-floor-hoist` (2d371444..HEAD) via
> `internals/superpowers/2026-06-30-settings-promotion-as-direction.md`. A promoted port borrows
> the setting's P4 cell BY REFERENCE (`DataPort.bind_field`) — one cell, two views; no second
> value, no `_promoted_port_id`, no read-tier bridge. `promote_setting(node, accessor, field,
> direction)` takes a `PortType ∈ {INLET, OUTLET}` (config dropped); eligibility is two flag
> checks (read-only ⇒ outlet-only; direction=outlet ⇒ `is_linked_lazy` + `on_changed→propagate`).
> The mirror-field cell is made authoritative in the setting (new Task 2.5) so a promoted mirror
> reads correctly headless. Serialization is value-less (`promoted:true` + id, no recipe/field_data)
> and load is settings-first so a promoted outlet binds a cell already at value (no mid-load
> propagation). Demote freezes the value (§C3). The `SettingWidgetModel` throwaway-field adapter is
> retired (binds the shared cell for display, writes through the descriptor `__set__`). Rationale:
> `docs/adr/0014-promotion-as-direction.md`. **This completes the arc (P1–P5).**
>
> **Design-doc deviations (recorded in ADR 0014, supersede DECISIONS §B/§C4):** config direction
> dropped (unlinked inlet already shows its widget; `as_config` is pinless); `is_linked_lazy`
> generalized from watch-only to *all* promoted outlets (the real discriminator is
> "setting-driven ⇒ out-of-frame"), and the flag needs the `on_changed→propagate` trigger to
> fire (the flag alone is inert).

- **Decision:** DECISIONS.md **B (matrix + per-direction ownership), C2 (oblivious setting,
  port borrows cell by reference), C3 (two verbs only), C4 (`is_linked_lazy`/watch→outlet),
  C5 (hot-reload).**
- **Matrix:** plain/shadow → inlet|config|outlet; watch → outlet ONLY. Single invariant:
  read-only ⇒ outlet-only. Two verbs only: `promote(direction)` + `demote` (no in-place
  redirect; redirect = demote + re-promote; cell survives both).
- **Serialization (C2):** promoted port = `{promoted:true, id(=setting key), port_type, display}`
  — NO `recipe` (type derived from setting), NO `field_data` (value via settings block). Port
  borrows the setting's cell BY REFERENCE → load-order-independent. `from_spec` gains a
  promoted branch. `StoreStrategy.NEVER` bolt-on retires naturally.
- **`is_linked_lazy` (C4):** new general-purpose port flag; when set, port forces linked edges
  `is_lazy=True` at link time. watch→outlet sets it → consumer pulls live registry value on its
  next execution. Reusable beyond watch. Out of scope: idle-liveness (registry → scheduler).
- **Retires (idea doc "what this retires"):** `_promoted_port_id` flag, `store_strategy=NEVER`
  on promoted port, the bespoke read-tier branch in `__get__`, `SettingWidgetModel.create_field`
  adapter (the setting already HAS a DataField).
- **Prerequisite:** P1–P4 (needs the single cell).
- **Code sites:**
  - `core/node/promotion.py` — the whole module reworks (currently encodes a separate port +
    `_promoted_port_id`; now attaches a direction to the existing field's cell).
  - `core/types/port.py` — `from_spec` (line ~580) promoted branch; `to_dict` (line ~651)
    skips recipe/field_data for promoted; add `promoted` + `is_linked_lazy` fields; `set_value`
    (line ~272) outlet path; `_pipes.propagate` (line ~308).
  - `core/types/pipe.py` — `Pipe.is_lazy`/`pull()` (always-latest) is the mechanism
    `is_linked_lazy` rides; verify no change needed beyond forcing the flag at link.
  - `core/types/enums.py` — `ShowWidgetStrategy` per-direction defaults (inlet NOT_LINKED,
    config ALWAYS, outlet NEVER) already exist — reuse, don't reinvent (retires idea #5).
  - `core/edge/edge_wrapper.py` — `is_lazy` plumbing.
  - **UI (barn):** `barn/haybale-graph-editor/.../handlers/context_menu.py` +
    `context_menu_actions.py` — promote/demote verbs (Plan 3 landed inlet-only here; extend to
    the direction matrix). Per Plan-3 deviations: menu uses `SelectionContextActions` /
    `PortContextActions`, NOT `NodeFocus`.
- **ADR-C** is the final task (supersedes the Plan 3 two-cell + read-tier-bridge design).

---

## Cross-cutting reminders

- **Glossary** (`docs/reference/glossary.md`): the `Settings` entry still describes the OLD
  6-tier chain — rewrite at P2. Add entries for `DataField`/`promotion`/`inlet|config|outlet`
  vocabulary as those land (P4/P5). The interview deliberately did NOT overwrite it while the
  model was unbuilt.
- **Docs** (`docs/components/settings/`, `docs/architecture/settings/`): rewrite per plan as
  each lands — architecture documents ONLY the current solution; the superseded model lives in
  the ADRs.
- **Three landed plans this arc builds on:** type-floor-hoist, widget-unification,
  promote-setting-to-inlet (see their `-DEVIATIONS.md` for landed names — e.g. promotion uses
  `encode_promoted_port_id`, `rejig(include=[pid])`, ports serialize as a dict keyed by id).
