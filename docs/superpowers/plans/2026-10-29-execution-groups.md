# Execution Groups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop two threads from ever executing the same node at once: flows that share a control node run on one runner thread; a data node executed by several groups runs under its own lock.

**Architecture:** Assembly is unchanged. After assembly, the Interpreter partitions flows into **execution groups**: flows that share a control node land in one group. Each group gets one runner thread that drains a merged FIFO of its flows' triggers and runs one whole frame at a time. A data node that more than one group executes (a **shared data node**) is executed under its wrapper's execution lock, so groups take turns on it while staying parallel everywhere else; values move between groups asynchronously through ordinary data edges. The gap between two frames is the **frame barrier**: structural validation batches park every group there, and stop/kill are checked there. Lifecycle hooks are reference-counted on the wrapper: the first group to use a node starts it, the last one stops it.

**Tech Stack:** Python 3.12 (GIL build), stdlib `threading`/`queue`, pytest.

**Spec:** the *Design* section below (settled with the user 2026-10-28/29). Evidence: `internals/issues/REPORT_Shared_node_concurrent_execution.md` plus a passing reproduction at `.claude/worktrees/wf_3cfd358b-ad1-6/tests/core/test_execution/test_shared_node_concurrency_repro.py` (untracked; written on `5a907a54a`, whose execution core is identical to master).

## Design (settled)

| # | Decision |
|---|---|
| D1 | Keep one-thread-per-unit execution; the unit becomes the **execution group**, not the flow. |
| D2 | Assembly refuses no cross-flow link. Flows that share a control node are merged into one group instead (ADR 0043: defuse, don't refuse). |
| D3 | **Grouping rule:** flows that share a control node form a group (transitive closure over each flow's control nodes, entry event node included). Data nodes and data edges never group flows; callback/subscription edges never group flows. |
| D3a | **Shared data node:** a data node in the localized data flows of more than one group. Its `_execute`, `on_frame_start` and `on_frame_end` run under its wrapper's `exec_lock`. The first group to reach it in a frame computes it; a group arriving later waits, finds it clean and reads the fresh outlet. Its state advances once per frame of whichever group reaches it first. Its `on_frame_start`/`on_frame_end` run at the start/end of every frame of every group that executes it; calls never overlap, but calls from different groups may interleave, so a node must not rely on start/end pairing. |
| D3b | Values cross groups asynchronously through data edges ("let it rip", as D7). A value object must not be mutated in place once written to an outlet. |
| D4 | One runner thread per group, merged queue, strict arrival order (FIFO), system events included. |
| D5 | DROP inside a group keeps the **newest** pending trigger (replace, don't refuse). Applies to every flow, since a one-flow group is the same machinery. |
| D6 | A callback emitted from inside a group's own frame never blocks: enqueue without waiting; drop with a warning if that flow's queue is full. |
| D7 | Value writes from outside a frame (UI, edit route, Farmhand, node-owned threads) apply immediately ("let it rip"). Node authors guard state an `on_change`/settings handler shares with `worker()` (documented contract). |
| D8 | Structural changes wait for the barrier: a validation batch that mutates structure first parks every group of the graph tree, and leaves them parked if the batch requires reassembly. |
| D9 | Stop/autorestart runs outside the validation lock (after the batch). |
| D10 | Lifecycle is reference-counted on the wrapper (`retain()`/`release()` under `exec_lock`): each group, before its first frame, retains every node it executes and the first retain calls `on_startup`; after its last frame it releases them and the last release calls `on_shutdown`. "Started on first use, stopped after last use" — a node can start twice in one run only if one group fully stops before another starts (calls stay paired, never overlap). |
| D11 | Kill switch: skip the Shutdown flow, clear queues, end the running frame at the next control node, still run `on_shutdown`. A runner that never exits is *abandoned*; restart is refused while one is alive. A graceful stop that times out escalates to kill. |
| D12 | No UI for flows or groups (dropped as overkill). |
| D13 | Node-owned threads (TickEmit tick loop, capture loops): may emit callbacks and read inputs; guard state shared with `worker()`/lifecycle with the node's own lock; never write ports directly — use `BaseNode.post_value`, which hands the write to the validation scheduler's thread. |

**Lock order (new, documented in Task 8):** group hold → `NodeWrapper.exec_lock` → validation lock → `NodeWrapper._lock`. A runner thread never waits for a hold; a holder never holds the validation lock while waiting for runners; a thread holds at most one `exec_lock` (only the VM calls `_execute`, and a data node's worker never executes another node); validation never takes an `exec_lock`.

## Global Constraints

- No new third-party dependencies; stdlib `threading`/`queue` only.
- Graph layer stays framework-free (ADR 0002): nothing under `haywire/core/graph` or `haywire/core/execution` imports NiceGUI.
- No relative imports under `barn/` (ruff TID252).
- Runner thread name: `FlowExec-<group_id>`; `group_id` is `group_<flow_id of the group's first flow>`.
- Glossary and ADR text is collected in Task 8 and lands with the code, not before.
- Line length 109; run both `uv run ruff check` and `uv run ruff format --check` on touched files.
- Commit `barn/haybale-testing` edits before any full-suite run (`test_generate.py` teardown reverts that dir).

## Review Focus

1. **Hold requested from a runner thread** (a `SyncScheduler` graph whose worker rejigs ports validates inline inside its own frame): must not wait for itself. Expected: `hold_for_batch()` returns `False` and the batch runs unheld. Test in Task 5.
2. **A callback emitted from flow A's frame to flow B of the same group**: B's frame runs after A's frame ends, never nested inside it, and A's frame is not delayed by the emit. Test in Task 3.
3. **Stop while held for reassembly**: a parked runner must wake on stop and exit without running another frame. Test in Task 5.
4. **Stuck worker on stop**: stop returns within `timeout_s + kill timeout`, the group is reported abandoned, and `GraphEntry.compile()` refuses with a message naming the graph. Test in Task 6.
5. **DROP flow with `max_queue_size=1` fed faster than it runs**: exactly one pending trigger at any time, always the newest; `wait_for_completion` still returns. Test in Task 3.
6. **Kill while a frame waits for a shared data node held by a stuck group**: the waiting frame gives up on the lock (cancel flag), its group exits; only the stuck group is abandoned. Test in Task 4.

---

### Task 1: Regression suite from the reproduction (expected to fail)

**Files:**
- Create: `tests/core/test_execution/test_shared_node_concurrency.py`
- Reference (do not commit): `.claude/worktrees/wf_3cfd358b-ad1-6/tests/core/test_execution/test_shared_node_concurrency_repro.py`

**Interfaces:**
- Produces: five tests marked `@pytest.mark.xfail(strict=True, reason="execution groups")`; Tasks 3 and 4 remove the marks they satisfy.

- [ ] **Step 1: Port the five repro tests with inverted assertions.** Keep `_OverlapProbe`, graph construction and triggers verbatim; set `BARRIER_TIMEOUT_S = 0.5` (a serialized run now times the barrier out on purpose). New assertions:
  - `test_shared_control_node_never_runs_on_two_threads`: `probe.broken is True`, `probe.max_active == 1`.
  - `test_shared_node_worker_sees_its_own_flows_payload`: `worker_saw[key_a] == {"flow": "A"}`, `worker_saw[key_b] == {"flow": "B"}`.
  - `test_dirty_port_drain_has_one_drainer`: node `error_runtime is None`, both flows' `runs` recorded.
  - `test_stop_during_begin_play_frame_serializes_with_shutdown`: `max_active == 1`; `hook_threads["on_startup"]` and `["on_shutdown"]` each have length 1.
  - `test_shared_data_node_never_runs_on_two_threads`: the two flows are in **different** groups (`len(interpreter.groups) == 2`) and `max_active == 1`.
- [ ] **Step 2: Run** `uv run pytest tests/core/test_execution/test_shared_node_concurrency.py -q` → Expected: `5 xfailed`.
- [ ] **Step 3: Commit** `test(execution): shared-node concurrency regression suite (xfail)`.

### Task 2: Partition flows into groups

**Files:**
- Create: `packages/haywire-core/src/haywire/core/execution/execution_group.py`
- Test: `tests/core/test_execution/test_group_flows.py`

**Interfaces:**
- Produces:
  - `group_flows(flows: Sequence[Flow]) -> list[list[Flow]]` — union-find over each flow's control node ids (`flow.get_control_node_ids()` plus `flow.get_entry_node_id()`). Groups ordered by first appearance in `flows`; flows inside a group keep input order.
  - `shared_data_node_ids(groups: list[list[Flow]]) -> frozenset[str]` — ids of nodes from `Flow.get_all_nodes()` that are not control nodes and appear in more than one group.

- [ ] **Step 1: Write failing tests** using stub flows exposing `get_control_node_ids()`, `get_entry_node_id()` and `get_all_nodes()` (objects with `node_id`):
  - `test_disjoint_flows_get_one_group_each` → `len(groups) == 3`.
  - `test_shared_control_node_merges` (A, B share control node `x`) → one group `[A, B]`.
  - `test_shared_data_node_does_not_merge` (A, B share only data node `s`) → two groups; `shared_data_node_ids(groups) == {"s"}`.
  - `test_data_node_shared_inside_one_group_is_not_shared` (A, B share control `x` and data `s`) → one group; `shared_data_node_ids(groups) == frozenset()`.
  - `test_transitive_chain_merges` (A–B share control `x`, B–C share control `y`) → one group `[A, B, C]`.
- [ ] **Step 2: Run** `uv run pytest tests/core/test_execution/test_group_flows.py -q` → FAIL (import error).
- [ ] **Step 3: Implement** `group_flows` and `shared_data_node_ids` in `execution_group.py`.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(execution): partition flows into execution groups`.

### Task 3: Group runner, per-flow policy, shared data nodes, reference-counted lifecycle

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/execution/execution_group.py` (add `ExecutionGroup`)
- Modify: `packages/haywire-core/src/haywire/core/execution/scheduler.py` (`FlowScheduler` loses its thread)
- Modify: `packages/haywire-core/src/haywire/core/execution/vm.py` (`call_flow_startup`/`call_flow_shutdown` → `call_startup`/`call_shutdown`; shared data nodes and their frame hooks run under `exec_lock`)
- Modify: `packages/haywire-core/src/haywire/core/execution/flow.py` (delete dead `is_locked`; add `shared_node_ids: frozenset[str] = frozenset()`; module-level `overrides(node, method_name) -> bool` replacing `Flow._is_method_overridden`)
- Modify: `packages/haywire-core/src/haywire/core/node/node_wrapper.py` (`exec_lock`, `_run_refs`, `retain()`, `release()`)
- Modify: `packages/haywire-core/src/haywire/core/execution/interpreter.py` (`_register_flow`, `load_graph`, `_cleanup_current_graph`, `wait_all`, `get_statistics`)
- Modify: `packages/haywire-core/src/haywire/core/execution/__init__.py` (export `ExecutionGroup`)
- Test: `tests/core/test_execution/test_execution_group.py`; update `tests/core/test_execution/test_event_source_queue_mode.py`, `tests/core/test_execution/test_scheduler_wait.py`

**Interfaces:**
- Consumes: `group_flows`, `shared_data_node_ids` (Task 2).
- Produces:
  - `NodeWrapper.exec_lock: threading.Lock` (created in `__init__`, survives node rebuilds and Interpreters); `_run_refs: int = 0`; `retain() -> bool` (increments; `True` when it was 0); `release() -> bool` (decrements, never below 0; `True` when it reaches 0). Callers hold `exec_lock` around both and around the hook they trigger.
  - `ExecutionGroup(group_id: str, flows: list[Flow], vm: HaywireVM)`; attributes `nodes: list[BaseNode]` (deduplicated union of the flows' `get_all_nodes()`, first-seen order), `cancel: threading.Event`; methods `start() -> None`, `post(scheduler: FlowScheduler) -> None` (append one ready token), `is_runner_thread() -> bool`, `stop(timeout_s: float = 2.0) -> bool` (True = runner exited).
  - `FlowScheduler(flow, vm, queue_mode=QueueMode.BLOCK, max_queue_size=100, group: ExecutionGroup | None = None)`; keeps `enqueue_trigger`, `wait_for_completion`, `get_execution_stats`, `is_busy`, `get_queue_size`; adds `_run_one() -> None` (take one trigger, run the frame, `task_done`); removes `start`, `stop`, `_execution_loop`.
  - `HaywireVM.call_startup(nodes: Sequence[BaseNode], context_flow: Flow) -> None` — per node: `with wrapper.exec_lock: if wrapper.retain() and overrides(node, "on_startup"): node.on_startup(ctx)`. `call_shutdown(...)`, same signature, mirrors it with `release()`/`on_shutdown`. Every node is retained, whether or not it overrides the hook.
  - `HaywireVM._evaluate_data_flow` and the `on_frame_start`/`on_frame_end` loops: a node whose id is in `flow.shared_node_ids` runs under `node.wrapper.exec_lock`; all others run as today.
  - `Interpreter.groups: list[ExecutionGroup]`; `load_graph` sets every flow's `shared_node_ids` from `shared_data_node_ids(groups)` before starting the groups.

Runner loop (the one algorithm the tests don't pin):

```python
self.vm.call_startup(self.nodes, self.flows[0])
try:
    while True:
        token = self._ready.get()
        if token is _STOP or self._stop.is_set():
            break
        self._wait_while_held()          # Task 5; no-op until then
        token._run_one()
finally:
    self.vm.call_shutdown(self.nodes, self.flows[0])
    self._exited.set()
```

`enqueue_trigger` rules: reject when the group is stopping. **DROP**: when the flow's queue is full, take the oldest pending trigger out (`get_nowait` + `task_done`) and put the new one in, posting **no** new token; otherwise put + post. **BLOCK**: if `group.is_runner_thread()`, `put_nowait` and on `Full` log a warning and return `False`; otherwise `put(block=True, timeout=5.0)` then post. A per-scheduler `threading.Lock` makes replace-or-put atomic.

- [ ] **Step 1: Write failing tests** (`test_execution_group.py`, real `HaywireVM` with stub flows whose `execute_control_flow` is observed via a recording VM subclass):
  - `test_frames_of_one_group_never_overlap` → recorded `max_active == 1` across 2 flows × 20 triggers.
  - `test_frames_run_in_arrival_order` → recorded order equals enqueue order across flows.
  - `test_two_groups_run_concurrently` → a barrier of 2 inside both groups' frames opens (not broken).
  - `test_drop_keeps_newest_pending` (Review Focus 5) → with `max_queue_size=1` and the runner parked, enqueue t1, t2, t3 → only t3 runs after release; `wait_for_completion(1.0) is True`.
  - `test_emit_from_own_runner_never_blocks` → a frame enqueues 3 triggers into a sibling BLOCK flow with `max_queue_size=1`; returns within 0.2 s; result list `[True, False, False]`.
  - `test_startup_and_shutdown_once_per_node` → control node shared by 2 flows records exactly 1 `on_startup` and 1 `on_shutdown`, both on the runner thread.
  - `test_retain_release_counts` (wrapper unit test) → `retain()` returns `True, False`; `release()` returns `False, True`; a third `release()` returns `False` and `_run_refs == 0`.
  - `test_shared_data_node_started_before_either_groups_first_frame` → data node `s` in two groups records `on_startup` once, and before the first `worker` call of either group.
  - `test_shared_data_node_stopped_after_both_groups` → `on_shutdown` once, recorded after the last frame of both groups.
  - `test_shared_data_node_computed_once_and_read_fresh` → groups A and B both reach `s` in one round (A held inside `s.worker` by an `Event`); B's consumer waits, then reads the value A wrote; `s.worker` ran once.
  - `test_unshared_data_node_takes_no_lock` → a data node in one group: `exec_lock` is never acquired during frames (patch the lock with a recording stub).
  - `test_in_group_emit_runs_after_current_frame` (Review Focus 2) → A's worker emits to B (same group) then records `"A-end"`; recorded order is `["A-start", "A-end", "B-start"]`.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** the wrapper's `exec_lock`/`retain`/`release`, `ExecutionGroup`, the `FlowScheduler` changes, `call_startup`/`call_shutdown`, the `shared_node_ids` lock path in the VM, `overrides`; delete `Flow.is_locked`. Interpreter: `load_graph` registers flows (subscriptions + callback listeners) with `scheduler.group` set, then builds groups via `group_flows`, then starts each group. `_cleanup_current_graph` and `wait_all` stop groups instead of schedulers.
- [ ] **Step 4: Update existing tests:** `test_event_source_queue_mode.py` DROP expectation becomes "newest pending kept" (D5); `test_scheduler_wait.py` keeps constructing `FlowScheduler(flow=..., vm=None)` without a group.
- [ ] **Step 5: Remove the xfail marks** from Task 1's tests 1, 2, 3 and 5.
- [ ] **Step 6: Run** `uv run pytest tests/core/test_execution/ -q` → PASS (test 4 still xfail).
- [ ] **Step 7: Commit** `feat(execution): one runner thread per execution group`.

### Task 4: Graceful stop, kill switch, abandoned runners

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/execution/execution_context.py` (field `cancel: Optional[threading.Event] = None`)
- Modify: `packages/haywire-core/src/haywire/core/execution/vm.py` (`execute_control_flow` ends the control loop when `exec_ctx.cancel` is set, checked before each control node; `on_frame_end` still runs. A shared data node's `exec_lock` is taken with `acquire(timeout=0.1)` in a loop that gives up when `exec_ctx.cancel` is set — the node is then skipped and the frame ends)
- Modify: `execution_group.py` (`kill(timeout_s: float = 2.0) -> bool`, `is_abandoned` property), `interpreter.py`
- Test: `tests/core/test_execution/test_execution_group_stop.py`

**Interfaces:**
- Produces:
  - `ExecutionGroup.kill(timeout_s: float = 2.0) -> bool` — sets stop + `cancel`, drains every flow queue (one `task_done` per discarded trigger), posts the stop token, joins; `True` when the runner exited.
  - `ExecutionGroup.is_abandoned -> bool` — runner thread still alive after `stop`/`kill` returned `False`.
  - `Interpreter.kill_execution(timeout_s: float = 2.0) -> None` — no SHUTDOWN dispatch; kills every group; clears subscriptions like `_cleanup_current_graph`.
  - `Interpreter.has_abandoned_runners() -> bool`.
  - `stop_execution` keeps its protocol (dispatch SHUTDOWN, bounded wait on Shutdown flows), then `stop(timeout_s)` per group; a group whose stop returns `False` is killed.

- [ ] **Step 1: Write failing tests:**
  - `test_kill_ends_frame_at_next_control_node` → a 10-node chain whose 3rd worker sets a flag and sleeps 0.2 s; `kill()` during the sleep → nodes 4–10 never run; `on_frame_end` ran once; `kill(...) is True`.
  - `test_kill_skips_shutdown_flow` → Shutdown flow's worker never runs; `on_shutdown` of a shared node ran once.
  - `test_stop_timeout_escalates_to_kill` → worker loops on `time.sleep(0.01)` forever but is a chain → stop(0.2) returns after the kill finished the frame; `is_abandoned is False`.
  - `test_kill_frees_group_waiting_on_shared_data_node` (Review Focus 6) → group A stuck inside shared data node `s` (worker blocks on an `Event`); group B's frame waits for `s`; `interpreter.kill_execution(0.3)` → B's runner exits, A is abandoned, `has_abandoned_runners() is True`; `s.on_shutdown` not called (A never released it).
  - `test_stuck_worker_is_abandoned` (Review Focus 4) → worker blocks on an `Event` never set (released in teardown); `kill(0.2) is False`; `is_abandoned is True`; `has_abandoned_runners() is True`.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Remove the xfail mark** from Task 1's test 4; run `uv run pytest tests/core/test_execution/ -q` → PASS.
- [ ] **Step 5: Commit** `feat(execution): kill switch and abandoned-runner tracking`.

### Task 5: Structural batches wait for the barrier

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/graph/types.py` (`ChangeReason.mutates_structure() -> bool`)
- Modify: `packages/haywire-core/src/haywire/core/graph/validation.py` (`ExecutionHold` protocol, `set_execution_hold`, `call_soon`, hold around `_validate_batch`)
- Modify: `execution_group.py` (`hold() -> None`, `release() -> None`, `_wait_while_held()`), `interpreter.py`
- Test: `tests/core/test_graph/test_change_reason_structure.py`, `tests/core/test_execution/test_structural_hold.py`

**Interfaces:**
- Produces:
  - `ChangeReason.mutates_structure()` — `False` for `NODE_VALUE_CHANGED`, `GRAPH_CONTENT_CHANGED`, `NODE_REDRAW_REQUESTED`, `NODE_MOVED`, `NODE_STAGE_CHANGED`, `NODE_LAYOUT_CHANGED`, `EDGE_REDRAW_REQUESTED`, `EDGE_STYLE_CHANGED`; `True` for every other member.
  - `class ExecutionHold(Protocol)`: `hold_for_batch(self) -> bool`; `release_after_batch(self, requires_reassembly: bool) -> None`.
  - `ValidationManager.set_execution_hold(hold: ExecutionHold | None) -> None` — called on the **root** graph's manager; a Subgraph's manager reads it through `self._graph.root_graph._validation`.
  - `ValidationManager.call_soon(fn: Callable[[], object]) -> None` — `self._scheduler.schedule(0.0, fn)`.
  - `ExecutionGroup.hold()` sets the hold flag and waits until no frame runs; `release()` clears it and wakes the runner; `stop`/`kill` also wake a held runner, which then exits without another frame.
  - `Interpreter` implements `ExecutionHold`: `hold_for_batch()` returns `False` (no-op) when called on any of its runner threads, else holds every group and returns `True`; `release_after_batch(requires_reassembly)` releases unless `requires_reassembly`, in which case groups stay held until stop. `load_graph` calls `set_execution_hold(self)` on `graph.root_graph`; cleanup clears it.

Batch protocol in `_validate_batch` (lock order: hold before the validation lock):

```python
held = False
while True:
    with self._validation_lock:
        structural = self._pending_mutates_structure()
        if held or not structural or hold is None:
            ...existing batch body...
            break
    held = hold.hold_for_batch()
    if not held:
        ...run the existing batch body unheld (runner-thread case)...
        break
# after the with-block has released the lock:
if held:
    hold.release_after_batch(requires_reassembly=result.graph is not None
                             and result.graph.requires_graph_reassembly())
```

(Factor the existing body into `_run_batch_locked() -> ValidationResult` so both branches call one function.)

- [ ] **Step 1: Write failing tests:**
  - `test_mutates_structure_table` → parametrized over every `ChangeReason` member against the lists above.
  - `test_structural_batch_waits_for_running_frame` → frame blocked on an `Event`; a `NODE_VALIDATION_REQUESTED` batch on a `ThreadingTimerScheduler` does not start housekeeping until the event is set (record order: `frame_end` before `housekeeping`).
  - `test_value_batch_does_not_hold` → `NODE_VALUE_CHANGED` batch completes while a frame is blocked.
  - `test_reassembly_batch_leaves_groups_held` → after an `EDGE_ADDED` batch, a new trigger does not run within 0.2 s; `stop()` then returns `True` (Review Focus 3).
  - `test_hold_from_runner_thread_is_noop` (Review Focus 1) → `SyncScheduler` graph; a worker adds a port inside its frame; the frame completes; no deadlock within 2 s.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest tests/core/test_graph/ tests/core/test_execution/ -q` → PASS.
- [ ] **Step 5: Commit** `feat(validation): structural batches wait for the frame barrier`.

### Task 6: Haystack — stop/restart outside the validation lock, kill, refuse restart

**Files:**
- Modify: `barn/haybale-haystack/haybale_haystack/state/haystack_state.py` (`_on_entry_validation` lines ~214-223; `kill_execution(entry)`)
- Modify: `barn/haybale-haystack/haybale_haystack/graph_entry.py` (`kill_execution()`, `compile()` refusal, abandoned-interpreter list)
- Modify: `barn/haybale-haystack/haybale_haystack/editors/haystack_editor.py` (a "Kill" row/button next to Stop, shown while executing; mirror `_on_stop_execution` at :652)
- Test: `tests/haystack/test_autorestart.py`, `tests/haystack/test_graph_entry_compile.py`

**Interfaces:**
- Consumes: `ValidationManager.call_soon` (Task 5), `Interpreter.kill_execution`, `Interpreter.has_abandoned_runners` (Task 4).
- Produces: `GraphEntry.kill_execution() -> None`; `HaystackState.kill_execution(entry: GraphEntry) -> None`.

- [ ] **Step 1: Write failing tests:**
  - `test_restart_runs_after_batch_releases_lock` → with a scheduler stub recording `call_soon`, the reassembly path calls `stop`/`start` from the deferred callable, not inline; when the callable runs, `graph._validation.lock` is not held by the current thread (`lock._is_owned()` is `False`).
  - `test_compile_refused_while_previous_run_abandoned` → `GraphEntry` with a prior interpreter whose `has_abandoned_runners()` is `True` → `compile().ok is False`, error contains the graph's display name; after it turns `False`, compile succeeds.
  - `test_kill_execution_forwards` → `HaystackState.kill_execution(entry)` calls `entry.kill_execution()` and marks the haystack dirty (mirror `test_stop_execution_marks_haystack_dirty`).
- [ ] **Step 2: Run** `uv run pytest tests/haystack/ -q` → FAIL.
- [ ] **Step 3: Implement.** `_on_entry_validation` keeps steps 2–3 inline; step 1 becomes `entry.graph._validation.call_soon(lambda: self._restart_after_reassembly(entry))`. `GraphEntry.stop_execution`/`kill_execution` move an interpreter with `has_abandoned_runners()` into `self._abandoned`; `compile()` prunes entries that no longer have live runners and refuses while any remain.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `fix(haystack): restart outside the validation lock; kill and abandoned-run refusal`.

### Task 7: Node-owned threads — `post_value` and TickEmit

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/node/base.py` (`post_value`; hook docstrings state the threading contract: `on_change` and settings handlers may run while `worker()` runs)
- Modify: `barn/haybale-core/haybale_core/nodes/emits/tick_emit.py` (`_handle_start`, `_handle_stop`, `_stop_thread` under `self._lock`; read `target_fps`/`callback_names` once at start and pass them to `_tick_loop`)
- Test: `tests/core/test_node/test_post_value.py`, `tests/core/test_execution/test_tick_emit_start_stop.py`

**Interfaces:**
- Consumes: `ValidationManager.call_soon` (Task 5).
- Produces: `BaseNode.post_value(port_id: str, value: Any) -> None` — `self.wrapper.graph._validation.call_soon(lambda: self.ports[port_id].set_value(value))`; a missing port at delivery time is ignored.

- [ ] **Step 1: Write failing tests:**
  - `test_post_value_delivers_on_scheduler_thread` → `ThreadingTimerScheduler` graph; `post_value` from a plain thread; the port's `on_change` records a thread that is not the posting thread; value equals the posted one.
  - `test_post_value_inline_under_sync_scheduler` → value set before `post_value` returns.
  - `test_concurrent_start_spawns_one_tick_thread` → 8 threads call `_handle_start` together → exactly one live tick thread.
  - `test_concurrent_stop_never_raises` → 8 threads call `_stop_thread` together → no exception; `_thread is None`.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement.** Commit `barn/haybale-core` before the full-suite run in Task 9.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(node): post_value for node-owned threads; TickEmit start/stop under its lock`.

### Task 8: Docs, glossary, ADR

**Files:**
- Create: `docs/adr/0064-flows-that-share-a-node-share-a-runner.md`
- Create: `.insights/project_execution_group_lock_order.md`; add its one-line entry under *Architecture traps* in `CLAUDE.md`
- Modify: `docs/reference/glossary.md`, `docs/architecture/execution/assembly/assembly-arch.md:204-205`, `docs/architecture/execution/callbacks/callbacks-arch.md:136`, `docs/components/nodes/node-canon.md:198,427`, `docs/adr/0010-event-source-queue-mode.md` (amendment line for D5)

- [ ] **Step 1: Docs.** Exact text to land:
  - Glossary **Execution group**: "Flows that share a control node. One runner thread runs the group's frames one at a time, in trigger arrival order. Data edges never join groups: values cross between groups as they are written."
  - Glossary **Shared data node**: "A data node that more than one execution group executes. Groups take turns on it: the first to reach it in a frame computes it, the others read that result. Its state advances once per frame of whichever group reaches it first."
  - Glossary **Frame barrier**: "The moment between two frames of an execution group, when none of its nodes is executing. Structural validation, stop and kill take effect there."
  - Glossary **Kill**: "Ending a run without its Shutdown flow: queued triggers are discarded and the running frame ends at its next control node. `on_shutdown` still runs."
  - Glossary **FlowScheduler**: replace "owns … the single execution thread" with "owns the flow's trigger queue and queue mode; its frames run on its execution group's runner thread."
  - `assembly-arch.md:205`: "Each execution group runs on its own thread; flows that share a control node share a group (ADR 0064)." and fix "compute it twice" → "a shared data subtree is computed once per frame of whichever group reaches it first".
  - `callbacks-arch.md:136`: data between sibling flows may also travel over data edges; it arrives as written (D3b), not at frame boundaries.
  - `node-canon.md:198,427`: `on_startup` "before the node's first use in a run"; `on_shutdown` "after its last use"; both may run more than once per run only if one group stops before another starts.
  - Node threading contract (node-canon §6): D3b, D7 and D13 wording.
  - Frame hooks (node-canon §6 table rows for `on_frame_start`/`on_frame_end`, and the `BaseNode.on_frame_start`/`on_frame_end` docstrings in `packages/haywire-core/src/haywire/core/node/base.py`): "Runs at the start/end of each frame of each execution group that executes this node. A node executed by several groups gets these calls from each of them; the calls never overlap, but may interleave between groups, so start and end are not guaranteed to pair."
  - ADR 0064: context (report + reproduction), decisions D1–D13, lock order, alternatives considered (sorted per-node locks; per-node `_execute` lock for control nodes — refuted by the payload-swap test; grouping on any shared node — rejected because the rule needs explaining and forbids asynchronous data sharing; one thread per graph; refusing cross-flow links), consequences (DROP keeps newest; shared data node state advances per first-arriving group).
  - Insight file: lock order hold → exec lock → validation → node; one `exec_lock` per thread at a time; a runner never waits for a hold; why stop/restart is deferred via `call_soon`.
- [ ] **Step 2: Commit** `docs: ADR 0064 execution groups`.

### Task 9: Verification and cleanup

- [ ] **Step 1:** `uv run ruff check . && uv run ruff format --check .`
- [ ] **Step 2:** the mypy command from `CLAUDE.md`.
- [ ] **Step 3:** `uv run pytest -m "not browser and not perf" -n 4 -q > /tmp/t.log 2>&1; echo "exit=$?"` → `exit=0`. Then `uv run pytest -m browser -n 4 -q` → exit 0.
- [ ] **Step 4:** Run `tests/core/test_execution/` 5× with `-n 4` (lock-order regressions hang rather than fail) → all green, no 120 s timeouts.
- [ ] **Step 5:** Live check in the studio: run `graphs/oakNwebCam.haywire` (two camera flows stay in separate groups — check the runner thread names in the log); add an edge while running (graph pauses, restarts, cameras reopen); Stop; Kill.
- [ ] **Step 6:** Delete `internals/issues/REPORT_Shared_node_concurrent_execution.md` (superseded by ADR 0064); remove the repro worktree (`git worktree remove .claude/worktrees/wf_3cfd358b-ad1-6`). Commit `chore: retire shared-node report`.

## Out of scope (separate issues)

- Lazy edge fires `on_change` twice per execution (confirmed by probe; unrelated to threading).
- `CallbackManager.callback_stats` lost updates; `CallbackManager.callbacks` and `Event.invoke` iterated while mutated.
- Reassembly in place at the barrier, so cameras survive edits (decision 5b, later).
- haybale-visiongraph follow-ups (separate repo): estimator `hb_on_model_change` must guard `hb_estimator` against a running `process()` (D7 contract); webcam/OAK-D status writes from capture threads → `post_value` (D13).
