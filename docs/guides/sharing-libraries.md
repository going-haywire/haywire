---
status: draft
doc_template: guide
scope: Authoring a haybale library and publishing it for others — from new import to a hosted marketstall consumers can subscribe to
see-also:
  - ../haybale/haybale-package-canon.md
  - ../architecture/sharing/sharing-arch.md
  - ../haybale/haybale-marketplace-arch.md
  - ./subscribing-to-marketplaces.md
  - ../reference/publish_releases.md
  - ../reference/glossary.md
---

# Sharing libraries — Author guide

This guide walks an author through the full publish flow: scaffolding the library, keeping its dependency manifests honest as it evolves, producing the publish artifact, and hosting it so others can subscribe. For the conceptual model — *why* the flow is shaped this way — see [sharing-arch](../architecture/sharing/sharing-arch.md). For the consumer side, see [subscribing-to-marketplaces](./subscribing-to-marketplaces.md).

## 1. What it solves

A **haybale library** is a Python package containing one `BaseLibrary` subclass plus the components it contributes (nodes, types, widgets, skins, adapters, themes, panels, editors, states, settings). Sharing one means making it findable and installable by other people without going through a central registry. The mechanism is a small TOML file you host yourself, called a **marketstall**, that lists what you publish and how to install it.

Three things have to be true for a shared library to land cleanly in someone else's project:

1. The library's manifests (`@library(dependencies=...)` decorator and the library's own `pyproject.toml`) accurately describe what the source actually imports.
2. The marketstall file contains a valid entry pointing at the library's git location.
3. The marketstall is hosted somewhere a consumer can reach by URL.

The tooling in this guide makes all three easy.

## 2. The shape of a haybale library

A haybale library is a Python package with a specific layout. `haywire init` produces this for you; if you're starting from scratch, see [haybale/haybale-package](../haybale/haybale-package-canon.md) for the full canon. The relevant parts for sharing:

```
haybale-my-lib/
├── pyproject.toml          ← library-level manifest (travels to PyPI / pip)
└── haybale_my_lib/
    └── __init__.py         ← @library(...) decorator declares the haywire runtime contract
```

The two manifests answer different questions:

| Manifest | Audience | Answers |
|---|---|---|
| `pyproject.toml` `[project] dependencies` | pip / PyPI / `uv pip install` | "What Python distributions does this library need installed?" |
| `@library(dependencies=[...])` in `__init__.py` | haywire's runtime (LibraryManager) | "Which *other haywire libraries* must be enabled for this one to enable?" |

The library's source imports are a third, implicit layer. The three have to agree at publish time — if your source `from haybale_core import types` but neither manifest declares `haybale-core`, the published library will fail to install or to enable for consumers.

## 3. Keeping the manifests honest

As you add imports to your library's source, you'll add lines like `from haywire.ui.elements import elements as hui` or `from haybale_haystack.states import HaystackState`. Each new import is a new dependency — and the two manifests need to follow.

You don't have to track this by hand. Open your library in the Library Overview Editor, click **Edit**, and click the magnifying-glass **Detect Dependencies** button next to the dependencies field.

What happens:

1. The runtime statically scans every `.py` file in your library's source tree.
2. It resolves every top-level import to its installed Python distribution.
3. It classifies each one: framework (`haywire-core`, `haywire-studio`), registered haywire library (anything declaring a `haywire.libraries` entry point), or third-party (`numpy`, `requests`, etc.).
4. It diffs the result against what your two manifests currently declare.
5. A diff modal previews the changes, with two ways to apply them:

| Apply mode | Effect |
|---|---|
| **Union** | Add what's missing. Never remove. Safe against dynamic imports the static scan missed. |
| **Replace** | Overwrite both manifests with the detected set. Removes anything not detected. Useful for cleanup; risky if you have dynamic imports. |

After Apply:

- The Edit dialog's dependencies field updates immediately. You still have to click **Save Changes** to persist the `@library` decorator update.
- The library's `pyproject.toml` is written to disk right away (it isn't part of the identity-save bundle).

A typical workflow is: write code → realize you've added an import → click Detect → Union → Save Changes. Done in five seconds.

## 4. The publish flow

Once the manifests are honest, publishing is `haywire share`. Unlike the old
per-library snippet tool, it publishes the whole **project**: every `barn/*`
library is bumped to the same version (lockstep), docs are regenerated,
`marketstall.toml` is rebuilt, and the result is committed, tagged
`v<version>`, and pushed. See [ADR-0023](../adr/0023-project-scoped-lockstep-sharing.md)
for why the unit of sharing is the project, not one library.

The same pipeline is available two ways: the CLI (this section) and the
**Share Project…** item on `LibraryBrowserEditor`'s burger menu, which walks
the same steps as a popup wizard.

### 4.1 Interactive mode (default)

```sh
uv run haywire share
```

Prompts through the same six steps as the GUI wizard — check the project,
resolve dependency drift, choose a version, regenerate docs, review the
commit, then push.

### 4.2 Check mode — read-only PR gate

```sh
uv run haywire share --check
```

Reports dependency drift and stale docs/marketstall and exits non-zero if
anything is out of date. Writes nothing, commits nothing, pushes nothing.
Use this in CI to fail a PR before a human runs the real thing.

### 4.3 Non-interactive mode

```sh
uv run haywire share --yes --bump patch
```

Every answer comes from a flag instead of a prompt. Requires `--bump`
(`patch|minor|major` or an explicit `X.Y.Z`); refuses to run if there is
unresolved dependency drift — resolve it first (§3) or the run fails with the
same information `--check` would have reported.

### 4.4 Pinning the share URL (`--ref` / `--tag`)

```sh
uv run haywire share --yes --bump patch --tag latest
```

By default the published `install_spec` is branch-live: `marketstall.toml` is
a subscription feed, so a branch-pinned URL keeps subscribers discovering
every future release. `--ref <branch|tag|SHA>` or `--tag <tag>` (`--tag latest`
resolves to the most recent tag reachable from HEAD) freezes the URL to a
specific point instead — use this for a one-off frozen snippet, not for the
feed you expect people to keep subscribing to.

### 4.5 What an entry looks like

Each `barn/*` library becomes one `[[haybales]]` entry in the generated
`marketstall.toml`:

```toml
[[haybales]]
name         = "haybale-my-lib"
label        = "My Lib"
min_version  = "0.1.0"
description  = "One-line summary of what the library does."
author       = "Your Name"
source       = "git"
install_spec = "haybale-my-lib @ git+https://github.com/you/repo.git#subdirectory=barn/haybale-my-lib"
tags         = ["vision", "experimental"]
os           = ["macos", "linux"]
dependencies = ["haybale-core"]
source_url   = "https://github.com/you/repo"
docs_url     = "https://raw.githubusercontent.com/you/repo/main/barn/haybale-my-lib/haybale_my_lib/"
```

A few points worth knowing:

- `source = "git"` and the `install_spec` with `#subdirectory=` are how `haywire share` packages a monorepo library. The consumer installs it directly from your git repo; you don't have to publish to PyPI.
- `dependencies` lists pip distribution names of the haybale libraries you depend on — *not* the underscore form used inside the `@library` decorator.
- `docs_url` points at the library's Python module directory. Generated `OVERVIEW.md` and `QUICKREF.md` live there and the Library Manager will fetch them for pre-install discovery.
- `min_version` is a *floor*, not "latest". Consumers may install a higher version.

`haywire share` derives all this from each library's `pyproject.toml`, its `__init__.py`, and your git remote. SSH URLs are converted to HTTPS automatically.

## 5. Versioning

> `haywire share` (§4) is the tool for a project you scaffolded with `haywire init` — a uv workspace root with a `barn/` of libraries that publish in lockstep. The haywire **monorepo itself** uses a related but separate lockstep flow described below.

Versions are managed at the monorepo level by `scripts/bump_version.py`, invoked through `/haywire-release`. See [publish_releases](../reference/publish_releases.md) for the operational flow. The short version:

- The repo declares which packages release in lockstep (`[tool.haywire.release]` in the repo root `pyproject.toml`).
- A release bumps every member's `[project] version` to the same value.
- Inter-package dependencies use `~=` compatible-release operators (`haywire-core~=0.0.1`) so any patch within the lockstep tier is acceptable.
- CI publishes to PyPI; the marketstall in `gh-pages` is regenerated from `scripts/generate_marketstall.py` as part of the same workflow.

Authors outside the official monorepo can use any versioning scheme they like — the marketstall format doesn't require lockstep. The `~=` convention is a haywire-team practice.

## 6. Hosting your marketstall

A marketstall is just a TOML file. Wherever consumers can reach by URL, you can host one. Common patterns:

| Hosting | URL shape | Notes |
|---|---|---|
| GitHub Pages | `https://<you>.github.io/<repo>/marketstall.toml` | Free, persistent, served as raw bytes. Standard for monorepo libraries. |
| GitHub raw | `https://raw.githubusercontent.com/<you>/<repo>/main/marketstall.toml` | Works without Pages setup. Counts against GitHub's rate limit; less appropriate for high-traffic. |
| GitLab Pages | `https://<you>.gitlab.io/<repo>/marketstall.toml` | Same shape as GitHub Pages. |
| Your own static host | Any URL serving TOML | No haywire-specific requirements; just must be reachable. |

The haywire team publishes the official marketstall at `https://going-haywire.github.io/haywire/marketplace.toml` (a marketplace aggregating multiple marketstalls — see [sharing-arch](../architecture/sharing/sharing-arch.md) for the marketplace vs marketstall distinction). Your file is structurally the same.

Once hosted, share the URL. Per spec §4.2 a consumer can paste any of four forms into the Library Manager's Add Source dialog — the GitHub *blob* URL of your `marketstall.toml` (e.g. `https://github.com/you/repo/blob/main/marketstall.toml`) is the recommended canonical form. The runtime recognizes the host, derives the raw URL, fetches the body, sees one `[[haybales]]` section, and writes a `[[stalls]]` subscription to the user's global marketplace. The next refresh picks up your library. See [subscribing-to-marketplaces](./subscribing-to-marketplaces.md) for the consumer side.

## 7. The full author cycle

End-to-end, the flow is:

```
write code → add import → click Detect Dependencies → Union → Save Changes
                                                                    │
                                                                    ▼
                                                          [manifest layers in sync]
                                                                    │
                                                                    ▼
                                                    git commit && git push
                                                                    │
                                                                    ▼
                                            uv run haywire share --yes --bump patch
                                          (or: Share Project… in the burger menu)
                                                                    │
                                                                    ▼
                                        [barn/* bumped in lockstep, docs regenerated,
                                          marketstall.toml rebuilt, committed, tagged,
                                                              and pushed]
                                                                    │
                                                                    ▼
                                                      [marketstall hosted at URL]
                                                                    │
                                                                    ▼
                                              consumer subscribes via Add Source
```

`haywire share --check` is the CI-side companion — run it as a PR gate to catch drift or stale docs/marketstall before merging, without writing anything.

## 8. Common pitfalls

**You ran `haywire share` and got "unresolved dependency drift."**
`--yes` refuses to run with drift unresolved. Either drop `--yes` and resolve it interactively, or open the Library Overview Editor for the flagged library and Detect → Union, then re-run `--yes --bump ...`. The error message lists which manifest entries are missing.

**Your marketstall has an entry but consumers don't see the library after subscribing.**
Three causes worth checking:

1. Their `Refresh` hasn't run. Subscriptions are passive; the catalog updates only on refresh.
2. The library's name collides with one they already have from another feed. They'll see a conflict prompt at Add Source time; if they picked the other source, your entry is in their `ignores`. They can edit `~/.haywire/marketplace.toml` to remove the ignore.
3. The git URL in your `install_spec` is unreachable. Test with `uv pip install '<install_spec>'` directly.

**Detect Dependencies didn't pick up an import.**
The scan is static AST analysis. Dynamic imports (`importlib.import_module(name)`, `__import__(...)`) are invisible. Declare those manually in both manifests.

**`haywire share` produces a URL with `<REPO_URL>` placeholder.**
The library has no git remote (`git remote -v` returns nothing). Add a remote: `git remote add origin <url>`.

**You're working in `--dev` mode and want to share a library that has dev-repo dependencies.**
`haywire share`'s output uses `source = "git"` for haywire's `dependencies` field, which is correct — consumers don't have your dev workspace. But the dev-repo path-style `pyproject.toml` won't survive `pip install`. Make sure the published version of your library declares versioned dependencies (`haybale-core~=0.0.1`), not editable path sources. `haywire share` handles this correctly when the dependencies are listed in the library's `pyproject.toml` rather than in the project root's `pyproject.toml`.

## 9. Reading on

- The **consumer side** of this flow: [subscribing-to-marketplaces](./subscribing-to-marketplaces.md).
- The **conceptual model** behind these mechanics: [sharing-arch](../architecture/sharing/sharing-arch.md).
- The **library manager architecture** these tools plug into: [haybale-marketplace-arch](../haybale/marketplace/haybale-marketplace-arch.md).
- The **operational release flow** for the monorepo (`/haywire-release`, CI, PyPI Trusted Publisher): [publish_releases](../reference/publish_releases.md).
- The **per-author canon** for the package itself (folder layout, pyproject shape, build/test/publish): [haybale/haybale-package](../haybale/haybale-package-canon.md).
