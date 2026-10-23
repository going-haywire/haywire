---
name: reload-and-reset-are-undoable
description: A node Reset and a successful hot reload rebuild the node pristine through init(), and each is one undo step per graph whose Undo rebuilds the nodes exactly from their data from before
status: accepted
see-also: ADR-0053, ADR-0058
level: framework
---

# Reload and Reset are undoable

**Context.**

- A hot reload of a node class rebuilds every placed node of it through `init()`. Everything the user set on those nodes — promotions, setting and port values, grown pins, label — is gone; only the arrangement survives: position, stacking order and place on stage (ADR 0053). A node Reset does the same on purpose, and could not be undone either.
- Carrying the user's data across the rebuild was tried and abandoned (2026-10-21): deciding whether a value still "fits" new code is a guess about intent, and the guesses kept misfiring.

**Decision.**

- **The rebuild stays pristine; the step before it is kept.** `RebuildNodesAction` holds each node's `serialize()["node_data"]` from before the rebuild. Undo rebuilds every node exactly from it — the load path, as opening a saved file does. Redo rebuilds them through `init()` again. Both go through `BaseGraph.request_node_rebuild`, so the validation pass rebuilds attached edges with them.
- **Reset is that action**, run through `Editor.reset_nodes` as an ordinary edit (refused below level mode edit).
- **A successful hot reload records it after the fact.** An `Editor` registers its history on its graph (`BaseGraph.set_history`). The validation pass keeps each `NODE_HOT_RELOADED` node's data before rebuilding it and records the batch as one step (`IHistoryManager.record_executed`), named "Reload Print", "Reload Print (2 nodes)" or "Reload 3 nodes".
- **Not recorded:** a reload that ended as a stand-in (a failed reload is not undoable); a reload of a stand-in, which already restores its kept data (ADR 0058); a node whose data the reload left as it was (an untouched node); a node that absorbs its own reload (`on_class_reloaded`); a graph without an editor; a batch validated off the main thread, since the history has no lock.

**Considered.**

- *Rehydrating the user's data onto the rebuilt node* where it still fits the new code. Every fit test inspected values (validators, read-back types, default comparisons) and a review round found three cases where it guessed wrong.
- *No undo* (the previous behaviour). Every save of a class threw away what the user had set on its nodes, with no way back.

**Consequences.**

- Undo after a reload brings back the node's previous shape on the new code, as opening an older file does: ports the code removed come back until Redo.
- A reload hitting the host graph and an opened Group interior records one step for each graph on their shared history: two Ctrl+Z for one save.
- A Group whose interior was never opened has no editor on its definition graph, so a reload inside it is not recorded.
- Several quick saves of a class record one step each.
