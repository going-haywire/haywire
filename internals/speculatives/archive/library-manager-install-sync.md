---
status: implemented
scope: After a successful Library Manager install, write the package into the project's `pyproject.toml` so `uv sync` on a fresh clone restores it.
see-also:
  - ./marketstall-distribution.md
  - ../../docs/reference/publish_releases.md
---

# Library Manager install → `pyproject.toml` sync

## Goal

Make Library Manager installs reproducible. A package installed via the UI must survive `uv sync` on a fresh clone of the project.

Today, the Library Manager runs `uv pip install ...` directly. The package lands in the venv, the entry-point shows up, and the Library System rescan picks it up — but the project's `pyproject.toml` doesn't reflect what was installed. A teammate who clones the project and runs `uv sync` gets a different set of installed haybales than the original author.

This spec describes the small piece of write-back logic that closes that loop.

## Behaviour per source type

When the user installs from the Library Browser, the runtime inspects the source kind (from the `[[haybales]]` entry's `source` field, the `[[stalls]]` it came from, or the `[[heaps]]` direct reference) and writes the appropriate dependency declaration:

| Source kind                                                | `[project] dependencies` entry written              | `[tool.uv.sources]` entry written                                                                                       |
| ---------------------------------------------------------- | --------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| `[[haybales]]` with `source = "pypi"`                      | `"haybale-foo~=X.Y.Z"` (installed version as floor) | no — PyPI is the default                                                                                                |
| `[[haybales]]` with `source = "git"`                       | `"haybale-foo~=X.Y.Z"`                              | yes — git URL + subdirectory parsed from `install_spec`                                                                 |
| `[[heaps]]` entry pointing inside the project's `barn/`    | no — already a workspace member via `barn/*` glob   | no                                                                                                                      |
| `[[heaps]]` entry pointing outside the project (dev-repo)  | `"haybale-foo~=X.Y.Z"`                              | yes — `{ path = "...", editable = true }`. Absolute path written verbatim; dev-mode projects are non-portable by design |

## Version floor

After install, `importlib.metadata.version(pkg.name)` gives the exact installed version. Written as `~=X.Y.Z` (compatible release — allows patch bumps, blocks minor jumps). Re-installing a newer version overwrites the existing constraint with the new floor.

## `install_spec` parsing for git sources

The PEP 440 VCS URL format is:

```text
haybale-foo @ git+https://github.com/user/repo.git#subdirectory=barn/haybale-foo
```

Parse: strip the leading `haybale-foo @` (including the trailing space), strip the `git+` prefix, split on `#subdirectory=` to get URL and subdirectory separately. Write to `[tool.uv.sources]` as:

```toml
haybale-foo = { git = "https://github.com/user/repo.git", subdirectory = "barn/haybale-foo" }
```

## Scope

Only applies when `self.project_dir` is set on the `LibraryManager` (i.e. running inside a project, not the dev repo). No-op otherwise.

## Files touched

`<project_dir>/pyproject.toml` only. No `uv sync` triggered — the next `uv sync` the user runs will see the entry.

## Uninstall

The uninstall flow performs the inverse: remove the corresponding entry from `[project] dependencies` and from `[tool.uv.sources]` (if present). Workspace members (entries with no dependency line written in the first place) are not touched.

## Open questions

- **Multi-write atomicity**: should the install pipeline write to `pyproject.toml` before or after running `uv pip install`? Writing first risks an orphaned entry if install fails; writing after risks losing the entry if the runtime crashes between install and write. Current preference: write after install succeeds, accept the rare crash-window risk in exchange for never leaving stale entries.
- **Manual `pyproject.toml` edits**: the runtime treats the file as authoritative on read but overwrites on install. Authors who hand-edit may have their edits clobbered. A future flag could open a diff/confirm dialog before overwriting non-matching entries — out of scope for first ship.
