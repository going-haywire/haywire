---
name: a-reload-keeps-the-previous-setup
description: A hot reload rebuilds nodes pristine and records no undo step; each node whose setup changed keeps its previous setup, which the user applies or dismisses from the card, in every graph
status: accepted
see-also: ADR-0058, ADR-0059, ADR-0061
level: framework
---

# A reload keeps the previous setup

**Context.**

- A hot reload rebuilds every placed node of the reloaded class through `init()` (ADR 0059). The user's setup on those nodes (values, promotions, grown pins, label) survived only as an undo step the reload recorded after the fact.
- That step was misleading where it worked. Undo is a reflex for graph edits; when the code change was about those very settings, an undo reapplied the old values over it, on whichever instance the user happened to undo. The step also sat in the history's order, so getting the setup back meant undoing every edit made since.
- It was silent where it did not work. A graph without an editor has no history: a Group interior that was never opened, a Macro interior, a graph built for one task. There the setup was gone with nothing shown (backlog #46).

**Decision.**

- **The reload records nothing; each changed node keeps its previous setup.** A node whose data after the rebuild differs from before holds that data as its **previous setup** (`NodeWrapper.previous_setup`). Stand-ins (ADR 0058) and nodes that absorb their reload (`on_class_reloaded`) are left out. Needing no history, it works in every graph.
- **The first one is kept.** A later reload never replaces a held previous setup, since the data before it is a rebuilt node's pristine data. When a rebuild reproduces the previous setup, it clears itself. A reload that ends as a stand-in keeps what was held.
- **It is part of the node's data.** `serialize()` writes it inside `node_data` under `previous_setup`, and `build(node_info)` reads it back. So a saved file, Delete+Undo, Collapse to Group and every rebuild snapshot carry it. Copies drop it: the clipboard payload, a Macro template written from a Group, and each Macro placement built from its template hold none (`strip_previous_setups`).
- **The user decides on the node.** The node carries a `NodeWarning(kind="previous_setup")`, which its card's warning badge shows. The commands live in panels, not in the skin, so a node drawn by any skin can be resolved: under "Settings reset by a code change" in the node's right-click menu and in the Node tab of the Properties editor, **Restore** (apply it) and **Discard** (dismiss it) sit side by side, each with a tooltip, from level mode edit. Farmhand's `graph_editor_previous_setup` does the same for agents.
- **Apply restores the whole previous setup.** It goes through the load path, as opening a file saved before the code change would, with no per-field matching. Only the node's arrangement (position, stacking order, place on stage) stays as it is now.
- **Reset, Apply and Dismiss are one action.** `RebuildNodesAction` rebuilds each node from an optional `after` data, else through `init()`; one undo step each. Undo restores the node's data from before, previous setup included. A rebuild through `init()` drops the previous setup, so Reset dismisses it and Undo of Reset brings it back.
- **The ledger is told, per node.** Each node that keeps a previous setup, and each node found holding one when a graph is opened, adds a WARNING with its `graph_id` and `node_id`, so Reveal finds it. A node inside an interior is named with its host. The row only informs: resolving the node leaves the row, and clearing rows leaves the setup.

**Considered.**

- *The undo step (ADR 0059).* Undo reapplied the old setup over a code change about it, and nothing happened at all without a history.
- *Recording on the nearest host's history* for graphs without one. That closes the silent case but keeps the misleading one.
- *A ledger entry only* (ADR 0061 had settled #46 that way, as a loss). With the setup kept, nothing is lost; the decision belongs on the node, and the ledger cannot act on it.
- *Rehydrating the setup onto the rebuilt node* where it still fits. Rejected in ADR 0059: every fit test guessed at intent and some guessed wrong.

**Consequences.**

- A hot reload is not undoable. Getting the setup back is Apply, an ordinary undoable edit.
- A code change to a default flags every placed node, also one the user never touched, since its data differs from before. One Dismiss each, or the Farmhand tool for many.
- Dismiss rebuilds the node, as Reset does.
- A node inside a closed interior is reached through its ledger row, which names the host; Reveal does not yet open closed interiors.
- A Macro placement's interior is not saved, so a previous setup kept there after a reload lasts for the session; the placement rebuilds from its template when the graph is reopened.
- A reload compares only what Apply would restore (`previous_setup.restorable`): not `identity` and `library`, which describe the class; not the node's arrangement, which Apply keeps; and not a size the canvas measures on an auto axis. So editing a class's label or docstring flags no node, an untouched node is never flagged by its measured size, and a node moved since it was flagged still clears once a rebuild matches its setup.
