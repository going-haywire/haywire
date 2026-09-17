# Assembly decides *when* a node runs; pipes decide *where* a value goes

Two independent systems, sharing no code. Getting them confused costs a
redesign, and the failure mode is silent: a graph that runs and produces stale
numbers, with no exception, no invalid edge and no node error.

## The two paths

**Order** — `FlowAssemblyManager.assemble_graph()` → `ControlFlowBuilder` +
`DataFlowBuilder` → a `Flow` whose `control_graph.control_nodes` and per-node
`LocalizedDataFlow.execution_sequence` say what the VM executes, and in what
order. All of it travels as **node ids**, resolved through the graph. This layer
*can* be virtualized — that is what `core/assembly/flat_view.py` does.

**Values** — entirely separate, and the graph is not in it:

```
worker: self.out('value', 2.0)                  node/data.py
  → port.set_value(...)
    → if outlet: self._pipes.propagate()        types/port.py
      → pipe.pull()                             types/pipe.py
        → self.sink.set_value(converted, ...)
```

`_pipes` is built in `DataPort._refresh_pipes()` from **that port's own linked
`EdgeWrapper`s**, and a `Pipe` holds a **direct Python reference** to the sink
`DataPort`, captured at housekeeping time. There is no id lookup at runtime to
intercept, and `vm._evaluate_data_flow` just calls `_execute` in sequence.

So: **assembly is id-based and can be virtualized; the data path is
object-reference-based and cannot.**

## What this rules out

A view over the assembler cannot move a value across any boundary. The Group
design originally proposed exactly that — elide the Graph-node and both boundary
nodes at assembly, splice the two graph lookups, leave execution untouched. It
would have produced a correctly ordered flow in which every boundary-crossing
value stayed on the card's own port while the interior read its defaults.

If you are ever tempted to make a node "transparent" by teaching assembly to see
through it, the value plumbing needs its own answer: a real edge to the real
endpoint, or a worker that copies. Groups took the second (ADR 0036).

## A second trap in the same area

`ControlFlowBuilder` does **not** consult the graph for a control target either:
it reads `outlet.get_valid_edges()` off the port object, and
`graph.get_node_wrapper` at the next line only turns an already-chosen id into a
node. `BaseGraph.control_transitions()` exists so that question goes through the
graph and a view can answer it differently; if you add a lookup back onto the
port, Subgraph crossings stop resolving.

## How to check

A graph that assembles into the right nodes in the right order proves nothing
about values. Assert on a **port value after a frame**, not on the assembled
shape — `tests/core/test_assembly/test_flat_view.py` does this: 7.0 on an
unconnected card inlet must come back as 12.0 on the card's outlet. The shape
assertions there all passed while values were still broken.
