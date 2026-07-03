---
status: accepted
supersedes-in-part: ADR-0014
---

# A promoted port's id is the setting's storage_key; the port stays the signal

**Context.** ADR 0014 gave a promoted port a synthetic id `setting__<accessor>__<field>`
and made "port id + `DataPort.promoted`" the binding signal, requiring a parallel
encode/decode scheme, id-decode helpers on `DataPort`, a `from_spec` branch that reached
into settings for the port's type, a per-write `_mark_promoted_setting_set` on edge-drive,
and an `object.__setattr__` `_node` monkeypatch on each settings bag.

**Decision.** Keep the port as the promotion signal (still serialized in the ports block),
but make its id the setting's own `descriptor.storage_key` (globally unique per node,
dot-safe), deleting the encode/decode scheme. The port carries only `promoted: bool`.
Promoted ports now serialize with a `recipe` (type) but no `field_data`, so `from_spec`
is fully generic; the one port→settings crossing — binding the shared cell — moves to a
node method `_bind_promoted_ports()` run after ports deserialize, resolving (bag, desc) via
`_resolve_promoted` (match on storage_key). `promote_setting` marks the field locally-set
at promote-time, so edge-drive needs no per-write hook. The `_node` back-reference becomes
a constructor parameter.

**Consequences.** Deleted: the id encode/decode module, the `DataPort` id-decode helpers,
`from_spec`'s promoted branch, `_mark_promoted_setting_set` and its edge-drive call site,
and the `_node` monkeypatch. **Demote stays trivial** (remove port + unbind) — the port
being the signal means no settings-side record to clean up. **Behavioral change:** a
promoted field is locally-set for the port's lifetime, so a promoted *shadow* inlet stops
tracking its global until demote + explicit `reset` (deliberate deviation from "unset
tracks", DECISIONS.md §A). **Hard cutover, no migration** (matches ADR 0011/0012): port ids
change, so an old graph's edge into a promoted port goes dangling on load. Promotion-as-
direction and one-cell-two-views (ADR 0014) stand; only the id-encoding + set-tracking
mechanism is replaced.
