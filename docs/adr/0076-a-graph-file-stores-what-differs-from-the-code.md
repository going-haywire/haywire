---
name: a-graph-file-stores-what-differs-from-the-code
description: A saved port holds its floor plus what differs from its node's declaration, a load runs init() first, and the file names its libraries and declarations once (format v5)
status: accepted
see-also: ADR-0005, ADR-0019, ADR-0058, ADR-0062
level: architectural
---

# A graph file stores what differs from the code

**Context.**

- A load rebuilt every port from the file alone; `init()` ran only for a freshly dropped node ([ADR 0005](0005-compatibility-warnings.md)). Each saved port carried three owners' values in one block: its type's (colour, icons, default, widget, class and module names), its node author's (label, description, callbacks, link rules) and the user's (order, hidden, value).
- So a code change never reached a saved graph. A type's new colour, a port's corrected label or default, a renamed callback method: placed nodes kept what the file said. The remedy was Reset, which drops the node's values.
- Drift was reported only where a library author had written a `CompatibilityWarning` by hand.
- Settings already worked the other way: the class declares them and the file holds values and promotions ([ADR 0019](0019-settings-owned-promotion.md)).
- Each node also carried its class's `identity` and `library` blocks (an absolute folder path among them), its `props` twice and its id twice.

**Decision.**

- **What a type says is not saved.** A port's `to_dict()` leaves out each field that equals its type's identity, and `from_spec()` takes those from the type the `recipe` names.
- **A node has a declaration.** The ports `init()` adds, taken right after it runs (`NodeData.declaration`). A port reshaped, removed or grown later does not change it.
- **`init()` runs on every build, and only declares.** A load runs `init()`, takes the declaration, then replaces the ports with the saved ones. `init()` adds ports and does nothing else; runtime state belongs in `post_init()`.
- **A declared port is saved as its floor and its differences.** The floor is `id`, `port_type`, `origin`, `parent_fold` and `is_fold`: what a stand-in ([ADR 0058](0058-a-broken-node-keeps-its-data.md)) needs to rebuild the port and hold its edges without the class. Every other field is saved only where it differs from the declaration, and the load builds the port on its declaration.
- **Any other port is saved whole.** A port grown after `init()` (resolved from an `ADD` pin, added by a callback), and a declared port whose node gave it another type, have no declaration to lean on. The file owns them, minus what their type says.
- **The file decides which ports exist.** A declared port absent from the file stays absent: its node removed it.
- **The file names its libraries and declarations once.** `requires` maps each library to the version the file was saved with; `declarations` maps each node class to its declaration. A node keeps `ports`, `settings`, `props` and `store`, and nothing its class says. An entry for a class that is not loaded is written back unchanged.
- **Format v5.** `UpgradeVersionFive` builds `requires` from the v4 `library` blocks and drops the rest, in Subgraph definitions too.
- **A v4 port takes its fields from the code, once.** A v4 file saved every field and holds no declaration, so a value the code has since changed cannot be told from one the user set. The upgrader marks such nodes (`legacy_ports`); a declared port of a marked node, still of its declared type, takes only its order, its hidden state and its value from the file. Grown and retyped ports stay as the file has them.

**Considered.**

- *Leaving the file as the whole truth and improving the warnings.* The stale value stays, and the only repair still drops the user's values.
- *A version number per node class.* It says a class changed only when its author remembers to raise it, and nobody raises one per save during a hot-reload session. The saved declaration is the same fact, computed.
- *A hash of the declaration instead of the declaration.* Smaller, but a hash cannot be upgraded: renaming one port field would make every node of every older file look changed.
- *Declaring ports in the class body, as settings are.* It gives the declaration without building a node, but changes how every node is written; `init()` gives it for the price of one call per build.
- *Letting a v4 file win.* Every existing graph would keep its stale values and save them again as if they were choices.

**Consequences.**

- A change to a type reaches every saved port of that type at the next load, with no notice.
- A change to a declared port's label, description, widget, callback or link rule reaches saved nodes where the user or the node has not changed that field.
- A node whose `init()` raises no longer loads from its file; it keeps its data as a node that fails to load does (ADR 0058).
- A stand-in's ports carry only what the file has: a declared port shows its type's label until its class returns.
- Ports a callback adds keep their saved label and callback names, as before.
- A v4 file loses, on declared ports, a `show_widget` choice made from the pin menu and a widget setting changed on the card.
- The saved declaration lets a load tell that a class's declaration changed since the file was saved. Nothing acts on that yet.
- ADR 0005's warnings remain for changes of behaviour; a changed port declaration no longer needs one.
- A file grows by one declaration per node class and shrinks by the class facts of every node: `10x64n_56x5e` went from 1578 KB to 855 KB.
