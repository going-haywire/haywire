# Report: Allow multiple event nodes of the same type per graph

Date: 2026-06-03
Type: design change (loosen a structural rule)
Status (2026-10-29): **blocked on execution groups** (`docs/superpowers/plans/2026-10-29-execution-groups.md`,
ADR 0064). Do not loosen before that lands: two event nodes whose chains share a control node would
run that node on two threads at once. Once it lands the refusal breaks nothing it protects and should
go (ADR 0043: defuse, don't refuse). Fan-out stays illegal: ADR 0044 caps a control outlet at one link.

## The restriction today

A graph may contain **at most one event node per event subscription key**. Enforced
in two places:

- `StructuralValidator._validate_event_nodes_graph_wide`
  (`packages/haywire-core/src/haywire/core/validation/structural_validator.py:278`)
  — errors on `len(node_ids) > 1` for any subscription key.
- `FlowAssemblyManager._validate_graph`
  (`packages/haywire-core/src/haywire/core/assembly/flow_assembly_manager.py:157`)
  — the same duplicate-subscription check, raised as a `RuntimeError` at assembly.

So a graph can have only one `Begin Player`, one `Shutdown`, one `Tick` of a given
identity, etc.

## Why this is too strict

We want to be able to **start several independent flows from the same event** — e.g.
two unrelated chains both kicking off at `Begin Player`.

Given the **hard rule for control edges** — an EXEC outlet drives exactly one
successor; `ControlFlowBuilder` takes `edge_wrappers[0]` and ignores the rest
(`packages/haywire-core/src/haywire/core/assembly/control_flow_builder.py:88`) — a
single event node *cannot* fan out to two independent control chains. One outlet =
one downstream path.

Therefore the only way to express "two independent flows triggered by Begin Play"
is **two Begin Play nodes**, one rooting each chain. The current one-event-node
rule forbids exactly that. The two rules together make parallel same-event startup
**impossible to express** in a graph.

## Why allowing it is sound

- The execution model already supports it. Assembly builds **one flow per event
  node** (`flow_assembly_manager.py:107`) and dispatch enqueues a trigger into
  **every** flow registered for a subscription key
  (`Interpreter._dispatch_event`, `interpreter.py:282`+ iterates the list of
  flows). The dispatch path is already list-shaped — `event_subscriptions[key]` is
  a `List[Flow]`. Two Begin Play nodes would simply register two flows under
  `system:begin_play`, and one BEGIN_PLAY dispatch would trigger both.
- So the restriction is a *validation* policy, not an execution limitation. Removing
  the duplicate-subscription check (in both validator and assembly) likely makes
  multiple same-type event nodes "just work" for dispatch.

## What to change (needs design — do not implement blind)

- Drop / loosen the duplicate-subscription error in
  `_validate_event_nodes_graph_wide` (structural_validator.py:278) and the mirror
  in `_validate_graph` (flow_assembly_manager.py:157).
- Confirm flow ids stay unique: `Flow(flow_id=f"flow_{event_node.node_id}", ...)`
  (`flow_assembly_manager.py:210`) is keyed by node id, so two event nodes already
  produce distinct flow ids — good.
- Verify nothing downstream assumes a 1:1 subscription→flow mapping (stats,
  callback registration, UI that lists "the" begin/shutdown node).

## Open questions / interactions

- **Determinism / ordering.** Answered by execution groups (D3/D4): disjoint chains
  land in separate groups and run in parallel, unordered; chains sharing a control
  node merge into one group and run one frame at a time in trigger arrival order.
- **Shutdown semantics.** Multiple `Shutdown` nodes → multiple graceful-teardown
  flows. `Interpreter.stop_execution` waits on *all* flows under `system:shutdown`,
  and execution groups keep that protocol — still worth a test.
- **Fan-out vs. multiple event nodes.** Settled: ADR 0044 caps a control outlet at
  one link, so multiple event nodes are the only way to express "N parallel chains
  from one event."

## What to test when unblocked

- Two Begin Play nodes, disjoint chains → two groups, both run on one BEGIN_PLAY.
- Two Begin Play nodes sharing a control node → one group, frames serialized.
- Two Shutdown nodes → both run within the stop grace period.

## Related

- ADR 0044 (link ceiling) — a control outlet takes one link; replaces the retired
  `REPORT_Compiler_accepts_invald_graph.md`.
- ADR 0064 / execution groups plan — replaces `REPORT_Shared_node_concurrent_execution.md`;
  makes shared nodes across flows safe, which is what this change needs.
- Inquisition resolution: "one event node per flow" (one *flow* rooted per event
  node) still holds; this issue only loosens "one event node per *event type* per
  *graph*."
