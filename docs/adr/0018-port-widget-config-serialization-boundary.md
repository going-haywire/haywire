---
status: superseded-in-part by ADR-0019
see-also: ADR-0014, ADR-0017, ADR-0019
---

# `widget_config` callables are safe on a `setting()`, unsafe on a plain port

> **⚠️ Promoted-port half superseded by [ADR 0019](0019-settings-owned-promotion.md) (2026-07-06).** This ADR's promoted-port mechanism — exclude `widget_config` from `DataPort.to_dict()`, re-apply it from the descriptor in `_bind_port` — was **never implemented as described**: ADR 0019 supersedes it with "promoted ports are not serialized at all" (regenerated from `Settings._promoted_keys` on load), which makes the exclusion moot. **The plain-port half of this ADR — the construction-time `is_cattrs_serializable` raise in `DataPort.__post_init__` — is RETAINED and is what shipped.** Read the plain-port Decision bullet and the demote-gap note as current; read the promoted-port Decision bullet as superseded history.

**Context.** `SelectWidget` (and any widget honoring the same convention)
resolves a callable placed at `widget_config["properties"]["options"]` at
render time (`if callable(options): options = options()`) — an intentional,
documented mechanism for dropdowns whose choices must be queried live (e.g.
enumerate connected hardware). `DataPort.to_dict()` serializes `widget_config`
as an ordinary `kwargs` entry, with no exclusion and no callable-detection.
`OakDCameraNode`'s `mxid` port used exactly this pattern
(`widget_config={"options": self.hb_list_available_mxids}`, a bound method)
and crashed `json.dumps` on graph save — nine stack frames deep, far from the
actual mistake.

Two materially different cases share this one symptom:

1. **A promoted port** (a `setting()` field exposed as a port, ADR 0014) gets
   its `widget_config` baked onto the `DataPort` instance once, at promotion
   time, by copying the descriptor's stamped `widget_config`
   (`_metadata_to_port_kwargs`). The descriptor itself is re-derived fresh
   from the class body on every load (`_stamp_widget()` runs at
   `__set_name__`/`__init__`, never from persisted state) — so the live
   callable is *never actually needed* in the serialized port at all; it's
   always available again, correctly, from the descriptor. `Settings.to_dict()`
   independently confirms this: it never serializes `widget_config` for a
   setting field either.
2. **A plain, non-promoted port** (declared directly via `as_inlet`/`as_outlet`/
   `as_config` in a node's `init()`, like `mxid`) has no descriptor to fall
   back to. The port instance IS the only place the callable lives. There is
   no rescue mechanism available for this case.

Two other options were considered and rejected for the plain-port case:

- **Serialize a resolved snapshot** (call the callable once, persist its
  result). Rejected: `_deserialize_ports` reconstructs ports purely from the
  saved spec — there is no post-load `init()` re-run for a loaded node
  (`_initialize` calls either `init()` **or** `_initialize_from_dict()`,
  never both). A snapshot would permanently freeze the dropdown's options as
  of the save moment, defeating the entire purpose of a *dynamic* callable
  and silently degrading the feature on every save/load cycle.
- **Silently drop the callable key during serialization.** Rejected: this
  hides a real authoring mistake (or, at best, a design choice with no
  working replacement) behind data loss a node author would only discover by
  noticing a dropdown mysteriously empty after a reload — much later and
  much less actionable than a construction-time error naming the exact port
  and key.

**Decision.**

- **Promoted ports:** `DataPort.to_dict()` excludes `widget_config` whenever
  `self.promoted` is `True` — mirroring the existing `field_data` exclusion
  (`if include_data and self._data and not self.promoted`) exactly, since
  the reasoning is identical: a promoted port's value/config both round-trip
  through the shared setting, never through the port's own serialized state.
  `_bind_port` (the one function establishing every promoted-port invariant:
  cell binding, locally-set marking) gains a third invariant — it sets
  `port.widget_config = desc.widget_config` unconditionally on every bind,
  wholesale-replacing rather than merging (the descriptor is the sole source
  of truth; a promoted port has no independent widget-config identity to
  preserve alongside it). This runs identically from `promote_setting`
  (interactive) and `bind_promoted_ports` (load-time repair after
  `_deserialize_ports` produced an empty `widget_config`), so copy/paste
  (which reconstructs nodes through the same `_initialize_from_dict` →
  `_bind_promoted_ports` path) is covered for free, with no separate branch.
- **Plain ports:** `DataPort.__post_init__` validates `widget_config` via the
  existing `is_cattrs_serializable()` utility (already used by
  `normalize_and_validate_default` for the identical class of problem on
  `default=`), raising `TypeError` at construction time — the moment
  `node.add(...)` runs during `init()` — when `self.promoted` is `False` and
  the check fails. The check is skipped entirely when `self.promoted` is
  `True`: a promoted port's `widget_config` is provably always safe (per the
  point above), so validating it would be a pointless false-positive trap
  against the documented, working "promote a CHOICES setting with a
  `lambda:`-options field" pattern.
- **Demotion is an accepted, narrow gap.** `demote_setting` does not
  reconstruct the `DataPort` (`__post_init__` never re-runs), so a
  freshly-demoted port in the same live session keeps whatever
  `widget_config` it had while promoted — including a callable, now
  un-rescued. No current node promotes a callable-bearing field and then
  demotes it pre-save, so this is documented as a known limitation rather
  than built against.
- **`OakDCameraNode.mxid` is left broken by this change, deliberately.** Once
  this lands, that node's `init()` raises. The fix (likely: move `mxid` into
  a `NodeSettings` bag so its callable becomes safe, or replace the live
  callable with a different refresh mechanism) is a node-authoring design
  decision for a different repository (`haybale-visiongraph`), scoped and
  reviewed on its own rather than bundled into this framework change.

**Consequences.**

- A promoted port's `widget_config` is never independently inspectable from
  its own serialized `to_dict()` output — tests asserting on a promoted
  port's widget contract must read it off the live `DataPort` instance
  in-memory (as `test_promoted_port_carries_the_settings_widget_config`
  already does), not from a round-tripped save file.
- Any future node author who reaches for the same "live callable in
  `widget_config`" pattern on a plain port gets a `TypeError` at the exact
  `node.add(...)` call site, in development, instead of a cryptic
  `json.dumps` failure discovered later by whoever next tries to save that
  graph.
- This is a deliberate, hard, undocumented-migration breaking change for any
  existing node using this pattern on a non-promoted port (`OakDCameraNode`
  is the one known instance) — matches this codebase's established
  "hard cutover, no migration" convention for framework corrections (ADR
  0011/0012/0014).
