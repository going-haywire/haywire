---
name: a-node-follows-its-changed-code-where-nothing-conflicts
description: When a node's class changed its declaration, the node's saved ports follow the code field by field and keep what the user or the node changed; the node is reset only where both changed the same thing
status: accepted
see-also: ADR-0062, ADR-0076, ADR-0077
level: framework
---

# A node follows its changed code where nothing conflicts

**Context.**

- A changed declaration reset the node ([ADR 0077](0077-a-changed-declaration-resets-the-node.md)). Correcting one port label in `init()` reset every configured node of the class, in every graph and on every hot reload; the user had to pick Restore on each.
- Three things are known at that moment: the declaration the data was saved against, the saved ports, and the declaration the class makes now. A saved port holds only what differs from the first ([ADR 0076](0076-a-graph-file-stores-what-differs-from-the-code.md)), so what the user or the node changed is already written down, per field.

**Decision.**

- **The saved ports are merged onto the current declaration** (`merge_ports`) before the node is built from them. The merge compares the three by equality only; it never judges whether a value fits.
- **A field only the code changed follows the code.** Label, description, widget, default and the rest of a declared port.
- **A field only the saved port changed keeps its saved value.**
- **A field both changed to different values is a conflict.** Display order and hidden state are the exception: the saved value wins.
- **A value follows a changed default only while nobody set it**, which is when it equals the earlier default. A set value stays.
- **A port the code added is added**, after the declared port it follows in `init()`. **A port the code removed is left out**, with its value.
- **A port the code retyped** takes the new type if the saved port holds nothing of its own. If it holds a set value or a changed field, that is a conflict.
- **Where the node changed a declared port itself and the code changed it too, that is a conflict**: a port the node retyped or removed, or a port id the node grew that the class now declares.
- **A conflict resets the node** and keeps its previous setup, as ADR 0077 describes. One conflict resets the whole node, not the one port.
- **A merge that changed something leaves an info entry in the ledger**, naming what changed. The node shows no badge.
- The rule is the same for loading a file and for a hot reload.

**Considered.**

- *Resetting on every changed declaration* (ADR 0077 alone). Simple to explain, but an author's smallest correction costs every user their settings, so authors stop correcting.
- *Conflict per port instead of per field.* Any user change to a port would conflict with any code change to it. More resets, and no simpler: the comparison is the same.
- *Keeping a removed port that holds a value or an edge.* The node would then differ from its code for good, and the next save would write a port no code declares.
- *Resetting only the conflicting port.* A node half from its file and half fresh is harder to reason about than one that is either.

**Consequences.**

- Opening a graph after a library changed labels, defaults or widgets, or added or removed ports, changes its nodes without asking. The ledger lists each one.
- An edge to a removed port is dropped when the graph loads, as it is after a reset.
- A node that reshaped a declared port itself is reset when the code changes that port, although the user touched nothing.
- A change of meaning that keeps the shape (degrees to radians) is not seen by the merge, nor by the reset.
- A port added by a callback has no declaration, so it does not follow the code.
