# Report: The compiler accepted an invalid graph (control fan-out)

Date: 2026-06-02

The original graph wired one EXEC **outlet** (Begin Player.Execute) to **two**
control inlets. This should be illegal (control flow is single-successor per outlet)
but assembly accepted it.

### Where the gap is
- `FlowAssemblyManager._validate_graph` (`flow_assembly_manager.py:134`) only checks
  for **duplicate event nodes of the same subscription**. No control-topology check.
- `StructuralValidator` (`packages/haywire-core/src/haywire/core/validation/structural_validator.py`)
  has node-level and edge-level rules, but:
  - `validate_graph()` (line 354) only runs `_validate_event_nodes_graph_wide()`.
    "Control flow topology" and "data flow cycles" are explicitly marked
    `# (future: implement ...)` (lines 367–371).
  - `validate_edge` has no rule limiting a control **outlet** to a single outgoing
    control edge.
- `EXEC` type (`barn/haybale-core/haybale_core/types/specs.py:215`) does not set
  `allow_multiple_links`, so multiplicity is left to the port default / builder.

### Open question / needs deeper trace
Is single-successor control fan-out *meant* to be illegal, or is fan-out actually
supported (parallel/sequential execution) and just mis-rendered here? The
`ControlFlowBuilder` behaviour with multiple control successors was not traced.
Decide the intended semantics first, then either:
- add an outlet-multiplicity rule in `validate_edge` / `_validate_edge` for
  `FlowType.CONTROL`, or
- implement the deferred "control flow topology" check in `validate_graph`.
