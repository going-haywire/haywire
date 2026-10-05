---
name: wire-types-replace-flowtype
description: A port's transport is a wire type its data type declares — a never-instantiated class with a closed role — derived for ports and edges, never stored; FlowType is gone
status: accepted
see-also: ADR-0009, ADR-0039, ADR-0041
level: architectural
---

# Wire types replace FlowType

**Context.** `FlowType` was a closed enum (DATA, CONTROL, CALLBACK, NONE) that every type, port and edge carried and saved. A library could not add a kind of edge, three places decided what may connect (the server's formal check, the canvas and auto-wire) and drifted apart, a config port reloaded as DATA because the saved flow beat the type, and `ADD[T]` was DATA whatever `T` was.

**Decision.** A **wire type** is a class that is never instantiated, following the Surface pattern (ADR 0009): its metadata is class attributes, `__init_subclass__` derives its id `"<library>:wire:<ClassName>"` and records it in an id map, and everything compares it by id. A data type names one with `@type(wire_type=…)`; a derived type inherits it, and a container or wrapper without one takes its element's. A wire type picks one of four **roles** — `DEPENDENT`, `SEQUENCE`, `IMMEDIATE`, `VISUAL` — and framework code branches on the role, never on which wire type it is; a new role is a framework change. A port's wire type is derived from its type and never passed or saved (config ports and folds have none); an edge's comes from its ports. Two pins connect when their **wire keys** match: equal ids, or a bare `ADD` slot's wildcard `*`. One function, `wires_match`, decides it on the server, and its mirror on the canvas.

An edge that fails validation is never rewritten: while it fails, its wire type comes from whichever end resolves, for drawing only, and its saved propagation and style are fitted to the wire type only once it validates again. A missing port must never cost the user work — the ghost pin anchors the edge until the port returns.

**Alternatives.** *Keep the enum and add members* — a new kind of edge would still be a framework change, and the drift between the three checks would stay. *A registry with a DI provider* — wire types have no lifecycle of their own beyond their module; the type registry's unmanaged-module reload already reaches them. *Store the wire type on edges and ports* — the stored value is what made a config port reload as DATA; derive it instead.

**Consequences.** A non-builtin wire type is an island: adapters do not bridge two wire types, so a library that wants its types convertible keeps them on `DataWire`. Saved `edge_type` and port `flow_type` keys are ignored; re-saving a graph drops them. A library defines its wire types in a module it imports by full path (`from mylib.wires import MyWire`): the reload cascade follows module imports, and `from mylib import MyWire` does not reach it.
