---
name: NiceGUI user_simulation — find() ignores kind when given a positional string
description: Two traps that make User-simulation clicks silently do nothing, and how to read client state from the test driver
type: feedback
---

`nicegui.testing.User` + `user_simulation()` gives real rendering without a
browser (fast `@pytest.mark.unit` tier, no Playwright, no
`.insights/project_playwright_asyncio_order_trap.md` ordering hazard). Two
things about it cost a debugging session each.

## 1. `user.find("Text")` matches every element kind, and `kind=` is ignored

`User._gather_elements` branches on the FIRST POSITIONAL argument:

```python
elif isinstance(target, str):
    elements = set(ElementFilter(marker=target, only_visible=True)) \
        .union(ElementFilter(content=target, only_visible=True))
```

`kind` is not consulted on that branch at all. So `user.find("Check", kind=ui.button)`
still returns labels, tooltips, and the button. Then
`UserInteraction.click()` picks `min(enabled_elements, key=lambda e: e.id)` —
the **lowest element id**, i.e. whichever matching element was created
earliest. A step title (`"Check the project"`) or a description label
(`"Checks that your working tree is clean…"`) is created before the button,
so the click lands on a `Label` and **silently does nothing** — no error, the
handler simply never fires.

Filter by passing keywords with NO positional target:

```python
user.find(kind=ui.button, content="Check").click()   # correct
user.find("Check", kind=ui.button).click()           # WRONG — matches labels too
```

## 2. Reading client state from the test body needs `user._client`

`ui.context.client` resolves through the current asyncio task's slot stack,
which is empty in the test driver itself — it raises
`RuntimeError: The current slot cannot be determined…`. Use the client the
`User` already holds:

```python
client = user._client            # no public accessor exists
sum(1 for e in client.elements.values() if isinstance(e, ui.dialog) and e.value)
```

## Also worth knowing

- `should_see(..., retries=N)` defaults to 3 × 0.1s. A step that runs work in
  `asyncio.to_thread` (a `git` subprocess, say) can outlast that — raise
  `retries`.
- Driving the state machine directly (`await wizard.advance_from_x()`) skips
  the `rerender()` that `busy_advance` runs after the coroutine, so the DOM
  never updates. To assert on rendered output, click the real button.

**Why:** Both failures present identically — the assertion fails and the dumped
DOM shows the pre-click UI, with nothing to indicate the click was swallowed
or that the handler never ran.
**How to apply:** In `user_simulation` tests, always select buttons with
`find(kind=ui.button, content=...)`, and drive flows through clicks rather
than calling `advance_*` directly when the assertion is about the DOM.
See `tests/test_share_wizard_precondition_modal.py`.
