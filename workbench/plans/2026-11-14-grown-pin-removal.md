# Grown pin removal: companion ports and the `on_pin_removed` hook pair

Settled in an inquisition on 2026-11-14 (questions Q1–Q18 below). Design only: nothing is
built yet. Inputs: the feasibility brief from the main checkout and the haybale-protokol
brief (OSC Receive / OSC Send, `ArgPins`).

## Problem

When the user removes a pin a node grew from an `ADD` pin (a **Grown port**, origin
`RESOLVED`), the node is not told, and two things break:

1. **Orphaned pins.** The audio mixer grows `gain_N` and `mute_N` beside each input
   (`barn/haybale-audio/haybale_audio/nodes/audio_mixer.py:105`). Removing `in_N` leaves
   them on the card, and the user cannot remove them: they are `DECLARED`.
2. **A second source of truth falls out of step.** OSC's config text `arg_shape` is the
   single source of truth for its argument pins. A pin-menu removal leaves text and pins
   disagreeing; `ArgPins._pins_mismatch` turns it into a status, and the node writes no
   outlets.

## Decisions

| # | Area | Decision |
|---|---|---|
| 1D | Need | Both: framework-owned **companion ports** for structure (mixer) and a notify-only hook pair for node state (OSC). |
| 2A | Companion direction | One-way: a grown port owns its companions. Removing the owner removes them; a companion cannot be removed on its own. |
| 3B | Companion origin | `RESOLVED` (the user brought it into being). `is_user_removable()` gains one rule: a port with an owner is not removable on its own. |
| 4A | Where the link lives | On the companion: `owner="<owner port id>"`, saved with the port. Older graphs have no `owner` and load unchanged. |
| 5B | Where the cascade lives | In `NodeData._pop()`: a companion never outlives its owner, on every path. A swap in the same `rejig` block (owner dropped and re-added) does not cascade. |
| 6A | Old mixer graphs | The mixer upgrades them itself in `_upgrade_saved_inputs()`: re-add `gain_N`/`mute_N` as `RESOLVED` with `owner=in_N`, inside a `rejig` so their edges stay. No framework migration. |
| 7C | Relation to folds | `owner` is separate from `parent_fold` (lifetime vs layout). Also: a `RESOLVED` fold left with no children dies in the `_pop()` cascade. `DECLARED` folds are untouched. |
| 9B | Undo state | The undo step holds it. `on_pin_removed` returns an opaque memento; `RemovePortAction` stores it next to the spec and passes it to `on_pin_restored`. Redo calls `on_pin_removed` again and replaces the memento. |
| 10A | What fires the hook | One call per user removal, for the grown port only, `RESOLVED` only. No calls for cascaded companions; `PROMOTED` ports don't fire it. |
| 11B | Names | `on_pin_removed` / `on_pin_restored`, beside `release_pins` / `restore_pins`. Parameters stay `port_id`. |
| 12B | Where it fires | In `RemovePortAction`, after `remove_port()` returns, the one place that can keep the memento. `remove_port()` stays a structural primitive with no callback, so a node calling it from its own code (`Annotation.release_pins`) gets no callback to itself. |
| 13A | Mutation contract | The hooks may change node state (store, attributes) and port values, config ports included. They must never add, remove, retype or reorder ports, nor touch edges. Value writes are reversed through the memento. No framework quiet write: suppressing one's own `on_change` is the author's business. |
| 14B | Enforcing the contract | `RemovePortAction` compares the node's `(port_id, type)` set before and after each hook. On a difference it builds a `HaywireException` and `.log()`s it: an `ERROR` Failure in the error ledger with `operation="Remove pin"`, `graph_id`, `node_id`, `registry_key`, and in `details` the hook name and the changed ports. It does not raise. |
| 15B | A raising hook | The action catches it and records it (`report_failure`, `operation="Remove pin"`, hook name in context). The memento becomes `None` and the step completes, so removal and undo stay whole. The same for `on_pin_restored` on undo. This is the common case while a node is being developed. |
| 16A | Running graph | The hooks run on the edit thread in the same window as the removal: workers may still be running, and the reassembly stop follows via `call_soon` (ADR 0064). The docstring says so. No new guarantee. |
| 17A | Tests | See *Tests*. |
| 18A | Docs | See *Docs*. |

## Contract (as authors will read it)

```python
class BaseNode:
    def on_pin_removed(self, port_id: str, spec: dict) -> Any:
        """The user removed *port_id*, a pin this node grew from an ``ADD`` pin.

        Called by the user's removal (pin menu, canvas, settings panel, Farmhand)
        after the port, its companions and their edges are gone; *spec* is the
        removed port's saved spec. Update the node's own state and port values;
        never add, remove, retype or reorder ports, nor touch edges.

        Runs on the edit thread, possibly while the graph's workers are still
        running; the graph stops for reassembly afterwards.

        Returns:
            Whatever ``on_pin_restored`` needs to reverse what this did, held by
            the undo step; keep it to plain values. The default returns ``None``.
        """
        return None

    def on_pin_restored(self, port_id: str, memento: Any) -> None:
        """Undo put *port_id* back, with its companions and edges.

        *memento* is what ``on_pin_removed`` returned for this removal.
        """
```

## Framework changes

1. **`DataPort.owner: str | None`**, saved in `to_dict()` (outside the **Floor**: only when
   set). `add()` does not check that the owner exists, because load adds ports in saved
   order.
2. **`DataPort.is_user_removable()`**: `False` when `owner` is set.
3. **`NodeData._pop()`**: after removing the flagged ports, it also removes every port
   whose `owner` names a port that no longer exists, repeating until nothing changes
   (with their edges detached the same way), and then every `RESOLVED` fold left with
   no children.
4. **`RemovePortAction`**:
   - snapshots the owner and every companion (spec + order);
   - calls `remove_port()`, then `on_pin_removed` under the structure check (14B) and the
     catch (15B), and stores the memento;
   - on undo, re-adds the owner and companions inside one `rejig`, restores each
     member's `order` (`add()` stamps its own counter), then calls `on_pin_restored`
     under the same check and catch;
   - on redo, runs execute again and replaces the memento.
5. `remove_port()` itself is unchanged apart from the cascade it inherits from `_pop()`.

## Library changes

- **haybale-audio mixer**: grow `gain_N`/`mute_N` as `RESOLVED` with `owner=in_N`, and
  upgrade saved inputs in `_upgrade_saved_inputs()` (6A).
- **haybale-protokol** (their last slice, their repo): adopt the pair. Their
  `arg_released` stash becomes the returned memento for this path.

## Tests

- **Companions** (`tests/core/test_node/`): removing an owner removes its companions and an
  emptied `RESOLVED` fold; a companion is not user-removable; the cascade fires on an
  author `rejig` that drops an owner and not on a same-block swap; `owner` round-trips
  save/load; a graph without `owner` loads unchanged.
- **Hooks** (`tests/core/test_undo/`): execute → undo → redo with the memento handed back
  and replaced on redo; group undo restores every member's spec, order and edges; a bare
  `remove_port()` calls no hook; a structure change in a hook logs one ledger Failure; a
  raising hook (on removal and on restore) leaves a whole, undoable step and a ledger
  entry.
- **Testbed**: `AddPortTestNode` grows a companion and overrides both hooks, for a hand
  check in the live studio.
- **Mixer**: removing `in_N` takes `gain_N`/`mute_N`; the saved-input upgrade stamps
  `owner`.

## Docs

- **ADR 0082**: why the hook fires in the action and not in `remove_port()`, why the
  cascade lives in `_pop()`, why the memento travels through the undo step, and why
  contract breaches and raises are recorded rather than refused (decisions 1, 5, 9, 12, 14,
  15 with their rejected alternatives).
- **`docs/components/nodes/node-canon.md`**: §7 "The growing slot" gains companions and the
  hook pair, and documents the existing `release_pins`/`restore_pins` beside them (they are
  undocumented today); the lifecycle hook reference gains both hooks.
- **`docs/guides/ports.md`**: `owner=` next to Folds, with the layout-vs-lifetime
  distinction.
- **Glossary**: **Grown port** and **Companion port** are already added (2026-11-14); drop
  their "not built" mark.

## Out of scope

- `PROMOTED` ports firing the hook (demotion has its own record and restore path).
- A framework quiet write that skips `on_change`.
- Moving `release_pins`/`restore_pins` to mementos.
- The mixer's `hb_buffers` entries for removed inputs (a prune in its own code, separate
  from this design).

## Status

| Slice | State |
|---|---|
| Design | Settled 2026-11-14 |
| Framework + tests | Done 2026-11-14 on `feature/removePort`. Deviations: the undo snapshot covers only the port, ports with an owner and resolved folds, so an unrelated port's bad value cannot break a removal; `AddPortTestNode`'s `Str` side is the testbed (a `Note` companion in a resolved fold). |
| Mixer adoption | Not started |
| Docs + ADR | Not started |
