---
status: current
doc_template: system-reference
scope: What the VM does when a node's worker raises — the report, the retry, ExecutionContext.failures, and how far the frame bails under the graph's on_exception_bail run policy
see-also:
  - ../../../adr/0066-a-worker-exception-bails-by-run-policy.md
  - ../../errors/errors-arch.md
  - ../../graph/graph-arch.md
  - ../../../reference/glossary.md
---

# Worker exceptions — Architecture

When a node's worker raises, nothing after it may act on what it left behind: its outlets still hold an earlier run's values. So the VM reports the exception, makes the node retry at its next evaluation, and **bails**: it stops running the current branch, frame or run, as the graph's run policy says. Once something has raised, the VM spends nothing on efficiency; what matters is that the error is visible and the run reproducible. The why is in [ADR 0066](../../../adr/0066-a-worker-exception-bails-by-run-policy.md).

Code: `packages/haywire-core/src/haywire/core/execution/vm.py` (`_fail`, `execute_control_flow`), `barn/haybale-haystack/haybale_haystack/settings/graph_run_settings.py`.

## What happens on an exception

A worker exception (raised by dirty resolution, `on_validate`, the worker, or parsing its result) is caught by the VM, which:

1. **reports it** through `HaywireVM.catch_exception`: it is logged, recorded in the error ledger (deduplicated) and set as the node's `error_runtime`, so the card shows its error badge;
2. **marks the node's data inlets dirty again**, so its next evaluation retries it without anyone editing anything — a transient failure (an out-of-memory, a dropped camera frame) recovers on its own;
3. **records it** in the frame's `ExecutionContext.failures` as `(node, exception)`;
4. **bails**, as far as the policy says.

A data node that raises stops its control node's data flow: the control node does not run. A control node that raises bails the same way.

## The bail policy

`GraphRunSettings.on_exception_bail` (in the graph's run settings, persisted with the haystack) says how far a run gives up:

| value | effect |
| --- | --- |
| `branch` (default) | The current branch ends. Inside a loop, the loop goes on with its next iteration; otherwise the frame ends. |
| `frame` | The current frame ends. The next frame (a tick, a trigger) runs as usual. |
| `run` | The current frame ends and the graph's run stops. |

The policy reaches the VM through the `Interpreter` as a callable, read at each exception, so changing it applies to a running graph at once. `run` asks the graph's entry to stop through `graph._validation.call_soon`, never on the runner thread, since stopping waits for the runners; the entry stops through its haystack and broadcasts `GraphDataMutated`, so every session's haystack shows the run as stopped.

## Badge and ledger

The error badge shows while the node keeps failing: a worker error is cleared from the card when the next frame of the flow that raised it starts, and set again if the node raises again. A stopped run keeps its errors on the cards; starting a new run clears them. The error ledger keeps every occurrence (deduplicated with a count).

## `ExecutionContext.failures`

Each frame's context lists its worker exceptions in order, each with the node that raised it. A node that iterates (such as a loop over files) can compare the list's length before and after an iteration to see whether that iteration failed.

## Cost

The happy path pays one boolean test per data node and one attribute test per control node. The benchmark cases `graph_data_chain_ok`, `graph_data_chain_root_fails`, `graph_loop_half_failing` and `node_execute_raises` (`benchmarks/README.md`) measure the happy path and the exception path.
