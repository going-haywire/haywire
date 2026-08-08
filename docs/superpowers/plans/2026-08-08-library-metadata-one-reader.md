# One Decorator Reader, One Generator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One reader for the `@library(...)` decorator, and one path from source to
a marketstall row. Today there are five reader call sites across four modules, two
of them regex, and two independent generators that disagree about where a row's
fields come from.

**Architecture:** Promote the AST reader out of `scripts/generate_marketstall.py`
into `haywire.core.publishing`, widened to every decorator field a row needs. Both
producers then build a `Haybale` through `LibraryMetadata` instead of assembling
dicts by hand, which also fixes the two places the CI generator contradicts the
share pipeline.

**Tech Stack:** Python 3.12, `ast`, dataclasses, pytest.

## Global Constraints

- Line length 109 (`uv run ruff check .` **and** `uv run ruff format --check .` — CI runs both).
- Type-check with the exact command in `CLAUDE.md`; `haybale-visiongraph` is excluded.
- Gate before every commit: `uv run pytest -m "not browser and not perf"` (~2.5 min).
- Never call `create_test_injector()` directly in a test — use the `test_injector` fixtures.
- Barn `__init__.py` files use **double quotes**; any regex touching decorator
  source must be quote-agnostic. The AST reader is immune to this by construction.
- **Readers parse; writers rewrite.** The regex *writers* in `decorator_io` stay —
  they edit source text in place and an AST round-trip would reformat the file.

## Predecessors

Both landed:

- [2026-08-08-library-metadata-foundation.md](2026-08-08-library-metadata-foundation.md) —
  `LibraryMetadata` base; rows carry coordinates (`origin` + `install_spec` +
  `*_path`) resolved through `HostProvider`.
- [2026-08-08-library-metadata-distribution.md](2026-08-08-library-metadata-distribution.md) —
  the decorator reads PEP 621 fields from installed distribution metadata;
  `version`/`description`/`author`/`author_url`/`url`/`tags` are no longer kwargs;
  `os`/`examples_path`/`tests_path` became kwargs; `id` is required;
  `LibraryIdentity.url`/`.author` deleted.

`LibraryIdentity` now adds exactly `id`, `folder_path`, `module_name`,
`file_watcher` to the base — verified on disk.

## Verified starting state

Confirmed 2026-08-08, not assumed.

**Five decorator-reader call sites, four modules:**

| reader | kind | callers |
| --- | --- | --- |
| `manifest/deps._read_library_label` | regex | `publishing/marketstall.py:96` |
| `manifest/deps._read_library_dependencies` | regex | `publishing/marketstall.py:97`, `drift/detect.py:68`, `studio/init.py:504` |
| `decorator_io._get_decorator_list_field` | regex | `publishing/marketstall.py:118` (`os`) |
| `decorator_io._get_decorator_str_field` | regex | `publishing/marketstall.py:143-144` (paths) |
| `scripts/generate_marketstall.extract_library_metadata` | **AST** | `generate_marketstall.py:152` |

The AST one reads only `label`/`description`/`author`/`tags` and returns `None` per
field when unauthored. `_as_str` and `_as_str_list` are its literal extractors.

**Two live divergences in `generate_marketstall.build_entry`** (lines 160-190):

1. `linked_libraries` is filled from `_filter_haybale_siblings(pyproject_deps)` —
   pyproject's `haybale-*` dependencies — while the share pipeline reads the
   decorator's `linked_libraries`. Different inputs, same field.
2. `description`, `tags` and `author` prefer the **decorator** over pyproject
   (`meta.description or pyproject_description`). Since the distribution plan
   landed, the decorator no longer accepts those kwargs at all, so `meta.*` is
   now always `None` for a migrated library and the fallback silently carries
   everything. For an unmigrated library it still wins — the reverse of the
   ADR's precedence.

**`_get_decorator_list_field` converts `_` → `-` on every value.** It was written
for dependency names. `publishing/marketstall.py:111-118` already works around this
for `os` by filtering against `_DECLARABLE_OS_VALUES`. The AST reader must not
inherit the conversion.

**`drift/detect.py` normalizes both sides** through `_norm_dep` before comparing,
so the pip-form conversion is incidental there — switching it to module names is
safe.

## Out of scope — the remaining plans

- **step 6: declared-path preconditions.** A declared `examples_path`/`tests_path`
  that does not exist fails `check_preconditions` with a `fix_id`.
- **step 8: metadata editing moves into the Share flow.** Deletes
  `_overview_edit_dialog.py` and `update_library_identity` — and with them the
  quote-bug fix from the foundation plan, which was temporary by design.
- **step 10: author-facing migration.** The 10 barn libraries, the `haywire init`
  scaffold, `haywire rename`, docs.

## File Structure

| File | Responsibility |
| --- | --- |
| `packages/haywire-core/src/haywire/core/publishing/manifest/decorator_ast.py` | **new** — the one AST reader |
| `packages/haywire-core/src/haywire/core/publishing/manifest/deps.py` | **deleted** — both regex readers go |
| `packages/haywire-core/src/haywire/core/publishing/marketstall.py` | four reads become one |
| `packages/haywire-core/src/haywire/core/publishing/drift/detect.py` | reads module names |
| `packages/haywire-studio/src/haywire_studio/init.py` | follows the reader move |
| `scripts/generate_marketstall.py` | builds a `Haybale`; two divergences fixed |
| `tests/core/test_publishing/test_decorator_ast.py` | **new** |

---

### Task 1: The one AST reader

**Files:**

- Create: `packages/haywire-core/src/haywire/core/publishing/manifest/decorator_ast.py`
- Test: `tests/core/test_publishing/test_decorator_ast.py` (create)

**Interfaces:**

- Consumes: nothing from earlier tasks.
- Produces:
  - `DecoratorFields` — frozen dataclass: `id: str`, `label: str`,
    `linked_libraries: list[str]`, `on_reload: str`, `os: list[str]`,
    `examples_path: str`, `tests_path: str`, `file_watcher: bool`.
  - `read_decorator(init_py: Path) -> DecoratorFields` — all-default when the
    file is missing or has no `@library(...)`.

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_publishing/test_decorator_ast.py`:

```python
"""The single reader for @library(...) source.

AST, not regex: the regex readers this replaces could be defeated by quoting
(the foundation plan shipped a fix for exactly that bug), and one of them
converted `_` to `-` on every list value because it was written for dependency
names.
"""

from pathlib import Path

import pytest

from haywire.core.publishing.manifest.decorator_ast import DecoratorFields, read_decorator

FULL = '''from haywire.core.library.decorator import library


@library(
    id="core",
    label="Core",
    linked_libraries=["haybale_studio", "haybale_graph_editor"],
    on_reload="restart",
    os=["macos", "linux"],
    examples_path="examples/OVERVIEW.md",
    tests_path="tests/",
    file_watcher=True,
)
class Library:
    pass
'''

MINIMAL = '''from haywire.core.library.decorator import library


@library(id="min", label="Min")
class Library:
    pass
'''


def _write(tmp_path: Path, source: str) -> Path:
    init_py = tmp_path / "__init__.py"
    init_py.write_text(source)
    return init_py


def test_reads_every_field(tmp_path):
    got = read_decorator(_write(tmp_path, FULL))
    assert got == DecoratorFields(
        id="core",
        label="Core",
        linked_libraries=["haybale_studio", "haybale_graph_editor"],
        on_reload="restart",
        os=["macos", "linux"],
        examples_path="examples/OVERVIEW.md",
        tests_path="tests/",
        file_watcher=True,
    )


def test_unauthored_fields_take_defaults(tmp_path):
    got = read_decorator(_write(tmp_path, MINIMAL))
    assert got.id == "min"
    assert got.label == "Min"
    assert got.linked_libraries == []
    assert got.on_reload == "none"
    assert got.os == []
    assert got.examples_path == ""
    assert got.file_watcher is False


def test_module_names_are_not_converted_to_pip_names(tmp_path):
    """The regex reader this replaces did `_` -> `-`; module names are authoritative."""
    got = read_decorator(_write(tmp_path, FULL))
    assert got.linked_libraries == ["haybale_studio", "haybale_graph_editor"]


def test_underscored_values_survive(tmp_path):
    """The old converter silently mangled any value containing an underscore."""
    source = '@library(id="x", label="X", os=["mac_os"])\nclass Library: pass\n'
    assert read_decorator(_write(tmp_path, source)).os == ["mac_os"]


@pytest.mark.parametrize("quote", ["'", '"'])
def test_both_quote_styles(tmp_path, quote):
    source = f"@library(id={quote}q{quote}, label={quote}Q{quote})\nclass Library: pass\n"
    assert read_decorator(_write(tmp_path, source)).label == "Q"


def test_missing_file_yields_defaults(tmp_path):
    assert read_decorator(tmp_path / "nope.py") == DecoratorFields()


def test_file_without_a_decorator_yields_defaults(tmp_path):
    """Framework packages have no Library class; that is not an error."""
    assert read_decorator(_write(tmp_path, "x = 1\n")) == DecoratorFields()


def test_unparseable_file_yields_defaults(tmp_path):
    """A syntax error in a library must not crash a read-only report."""
    assert read_decorator(_write(tmp_path, "def (\n")) == DecoratorFields()


def test_non_literal_values_are_skipped_not_guessed(tmp_path):
    """A computed value cannot be read statically; report absent, never wrong."""
    source = (
        "@library(id=NAME, label=_compute(), linked_libraries=[*OTHERS])\n"
        "class Library: pass\n"
    )
    got = read_decorator(_write(tmp_path, source))
    assert got.id == ""
    assert got.label == ""
    assert got.linked_libraries == []


def test_decorated_class_found_below_other_statements(tmp_path):
    source = "import os\n\nCONST = 1\n\n\n@library(id='deep', label='Deep')\nclass Library: pass\n"
    assert read_decorator(_write(tmp_path, source)).id == "deep"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/core/test_publishing/test_decorator_ast.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named
'haywire.core.publishing.manifest.decorator_ast'`.

If `tests/core/test_publishing/` does not exist, create it; no `__init__.py` is
needed.

- [ ] **Step 3: Write the reader**

Create `packages/haywire-core/src/haywire/core/publishing/manifest/decorator_ast.py`:

```python
"""Read `@library(...)` fields out of a library's source, without importing it.

`haywire share` and the CI feed generator both run against a checkout where
nothing is installed, so they cannot read `cls.class_identity`. They parse the
source instead — and they parse it *here*, once.

AST rather than regex, for two reasons the regex readers this replaces
demonstrated: a pattern anchored on one quote style silently no-ops against the
other (barn libraries are `ruff format`ted to double quotes), and the list
reader converted `_` to `-` on every value because it was written for dependency
names, which quietly mangles anything else.

Only literal values are readable. A computed one is reported absent rather than
guessed: an absent field is a state every caller already handles, whereas a
wrong one propagates into a published feed.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class DecoratorFields:
    """What `@library(...)` declares. Defaults mirror the decorator's own."""

    id: str = ""
    label: str = ""
    linked_libraries: list[str] = field(default_factory=list)
    on_reload: str = "none"
    os: list[str] = field(default_factory=list)
    examples_path: str = ""
    tests_path: str = ""
    file_watcher: bool = False


def _as_str(node: ast.expr | None) -> str | None:
    """The string literal's value, or None for anything non-literal."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _as_str_list(node: ast.expr | None) -> list[str] | None:
    """A list of string literals, or None if any element is not one."""
    if not isinstance(node, ast.List):
        return None
    out: list[str] = []
    for element in node.elts:
        value = _as_str(element)
        if value is None:
            return None
        out.append(value)
    return out


def _as_bool(node: ast.expr | None) -> bool | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, bool):
        return node.value
    return None


def _library_call(tree: ast.Module) -> ast.Call | None:
    """The first `@library(...)` call decorating a class, or None."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            func = decorator.func
            if isinstance(func, ast.Name) and func.id == "library":
                return decorator
    return None


def read_decorator(init_py: Path) -> DecoratorFields:
    """Read *init_py*'s `@library(...)` declaration.

    Returns all-defaults when the file is missing, unparseable, or has no
    decorated class — a framework package has no `Library` class, and a
    read-only drift report must not crash on a library with a syntax error.
    """
    try:
        source = init_py.read_text(encoding="utf-8")
    except OSError:
        return DecoratorFields()

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return DecoratorFields()

    call = _library_call(tree)
    if call is None:
        return DecoratorFields()

    kwargs = {kw.arg: kw.value for kw in call.keywords if kw.arg is not None}
    defaults = DecoratorFields()

    def _str(name: str, fallback: str) -> str:
        value = _as_str(kwargs.get(name))
        return fallback if value is None else value

    def _list(name: str) -> list[str]:
        value = _as_str_list(kwargs.get(name))
        return [] if value is None else value

    file_watcher = _as_bool(kwargs.get("file_watcher"))

    return DecoratorFields(
        id=_str("id", defaults.id),
        label=_str("label", defaults.label),
        linked_libraries=_list("linked_libraries"),
        on_reload=_str("on_reload", defaults.on_reload),
        os=_list("os"),
        examples_path=_str("examples_path", defaults.examples_path),
        tests_path=_str("tests_path", defaults.tests_path),
        file_watcher=defaults.file_watcher if file_watcher is None else file_watcher,
    )
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/core/test_publishing/test_decorator_ast.py -v`

Expected: all PASS.

- [ ] **Step 5: Handle the unmigrated-library case**

Barn libraries have not been rewritten yet (that is step 10), so they still write
`dependencies=` rather than `linked_libraries=`. Add the same shim the decorator
carries, and a test:

```python
    # Libraries not yet migrated still write `dependencies=`; the decorator
    # carries the same shim. Both go in migration step 10.
    linked = _list("linked_libraries") or _list("dependencies")
```

Append the test:

```python
def test_legacy_dependencies_keyword_is_read(tmp_path):
    """Unmigrated libraries still write `dependencies=`; step 10 rewrites them."""
    source = '@library(id="x", label="X", dependencies=["haybale_core"])\nclass Library: pass\n'
    assert read_decorator(_write(tmp_path, source)).linked_libraries == ["haybale_core"]
```

Run: `uv run pytest tests/core/test_publishing/test_decorator_ast.py -v`

Expected: all PASS.

- [ ] **Step 6: Lint, format, type-check**

```bash
uv run ruff check packages/haywire-core/src/haywire/core/publishing/ tests/core/test_publishing/
uv run ruff format --check packages/haywire-core/src/haywire/core/publishing/ tests/core/test_publishing/
uv run mypy packages/haywire-core/src/
```

Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add packages/haywire-core/src/haywire/core/publishing/manifest/decorator_ast.py \
        tests/core/test_publishing/test_decorator_ast.py
git commit -m "feat(publishing): one AST reader for the @library decorator

No callers yet. AST rather than regex because the readers it will replace could
be defeated by quoting — the foundation plan shipped a fix for exactly that —
and because the list reader converted _ to - on every value, having been written
for dependency names.

Non-literal values report absent rather than guessed: an absent field is a state
every caller handles, a wrong one reaches a published feed.

ADR 0024."
```

---

### Task 2: Route the share pipeline through it

Four reads in `publishing/marketstall.py` collapse to one, and `deps.py` loses
both its readers.

**Files:**

- Modify: `packages/haywire-core/src/haywire/core/publishing/marketstall.py:14-20,96-97,111-118,143-144`
- Modify: `packages/haywire-core/src/haywire/core/publishing/drift/detect.py:26,68,82`
- Modify: `packages/haywire-studio/src/haywire_studio/init.py:482,504`
- Modify: `packages/haywire-core/src/haywire/core/publishing/__init__.py:26,64`
- Delete: `packages/haywire-core/src/haywire/core/publishing/manifest/deps.py`

**Interfaces:**

- Consumes: `read_decorator(init_py) -> DecoratorFields` from Task 1.
- Produces: no new API; `_read_library_label` and `_read_library_dependencies`
  cease to exist.

- [ ] **Step 1: Confirm the caller list is still what the plan says**

```bash
grep -rn "_read_library_label\|_read_library_dependencies" --include="*.py" packages/ barn/ scripts/ tests/
```

Expected: `marketstall.py` (2), `drift/detect.py` (1), `studio/init.py` (1),
`publishing/__init__.py` (2 export lines), plus any tests. If a caller appears
that this plan does not name, handle it in this task and note it.

- [ ] **Step 2: Rewrite `marketstall.py`'s reads**

Replace the imports:

```python
from haywire.core.publishing.manifest.decorator_ast import read_decorator
```

removing the `decorator_io` and `manifest.deps` imports. Then replace the four
read sites with a single call near the top of `_build_entry_for_library`, after
`module_dir` is resolved:

```python
    decorator = read_decorator(module_dir / "__init__.py") if module_dir else DecoratorFields()

    label = decorator.label or label_fallback
    linked_libraries = decorator.linked_libraries
    os_decl = [v for v in decorator.os if v in _DECLARABLE_OS_VALUES]
```

and further down, where the paths are prefixed:

```python
    examples_path = _declared_path(decorator.examples_path)
    tests_path = _declared_path(decorator.tests_path)
```

Delete the `init_source = ...` read and the comment explaining the `_` → `-`
workaround — the AST reader does not convert, so the filter against
`_DECLARABLE_OS_VALUES` is now plain validation rather than damage control. Say
so:

```python
    # Validation, not workaround: an unknown platform string is dropped rather
    # than published. (The regex reader this replaced also mangled underscores.)
```

Import `DecoratorFields` alongside `read_decorator`.

- [ ] **Step 3: Point `drift/detect.py` at the reader**

Replace the import and the call:

```python
from haywire.core.publishing.manifest.decorator_ast import read_decorator
...
    declared_decorator: list[str] = []
    if module_dir:
        declared_decorator = read_decorator(module_dir / "__init__.py").linked_libraries
```

The comment at line 82 says `_read_library_dependencies` "already converts to
pip-package form". That is no longer true — update it:

```python
    # Both sides are normalized before comparing, so decorator module names
    # ("haybale_core") and detected pip names ("haybale-core") compare equal.
```

The `_norm_dep` normalization on both sides already handles the difference —
verified — so no behavior changes here.

- [ ] **Step 4: Point `studio/init.py` at the reader**

Replace the local import and call at lines 482 and 504:

```python
        from haywire.core.publishing.manifest.decorator_ast import read_decorator
...
        dependencies = read_decorator(module_dir / "__init__.py").linked_libraries if module_dir else []
```

Read the surrounding comment first — it explains that this keeps the scaffold's
decorator and pyproject deps in sync. If it names `_read_library_dependencies`,
update the name.

- [ ] **Step 5: Delete `deps.py` and its exports**

```bash
rm packages/haywire-core/src/haywire/core/publishing/manifest/deps.py
```

Remove from `packages/haywire-core/src/haywire/core/publishing/__init__.py` both
the import (line ~26) and the `__all__` entry (line ~64).

- [ ] **Step 6: Verify nothing still references it**

```bash
grep -rn "manifest.deps\|_read_library_label\|_read_library_dependencies" --include="*.py" packages/ barn/ scripts/ tests/
```

Expected: no output.

- [ ] **Step 7: Run the affected suites**

```bash
uv run pytest tests/test_share_marketstall_write.py tests/test_share_drift.py tests/test_init_scaffolding.py tests/test_dep_detect.py -q
```

Expected: all pass. A failure naming a pip-form dependency (`haybale-core` where
`haybale_core` is now returned) is a test asserting the old converter's output —
update the expectation, since module names are the authored form.

- [ ] **Step 8: Run the full gate**

```bash
uv run pytest -m "not browser and not perf" -q > /tmp/task2.log 2>&1; echo "exit=$?"
grep -E "^FAILED|^ERROR" /tmp/task2.log | head -20
```

Expected: `exit=0`, no FAILED lines.

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
git commit -m "refactor(publishing): one decorator reader for the share pipeline

Four reads in _build_entry_for_library — two regex helpers plus label and
dependency readers — collapse to a single read_decorator() call. deps.py is
deleted; drift detection and the init scaffold follow.

Decorator lists now arrive as authored module names rather than pip names. The
drift detector normalizes both sides before comparing, so this changes no
behavior there; it removes a conversion that silently mangled any value with an
underscore.

ADR 0024."
```

---

### Task 3: The CI generator builds a `Haybale`

`scripts/generate_marketstall.py` assembles a row dict by hand and disagrees with
the share pipeline in two places. Both go.

**Files:**

- Modify: `scripts/generate_marketstall.py:36-95,152,160-200`
- Test: `tests/scripts/test_generate_marketstall.py` (extend)

**Interfaces:**

- Consumes: `read_decorator` from Task 1; `Haybale` and `LibraryMetadata`.
- Produces: `build_entry` returning `Haybale(...).to_dict()`.

- [ ] **Step 1: Write the failing test**

Append to `tests/scripts/test_generate_marketstall.py`:

```python
def test_linked_libraries_come_from_the_decorator_not_pyproject(tmp_path):
    """The CI generator used to fill this from pyproject's haybale-* deps.

    The share pipeline reads the decorator. Same field, two inputs — a
    divergence that only showed up when comparing published feeds.
    """
    from scripts.generate_marketstall import build_entry, MarketstallConfig

    lib = tmp_path / "barn" / "haybale-demo"
    (lib / "haybale_demo").mkdir(parents=True)
    (lib / "pyproject.toml").write_text(
        '[project]\nname = "haybale-demo"\nversion = "0.1.0"\n'
        'description = "From pyproject"\n'
        'dependencies = ["haybale-other>=1.0", "haywire-core>=0.0.40"]\n'
    )
    (lib / "haybale_demo" / "__init__.py").write_text(
        '@library(\n    id="demo",\n    label="Demo",\n'
        '    linked_libraries=["haybale_studio"],\n)\nclass Library: ...\n'
    )

    entry = build_entry(
        lib / "pyproject.toml",
        lib / "haybale_demo" / "__init__.py",
        MarketstallConfig(source_url="https://github.com/o/r", docs_branch="main"),
        "barn/haybale-demo",
        "haybale_demo",
    )

    assert entry["linked_libraries"] == ["haybale_studio"]
    assert "haybale-other" not in entry.get("linked_libraries", [])


def test_description_comes_from_pyproject(tmp_path):
    """Precedence is pyproject, not the decorator — the decorator no longer
    accepts description= at all since the distribution plan landed."""
    from scripts.generate_marketstall import build_entry, MarketstallConfig

    lib = tmp_path / "barn" / "haybale-demo"
    (lib / "haybale_demo").mkdir(parents=True)
    (lib / "pyproject.toml").write_text(
        '[project]\nname = "haybale-demo"\nversion = "0.1.0"\n'
        'description = "From pyproject"\nkeywords = ["a", "b"]\n'
    )
    (lib / "haybale_demo" / "__init__.py").write_text(
        '@library(id="demo", label="Demo")\nclass Library: ...\n'
    )

    entry = build_entry(
        lib / "pyproject.toml",
        lib / "haybale_demo" / "__init__.py",
        MarketstallConfig(source_url="https://github.com/o/r", docs_branch="main"),
        "barn/haybale-demo",
        "haybale_demo",
    )

    assert entry["description"] == "From pyproject"
    assert entry["tags"] == ["a", "b"]


def test_os_and_paths_reach_the_row(tmp_path):
    from scripts.generate_marketstall import build_entry, MarketstallConfig

    lib = tmp_path / "barn" / "haybale-demo"
    (lib / "haybale_demo").mkdir(parents=True)
    (lib / "pyproject.toml").write_text(
        '[project]\nname = "haybale-demo"\nversion = "0.1.0"\n'
    )
    (lib / "haybale_demo" / "__init__.py").write_text(
        '@library(\n    id="demo",\n    label="Demo",\n'
        '    os=["macos"],\n    on_reload="restart",\n'
        '    examples_path="examples/OVERVIEW.md",\n)\nclass Library: ...\n'
    )

    entry = build_entry(
        lib / "pyproject.toml",
        lib / "haybale_demo" / "__init__.py",
        MarketstallConfig(source_url="https://github.com/o/r", docs_branch="main"),
        "barn/haybale-demo",
        "haybale_demo",
    )

    assert entry["os"] == ["macos"]
    assert entry["on_reload"] == "restart"
    assert entry["examples_path"] == "barn/haybale-demo/examples/OVERVIEW.md"
```

Adjust the `MarketstallConfig(...)` constructor calls to that dataclass's real
signature — read it first; it carries `default_author`/`default_tags` fields this
task removes.

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/scripts/test_generate_marketstall.py -v`

Expected: FAIL — `linked_libraries` holds `["haybale-other"]`, and `os`/
`on_reload`/`examples_path` are absent from the row.

- [ ] **Step 3: Replace the local reader with the shared one**

Delete `LibraryMetadata`, `extract_library_metadata`, `_as_str` and `_as_str_list`
from `scripts/generate_marketstall.py` (lines ~36-95) — Task 1's module supersedes
all four. The local `LibraryMetadata` name also collides with
`haywire.core.library.metadata.LibraryMetadata`, which this file now imports
transitively; removing it avoids the ambiguity.

Import instead:

```python
from haywire.core.marketstall.types import Haybale
from haywire.core.publishing.manifest.decorator_ast import read_decorator
```

- [ ] **Step 4: Rewrite `build_entry` to produce a `Haybale`**

```python
    decorator = read_decorator(init_py)

    # Paths are relative to the git root; the consumer resolves them against
    # `origin` at `install_spec`'s ref. Trailing slash marks a directory.
    docs_path = f"{subdirectory}/{module_name}/"

    def _declared(path: str) -> str:
        return f"{subdirectory}/{path.lstrip('/')}" if path else ""

    if source == "git":
        install_spec = f"{name} @ git+{config.source_url}.git#subdirectory={subdirectory}"
    else:
        install_spec = name

    row = Haybale(
        name=name,
        label=decorator.label or name,
        version=version,
        description=pyproject_description,
        authors=pyproject_authors,
        tags=pyproject_keywords or list(config.default_tags),
        linked_libraries=decorator.linked_libraries,
        on_reload=decorator.on_reload,
        os=decorator.os,
        source=source,
        install_spec=install_spec,
        origin=config.source_url,
        docs_path=docs_path,
        examples_path=_declared(decorator.examples_path),
        tests_path=_declared(decorator.tests_path),
    )
    entry = row.to_dict()
    if require is not None:
        entry["require"] = require
    return entry
```

Read `pyproject_authors` and `pyproject_keywords` from the manifest beside the
existing `pyproject_description`:

```python
    pyproject_authors = [a.get("name", "") for a in project.get("authors", []) if a.get("name")]
    pyproject_keywords = list(project.get("keywords", []))
```

`_filter_haybale_siblings` loses its only caller — delete it, and any import it
needed.

`config.default_author` also loses its caller. Leave the field on
`MarketstallConfig` if other code reads it; otherwise remove it and its
`read_marketstall_config` line. Check with:

```bash
grep -n "default_author" scripts/generate_marketstall.py
```

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/scripts/test_generate_marketstall.py -v`

Expected: all PASS. Existing tests asserting `entry["dependencies"]` or
`entry["author"]` are asserting the pre-`LibraryMetadata` row shape — update them
to `linked_libraries` and `authors`.

- [ ] **Step 6: Verify both producers agree**

Add a test that pins the convergence:

```python
def test_both_producers_emit_the_same_row_for_one_library(tmp_path):
    """The share pipeline and the CI generator differ only in documented ways.

    They disagreed on two fields before this plan: linked_libraries came from
    pyproject in one and the decorator in the other, and description/tags
    preferred the decorator in one and pyproject in the other.
    """
    from haywire.core.publishing.marketstall import _build_entry_for_library
    from scripts.generate_marketstall import build_entry, MarketstallConfig

    lib = tmp_path / "barn" / "haybale-demo"
    (lib / "haybale_demo").mkdir(parents=True)
    (lib / "pyproject.toml").write_text(
        '[project]\nname = "haybale-demo"\nversion = "0.1.0"\n'
        'description = "Shared"\nkeywords = ["k"]\n'
    )
    (lib / "haybale_demo" / "__init__.py").write_text(
        '@library(\n    id="demo",\n    label="Demo",\n'
        '    linked_libraries=["haybale_studio"],\n    os=["macos"],\n)\n'
        "class Library: ...\n"
    )

    ci = build_entry(
        lib / "pyproject.toml",
        lib / "haybale_demo" / "__init__.py",
        MarketstallConfig(source_url="https://github.com/o/r", docs_branch="main"),
        "barn/haybale-demo",
        "haybale_demo",
    )
    share = _build_entry_for_library(lib)

    # source and install_spec differ by design: PyPI vs git, and the CI
    # generator resolves refs against a branch because it has no tag context.
    shared = {"label", "version", "description", "tags", "linked_libraries", "os"}
    for key in shared:
        assert ci.get(key) == share.get(key), key
```

If `_build_entry_for_library` returns `None` for a fixture with no git remote,
either initialise one in the fixture or assert only on the CI side and mark the
comparison `xfail` with that reason stated.

- [ ] **Step 7: Run the full gate**

```bash
uv run pytest -m "not browser and not perf" -q > /tmp/task3.log 2>&1; echo "exit=$?"
grep -E "^FAILED|^ERROR" /tmp/task3.log | head -20
```

Expected: `exit=0`, no FAILED lines.

- [ ] **Step 8: Lint, format, type-check**

```bash
uv run ruff check packages/ barn/ scripts/ tests/
uv run ruff format --check packages/ barn/ scripts/ tests/
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-TEST_A/haybale_test_a/ tests/
```

Expected: clean.

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "refactor(scripts): CI generator builds a Haybale through one reader

generate_marketstall assembled a row dict by hand and disagreed with the share
pipeline in two places: linked_libraries came from pyproject's haybale-* deps
rather than the decorator, and description/tags/author preferred the decorator
over pyproject — the reverse of the ADR's precedence, and dead since the
decorator stopped accepting those kwargs.

Both producers now run pyproject + decorator -> LibraryMetadata -> Haybale ->
TOML, and a test pins that they agree on every shared field. What stays
different is documented: PyPI vs git source, and branch- vs tag-based refs,
because CI has no tag context.

Deletes the local extract_library_metadata/_as_str/_as_str_list and
_filter_haybale_siblings.

ADR 0024."
```

---

## Self-Review

**Spec coverage.** This plan implements migration **step 9** in full: one AST
reader, `deps.py` deleted, both producers converged, both divergences fixed.

**What it leaves.** The regex *writers* in `decorator_io`
(`_set_decorator_str_field`, `_set_decorator_list_field`,
`merge_decorator_list_field`) stay — they rewrite source text in place, and an AST
round-trip would reformat the file. `_get_decorator_str_field` and
`_get_decorator_list_field` lose their production callers here; check whether the
writers still use `_get_decorator_list_field` internally
(`decorator_io.py:82` does, inside `merge_decorator_list_field`) before deleting
either.

**Type consistency.** `DecoratorFields` is frozen with `list[str]` for
`linked_libraries` and `os`, `str` for the rest, `bool` for `file_watcher`.
`read_decorator` returns it unconditionally — never `None` — so no caller needs a
guard. `Haybale.to_dict()` omits falsy values, so an unauthored field stays out of
the written feed.

**Three risks worth naming.**

1. **`linked_libraries` becomes module names in the drift detector.** Verified
   safe — `detect.py` normalizes both sides with `_norm_dep` before comparing —
   but the comment there currently asserts the opposite, and a future reader
   trusting it would be misled. Task 2 Step 3 fixes the comment, which matters as
   much as the code.
2. **`scripts/generate_marketstall.py` imports from `haywire.core`.** It already
   imports `haywire_core_requirement`, so the dependency direction is established;
   this plan deepens it. If the script is ever meant to run without the package
   installed, that assumption breaks — worth confirming against
   `.github/workflows/publish.yml` job 4.
3. **The convergence test may not be runnable as written.**
   `_build_entry_for_library` derives `origin` from a git remote, so a `tmp_path`
   fixture with no repo yields `None`. Step 6 says to initialise one or `xfail`
   with the reason stated — do not silently weaken the assertion, since this test
   is the only thing preventing the two generators drifting again.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-08-library-metadata-one-reader.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
