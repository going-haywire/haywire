# Browser test suite performance

## Baseline (measured 2026-09-23, after the two bug fixes)

Full suite: **420.56s**. Browser tier alone: **185.42s / 135 tests**, split:

| phase | total | per test |
| --- | --- | --- |
| setup | 9.92s | 73ms |
| call | 167.49s | 1.24s (median 1.02s) |
| teardown | 0.53s | — |

Fixture setup is **not** the bottleneck. Two levers inside `call`:

1. **~45s of fixed sleeps.** 80 `page.wait_for_timeout(N)` calls across 18
   files, mean 562ms, summing to 44,986ms of unconditional waiting.
2. **No parallelism.** 135 tests run serially against one harness server on a
   hardcoded port; the box has 10 cores.

Non-goal: touching the non-browser tiers. They are already ~2.5 min for 2985
tests and share process-global DI state (`.insights/project_di_context.md`) —
parallelising them is a separate question with its own risks.

## Slice 1 — xdist (structural, no per-test semantics change)

Cuts wall clock by worker count without changing what any test asserts.

The blocker is addressing, not xdist itself: `harness` is session-scoped, and
xdist gives **each worker its own session**, so every worker starts its own
harness subprocess. Today they would all bind 8090. Worse, 31 module-level
constants across 28 files hardcode `http://localhost:8090/...`, bypassing the
fixture's value entirely — so even with per-worker ports, tests would all hit
worker 0's server.

Verified state: **every** test function that reaches a URL constant already
takes `harness` as a parameter (0 exceptions), so no test signature changes.
12 module-level helpers (`_open(page)`, `_open_and_count(page, edges)`,
`_open_row_menu(page, field)`) close over the constants and need `harness`
threaded through, across 52 call sites.

### Steps

1. Add `pytest-xdist` to the `dev` dependency group. *(done)*
2. `app.py`: read the port from `HAYWIRE_HARNESS_PORT`, defaulting to 8090 so
   `uv run python tests/ui/harness/app.py` is unchanged. *(done)*
3. `conftest.py`: `_harness_port()` offsets by the digits of
   `PYTEST_XDIST_WORKER` (`gw0` → 8090, `gw1` → 8091, …); pass it to the
   subprocess and yield the matching base URL. *(done)*
4. Replace each module-level URL constant with a **path** constant
   (`_PATH = "/graph-connect"`), and build the URL at call time from the
   `harness` fixture. A path constant keeps the one-line-per-file shape and
   makes a missed conversion a `NameError`, not a silent wrong-port hit.
5. Thread `harness` into the 12 helpers and their 52 call sites.
6. `test_mirror.py` additionally uses `_BASE_URL` for a `requests.post` — that
   becomes `harness` directly.

### Verification — DONE 2026-09-23

- `grep -rn 8090 tests/ui/harness/*.py` returns only `app.py` and `conftest.py`. ✓
- Serial: **135 passed in 186.18s**, against a 185.42s pre-refactor baseline —
  the URL refactor is behaviour-neutral. ✓
- Parallel `-n 4`: **135 passed in 53.7/53.8/54.0s** over three consecutive
  runs. **3.5x**, and stable. ✓
- Parallel `-n 8`: 36-54s, but one run timed out
  `test_edge_batch_cost.py::test_edge_sync_message_count_does_not_grow_with_edge_count`
  at the 30s Playwright default. That test *measures cost*, so it is the one
  most sensitive to a loaded box; it passes alone in 3.55s. **`-n 4` is the
  recommended setting** — `-n 8` trades stability for ~15s.

Parallelism stays **opt-in** (`-n` on the command line), not in `addopts`: the
pre-commit gate is `-m "not browser and not perf"` and must keep its current
behaviour, and a wedged browser worker is easier to read serially.

## Slice 2 — replace fixed sleeps with condition waits

~45s of pure sleeping. Each `wait_for_timeout(N)` encodes an assumption about
how long an async settle takes; replacing one with a wait on the actual
condition is both faster and less flaky — but replacing it with the *wrong*
condition trades a slow test for an intermittent one, so this is per-call-site
work, not a regex.

Distribution: 300ms×17, 600ms×12, 400ms×12, 500ms×10, 1200ms×8, 900ms×4,
800ms×4, plus a tail of 200/250/1500/1000/150/120/100/16.

### Approach

Work file by file, largest sleeps first (the 1200ms/900ms ones in
`test_graph_layout_direction.py` and `test_graph_node_detail*.py` are the
richest). For each call site, classify:

- **Waiting for a DOM state** → `page.wait_for_selector` / `wait_for_function`
  on the thing actually being asserted.
- **Waiting for a server round trip** → the harness already stamps
  `data-hw-synced`; prefer an equivalent explicit signal over a guess.
- **Waiting for an animation/settle with no observable end state** → keep the
  sleep, but justify the number in a comment. Some are legitimate (e.g.
  `wait_for_timeout(16)` for one frame).

A sleep that cannot be replaced honestly stays. The goal is removing guesses,
not hitting a number.

### Verification

Per file: run that file 3× and confirm green each time (a condition wait that
is subtly wrong shows up as intermittence, which a single run hides). Then the
whole browser tier, and record the new total.

### Result — DONE 2026-09-23

Sleep budget **44,986ms over 80 calls → 20,386ms over 37**. Serial browser tier
**186.18s → 137.75s** (−26%), 135 passed.

What was replaced, and with what:

- `_open()`'s 800–1500ms "let the graph sync + center" in 8 files → a new
  `nav.wait_for_canvas_settled()`, which holds `.zoom-pan-content`'s transform
  equal across two frames. This was the single broadest win: it ran once per
  test in those files.
- `test_interaction.py` (8 sleeps → 0): every one waited for a row to re-render
  with the `•` override marker → a retrying `expect` on the marker itself.
- `test_validation.py` (7 → 0): pure redundancy. Every assertion was already a
  retrying `expect(...)`, so the sleeps bought nothing.
- `test_node_sizing.py` (13 → 4): size presets round-trip to the server, so
  wait on the inline `min-width` the assertion then reads.
- `test_graph_hidden_level_edges.py` (12 → 2): the file already had
  `_wait_until_on_pins`, a poll-to-tolerance helper; the sleeps around it were
  redundant.
- `test_graph_connect.py` (7 → 3): "an edge appears" → `wait_for_selector`.

**Two sleeps were restored after failing verification**, and this is the useful
part of the result. Both are at `[data-testid="rekey"]`, which tears the canvas
down and remounts it. Removing them made
`test_re_keying_the_panel_brings_the_edges_back` fail 3/3: `_wait_for_all_edges`
is satisfied by the edges still on screen from *before* the remount, so it
returned instantly and the geometry was then measured mid-remount. Nothing
observable marks the teardown — the file's own docstring says it "is too brief
to catch from here". They are back, each with a comment saying why. This is the
plan's "a sleep that cannot be replaced honestly stays" case.

A negative assertion (`test_outlet_to_outlet_makes_no_edge`) also keeps its
sleep: there is nothing to wait *for*, and the wait is what gives a wrong edge
time to appear.

## Slice 3 — the non-browser tier parallelises too

Not in the original plan: the non-browser tier was a stated non-goal, on the
assumption that process-global DI state made it unsafe. That assumption was
wrong in the way that matters — xdist gives each worker its own *process*, so
module-level globals are per-worker and isolated for free.

Plain `-n 4` runs 5769 tests in ~90s against 248s serial, with no source
changes at all. The shared-resource hazard that did look real —
`tests/studio/test_docs/test_generate.py` running `git checkout -- barn/haybale-testing`
on the live working tree — turns out to be confined to that one file, and has
not been observed to bite.

**`--dist loadfile` must not be used.** It was tried as the textbook fix for
that git hazard and is strictly worse: 5 failures on every run, in rotating
macro/registry tests, *and* it silently collects fewer tests than exist
(3689–4242 instead of 5769). The default `--dist load` is the working mode.

## Combined result

| tier | serial | `-n 4` |
| --- | --- | --- |
| browser (135 tests) | 137.8s (was 185.4s) | ~42.8s |
| non-browser (5769 tests) | 248s | ~90s |
| **both** | **~386s** | **~133s** |

Browser tier end to end: **4.3x**. Whole suite: **~2.9x**.

## What this uncovered — a real deadlock

Roughly 1 parallel run in 13 hangs and dies at the 120s pytest-timeout. Caught
in `test_collapse_expand.py::test_a_switch_keeps_both_exec_exits_on_the_card`:

```text
node_wrapper.py:649  _housekeeping → with self._lock:      ← blocks forever
   …while Thread-435 holds that lock inside:
validation.py:362    _validate_batch → _notify_subscribers
                     → graph_node.py:124 _on_definition_validated
```

The validation **timer thread** and the main thread acquire
`NodeWrapper._lock` in conflicting orders. The test passes 5/5 serially; only
CPU contention makes the interleaving likely.

This is a product bug, not a test bug, and it can hang a real studio session.
Parallelism did not introduce it — it exposed it. Tracked separately; the
hazard is written into CLAUDE.md so a future hang is not dismissed as xdist
flakiness.

## Order

Slice 1 first: it is mechanical, independently valuable, and its verification
run gives a clean parallel baseline to measure Slice 2 against.
