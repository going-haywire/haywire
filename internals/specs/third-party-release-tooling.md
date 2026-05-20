# Third-Party Release Tooling Spec

**Status:** staked — awaiting implementation
**Date:** 2026-05-18
**Author:** going-haywire

---

## Problem

The third-party authoring contract — what `pyproject.toml` must contain, what the `@library`
decorator requires, what `marketstall.toml` looks like — is documented in
[`docs/components/haybale-package/haybale-package-canon.md`](../../docs/components/haybale-package/haybale-package-canon.md) §5 (the compliance contract)
and [`marketstall-distribution.md`](./marketstall-distribution.md) (the marketstall schema).
This spec covers the **tooling layer** that makes living up to that contract ergonomic for
external authors.

Without tooling, a third-party author who wants to publish their library to PyPI has to:

1. Hand-author a CI workflow (PyPI Trusted Publisher, build matrix, tag triggers).
2. Manually bump the `pyproject.toml` version on every release.
3. Manually regenerate `marketstall.toml` after every publish.
4. Manually deploy the marketstall to a host (GitHub Pages or similar) so subscribers can fetch it.
5. Hand-write commit messages, tags, and release notes.

This is a lot of boilerplate to reproduce per author. It also risks ecosystem fragmentation:
different authors will solve the same problem in subtly incompatible ways.

This spec defines the **tooling layer** that makes third-party publishing as ergonomic as the
monorepo's own release flow.

---

## Goals

1. A third-party author can release a haybale library to PyPI with one command.
2. The release flow is identical in shape to the monorepo's flow — same skill, same CI templates.
3. The tooling auto-detects whether it is operating on the monorepo or on an external repo.
4. The marketstall is regenerated and deployed as part of the release flow.
5. No author-specific code paths in the release tooling — everything is parameterised.

## Non-goals

- This spec does NOT define the marketstall format, `@library` requirements, or `pyproject.toml`
  conventions. Marketstall format is in [`marketstall-distribution.md`](./marketstall-distribution.md);
  `@library` and `pyproject.toml` conventions are in
  [`docs/components/haybale-package/haybale-package-canon.md`](../../docs/components/haybale-package/haybale-package-canon.md).
- This spec does NOT cover non-PyPI publishing. Git-only libraries are already handled by
  `haywire share --save`.
- This spec does NOT cover discovery (how subscribers find third-party marketstalls). That
  belongs to the marketstall feed UX work tracked in the parent spec.

---

## Decisions

### 1. One skill, two modes

`/haywire-release` (T8 in the parent spec) is generalised to detect repo type at invocation:

- **Monorepo mode** — detects the haywire dev repo by presence of `packages/haywire-core/`
  and the multi-package layout. Runs the monorepo-specific tier-aware bump + tag + push.
- **Single-package mode** — detects a third-party haybale library by presence of a top-level
  `pyproject.toml` with `[project] name = "haybale-*"`. Runs a single-package bump + tag + push.
- **Multi-library project mode** — detects a project with multiple barn libraries (presence of
  `barn/` with multiple `haybale-*` directories). Runs the multi-package flow against the
  project's own libraries.

Detection happens before any prompts. If the repo type is ambiguous, the skill asks the user
to disambiguate.

### 2. Reusable CI workflow templates

The repo ships three reusable workflow templates under
`packages/haywire-studio/templates/ci/`:

```
ci/
├── publish-monorepo.yml      ← what the monorepo itself uses
├── publish-single.yml        ← single-package third-party library
└── publish-multilib.yml      ← multi-library project repo
```

Each is a complete `.github/workflows/publish.yml` that:

1. Triggers on tag `v*.*.*`.
2. Runs the gate tests (`pytest -m "not integration"`).
3. Builds and publishes to PyPI via Trusted Publisher (OIDC).
4. Regenerates `marketstall.toml`.
5. Deploys the marketstall to GitHub Pages.

Templates are parameterised by:

- Package name(s) — derived from `pyproject.toml`.
- Marketstall deploy target — defaults to GitHub Pages, configurable to other static hosts.
- Test command — defaults to `pytest -m "not integration"`, configurable.

The user copies the appropriate template into `.github/workflows/` via:

```sh
haywire init-ci [--type=single|multilib]
```

The command auto-detects the type if `--type` is omitted.

### 3. PyPI Trusted Publisher setup

The author's responsibility is to configure PyPI Trusted Publisher on their account; this
spec does not automate that (it requires a logged-in PyPI session). The skill prints
step-by-step instructions:

```
1. Visit https://pypi.org/manage/account/publishing/
2. Add a pending publisher with:
   - PyPI Project Name: haybale-foo
   - Owner: <github-user>
   - Repository name: <repo-name>
   - Workflow filename: publish.yml
   - Environment name: pypi
3. Push your first tag to trigger the workflow.
```

The skill detects whether Trusted Publisher is configured by attempting a dry-run publish
on the first release; if it fails with the OIDC error, it surfaces the instructions inline.

### 4. Marketstall regeneration

`scripts/generate_marketstall.py` from the parent spec (T3) is generalised to read package
metadata from any `pyproject.toml` in the repo, not just the monorepo's hardcoded list.

In single-package mode it produces a one-entry marketstall.
In multi-library mode it produces an N-entry marketstall.
In monorepo mode it produces the full Tier 1+2 marketstall.

Detection rule: same as `/haywire-release` repo-type detection.

The script writes `marketstall.toml` to the repo root regardless of mode.

### 5. Marketstall hosting

Default hosting target is GitHub Pages, configured via the CI workflow template. Alternative
hosts (Cloudflare Pages, Netlify, a personal server) are supported via the template's
`deploy_target` parameter.

The spec does NOT define how subscribers discover the marketstall URL — that belongs to the
parent spec's deferred feed-subscription UX.

### 6. Versioning model for third-party libraries

Third-party authors choose between two versioning models:

- **Lockstep** — multi-library repos may release all libraries at the same version (same as
  the monorepo). Default for `multi-library project mode`.
- **Independent** — single-library repos release on their own cadence. Default for
  `single-package mode`.

The skill detects the right default from repo type. The user can override via a prompt.

`~=` constraints across third-party haybale libraries follow the same convention as the
parent spec.

---

## Implementation tasks

Depends on completion of T1-T12 in the parent spec.

- [ ] **C1** — `/haywire-release` repo-type detection (monorepo / single / multilib)
- [ ] **C2** — Generalise `scripts/generate_marketstall.py` to read any repo
- [ ] **C3** — CI workflow templates (`publish-monorepo.yml`, `publish-single.yml`, `publish-multilib.yml`)
- [ ] **C4** — `haywire init-ci` command to scaffold the right template
- [ ] **C5** — PyPI Trusted Publisher dry-run probe with inline setup instructions
- [ ] **C6** — Per-mode test plan covering all three repo types

---

## Open / deferred

- **Marketstall subscription UX** — how a subscriber adds a third-party marketstall URL is
  covered by the parent spec's deferred work.
- **Non-GitHub hosting** — Cloudflare Pages, GitLab Pages, personal servers. Templates can be
  added per request; not in the initial scope.
- **Private PyPI registries** — only public PyPI is in scope. Private/internal registries
  would need their own workflow template.
- **Auth-required git sources** — same scope limit as the parent spec.
