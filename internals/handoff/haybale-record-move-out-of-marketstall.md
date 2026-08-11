---
name: haybale_record_move_out_of_marketstall
description: Handoff — move the Haybale metadata record out of core.marketstall into core.library, then delete the TID251 ruff rule that exists only to protect that move
metadata:
  type: project
---

# Handoff: move `Haybale` out of `marketstall`, then drop the TID251 rule

## Where this came from

The [one-metadata-record branch](../../docs/superpowers/plans/2026-08-10-haybale-one-metadata-record-decisions.md)
(D1, D11) made `Haybale` the single library-metadata record, read from **two** files:

- a library's own `haybale.toml`, via `read_haybale()` in `haywire/core/library/haybale_toml.py`
- a published marketstall feed, via `_parse_haybale_entry()` in `haywire/core/marketstall/parsing.py`

The type stayed in `haywire.core.marketstall.types` — deliberately, "for the time being",
because moving it was out of scope for that branch. To keep the move cheap later, D11 added
a ruff `TID251` banned-api rule pinning the canonical import path so consumers could not
re-accumulate deep imports.

**That rule is scaffolding for this task.** It has no independent value. Doing the move is
what lets it go.

## The problem in one line

`Haybale` lives in the *distribution* layer but is now equally the *authoring* layer's
record — so `core.library` has to reach sideways into `core.marketstall` to name its own
metadata type, and it can only do so through function-local imports that dodge a cycle.

## Evidence

**The cycle dodge.** `haybale_toml.py` cannot import `Haybale` at module scope. Every use is
either `TYPE_CHECKING`-guarded or function-local, with the reason written in the code:

- [`haybale_toml.py:33-35`](../../packages/haywire-core/src/haywire/core/library/haybale_toml.py#L33-L35)
  — *"function bodies (see read_haybale) to avoid a haybale_toml <-> marketstall"* cycle
- [`:239`](../../packages/haywire-core/src/haywire/core/library/haybale_toml.py#L239) and
  [`:269`](../../packages/haywire-core/src/haywire/core/library/haybale_toml.py#L269)
  — function-local `from haywire.core.marketstall import ...`

This is the layering smell, stated by the code itself. After the move both modules live in
`core/library/`, the cycle cannot form, and the guards become plain top-level imports.

**The import split is already clean.** Every deep import of `marketstall.types` is inside
the two paths the ruff rule exempts — the module's own siblings and its dedicated tests:

```text
packages/haywire-core/src/haywire/core/marketstall/   parsing, subscribe, locate, cache,
                                                      __init__, platform, refresh, helpers  (8)
tests/marketstall/                                    9 files
```

All ~46 other call sites already use `from haywire.core.marketstall import Haybale`. That is
what makes the move small, and it is exactly what the rule was protecting.

## What to do

### 1. Move the record

`Haybale` and `Deprecation` (which `Haybale` holds) move from
`packages/haywire-core/src/haywire/core/marketstall/types.py` to a new module under
`haywire/core/library/` — suggest `record.py`.

**Leave behind in `marketstall/types.py`** everything that is genuinely about *distribution
and transport* — verified against the file, these are all of them: `Subscription`,
`MarketplaceFile`, `ProjectMarketplaceFile`, `RefreshOutcome`, `FetchResult`,
`RefreshReport`, `SourceOutcome`, `FetchedSources`, `ResolvedCatalog`. Those describe feeds
and refresh runs, not libraries.

`Deprecation` moves *with* `Haybale`: it is a `[deprecated]` block authored in
`haybale.toml`, held as `Haybale.deprecated`, and read by `_row_from()` in
`haybale_toml.py` — it is metadata, not transport.

> Judgement call for whoever does this: `Haybale` carries publish/transport fields
> (`install_spec`, `require`, `source`, `via`, `last_seen`, `stale`, `source_*`). D1 decided
> deliberately that these stay on the one class — empty on a row read from disk is *honest*,
> not a lie, and splitting them would cost ~91 call sites their flat attribute access. **Do
> not re-litigate that as part of this move.** Move the class as it stands.

### 2. Re-export from `marketstall/__init__.py`

```python
from haywire.core.library.record import Deprecation, Haybale
```

Keep both in `__all__`. This is what keeps all ~46 external call sites untouched — they
already import from the package root.

⚠️ **Check the cycle direction.** `core/library/record.py` must not import anything from
`core/marketstall/`. If `Haybale` needs a helper that lives in marketstall, move the helper
or inline it; do not import upward.

### 3. Update the deep-path users

The 8 sibling modules in `core/marketstall/` and the 9 files in `tests/marketstall/`.

⚠️ **`marketstall/*.py` must import from `haywire.core.library.record`, NOT from
`haywire.core.marketstall`.** Importing the package root from inside the package is the
exact cycle `tests/share_pipeline/test_layering.py` was written to prevent for the
`publishing` package — see its docstring: *"no module inside the package imports the package
root, so the root's re-exports cannot loop back."* The same hazard applies here, and there
is currently **no equivalent test guarding `marketstall`**. Consider adding one (step 6).

### 4. Straighten `haybale_toml.py`

Once both modules are in `core/library/`, replace the `TYPE_CHECKING` guard and the two
function-local imports with one ordinary top-level import, and delete the cycle comment at
[`:33-35`](../../packages/haywire-core/src/haywire/core/library/haybale_toml.py#L33-L35).

Also fix the two docstring references that name the old path:
[`:226`](../../packages/haywire-core/src/haywire/core/library/haybale_toml.py#L226) and
[`:374`](../../packages/haywire-core/src/haywire/core/library/haybale_toml.py#L374) both say
`~haywire.core.marketstall.types.Haybale`.

### 5. Delete the ruff rules

In the root `pyproject.toml` — the deep path no longer contains `Haybale`, so there is
nothing left to ban:

- drop `"TID251"` from `extend-select` (leave `"E501", "PT", "B"` alone)
- delete the whole `[tool.ruff.lint.flake8-tidy-imports.banned-api]` section
- delete the two `per-file-ignores` entries for
  `packages/haywire-core/src/haywire/core/marketstall/*` and `tests/marketstall/*`
- fix the `[tool.ruff.lint]` comment above `extend-select`, which explains TID251 and TID252

> **Do not** substitute bare `"TID"`. It also enables `TID252` (relative-imports), which has
> **198 pre-existing, unrelated violations** repo-wide and fails `ruff check .` outright.
> This was already hit once during the branch and is why the rule is named specifically.

### 6. Consider a layering test

`tests/share_pipeline/test_layering.py` enforces the no-import-the-root rule for
`publishing`. `marketstall` has no equivalent, and step 2 introduces a re-export that makes
the cycle newly reachable. Adapting that test to `core/marketstall/` would replace the
deleted ruff rule with a structural guard that protects something real — rather than leaving
nothing behind.

## Naming — decide before starting

Once the type lives in `core/library/record.py`, is it still `Haybale`?

**Recommendation: keep the name.** It was settled deliberately (decisions doc Q1-A):
`Haybale` is established across 64 import sites, two canon docs and the glossary's
three-meanings table, and renaming buys clarity that the redefinition already bought. The
glossary entry for meaning 3 was rewritten on this branch to say the dataclass *is* the
metadata, so the name no longer implies "a row in a feed".

If a future reader still finds `Haybale` odd in `core/library/`, that is a rename to argue
on its own merits — not a rider on this move.

## Scope

~17 files, all mechanical. No consumer changes, because the re-export absorbs them.

**Verify with:**

```sh
uv run ruff check . && uv run ruff format --check .
uv run mypy   # the 11 paths in CLAUDE.md
uv run pytest -m "not browser and not perf"   # baseline on this branch: 3263 passed
```

Plus a real import smoke test, since the point is a cycle:

```sh
uv run python -c "import haywire.core.marketstall, haywire.core.library.haybale_toml; print('ok')"
```

## Do not do this while the one-metadata-record branch is unmerged

That branch is verified and review-clean at 16 commits. Folding a 17-file move into it would
invalidate the whole-branch review. Merge first; this is a follow-up.

## Related

- [Decisions record](../../docs/superpowers/plans/2026-08-10-haybale-one-metadata-record-decisions.md)
  — D1 (one bag), D11 (import discipline), and the deferred-move note
- [Glossary](../../docs/reference/glossary.md) — "Haybale" three meanings; meaning 3 was
  redefined on that branch
- `tests/share_pipeline/test_layering.py` — the precedent for step 6
