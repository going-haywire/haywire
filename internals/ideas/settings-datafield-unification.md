# Unify settings and ports on a single-cell `DataField`

> Greenfield idea. No backward-compat constraint.

## The agreement

A setting's value should live in a `DataField` exactly like a port's does — **one value
cell**, same semantics. A **setting** and a **data port** are two *views onto the same
field*: the panel edits it, an edge can drive it. There is no durable/transient split; there
is one cell with one meaning.

This makes "port vs setting" a surface/role distinction, not a storage one. Today a port
stores its value in a `DataField` and a setting stores a raw value in a dict; unifying on the
`DataField` removes that divergence and the machinery bridging it.

## Ownership and lifecycle of the cell

- **Wiring = ownership.** When an edge is linked to the field, the edge drives the cell. The
  graph owns the value for as long as the link exists. (The inline widget is hidden while
  linked — there is nothing to edit, the graph is the source.)
- **On disconnect: freeze.** When the edge is removed, the cell keeps the last driven value.
  It is not re-resolved and the previously hand-set value does not re-emerge.
- **The frozen value persists.** Serialization writes whatever is in the cell, including a
  value that originated from an edge that no longer exists. One cell, one meaning — including
  on save/reload.

The rationale: promoting a setting to an inlet, or wiring an inlet at all, *is* the user
consenting to the graph owning that value — during the connection and after it. There is no
hidden "the value I typed earlier" the system must protect, so a single shared cell is safe
and correct.

## Recovery: reset-to-default

Because a wired-then-unwired field keeps the driven value, the only way back to the
developer-recommended value is an explicit **reset-to-default** action (as mirror fields have
today). This is universal: any field with a declared default — plain inlet widget, setting,
or promoted setting — can be reset to that default by the user. Reset is the deliberate
counterpart to "wiring owns the cell"; nothing reverts automatically.

## What this retires in the current promotion code

With a setting and a port being one cell viewed two ways, the promotion bolt-ons fall away:

- `store_strategy=NEVER` on the promoted port — there is no separate transient value to keep
  out of serialization; the one cell persists like any other.
- the `_promoted_port_id` flag on the class-shared descriptor — promotion binding lives on
  the field/instance, not on shared declaration metadata.
- the bespoke read-tier branch in the descriptor's `__get__` — there is nothing to reconcile;
  reading the field is reading the field, whether the view is a setting or a port.
- the `SettingWidgetModel.create_field` adapter — the setting already *has* a `DataField`, so
  the widget binds to it directly.

## Persistence: settings tiers move from TOML to JSON

Allowing complex ITypes as setting values breaks the current TOML persistence of the
registry tiers: a complex type's `to_dict` can produce nested/heterogeneous structures TOML
can't cleanly represent. The fix is to persist the settings tiers as **JSON** instead of
TOML. JSON handles arbitrary nested structures, and (per VS Code's settings) JSON config
stays perfectly hand-editable — the property TOML was originally chosen for is not lost.

- **Both tiers go JSON.** Global (`~/.haywire/settings.json`) and workspace
  (`<ws>/.haywire/settings.json`) both switch, so persistence is one format, not a per-tier
  fork. (Today: `registry.py` is the only code touching settings TOML — ~6 read/write sites.)
- **Hard cutover, no migration.** Existing `.toml` files are not read or converted; users
  re-set their global/workspace settings once. This drops settings currently on disk — a
  deliberate greenfield trade-off that **must be surfaced at ship time** (changelog / first-run
  notice), not allowed to happen silently.
- **One serialization contract, everywhere.** Any value whose field's `to_dict`/`from_dict`
  round-trips persists in any tier — the *same* contract a field already meets to land in the
  graph JSON for a node. There is no settings-specific representability restriction: if it
  serializes for a node, it serializes for a setting. The IType author's `to_dict`/`from_dict`
  is the single thing that must be correct.

> This is a format migration of a deliberately-chosen prior decision (TOML for hand-editable
> config) — it warrants an ADR when built.

## Relationship to current `DataPort` behavior

Today a `DataPort` inlet already stores the widget value and the edge value in the same
`_data` cell, and on disconnect keeps the last edge value. Under this model that is **the
intended behavior, not a defect** — it is exactly "wiring owns the cell, freeze on
disconnect." The work is to bring *settings* onto the same single-cell `DataField` so they
behave identically, not to change how ports behave.

---

## Appendix: related settings-code cleanups

Independent critiques of the *current* settings code, found while exploring the above. Each
is tagged **[subsumed]** (the single-cell field dissolves or answers it) or **[orthogonal]**
(true regardless of the unification — ship anytime). Evidence is the current-code smell.

1. **[subsumed] Dual-mode split (simple vs extended).** `__get__`/`to_dict`/`reset`/`_resolve`
   all branch on `self._registry is None` — two value systems welded into one class (local
   dict vs 6-tier registry chain). The single-cell field collapses this to one resolution
   model; "simple mode" becomes "no registry tiers feeding the cell."

2. **[subsumed] Dual keying — `_setting_key if _setting_key else name`.** A field is addressed
   by `_attr_name` sometimes and `_setting_key` other times (~5 sites); this conditional is a
   bug surface (the promotion codec had to dodge `__` in names). Assign **one canonical key
   always** at `__set_name__`/`@node` (`f"{owner}.{name}"`), used by store, registry,
   serialization, and promotion alike. Worth doing on its own, ahead of the field work.

3. **[subsumed] Recompute-on-read.** `__get__` runs `_resolve` (registry call + tier walk)
   every read; settings are read in worker hot paths. A field that *holds* its value (cache
   invalidated via the existing `_on_field_change` signal) removes per-read resolution.

4. **[subsumed] Instance state on a class-shared descriptor.** `_promoted_port_id` (also
   `_mirror_descriptor`/`_mirror_key`) lives on the class-shared descriptor yet means
   something per instance. Move per-instance binding onto the field/instance; the descriptor
   keeps only immutable declaration metadata. Kills the cross-instance bleed by construction.

5. **[orthogonal] Stringly-typed widget desugaring.** `_widget == "label"/"color"`, `choices`
   → SelectWidget, `min`/`max` → bounds in `resolved_widget_key`/`resolved_widget_config` —
   the setting re-derives widgets the IType already declares. Defer to the IType's
   `widget_key`/`widget_config`, with `widget=` as the single explicit override.

6. **[orthogonal] `_type: type = object` but semantically an IType.** The cutover enforces
   IType at runtime while the annotation says plain `type` with an `object` sentinel. Make it
   `_type: type[IType]`, resolve eagerly or fail loudly — put the trust in the type system.

7. **[not pursued] Split `Settings` responsibilities** (value store / reactivity /
   persistence / DI). Flagged and *declined*: the coupling is genuine and splitting risks the
   over-abstraction CLAUDE.md warns against. Recorded so it isn't rediscovered as a fresh idea.
