---
name: Assert order, not latency
description: A test that times A against B's sleep ("echo returns in < 1.0 s while block sleeps 1.5 s") fails on a loaded runner without any bug. Hold B on a gate the test opens after A finished; drive throttles and debounces with a clock or timers the test controls.
type: feedback
---

# Assert order, not latency

A wall-clock bound in a test measures the runner as much as the code. On a busy CI runner
a call that takes 5 ms locally takes over a second, so `assert elapsed < 1.0` fails with no
bug behind it, and a generous bound stops proving anything.

Read the numbers before calling it a stall: an elapsed time measured from before B started
that is still shorter than B's sleep means A returned while B was running, so B did not
hold it up; the runner was slow.

What to do instead:

- **To show A does not wait for B**, hold B until the test releases it after A has
  finished: the testing library's Block tool waits on a gate the Release tool opens. A
  server that stalls serves Release only after Block gives up, so the test fails for a
  stall and for nothing else.
- **A throttle or debounce window** is driven by a patched clock or by timers the test
  fires itself, not by sleeping past it.
- **A rate** is checked as order and count (each delivery after the previous, none early),
  not as deliveries per second.
- **A timeout** only bounds a failing run: 10 s and more, never the thing asserted.

Uniform CPU load rarely reproduces these. Delaying the one call the test races (a
monkeypatched sleep, a delayed server handler) does, deterministically.
