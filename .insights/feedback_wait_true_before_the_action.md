---
name: A test wait already true before the action
description: A test that fails once and passes on re-run is most often waiting on a condition the state before the action already satisfies, so the wait returns at once and the assertion races the app. Four forms seen in this suite, and how to check a wait.
type: feedback
---

# A test wait that is already true before the action

A wait only helps if its condition is false until the action has taken effect. When the
state the test starts from already satisfies it, the wait returns at once and the
assertion races the app: it passes on a fast machine and fails on a busy CI runner,
usually macOS, then passes on re-run.

Forms seen in this suite:

- **A substring of the old text.** `expect(echo).to_contain_text("set")` matches the
  unset echo `"None|unset"`. Wait for the whole new text (`to_have_text`, an anchored
  regex).
- **An element that is already there.** After a first click the selection toolbar is
  visible, so `wait_for_selector(toolbar)` after a second click returns before the
  toolbar re-renders. Wait for the content that changes.
- **Half of a two-step update.** On Tab, the browser scrolls the focused field into view
  and the canvas container turns that scroll into a pan on the next scroll event,
  about 3 ms later. "Focused and in view" holds in between, with the container still
  scrolled. Wait for the whole end state, including `scroll == [0, 0]`.
- **A file that exists before it is written.** `open(path, "x")` and `write_text()`
  create the file empty. A fake watcher that fires on `path.exists()` makes the
  registry import an empty module. Wait for the file's text.

Fixed sleeps fail the same way: `asyncio.sleep(FLYOUT_OPEN_DELAY_S + 0.08)` before
asserting a `ui.timer` has fired holds only while the event loop keeps up. Poll for the
state instead (`nav.wait_until`, `tests.ui.user_wait.eventually`).

**How to check a wait:** evaluate its condition against the state just before the action.
If it is already true, the wait does nothing. To show a suspected race, record the
intermediate state in the page (a capture-phase listener that logs values with
`performance.now()`), or widen the window from a scratch pytest plugin (delay a write,
force a thread switch). Uniform CPU load and Chromium CPU throttling rarely reproduce
these on Linux.

A real-time loop has a related trap: only its lower bound is exact. A paced pump never
delivers early, but a busy runner can deliver any block late, so an assertion with a
tight upper bound on wall-clock time fails under load.
