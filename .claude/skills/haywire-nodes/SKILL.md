---
name: haywire-nodes
description: Load Haywire node development docs into context. Use when the user wants to create or modify node classes, define ports, configure dynamic port behavior, or work with node workers.
---

# Load Haywire Node Development Docs

Read the following documentation files in order and use them as the authoritative reference for any node development task. After reading, output a brief recap of key patterns before proceeding.

## Files to read

1. `docs/components/nodes/node-canon.md` — `@node` decorated classes, lifecycle hooks (`init`, `post_init`, `on_startup`, `on_validate`, `worker`, `on_frame_start`/`end`, `on_shutdown`, `on_saved`, `on_teardown`), worker contract (parameter-name = inlet ID), return values, `rejig()` for dynamic ports, groups & sections, `hb_*` prefix convention
2. `docs/components/ports/port-canon.md` — `as_inlet` / `as_outlet` / `as_config`, port flags, primitive vs `ArrayType[T]` vs `PooledType[T]`, worker access patterns (`self.value(id)`, `self.out(id, v)`, `self.ports[id].is_linked()`), connection-state checks, common pitfalls
3. `docs/components/datatypes/datatype-canon.md` — `@type` decorator, `PrimitiveType[T]`, `BaseType` (`@dataclass`), `CompoundType[T]` (`ArrayType`, `PooledType`), child→parent passthrough, `default` dict format, custom `field_class` for type coercion, derived primitives

Optional context (load if the task touches them):

- `docs/components/adapters/adapter-canon.md` — type-pair adapters with `@adapter`, `BaseAdapter.convert()`, chain resolution
- `docs/components/widgets/widget-canon.md` — UI widgets bound to types via `compatible_types`

## After reading

Summarise in 6–10 bullet points:
- The `@node` decorator fields (id, label, menu, description, node_type)
- The `init()` / `worker()` contract — especially that worker parameter names must exactly match inlet port IDs
- Port directions and `FlowType` (CONTROL, DATA, NONE for config)
- `allow_multiple` rules (hardcoded for DATA and EXEC — do not set manually)
- `rejig()` context manager for dynamic port reconfiguration, and which prefix is safe for method names (`hb_`, `my_`, `custom_`, `ext_`)
- Pooled inlets and what the worker receives (`dict` keyed by upstream node ID)
- Type hierarchy: child → parent is a passthrough; parent → child needs an adapter
- Any gotchas called out in the docs

Then proceed with the user's task using these patterns as the guide.
