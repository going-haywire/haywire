# Writing and running tests

Commands live in [docs/guides/development.md](../docs/guides/development.md). This file is the why behind them — read it before
writing a test, when a run behaves oddly, when you are changing test infrastructure, or
when you are about to write off a failure as flakiness.

## Tiers

| command | tests | serial | `-n 4` |
| --- | --- | --- | --- |
| `-m "not browser and not perf"` | 5769 | ~250s | ~90s |
| `-m browser` | 135 | ~138s | ~43s |
| `-m unit` | 1252 | ~100s | — |
| everything | 5904 | ~385s | — |

Pick the smallest tier that covers the change. Run the full suite once at the
end, not on every iteration.

The browser tier runs in Chromium only. After touching browser-side input,
clipboard or canvas code, also run it in Firefox once:
`uv run pytest -m browser -n 4 --browser firefox`. Playwright's synthetic input
differs per engine: Firefox's `ClipboardEvent` constructor drops a
`clipboardData` init, and Control+A has no native effect in a field on macOS.
A test that fakes input must hold in both engines.

## Parallelism

Both tiers parallelise with `-n 4` (pytest-xdist). Together that is roughly
386s → 133s.

**The browser tier is safe because each xdist worker gets its own harness
server.** `tests/ui/harness/ports.py` gives each checkout a block of 20 ports
derived from its path, so two worktrees can run the browser tier at once, and
each worker takes the next port in its block (`gw0` → base, `gw1` → base + 1, …).
The fixture passes the port to the subprocess as `HAYWIRE_HARNESS_PORT`. Every
test builds its URL from the `harness` fixture; nothing hardcodes a port. If you add a
harness test, take `harness` as a parameter and build the URL from it — a
hardcoded port will pass alone and send every worker to worker 0's server
under `-n`.

**Stick to `-n 4`.** At `-n 8` the cost-measuring browser tests
(`test_edge_batch_cost`, `test_edge_drag_cost`) intermittently exceed their 30s
Playwright timeout on a loaded box. They measure work per frame, so contention
*is* the failure — there is nothing to fix in the test.

**Never use `--dist loadfile`.** It was tried as the textbook fix for the
shared-directory hazard below and is strictly worse: ~5 failures on every run,
in rotating macro/registry tests, *and* it silently collects fewer tests than
exist (3689–4242 instead of 5769). The default `--dist load` is the working
mode.

### A parallel hang is a real bug, not flakiness

Going parallel surfaced a genuine deadlock — a Subgraph validating on a
background timer while its host validated inline, deadlocking through the
Graph-node card that spans both graphs. It hung ~1 run in 13 and never failed
serially. Fixed 2026-09-23; see
[.insights/project_subgraph_scheduler_deadlock.md](../.insights/project_subgraph_scheduler_deadlock.md).

Keep the lesson: a run that **hangs** to the 120s timeout, rather than
failing, is a lock cycle until proven otherwise. Do not write one off as xdist
flakiness — the suite is the only place this class of bug is currently
observable, and the same cycle can hang a real studio session.

## Validation in tests

Use `force_immediate_validation()` only when the test needs the `ValidationResult`
synchronously, or for a graph left on the default (timer) scheduler. See ADR 0002.

## Test data

A test reads only files inside `tests/` or the `barn/haybale-testing` library, never the
working graphs in `graphs/` or `haystacks/`: those are edited and resaved during normal
work, and a resave silently changes what the test checks. A test that needs a saved graph
gets a frozen copy under `tests/` (for example `tests/core/test_graph/fixtures/`) or
builds it in code.

## Text in tests

A test never pins wording: error and validation messages, hints, tooltips, labels,
placeholders, empty-state text, dialog sentences, CLI and agent-facing prose. Wording is
rewritten whenever a reader misunderstands it, and that must not break the suite. A test
may check:

- that a message exists (non-empty, a notification shown, the exception type);
- the facts it carries: a file path, a node or port name, an id, a count, a value;
- names with a function: a command the user types, a tool or parameter an agent calls,
  an error code, a protocol marker (`STATE:`, `STOP:`), a URI;
- text the test itself supplies (a fixture's description passed through).

For `pytest.raises(ValueError)`, which ruff (PT011) requires a `match=` for, match one of
those facts, never a phrase. To tell two refusals apart, check the state each leaves
behind, or the fact each names.

## Shared mutable state

`tests/studio/test_docs/test_generate.py` rewrites the real
`barn/haybale-testing` in place and restores it with `git checkout` — see
[.insights/project_docs_test_reverts_barn_testing.md](../.insights/project_docs_test_reverts_barn_testing.md)
for what that costs you and why it cannot be redirected to a scratch copy.

For parallelism it is the one genuine shared-resource hazard: workers
regenerating and `git checkout`-ing the same directory. The
`clean_haybale_testing` fixture serializes its users across workers with an
`fcntl` lock in the shared xdist basetemp. Any new test that writes into
`barn/` must take that fixture, or a version-specific assertion
(`test_generate_renders_explicit_version_over_declared`) reads another
worker's QUICKREF.

## Reading a long run

`addopts` includes `-v`, so a full run emits thousands of lines and the tail is
easily buried under the studio's post-run update banner. Redirect, then read
the exit code — that is the actual pass/fail signal:

```sh
uv run pytest -m "not browser and not perf" -q > /tmp/t.log 2>&1; echo "exit=$?"
grep -E "^FAILED|^ERROR" /tmp/t.log            # what broke
grep -E "passed|failed" /tmp/t.log | tail -1   # the summary line
```

Use a timeout ≥ 600000 ms for the full suite. `--durations=25` shows where the
time goes; anything over ~5s in the non-browser suite is worth a look — a 60s
outlier is usually an accidental network call, not real work.

## Waiting

CI runners are heavily loaded: anything a test leaves to the clock fails there
sooner or later. Wait on the thing you are about to assert, never on a duration,
and never assert how long something took:

- `nav.goto_ready(page, url)` — navigate and wait for the client to be
  interactive (`data-hw-synced`). Always use this over `page.goto`.
- `nav.wait_for_canvas_settled(page)` — the canvas centres itself after
  `goto_ready` returns, through a server round trip, which moves every pin.
  A harness canvas stamps `data-hw-fit-done` once the fit has run; this waits
  for the stamp, then for the transform to hold still. Call it before reading
  geometry, instead of sleeping.
- `nav.next_frames(page, n)` — for work the page defers to
  `requestAnimationFrame` (an edge repaint, a cull pass).
- A retrying `expect(locator)` assertion needs no wait in front of it at all.
- `nav.wait_until(page, check)` polls any condition in the browser;
  `tests.ui.user_wait.eventually(check)` does the same on the NiceGUI event loop;
  `tests.wait.wait_until(check)` in a plain test waiting on another thread, a
  timer or a server.

The condition you wait on must be false *before* the action, or the wait returns
at once and the assertion races the app. Check it against the state you start
from: `to_contain_text("set")` already matches `"None|unset"`; a toolbar still up
from the previous selection already passes a visibility wait; a field the browser
scrolled into view is "in view" a frame before the canvas turns that scroll into
a pan. Wait on the whole state the assertion reads. The same holds outside the
browser: a fake file watcher waits for the file's text, not for the file to exist
(`open(path, "x")` creates it empty). See
[.insights/feedback_wait_true_before_the_action.md](../.insights/feedback_wait_true_before_the_action.md).

The other rules:

- **Order, not latency.** To show that A does not wait for B, hold B on a gate the
  test opens after A has finished (the Farmhand stall test holds Block until
  Release reaches it), instead of timing A against B's sleep.
- **Time the code reads, the test controls.** A throttle or a debounce window is
  tested with a patched clock or with timers the test fires itself
  (`test_needs.py`, `test_file_watcher.py`), not by sleeping past the window.
- **A timeout only bounds a failing run.** Make it generous (10 s and more): a
  passing run never waits for it.
- **A fake server records before it answers.** The client can finish and the test
  assert before the server thread runs its next line.

A sleep survives only before a negative assertion ("nothing happens"), where there
is nothing to wait *for*, or where the sleep is itself the work under test. Each
carries a comment saying why. If a sleep genuinely cannot be replaced, keep it and
say why in a comment.
