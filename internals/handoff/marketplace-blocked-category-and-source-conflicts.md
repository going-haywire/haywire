---
name: marketplace-blocked-category-and-source-conflicts
description: Handoff — LANDED 2026-08-14: `preference` replaces `ignores`+`doubles`, and a name-conflict step settles several libraries claiming one name; only the Blocked-category chip in the library browser is still open
metadata:
  type: project
  status: open
---

# Blocked as a library category, and the silent cross-source winner

> **Read the LANDED section first.** Everything above it is the original
> 2026-08-03 analysis and the 2026-08-14 drift check, both written when
> `ignores` and `doubles` still existed. They are kept for the reasoning, not
> as a description of the current schema — a subscription now carries `url`,
> `preference`, `blocked`. Anywhere below that says "`ignores`", read
> "`preference`, inverted": it named the loser, `preference` names the winner.

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
   Related: the install flow's Block affordance ("Don't offer this again") is
   deliberately a **side exit** that closes the flow, not a step — blocking
   means you are not installing. If blocking becomes reversible from a
   category chip, that side exit probably wants to say so.
4. Where does a blocked entry live in the project cache? It is currently
   dropped during resolve, so nothing persists it; a visible category needs it
   either retained-and-flagged (like `stale`) or re-derived from the global
   file's `blocked` arrays at render time.

## Drift check — 2026-08-14

Re-verified every claim below against the tree. **The analysis holds in full**:
`apply_first_come_first_served` still dedupes on bare `hb.name` with no record
of the discard (`refresh.py:120`), `apply_blocked`/`apply_ignores` are still
the same function modulo the field they read (`refresh.py:82`/`94`), and
`detect_subscription_conflicts` still runs only on the add-source path.

Three corrections to the "Relevant code" pointers:

- **Blocks are created in `_overview_install_flow.py:_on_block`**, not in
  `_install_flow/chrome.py`. Chrome only renders the button and invokes the
  `on_block` callback the caller passes; the write (`resolve_block_target` →
  `record_block_on_source`) lives in `_overview_install_flow.py:59-88`. That
  is also where the un-block write path would have to be mirrored.
- **`resolve()` gained a blocked-names stale-rescue guard** (`refresh.py:306`)
  that the original text predates: blocked names are stripped from the previous
  `[[caches]]` before `mark_stale_against_previous`, so a blocked entry cannot
  come back as `stale=True`. This is load-bearing for question 4 — nothing
  persists a blocked entry today, by explicit design, not by omission.
- **`ResolvedCatalog` has no `collisions` field yet** (`types.py:146`); the
  landing site predicted below is still unbuilt.

### The unused `doubles` field — not previously noted

`Subscription.doubles` (`types.py:29`) is **fully plumbed and never written**:
parsed (`parsing.py:134`), serialized (`parsing.py:267`), preserved across both
helper rewrites (`helpers.py:149`/`175`), scaffolded into every new
subscription (`haybale_marketplace/config.py:18`), and documented in the
glossary as *"names that two `[[markets]]` entries silently dedup to.
Diagnostic only."*

That is a description of exactly the bug this document is about — someone
reserved the slot for the silent-FCFS record and never filled it. Any solution
should either use `doubles` as intended or delete it; leaving a documented
field that no code writes is worse than either.

## LANDED 2026-08-14 — `preference` replaces `ignores` + `doubles`

The silent-winner half of this document is **built and green** (3447 passing).
The `Blocked` category half stays open behind it; nothing here touches
`blocked`'s per-source semantics.

**Breaking schema change, no migration** (agreed): a subscription now carries
`url`, `preference`, `blocked`. Both `ignores` and `doubles` are gone.

The first cut of this recorded FCFS losers into `doubles` and resolved
collisions by writing `ignores` on the winner. Two problems killed it:

- `doubles` was written and never read — a receipt nobody consumed, needing a
  rewrite-per-run rule purely to stop it rotting, and making refresh write to
  the user's config file for no one's benefit.
- `ignores` is *negative*, so reaching the third of three sources took two
  clicks and passed through an intermediate winner nobody asked for.

`preference` is positive and exclusive: naming the winner clears that name from
every other subscription. One click settles any collision at any source count,
and the result no longer depends on subscription order — which was the original
bug.

What shipped:

- `Subscription(url, preference, blocked)`; `apply_ignores` and `record_doubles`
  deleted, `record_ignore_on_source` → `record_preference` (returns bool).
- `preferred_sources()` builds `name -> url`; a double claim (hand-edit only)
  resolves by file order and is still reported as a collision.
- `dedupe_reporting_collisions()` picks the preferred copy, falling back to
  first-come-first-served. A stale preference (source stopped offering the
  name) falls back rather than blanking the row.
- **Refresh never writes the global file.** It is user intent; only an explicit
  action edits it. `apply()` lost the `global_path` parameter it briefly had.
- Settling a collision does not hide it — losers stay listed, so the choice is
  reversible from the same panel with one click.

**Transitive-discovery trap, found by testing against the real feed.** A stall
discovered through a `[[markets]]` body is not subscribable, so a preference
against its own URL matches nothing and the click silently did nothing. Fixed
by stamping `Haybale.owner_url` (runtime-only) with the aggregator that found
it, matching preferences on `via` *or* `owner_url`, and carrying
`SourceCollision.loser_owners` so the panel displays the real source but writes
to the subscription that owns it. `record_preference` routes through
`resolve_block_target` — the same mapping the Block button uses — and returns
False when nothing can own the URL.

Also: the CI aggregator (`scripts/generate_marketstall.py`) now emits `url`
only. `preference`/`blocked` are a consumer's opinion about their own
subscriptions, and the remote parser reads neither — emitting them implied the
publisher had a say. The share pipeline never touched subscriptions.

Tests: 14 in `tests/marketstall/test_refresh.py`, 5 in `test_helpers.py`,
4 in `tests/test_refresh_flow_ui.py`.

### Downgrade surfacing (same session)

A source preference can point the catalog at a feed publishing an *older*
release than the one installed. Refresh never touches the venv, so nothing
broke — but both update checks were `catalog > installed`, so the disagreement
was completely silent and a reinstall would have quietly downgraded.

- Library browser: `downgrades_available` alongside `updates_available` (same
  loop, inverse comparison) → a `arrow_downward` warning chip.
- Install flow: `is_downgrade` + a `verb` property, so the title, the heading
  and the done-message read Install / Update / **Downgrade**. Unparseable
  versions (non-PEP-440 git tags) fall back to "Update" rather than raising.
- Version picker: shows the installed version next to the count, and now moves
  `version` with `install_spec` when pinning — it previously kept the catalog's
  version on a pinned spec, which would have made the flow describe the wrong
  release.

**Still missing: install provenance.** Nothing records which subscription a
library was installed *from*, so switching preference between two sources at
the *same* version is undetectable — no version comparison can see it. That is
the gap under both the badge and the "is my copy the one this source means"
question, and it wants a field on the project cache rather than a UI change.

Not done, deliberately: the add-source stale-baseline gap is *narrowed* (a
missed collision surfaces on the next refresh) but `existing_haybales()` still
reads the last refresh's catalog. Fixing it properly means probing every
subscribed source at add time — a network-cost decision wanting its own round.

## LANDED 2026-08-14 (second round) — name conflicts

A name offered by several sources was treated as one library seen through
several feeds. It is not always: the marketplace has no namespace for
git-sourced names, so two authors can publish `haybale-mesh` from unrelated
repositories and the catalog would offer them as interchangeable — one click
away from installing somebody else's code under the name you meant.

**Identity policy lives in the barn, not core.** `resolve(..., same_library=)`
is a seam core defines and never fills; `haybale_marketplace.identity` supplies
`identity_matches`. Rule, deliberately conservative — say "same" only when
provable:

| Candidates | Verdict |
|---|---|
| Both PyPI, same name | same library (PyPI's namespace has one owner) |
| Both git, same `origin` | same library |
| Both git, different `origin` | **conflict** |
| PyPI vs git | **conflict**, labelled, no auto-win |
| `origin` missing | **conflict** |

PyPI does *not* auto-win: registering a name there is trivial, so preferring it
would hand the win to a squatter in the case that does damage.

`installed_identity_matches` adds one rule: an **editable project-local**
checkout is authoritative for its own identity. Its `haybale.toml` legitimately
carries no `origin` (the share wizard writes that at publish), so the plain rule
would raise a conflict on every refresh for anyone developing in-repo.

**The step.** `conflicts` sits between `fetched` and `resolved` and is
*stopped at* only when there is one — but stays in `STEPS` either way, because
the progress bar is redrawn from that list and a growing bar moves the
goalposts mid-flow. Every claimant is listed, blocked ones included, read from
`candidate_haybales(fetched, honour_blocked=False)` — the resolve drops blocked
names, and a claimant that vanishes when blocked turns the step into an
elimination game where the survivor wins by attrition. Continue is disabled
until **exactly one** claimant per name is unblocked; blocking all of them is as
unresolved as blocking none. The installed copy cannot be blocked (disabled
button + a guard in `block_claimant`) — uninstall first to switch.

Blocks are per-name and per-source, written only by the user, and reversible:
`remove_block_on_source` is new, and `record_block_on_source`'s "un-block only
by editing the file" docstring was corrected.

**Resolves three of the four open questions above.** Q1 dissolved when
`ignores` was removed — `preference` owns per-source preference, `blocked` owns
rejection, and the two are no longer near-duplicates. Q2 is built. Q4's answer
is "it doesn't need to live in the cache": blocked state is re-derived from the
global file at render time. Q3 is answered here (un-blocking is a UI action).

Still open: only the **`Blocked` category chip in the library browser** — a
different surface, and now cheap, since re-deriving from the global file at
render time is the proven pattern. Its precedence against
Required/Enabled/Disabled/Available is still undecided, but that is a
UI-ordering question, not a semantics one.

## What changed since this was written

The five marketplace flows landed (`da7bcb3c` … `fcca7aef`). Three things
that affect this work:

**1. The conflict prompt moved, and now runs before the write.** The old Add
Source dialog subscribed first and asked about collisions afterwards. The
stepped flow (`_add_source_flow/`) probes the source, detects collisions on
its `probed` step, and only writes on `resolved`. So the *prompt* half of the
conflict story is now in good shape — a per-conflict "Keep existing / Use new"
choice that is recorded as `ignores` against the losing side, exactly as
before, but before anything is committed.

**2. The stale-baseline gap is still there and is now localised.** Collisions
are detected against the project's `[[caches]]` — the *last refresh's* result
— so a source subscribed but not yet refreshed is invisible to the check. That
was true of the old dialog too; it now lives in one place and is commented:

    MarketplaceAddSourceTarget.existing_haybales()
      barn/haybale-marketplace/haybale_marketplace/editors/_add_source_flow/chrome.py

This is the same root cause as the silent-FCFS-winner bug above: conflict
detection reads one dataset, dedup happens over another. Fixing the standing
conflict question would naturally fix this too.

**3. `ResolvedCatalog` exists and is the obvious carrier.** Question 2 below
predicted this — `refresh.resolve()` now returns a `ResolvedCatalog`
(`core/marketstall/refresh.py`), and its `resolved` step in `_refresh_flow/`
already renders `newly_added` / `newly_stale` / `updates_available` before the
write. Adding a `collisions: list[SubscriptionConflict]` field there costs no
extra fetch — `resolve()` already has every candidate in hand at the point
`apply_first_come_first_served` discards the losers.

That is the cheapest possible landing site for surfacing standing conflicts,
and it did not exist when this document was written.

## Relevant code

- `packages/haywire-core/src/haywire/core/marketstall/refresh.py` —
  `resolve()`, `apply_blocked`, `apply_ignores`, `apply_first_come_first_served`.
  Note `resolve()` is now a pure function returning `ResolvedCatalog`; the
  write moved to `apply()`.
- `packages/haywire-core/src/haywire/core/marketstall/helpers.py` —
  `record_block_on_source`, `record_ignore_on_source`,
  `detect_subscription_conflicts`, `SubscriptionConflict`
- `packages/haywire-core/src/haywire/core/marketstall/types.py` —
  `Subscription.blocked` / `.ignores`, `ResolvedCatalog`
- `packages/haywire-core/src/haywire/core/marketstall/subscribe.py` —
  `resolve_source()` / `subscribe()`; `ResolvedSource.haybales` is what the
  add-source flow collides against
- `barn/haybale-marketplace/haybale_marketplace/editors/library_browser_editor.py`
  — `_render_list` category computation, `_make_toggle` filter chips
- `barn/haybale-marketplace/haybale_marketplace/editors/_add_source_flow/`
  — `_state.py` holds `_detect_conflicts` and `_apply_conflict_choices`;
  `chrome.py` holds the stale-baseline note on `existing_haybales`
- `barn/haybale-marketplace/haybale_marketplace/editors/_install_flow/chrome.py`
  — `_render_block`, which renders the side exit off the first step (not a step
  of its own) and calls back out
- `barn/haybale-marketplace/haybale_marketplace/editors/_overview_install_flow.py`
  — `_on_block`, the only place a block is actually **written**
  (`resolve_block_target` → `record_block_on_source`)
