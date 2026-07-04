---
status: accepted
extends: ADR-0013
see-also: ADR-0015
---

# Cell-authoritative settings: pure cell reads, registry-owned cells, one change primitive

**Context.** After P4 (ADR 0013) and promotion (ADR 0014/0015), a setting's value
already lived in a `DataField` cell — but only *sometimes* authoritatively.
`setting.__get__` had four semantically different paths: locally-set → cell;
unset cross-mirror → cell (kept current by P5's sync); unset plain node field →
a registry walk that ALWAYS ended in a swallowed `KeyError` (node settings have
no registry definitions — the workspace/global tiers can never apply to them),
paying a function-level import, branching, and an exception construction per
read on the node-execution hot path; persistent (Framework/Library) fields →
a genuine tier walk, with every rendered widget synthesizing a throwaway
`DataField` plus a subscribe/re-resolve/apply loop to compensate for the value
having no live cell home. Change notification ran over three overlapping
channels (`Settings._callbacks` fan-out, `_on_property_change`, an unused
`on_change='method'` string dispatch with a fragile two-arity `TypeError`
fallback), and Framework/Library schemas stamped `_mirror_key = _setting_key`
("a mirror of itself") purely to ride the mirror subscription machinery.

**Decision.** The cell is authoritative everywhere; the resolution chain runs
at **write/seed time only**.

- `setting.__get__` is a pure cell read — `obj._cell_for(self).get_value()` —
  on every path. No mode branch, no locally-set check, no chain walk.
- **Registry-owned cells**: a wired persistent field has no per-instance state
  (writes go to the tiers), so the registry owns one live `DataField` per
  definition (`registry.cell_for(key)`), lazily created, seeded via
  `resolve()`, stamped `field_id = key`, kept current by a single write-through
  in `_notify_subscribers` (every tier mutation funnels there), and dropped
  with its definition on hot-reload unregister. Instances' `_cell_for`
  *borrows* it — one cell, N views. The settings panel binds this same cell,
  deleting the throwaway per-widget field and its sync loop.
- **One change primitive**: `DataField.on_changed` fires
  `FieldChange(value, old, field_id)`; `bag.subscribe(cb)` attaches one
  adapter per field cell, so a subscriber hears every writer uniformly —
  descriptor sets, resets, registry write-through, and edge drives into a
  promoted shared cell (previously silent). `setting.__set__` records the
  set-opinion *before* the cell write so callbacks observe `is_locally_set()`
  correctly. Deleted: `Settings._callbacks`, `_on_property_change`, the
  `on_change=` string dispatch, and the `stored=` flag (only user was the
  testbed field exercising it).
- **Self-mirror hack removed**: `_mirror_key` means only "mirrors another
  setting"; `is_cross_mirror` is `bool(_mirror_key)`.
- **Exact-key registry subscriptions** (plus `None` listen-all for the debug
  configurator); the namespace-prefix walk lost its last consumer with the
  panel convergence and is gone.

**Callable defaults stay.** The plan proposed dropping them on a zero-usage
claim that proved wrong: `ui/skin/settings.py` passes `_default_skin` by
function reference for genuine late binding (the skin registry doesn't exist
at class-definition time). A callable default now evaluates **once, at
cell-seed time** — never per read.

**Consequences.** The node-execution hot path (`self.<bag>.<field>` in
`worker()`) is one dict hit + one attribute read, with no per-read exception.
Correctness moves from pull (self-healing, re-derived per read) to push: a
future tier-mutation path that bypasses `_notify_subscribers` would leave
registry cells stale — keep tier mutations funnelling through it.
`Settings.cleanup()` MUST run on bag teardown: adapters attached to borrowed
registry-owned cells outlive the bag otherwise. Behavior changes:
`from_dict` restores notify already-attached subscribers (graph load restores
before anything subscribes); `reset()` notifies through the cell event; a
field's value is never the raw callable (seeded once). Widgets on a dropped
definition (hot-reload) hold a frozen, orphaned cell until their panel
re-renders. `resolve()` and its `(value, source)` contract are unchanged for
tier-aware UI display.
