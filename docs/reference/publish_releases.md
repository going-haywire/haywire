# Publishing Releases

This document is the operational reference for cutting a release of the haywire monorepo's
Tier 1+2 packages and deploying the marketplace. It defines both the *why* and the *how* —
prerequisites, configuration locations, release procedure, and recovery procedures.

## TL;DR

```sh
/haywire-release           # interactive: enter version, runs tests, tags, pushes
                           # → CI takes over from here
```

That's the whole flow. The rest of this page is reference: prerequisites, configuration
locations, recovery procedures, and per-step detail.

## Prerequisites (one-time)

### PyPI Trusted Publisher

Each package in `[tool.haywire.release].publish_order` must be registered as a Trusted
Publisher on PyPI before the first publish workflow run.

For each package name in `publish_order`:

1. Reserve the project on PyPI: create an account, claim the name (if not already present),
   then go to **Project → Settings → Publishing**.
2. Click **Add a new pending publisher** (for first-time projects) or **Add a new trusted
   publisher** (for already-published projects).
3. Fill in:
   - **Owner:** `maybites`
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
# Packages published to PyPI on every release tag, in dependency order.
# The order is significant: the CI publish job walks this list sequentially.
publish_order = [
    "haywire-core",
    "haywire-studio",
    "haybale-core",
    "haybale-studio",
    "haybale-marketplace",
    "haybale-graph-editor",
    "haybale-haystack",
    "haybale-example",
]

# Packages versioned in lockstep with the release but NOT published.
# The bump script keeps these on the same version as `publish_order` so internal users
# (dev installs, internal test fixtures) stay coherent.
#  - haybale-visiongraph: Tier 2 git-only (binary deps, deferred from PyPI).
#  - haybale-testing, haybale-TEST_A: Tier 3 internal test fixtures.
lockstep_unpublished = [
    "haybale-visiongraph",
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
# Repo URL used as the source_url for every generated [[haybales]] entry.
# Also forms the base for the docs_url raw-githubusercontent URL.
source_url = "https://github.com/going-haywire/haywire"

# Default branch used in the raw-githubusercontent docs_url.
docs_branch = "main"

# Default author and tags applied when a package's @library decorator
# doesn't set them. Per-package values from the decorator always win.
default_author = "Haywire Team"
default_tags = []
```

## Release procedure

### Local phase (author-driven)

1. Run `/haywire-release` — the skill prompts for the new version (e.g. `0.0.2`).
2. The skill runs the gate tests: `pytest -m "not integration"`. Failure stops here.
3. The skill patches every `pyproject.toml` referenced by `publish_order + lockstep_unpublished`:
   - `[project] version = "0.0.2"`
   - All `~=` inter-package constraints updated to the new floor (e.g. `haywire-core~=0.0.2`).
4. The skill shows a unified diff of every changed file and asks for confirmation.
5. On confirm: commit (`chore: release v0.0.2`), tag (`v0.0.2`), push branch + tag.
6. CI takes over.

Until the `/haywire-release` skill ships (separate plan — spec T8), run the steps manually:

```sh
uv run python scripts/bump_version.py 0.0.2
git add packages/*/pyproject.toml barn/*/pyproject.toml uv.lock
git commit -m "chore: release v0.0.2"
git tag v0.0.2
git push origin main v0.0.2
```

### CI phase (on tag push `v*.*.*`)

#### Job 1 — gate

```sh
pytest -m "not integration"
```

Failure stops the pipeline. Nothing publishes.

#### Job 2 — build all wheels

For every package in `publish_order`, run `uv build` and collect the resulting wheel and sdist
into the workflow's artifact storage. All builds happen before any publish — a build failure
in any package stops the pipeline before anything reaches PyPI. This catches build errors
(missing files, invalid metadata, dependency resolution failures) without leaving partial
state on PyPI.

If Job 2 fails, nothing publishes. Fix the build error, push a new tag (or re-run the
workflow), and try again.

#### Job 3 — publish wheels (sequential, dependency order, idempotent, fail-fast)

For each package in `publish_order`:

1. Check whether `name == version` already exists on PyPI
   (`GET https://pypi.org/pypi/<name>/<version>/json` → 200 means already published).
2. If it exists, skip — already done in a previous run.
3. Otherwise: `uv publish` the wheel and sdist from Job 2's artifacts via PyPI Trusted
   Publisher (OIDC, no stored token).

Any failure stops remaining packages. The idempotent skip makes the workflow safe to re-run.

#### Job 4 — deploy marketplace

Runs only if Job 3 succeeded.

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

## Recovery procedures

### Build failure (Job 2)

A package failed to build. Nothing has been published — Job 3 only runs after Job 2 succeeds
for every package. Fix the build error, push the fix, re-run the workflow on the same tag (or
push a new tag if the fix is on a different commit).

### Partial publish failure (Job 3)

If Job 3 fails partway (e.g. `haybale-haystack` publishes, `haybale-example` fails):

1. Identify the cause from CI logs:
   - **First-time setup**: Trusted Publisher not configured for the failing package, or the
     package was never published before and needs the PyPI "claim" step (see Prerequisites
     above).
   - **Transient**: PyPI hiccup, network timeout, OIDC blip — retry usually works.
   - **Permanent**: PyPI rejected metadata (rare; signals a real package issue).
2. Fix the cause.
3. Re-run the workflow on the same tag:

    ```sh
    gh workflow run publish.yml --ref v0.0.2
    ```

4. Job 2 re-builds all wheels (idempotent; same inputs produce same outputs). Job 3's
   idempotent skip ensures already-published packages are not re-published. The workflow
   resumes at the failed package.
5. Once all packages publish, Job 4 deploys the updated marketplace.

**Do not bump the version** for transient or configuration failures. PyPI keeps versions
monotonic; orphaned versions never arise because the same tag drives all publishes.

The only case where bumping is correct: a package was rejected for irrecoverable metadata
reasons that require a code fix. That's rare and signals a problem with the package, not the
release flow.

### Gate test failure

Job 1 failed — nothing has been published. Fix the test, commit on `main`, retag with the
same version, force-push the tag (only the tag, never the branch):

```sh
git tag -d v0.0.2
git push origin :refs/tags/v0.0.2
git tag v0.0.2
git push origin v0.0.2
```

This triggers Job 1 again. The version number stays the same.

### Marketplace deploy failure (Job 4)

Job 3 succeeded but the marketplace deploy failed (GitHub Pages misconfiguration, transient
deploy issue). Fix the cause and re-run the workflow on the same tag:

```sh
gh workflow run publish.yml --ref v0.0.2
```

Job 3's idempotent skip means already-published packages are not re-published; the workflow
walks through to Job 4 and re-attempts the deploy.

## Adding a new package to the release set

1. Add the pip distribution name to `[tool.haywire.release].publish_order` in the workspace
   root `pyproject.toml`. Insert it at the correct position (after all its dependencies).
2. Register the new package as a Trusted Publisher on PyPI (see Prerequisites above).
3. Confirm `uv build --package <name>` works locally.
4. Confirm `uv run python scripts/generate_marketstall.py` includes the package.
5. Cut the next release; the new package will publish on the same tag as the rest.

## Moving a package between tiers

### `lockstep_unpublished` → `publish_order` (start publishing)

A package is in `lockstep_unpublished` because it's not yet ready for PyPI (e.g.
`haybale-visiongraph` has binary deps) or is internal-only. To start publishing it:

1. Move the package name from `lockstep_unpublished` to `publish_order` in
   `[tool.haywire.release]`, at the correct dependency position.
2. Register the new package as a Trusted Publisher on PyPI.
3. Verify `uv build --package <name>` succeeds.
4. Update the §5 tier table.

On the next release, the package is published to PyPI for the first time. Existing users who
installed via `source = "git"` (from a third-party marketstall, if any) keep their git install
until they re-install; the new marketplace has `source = "pypi"` for new installs.

### `publish_order` → `lockstep_unpublished` (stop publishing)

1. Move the package name from `publish_order` to `lockstep_unpublished`.
2. Update the §5 tier table.

The next release stops publishing this package. Already-published PyPI versions remain
available but are no longer updated. The bump script still keeps the package's version in
lockstep so internal users stay coherent.

### `lockstep_unpublished` → removed entirely (deprecate)

If a package is being removed from the monorepo altogether, remove it from
`lockstep_unpublished` AND delete its workspace directory. The bump script will no longer
touch it. The PyPI registration (if any) stays in place — PyPI does not let you "unpublish",
but skipping further releases is enough.
