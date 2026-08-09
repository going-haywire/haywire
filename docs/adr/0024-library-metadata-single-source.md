# Library metadata has one source per field

> **⚠️ Superseded by [ADR 0025](0025-haybale-toml-is-canon.md) (2026-08-09).**
> The two-place split below no longer describes the code. Descriptive metadata
> now lives in `haybale.toml`, inside the package directory; `pyproject.toml`
> keeps `dependencies` and is otherwise generated from it.
>
> What this ADR got right and 0025 keeps: the duplication had to go, and
> `[tool.haywire]` cannot carry these fields because it does not reach an
> installed wheel. What it could not fix: `[project]` does not reach one either
> — only the *distribution metadata* built from it does, and that is written
> once at install time. Reading it back therefore made every edit require
> `uv sync` plus a reload, which is what pushed editing out of a modal and into
> the Share wizard. The prose below is retained as the historical record.


Every piece of library metadata is authored in exactly one place, and there are
two places:

- **`[project]` / `[project.urls]`** — `version`, `description`, `authors`,
  `keywords`, and every URL. Standard PEP 621, which hatchling copies into wheel
  `METADATA`, so `importlib.metadata` reads them back from an installed library.
  No longer `@library(...)` kwargs.
- **`@library(...)`** — `id`, `label`, `linked_libraries`, `on_reload`,
  `file_watcher`, `os`, `examples_path`, `tests_path`. Everything
  Haywire-specific.

The rule an author needs: **standard packaging → `[project]`, everything
Haywire → the decorator.**

`[tool.haywire]` is not used. An earlier draft put the Haywire-specific fields
there and split them from the decorator by whether each was needed at runtime or
only at publish. That split rested on a mechanical fact — **`[tool.haywire]`
does not survive into an installed wheel** (verified: no barn library
force-includes `pyproject.toml`, and `dist.files` for an installed haybale
contains none) — but the split it produced was arbitrary from an author's point
of view, and it left `os`, `examples_path`, and `tests_path` unreadable at
runtime for no gain. Putting every Haywire field in the decorator makes them all
survive the wheel and reduces the rule to one line.

`os` is the one field this trades something away on: it gates *installation*, so
it must be readable before the library is importable. It is, from the marketstall
row, which is built at publish time from source where the decorator is readable
either way. What is lost is reading `os` from an uninstalled checkout without
parsing Python — acceptable, since the publish path already uses an AST reader,
and it deletes `_apply_os_to_pyproject`'s careful `edit_toml` handling in favour
of a decorator list write.

Before this, `version`, `description`, `author`, and `tags` were authored in
both `pyproject.toml` and the `@library(...)` decorator, and the marketstall
generator read the pyproject copy while the studio's library overview read the
decorator copy. They had already drifted in-tree: installed `haybale-core`
metadata says "Haywire's core library with types, nodes, widgets, and
renderers"; its decorator said "Fundamental components for hayire graphs" —
a different sentence carrying a typo, and the decorator copy is the one users
saw once the library was installed.

## Considered options

- **Move everything to `[tool.haywire]`, decorator holds only `id`.** The
  tidiest split on paper, and the one this design carried for two rounds. Ruled
  out by measurement: no barn library force-includes `pyproject.toml`, so
  `dist.files` for an installed haybale contains no pyproject at all. `os` reads
  from pyproject today only because that path runs for *heaps* (editable
  project libraries) and silently returns `[]` for installed wheels, falling
  back to the marketstall row. Moving `label`/`linked_libraries`/`on_reload`
  there would have worked in an author's dev tree and broken hot-reload scope
  tracking and the post-install prompt for every consumer.
- **Force-include `pyproject.toml` into each wheel**, making `[tool.haywire]`
  runtime-readable and collapsing the split further. Rejected: it puts build
  config on every third-party haybale author, fails silently when wrong, and a
  broken `force-include` already shipped once in v0.0.26
  (`.insights/project_farmhand_docs_bake.md`). The decorator gives the same
  guarantee with no build step.
- **Split the Haywire fields across `[tool.haywire]` and the decorator** by
  whether each is read at runtime or only at publish — `label`,
  `linked_libraries`, `on_reload` in code; `os`, `examples_path`, `tests_path`
  in TOML. Correct on the mechanics, and carried for a round. Rejected because
  the line is invisible to an author: two files, and which field goes where
  depends on framework internals they have no reason to know. Putting all of
  them in the decorator costs only `os`'s readability from an uninstalled
  checkout and reduces the rule to one sentence.
- **Keep the duplication, add a drift check to `haywire share`.** Rejected: it
  detects the problem instead of removing it, and leaves the install-state split
  — the same library showing a different description depending on whether it is
  installed — fully intact.
- **Separate classes with a name-parity test**, or a `Protocol` the renderer
  types against, instead of a shared base. Rejected once the three apparent
  divergences (`version`, `linked_libraries`, `on_reload`) turned out to be
  incidental: with those reconciled the two classes share fifteen fields, and a
  base makes the invariant structural instead of something a test has to
  re-check.

## Consequences

- `@library(...)` loses seven kwargs: `version`, `description`, `author`,
  `author_url`, `url`, `help_url`, `tags`. `id` becomes required, since it
  defaulted to `label` and that default no longer has a source.
- `dependencies` is renamed `linked_libraries` on **both** the decorator and the
  marketstall row (`Haybale.dependencies` keeps a deprecated parse alias). It
  never meant what `[project] dependencies` means — it takes Python module names
  of sibling haybales whose classes this library subscribes to, and the collision
  is a documented trap
  (`.insights/project_library_dependencies_use_package_names.md`).
- `help_url` is deleted outright. It had zero readers repo-wide; its role was
  taken by the generated `docs_url`. `[project.urls] Documentation` revives the
  slot with a real consumer — a rendered docs site, distinct from the raw
  fetchable prefix.
- Reading distribution metadata at decoration time requires the library to be
  installed as a distribution. Editable heaps and wheel installs both satisfy
  this; a bare path import does not, and needs a `pyproject.toml` walk-up
  fallback.

## Metadata editing moves into the Share flow

The marketplace Edit dialog is deleted — `_overview_edit_dialog.py` and
`LibraryManager.update_library_identity` both go, taking the five broken
single-quote regexes with them. Metadata is edited on a new `edit` screen in the
Share wizard, between `preflight` and `review`:

```python
STEPS = ("preflight", "edit", "review", "publish", "done")
```

Four acting screens where there were three (`publish` executes, `done` reports).

Standalone editing would have to *invent* a sync-and-reload to make an edit
visible, because `version`/`description`/`tags` come from distribution metadata
written at install time, not from `pyproject.toml` on disk. Share already owns
that mechanism: `steps/refresh.py` runs `uv sync` and the flow reloads the
registry, and its docstring states the ordering rule this depends on — the sync
must precede the reload, since the reload re-runs `@library(...)` and reads back
exactly the metadata the sync rewrote. Editing inside Share rides that for free
instead of building a second one.

The placement is also honest about what these fields are. They are publication
metadata; an edit that is never published changes only what the author's own
studio displays, which is close to meaningless for fields whose purpose is
telling other people what the library is.

`edit` sits before `review` rather than inside it. `review` fuses the version
plan, the dependency-drift decision, and the framework floor onto one screen
deliberately — splitting them "would ask for three clicks to authorize one"
action. But those are decisions the pipeline *computed* and asks the user to
authorize, whereas `edit` is free-text authoring with no computed proposal.
Mixing "approve this bump" with "type a new description" would muddy what the
confirm button means. Placing it before `review` also means drift detection and
the marketstall generator both see the edited state; editing afterwards would
let a `linked_libraries` change invalidate a decision the user had just made.

Consequences:

- Metadata is editable for **heaps only**. Share operates on a project's
  `barn/*`, so an installed library's metadata is no longer editable at all —
  correct, since an author cannot edit someone else's published library, and
  today's dialog pretending otherwise is a bug.
- The overview's Edit button becomes read-only or a "Share…" entry point, which
  fits its role as a detail view.
- Per `.insights/project_stepper_flows.md` only the last step may write, so
  `edit` collects into pipeline state and the write happens in `publish`
  alongside the bump. An edit abandoned mid-flow needs no rollback — it lands in
  the failure posture's first outcome, before any mutation.
- `edit` can invalidate a precondition `preflight` already passed: changing
  `examples_path` to a nonexistent path makes preflight's verdict stale. The
  path fields validate inline rather than re-running preflight, keeping it a
  single pass.

## `LibraryMetadata` — a shared base for `LibraryIdentity` and `Haybale`

Metadata reaches the UI through two channels, and a library is rendered from
whichever is available:

| library is | source |
| --- | --- |
| online (not installed) | marketstall row |
| installed | marketstall row; the identity when no row exists |
| local heap | the identity — heaps are never in a row |

A row is missing more often than "not yet installed": a library installed from a
source later unsubscribed, or by direct `uv pip install git+…` outside any
subscription, has none either. So the rule is **row when present, identity
otherwise**, and the heap is simply the always-absent case.

Rather than enforce name parity between the two classes with a test, they share
a base. `LibraryMetadata` holds the fifteen fields both carry:

```python
label, version, description, authors, tags, linked_libraries, on_reload,
os, docs_path, examples_path, tests_path,
homepage_url, documentation_url, author_url, issues_url
```

`LibraryIdentity(LibraryMetadata)` adds `id`, `folder_path`, `module_name`,
`file_watcher`. `Haybale(LibraryMetadata)` adds `name`, `require`, `source`,
`install_spec`, `origin`, plus the runtime-routing and cache fields. The detail
renderer takes a `LibraryMetadata` and works for either without branching — the
parity invariant becomes the type rather than a test.

Three fields had to be reconciled for the base to be honest, and in each case
the divergence was incidental rather than semantic:

- **`version`** describes the same thing on both. A row's version is what the
  publisher advertised and an identity's is what is installed; they differ only
  while an update is pending, which is the transient the update badge exists to
  observe.
- **`linked_libraries`** is `list[str]` of **module names** on both. The row
  previously held pip names, converted at the boundary by
  `_read_library_dependencies`; module names are the authored form, so the
  marketplace converts at the point of use instead of the metadata carrying the
  converted form.
- **`on_reload`** is `str` on both — the wire form, which is already what TOML
  and farmhand JSON carry. `LibraryReloadAction` stays available through a
  property, since combining declarations across libraries needs its ordering.

An earlier draft left `authors` and the URL fields off the identity on the
grounds that their only reader is one header, and patched the resulting hole by
having that header read `pyproject.toml` off disk for heaps. Both are dropped:
the base carries them, and the disk read was a third source for a renderer that
should see two, was the only render path touching the filesystem, and worked
only because a heap's source tree happens to sit adjacent — an
installed-but-unsubscribed library has the same empty-row problem and no
pyproject on disk.

### Two populations of one shape

The two classes are filled from different sources at different times, and only
`docs_path` differs:

| field | runtime (decoration) | publish (from source) |
| --- | --- | --- |
| `label`, `linked_libraries`, `on_reload`, `os`, `examples_path`, `tests_path` | decorator kwarg | decorator, read by AST |
| `version`, `description`, `authors`, `tags`, the four `*_url` | `importlib.metadata` | `[project]` / `[project.urls]` |
| `docs_path` | empty | derived from the module dir relative to the git root |

`docs_path` is a coordinate into a git host and has no runtime meaning — an
installed library's docs travel in the wheel. The same applies to the
`Haybale`-only fields (`origin`, `install_spec`, `require`) which are publish
concepts throughout.

Because decorator-authored fields arrive identically in both populations, and
the PEP 621 fields are two routes to the same values, a test can construct
`LibraryMetadata` both ways for the same library and assert equality on every
field except `docs_path` and `version` (which legitimately differs when the
working tree is bumped but not yet synced). That is a stronger guard than name
parity, and it checks the failure this ADR exists to prevent.

The `METADATA` shapes were verified by building a throwaway package and
installing it into a clean venv, rather than inferred. Reading `authors` needs
both headers: PEP 621 renders `{name = "X"}` as `Author:` but
`{name = "X", email = "…"}` as `Author-email: "X" <…>`, and a mixed list splits
across the two in the same package. Every barn library currently omits email, so
a naive read works today and would break on the first author who fills one in.
An email-only entry yields the bare address as its display name. `Keywords`
arrives as a single comma-joined, backend-alphabetized string, so tags must be
split and their order not relied upon. `Project-URL` is one header per entry,
shaped `"Label, URL"`, with labels preserved verbatim — including the fact that
`Source` carries no special meaning to the packaging layer, so treating it as
the override for the git-derived `origin` is this project's convention and a
mistyped label fails silently rather than erroring.

## Marketstall rows carry paths, not URLs

`source_url` is renamed `origin` and becomes the base that other locations
resolve against. `docs_url`, `examples_url`, and `tests_url` are replaced by
repo-relative `docs_path`, `examples_path`, and `tests_path`; consumers resolve
them through `HostProvider` — `raw_url()` to fetch, `blob_url()`/`tree_url()` to
link — recovering the ref from `install_spec` via `_parse_git_install_spec`.

Host knowledge currently lives in three places that each re-encode the same
rules: inline `"github.com" in https_url` branching in
`_build_entry_for_library`, a separate `_github_raw_base` heuristic in
`fetch_overview`, and `_clickable_doc_url` patching a raw prefix into a
browsable one. `HostProvider` already implements all of it as a tested
abstraction with paired `raw_url`/`blob_url` methods and a self-hosted registry.
Storing paths forces every consumer through it.

Storing relative also fixes a reach problem: with absolute URLs baked at publish
time, a consumer whose config knows a self-hosted GitLab still cannot resolve a
row generated by a publisher whose config did not. Resolution moves to the
consumer's machine with the consumer's host table. And the ref lives in exactly
one place (`install_spec`) instead of being redundantly baked into four URLs
that could contradict it — the class of contradiction `_build_entry_for_library`
already works to prevent.

The cost: a row is no longer self-describing, and an unrecognised host degrades
to no link rather than a possibly-working URL.

`HostProvider` gains `tree_url()`. Declared paths may name a directory (`tests/`,
where consumers append `OVERVIEW.md`/`QUICKREF.md`) or a file
(`examples/OVERVIEW.md`); GitHub needs `/tree/` for the former and `/blob/` for
the latter, and a trailing slash is the marker.

## One generator, one decorator reader

There are two producers of marketstall rows today and they disagree.
`_build_entry_for_library` (the share pipeline) and `scripts/generate_marketstall.py`
(the publish CI workflow) populate the same row shape from different inputs:
the script fills `dependencies` from `[project] dependencies` filtered to
`haybale-*` while the pipeline reads the decorator, and the script prefers the
*decorator's* description/author/tags over the pyproject ones — the opposite of
the precedence this ADR sets.

Both converge on `pyproject + decorator → LibraryMetadata → Haybale → TOML`.
The script keeps only what is genuinely its own: the two-tier
`marketplace.toml` + `stalls/*.toml` layout, `source = "pypi"`, PyPI-style
`install_spec`, and its `[tool.haywire.marketstall]` config defaults. It also
resolves refs against a configured branch rather than a tag, since it runs in CI
with no tag context — a real difference, not a divergence to remove.

The decorator is read by **one** reader: the AST parser already living in
`scripts/generate_marketstall.py`, promoted into `haywire.core.publishing`. It
is the only decorator reader in the repo that cannot be defeated by quoting —
the regex readers it replaces (`_read_library_label`,
`_read_library_dependencies`) are the same class of code that produced the
silently-no-oping Edit dialog.

Neither producer imports the library or touches `importlib.metadata`: at publish
time `pyproject.toml` on disk is the truth, which is what lets the CI script run
against a checkout with nothing installed. The sync-and-reload in
`steps/refresh.py` repairs the *running process* after a publish; it is not in
the path to the TOML.

## Declared paths are checked at publish time

`examples_path` and `tests_path` replace a folder scan that emitted a URL only
when `<lib>/examples/` existed *and* contained at least one `.haywire` file — so
an examples folder holding anything else published nothing, silently, and
examples living elsewhere could not be pointed at.

Both are decorator kwargs, declared relative to the library directory. An absent
kwarg means "no examples", which needs no check. A kwarg naming a path that does
not exist is an assertion the publish would contradict, so it fails
`SharePipeline.check_preconditions` with a `fix_id` and a resolve modal, joining
`strip_os`/`add_origin` in `_PRECONDITION_FIXES`. Because rows are tag-pinned, a
silently-omitted URL is unfixable without cutting a new release. Standalone
`write_marketstall()` still degrades rather than raising, matching the existing
split for an undeterminable branch.

## Authors are names only

`[project] authors` is already a list; the generator took `authors[0]` and
discarded the rest. It now takes all of them.

Per-author URLs are not modelled. PEP 621 has no such concept, so any mapping
from author name to URL is invented convention — either a `"Author: <name>"` key
in the flat `[project.urls]` table or a parallel `[tool.haywire.author_urls]`
map, both joined by name, both silently dropping a link when an author is
renamed, both needing publish-time validation and a fix_id of their own. Every
barn library today has exactly one author and a mostly-empty `author_url`, so
the feature is speculative. Project-level `[project.urls] Author` covers the
real case; a per-author map stays additive if co-authors ever want one.

`Haybale.author` is superseded by `authors`, and stays populated from
`authors[0]` for one release so existing marketstall files and older studios
keep working. `source_url` is likewise accepted as a deprecated alias for
`origin`.

Full design: [2026-08-08-library-metadata-consolidation.md](../../internals/superpowers/2026-08-08-library-metadata-consolidation.md).
