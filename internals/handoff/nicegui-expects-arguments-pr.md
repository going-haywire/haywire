# Handoff — upstream NiceGUI PR: stop re-running `inspect.signature` on every observable change

**Date:** 2026-06-09
**Status:** deferred — Haywire side is done & shipped; only the upstream PR remains.
**Who's waiting:** the NiceGUI maintainer reviewed our proposal, said the
diagnosis is "spot on", and **offered to review a PR**. This is a welcomed,
pre-greenlit contribution — not a cold submission.

---

## One-paragraph context

Profiling Haywire's large-graph render found that every
`.props()`/`.classes()`/`.style()` mutation routes through
`ObservableCollection._handle_change` → `events.handle_event(handler, …)` →
`helpers.expects_arguments(handler)`, which runs a fresh `inspect.signature()`
**every time** to decide whether to call the handler with args. The handler's
signature never changes, so on a dense page this is enormous wasted
recomputation (~135,000 `inspect.signature` calls to render a 200-node graph).
Haywire already ships a local mitigation; this handoff is **only** about
contributing the proper fix upstream.

Full reasoning, measurements, and the local fix are recorded in
[`docs/adr/0006-node-render-performance.md`](../../docs/adr/0006-node-render-performance.md)
(see the `expects_arguments` decision + "Patching a vendored internal"). Don't
re-derive — read that first.

---

## What's already done (do NOT redo)

- **Local Haywire fix is shipped** on branch `widget-perf-verification`:
  `packages/haywire-core/src/haywire/ui/nicegui_patches.py` installs a **bounded**
  `lru_cache(maxsize=1024)` over `expects_arguments` at startup. Bounded — not
  `maxsize=None` — because the maintainer correctly flagged that an unbounded
  cache leaks (keys are per-element bound methods + every user event lambda;
  unbounded pins them and their elements forever on a long-running server). This
  is our **bridge until the upstream fix lands**; it gets deleted then.
- Benchmark proving the win and that bounded loses nothing:
  `tests/ui/widget/test_expects_arguments_cache.py` (measured: every `maxsize`
  from 4 to None → identical 73% hit rate, ~1.4× render speedup).

## The PR to write (the deferred task)

**The maintainer's preferred fix is NOT a cache.** It is to **resolve
`expects_arguments` once at handler-registration time** and store the bool, then
read the stored flag in `_handle_change` — no per-fire introspection, leak-free.

This mirrors an existing precedent in NiceGUI's own Event system: `Callback`
(`nicegui/event.py:23`) stores `expect_args: bool` (computed once at
`event.py:77` via `helpers.expects_arguments(...)`) and at call time does
`self.func(*args) if self.expect_args else self.func()` (`event.py:33`). The PR
extends that same "resolve once at registration" pattern to the observable /
`handle_event` path.

**Concrete change sites** (verified against installed NiceGUI **3.12.1**,
`nicegui/observables.py`):

- `ObservableCollection.__init__` stores
  `self._change_handlers: list[Callable] = [on_change] if on_change else []`.
  Registration also happens wherever handlers are appended to `_change_handlers`
  (the `on_change` setter / subscribe path — grep `_change_handlers` in
  `observables.py`).
- `ObservableCollection._handle_change` currently does:
  ```python
  for handler in self.change_handlers:
      events.handle_event(handler, events.ObservableChangeEventArguments(sender=self))
  ```
  The fix: at *registration*, wrap each handler in (or alongside) a stored
  `expect_args` bool — likely a small `Callback`-like record — so `_handle_change`
  calls with/without args from the stored flag instead of going through
  `handle_event`'s per-fire `expects_arguments`. Reuse `Callback` from
  `nicegui/event.py` if it fits, to stay consistent.

**Watch-outs:**
- `handle_event` does more than the arg check (it also handles async, error
  wrapping, slot/client context). Don't lose those — the observable path may
  still want `handle_event`'s machinery; the goal is only to avoid the *per-fire
  signature introspection*. Confirm what `handle_event` does for these
  `ObservableChangeEventArguments` handlers specifically before bypassing it.
- The earlier upstream attempt at a *different* perf fix (vnode-cache, PR #5761)
  was reverted for a regression (#5823). Maintainer will be regression-cautious —
  keep the change minimal and mirror the existing `Callback` pattern exactly.

## Suggested approach

1. Fork/clone `zauberzeug/nicegui`, work against `main` (not 3.12.1 — re-check
   the change sites there; the API may have shifted).
2. Implement the resolve-once pattern; add/adjust a unit test proving no
   per-fire `inspect.signature` (e.g. patch `helpers.expects_arguments` to count
   calls and assert it's called once per handler registration, not per fire).
3. Reference our profiling in the PR description; the maintainer already has the
   context and offered review. Link back so the loop closes.
4. When merged + released: delete `haywire.ui.nicegui_patches` (the bounded-cache
   bridge), bump the NiceGUI floor, and update ADR-0006 to mark the patch
   removed.

## Suggested skills

- **`claude-api`** is NOT relevant here. Instead:
- **`nicegui`** — load NiceGUI framework patterns/context before editing NiceGUI
  internals (event system, observables, Vue-component wrapping).
- **`verify`** / **`haywire-codesanitizer`** — after deleting the local patch
  (the eventual cleanup step), run the full ruff + mypy + pytest suite clean.
- Plain web/gh tooling for the actual fork + PR (no special skill needed).

## Pointers

- Maintainer's full review feedback (the two options, the leak explanation, the
  `Callback.expect_args` precedent) is in the conversation that produced commit
  `17c6d7bd` — and its substance is captured in ADR-0006's decision #2 + "Patching
  a vendored internal" section. Read those rather than reconstructing.
- Branch `widget-perf-verification` holds all the perf work (not yet pushed/PR'd
  to Haywire's own repo — a separate decision from this upstream PR).
- This is a **community contribution we owe**, not a Haywire blocker: our app is
  correct and leak-free today via the bounded bridge. No urgency; pick it up when
  convenient.
