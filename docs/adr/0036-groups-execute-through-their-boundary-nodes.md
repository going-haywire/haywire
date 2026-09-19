---
name: groups-execute-through-their-boundary-nodes
description: A Group runs as ordinary nodes in the host's flow — the boundary nodes copy values across a virtual crossing — because a view over assembly can decide when a node runs but never where a value goes; and the interface those nodes carry belongs to the user, so it can grow and shrink while the card only reflects it
status: accepted
see-also: ADR-0022, ADR-0034, ADR-0035
level: architectural
---

# A Group executes through its boundary nodes

**Context.** Haywire had no way to encapsulate part of a graph. Slice 1 of the
Graph-node design gives a selection a **Group**: one card on the parent canvas
standing for a **Subgraph** whose contents live in the same `.haywire` file,
with two **boundary nodes** — `Subgraph Input` and `Subgraph Output` — defining
its interface.

This record settles two questions: how a Group *runs*, and who owns the
*interface* it runs through.

## Inlining at assembly does not work, and fails silently

The original design was to leave execution alone: wrap the graph in a
`FlatGraphView` at the top of `assemble_graph()` that teaches two lookups —
`get_node_wrapper` and `_get_edge_wrappers_for_port` — to see through a
Graph-node. The card and both boundary nodes would be elided, their workers
never called, and the VM, scheduler, lazy masks and callbacks untouched.

Two things make that impossible, and both were found by reading the execution
path rather than by testing:

**Control flow never asks the graph.** `ControlFlowBuilder` reads an outlet's
target straight off the port object — `outlet.get_valid_edges()` — and
`get_node_wrapper` is consulted only afterwards, to turn an id already chosen
into a node. A view can answer questions about ids the builder committed to; it
cannot redirect. A Graph-node therefore stays in `control_nodes` with its worker
running, and since that worker returns no outlet, `_navigate_next` ends the
whole flow at the Group — everything downstream silently stops.

**Data values never travel through assembly at all.** Runtime data transport is
pipe-based and edge-driven: `out()` → `set_value` → `_pipes.propagate()` →
`pipe.pull()` → `sink.set_value()`. A port's `_pipes` are built in
`_refresh_pipes()` from *that port's own linked `EdgeWrapper`s*, and a `Pipe`
holds a **direct Python reference** to the sink `DataPort`. Nothing in that path
reads the Flow, the assembly, or the graph.

That asymmetry is the heart of it: **assembly is id-based and can be
virtualized; the data path is object-reference-based and cannot.** A view over
the assembler decides *when* a node runs and in what order. It can never decide
*where a value goes*. So an inlined Group would have produced a correctly
ordered flow in which every boundary-crossing value stayed on the card's own
port and the interior read its defaults — no exception, no invalid edge, no node
error. The graph would run and quietly produce stale numbers.

## Decision

A Group is **crossed, never bypassed**. The card and both boundary nodes execute
as ordinary nodes in the host's flow, and the boundary nodes carry the values.

In a Subgraph crossed by control:

| step | node | does |
|---|---|---|
| 1 | card, entry hop | its localized data flow evaluates the producers feeding its inlets over **real** edges; `_execute` drains any lazy pull. Returns the virtual `enter_` crossing |
| 2 | Subgraph Input | copies the card's data inlets onto its own outlets; each write fires that outlet's pipes, carrying the values inward over the Subgraph's real edges |
| 3 | interior | runs normally — real edges, real pipes, real adapter chains |
| 4 | Subgraph Output | copies its data inlets onto the **card's** data outlets, which propagate outward |
| 5 | card, exit hop | returns the card's matching real control outlet. A pure hop |

In a Subgraph crossed by data alone there is no control chain, so the card is a
DATA node run once from its consumer's localized data flow, and it does the
inward copy itself.

`FlatGraphView` survives, doing far less than first designed: tree-wide
`get_node_wrapper`, the virtual control transitions, and — for a data-only
Subgraph — one `_get_edge_wrappers_for_port` splice that exists purely so the
topological sort puts the card before the interior. Values cross by worker copy,
never by splice.

## Why the crossings are strings, not ports

A card and its Subgraph are separate graphs, so no edge joins them. A boundary
crossing is instead a **string**, carried by the two places a control transition
travels: the `outlet_map` the assembler builds, and
`ExecutionContext.control_pin`. Both tolerate it — the VM stores the inlet id
without ever resolving it to a port, and `_parse_worker_result` only checks that
a worker returned a `str`.

One token names each crossing from both ends: `enter_in_exec` is the virtual
outlet the card leaves by *and* the virtual inlet the Subgraph Input is entered
through. That is what lets each worker decide what to do from `control_pin`
alone, and it means **no port had to be added anywhere** — every port an edge
actually attaches to stays real and one-directional, so the boundary nodes keep
the direction rule they were designed with.

The seam that makes this possible is `BaseGraph.control_transitions(node_id)`,
which returns the whole `{outlet_id: (next_node_id, inlet_id)}` set. Its default
is what `ControlFlowBuilder` used to do inline, so an ordinary graph is
unchanged; `FlatGraphView` overrides it to add the crossings.

## What each alternative cost

**Splice at the edge layer** — make a crossing edge a real `EdgeWrapper` from
the outer source to the *inner* sink, with the card's pin as the drawn endpoint
only. Genuinely fewer moving parts: pipes, assembly and the VM need no change
because nothing special is left to see through. Rejected because it **dissolves
the boundary at runtime**, and Slice 3's Functions — which run a Subgraph
through a re-entrant call into the same VM — would have to rebuild the boundary
it deleted. The chosen design keeps the boundary real, so a Function becomes an
increment: swap "copy, then continue in the same flow" for "copy, then call a
nested flow".

**Run the card twice with a cache** — the card copies inward on its entry visit
and outward on its exit visit, passing values between the two through
`self.cache`. Rejected on two counts. The entry/exit split is representable for
control but not for data: a data-only Group's card is executed from
`LocalizedDataFlow.execution_sequence`, which is a `List[BaseNode]` iterated
with no inlet, no index and no role, so the worker cannot tell its first
occurrence from its second. And the cache would be the one piece of inter-visit
mutable state in the design, in a VM whose every other piece of mutable state is
a local precisely because it is shared across scheduler threads. Assigning the
two copies to the two boundary nodes — which are already two distinct nodes —
makes the roles distinct by construction and needs no cache at all.

## Why `NodeType.BOUNDARY` earns its place

A boundary node carries neither the DATA nor the CONTROL bit. That was chosen so
one pair of classes could serve data and control crossings alike, the role
coming from the assembly context rather than the type. It turns out to be
load-bearing for a second reason: `BaseNode._execute` returns early for a **data
node with no dirty port**, and a boundary node has nothing feeding it. As a DATA
node it would never run its worker, and the copy would never happen. As
`BOUNDARY` the guard is skipped and it always runs.

## A loop may straddle the boundary

An earlier draft forbade a loopback outlet crossing a Subgraph boundary. It is
wrong here: the inlined control graph spans host and Subgraph alike and the
loopback stack is one local list, so the push and the pop land in the same place
whichever side of the boundary each is on. The rule was also nearly unreachable
— `needs_loopback` is an outlet property, and a crossing loop-body edge derives
a Subgraph *inlet*.

The constraint is real for Functions, where the stack is a local per call and a
body crossing out of a nested flow would push onto one stack and pop from
another. It belongs there, with the mechanism that creates it.

## The interface belongs to the user; the card reflects it

An interface derived once at collapse is wrong as soon as the Subgraph needs
another input. So a boundary node declares exactly **one** port of its own: a
bare `ADD` **growing slot** (ADR 0034). Connecting an interior port to it grows
an **interface port** of that port's type and puts a fresh slot below, the idiom
`AddPortTestNode` already ships.

That makes the ownership explicit, and it runs one way:

**The Subgraph owns the shape** — which ports exist, their ids, their types and
their labels. Every interface port is `PortOrigin.RESOLVED`, because the user
brought it into being, whether by collapsing a selection or by connecting to the
slot. `is_user_removable()` therefore already lets the user remove one, and the
pin menu's removal row already appears. The growing slot alone is `DECLARED`: it
is what the boundary node *is*, so it cannot be removed or renamed.

**The Graph-node owns the values and the order.** Its pins are `DECLARED` — the
user did not make them, the Subgraph did, and a removal row on a card pin would
desync the card from the Subgraph it stands for. But **port order is
presentation**: it is read only when sorting for display, never in assembly,
execution or the edge layer. The card is a node on the parent canvas, so how its
pins are arranged for *that* canvas is the parent's business. `reconcile_interface`
stamps `order` only on a pin it is adding; an existing pin keeps its own.

Growth runs **inward to outward only**. A card cannot author shape: the card
would then have to add a port to a node in another graph, and
`reconcile_interface` — which rebuilds the card *from* the boundary — would have
to become a merge, since a card-originated pin must survive a reconcile that
happens before it reaches the boundary. Keeping one direction keeps reconcile a
rebuild.

### The card learns by watching, not by being told

`reconcile_interface` is the single funnel: collapse, re-bind, growth and
removal all arrive through it. The Graph-node watches its own `SubgraphDefinition`
and reconciles when a boundary node reports a structural change, rather than the
boundary node calling the card.

That direction is the same one the rest of the design already runs in — the card
reads the boundary — and it is the only one that covers removal, which happens
in `remove_port`, framework code with no boundary-node hook. It also fans out for
free: a Macro with several cards gets each of them watching the one definition,
with nothing added.

A **rename** changes a label, never an id. Value transmission pairs card pin to
boundary port through `card_port_id(port.id)`, and every attached edge keys on
the id, so renaming one would break both, across two graphs. The label is carried
to the card by the same reconcile and is read by nothing else.

### A grown `EXEC` port changes what the card is

`flow_type` is a field of a type's `class_identity`, inherited by `as_inlet` /
`as_outlet`. A slot that adopts `EXEC` therefore yields a CONTROL port with no
special casing, and `GraphNode.behavior` — which derives its node type by asking
whether the card carries any CONTROL pin — turns the card into a CONTROL node.
A Group crossed only by data becomes one crossed by control, mid-edit, and
assembles accordingly.

This is why `behavior` is resolved in `reconcile_interface` rather than per read:
it is the one moment the card's pins are stamped, it runs in `post_init` before
anything can read the result, and `BaseNode._execute` reads `is_data_node` on
every node on every run.

### A removed port leaves its edges alone

Removing an interface port removes the card's pin, and the edges that were on it
**stay in the graph, unlinked**. The canvas already draws an edge whose port id
resolves to nothing at the node's **Ghost pin** — `_findPinInHierarchy` walks
`port_id >> parent_id >> root` — so the user sees the wire still attached to the
card and can re-target it. Deleting those edges instead would silently destroy
outer wiring on what may have been a misclick, and would make Subgraphs the only
place in the framework where a vanished port takes its edges with it.

### Non-goals

- **Card-side growth**, for the reason above.
- **Renaming a port id**, which is a cross-graph re-keying operation.
- **Undo for interface edits.** Growing a pin is not undoable anywhere in the
  framework — `hb_resolve` fires from inside `_add_link`, past the undo layer —
  and boundary nodes are not made an exception. The gap is framework-wide.
- **Reordering or renaming from the card.** Both are boundary-side gestures.
- **Macro fan-out**, which needs one definition to serve many cards. Nothing here
  forecloses it; the per-card watcher already supports it.

## Consequences

- The VM, the scheduler, `execution/flow.py` and the whole pipe layer are
  untouched — by construction rather than by assertion. The one change to
  `vm.py` is unrelated and defensive: a strict `ports[...]` lookup in the
  loopback check became `.get(...)`, so a worker returning an id that names no
  port ends its branch through `_navigate_next` instead of aborting the frame
  from a `KeyError` that reached only the log.
- Adapter chains are **not** composed across a boundary. The outer chain runs
  into the card's inlet and the inner chain out of the Subgraph Input's outlet —
  two real hops, same result.
- A card pin's id is namespaced by side (`in_` / `out_`), because the two
  boundary nodes are separate nodes free to use one name each and a control
  Subgraph has `exec` on both. Every pin is prefixed, which keeps the mapping
  total.
- Lazy edges need no special handling: the card runs before the inward copy in
  both shapes, and `_execute` drains its dirty ports there.
- `Subgraph Output`'s worker writes ports it does not own — the card's outlets.
  The card cannot do it itself, because a data-only Subgraph gives it a single
  run that would have to precede the interior.
- A node always sees its own graph's settings tier: an inner node's `graph()`
  mirror resolves through its own `SubgraphDefinition` (ADR 0022), which is a
  `BaseGraph` for exactly that reason.
- A boundary node is never port-less: it carries its growing slot from `init()`,
  so a Subgraph can grow however it was created — by a collapse, by
  `instantiate()`, or from a file. `_validate_boundary_node` still accepts a
  port-less node, because a slot-only node satisfies the one-direction rule
  either way.
- The interface a boundary node carries is `RESOLVED`, so `PortOrigin` now means
  "the user brought this port into being" rather than only "resolved from an
  `ADD` pin". `is_user_removable()` is unchanged, and is still the single gate.
- A card's pin order can drift from its Subgraph's. That is intended, and it is
  why reconcile stamps `order` only on a pin it adds.
