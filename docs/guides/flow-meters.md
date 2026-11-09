---
status: draft
doc_template: guide
scope: Flow meters — what the bars on a running graph's haystack row show, how they are measured and graded, and how to turn them off
see-also:
  - ../architecture/execution/flow/flow-arch.md
  - ../adr/0064-flows-that-share-a-node-share-a-runner.md
  - ../adr/0010-event-source-queue-mode.md
  - ../reference/glossary.md
---

# Flow meters

## 1. What the user sees

A running graph's row in the **HaystackEditor** shows a **flow meter** where the overflow menu is for a stopped graph: one thin bar for the worst **Flow**. The bar fills with the Flow's load and is green, amber or red.

Clicking the bar opens a strip of one bar per Flow on the same line, left of the bar. The strip is ordered worst first, nearest the end of the row, with a gap between **execution groups** (Flows in a group share one runner thread and can stall each other). The name keeps all its text: bars that do not fit are cut off, least severe first, and widening the action slot shows them. Hover a bar for the Flow's name, load, frames per second, queue and drops. A stopped graph shows nothing.

The **Show flow meters** setting turns the meters off. It is in the library settings of the properties editor (the **Barns** surface), in the **Haystack** panel under **Flow meters**, and applies the next time a graph is started or stopped.

## 2. What is measured

All figures come from the counters each **FlowQueue** keeps, read twice and compared:

| Figure | Meaning |
|---|---|
| **Flow load** | Share of the sampling window in which the Flow's frames ran. A frame still running at the end of the window counts the window as fully busy. |
| Runner load | The sum of the loads of the Flows in the same execution group. |
| Queue fill | Queue depth over its maximum size. |
| **Dropped Triggers** | Triggers a queue discarded without running them: replaced in DROP mode, refused because the queue was full inside the group, or timed out waiting in BLOCK mode. |
| **Drop rate** | Dropped share of the Triggers that arrived in the window. |

## 3. How a Flow is graded

A Flow is amber from 70% and red from 90% of the larger of its own load and its runner load. A BLOCK-mode Flow is also graded by queue fill (amber from 50%, red from 80%) and is red for 5 seconds after any drop. A DROP-mode Flow drops by design, so a single drop means nothing: it turns amber only when more than 10% of its Triggers are dropped, and its queue fill is not graded, because a one-slot queue is full whenever a Trigger waits. The limits are the defaults of `Thresholds` in `haywire.core.execution.flow_metrics`.

## 4. Cost

Sampling runs on the server, 2 Hz per editor, while at least one graph is running. One snapshot of a Flow costs about a microsecond. A bar is sent to the browser only when its colour or fill step changes, the open strip is redrawn only when something in it changes, and a tooltip is filled when it opens. A steady, healthy graph sends nothing.

## 5. Reading the counters from code

`Interpreter.flow_metrics()` returns a `FlowSnapshot` per assembled Flow. A `FlowMeterSampler` turns successive snapshots into a `MeterReading`:

```python
sampler = FlowMeterSampler()
sampler.update(interpreter.flow_metrics())          # primes the sampler
reading = sampler.update(interpreter.flow_metrics())
for group in reading.groups:                        # worst group first
    for flow in group.flows:                        # worst flow first
        print(flow.entry_node_id, flow.severity, f"{flow.load:.0%}", flow.dropped_total)
```
