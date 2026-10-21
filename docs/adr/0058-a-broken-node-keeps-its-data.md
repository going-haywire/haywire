---
name: a-broken-node-keeps-its-data
description: A node whose class is missing or fails to construct is held by an ErrorNode stand-in that keeps the graph editable and saves the node's original data back, so the real node returns with its values once its class works
status: accepted
see-also: ADR-0053
level: framework
---

# A broken node keeps its data

**Context.**

- A node cannot be built for two reasons: its class is unknown (its library is missing, or the key failed to import), or its class's constructor raises (a broken settings declaration or `__init__`, often after a hot reload).
- For an unknown class, `NodeFactory.get_node` already returned the registered error node. The wrapper built an `ErrorNode` from the file's data, but a save wrote the `ErrorNode`'s own `identity` and `library` and dropped every settings bag except `props`.
- For a constructor that raised, the wrapper kept no instance. `NodeWrapper.node` raised, so every add, move and remove in the graph failed in `BaseGraph._check_canvas_size`, the selection toolbar failed for the node, its card stayed stale with no error, and a save wrote no `node_data` at all.

**Decision.**

- **A wrapper always holds a node.** When the class constructor raises, the wrapper constructs the registry's error node instead (`NodeFactory.get_error_node`), as the factory does for an unknown key. `state.error_instantiate` still records the failure.
- **The error node is a stand-in** (`NodeWrapper.is_stand_in`) while the wrapper's `registry_key` is not the error node's own. A stand-in keeps the node's original `node_data`: the file's, or the old instance's, captured before a failed rebuild cleaned it up.
- **A stand-in saves the node it replaces.** `serialize()` writes the kept data, with only `props` (position, label, colour, stage fields) taken from the live stand-in. `identity`, `library`, ports, the other settings bags and the store are written back unchanged.
- **The real node returns from the kept data.** A rebuild of a stand-in (a hot reload that succeeds, an installed library, a reset) builds from the kept data with the live props, so values, position and edges come back.

**Considered.**

- *Leaving such nodes out of the canvas-size check.* It fixed the move crash only; every other `wrapper.node` reader kept failing one at a time, and both save losses stayed.
- *Guarding each `wrapper.node` caller.* Many callers, each a place to forget; the invariant "a wrapper always holds a node" removes the whole class.

**Consequences.**

- `NodeWrapper.node` raises only before the first build and after `cleanup()`. The no-instance path (`_pending_position`) remains only for an error node that cannot construct either.
- A stand-in's card shows the error node's look and errors; its title is the error node's label unless the node has a label of its own.
- A stand-in for a freshly dropped node has no data to keep and saves none, as before; it reloads as a fresh node.
- Opening and saving a graph while a library is missing no longer changes that library's nodes in the file.
- The real node returns from the kept data, as when the file is reopened: ports an author added to the class in the fix appear after a reset, not at once.
