---
status: draft
doc_template: reference
scope: haybale.toml — the authoring surface for a library's metadata. Every field, who writes it, and what it becomes downstream.
see-also:
  - pyproject-toml.md
  - marketstall-toml.md
  - ../../haybale/metadata-flow.md
  - ../../haybale/haybale-canon.md
  - ../../adr/0025-haybale-toml-is-canon.md
---

# `haybale.toml`

**Location:** inside the Python package, beside `__init__.py` —
`barn/haybale-core/haybale_core/haybale.toml`.

**Owner:** the library author, plus the share wizard for three fields.

`haybale.toml` is canon for everything descriptive about a library. It sits
inside the package directory, so it ships in the wheel and is readable from disk
wherever the library lands. The runtime reads it at the point of use, which is
what makes an edit take effect on the next read — no `uv sync`, no reinstall, no
registry reload.

`pyproject.toml` cannot hold this: it is not installed. The installed
distribution's `METADATA` cannot either — it is written once at install time and
does not change when the source does.

## The file

```toml
# Library metadata. Canon for everything descriptive about this haybale;
# ships in the wheel beside __init__.py and is read from disk at runtime.
# Edited in the studio's library overview — no reinstall, no reload.

# ── identity ────────────────────────────────────────────────────────────────
# Immutable after scaffold. `name` is the library's sole identifier: the pip
# distribution name every consumer's install_spec holds, AND the prefix of
# every component's registry key (`haybale-core:node:Add`) — so changing it
# orphans saved graphs. Not passed to @library(...): this file is the only
# source.
name = "haybale-core"

# ── written by the share wizard, never by the edit modal ────────────────────
# PEP 440 — no leading "v". The git tag is derived: tag_for(version) → v0.0.40.
version = "0.0.40"
# The repository this library publishes from. Regenerated from the git remote
# on every publish, so a fork corrects itself on its first share. Every
# declared path below resolves against this.
origin = "https://github.com/going-haywire/haywire"
# Which kind of forge `origin` is: "github" | "gitlab". Published rather than
# resolved locally — the hostname→provider mapping otherwise lives only in the
# publisher's ~/.haywire/config.toml, so a self-hosted forge would render links
# on exactly one machine.
origin_provider = "github"

# ── display ─────────────────────────────────────────────────────────────────
label = "Core"
description = "Fundamental components for haywire graphs"
tags = ["haywire", "node-editor", "core"]

# ── behaviour ───────────────────────────────────────────────────────────────
# Platforms this library runs on. Empty or absent = every platform. The only
# field that blocks installation.
os = ["macos", "linux"]
# How far a user has to go when hot-reload alone cannot pick this library up:
# "none" (default) | "refresh" (reload the browser tab) | "restart" (restart
# the studio). Applies to install, update and uninstall alike.
on_reload = "restart"

# Sibling haybales whose classes this library subscribes to, as MODULE names
# (haybale_studio), NOT distribution names (haybale-studio). A hyphen produces
# a hot-reload scope matching no module, so it is rejected at read time.
# Distinct from [project] dependencies in pyproject.toml, which are pip
# requirements. The share wizard's drift detector maintains this list.
linked_libraries = ["haybale_studio"]

# ── declared paths ──────────────────────────────────────────────────────────
# Relative to the PROJECT root — the directory holding .haywire/, which
# preflight requires to be the git root. Project-relative rather than
# library-relative because an example graph wires several libraries together
# and cannot live inside any one of them. A trailing slash marks a directory.
examples_path = "examples/"
tests_path = "tests/"

# One supplementary human-readable page: a bare filename in THIS directory,
# no slashes, no "../". Not the library's front page — label, description,
# tags and authors already carry that.
notes = "NOTES.md"

# ── absolute URLs, used verbatim ────────────────────────────────────────────
homepage_url = "https://github.com/going-haywire/haywire"
documentation_url = "https://going-haywire.github.io/haywire/"
issues_url = "https://github.com/going-haywire/haywire/issues"

# ── tables come last ────────────────────────────────────────────────────────
# TOML parses every bare key after a table header INTO that table, so all
# scalar fields must precede [[authors]] and [deprecated].

# Repeatable. `url` is optional and does not survive into pyproject — PEP 621
# authors carry {name, email} and have no URL slot.
[[authors]]
name = "maybites"
url = "https://maybites.ch"

[[authors]]
name = "cansik"

# Omitted unless the library is being retired. Hand-edited — the edit modal has
# no field for it. Informational only: a deprecated library still installs,
# still enables, still updates.
[deprecated]
since = "0.0.41"                # required — deprecation is a historical fact
reason = "Superseded by haybale-vision, which handles both OAK-D revisions."
successor = "haybale-vision"    # optional
```

The smallest valid file is three lines — `name`, `label`, and whatever the
library actually needs:

```toml
name = "haybale-minimal"
label = "Minimal"
description = "One node, nothing else"
```

`name` is the only field whose absence is fatal: without it the library cannot
be named in a registry, and `@library` raises `HaybaleTomlError` at decoration
time.

## The fields

Every field this file may declare, and which file each one reaches.

- **haybale** — read from *this* file by the studio, while the library is
  installed.
- **marketstall** — copied into the published
  [`marketstall.toml`](marketstall-toml.md) row, so a consumer sees it *before*
  installing.
- **pyproject** — projected into the generated `[project]` block of
  [`pyproject.toml`](pyproject-toml.md) at publish, naming the key it becomes.

| Field                          | Type      | Required | haybale | marketstall | pyproject                  | Meaning                                                                                           |
| ------------------------------ | --------- | -------- |:-------:|:-----------:|:--------------------------:| ------------------------------------------------------------------------------------------------- |
| `name`                         | string    | yes      | ●       | ●           | `name`                     | Pip distribution name — the library's sole identifier, and the prefix of every component's registry key (`haybale-core:node:Add`). Canon here; pyproject carries the generated copy. Immutable |
| `version`                      | string    | yes      | ●       | ●           | `version`                  | PEP 440, no `v`. Canon here; pyproject carries the generated copy. The git tag is derived from it |
| `label`                        | string    | yes      | ●       | ●           |                            | Human display name                                                                                |
| `description`                  | string    | no       | ●       | ●           | `description`              | One line                                                                                          |
| `tags`                         | list[str] | no       | ●       | ●           | `keywords`                 | Filter tags in the library browser                                                                |
| `os`                           | list[str] | no       | ●       | ●           |                            | `macos`/`linux`/`windows`. Empty = everywhere. The only field that blocks installation            |
| `on_reload`                    | string    | no       | ●       | ●           |                            | `none` (default) / `refresh` / `restart`                                                          |
| `linked_libraries`             | list[str] | no       | ●       | ●           |                            | **Module** names. Hot-reload scope, and enable/uninstall gating                                   |
| `origin`                       | string    | no       | ●       | ●           | `urls.Source`              | The repository this publishes from. Every declared path resolves against it                       |
| `origin_provider`              | string    | no       | ●       | ●           |                            | `github` / `gitlab`. Lets a consumer build URLs with no local host config                         |
| `notes`                        | string    | no       | ●       | ●           |                            | A bare filename in this directory — one supplementary page                                        |
| `examples_path`                | string    | no       | ●       | ●           |                            | Project-relative path. Trailing slash marks a directory                                           |
| `tests_path`                   | string    | no       | ●       | ●           |                            | Project-relative path. Not surfaced in the UI                                                     |
| `homepage_url`                 | string    | no       | ●       | ●           | `urls.Homepage`            | Absolute URL, verbatim                                                                            |
| `documentation_url`            | string    | no       | ●       | ●           | `urls.Documentation`       | Absolute URL, verbatim                                                                            |
| `issues_url`                   | string    | no       | ●       | ●           | `urls.Issues`              | Absolute URL, verbatim                                                                            |
| `[[authors]]`                  | table[]   | no       | ●       | ●           | `authors`                  | Repeatable `name` + optional `url`, copied verbatim to the marketstall row; no pyproject slot     |
| `[deprecated]`                 | table     | no       | ●       | ●           | `classifiers`              | `since` (required), `reason`, optional `successor`. Informs; never blocks                         |
| **fields in marketstall.toml** | ---       | ----     | ---     | ---         | ---                        | ---                                                                                               |
| install_spec                   | string    | yes      |         | ●           |                            | pip install string                                                                                |
| source                         | string    | no       |         | ●           |                            | generated                                                                                         |
| require                        | string    | yes      |         | ●           | `dependency[haywire-core]` | projected from pyproject                                                                          |

pip requirements (projected into require) and the entry point live in [`pyproject.toml`](pyproject-toml.md).

## Who writes what

| Written by                                     | Fields                                                                                                                                                                          |
| ---------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `haywire init` (scaffold)                      | `name`, `version`, `label`, `description`, `tags`, `linked_libraries` (empty); every other field commented out as a template                                                    |
| The author, by hand or in the edit modal       | `label`, `description`, `tags`, `os`, `on_reload`, `linked_libraries`, `homepage_url`, `documentation_url`, `issues_url`, `examples_path`, `tests_path`, `notes`, `[[authors]]` |
| The author, by hand only                       | `[deprecated]`                                                                                                                                                                  |
| `scripts/bump_version.py` and the share wizard | `version` — canon here; the generated copy is synced into `pyproject.toml`                                                                                                      |
| The share wizard                               | `origin`, `origin_provider`, and drift-detected `linked_libraries` additions                                                                                                    |
| Nothing — immutable                            | `name`                                                                                                                                                                          |

The edit modal accepts exactly the thirteen author-editable fields above
(`EDITABLE_FIELDS`); passing any other raises rather than silently dropping the
write. Writing an empty value removes the key instead of writing `""`, so absent
and empty stay the same thing and a UI-edited file is indistinguishable from a
hand-written one.

`[[authors]]` rows are edited positionally: the modal has no per-author identity
to diff against, so save always writes exactly the rows currently shown,
top-to-bottom. A row with a name but no URL writes `url`-less; a row with no
name is dropped from the save (matching the read side's own rule that a
nameless entry is not an author) unless it carries a URL, in which case the
save is blocked rather than silently discarding the typed URL.

There is no supported rename path in the studio today: `name` is read-only
everywhere until the rename-wizard lands (the CLI `haywire rename` tool
rewrites it out-of-band, including saved graphs' registry-key prefixes).

For what happens to each field *after* it is written — how it is carried into a
published marketstall, and which fields are generated there rather than copied
— see [marketstall.toml § Field inheritance](marketstall-toml.md#field-inheritance).

## Field notes

Only where a table cell cannot carry the whole answer.

### `version`

PEP 440, no `v` prefix. The `v` belongs to the git tag, which is derived —
`tag_for("0.0.40")` → `v0.0.40`, one definition for the commit step, the tag
step, and `install_spec`.

haybale.toml's `version` is canon and is what `LibraryIdentity.version` loads at decoration
time; `pyproject.toml`'s `[project] version` is the generated copy, written because pip reads
that file and cannot read this one.

`scripts/bump_version.py` writes both files together for the monorepo's own lockstep release;
the share wizard's `write_barn_versions()` does the same for a per-library publish. Required:
`read_haybale_toml()` raises if the key is absent, the same way it does for a
missing `name`.

Storing the tag form here instead would be invalid in `[project] version`,
and `packaging.Version` normalises a leading `v` away — so mixed forms compare
correctly right up until something does a string equality.

The bump machinery owns this field, so it is displayed read-only in the edit
modal: a version the modal could edit would be a version no tag corresponds
to, and `write_haybale_fields()` rejects it outright (`EDITABLE_FIELDS`
excludes it) rather than silently dropping the write.

### `linked_libraries`

**Module** names (`haybale_studio`), not distribution names (`haybale-studio`).
The hot-reload tracker builds a scope by appending `"."` to each entry verbatim,
so a hyphen yields a prefix matching no module and silently disables reload
tracking for that dependency. Rejected at read time rather than accepted and
ignored.

The field is load-bearing twice:

- **Hot-reload scope**, read at import into `LibraryIdentity` and snapshotted
  into the module graph.
- **Marketplace gating**, read live from the file: "3 libraries depend on this"
  on uninstall, and the missing-dependency refusal on enable. Pre-install
  gating reads the [marketstall row](marketstall-toml.md) instead, since the
  library is not on disk yet.

Not to be confused with `[project] dependencies`, which are
[pip requirements](pyproject-toml.md).

### `os`

The only field that blocks installation. Values are `macos`, `linux`, `windows`;
anything else is rejected at `haywire share` time. Empty or absent means every
platform.

### `examples_path` and `tests_path`

Project-relative — from the directory holding `.haywire/`, which preflight
requires to be the git root.

In a wheel installed by a consumer these point into the *publisher's* project
and mean nothing locally. They are publisher-side coordinates, resolved against
`origin` at `install_spec`'s ref, never read as local paths — except when the
project root is on disk (a heap or barn library), where the local directory is
opened directly, since examples are meant to be run.

No absolute URL is stored: the host and ref come from `origin` and
`install_spec`, so a baked URL could contradict them.

### `notes`

A bare filename inside the package directory — same directory as `haybale.toml`
itself, so there is no "relative to what?" question. Ships in the wheel, so it
means the same thing wherever the library lands.

A declared file that does not exist fails preflight, with a fix that scans the
package root for `*.md` and offers what it finds.

### `[deprecated]`

`since` is required: deprecation is a historical fact, not a current state.
Without it, a user on 0.0.30 cannot be told whether their version predates the
notice.

It informs and never gates — a deprecated library still installs, enables and
updates. `os` remains the only field that blocks installation.

The block travels into the [marketstall row](marketstall-toml.md), so a consumer
can read the notice before installing rather than only from PyPI's
`Development Status :: 7 - Inactive` classifier, which carries neither `reason`
nor `successor`.

!!! note "Not yet rendered"

    Nothing in the studio displays the notice today — no browser badge, no
    overview banner, no `successor` action. The data reaches the consumer; the
    UI is unbuilt. Tracked in
    `internals/handoff/deprecated-libraries-have-no-ui-surface.md`.

Treat a published block as immutable: an author who changes their mind bumps a
version and removes the block rather than rewriting what consumers already
fetched.

Distinct from [Compatibility Warnings](../../haybale/haybale-canon.md#7-compatibility-warnings),
which are per-component, append-only, and checked against saved graphs.

### `origin_provider`

The vocabulary is closed (`"github"`, `"gitlab"`). A consumer resolves in this
order:

1. `origin_provider` when present — the publisher's own answer.
2. `resolve_host(hostname)` — built-ins, then `~/.haywire/config.toml`.
3. Nothing — no link rendered. Never a guess: a wrong URL is worse than none.

## Not in this file

|                                     | Lives in                                                                                  |
| ----------------------------------- | ----------------------------------------------------------------------------------------- |
| `file_watcher` kwarg                | `@library(...)` — see [haybale-canon](../../haybale/haybale-canon.md#4-the-library-class) |
| Pip requirements (`dependencies`)   | [`pyproject.toml`](pyproject-toml.md)                                                     |
| The entry point and build config    | [`pyproject.toml`](pyproject-toml.md)                                                     |
| `install_spec`, `require`, `source` | [`marketstall.toml`](marketstall-toml.md) — generated at publish                          |

## Reading it in code

| Reader                                      | Use                                                     | Behaviour on a bad file                                  |
| ------------------------------------------- | ------------------------------------------------------- | -------------------------------------------------------- |
| `read_haybale_toml(package_dir)`            | Decoration time; returns `LibraryIdentity` kwargs       | Raises `HaybaleTomlError` — fatal for that library alone |
| `read_haybale_toml_lenient(package_dir)`    | Report-only callers                                     | Returns `{}`                                             |
| `read_haybale(package_dir)`                 | Rendering; returns a `Haybale`                          | Never raises — returns an empty row; cached on mtime     |
| `read_raw(package_dir)`                     | The publisher, which needs keys the runtime never loads | Returns `{}`                                             |
| `write_haybale_fields(package_dir, fields)` | The edit modal                                          | Raises on a non-editable field                           |



All five live in `haywire.core.library.haybale_toml`.

## The distribution name

`name` is canon. Nothing else stores the distribution name as a fact of its own:

- `pyproject.toml`'s `[project] name` is generated from it (`PROJECT_FIELDS`),
  and `pyproject_drift()` reports the copy against canon, never the reverse.
- The installed distribution's entry-point metadata (`ep.dist.name`) is that
  generated copy, observed at runtime. `LibraryRegistry` caches it per library
  id for the install/uninstall paths, which need the string pip accepts.
- `LibraryInfo` has **no** distribution-name field. Readers use `info.row.name`.

Reading the entry point in preference to canon would also lose the folder
installs, which have no entry point at all: `builtin` ships inside
`haywire-core` and declares `name = "haywire-core"` here, which is the only
place that name exists for it.

The `haybale-` prefix is a convention, not a rule — `builtin` disproves it — so
a distribution name is displayed as declared, never derived or reconstructed.

Nothing falls back to the identity when a row reads empty, because there is no
state in which that helps:

- **Corrupt at load** — `@library` reads this file strictly, so the library
  never loads and no `LibraryInfo` is built for it. Discovery logs the failure
  and moves on.
- **Corrupted while running** — `BaseLibrary.update_identity_from_toml()` keeps
  the previous values ("the author is mid-keystroke and a half-written file is
  expected"), and the next render re-reads the file.

An empty row therefore means the sub-render window between a write and the next
read, which heals itself. A render that reaches for `LibraryIdentity` to cover
it is a stale read buying nothing.
