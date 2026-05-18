# Versioning & Publishing Spec

**Status:** decided — ready for implementation  
**Date:** 2026-05-18  
**Author:** maybites  

---

## Problem

The haywire monorepo contains ten packages across two tiers. Before this spec there was no
coordinated release process, no PyPI publishing pipeline, no stable marketstall URL, no single
source of truth for version numbers, and no defined doc structure for haybale packages. Version
numbers in `pyproject.toml` and `@library` decorators were already drifting apart.

---

## Decisions

### 1. Versioning model — lockstep

All Tier 1 and Tier 2 packages share one version number per release. A single git tag
`vX.Y.Z` on `main` means all publishable packages release at that version simultaneously.

**Rationale:** packages are tightly coupled; independent versioning requires semver discipline
across the full tree and is unnecessary until external contributors maintain separate packages.

### 2. Version source of truth — `pyproject.toml`

`pyproject.toml` is the single authority. `@library(version=...)` is replaced in every haybale
`__init__.py` with:

```python
from importlib.metadata import version as _pkg_version
@library(
    version=_pkg_version("haybale-foo"),
    ...
)
```

Works for both installed and editable (`uv sync --dev`) installs. The bump script only touches
`pyproject.toml` files — no `__init__.py` changes needed at release time.

### 3. First release version — `0.0.1`

Nothing is on PyPI yet. All `pyproject.toml` files currently read `0.1.0`; these will be
patched to `0.0.1` as part of the initial migration. Signals: very early, expect change.

### 4. Dependency constraint format — compatible release `~=`

Inter-package dependencies use `~=X.Y.Z` (pip compatible release). For example:

```toml
dependencies = ["haywire-core~=0.0.1"]
```

This means `>=0.0.1, <0.1.0` — allows patch bumps, blocks minor version jumps. The bump
script updates all lower bounds on every release. Standard pip convention, no custom schema.

### 5. Package tiers

| Tier | Packages | Publish target |
|---|---|---|
| 1 — Framework | `haywire-core`, `haywire-studio` | PyPI |
| 2 — Official haybale | `haybale-core`, `haybale-studio`, `haybale-graph-editor`, `haybale-haystack`, `haybale-example` | PyPI |
| 2 — Git-only | `haybale-visiongraph` | git only (binary deps, not suitable for PyPI yet) |
| 3 — Internal | `haybale-testing`, `haybale-TEST_A` | never published |

### 6. Marketstall vs Marketplace

See glossary for canonical definitions. In brief:

- **Marketstall** (`marketstall.toml`) — a TOML file a library author hosts that lists their
  packages. Produced by `haywire share`. Lives at repo root. Platform-agnostic raw URL.
- **Marketplace** (`.haywire/marketplace.toml`) — the local project catalog of installable
  packages; aggregated from one or more marketstall feeds.

The official haywire monorepo marketstall is deployed to GitHub Pages after each release:
`https://maybites.github.io/haywire/marketstall.toml`

### 7. Marketstall file format

A marketstall is a TOML file with one top-level key `[[packages]]`. Each entry maps to a
`MarketplaceEntry` (defined in `haywire.core.marketplace`).

#### Complete field reference

| Field | Type | Persisted | Description |
|---|---|---|---|
| `name` | `str` | yes | pip distribution name, e.g. `"haybale-haystack"`. Required. |
| `label` | `str` | yes | Human-readable display name, e.g. `"Haystack"`. |
| `min_version` | `str` | yes | **Minimum required version** — the oldest version of this package that is known to work correctly, e.g. `"0.0.1"`. Not "latest available." See rationale below. |
| `description` | `str` | yes | One-line summary shown in the Library Manager. |
| `author` | `str` | yes | Author name or team name. |
| `source` | `str` | yes | Install method: `"pypi"`, `"git"`, or `"local"`. Required. |
| `install_spec` | `str` | yes | The exact string passed to `uv install`. See formats below. |
| `tags` | `list[str]` | yes | Searchable keywords, e.g. `["vision", "camera"]`. |
| `dependencies` | `list[str]` | yes | pip distribution names of required haybale packages, e.g. `["haybale-core"]`. **Bare names only — no version constraints.** See rationale below. |
| `source_url` | `str` | yes | URL to the library source — repo root or subdirectory. Used for the "Source" link in the UI and as a fallback for doc discovery. |
| `docs_url` | `str` | yes | Raw URL to the module directory containing `OVERVIEW.md`. See resolution strategy below. |
| `source_label` | `str` | **no** | Runtime-only. Which feed this entry came from (`"project"`, `"official"`, a user-defined feed name). Never written to TOML. |
| `source_file` | `str` | **no** | Runtime-only. Local path to the marketstall file the user can edit. Never written to TOML. |
| `source_origin` | `str` | **no** | Runtime-only. Remote URL if fetched via a `[[sources]]` entry. Never written to TOML. |

The three `source_*` runtime fields are populated by the Library Manager when loading — they are
never written to any file. `to_dict()` only serialises the first 11 fields (the `_TOML_FIELDS`
tuple).

#### `min_version` — minimum required, not latest available

`min_version` declares the **oldest version of this package known to work correctly** — a floor,
not a ceiling. It is set by the author at marketstall generation time and does not go stale
as new versions are released.

**What it is NOT:** it is not "the latest published version." That information is always
fetched live via `fetch_versions()` (PyPI JSON API for `source = "pypi"`, GitHub tags API
for `source = "git"`).

**Library Manager behaviour:**

| Signal | Source | Used for |
|---|---|---|
| `marketstall.min_version` | marketstall entry | Install gate: warn if installed version is below this floor |
| `fetch_versions()` result | live PyPI / GitHub API | "Update available" badge and version picker |
| `installed_lib.identity.version` | installed package metadata | Current installed version display |

The current Library Manager compares `marketplace_pkg.min_version > installed_lib.identity.version`
to show the "Update available" badge. This must be changed (T10): the badge should be driven by
`fetch_versions()` instead. `marketplace_pkg.min_version` becomes an install-gate floor check only.

**What authors set it to:** the version at which the marketstall entry was authored. For the
official CI-generated marketstall this is always the current release version. For `haywire share`
this is whatever `min_version` is in `pyproject.toml` at time of running.

#### `dependencies` — purpose and format

The `dependencies` field serves **UI orchestration only** — it is not consumed by pip/uv.
Its two jobs in the Library Manager are:

1. **Install ordering** — block the Install button for a dependent until all its dependencies
   are installed and enabled. Ensures that e.g. `haybale-haystack` cannot be installed before
   `haybale-studio` is both installed and enabled (required for reliable studio operation).

2. **Disable/uninstall guards** — prevent disabling or uninstalling a library while any
   installed dependent still needs it.

Version constraints are **intentionally omitted**. Reasons:

- The Library Manager checks presence and enabled-state, not version compatibility.
- `pyproject.toml` is the canonical record of what is installed and at what version — uv
  handles actual version resolution when `uv install` is called.
- The marketplace is a discovery and orchestration surface, not a package management system.
  If the user clones the project to another machine, `uv sync` restores everything from
  `pyproject.toml` without consulting the marketplace at all.
- Third-party authors version independently. A version constraint from the official marketstall
  would be wrong or misleading for community libraries that have their own release cadence.

Format: bare pip distribution names (hyphens), never Python module names (underscores),
never version specifiers.

```toml
dependencies = ["haybale-studio", "haybale-graph-editor"]   # correct
dependencies = ["haybale_studio", "haybale-studio~=0.0.1"]  # wrong
```

#### `install_spec` formats by source

| `source` | `install_spec` format | Example |
|---|---|---|
| `"pypi"` | package name, optionally version-pinned | `"haybale-haystack"` or `"haybale-haystack==0.0.1"` |
| `"git"` | full PEP 440 VCS URL with optional `#subdirectory=` | `"haybale-haystack @ git+https://github.com/user/repo.git#subdirectory=barn/haybale-haystack"` |
| `"local"` | absolute path to package directory | `"/home/user/my-project/barn/haybale-my-project"` (editable install) |

#### `docs_url` — resolution strategy

`docs_url` is used **only for pre-install discovery** (marketplace browsing before a package is
installed). Once installed, the Library Manager reads `OVERVIEW.md` directly from
`lib.identity.folder_path` on disk — no URL fetch needed.

The Library Manager resolves docs in this priority order:

1. **Explicit `docs_url`** — if set, treated as either:
   - A local path → reads `OVERVIEW.md` or `QUICKREF.md` from that directory
   - An HTTP URL ending in `.md` → fetched directly
   - An HTTP URL (directory) → tries `{url}/OVERVIEW.md` then `{url}/QUICKREF.md`

2. **Heuristic GitHub lookup** — derived from `source_url` or the git URL in `install_spec`.
   Constructs raw.githubusercontent.com URLs for both `main` and `master` branches, tries
   `{module_name}/OVERVIEW.md` inside any declared `#subdirectory`.

3. **PyPI long_description fallback** — for `source = "pypi"` only: fetches the package
   description from the PyPI JSON API (i.e. the `README.md` content uploaded with the package).

**What to set for each source type:**

| Source type | Recommended `docs_url` | Fallback if omitted |
|---|---|---|
| `"pypi"` (GitHub-hosted) | `https://raw.githubusercontent.com/{user}/{repo}/main/{subdir}/{module}/` | Heuristic lookup from `source_url`, then PyPI description |
| `"git"` | `https://raw.githubusercontent.com/{user}/{repo}/main/{subdir}/{module}/` | Heuristic lookup from `install_spec` git URL |
| `"local"` | Absolute path to module dir, e.g. `/path/to/barn/haybale-foo/haybale_foo/` | No fallback — set it explicitly |
| Any (GitLab) | `https://gitlab.com/{user}/{repo}/-/raw/main/{subdir}/{module}/` | No heuristic for GitLab — must be explicit |
| Any (Bitbucket etc.) | Explicit raw URL | No heuristic — must be explicit |

**Key insight:** for officially published PyPI packages the `docs_url` raw GitHub URL works
before install, and post-install the file is read from disk — so `docs_url` is only needed for
the "Available" tab in the Library Manager. For `"local"` source the Library Manager can always
read from disk directly, so `docs_url` is optional.

#### Two producers, two `source` values

- `haywire share [--save]` → always `source = "git"` (third-party authors, git-hosted)
- `scripts/generate_marketstall.py` (CI) → always `source = "pypi"` (officially published)

#### Full annotated example

```toml
[[packages]]
name         = "haybale-haystack"
label        = "Haystack"
min_version  = "0.0.1"
description  = "File-centric multi-graph manager for Haywire"
author       = "Haywire Team"
source       = "pypi"
install_spec = "haybale-haystack"
tags         = ["haystack", "graphs", "files"]
dependencies = ["haybale-studio", "haybale-graph-editor"]
source_url   = "https://github.com/maybites/haywire"
docs_url     = "https://raw.githubusercontent.com/maybites/haywire/main/barn/haybale-haystack/haybale_haystack/"
```

#### Minimal valid marketstall (scaffolded by `haywire init`)

```toml
# marketstall.toml — share this file's raw URL so others can subscribe to your library feed
# Run: haywire share --save   to update this file

[[packages]]
name         = "haybale-my-project"
label        = "My Project"
min_version  = "0.1.0"
source       = "git"
install_spec = "haybale-my-project @ git+https://<REPO_URL>.git#subdirectory=barn/haybale-my-project"
```

### 8. `haywire share` stays git-only

`haywire share` always produces `source = "git"` entries. It is the tool for third-party authors
who publish on git but not PyPI. A new `--save` flag writes the output to `marketstall.toml` at
the repo root instead of stdout, aggregating all barn libraries in the repo into one file.
`haywire init` scaffolds an empty `marketstall.toml` at the project root.

`haywire share --save` works identically for both library-only repos and project repos (which
also contain graphs, haystacks, and other project artefacts). The marketstall always lives at
the repo root regardless of project structure. For projects with multiple barn libraries, all
entries are aggregated into the single root `marketstall.toml`.

The CI marketstall generator (`scripts/generate_marketstall.py`) is a separate internal script
that produces `source = "pypi"` entries for officially published packages.

### 9. Haybale package documentation structure

```
barn/haybale-foo/
  pyproject.toml
  README.md               ← generated by haywire-gen-docs (see content model below)
  haybale_foo/
    __init__.py           ← @library(version=importlib.metadata.version(...))
    OVERVIEW.md           ← generated — component catalog (ships inside wheel)
    QUICKREF.md           ← generated — compact alphabetical reference (ships inside wheel)
    NOTES.md              ← hand-authored, never touched by generator (ships inside wheel)
    docs/
      nodes/ClassName.md  ← generated, sha256 hash-tracked (ships inside wheel)
      widgets/ClassName.md
```

The `marketstall.toml` lives at the **repo root**, not inside the barn library directory.

#### README.md content model

`README.md` is **fully generated** by `haywire-gen-docs` in one pass alongside `OVERVIEW.md`.
It is not hand-authored. Hand-authored content belongs in `NOTES.md`.

```
README.md  (package root — NOT shipped in wheel; visible on PyPI and git platforms)
│
├── [NOTES.md content verbatim, if present]
│   The author's "what & why" — problem domain, key abstractions, when to use
│
└── [Component catalog — identical content to OVERVIEW.md]
    Nodes grouped by category, one intent line each
    Types, Widgets, Adapters as flat lists
```

`OVERVIEW.md` (module dir — ships inside wheel; read from disk post-install by Library Manager)
```
└── [Component catalog only — no NOTES.md prefix]
```

Both files are generated from the same source data in one pass. They cannot diverge.
No cross-file links are generated — the catalog IS the content in both files.

#### Why two files with overlapping content

| | `README.md` | `OVERVIEW.md` |
|---|---|---|
| Location | package root (not in wheel) | module dir (in wheel) |
| Reachable via | git raw URL, PyPI `info.description` | `lib.identity.folder_path` on disk |
| When useful | pre-install discovery (marketplace browsing, LLM agents, PyPI page) | post-install runtime (Library Manager, LLM agents after install) |
| Contains NOTES | yes (prepended) | no (catalog only) |

The PyPI JSON API returns `README.md` content as `info.description` — the only discovery path
for a package with no git reference. This makes `README.md` the **universal fallback** discovery
document reachable via every distribution method.

`NOTES.md` replaces the old `LIBRARY.md` name. Its content is prepended to `README.md` and
also appended as "Additional Notes" in `OVERVIEW.md` by the generator.

---

## Release flow

### Local (author-driven via `/haywire-release` skill)

```
1. Skill prompts: "Release version?" — author enters e.g. 0.0.2
2. Runs: pytest -m "not integration"          ← gate; stops on failure
3. Patches version in all Tier 1+2 pyproject.toml files
4. Updates all ~= constraints to new version
5. Shows unified diff of all changed files
6. Asks: "Commit, tag v0.0.2, and push?" — author confirms
7. Commits: "chore: release v0.0.2"
8. Creates tag v0.0.2 and pushes branch + tag
9. CI takes over
```

### CI pipeline (on tag `v*.*.*`)

**Job 1 — gate**
```
pytest -m "not integration"
```
Fails → pipeline stops, nothing publishes.

**Job 2 — publish** (sequential, dependency order, fail-fast)
```
haywire-core
→ haywire-studio
→ haybale-core
→ haybale-studio
→ haybale-graph-editor
→ haybale-haystack
→ haybale-example
```
Each step: `uv build` → `uv publish` via PyPI Trusted Publisher (OIDC — no stored token).
Any failure stops remaining packages.

**Job 3 — deploy marketstall** (only if Job 2 succeeded)
```
python scripts/generate_marketstall.py
→ deploys marketstall.toml to GitHub Pages
```
The generator reads each package's `pyproject.toml`, emits `source = "pypi"` entries with
`~=` version constraints on dependencies.

---

## Implementation tasks

In dependency order:

- [x] **T1** — Patch `@library` decorators to use `importlib.metadata.version()` in all barn packages
- [ ] **T2** — `scripts/bump_version.py` — patches all Tier 1+2 `pyproject.toml` version fields and `~=` constraints
- [ ] **T3** — `scripts/generate_marketstall.py` — CI marketstall generator (PyPI source entries)
- [ ] **T4** — `.github/workflows/publish.yml` — publish + deploy CI workflow
- [ ] **T5** — `haywire share --save` — write to `marketstall.toml` at repo root, aggregating all barn libraries
- [ ] **T6** — `haywire init` scaffold update — add empty `marketstall.toml` at project root
- [ ] **T7** — Remote marketstall loading — wire `_fetch_remote_marketplace` at app startup
- [ ] **T8** — `/haywire-release` skill — guides author through release flow
- [ ] **T9** — `haywire-gen-docs` skill update — `LIBRARY.md` → `NOTES.md`, generate both `README.md` and `OVERVIEW.md` in one pass
- [ ] **T10** — Library Manager "Update available" logic — replace `marketplace_pkg.min_version` comparison with live `fetch_versions()` result; use `marketplace_pkg.min_version` as install-floor check only
- [ ] **T11** — `haybale-marketplace` carve-out — Library Manager extracted from `haybale-studio` (scope TBD, separate spec)

### Task dependencies

```
T1 (importlib.metadata)
T2 (bump script) → T8 (release skill)
T3 (marketstall gen) → T4 (CI workflow)
T4 (CI workflow) requires: T1, T2, T3
T5 (share --save) → T6 (init scaffold)
T7 (remote loading) — independent
T9 (gen-docs skill) — independent
T10 (update-available logic) — independent
T11 — separate spec
```

---

## Files changed at first migration (pre-release)

| File | Change |
|---|---|
| `barn/*/haybale_*/`__init__.py` | Replace `version="..."` with `importlib.metadata.version(...)` |
| `barn/*/pyproject.toml` | `version = "0.0.1"`, all inter-package deps to `~=0.0.1` |
| `packages/*/pyproject.toml` | `version = "0.0.1"`, `haywire-core~=0.0.1` |
| `barn/*/haybale_*/LIBRARY.md` | Rename to `NOTES.md` (haybale-visiongraph only, currently) |
| `barn/haybale-visiongraph/haybale_visiongraph/OVERVIEW.md` | Stays as-is; other packages need docs generated |

---

## Open / deferred

- **`haybale-visiongraph` on PyPI** — deferred until binary wheel complexity is resolved
- **`haybale-marketplace` split** — separate spec; `haybale-studio` retains the Library Manager until that spec is written
- **Multi-source marketstall aggregation** — exact UX for adding/removing remote feeds is TBD
- **Version constraint in `@library(dependencies=[...])`** — currently name-only; version ranges not yet supported. Separate concern from this spec.
- **"Update available" badge** — covered by T10; driven by live `fetch_versions()`, not the marketstall `version` field.
