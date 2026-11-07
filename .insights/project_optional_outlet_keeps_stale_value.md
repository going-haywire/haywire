---
name: optional-outlet-keeps-stale-value
description: Writing None to an OPTIONAL[T] outlet does not reach a plain T inlet, which keeps its last value
type: project
---

An `OPTIONAL[T]` outlet connects to a plain `T` inlet with no adapter. Writing `None` to it updates the outlet and nothing else: measured writing 5, `None`, 6, `None`, the inlet read 5, 5, 6, 6, while the outlet held `None`. A per-frame consumer silently keeps last frame's value.

A plain `INT` or `FLOAT` outlet raises `TypeError` on `out(name, None)`, because the field coerces; `STRING` and `IMAGE` accept it, and the inlet's reading is unchanged the same way.

So a node that must clear a downstream reading has to write a value. The Metadata node writes the pin type's default (`port.stored_type.create_field().get_value()`) for an absent field; see ADR 0075.
