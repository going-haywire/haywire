# `haybale.toml` — staged implementation plan

**Status: complete, 2026-08-09.** All nine stages landed on
`feat/haybale-toml-metadata`. Stage 6 was split into 6a (row generator), 6b
(preflight checks) and 6c (phase A/B ordering), as the plan allowed.

Execution plan for [the field-canon design note](2026-08-09-haybale-toml-field-canon.md).
Written 2026-08-09. The design note settles *what*; this settles *in what order*,
and resolves what the rollback left missing.

## Starting point

Branch `feat/haybale-toml-metadata`, 5 commits ahead of `ed00decd`: the design
note plus four cherry-picks from the archive branch
(`feat/library-metadata-consolidation`, tip `53108922`).

Recovered already — do not redo:

| commit | what |
| --- | --- |
| `6858723b` | post-publish `uv sync` + registry reload (`steps/refresh.py`) |
| `48100a55` | decorator quote-bug fix + regression test |
| `580d572d` | `help_url` deleted |
| `104a47be` | `on_reload` stored in its wire form |

Verified green at that base: 3138 passed (`pytest -m "not browser and not perf"`).

**Still on the old surface**, and this is what stage 0 exists for:

```python
# LibraryIdentity today
label, version, description, url, author, author_url,
folder_path, module_name, id, dependencies, tags, file_watcher, on_reload
```

```python
# Haybale._TOML_FIELDS today — URL-shaped, no coordinates
name, label, version, require, description, author, source, install_spec,
tags, os, dependencies, source_url, docs_url, examples_url, tests_url,
via, last_seen, stale
```

`locate.py`, `host_providers/`, `metadata.py`, `distmeta.py` and
`manifest/decorator_ast.py` do **not** exist on this branch.

## What is reused from the archive branch, and how

Three categories. Getting this wrong is the main risk in the whole plan.

**Port verbatim** — new files, no conflict, independent of the reversed
direction:

- `core/marketstall/host_providers/{__init__,base,github,gitlab,config}.py`
- `core/marketstall/locate.py` (`resolve_row_path`, `link_form`,
  `_ref_from_install_spec`)
- their tests: `tests/marketstall/test_locate.py`,
  `tests/marketstall/test_host_provider_config.py`

**Port with edits** — the keep-half of `17e32dc7`, which bundles wanted
infrastructure with `LibraryMetadata`:

- `types.py` — rows carry `origin` + repo-relative paths instead of `*_url`
- `registry/base.py` — `dependencies` → `linked_libraries`
- `identity.py` — write **directly** to the seven-field target; do **not**
  reintroduce `LibraryMetadata`

**Reference only, never merge** — built on decorator-writing, which the design
forbids:

- `839fa8f6` AST reader — reimplement reading `haybale.toml`, keeping only the
  `id` read for the mismatch check
- `bd7b2c31` / `36d299ea` declared-path preconditions — reimplement against the
  new scopes, gaining the `set_*` handlers the originals lacked
- `7f8ca3eb` / `c04f4cf9` wizard edit screen — replaced by the modal
- `3f46952e` / `6bd1eca9` barn migration to pyproject — replaced by stage 6

## Ground rules

- **Every stage ends green** on `uv run pytest -m "not browser and not perf" -q`,
  plus `ruff check`, `ruff format --check`, and `mypy` over the touched paths.
  Baseline first, per CLAUDE.md — anything new is ours.
- **One stage per commit.** A stage that grows past ~400 lines of production
  change wants splitting.
- Stages 0–2 are internal; nothing user-visible moves until stage 3.
- **Nothing writes `@library(...)`.** If a stage needs a decorator write, the
  stage is wrong.

---

## Stage 0 — infrastructure port

Rebuild the coordinate machinery the design rests on, without the metadata
direction it reverses.

1. Port `host_providers/` verbatim from `53108922`.
2. **Parameterise the providers by hostname** — the design's stated
   prerequisite. `GitLabProvider(hostname="gitlab.com")`, patterns via
   `re.escape(self._hostname)`, `resolve_host()` constructing a per-host
   instance rather than returning the shared singleton. Same for GitHub.
3. Port `locate.py` verbatim.
4. `types.py`: replace `source_url`/`docs_url`/`examples_url`/`tests_url` with
   `origin` + repo-relative `docs_path`/`examples_path`/`tests_path`, rename
   `dependencies` → `linked_libraries`, add `on_reload`. **Not** `notes` or
   `origin_provider` yet — those arrive with the fields that feed them.
5. `registry/base.py`: `_get_tracking_scopes` reads `linked_libraries`.
6. `identity.py`: rename `dependencies` → `linked_libraries`. Leave the
   descriptive fields alone; stage 2 removes them.

**Verify:** the ported `test_locate.py` passes, plus a new test that
`GitLabProvider("gitlab.zhdk.ch").blob_url(...)` emits that host and **not**
`gitlab.com` — the bug that made `load_self_hosted_hosts()` inert.

**Risk:** the widest blast radius of any stage — `linked_libraries` touches
every barn `__init__.py` and ~40 tests. Do the rename mechanically and let the
suite find the stragglers.

---

## Stage 1 — the reader

`core/library/haybale_toml.py`, sibling to where `distmeta.py` used to sit (in
`core.library`, so no `core.library` → `core.marketstall` edge).

- `read_haybale_toml(package_dir: Path) -> dict` — omits absent keys so callers
  can splat over defaults, the contract `distribution_fields()` established.
- Strict by default; a lenient sibling for report-only callers, mirroring
  `read_manifest` / `read_manifest_lenient`.
- Raises `LibraryLoadError` on: missing file, malformed TOML (wrap
  `TOMLDecodeError` with the path), missing `id`.
- **Validates `linked_libraries` entries are module-shaped.** A hyphen yields a
  dead scope silently — `_get_tracking_scopes` appends `dep + "."` verbatim.
- `module_of(dist_name)` → `re.sub(r"[-_.]+", "_", name).lower()`. Not
  `replace("-", "_")`: `haybale-TEST_A` proves that wrong.
- `tag_for(version)` → `f"v{version}"`, beside `haywire_core_requirement()`.

Pure functions, no callers yet. Tests cover every raise, the splat contract, and
both derivations.

---

## Stage 2 — the decorator reads it

Where the surface actually changes.

1. Decorator: `kwargs.update(read_haybale_toml(Path(class_file).parent))`, at
   the point where the identity is built.
2. Reject the descriptive kwargs with a message naming `haybale.toml` — the
   `_SUPERSEDED_KWARGS` pattern, now pointing at the TOML rather than
   `[project]`.
3. `LibraryIdentity` → its seven fields: `id`, `folder_path`, `module_name`,
   `file_watcher` (decorator) + `label`, `linked_libraries`, `on_reload` (TOML).
4. Write `haybale.toml` for **`haybale-testing` only** — one library, to prove
   the path end to end without a mass migration.

**Verify:** `haybale-testing` loads with its metadata; a deliberately malformed
`haybale.toml` fails *that library only* and the studio still starts
(`registry.py`'s per-library `try/except` is what makes the raise safe).

**Risk:** the rest of the barn has no `haybale.toml` yet and would fail to load.
Either land 2 and 6 together, or have the reader tolerate a missing file for one
stage and tighten in 6. **Prefer the former** — a temporarily lenient reader is
exactly the state a later stage forgets to close.

---

## Stage 3 — read at the point of use

- Marketplace overview renders from the row (not installed) or from
  `haybale.toml` off `folder_path` (installed). The per-field
  `if installed_lib: … else: …` block collapses.
- `get_installed_dependents` / `get_missing_dependencies` read the file live;
  `get_missing_dependencies_for_package` keeps reading the row.
- Read-through cache keyed on `(path, mtime)` — the overview re-renders per
  panel redraw.

**Verify:** editing `description` in `haybale.toml` changes the overview with no
reload. That is the whole point of the design; it is the test that proves it.

---

## Stage 4 — the watcher

`LibraryFileHandler` admits `haybale.toml` alongside `.py`, refreshes that
library's identity, and re-registers its modules so `_get_tracking_scopes` runs
again.

Three constraints from the design:

- the identity is shared by reference with the handler — mutate under its
  existing `_lock`
- editors write atomically: `on_created` (downgraded to MODIFIED) and
  `on_moved` must admit the file too, not just `on_modified`
- a mid-session malformed edit **logs and keeps the previous values** — the
  opposite of the import-time rule, because the author is mid-keystroke

---

## Stage 5 — the edit modal

Resurrect the deleted overview dialog, writing `haybale.toml` and nothing else.

- Read-only: `name`, `id`, `version`, `origin`, `origin_provider`
- Absent: `[deprecated]` — hand-edited by design, and the authoring docs must
  say so
- No `uv sync`, no reload, no reinstall

---

## Stage 6 — the share pipeline

The largest stage; split if it grows.

**Phase A — finalize `haybale.toml`:** write `version` (bump), `origin` +
`origin_provider` (from preflight's existing `resolve_host()` call, which
currently discards the provider), `linked_libraries` (drift auto-apply).

**Phase B — generate:** `[project]` + `[project.urls]` + the `[deprecated]` →
classifier projection; then the marketstall row (copy 17, generate 3, `require`
from `[project] dependencies`); then commit, tag `tag_for(version)`, push.

**Four preflight checks**, all `kind="act"` in the `strip_os` shape:

| check | fix |
| --- | --- |
| `sync_pyproject` | regenerate from `haybale.toml`; **must render the diff** |
| `set_notes` | offer the package root's `*.md`, plus `<empty>` |
| declared paths | `set_*` / `clear_*` for `examples_path` / `tests_path` |
| project root ≠ git root | **blocks**, no inline fix, points at the CLI |

The invariant: **nothing generates until `haybale.toml` is final.**

---

## Stage 7 — barn migration

`haybale.toml` for the remaining nine libraries; descriptive kwargs out of every
`@library(...)`; `[project]` regenerated. Mechanical but wide — every
`__init__.py` and every test that constructs an identity.

Trap: `.insights/feedback_barn_module_reload_test_trap.md` — top-of-file imports
of barn classes go stale after `importlib.reload`.

---

## Stage 8 — docs

- Mark **ADR 0024 superseded** (it returned with `580d572d` and currently
  asserts the opposite of this design).
- `library-canon.md`, `haybale-package-canon.md`, `marketplace-canon.md`,
  glossary.
- The **deferred path-scope sweep** from the design note's task section —
  `examples_path`/`tests_path` are project-relative, and its file:line
  references are as of `53108922`, so re-locate by symbol.
- Note in the authoring guide that `[deprecated]` is hand-edited.

---

## Sequencing notes

- **0 → 1 → 2 are hard-ordered.** 3–5 could interleave but read cleanest in
  order. 6 needs 0 (coordinates) and 2 (the surface). 7 needs 2. 8 last.
- **2 and 7 may need to land together** — see stage 2's risk.
- Suggested review points: after 0 (infrastructure, no behaviour change), after
  2 (the surface has moved), after 6 (publishing works end to end).

## Deliberately out of scope

- The **rename-wizard** — deferred by decision; `name`/`id` stay immutable.
- **Migration for already-published libraries** — clean slate; no `distmeta`
  fallback, no dual-read window.
- **Nested projects in a monorepo** — preflight blocks project-root ≠ git-root;
  supporting it is a separate feature.
