# Blocked as a library category, and the silent cross-source winner

Raised 2026-08-03 while designing the marketplace stepper flows. Scoped OUT of
that UX work deliberately: this is marketplace *semantics*, not presentation,
and it contains a real bug that exists independently of any UI.

Pick this up once the uninstall/install stepper flows have landed.

## Two questions that turned out to be one

The user asked whether `Blocked` should join `Required | Enabled | Disabled |
Available` as a library category, and — separately — whether the marketplace
treats each stall entry as its own library entry or whether entries from
different stalls can conflict.

They're the same question, because the answer to the second one is what makes
the first one lossy.

## What the code actually does

Two mechanisms key on **different things**:

| Mechanism | Keyed on | Scope |
|---|---|---|
| `blocked` / `ignores` (`Subscription` fields) | `(subscription_url, haybale_name)` | per-source |
| `apply_first_come_first_served` | `haybale_name` alone | global |

`refresh.resolve()` builds the candidate list in a fixed order — inline
`[[haybales]]` in the global file, then stalls, then market-inline — and then
`apply_first_come_first_served` dedupes on bare `hb.name` (`seen: set[str]`).

So **the same library offered by two stalls never produces two catalog
entries.** One wins by list position; the loser is dropped with no prompt and
no diagnostic. The winner's `via` field records which source it came from, but
nothing records that a choice was made at all.

### The bug

If stall A and stall B both offer `haybale-foo` at different versions, the user
gets one of them, chosen by file order, silently. There is no way to see that
a collision occurred, no way to tell which source lost, and no way to prefer
the other one short of hand-editing `ignores` in the global marketplace file.

`detect_subscription_conflicts()` / `SubscriptionConflict`
(`core/marketstall/helpers.py`) already model exactly this — but they only run
on the **add-source** path. Nothing surfaces a *standing* conflict on refresh.

Note the ordering is also only quasi-deterministic across refreshes: it follows
the order subscriptions appear in the global file, so reordering that file (or
a market discovering stalls in a different order) can flip which source wins
without the user doing anything they'd recognise as a version change.

## Why "Blocked" as a flat category is lossy

`apply_blocked` drops blocked haybales during resolve, before they reach the
project cache — so a blocked library is *invisible*, not *marked*. Rendering a
`Blocked` category means changing what the catalog surfaces, not adding a state
field.

More importantly, the existing block is per-source but a category row is
per-name. The two documented use cases want different scopes:

1. **No trust** — "never install this, from anywhere." Wants global.
2. **Deduplication** — "I get this from stall B, so ignore stall A's copy."
   Wants per-source, and is arguably what `ignores` already means.

A flat `Blocked` category cannot express #2: it can't say "blocked from stall
A, still available from stall B". Collapsing them would either break the dedupe
case or silently widen a per-source block into a global one.

Worth resolving first: **is `blocked` actually two concepts wearing one name?**
`ignores` and `blocked` have identical filter shapes (`apply_ignores` and
`apply_blocked` are the same function modulo the field they read) and differ
only in intent — `ignores` = "another source is preferred", `blocked` = "the
user rejected this via the safety modal". The dedupe use case above is
literally `ignores`. That suggests the fix may be to give `blocked` the global
"never install" meaning it's reaching for, and let `ignores` own per-source
preference — rather than adding a third mechanism.

## How categories currently work

Required / Enabled / Disabled / Available are **computed live** in
`LibraryBrowserEditor._render_list`, not stored:

- `Required` = some *installed* library declares this one in
  `@library(dependencies=[...])` (via `manager.get_installed_dependents`).
  Same signal that gates the Disable/Uninstall buttons, so badge and button
  always agree.
- They are not naturally mutually exclusive — `required_set` exists purely to
  stop Required bleeding into Enabled.

Any `Blocked` category has to decide where it sits in that precedence, and
whether a blocked-but-installed library is possible at all (today: yes, since
blocking only filters the marketplace catalog, not the venv).

## Open questions

1. Does `blocked` become global ("never install, from any source") with
   `ignores` retained for per-source preference? Or does `Blocked` stay
   per-source and the UI shows one row per `(name, source)`?
2. Should a cross-source collision be **surfaced** at all — a conflict badge, a
   step in the refresh flow, a per-library "offered by 3 sources, using B"
   affordance? The refresh flow's `resolved` step is the natural place: it
   already renders deltas before the write, and `ResolvedCatalog` could carry a
   `collisions` list at no extra fetch cost.
3. Is un-blocking a UI action? Today the docstring on `record_block_on_source`
   says "un-block only by editing the file" — a `Blocked` category strongly
   implies a visible un-block, which is a new write path.
4. Where does a blocked entry live in the project cache? It is currently
   dropped during resolve, so nothing persists it; a visible category needs it
   either retained-and-flagged (like `stale`) or re-derived from the global
   file's `blocked` arrays at render time.

## Relevant code

- `packages/haywire-core/src/haywire/core/marketstall/refresh.py` —
  `resolve()`, `apply_blocked`, `apply_ignores`, `apply_first_come_first_served`
- `packages/haywire-core/src/haywire/core/marketstall/helpers.py` —
  `record_block_on_source`, `record_ignore_on_source`,
  `detect_subscription_conflicts`, `SubscriptionConflict`
- `packages/haywire-core/src/haywire/core/marketstall/types.py` —
  `Subscription.blocked` / `.ignores`, `ResolvedCatalog`
- `barn/haybale-marketplace/haybale_marketplace/editors/library_browser_editor.py`
  — `_render_list` category computation, `_make_toggle` filter chips
- `barn/haybale-marketplace/haybale_marketplace/editors/_overview_install_flow.py`
  — `install_with_safety_check`, the only place a block is currently created
