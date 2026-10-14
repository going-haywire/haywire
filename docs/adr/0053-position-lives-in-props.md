---
name: position-lives-in-props
description: A node's position lives only in its props posX/posY; the saved "position" key is dropped with no upgrader, a layout channel names the fields a canvas reads and writes, and moves take that channel
status: accepted
see-also: ADR-0029, ADR-0051
level: core
---

# A node's position lives in its props

**Context.**

- A node's position lived in two places: `NodeWrapper._initial_position` (set from a constructor argument and saved as the `"position"` key) and the props fields `posX`/`posY`. Writing `posX` through `set_property` (the Properties panel, Farmhand) did not update `_initial_position`, which won on the next rebuild, so a moved node jumped back after a reset or hot reload.
- The stage (slice 5) needs a second set of layout fields on the same node. A canvas had no way to say which set it reads and writes.

**Decision.**

- **Props are the single source.** `props.posX`/`props.posY` hold the position. `NodeWrapper` has no `position` constructor argument and no `_initial_position`; `serialize` writes no `"position"` key.
- **The `"position"` key is dropped with no upgrader and no `format_version` bump.** The loader ignores it. Every node in the repo's tracked graph files already carries `posX`/`posY` in its props. A node with neither value in its props loads at `(0, 0)`, where the old fallback was `(100, 100)`. A file whose `"position"` disagrees with its props loads at the props position.
- **A missing value means `0.0`.** Settings serialize sparsely and omit a value equal to its default, so a node at `x == 0` has no `posX` in the file. Readers use `position_of(node)` (`haywire.core.node.layout`), never a direct key lookup.
- **`create_node_wrapper` and `AddNodeAction` keep a keyword-only `position`.** Non-empty `node_data` takes the restore path and skips `init()`; empty `node_data` runs `init()`. A fresh node therefore cannot carry its position in `node_data`. The keyword is written to props after the build and before the node is added. Nothing stores it. Callers that hold `node_data` (load, instantiate, paste, expand, collapse, detach, Save new Macro) put the position in it with `with_position` and pass no `position`.
- **A rebuild carries over the position only.** A rebuild with no `node_info` (reset, hot reload) copies the old instance's `posX`/`posY`. Width, height and `size_adapt` reset, as before.
- **A layout channel names the fields.** `LayoutChannel(name, x, y, width, height, size_adapt)` is a frozen dataclass; `PATCH` is `posX`/`posY`/`width`/`height`/`size_adapt`. `STAGE` arrives in slice 5 with the `stage_*` fields. `NodeProperties.set_position`/`get_position`, `NodeWrapper.move`, `BaseGraph.move_node`, the canvas-size check, `MoveNodesToAction`/`MoveNodesAction` and `Editor.move_nodes_to`/`move_nodes` take a channel. Two moves on different channels never merge in the undo stack. `BaseGraph.move_node` takes `None` for `PATCH`, because a module-level import of `layout` in `graph/base.py` is an import cycle.
- **A canvas owns one channel.** `GraphCanvasManager(channel=PATCH)` passes it to its interaction handlers, visual layer and node UI.
- **`NODE_MOVED` carries no channel.** Each canvas re-reads its own fields on the event. Every JS event and the Farmhand `move_nodes` tool are unchanged.
- **`canvas_width`/`canvas_height` describe the patch.** Where the stage's extent lives is slice 5's decision.

**Considered options.**

- *Keep `"position"` and read it first.* Rejected: it is the second source that caused the bug.
- *An upgrader that copies `"position"` into props for old files.* Rejected: every tracked file already carries props, so the upgrader would only guard files that never saved through the current code, at the price of a version bump.
- *Removing the `position` keyword from `create_node_wrapper`.* Rejected: see the init-versus-restore split above.
- *The channel travelling on `NODE_MOVED`.* Rejected: a canvas knows its own channel, and the JS side would change for nothing.

**Consequences.**

- Breaking by decision: an old file with a node that has `"position"` and no `posX`/`posY` in props loads that node at `(0, 0)`.
- A node written by `set_property` survives save, load and rebuild.
- Slice 5 adds `STAGE` and its extent rule; the patch code paths do not change.
