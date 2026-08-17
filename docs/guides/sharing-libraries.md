---
status: draft
doc_template: guide
scope: Authoring a haybale library and publishing it for others — from new import to a hosted marketstall consumers can subscribe to
see-also:
  - ../haybale/haybale-canon.md
  - ../reference/files/marketstall-toml.md
  - ../haybale/marketplace/haybale-marketplace-arch.md
  - ./subscribing-to-marketplaces.md
  - ../reference/publish_releases.md
  - ../reference/glossary.md
---

# Sharing libraries — Author guide

Publishing a library is one command, or one wizard. This guide starts there.
Later sections cover the things that can stop a publish (§4), and what the
pipeline is doing on your behalf (§6 onward) — worth reading once, not before
your first share.

For the consumer side, see [subscribing-to-marketplaces](./subscribing-to-marketplaces.md).

## 1. The short version

Sharing a library is easy. If you followed the standard way of setting up a
haywire project, your project already contains its own library: every node,
widget, type and other component you built for your graphs is already in it.
All that is left is to share it.

Before you start though you have to make a decision about your library name. You might have noticed that the folder inside `barn/` is called `haybale-your-lib` and the package inside it is called `haybale_your_lib`. This naming scheme was not chosen arbitrarily — it is the canonical form for haybale libraries because haybale-* is a namespae in [[pypi](https://pypi.org)] (where all the python packages live) that is not used by any other project so far - the only haybale-* libraries there are, are the ones that are part of the haywire project (at least at the time of this writing). If you want to share your library with others, it is recommended to follow this naming scheme and use a name that is not already taken in pypi.org. You can check if a name is available by searching for it on pypi.org. But this only applies if you choose to share your library on pypi.org. If you choose to share it only via git (which this guide will cover) and amongst you friends, you can use any name you like, but it is still recommended to follow the haybale-* naming scheme to avoid confusion.

If you do plan to share your library along a wider audience and want to avoid the painfull (for you and your library users) experience of having to rename your library later, it is recommended to choose a name you want that is available on pypi.org before you start with this process. Because if you don't, and your library name is already taken, your library and the other libary (that has a pypi package) will never be able to coexist in the same graph. Ever. Which would be a shame. But if you do, then once you have successfully shared your library with the approach described in this guide, you can follow the steps described in [publish-to-pypi](publish-to-pypi.md) to publish your library on pypi.org as well.

The process:

* Document your components: write descriptions, tags, class docstrings.

* In the Marketplace browser → select your local library → in the Overview
  editor press **Edit** and update the metadata.

* The **haybale-share** library (installable via the Marketplace) gives you a
  wizard that steps you through the share process interactively. All you need
  is a cloud account for a git repository.

* Once the wizard completes, your library is online for others to subscribe to.

You need a clean working tree, an `origin` remote on a recognised host, and to
be on the default branch. The wizard checks all of it up front and offers a fix
button where the repair is unambiguous — §4 has the details if a check stops
you.

## 2. Publishing

Publishing is `haywire share`. It publishes the whole **project**, not one
library: every `barn/*` library is bumped to the same version (lockstep), docs
are regenerated, `marketstall.toml` is rebuilt, and the result is committed,
tagged `v<version>`, and pushed. See [ADR-0023](../adr/0023-project-scoped-lockstep-sharing.md) for why the unit of sharing is the project.

The same pipeline is available two ways — a wizard and a CLI.

### 2.1 The Share editor

Open **Share** from the studio's left toolbar. It shows the project's
publishing status — the barn libraries, their lockstep version — and a
**Share…** button that opens the flow.

Three screens:

1. **Preflight** runs the moment it opens and reports the earliest problem
   it finds, with the repair inline where one is safe (see [§4](#4-what-has-to-be-true-before-you-publish)).
2. **Review** carries every dependency decision and the version on one
   screen. Findings with nothing to report collapse to a single ✓ line, so a
   clean project is one screen and one click. Nothing is written until you
   confirm here.
3. **Publish** regenerates docs, rebuilds the marketstall, then commits, tags
   and pushes — one authorized action, with the subprocess output streamed.

### 2.2 The CLI

```sh
uv run haywire share --bump patch
uv run haywire share --dry-run      # report only; writes nothing
```

One mode, non-interactive. Every answer comes from a flag or takes its inert
default. Requires `--bump` (`patch|minor|major` or an explicit `X.Y.Z`).

It does not refuse over dependency drift. An **undeclared import** is declared
for you — that one breaks a consumer's install and declaring it is
unambiguously correct — while **unused declarations** and **version floor lag**
are left untouched, because removing is lossy and nothing here can compute the
oldest version that still works. Use the Share editor when you want to decide
those.

`--dry-run` reports preconditions, findings and the version it would cut, and
writes nothing. Preconditions are *reported* rather than enforced there, so it
stays useful on a feature branch or a PR checkout.

## 3. What gets published

Each `barn/*` library becomes one `[[haybales]]` entry in the generated
`marketstall.toml` — mostly a verbatim copy of your `haybale.toml`, plus the
coordinates a library cannot state about itself (`install_spec`, `source`,
`require`). You never author this file; publishing writes it.

Two things worth knowing as an author:

- `install_spec` pins to the release tag `v<version>` created by this run — not
  the branch you published from — so it stays correct even after your branch is
  deleted.
- `require` (`haywire-core>=0.0.31`) comes from your library's own
  `pyproject.toml`. Keep it as low as your library actually allows: a floor
  restricts *consumers*, and raising it forces every one of them to update
  before they can install you.

Field by field: [marketstall.toml](../reference/files/marketstall-toml.md).

## 4. What has to be true before you publish

Any precondition failure stops `haywire share` and reports the single earliest
problem it found — checks run in the order below, and an earlier failure makes
a later one moot, so fixing one and re-running can surface the next. In the
Share editor this renders on the **Preflight screen**: message and remedy text,
plus — for failures with a safe, unambiguous repair — a button that performs
the fix right there, with your permission. Every one ends with **Check again**,
which re-runs every check from the top.

### 4.1 Git requirements

`haywire share` needs four things from your git setup before it will publish anything, checked in this order:

1. **The working tree is clean.** `git status --porcelain` must be empty —
   no staged, unstaged, or untracked changes anywhere in the repo, not just
   under `barn/`. This is deliberately strict: if a later step fails
   partway through, the publish pipeline reverts everything it has written
   by resetting the whole working tree, and that revert is only safe
   because nothing else could have been sitting there dirty when the run
   started. Commit or stash first. This applies to `haywire share` on the
   command line exactly as it does in the Share editor — both run the same
   checks. (A step-1 failure itself never mutates anything and never
   triggers a revert — there's nothing yet to revert.)

2. **An `origin` remote is configured.** `git remote add origin <url>` if it isn't. The Share editor's Preflight screen offers this as an **Add origin remote** fix (§8).

3. **The remote's host is recognized.** GitHub and GitLab (`github.com`, `gitlab.com`) work out of the box. A self-hosted GitLab or GitHub Enterprise instance — anything on a different hostname — needs one entry in `~/.haywire/config.toml`:
   
   ```toml
   [[hosts]]
   hostname = "gitlab.example.com"
   provider = "gitlab"   # or "github"
   ```
   
   This only teaches haywire how to build browser-friendly URLs (blob links, raw-content links) for that host — it has nothing to do with push access, which is check 4. A remote pointing at a local filesystem path (a sibling clone, a shared network drive) skips this check entirely — it isn't an unrecognized host, since there's no hostname to recognize or fail to recognize.

4. **The push will be accepted.** `haywire share`'s commit step runs a `git push --dry-run` before it commits or tags anything, so a credential problem surfaces before anything is written. Because both the Share editor and the CLI push non-interactively, git cannot fall back to an interactive username/password prompt — there is no terminal for it to prompt on. This means:
   
   - An **HTTPS** remote (`https://gitlab.example.com/...`) needs a credential cached ahead of time — a personal access token stored via a credential helper (`git config --global credential.helper osxkeychain` on macOS, then push once by hand to seed it) is the common approach.
   - An **SSH** remote (`git@gitlab.example.com:...`) needs a key registered with the host and `ssh-agent` running, so no passphrase prompt blocks the push either.
   
   Setting up either is entirely between you and your git host — see your host's own documentation: [GitHub's guide to authenticating with the CLI/HTTPS](https://docs.github.com/en/authentication) or [GitLab's guide to credentials](https://docs.gitlab.com/auth/) cover both paths and the most common failures. This guide only covers what haywire itself checks, not general git credential troubleshooting.

### 4.2 Publish from the default branch

`haywire share` refuses to publish from anything but the repository's default
branch. There is no escape hatch — the rule is unconditional. It guarantees
every published entry reflects a state that will still exist and keep
receiving fixes after the run. For the full rationale, and why tag-pinning
did not relax the rule, see
[share-pipeline-arch §5](../architecture/sharing/share-pipeline-arch.md#5-the-default-branch-publishing-rule).

If `haywire share` reports that you're on the wrong branch, e.g.:

```text
Currently on `feature-x`, but the repository's default branch is `main`.
```

switch to the default branch and publish from there: `git switch main`.

This check, along with a companion check that HEAD isn't detached, always
runs — there's no flag to skip it.

## 5. Hosting your marketstall

A marketstall is just a TOML file. Wherever consumers can reach by URL, you can host one. Common patterns:

| Hosting              | URL shape                                                              | Notes                                                                                             |
| -------------------- | ---------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| GitHub Pages         | `https://<you>.github.io/<repo>/marketstall.toml`                      | Free, persistent, served as raw bytes. Standard for monorepo libraries.                           |
| GitHub raw           | `https://raw.githubusercontent.com/<you>/<repo>/main/marketstall.toml` | Works without Pages setup. Counts against GitHub's rate limit; less appropriate for high-traffic. |
| GitLab Pages         | `https://<you>.gitlab.io/<repo>/marketstall.toml`                      | Same shape as GitHub Pages.                                                                       |
| Your own static host | Any URL serving TOML                                                   | No haywire-specific requirements; just must be reachable.                                         |

The haywire team publishes the official marketstall at `https://going-haywire.github.io/haywire/marketplace.toml` (a marketplace aggregating multiple marketstalls — see [marketplace.toml](../reference/files/marketplace-toml.md) for the distinction). Your file is structurally the same.

Once hosted, share the URL. Per spec §4.2 a consumer can paste any of four forms into the Library Manager's Add Source dialog — the GitHub *blob* URL of your `marketstall.toml` (e.g. `https://github.com/you/repo/blob/main/marketstall.toml`) is the recommended canonical form. The runtime recognizes the host, derives the raw URL, fetches the body, sees one `[[haybales]]` section, and writes a `[[stalls]]` subscription to the user's global marketplace. The next refresh picks up your library. See [subscribing-to-marketplaces](./subscribing-to-marketplaces.md) for the consumer side.

## 6. Under the hood

Nothing below is something you have to do. The share pipeline handles all of
it; this is what it is handling, for when you want to know — or when something
went wrong and the message mentions a manifest.

### 6.1 What sharing actually requires

A **haybale library** is a Python package containing one `BaseLibrary` subclass plus the components it contributes (nodes, types, widgets, skins, adapters, themes, panels, editors, states, settings). Sharing one means making it findable and installable by other people without going through a central registry. The mechanism is a small TOML file you host yourself, called a **marketstall**, that lists what you publish and how to install it.

Three things have to be true for a shared library to land cleanly in someone else's project:

1. The library's manifests (`linked_libraries` in `haybale.toml` and `dependencies` in the library's own `pyproject.toml`) accurately describe what the source actually imports.
2. The marketstall file contains a valid entry pointing at the library's git location.
3. The marketstall is hosted somewhere a consumer can reach by URL.

The tooling in this guide makes all three easy.

### 6.2 The shape of a haybale library

A haybale library is a Python package with a specific layout. `haywire init` produces this for you; if you're starting from scratch, see [haybale-canon](../haybale/haybale-canon.md) for the full canon. The relevant parts for sharing:

```
haybale-my-lib/
├── pyproject.toml          ← pip manifest (travels to PyPI / pip)
└── haybale_my_lib/
    ├── haybale.toml        ← library metadata (ships INSIDE the wheel)
    └── __init__.py         ← @library(...) declares the haywire runtime contract
```

The two manifests answer different questions:

| Manifest                                  | Audience                           | Answers                                                                   |
| ----------------------------------------- | ---------------------------------- | ------------------------------------------------------------------------- |
| `pyproject.toml` `[project] dependencies` | pip / PyPI / `uv pip install`      | "What Python distributions does this library need installed?"             |
| `haybale.toml` `linked_libraries`         | haywire's runtime (LibraryManager) | "Which *other haywire libraries* must be enabled for this one to enable?" |

Note the spelling difference: `dependencies` takes pip **distribution** names (`haybale-core`), `linked_libraries` takes Python **module** names (`haybale_core`).

`haybale.toml` also carries everything descriptive a subscriber sees before installing — `label`, `description`, `tags`, `os`, and the URL fields — which is why it lives *inside* the package and ships in the wheel. Publishing copies it almost verbatim into your marketstall, and generates `pyproject.toml`'s descriptive `[project]` fields from it, so you never write those twice. Full field list: [reference/files/haybale.toml](../reference/files/haybale-toml.md).

The library's source imports are a third, implicit layer. The three have to agree at publish time — if your source `from haybale_core import types` but neither manifest declares it, the published library will fail to install or to enable for consumers.

### 6.3 Keeping the manifests honest

As you add imports to your library's source, you'll add lines like `from haywire.ui.elements import elements as hui` or `from haybale_haystack.states import HaystackState`. Each new import is a new dependency — and the two manifests need to follow.

You don't have to track this by hand. `haywire share`'s **Detect** step does it for you, and `uv run haywire deps check` runs the same detection non-interactively (useful in CI).

What happens:

1. The runtime statically scans every `.py` file in your library's source tree.
2. It resolves every top-level import to its installed Python distribution.
3. It classifies each one: framework (`haywire-core`, `haywire-studio`), registered haywire library (anything declaring a `haywire.libraries` entry point), or third-party (`numpy`, `requests`, etc.).
4. It diffs the result against what your two manifests currently declare.
5. The Share flow's screens ask you about each finding, one kind at a time.

How each finding is handled:

| Finding | What happens |
| --- | --- |
| An import your library pyproject doesn't declare | You choose the pin per item: no pin, floor at installed, custom, or skip. This is the only finding that blocks a publish — it breaks a consumer's install. |
| An imported haywire library missing from `linked_libraries` | Added for you, and reported. There is nothing to decide: it carries no version and narrows nothing. |
| A declaration the source no longer imports | Reported, never removed on its own. A dynamic import looks exactly like an unused declaration, so dropping it is your call. |
| A declared floor below the installed version | Left alone by default. "Newer is installed" only means time passed, not that your floor is wrong. |

Nothing is ever removed without you asking for it, so a hand-added entry for a
dynamic import survives every publish.

Because the share pipeline runs this detection itself, a publish never ships a
manifest that lies about the source. Running `deps check` as you go just means
the publish has nothing left to report.

### 6.4 Versioning in the haywire monorepo

> `haywire share` ([§2](#2-publishing)) is the tool for a project you scaffolded with `haywire init` — a uv workspace root with a `barn/` of libraries that publish in lockstep. The haywire **monorepo itself** uses a related but separate lockstep flow described below.

Versions are managed at the monorepo level by `scripts/bump_version.py`, invoked through `/haywire-release`. See [publish_releases](../reference/publish_releases.md) for the operational flow. The short version:

- The repo declares which packages release in lockstep (`[tool.haywire.release]` in the repo root `pyproject.toml`).
- A release bumps every member's `[project] version` to the same value.
- Inter-package dependencies use `>=` floor operators (`haywire-core>=0.0.1`) so any later release is acceptable. A `~=X.Y.Z` compatible-release constraint would also stamp a *ceiling* — `~=0.0.37` excludes 0.1.0 — and a bound written by tooling is not an author's policy.
- CI publishes to PyPI; the marketstall in `gh-pages` is regenerated from `scripts/generate_marketstall.py` as part of the same workflow.

Authors outside the official monorepo can use any versioning scheme they like — the marketstall format doesn't require lockstep. The `>=` convention is a haywire-team practice.

## 7. The full author cycle

End-to-end, the flow is:

```
write code, build components
        │
        ▼
document them — descriptions, tags, docstrings
        │
        ▼
git commit && git push          (the tree must be clean — §4.1)
        │
        ▼
uv run haywire share --bump patch
  or: Share… in the Share editor
        │
        ├─▶ preflight: tree, remote, host, push, branch      §4
        ├─▶ dependency drift detected and reconciled         §6.3
        ├─▶ barn/* bumped in lockstep, docs regenerated      §6.4
        └─▶ marketstall.toml rebuilt, committed, tagged, pushed
        │
        ▼
marketstall hosted at a URL      §5
        │
        ▼
consumer subscribes via Add Source
```

Everything in the indented block happens inside the one command. The only steps
that are yours are writing the code, documenting it, and committing.

Two separate commands cover the CI side — there's no single `--check` gate.
Run `haywire deps check` as a PR gate to catch manifest drift before merging,
and `haywire docs --all --json <path>` on merge to keep generated docs current,
committing whatever it produces. What each one exits with, and why neither is a
staleness gate, is in
[share-pipeline-arch §6](../architecture/sharing/share-pipeline-arch.md#6-the-current-ci-story).

## 8. Common pitfalls

**You want to review dependency findings before publishing.**
The CLI does not stop for them — it declares undeclared imports and leaves the
judgement calls alone. Run `haywire share --dry-run` to see every finding
without writing anything, or open the **Share** editor and use its Review
screen, which offers each finding with a per-item choice.

**Your marketstall has an entry but consumers don't see the library after subscribing.**
Three causes worth checking:

1. Their `Refresh` hasn't run. Subscriptions are passive; the catalog updates only on refresh.
2. The library's name collides with one they already have from another feed. They'll see a conflict prompt at Add Source time; if they picked the other source, that source holds the `preference`. Every later refresh lists the collision on its resolve step, so they can switch to your copy in one click.
3. The git URL in your `install_spec` is unreachable. Test with `uv pip install '<install_spec>'` directly.

**Detection didn't pick up an import.**
The scan is static AST analysis, so dynamic imports (`importlib.import_module(name)`, `__import__(...)`) are invisible to it. Declare those manually in both manifests. Nothing removes a declaration on its own — a declaration the scan can't see is reported as unused and left alone unless you choose to drop it — so a hand-added entry for a dynamic import survives.

**`haywire share` fails with "Working tree is not clean.".**
You have uncommitted changes somewhere in the repo — not just under `barn/`. The publish pipeline reverts everything it writes if a later step fails partway through, by resetting the whole working tree, and that's only safe when nothing else was dirty to begin with. Commit or stash your changes, then retry.

**`haywire share` produces a URL with `<REPO_URL>` placeholder.**
The library has no git remote (`git remote -v` returns nothing). Add a remote: `git remote add origin <url>`. In the Share editor, Preflight offers an **Add origin remote** fix — type the URL, click it, then **Check again**.

**`haywire share` fails with "Host '\<hostname\>' is not recognized.".**
Your `origin` remote points at a host haywire doesn't ship built-in support for — anything other than `github.com`/`gitlab.com`, typically a self-hosted GitLab or GitHub Enterprise instance. In the Share editor, the Preflight screen offers to write the needed `~/.haywire/config.toml` entry for you — click the fix, then Check again. From the CLI, add it by hand per [§4.1](#41-git-requirements) and retry. This is unrelated to push access — see the next entry if the push itself also fails.

**`haywire share` fails with "Push failed: ... terminal prompts disabled".**
git tried to prompt for a username/password and couldn't — both the Share editor and the CLI push non-interactively, so there's no terminal to prompt on. Preflight catches this before anything is written, and links your host's own authentication docs directly (SSH keys or tokens, whichever your remote uses). You need a credential cached *before* running share: either switch the remote to SSH (`git remote set-url origin git@<host>:<owner>/<repo>.git`) with a key registered on the host and `ssh-agent` running, or keep HTTPS and cache a personal access token via a git credential helper. See [§4.1](#41-git-requirements) for both paths and links to your host's own credential docs — this is a general git-auth problem, not something haywire's pipeline can resolve for you.

**`haywire share` fails with "Could not read `barn/<lib>/pyproject.toml`: ...".**
That library's `pyproject.toml` doesn't parse as TOML. Fix the TOML in `barn/<lib>/pyproject.toml` so it parses, then try again.

**`haywire share` fails with "Invalid manifest at `barn/<lib>/pyproject.toml`: ...".**
The library's `[tool.haywire]` `os` list declares something other than `macos`, `windows`, or `linux`. `other` is a runtime sentinel for platforms that don't map to one of those three — it's set automatically and must never be declared by hand. Remove it (or the whole invalid entry) from the `os` list. In the Share editor, Preflight offers a fix button (**Remove invalid values**, or **Correct to macos**/**Correct to windows** when every bad value maps unambiguously) that rewrites the field for you — click it, then **Check again**.

**`haywire share` fails with "HEAD is detached — no branch is currently checked out.".**
You're not on a branch. If the remedy names one or more branches (e.g. `` This commit is on `main`, `feature-x` — run `git switch main`. ``), switch to the first one it lists. If it instead says the commit isn't on any branch, create one and publish from there: `git switch -c my-branch`.

**`haywire share` fails with "Currently on `<branch>`, but the repository's default branch is `<default>`.".**
See [§4.2 Publish from the default branch](#42-publish-from-the-default-branch): switch to the default branch (`git switch <default>`).

**`haywire deps check` exits non-zero in CI.**
One or more `barn/*` libraries have actionable dependency-manifest drift. The
command prints which library and which manifest entries are missing. Resolve it
with `haywire share` (interactive) or the Library Overview Editor's Detect
Dependencies button ([§6.3](#63-keeping-the-manifests-honest)).

**You're working in `--dev` mode and want to share a library that has dev-repo dependencies.**
`haywire share`'s output uses `source = "git"` for haywire's `dependencies` field, which is correct — consumers don't have your dev workspace. But the dev-repo path-style `pyproject.toml` won't survive `pip install`. Make sure the published version of your library declares versioned dependencies (`haybale-core>=0.0.1`), not editable path sources. `haywire share` handles this correctly when the dependencies are listed in the library's `pyproject.toml` rather than in the project root's `pyproject.toml`.

## 9. Reading on

- The **consumer side** of this flow: [subscribing-to-marketplaces](./subscribing-to-marketplaces.md).
- Why the model is shaped this way: [haybale-marketplace-arch §8](../haybale/marketplace/haybale-marketplace-arch.md#8-why-the-model-is-shaped-this-way).
- The **library manager architecture** these tools plug into: [haybale-marketplace-arch](../haybale/marketplace/haybale-marketplace-arch.md).
- The **operational release flow** for the monorepo (`/haywire-release`, CI, PyPI Trusted Publisher): [publish_releases](../reference/publish_releases.md).
- The **per-author canon** for the package itself (folder layout, pyproject shape, build/test/publish): [haybale-canon](../haybale/haybale-canon.md).
