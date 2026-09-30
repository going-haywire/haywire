---
name: unlinking-reveals-the-own-value
description: A port keeps its own value and, while an edge feeds it, the linked value in front of it; removing the last edge shows the own value — one rule for every port, edge kind and propagation mode; supersedes ADR 0014's freeze-on-disconnect
status: accepted
see-also: ADR-0014, ADR-0016, ADR-0019, ADR-0033, ADR-0036, ADR-0039
level: architectural
---

# Unlinking reveals a port's own value

**Context.** An edge wrote its value into the inlet's field, over whatever the user had set. Unlinking left that last delivered value in place (ADR 0014's freeze-on-disconnect), so the user's value was lost, and a linked promoted setting saved the upstream value over the user's. Callbacks needed a rule of their own — an unlinked callback inlet had to go absent to end a subscription — which set them apart from every other port. Blender keeps the user's value and shows it again after unlinking.

**Decision.** One rule for every inlet, edge kind and propagation mode: an inlet shows its **linked value** while an edge feeds it and its **own value** otherwise.

- *Two values in the field.* `DataField` keeps the own value in its subclass storage and the linked value in a second instance of the same class, so both get the field's checks and coercion. A write with a `source_id` (an edge) sets the linked value; any other write sets the own value. Field classes implement `_get_own`/`_set_own`; `PooledField` keeps one value per source and never holds a linked value.
- *Unlinking.* When the last linked edge goes and no displaced edge takes over, the field drops the linked value. The node learns of it through the port's propagation: an immediate inlet fires `on_change` at once, a deferred one is marked dirty. A lazy pull still queued for the removed edge is dropped. A control inlet with several edges keeps its linked value until the last goes; a DATA inlet takes one edge unless pooled.
- *Parked while linked.* While linked, the own value is parked: no UI shows or edits it — a widget on a linked inlet shows the linked value and refuses edits, the view snapping back, and a promoted inlet's settings row is read-only (ADR 0017) — and only saving reads it. A write from code (a mirror sync, a settings reset, undo, a node) is never refused: it lands in the parked value with no `on_change` and no dirty mark, and the field event still fires, carrying the value `get_value()` returns. Refusing those writes would give each writer its own failure case.
- *Saving.* Only the own value is saved; `StoreStrategy.WHEN_LINKED` is gone. `ALWAYS` takes the freed bit as a flag of its own, so `HAS_WIDGET | NODE_SET` stays conditional and a saved `14` still reads as `ALWAYS`.
- *Promoted settings.* A promoted port shares the setting's field (ADR 0014, one cell two views), so the setting reads the linked value while linked and saves, resets and shows its own value. Promotion marks nothing locally set, so an unset mirror keeps tracking its global; demote shows the own value.
- *Callbacks.* A callback's default is an ordinary value (an empty name for `CALLBACK`) that an emitter's pool reads as "no subscription". No callback type needs absence storage, and `@type` rejects a primitive type with no default value.

**Alternatives.** *Freeze-on-disconnect (ADR 0014)* — one value, but user values are lost and callbacks need their own unlink rule. *Snapshot the own value at link time and restore it on unlink* — one stored value, but an own write while linked is overwritten by the next delivery. *Keep the linked value on the port* — promoted settings read the field, so they would need the read-tier bridge ADR 0014 retired. *Widgets write the linked value* — an edit then lasts until the upstream next delivers and is lost on reload. *Refuse every own write while linked* — each writer (mirror sync, reset, undo, node code) then needs its own answer for a dropped write, and the field needs link/unlink signals from the port, since settings write the field directly.

**Consequences.**

- Removing a DATA edge changes the node's input: at its next execution the node sees its own value, not the last delivered one. A DATA reroute that loses its input forwards its type's default.
- Between linking an edge and its first delivery the port has no linked value yet: it shows its own value, and a widget set to `ALWAYS` stays editable until then.
- A graph saved before this ADR stored a linked inlet's delivered value as the port's value; it loads as the own value. No migration.
- A field class written by a library author renames `get_value`/`set_value` to `_get_own`/`_set_own`.
- EdgeKind (edge-kinds step 5) inherits one unlink rule; "the default means no subscription" moves to the callback kind.
