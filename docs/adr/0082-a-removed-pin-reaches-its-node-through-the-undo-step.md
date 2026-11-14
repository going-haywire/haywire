---
name: a-removed-pin-reaches-its-node-through-the-undo-step
description: Ports that exist for a grown port name it as their owner and are removed with it wherever ports are destroyed; the node hears of the user's removal through on_pin_removed and on_pin_restored, called by the undo step, which keeps what the node needs to reverse its reaction
status: accepted
see-also: ADR-0034, ADR-0064
level: framework
---

# A removed pin reaches its node through the undo step

**Context.**

- A node grows a port when the user wires its `ADD` pin ([ADR 0034](0034-add-is-a-type.md)), and the user may remove that port again from the pin menu.
- Some nodes grow more than the port. The audio mixer adds a `Gain` and a `Mute` beside each input; removing the input left them behind, and the user could not remove them.
- Some nodes keep a second record of their grown ports. The OSC nodes in haybale-protokol hold their argument pins as a text setting; a removal from the pin menu left text and pins disagreeing, and the node was never told.
- Every user removal goes through `RemovePortAction`, which calls `remove_port()`. A node's own code also calls `remove_port()` (Annotation's `release_pins`), and rebuilds ports through `rejig()`.

**Decision.**

- **A port may name an owner** (`DataPort.owner`): a grown port it exists for. It is a **companion**: `RESOLVED`, saved with its owner's id, and the user cannot remove it on its own.
- **A companion never outlives its owner.** `NodeData._pop()`, where every port is destroyed, also destroys each port whose owner is gone, and a `RESOLVED` fold this leaves empty. A rebuild that drops and re-adds the owner in one `rejig` keeps its companions.
- **The node is told through a hook pair on `BaseNode`.** `on_pin_removed(port_id, spec)` returns a memento; `on_pin_restored(port_id, memento)` receives it. They fire once per removal, for the grown port only, and only for `RESOLVED` ports.
- **Only `RemovePortAction` calls them**, after `remove_port()` returns. `remove_port()` stays a structural primitive with no callback, so a node removing its own ports is never called back.
- **The undo step keeps the memento.** Redo calls `on_pin_removed` again and keeps its new memento. Undo re-adds the port and its companions from their saved specs and orders before calling `on_pin_restored`.
- **The hooks may change node state and port values, never ports or edges.** A hook that changes the node's ports, or raises, is recorded in the error ledger as a failure of `Remove pin`. The removal and its undo complete either way, with a `None` memento after a raise.
- **The hooks run on the edit thread**, in the window where the removal already happens: workers may still run, and the graph stops for reassembly afterwards ([ADR 0064](0064-flows-that-share-a-node-share-a-runner.md)).

**Considered.**

- *Firing the hook inside `remove_port()`.* It covers every caller, but on a node's own call nobody keeps the memento, so the reaction cannot be undone, and the hook fires inside the node's own `release_pins`.
- *Firing in `rejig()` or `_pop()`.* The node's own rebuilds pass there too; a hook could not tell the user's removal from them.
- *The node keeping its own undo stash*, as `release_pins`/`restore_pins` do. The stash lives as long as the node, across hot reloads and repeated removals of one id; the memento lives exactly as long as the undo step.
- *Letting the hook remove sibling ports.* The undo step would have to snapshot the whole node. Companions give the framework the structure, so the hook needs none.
- *Companions as a new port origin, or as children of `parent_fold`.* A fourth origin every filter must learn about; a fold has no pin and holds only one level, and where a port shows is a separate question from how long it lives.
- *Refusing a removal whose hook raises or breaks the contract.* A rollback path only broken nodes reach, and a node in development could never lose that pin.

**Consequences.**

- A companion added by code that runs before its owner exists is removed by the next `rejig` on that node.
- A node can learn of a removal only from the user's gesture. Its own removals it knows of already.
- A hook that writes a setting whose callback rebuilds ports must suppress that callback itself; the framework offers no quiet write.
- Graphs saved before `owner` existed load with free-standing ports. A library that wants them owned upgrades them on load, as the mixer does.
