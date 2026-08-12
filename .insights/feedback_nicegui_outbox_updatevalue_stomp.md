---
name: NiceGUI client-side timing races — outbox flush stomps early input, and autofocus into a not-yet-mounted element
description: Two distinct client-side timing gotchas that both look like flakiness — updateValue messages queued during server-side render flush only after websocket connect and can revert a user's edit; and autofocus attributes silently no-op on elements that don't exist at DOM-ready time
type: feedback
originSessionId: 94f4387e-a8ba-47b9-ac0e-5199af2d3a6f
---

## 1. Outbox flush stomps early user input after page load

When a NiceGUI page assigns values to value-elements (`ui.input` etc.) during
server-side render, each assignment queues a `run_method('updateValue')`
message in the client's outbox. Those messages can only be delivered once the
websocket connects — i.e. *after* the DOM is already visible and interactive.

The race, captured via Playwright websocket-frame logging on
`tests/ui/harness/test_validation.py`:

1. Browser renders; user (or test) types into an input and commits — the
   client emits the new value; the server processes it (e.g. creates a
   validation error element).
2. The queued `updateValue` for that element arrives a few ms later and stomps
   the input back to the render-time server value.
3. The stomp fires the input's `update:value` listener, so the client sends
   the OLD value back — the server reverts the edit and destroys the reaction
   from step 1 (the error element flashes into existence and vanishes).

Symptom in tests: `expect(locator).to_be_visible()` times out even though the
interaction "worked"; the input shows its original value in the failure dump.
Looks exactly like a timing flake (~50% standalone failure rate) but is fully
deterministic once the frame ordering is visible. `wait_for_selector` does NOT
protect against it (DOM ≠ flushed outbox), and neither does waiting for
`window.socket.connected` or `window.did_handshake` (the flush trails both).

**Why:** diagnosed the "flaky" `test_string_field_valid_clears_error` this way;
two earlier wait-strategies (socket.connected, did_handshake) reduced but did
not eliminate the failures, frame capture found the real mechanism.

**How to apply:**

1. Server→client messages are delivered in FIFO order, so a marker queued as
   the LAST message of the page build is guaranteed to execute after every
   pending `updateValue`. Every harness page calls `routes._stamp_synced()`
   (queues `document.body.dataset.hwSynced = '1'`) at the end of its build;
   tests navigate with `nav.goto_ready(page, url)` which waits for the stamp.
2. New harness pages MUST call `_stamp_synced()` last, or `goto_ready` hangs
   on them (a loud failure — by design).
3. This is a real (if tiny-window) product race too: a user who types within
   the connect-flush window loses the edit. If it ever bites in the studio,
   the same ordered-marker technique applies.

## 2. Autofocus into a dynamically-shown container silently no-ops

HTML `autofocus` and `.props("autofocus")` do NOT work for inputs inside
dynamically shown containers (popups, dialogs) because the element is not
present/visible at DOM-ready time — a different mechanism from the outbox
race above (no server message involved), but the same family of "the client
wasn't ready when the naive approach ran."

**Working solution** — implemented as `autofocus=True` on `hui.input_field()`:

```python
def _focus_search():
    ui.run_javascript(f'document.getElementById("c{search_input.id}")?.focus();')
ui.timer(0.1, _focus_search, once=True)
```

The 0.1s timer lets the popup finish rendering before the JS focus call. The
`?.` null-safe operator prevents the "can't access property focus" error that
fires if the timer runs before the element is mounted.

**Gotcha:** the element ID is `c{element.id}` (NiceGUI prefixes the numeric id
with `c`) — `document.getElementById(str(el.id))` won't find it.

**How to apply:** use `hui.input_field(autofocus=True, ...)` for any
search/input that should auto-focus when a popup opens. Implemented in
`hui.input_field()` in `haywire/ui/elements/elements.py`.
