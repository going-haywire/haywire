# Graph-nodes: encapsulation for Haywire graphs

## Context

Haywire has no way to encapsulate part of a graph. Large graphs stay flat, and a
useful cluster of nodes cannot be named, hidden, or reused. Every comparable
node system solves this, and the whitepaper
([docs/archive/whitepaper/Haywire_design.md:178-190](docs/archive/whitepaper/Haywire_design.md))
sketched it years ago under "Graph-node / Subgraph / Abstraction / Module" — but
nothing was ever built. There is no subgraph code in the repo today.

This plan is the outcome of a design interview (26 decisions). It delivers
**Slice 1 only**: a selection can be collapsed into a **Group** — a Graph-node
whose Subgraph lives in the parent `.haywire` file. Reusable **Macros** are a
follow-on slice, deliberately deferred — but two Slice-1 choices (the keyed
definition table, root-unique instance ids) exist solely to keep that slice a
*move* rather than a rewrite.

Intended outcome: a user selects a connected set of nodes, collapses it into one
card with inlets and outlets, steps inside to edit it, steps back out, and the
graph runs exactly as it did before.

---

## Status and sequence — 2026-09-15

**Slice 1 is built.** Branch `feat/graph-nodes-slice1`, eight commits. Gate: 5338
passed (`-m "not browser and not perf"`), 119 browser tests, ruff + format clean.

A selection collapses into a Group, runs identically to the graph it replaced,
can be entered, edited, left and expanded, and round-trips through save and
load. Nesting works to any depth. The mechanism is
[ADR 0036](docs/adr/0036-groups-execute-through-their-boundary-nodes.md).

### The sequence

Pending plans are numbered by their place in it; `landed/` holds the Slice-1
step plans, numbered in the order they were built.


**1. Instant switching** —
[2026-09-15-instant-subgraph-switching.md](01-instant-subgraph-switching.md)

Keep every visited level mounted so entering and leaving a Group costs a
`set_value`. First, because it changes *how* a Subgraph is opened: a Group gets
its own editor tab rather than re-keying one. Slice 2's Macro opens as its own
document and needs exactly that primitive, so building Macro tabs first would
mean two navigation models and then a conversion.

**2. Give `reconcile_interface()` a caller**

Editing a boundary port through the Ports panel must reach the card; today only
an explicit call does. A validation subscription is not the hook —
`mark_as_structuraly_dirty` short-circuits on a node already flagged dirty, so a
second `rejig` produces no batch.

Second, because Slice 2's *"saving a Macro rebuilds every instantiation"* is this
reconciliation fanned out across placements. Building Macros on a reconciliation
path that never fires would hide the failure behind a feature.

**3. Slice 2 — Macro**

Three things to settle before writing code; see that section.

**4. Slice 3 — Function**

Design against *"What the current system already gives this slice"*, and settle
the loopback question under called execution.

### Independent

Neither blocks nor is blocked; pick up whenever:

- An error inside a closed Group needs a badge on the card, and clicking it
  should descend to the failing node.
- Double-click on a Graph-node should enter it.

---

## Vocabulary

Settled, and used throughout.

| Term | Meaning |
|---|---|
| **Graph-node** | The card on the parent canvas. A Node whose behaviour is a whole Subgraph. The umbrella term for all three variants below. |
| **Subgraph** | The contents of a Graph-node — its nodes and edges. |
| **Subgraph Input / Subgraph Output** | The two **boundary nodes** that define the interface. The Input node has only *outlets*; the Output node has only *inlets*. They are named for the side they represent on the Graph-node card. |

The three variants are named for their **execution mechanism**, following Unreal
Blueprint, which draws the same line: *Collapsed Graph* / *Macro* / *Function*.
The name says what happens, so you know which you placed without opening a config.

| Variant | Storage | Reuse | Execution | Slice |
|---|---|---|---|---|
| **Group** | parent `.haywire` file | one Graph-node | **inlined** at assembly | 1 |
| **Macro** | own file, a library component | any graph | **inlined** at assembly | 2 |
| **Function** | own file, a library component | any graph | **called** — its own flow, per invocation | 3 |

**All three hold a Subgraph.** "Subgraph" names the *contents* and nothing else —
which is why the boundary nodes are `Subgraph Input`/`Subgraph Output`, the
definition object is `SubgraphDefinition`, and the settings tier reads
`framework < subgraph < node`, whichever variant wraps it.

"Module" is deliberately **not** used: `module_name`, `add_managed_module` and
`_managed_modules` already mean dotted **Python** module paths in the hot-reload
dependency graph ([dependency_graph.py:61-83](packages/haywire-core/src/haywire/core/registry/dependency_graph.py#L61-L83)),
and a `modules/` component folder would sit inside a Python module directory next
to `nodes/` and `types/`. The glossary already carries a section explaining that
"library" means five things; this declines to start a second one.

**"Group" is reclaimed, not overloaded.** [ADR 0035](docs/adr/0035-fold-replaces-group-and-section.md)
retired the author-facing `group()` and the `GROUP` port type — both are gone from
the code. What survived is internal: `parent_group` and `is_group` on `DataPort`
([port.py:134,140](packages/haywire-core/src/haywire/core/types/port.py#L134)),
26 uses meaning *fold membership*, and **serialized into every `.haywire` file**.
Slice 1 finishes that rename (decision 25). Known mis-cue: Blender's "Node Group"
is reusable, so Blender users will expect a **Macro** — mitigated by
"Promote to Macro…" sitting one action away.

---

## Decisions

| # | Decision |
|---|---|
| 1 | Encapsulation only. Visual frames/backdrops are a separate, unbuilt feature; **frame** / **backdrop** are the words reserved for it. |
| 2 | Graph-node (card) / Subgraph (contents). |
| 3 | Two storage variants — in the parent file, or in its own file. **Abstraction dropped** (many Graph-nodes sharing one *in-file* definition). Definitions live in a *keyed table*, referenced by the Graph-node, so Abstraction stays reachable. |
| 4 | `NodeType`'s docstring drifted; correct it. Outlet *count* does not distinguish CONTROL from LOOPBACK — the `is_loopback_outlet` flag does. |
| 5 | A Subgraph holds DATA + CONTROL nodes in any combination. **Execution is by inlining** into the host graph at assembly; a Macro is an instanced Subgraph. |
| 6 | No EVENT and no OUTPUT nodes inside a Subgraph. A Graph-node is a function of its inlets. |
| 7 | The interface nodes are **Subgraph Input / Subgraph Output**; collectively **boundary nodes**. |
| 8 | Two hidden builtin classes under a new standalone `NodeType.BOUNDARY`, built on the `RerouteNode` pattern. |
| 9 | Each Graph-node owns its **own live instantiation** of the definition — one node set serving both editing and execution. |
| 10 | Descend in place to look; edit a Macro by opening it as its own document (Slice 2). |
| 11 | The boundary nodes' ports **are** the interface. The Graph-node mirrors their shape and owns the port *values*. |
| 12 | Collapse dedups by endpoint: inlets group by outer source, outlets by inner source. Pins named from the inner side. |
| 13 | Selections must be **convex** — refuse a collapse that would let control re-enter the Graph-node, and offer to extend the selection. |
| 14 | Macros become a **new component kind** (`"macro"`), joining the eleven in `kind_registry_map()`. **Slice 2.** |
| 15 | Inner nodes get **root-unique ids at instantiation**; assembly is handed a flat lookup view. Builders and VM unchanged. |
| 16 | A Subgraph owns its own settings tier: `framework < subgraph < node`. Host inheritance is an additive change later. |
| 17 | **No recursion** for Groups or Macros — static composition is the price of inlining. Functions (Slice 3) are the only route to recursion. |
| 18 | Slice 1 = Group. Slice 2 = Macro. Slice 3 = Function. |
| 19 | Boundary nodes are **not** split by FlowType. One mixed pair serves both execution mechanisms. |
| 20 | Lifecycle-hook passes **walk flows**, not a flattened node list, so every node sees its own graph's Variables. (Slice 3.) |
| 21 | Inlining is the default and the common path. Calling is confined to Functions, which exist for what inlining cannot do. |
| 22 | The three variants are named for their mechanism: **Group / Macro / Function**. "Module" is not used. |
| 23 | Execution mechanism is chosen by the **author**, once, and carried by the kind — not by a per-placement config. Changing it is an explicit **"Convert to Function…"** action on the definition. |
| 24 | **Subgraph** means the contents, and only the contents. Group, Macro and Function each hold one. |
| 25 | Variant 1 is **Group**, reclaiming the word ADR 0035 retired — and Slice 1 completes that ADR by renaming `parent_group`/`is_group` to `parent_fold`/`is_fold`, riding the format bump Slice 1 needs anyway. |
| 26 | Boundary nodes cannot be deleted or copied. Enforced by filtering them out in the delete and copy paths — **not** by a new framework-level `deletable` flag, which would have exactly one user. |

---

## How a Group executes

A Group is crossed, never bypassed: the card and both boundary nodes run as
ordinary nodes in the host's flow, and the boundary nodes carry the values
across. Crossings are strings in `outlet_map` and `ExecutionContext.control_pin`,
supplied through `BaseGraph.control_transitions()`. The VM, the scheduler,
`execution/flow.py` and the pipe layer are untouched.

Read [ADR 0036](docs/adr/0036-groups-execute-through-their-boundary-nodes.md)
before changing any of it, and
`.insights/project_assembly_decides_when_pipes_decide_where.md` before assuming
a view over assembly can move a value.

---

## Slice 1 — Group (the build)

Split into five steps, each independently testable. Later steps depend on earlier
ones only where stated.

| Step | Scope | Plan |
|---|---|---|
| 1 | `NodeType.BOUNDARY`, the two boundary node classes, registry slots, validator rules, skins | [step1](landed/01-node-types-and-boundary-nodes.md) |
| 2 | `SubgraphDefinition`, instantiation, the `subgraphs` table, format bump + the ADR 0035 fold rename | [step2](landed/02-subgraph-model-and-format.md) |
| 3 | `FlatGraphView` and the assembly seam — the whole execution change | [step3](landed/03-assembly-seam.md) |
| 4 | Collapse / expand actions, dedup, the convexity check, delete/copy filtering | [step4](landed/04-collapse-expand-actions.md) |
| 5 | `SubgraphContainer`, descend/ascend, toolbar verbs, Ports-panel interface editing, docs | [step5](landed/05-navigation-and-docs.md) |

Step 3 is the load-bearing one: if `FlatGraphView` is right, the VM, the
scheduler, lazy masks and callbacks need no change at all.

---

## Slice 2 — Macro (outline, not in scope)

`"macro"` joins `kind_registry_map()`
([kinds.py:22-49](packages/haywire-core/src/haywire/core/library/kinds.py#L22-L49))
as a twelfth component kind: folder `macros/`, key `lib:macro:Name`, doc area
`docs/components/macros/`. The registry holds `.haywire` **documents**, so it is
a sibling of `BaseRegistry` rather than a subclass (which is class-based
throughout — `_class_filter`, import-based scan, module-reload).

Default save target is the project's own scaffolded library at
`barn/<lib>/<module>/`, which `haywire init` already creates
([init.py:176-188](packages/haywire-studio/src/haywire_studio/init.py#L176-L188)).
"Edit Macro…" opens the file as its own graph document — its own tab, dirty dot,
Save and undo stack — and saving rebuilds every instantiation. Add-node menu
integration extends `NodeFactory.get_menu_structure()`
([node_menu_builder.py:157](barn/haybale-graph-editor/haybale_graph_editor/panels/node_menu_builder.py#L157)).
Cross-file cycle detection enforces decision 17.

### Three things to settle first

1. **Give each Graph-node its own instantiation.** A `SubgraphDefinition` is
   currently both the template and the single live graph, 1:1 with its card. A
   Macro is placed in any graph, possibly twice in one graph, so each placement
   needs its own live node set: `instantiate()` becomes the normal path, and
   `SubgraphDefinition.graph_node_wrapper()` needs a per-card answer rather than
   one memo. The keyed table means the file format is already right.
2. **Give a Macro a container that owns its file.** `SubgraphContainer` defers
   `path`, `unsaved` and `save()` to the graph holding it, which is what a Group
   wants. A Macro owns its own file, dirty dot and Save, so it needs a sibling
   container.
3. **Wire `reconcile_interface()` to the editing path.** "Saving a Macro rebuilds
   every instantiation" is that reconciliation, fanned out. See the Status
   section for the hook that does not work.

Steps 1 and 2 of the sequence come first — see *Status and sequence*.

---

## Slice 3 — Function (designed for, not built)

A **Function** is a thirteenth component kind — `lib:function:Name`, folder
`functions/`, doc area `docs/components/functions/` — a sibling of Macro sharing
its document shape and registry machinery, differing only in that its Graph-node
stays **opaque** and runs its interior through a re-entrant call into the same VM.
Mechanism is carried by the kind, so the slice boundary falls on a kind boundary
rather than cutting through one (decision 23); moving a definition between kinds is
an explicit **"Convert to Function…"** action that runs the validity check and
warns about pin changes once.

Recorded here because the *reason* Slices 1–2 need no accommodation is non-obvious
and would otherwise be re-derived from scratch.

### What the current system already gives this slice

Design against these facts rather than the text below, which predates Slice 1.

- **The boundary workers already carry values.** `SubgraphInput` copies the
  card's data inlets onto its own outlets; `SubgraphOutput` copies its inlets
  onto the card's outlets; each write fires that port's pipes. The Function work
  is to swap "continue in the same flow" for "call a nested flow", not to give
  these workers a role.
- **Lifecycle hooks already reach interior nodes.** They sit in
  `control_graph.control_nodes` and in the localized data flows, so
  `Flow.get_all_nodes()` finds them and all four hooks fire. Only a nested flow
  needs the flow-walk in change 5.
- **The boundary workers hold no cache.** Port objects resolve per call, so
  `RerouteNode`'s silent `on_startup` failure mode does not apply to them.
- **An unknown outlet id ends its branch.** `_navigate_next` handles a worker
  returning a string that names no port, so a card's entry hop can return a
  virtual crossing id while the card is `LOOPBACK`.
- **A loopback may cross a boundary under inlining** — one control graph, one
  loopback stack, so push and pop land in the same list either side. Under
  called execution the stack is a local per call, so a loop body crossing out of
  a nested flow pushes onto one stack and pops from another. **Design for that
  before a Function may be a loopback node.**

### The boundary nodes' runtime roles

Nesting is where the whitepaper's typing becomes true: **Subgraph Input is the
nested flow's entry node, Subgraph Output terminates it.** Both designs are served
by one pair of classes because `NodeType.BOUNDARY` carries neither the DATA nor
the CONTROL bit — the *role* comes from the assembly context, not the type. Under inlining the
typing is inert while the nodes still run, copying values across the boundary.

Both use the ordinary control-node contract, which already carries everything
needed: the VM sets `exec_ctx.control_pin` to the inlet the node was entered
through ([vm.py:192](packages/haywire-core/src/haywire/core/execution/vm.py#L192)),
and the worker's return value names the outlet to leave by
([vm.py:249-277](packages/haywire-core/src/haywire/core/execution/vm.py#L249-L277)).

1. Host hydrates the Graph-node's data inlets, calls its worker.
2. Worker copies inlet values onto the Subgraph Input's data outlets, enters the nested flow.
3. Subgraph Input returns the control outlet matching how the host entered → VM walks inward.
4. Interior runs.
5. Subgraph Output copies its data inlets onto the Graph-node's data outlets, ends the nested flow.
6. Graph-node's worker returns the host outlet matching the Subgraph Output inlet reached.

### Five changes, all additive

1. **Extract `_run_control_loop(flow, exec_ctx, entry_inlet, depth)`** from
   `execute_control_flow`, with two wrappers over it. `execute_control_flow`
   (one caller, [scheduler.py:233](packages/haywire-core/src/haywire/core/execution/scheduler.py#L233))
   keeps its signature and fires frame hooks; `execute_nested_flow` skips them
   and returns `(exit_inlet_id, exec_count)`.

   Frame hooks are the reason this is a second entry point rather than a flag:
   `execute_control_flow` fires `on_frame_start`/`on_frame_end` across the whole
   flow ([vm.py:172-177,218-223](packages/haywire-core/src/haywire/core/execution/vm.py#L172-L177)),
   and a nested flow invoked many times inside one host frame must not re-fire them.

   The exit inlet travels as a **return value, not node state**: the VM is shared
   across threads and `_backpropagate` can pull one data node into two flows'
   localized data flows, so a Graph-node instance can execute concurrently.

2. **`_navigate_next` must terminate on the Subgraph Output** the way it does on
   `NodeType.OUTPUT` ([vm.py:314-322](packages/haywire-core/src/haywire/core/execution/vm.py#L314-L322)).
   Without it, a Subgraph Output reached inside an interior loop pops the loopback
   stack instead of returning — early exit from a Function silently doesn't work.

3. **A nesting-depth counter** threaded through `execute_nested_flow`.
   `max_stack_depth` guards the *loopback* stack, a local per call, so it cannot
   see nesting depth. This is decision 17's guard, and what makes recursion safe
   for Functions.

4. **A nested flow entry path in the assembler.** `Flow` requires an
   `event_subscription` ([flow.py:100-119](packages/haywire-core/src/haywire/core/execution/flow.py#L100-L119))
   and flows are rooted by `_identify_event_nodes`
   ([flow_assembly_manager.py:97](packages/haywire-core/src/haywire/core/assembly/flow_assembly_manager.py#L97));
   a nested flow is rooted at a boundary node with no event. This is the only
   place nesting touches the assembler rather than the VM alone.

5. **Lifecycle hooks must reach interior nodes.** Four hooks —
   `on_startup`/`on_shutdown` ([vm.py:99-136](packages/haywire-core/src/haywire/core/execution/vm.py#L99-L136),
   called once per scheduler thread at
   [scheduler.py:176,205](packages/haywire-core/src/haywire/core/execution/scheduler.py#L176))
   and `on_frame_start`/`on_frame_end` ([vm.py:172-177,218-223](packages/haywire-core/src/haywire/core/execution/vm.py#L172-L177))
   — all filter `Flow.get_all_nodes()`
   ([flow.py:158-183](packages/haywire-core/src/haywire/core/execution/flow.py#L158-L183))
   and memoize into five per-Flow caches.

   `Flow` gains a **`nested_flows`** list, and the four hook sites **walk flows**
   rather than a flattened node list — so each interior node is invoked with its
   own flow's context and therefore its own graph's Variables. One rule, no
   exception: a node always sees its own graph's Variables. Frame hooks still
   fire **once per host frame**, not once per nested invocation, which is the
   correct reading of "a new frame began" for a Function that runs ten times in one.

Free, with no work: `_create_execution_context` builds `local_ctx` from
`flow.graph_ref.variables` ([vm.py:76-80](packages/haywire-core/src/haywire/core/execution/vm.py#L76-L80)),
so a nested flow gets the **Subgraph's own Variables**, isolated per level —
consistent with decision 16.

### Two traps in change 5

**Missing `on_startup`/`on_shutdown` fails silently and permanently.** They run
once per scheduler thread, so there is no next frame to correct a miss.
`RerouteNode` resolves its port objects in `on_startup` and notes the cache is
re-resolved each run start ([reroute.py:89-97](packages/haywire-core/src/haywire/barn/builtin/nodes/reroute.py#L89-L97));
an interior reroute that never receives it has `cache.outlet = None` and forwards
nothing, with no error. A missed `on_shutdown` leaks whatever the node acquired —
a Function wrapping a capture pipeline holds the device open after the graph stops,
and the next run fails to acquire it. That presents as "the app is broken", which
is the worst possible attribution.

**Cache invalidation runs upward.** The five caches live on the *host* Flow but
would depend on nested Flow contents. Editing a Function's Subgraph must
invalidate the host Flow's caches. Free under inline execution (the host flow is
rebuilt); not free under nesting, where only the interior changed.

### Two call shapes, not two node classes

| Boundary crossing | Call entry | Status |
|---|---|---|
| control | `_run_control_loop` | loop exists; entry point is new |
| data only | `vm._evaluate_data_flow(nested_ldf, nested_ctx)` | **exists unchanged** ([vm.py:348-371](packages/haywire-core/src/haywire/core/execution/vm.py#L348-L371)) |

A data-only Function's Graph-node is a DATA node executed via
`data_node._execute(exec_ctx)` ([vm.py:363](packages/haywire-core/src/haywire/core/execution/vm.py#L363));
its worker reaches the VM the same way. The assembler builds one nested
`LocalizedDataFlow` per Subgraph, rooted at the Subgraph Output's data inlets.

### A Function can be a loopback node

The Graph-node is typed LOOPBACK; the **loop body lives in the host graph** and the
control logic inside the Function. Host enters → nested run exits via the Subgraph
Output's `body` inlet → Graph-node returns the `body` outlet → `needs_loopback`
pushes the Graph-node and the host walks its own body
([vm.py:199-208](packages/haywire-core/src/haywire/core/execution/vm.py#L199-L208))
→ body ends → host pops and **re-enters the Graph-node with `control_pin = None`**
([vm.py:339-341](packages/haywire-core/src/haywire/core/execution/vm.py#L339-L341))
→ nested run again, until the interior routes to `done`.

Needs nothing beyond the above. Interior loop state survives across invocations
because decision 9 gives each Graph-node its own node instances. One consequence:
the **Subgraph Input carries one control outlet per host control inlet plus one for
"re-entered via loopback"**, because `control_pin is None` is how every loopback
node already tells re-entry from fresh entry.

This is also why boundary nodes are **not** split into DATA and CONTROL classes:
the Subgraph Input's outlet set answers *"how was I entered"*, which spans control
inlets and loopback re-entry, and does not decompose along FlowType.

---

## Out of scope

- **Abstraction** (many Graph-nodes sharing one in-file definition). The keyed
  table keeps it reachable.
- **Recursion.** Incompatible with inlining — reachable only through Slice 3's
  Functions, guarded by a nesting-depth counter.
- **Functions / called execution.** Designed for above; not built.
- **Visual frames / backdrops.** A separate feature, under the words *frame* and
  *backdrop* — "group" now means a Graph-node variant.
- **EVENT or OUTPUT nodes inside a Subgraph.** Would need per-instance event
  identity namespacing.
- **Host → Subgraph settings inheritance.** Additive later (decision 16).
- **Promoting an inner node's settings onto the Graph-node card.**
- **Farmhand/MCP tools, marketplace publishing, Macro versioning.** Slice 2+.

---

## Acceptance

Per-step verification lives in each step plan. Slice 1 is done when all of the
following hold — the list is the acceptance criteria, not a substitute for the
step plans' own tests.

**Unit** — new tests under `tests/core/`:
- Flat view: a graph with one Graph-node assembles to the *same* `Flow` shape as
  the equivalent hand-inlined graph (control DAG, localized data flows,
  topology order).
- Collapse → expand round-trips to an equivalent graph.
- Dedup: one outer outlet feeding three selected nodes yields **one** inlet.
- Convexity: `A → B → C` selecting `{A, C}` is refused and names `B`.
- Containment: an EVENT or OUTPUT node inside fails validation.
- Serialization: a graph containing a Group round-trips through
  `to_dict`/`load_from_dict`; a pre-feature file still loads.
- Settings: an inner node's `graph()` mirror resolves from its own Subgraph, not
  the host graph.
- Boundary port removal drops exactly the edges that lost a port.
- Selecting every node inside a Subgraph and deleting leaves both boundary nodes
  standing; copying a selection that includes them yields a payload without them.
- Fold rename (decision 25): a `.haywire` file written before the bump, carrying
  `parent_group`/`is_group`, loads with its folds intact — `graphs/any_and_nonde.haywire`
  is a real fixture for this.

**Gate** (per [CLAUDE.md](CLAUDE.md)):
```sh
uv run ruff check .
uv run ruff format --check .
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/*/ tests/
uv run pytest -m "not browser and not perf" -q > /tmp/t.log 2>&1; echo "exit=$?"
```
Establish the mypy/ruff baseline on the touched paths **before** editing — this
is a multi-file, type-system-touching change.

**Manual** — `uv run haywire`: build a chain with a Switch and a ForLoop, select
a convex middle section, collapse it, confirm the card's pins match the crossing
edges, run the graph and confirm identical behaviour, descend and edit inside,
ascend, expand, and confirm the graph is back to where it started.

**Watch for**: `tests/studio/test_docs/test_generate.py` runs
`git checkout -- barn/haybale-testing` in teardown and silently discards
uncommitted work there ([.insights](.insights/)). Commit before running the
full suite.
