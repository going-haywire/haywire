---
status: draft
doc_template: guide
scope: Publishing a haybale library to PyPI — account setup, name claim, Trusted Publisher CI, and the pyproject keys that put the released feed in your README
see-also:
  - ./sharing-libraries.md
  - ./subscribing-to-marketplaces.md
  - ../haybale/haybale-canon.md
  - ../reference/publish_releases.md
---

# Publishing to PyPI — Author guide

[sharing-libraries](./sharing-libraries.md) gets your library to consumers as a **git clone** — they install from a tag or a branch of your repository. This guide covers the other distribution path: publishing the library as a **released package on PyPI**, so consumers `pip install haybale-my-lib` instead of cloning source.

The two paths are complementary, not alternatives. A published project ends up advertising both, and the marketstall marker block in your README lists the PyPI feed first because a released package is the primary way most people will consume your library.

## 1. What it solves

Installing from git works, but it makes the consumer's machine do your build. `uv pip install "haybale-my-lib @ git+https://..."` literally runs `git clone` (shallow, when the ref resolves server-side) and then builds a wheel from the checkout — even with `#subdirectory=`, which filters *after* cloning the whole repo. That means the consumer needs `git`, network access to your host, credentials if the repo is private, and a working run of your build backend. It also means anything your build touches must be committed: gitignored files are simply absent for them, and LFS assets arrive as pointer text.

A PyPI release inverts all of that. The wheel is built once, by you, in CI — a fixed, self-contained artifact that resolves by version and never changes once uploaded.

Publishing to PyPI adds three things to the flow in [sharing-libraries](./sharing-libraries.md):

1. A **PyPI account** and a **claimed distribution name**.
2. A **CI workflow** that builds a wheel on every version tag and uploads it.
3. A **deployed feed** (`marketplace.toml`) listing your released packages, hosted somewhere consumers can reach — GitHub Pages in the example below.

Steps 1 and 2 are one-time setup. After that, `haywire share --bump patch` pushes a tag and CI does the rest.

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

Copy this to `.github/workflows/publish.yml`. It builds and publishes a **single-package** repository on every `v*.*.*` tag, then deploys a marketplace feed to GitHub Pages.

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
  # Human-readable name shown in the Library Browser.
  LIBRARY_LABEL: My Library
  # One line. Shown under the label in the browser.
  LIBRARY_DESCRIPTION: What your library does
  LIBRARY_AUTHOR: Your Name
  # Your repository, used for the "source" link on the catalog entry.
  SOURCE_URL: https://github.com/you/haybale-my-lib

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

  deploy-feed:
    name: Deploy marketplace feed to GitHub Pages
    runs-on: ubuntu-latest
    needs: publish
    permissions:
      contents: write                  # to push the gh-pages branch
    steps:
      - uses: actions/checkout@v4

      # Reads the env: block at the top of this file — nothing to edit here.
      # The version comes from the tag that triggered the run (v1.2.0 → 1.2.0),
      # so the feed can never advertise a version you didn't publish.
      - name: Write marketplace.toml
        run: |
          mkdir -p feed
          VERSION="${GITHUB_REF_NAME#v}"
          cat > feed/marketplace.toml <<EOF
          # Released packages for ${DIST_NAME}.
          # Subscribe to this URL in the haywire Library Browser.
          # Generated by .github/workflows/publish.yml — do not edit by hand.

          [[haybales]]
          name = "${DIST_NAME}"
          label = "${LIBRARY_LABEL}"
          version = "${VERSION}"
          description = "${LIBRARY_DESCRIPTION}"
          author = "${LIBRARY_AUTHOR}"
          source = "pypi"
          install_spec = "${DIST_NAME}"
          tags = []
          dependencies = []
          source_url = "${SOURCE_URL}"
          EOF

      - name: Deploy to GitHub Pages
        uses: peaceiris/actions-gh-pages@v4
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./feed
          publish_branch: gh-pages
          keep_files: true
```

Enable Pages once, under repo *Settings* → *Pages* → source `gh-pages`. The feed then lives at `https://<you>.github.io/<repo>/marketplace.toml`.

!!! warning "`source = \"pypi\"` changes what `install_spec` means"
    With `source = "git"`, `install_spec` is a full `name @ git+URL` clone spec. With `source = "pypi"` it is just the bare distribution name — pip resolves it from the index. Mixing the two up produces a feed that looks valid and fails at install.

### Other CI providers

The only provider-specific parts are the OIDC identity and the Pages deploy. GitLab CI, Circle, and others can publish to PyPI the same way — consult [the PyPI Trusted Publishers docs](https://docs.pypi.org/trusted-publishers/) for the provider list, and fall back to an API token (`UV_PUBLISH_TOKEN` / `TWINE_PASSWORD`) where OIDC isn't supported. The build step is always `uv build`; the upload is always `uv publish` or `twine upload dist/*`.

## 5. Point your README at the feed

Add the feed URL to your **project root** `pyproject.toml`:

```toml
[tool.haywire.marketstall]
pypi_marketplace_url = "https://you.github.io/haybale-my-lib/marketplace.toml"
```

This is project-scoped config, authored once — not a per-run flag. On the next `haywire share`, the README marker block gains the PyPI feed on top of the two git URLs:

````markdown
<!-- marketstall:share-url:start -->
```sh
# Released packages (recommended):
https://you.github.io/haybale-my-lib/marketplace.toml

# Always the latest (tracks the current branch):
https://github.com/you/haybale-my-lib/blob/main/marketstall.toml

# Frozen to this version:
https://github.com/you/haybale-my-lib/blob/v0.0.1/marketstall.toml
```
<!-- marketstall:share-url:end -->
````

Three links, three install stories: install a released package, track the branch, or freeze to a tag. Omit the key and you get the two git links exactly as before — the line is only added when you declare a feed.

The block is rewritten **wholesale** on every publish, which is why the URL lives in config rather than on the command line: a flag you forgot once would silently delete the link.

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

**The feed version must be bumped with the package.** In the workflow above it's derived from the tag (`${GITHUB_REF_NAME#v}`), so it tracks automatically. If you hand-write the feed instead, a stale `version` field advertises a release consumers can't resolve.

**Don't quote the feed heredoc.** The workflow writes `<<EOF`, not `<<'EOF'`, because the body depends on shell expansion of the `env:` values. Quoting the delimiter turns the whole block literal and deploys a feed containing `name = "${DIST_NAME}"` — which parses as valid TOML and fails only when a consumer tries to install it.

## 8. Related

- [sharing-libraries](./sharing-libraries.md) — the git-clone path and the full authoring flow
- [subscribing-to-marketplaces](./subscribing-to-marketplaces.md) — the consumer's side of the feed you just deployed
- [haybale-canon](../haybale/haybale-canon.md) — required package layout
- [haybale-marketplace-arch §8](../haybale/marketplace/haybale-marketplace-arch.md#8-why-the-model-is-shaped-this-way) — why the flow is shaped this way
