# Author-Facing Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The last plan in the consolidation. Move every barn library to the target
surface, then delete the transitional shims that let both spellings work.

**Architecture:** Migrate the ten libraries first — their decorator values must
land in `pyproject.toml` before the kwargs are removed, or the values are lost.
Then the scaffold and `haywire rename`, then the shims, then the docs. Each task
leaves the tree green.

**Tech Stack:** Python 3.12, `pyproject.toml`, pytest.

## Global Constraints

- Line length 109 (`uv run ruff check .` **and** `uv run ruff format --check .` — CI runs both).
- Type-check with the exact command in `CLAUDE.md`; `haybale-visiongraph` is excluded.
- Gate before every commit: `uv run pytest -m "not browser and not perf"` (~2.5 min).
- Never call `create_test_injector()` directly in a test — use the `test_injector` fixtures.
- **Migrate values before deleting kwargs.** A decorator value with no
  `pyproject.toml` home is destroyed by removing the kwarg, and the identity reads
  distribution metadata — so the loss is silent until someone looks at the UI.
- `uv sync` after editing a `pyproject.toml`, or the installed metadata still
  holds the old values (`.insights/project_stale_version_diagnosis.md`).

## Predecessors

All landed:

- [foundation](2026-08-08-library-metadata-foundation.md), [distribution](2026-08-08-library-metadata-distribution.md),
  [one-reader](2026-08-08-library-metadata-one-reader.md),
  [edit-in-share](2026-08-08-library-metadata-edit-in-share.md),
  [declared-paths](2026-08-09-library-metadata-declared-paths.md).

## Verified starting state

Confirmed on disk 2026-08-09.

**All ten barn libraries still pass the six superseded kwargs** — `version`,
`description`, `url`, `author`, `author_url`, `tags` — plus `dependencies=`
instead of `linked_libraries=`. The decorator accepts and ignores them
(`_SUPERSEDED_KWARGS`, `decorator.py:22`).

**`[project.urls]` is declared by *no* library.** So `homepage_url`,
`author_url`, `documentation_url` and `issues_url` are empty on every identity
today, and the decorator's `url=`/`author_url=` values have nowhere to go until
this plan creates one.

**Five libraries lack `keywords` and `authors` in pyproject entirely:**

| library | pyproject has keywords? | authors? |
| --- | --- | --- |
| TEST_A, core, example, testing, visiongraph | yes | yes |
| graph-editor, haystack, marketplace, share, studio | **no** | **no** |

**Decorator values with no pyproject home**, which must be migrated before the
kwargs are deleted:

| library | url | author | author_url | tags |
| --- | --- | --- | --- | --- |
| TEST_A | going-haywire/haywire | Haywire Team | going-haywire/haywire | testing, development |
| core | going-haywire/haywire | maybites | maybites.ch | core, types, widgets, skins, adapters |
| example | github.com/author/haywire_library | Example Author | `https://author_url` | example, demo, tutorial |
| testing | going-haywire/haywire | Haywire Team | going-haywire/haywire | testing, development, debug |
| visiongraph | haywire/haywire-repo/libraries/… | Florian Briggisser, Martin Fröhlich | `https://author_url` | vision, camera, video, opencv |
| graph-editor, haystack, marketplace, share, studio | (empty) | (empty) | (empty) | one tag each |

Three of those URLs are **placeholders, not data**: `https://author_url` appears
twice, and `github.com/author/haywire_library` is fictional. They are dropped, not
migrated — see Task 1.

**`haybale-visiongraph` is a gitignored local-only symlink** (excluded from mypy
per `CLAUDE.md`). It still needs migrating, but a failure there must not block the
rest.

**Two live bugs this plan fixes:**

1. `packaging/rename.py:129-134` rewrites `label`, `url`, `author_url` with
   **single-quote-only regexes** — `(    label=')[^']*(')`. Every barn library is
   `ruff format`ted to double quotes, so all three silently no-op. This is the
   same defect the foundation plan fixed in `library_manager.update_library_identity`;
   `rename.py` was a separate file and was missed. Two of the three fields it
   rewrites no longer exist on the decorator at all.
2. `studio/init.py:375-384` scaffolds a new library with all six superseded
   kwargs, so every project created today starts pre-migration.

## Out of scope

- Publishing a release. This plan changes metadata, not versions.
- `docs_path` — derived at publish time, never authored.

## File Structure

| File | Responsibility |
| --- | --- |
| `barn/*/pyproject.toml` (10) | gain `keywords`, `authors`, `[project.urls]` |
| `barn/*/[a-z_]*/__init__.py` (10) | six kwargs removed; `dependencies` → `linked_libraries` |
| `packages/haywire-studio/src/haywire_studio/init.py:375-384` | scaffold template |
| `packages/haywire-studio/src/haywire_studio/packaging/rename.py:101-134` | quote bug + dead fields |
| `packages/haywire-core/src/haywire/core/library/decorator.py:22,116` | `_SUPERSEDED_KWARGS` + `dependencies` shim deleted |
| `packages/haywire-core/src/haywire/core/publishing/manifest/decorator_ast.py` | `dependencies` fallback deleted |
| `packages/haywire-core/src/haywire/core/publishing/marketstall.py:117-119` | `[tool.haywire].os` fallback deleted |
| `docs/haybale/library-canon.md`, `docs/haybale/haybale-package-canon.md` | authoring guide |

---

### Task 1: Migrate the ten barn libraries

**Files:**

- Modify: all 10 `barn/*/pyproject.toml`
- Modify: all 10 `barn/*/[a-z_]*/__init__.py`

**Interfaces:**

- Consumes: nothing.
- Produces: no library passes a superseded kwarg; every decorator value worth
  keeping has a `[project]` home.

- [ ] **Step 1: Record the current identity values**

Before touching anything, capture what the UI shows today so the migration can be
checked against it rather than against the plan's table:

```bash
uv run python -c "
import importlib, importlib.metadata as md
for dist in sorted(d.metadata['Name'] for d in md.distributions() if (d.metadata['Name'] or '').startswith('haybale-')):
    m = md.distribution(dist).metadata
    print(f'{dist}: version={m[\"Version\"]!r} summary={m[\"Summary\"]!r} kw={m[\"Keywords\"]!r} author={m[\"Author\"]!r}')
" | tee /tmp/before-migration.txt
```

- [ ] **Step 2: Add the missing `[project]` fields**

For each library, edit `barn/<name>/pyproject.toml`. Add `keywords` and `authors`
where the table above marks them missing, and `[project.urls]` where the decorator
carried a real URL.

`barn/haybale-core/pyproject.toml` — it already has `keywords` and `authors`, so
only the URLs are new:

```toml
[project.urls]
Homepage = "https://github.com/going-haywire/haywire"
Author = "https://maybites.ch"
```

`barn/haybale-graph-editor/pyproject.toml` — nothing to preserve but the tag:

```toml
keywords = ["graph-editor"]
authors = [{ name = "Haywire Team" }]
```

Apply the same shape to `haystack` (`["graph-management"]`), `marketplace`
(`["marketplace"]`), `share` (`["publishing"]`), `studio`
(`["experimental", "project-local"]`).

`barn/haybale-TEST_A` and `barn/haybale-testing` — both carry the repo URL for
`url` and `author_url`, which is right for `Homepage` but wrong for `Author` (it
points at the repo, not a person). Take only:

```toml
[project.urls]
Homepage = "https://github.com/going-haywire/haywire"
```

`barn/haybale-example` — **drop all three URL values.**
`https://author_url` is a placeholder and `https://github.com/author/haywire_library`
is fictional. Publishing either would give consumers a dead link. Add no
`[project.urls]`; the example library is a template, and an absent section is a
better template than a fake one.

`barn/haybale-visiongraph` — keep the two real author names, drop the placeholder
`author_url`. Confirm the `url` resolves before adding it as `Homepage`; if it
404s, omit it.

```toml
[[project.authors]]
name = "Florian Briggisser"

[[project.authors]]
name = "Martin Fröhlich"
```

Where a library's existing pyproject `description` differs from its decorator's,
**pyproject wins** — it is what publishes, and it is what the identity already
reads. Note `haybale-core`'s decorator says "Fundamental components for hayire
graphs" (with the typo); its pyproject says "Haywire's core library with types,
nodes, widgets, and renderers". Keep the pyproject text.

- [ ] **Step 3: Strip the decorators**

For each `barn/*/[a-z_]*/__init__.py`, delete these lines from `@library(...)`:

```python
    version=_pkg_version("haybale-…"),
    description="…",
    url="…",
    author="…",
    author_url="…",
    tags=[…],
```

and rename the remaining one:

```python
    dependencies=[…],   ->   linked_libraries=[…],
```

Then remove the now-unused import:

```python
from importlib.metadata import version as _pkg_version
```

Check it is unused first — some libraries may call `_pkg_version` elsewhere:

```bash
grep -n "_pkg_version" barn/*/[a-z_]*/__init__.py
```

What remains is `id`, `label`, `linked_libraries`, `file_watcher`, plus
`on_reload`/`os`/`examples_path`/`tests_path` where declared. `haybale-core`
becomes:

```python
@library(
    id="core",
    label="Core",
    linked_libraries=[],
    file_watcher=True,
)
class Library(BaseLibrary):
```

- [ ] **Step 4: Re-sync so the metadata reaches the identity**

```bash
uv sync
```

Editing `pyproject.toml` does not change what a running process reports —
`importlib.metadata` reads `site-packages/<dist>.dist-info/METADATA`, written at
install time. Without this the next step compares against stale metadata and
proves nothing.

- [ ] **Step 5: Verify nothing was lost**

```bash
uv run python -c "
import importlib.metadata as md
for dist in sorted(d.metadata['Name'] for d in md.distributions() if (d.metadata['Name'] or '').startswith('haybale-')):
    m = md.distribution(dist).metadata
    print(f'{dist}: version={m[\"Version\"]!r} summary={m[\"Summary\"]!r} kw={m[\"Keywords\"]!r} author={m[\"Author\"]!r} urls={m.get_all(\"Project-URL\")}')
"
```

Compare against `/tmp/before-migration.txt`. Expected differences: `Keywords` and
`Author` now populated for the five libraries that lacked them, `Project-URL`
populated where added. **No field should become empty that was populated before.**

Then check the identities agree:

```bash
uv run python -c "
from haywire.core.library.registry import LibraryRegistry
" 2>/dev/null || echo "(registry import needs DI — check via the studio instead)"
```

If the registry cannot be constructed standalone, verify through the test suite in
Step 6 instead; do not skip the check.

- [ ] **Step 6: Run the full gate**

```bash
uv run pytest -m "not browser and not perf" -q > /tmp/task1.log 2>&1; echo "exit=$?"
grep -E "^FAILED|^ERROR" /tmp/task1.log | head -20
```

Expected: `exit=0`. A test asserting a specific `identity.description` or
`identity.tags` for a barn library may now see the pyproject text instead of the
decorator's — check which is correct before editing the test. Per
`.insights/feedback_barn_module_reload_test_trap.md`, watch for
`assert Foo is Foo` failures from stale top-level imports.

- [ ] **Step 7: Lint, format, type-check**

```bash
uv run ruff check packages/ barn/ tests/
uv run ruff format --check packages/ barn/ tests/
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-TEST_A/haybale_test_a/ tests/
```

Expected: clean.

- [ ] **Step 8: Regenerate the library docs**

```bash
uv run haywire docs --all
```

Per `.insights/project_docs_gen_reentrancy.md`, this **must** be the CLI, never
called in-process — `generate_docs()` builds a second library system that
repoints the global injector and instantiates every node.

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "refactor(barn)!: move library metadata to pyproject.toml

All ten libraries drop version/description/url/author/author_url/tags from
@library and declare them in [project] and [project.urls]. dependencies=
becomes linked_libraries=.

Values with no pyproject home were migrated first, so nothing is lost. Three
placeholder URLs were dropped rather than migrated: https://author_url appears
in two libraries and github.com/author/haywire_library is fictional — publishing
either would hand consumers a dead link.

haybale-core's decorator description ('Fundamental components for hayire
graphs', with the typo) is superseded by its pyproject text, which is what
already published and what the identity already read.

ADR 0024."
```

---

### Task 2: Scaffold and rename

New projects must start migrated, and `haywire rename` must stop rewriting fields
that no longer exist.

**Files:**

- Modify: `packages/haywire-studio/src/haywire_studio/init.py:375-384`
- Modify: `packages/haywire-studio/src/haywire_studio/packaging/rename.py:101-134`
- Test: `tests/test_init_scaffolding.py` (extend), `tests/test_rename.py` (extend)

**Interfaces:**

- Consumes: `decorator_io._set_decorator_str_field` (quote-agnostic).
- Produces: a scaffold emitting only current kwargs; `rename` rewriting only
  `label`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_init_scaffolding.py`:

```python
def test_scaffolded_library_uses_the_current_decorator_surface(tmp_path):
    """A new project must not start pre-migration."""
    from haywire.core.publishing.manifest.decorator_ast import read_decorator

    # …call the scaffolder the way the existing tests in this file do…
    init_py = project / "barn" / f"haybale-{name}" / f"haybale_{name}" / "__init__.py"
    source = init_py.read_text()

    for gone in ("version=", "description=", "url=", "author=", "author_url=", "tags="):
        assert gone not in source, gone
    assert "dependencies=" not in source
    assert "linked_libraries=" in source

    got = read_decorator(init_py)
    assert got.id
    assert got.label


def test_scaffolded_pyproject_carries_the_pep621_fields(tmp_path):
    import tomllib

    # …scaffold as above…
    data = tomllib.loads((project / "barn" / f"haybale-{name}" / "pyproject.toml").read_text())
    assert data["project"]["description"]
    assert data["project"]["version"]
```

Append to `tests/test_rename.py` (create if absent):

```python
def test_rename_rewrites_a_double_quoted_label(tmp_path):
    """Regression: rename used single-quote-only regexes, so every rewrite
    silently no-opped against ruff-formatted source — the same defect fixed in
    update_library_identity, missed because rename.py is a separate file."""
    source = '@library(\n    id="old",\n    label="Old Label",\n)\nclass Library: pass\n'
    # …drive rename over a fixture library whose __init__.py holds `source`…
    assert 'label="New Name"' in result
    assert "Old Label" not in result


def test_rename_does_not_write_removed_fields(tmp_path):
    """url and author_url are no longer decorator fields."""
    # …rename a library…
    assert "url=" not in result
    assert "author_url=" not in result
```

Read both test files first and match their existing fixture idiom — they already
scaffold and rename libraries, so reuse those helpers rather than inventing new
ones.

- [ ] **Step 2: Run them to verify they fail**

```bash
uv run pytest tests/test_init_scaffolding.py tests/test_rename.py -v -k "decorator_surface or double_quoted or removed_fields"
```

Expected: FAIL.

- [ ] **Step 3: Fix the scaffold template**

In `packages/haywire-studio/src/haywire_studio/init.py`, the template around line
375 becomes:

```python
@library(
    id='{lib_base}',
    label='{label}',
    linked_libraries=[],
    file_watcher=True,
)
```

Delete the `version=`, `description=`, `url=`, `author=`, `author_url=`, `tags=`
lines and the `from importlib.metadata import version as _pkg_version` import from
the generated source — the scaffolded `pyproject.toml` already carries
`description` and `version` (line ~546).

Check whether the template still needs `id=`; if the scaffolder previously relied
on `id` defaulting to `label`, it must now pass it explicitly — `id` became
required in the distribution plan.

- [ ] **Step 4: Fix `rename.py`**

Lines 101-134 currently compute `label_val`, `url_val`, `author_url_val` and
rewrite all three with single-quote regexes. Two of those fields no longer exist.

Delete `url_val` and `author_url_val` and their `re.sub` calls. Replace the
`label` rewrite with the quote-agnostic helper:

```python
        content = _set_decorator_str_field(content, "label", label_val)
```

importing `_set_decorator_str_field` from `haywire.core.library.decorator_io`.

Check whether `re` is still used in the file before removing its import:

```bash
grep -n "re\.\(sub\|search\|match\|compile\)" packages/haywire-studio/src/haywire_studio/packaging/rename.py
```

Also check whether rename should now rewrite `id=` — a renamed library keeps its
old `id`, which prefixes every component's registry key. That is either a bug or
deliberate; read the surrounding comments before changing it, and if unclear leave
it and note it rather than guessing.

- [ ] **Step 5: Run the tests**

```bash
uv run pytest tests/test_init_scaffolding.py tests/test_rename.py -v
```

Expected: all pass.

- [ ] **Step 6: Run the full gate**

```bash
uv run pytest -m "not browser and not perf" -q > /tmp/task2.log 2>&1; echo "exit=$?"
grep -E "^FAILED|^ERROR" /tmp/task2.log | head -20
```

Expected: `exit=0`.

- [ ] **Step 7: Lint, format, type-check**

```bash
uv run ruff check packages/ barn/ tests/
uv run ruff format --check packages/ barn/ tests/
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-TEST_A/haybale_test_a/ tests/
```

Expected: clean.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "fix(studio): scaffold and rename use the current decorator surface

The scaffold emitted all six superseded kwargs, so every project created today
started pre-migration.

rename.py rewrote label, url and author_url with single-quote-only regexes —
the same defect fixed in update_library_identity, missed because rename.py is a
separate file. Every barn library is ruff-formatted to double quotes, so all
three silently no-opped. url and author_url are no longer decorator fields at
all; label moves to the quote-agnostic helper.

ADR 0024."
```

---

### Task 3: Delete the transitional shims

Nothing passes the old spellings any more, so the code accepting them goes.

**Files:**

- Modify: `packages/haywire-core/src/haywire/core/library/decorator.py:22,112-118`
- Modify: `packages/haywire-core/src/haywire/core/publishing/manifest/decorator_ast.py`
- Modify: `packages/haywire-core/src/haywire/core/publishing/marketstall.py:110-119`

**Interfaces:**

- Consumes: Task 1's migrated libraries.
- Produces: `@library(version=...)` raises `TypeError`; `dependencies=` is no
  longer read; `[tool.haywire].os` is no longer consulted.

- [ ] **Step 1: Prove nothing still uses them**

```bash
grep -rn "dependencies=" --include="*.py" barn/*/[a-z_]*/__init__.py
grep -rn "tool.haywire" --include="*.toml" barn/
grep -rn "version=\|description=\|author=\|author_url=\|url=\|tags=" --include="*.py" barn/*/[a-z_]*/__init__.py
```

Expected: no output from all three. If the third prints a `url=` inside a
component decorator (`@node`, `@editor`), that is a different decorator — narrow
the grep to the `@library(` block before concluding.

- [ ] **Step 2: Write the failing test**

Append to `tests/core/test_library/test_decorator_distmeta.py`:

```python
def test_superseded_kwargs_now_raise(monkeypatch):
    """Accepted-and-ignored was a migration affordance. With every library
    migrated, silently dropping a kwarg would hide a real authoring mistake."""
    import haywire.core.library.decorator as dec

    monkeypatch.setattr(dec, "_dist_for_module", lambda _m: "haybale-core")
    with pytest.raises(TypeError):

        @dec.library(id="x", label="X", version="9.9.9")
        class _Lib(BaseLibrary):
            pass


def test_dependencies_kwarg_now_raises(monkeypatch):
    import haywire.core.library.decorator as dec

    monkeypatch.setattr(dec, "_dist_for_module", lambda _m: "haybale-core")
    with pytest.raises(TypeError):

        @dec.library(id="x", label="X", dependencies=["haybale_core"])
        class _Lib(BaseLibrary):
            pass
```

- [ ] **Step 3: Run it to verify it fails**

Run: `uv run pytest tests/core/test_library/test_decorator_distmeta.py -v -k "now_raise"`

Expected: FAIL — the kwargs are silently dropped, so no `TypeError`.

- [ ] **Step 4: Delete the decorator shims**

In `packages/haywire-core/src/haywire/core/library/decorator.py`, delete
`_SUPERSEDED_KWARGS` (line 22), the loop that pops it (~line 116), and the
`dependencies` → `linked_libraries` rename (~line 112). `LibraryIdentity(**kwargs)`
then raises `TypeError` on an unknown kwarg, which is the desired behavior.

Update the docstring: the "**Not decorator arguments**" paragraph explaining that
the six are accepted and ignored must now say they are rejected, and keep the
`[project]` example — it is the authoring guide.

- [ ] **Step 5: Delete the AST reader's fallback**

In `decorator_ast.py`, the `linked_libraries` read falls back to `dependencies`:

```python
    linked = _list("linked_libraries") or _list("dependencies")
```

becomes:

```python
    linked = _list("linked_libraries")
```

Delete the accompanying comment and the
`test_legacy_dependencies_keyword_is_read` test — it pins behavior being removed.

- [ ] **Step 6: Delete the `[tool.haywire].os` fallback**

In `publishing/marketstall.py`, remove:

```python
    if not os_decl:
        os_decl = data.get("tool", {}).get("haywire", {}).get("os") or []
```

and the comment naming step 10. Check whether `data` is still used afterwards; if
`read_manifest`'s result is now unused, that is a larger removal — `os_field.py`
and the `strip_os` precondition also read `[tool.haywire].os`. **Leave those:**
`strip_os` repairs a fault in a library that still declares the key, and removing
the repair path before every third-party library has migrated would strand them.
Note it as follow-up rather than widening this task.

- [ ] **Step 7: Run the tests**

```bash
uv run pytest tests/core/test_library/ tests/core/test_publishing/ tests/share_pipeline/ -q
```

Expected: all pass, plus the two new `TypeError` tests.

- [ ] **Step 8: Run the full gate**

```bash
uv run pytest -m "not browser and not perf" -q > /tmp/task3.log 2>&1; echo "exit=$?"
grep -E "^FAILED|^ERROR" /tmp/task3.log | head -20
```

Expected: `exit=0`. A `TypeError: __init__() got an unexpected keyword argument`
from a **test fixture** library means that fixture still uses the old surface —
migrate it; it is the same change Task 1 made to the real libraries.

- [ ] **Step 9: Lint, format, type-check**

```bash
uv run ruff check packages/ barn/ tests/
uv run ruff format --check packages/ barn/ tests/
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-TEST_A/haybale_test_a/ tests/
```

Expected: clean.

- [ ] **Step 10: Commit**

```bash
git add -A
git commit -m "refactor(library)!: delete the migration shims

Every library is migrated, so the code accepting both spellings goes:
_SUPERSEDED_KWARGS, the dependencies -> linked_libraries rename, the AST
reader's dependencies fallback, and the marketstall producer's
[tool.haywire].os fallback.

BREAKING CHANGE: @library() now raises TypeError for version, description,
author, author_url, url, tags and dependencies. Accepted-and-ignored was a
migration affordance; with the migration done, silently dropping a kwarg would
hide a real authoring mistake.

strip_os and its precondition stay — they repair a library that still declares
[tool.haywire].os, and third-party libraries have not migrated.

ADR 0024."
```

---

### Task 4: Documentation

**Files:**

- Modify: `docs/haybale/library-canon.md`
- Modify: `docs/haybale/haybale-package-canon.md`
- Modify: `.insights/project_library_dependencies_use_package_names.md`
- Modify: `docs/architecture/sharing/*.md` where they describe row fields

- [ ] **Step 1: Find every stale reference**

```bash
grep -rn "@library(" docs/ .insights/ | head -30
grep -rn "help_url\|author_url=\|source_url\|docs_url\|examples_url\|dependencies=" docs/ .insights/ | head -30
```

- [ ] **Step 2: Rewrite the authoring guide**

`docs/haybale/library-canon.md` must show the current surface — the rule is
**standard packaging → `[project]`, everything Haywire → the decorator**:

````markdown
```toml
[project]
name = "haybale-mylib"
version = "0.1.0"
description = "What this library does"
keywords = ["mylib"]
authors = [{ name = "Your Name" }]

[project.urls]
Homepage = "https://github.com/you/yourrepo"
Documentation = "https://you.github.io/yourrepo/"
Author = "https://your.site"
Issues = "https://github.com/you/yourrepo/issues"
```

```python
@library(
    id="mylib",
    label="My Library",
    linked_libraries=["haybale_core"],
    on_reload="none",
    os=["macos", "linux"],
    examples_path="examples/OVERVIEW.md",
    file_watcher=True,
)
class Library(BaseLibrary): ...
```
````

State why: `version`/`description`/`authors`/`keywords`/URLs are read from the
installed distribution's metadata, so authoring them twice is what let them drift.

- [ ] **Step 3: Retitle the dependencies insight**

`.insights/project_library_dependencies_use_package_names.md` documents the
`dependencies=` trap. The field is now `linked_libraries`, and the collision it
warned about is gone by construction. Either retitle it for `linked_libraries`
(module names, still required for hot-reload) or delete it and add a one-line
entry to `CLAUDE.md`'s trap list. Update the `CLAUDE.md` entry either way.

- [ ] **Step 4: Verify the docs build**

```bash
uv run mkdocs build 2>&1 | tail -5
```

Expected: no broken-link warnings for pages this task touched.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "docs: library authoring reflects the consolidated surface

Standard packaging goes in [project], everything Haywire in the decorator.
Documents why: the PEP 621 half is read from installed distribution metadata,
so authoring it twice is what let it drift.

ADR 0024."
```

---

## Self-Review

**Spec coverage.** This plan implements migration **step 10**, the last. After it
lands, ADR 0024 is fully realized: one source per field, one reader, one editing
surface, coordinate-based rows.

**Ordering is load-bearing.** Task 1 migrates values *before* Task 3 deletes the
kwargs that carry them. Reversed, five libraries' `tags` and three libraries'
author names would be destroyed — and because the identity reads distribution
metadata, the loss would be silent until someone opened the UI.

**Two live bugs found while verifying, both fixed here.** `rename.py`'s
single-quote regexes are the same defect the foundation plan fixed in
`library_manager` — missed because it is a separate file, and *still* missed by
every plan since. The scaffold emitting all six superseded kwargs means every
project created since the distribution plan started pre-migration.

**Three placeholder URLs are dropped, not migrated.** `https://author_url` in two
libraries and `github.com/author/haywire_library` in a third are fictional.
Migrating them would publish dead links to consumers; an absent `[project.urls]`
is the honest answer, and for the example library a better template.

**What stays behind deliberately.** `strip_os` and its precondition keep reading
`[tool.haywire].os`. They repair a library that still declares the key, and
third-party libraries have not migrated — removing the repair path would strand
them with an unfixable fault. Task 3 Step 6 says so rather than widening.

**Three risks worth naming.**

1. **`uv sync` between Steps 3 and 5 is not optional.** Skipping it means Step 5
   compares against stale `METADATA` and "proves" a migration that has not taken
   effect. Same trap as `.insights/project_stale_version_diagnosis.md`.
2. **`haybale-visiongraph` is a gitignored symlink** excluded from mypy. It must
   still be migrated or its identity loses `tags` and both author names — but a
   failure there must not block the other nine. Migrate it, verify separately.
3. **Task 3's `TypeError` will surface test fixtures.** Any fixture library still
   using the old surface fails loudly rather than silently — which is the point,
   but it means Task 3's gate run may touch more files than the task's own list.
   The failures name their files; migrate them the same way.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-09-library-metadata-author-migration.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
