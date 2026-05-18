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

Inter-package dependencies in **`pyproject.toml`** use `~=X.Y.Z` (pip compatible release):

```toml
# In a package's pyproject.toml — read by uv at install time
[project]
dependencies = ["haywire-core~=0.0.1"]
```

This means `>=0.0.1, <0.1.0` — allows patch bumps, blocks minor version jumps. The bump
script updates all lower bounds on every release. Standard pip convention, no custom schema.

**Not the same field as the marketstall `dependencies` field.** Marketstall `[[packages]]`
entries also have a `dependencies` field, but it serves UI install-ordering only and uses
bare pip distribution names with no version constraints (see §7). The two fields share a
name but live in different files and serve different purposes:

| File                       | Field                    | Format                    | Consumed by                                                  |
| -------------------------- | ------------------------ | ------------------------- | ------------------------------------------------------------ |
| `pyproject.toml`           | `[project] dependencies` | `["haybale-core~=0.0.1"]` | uv at install time                                           |
| Marketstall `[[packages]]` | `dependencies`           | `["haybale-core"]`        | Library Manager UI (install order, disable/uninstall guards) |

### 5. Package tiers

| Tier                 | Packages                                                                                        | Publish target                                    |
| -------------------- | ----------------------------------------------------------------------------------------------- | ------------------------------------------------- |
| 1 — Framework        | `haywire-core`, `haywire-studio`                                                                | PyPI                                              |
| 2 — Official haybale | `haybale-core`, `haybale-studio`, `haybale-graph-editor`, `haybale-haystack`, `haybale-example` | PyPI                                              |
| 2 — Git-only         | `haybale-visiongraph`                                                                           | git only (binary deps, not suitable for PyPI yet) |
| 3 — Internal         | `haybale-testing`, `haybale-TEST_A`                                                             | never published                                   |

**Source of truth:** the table above is human documentation. The machine-readable canonical
list lives in the monorepo's root `pyproject.toml` under `[tool.haywire.release]` and is read
by the bump script (T2), marketstall generator (T3), and CI workflow (T4). See
[docs/reference/publish_releases.md](../../docs/reference/publish_releases.md) for the schema
and the complete operational procedure (release flow, recovery, adding packages, tier moves).
If this table ever disagrees with `[tool.haywire.release]`, the latter wins — update the table
to match.

### 6. Marketstall vs Marketplace

See glossary for canonical definitions. In brief:

- **Marketstall** — a TOML file a library author hosts (`marketstall.toml` at their repo root)
  that lists their packages. Produced by `haywire share`. Subscribers reach it via a raw URL.
- **Marketplace** — a TOML file the *user* curates (`~/.haywire/marketplace.toml` machine-global,
  `<project>/.haywire/marketplace.toml` per-project cache). The marketplace is a catalog of
  installable packages, aggregated from multiple sources (direct entries, subscribed
  marketstalls, subscribed marketplaces, project-local libraries).

The official haywire monorepo marketplace is deployed to GitHub Pages after each release:
`https://maybites.github.io/haywire/marketplace.toml`. New haywire installs pre-subscribe to
this URL on first run.

#### Two-tier model: global ground truth, project cache

**Global marketplace** (`~/.haywire/marketplace.toml`) — machine-wide ground truth. Curated
by the user via the Library Manager UI. Fully UI-managed for additions; manual edit (via an
"Edit file" button that opens the OS text editor) for deletions and `ignores` adjustments.
Contains four section types — see [structure](#global-marketplace-structure) below.

**Project marketplace** (`<project>/.haywire/marketplace.toml`) — per-project transient
cache. Populated by **refresh** (manual, user-triggered): the Library Manager reads global,
fetches subscribed marketplaces and marketstalls, flattens to a list of resolved packages,
and writes them as `[[packages]]` entries in the project marketplace. `[[locals]]` in the
project marketplace are untouched by refresh (they survive every refresh) and are written
once by `haywire init`.

Refresh is not automatic on startup — fetching multiple remote URLs is slow, and the user
should not wait. Refresh runs only when the user clicks the **Refresh** button.

#### Global marketplace structure

The global file uses four section types, each with a distinct role:

```toml
# Subscribed remote marketplaces (curated aggregations).
# Pre-seeded on first run with the official haywire marketplace.
[[marketplaces]]
url     = "https://maybites.github.io/haywire/marketplace.toml"
ignores = []   # package names from this marketplace to skip — populated when user resolves conflicts
doubles = []   # package names also provided by another source — silent dedup diagnostic

# Subscribed remote marketstalls (single-author feeds).
[[marketstalls]]
url     = "https://author.example/marketstall.toml"
ignores = []
doubles = []

# Direct user-added marketstall entries.
# Same schema as the §7 marketstall [[packages]] format.
[[packages]]
name = "haybale-foo"
# ...

# Project-scaffolded local libraries (registered by haywire init).
[[locals]]
name = "haybale-my-project"
path = "/Users/<user>/code/my-project/barn/haybale-my-project"
# ...
```

Notes:

- All four sections are optional and can be empty.
- A `[[packages]]` entry in the global is a "direct" entry — the user pasted in a marketstall
  block manually (or scaffolding added it).
- A `[[locals]]` entry is a path-based reference to a project's own barn library. It is
  always installed editably; it is never published to PyPI or git. Locals are how
  `haywire init` and `haywire init --dev` populate the catalog.

#### Project marketplace structure

```toml
# Untouched by refresh — written by haywire init.
[[locals]]
# the project's own scaffolded library

# Cache: flattened, resolved package list from the last refresh.
# Each entry includes "via" annotation recording the source URL it came from.
[[packages]]
name = "haybale-foo"
via  = "https://author.example/marketstall.toml"
# ... rest of the §7 schema
```

The project marketplace has no `[[marketstalls]]` or `[[marketplaces]]` sections — those
live only in the global file. The project marketplace is a pure cache of resolved packages
plus its own `[[locals]]`.

#### Refresh semantics

The user clicks **Refresh** in the Library Manager. The refresh:

1. Reads the global marketplace.
2. For each `[[marketplaces]]` entry, fetches the URL. The response is itself a marketplace
   file. Reads its `[[marketstalls]]` and `[[packages]]` sections. **Resolution is one level
   deep**: a remote marketplace's own `[[marketplaces]]` entries are ignored (no recursive
   chain-following). This prevents infinite recursion and bounds the refresh blast radius.
3. For each `[[marketstalls]]` entry (both directly in the global and discovered via step 2),
   fetches the URL and reads its `[[packages]]` section.
4. Builds a flat candidate list of packages by concatenating: global `[[packages]]`, global
   `[[locals]]`, all resolved marketstalls, and remote-marketplace `[[packages]]`.
5. Applies conflict resolution (see below).
6. Writes the resolved list to the project marketplace as `[[packages]]` (preserving
   `[[locals]]` from the project marketplace untouched).
7. Compares against the previous project marketplace: any package that *was* in the cache
   but is no longer resolved gets marked **stale** with a `last_seen` timestamp.

Stale entries are kept in the project marketplace if the corresponding package is currently
installed. Stale + uninstalled entries are user-removable via the UI; stale + installed
entries are locked until the user uninstalls.

Refresh never silently removes a cache entry — it can add, modify, or mark stale.

#### Conflict resolution

Conflicts are resolved by **first-come, first-served** at refresh time, with two
user-managed override mechanisms:

| Situation                                                                            | Resolution                                                                                                                                                                                                                                                                |
| ------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Same marketstall URL via two `[[marketplaces]]`                                      | Silent dedup; the second `[[marketplaces]]` entry gets the marketstall name added to its `doubles` array for diagnostics. No user prompt.                                                                                                                                 |
| Two different marketstalls (different URLs) both advertise the same package `name`   | First-encountered wins. The user is prompted at the moment a new subscription would introduce the conflict: "this marketplace/marketstall provides `haybale-foo`, also provided by `<other>` — which to keep?" The losing side's `ignores` array gains that package name. |
| A `[[locals]]` entry has the same `name` as a resolved package from any other source | `[[locals]]` wins. The other source's contribution is silently shadowed.                                                                                                                                                                                                  |
| Two `[[locals]]` entries with the same `name` in the global                          | Refused at `haywire init` time (G5 — name collision between projects). The user must rename one of their projects.                                                                                                                                                        |
| Two `[[packages]]` (direct) entries with the same `name` in the global               | Refused at UI write time and by the parser.                                                                                                                                                                                                                               |

`ignores` lives on the **yielding** side: when a user picks between A and B for `haybale-foo`,
the losing entry's parent source gets `haybale-foo` added to its `ignores` array. Refresh
honours `ignores` by skipping those names from that source.

#### Remote fetch behaviour

The Library Manager fetches remote marketplaces and marketstalls following these rules:

- **When**: only on user-triggered **Refresh**. Not on startup.
- **On success**: response is cached in `~/.haywire/cache/<url-hash>.toml` with the fetch
  timestamp. Cache replaces any previous entry for the same URL.
- **On failure** (network error, HTTP 4xx/5xx, malformed TOML, timeout, GitHub-301-redirect-
  expired): the error is logged. If a cached response exists, the cache is used as a fallback
  and the affected entries get a "stale" badge with a tooltip showing the cache age. If no
  cache exists, the source is skipped and the user sees a banner "1 source unavailable:
  `<url>`".
- **Network-isolated environments**: with at least one prior successful refresh cached, the
  Library Manager operates fully offline. With no cache, only `[[packages]]` and `[[locals]]`
  from the global are available.
- **Cache invalidation**: only by successful re-fetch on next refresh. No TTL — stale-cache
  age is shown but never auto-discards.
- **Malformed global**: if the global file itself is malformed (invalid TOML, schema
  violation, intra-file duplicate), the Library Manager refuses to start and surfaces the
  error. The "Edit file" button opens the global so the user can fix it. No auto-recovery.

#### Adding sources via the UI

Three add paths, all enforced at write time:

1. **Add a marketplace URL**: user pastes a marketplace URL. The Library Manager fetches it
   immediately (G4 fail-fast on parse), scans its `[[marketstalls]]` and `[[packages]]` for
   name conflicts against the current resolved state. Conflicts surface a per-package prompt
   ("keep existing / use new"). Result is written to global `[[marketplaces]]`.
2. **Add a marketstall URL**: user pastes a marketstall URL. Same conflict-check flow.
   Written to global `[[marketstalls]]`.
3. **Add a direct package entry**: user pastes a marketstall TOML block (or fills a form).
   Conflict-checked against `name`. Written to global `[[packages]]`.

After any add, the UI prompts the user to **Refresh** so the new source flows into the
project marketplace.

Deletion is not exposed in the UI in the initial implementation: the user clicks "Edit file"
which opens the global marketplace in the OS text editor. After saving, a refresh is
required. This keeps the UI surface small and matches the spec's "the file is an
implementation detail in the happy path" principle.

#### Installed metadata vs. catalog metadata

The installed library card always reflects what was actually installed in the venv, not what
the catalog currently advertises. Source-of-truth: `importlib.metadata` for installed packages
(including the install-source kind read from `direct_url.json` — used by the tier-transition
detection logic to offer "Switch to PyPI" when a git-installed package is now PyPI-available);
the project marketplace for the "Available" tab.

A consequence of the conflict-resolution rules above: at any given moment, the project
marketplace has at most one entry per package `name`. Subscribing to a second source for an
already-listed package either prompts the user to pick (and updates the loser's `ignores`)
or is silently shadowed by an existing `[[locals]]` entry. The user never sees two competing
entries for the same package simultaneously.

#### Manual `pyproject.toml` edits

The Library Manager observes installed packages exclusively through `LibraryRegistry`, which
discovers them via the `haywire.libraries` entry-point mechanism on a venv scan. It does not
parse `pyproject.toml` to determine what is installed.

Concrete consequences:

- **User adds a dependency to `pyproject.toml` and runs `uv sync`** — venv changes, registry
  scan picks it up, Library Manager shows it as installed. No special handling needed.
- **User removes a dependency from `pyproject.toml` and runs `uv sync`** — venv changes,
  registry scan no longer finds it, Library Manager updates. No special handling needed.
- **User adds a dependency to `pyproject.toml` without running `uv sync`** — declarative
  state diverges from runtime state. This is uv's domain, not the Library Manager's. The
  user will discover the gap the next time they run `uv sync`. The Library Manager does not
  parse `pyproject.toml` to detect this divergence.
- **Library Manager installs via `uv add` (T12)** — both `pyproject.toml` and the venv are
  updated atomically. Registry rescan picks it up.

Authoritative split:

- `pyproject.toml` — declarative truth (what should be installed).
- Venv via `LibraryRegistry` — runtime truth (what is installed).
- `uv sync` — the reconciler between the two; not owned by the Library Manager.

### 7. Marketstall file format

A marketstall is a TOML file with one top-level key `[[packages]]`. Each entry maps to a
`MarketplaceEntry` (defined in `haywire.core.marketplace`).

#### Complete field reference

| Field           | Type        | Persisted | Description                                                                                                                                                     |
| --------------- | ----------- | --------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `name`          | `str`       | yes       | pip distribution name, e.g. `"haybale-haystack"`. Required.                                                                                                     |
| `label`         | `str`       | yes       | Human-readable display name, e.g. `"Haystack"`.                                                                                                                 |
| `min_version`   | `str`       | yes       | **Minimum required version** — the oldest version of this package that is known to work correctly, e.g. `"0.0.1"`. Not "latest available." See rationale below. |
| `description`   | `str`       | yes       | One-line summary shown in the Library Manager.                                                                                                                  |
| `author`        | `str`       | yes       | Author name or team name.                                                                                                                                       |
| `source`        | `str`       | yes       | Install method: `"pypi"` or `"git"`. Required. Path-based libraries live in `[[locals]]` (see §6), not as `[[packages]]` entries.                               |
| `install_spec`  | `str`       | yes       | The exact string passed to `uv install`. See formats below.                                                                                                     |
| `tags`          | `list[str]` | yes       | Searchable keywords, e.g. `["vision", "camera"]`.                                                                                                               |
| `dependencies`  | `list[str]` | yes       | pip distribution names of required haybale packages, e.g. `["haybale-core"]`. **Bare names only — no version constraints.** See rationale below.                |
| `source_url`    | `str`       | yes       | URL to the library source — repo root or subdirectory. Used for the "Source" link in the UI and as a fallback for doc discovery.                                |
| `docs_url`      | `str`       | yes       | Raw URL to the module directory containing `OVERVIEW.md`. See resolution strategy below.                                                                        |
| `source_label`  | `str`       | **no**    | Runtime-only. Which feed this entry came from (`"project"`, `"official"`, a user-defined feed name). Never written to TOML.                                     |
| `source_file`   | `str`       | **no**    | Runtime-only. Local path to the marketstall file the user can edit. Never written to TOML.                                                                      |
| `source_origin` | `str`       | **no**    | Runtime-only. Remote URL if fetched via a `[[sources]]` entry. Never written to TOML.                                                                           |

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

| Signal                           | Source                     | Used for                                                    |
| -------------------------------- | -------------------------- | ----------------------------------------------------------- |
| `marketstall.min_version`        | marketstall entry          | Install gate: warn if installed version is below this floor |
| `fetch_versions()` result        | live PyPI / GitHub API     | "Update available" badge and version picker                 |
| `installed_lib.identity.version` | installed package metadata | Current installed version display                           |

The current Library Manager compares `marketplace_pkg.min_version > installed_lib.identity.version`
to show the "Update available" badge. This must be changed (T10): the badge should be driven by
`fetch_versions()` instead. `marketplace_pkg.min_version` becomes an install-gate floor check only.

**What authors set it to:** the version at which the marketstall entry was authored. For the
official CI-generated marketstall this is always the current release version. For `haywire share`
this is whatever `min_version` is in `pyproject.toml` at time of running.

**UI display of installed/min/latest versions:** an installed library card shows two numbers
side-by-side: `Installed: X.Y.Z · Latest: Y.Y.Y` (latest from live `fetch_versions()`, cached
per refresh). `min_version` is hidden in the normal case — it appears only when the floor is
violated, as a warning badge: "Below required floor vX.Y.Z". This keeps the day-to-day display
focused on the two numbers users act on (installed and latest), while making floor violations
unmissable.

**When the floor is violated:** if a user attempts to install or already has installed a
version below the marketplace entry's `min_version`, the Library Manager shows a confirmation
modal:

> "v0.0.0 is below the marketplace floor of v0.0.1. The author marked this as 'known to work'
> starting at v0.0.1. Continue anyway? [Cancel] [Install older]"

The user can override the floor deliberately (one confirmation per install attempt). After
install, the "Below required floor" warning badge stays on the card as a visual reminder.
The floor is informational + deliberate-override-required, never a hard block — but never
silently allowed either.

**Repo renames and moves:** if a `source = "git"` entry references a renamed or moved git
repo, the Library Manager relies first on the hosting platform's redirect mechanism (GitHub
returns HTTP 301 with the new URL for ~1 year after a rename, and `uv pip install`'s git
client follows these automatically). When the user-visible URL changes, the Library Manager
surfaces a small "URL changed" notification offering to update the subscription. After the
platform redirect expires the fetch fails and falls back to the cached marketstall (§6
remote-fetch behaviour) with a "stale" badge; the user must obtain the new URL out-of-band.
The third-party authoring contract (§10) requires authors to keep their marketstall current
after a rename.

**Yanked floor version:** if `min_version` references a PyPI version that was later yanked,
the install will fail with a "no version satisfying" error. The Library Manager detects this
pattern (failure + available newer versions returned by `fetch_versions()`) and offers:
"v0.0.1 was yanked. Install v0.0.2 instead?" with a single confirm button. Because `min_version`
is a floor by definition, any newer version still honours the contract — installing forward is
the canonical recovery. The marketstall maintainer should still update the entry; the auto-fix
is a per-user workaround, not a permanent solution.

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

#### Source types

| `source`  | Intent                    | Where it appears                              |
| --------- | ------------------------- | --------------------------------------------- |
| `"pypi"`  | Published package on PyPI | `[[packages]]` in any marketstall/marketplace |
| `"git"`   | Git-hosted, not on PyPI   | `[[packages]]` in any marketstall/marketplace |
| `"local"` | Path-based reference      | `[[locals]]` only — see §6 two-tier model     |

Local libraries (project-scaffolded barn libraries, dev-repo references) are NOT `[[packages]]`
entries — they live in the `[[locals]]` section of the global or project marketplace. The
`[[locals]]` section uses a different schema (`name`, `path`, optional metadata fields) and is
never refreshed from remote sources. See §6 for the full structure.

This means `[[packages]]` entries — whether in a marketstall, a remote marketplace, or
directly in the global — always have `source = "pypi"` or `source = "git"`. Path-based
references are structurally separated, not a `source` value.

#### `install_spec` formats by source

| `source` | `install_spec` format                               | Example                                                                                        |
| -------- | --------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| `"pypi"` | package name, optionally version-pinned             | `"haybale-haystack"` or `"haybale-haystack==0.0.1"`                                            |
| `"git"`  | full PEP 440 VCS URL with optional `#subdirectory=` | `"haybale-haystack @ git+https://github.com/user/repo.git#subdirectory=barn/haybale-haystack"` |

`[[locals]]` entries do not have an `install_spec` field — the `path` field directly drives
an editable install (`uv pip install -e <path>` or, when project-relative, the uv workspace
membership).

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

| Source type              | Recommended `docs_url`                                                    | Fallback if omitted                                       |
| ------------------------ | ------------------------------------------------------------------------- | --------------------------------------------------------- |
| `"pypi"` (GitHub-hosted) | `https://raw.githubusercontent.com/{user}/{repo}/main/{subdir}/{module}/` | Heuristic lookup from `source_url`, then PyPI description |
| `"git"`                  | `https://raw.githubusercontent.com/{user}/{repo}/main/{subdir}/{module}/` | Heuristic lookup from `install_spec` git URL              |
| Any (GitLab)             | `https://gitlab.com/{user}/{repo}/-/raw/main/{subdir}/{module}/`          | No heuristic for GitLab — must be explicit                |
| Any (Bitbucket etc.)     | Explicit raw URL                                                          | No heuristic — must be explicit                           |

**Key insight:** for officially published PyPI packages the `docs_url` raw GitHub URL works
before install, and post-install the file is read from disk — so `docs_url` is only needed for
the "Available" tab in the Library Manager. `[[locals]]` entries always read docs from disk
directly via their `path` field, so they have no `docs_url` field at all.

#### Producers

- `haywire share [--save]` → emits a marketstall with `[[packages]]` of `source = "git"`
  (third-party authors, git-hosted).
- `scripts/generate_marketstall.py` (CI) → emits the official monorepo marketstall with
  `[[packages]]` of `source = "pypi"` (officially published).
- `haywire init` (regular and `--dev`) → writes `[[locals]]` to the user-global marketplace
  for the scaffolded project library. `--dev` additionally writes `[[locals]]` entries for
  the dev-repo libraries the user wants to test against.

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

#### Minimal valid marketstall (produced by `haywire share`)

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

### 8. `haywire init` and `haywire share` responsibilities

`haywire init` (regular and `--dev`) scaffolds a new project directory and registers the
project's own barn library with the user-global marketplace as a `[[locals]]` entry. It does
NOT create a `marketstall.toml`. The user only creates a marketstall when they explicitly want
to publish their library — that's `haywire share`'s job.

`haywire init` checks the user-global marketplace before writing the new `[[locals]]` entry: if
another `[[locals]]` already uses the same project library name, the init refuses with an error
asking the user to rename the new project (G5 — name collision between projects).

`haywire init --dev` additionally writes `[[locals]]` entries for each dev-repo library the
user wants to test against (`haybale-core`, `haybale-studio`, etc.), pointing at absolute paths
in the dev repo. These flow through the same path-based install mechanism as any other
`[[locals]]` entry.

`haywire share` always produces `source = "git"` `[[packages]]` entries. It is the tool for
third-party authors who publish on git but not PyPI. A `--save` flag writes the output to
`marketstall.toml` at the repo root instead of stdout, aggregating all barn libraries in the
repo into one file.

`haywire share --save` works identically for library-only repos and project repos. The
marketstall always lives at the repo root regardless of project structure. For projects with
multiple barn libraries, all entries are aggregated into the single root `marketstall.toml`.

The CI marketstall generator (`scripts/generate_marketstall.py`) is a separate internal script
that produces `source = "pypi"` entries for officially published packages, writing to the
official monorepo marketplace deployed at
`https://maybites.github.io/haywire/marketplace.toml`.

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

|                | `README.md`                                                         | `OVERVIEW.md`                                                    |
| -------------- | ------------------------------------------------------------------- | ---------------------------------------------------------------- |
| Location       | package root (not in wheel)                                         | module dir (in wheel)                                            |
| Reachable via  | git raw URL, PyPI `info.description`                                | `lib.identity.folder_path` on disk                               |
| When useful    | pre-install discovery (marketplace browsing, LLM agents, PyPI page) | post-install runtime (Library Manager, LLM agents after install) |
| Contains NOTES | yes (prepended)                                                     | no (catalog only)                                                |

The PyPI JSON API returns `README.md` content as `info.description` — the only discovery path
for a package with no git reference. This makes `README.md` the **universal fallback** discovery
document reachable via every distribution method.

`NOTES.md` replaces the old `LIBRARY.md` name. Its content is prepended to `README.md` and
also appended as "Additional Notes" in `OVERVIEW.md` by the generator.

### 10. Third-party authoring contract

Any author can publish a haybale library that participates in the haywire ecosystem provided
they meet the contract below. The release tooling for third parties (CI templates, generalised
release skill) is staked as a follow-up spec — see
[third-party-release-tooling.md](./third-party-release-tooling.md). This section defines what
"compliant" means independent of any tooling.

#### Required

A third-party haybale library MUST provide:

- **`pyproject.toml`** at the repo root (or at the library subdirectory in multi-library
  repos) with:
  - `[project] name = "haybale-*"` — the pip distribution name follows the `haybale-` prefix
    convention.
  - `[project] version = "X.Y.Z"` — semver, the single source of truth.
  - `[project] requires-python = ">=3.10"` — minimum Python version.
  - `[project.entry-points."haywire.libraries"]` entry resolving to a `BaseLibrary` subclass.
- **`@library` decorator** on the `BaseLibrary` subclass with at least:
  - `label` — human-readable display name.
  - `id` — short identifier (no `haybale_` prefix).
  - `version` — must come from `importlib.metadata.version("haybale-foo")`, not a hardcoded
    string. This guarantees `pyproject.toml` is the single source of truth.
  - `dependencies` — list of pip distribution names (hyphens) for any required haybale
    libraries, e.g. `["haybale-core"]`. Empty list if none.
- **For PyPI publishing**: a valid PyPI package — Trusted Publisher (OIDC) recommended, but
  the author may use any auth method PyPI supports.
- **For marketstall publishing**: a `marketstall.toml` at the repo root with at least one
  `[[packages]]` entry conforming to the §7 schema. Required fields per entry: `name`,
  `min_version`, `source`, `install_spec`.

A library meeting only the Required contract is installable, importable, and resolvable by
the Library Manager. It may render with minimal UI affordances (no description, no tags,
no docs link) — see Recommended below.

#### Recommended

A compliant library SHOULD additionally provide:

- **`@library` decorator** fields: `description`, `author`, `tags`, `url`, `author_url`,
  `help_url`. These populate the Library Manager UI.
- **Marketstall entry** fields: `label`, `description`, `author`, `tags`, `source_url`,
  `docs_url`. See §7 for the resolution strategy when fields are omitted.
- **Generated docs** via `haywire-gen-docs`: `README.md` at the package root, `OVERVIEW.md`
  and `QUICKREF.md` in the module directory, per-component docs under `docs/`. See §9.
- **Hand-authored `NOTES.md`** in the module directory — the author's "what & why" content
  that the generator prepends to `README.md`.
- **Semver discipline** — patch versions for fixes, minor for new features, major for
  breaking changes. `~=X.Y.Z` constraints depend on this.

#### Private repos and auth

If an author publishes from a private git repo, **subscribers are responsible for configuring
their own git credentials** (SSH keys, credential helper, `~/.netrc`, etc.). The Library
Manager does not handle authentication — it delegates entirely to `uv pip install` and the
underlying git client. Any auth failure surfaces as the raw clone error from uv. Authors
publishing from private repos should document the required credentials setup in their
`NOTES.md`.

Auth handling is intentionally out of scope: it is an OS/git configuration concern that
haywire does not own. The third-party authoring contract requires only that the install
target is reachable with the subscriber's existing git setup.

#### UI behaviour for partial compliance

The Library Manager surfaces a hint on entries that meet Required but not Recommended:

- Missing `description` → "No description provided" in the list view.
- Missing `tags` → tag chips area shows "No tags".
- Missing `docs_url` and no resolvable fallback → "No documentation available" in the
  details view, with a tooltip linking to the contract docs.

These hints are informational, not gating — a library with no recommended fields still
installs, enables, and runs normally.

---

## Release flow

### Local (author-driven via `/haywire-release` skill)

```
0. Skill prints: "Current release version: x.y.z"
1. Skill prompts: "New release version?" — author enters e.g. 0.0.2
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

#### Job 1 — gate

```
pytest -m "not integration"
```

Fails → pipeline stops, nothing publishes.

#### Job 2 — build all wheels

For every package in `publish_order`, run `uv build` and collect the resulting wheel and
sdist into the workflow's artifact storage. All builds happen before any publish — a build
failure in any package stops the pipeline before anything reaches PyPI. This catches build
errors (missing files, invalid metadata, dependency resolution failures) without leaving
partial state on PyPI.

If Job 2 fails, nothing publishes. Fix the build error, push a new tag (or re-run the
workflow), and try again.

#### Job 3 — publish wheels (sequential, dependency order, idempotent, fail-fast)

```text
haywire-core
→ haywire-studio
→ haybale-core
→ haybale-studio
→ haybale-graph-editor
→ haybale-haystack
→ haybale-example
```

For each package in `publish_order`:

1. Check whether `name == version` already exists on PyPI (PyPI JSON API: `GET /pypi/<name>/<version>/json`). If it does, skip — already published in a previous run.
2. Otherwise: `uv publish` the wheel and sdist from Job 2's artifacts via PyPI Trusted Publisher (OIDC — no stored token).

Any failure stops remaining packages. The "already exists" skip makes the workflow
idempotent: re-running after a partial failure picks up where it left off without retrying
already-published packages.

#### Job 4 — deploy marketstall (only if Job 3 succeeded)

```text
python scripts/generate_marketstall.py
→ deploys marketstall.toml to GitHub Pages
```

The generator reads each package's `pyproject.toml`, emits `source = "pypi"` entries with
`~=` version constraints on dependencies.

#### Recovery from partial publish

If Job 3 fails partway through (transient PyPI hiccup, first-time Trusted Publisher
configuration issue, OIDC misconfiguration for a specific package), recovery is **retry at
the same version**:

1. Identify the cause (CI logs, PyPI status, Trusted Publisher config).
2. Fix the underlying issue.
3. Re-run the workflow on the same tag (`gh workflow run publish.yml --ref v0.0.1`) or
   trigger via the GitHub UI.
4. The idempotent skip ensures already-published packages are not re-published; the
   workflow picks up at the failed package and continues.
5. Once all packages are published, Job 4 runs and the marketstall is deployed.

No version bump on partial failure. PyPI versions stay monotonic. Orphaned versions never
arise because the same tag drives all publishes.

If the underlying issue cannot be fixed (e.g. a package was rejected by PyPI for irrecoverable
metadata reasons), bump the version and cut a new release — but this is rare and signals a
real problem with the package, not a release-flow problem.

---

## Implementation tasks

In dependency order:

- [x] **T1** — Patch `@library` decorators to use `importlib.metadata.version()` in all barn packages
- [ ] **T2** — `scripts/bump_version.py` — patches all Tier 1+2 `pyproject.toml` version fields and `~=` constraints
- [ ] **T3** — `scripts/generate_marketstall.py` — CI marketstall generator (PyPI source entries)
- [ ] **T4** — `.github/workflows/publish.yml` — publish + deploy CI workflow
- [ ] **T5** — `haywire share --save` — write to `marketstall.toml` at repo root, aggregating all barn libraries
- [ ] **T6** — `haywire init` scaffold update — register the new project's barn library as a `[[locals]]` entry in the user-global marketplace (and dev-repo libraries too for `--dev`); refuse on name collision; no `marketstall.toml` is created at init time
- [ ] **T7** — Two-tier marketplace runtime — implement global / project marketplace structure (§6), refresh button, conflict resolution (`ignores`/`doubles`), and stale-entry handling. Replaces the deprecated `_fetch_remote_marketplace`-at-startup approach.
- [ ] **T8** — `/haywire-release` skill — guides author through release flow
- [ ] **T9** — `haywire-gen-docs` skill update — `LIBRARY.md` → `NOTES.md`, generate both `README.md` and `OVERVIEW.md` in one pass
- [ ] **T10** — Library Manager "Update available" logic — replace `marketplace_pkg.min_version` comparison with live `fetch_versions()` result; use `marketplace_pkg.min_version` as install-floor check only
- [ ] **T11** — `haybale-marketplace` carve-out — Library Manager extracted from `haybale-studio` (scope TBD, separate spec)
- [ ] **T12** — Library Manager install → `pyproject.toml` sync — after a successful `install_streaming`, write the package into the project's `pyproject.toml` so `uv sync` on a fresh clone restores it
- [ ] **T13** ⚠️ *requires manual verification* — Library Manager dependency guards — use pip `Requires-Dist` introspection (already used for REQUIRED badge) for disable/uninstall guards; keep `@library` deps for install-ordering only. End-to-end guard behaviour (button state, actual block before uninstall) cannot be fully covered by automated tests without significant UI mocking scaffolding.

### T12 detail

**Goal:** make Library Manager installs reproducible. A package installed via the UI must survive `uv sync` on a fresh clone.

**Behaviour per source type:**

| Marketplace entry kind                       | Dependency line written                             | `[tool.uv.sources]` entry written                                                                                                                  |
| -------------------------------------------- | --------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| `[[packages]]` `source = "pypi"`             | `"haybale-foo~=X.Y.Z"` (installed version as floor) | no — PyPI is the default                                                                                                                           |
| `[[packages]]` `source = "git"`              | `"haybale-foo~=X.Y.Z"`                              | yes — git URL + subdirectory parsed from `install_spec`                                                                                            |
| `[[locals]]` path inside project `barn/`     | no — already a workspace member via `barn/*` glob   | no                                                                                                                                                 |
| `[[locals]]` path outside project (dev-repo) | `"haybale-foo~=X.Y.Z"`                              | yes — `{ path = "...", editable = true }`. Absolute path written verbatim; dev-mode projects are non-portable by design (see Q-r decisions in §6). |

**Version floor:** after install, `importlib.metadata.version(pkg.name)` gives the exact installed version. Written as `~=X.Y.Z` (compatible release — allows patch bumps, blocks minor jumps). Re-installing a newer version overwrites the existing constraint.

**`install_spec` parsing for git sources:** the PEP 440 VCS URL format is:

```text
haybale-foo @ git+https://github.com/user/repo.git#subdirectory=barn/haybale-foo
```

Parse: strip leading `haybale-foo @ `, strip `git+` prefix, split on `#subdirectory=` to get URL and subdirectory separately. Write to `[tool.uv.sources]` as:

```toml
haybale-foo = { git = "https://github.com/user/repo.git", subdirectory = "barn/haybale-foo" }
```

**Scope:** only applies when `self.project_dir` is set (i.e. running inside a project, not the dev repo). No-op otherwise.

**Files touched:** `<project_dir>/pyproject.toml` only. No `uv sync` triggered — the next `uv sync` the user runs will see the entry.

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
T12 (install → pyproject.toml sync) — independent
```

---

## Files changed at first migration (pre-release)

| File                                                       | Change                                                         |
| ---------------------------------------------------------- | -------------------------------------------------------------- |
| `barn/*/haybale_*/`__init__.py`                            | Replace `version="..."` with `importlib.metadata.version(...)` |
| `barn/*/pyproject.toml`                                    | `version = "0.0.1"`, all inter-package deps to `~=0.0.1`       |
| `packages/*/pyproject.toml`                                | `version = "0.0.1"`, `haywire-core~=0.0.1`                     |
| `barn/*/haybale_*/LIBRARY.md`                              | Rename to `NOTES.md` (haybale-visiongraph only, currently)     |
| `barn/haybale-visiongraph/haybale_visiongraph/OVERVIEW.md` | Stays as-is; other packages need docs generated                |

---

## Open / deferred

- **`haybale-visiongraph` on PyPI** — deferred until binary wheel complexity is resolved.
- **`haybale-marketplace` split** — separate spec; `haybale-studio` retains the Library Manager until that spec is written.
- **Version constraint in `@library(dependencies=[...])`** — currently name-only; version ranges not yet supported. Separate concern from this spec.
- **Third-party release tooling** — see [third-party-release-tooling.md](./third-party-release-tooling.md). Staked as the next spec once this one is implemented; covers `/haywire-release` repo-type detection, reusable CI templates, and `scripts/generate_marketstall.py` generalisation.
- **Legacy project migration tooling** — this spec ships before any user projects exist, so no migration is needed now. If a future breaking change to the marketplace format requires one, the agreed approach is a dedicated `haywire migrate` CLI command: detect the legacy format, show a diff of proposed changes, apply on confirmation.

