---
name: a-worker-exception-bails-by-run-policy
description: A worker exception is reported, the node retried at its next evaluation, and the run bails — ends the branch, the frame or the run — by the graph's on_exception_bail policy; nothing after the exception runs on the failed node's stale outlets
status: accepted
see-also: ADR-0061, ADR-0064
level: framework
---

# A worker exception bails by run policy

**Context.**

- The VM caught a worker's exception, recorded it, and carried on with the frame. A control node downstream then ran on the failed node's outlet from an earlier run: in a batch that saves images, `img_042.png` silently contained image 41; in a live pipeline a detector counted the previous camera frame twice.
- The failed data node was not retried: its dirty inputs had been consumed before the worker raised, so with unchanged inputs it never ran again and its stale outlet stayed.
- The error badge stayed until revalidation, so it did not show whether the node was still failing.
- Once something has raised, efficiency stops mattering; visibility and reproducibility do.

**Decision.**

- **D1** On a worker exception the VM reports it as before (log, ledger, `error_runtime`), marks the node's data inlets dirty so its next evaluation retries it, and records `(node, exception)` in `ExecutionContext.failures`.
- **D2** The run then **bails** by the graph's run policy `GraphRunSettings.on_exception_bail`: `branch` (default) ends the current branch — a loop goes on with its next iteration, otherwise the frame ends; `frame` ends the frame; `run` ends the frame and stops the run.
- **D3** A data node that raises stops its control node's data flow; the control node does not run.
- **D4** The policy reaches the VM through the `Interpreter` as callables: `exception_bail` (read at each exception, so a change applies at once) and `on_bail_run`, which the graph entry implements by scheduling a stop through `graph._validation.call_soon` (the autorestart route, ADR 0064 D9); it stops through its haystack and broadcasts `GraphDataMutated` so the UI shows the run stopped.
- **D5** A worker error on a card is cleared when the next frame of the flow that raised it starts, and set again if the node raises again; a stopped run keeps its errors, and starting a new run clears them. The ledger keeps every occurrence.

**Considered.**

- *Run anyway (the previous behaviour).* Downstream nodes act on stale values, silently.
- *Mark failed nodes and block every node depending on them, across flows.* Precise, but it needed failed and blocked flags, per-flow source lists, a process-wide count to keep the check free, and per-node warnings; its machinery held three bugs at review. Ending the branch or frame gives the same guarantee — nothing acts on a stale value — with one test per node.
- *Always end the frame.* Kills a batch (a loop over files) at its first bad item; `branch` lets the loop go on, `frame` and `run` remain available.

**Consequences.**

- Nothing after an exception acts on the failed node's outlets; independent work later in the same frame waits for the next frame (`frame`, `run`) or is skipped only on that branch (`branch`).
- A failing node retries every evaluation and redraws its card each frame it fails.
- Exceptions raised by adapters during transport are not covered yet.
