# One metadata record: settled decisions

**Status:** settled, unbuilt.
**Date:** 2026-08-10
**Landing:** one change. The `LibraryIdentity` migration (D10) is sequenced last.

---

## D1 — `Haybale` is the metadata record

`Haybale` keeps its name and stays in `haywire.core.marketstall.types`. Its definition:

> The runtime dataclass holding a library's declared metadata — the one shape both files
> carry. Read from the library's own `haybale.toml` *and* parsed from a `[[haybales]]`
> section; the fields are identical either way.

One class. Publish-generated (`install_spec`, `require`, `source`, `origin_provider`) and
transport (`via`, `last_seen`, `stale`, `source_label`, `source_file`, `source_origin`)
fields stay on it, empty on a row read from disk. No base class, no split.

## D2 — `source = "local"` on a file-read row

`read_haybale()` sets `source="local"`. Publish overwrites with `"git"`/`"pypi"`.

## D3 — `authors` replaces `author`

```python
authors: list[tuple[str, str]] = field(default_factory=list)   # (name, url)
```

`author: str` is deleted. `_TOML_FIELDS` gains `authors`, loses `author`.

`authors` is a table array: `to_dict()` must emit it after all bare keys, ordered
`authors` then `deprecated`.

Breaking, no migration. Feeds carrying flat `author` lose their author line until
republished.

## D4 — `read_haybale()` replaces `read_display()`

```python
def read_haybale(package_dir: Path) -> Haybale
```

Never raises; empty record on a missing or malformed file. `LibraryDisplay` and
`_display_from` are deleted.

The other two readers keep their existing contracts: `read_haybale_toml()` raises
`HaybaleTomlError`, `_parse_haybale_entry()` raises `MalformedMarketplaceError`.

Call sites to rename: `library_overview_editor.py:336`, `library_browser_editor.py:57`,
`_overview_edit_dialog.py:137`, `farmhands/catalog.py:66`,
`packaging/docs/extract.py:156`.

## D5 — Caching unchanged

`read_haybale()` keeps the `(path, mtime_ns)` cache: one `stat` per render, parse only on
change.

## D6 — `haybale.toml` is canon for `name`

Direction: `haybale.toml` → `pyproject.toml`. No bump-sync.

- `_STR_FIELDS` gains `name`.
- `_build_entry_for_library` reads `declared.name`, not `project.get("name")`
  (`marketstall.py:100`).
- `name` does **not** enter `EDITABLE_FIELDS`.

## D7 — `haybale.toml` is canon for `version`

Declarative canon. `pyproject.toml` still carries a literal version at build time.

- `bump_version.py` keeps writing both files.
- Drift checks report **pyproject** as the stale side.
- `generate.py`'s `PROJECT_FIELDS` gains `version`.
- `read_haybale_toml()`'s missing-version error rewords; fatal-on-missing stays.

## D8 — `id` is published

`id` joins the marketstall row.

## D9 — `LibraryInfo` carries the metadata row

No new type. `LibraryInfo` (`haywire.core.library.info`) gains a `Haybale` field and
represents a library whether or not it is installed:

```python
@dataclass(frozen=True)
class LibraryInfo:
    row: Haybale                 # metadata — from disk or from the catalog
    identity: LibraryIdentity    # runtime handles; empty when not installed
    enabled: bool                # False when not installed
    install_type: InstallType    # NOT_INSTALLED when not installed (D13)
    distribution_name: str       # "" when not installed
```

Docstring changes from *"Runtime snapshot of an installed library"* to *"A library as the
Library Manager sees it: its declared metadata, plus install state when it is
installed."*

- Built for catalog rows as well as installed libraries; `LibraryManager` gains the
  not-installed construction path alongside `get_installed_library()`.
- `_lib_view` / `_LibView` deleted.
- `_library_item(info)` — no `hasattr`/`getattr` probing.
- `_render_center(info)` — one parameter.
- `SessionContext.active_library: Optional["LibraryInfo"]` (`context.py:46`) is unchanged
  and becomes **true** — it currently also receives `Haybale` values.

`LibraryInfo` already lives in `haywire-core` while its only constructor lives in
`haybale-marketplace`; that split is unchanged. Core references no barn type.

## D13 — `InstallType.NOT_INSTALLED`

New member: `NOT_INSTALLED = "not_installed"`. Means **not present in this environment** —
a catalog row for a library that is not installed here. Spelled `NOT_INSTALLED` rather
than `UNINSTALLED` so it cannot be read as "was removed"; the surrounding uninstall
vocabulary (`UninstallFlow`, `UninstallImpact`, `UninstallSource`) all names the removal
*action*, and an uninstall leaves no `LibraryInfo` at all.

- `is_editable()` needs no change (returns `False` for it).
- Replaces the `install_type or InstallType.FOLDER` fallback at `library_manager.py:699`.
- Fixes a live misclassification: `compute_library_origin` rule 1 maps
  `InstallType.FOLDER` → `LibraryOrigin.FRAMEWORK`, whose `is_protected` is `True` and
  gates Disable/Uninstall. Under D9 a not-installed row defaulting to `FOLDER` would be
  wrongly protected; `NOT_INSTALLED` falls through to the catalog-source rules and yields
  `PYPI`/`GIT`/`UNKNOWN` correctly.

## D10 — `LibraryIdentity` descriptive fields removed

Delete `description`, `url`, `author`, `author_url`, `tags` (~30 call sites). Readers use
`read_haybale()`.

`LibraryIdentity` retains `id`, `folder_path`, `module_name`, `label`,
`linked_libraries`, `on_reload`, `file_watcher`, `version`.

`version` stays for now; revisit separately.

## D11 — Import discipline

Canonical for external consumers:

```python
from haywire.core.marketstall import Haybale
```

Deep imports (`...marketstall.types`) permitted only inside `core/marketstall/**` and
`tests/marketstall/**`. Enforced by a ruff `flake8-tidy-imports` `banned-api` rule scoped
via `per-file-ignores`.

To fix: `library_origin.py:29`, `test_share_examples.py`,
`test_haybale_preconditions.py`.

`Haybale` stays in `marketstall`; the move to `core.library` is a later refactor.

## D12 — Scope

In:

- `collect_overview_links(entry.row)` — links render for project-local libraries.
- `issues_url` added to `collect_overview_links`.

Out: any rethink of the detail page's link presentation or information hierarchy.

---

## Documentation corrections

| Location | Change |
|---|---|
| `haybale-toml.md:154,161` | `os`, `tests_path` are authored in `haybale.toml` — add the haybale column. Code unchanged |
| `haybale-toml.md:148` | `name` gains a haybale column (D6) |
| `marketstall-toml.md:135,191` | Per-author URLs reach the marketstall (D3) |
| `marketstall-toml.md:150` | `source` values include `"local"` (D2) |
| `marketstall.py:95-97` | Comment becomes true via D6's code change; no edit needed |

Split out, own commit: delete `scripts/generate_marketstall.py` (dead — `ast`-parses
`@library` fields ADR 0025 removed). Requires a CI check first; `bump_version.py`'s
docstring cites it as a CI consumer of release config.

## Glossary

`docs/reference/glossary.md` — already updated: `Haybale` redefined per D1;
`LibraryIdentity`, `LibraryInfo`, `LibraryEntry` added.

---

## Field matrix after the change

| Field | haybale.toml | marketstall | Canon | Notes |
|---|:-:|:-:|---|---|
| `name` | ● | ● | haybale | immutable; not editable |
| `id` | ● | ● | haybale | immutable |
| `version` | ● | ● | haybale | pyproject carries synced copy |
| `label`, `description`, `tags` | ● | ● | haybale | |
| `os`, `tests_path` | ● | ● | haybale | |
| `on_reload`, `linked_libraries` | ● | ● | haybale | |
| `homepage_url`, `documentation_url`, `issues_url` | ● | ● | haybale | absolute, verbatim |
| `notes`, `examples_path` | ● | ● | haybale | repo-relative paths |
| `authors` | ● | ● | haybale | `(name, url)` pairs |
| `[deprecated]` | ● | ● | haybale | hand-edited only |
| `origin`, `origin_provider` | ● | ● | share wizard | |
| `source` | — | ● | generated | `"local"` when read from disk |
| `install_spec`, `require` | — | ● | generated | |
| `via`, `last_seen`, `stale`, `source_*` | — | ● | consumer refresh | runtime-only |

## Blast radius

- `Haybale` — 91 call sites; flat attribute access preserved.
- `read_display` → `read_haybale` — 5 production sites.
- `LibraryInfo` — 14 call sites; gains `row`, docstring rewritten (D9).
- `InstallType` — new `NOT_INSTALLED` member; check `compute_library_origin`,
  `library_manager.py:699`, and the badge render at `library_overview_editor.py:411`
  (D13).
- `LibraryIdentity` descriptive fields — ~30 sites.
- Wire format — `author` → `authors`, `id` added.
- Release machinery — `bump_version.py`, `check_release_versions.py`.
- Docs — 4 edits; glossary already updated.

## Already landed

`library_overview_editor.py:625-636` — authors render individually, each linked when it
has a URL, comma-separated. Marketplace-sourced libraries render a flat string until D3
lands.
