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
2. A **CI workflow** that builds a wheel on every version tag and uploads it. `haywire init` writes it for you (§4).
3. One line of config — `distribute = "pypi"` — which makes `haywire share` write PyPI coordinates into the `marketstall.toml` it already generates.

All three are one-time setup. After that, `haywire share --bump patch` pushes a tag and CI does the rest.

There is no separate feed to deploy. Your repo-root `marketstall.toml` **is** the feed, reachable at its raw URL; earlier versions of this guide had you publish a second, hand-written `marketplace.toml` to GitHub Pages, which existed only because that file was always git-flavoured.

## 2. Before you start — claim the name

PyPI distribution names are **globally unique and first-come**. Claim yours before you write any CI, because discovering the name is taken after you've wired everything up means renaming the package.

1. Create an account at [pypi.org/account/register](https://pypi.org/account/register/) and enable 2FA (required for uploads).
2. Check availability: visit `https://pypi.org/project/haybale-my-lib/`. A 404 means it's free.
3. The name is claimed by the first upload, which is §6 (*The first release*). A *pending publisher* (§3) reserves the trust relationship, **not** the name: PyPI's JSON API still answers 404 for the name until something is uploaded.

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

The environment name must match the `environment:` block in the workflow. If the project does not exist on PyPI yet, add the publisher at [pypi.org/manage/account/publishing](https://pypi.org/manage/account/publishing/) (the *pending publisher* form) instead. It lets CI create the project on the first upload without a token. It does **not** make the name exist: until that first upload succeeds, the project page and `https://pypi.org/pypi/<name>/json` both return 404, and `haywire share` preflight (§5) fails on it. Do the first upload as described in §6.

## 4. The workflow

`haywire init` writes `.github/workflows/publish.yml` and the small planner it calls, `.github/publish_plan.py`. You do not copy or edit anything. (A project created before this existed: copy both files from a fresh `haywire init`.) The workflow runs on every `v*.*.*` tag and has three jobs:

1. **Plan** runs the planner. Unless the root `pyproject.toml` declares `distribute = "pypi"` (§5) it prints "nothing to publish" and the run ends green. With `pypi`, it lists every `barn/*` library and checks that the tag equals each library's committed version; a mismatch fails the run before anything is built or uploaded.
2. **Build** runs once per library. If there is a `tests/` directory it runs your tests first (`uv sync --frozen`, then `pytest`), then builds the library with `uv build` inside its own `barn/<library>` directory. The tests need a root that resolves its own dependencies on a runner. A `--dev` project's root links to your haywire checkout by path (`[tool.uv.sources]`), which a runner does not have, so the planner detects that and the tests are skipped; the build does not depend on the root and still runs. Run the tests locally before you tag.
3. **Publish** runs once per library with `environment: pypi` and the OIDC identity (`id-token: write`). It skips a version PyPI already has, so re-running it is safe.

A project with several libraries has several PyPI projects. Each needs its **own** pending publisher (§3), with identical owner, repository, workflow name and environment. The workflow cannot tell them apart by anything but the project name, which is what makes a mistyped name fail without uploading (§6).

The workflow publishes from a tag only. If a run fails, fix the cause and re-run it on the same tag:

```sh
gh workflow run publish.yml --ref v0.0.2
```

A run on a branch is refused, so a version can never reach PyPI without a tag that names it.

### Other CI providers

The only provider-specific part is the OIDC identity. GitLab CI, Circle, and others can publish to PyPI the same way; see [the PyPI Trusted Publishers docs](https://docs.pypi.org/trusted-publishers/), and fall back to an API token (`UV_PUBLISH_TOKEN` / `TWINE_PASSWORD`) where OIDC isn't supported. The build step is always `uv build`; the upload is always `uv publish` or `twine upload dist/*`.

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

!!! warning "The name must exist on PyPI before `haywire share` runs"
    `haywire share` checks the declaration at preflight: `distribute = "pypi"` against a distribution name PyPI answers 404 for fails **before** a tag is pushed, rather than surfacing when a consumer tries to install. A *pending publisher* (§3) does not satisfy this check, because the name does not exist until the first upload. Do the first release with `haywire share --first-release` (§6) instead. The check is skipped when PyPI cannot be reached, so it never blocks an offline publish.

## 6. The first release

The first upload creates the PyPI project, so `haywire share` cannot do it the ordinary way: it refuses a name PyPI does not know yet (§5). `haywire share --first-release` is the explicit first-release mode.

1. The owner completes §2 to §5: a pending publisher on PyPI for **each** library name, the `pypi` environment created in the repository's *Settings → Environments*, and `distribute = "pypi"` declared and committed. Running `haywire share` before this stops with `STOP: human needed` and prints this checklist filled in from your remote and library names.
2. Run:

   ```sh
   uv run --frozen haywire share --first-release
   ```

   It publishes the version already declared (so `0.0.1` really is released; add `--bump patch` to move on first), commits, tags and pushes. The tag push starts the workflow, which creates each project through the pending publisher's OIDC identity.
3. Check that `https://pypi.org/project/haybale-my-lib/` answers 200. The pending publisher is now an ordinary one.
4. From now on use the normal flow below: `haywire share --bump patch`.

`--first-release` is refused when any library name already exists on PyPI (drop the flag if it is yours, rename if it is not), when PyPI cannot be reached to confirm that, when the project does not declare `distribute = "pypi"`, and when the remote is not on github.com. If the declared version is already tagged it tells you to add `--bump patch`. PyPI offers no way to ask whether a pending publisher exists, so the flag is your statement that it does; the safety net is below.

**A mistyped name fails safe.** PyPI looks the publisher up by the project name in the upload. If the name on the PyPI form and `[project].name` differ, the upload is rejected before any file is stored, and no version number is used up. Correct the PyPI form (or the library name), then re-run the failed job on the tag. If the library name itself was wrong, the tag cannot move: fix the name in a new commit and run `share --first-release --bump patch`.

## 7. Cutting a release

With setup done, releasing is the normal share flow:

```sh
haywire share --bump patch
```

That bumps the version, regenerates docs, rebuilds `marketstall.toml`, commits, tags `v0.0.2`, and pushes. The tag push triggers the workflow: tests → wheel → PyPI → feed. Watch it in the Actions tab; the whole run is typically a couple of minutes.

Verify by checking `https://pypi.org/project/haybale-my-lib/` shows the new version, then installing it clean:

```sh
uv pip install haybale-my-lib==0.0.2
```

## 8. Traps

**Sibling libraries symlinked into the workspace pollute `uv.lock`.** If you develop against another library by symlinking its checkout into a workspace folder (`barn/*` in the haywire monorepo), a plain `uv lock`, and any `uv run`, which re-locks first, adds it and its whole dependency tree to `uv.lock`. CI cannot resolve that path. This slipped into a release commit once and sat on `master` unnoticed. Three guards:

- List every such symlink in `[tool.uv.workspace].exclude` of the root `pyproject.toml` (the haywire monorepo excludes `barn/haybale-visiongraph`, `barn/haybale-spandrel` and `barn/haybale-stream`), and gitignore it.
- Before committing, look at `git diff --stat uv.lock`. A diff you did not intend (new packages, a sibling library) is a side effect: `git checkout uv.lock` discards it.
- In release and CI-like steps run `uv run --frozen ...` so uv uses the committed lock and does not rewrite it. After a version bump, run `uv lock` once, deliberately, and read the diff: it should contain version lines only.

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

## 9. Related

- [sharing-libraries](./sharing-libraries.md) — the git-clone path and the full authoring flow
- [subscribing-to-marketplaces](./subscribing-to-marketplaces.md) — the consumer's side of the feed you just published
- [marketstall.toml](../reference/files/marketstall-toml.md) — the row schema and `distribute`
- [haybale-canon](../haybale/haybale-canon.md) — required package layout
- [haybale-marketplace-arch §8](../haybale/marketplace/haybale-marketplace-arch.md#8-why-the-model-is-shaped-this-way) — why the flow is shaped this way
