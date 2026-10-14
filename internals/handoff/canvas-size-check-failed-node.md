---
name: canvas-size-check-failed-node
description: Handoff — one node whose construction failed makes BaseGraph._check_canvas_size raise, so every later add, remove and move in that graph fails until the node is fixed
metadata:
  type: project
  status: open
---

# Handoff — A node that failed construction breaks the canvas-size check

**Status:** not started. Found in the final review of editor-modes slice 4 (Position), which is merged into `feat/editor-modes-slice1` (`3dfd0e26`). It predates slice 4: the same code raised the same way at `8722a4f4`, the branch base. Slice 4 did not make it worse, and it doesn't block slice 5.

**Context:** [ADR 0053](../../docs/adr/0053-position-lives-in-props.md), plan `docs/superpowers/plans/2026-10-14-editor-modes-04-position.md`.

Line references are from 2026-10-14. Check them before you rely on them.

## Mechanism

- `BaseGraph._check_canvas_size` (`packages/haywire-core/src/haywire/core/graph/base.py:552`) takes the maximum of `getattr(w.node.props, channel.x/y)` over every wrapper in `node_wrappers`.
- `NodeWrapper.node` (`packages/haywire-core/src/haywire/core/node/node_wrapper.py:177`) raises `RuntimeError` when `_node_instance` is `None`. That is the case for a node whose class failed to construct, from a bad setting declaration, an exception in `__init__`, or an import error after a hot reload.
- The check runs from:
  - `add_node_wrapper` (:467)
  - `remove_node_wrapper` (:493)
  - `move_node` (:534)
  - `estimate_canvas_size` (:597)

  So once one node in a graph has no instance, every later add, remove and move in that graph raises, not just actions on that node.

## Effect on the user

A class edit that breaks construction (a typo during hot reload) leaves the graph unable to add, delete or move anything until the class is fixed and the node rebuilt. The error surfaces far from its cause.

**Check first:** whether loading a file with such a node fails as well. The loader adds wrappers through `add_node_wrapper`. The slice-4 implementer reported that "a load drops such a node the same way". Confirm what the user actually sees.

## Suggested fix

- Skip wrappers without an instance in the max, or let them contribute their pending position.
- Since slice 4, `NodeWrapper._pending_position` holds the position of a node with no instance (ruling R3, ADR 0053). A small accessor such as `NodeWrapper.layout_position(channel)`, which returns the props position or the pending one, would let the canvas check measure every node without touching `.node`.
- The pending position is PATCH-only (`NodeWrapper.move`). For the stage channel (slice 5), skipping is enough.

## Verify with

1. A test node whose `__init__` raises (pattern: `tests/core/test_node/test_position_single_source.py`, the raise-once class). With one such node in a graph, `create_node_wrapper`, `remove_node_wrapper` and `move_node` on another node still work.
2. The canvas size still covers a failed node at its pending position, if you take that route.
3. A load of a file containing such a node: other nodes load, and the graph stays editable.
4. Full gate: `uv run pytest -m "not browser and not perf" -n 4`. This is core graph code.

## Related

`NodeWrapper.serialize` writes no `node_data` for a node without an instance, so its position and settings are lost on save (ADR 0053, Consequences). This is broader than position. Decide it together with this fix or ticket it separately.
