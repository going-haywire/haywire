# Curated marketplace — implementation plan

Adds `going-haywire/marketplace`: a second feed publisher carrying first-party
standalone libraries and selected third-party ones, in three channels. Settled
by inquisition on 2026-08-27; twenty-six decisions, recorded in
[curated-marketplace.md](../../haybale/marketplace/curated-marketplace.md).
No ADR — the design doc is canon.

**The one sentence:** a curated row is generated from the artifact it pins, so
it cannot lie about what it installs; the three channels differ only in what
they assert about which version, and placement is derived, never granted.

```
registry/*.toml       membership          (human — the only decision)
        ↓
edge      nightly, unpinned               membership + identity
latest    curation tag, ==pinned          + installs and loads alone
stable    solved set, ==pinned            + resolves and loads together
```

## Baseline

Establish before Stage 1 and record the output here:

```sh
uv run ruff check .
uv run ruff format --check .
uv run mypy <the CLAUDE.md file list>
uv run pytest -m "not browser and not perf" -q > /tmp/t.log 2>&1; echo "exit=$?"
```

Anything failing after an edit that was not failing here belongs to the edit.

## Stage 1 — the tomlkit char-array defect (P1, independent) — **LANDED**

> **Done, 2026-08-28.** The deferred last line — regenerating
> `haybale-visiongraph`'s marketstall — was completed with Stage 3, so the file
> was rewritten once as a `pypi` row rather than republished as a `git` row we
> had already decided to replace. Published as v0.0.38.
>
> Fixed at the parse boundary rather than per-writer: `plain()` in
> `core/tomlio.py`, beside `read_toml`, recursively strips tomlkit's wrapper
> types. Applied in `read_haybale_toml()`, `read_haybale()` and `read_raw()`,
> which covers all **three** sources the original diagnosis under-counted —
> `_row_from` (name/version/label/description/tags/authors), `_fields_from`
> (`linked_libraries`, `os`) and `read_raw` (`origin`, `origin_provider`).
>
> It lives in `tomlio` rather than at the fix site because this seam had already
> been patched locally three times without anyone noticing the others:
> `_declared_deprecation`'s inline `str(...)` calls, a private `_plain` in
> `publishing/generate.py`, and (nearly) a fourth of the same name. Both private
> copies are now gone.
>
> Also corrected: `generate.py` justified its copy with "tomlkit containers
> compare unequal to plain lists/dicts" — **false on tomlkit 0.15.1**, where
> array, table, sub-table and array-of-tables all compare equal. The workaround
> outlived its bug; its calls are kept for a stated reason instead.
>
> Ten tests added, each verified red against the unfixed source (five on the
> readers and the write→parse round trip, five on `plain()` itself — including
> one asserting the *premise*, so the whole thing gets deleted rather than
> cargo-culted if tomlkit ever stops subclassing builtins).
> Gate: `4493 passed`, ruff/mypy clean; the one remaining `ruff format` drift
> (`debug/debug_settings.py`) is committed on master and untouched here.

`haywire share` writes marketstalls whose every string field is a character
array, making them unsubscribable. `haybale-visiongraph`'s published feed is
broken today.

Chain:

1. `read_toml()` parses with **tomlkit**
   (`packages/haywire-core/src/haywire/core/tomlio.py:43`);
   `tomlkit.items.String` is a `str` **subclass**.
2. `_row_from()` guards with `isinstance(value, str)`
   (`packages/haywire-core/src/haywire/core/library/haybale_toml.py:265`),
   so tomlkit Strings pass into the `Haybale` unchanged.
3. `write_marketstall()` serializes with `toml.dumps`
   (`packages/haywire-core/src/haywire/core/publishing/marketstall.py:309`),
   which treats a `str` subclass as a **sequence of characters**.
4. `parsing.py` requires a real `str` for `name` and raises
   (`packages/haywire-core/src/haywire/core/marketstall/parsing.py:89`)
   — subscribing yields `MalformedMarketplaceError`.

Why it was never seen: `scripts/generate_marketstall.py` hand-formats via
`_format_value()` instead of `toml.dumps`, so the Official feed is unaffected.
Only the author-facing path corrupts. The codebase already knows this trap and
defends against it in exactly one place — `_declared_deprecation`
(`packages/haywire-core/src/haywire/core/publishing/marketstall.py:54`).

**Fix** in `_row_from`'s `_str` / `_list` helpers: normalise with `str(...)`
rather than returning the value the isinstance check admitted. This repairs
every `read_haybale()` consumer, not just publishing. Check the `authors` and
`deprecated` branches in the same function for the same pattern.

**Tests**

- `tests/core/test_library/test_haybale_toml.py` — a `haybale.toml` read back
  yields `type(row.version) is str` exactly, not a subclass. Assert on
  `type(...) is str`; an `isinstance` assertion passes today and proves nothing.
- `tests/share_pipeline/` — round-trip: write a marketstall from a fixture
  library, re-parse it with `parsing.py`, assert every field survives. This is
  the test whose absence let this ship.

**Then regenerate** `haybale-visiongraph`'s marketstall and push it.

## Stage 2 — exact pins in the Official feed — **LANDED**

`generate_marketstall.py:87` sets `install_spec` to the bare dist name for pypi
rows. The row then advertises one version and installs another, so
`updates_available` (`installed < version`) shows a phantom update forever and
clicking it reinstalls the same thing.

- Emit `install_spec = f"{name}=={version}"` for `source == "pypi"`.
- Update [marketstall-toml.md:116](../../reference/files/marketstall-toml.md#L116),
  which documents `"haybale-image>=1.0.0"` — neither what the code did nor what
  it will do.
- Update the "Tag pinning" section of the same page: the pinning rule now
  covers both sources.

The behaviour change is that a user on an older `haywire-core` gets a refusal
instead of a silent downgrade to a compatible older library. `check_require()`
(`packages/haywire-core/src/haywire/core/marketstall/framework_gate.py:64`)
already catches this before the button does anything and names both sides.
Verify that path has a test.

## Stage 3 — `distribute`, and deleting `pypi_marketplace_url` — **LANDED**

**Add** to `[tool.haywire.marketstall]`:

```toml
distribute = "pypi"   # or "git" (default)
```

- Read it beside `read_pypi_marketplace_url()` in
  `packages/haywire-core/src/haywire/core/publishing/marketstall.py`
  — same block, same project scope, same leniency rules.
- `_build_entry_for_library()` branches on it: `"pypi"` emits
  `source = "pypi"` and `install_spec = f"{name}=={version}"`; `"git"` keeps
  today's VCS spec. The git branch must stay byte-identical for repos that
  never declare it.
- Preconditions: `distribute = "pypi"` against a name not registered on PyPI is
  a `PreconditionFailure`, reported like the others. No `fix_id` — registration
  needs a human on pypi.org. Link to the right page in the message.

**Delete**, in one commit:

- `read_pypi_marketplace_url()` and its call in `write_marketstall()`.
- The `pypi_url` parameter through `_update_readme_markers()` and
  `_update_repo_readmes()` (`packages/haywire-core/src/haywire/core/publishing/readme.py`),
  and the "Released packages (recommended):" block it emits.
- The `pypi_marketplace_url` key from `haybale-visiongraph`'s pyproject, that
  repo's Pages deploy workflow, and the deployed file.

No deprecation window — it has no consumers. `tests/test_share_readme_markers.py`
has two tests naming it directly (`test_share_save_writes_pypi_link_from_config`,
`test_share_save_without_pypi_config_omits_the_link`); they go with it.

## Stage 4 — the default subscription — **LANDED**

> **Unblocked and landed 2026-08-29.** The gate was that the curated feed had to
> be live first — a default subscription to a URL that 404s gives every fresh
> install a `RefreshOutcome.UNAVAILABLE` source with no cached body to fall back
> on, and nothing tells the user it is expected.
>
> Verified against the live feed before wiring it in: all six published URLs
> return 200; `stable` and `latest` carry `haybale-visiongraph==0.0.38` while
> `edge` carries the bare name; every row parses with the consumer's own
> `parse_global_marketplace`; `name`/`version` are exactly `str`; and no row
> leaks the cache-only `via`/`last_seen`/`stale` fields.

`ensure_marketplace_config()`
(`barn/haybale-marketplace/haybale_marketplace/config.py:24`)
writes with `toml.dumps(_DEFAULT_MARKETPLACE)`, so no comments survive. Replace
the dict with a text template that writes:

- Two active `[[markets]]`: the Official feed, and
  `https://going-haywire.github.io/marketplace/stable/marketplace.toml`.
- `edge` and `latest` as **commented-out** `[[markets]]` blocks, each with the
  one line that says what it asserts.
- The archive index URL, commented.

This file is the only way to change a subscription (there is no unsubscribe
UI, by decision), so it is the one place a user is guaranteed to open. The
alternatives belong in front of them there.

Existing installs are untouched — the function only writes when the file is
absent.

## Stage 5 — the marketplace repo (separate session, separate repo)

Executed from
[2026-08-28-marketplace-repo-buildout.md](2026-08-28-marketplace-repo-buildout.md),
which is deliberately **standalone**: it assumes no access to this working tree
and inlines every format spec and constraint it needs. Do not duplicate its
content here — it is the one place that plan's reader will look.

What this repo needs to know about it:

- It ships the README drafted at
  [2026-08-27-curated-marketplace-README.md](2026-08-27-curated-marketplace-README.md)
  verbatim.
- Its first successful deploy is what **unblocks Stage 4**. Nothing else in
  this repo waits on it.
- It builds against a *published* `haywire-core`, so Stage 2's exact-pinning
  change reaches it only after a release. Build it against the fixed generator's
  behaviour, not the current one.

## Stage 6 — docs — **LANDED**

Done, in `a446ec07` and `c8599d00`:

- `docs/reference/files/marketstall-toml.md` — `distribute`, the pinning rule,
  the `pypi_marketplace_url` removal.
- `docs/guides/publish-to-pypi.md` — rewritten. It described the deleted model
  (hand-written feed on Pages + `pypi_marketplace_url`), so following it would
  have rebuilt exactly what Stage 3 removed.
- `docs/guides/sharing-libraries.md` — `distribute` and the one-coordinate rule.

Done with Stage 4, now that the things they describe exist:

- `docs/guides/subscribing-to-marketplaces.md` — a new §1.0 covering what a
  fresh install already subscribes to, the three channels and what each proves,
  how to switch by editing the file, the one-channel-at-a-time rule, the
  archives, and what being listed does *not* mean.
- `docs/reference/files/marketplace-toml.md` — the default file now has two
  subscriptions and is written from a text template so its comments survive.
- [glossary.md](../../reference/glossary.md) — already written during the
  inquisition. Re-read it after Stage 3; the `distribute` and
  *one coordinate per version* entries describe behaviour that lands there.

## Sequencing

```text
Stage 1   LANDED  96532c13  parse-boundary normalisation
Stage 2   LANDED  c8599d00  ─┐ install_spec names the exact version,
Stage 3   LANDED  c8599d00  ─┘ in both writers
          LANDED  4b841ba8  docs staged from new dirs; one URL per README block
Stage 5   LANDED            separate repo, first tag published 2026-08-29
Stage 4   LANDED            default = official feed + curated stable
Stage 6   LANDED            reference + all three guides
```

**The plan is complete.** `haybale-visiongraph 0.0.38` is published to PyPI and
carried by all three channels.

Remaining, and outside this repo:

- The stale `going-haywire.github.io/haybale-visiongraph/marketplace.toml` is
  still served and no longer updated. Deleting that `gh-pages` branch needs a
  push.
- The curated repo's own follow-ups live in its README and issue tracker, not
  here.

Stages 1, 2 and 3 are independent of the new repo and can land in any order;
each is worth doing on its own merits regardless of whether the curated
marketplace ever ships. Stage 4 is the only ordering constraint in the plan,
and it is a hard one — see the warning on that stage.

## Traps

- `tests/studio/test_docs/test_generate.py`'s teardown runs
  `git checkout -- barn/haybale-testing`, discarding uncommitted work there.
  Commit before running the suite (`.insights/project_docs_test_reverts_barn_testing.md`).
- Do not call `generate_docs()` in-process from anywhere in Stage 5's tooling —
  it repoints the global injector and instantiates every node
  (`.insights/project_docs_gen_reentrancy.md`).
- The `_format_value()` path in `generate_marketstall.py` and the `toml.dumps`
  path in `write_marketstall()` are two serializers for one format. Stage 1
  fixes the input side; consider whether Stage 2 should collapse them onto one
  writer rather than leaving a second chance to diverge.
