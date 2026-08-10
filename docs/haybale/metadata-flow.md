---
status: draft
doc_template: impl-spec
scope: How library metadata moves — haybale.toml to pyproject to marketstall to a consumer's cache, and which files are read at each moment
see-also:
  - ../reference/files/haybale-toml.md
  - ../reference/files/pyproject-toml.md
  - ../reference/files/marketstall-toml.md
  - ../reference/files/marketplace-toml.md
  - haybale-canon.md
  - ../architecture/sharing/share-pipeline-arch.md
  - ../adr/0025-haybale-toml-is-canon.md
---

# Library metadata — where the data lives

Four files carry a library's metadata between an author and a consumer. This
page is about the *movement* between them: what is copied, what is generated,
and which file is read at each moment.

What each field **means** is defined once, in the page that owns the file it
lives in. Nothing here restates a field definition.

## 1. One canon, four files

| File | Owner | Written by | In the wheel | Reference |
| --- | --- | --- | :-: | --- |
| `haybale.toml` | the author | author + share wizard | ● | [fields](../reference/files/haybale-toml.md) |
| `pyproject.toml` | split | author (`dependencies`) + publish (the rest) | | [fields](../reference/files/pyproject-toml.md) |
| `marketstall.toml` | `haywire share` | publish, in full | | [fields](../reference/files/marketstall-toml.md) |
| `marketplace.toml` | user / project | Add Source, `haywire init`, refresh | | [fields](../reference/files/marketplace-toml.md) |

`haybale.toml` is canon for everything descriptive. It sits inside the package
directory, so it ships in the wheel and is readable wherever the library lands.
`pyproject.toml` keeps `dependencies` as its sole canonical field plus the
packaging machinery no other file can own; the rest of its `[project]` block is
generated. The other two are downstream artifacts.

Data flows one way. `haybale.toml` is the only input to generation, with
`[project] dependencies` the single documented exception (it becomes the row's
`require`).

## 2. The hops

```text
    ┌─────────────────┐
    │  haywire init   │  scaffold: name, id, label, linked_libraries
    └────────┬────────┘
             ▼
    ┌─────────────────┐
    │  haybale.toml   │◀─── edit modal (12 fields; a plain file write)
    └────────┬────────┘
             │  haywire share
             │
    ┌────────┴─────────────────────────────────┐
    │ Phase A — finalize haybale.toml          │  version, origin,
    │   nothing generates until this is done   │  origin_provider
    └────────┬─────────────────────────────────┘
             ▼
    ┌────────┴─────────────────────────────────┐
    │ Phase B — generate from it               │
    └───┬──────────────────────┬───────────────┘
        ▼                      ▼
  pyproject.toml         marketstall.toml ──── push ────▶ a URL
  [project] block        one row per library                  │
                                                              │ Add Source
                                                              ▼
                                              global marketplace.toml
                                                     [[markets]] / [[stalls]]
                                                              │ refresh
                                                              ▼
                                              project marketplace.toml
                                                     [[caches]]
                                                              │ install
                                                              ▼
                                              the wheel's own haybale.toml
```

### 2.1 Scaffold

`haywire init` writes `haybale.toml` with `name`, `id` and `label` from the
author's answers, and **seeds `linked_libraries`** — it knows which libraries it
is wiring together, and this is the only chance to get hot-reload scope right
before the first publish. It writes `pyproject.toml` with `dependencies` and the
packaging machinery, so the package is installable before it is ever published.

### 2.2 Edit

The studio's library overview writes `haybale.toml` and nothing else. No
`uv sync`, no registry reload, no reinstall — the next read is the new value.

`version`, `origin` and `origin_provider` are displayed read-only: the share
wizard observes them rather than accepting them. `name` and `id` are read-only
because a rename breaks saved graphs and every consumer's install spec.

Declared paths accept anything here. A path that does not exist is not an error
yet — it becomes one at publish, when the row would point at nothing, and all
path checking happens in one place ([§2.3](#23-preflight)).

### 2.3 Preflight

The only place folder checks and cross-file agreement are verified. Failures
carry a `fix_id`, and the fix writes the correction **back into `haybale.toml`**
so the repair persists rather than being re-prompted next publish.

| `fix_id` | Fixes |
| --- | --- |
| `sync_pyproject` | Generated `[project]` fields disagree with `haybale.toml` |
| `strip_os` | An `os` value outside `macos` / `linux` / `windows` |
| `clear_examples_path` · `set_examples_path` | A declared `examples_path` that does not exist |
| `clear_tests_path` · `set_tests_path` | The same, for `tests_path` |
| `add_origin` | No git remote to publish from |
| `commit_dirty_tree` · `switch_branch` | Working tree and branch preconditions |

`sync_pyproject` offers no per-field source choice — `haybale.toml` wins. It
renders which fields differ and what they will become, then regenerates. The
value is learning that a pyproject hand-edit is about to be discarded *before*
the push rather than after.

### 2.4 Publish

Two phases, and the boundary between them is the load-bearing invariant:
**nothing generates until `haybale.toml` is final.**

**Phase A — finalize `haybale.toml`.** Every write to it happens here:

1. `version` — the wizard's bump, written into `haybale.toml` first and
   `pyproject.toml` from the same call, so two writers cannot disagree.
2. `origin` and `origin_provider` — read fresh from the git remote and from the
   host check preflight already made. Regenerated every publish rather than
   authored, which is what makes a fork correct for free: cloning a fork gives
   `origin` = the fork.
3. Preflight fixes from [§2.3](#23-preflight) already landed, before this ran.

**Phase B — generate from it.** Everything downstream reads the finalized file
and writes nothing back:

1. Regenerate `[project]` and `[project.urls]`, comment-preserving, removing a
   key rather than writing an empty value.
2. Build one marketstall row per library: copy the descriptive fields, generate
   `install_spec` / `source`, project `require` out of `[project] dependencies`.
3. Commit, tag `v<version>`, push.

`install_spec` is tag-pinned **here and only here**. A standalone
`write_marketstall()` call floats to the current branch — see
[the publishing traps](../reference/files/marketstall-toml.md#tag-pinning).

### 2.5 Subscribe and refresh

A consumer pastes the marketstall's URL into **Add Source**, which writes a
`[[markets]]` or `[[stalls]]` entry to the global marketplace. Refresh — the
only operation that touches the network — fetches every subscription, resolves
one level deep, applies the conflict filters, and writes the result into the
project's `[[caches]]`.

Opening a library's detail view does no network call: it reads the local cache.
The full pipeline is in
[haybale-marketplace-arch](marketplace/haybale-marketplace-arch.md).

### 2.6 Install

The consumer reads `os` from the row to gate installation *before* installing,
then hands `install_spec` verbatim to `uv pip install`. After install, the
library's own `haybale.toml` arrives in the wheel and becomes the runtime
source — the same values the row advertised, now local.

## 3. Copied, generated, cache-owned

A marketstall row is mostly a verbatim `haybale.toml`:

- **copied** — 18 fields pass through untouched.
- **generated** — 3 fields a library cannot state about itself: `install_spec`,
  `source`, and `require`.
- **cache-owned** — `via`, `last_seen` and `stale`, written by a consumer's
  refresh and never by a publisher.

Field by field, with what produces each:
[marketstall.toml § Field inheritance](../reference/files/marketstall-toml.md#field-inheritance).

## 4. Two readers, and why they differ

`haybale.toml` is read at two distinct moments, and conflating them is the
mistake this design exists to avoid.

| | The loader | Everything else |
| --- | --- | --- |
| When | Decoration time, once per import | At the point of use, every render |
| Takes | `id`, `label`, `linked_libraries`, `on_reload` | Whatever it is about to display |
| Into | `LibraryIdentity` | Nothing — read and used |
| A bad file | Raises; that library alone fails to load | Renders blank |

**Rendering never goes through `LibraryIdentity`.** The identity is built once
at import, so a value served through it is only as fresh as the last reload —
the same staleness the installed distribution's `METADATA` had, with a shorter
cache. Reading the file at the point of use is what makes "write it, see it"
true.

The identity keeps exactly what cannot be re-read on demand:
`linked_libraries` is snapshotted into the hot-reload module graph at
registration; `on_reload` is consumed *after* a library has been evicted, when
its files may already be gone; `label` is mentioned by ~20 framework call sites
that cannot each afford a file read.

## 5. Where a library's own pages resolve from

Docs and Examples links need three inputs: `origin`, a git ref, and a declared
path.

| The library | Resolved from |
| --- | --- |
| Has a marketstall row | the row (`origin` + the ref in `install_spec`) |
| Installed, no row — heap, barn folder, editable | its own `haybale.toml` |
| Project root on disk | the local directory, opened directly |

The second case is why `origin` lives in `haybale.toml` rather than only in the
row: a library installed as a heap has no row at all, and would otherwise render
no links despite declaring the paths.

The third case is a deliberate preference — examples are meant to be run, not
read about.

Host resolution consults `origin_provider` first, then built-ins and
`~/.haywire/config.toml`. Anything unresolvable yields **no link** rather than a
guessed one: a wrong URL is worse than none.

## 6. What each file is worth losing

| Deleted | Consequence |
| --- | --- |
| A project's `[[caches]]` | None — the next refresh rebuilds it |
| `~/.haywire/cache/` | None — forces a refetch |
| The global `marketplace.toml` | The user's subscriptions; recreated with the official feed |
| A library's `haybale.toml` | The library cannot load — it is read from disk at runtime |

No installed package is lost by deleting any marketplace file: installation is
pip state, not marketplace state. The recovery ladder is in
[haybale-marketplace-arch](marketplace/haybale-marketplace-arch.md).
