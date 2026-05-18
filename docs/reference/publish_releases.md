# Publishing Releases

This document is the operational reference for cutting a release of the haywire monorepo's
Tier 1+2 packages and deploying the marketstall. It is the human-facing companion to the
[versioning-and-publishing spec](../../internals/specs/versioning-and-publishing.md), which
defines the *why* and *what*; this page defines the *how* and *where*.

## TL;DR

```sh
/haywire-release           # interactive: enter version, runs tests, tags, pushes
                           # → CI takes over from here
```

That's the whole flow. The rest of this page is reference: configuration locations, recovery
procedures, and per-step detail.

## Configuration locations

| What | Where | Read by |
| --- | --- | --- |
| Tier membership & publish order | `pyproject.toml [tool.haywire.release]` (repo root) | bump script, marketstall generator, CI workflow |
| Package versions | each package's `pyproject.toml` `[project] version` | bump script, `@library` decorators (via `importlib.metadata`) |
| Inter-package version constraints | each package's `pyproject.toml` `[project] dependencies` | uv at install time, bump script at release time |
| CI workflow | `.github/workflows/publish.yml` | GitHub Actions |
| Marketstall output | `marketstall.toml` (repo root, generated) | subscribers via raw URL |
| Marketstall deploy target | CI workflow + GitHub Pages config | GitHub Pages |

### `[tool.haywire.release]` schema

```toml
[tool.haywire.release]
# Framework packages — published to PyPI, must build before any Tier 2 package
tier1 = ["haywire-core", "haywire-studio"]

# Official haybale libraries published to PyPI
tier2_pypi = [
    "haybale-core",
    "haybale-studio",
    "haybale-graph-editor",
    "haybale-haystack",
    "haybale-example",
]

# Official haybale libraries distributed via git only (not PyPI)
tier2_git = ["haybale-visiongraph"]

# Internal-only — never published
tier3_internal = ["haybale-testing", "haybale-TEST_A"]

# Dependency-aware publish order — must be a topological sort of tier1 + tier2_pypi
publish_order = [
    "haywire-core",
    "haywire-studio",
    "haybale-core",
    "haybale-studio",
    "haybale-graph-editor",
    "haybale-haystack",
    "haybale-example",
]
```

This is the **single source of truth** for tier membership. The bump script, marketstall
generator, and CI publish job all read from this section. The spec's §5 tier table is human
documentation only; if it ever disagrees with this section, the section wins.

## Release procedure

### Local phase (author-driven)

1. Run `/haywire-release` — the skill prompts for the new version (e.g. `0.0.2`).
2. The skill runs the gate tests: `pytest -m "not integration"`. Failure stops here.
3. The skill patches all `pyproject.toml` files listed in `tier1 + tier2_pypi + tier2_git`:
   - `[project] version = "0.0.2"`
   - All `~=` inter-package constraints updated to the new floor (e.g. `haywire-core~=0.0.2`).
4. The skill shows a unified diff of every changed file and asks for confirmation.
5. On confirm: commit (`chore: release v0.0.2`), tag (`v0.0.2`), push branch + tag.
6. CI takes over.

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

#### Job 4 — deploy marketstall

Runs only if Job 3 succeeded.

```sh
python scripts/generate_marketstall.py
```

The generator reads each Tier 1+2 `pyproject.toml`, emits `source = "pypi"` entries with `~=`
version constraints on dependencies, writes `marketstall.toml` at the repo root, and the
workflow deploys it to GitHub Pages at:

```
https://maybites.github.io/haywire/marketstall.toml
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
     package was never published before and needs the PyPI "claim" step.
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
5. Once all packages publish, Job 4 deploys the updated marketstall.

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

### Marketstall deploy failure (Job 4)

Job 3 succeeded but the marketstall deploy failed (GitHub Pages misconfiguration, transient
deploy issue). Fix the cause and re-run only Job 4:

```sh
gh workflow run publish.yml --ref v0.0.2 --field job=deploy-marketstall
```

(Requires the workflow to expose `job` as a `workflow_dispatch` input.)

## Adding a new Tier 1+2 package

1. Add `[tool.haywire.release]` entries:
   - List the new package under `tier1` or `tier2_pypi` (or `tier2_git`/`tier3_internal`).
   - Insert it into `publish_order` at the correct position (after all its dependencies).
2. Verify the package's own `pyproject.toml` has `version = "<current monorepo version>"`
   and correct `~=` constraints.
3. Configure PyPI Trusted Publisher for the new package name (one-time, via the PyPI web UI).
4. Update the §5 tier table in
   [versioning-and-publishing.md](../../internals/specs/versioning-and-publishing.md) for
   human documentation.

The next release will publish the new package automatically.

## Moving a package between tiers

### Tier 2 git-only → Tier 2 PyPI

1. Move the package name from `tier2_git` to `tier2_pypi` in `[tool.haywire.release]`.
2. Add it to `publish_order` at the correct dependency position.
3. Configure PyPI Trusted Publisher for the package name (one-time, via PyPI web UI).
4. Update the §5 tier table.

On the next release, the package is published to PyPI for the first time. Existing
subscribers who installed via `source = "git"` keep their git install until they re-install;
the new marketstall has `source = "pypi"` for new installs.

### Tier 2 PyPI → Tier 3 internal

1. Move the package name from `tier2_pypi` to `tier3_internal`.
2. Remove it from `publish_order`.
3. Update the §5 tier table.

The next release stops publishing this package. Already-published PyPI versions remain
available but are no longer updated.
