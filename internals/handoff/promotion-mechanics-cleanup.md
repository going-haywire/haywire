# Handoff: Promotion Mechanics Cleanup

**Date:** 2026-07-01
**Branch:** `review/type-floor-hoist-squashed`
**Status:** Refactor complete, deferred design decision documented below.

---

## What was done this session

A series of simplifications to `packages/haywire-core/src/haywire/core/node/promotion.py` and the graph-editor UI layer:

### 1. Stripped the freeze block from `demote_setting`

The original `demote_setting` had a "§C3 freeze-on-disconnect" block that checked whether the cell value diverged from the unoverridden default and, if so, added `storage_key` to `_set_keys`. This was dead code: `_mark_promoted_setting_set` (called on every edge-driven write in `port.py:323`) already flips `_set_keys` at drive time, so by demote time the field is always already locally-set if it was ever driven.

`_resolved_without_override` helper was also removed (only existed to serve the freeze block).

Test coverage: `tests/core/node/test_promotion_e2e.py::test_full_promote_drive_demote_cycle` asserts the value survives demote — it passes without the freeze block, confirming it was redundant.

### 2. `demote_setting` signature: `(node, accessor, field)` → `(node, port_id)`

The old signature encoded accessor+field into a pid internally. Since the caller always has the pid, the encode/decode round-trip was eliminated. All callers updated (tests + handler).

### 3. UI layer: decode moved to handler, panel simplified

- `PortContextActions.demote_setting(accessor, field)` → `demote_setting(port_id)`
- `context_menu.py` handler now decodes `port_id` → `(accessor, field)` before calling the core function (decode still needed there because `demote_setting` now takes a port_id directly)
- `panels/graph/menu/port/port.py` no longer imports or calls `decode_promoted_port_id` — passes `port.id` straight to the action
- `poll()` in `DetachSettingMenuPanel` already used `port.promoted` (confirmed correct before session)

### 4. `decode_promoted_port_id` is still present

It's still used in `port.py` (lines 770, 778) for `_promoted_accessor` and `_promoted_descriptor_for`. Do not remove it.

---

## Deferred design decision: `_node` back-reference on settings bags

### The situation

`data.py:77` sets `_node` on every settings bag at node construction:
```python
object.__setattr__(_bag_instance, "_node", self)
```

This back-reference exists **solely** to support `is_field_promoted(bag, field)` in `promotion.py:48`, which walks `bag._node.ports` to check if the encoded port id exists.

`is_field_promoted` is called from:
- `packages/haywire-core/src/haywire/ui/panel/render_utils.py:265` — marks promoted fields as non-editable in the properties panel

### The smell

The pattern is: bag → node → port dict → check port id. This is a lookup chain through a back-reference set via `object.__setattr__` (bypassing the descriptor protocol). It works but feels like a patch.

### Alternative considered: `_promoted_fields: set[str]` on the bag

`Settings.__init__` gets `_promoted_fields: set[str] = set()`. `promote_setting` adds the field name, `demote_setting` removes it, `from_spec`'s promoted branch also adds it (to handle deserialization). `is_field_promoted` becomes `field in bag._promoted_fields`. `_node` back-ref removed.

### Why it was deferred

`demote_setting(node, port_id)` has no bag reference. To remove from `_promoted_fields` it would need to decode `port_id` back to `(accessor, field)`, then `getattr(node, accessor)` to reach the bag. So `decode_promoted_port_id` would re-enter `demote_setting` — roughly the same complexity, just shuffled. Net gain unclear.

A third alternative (holding a `_promoted_port` reference on the bag) was also considered but rejected: the setting staying oblivious to port objects is an explicit ADR 0014 invariant.

### Decision deferred

Leave `_node` back-ref as-is for now. Revisit if `is_field_promoted` grows more callers or if the bag needs additional node-side lookups that would justify a cleaner interface.

---

## Suggested skills

- `/haywire-nodes` — if the deferred decision is revisited and touches port or bag internals
- `/code-review` — before merging this branch; the promotion.py changes are clean but worth a pass
- `/verification-before-completion` — run full test suite before closing the branch

---

## Files changed this session

| File | Change |
|---|---|
| `packages/haywire-core/src/haywire/core/node/promotion.py` | Removed freeze block + `_resolved_without_override`; `demote_setting` signature → `(node, port_id)` |
| `barn/haybale-graph-editor/.../handlers/context_menu_actions.py` | Protocol: `demote_setting(port_id)` |
| `barn/haybale-graph-editor/.../handlers/context_menu.py` | Handler: decodes port_id, calls updated core |
| `barn/haybale-graph-editor/.../panels/graph/menu/port/port.py` | Removed decode call + promotion imports; passes `port.id` directly |
| `tests/core/node/test_promote_demote.py` | Updated demote call |
| `tests/core/node/test_promotion_e2e.py` | Updated demote calls (×2) |
| `tests/core/node/test_promotion_single_cell.py` | Updated demote calls (×3) |
| `tests/core/node/test_promotion_serialization.py` | Updated demote call |
| `tests/ui/graph_canvas/test_context_menu_actions.py` | Updated protocol stub |

All 31 promotion-related tests pass.
