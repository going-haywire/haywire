---
name: a-changed-declaration-resets-the-node
description: A node is built fresh, keeping its previous setup, exactly when its class declares other ports than its data was saved against; one rule for loading a file and for a hot reload
status: accepted
see-also: ADR-0005, ADR-0059, ADR-0062, ADR-0076, ADR-0078
level: framework
---

# A changed declaration resets the node

> **Amended by [ADR 0078](0078-a-node-follows-its-changed-code-where-nothing-conflicts.md).** A changed declaration resets the node only where its data conflicts with the change; otherwise the saved ports follow the code and the node keeps its setup.

**Context.**

- A graph file holds the declaration each node class had when it was saved ([ADR 0076](0076-a-graph-file-stores-what-differs-from-the-code.md)), but nothing read it. A node loaded after its library changed kept the ports its file listed: a port the code had added was missing and one the code had removed was still there, with no notice.
- A hot reload treated every edit alike. It rebuilt each placed node through `init()` and flagged every node the user had configured, also when the edit changed only a worker ([ADR 0062](0062-a-reload-keeps-the-previous-setup.md)).
- The two events are the same: a node's data was saved against one declaration and its class now has another.

**Decision.**

- **One test.** `NodeWrapper.build(node_info, declared=...)` takes the declaration the data was saved against and compares it with what `init()` declares now, both in the form a file holds them (`same_declaration`).
- **Same declaration: the node is built from its data.** On a load as before. On a hot reload this is new: the node keeps its values, promotions, grown ports and label, and nothing is flagged.
- **Changed declaration: the node is built fresh and keeps its previous setup.** It stays where its data put it (position, stacking order, place on stage). The data becomes its previous setup if the fresh node differs from it, with the ADR 0062 badge, commands and ledger row. An untouched node keeps nothing.
- **A previous setup carries the declaration it was saved against**, under `declared`.
- **Restore puts the previous setup on the ports the code declares now.** A declared port is built on the current declaration with the setup's values and changes. A port the old code declared, of the type it declared, that the code no longer declares is left out. A port the user grew comes back.
- **A node may carry its own declaration.** A node whose `init()` declares something of its own, such as its id as a default, differs from the one entry the file holds for its class. A save writes that node's declaration into its data, and a load reads it before the class's entry.
- **No declaration, no test.** Data from a paste, an undo, a file older than format v5 or a file without an entry for the class is built unchecked.

**Considered.**

- *Merging the file's ports with the changed declaration.* It keeps the user's values across a code change without asking, and is the intended next step. It needs rules for a field both sides changed; resetting needs none, so it comes first and stays the answer wherever a merge would have to guess.
- *Resetting on a library version change.* Every node of every class of a released library would reset, also the classes that did not change.
- *Requiring that `init()` declares the same for every node.* A node that breaks the rule would reset on every load with nothing to tell its author why. Letting the node carry its declaration costs a few lines in the file.

**Consequences.**

- Opening a graph after a library changed a node's ports resets the nodes of that class the user had configured; each shows the badge until the user picks Restore or Discard.
- A worker-only edit no longer resets anything on hot reload. An edit to code that adds ports later (a callback) does not show on placed nodes until they are reset or the callback runs again.
- A stand-in is never reset: it has no class to compare with, and keeps its data ([ADR 0058](0058-a-broken-node-keeps-its-data.md)).
- `ValidationManager._keep_previous_setup` is gone; the wrapper decides for both events.
