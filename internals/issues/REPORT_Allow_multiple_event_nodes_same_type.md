# Report: Allow multiple event nodes of the same type per graph

Date: 2026-06-03
Type: design change (loosen a structural rule)

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

- **Determinism / ordering.** If two flows are triggered by one event, do they run
  concurrently (separate scheduler threads — current model) with no ordering
  guarantee? Is that acceptable, or do some events need ordered fan-out? Document
  the contract either way.
- **Shutdown semantics.** Multiple `Shutdown` nodes → multiple graceful-teardown
  flows. The scoped grace period in `Interpreter.stop_execution` already waits on
  *all* flows under `system:shutdown` (it iterates the list), so this is already
  handled — but worth a test.
- **Should this fully replace the fan-out desire, or coexist?** See Issue 2: if
  control fan-out were ever made legal, the need for multiple event nodes shrinks.
  These are alternative answers to the same expressiveness gap — decide which is the
  canonical way to express "N parallel chains from one event."

## Related
- `REPORT_Compiler_accepts_invald_graph.md` — the EXEC-outlet fan-out that assembly
  silently accepts (`edge_wrappers[0]`, drops the rest). Direct counterpart: this
  issue assumes fan-out stays illegal and routes the need through multiple event
  nodes instead.
- `REPORT_Shared_node_concurrent_execution.md` — more event nodes ⇒ more flows ⇒
  more opportunity for node sharing across flows ⇒ raises the priority of the
  per-shared-node frame lock.
- Inquisition resolution: "one event node per flow" (one *flow* rooted per event
  node) still holds; this issue only loosens "one event node per *event type* per
  *graph*."
