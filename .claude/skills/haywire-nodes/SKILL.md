---
name: haywire-nodes
description: Load Haywire node development docs into context. Use when the user wants to create or modify node classes, define ports, configure dynamic port behavior, or work with node workers.
---

# Load Haywire Node Development Docs

Read the following documentation files in order and use them as the authoritative reference for any node development task. After reading, output a brief recap of key patterns before proceeding.

## Files to read

1. `docs/documentation/Creating_Nodes.md` — full guide to writing `@node` decorated classes: `init()`, `worker()`, node types, menu paths, lifecycle callbacks
2. `docs/documentation/Defining_DataPorts_inside_Nodes.md` — `self.add()` calls, port directions (inlet/outlet/config), `FlowType`, `allow_multiple`, `on_change`, `on_connect`, `on_disconnect`
3. `docs/documentation/Defining_DataTypes.md` — `PrimitiveType`, `BaseType`, `CompoundType`, child→parent passthrough, adapter chains, `PooledType`

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
