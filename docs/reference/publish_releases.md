# Publishing Releases

This document is the operational reference for cutting a release of the haywire monorepo's
Tier 1+2 packages and deploying the marketplace. It defines both the *why* and the *how* —
prerequisites, configuration locations, release procedure, and recovery procedures.

## TL;DR

```sh
/release           # shows what would ship, bumps, opens the release PR;
                           # "yes" merges it → the merge run tags and publishes
```

That's the whole flow. **A release is the merge of a release PR**
([ADR 0088](../adr/0088-a-release-is-the-merge-of-a-release-pr-and-ci-tags-it.md)): nobody
pushes a tag. The rest of this page is reference: prerequisites, configuration locations,
recovery procedures, and per-step detail.

## Prerequisites (one-time)

### PyPI Trusted Publisher

Each package in `[tool.haywire.release].pip_publish_order` must be registered as a Trusted
Publisher on PyPI before the first publish workflow run.

For each package name in `pip_publish_order`:

1. Reserve the project on PyPI: create an account, claim the name (if not already present),
   then go to **Project → Settings → Publishing**.
2. Click **Add a new pending publisher** (for first-time projects) or **Add a new trusted
   publisher** (for already-published projects).
3. Fill in:
   - **Owner:** `going-haywire`
   - **Repository name:** `haywire`
   - **Workflow name:** `publish.yml`
   - **Environment name:** `pypi` (matches `.github/workflows/publish.yml`)
4. Save. Repeat for every package.

No PyPI API tokens are needed. The workflow authenticates via OIDC.

### GitHub Pages

The workflow's final job deploys the generated marketplace to GitHub Pages on the `gh-pages`
branch. Enable Pages once:

1. Repo **Settings → Pages**.
2. **Source:** Deploy from a branch.
3. **Branch:** `gh-pages` / `/ (root)`.
4. Save.

The first publish workflow run creates the `gh-pages` branch automatically. After that, the
URL `https://going-haywire.github.io/haywire/marketplace.toml` resolves.

## Configuration locations

| What | Where | Read by |
| --- | --- | --- |
| Release membership & publish order | `pyproject.toml [tool.haywire.release]` (repo root) | bump script, marketstall generator, CI workflow |
| Marketstall generator defaults | `pyproject.toml [tool.haywire.marketstall]` (repo root) | marketstall generator |
| Package versions | each package's `pyproject.toml` `[project] version` | bump script, `@library` decorators (via `importlib.metadata`) |
| Inter-package version constraints | each package's `pyproject.toml` `[project] dependencies` | uv at install time, bump script at release time |
| CI workflow | `.github/workflows/publish.yml` | GitHub Actions |
| Marketplace output | `marketplace.toml` (generated, deployed to `gh-pages`) | subscribers via the GitHub Pages URL |

### `[tool.haywire.release]` schema

```toml
[tool.haywire.release]
# Canonical machine-readable list of releasable packages.
# Consumed by: scripts/bump_version.py (this repo),
#              scripts/generate_marketstall.py,
#              .github/workflows/publish.yml.
# Order is significant for the publish workflow: dependencies first.

# Packages published to PyPI on every release tag, in dependency order.
pip_publish_order = [
    "haywire-core",
    "haywire-studio",
    "haybale-core",
    "haybale-studio",
    "haybale-marketplace",
    "haybale-share",
    "haybale-graph-editor",
    "haybale-haystack",
    "haybale-models",
    "haybale-image",
    "haybale-audio",
]

# Packages published via git subdirectory URL (binary deps or deferred from PyPI).
# Versioned in lockstep; installed as git+<source_url>#subdirectory=<pkg dir>.
git_publish_order = []

# Packages versioned in lockstep with the release but NOT published anywhere.
# The bump script updates these too so internal users stay coherent.
lockstep_unpublished = [
    "haybale-example",
    "haybale-testing",
    "haybale-TEST_A",
]
```

This is the **single source of truth** for release membership. The bump script
(`scripts/bump_version.py`), the marketstall generator (`scripts/generate_marketstall.py`),
and the CI publish workflow all read from this section. The spec's §5 tier table is human
documentation only; if it ever disagrees with this section, the section wins.

### `[tool.haywire.marketstall]` schema

```toml
[tool.haywire.marketstall]
# source_url/docs_branch describe this repo's canonical remote. Currently
# read but unconsumed by the generator: each entry's `origin` now comes
# from haybale.toml / the git remote via the shared marketstall builder
# (haywire.core.publishing.marketstall), not from these repo-level values.
source_url = "https://github.com/going-haywire/haywire"
docs_branch = "master"
```

## Release procedure

### Local phase (author-driven)

1. Run `/release`. It starts with *What this release would ship* (the commits since
   the last tag by type, the libraries whose dependency floor waits for a release, the open
   reminders, a proposed version) and then asks for the new version (e.g. `0.0.2`).
2. The skill checks that CI passed on `master` for the commit being released; it does not run the gate tests locally. A failed or missing run stops here.
3. The skill patches every `pyproject.toml` referenced by `pip_publish_order + lockstep_unpublished`:
   - `[project] version = "0.0.2"`
   - All `>=` inter-package constraints updated to the new floor (e.g. `haywire-core>=0.0.2`).
4. The skill re-locks (`uv lock`) and **bakes the docs**
   (`scripts/bake_docs.py --version v0.0.2`) — this regenerates the gitignored
   `packages/haywire-core/src/haywire/_baked_docs/` tree the haywire-core wheel
   ships as `haywire/docs/` (see [Baked docs](#baked-docs) below). The bake runs
   *after* the bump because it embeds the new tag in source-file GitHub URLs.
5. The skill shows a unified diff of every changed file and asks for confirmation.
6. On confirm: commit (`chore: release v0.0.2`) on `release/v0.0.2`, then a local
   `uv build --package haywire-core` smoke to prove the wheel builds from the
   baked docs, then it opens the release PR.
7. Once the PR's checks are green, the skill merges it: the "yes" in step 5 is the word to
   merge, and so to publish. The merge starts the CI phase.

The PR's title must start `chore: release v`: `scripts/check_version_changes.py` fails any
other PR that changes a package version.

To run the local phase manually (without the skill):

```sh
gh run list --branch master --workflow CI --limit 1   # gate: CI passed on master
git switch -c release/v0.0.2
uv run python scripts/bump_version.py 0.0.2     # bump every pyproject
uv lock                                                # re-pin uv.lock
uv run python scripts/bake_docs.py --version v0.0.2    # bake docs (AFTER the bump)
git add -u                                             # baked dir is gitignored
git commit -m "chore: release v0.0.2"
uv build --package haywire-core                        # smoke: wheel builds from baked docs
git push -u origin release/v0.0.2
gh pr create --base master --title "chore: release v0.0.2" --body "Version bump to 0.0.2."
gh pr checks --watch
gh pr merge --squash                                   # the merge publishes
```

### Baked docs

Farmhand serves the full `docs/` tree to an attached agent as MCP resources. Raw
`docs/` is unservable — `--8<--` snippet directives, relative cross-links, and
source-file links that don't resolve over MCP — so `scripts/bake_docs.py` bakes
every `docs/*.md` to pure markdown (snippets expanded; `.md` links →
`farmhand://docs/...`; source links → versioned GitHub `blob`/`tree` URLs) into a
gitignored `packages/haywire-core/src/haywire/_baked_docs/` mirror. The
haywire-core wheel force-includes that mirror as `haywire/docs/`; the sdist
includes it too, so the from-sdist wheel build finds it.

The bake is **not** committed (the output is generated), so it must run as part of
each release — which is why it lives in the local phase above, keyed to the new
tag. A `pytest` gate (`tests/farmhand/test_doc_keys_resolve.py`) asserts every
hand-authored `lib:kind:id` registry key in the docs resolves, failing CI on
drift. In a dev checkout, running the bake once makes a from-source studio serve
the baked docs too; otherwise it falls back to the raw `docs/` tree.

### CI phase (on a push to `master`, or a pushed tag)

`.github/workflows/publish.yml` runs on every push to `master`, on a pushed `v*.*.*` tag
and on a manual dispatch. Its first job, `plan`, runs `scripts/release_plan.py`:

| Trigger | Result |
| --- | --- |
| Push to `master`, lockstep version differs from the latest `v*` tag | A release: every job below runs, and `tag` creates `v<version>` on the pushed commit |
| Push to `master`, version equals the latest tag | No release: `plan` ends green, every other job is skipped |
| Push to `master`, version names an older tag | Fails: the tree's version is tagged but not the latest |
| A `v*.*.*` tag pushed by hand | A release of that tag; `tag` is skipped (recovery, see below) |
| Manual dispatch on `master` | A release of the tree's version; the tag is created only if it is missing |
| Anything else | No release |

The lockstep version is the one in `packages/haywire-core/pyproject.toml`. Runs of the
workflow queue (`concurrency: publish-release`), so a push waits for the run before it and
its `plan` sees the tag that run made.

The jobs run in this order: `plan` → `gate` → `build` → `tag` → `publish` →
`deploy-marketstall` → `release-notes`. A failed gate or build therefore leaves no tag.

#### Job gate

```sh
pytest -m "not integration and not browser and not perf"
```

Failure stops the pipeline. Nothing is tagged or published.

#### Job build — all wheels

First, `scripts/check_release_versions.py --expect <version>` asserts that the version being
released matches what is actually committed: every package in `[tool.haywire.release]` at
that one version, and every `haybale.toml` in sync with its own `pyproject.toml`. Since the
bump is a step of the release PR, this is the only thing standing between a forgotten
`scripts/bump_version.py` run (a tag pushed by hand without a bump) and a green release that
publishes nothing — `publish` reads its versions from `pyproject.toml`, would find the
previous release already on PyPI, and skip every package as "already published". Failure
stops the pipeline before any wheel is built.

Then, for every package in `pip_publish_order`, run `uv build` and collect the resulting wheel and sdist
into the workflow's artifact storage. All builds happen before anything is tagged or
published — a build failure in any package stops the pipeline before anything reaches PyPI.
This catches build errors (missing files, invalid metadata, dependency resolution failures)
without leaving partial state on PyPI.

#### Job tag

Creates `v<version>` on the pushed commit (`contents: write`, a `GITHUB_TOKEN` push). It runs
only when `plan` found a tag to create, and only after `build` passed. The `Release tags`
ruleset forbids deleting or moving a `v*` tag but allows creating one, so the job can do
this and nobody can undo it. A tag pushed with `GITHUB_TOKEN` starts no further workflow run,
so the new tag does not start a second publish.

If this job fails, `publish` does not run.

#### Job publish — wheels (sequential, dependency order, idempotent, fail-fast)

For each package in `pip_publish_order`:

1. Check whether `name == version` already exists on PyPI
   (`GET https://pypi.org/pypi/<name>/<version>/json` → 200 means already published).
2. If it exists, skip — already done in a previous run.
3. Otherwise: `uv publish` the wheel and sdist from the build job's artifacts via PyPI Trusted
   Publisher (OIDC, no stored token).

Any failure stops remaining packages. The idempotent skip makes a re-run of the failed job safe.

#### Job deploy-marketstall

Runs only if `publish` succeeded.

```sh
uv run python scripts/generate_marketstall.py --out-dir gh-pages-content
```

The generator reads each package's `pyproject.toml` and `__init__.py`, emits `source = "pypi"`
entries with bare `haybale-*` sibling dependency names, writes the two-tier aggregator layout
(top-level `marketplace.toml` plus one `stalls/<dist-name>.toml` per published library),
and the workflow deploys the entire directory to GitHub Pages at:

```text
https://going-haywire.github.io/haywire/marketplace.toml
```

#### Job release-notes

Runs only if the marketstall deployed. Creates the GitHub Release for the tag with
`gh release create v<version> --generate-notes` (the merged PRs since the previous release);
it skips if the release exists.

### Release reminders

A library outside the monorepo may record, with the owner's agreement, a dependency to
raise once a core release contains a change: an `after-core-release` issue with a
`Waits for: going-haywire/haywire@<sha>` line
([sharing-libraries §7.1](../guides/sharing-libraries.md#71-release-reminders)).
After a publish, `/release` (Step 10) lists those reminders across the
organisation and which of them the new tag contains, plus the libraries whose dependency
floor the new tag now satisfies (`floors --ref`); before the bump (Step 0) it shows the
libraries still waiting for a core release (`floors`) and the Author API names the release
removes with the libraries that import them (`names`). All come from
`scripts/release_sweep.py`. Open `todo-pre-release` reminders in this repository are
listed in Step 0.3, and the user decides whether to release anyway.

## Recovery procedures

A tag is permanent: the `Release tags` ruleset forbids deleting or moving a `v*` tag, so no
recovery below involves removing one. Recovery is a re-run, or a fix through a PR.

### Gate or build failure

The `gate` or `build` job failed. Nothing is tagged and nothing is published. Fix the cause
through a PR. While `master` carries a version without a tag, any push to `master` is a
release of that version, so the fix's own merge tags and publishes it: hold other merges
until the fix is in. To release a different version instead, open a new release PR with it.

### Partial publish failure

If `publish` fails partway (e.g. `haybale-haystack` publishes, `haybale-example` fails), the
tag exists:

1. Identify the cause from CI logs:
   - **First-time setup**: Trusted Publisher not configured for the failing package, or the
     package was never published before and needs the PyPI "claim" step (see Prerequisites
     above).
   - **Transient**: PyPI hiccup, network timeout, OIDC blip — retry usually works.
   - **Permanent**: PyPI rejected metadata (rare; signals a real package issue).
2. Fix the cause.
3. Re-run only the failed jobs of that run:

    ```sh
    gh run rerun <run-id> --failed
    ```

4. The `publish` job's idempotent skip ensures already-published packages are not
   re-published. The workflow resumes at the failed package, then deploys the marketstall and
   writes the release notes.

A full re-run of the same run finds the tag and ends green without publishing: use
`--failed`. Alternatively dispatch the workflow on `master`
(`gh workflow run publish.yml --ref master`), which releases the tree's version again and
creates the tag only if it is missing.

**Do not bump the version** for transient or configuration failures. PyPI keeps versions
monotonic; orphaned versions never arise because one run drives all publishes.

The only case where bumping is correct: a package was rejected for irrecoverable metadata
reasons that require a code fix. That's rare and signals a problem with the package, not the
release flow.

### The tag job failed

`publish` does not run without the tag. The usual cause is the `Release tags` ruleset
refusing the creation (it must allow creating `v*` tags and forbid deleting or moving them),
or `contents: write` missing. Fix the ruleset or the permission, then re-run the failed
jobs. The ruleset is the maintainer's to change.

### Marketplace deploy or release-notes failure

`publish` succeeded but the marketplace deploy (GitHub Pages misconfiguration, transient
deploy issue) or the release notes failed. Fix the cause and re-run the failed jobs:

```sh
gh run rerun <run-id> --failed
```

`publish` is not repeated; the workflow walks on to the failed job.

### Publishing a tag by hand (last resort)

If the merge run cannot be recovered by a re-run, the user may push a `v*.*.*` tag on the
commit to release. The workflow then publishes that tag with `tag` skipped. The agent hook
`block-dangerous-git.sh` blocks a tag push from an agent session, so this step is always the
user's, in their own terminal. The tag must name the committed version
(`scripts/check_release_versions.py` refuses it otherwise).

## Adding a new package to the release set

1. Add the pip distribution name to `[tool.haywire.release].pip_publish_order` in the workspace
   root `pyproject.toml`. Insert it at the correct position (after all its dependencies).
2. Register the new package as a Trusted Publisher on PyPI (see Prerequisites above).
3. Confirm `uv build --package <name>` works locally.
4. Confirm `uv run python scripts/generate_marketstall.py` includes the package.
5. Cut the next release; the new package will publish on the same tag as the rest.

## Moving a package between tiers

### `lockstep_unpublished` → `pip_publish_order` (start publishing)

A package is in `lockstep_unpublished` because it's not yet ready for PyPI (e.g.
`haybale-visiongraph` has binary deps) or is internal-only. To start publishing it:

1. Move the package name from `lockstep_unpublished` to `pip_publish_order` in
   `[tool.haywire.release]`, at the correct dependency position.
2. Register the new package as a Trusted Publisher on PyPI.
3. Verify `uv build --package <name>` succeeds.
4. Update the §5 tier table.

On the next release, the package is published to PyPI for the first time. Existing users who
installed via `source = "git"` (from a third-party marketstall, if any) keep their git install
until they re-install; the new marketplace has `source = "pypi"` for new installs.

### `pip_publish_order` → `lockstep_unpublished` (stop publishing)

1. Move the package name from `pip_publish_order` to `lockstep_unpublished`.
2. Update the §5 tier table.

The next release stops publishing this package. Already-published PyPI versions remain
available but are no longer updated. The bump script still keeps the package's version in
lockstep so internal users stay coherent.

### `lockstep_unpublished` → removed entirely (deprecate)

If a package is being removed from the monorepo altogether, remove it from
`lockstep_unpublished` AND delete its workspace directory. The bump script will no longer
touch it. The PyPI registration (if any) stays in place — PyPI does not let you "unpublish",
but skipping further releases is enough.
