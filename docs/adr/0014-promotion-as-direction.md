# Promotion is a field + a direction; a setting and a promoted port are one cell, two views

**Status:** Accepted.

> The binding-signal *mechanism* originally recorded here (synthetic `setting__…` port id,
> id-as-binding-key, per-write `_set_keys` marking) was later replaced. The current mechanism
> — a promoted port's id IS the setting's `storage_key`, marked locally-set at promote-time —
> is recorded in the [Amendment](#amendment--a-promoted-ports-id-is-the-settings-storage_key)
> at the end of this ADR. The prose in the Decision section below still describes the
> *original* synthetic-id mechanism; read it for the direction model and one-cell-two-views,
> and the amendment for the id mechanism that shipped. **The amendment itself is now
> superseded by [ADR 0019](0019-settings-owned-promotion.md)** — see its superseded marker:
> promotion state now lives in `Settings._promoted_keys`, and a promoted port is no longer
> serialized in the ports block at all.

Promoting a setting used to mean "create a separate DATA inlet and bridge reads back to it." The inlet owned its own `DataField`; the setting descriptor carried a `_promoted_port_id` back-reference; and `setting.__get__` had a *read-tier branch* that, when the named port was linked, returned `port.get_value()` instead of resolving the setting. That is a **two-value** design — the port has one value, the setting resolves another, and a bridge forwards reads. This ADR records replacing it with **reference-sharing**: a promoted port borrows the setting's [P4 cell](0013-settings-single-cell.md) *by reference* (via a new `DataPort.bind_field`), so a setting and its promoted port are **one cell, two views** — there is no second value, no `_promoted_port_id`, and no read-tier bridge. It is plan **P5**, the final plan of the settings↔DataField unification arc (canonical-key → tier-collapse → JSON → single-cell → **promotion-as-direction**), and it completes the arc.

## Context — a second cell and a read-tier bridge

The Plan-3 (P4-era) promotion design carried the value in two places:

- **A separate inlet with its own field.** `promote_setting` created a DATA inlet with `StoreStrategy.NEVER` + `ShowWidgetStrategy.NEVER`; the port owned its own `_data`, distinct from the setting's cell.
- **The `_promoted_port_id` read-tier branch.** `setting.__get__` (the block P4 kept *verbatim*) read `descriptor._promoted_port_id`; when set and the port was linked, it returned `port.get_value()`, bypassing the setting's own cell. Re-bound on graph load by a loop in `_initialize_from_dict`.
- **Inlet only.** Direction was not a concept — only setting→inlet, and `shadow()`/`watch()` mirror fields were rejected outright.
- **The throwaway-field bridge.** `SettingWidgetModel` still copied values in and out of a throwaway `DataField` (P4 skipped retiring it precisely because an unset mirror field's cell held only the descriptor default, not the resolved global — the display gap this plan closes).

## Decision

**Promotion = field + direction.** A promoted port `bind_field`s the setting's `DataField` cell by reference — the same object-swap `_add_link` already performs when two ports share a cell. The field's `on_changed` event is the single fan-out; whenever the value changes (widget edit, edge drive, or registry sync) every observer reacts.

- **Two directions — inlet / outlet.** `promote_setting(node, accessor, field, direction)` takes a `PortType ∈ {INLET, OUTLET}` (the existing port discriminator — no new enum). The config direction from DECISIONS §B was **dropped**: an unlinked inlet already shows its widget (`ShowWidgetStrategy.NOT_LINKED` is the inlet default), so config's "always-on widget" is just what a promoted inlet does for free, and the existing `as_config` factory is *pinless* (`flow_type=NONE`), the opposite of edge-drivable.
- **Two verbs — `promote(direction)` and `demote`.** No in-place redirect; redirect = demote + re-promote, and the cell survives both (eligibility re-checked at re-promote).
- **Eligibility is two orthogonal flag checks, not a per-kind matrix.** (1) `descriptor._read_only` (a `watch()` field) ⇒ **outlet only** — a read-only field has no write path in. (2) `direction == OUTLET` ⇒ the port is `is_linked_lazy` **and** subscribes `on_changed → propagate`. This holds for *every* promoted outlet — plain, shadow, watch alike — because a promoted outlet is never worker-`out()`-driven.
- **The port carries the whole binding signal.** `promoted: true` + an `id` that equals the setting key (`setting__<accessor>__<field>`). No descriptor flag: the setting stays oblivious to ports, and the port shares the setting's cell so reads agree. An edge-driven write onto a promoted inlet marks the bag's `_set_keys` (in `DataPort.set_value`, O(1) via the id) so the setting read returns the driven value — replacing the retired read-tier branch with no per-read port lookup.
- **The mirror-field cell is authoritative in the setting.** For "one cell, two views" to hold, the shared cell must carry the *resolved* value, not the descriptor default. A **cross-mirror** field (a `shadow`/`watch` of *another* setting, i.e. `_mirror_key != storage_key`) keeps its cell synced to the resolved global: `_cell_for` seeds it, `_on_field_change` writes it, `reset` re-seeds from the global, `__get__` reads it, `cleanup` unsubscribes — all headless (no UI subscriber). A self-namespaced persistent field (which "mirrors itself" for resolution) is *not* a cross-mirror and is unaffected; its value lives in the registry tier.
- **`is_linked_lazy` — the two-part freshness mechanism.** A promoted outlet is written by widget / registry / edge — never by the worker's `out()` — and all those writes fire *outside* the scheduler frame, where an eager propagate is unsafe. So (1) `_refresh_pipes` forces every linked edge to `is_lazy`, deferring each consumer's pull to its next execution; and (2) `bind_field` on an outlet subscribes `field.on_changed → self._pipes.propagate()`, which is what *triggers* that lazy pull. The flag alone is inert — a lazy pipe only pulls once its sink is marked dirty via `propagate()`. Downstream is "fresh as of the consumer's next execution"; idle-liveness (rippling to an *idle* consumer immediately) is out of scope.
- **Value-less serialization; settings-first load.** A promoted port serializes as `promoted:true` + `id` + `port_type` + display kwargs — **no `recipe`**, **no `field_data`**; the value round-trips through the settings block only. `from_spec` gains a promoted branch that derives the type from the setting at `id` and `bind_field`s the cell instead of creating a fresh field. `_initialize_from_dict` restores **settings bags first, then ports**, so a promoted outlet binds a cell already at its loaded value — no propagation mid-load.
- **The throwaway-field bridge retires.** `SettingWidgetModel` binds the bag's shared cell for **display** (registry/edge changes show live via `on_changed`) and **writes through the descriptor `__set__`** via the panel setter — never raw to the cell, so `_set_keys` bookkeeping stays correct (a raw write would flip the value while leaving the field "unset," and the next registry sync would clobber the edit).

## Design-doc deviations recorded

Two refinements from a code-grounded pass **supersede** DECISIONS §B and §C4:

- **Config direction dropped, then reintroduced (2026-07-08).** Original reasoning: an unlinked inlet already shows its widget (`enums.py`), and `as_config` is pinless (`interface.py`), so §B's three-direction matrix looked internally contradictory against the code it named. That held only while `Promotable`/`eligible_promotion_directions`/the Setting-row menu didn't yet exist. The concrete gap that reopened this: a `CHOICES` setting with a dynamic-options callable (`widget_config={"options": self.method}`) cannot safely use `as_config()` directly — `DataPort.__post_init__` raises `TypeError` for a callable in a **plain** (non-promoted) port's `widget_config` (ADR 0018/0019's serialization guard), but a **promoted** port is exempt (never serialized). Promoting a setting to `PortType.CONFIG` is therefore the only safe path to a callable-driven config port. `Promotable` gains a `CONFIG` member and a composite `INPUT = INLET | CONFIG` (a promoted CONFIG field is treated as an input — marked locally-set at promote time, same as INLET, since its widget is its only write path); `ALL` becomes `INLET | OUTLET | CONFIG`. A promoted CONFIG field's Properties-panel row renders exactly like a promoted INLET (static read-only "promoted" label, hint "promoted to config") — the interactive, callable-driven widget instead renders wherever a `PortType.CONFIG` port's live widget already renders (Ports Panel / node card), unchanged by this addition. `watch()` fields remain `Promotable.OUTLET`-only and are never CONFIG-eligible (a mirrored field promoted to CONFIG would freeze against its global at promote-time before any real edit, same objection as promoting a `watch()` field to INLET). See `haywire.core.node.promotion.promote_setting`'s `PortType.CONFIG` branch and `Settings.promote()`/`demote()` for the resulting bag-level API.
- **`is_linked_lazy` generalized from watch-only to all outlets** (supersedes §C4/Q8's "mirror ⇒ lazy"). The real discriminator is "setting-driven ⇒ written outside the scheduler frame," true of *all* promoted outlets. And the flag needs a trigger: the outlet's `on_changed → propagate` subscription is required, not optional (verified against `pipe.py`/`port.py`).

## Supersedes

The Plan-3 two-cell + `_promoted_port_id` read-tier-bridge design (DECISIONS §E, "ADR-C"). **Trade-off:** a single shared cell with **freeze-on-disconnect** (demote keeps the cell's current value; recovery is an explicit `reset`) versus the two-cell model's "preserve the typed-earlier value" safety. Freeze-on-disconnect was chosen because it follows directly from the cell-mutation spine (§C3): no *structural* action — promote, demote, link, unlink, redirect — ever resets the value; only edit / edge-drive / explicit reset change it.

## Consequences

- **One value model, end to end.** A setting's value and its promoted port's value are the same `DataField` cell; there is no bridge and no second cell.
- **Retirements.** `SettingDescriptor._promoted_port_id`, the `setting.__get__` read-tier branch, the load-time re-bind loop, `StoreStrategy.NEVER`-as-a-bolt-on (nothing to store), and the `SettingWidgetModel` throwaway-field adapter all go away.
- **`shadow`/`watch` are now promotable** (to an outlet; `shadow` to an inlet too), which the Plan-3 design rejected outright.
- **Behavior-preserving for the inlet path.** A characterization suite (`tests/core/node/test_promotion_single_cell.py`) pinned the inlet path before the rework; the whole suite stayed green through the arc.
- **The arc is complete.** P1–P5 have landed; `architecture/settings/settings-arch.md` §6.4's "Deferred to P5" forward-ref now points here.

---

## Amendment — a promoted port's id is the setting's storage_key

*(Originally ADR 0015. Supersedes-in-part the Decision section above: the direction model and one-cell-two-views stand; only the id-encoding + set-tracking mechanism is replaced.)*

> **⚠️ Superseded by [ADR 0019](0019-settings-owned-promotion.md) (2026-07-06).** The amendment's core principle — "the port IS the promotion signal (serialized in the ports block); settings stay oblivious" — no longer describes the code. Promotion state now lives in `Settings._promoted_keys`; promoted ports are regenerated from settings on load and are **not serialized** in the ports block. `demote_setting` now clears the settings-side record (the amendment's "no settings-side record to clean up" property was deliberately given up). The direction model and one-cell-two-views (in the Decision section above) still stand. This amendment's prose is retained as the historical record of the intermediate design.

**Context.** The Decision above gave a promoted port a synthetic id `setting__<accessor>__<field>` and made "port id + `DataPort.promoted`" the binding signal, requiring a parallel encode/decode scheme, id-decode helpers on `DataPort`, a `from_spec` branch that reached into settings for the port's type, a per-write `_mark_promoted_setting_set` on edge-drive, and an `object.__setattr__` `_node` monkeypatch on each settings bag.

**Decision.** Keep the port as the promotion signal (still serialized in the ports block), but make its id the setting's own `descriptor.storage_key` (globally unique per node, dot-safe), deleting the encode/decode scheme. The port carries only `promoted: bool`. Promoted ports now serialize with a `recipe` (type) but no `field_data`, so `from_spec` is fully generic; the one port→settings crossing — binding the shared cell — moves to a node method `_bind_promoted_ports()` run after ports deserialize, resolving (bag, desc) via `_resolve_promoted` (match on storage_key). `promote_setting` marks the field locally-set at promote-time, so edge-drive needs no per-write hook. The `_node` back-reference becomes a constructor parameter.

**Consequences.** Deleted: the id encode/decode module, the `DataPort` id-decode helpers, `from_spec`'s promoted branch, `_mark_promoted_setting_set` and its edge-drive call site, and the `_node` monkeypatch. **Demote stays trivial** (remove port + unbind) — the port being the signal means no settings-side record to clean up. **Behavioral change:** a promoted field is locally-set for the port's lifetime, so a promoted *shadow* inlet stops tracking its global until demote + explicit `reset` (deliberate deviation from "unset tracks", DECISIONS.md §A). **Hard cutover, no migration** (matches [ADR 0011](0011-collapse-settings-tiers.md)/[ADR 0012](0012-settings-json-persistence.md)): port ids change, so an old graph's edge into a promoted port goes dangling on load.
