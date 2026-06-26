# Handoff — Node-busy visual highlight from the `is_executing` flag

**Status:** not started — design idea only, surfaced as a follow-up during an
unrelated library inquisition. No code written. No branch.

**Type:** framework feature (haywire-core), cross-cutting UI capability. *Not* a
haybale-visiongraph change — it only came up while designing slow estimator nodes.

## Goal

Give a node a visible "I'm executing right now" highlight on the canvas while its
`worker()` runs, driven from the node wrapper's `is_executing` flag. The motivating
case: synchronous, slow nodes (e.g. ML inference taking 100s of ms to seconds)
currently freeze with zero feedback — the user can't tell a node is working vs.
hung. A skin-level busy state fixes this for *every* node, not just vision nodes.

## Why this is more than "surface an existing flag" — the key finding

`NodeWrapper.is_executing` **exists but is never assigned anywhere.** It is a
declared-but-dead field.

- Declared: `packages/haywire-core/src/haywire/core/node/node_wrapper.py:46`
  (`is_executing: bool = False`), sitting among the lifecycle flags
  (`is_initialized`, `is_structural`, `has_test_passed`, `error_runtime`, …).
- A `grep` for writes to it finds **none** in the node path. The only other
  `is_executing` in the codebase is `scheduler.py:76`'s `self._is_executing =
  Event()` — a **separate** `threading.Event` on the scheduler, unrelated to the
  per-node flag. Do not conflate them.

So the work has **two halves**:

1. **Set/clear the flag** around worker execution (it's currently never set).
2. **Propagate it to the skin** so the canvas renders a busy state.

## Where to look (anchors, not a prescription — verify before trusting)

**Half 1 — setting the flag.** The worker is invoked through an *executor* built by
`DataNode._analyze_worker_signature` / `_create_executor`
(`packages/haywire-core/src/haywire/core/node/data.py:821-874`) — these return
`lambda ctx: self.worker(...)`. The natural place to wrap with
`is_executing = True` / `… = False` (try/finally) is wherever that executor is
*called* by the wrapper during a Frame, not where it's *built*. Trace the caller of
`self._executor(ctx)` to find the exact site. Mind the threading reality: workers
can run on a producer/capture thread (see the camera nodes in haybale-visiongraph),
so the flag write + the skin push must be safe from a non-UI thread (the
`ui.context.client` / `with client:` discipline — see
`.insights/feedback_nicegui_redraw_deletes_handler_slot.md`).

**Half 2 — pushing to the skin.** The proven precedent is `error_runtime`: a
node-state field that *does* reach the canvas. Follow it end to end:
- `packages/haywire-core/src/haywire/ui/editor/wrapper.py` sets
  `self._state.error_runtime = …` (lines ~409, 475, 512) and exposes
  `redraw()` (line 210).
- Find how `error_runtime` (or the error skin class) is serialized into the node's
  Vue props / skin payload and rendered — that same channel is where an
  `is_executing` → CSS-class/skin-state should ride. The skin authoring surface is
  `docs/components/skins/skin-canon.md`; node visual states are
  `docs/components/states/state-canon.md` (note: "state" there means library
  runtime data — *not* this; this is a node-wrapper visual flag, closer to how
  `error_runtime` renders an error ring).

## Design questions the next agent must resolve (were not decided)

- **Granularity / debounce.** A 30 ms worker shouldn't flash a spinner every Frame
  at 30 fps — that's strobing, not feedback. Decide a threshold/debounce (only show
  busy if a worker exceeds ~N ms) or an animation that reads as steady under rapid
  re-fire. This is the hardest UX call.
- **Sync-only limitation.** A *synchronous* worker holds the thread, so the busy
  state can only render if the push happens before the blocking call and the UI
  thread is free to paint it. For nodes whose worker blocks the very thread that
  paints, the highlight may not appear until after — verify the threading model
  actually lets the "on" state render. (This caveat is exactly why the vision
  inquisition did *not* try to hand-roll a per-node spinner — see provenance.)
- **Visual language.** What does "busy" look like — pulsing border, corner spinner,
  overlay? Must compose with the existing error ring and selection highlight, and
  obey the design rules in `.insights/project_ui_design_system.md` (no box-shadow on
  chrome, etc.) and `docs/reference/design-guide.md`.
- **Scope of v1.** Possibly ship just the flag-setting + a minimal CSS class first,
  defer the polished animation.

## Decision-record question

This is plausibly **ADR-worthy** *if* the chosen approach is non-obvious or hard to
reverse (e.g. a new node-state propagation channel, or a deliberate "we only show
busy above N ms because …" trade-off). If it ends up a trivial CSS class on an
already-existing channel, skip the ADR. Offer one only if all three hold:
hard-to-reverse, surprising-without-context, real-trade-off (see
`docs/adr/` conventions / the inquisition skill's ADR format).

## Provenance

Surfaced as "Q9 / FOLLOW-UP" while designing slow vision estimator nodes. The
reasoning for *why a per-node hand-rolled spinner was rejected in favour of a
framework capability* lives in
`barn/haybale-visiongraph/notes.md` (search "Q9" and "node-busy"). That file is the
only context to read for the origin; everything needed to *do* this work is in the
present document. Do **not** pull in the rest of the vision estimator design — it's
a separate effort.

## Suggested skills

- **`haywire-ui`** — load the UI architecture docs (editors, skins, app shell, the
  node render path). Start here; this is fundamentally a UI/skin propagation task.
- **`haywire-nodes`** — for the node-wrapper / worker-execution side (where the flag
  gets set). Needed for Half 1.
- **`inquisition`** (or **`design`**) — before coding, stress-test the
  granularity/debounce and visual-language decisions above; they're the real design
  risk, not the wiring.
- **`verify`** — before claiming done (lint, type-check, tests per CLAUDE.md).
- **`requesting-code-review`** — a cross-cutting framework change touching the
  render path warrants review before merge.
