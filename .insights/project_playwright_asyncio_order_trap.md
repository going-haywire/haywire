---
name: First Playwright test permanently blocks asyncio tests in the same process
description: pytest-playwright's sync API parks a running event loop in the main thread for the rest of the session; any anyio/asyncio test that runs after any browser test fails with "Cannot run the event loop while another loop is running" or "Runner is closed"
type: project
originSessionId: 94f4387e-a8ba-47b9-ac0e-5199af2d3a6f
---
pytest-playwright's **sync** API is greenlet-based: it starts an asyncio event
loop in the main thread and leaves it registered as *running* for as long as the
session-scoped `playwright`/`browser` fixtures live — i.e. until the very end of
the pytest session. From the moment the first browser test runs:

- `asyncio.events._get_running_loop()` in the main thread returns Playwright's
  parked loop.
- Any test that needs its own loop in the main thread — every anyio-marked
  async test (`tests/test_library_manager_hints.py`, `_dry_run`,
  `test_library_operation_progress_modal.py`, …) — fails with
  `RuntimeError: Cannot run the event loop while another loop is running`, or
  `Runner is closed` when anyio's cached runner gets poisoned.

The suite was green only because alphabetical collection happened to run all
async tests **before** `tests/ui/harness/`. Reversing collection order (or any
subset invocation that puts a browser test first) reproduced it deterministically
with just two tests.

**Why:** discovered during a reverse-collection-order stress run of the full
suite (20 failures, all downstream of the first harness test). Minimal repro:
`pytest tests/ui/harness/test_validation.py::test_odd_integer_fails_validator
tests/test_library_manager_hints.py` on the pre-fix tree.

**How to apply:**

1. `tests/conftest.py` enforces the invariant: a tryfirst
   `pytest_collection_modifyitems` auto-applies the `browser` marker to
   everything under `tests/ui/harness/`, and the `_BrowserTestsLast` plugin
   (trylast) sorts browser-marked tests to the END of every run. Do not remove
   either half; the sort is what keeps async tests safe under any ordering.
2. Playwright tests added OUTSIDE `tests/ui/harness/` must carry
   `@pytest.mark.browser` themselves, or they silently re-open this trap.
3. Worker-thread loops (`asyncio.new_event_loop()` inside a `threading.Thread`,
   as in `tests/ui/test_editor_wrapper.py::_run_async`) are unaffected — the
   parked loop only occupies the main thread.
4. `uv run pytest -m "not browser and not perf"` is the fast local loop (~33s);
   it also sidesteps the trap entirely.
