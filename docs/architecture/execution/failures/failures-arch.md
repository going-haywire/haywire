---
status: current
doc_template: system-reference
scope: What the VM does when a node's worker raises — the failed node stays dirty and is retried, its data consumers are blocked instead of running on a stale outlet, the blocked warning, ExecutionContext.failures, and the fast path that keeps this free while nothing has failed
see-also:
  - ../../../adr/0066-failed-nodes-block-their-consumers.md
  - ../../errors/errors-arch.md
  - ../../../adr/0064-flows-that-share-a-node-share-a-runner.md
  - ../../../reference/glossary.md
---

# Failed and blocked nodes — Architecture

When a node's worker raises, the VM records the error and carries on with the frame. What it does with the nodes downstream decides whether the frame's results can be trusted: a consumer that ran anyway would read the failed node's outlet from an earlier run. So a raise makes the node **failed**, and every node that reads its data, directly or through other data nodes, is **blocked**: skipped for that pass, still dirty, with a warning naming the failed node. The why is in [ADR 0066](../../../adr/0066-failed-nodes-block-their-consumers.md).

Code: `packages/haywire-core/src/haywire/core/execution/vm.py`, `.../execution/failures.py`, `packages/haywire-core/src/haywire/core/node/base.py`.

## A failed node

A node is failed from the moment its run raises (in dirty resolution, `on_validate`, the worker, or parsing its result) until a later run returns normally. The flag is `BaseNode.failed`; it lives on the node, so a data node shared by several execution groups is failed for all of them.

- The exception goes through `HaywireVM.catch_exception` as before: it is logged, recorded in the error ledger (deduplicated) and kept as the node's `error_runtime`. `error_runtime` stays until the node is revalidated; `failed` is the live state.
- **A failed node stays dirty.** The VM marks every inlet of the node dirty again, so the next evaluation runs it again without anyone editing anything; a transient failure (an out-of-memory, a dropped camera frame) recovers on its own. On that retry, `on_change` fires for each inlet with its current value.
- A failed node **poisons all its outlets**, including any it wrote before raising: the check is per node, not per port.

## A blocked node

Before a data node runs, the VM looks at the nodes feeding its data inlets. If one is failed, or was blocked earlier in the same pass, the node is blocked instead of run:

- its worker does not run and its dirty ports stay as they are, so it runs once its source recovers;
- it is recorded as blocked in this pass, so its own consumers are blocked too — blocking is transitive along data edges;
- a control node whose data inlets are poisoned is blocked the same way: its worker does not run, and the branch ends as if it had returned `None` (a loop goes on with its next iteration).

Only data inlets count. A control (exec) edge never blocks: a control node after a failed one still runs when its own data is clean. A source outside the control node's localized data flow (a control node's data outlet, a node shared with another flow) counts through its `failed` flag.

A blocked node shows a `blocked` warning, `skipped: <failed node> failed`, on its card, and has no ledger entry: the failed node's entry is the root cause. The warning goes when the node next runs. Warnings are updated once at the end of the frame, so a loop whose body fails every other iteration redraws a card at most once per frame.

## `ExecutionContext.failures`

Each frame's context lists what failed in it, in order: `(node_id, exception)` for each raise and `(node_id, "blocked")` for each block. A node that iterates (such as a loop over files) can compare the list's length before and after an iteration to see whether that iteration failed.

## The fast path

The checks cost nothing measurable while nothing has failed. `failure_counts` (`haywire.core.execution.failures`) counts the nodes that are failed, and those that are failed or blocked (`flagged`). Each node's data sources are worked out once, at assembly (`LocalizedDataFlow.upstream`). The VM tests `failure_counts.flagged` once per node; only when it is nonzero does it read `upstream`, and only then does it clear a node's flags after a normal run. Removing or rebuilding a node clears its flags, so the count cannot stay above zero for a node that is gone.

The benchmark cases `graph_data_chain_ok`, `graph_data_chain_root_fails`, `graph_loop_half_failing` and `node_execute_raises` (`benchmarks/README.md`) measure the happy path and the cost of failing and blocking.
