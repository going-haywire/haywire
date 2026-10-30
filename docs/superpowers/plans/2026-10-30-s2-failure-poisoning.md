# S2 — Failure poisoning and failed-stays-dirty — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline, the user's current choice) or superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A node whose worker raises no longer leaves a stale outlet that consumers silently run on. The
node is marked **failed** and stays dirty (retried next evaluation); every data node downstream of it, through
data edges, is **blocked** (skipped, still dirty) for that pass; a control node whose data inlets are poisoned
does not run its worker. The happy path stays ~free.

**Architecture:** One `failed` flag per node (`BaseNode`), separate from the sticky `error_runtime`. A
process-wide count of failed nodes makes the per-node check a single integer test while nothing has failed.
`_execute` re-inserts the dirty ports it popped when the worker raises. Assembly precomputes each node's
upstream data sources on `LocalizedDataFlow`, so the slow path never walks ports or edges. The VM skips poisoned
nodes, keeps a pass-local blocked set, records `ExecutionContext.failures`, and shows a `blocked` warning.

**Spec:** [2026-10-30-spandrel-haybale-design.md](2026-10-30-spandrel-haybale-design.md) §2.3 (Q9, Q10, Q37).
**ADR required:** 0066 (next free).

## Decisions settled while planning S2 (2026-10-30)

| # | decision |
|---|---|
| S2-Q1 | The happy-path fast path is a **process-wide failed-node count** (`BaseNode._failed_count`, class attribute). It changes only when a node's `failed` flag flips, under one lock; readers test it without a lock. One count serves every flow and execution group, because a shared data node's flag is seen by all of them (ADR 0064). |
| S2-Q2 | "Poisoned" = a data-inlet source node is **failed**, or is **blocked in this pass**. Sources come from data edges only; control (exec) edges never poison. A source outside the current localized flow (e.g. a control node's data outlet, a shared node) counts through its `failed` flag. |
| S2-Q3 | Precomputed at Assembly: `LocalizedDataFlow.upstream: dict[node_id, tuple[BaseNode, ...]]` for every node in the sequence **and** for the control node, built in `DataFlowBuilder.build_localized`. |
| S2-Q4 | `failed` is set by the VM's catch path (data and control nodes); cleared inside `_execute` when the worker returns normally. `error_runtime` keeps its current sticky behaviour. |
| S2-Q5 | Blocked surface: `NodeWarning(message="skipped: <upstream label> failed", source_version=None, kind="blocked")`, added once (no duplicate, no redraw flood), removed when the node next runs its worker. No ledger entry. |
| S2-Q6 | `ExecutionContext.failures: list[tuple[str, BaseException \| Literal["blocked"]]]`, append-only per frame. Its consumer (`For Each File`, `on_error=continue\|stop`) is S4; S2 tests the bookkeeping only. |
| S2-Q7 | A failed node poisons **all** its outlets (partial writes included) — the check is per node, not per port. |
| S2-Q8 | New frozen benchmark nodes live in `barn/haybale-testing/haybale_testing/nodes/benchmark/` and are committed **before** any full-suite run (the docs test reverts uncommitted edits there). |

**Amendment S2-Q9 (2026-10-30, after the final review, user decision "b"):** blocking moves from every
data node to the **control node only**. A raising node is still failed and stays dirty (retried). Data
nodes are never blocked and never skipped. A control node is skipped (blocked, warning, `failures` entry, its
branch ends) when any node of its localized data flow, or any external source feeding that flow, is failed
or blocked after the flow has been evaluated. `LocalizedDataFlow.upstream` (per node) becomes
`LocalizedDataFlow.sources` (one tuple per flow: the sequence plus external data sources). Supersedes S2-Q2,
S2-Q3 and S2-Q5 where they speak of data nodes. Why: per-data-node blocking bought only skipped work on a
failing pass and cross-flow staleness, which the persisted flags cover; its machinery held all three review
bugs.

**Amendment S2-Q10 (2026-10-30, user decision; supersedes S2-Q1..Q9 except the benchmark cases):**
no poisoning machinery. Once a node has raised, efficiency no longer matters, only visibility and
reproducibility. On a worker exception the VM (1) reports it as before (ledger, `error_runtime`), (2) marks
the node's data inlets dirty so the next evaluation retries it, (3) records it in
`ExecutionContext.failures`, and (4) **bails** by the graph's run policy
`GraphRunSettings.on_exception_bail`: `run` (stop the run), `frame` (end the frame), `branch` (end the current
branch: back to the enclosing loop, else the frame ends — default). `error_runtime` set by a worker failure is
cleared at the start of the flow's next frame. The policy reaches the VM as callables through the
`Interpreter` (`exception_bail`, `on_bail_run`); `bail: run` schedules the entry's `stop_execution` through
`graph._validation.call_soon` (the autorestart route, ADR 0064 D9). Removed: failed/blocked flags,
`failure_counts`, `LocalizedDataFlow.sources`, blocked warnings, the removal hook.

## Global Constraints

- Happy path: `_evaluate_data_flow` adds at most one integer test per data node while `_failed_count == 0`.
  `_execute`'s success path allocates nothing new per call.
- Exceptions still go through `HaywireVM.catch_exception` (error_runtime + log) unchanged.
- `failed` is a node property shared across execution groups; flips take the class lock; no lock on reads.
- The check never mutates `_has_dirty_ports` of a skipped node.
- Control (exec) edges never poison; only data inlets (`port.is_dependent and port.is_inlet()`) count.
- Line length 109; docstrings per `.claude/rules/python-docs.md`; no relative imports under `barn/`.
- Benchmarks: absolute per case, min-of-N, fixed topology, frozen nodes; never a derived delta. Rows are folded
  into the slice's commits. Clean baseline already recorded on master `f77d5a560` (graph_loop 2702 ns,
  node_execute_bare 137.8 ns) — uncommitted rows in `benchmarks/results/results.jsonl`, fold into Task 1.
- Glossary/ADR text lands in Task 7 with the code.

## Review Focus

1. **Shared data node across two execution groups** (ADR 0064): group A's failure blocks group B's consumers;
   B's own retry of the shared node under `exec_lock` clears it for both.
2. **Control node that raises after writing a data outlet** read by a later control node's localized flow in
   the same frame → that consumer is blocked.
3. **Loopback**: a body data node failing every other iteration; the loop continues, the count returns to 0
   when it recovers, `failures` grows per failing iteration only.
4. **Counter drift**: hot reload / node removal / graph close while a node is failed must not leave
   `_failed_count` > 0 forever (fast path lost). → decrement on cleanup.
5. **Re-entrancy**: a worker that raises inside a `resolve_dirty_data` `on_change` callback — ports popped
   before the raise are re-inserted.

---

### Task 1: Frozen benchmark nodes and the four new cases (pre-change numbers)

**Files:**
- Create: `barn/haybale-testing/haybale_testing/nodes/benchmark/bench_data_pass_node.py` (DATA node, one
  FLOAT inlet `x`, one FLOAT outlet `y = x + 1`), `bench_data_raise_node.py` (DATA node, same ports, worker
  raises when a module-level switch says so — the switch is the case's input, not an edit),
  `bench_fan_in_node.py` (DATA node, inlets `a`, `b` → `y = a + b`), `bench_loop_raise_node.py` (DATA node
  raising on odd input), each with the *FROZEN — DO NOT EDIT* header used by `bench_bare_node.py`; register in
  the benchmark package `__init__`.
- Modify: `benchmarks/cases.py` (cases `graph_data_chain_ok`, `graph_data_chain_root_fails`,
  `graph_loop_half_failing`, `node_execute_raises`), `benchmarks/README.md` (case list).

- [ ] **Step 1.** Build the topologies with the public graph API, like `_build_loop_graph`:
  - `graph_data_chain_*`: event → one control node (`BenchExecNode` or a frozen control node with one FLOAT
    data inlet) whose localized data flow is a 32-node chain of `BenchDataPassNode` plus a fan-in
    (`BenchFanInNode` joining node 16 and node 32) feeding the control inlet. `_root_fails` makes the chain's
    first node a `BenchDataRaiseNode` with the switch on. Dirty the root inlet before every frame so the whole
    chain evaluates each run.
  - `graph_loop_half_failing`: the `graph_loop` ForLoop topology with a `BenchLoopRaiseNode` fed by the loop
    index in the body.
  - `node_execute_raises`: micro, one `BenchDataRaiseNode` with a dirty inlet, `node._execute(ctx)` in a
    `try/except` loop (re-dirty the inlet each call so the pre-S2 run measures the same work).
- [ ] **Step 2.** `uv run python benchmarks/run.py graph_data_chain` etc. on the **pre-change** code; check
  the tree is clean for each run (run one case per clean tree, or stash the results file between runs as done
  for the baseline) so every row is `dirty=false`.
- [ ] **Step 3.** Commit nodes + cases + all baseline rows (incl. the two master rows):
  `git commit -m "bench(vm): frozen failure-path benchmark cases with pre-S2 baselines"`.

---

### Task 2: `failed` flag, process-wide count, failed-stays-dirty

**Files:** Modify `packages/haywire-core/src/haywire/core/node/base.py` (`_execute`), `.../node/data.py`
(`failed` state, `_failed_count`, lock, `_mark_failed()`, `_clear_failed()`, cleanup decrement);
Test `tests/core/test_execution/test_failure_state.py`.

**Interfaces:** `BaseNode.failed: bool` (read-only property); `BaseNode._failed_count: ClassVar[int]`;
`BaseNode._mark_failed() -> None` (idempotent; increments the count on the False→True flip);
`BaseNode._clear_failed() -> None` (idempotent; decrements on True→False). `_execute`: on exception from
dirty resolution, `on_validate` or the worker, re-insert every port it popped, then re-raise; on a normal
return call `_clear_failed()` only when `failed` (one attribute test on the hot path).

- [ ] **Step 1: Failing tests:** worker raises → after the VM catch the node is `failed`, its dirty inlet is
  dirty again, `error_runtime` set; next `_execute` with a working worker clears `failed` and the count goes
  back to 0; raising twice counts once; raising in `on_validate` and in an `on_change` during resolution
  (Review Focus 5) re-inserts popped ports; node cleanup while failed decrements (Review Focus 4); a data node
  with no dirty port still early-outs.
- [ ] **Step 2–4:** run → FAIL; implement; run → PASS; `uv run pytest tests/core/test_execution -n 4 -q`.
- [ ] **Step 5:** `git commit -m "feat(vm): a raising node is failed and stays dirty"`.

---

### Task 3: Upstream sources precomputed at Assembly

**Files:** Modify `packages/haywire-core/src/haywire/core/execution/flow.py` (`LocalizedDataFlow.upstream`),
`packages/haywire-core/src/haywire/core/assembly/data_flow_builder.py`; Test
`tests/core/test_assembly/test_localized_upstream.py`.

- [ ] **Step 1: Failing tests:** for a chain A→B→C feeding control node K, `upstream["B"] == (A,)`,
  `upstream["K"] == (C,)`; a fan-in node lists both sources once; an exec edge contributes nothing; a source
  outside the sequence (a control node's data outlet, a subgraph boundary through `FlatGraphView`) is listed;
  a node with no data inlets maps to `()`. Use `FlatGraphView` inlet-side lookups (see
  `.insights/project_flat_view_ordering_inlet_side.md`).
- [ ] **Step 2–4:** run → FAIL; implement; run → PASS; `uv run pytest tests/core/test_assembly -n 4 -q`.
- [ ] **Step 5:** `git commit -m "feat(assembly): localized data flows know each node's data sources"`.

---

### Task 4: The VM blocks poisoned nodes

**Files:** Modify `packages/haywire-core/src/haywire/core/execution/vm.py` (`_evaluate_data_flow` returns the
pass-local blocked set; `_execute_control_node` checks the control node; `catch_exception` callers mark
failed and append to `failures`), `.../execution/execution_context.py` (`failures`); Test
`tests/core/test_execution/test_failure_poisoning.py`.

- [ ] **Step 1: Failing tests** (real assembled graphs, `graph_with_library_system`, haybale-testing
  testbed nodes or tiny test-local nodes registered like other execution tests):
  - stale-outlet regression (the `img_042` scenario): source data node outputs frame index; it raises on
    frame 41; the consumer's outlet after frame 41 is **not** 41's stale value (consumer did not run) and on
    frame 42 is 42;
  - transitive blocking A(fails)→B→C: B and C skipped, keep dirty ports, get the `blocked` warning naming A;
    next frame A succeeds → all run, warnings gone, count 0;
  - retry recovery: a node failing once (transient) recovers the next frame without a new edit;
  - control node with a poisoned data inlet does not run its worker; the branch ends normally (loopback pop
    works) — Review Focus 3 with a ForLoop body;
  - control node raising after writing its data outlet; a later control node in the same frame reading it is
    blocked (Review Focus 2);
  - shared data node across two execution groups (Review Focus 1) — follow
    `tests/core/test_execution/test_execution_group.py` patterns;
  - exec edges never poison: a control node after a failed control node (via exec) still runs when its data
    inlets are clean;
  - `context.failures` gets `(id, exc)` for each raise and `(id, "blocked")` for each block, per frame;
  - with `_failed_count == 0` the check never touches `upstream` (assert via a sentinel dict that raises on
    access).
- [ ] **Step 2–4:** run → FAIL; implement; run → PASS; `uv run pytest tests/core/test_execution -n 4 -q`.
- [ ] **Step 5:** `git commit -m "feat(vm): consumers of a failed node are blocked, not run on stale data"`.

---

### Task 5: Sweep for "run anyway" reliance

- [ ] **Step 1:** `uv run pytest -m "not browser and not perf" -n 4 -q > <ws>/sweep.log 2>&1`; triage every
  failure: a test asserting a consumer ran after its source raised is updated to the new semantics with a
  one-line comment citing ADR 0066; anything else is a bug in Tasks 2–4.
- [ ] **Step 2:** grep `graphs/`-free test fixtures and `barn/*` example graphs for nodes that raise by
  design (e.g. error testbed nodes) and check their cards still behave (error badge on the root, blocked
  warning downstream). Commit `test(vm): align tests with failure poisoning` if anything changed.

---

### Task 6: Benchmarks after the change — acceptance

- [ ] **Step 1:** clean tree; run `graph_loop`, `node_execute_bare`, `graph_data_chain_ok`,
  `graph_data_chain_root_fails`, `graph_loop_half_failing`, `node_execute_raises` (each on a clean tree).
- [ ] **Step 2: Acceptance:** `graph_loop`, `node_execute_bare`, `graph_data_chain_ok` within noise of the
  pre-change rows (target ≤ 2 % on min; re-run twice before calling a regression); `graph_data_chain_root_fails`
  < `graph_data_chain_ok`. If a target is missed, profile and fix before continuing (a ruling only if the
  miss is within documented session noise, ±4 % per `benchmarks/README.md`).
- [ ] **Step 3:** `git commit -m "bench(vm): failure poisoning results"`.

---

### Task 7: ADR, glossary, docs, insight

**Files:** Create `docs/adr/0066-failed-nodes-poison-their-consumers.md`; modify `docs/reference/glossary.md`
(**Failed node**, **Blocked node**), `docs/architecture/execution/virtual-machine/*`,
`docs/architecture/execution/lazy-evaluation/*` (poisoning + failed-stays-dirty, present tense),
`docs/architecture/errors/errors-arch.md` (`error_runtime` is sticky until revalidation; `failed` is the live
flag), `CLAUDE.md`/`.insights` only if a new trap surfaced.

- [ ] **Step 1–2:** write; `uv run mkdocs build --strict` → 0.
- [ ] **Step 3:** `git commit -m "docs(vm): failure poisoning — ADR 0066, glossary, execution docs"`.

---

### Task 8: Verify and mark S2 done (status rule — mandatory last task)

- [ ] **Step 1:** ruff + format check; full mypy from CLAUDE.md; non-browser and browser suites → exit 0.
- [ ] **Step 2:** live check with `haywire-live-studio`: a graph with a raising data node feeding a viewer —
  root shows the error badge, consumer shows the blocked warning, fixing the input recovers without an edit.
- [ ] **Step 3:** spec §3 S2 row → `done (<sha>, <date>)` + deviations; commit
  `docs(plan): S2 done — failure poisoning`.
