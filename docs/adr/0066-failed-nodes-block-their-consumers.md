---
name: failed-nodes-block-their-consumers
description: A node whose worker raises is failed and stays dirty (retried next evaluation); every node reading its data, transitively, is blocked for the pass instead of running on its stale outlet; exec edges never block; one process-wide count keeps the check free while nothing failed
status: accepted
see-also: ADR-0061, ADR-0064
level: framework
---

# Failed nodes block their consumers

**Context.**

- The VM catches a worker's exception, records it, and carries on with the frame. A node downstream of the failed one then ran anyway, reading the failed node's outlet from an earlier run. In a batch that saves images, `img_042.png` silently contained image 41; in a live pipeline a detector counted the previous camera frame twice.
- The node's error badge pointed at the cause, but nothing said which results were wrong.
- Ending the whole frame on an exception would stop loops and batches at the first bad item, and stop independent branches of the same frame.
- The data-flow check runs once per data node per evaluation: it has to cost nothing measurable when nothing fails.

**Decision.**

- **D1** A node whose run raises is **failed**: `BaseNode.failed`, set by the VM, cleared when a later run returns normally. `error_runtime` keeps its meaning (the sticky diagnostic until revalidation).
- **D2** A failed node **stays dirty**: the VM marks all its inlets dirty again, so the next evaluation retries it without an edit.
- **D3** Before a data or control node runs, if a node feeding its **data inlets** is failed or blocked in the same pass, it is **blocked**: not run, its dirty ports kept, recorded as blocked so its own consumers are blocked too. A blocked control node ends its branch as a `None` return does. Exec edges never block.
- **D4** A failed node blocks consumers of **all** its outlets, including outlets it wrote before raising.
- **D5** A blocked node shows a `blocked` warning naming the failed node, removed when it next runs; warnings are synced once at the end of the frame. No ledger entry: the failed node's is the cause.
- **D6** `ExecutionContext.failures` lists the frame's raises and blocks in order, for nodes that iterate (`For Each File`'s `on_error`).
- **D7** A process-wide count of failed-or-blocked nodes gates every check: while it is zero the VM pays one integer test per node. Each node's data sources are worked out at assembly (`LocalizedDataFlow.upstream`), so the slow path walks no edges. Removing a node clears its flags.

**Considered.**

- *Run consumers anyway (the previous behaviour).* Silent wrong results.
- *End the frame on any exception.* Loses the rest of a batch and every independent branch of the frame.
- *Per-port poisoning (only the outlets not written).* A node that raised half way is not trusted for any outlet.
- *Re-dirty only the ports the failed run had resolved.* Recording them cost ~4% on the happy path; re-dirtying all inlets costs nothing until a raise, at the price of extra `on_change` calls on the retry.
- *A per-node-kind or per-wire gate for "accepts failed".* Left for a future Try/Fallback node as a general port capability, never a special case.

**Consequences.**

- A consumer of a failed node skips that frame instead of running on stale data; live flows recover on the next frame by themselves.
- A blocked node with nothing to do (no dirty inlet) is still blocked, so its consumers never read its stale outlet.
- Failing paths pay the bookkeeping: about 0.3 µs per blocked node, against about 1.5 µs to run one.
- Exceptions inside adapters during transport are not covered yet.
