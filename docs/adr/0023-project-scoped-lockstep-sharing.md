# Project-scoped lockstep sharing

The share wizard publishes a **project**, not a library: it versions every
`barn/*` library in lockstep, tags the repo `v<version>`, and is entered from
`LibraryBrowserEditor`'s burger menu rather than from a button on the library
being published. We designed the library-scoped alternative first and switched,
because the artifact being published is repo-shaped — a `haywire init` project
is a uv workspace root (`members = ["barn/*"]`) with a single root
`marketstall.toml` feed and one git remote, and consumers install by git URL
from one clone. Library scoping kept forcing "…but it's actually repo-wide"
compromises: the marketstall has to aggregate all of `barn/*` or it silently
deletes sibling entries, `_update_repo_readmes` already rewrites every
`barn/*/README.md`, `uv.lock` lives at the root, and per-library versions make a
repo-level tag non-monotonic and untruthful.

## Considered options

- **Library-scoped, per-library tags** (`haybale-x/v0.3.1`). Honest versions for
  libraries that didn't change, and the Share button sits on the thing it
  publishes. Rejected: the marketstall rebuild, README rewrites, and lockfile
  refresh are repo-wide regardless, so the "unit" was a fiction that had to be
  explained away at every step, including a preview panel whose job was to
  justify why a sibling library's README was in the user's commit.
- **Project-scoped, per-library versions preserved** (no lockstep). Honest
  versions plus one publish action. Rejected: needs a per-library version table
  in the stepper and reintroduces per-library tags, for a project shape where
  the common case is a single library.

## Consequences

- Libraries that did not change still get a version bump. This is the standard
  monorepo lockstep trade and the same one `/haywire-release` already makes for
  this repo.
- Two front doors now perform lockstep publishing. They do not conflict:
  `/haywire-release` ships Tier 1+2 packages to PyPI via CI tags for haywire
  maintainers and owns the `vX.Y.Z` tag on this repo; the share wizard ships one
  project repo's barn feed via git URL for project authors. Different artifact,
  different audience.
- The wizard must handle a barn whose versions already disagree (hand-added
  library, `--dev` mode). It shows the disagreement and requires an explicit
  target version rather than resolving silently — `bump_version`'s existing
  "first barn library found" heuristic would downgrade a higher-versioned
  sibling.

Full design: See `internals/superpowers/2026-07-30-share-wizard.md` for detailed implementation notes.
