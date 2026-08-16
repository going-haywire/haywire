---
name: Clipboard copy buttons are dead on a LAN-exposed studio (secure-context rule)
description: "FIXED — clipboard_script() falls back to execCommand, so copy buttons DO work over LAN http. Do not cite ANY secure-context symptom as a current consequence of plain HTTP: the clipboard is fixed, and camera/mic never applied (Haywire captures server-side in Python). The rule only bites a future front-end feature."
type: feedback
---

> **Status: fixed.** The fallback described under *The fix, as implemented*
> has landed and is verified on a real LAN-exposed studio. Copy buttons work
> over `http://<lan-ip>`. Everything above that section is the *original bug*,
> kept for the rule it teaches — do not quote it as current behaviour.
>
> **Do not substitute another symptom either.** Camera and microphone look
> like the natural replacement and are wrong: Haywire grabs video *server-side*
> in Python (`cv2.VideoCapture`, `depthai`), so `navigator.mediaDevices` is
> never called and no browser permission is involved. As of today **no shipped
> Haywire feature is broken by plain HTTP** — the only real consequence is that
> traffic is readable on the wire. The secure-context rule is worth knowing
> because it will bite the first front-end feature that reaches for
> `mediaDevices`, geolocation, notifications or a service worker; it is not a
> present-tense symptom to warn users about.

**The rule:** the Clipboard API (`navigator.clipboard`) is **restricted to
secure contexts**. `localhost` and `127.0.0.1` count as secure even over plain
`http://`; a LAN address does not. On `http://192.168.1.5:8080` —  a studio
with `expose_to_network` on — `navigator.clipboard` is `undefined`. Any code
that reaches for it unconditionally throws inside the browser and fails
**silently**: no copy, no error dialog, no server-side exception, no log line.
The user clicks, sees no feedback, and assumes it worked.

**Why you will not catch this in normal development:** every way you normally
run the studio is a secure context. `uv run haywire` binds `127.0.0.1`,
`ui.run(show=True)` opens `http://localhost:...`, and the Playwright harness in
`tests/ui/harness/` also drives localhost. The bug only shows up in the one
deployment you cannot reach from a test — a second machine on the LAN — which
is also the deployment where authentication (ADR 0027) is in use, and the
place where the agent-token copy button matters most.

**The fix, as implemented:** `clipboard_script()` in
`packages/haywire-core/src/haywire/ui/elements/elements.py` builds the JS for
every `hui` copy button (`hui.info_row()`, `hui.code_snippet()`, and anything
using `_copy_button()`). It feature-detects `navigator.clipboard &&
window.isSecureContext`; when absent it falls back to a hidden `<textarea>` +
`document.execCommand('copy')`, which still works outside a secure context.
The script returns a boolean rather than assuming success — `execCommand` is
itself deprecated and can be refused — and `_perform_copy()` awaits that
result and calls `ui.notify()` on both branches, naming HTTPS/secure in the
failure message. This bug's whole character was that failure looked identical
to success; the confirmation is what makes the difference observable.
Verified against a real LAN-exposed studio: the fallback engages and the
button now reports success correctly.

**Same trap, other APIs.** The secure-context restriction is not clipboard-
specific: `navigator.mediaDevices` (camera/mic), geolocation, notifications and
service workers all behave identically — present on localhost, absent on a LAN
IP over http. Any feature reaching for one of those needs the same LAN check
before it is called done. Configuring `NetworkSettings.ssl_certfile` /
`ssl_keyfile` makes the studio a secure context and all of them return.

**The fix is one command.** `haywire ssl setup` generates a self-signed
certificate covering this machine's names and writes both settings; restart and
the LAN origin is secure, clipboard included. Clicking through the browser's
first-visit warning is enough to earn secure-context status — `haywire ssl
trust` removes the warning itself. `haywire ssl status` reports whether TLS is
on and, when it is, whether the address you are actually reachable at is one
the certificate covers. See `docs/guides/network_config.md` §9.
