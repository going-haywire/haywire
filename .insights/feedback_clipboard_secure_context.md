---
name: Clipboard copy buttons are dead on a LAN-exposed studio (secure-context rule)
description: navigator.clipboard is undefined outside a secure context, so every hui copy button silently no-ops over plain HTTP on a LAN IP — and works perfectly on localhost, which is where you test it
type: feedback
---

`hui._copy_button()` (`ui/elements/elements.py`) — used by `hui.info_row()` and
`hui.code_snippet()` — copies with `navigator.clipboard.writeText(...)`. The
Clipboard API is **restricted to secure contexts**. `localhost` and `127.0.0.1`
count as secure even over plain `http://`; a LAN address does not.

So on `http://192.168.1.5:8080` — the studio with `expose_to_network` on —
`navigator.clipboard` is `undefined`, the JS throws inside the browser, and the
button does **nothing**: no copy, no error dialog, no server-side exception, no
log line. The user clicks, sees no feedback, and assumes it worked.

**Why you will not catch this in normal development:** every way you normally
run the studio is a secure context. `uv run haywire` binds `127.0.0.1`,
`ui.run(show=True)` opens `http://localhost:...`, and the Playwright harness in
`tests/ui/harness/` also drives localhost. The bug only exists in the one
deployment you cannot reach from a test — a second machine on the LAN — which
is also the only deployment where authentication (ADR 0027) is in use, and the
place where the token copy button matters most.

**The fix pattern:** feature-detect, fall back, and always confirm.

```js
if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(v);
} else {
    // hidden textarea + execCommand — works in non-secure contexts
    const ta = document.createElement('textarea');
    ta.value = v; ta.style.position = 'fixed'; ta.style.opacity = '0';
    document.body.appendChild(ta); ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
}
```

`document.execCommand('copy')` is deprecated and can itself be refused, so a
fallback alone still fails silently. Pair it with a visible `ui.notify("Copied")`
— this bug's whole character is that failure is indistinguishable from success,
and a confirmation is what makes the difference observable.

**Same trap, other APIs.** The secure-context restriction is not clipboard-
specific: `navigator.mediaDevices` (camera/mic), geolocation, notifications and
service workers all behave identically — present on localhost, absent on a LAN
IP over http. Any feature reaching for one of those needs the same LAN check
before it is called done. Configuring `NetworkSettings.ssl_certfile` /
`ssl_keyfile` makes the studio a secure context and all of them return.
