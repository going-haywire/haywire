# Running the test suite

Commands live in `CLAUDE.md`. This file is the why behind them — read it when a
run behaves oddly, when you are changing test infrastructure, or when you are
about to write off a failure as flakiness.

## Tiers

| command | tests | serial | `-n 4` |
| --- | --- | --- | --- |
| `-m "not browser and not perf"` | 5769 | ~250s | ~90s |
| `-m browser` | 135 | ~138s | ~43s |
| `-m unit` | 1252 | ~100s | — |
| everything | 5904 | ~385s | — |

Pick the smallest tier that covers the change. Run the full suite once at the
end, not on every iteration.

## Parallelism

Both tiers parallelise with `-n 4` (pytest-xdist). Together that is roughly
386s → 133s.

**The browser tier is safe because each xdist worker gets its own harness
server.** `tests/ui/harness/conftest.py` derives the port from
`PYTEST_XDIST_WORKER` (`gw0` → 8090, `gw1` → 8091, …) and passes it to the
subprocess as `HAYWIRE_HARNESS_PORT`. Every test builds its URL from the
`harness` fixture; nothing hardcodes `localhost:8090` any more. If you add a
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

Roughly 1 non-browser run in 13 hangs and dies at the 120s pytest-timeout,
somewhere in `tests/core/test_undo/` or a macro/registry test. That is a
**lock-ordering deadlock in product code**:

```text
node_wrapper.py:649  _housekeeping → with self._lock:      ← blocks forever
   …while the validation timer thread holds it inside:
validation.py:362    _validate_batch → _notify_subscribers
                     → graph_node.py:124 _on_definition_validated
```

The validation timer thread and the main thread take `NodeWrapper._lock` in
conflicting orders. The affected tests pass 5/5 serially; only CPU contention
makes the interleaving likely. Parallelism exposed this, it did not cause it,
and it can hang a real studio session. Do not dismiss such a hang.

## Shared mutable state

`tests/studio/test_docs/test_generate.py` rewrites the real
`barn/haybale-testing` in place and restores it with `git checkout` — see
[.insights/project_docs_test_reverts_barn_testing.md](../.insights/project_docs_test_reverts_barn_testing.md)
for what that costs you and why it cannot be redirected to a scratch copy.

For parallelism it is the one genuine shared-resource hazard: a repo-wide
`git checkout` on a working tree other workers are reading. It is confined to
that single file and has not been observed to bite, but it is the first
suspect if a docs test starts failing only under `-n`.

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

## Waiting in browser tests

Fixed sleeps were cut from 45s to 20s across the harness tests. When adding a
test, wait on the thing you are about to assert, not on a duration:

- `nav.goto_ready(page, url)` — navigate and wait for the client to be
  interactive (`data-hw-synced`). Always use this over `page.goto`.
- `nav.wait_for_canvas_settled(page)` — the canvas centres itself after
  `goto_ready` returns, which moves every pin. Call this before reading
  geometry, instead of sleeping.
- A retrying `expect(locator)` assertion needs no wait in front of it at all.

Three sleeps survive deliberately, each with a comment saying why. Two are at
`[data-testid="rekey"]`, which remounts the canvas: `_wait_for_all_edges` is
satisfied by the edges still on screen from *before* the remount, so removing
the sleep measures geometry mid-remount (it failed 3/3). Nothing observable
marks that teardown. The third precedes a negative assertion, where there is
nothing to wait *for* and the wait is what gives a wrong edge time to appear.

If a sleep genuinely cannot be replaced, keep it and say why in a comment.
