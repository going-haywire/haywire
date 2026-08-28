---
status: draft
doc_template: guide
scope: Publishing a haybale library to PyPI — account setup, name claim, Trusted Publisher CI, and the `distribute` declaration that turns your marketstall into a PyPI feed
see-also:
  - ./sharing-libraries.md
  - ./subscribing-to-marketplaces.md
  - ../haybale/haybale-canon.md
  - ../reference/publish_releases.md
---

# Publishing to PyPI — Author guide

[sharing-libraries](./sharing-libraries.md) gets your library to consumers as a **git clone** — they install from a tag or a branch of your repository. This guide covers the other distribution path: publishing the library as a **released package on PyPI**, so consumers `pip install haybale-my-lib` instead of cloning source.

**They are alternatives, not complements — pick one per project.** A library published at one version must have exactly one install coordinate. `identity_matches` treats a PyPI row and a git row of the same name as *different libraries*, so a consumer subscribed to two feeds that disagree about yours is asked to block one of two rows describing the same release. You declare which one you publish with `distribute`, in §5.

## 1. What it solves

Installing from git works, but it makes the consumer's machine do your build. `uv pip install "haybale-my-lib @ git+https://..."` literally runs `git clone` (shallow, when the ref resolves server-side) and then builds a wheel from the checkout — even with `#subdirectory=`, which filters *after* cloning the whole repo. That means the consumer needs `git`, network access to your host, credentials if the repo is private, and a working run of your build backend. It also means anything your build touches must be committed: gitignored files are simply absent for them, and LFS assets arrive as pointer text.

A PyPI release inverts all of that. The wheel is built once, by you, in CI — a fixed, self-contained artifact that resolves by version and never changes once uploaded.

Publishing to PyPI adds three things to the flow in [sharing-libraries](./sharing-libraries.md):

1. A **PyPI account** and a **claimed distribution name**.
2. A **CI workflow** that builds a wheel on every version tag and uploads it.
3. One line of config — `distribute = "pypi"` — which makes `haywire share` write PyPI coordinates into the `marketstall.toml` it already generates.

All three are one-time setup. After that, `haywire share --bump patch` pushes a tag and CI does the rest.

There is no separate feed to deploy. Your repo-root `marketstall.toml` **is** the feed, reachable at its raw URL; earlier versions of this guide had you publish a second, hand-written `marketplace.toml` to GitHub Pages, which existed only because that file was always git-flavoured.

## 2. Before you start — claim the name

PyPI distribution names are **globally unique and first-come**. Claim yours before you write any CI, because discovering the name is taken after you've wired everything up means renaming the package.

1. Create an account at [pypi.org/account/register](https://pypi.org/account/register/) and enable 2FA (required for uploads).
2. Check availability: visit `https://pypi.org/project/haybale-my-lib/`. A 404 means it's free.
3. Claim it by uploading once, or reserve it as part of your first real release below.

Your library's `pyproject.toml` `[project].name` **is** the distribution name. By convention haybale libraries are named `haybale-<something>`:

```toml
[project]
name = "haybale-my-lib"
version = "0.0.1"
description = "What your library does"
```

!!! note "Test it on TestPyPI first"
    [test.pypi.org](https://test.pypi.org) is a separate instance with separate accounts, made for exactly this. Publishing there first lets you verify the whole workflow without burning a version number on the real index — a version, once uploaded to PyPI, can never be reused even if you delete it.

## 3. Configure Trusted Publishing (no API tokens)

PyPI supports **Trusted Publishing** — your CI authenticates with an OpenID Connect identity instead of a long-lived API token. Nothing secret is stored in your repository. This is the recommended path and what the workflow below assumes.

On PyPI, go to your project → *Publishing* → *Add a new publisher* → *GitHub*, and fill in:

| Field | Value |
|---|---|
| Owner | your GitHub user or org |
| Repository | your repo name |
| Workflow name | `publish.yml` |
| Environment name | `pypi` |

The environment name must match the `environment:` block in the workflow. If you haven't uploaded yet, use PyPI's *pending publisher* form instead — it reserves the name and the trust relationship together, so your first upload is also your name claim.

## 4. The workflow

Copy this to `.github/workflows/publish.yml`. It builds and publishes a **single-package** repository on every `v*.*.*` tag.

**Edit the `env:` block at the top and nothing else.** Every value you need to change is collected there — distribution name, label, description, author, repo URL — and the steps below read them, so there are no placeholders buried further down the file. The version is never hardcoded: it is derived from the tag that triggered the run.

```yaml
name: Publish Release

on:
  push:
    tags:
      - 'v*.*.*'
  workflow_dispatch:

# ─────────────────────────────────────────────────────────────────────
# ADAPT THIS BLOCK — everything below it is generic and can stay as-is.
# ─────────────────────────────────────────────────────────────────────
env:
  PYTHON_VERSION: '3.12'

  # Your PyPI distribution name — must match [project].name in pyproject.toml.
  DIST_NAME: haybale-my-lib

jobs:
  build:
    name: Build wheel
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v3
        with:
          enable-cache: true

      - name: Set up Python ${{ env.PYTHON_VERSION }}
        run: uv python install ${{ env.PYTHON_VERSION }}

      - name: Install project
        run: uv sync --dev

      # Your gate. Keep it cheap and keep it here: a broken release is far
      # more expensive to withdraw from PyPI than to catch before upload.
      - name: Run tests
        run: uv run pytest -q

      - name: Build wheel + sdist
        run: |
          rm -rf dist/
          uv build

      - uses: actions/upload-artifact@v4
        with:
          name: dist
          path: dist/
          if-no-files-found: error

  publish:
    name: Publish to PyPI
    runs-on: ubuntu-latest
    needs: build
    environment:
      name: pypi                       # must match the Trusted Publisher config
      url: https://pypi.org/project/${{ env.DIST_NAME }}/
    permissions:
      contents: read
      id-token: write                  # required for Trusted Publishing (OIDC)
    steps:
      - uses: actions/download-artifact@v4
        with:
          name: dist
          path: dist/

      - name: Publish
        uses: pypa/gh-action-pypi-publish@release/v1
        # No `password:` — the OIDC identity above is the credential.
```

Everything descriptive — label, description, tags, authors — comes from your library's `haybale.toml` when `haywire share` writes the marketstall, so the workflow never restates it. That is why the `env:` block has one entry.

### Other CI providers

The only provider-specific part is the OIDC identity. GitLab CI, Circle, and others can publish to PyPI the same way — consult [the PyPI Trusted Publishers docs](https://docs.pypi.org/trusted-publishers/) for the provider list, and fall back to an API token (`UV_PUBLISH_TOKEN` / `TWINE_PASSWORD`) where OIDC isn't supported. The build step is always `uv build`; the upload is always `uv publish` or `twine upload dist/*`.

## 5. Declare how you distribute

Add one key to your **project root** `pyproject.toml`:

```toml
[tool.haywire.marketstall]
distribute = "pypi"   # or "git" (the default)
```

That is the whole configuration. On the next `haywire share`, every row in your `marketstall.toml` is written as a PyPI coordinate:

```toml
[[haybales]]
name         = "haybale-my-lib"
version      = "0.0.2"
source       = "pypi"
install_spec = "haybale-my-lib==0.0.2"
```

Note that `install_spec` pins the **exact version the row advertises**. It is not the bare distribution name: a row saying `version = "0.0.2"` that installed whatever PyPI currently served would make the Library Browser's update indicator (`installed < row.version`) never settle — it would offer an update forever, and clicking it would reinstall the same thing.

Your README's marker block is unchanged, and still lists two URLs:

````markdown
<!-- marketstall:share-url:start -->
Always the latest (tracks the current branch):

```sh
https://github.com/you/haybale-my-lib/blob/main/marketstall.toml
```

Frozen to this version:

```sh
https://github.com/you/haybale-my-lib/blob/v0.0.1/marketstall.toml
```
<!-- marketstall:share-url:end -->
````

One URL per fenced block, deliberately: a git host's copy button yields the
whole block, so two URLs sharing one fence means a reader aiming at either gets
both — and pasting that into Add Source fails.

Both now point at PyPI coordinates rather than clone specs. Subscribing to the first tracks your releases; the second freezes to the one you published at that tag.

!!! warning "Declare it before your first release"
    `haywire share` checks the declaration at preflight: `distribute = "pypi"` against a distribution name PyPI does not know fails **before** a tag is pushed, rather than surfacing when a consumer tries to install. Use PyPI's *pending publisher* form (§3) so the name exists before your first run. The check is skipped when PyPI cannot be reached, so it never blocks an offline publish.

## 6. Cutting a release

With setup done, releasing is the normal share flow:

```sh
haywire share --bump patch
```

That bumps the version, regenerates docs, rebuilds `marketstall.toml`, commits, tags `v0.0.2`, and pushes. The tag push triggers the workflow: tests → wheel → PyPI → feed. Watch it in the Actions tab; the whole run is typically a couple of minutes.

Verify by checking `https://pypi.org/project/haybale-my-lib/` shows the new version, then installing it clean:

```sh
uv pip install haybale-my-lib==0.0.2
```

## 7. Traps

**A version number is permanent.** PyPI refuses re-uploads of a version even after you delete it. A botched `0.0.2` means `0.0.3`, never a corrected `0.0.2`. This is why the test gate belongs before the upload step, and why TestPyPI exists.

**Yanking is not deleting.** If a release is broken, [yank](https://pypi.org/help/#yanked) it — resolvers skip yanked versions unless a consumer pinned that exact version. Deleting it instead breaks anyone who already pinned it.

**Your wheel may not contain what you think.** `uv build` includes what your build backend is told to include. Verify before your first upload:

```sh
uv build && python -m zipfile -l dist/*.whl
```

A library whose `__init__.py` carries the `@library(...)` decorator but whose wheel omits a subpackage will install and then fail to register at runtime.

**`[tool.haywire.marketstall]` is read from the project root.** Not from the library's own `pyproject.toml` when those differ. In a single-package repo they're the same file; in a monorepo with `barn/*`, the key belongs in the root.

**Don't publish both coordinates for one library.** `distribute` is project-scoped and applies to every library in the repo, which is deliberate: the unit of publishing is the project. A repo that somehow advertised git rows in one feed and PyPI rows in another would make its own library look like two libraries in conflict to anyone subscribed to both.

**The feed tracks the package automatically.** `version` and `install_spec` are both written from your `haybale.toml` at publish time, by the same run that pushes the tag CI builds from — so the feed cannot advertise a release you did not publish.

## 8. Related

- [sharing-libraries](./sharing-libraries.md) — the git-clone path and the full authoring flow
- [subscribing-to-marketplaces](./subscribing-to-marketplaces.md) — the consumer's side of the feed you just published
- [marketstall.toml](../reference/files/marketstall-toml.md) — the row schema and `distribute`
- [haybale-canon](../haybale/haybale-canon.md) — required package layout
- [haybale-marketplace-arch §8](../haybale/marketplace/haybale-marketplace-arch.md#8-why-the-model-is-shaped-this-way) — why the flow is shaped this way
