---
status: implemented
slice: 6 of 6
feature: studio-authentication
adr: docs/adr/0027-studio-authentication.md
previous: none — independent of the chain
next: none — but land this BEFORE slice 5's Task 4
---

# Slice 6 — Clipboard secure-context fix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every `hui` copy button work on a LAN-exposed studio over plain HTTP, and make a failed copy visible instead of silent.

**Architecture:** One shared helper in the design system, fixed once. `_copy_button` currently calls `navigator.clipboard.writeText` unconditionally; the Clipboard API is restricted to secure contexts, so it is `undefined` on `http://192.168.1.5:8080` and the click silently does nothing.

**Tech Stack:** NiceGUI, `ui.run_javascript`. No new dependencies.

## Chain position

- **Independent of the auth chain.** It touches no auth code and can run at any point.
- **But land it before Slice 5 Task 4.** The roster UI hands an agent token over with a copy button, and the LAN studio is exactly the deployment where authentication is used. Shipping that button dead would mean the feature does not work where it matters.
- It is a **pre-existing bug**, not one this feature introduces — every `hui.info_row()` and `hui.code_snippet()` copy button in the studio is already affected. That is why it gets its own slice and its own commit rather than being buried in an auth change.

## Chain protocol

1. **Task 0** affirms current state. There is no previous slice to reconcile against.
2. **The final task** fills in this document's Drift Log and flips `status:` to `implemented`.

## Global Constraints

- Line length 109; `ruff check` **and** `ruff format --check` must both pass.
- Full `mypy` command must pass.
- **No new dependencies.**
- The fix must not change the copy button's appearance or its `hui` call signature — every existing call site keeps working untouched.

---

### Task 0: Affirm current state

- [x] **Step 1: Read the insight**

Read `.insights/feedback_clipboard_secure_context.md` — it documents the trap, why local testing never catches it, and the fix pattern.

- [x] **Step 2: Confirm the bug is still there**

```bash
grep -n "navigator.clipboard" packages/haywire-core/src/haywire/ui/elements/elements.py
```

Expected: one hit inside `_copy_button`, with no `isSecureContext` check and no fallback. If it already has one, this slice has been done — reconcile and stop.

- [x] **Step 3: Confirm the call sites**

```bash
grep -n "_copy_button" packages/haywire-core/src/haywire/ui/elements/elements.py
```

Expected: the definition plus two callers (`info_row`, `code_snippet`). If there are more, they all benefit — note the count in the Drift Log.

- [x] **Step 4: Baseline clean**

```bash
uv run ruff check packages/haywire-core/src/haywire/ui/elements/ && uv run mypy packages/haywire-core/src/
```

---

### Task 1: Extract and fix the clipboard script

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/elements/elements.py`
- Test: `tests/ui/test_clipboard_script.py`

**Interfaces:**
- Produces: `clipboard_script(value: str) -> str` — a pure function returning the JS, so the branching logic is unit-testable without a browser; `_copy_button` unchanged in signature and appearance.

- [x] **Step 1: Write the failing test**

Create `tests/ui/test_clipboard_script.py`:

```python
"""The clipboard script must work outside a secure context (LAN studio over http)."""

import json

import pytest

from haywire.ui.elements.elements import clipboard_script


def test_prefers_the_clipboard_api_in_a_secure_context():
    script = clipboard_script("hello")
    assert "navigator.clipboard" in script
    assert "isSecureContext" in script


def test_falls_back_to_exec_command():
    """The whole point: navigator.clipboard is undefined on a LAN IP over http."""
    script = clipboard_script("hello")
    assert "execCommand" in script
    assert "textarea" in script.lower()


def test_returns_a_boolean_so_the_caller_can_report_failure():
    script = clipboard_script("hello")
    assert "return true" in script
    assert "return false" in script


def test_removes_the_temporary_element_again():
    assert "removeChild" in clipboard_script("hello")


@pytest.mark.parametrize(
    "value",
    [
        "plain",
        "with 'single' quotes",
        'with "double" quotes',
        "with\nnewline",
        "with </script> tag",
        "with \\ backslash",
        "with `backtick` and ${template}",
        "",
    ],
)
def test_value_is_json_encoded_not_interpolated(value):
    """A token or a path could contain anything — never build JS by concatenation."""
    script = clipboard_script(value)
    assert json.dumps(value) in script


def test_a_quote_in_the_value_cannot_break_out_of_the_string():
    script = clipboard_script('"; alert(1); //')
    assert "alert(1)" not in script.replace(json.dumps('"; alert(1); //'), "")
```

- [x] **Step 2: Run it**

Run: `uv run pytest tests/ui/test_clipboard_script.py -v`
Expected: FAIL — `ImportError: cannot import name 'clipboard_script'`

- [x] **Step 3: Write the implementation**

In `packages/haywire-core/src/haywire/ui/elements/elements.py`, add above `_copy_button`:

```python
def clipboard_script(value: str) -> str:
    """JS that copies ``value``, returning ``true`` on success.

    ``navigator.clipboard`` is restricted to **secure contexts**. ``localhost``
    and ``127.0.0.1`` qualify even over plain ``http://``; a LAN address does
    not. So on a studio reached at ``http://192.168.1.5:8124`` — the exposed
    deployment, the one where copying an agent token actually matters — the
    Clipboard API is ``undefined``, the click throws inside the browser, and
    the user sees no copy, no error and no log line.

    You will not catch this locally: ``uv run haywire`` binds 127.0.0.1,
    ``ui.run(show=True)`` opens ``localhost``, and the Playwright harness drives
    localhost too. Every development path is a secure context.

    The fallback is a hidden ``<textarea>`` plus ``document.execCommand('copy')``,
    which still works outside a secure context. It is deprecated and can itself
    be refused, which is why this returns a boolean rather than assuming success
    — see :func:`_copy_button`, which reports the result.

    The value is JSON-encoded, never interpolated: it may be a token, a
    filesystem path, or arbitrary source text containing quotes and newlines.
    """
    encoded = _json.dumps(value)
    return f"""(function () {{
    const text = {encoded};
    if (navigator.clipboard && window.isSecureContext) {{
        navigator.clipboard.writeText(text);
        return true;
    }}
    try {{
        const area = document.createElement('textarea');
        area.value = text;
        area.setAttribute('readonly', '');
        area.style.position = 'fixed';
        area.style.top = '-1000px';
        document.body.appendChild(area);
        area.select();
        const ok = document.execCommand('copy');
        document.body.removeChild(area);
        return ok;
    }} catch (error) {{
        return false;
    }}
}})()"""
```

- [x] **Step 4: Run it**

Run: `uv run pytest tests/ui/test_clipboard_script.py -v`
Expected: PASS, 14 tests.

- [x] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/elements/elements.py tests/ui/test_clipboard_script.py
git commit -m "fix(ui): clipboard copy falls back outside a secure context"
```

---

### Task 2: Report the result

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/elements/elements.py`
- Test: `tests/ui/test_copy_button.py`

**Interfaces:**
- Produces: `_copy_button` with an async handler that awaits `run_javascript` and notifies on both outcomes.

**Why the notify is not optional:** this bug's whole character is *silence* — it looks like it worked. A fallback with no confirmation just moves the silent failure one level down, since `execCommand` is deprecated and can be refused.

- [x] **Step 1: Write the failing test**

Create `tests/ui/test_copy_button.py`:

```python
"""_copy_button reports success and failure rather than failing silently."""

import inspect

import pytest


def test_handler_is_async_so_it_can_await_the_result():
    """A fire-and-forget handler cannot know whether the copy worked."""
    from haywire.ui.elements import elements

    source = inspect.getsource(elements._copy_button)
    assert "async def" in source


def test_handler_notifies_on_both_outcomes():
    from haywire.ui.elements import elements

    source = inspect.getsource(elements._copy_button)
    assert source.count("ui.notify") >= 2


def test_failure_message_names_the_cause():
    """A user on a LAN studio should learn WHY, not just that it failed."""
    from haywire.ui.elements import elements

    source = inspect.getsource(elements._copy_button)
    assert "HTTPS" in source or "secure" in source.lower()


@pytest.mark.anyio
async def test_copy_handler_notifies_success(monkeypatch):
    from haywire.ui.elements import elements

    notified = []
    monkeypatch.setattr(elements.ui, "notify", lambda message, **kw: notified.append((message, kw)))

    async def _fake_run_javascript(script, **kwargs):
        return True

    monkeypatch.setattr(elements.ui, "run_javascript", _fake_run_javascript)

    button = elements._copy_button("secret")
    handler = button._event_listeners  # NiceGUI stores handlers here
    await elements._perform_copy("secret")

    assert notified and "Copied" in notified[0][0]


@pytest.mark.anyio
async def test_copy_handler_notifies_failure(monkeypatch):
    from haywire.ui.elements import elements

    notified = []
    monkeypatch.setattr(elements.ui, "notify", lambda message, **kw: notified.append((message, kw)))

    async def _fake_run_javascript(script, **kwargs):
        return False

    monkeypatch.setattr(elements.ui, "run_javascript", _fake_run_javascript)

    await elements._perform_copy("secret")

    assert notified
    assert notified[0][1].get("type") == "negative"
```

**Note:** the `button._event_listeners` line above is illustrative of NiceGUI internals and brittle. When implementing, delete that line and test `_perform_copy` directly — it is the seam that exists precisely so the behaviour is testable without touching NiceGUI internals. Record the deletion in the Drift Log.

- [x] **Step 2: Run it**

Run: `uv run pytest tests/ui/test_copy_button.py -v`
Expected: FAIL — the handler is a sync lambda and there is no `_perform_copy`.

- [x] **Step 3: Write the implementation**

Replace `_copy_button` in `packages/haywire-core/src/haywire/ui/elements/elements.py`:

```python
async def _perform_copy(value: str) -> None:
    """Run the clipboard script and tell the user what happened.

    Separate from the button so the outcome handling is testable without
    driving a browser — and because the failure path is the one that matters
    and is the hardest to reach in a test environment (every local run is a
    secure context).
    """
    try:
        copied = await ui.run_javascript(clipboard_script(value))
    except Exception:
        copied = False

    if copied:
        ui.notify("Copied to clipboard")
    else:
        ui.notify(
            "Could not copy — your browser blocks clipboard access on this "
            "connection. Select the text and copy it manually, or serve the "
            "studio over HTTPS.",
            type="negative",
        )


def _copy_button(value: str) -> ui.button:
    """Small copy-to-clipboard button used internally by info_row and code_snippet.

    The click handler is async and awaits the result: a silent no-op is this
    feature's known failure mode outside a secure context (see
    ``clipboard_script``), so the outcome is always reported.
    """

    async def _on_click(_event=None, _value: str = value) -> None:
        await _perform_copy(_value)

    return (
        ui.button(icon=AppIcon.copy, on_click=_on_click)
        .props("flat round dense size=xs")
        .tooltip("Copy to clipboard")
    )
```

**Check before writing:** `.insights/feedback_nicegui_async.md` records that `asyncio.ensure_future()` breaks `ui.notify()` — the handler must be awaited by NiceGUI, not scheduled. An `async def` passed to `on_click` is the supported form. Do **not** wrap it in `ensure_future`.

- [x] **Step 4: Fix the test file**

Delete the brittle `button._event_listeners` line flagged in Step 1 and keep the direct `_perform_copy` tests.

- [x] **Step 5: Run it**

Run: `uv run pytest tests/ui/test_copy_button.py -v`
Expected: PASS.

- [x] **Step 6: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/elements/elements.py tests/ui/test_copy_button.py
git commit -m "fix(ui): copy button reports success or failure instead of failing silently"
```

---

### Task 3: Browser regression test

**Files:**
- Test: `tests/ui/harness/test_copy_button_browser.py`

**Scope note:** the harness runs on localhost, which **is** a secure context, so this proves the happy path and that the async handler is wired correctly — it cannot exercise the fallback. The fallback is covered by the unit tests in Task 1 and by manual verification in Task 4. Say so in the test's docstring so a future reader does not mistake it for full coverage.

- [x] **Step 1: Read an existing harness test** in `tests/ui/harness/` to match the fixture and `goto_ready` idiom (`.insights/feedback_nicegui_outbox_updatevalue_stomp.md` — pages stamp `data-hw-synced` last; tests use `goto_ready`).

- [x] **Step 2: Write the test**, mounting a page with `hui.code_snippet("copy-me")`, clicking the copy button, and asserting a notification appears. Use `find(kind=..., content=...)` if using the NiceGUI user simulation — `user.find("Text", kind=ui.button)` silently ignores `kind` (`.insights/feedback_nicegui_user_simulation_find.md`).

- [x] **Step 3: Run it**

Run: `uv run pytest tests/ui/harness/test_copy_button_browser.py -v`
Expected: PASS.

- [x] **Step 4: Commit**

```bash
git add tests/ui/harness/test_copy_button_browser.py
git commit -m "test(ui): browser regression for the copy button"
```

---

### Task 4: Manual verification on a non-secure context

This is the only step that actually exercises the bug being fixed. It needs a second device or a LAN IP.

- [x] **Step 1: Expose the studio**

Set `expose_to_network` to `True` in the studio's network settings, leave `ssl_certfile`/`ssl_keyfile` empty, and start it:

```bash
uv run haywire --no-browser
ipconfig getifaddr en0    # macOS: your LAN address
```

- [x] **Step 2: Open `http://<lan-ip>:8124/` from another device** on the same network (or from a browser profile that resolves the LAN IP rather than localhost).

- [x] **Step 3: Find any `info_row` or `code_snippet`** — the Properties editor's component info rows are the easiest — and click its copy button.

Expected **after this fix**: the text is on the clipboard and a "Copied to clipboard" notification appears.
Expected **before this fix** (worth confirming once on `git stash`, to be sure the fix is real): nothing at all happens.

- [x] **Step 4: Restore** `expose_to_network` to `False`.

- [x] **Step 5: Record the result in the Drift Log** — including "could not test, no second device available", if that is the truth. An untested fallback is a known risk, not a silent one.

---

### Task 5: Quality gate

- [x] **Step 1:** `uv run ruff check . && uv run ruff format --check .`
- [x] **Step 2:** full mypy command from CLAUDE.md.
- [x] **Step 3:**

```bash
uv run pytest -m "not browser and not perf" -q > /tmp/slice6.log 2>&1; echo "exit=$?"
grep -E "^FAILED|^ERROR" /tmp/slice6.log
```

- [x] **Step 4:** browser tests — `elements.py` is used everywhere:

```bash
uv run pytest tests/ui/harness/ -q > /tmp/slice6-browser.log 2>&1; echo "exit=$?"
```

- [x] **Step 5:** commit fixes.

---

### Task 6 (final): Record delivery and drift

- [x] **Step 1: Fill in the Drift Log** — one line per deviation, or "No drift." explicitly. Include whether Task 4's LAN verification was actually performed.
- [x] **Step 2: Update `.insights/feedback_clipboard_secure_context.md`** — it currently describes the bug in the present tense. Rewrite the opening so it describes the *rule* and points at `clipboard_script` as the fixed implementation, keeping the "why you will not catch this locally" reasoning, which stays true for every future secure-context feature (camera, mic, geolocation).
- [x] **Step 3: Flip `status:` to `implemented`.**
- [x] **Step 4: Commit**

```bash
git add .insights/ docs/superpowers/plans/2026-08-15-auth-6-clipboard-secure-context.md
git commit -m "docs(plan): slice 6 complete — clipboard secure-context fix"
```

---

## Delivered

- `clipboard_script(value: str) -> str` (`packages/haywire-core/src/haywire/ui/elements/elements.py`) — pure function producing JS that prefers `navigator.clipboard` in a secure context and falls back to a hidden `<textarea>` + `document.execCommand('copy')` outside one, returning `true`/`false`. Value is JSON-encoded, never interpolated.
- `_perform_copy(value: str) -> None` — awaits `ui.run_javascript(clipboard_script(value))` and calls `ui.notify()` on both outcomes; the failure message names HTTPS/secure so the user learns why, not just that it failed.
- `_copy_button` — click handler is now `async def`, calling `_perform_copy` directly (never wrapped in `ensure_future`, per `.insights/feedback_nicegui_async.md`). Signature and appearance unchanged; `info_row` and `code_snippet` callers work untouched.
- Unit tests: `tests/ui/test_clipboard_script.py` (13 cases), `tests/ui/test_copy_button.py` (5 cases).
- Browser regression: `tests/ui/harness/test_copy_button_browser.py`, proving the happy path (secure-context Clipboard API branch) end-to-end; a new minimal `/copy-button` route was added to `tests/ui/harness/routes.py` to give it something to click.
- `.insights/feedback_clipboard_secure_context.md` rewritten to describe the rule and point at `clipboard_script` as the fix, keeping the "why you won't catch this locally" reasoning for future secure-context features.
- Manually verified on a real LAN-exposed studio (`expose_to_network=True`, plain HTTP, second device/LAN-IP profile): the `execCommand` fallback engages and "Copied to clipboard" is reported correctly — the fix is confirmed on the one deployment that could never be exercised by a test.

## Drift Log

- Task 1: the brief's Step 4 said "Expected: PASS, 14 tests"; the actual, correct count is 13 (the brief undercounted its own parametrize block by one). Verified as a brief arithmetic error, not a missing test — the test file is a verbatim match of the brief's Step 1 code.
- Task 2: the brief's `test_handler_notifies_on_both_outcomes` test (Step 1) inspects `_copy_button`'s source for `ui.notify`, but the brief's own Step 3 implementation puts both `ui.notify` calls in `_perform_copy`, not `_copy_button` (which only calls `_perform_copy`). Retargeted that one assertion to inspect `_perform_copy` instead, preserving the substantive requirement. Verified against the diff by the task reviewer.
- Task 3: the brief listed only `tests/ui/harness/test_copy_button_browser.py` under Files, but no existing harness route mounted a bare `hui` element to click against. Added a minimal `/copy-button` route to `tests/ui/harness/routes.py`, structurally consistent with sibling routes. Verified necessary (no pre-existing route touches `hui` directly) and minimal by the task reviewer.
- Task 4: performed. LAN verification confirmed the fix works — `expose_to_network=True`, plain HTTP, tested from a second device/LAN-IP browser profile; the `execCommand` fallback engaged and the "Copied to clipboard" notification appeared correctly.
- No other drift. All Global Constraints held: line length 109, `ruff check` + `ruff format --check` clean, full mypy command clean, no new dependencies, `_copy_button`'s appearance and call signature unchanged throughout.
