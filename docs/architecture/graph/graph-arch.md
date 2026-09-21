---
status: draft
doc_template: impl-spec
scope: The Graph as data structure: variables, validation pipeline, graph-nodes, haystacks, serialization
see-also:
  - ../../archive/whitepaper/Haywire_design.md
---

# Graph — Architecture

*This is a placeholder. Content has not yet been written.*

**Template:** `impl-spec` — when filled in, this file will follow the proven shape from `library_state.md`:

1. **Mental model.** What this subsystem is, in one paragraph.
2. **Contract.** Declaration / registration / access / invariants.
3. **Lifecycle.** Creation, hot-reload, ordering, observability.
4. **Boundary.** What this is NOT for.
5. **Examples.** Concrete worked cases.
6. **Open questions.** What remains undecided.

**Scope.** The Graph as data structure: variables, validation pipeline, graph-nodes, haystacks, serialization.

## Source material

When migrating, draw from:

- [Haywire_design.md (whitepaper)](../../archive/whitepaper/Haywire_design.md)

## GraphEntry execution lifecycle

`GraphEntry` separates *assembly* from *starting*:

- `compile() -> CompileResult` — builds the per-entry `Interpreter` and calls
  `load_graph` (which assembles the graph; assembly raises `RuntimeError` on an
  invalid graph). The exception is caught and converted to a `CompileResult`
  verdict (`ok` + optional `error`); a failed compile leaves the entry
  non-executing with `interpreter = None`.
- `start()` — dispatches `BEGIN_PLAY` on the already-compiled interpreter.
- `start_execution() -> CompileResult` — compile then (if `ok`) start; the
  back-compatible combined entry point. Returns the verdict so callers (play
  button, haystack load, autorestart) surface assembly failure rather than
  letting a `RuntimeError` escape.

## Run policy

Each `GraphEntry` owns a `GraphRunSettings` bag (purely local, never
registry-backed) describing *how* it runs within its haystack — currently the
`autorestart` flag. It is persisted under the `[graphs.run]` table of the
haystack TOML (omitted when at defaults; sparse). When a running graph is
auto-stopped by a reassembly-requiring validation change
(`HaystackState._on_entry_validation`) and `autorestart` is set, the entry is
recompiled and restarted — but only if `compile()` reports the rebuilt graph is
viable; otherwise it stays stopped.

## Subgraphs

A **Subgraph** is the contents of a **Graph-node** — one card on the parent
canvas standing for a whole set of nodes and edges. Two variants ship: the
**Group**, whose Subgraph lives in the parent `.haywire` file and serves that
one card, and the **Macro**, whose Subgraph lives in its own `.hwm` file as a
library component and can be placed any number of times in any graph. See
[ADR 0036](../../adr/0036-groups-execute-through-their-boundary-nodes.md) for how
a Subgraph executes,
[ADR 0037](../../adr/0037-macros-are-node-kind-components.md) and
[ADR 0038](../../adr/0038-a-placements-interior-is-runtime-state.md) for macros,
and the [glossary](../../reference/glossary.md#encapsulation) for the vocabulary.

### The definition is a graph

`SubgraphDefinition` subclasses `BaseGraph`, so it carries its own `props`,
`meta`, Variables and validation pipeline. That is what delivers the
`framework < subgraph < node` settings chain: an inner node's field resolves its
graph tier by walking `node → wrapper → graph → settings_bag_for(...)`
(ADR 0022), and that graph is the definition rather than the host.

A definition holds its nodes **live** — the wrappers in `node_wrappers` are the
same objects the canvas draws and the VM executes, which is what makes error
locations and live values inside a closed Group work with no id translation.

### One id space across the tree

`BaseGraph` gains a `subgraphs` table keyed by the definition's `key`, plus
`_host_graph` pointing back at the graph whose table holds it. `root_graph`
walks that chain, and `generate_unique_node_id` mints against
`root_graph.tree_contains_node_id` — so **every node id is unique across the
host and every Subgraph beneath it**, at any depth.

That single invariant is what lets `FlatGraphView` be a flat dict search with
nothing to namespace, and what lets a collapse move nodes into a definition and
an expand lift them back out without ever remapping an id.

### Interface

The two **boundary nodes** inside a Subgraph define its interface, and the card
mirrors their ports onto its own pins: the Subgraph Input's outlets become the
card's inlets, the Subgraph Output's inlets its outlets. Pin ids are namespaced
by side (`in_` / `out_`) because the two boundary nodes are separate nodes free
to use one name each — a control Subgraph has `exec` on both. The definition
owns the interface's *shape*; the card owns the port *values*, so an unconnected
inlet's widget value belongs to the instance.

`haywire.core.graph.subgraph_crossing` holds every conversion between the four
id spaces that meet here, so the view that builds a crossing and the worker that
follows one cannot drift.

A Subgraph's **containment** rules — exactly one Subgraph Input and one Subgraph
Output, no EVENT or OUTPUT node inside — are enforced by
`StructuralValidator.validate_subgraph_contents`, which runs in exactly **one**
place: host assembly, from `FlowAssemblyManager`. A Subgraph that is never
assembled therefore never reaches it, which is why a macro document open in its
own tab is not checked there, and why `MacroRegistry` validates containment
itself at registry load.

### Serialization

`to_dict` gains a `"subgraphs"` table; `load_from_dict` restores it **before**
the nodes loop, so a Graph-node can resolve its definition during
`wrapper.build()` and mirror the interface onto its card. A file without the
key restores nothing, and `clear()` drops the table so reloading the same file
is not a duplicate-key error.

A **macro placement**'s definition is the exception: it is marked with
`template_key` and `to_dict` skips every marked entry, so the host file carries
the card and its port values but no interior. The interior is rebuilt from the
template on load, by `post_init`. See
[ADR 0038](../../adr/0038-a-placements-interior-is-runtime-state.md).

Format **v4** carries this, and rides the same bump that renames `DataPort`'s
`parent_group`/`is_group` to `parent_fold`/`is_fold` — finishing ADR 0035, after
which "group" has exactly one meaning in the codebase.

### Collapse and expand

`core/graph/subgraph_collapse.py` is pure analysis over a graph and a selection:
`check_convex` (a two-direction reachability test — see **Convex selection** in
the glossary) and `derive_interface`, which splits the selection's edges by the
clipboard's both-endpoints rule and dedups inlets by their *outer* source,
outlets by their *inner* source. `CollapseToGraphNodeAction` and
`ExpandGraphNodeAction` are inverses, each undoable on its own.

### Macros

A macro is a `.hwm` document registered as a component kind, `MacroNode` is the
card standing for one, and `haywire.core.macro` holds the registry, the template,
the source-resolution helpers and the promote pipeline.

Three things share the name and are not the same:

| | What it is | Where it lives |
|---|---|---|
| the **file** | a graph document, `BaseGraph.to_dict()` minus `key` | `<library>/macros/<Name>.hwm` |
| the **template** | that document parsed, plus a path, a content hash and a per-macro identity | `MacroRegistry`, one per file |
| a **placement's interior** | a live `SubgraphDefinition` instantiated from the template | the host graph's `subgraphs` table, keyed `macro_<node_id>` |

Because a placement registers its interior in its *owning* graph's table — where
a Group's sits — every tree walk finds it unchanged: assembly and validation
recurse on `graph.subgraphs` at whatever level they stand, and
`resolve_definition()` resolves from the graph that owns the node.
`SubgraphDefinition.instantiate()` does the per-placement work, minting
tree-unique ids and rewriting every edge onto them, recursing through nested
definitions.

A card's key is **derived** (`macro_<node_id>`) rather than stored, so pasting a
placement yields a second interior instead of two cards sharing one, and
`bind_subgraph` raises. A reload swaps the interior in place —
`on_class_reloaded` returns `True`, skipping the generic rebuild — and then
takes the ordinary `reconcile_interface()` path, so values, the label and edges
on surviving pins are kept. Recursion is refused at bind time by `MacroNode`, and
again at registry load as the backstop for a file edited outside the studio.

## TODO

- [ ] Write content
- [ ] Verify against codebase
- [ ] Archive source files
