# A setting's per-instance value lives in a per-field DataField cell (single-cell model)

**Status:** Accepted.

A `Settings` instance's per-field value used to live in an untyped `_local_store: dict[str, Any]`, and the `setting` descriptor ran in one of two modes: a *simple* mode that read/wrote `_local_store` by attribute name, and an *extended* mode (registry injected) that walked the resolution chain and, for a local override, recomputed the resolved value on every read. The UI bridged this with a throwaway `DataField` in `SettingWidgetModel` that it copied values into and out of. This ADR records replacing `_local_store` with a per-field **`DataField` cell** — the same cell a port uses — so a setting and a port become two views of one value. It is plan **P4** of the settings↔DataField unification arc (canonical-key → tier-collapse → TOML→JSON → **single-cell** → promotion-as-direction). P1 (canonical `storage_key`), P2 (tier collapse to set-or-unset), and P3 ([ADR 0012](0012-settings-json-persistence.md), TOML→JSON + the IType `to_dict`/`from_dict` seam) all landed first, and P4 builds on them.

## Context — an untyped dict, a dual mode, and a recompute-on-read

Three things sat in the way of the "settings and ports are the same value" model:

- **The untyped store.** Every `Settings` instance held `_local_store: dict[str, Any]` (`settings.py`). The value was a raw Python object; complex ITypes (`COLOR`, the `VEC*` types) had no cell to carry their IType round-trip at the instance level — only the registry's disk edge did (P3).
- **The `_registry is None` dual mode.** `setting.__get__`/`__set__` branched on whether a registry was injected: *simple* mode read/wrote `_local_store` by attribute name; *extended* mode walked `_resolve`. Two code paths for one conceptual operation ("read this field's value").
- **Recompute-on-read.** In extended mode a *local override* was re-resolved through the chain on every read, even though the instance already held the overriding value.
- **The throwaway-field bridge.** `SettingWidgetModel` (`packages/haywire-core/src/haywire/ui/panel/setting_widget_model.py`) built a real `DataField` for the widget, seeded it with the setting's current value, and copied edits back through the panel setter — a copy-in/copy-out adapter standing in for the cell the value should have lived in all along.

## Decision

A setting's per-instance value lives in a per-field `DataField` cell on the bag, built lazily from the field's IType by `Settings._cell_for(descriptor)` and cached in `self._cells` keyed by `storage_key`.

- **`cell ?? default` resolution.** `setting.__get__` returns the cell value when the field is locally set, else the per-kind default (a plain literal, or `registry.resolve(...)` for a shadow/watch/extended field). The dual `_registry is None` mode collapses to one question — "is this field locally set?" — and the local-override case returns the cell's held value instead of re-resolving (recompute-on-read gone).
- **`_set_keys` carries the opinion.** A `DataField` always holds *a* value (its default), so cell membership can't encode "overridden" the way dict membership did. `Settings._set_keys: set[str]` records the set-or-unset opinion explicitly — the same set-or-unset shape P2 gave the registry tiers. `__set__`/`from_dict` add the `storage_key`; `reset` discards it; `is_locally_set(name)` ⇔ membership. Set-ness is never inferred from `cell.get_value() != default` (that would misread "set to the default on purpose" and re-introduce the phantom-override bug P2 fixed at the tier level).
- **The cell-mutation spine.** No *structural* action resets a cell. Its **value** returns to default only on an explicit `reset()` (or, in P5, an edge-drive); `reset` clears `_set_keys` and calls `cell.reset()` but never removes the cell. This stable identity is what a future port binds to.
- **Registry tiers unchanged.** The global/workspace tiers, `save_to_json`/`load_from_json`, and `persistent_setting`'s registry write are untouched (P2/P3). Only the *instance-local* store changed.
- **Wire shape preserved.** `bag.to_dict()` still emits `{attr_name: bare_value}` per locally-set field (via `cell.get_value()`, not the IType `to_dict` dict), and `from_dict` writes each value back into the cell. Existing saved graphs load unchanged; complex ITypes round-trip losslessly because the *cell* guarantees the IType round-trip.
- **Object-typed escape hatch.** A field with no IType (`_type is object`) can't build a cell, so `_cell_for` returns `None` and those fields fall back to a narrow `_plain: dict`. `SettingDescriptor.__set_name__` enforces an IType on every declared field, so `_plain` stays empty in practice — it is defensive, not a revived general store. *(Since removed: settings were committed to as IType-only, `_plain` was deleted, and `_cell_for` now raises for a non-IType descriptor.)*

## Coordination with DECISIONS.md §D

`settings-datafield-unification-DECISIONS.md` §D-A says a tier should store the IType's `to_dict`, `resolve()` should return the **raw serialized form**, and the consuming **field rehydrates via `from_dict`** into its cell. P3 deliberately deviated ([ADR 0012](0012-settings-json-persistence.md)): the in-memory tier holds the **live** Python value and `resolve()` returns it live, with `to_dict`/`from_dict` only at the disk edge.

P4 keeps P3's disk-edge contract. The cell materializes from a live value — `registry.resolve()` already returns a live value, so `cell.set_value(resolved_value)` needs no `from_dict` hop. **The cell IS the "field that holds the value" §D refers to; §D is satisfied in substance once the value lives in a cell.** The literal "tier stores `to_dict`" representation was judged unnecessary churn given P3's disk-edge seam already provides one serialization contract across the system. If a future reviewer wants the literal tier-stored-dict form, that is a separate, behavior-neutral registry-internal change — not gated by P4.

## Scope and what is deferred to P5

P4 is **value-into-cell + dual-mode removal only**. It stops before *promotion*, which is P5:

- **Promotion = field + direction.** The direction-eligibility matrix (DECISIONS §B), the `_promoted_port_id` read-tier branch in `setting.__get__` (kept **verbatim** in P4), and `is_linked_lazy` / watch→outlet emit (§C4) are all P5. The ADR for promotion-as-direction (DECISIONS §E's ADR-C-promotion) is P5's.
- **The throwaway-field bridge stays.** Binding `SettingWidgetModel` directly to the bag's cell was gated and **skipped**: the widget must display the *resolved* value, but an unset extended/mirror field's cell holds only the descriptor default (the resolved global lives in the registry). Reconciling that display gap is exactly P5's promotion-as-direction work, where the port reaches the cell cleanly. The copy-in/copy-out adapter is left for P5 to retire.

## Consequences

- **One value model.** A setting's per-instance value and a port's value are the same `DataField` cell; the `_registry is None` dual mode and recompute-on-read are gone. "Locally set" is `_set_keys` membership everywhere (`to_dict`, `from_dict`, `reset`, `is_locally_set`, `_on_field_change`).
- **Complex ITypes round-trip at the instance level.** `COLOR`, `VEC2I`, `VEC3F`, … survive a bag `to_dict`/`from_dict` cycle losslessly, exercising the same IType seam P3 introduced.
- **Behavior-preserving refactor of storage.** A characterization suite (`tests/core/test_settings/test_single_cell.py`) pins the public API through the migration; every commit stayed green (no intentionally-red window).
- **Supersedes** the "simple mode / extended mode" dual-mode prose in `architecture/settings/settings-arch.md` (rewritten to the single-cell model, §6.4).
- P4 is the cell; **P5** builds promotion-as-direction on it and retires the UI's throwaway-field bridge.

---

## Amendment — cell-authoritative reads, registry-owned cells, one change primitive

*(Originally ADR 0016, folded in here as a refinement of the single-cell model. Depends on the promotion work in [ADR 0014](0014-promotion-as-direction.md).)*

**Context.** After P4 (above) and promotion ([ADR 0014](0014-promotion-as-direction.md)), a setting's value already lived in a `DataField` cell — but only *sometimes* authoritatively. `setting.__get__` had four semantically different paths: locally-set → cell; unset cross-mirror → cell (kept current by P5's sync); unset plain node field → a registry walk that ALWAYS ended in a swallowed `KeyError` (node settings have no registry definitions — the workspace/global tiers can never apply to them), paying a function-level import, branching, and an exception construction per read on the node-execution hot path; persistent (Framework/Library) fields → a genuine tier walk, with every rendered widget synthesizing a throwaway `DataField` plus a subscribe/re-resolve/apply loop to compensate for the value having no live cell home. Change notification ran over three overlapping channels (`Settings._callbacks` fan-out, `_on_property_change`, an unused `on_change='method'` string dispatch with a fragile two-arity `TypeError` fallback), and Framework/Library schemas stamped `_mirror_key = _setting_key` ("a mirror of itself") purely to ride the mirror subscription machinery.

**Decision.** The cell is authoritative everywhere; the resolution chain runs at **write/seed time only**.

- `setting.__get__` is a pure cell read — `obj._cell_for(self).get_value()` — on every path. No mode branch, no locally-set check, no chain walk.
- **Registry-owned cells**: a wired persistent field has no per-instance state (writes go to the tiers), so the registry owns one live `DataField` per definition (`registry.cell_for(key)`), lazily created, seeded via `resolve()`, stamped `field_id = key`, kept current by a single write-through in `_notify_subscribers` (every tier mutation funnels there), and dropped with its definition on hot-reload unregister. Instances' `_cell_for` *borrows* it — one cell, N views. The settings panel binds this same cell, deleting the throwaway per-widget field and its sync loop.
- **One change primitive**: `DataField.on_changed` fires `FieldChange(value, old, field_id)`; `bag.subscribe(cb)` attaches one adapter per field cell, so a subscriber hears every writer uniformly — descriptor sets, resets, registry write-through, and edge drives into a promoted shared cell (previously silent). `setting.__set__` records the set-opinion *before* the cell write so callbacks observe `is_locally_set()` correctly. Deleted: `Settings._callbacks`, `_on_property_change`, the `on_change=` string dispatch, and the `stored=` flag (only user was the testbed field exercising it).
- **Self-mirror hack removed**: `_mirror_key` means only "mirrors another setting"; `is_cross_mirror` is `bool(_mirror_key)`.
- **Exact-key registry subscriptions** (plus `None` listen-all for the debug configurator); the namespace-prefix walk lost its last consumer with the panel convergence and is gone.

**Callable defaults stay.** The plan proposed dropping them on a zero-usage claim that proved wrong: `ui/skin/settings.py` passes `_default_skin` by function reference for genuine late binding (the skin registry doesn't exist at class-definition time). A callable default now evaluates **once, at cell-seed time** — never per read.

**Consequences.** The node-execution hot path (`self.<bag>.<field>` in `worker()`) is one dict hit + one attribute read, with no per-read exception. Correctness moves from pull (self-healing, re-derived per read) to push: a future tier-mutation path that bypasses `_notify_subscribers` would leave registry cells stale — keep tier mutations funnelling through it. `Settings.cleanup()` MUST run on bag teardown: adapters attached to borrowed registry-owned cells outlive the bag otherwise. Behavior changes: `from_dict` restores notify already-attached subscribers (graph load restores before anything subscribes); `reset()` notifies through the cell event; a field's value is never the raw callable (seeded once). Widgets on a dropped definition (hot-reload) hold a frozen, orphaned cell until their panel re-renders. `resolve()` and its `(value, source)` contract are unchanged for tier-aware UI display.
