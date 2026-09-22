---
name: macros-are-node-kind-components
description: A macro is a node kind whose component is a .hwm file rather than a Python class — registered through a DocumentRegistry that satisfies the class contract, so the factory, the add-node menu, the docs generator and the hot-reload relay reach every placement with no machinery of their own
status: accepted
see-also: ADR-0036, ADR-0038
level: architectural
---

# A macro is a node kind, and its component is a file

**Context.** A **Group** (ADR 0036) is a Graph-node whose Subgraph lives in the
parent `.haywire` file and serves exactly one card. A **Macro** is the same card
over a Subgraph that lives in **its own file**, is a library component, and can
be placed any number of times in any graph.

That raises one question the Group never had to answer: what is a macro *to the
framework* — a file the studio happens to read, or a component like any other?
Everything else follows from it.

## The alternative: a node class that points at a file

The obvious shape is a single `MacroNode` class registered once, whose store
holds the path (or key) of the macro it stands for. The registry stays
class-only, no file format enters the component system, and a placement is an
ordinary node with an unusual setting.

It breaks on reload, and on identity.

**Reload has nowhere to land.** Hot-reload fans out **per registry key**:
`NodeFactory` relays a registry's lifecycle batch to every `NodeWrapper`
subscribed on the key that changed. Under one shared class there is exactly one
key, `builtin:node:MacroNode`, so saving `Blur.hwm` either notifies every
placement of every macro or notifies none. Delivering the event to the right
cards would mean a second, macro-shaped subscription mechanism running beside
the one the framework already has.

**Identity is per macro, not per class.** A card's label, description, menu path
and search tags come from `class_identity`. One class has one identity, so every
macro in the add-node menu would read "Macro", and every consumer that shows a
component — the menu, the library overview, Component Docs, `describe_component`
— would need a macro-specific branch to find the real name.

## Decision

A macro **is a node kind**. Its registry key is `<library>:macro:<Name>`, minted
from the file's stem, and it takes a seat in `kind_registry_map()` beside
`node`, `type` and the rest.

Three things make that work.

**`ComponentRegistry`, extracted from `BaseRegistry`.** What a consumer actually
uses of a registry is thin: `add_folder`/`remove_folder` for `BaseLibrary`,
`event_dispatcher` for the file watcher, the lifecycle queue and both subscriber
lists for the factory, and `get`/`has`/`list_names`/`list_visible_names`. That
is now the base class. `BaseRegistry` keeps everything module-centric —
`sys.modules`, `importlib`, the dependency graph, rollback — and becomes one of
two subclasses.

**`DocumentRegistry`, the other subclass.** It globs one suffix under a claimed
folder, parses each file into an element, and maps file events onto the lifecycle
a class registry already emits: CREATED → `CLASS_ADDED`, MODIFIED →
`CLASS_RELOADED`, DELETED → `CLASS_REMOVED`. It hashes the text on every load, so
a save that does not change the bytes notifies nobody. A parse or validation
failure emits `CLASS_RELOAD_FAILED` against the key and leaves the previous
element registered.

The file watcher needed no change for this. `_get_matching_registries` already
routes *every* file under a claimed folder; the `.py` filter was never the
watcher's, it was `BaseRegistry.event_dispatcher`'s own. A document registry
simply claims a different suffix.

**The template satisfies the class contract.** `MacroRegistry.get(key)` returns a
`MacroTemplate` — the parsed document, its path, a content hash, and a per-macro
`NodeIdentity` whose label is the filestem, whose description is the document's
`meta.description`, and whose menu is `macros/<library label>` — one root the
create menu lifts above the node categories, grouped by library. It exposes
`class_identity` and `class_library`, which is all the `RegisteredClass` Protocol
asks for. Consumers that walk kinds generically — the docs extractor, the
farmhand helpers, the library overview — read it without learning it is a file.

`NodeFactory` takes both registries and dispatches on the key's kind segment.
`get_node("lib:macro:Blur")` returns `MacroNode` when the template is present and
takes the error-node path when it is not, so a graph using a macro from an
absent library loads its placement as the error node from the same serialized
ports block — exactly as any missing node does.

## Consequences

- **Reload fan-out is the machinery that already exists.** A placement's
  `registry_key` is the macro's own, so a save reaches every placement in every
  open graph through the per-key relay, with nothing added. What a placement
  *does* with that event is ADR 0038.

- **The file is a graph document.** A `.hwm` is `BaseGraph.to_dict()` output
  minus `key`, so the graph editor opens it unchanged and prehydration and
  format bumps apply to it as to any graph file. The suffix exists to tell the
  registry which files to claim, not to describe a second format.

- **Validation happens at registry load, without instantiating.**
  `validate_containment` reads each node's `registry_key` against `NodeRegistry`
  and checks the class's declared `NodeType`: exactly one Subgraph Input and one
  Subgraph Output, and no EVENT or OUTPUT node. It must not build the nodes — a
  registry scan that instantiates would open whatever hardware their `init()`
  touches. A node class that is not registered is skipped; an absent library is
  the placement's problem, not the document's.

- **Recursion is refused twice.** At bind time in `MacroNode`, so the card the
  user placed is the one that reports it, and again at registry load as the
  backstop for a file edited outside the studio. `MacroRegistry` walks the macro
  keys reachable from a document and refuses one that reaches back.

- **A filestem is a registry key**, so it must look like one:
  `^[A-Za-z][A-Za-z0-9_-]*$`. A non-conforming file is skipped at scan with a
  ledger warning rather than registered under a key nothing can address. The
  same stem twice in one library is a duplicate-key error; across libraries the
  keys differ and the usual alternate-key resolution applies.

- **Scan order matters.** `MacroRegistry` scans at priority 75, after
  `NodeRegistry` at 70, because containment reads node classes.

- **Lifecycle event names still say `CLASS_`.** Renaming them would touch every
  registry and every subscriber to describe the same event. The enum carries a
  note that a document registry emits them for documents.

- **The docs generator documents a macro like a node** — by its interface,
  through the same instantiate-in-a-throwaway-graph path, because a macro's pins
  exist only once a card is built. It carries no docstring: a document's prose is
  its description alone, so the coverage report does not ask for one.

- **Function (Slice 3) is the second `DocumentRegistry`.** The extraction is
  worth its cost only because a second file-backed kind is already designed.
