# Library Metadata from Distribution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** End the duplication. `version`, `description`, `authors`, `tags` and the
URLs stop being `@library(...)` kwargs and are read from installed distribution
metadata, so `pyproject.toml` is their single source.

**Architecture:** The decorator populates `LibraryMetadata`'s PEP 621 half from
`importlib.metadata` at decoration time, keyed on the distribution owning the
library's module. Haywire-specific fields it cannot get that way — `os`,
`examples_path`, `tests_path` — become decorator kwargs, which also makes them
survive into an installed wheel. `LibraryIdentity` loses its two transitional
fields (`author`, `url`).

**Tech Stack:** Python 3.12, `importlib.metadata`, `email.utils.getaddresses`,
dataclasses, pytest.

## Global Constraints

- Line length 109 (`uv run ruff check .` **and** `uv run ruff format --check .` — CI runs both).
- Type-check with the exact command in `CLAUDE.md`; `haybale-visiongraph` is excluded.
- Gate before every commit: `uv run pytest -m "not browser and not perf"` (~2.5 min, 3161 tests).
- Never call `create_test_injector()` directly in a test — use the `test_injector` fixtures.
- Barn `__init__.py` files use **double quotes**; any regex touching decorator
  source must be quote-agnostic.
- **No field may be authored in two places**, and no field's name may contradict
  its contents.

## Predecessor

[2026-08-08-library-metadata-foundation.md](2026-08-08-library-metadata-foundation.md) —
**landed** (commits `bc59f254`, `a082908f`, `b0df2350`, `17e32dc7`; 3161 passed,
ruff clean). It delivered:

- `LibraryMetadata` with the fifteen shared fields; `LibraryIdentity` and
  `Haybale` both extend it.
- `LibraryReloadAction` in `haywire/core/library/reload.py`, re-exported from
  `identity.py`; `on_reload` stored as `str` with a `reload_action` property.
- Marketstall rows carrying coordinates — `origin` + `install_spec` +
  `docs_path`/`examples_path`/`tests_path` — resolved via
  `haywire.core.marketstall.locate.resolve_row_path(row, path, *, form)` and
  `link_form(path)`.
- `HostProvider.tree_url()` and `.parse_origin()`; `_clickable_doc_url`,
  `_github_raw_base` and `_folder_url` deleted.

Two transitional artifacts it left **for this plan to remove**:

| artifact | where |
| --- | --- |
| `LibraryIdentity.url` and `.author` | `library/identity.py:36-43`, docstrings already name step 7 |
| `dependencies=` → `linked_libraries` kwarg shim | `library/decorator.py:112-114` |

## Verified starting state

Confirmed on disk 2026-08-08, not assumed:

- `LibraryMetadata` fields: `label`, `version`, `description`, `authors`, `tags`,
  `linked_libraries`, `on_reload`, `os`, `docs_path`, `examples_path`,
  `tests_path`, `homepage_url`, `documentation_url`, `author_url`, `issues_url`.
- `LibraryIdentity` adds: `id`, `folder_path`, `module_name`, `file_watcher`,
  plus the transitional `url` and `author`.
- `Haybale` adds: `name`, `require`, `source`, `install_spec`, `origin`,
  `source_label`, `source_file`, `source_origin`, `via`, `last_seen`, `stale`.
- Every barn library still passes `version=_pkg_version(...)`, `description=`,
  `url=`, `author=`, `author_url=`, `dependencies=`, `tags=` to `@library`.
- `decorator_io._get_decorator_str_field` exists and is quote-agnostic.
- `dep_detect._resolve_module_to_dist(module, mapping)` already maps a module
  name to its distribution via `importlib.metadata.packages_distributions()`.

Metadata shapes, verified by building a throwaway package and installing it into
a clean venv (see the consolidation doc):

- `Project-URL` is one header per entry, `"Label, URL"`, labels verbatim.
- `{name = "X"}` renders as `Author: X`; `{name = "X", email = "…"}` renders as
  `Author-email: X <…>`. A mixed list **splits across both headers**.
- `Keywords` is one comma-joined, backend-alphabetized string.

## Out of scope — the remaining plans, in order

- **step 9: one decorator reader, one generator.** Promotes the AST reader out of
  `scripts/generate_marketstall.py`; deletes `deps.py`'s regex readers and the
  `_get_decorator_str_field` calls this plan adds in Task 2.
- **step 6: declared-path preconditions.** Needs Task 2's decorator kwargs.
- **step 8: metadata editing moves into the Share flow.** Deletes
  `_overview_edit_dialog.py` and `update_library_identity`.
- **step 10: author-facing migration.** The 10 barn libraries, the `haywire init`
  scaffold, `haywire rename`, docs.

**This plan does not migrate the barn libraries.** It makes the decorator ignore
the removed kwargs (Task 4) so both spellings work during the transition; step 10
removes them from the libraries themselves.

## File Structure

| File | Responsibility |
| --- | --- |
| `packages/haywire-core/src/haywire/core/library/distmeta.py` | **new** — read PEP 621 fields out of `importlib.metadata` |
| `packages/haywire-core/src/haywire/core/library/decorator.py` | populate from distmeta; accept the three new kwargs; drop the shim |
| `packages/haywire-core/src/haywire/core/library/identity.py` | delete transitional `url`/`author` |
| `packages/haywire-core/src/haywire/core/library/metadata.py` | `os`/`examples_path`/`tests_path` docstrings drop "publish-time only" |
| `packages/haywire-core/src/haywire/core/publishing/marketstall.py` | read the three paths off the identity, not by regex |
| `barn/haybale-marketplace/haybale_marketplace/editors/library_overview_editor.py` | header reads base fields |
| `barn/haybale-marketplace/haybale_marketplace/editors/_overview_edit_dialog.py` | form reads base fields |
| `tests/core/test_library/test_distmeta.py` | **new** — header parsing, both author forms |
| `tests/core/test_library/test_decorator_distmeta.py` | **new** — decoration-time population |

---

### Task 1: Read PEP 621 fields out of distribution metadata

A pure function over an `importlib.metadata` message object, testable without
installing anything.

**Files:**

- Create: `packages/haywire-core/src/haywire/core/library/distmeta.py`
- Test: `tests/core/test_library/test_distmeta.py` (create)

**Interfaces:**

- Consumes: nothing from earlier tasks.
- Produces:
  - `distribution_fields(dist_name: str) -> dict[str, object]` — the kwargs to
    splat into `LibraryMetadata`. Empty dict when the distribution is absent.
  - `_parse_authors(md) -> list[str]`, `_parse_urls(md) -> dict[str, str]`,
    `_parse_keywords(md) -> list[str]` — used directly by Task 1's tests.

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_library/test_distmeta.py`:

```python
"""Reading PEP 621 fields back out of installed distribution metadata.

The header shapes here were verified against a real hatchling-built wheel
installed into a clean venv — see the consolidation doc. They are not guesses,
and two of them are easy to get wrong: authors split across Author and
Author-email depending on whether an email was declared, and Keywords arrives
comma-joined rather than as repeated headers.
"""

from email.message import Message

import pytest

from haywire.core.library.distmeta import (
    _parse_authors,
    _parse_keywords,
    _parse_urls,
)


def _md(**headers) -> Message:
    """Build a metadata message; a list value becomes repeated headers."""
    msg = Message()
    for key, value in headers.items():
        name = key.replace("_", "-")
        for item in value if isinstance(value, list) else [value]:
            msg[name] = item
    return msg


def test_author_without_email_is_a_plain_header():
    assert _parse_authors(_md(Author="Haywire Team")) == ["Haywire Team"]


def test_author_with_email_lands_in_author_email():
    md = _md(**{"Author-email": "Jane Doe <jane@example.com>"})
    assert _parse_authors(md) == ["Jane Doe"]


def test_mixed_list_splits_across_both_headers():
    """The case a naive get_all('Author') silently drops."""
    md = _md(
        Author="No Email Person",
        **{"Author-email": "With Email <we@example.com>, bare@example.com"},
    )
    assert _parse_authors(md) == ["No Email Person", "With Email", "bare@example.com"]


def test_email_only_entry_falls_back_to_the_address():
    md = _md(**{"Author-email": "bare@example.com"})
    assert _parse_authors(md) == ["bare@example.com"]


def test_no_author_headers_yields_empty():
    assert _parse_authors(_md(Summary="x")) == []


def test_urls_parse_label_and_target():
    md = _md(
        **{
            "Project-URL": [
                "Homepage, https://example.com/home",
                "Author, https://example.com/author",
                "Custom Label, https://example.com/custom",
            ]
        }
    )
    assert _parse_urls(md) == {
        "Homepage": "https://example.com/home",
        "Author": "https://example.com/author",
        "Custom Label": "https://example.com/custom",
    }


def test_urls_absent_yields_empty():
    assert _parse_urls(_md(Summary="x")) == {}


def test_malformed_url_entry_is_skipped_not_raised():
    md = _md(**{"Project-URL": ["no-comma-here", "Homepage, https://ok"]})
    assert _parse_urls(md) == {"Homepage": "https://ok"}


def test_keywords_split_on_commas():
    assert _parse_keywords(_md(Keywords="alpha,beta,gamma")) == ["alpha", "beta", "gamma"]


def test_keywords_tolerate_spaces_and_blanks():
    assert _parse_keywords(_md(Keywords="alpha, ,beta ")) == ["alpha", "beta"]


def test_keywords_absent_yields_empty():
    assert _parse_keywords(_md(Summary="x")) == []


@pytest.mark.parametrize("value", ["", "UNKNOWN"])
def test_placeholder_summary_is_not_a_description(value):
    """setuptools writes UNKNOWN for an absent field; it is not a description."""
    from haywire.core.library.distmeta import _clean

    assert _clean(value) == ""
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/core/test_library/test_distmeta.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'haywire.core.library.distmeta'`.

- [ ] **Step 3: Write the module**

Create `packages/haywire-core/src/haywire/core/library/distmeta.py`:

```python
"""Read a library's PEP 621 metadata back out of its installed distribution.

``pyproject.toml`` is the single source for version, description, authors,
keywords and URLs. The build backend copies them into the wheel's ``METADATA``,
so at decoration time the values come from here rather than from
``@library(...)`` kwargs — which is what stops the two from drifting.

The header shapes are not obvious and were verified against a real wheel:

* ``{name = "X"}`` renders as ``Author: X``, but ``{name = "X", email = "…"}``
  renders as ``Author-email: X <…>``. A list mixing both **splits across the two
  headers**, so reading only one silently loses authors.
* ``Keywords`` is a single comma-joined string, alphabetized by the backend —
  not repeated headers, and not in the order the author wrote them.
* ``Project-URL`` is one header per entry, ``"Label, URL"``, labels verbatim.
"""

from __future__ import annotations

import importlib.metadata
from email.message import Message
from email.utils import getaddresses

#: Placeholder some backends write for an absent field.
_PLACEHOLDERS = {"", "UNKNOWN"}


def _clean(value: str | None) -> str:
    """Normalise a header value, treating backend placeholders as absent."""
    text = (value or "").strip()
    return "" if text in _PLACEHOLDERS else text


def _parse_authors(md: Message) -> list[str]:
    """Every declared author's display name, across both header spellings."""
    names = [n for n in (_clean(v) for v in md.get_all("Author") or []) if n]
    for raw in md.get_all("Author-email") or []:
        for name, address in getaddresses([raw]):
            display = name.strip() or address.strip()
            if display:
                names.append(display)
    return names


def _parse_urls(md: Message) -> dict[str, str]:
    """``{label: url}`` from ``Project-URL`` headers. Malformed entries skipped."""
    urls: dict[str, str] = {}
    for entry in md.get_all("Project-URL") or []:
        label, sep, target = entry.partition(", ")
        if sep and label.strip() and target.strip():
            urls[label.strip()] = target.strip()
    return urls


def _parse_keywords(md: Message) -> list[str]:
    """``Keywords`` is comma-joined; order is the backend's, not the author's."""
    raw = _clean(md.get("Keywords"))
    return [k.strip() for k in raw.split(",") if k.strip()]


def distribution_fields(dist_name: str) -> dict[str, object]:
    """The ``LibraryMetadata`` fields carried by *dist_name*'s metadata.

    Returns ``{}`` when the distribution is not installed — the caller decides
    whether that is fatal. Keys are omitted rather than set empty when a field
    is absent, so a caller can splat this over defaults without clobbering them.
    """
    try:
        md = importlib.metadata.distribution(dist_name).metadata
    except importlib.metadata.PackageNotFoundError:
        return {}

    urls = _parse_urls(md)
    fields: dict[str, object] = {}

    for key, value in (
        ("version", _clean(md.get("Version"))),
        ("description", _clean(md.get("Summary"))),
        ("homepage_url", urls.get("Homepage", "")),
        ("documentation_url", urls.get("Documentation", "")),
        ("author_url", urls.get("Author", "")),
        ("issues_url", urls.get("Issues", "")),
    ):
        if value:
            fields[key] = value

    authors = _parse_authors(md)
    if authors:
        fields["authors"] = authors
    keywords = _parse_keywords(md)
    if keywords:
        fields["tags"] = keywords

    return fields
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/core/test_library/test_distmeta.py -v`

Expected: all PASS.

- [ ] **Step 5: Add a test against a really-installed distribution**

Append to `tests/core/test_library/test_distmeta.py`:

```python
def test_reads_a_really_installed_distribution():
    """End-to-end against haybale-core, which is installed in this workspace."""
    fields = distribution_fields("haybale-core")
    assert fields["version"]
    assert fields["description"]
    assert isinstance(fields.get("tags", []), list)


def test_absent_distribution_yields_empty_dict():
    assert distribution_fields("haybale-does-not-exist") == {}
```

with `distribution_fields` added to the imports at the top of the file.

- [ ] **Step 6: Run the tests**

Run: `uv run pytest tests/core/test_library/test_distmeta.py -v`

Expected: all PASS.

- [ ] **Step 7: Lint, format, type-check**

```bash
uv run ruff check packages/haywire-core/src/haywire/core/library/ tests/core/test_library/
uv run ruff format --check packages/haywire-core/src/haywire/core/library/ tests/core/test_library/
uv run mypy packages/haywire-core/src/
```

Expected: clean.

- [ ] **Step 8: Commit**

```bash
git add packages/haywire-core/src/haywire/core/library/distmeta.py \
        tests/core/test_library/test_distmeta.py
git commit -m "feat(library): read PEP 621 fields from distribution metadata

Pure reader, no callers yet. Handles the two header shapes that are easy to
get wrong: authors split across Author and Author-email depending on whether
an email was declared, and Keywords arriving comma-joined rather than as
repeated headers.

ADR 0024."
```

---

### Task 2: The decorator populates from distribution metadata

**Files:**

- Modify: `packages/haywire-core/src/haywire/core/library/decorator.py`
- Modify: `packages/haywire-core/src/haywire/core/library/metadata.py` (docstrings)
- Test: `tests/core/test_library/test_decorator_distmeta.py` (create)

**Interfaces:**

- Consumes: `distribution_fields(dist_name)` from Task 1;
  `dep_detect._resolve_module_to_dist(module, mapping)`.
- Produces: `@library(...)` accepting `os`, `examples_path`, `tests_path`;
  ignoring `version`, `description`, `author`, `author_url`, `url`, `tags`;
  and taking `linked_libraries=` directly.

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_library/test_decorator_distmeta.py`:

```python
"""The decorator fills LibraryMetadata's PEP 621 half from the installed dist.

An author writes these in pyproject.toml only. The decorator carries the
Haywire-specific fields, which have no packaging equivalent and must survive
into an installed wheel — hence kwargs rather than [tool.haywire], which the
wheel does not contain.
"""

import pytest

from haywire.core.library.base import BaseLibrary
from haywire.core.library.decorator import library


def _make(**kwargs):
    @library(id="core", label="Core", **kwargs)
    class _Lib(BaseLibrary):
        pass

    # Attribute the class to an installed distribution's module so the
    # decorator can resolve it; haybale_core is installed in this workspace.
    return _Lib


def test_version_comes_from_the_distribution_not_a_kwarg(monkeypatch):
    import haywire.core.library.decorator as dec

    monkeypatch.setattr(dec, "_dist_for_module", lambda _m: "haybale-core")
    identity = _make().class_identity
    assert identity.version
    assert identity.version != "1.0.0"  # the old hardcoded default


def test_description_and_tags_come_from_the_distribution(monkeypatch):
    import haywire.core.library.decorator as dec

    monkeypatch.setattr(dec, "_dist_for_module", lambda _m: "haybale-core")
    identity = _make().class_identity
    assert identity.description
    assert isinstance(identity.tags, list)


def test_removed_kwargs_are_ignored_not_fatal(monkeypatch):
    """Barn libraries still pass these until the author-facing migration."""
    import haywire.core.library.decorator as dec

    monkeypatch.setattr(dec, "_dist_for_module", lambda _m: "haybale-core")
    identity = _make(
        version="9.9.9",
        description="stale decorator copy",
        author="Stale",
        author_url="https://stale",
        url="https://stale",
        tags=["stale"],
    ).class_identity
    assert identity.version != "9.9.9"
    assert identity.description != "stale decorator copy"
    assert "stale" not in identity.tags


def test_haywire_specific_kwargs_are_carried():
    identity = _make(
        os=["macos", "linux"],
        examples_path="examples/OVERVIEW.md",
        tests_path="tests/",
        linked_libraries=["haybale_studio"],
        on_reload="restart",
    ).class_identity
    assert identity.os == ["macos", "linux"]
    assert identity.examples_path == "examples/OVERVIEW.md"
    assert identity.tests_path == "tests/"
    assert identity.linked_libraries == ["haybale_studio"]
    assert identity.on_reload == "restart"


def test_dependencies_keyword_still_maps_to_linked_libraries():
    """The shim stays until the author-facing migration rewrites the libraries."""
    identity = _make(dependencies=["haybale_core"]).class_identity
    assert identity.linked_libraries == ["haybale_core"]


def test_id_is_required():
    with pytest.raises(ValueError, match="id"):

        @library(label="No Id")
        class _Lib(BaseLibrary):
            pass


def test_uninstalled_module_leaves_pep621_fields_empty(monkeypatch):
    """A library imported from a path with no distribution still loads."""
    import haywire.core.library.decorator as dec

    monkeypatch.setattr(dec, "_dist_for_module", lambda _m: None)
    identity = _make().class_identity
    assert identity.version == ""
    assert identity.label == "Core"  # decorator-authored fields unaffected
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/core/test_library/test_decorator_distmeta.py -v`

Expected: FAIL — `AttributeError: module 'haywire.core.library.decorator' has no
attribute '_dist_for_module'`, and `test_id_is_required` fails because `id` still
defaults to `label`.

- [ ] **Step 3: Rewrite the decorator body**

In `packages/haywire-core/src/haywire/core/library/decorator.py`, replace the
inner `decorator` function body:

```python
#: Kwargs an author used to pass that now come from pyproject.toml. Accepted
#: and ignored so a library still loads during the author-facing migration;
#: removed once every barn library has been rewritten (migration step 10).
_SUPERSEDED_KWARGS = frozenset(
    {"version", "description", "author", "author_url", "url", "tags"}
)


def _dist_for_module(module: str) -> str | None:
    """The distribution owning *module*, or None when it is not installed."""
    import importlib.metadata

    from haywire.core.library.dep_detect import _resolve_module_to_dist

    return _resolve_module_to_dist(module, importlib.metadata.packages_distributions())


    def decorator(inner_cls: Type[T]) -> Type[T]:
        if not issubclass(inner_cls, BaseLibrary):
            raise TypeError(f"@library can only be applied to BaseLibrary subclasses, got {inner_cls}")

        if "label" not in kwargs:
            raise ValueError("@library decorator requires 'label' argument")
        if "id" not in kwargs:
            raise ValueError("@library decorator requires 'id' argument")

        # The authored keyword is still `dependencies=` in libraries that have
        # not been migrated; the field is `linked_libraries`. Migration step 10
        # rewrites the libraries, at which point this goes away.
        if "dependencies" in kwargs:
            kwargs["linked_libraries"] = kwargs.pop("dependencies")

        # Dropped silently rather than raising: barn libraries still pass them
        # until step 10, and a hard failure would make the migration a flag day.
        for superseded in _SUPERSEDED_KWARGS & kwargs.keys():
            kwargs.pop(superseded)

        class_file = inspect.getfile(inner_cls)
        kwargs["folder_path"] = str(Path(class_file).parent)
        kwargs["module_name"] = inner_cls.__module__

        # pyproject.toml is the single source for the PEP 621 half. Read from
        # the installed distribution, which is where the build backend copied
        # them — a path import with no distribution simply leaves them empty.
        dist = _dist_for_module(inner_cls.__module__)
        if dist:
            kwargs.update(distribution_fields(dist))

        inner_cls.class_identity = LibraryIdentity(**kwargs)
        return inner_cls

    return decorator
```

Add the import at the top:

```python
from haywire.core.library.distmeta import distribution_fields
```

and delete the two `kwargs.setdefault(...)` lines for `version` and `id`.

- [ ] **Step 4: Rewrite the decorator docstring**

Replace the `Args:` block so it documents only what an author still passes:

```python
    """
    Decorator to register a class as a Haywire library.

    Always invoked with parentheses — `@library(...)`. `label` and `id` are
    required.

    Args:
        label (str, required): Human-readable library name.
        id (str, required): Unique identifier; prefixes every component's
            registry key.
        linked_libraries (list[str], optional): Sibling haybale **module** names
            (e.g. ``"haybale_core"``) whose classes this library subscribes to.
            Required for hot-reload: without it a subscriber holds a stale class
            reference after a reload. Not the same as ``[project] dependencies``.
        on_reload (str, optional): ``"none"`` (default), ``"refresh"`` or
            ``"restart"`` — what the user must do after this library is
            installed, updated or uninstalled.
        os (list[str], optional): Platforms this library supports
            (``"macos"``, ``"windows"``, ``"linux"``). Empty means all. Gates
            installation from a marketplace.
        examples_path (str, optional): Path to this library's examples, relative
            to the library directory. Trailing slash means a directory.
        tests_path (str, optional): Likewise for tests.
        file_watcher (bool, optional): Watch this library's files and hot-reload
            on change. Development only. Defaults to False.

    **Not decorator arguments.** ``version``, ``description``, ``author``,
    ``author_url``, ``url`` and ``tags`` are read from the installed
    distribution's metadata, which the build backend copies from
    ``pyproject.toml``. Authoring them here as well is what let the two drift,
    so they are accepted and ignored until the barn libraries are migrated.
    Declare them in ``[project]`` and ``[project.urls]``:

        [project]
        version = "0.0.40"
        description = "…"
        keywords = ["haywire", "core"]
        authors = [{ name = "…" }]

        [project.urls]
        Homepage = "…"
        Documentation = "…"
        Author = "…"
        Issues = "…"

    Usage::

        @library(
            id="core",
            label="Core",
            linked_libraries=["haybale_studio"],
            on_reload="restart",
            os=["macos", "linux"],
            examples_path="examples/OVERVIEW.md",
            file_watcher=True,
        )
        class Library(BaseLibrary): ...
    """
```

- [ ] **Step 5: Drop "publish-time only" from three base docstrings**

In `packages/haywire-core/src/haywire/core/library/metadata.py`, `os`,
`examples_path` and `tests_path` are now decorator kwargs, so they are populated
at runtime too. Remove any sentence claiming they are empty on a
runtime-constructed identity. `docs_path` keeps its note — it is still derived at
publish time from the git root and has no runtime meaning.

- [ ] **Step 6: Run the tests**

```bash
uv run pytest tests/core/test_library/ -v
```

Expected: all PASS.

- [ ] **Step 7: Run the full gate**

```bash
uv run pytest -m "not browser and not perf" -q > /tmp/step7.log 2>&1; echo "exit=$?"
grep -E "^FAILED|^ERROR" /tmp/step7.log | head -20
```

Expected failures, and only these: tests asserting a decorator-authored
`version`/`description`/`author`/`tags`, and tests constructing `@library(...)`
without `id`. Fix each by moving the assertion to the distribution or adding
`id=`. **Any other failure is a real regression.**

- [ ] **Step 8: Lint, format, type-check**

```bash
uv run ruff check packages/ barn/ tests/
uv run ruff format --check packages/ barn/ tests/
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-TEST_A/haybale_test_a/ tests/
```

Expected: clean.

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat(library)!: decorator reads PEP 621 metadata from the distribution

version, description, author, author_url, url and tags are no longer @library
kwargs — they come from the installed distribution's METADATA, which the build
backend copies from pyproject.toml. That makes pyproject the single source and
ends the drift: haybale-core's decorator said 'Fundamental components for
hayire graphs' while its metadata said 'Haywire's core library with types,
nodes, widgets, and renderers'.

os, examples_path and tests_path become decorator kwargs. They have no PEP 621
equivalent and [tool.haywire] does not survive into a wheel, so code is the
only place they can live and still be readable at runtime.

BREAKING CHANGE: @library(id=...) is now required — it previously defaulted to
label, and label is no longer a sensible default for a registry key prefix.
The six superseded kwargs are accepted and ignored until the barn libraries are
migrated; passing them has no effect.

ADR 0024."
```

---

### Task 3: Delete the transitional identity fields

`LibraryIdentity.url` and `.author` were kept by the predecessor plan purely so
consumers had something to read. Task 2 populates `homepage_url` and `authors`
from the distribution, so the consumers move and the fields go.

**Files:**

- Modify: `packages/haywire-core/src/haywire/core/library/identity.py:36-43`
- Modify: `barn/haybale-marketplace/haybale_marketplace/editors/library_overview_editor.py:316-319,358`
- Modify: `barn/haybale-marketplace/haybale_marketplace/editors/_overview_edit_dialog.py:89,98-104`
- Modify: `packages/haywire-studio/src/haywire_studio/packaging/docs/extract.py:154-155`

**Interfaces:**

- Consumes: `LibraryIdentity.homepage_url`, `.authors` populated by Task 2.
- Produces: `LibraryIdentity` carrying only `id`, `folder_path`, `module_name`,
  `file_watcher` beyond the base.

- [ ] **Step 1: Find every reader**

```bash
grep -rn "identity\.author\b\|identity\.url\b" --include="*.py" packages/ barn/ tests/
```

Record the list. Each is either a display site (becomes `.authors` /
`.homepage_url`) or a form field (same, plus list handling for authors).

- [ ] **Step 2: Write the failing test**

Append to `tests/core/test_library/test_decorator_distmeta.py`:

```python
def test_transitional_fields_are_gone():
    """url and author were placeholders for homepage_url and authors.

    Not an absence check for its own sake: while both spellings existed a
    consumer could read the decorator-authored one and silently get a value
    pyproject.toml never sanctioned.
    """
    from dataclasses import fields

    from haywire.core.library.identity import LibraryIdentity

    names = {f.name for f in fields(LibraryIdentity)}
    assert "url" not in names
    assert "author" not in names
    assert {"homepage_url", "authors"} <= names
```

- [ ] **Step 3: Run it to verify it fails**

Run: `uv run pytest tests/core/test_library/test_decorator_distmeta.py::test_transitional_fields_are_gone -v`

Expected: FAIL — both fields still present.

- [ ] **Step 4: Delete the fields**

In `packages/haywire-core/src/haywire/core/library/identity.py`, delete the `url`
and `author` declarations and their docstrings (lines ~36-43).

- [ ] **Step 5: Move the consumers**

`library_overview_editor.py` around line 316:

```python
            version = installed_lib.identity.version
            description = installed_lib.identity.description
            authors = installed_lib.identity.authors
            tags = installed_lib.identity.tags or (marketplace_pkg.tags if marketplace_pkg else []) or []
```

and at line ~358, the title link:

```python
                        _title_url = (installed_lib.identity.homepage_url if installed_lib else "") or ""
```

Wherever the header renders a single author string, join the list:

```python
    author_text = ", ".join(authors)
```

`_overview_edit_dialog.py` — the form reads the same fields; these become
read-only for now, since the edit path itself moves in step 8:

```python
        ui.label(f"Version: {lib.identity.version or '0.1.0'} (from pyproject.toml)").classes(
            "text-xs hw-text-dim"
        )
        ui.label(f"Description: {lib.identity.description} (from pyproject.toml)").classes(
            "text-xs hw-text-dim"
        )
        ui.label(f"Authors: {', '.join(lib.identity.authors) or '(none)'} (from pyproject.toml)").classes(
            "text-xs hw-text-dim"
        )
        ui.label(f"Tags: {', '.join(lib.identity.tags) or '(none)'} (from pyproject.toml)").classes(
            "text-xs hw-text-dim"
        )
```

Delete the corresponding `hui.input_field(...)` calls and the keys they
contributed to the `identity` dict in `_save`. `update_library_identity` keeps
writing `label`, `on_reload` and `linked_libraries`, which are still decorator
fields.

`docs/extract.py:154-155` needs no change — `version` and `description` are still
identity attributes, now sourced differently.

- [ ] **Step 6: Run the tests**

```bash
uv run pytest tests/core/test_library/ tests/marketplace/ tests/studio/ -q
```

Expected: all pass.

- [ ] **Step 7: Run the full gate**

```bash
uv run pytest -m "not browser and not perf" -q > /tmp/task3.log 2>&1; echo "exit=$?"
grep -E "^FAILED|^ERROR" /tmp/task3.log | head -20
```

Expected: `exit=0`, no FAILED lines.

- [ ] **Step 8: Lint, format, type-check**

```bash
uv run ruff check packages/ barn/ tests/
uv run ruff format --check packages/ barn/ tests/
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-TEST_A/haybale_test_a/ tests/
```

Expected: clean.

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "refactor(library)!: drop transitional identity url and author

Both were placeholders the foundation plan kept so consumers had something to
read while the base carried homepage_url and authors unpopulated. The decorator
now fills those from distribution metadata, so the consumers move and the
duplicates go.

BREAKING CHANGE: LibraryIdentity.url and .author are removed; read
.homepage_url and .authors (a list) instead.

ADR 0024."
```

---

### Task 4: The producer reads paths off the identity

`_build_entry_for_library` currently reads `examples_path`/`tests_path` from the
decorator source with a regex, because when the foundation plan ran they were not
yet kwargs. They are now, so the regex goes.

**Files:**

- Modify: `packages/haywire-core/src/haywire/core/publishing/marketstall.py`
- Test: `tests/test_share_marketstall_write.py` (extend)

**Interfaces:**

- Consumes: `LibraryIdentity.examples_path`, `.tests_path`, `.os` from Task 2.
- Produces: no new API; removes the `_get_decorator_str_field` calls.

- [ ] **Step 1: Check whether the producer can reach an identity**

```bash
grep -n "_get_decorator_str_field\|examples_path\|tests_path\|os_decl" packages/haywire-core/src/haywire/core/publishing/marketstall.py
```

The producer runs against a **source tree**, without importing the library — that
is what lets `haywire share` work on a checkout. So it cannot read
`cls.class_identity`.

**Therefore: leave the regex reads in place.** They are replaced by the AST
reader in migration step 9, which is the plan that owns "one decorator reader".
Doing it here would mean writing a second reader that step 9 immediately deletes.

Record in the plan log that this task is a **no-op by design** and move on. The
only change is a comment correcting the note left by the foundation plan:

```python
    # Read from the decorator source rather than an imported class: `haywire
    # share` runs against a checkout, where nothing is imported. Migration step
    # 9 replaces this regex with the AST reader promoted out of
    # scripts/generate_marketstall.py — it is the one reader, and it cannot be
    # defeated by quoting.
```

- [ ] **Step 2: Verify `os` is still read from the right place**

```bash
grep -n "tool.*haywire.*os\|os_decl" packages/haywire-core/src/haywire/core/publishing/marketstall.py
```

`os` moved from `[tool.haywire]` to the decorator in Task 2, so a producer still
reading `data["tool"]["haywire"]["os"]` now reads a key the migrated libraries
will not have. Change it to the same decorator-source read the paths use:

```python
    os_decl = [
        v.strip()
        for v in _get_decorator_list_field(content, "os")
        if v.strip()
    ]
```

using the existing `_get_decorator_list_field` from `decorator_io`.

**Trap, verified 2026-08-08.** That helper converts `_` → `-` on every value — it
was written for dependency names, where module form and pip form differ. The three
declarable OS values (`macos`, `windows`, `linux`) contain no underscores, so it
is harmless *today*, but it silently mangles anything that does:

```python
>>> _get_decorator_list_field('os=["mac_os"]', "os")
['mac-os']
```

Either add a `convert=False` parameter to the helper, or validate `os_decl`
against the three known values and drop the rest — the latter matches what
`_apply_os_to_pyproject` used to do before it was deleted. Do **not** leave the
conversion unremarked.

Keep reading `[tool.haywire].os` as a fallback until step 10 migrates the
libraries:

```python
    if not os_decl:
        os_decl = data.get("tool", {}).get("haywire", {}).get("os") or []
```

- [ ] **Step 3: Write the test**

Append to `tests/test_share_marketstall_write.py`:

```python
def test_os_read_from_the_decorator(tmp_path):
    """os moved from [tool.haywire] to the decorator in migration step 7."""
    from haywire.core.publishing.marketstall import _build_entry_for_library

    lib = tmp_path / "barn" / "haybale-demo"
    (lib / "haybale_demo").mkdir(parents=True)
    (lib / "pyproject.toml").write_text(
        '[project]\nname = "haybale-demo"\nversion = "0.1.0"\n'
    )
    (lib / "haybale_demo" / "__init__.py").write_text(
        '@library(\n    id="demo",\n    label="Demo",\n'
        '    os=["macos", "linux"],\n)\nclass Library: ...\n'
    )

    entry = _build_entry_for_library(lib)
    assert entry["os"] == ["macos", "linux"]


def test_os_falls_back_to_tool_haywire(tmp_path):
    """Libraries not yet migrated still declare it in pyproject."""
    from haywire.core.publishing.marketstall import _build_entry_for_library

    lib = tmp_path / "barn" / "haybale-old"
    (lib / "haybale_old").mkdir(parents=True)
    (lib / "pyproject.toml").write_text(
        '[project]\nname = "haybale-old"\nversion = "0.1.0"\n'
        '[tool.haywire]\nos = ["windows"]\n'
    )
    (lib / "haybale_old" / "__init__.py").write_text(
        '@library(\n    id="old",\n    label="Old",\n)\nclass Library: ...\n'
    )

    entry = _build_entry_for_library(lib)
    assert entry["os"] == ["windows"]
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_share_marketstall_write.py -v`

Expected: all PASS. If `_build_entry_for_library` returns `None` because the
fixture lacks a git root, add `tag=None` and assert on the fields that do not
require a remote, or mark the git-dependent assertions `xfail` with a reason.

- [ ] **Step 5: Run the full gate**

```bash
uv run pytest -m "not browser and not perf" -q > /tmp/task4.log 2>&1; echo "exit=$?"
grep -E "^FAILED|^ERROR" /tmp/task4.log | head -20
```

Expected: `exit=0`, no FAILED lines.

- [ ] **Step 6: Lint, format, type-check**

```bash
uv run ruff check packages/ tests/
uv run ruff format --check packages/ tests/
uv run mypy packages/haywire-core/src/ tests/
```

Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "fix(share): read os from the decorator, falling back to pyproject

os became a decorator kwarg in the previous commit, so the producer must read
it there. [tool.haywire].os stays as a fallback until the barn libraries are
migrated (step 10).

The examples_path/tests_path regex reads stay: `haywire share` runs against a
checkout without importing anything, so it cannot read class_identity. Migration
step 9 replaces all of them with the one AST reader.

ADR 0024."
```

---

## Self-Review

**Spec coverage.** This plan implements migration **step 7** in full: the
decorator stops accepting the six PEP 621 kwargs and reads them from the
distribution, `os`/`examples_path`/`tests_path` become kwargs, `id` becomes
required, and the transitional `LibraryIdentity.url`/`.author` are deleted. Task 4
also corrects a consequence step 7 creates in the producer.

**What this plan finishes.** After it lands, no field is authored twice —
`pyproject.toml` owns the PEP 621 half, the decorator owns the Haywire half. That
is the ADR's headline outcome. The barn libraries still *pass* the superseded
kwargs, which are ignored; step 10 removes them.

**Deviation, flagged.** Task 4 turned out to be mostly a no-op. I expected the
producer to switch from regex to `class_identity`, but `haywire share` runs
against a checkout without importing the library, so it cannot. The task survives
because `os` genuinely moved and the producer would otherwise read a key that no
longer exists; the path reads stay for step 9. Recording this rather than deleting
the task, so the next reader does not re-derive it.

**Type consistency.** `distribution_fields` returns `dict[str, object]` and is
splatted into `LibraryIdentity(**kwargs)`; every key it emits is a
`LibraryMetadata` field name. `authors` and `tags` are `list[str]`;
`homepage_url`/`documentation_url`/`author_url`/`issues_url` are `str`.
`_dist_for_module` returns `str | None` and is monkeypatched by name in Task 2's
tests, so it must stay a module-level function.

**Three risks worth naming.**

1. **`id` becoming required is a hard break** for any out-of-tree library. It
   previously defaulted to `label`. Unavoidable — `label` is display text and a
   registry-key prefix should not silently derive from it — but it is the one
   change here that cannot be papered over during migration.
2. **Ignoring the six superseded kwargs is silent.** A library passing
   `version="9.9.9"` gets the distribution's version with no warning. That is
   deliberate (a raise would make step 10 a flag day) but it means a confused
   author sees no feedback. Consider a `logger.debug` naming the ignored keys.
3. **`_dist_for_module` runs at import time for every library**, calling
   `packages_distributions()`, which walks `sys.path`. It is cached by
   `importlib.metadata` within a process but is not free; if library import time
   regresses noticeably, hoist the mapping into a module-level
   `functools.cache`d helper.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-08-library-metadata-distribution.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
