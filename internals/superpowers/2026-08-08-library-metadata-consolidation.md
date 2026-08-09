# Library metadata consolidation — design and migration plan

Settled 2026-08-08. Decision record: [ADR 0024](../../docs/adr/0024-library-metadata-single-source.md).

Unbuilt. This is the design and the ordered plan, not a report of work done.

## The problem, as measured

`version`, `description`, `author`, and `tags` are authored twice — once in a
library's `pyproject.toml`, once in its `@library(...)` decorator. The
marketstall generator reads the pyproject copy; the studio's library overview
reads the decorator copy for installed libraries and the marketstall row for
available ones. So the same library shows different metadata depending on
install state.

Verified in-tree on 2026-08-08 against installed `haybale-core` 0.0.39:

| field | wheel `METADATA` | decorator |
| --- | --- | --- |
| description | `Haywire's core library with types, nodes, widgets, and renderers` | `Fundamental components for hayire graphs` |
| author | `Haywire Team` | `maybites` |

Two different sentences, and the decorator one carries a typo (`hayire`) — that
is the copy users see once the library is installed.

Three further faults found in the same review:

1. **`update_library_identity` is broken.** Five inline regexes of the form
   `(    label=')[^']*(')` match single quotes only. Every barn library is
   `ruff format`ted to double quotes, so `label`, `description`, `url`,
   `author`, and `author_url` silently no-op when edited from the UI. The
   sibling helpers in `decorator_io.py` are quote-agnostic (`['\"]`), so
   `tags`/`dependencies`/`on_reload` do land — the bug is confined to the five
   inline ones. `library_manager.py:986-990`.
2. **`help_url` is dead.** Zero readers repo-wide. Superseded by the generated
   `docs_url`.
3. **Examples publish silently-nothing.** `_folder_url()` emits a URL only when
   `<lib>/examples/` exists *and* contains ≥1 `.haywire` file.

## The measurement that decided the split

The design carried "move everything to `[tool.haywire]`" for two rounds before
this check reversed it:

```console
$ python3 -c "import importlib.metadata as md; d=md.distribution('haybale-core'); print([f for f in map(str,d.files) if 'pyproject' in f])"
[]                      # 9 files installed, none of them pyproject.toml

$ grep -l force-include barn/*/pyproject.toml
                        # no matches; only haywire-core uses it, for _baked_docs
```

`[tool.haywire]` does not reach installed wheels. `os` appears to be read from
pyproject at runtime today, but that path runs only for **heaps** (editable
project libraries); for installed wheels it returns `[]` and the UI falls back
to the marketstall row. Moving `label`/`linked_libraries`/`on_reload` there
would have worked in an author's dev tree and broken hot-reload scope tracking
and the post-install prompt for every consumer.

Confirmed in the same run that `[project]` fields *do* survive: `Name`,
`Version`, `Summary`, `Author`, `Keywords` all read back correctly via
`importlib.metadata`. `Project-URL` is `None` only because no barn library
declares `[project.urls]` yet — greenfield, no migration burden.

## Target author surface

`barn/haybale-core/pyproject.toml`:

```toml
[project]
name = "haybale-core"
version = "0.0.40"
description = "Fundamental components for haywire graphs"
keywords = ["haywire", "node-editor", "core"]
authors = [{ name = "maybites", email = "…" }]
dependencies = ["haywire-core>=0.0.31"]

[project.urls]
Homepage      = "https://github.com/going-haywire/haywire"
Documentation = "https://going-haywire.github.io/haywire/"
Source        = "https://github.com/going-haywire/haywire"
Author        = "https://maybites.ch"
Issues        = "https://github.com/going-haywire/haywire/issues"

```

`barn/haybale-core/haybale_core/__init__.py`:

```python
@library(
    id="core",
    label="Core",
    linked_libraries=["haybale_studio"],     # module names, not pip names
    on_reload="restart",
    os=["macos", "linux"],
    examples_path="examples/OVERVIEW.md",
    tests_path="tests/",
    file_watcher=True,
)
class Library(BaseLibrary): ...
```

Nothing is authored twice, and `[tool.haywire]` is not used — every
Haywire-specific field is a decorator kwarg, so all of them survive into the
wheel. `[tool.haywire].os` moves here and `_apply_os_to_pyproject` is deleted.

### `LibraryMetadata` — the shared base

```python
@dataclass
class LibraryMetadata:
    label: str = ""
    version: str = ""
    description: str = ""
    authors: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    linked_libraries: list[str] = field(default_factory=list)  # module names
    on_reload: str = "none"                                    # wire form
    os: list[str] = field(default_factory=list)
    docs_path: str = ""
    examples_path: str = ""
    tests_path: str = ""
    homepage_url: str = ""
    documentation_url: str = ""
    author_url: str = ""
    issues_url: str = ""
```

`LibraryIdentity(LibraryMetadata)` adds `id` (now required), `folder_path`,
`module_name`, `file_watcher`. `Haybale(LibraryMetadata)` adds `name`,
`require`, `source`, `install_spec`, `origin`, plus the runtime-routing
(`source_label`, `source_file`, `source_origin`) and cache (`via`, `last_seen`,
`stale`) fields.

The detail renderer takes a `LibraryMetadata`, so it works for a row, an
installed library, or a heap without branching.

Three reconciliations make the base honest, all incidental rather than semantic:
`version` means the same thing on both (a row's is advertised, an identity's
installed; they differ only while an update is pending); `linked_libraries` is
module names on both, with the marketplace converting to pip names at the point
of use; `on_reload` is `str` on both, with `LibraryReloadAction` available
through a property for the ordering `max()` needs.

**Dataclass inheritance forces every base field to have a default**, which makes
them all optional on `LibraryIdentity` — today `label`/`version`/`description`/
`id` and five others are positionally required across 84 construction sites. The
decorator populates them regardless, so required-ness was doing little, but a
bug yielding `label=""` no longer fails at construction. Behaviour change, not a
pure refactor.

### Two populations, one shape

| field | runtime (decoration) | publish (from source) |
| --- | --- | --- |
| `label`, `linked_libraries`, `on_reload`, `os`, `examples_path`, `tests_path` | decorator kwarg | decorator, read by AST |
| `version`, `description`, `authors`, `tags`, four `*_url` | `importlib.metadata` | `[project]` / `[project.urls]` |
| `docs_path` | empty | module dir relative to git root |

Neither publish producer imports the library — `pyproject.toml` on disk is the
truth at publish time, which is what lets the CI script run against a checkout
with nothing installed.

Metadata-reading details verified 2026-08-08 against installed `haybale-core`:

- `Author:` is a plain header **only because every barn library omits email**.
  PEP 621 renders `{name, email}` pairs into `Author-email: "X" <…>` instead,
  and a mixed list splits across both headers. The reader must merge
  `get_all("Author")` with `getaddresses()` over `get_all("Author-email")`.
- `Keywords` arrives as one comma-joined, backend-alphabetized string
  (`'core,haywire,node-editor,visual-programming'`). Split on commas; do not
  assert order.
- `Project-URL` is currently `None` for every barn library because none declares
  `[project.urls]`. **Settled by spike** (2026-08-08, throwaway package built
  with hatchling and installed into a clean venv): one header per entry, shaped
  `"Label, URL"`, labels preserved verbatim including spaces. All five
  conventional keys survive.

Verified reader, both halves exercised against a package declaring three authors
(no-email, name+email, email-only) and six URLs:

```python
def _parse_metadata_urls(md) -> dict[str, str]:
    return dict(p.split(", ", 1) for p in (md.get_all("Project-URL") or []) if ", " in p)

def _parse_metadata_authors(md) -> list[str]:
    names = list(md.get_all("Author") or [])
    for raw in md.get_all("Author-email") or []:
        names += [n or addr for n, addr in getaddresses([raw])]
    return names
```

The three-author case split across **both** headers — `Author: No Email Person`
and `Author-email: With Email <we@example.com>, bare@example.com` — and the
reader recovered `['No Email Person', 'With Email', 'bare@example.com']`. An
email-only entry yields the bare address as its display name; the renderer may
therefore show an address where a name belongs.

`[project.urls] Source` has no special status in the metadata layer — it is an
ordinary label, so the "Source overrides git-derived `origin`" rule is our
convention alone. A mistyped label (`source`, `SCM`) silently fails to override
rather than erroring; warn on unrecognised labels at publish time.

## Marketstall row — target generation

| field | source | example |
| --- | --- | --- |
| `name` | `[project] name`, fallback dir name | `"haybale-core"` |
| `label` | decorator `label`, read by AST | `"Core"` |
| `version` | `[project] version` | `"0.0.40"` |
| `description` | `[project] description` | `"Fundamental components for haywire graphs"` |
| `authors` | all of `[project] authors`, names only | `["maybites"]` |
| `tags` | `[project] keywords` | `["haywire", "node-editor", "core"]` |
| `require` | `haywire_core_requirement()` over `[project] dependencies` | `"haywire-core>=0.0.31"` |
| `linked_libraries` | decorator, **module names, no conversion** (row field renamed from `dependencies`) | `["haybale_studio"]` |
| `os` | decorator `os` | `["macos", "linux"]` |
| `on_reload` | decorator `on_reload`, default `"none"` | `"restart"` |
| `source` | hardcoded | `"git"` |
| `origin` | git remote via `ssh_to_https`, `.git` stripped; `[project.urls] Source` overrides | `"https://github.com/going-haywire/haywire"` |
| `install_spec` | `{name} @ git+{origin}.git@{tag}#subdirectory={lib_rel}` | `"haybale-core @ git+https://…@v0.0.40#subdirectory=barn/haybale-core"` |
| `docs_path` | module dir relative to git root, trailing `/` | `"barn/haybale-core/haybale_core/"` |
| `examples_path` | decorator `examples_path`, prefixed with lib rel | `"barn/haybale-core/examples/OVERVIEW.md"` |
| `tests_path` | decorator `tests_path`, prefixed with lib rel | `"barn/haybale-core/tests/"` |
| `homepage_url` | `[project.urls] Homepage` | `"https://github.com/going-haywire/haywire"` |
| `documentation_url` | `[project.urls] Documentation` | `"https://going-haywire.github.io/haywire/"` |
| `author_url` | `[project.urls] Author` | `"https://maybites.ch"` |
| `issues_url` | `[project.urls] Issues` | `"https://github.com/going-haywire/haywire/issues"` |
| `source_label`/`source_file`/`source_origin` | runtime routing, not persisted | — |
| `via`/`last_seen`/`stale` | refresh-owned, project `[[caches]]` only | — |

No absolute doc/example/test URL is stored. Consumers resolve via
`resolve_host(origin)` → `raw_url()` to fetch, `blob_url()`/`tree_url()` to
link, with `ref` recovered from `install_spec`.

Deprecated one release: `source_url` (alias of `origin`), `author` (populated
from `authors[0]`).

## Migration plan

Ten steps. Each ends green on `uv run pytest -m "not browser and not perf"`.
Steps 1 and 2 are independently shippable and worth landing first.

### 1. Fix the quote bug — standalone, ship immediately

Replace the five inline regexes in `library_manager.update_library_identity`
(`library_manager.py:986-990`) with `decorator_io._set_decorator_str_field`,
which is already quote-agnostic and already used for `on_reload` three lines
below.

Independent of everything else here. Right now identity editing is silently
broken for every library in the repo, and it stays broken for the duration of
this migration unless fixed first.

Step 7 deletes this call site, so the fix is temporary by design — worth doing
anyway, because the migration is long and the bug is live today. The helper it
moves onto survives; only the caller goes.

Test: edit each of the five fields against a double-quoted decorator fixture,
assert the value lands. There is no such test today — that is why the bug
survived.

### 2. Delete `help_url`

Remove from `LibraryIdentity`, the `@library` docstring, all 10 barn
`__init__.py` files, `settings/registry.py:43`, `themes/registry.py:23`,
`library/utils.py:77`, and `studio/init.py:381` (the scaffold template).

Zero readers, so nothing else moves. Ship on its own.

### 3. `HostProvider.tree_url()` + route the generator through it

Add `tree_url()` to the `HostProvider` ABC and both implementations
(`github.py`, `gitlab.py`), mirroring the existing `blob_url()`.

Rewrite `_build_entry_for_library`'s inline `"github.com" in https_url`
branching to use `resolve_host()`. Same output values, one code path. Land
before step 4 so path-based rows have a resolver to lean on.

Test: `tree_url` for both hosts; `_build_entry_for_library` emits byte-identical
URLs to the pre-refactor generator for a GitHub and a GitLab fixture.

### 4. Introduce `LibraryMetadata`

New dataclass in `haywire.core.library` holding the fifteen shared fields, with
`LibraryIdentity` and `Haybale` both extending it. Mechanical but wide: 84
`LibraryIdentity` sites and 75 `Haybale` sites.

- Every base field defaults, so all become optional on `LibraryIdentity` (see
  the note above — a behaviour change, not a pure refactor). Test helpers
  `_make_identity` / `make_lib_identity` shrink accordingly.
- `on_reload` becomes `str` on `LibraryIdentity`; keep a
  `reload_action -> LibraryReloadAction` property for the `max()` combining the
  install flow does. `__post_init__`'s enum coercion becomes a validation.
- Land before step 5 — the schema change is expressed in terms of the base.

Test: both subclasses expose the full base field set; `reload_action` round-trips
every wire value; an unknown `on_reload` string still raises.

### 5. Marketstall schema — paths and `origin`

- Rename `Haybale.source_url` → `origin` and `Haybale.dependencies` →
  `linked_libraries`; accept both old names as deprecated parse aliases in
  `parsing.py`.
- `linked_libraries` now carries **module names**, not pip names — drop the
  `_`→`-` conversion in the producer and convert at the marketplace's point of
  use instead. `norm_dep()` loses its metadata-boundary caller.
- Replace `docs_url`/`examples_url`/`tests_url` with
  `docs_path`/`examples_path`/`tests_path` in `_TOML_FIELDS` (the fields
  themselves now come from the base).
- Keep `author: str` populated from `authors[0]`.
- Read `examples_path`/`tests_path`/`os` from the decorator via the AST reader;
  delete `_folder_url` and the `.haywire` scan.
- Take all `[project] authors`, not `[0]`.
- Read `[project.urls]` into the four URL fields.

Consumer side, same step or rows break: `collect_overview_links` and
`fetch_overview` resolve paths through `HostProvider`; delete
`_clickable_doc_url` and `_github_raw_base`.

Also rewrite the overview header (`library_overview_editor.py:323-334`, `:366`,
`:606`) to take a `LibraryMetadata` — the row when one exists, the identity
otherwise — instead of branching between `installed_lib.identity` and
`marketplace_pkg` per field. This is what closes the install-state split, and
the base class from step 4 is what makes it a single code path.

No-row libraries (heaps, and installed libraries whose source was unsubscribed)
fall back to the identity — **not** to a disk read of `pyproject.toml`, which an
earlier draft proposed and ADR 0024 rejects.

Test: round-trip a row through `to_dict`/`parse`; `source_url` and
`dependencies` rows parse into `origin`/`linked_libraries`; resolution produces
correct raw and blob URLs for both hosts; unknown host degrades to no link
rather than a wrong one; **the overview header renders identical values for a
library whether installed or not**.

### 6. Declared-path preconditions

Add a `check_preconditions` check: a declared `examples_path`/`tests_path` that
does not exist on disk fails with a `fix_id`. Register handlers in
`_PRECONDITION_FIXES` — `clear_examples_path` (drop the key) and
`set_examples_path` (pick another). Wire the resolve modal alongside
`strip_os`/`add_origin`.

`write_marketstall()` standalone still degrades rather than raising, matching
the existing undeterminable-branch split.

Test: missing path fails preconditions with the right `fix_id`; each fix
handler leaves the pyproject in a publishable state; standalone
`write_marketstall` omits and does not raise.

### 7. `LibraryIdentity` reads distribution metadata

- Drop `version`, `description`, `author`, `author_url`, `url`, `tags` from the
  decorator's accepted kwargs — they come from `importlib.metadata` now.
- Add `os`, `examples_path`, `tests_path` as decorator kwargs (moved off
  `[tool.haywire]`); delete `_apply_os_to_pyproject` and
  `read_os_from_pyproject`.
- Populate `version`, `description`, `authors`, `tags` and the four `*_url`
  fields from `importlib.metadata` at decoration time, keyed on the distribution
  owning `module_name`. Handle the `Author`/`Author-email` split and the
  comma-joined `Keywords` (see the verified notes above).
- Fallback for a bare path import (no distribution): walk up for
  `pyproject.toml`. Confirm whether any supported flow actually hits this —
  if none does, raise instead of guessing.
- Rename `dependencies` → `linked_libraries`; `id` becomes required.
- Update the 13 files reading the removed identity fields.

The largest step and the only one that cannot be split — the decorator and every
barn library move together.

Test: identity fields match `importlib.metadata` for an installed library,
including an author declared **with** an email and one without; missing
distribution takes the documented path; `id` omitted raises. **Construct
`LibraryMetadata` both ways for the same library and assert equality on every
field except `docs_path` and `version`** — the strongest guard on the whole
change, since it directly checks the drift this ADR removes.

### 8. Metadata editing moves into the Share flow

Delete `_overview_edit_dialog.py` and `LibraryManager.update_library_identity`
outright — not rewritten. Step 1's quote fix is superseded here (it still ships
on its own; the bug is live until this lands). The overview's Edit button
becomes read-only or a "Share…" entry point.

Add an `edit` screen to the Share wizard between `preflight` and `review`:

```python
# haybale_share/_flow/copy.py
STEPS = ("preflight", "edit", "review", "publish", "done")
```

Four acting screens where there were three — `publish` executes, `done` reports.
Verified 2026-08-08: `STEPS` currently holds four entries and `_state.py`'s
docstring describes "Three screens".

Form, all heap-scoped (Share operates on a project's `barn/*`):

- `description`, `keywords` — `pyproject.toml`.
- `authors` — repeatable list (name + optional email), since the generator now
  takes all `[project] authors` rather than `[0]`.
- `[project.urls]` — key/value editor offering the conventional keys
  (`Homepage`, `Documentation`, `Source`, `Author`, `Issues`).
- `examples_path`, `tests_path` — validated **inline** against the working tree;
  editing them can otherwise stale the `preflight` verdict from step 5, and
  inline keeps preflight a single pass.
- `os` multi-select — moved from the deleted dialog, now a decorator field.
- `label`, `on_reload`, `linked_libraries` — decorator fields.

Writes, in the `publish` step per `.insights/project_stepper_flows.md` (only the
last step may write; `edit` collects into pipeline state):

- **Decorator** — `label`, `on_reload`, `linked_libraries`, `os`,
  `examples_path`, `tests_path` via `decorator_io._set_decorator_str_field` /
  `_set_decorator_list_field`.
- **`pyproject.toml`** — `description`, `keywords`, `authors`,
  `[project.urls]`, through `edit_toml`, following the (now deleted)
  `_apply_os_to_pyproject`'s shape: comment-preserving, canonical ordering,
  remove-the-key rather than write-empty so absent keeps meaning "unset".
- Both succeed or neither lands — a half-applied edit leaves the two files
  disagreeing, the exact failure this change exists to prevent.

Note the split is now decorator-heavy, and only the pyproject half is subject to
the sync-staleness below: decorator fields are read from code, so a reload alone
shows them.

No new sync mechanism is needed: `steps/refresh.py` already runs `uv sync` and
the flow reloads the registry, so edited `pyproject.toml` values reach
distribution metadata and from there the re-run `@library(...)`. Its ordering
rule is load-bearing here too — **sync before reload**, since the reload reads
back exactly what the sync rewrote.

Test: each field lands in its correct file; a comment elsewhere in
`pyproject.toml` survives; a failed decorator write leaves the pyproject
untouched and vice versa; clearing a URL removes the key rather than writing
`""`; an abandoned `edit` writes nothing; a `examples_path` edited to a
nonexistent path is rejected inline.

### 9. One decorator reader, one generator

Promote `extract_library_metadata` out of `scripts/generate_marketstall.py` into
`haywire.core.publishing` and widen it to every decorator field the row needs
(`label`, `linked_libraries`, `on_reload`, `os`, `examples_path`, `tests_path`).
It parses AST, so unlike the regex readers it cannot be defeated by quoting —
which is the bug class step 1 patched.

- Delete `_read_library_label` and `_read_library_dependencies` (`deps.py`).
- `_get_decorator_list_field` / `merge_decorator_list_field` callers in the share
  pipeline (`apply_drift_fix`, `SharePipeline.apply_drift_replace`) follow the
  `linked_libraries` rename. These stay regex-based — they *write*, and the AST
  reader only reads.
- Rewrite `generate_marketstall.build_entry` to produce a `Haybale` via
  `LibraryMetadata` rather than assembling a dict by hand. Its local
  `LibraryMetadata` (label/description/author/tags, `None` = unauthored) is
  replaced by the shared one.
- Fix the two divergences this exposes: the script fills `dependencies` from
  `[project] dependencies` filtered to `haybale-*` (should be the decorator's
  `linked_libraries`), and prefers decorator description/author/tags over
  pyproject (opposite of the ADR's precedence). `_filter_haybale_siblings`
  loses its caller.
- Keep what is genuinely the script's own: two-tier layout emission,
  `source="pypi"`, PyPI-style `install_spec`, `[tool.haywire.marketstall]`
  config defaults, and branch-based (not tag-based) ref resolution — it runs in
  CI with no tag context.

Test: both producers emit identical rows for the same fixture library, modulo
the documented `source`/`install_spec`/ref differences.

### 10. Author-facing migration

- All 10 barn `__init__.py` + `pyproject.toml` pairs to the target surface.
  Resolve each drift by hand: pyproject wins on `description`/`author` (it is
  what publishes), and fix the `hayire` typo.
- Add `[project.urls]` where a library has real URLs to declare — currently
  **none** do, so every URL field is unexercised until this step. Do the
  one-library spike (noted above) before step 7 builds the parser.
- Move each library's `[tool.haywire].os` into its decorator; the section then
  disappears from every barn pyproject.
- `studio/init.py` scaffold template.
- `haywire rename` (`packaging/rename.py:109,134`) drops its `author_url`
  rewrite.
- Docs: `docs/haybale/library-canon.md`, `docs/haybale/haybale-package-canon.md`,
  `docs/haybale/marketplace/*`, `docs/architecture/sharing/*`,
  `.insights/project_library_dependencies_use_package_names.md` (retitle for
  `linked_libraries`).
- Regenerate library docs: `uv run haywire docs --all`.

## Open questions

1. **Bare path imports.** Step 6's fallback assumes some flow imports a library
   without installing it. Grep the discovery paths first; if none does, drop the
   fallback and raise — a silent guess is worse than a clear failure.
2. **`docs_path` for non-monorepo layouts.** Derived as "module dir relative to
   git root", which assumes the library lives in a repo. A library published
   from a repo root with no `barn/` needs checking against
   `_build_entry_for_library`'s existing assumptions.
3. **Deprecation window.** ADR says one release for `source_url`/`author`. Worth
   confirming against the marketstall files already published — if the only
   consumers are in-repo, the aliases can be skipped entirely.
4. **Stale dist metadata after a pyproject edit** (step 7). Pre-existing, not
   introduced here — `_pkg_version()` in every barn `__init__.py` is
   `importlib.metadata.version`, which reads
   `site-packages/<dist>.dist-info/METADATA`, written once at install time. An
   editable install does not change this: verified 2026-08-08 by editing a
   `pyproject.toml` in place and re-reading in a fresh interpreter — version and
   description both still reported the pre-edit values until `pip install -e`
   was re-run.

   Today the window is unreachable from the UI because `version` is the only
   dist-metadata-backed field and the dialog refuses to edit it ("set via
   Share/publish"). This change makes `description` and `tags` dist-backed *and*
   editable, so it becomes reachable.

   **Resolved** by moving editing into Share. `steps/refresh.py` already runs
   `uv sync` and the flow reloads the registry, so the window closes with no new
   mechanism — the standalone dialog would have had to build one. The three
   options below are kept only as the record of why that placement was chosen:
   (a) `uv sync` on save — what Share does anyway; (b) annotate as "applies
   after reinstall" — leaves the user looking at an unchanged value; (c) read
   `pyproject.toml` for heaps, dist metadata for wheels — two sources for one
   field, which is what this ADR removes.

5. ~~**`authors` and the URL fields on `LibraryIdentity`.**~~ **Resolved** — the
   `LibraryMetadata` base carries them, so both populations have them and the
   no-row fallback is complete. The question only existed while the two classes
   were separate and parity was a test rather than a type.
6. ~~**`[project.urls]` shape is unverified.**~~ **Resolved by spike** — see the
   verified reader above. Remaining sub-question: warn or fail on an
   unrecognised `[project.urls]` label at publish time, since `Source` overriding
   `origin` is our convention and a typo fails silently.
7. **`LibraryMetadata`'s defaults weaken `LibraryIdentity`'s construction
   contract** (step 4). Dataclass inheritance requires every base field to
   default, so nine currently-required fields become optional across 84
   construction sites. Acceptable — the decorator fills them — but a bug
   yielding `label=""` will no longer fail loudly. Consider a `__post_init__`
   assertion on the decorator path only.

## Traps

- `.insights/project_git_url_publishing_traps.md` — `install_spec` and doc URLs
  are tag-pinned *only* through `SharePipeline`; a standalone call floats to the
  current branch. Step 4 must not widen that.
- `.insights/project_farmhand_docs_bake.md` — a broken `force-include` shipped
  in v0.0.26. The reason force-including `pyproject.toml` was rejected.
- `.insights/feedback_barn_module_reload_test_trap.md` — step 6 touches every
  barn `__init__.py`; tests importing barn classes at module top-level go stale
  after `importlib.reload`.
- `.insights/project_settings_registry_construction_side_effects.md` — step 6
  touches decoration-time behaviour; constructing registries in tests is not
  inert.
