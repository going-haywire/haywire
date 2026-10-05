---
name: callback-absence-and-immediate-guards
description: A wire type may hold absence (callback ports are None when unsubscribed, saved as null, dropped by pools); an immediate inlet fires only on change and drops a write that closes a loop
status: accepted
see-also: ADR-0033, ADR-0039, ADR-0040, ADR-0041, ADR-0042
level: architectural
---

# Callback absence and the immediate guards

**Context.** A callback port with no subscription held its type's default: an empty name for `CALLBACK`, a default dataclass instance for a dataclass callback type. An emitter's pool dropped any value equal to its element's default. That value was an in-band sentinel: a real subscription whose fields matched the default vanished, and every callback type had to keep its default unusable. Field serialization could not express absence either; `PrimitiveType` cannot be built from `None`, and the `DataField` base stubbed `to_dict` to the type's declared default, so array and map port values were never saved.

The immediate path had no equality check and no loop protection. An edge's write into an immediate inlet always fired `on_change`, so an emitter heard the same subscription twice, and two callback reroutes wired into each other recursed until `RecursionError`. Linking the closing edge was enough; no link-time check caught it, and the assembly cycle check never sees immediate edges.

**Decision.**

- A wire type declares `holds_absence`. `CallbackWire` is the only builtin one. `IType.create_field` gives a type that itself declares such a wire a field that can hold `None` (`_field_holding_absence`): `PrimitiveField` storage stores `None` past its coercion, and `BaseField` storage does too and starts and resets absent when its default kwargs are empty. A container or wrapper of such a type keeps its own field. `@type(default=None)` on such a wire stores an empty default, so the type's fields start absent.
- Callback types declare `default=None`. A pool of a callback element drops an absent entry; every present value, an empty name included, is a subscription.
- `DataField.to_dict` and `from_dict` are template methods. A field that `accepts_absence()` and holds no own value saves JSON `null`, and `from_dict(None)` restores absence; a present value goes through `_own_to_dict` / `_own_from_dict`. `from_dict(None)` on a field that cannot hold absence raises. Array and map fields save each item as a field of the element type does.
- `DataPort._fire_immediate` guards every edge's write into an immediate inlet, and the reveal on unlink. **Echo guard:** the write is stored, and `on_change` fires only when `get_value()` differs before and after. **Re-entrancy guard:** a thread-local set holds the inlets whose `on_change` is running; a write that reaches one of them is dropped, not stored, and logged as a warning.

**Alternatives.** *Keep the sentinel and make it configurable per type* — still in-band, and every pool must know it. *`OPTIONAL[CALLBACK]` on every callback port* — an `OPTIONAL` outlet reports its element as stored type, so absence would be skipped at a plain callback inlet and a subscription would go stale; every declaration would change. *Wrap the field class in `@type`* — assigning `field_class` after decoration is an established pattern, and a wrap at decoration time would be silently lost. *Detect loops at link time* — the cycle can pass through Subgraph boundaries and nodes that only relay on write; cutting at run time covers every shape, including the two-edge pair a future bidirectional port needs. *Store the dropped value* — the echo guard would then suppress a later write of that value, and the node would never hear of a value its inlet holds.

**Consequences.**

- An unlinked callback port reads `None`. Tests and code reading `""` there change.
- `OPTIONAL` saves absence as `null` where it saved `{"value": null}`; the old form still loads.
- A relay saved before this change holding `""` and with nothing upstream loads holding `""`, now a real name; relinking or deleting it fixes it. A relay with something upstream takes its value from upstream on load.
- In a loop of immediate edges, the dropped inlet and its upstream outlet disagree until the next write. A loop that relays the value unchanged ends at the echo guard, with no warning.
- `ControlWire` holds no absence, so a pool of `EXEC` stays refused: an unfired control source still contributes its empty payload.
- This lifts ADR 0033's primitive-only restriction for types on a `holds_absence` wire.
