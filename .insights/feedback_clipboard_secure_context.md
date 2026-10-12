---
name: Clipboard copy buttons are dead on a LAN-exposed studio (secure-context rule)
description: "FIXED for copy — clipboard_script() falls back to execCommand, so hui copy buttons and graph copy DO work over LAN http; graph keyboard paste reads the native paste event. One gap: the graph context menu's Paste calls readText(), which is absent on a LAN — it pastes only from the session mirror (same-tab copies). Camera/mic never applied (Haywire captures server-side in Python)."
type: feedback
---

> **Status: fixed for copy; one paste path still LAN-limited.** The fallback
> described under *The fix, as implemented* has landed and is verified on a
> real LAN-exposed studio. Copy buttons work over `http://<lan-ip>`. Everything
> above that section is the *original bug*, kept for the rule it teaches — do
> not quote it as current behaviour. The scope of "fixed" is spelled out under
> *Graph clipboard paths* below.
>
> **Do not substitute another symptom either.** Camera and microphone look
> like the natural replacement and are wrong: Haywire grabs video *server-side*
> in Python (`cv2.VideoCapture`, `depthai`), so `navigator.mediaDevices` is
> never called and no browser permission is involved. As of today the **only
> shipped feature plain HTTP limits is the graph context menu's Paste**, which
> on a LAN origin pastes only what this tab copied (see *Graph clipboard paths*);
> every copy path and keyboard paste work. Beyond that, the real consequence is
> that traffic is readable on the wire. The secure-context rule is worth knowing
> because it will bite the first front-end feature that reaches for
> `mediaDevices`, geolocation, notifications or a service worker.

**The rule:** the Clipboard API (`navigator.clipboard`) is **restricted to
secure contexts**. `localhost` and `127.0.0.1` count as secure even over plain
`http://`; a LAN address does not. On `http://192.168.1.5:8080` —  a studio
exposed to the network (`haywire network expose`, ADR 0028) — `navigator.clipboard`
is `undefined`. Any code that reaches for it unconditionally throws inside the
browser and fails **silently**: no copy, no error dialog, no server-side
exception, no log line. The user clicks, sees no feedback, and assumes it
worked.

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

**Graph clipboard paths.** The fix above covers every `hui` copy button.
The graph editor's clipboard has three paths, and only one still depends on
a secure context:

- **Copy** (keyboard and menu) writes through `clipboard_script()` too, so
  it inherits the fallback.
- **Keyboard paste** (`Mod+V`) never calls the Clipboard API: the keymap
  listener lets the keydown through and reads `clipboardData` off the
  browser's native `paste` event, which every context delivers.
- **Context-menu Paste** calls `navigator.clipboard.readText()`
  (`_handleClipboardPasteRequest` in `canvas.vue`). On a LAN origin that
  throws, the handler sends empty text, and the paste falls back to the
  session mirror — so it pastes what this tab copied, but never text copied
  in another tab or process. No `execCommand('paste')` fallback exists for
  reading.

**Same trap, other APIs.** The secure-context restriction is not clipboard-
specific: `navigator.mediaDevices` (camera/mic), geolocation, notifications and
service workers all behave identically — present on localhost, absent on a LAN
IP over http. Any feature reaching for one of those needs the same LAN check
before it is called done. Configuring `NetworkSettings.ssl_certfile` /
`ssl_keyfile` makes the studio a secure context and all of them return.

**The fix is one command.** `haywire ssl setup` generates a self-signed
certificate covering this machine's names and writes the certificate/key paths
into `~/.haywire/security.json`; restart and the LAN origin is secure,
clipboard included. Clicking through the browser's first-visit warning is
enough to earn secure-context status — `haywire ssl trust` removes the
warning itself. `haywire ssl status` reports whether TLS is on and, when it
is, whether the address you are actually reachable at is one the certificate
covers. See `docs/guides/security.md` §8.
