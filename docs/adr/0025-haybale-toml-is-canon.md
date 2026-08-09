# `haybale.toml` is canon for library metadata

Every piece of descriptive library metadata is authored in **one** file, which
sits inside the Python package and ships in the wheel:

```
barn/haybale-core/haybale_core/haybale.toml
```

`pyproject.toml` keeps exactly one canonical field of its own —
`[project] dependencies` — plus the packaging machinery no other file can own
(`build-system`, `entry-points`, `[tool.hatch]`). Everything else under
`[project]` is *generated* from `haybale.toml` during the share process.

`@library(...)` keeps only what must be known before any file is read: `id`,
`version`, `file_watcher`.

## Why the previous split could not work

[ADR 0024](0024-library-metadata-single-source.md) put the PEP 621 fields in
`[project]` and had the decorator read them back through `importlib.metadata`.
That removed the duplication, but inherited a defect it could not fix:

**Distribution metadata is written once, at install time.**
`site-packages/<dist>.dist-info/METADATA` does not change when
`pyproject.toml` changes — not even for an editable install. Verified 2026-08-08
by editing a pyproject in place and re-reading in a fresh interpreter: version
and description both reported pre-edit values until `pip install -e` was re-run.

So every metadata edit required `uv sync` plus a registry reload before it
became visible. That is what forced editing out of a modal and into the Share
wizard, and why the library overview's Edit dialog was deleted. The cost was
paid to work around the *read path*, not to solve the duplication.

`[tool.haywire]` cannot substitute: it does not survive into an installed wheel
either, which is why ADR 0024 rejected it. A file inside the package directory
does survive — verified by building `haybale-testing` and unzipping the wheel —
and can be read from disk at runtime.

## What this buys

- **An edit is a file write.** No `uv sync`, no module eviction, no restart
  offer. The runtime reads the file at the point of use, so the next render
  shows the change. The overview's Edit dialog is back.
- **Nothing writes the decorator.** A decorator edit is a *source* edit, and a
  source edit needs a reload — the cost this exists to remove. `decorator_io`'s
  regex writers lose their callers, and with them a bug class: two separate
  writers silently no-opped against `ruff format`'s double quotes because their
  patterns matched single quotes only.
- **A library can locate itself.** `origin` + `origin_provider` +
  `tag_for(version)` resolve its own paths without a marketstall row, so Docs
  and Examples links work for heap and editable installs, which previously
  rendered nothing at all.
- **Self-hosted forges work for consumers.** The hostname→provider mapping
  travels with the library instead of living only in the publisher's
  `~/.haywire/config.toml`.

## The fields

| where | what |
| --- | --- |
| `@library(...)` | `id`, `version`, `file_watcher` |
| `haybale.toml` | `name`, `id`, `label`, `description`, `tags`, `os`, `on_reload`, `linked_libraries`, `notes`, `examples_path`, `tests_path`, the URL fields, `[[authors]]`, `[deprecated]` — plus `version`, `origin`, `origin_provider`, written by the share wizard |
| `pyproject.toml` | `dependencies` (canon); everything else in `[project]` is generated |

`version` appears in two places deliberately. The release machinery owns it, and
it is the one field that flows *into* `haybale.toml` from the bump rather than
out of it.

## What stays on `LibraryIdentity`

Seven fields, and only what cannot do a file read at the point of use:

- `id`, `folder_path`, `module_name`, `file_watcher` — from the decorator
- `label` — logged and rendered from inside the registry, which cannot do a
  file read per log line
- `linked_libraries` — consumed during module registration, inside the import
  machinery
- `on_reload` — read by the post-install prompt *after* a library is evicted,
  when its files may already be gone

Everything else is read from `haybale.toml` where it is displayed. Routing it
through the identity would reintroduce import-time staleness: the identity is
built once, so a value read through it is only as fresh as the last reload.

## Consequences

- **A malformed or missing `haybale.toml` fails that library at import.**
  `LibraryRegistry` already wraps each load, so the studio starts, the broken
  library is visibly absent, and the error names the file. Defaulting to empty
  instead would yield `linked_libraries=[]` and a subscriber holding a stale
  class reference after a reload — the exact failure the field prevents,
  surfacing later and somewhere unrelated.
- **Preflight enforces the pyproject projection** rather than publish silently
  overwriting it. There is no per-field choice: `haybale.toml` wins. The check
  exists to say the hand-edit is about to be discarded *before* the point of no
  return.
- **`docs_path` is deleted.** It held the module directory, not docs, and both
  consumers appended to it. It is derivable from `install_spec`, so a stored
  copy could only disagree with the spec about which directory was published.
  `notes` takes its slot as one human-readable page.
- **Breaking, with no migration window.** No `distmeta` fallback for old wheels.
- **`name` and `id` are immutable** until a rename wizard exists — they key
  every saved graph's node references and every consumer's `install_spec`.

## Alternatives considered

**Keep ADR 0024 and accept the reload.** Rejected: the reload is the cost, not a
side effect. Every consequence 0024 accepted — editing moved into the wizard,
the Edit dialog deleted, a restart offer after each save — followed from it.

**`[tool.haywire]` in pyproject.** Rejected by 0024 and still correct: it does
not reach an installed wheel, so the fields would be publish-time only.

**A file outside the package directory.** Rejected: only what is inside the
package ships in the wheel, which is the entire mechanism.

## References

- Design: `internals/plans/2026-08-09-haybale-toml-field-canon.md`
- Implementation plan: `internals/plans/2026-08-09-haybale-toml-implementation.md`
- Supersedes: [ADR 0024](0024-library-metadata-single-source.md)
