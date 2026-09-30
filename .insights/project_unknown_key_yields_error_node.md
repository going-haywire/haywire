---
name: An unknown node registry key yields an ErrorNode that passes for the real node
description: NodeFactory.get_node falls back to the registered ErrorNode for a key it cannot find. The node's id is still derived from the requested key and it accepts ports added afterwards, so a test with a stale or misspelled key can pass without ever creating the node it names.
type: project
---

# An unknown registry key yields an ErrorNode that passes for the real node

`NodeFactory.get_node(registry_key)` never fails for an unknown key. It logs a
`NodeNotFoundError` and returns the registered **ErrorNode** class instead, so
`graph.create_node_wrapper(key, ...)` succeeds.

Three things then hide the substitution:

- **The id looks right.** The node id comes from the *requested* key, so
  `"haywire-core:node:RerouteNode"` and a stale `"builtin:node:RerouteNode"`
  both produce `RerouteNode_<hash>`.
- **Ports added later still work.** An ErrorNode takes ports through
  `rejig()`/`add()` like any node, so actions that add ports after creation
  (the reroute split, boundary slots) build the expected shape on it.
- **The log is invisible on a pass.** pytest shows captured logs only for a
  failing test, so the `NodeNotFoundError` banner never appears.

## The case

`tests/core/test_undo/test_split_edge_reroute.py` passed
`builtin:node:RerouteNode`, a key that no longer exists. All three split
integration tests passed: the node id, the added `in`/`out` ports and both
edges matched, but every one of them was built on an ErrorNode.

## How to avoid it

- Take a key from the class, not a literal:
  `RerouteNode.class_identity.registry_key`.
- When a test is about a specific node class, assert it:
  `assert isinstance(wrapper.node, RerouteNode)`.
- A `not found in registry` line in a passing test's output (`-rA`) means the
  test is not exercising the node it names.
