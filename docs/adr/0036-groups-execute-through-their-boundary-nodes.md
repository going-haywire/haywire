---
name: groups-execute-through-their-boundary-nodes
description: A Group runs as ordinary nodes in the host's flow — the boundary nodes copy values across a virtual crossing — because a view over assembly can decide when a node runs but never where a value goes
status: accepted
see-also: ADR-0022, ADR-0035
level: architectural
---

# A Group executes through its boundary nodes

**Context.** Haywire had no way to encapsulate part of a graph. Slice 1 of the
Graph-node design gives a selection a **Group**: one card on the parent canvas
standing for a **Subgraph** whose contents live in the same `.haywire` file,
with two **boundary nodes** — `Subgraph Input` and `Subgraph Output` — defining
its interface.

The question this record settles is how a Group *runs*.

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
