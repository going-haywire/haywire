# One Metadata Record Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `Haybale` the single metadata record read from both `haybale.toml` and marketstall feeds, so the Library Detail editor renders every field from one source instead of hand-picking between two half-populated ones.

**Architecture:** `Haybale` gains `authors`/`id`/`name` and keeps its publish/transport fields (empty when read from disk). A new `read_haybale()` replaces `read_display()`, deleting `LibraryDisplay`. `LibraryInfo` gains a `row: Haybale` field and represents libraries whether installed or not, discriminated by a new `InstallType.NOT_INSTALLED`. The Library Browser and Overview editors then consume one type, and `_render_center` takes one parameter.

**Tech Stack:** Python 3.12, dataclasses, tomlkit (`haywire.core.tomlio`), NiceGUI, pytest.

**Decision record:** [2026-08-10-haybale-one-metadata-record-decisions.md](2026-08-10-haybale-one-metadata-record-decisions.md) — D1–D13. Read it before starting; this plan implements it.

## Global Constraints

- Line length 109. CI runs **both** `uv run ruff check .` and `uv run ruff format --check .`.
- Type-check with the exact command in `CLAUDE.md`; `haybale-visiongraph` is excluded.
- Gate before every commit: `uv run pytest -m "not browser and not perf"` (~2.5 min). While iterating, run the single test file instead.
- Never call `create_test_injector()` directly in a test — use the `test_injector` fixtures.
- `_TOML_FIELDS` controls marketstall serialization; `to_dict()` omits falsy values. Table-valued fields (`authors`, `deprecated`) MUST come last, in that order.
- Import `Haybale` as `from haywire.core.marketstall import Haybale` everywhere except inside `core/marketstall/**` and `tests/marketstall/**` (D11).
- `haywire-core` must not import any `haybale_*` barn package.
- Barn `__init__.py` files use double quotes (`ruff format` output).

---

### Task 1: `authors` replaces `author` on `Haybale`

Implements D3, D8. Adds `authors`, `id`; deletes `author`.

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/marketstall/types.py:42-158`
- Modify: `packages/haywire-core/src/haywire/core/marketstall/parsing.py:59-97`
- Test: `tests/marketstall/test_haybale_dataclass.py`

**Interfaces:**
- Produces: `Haybale.authors: list[tuple[str, str]]` (name, url), `Haybale.id: str`. `Haybale.author` no longer exists.

- [ ] **Step 1: Write the failing tests**

Append to `tests/marketstall/test_haybale_dataclass.py`:

```python
def test_authors_round_trip_as_table_array():
    from haywire.core.marketstall.types import Haybale

    row = Haybale(
        name="haybale-x",
        version="1.0.0",
        authors=[("maybites", "https://maybites.ch"), ("cansik", "")],
    )
    d = row.to_dict()
    assert d["authors"] == [
        {"name": "maybites", "url": "https://maybites.ch"},
        {"name": "cansik"},
    ]


def test_authors_and_deprecated_are_serialized_last():
    from haywire.core.marketstall.types import Deprecation, Haybale

    row = Haybale(
        name="haybale-x",
        version="1.0.0",
        label="X",
        authors=[("a", "")],
        deprecated=Deprecation(since="1.0.0", reason="r", successor=""),
    )
    keys = list(row.to_dict())
    assert keys[-2:] == ["authors", "deprecated"]


def test_id_is_carried_on_the_row():
    from haywire.core.marketstall.types import Haybale

    row = Haybale(name="haybale-x", version="1.0.0", id="x")
    assert row.to_dict()["id"] == "x"


def test_empty_authors_is_omitted():
    from haywire.core.marketstall.types import Haybale

    row = Haybale(name="haybale-x", version="1.0.0")
    assert "authors" not in row.to_dict()


def test_parse_reads_authors_table_array():
    from haywire.core.marketstall.parsing import _parse_haybale_entry

    row = _parse_haybale_entry(
        {
            "name": "haybale-x",
            "version": "1.0.0",
            "id": "x",
            "authors": [
                {"name": "maybites", "url": "https://maybites.ch"},
                {"name": "cansik"},
            ],
        }
    )
    assert row.authors == [("maybites", "https://maybites.ch"), ("cansik", "")]
    assert row.id == "x"


def test_parse_ignores_legacy_author_string():
    from haywire.core.marketstall.parsing import _parse_haybale_entry

    row = _parse_haybale_entry(
        {"name": "haybale-x", "version": "1.0.0", "author": "maybites, cansik"}
    )
    assert row.authors == []
    assert not hasattr(row, "author")


def test_parse_drops_nameless_author_entries():
    from haywire.core.marketstall.parsing import _parse_haybale_entry

    row = _parse_haybale_entry(
        {
            "name": "haybale-x",
            "version": "1.0.0",
            "authors": [{"url": "https://x.test"}, {"name": "ok"}, "junk"],
        }
    )
    assert row.authors == [("ok", "")]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/marketstall/test_haybale_dataclass.py -k "authors or legacy_author or id_is_carried" -v`
Expected: FAIL — `TypeError: Haybale.__init__() got an unexpected keyword argument 'authors'`

- [ ] **Step 3: Replace `author` with `authors` and add `id` on the dataclass**

In `packages/haywire-core/src/haywire/core/marketstall/types.py`, replace the line `author: str = ""` (currently line 61) with:

```python
    id: str = ""
    """The library's registry-key prefix (``core`` in ``core:node:Add``). Published
    so a consumer can resolve a component key before installing."""
```

Then, immediately after the `stale: bool = False` line (currently line 129) and before `_TOML_FIELDS`, add:

```python
    authors: list[tuple[str, str]] = field(default_factory=list)
    """``(name, url)`` pairs; ``url`` is ``""`` when the author declared none.

    Serializes to a ``[[authors]]`` table array, so it is written after every bare
    key — see the ordering note on ``_TOML_FIELDS``."""
```

- [ ] **Step 4: Update `_TOML_FIELDS` ordering**

In the same file, replace the whole `_TOML_FIELDS` tuple with:

```python
    _TOML_FIELDS: ClassVar[tuple[str, ...]] = (
        "name",
        "id",
        "label",
        "version",
        "require",
        "description",
        "source",
        "install_spec",
        "tags",
        "os",
        "on_reload",
        "linked_libraries",
        "origin",
        "origin_provider",
        "notes",
        "homepage_url",
        "documentation_url",
        "issues_url",
        "examples_path",
        "tests_path",
        "via",
        "last_seen",
        "stale",
        # Both serialize to TOML tables, so they MUST stay last and in this
        # order: every bare key written after a table header is parsed into
        # that table.
        "authors",
        "deprecated",
    )
```

- [ ] **Step 5: Serialize `authors` in `to_dict()`**

Replace the body of `to_dict()` with:

```python
    def to_dict(self) -> dict:
        """TOML-serializable dict; omits empty/default-valued fields."""
        result: dict = {}
        for f in self._TOML_FIELDS:
            val = getattr(self, f)
            if not val:
                continue
            if f == "authors":
                result[f] = [
                    {"name": name, **({"url": url} if url else {})} for name, url in val
                ]
            else:
                result[f] = val.to_dict() if isinstance(val, Deprecation) else val
        return result
```

Verify `field` is imported at the top of the file (`from dataclasses import dataclass, field`); add it to the existing import if absent.

- [ ] **Step 6: Parse `authors` and `id`**

In `packages/haywire-core/src/haywire/core/marketstall/parsing.py`, add this helper immediately above `_parse_haybale_entry`:

```python
def _parse_authors(raw: dict) -> list[tuple[str, str]]:
    """``[[authors]]`` tables as ``(name, url)`` pairs.

    A nameless entry is not an author and is dropped, matching
    ``haybale.toml``'s own read rule. Junk entries are skipped rather than
    raised on: a feed is untrusted input, and one malformed author must not
    cost the consumer the whole row.
    """
    entries = raw.get("authors")
    if not isinstance(entries, list):
        return []
    authors: list[tuple[str, str]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        if not isinstance(name, str) or not name:
            continue
        url = entry.get("url")
        authors.append((name, url if isinstance(url, str) else ""))
    return authors
```

In `_parse_haybale_entry`, delete the line `author=raw.get("author", ""),` and add these two lines in its place:

```python
        id=raw.get("id", ""),
        authors=_parse_authors(raw),
```

- [ ] **Step 7: Run the tests**

Run: `uv run pytest tests/marketstall/ -v`
Expected: PASS. Any failure naming `author=` is a fixture in that file still passing the removed kwarg — update it to `authors=[("name", "")]`.

- [ ] **Step 8: Fix remaining `author=` construction sites**

Run: `grep -rn --include="*.py" "author=" packages/ barn/ tests/ scripts/ | grep -v author_url | grep -v authors=`

For each hit that constructs a `Haybale`, replace `author="X"` with `authors=[("X", "")]`. Leave `LibraryIdentity(author=...)` sites alone — a different class, handled in Task 8.

- [ ] **Step 9: Verify and commit**

Run: `uv run ruff check packages/haywire-core/src/haywire/core/marketstall/ && uv run ruff format packages/haywire-core/src/haywire/core/marketstall/ && uv run pytest tests/marketstall/ -q`
Expected: all pass.

```bash
git add packages/haywire-core/src/haywire/core/marketstall/types.py packages/haywire-core/src/haywire/core/marketstall/parsing.py tests/marketstall/test_haybale_dataclass.py
git commit -m "feat(marketstall)!: authors replaces author; publish id

BREAKING CHANGE: Haybale.author is removed in favour of authors, a list of
(name, url) pairs. Feeds carrying the flat author string lose their author
line until republished; parsing tolerates the unknown key."
```

---

### Task 2: `read_haybale()` replaces `read_display()`

Implements D1, D2, D4, D5. Deletes `LibraryDisplay`.

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/library/haybale_toml.py:230-338`
- Test: `tests/core/test_library/test_haybale_toml.py:245-325`

**Interfaces:**
- Consumes: `Haybale` from Task 1.
- Produces: `read_haybale(package_dir: Path) -> Haybale`. `LibraryDisplay`, `read_display`, `_display_from` no longer exist.

- [ ] **Step 1: Write the failing tests**

Replace the existing `read_display` tests in `tests/core/test_library/test_haybale_toml.py` (the block from `def test_read_display...` through the last `read_display` test, around lines 245-325) with:

```python
def test_read_haybale_reads_every_declared_field(tmp_path):
    from haywire.core.library.haybale_toml import read_haybale

    row = read_haybale(
        _write(
            tmp_path,
            'name = "haybale-core"\n'
            'id = "core"\n'
            'version = "1.2.3"\n'
            'label = "Core"\n'
            'description = "d"\n'
            'tags = ["a", "b"]\n'
            'os = ["linux"]\n'
            'on_reload = "refresh"\n'
            'linked_libraries = ["haybale_studio"]\n'
            'origin = "https://github.test/o/r"\n'
            'origin_provider = "github"\n'
            'notes = "NOTES.md"\n'
            'examples_path = "examples/"\n'
            'tests_path = "tests/"\n'
            'homepage_url = "https://home.test"\n'
            'documentation_url = "https://docs.test"\n'
            'issues_url = "https://issues.test"\n'
            "[[authors]]\n"
            'name = "maybites"\n'
            'url = "https://maybites.ch"\n'
            "[[authors]]\n"
            'name = "cansik"\n',
        )
    )
    assert row.name == "haybale-core"
    assert row.id == "core"
    assert row.version == "1.2.3"
    assert row.label == "Core"
    assert row.description == "d"
    assert row.tags == ["a", "b"]
    assert row.os == ["linux"]
    assert row.on_reload == "refresh"
    assert row.linked_libraries == ["haybale_studio"]
    assert row.origin == "https://github.test/o/r"
    assert row.origin_provider == "github"
    assert row.notes == "NOTES.md"
    assert row.examples_path == "examples/"
    assert row.tests_path == "tests/"
    assert row.homepage_url == "https://home.test"
    assert row.documentation_url == "https://docs.test"
    assert row.issues_url == "https://issues.test"
    assert row.authors == [("maybites", "https://maybites.ch"), ("cansik", "")]


def test_read_haybale_marks_source_local(tmp_path):
    from haywire.core.library.haybale_toml import read_haybale

    row = read_haybale(_write(tmp_path, 'id = "core"\nversion = "1.0.0"\n'))
    assert row.source == "local"
    assert row.install_spec == ""
    assert row.stale is False
    assert row.via == ""


def test_read_haybale_never_raises(tmp_path):
    from haywire.core.library.haybale_toml import read_haybale

    assert read_haybale(tmp_path).name == ""  # no file at all
    assert read_haybale(_write(tmp_path, "id = [broken\n")).name == ""


def test_read_haybale_drops_wrong_typed_values(tmp_path):
    from haywire.core.library.haybale_toml import read_haybale

    row = read_haybale(
        _write(tmp_path, 'id = "core"\nlabel = 3\ntags = "nope"\nauthors = ["Alice"]\n')
    )
    assert row.label == ""
    assert row.tags == []
    assert row.authors == []


def test_read_haybale_reads_deprecation(tmp_path):
    from haywire.core.library.haybale_toml import read_haybale

    row = read_haybale(
        _write(
            tmp_path,
            'id = "core"\n[deprecated]\nsince = "1.0.0"\nreason = "old"\n',
        )
    )
    assert row.deprecated is not None
    assert row.deprecated.since == "1.0.0"
    assert row.deprecated.reason == "old"


def test_read_haybale_reflects_edits(tmp_path):
    from haywire.core.library.haybale_toml import read_haybale

    d = _write(tmp_path, 'id = "core"\ndescription = "before"\n')
    assert read_haybale(d).description == "before"
    _write(tmp_path, 'id = "core"\ndescription = "after"\n')
    assert read_haybale(d).description == "after"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/test_library/test_haybale_toml.py -k read_haybale -v`
Expected: FAIL — `ImportError: cannot import name 'read_haybale'`

- [ ] **Step 3: Replace `LibraryDisplay` with `read_haybale`**

In `packages/haywire-core/src/haywire/core/library/haybale_toml.py`, delete the entire `LibraryDisplay` class, the `_display_cache` declaration, `read_display`, and `_display_from` (currently lines 235-338). Replace them with:

```python
#: (path, mtime_ns) -> parsed row. The overview re-renders on every panel redraw,
#: so a parse per render is waste; a stat per render is not. Keyed on mtime so an
#: edit invalidates the entry without anyone having to remember to.
_row_cache: dict[Path, tuple[int, "Haybale"]] = {}


def read_haybale(package_dir: Path) -> "Haybale":
    """The library's declared metadata, read from *package_dir*'s ``haybale.toml``.

    The same :class:`~haywire.core.marketstall.types.Haybale` a marketstall feed
    yields — the two files carry the same fields, so a renderer takes one row and
    never asks which source it came from.

    Never raises: an unreadable or malformed file yields an empty row. That is the
    opposite of :func:`read_haybale_toml`'s import-time rule, and correct here — a
    renderer has a frame to draw, and a caller displaying a half-known library is
    better than a panel that cannot draw. Cached on the file's mtime, so repeated
    renders cost one ``stat``.

    ``source`` is ``"local"`` and the publish/transport fields are empty: this row
    was read off disk, not fetched from a feed.
    """
    from haywire.core.marketstall.types import Haybale

    source = package_dir / HAYBALE_TOML
    try:
        mtime = source.stat().st_mtime_ns
    except OSError:
        _row_cache.pop(package_dir, None)
        return Haybale(name="", source="local")

    cached = _row_cache.get(package_dir)
    if cached is not None and cached[0] == mtime:
        return cached[1]

    try:
        data = read_toml(source)
    except (toml.TomlDecodeError, OSError):
        row = Haybale(name="", source="local")
    else:
        row = _row_from(dict(data) if isinstance(data, dict) else {})

    _row_cache[package_dir] = (mtime, row)
    return row


def _row_from(data: dict) -> "Haybale":
    """Project a parsed document onto :class:`Haybale`, ignoring junk.

    Wrong-typed values are dropped rather than raised on — see
    :func:`read_haybale`: rendering degrades, it does not fail.
    """
    from haywire.core.marketstall.types import Deprecation, Haybale

    def _str(key: str) -> str:
        value = data.get(key)
        return value if isinstance(value, str) else ""

    def _list(key: str) -> list[str]:
        value = data.get(key)
        return [v for v in value if isinstance(v, str)] if isinstance(value, list) else []

    authors: list[tuple[str, str]] = []
    raw_authors = data.get("authors")
    if isinstance(raw_authors, list):
        for entry in raw_authors:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name")
            if not isinstance(name, str) or not name:
                continue
            url = entry.get("url")
            authors.append((name, url if isinstance(url, str) else ""))

    deprecated = None
    raw_dep = data.get("deprecated")
    if isinstance(raw_dep, dict):
        since = raw_dep.get("since")
        if isinstance(since, str) and since:
            reason = raw_dep.get("reason")
            successor = raw_dep.get("successor")
            deprecated = Deprecation(
                since=since,
                reason=reason if isinstance(reason, str) else "",
                successor=successor if isinstance(successor, str) else "",
            )

    return Haybale(
        name=_str("name"),
        id=_str("id"),
        version=_str("version"),
        label=_str("label"),
        description=_str("description"),
        tags=_list("tags"),
        os=_list("os"),
        on_reload=_str("on_reload") or "none",
        linked_libraries=_list("linked_libraries"),
        origin=_str("origin"),
        origin_provider=_str("origin_provider"),
        notes=_str("notes"),
        examples_path=_str("examples_path"),
        tests_path=_str("tests_path"),
        homepage_url=_str("homepage_url"),
        documentation_url=_str("documentation_url"),
        issues_url=_str("issues_url"),
        authors=authors,
        deprecated=deprecated,
        # Read off disk, not fetched: this row has no feed coordinates.
        source="local",
    )
```

Update `__all__` at the top of the file: remove `"LibraryDisplay"` and `"read_display"`, add `"read_haybale"`.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/core/test_library/test_haybale_toml.py -v`
Expected: PASS.

- [ ] **Step 5: Verify no import cycle**

Run: `uv run python -c "from haywire.core.library.haybale_toml import read_haybale; from pathlib import Path; print(read_haybale(Path('barn/haybale-example/haybale_example')))"`
Expected: a `Haybale(...)` repr with `name='haybale-example'` and `source='local'`. If it raises `ImportError` about a circular import, the `Haybale` import must stay inside the function bodies (it already is) — check you did not hoist it to module level.

- [ ] **Step 6: Commit**

```bash
git add packages/haywire-core/src/haywire/core/library/haybale_toml.py tests/core/test_library/test_haybale_toml.py
git commit -m "feat(library)!: read_haybale returns a Haybale; delete LibraryDisplay

BREAKING CHANGE: LibraryDisplay and read_display are removed. read_haybale
returns the full Haybale row, so a renderer takes one value regardless of
whether the library is installed or only catalogued."
```

---

### Task 3: Migrate the five `read_display` call sites

Implements D4's call-site rename. No behaviour change.

**Files:**
- Modify: `barn/haybale-marketplace/haybale_marketplace/editors/library_browser_editor.py:17,57`
- Modify: `barn/haybale-marketplace/haybale_marketplace/editors/_overview_edit_dialog.py:39,137`
- Modify: `barn/haybale-studio/haybale_studio/farmhands/catalog.py:18,66`
- Modify: `packages/haywire-studio/src/haywire_studio/packaging/docs/extract.py:9,156`
- Modify: `barn/haybale-marketplace/haybale_marketplace/editors/library_overview_editor.py:56,336`
- Modify: `packages/haywire-core/src/haywire/core/publishing/marketstall.py:15-16,99,105`

**Interfaces:**
- Consumes: `read_haybale` from Task 2.

- [ ] **Step 1: Rename in the four pure-read sites**

In each of `library_browser_editor.py`, `_overview_edit_dialog.py`, `farmhands/catalog.py`, and `packaging/docs/extract.py`:

- change the import `read_display` → `read_haybale`
- change the call `read_display(` → `read_haybale(`
- rename the local variable `display` → `row`

All four use only `.description` and `.tags`, which are identical on `Haybale`.

- [ ] **Step 2: Rewrite the publisher to read the row directly**

Implements D6 (publisher reads `declared.name`, not pyproject).

In `packages/haywire-core/src/haywire/core/publishing/marketstall.py`:

Change the import block (lines 14-17) from `LibraryDisplay, read_display` to `read_haybale`.

Replace line 99 with:

```python
    declared = read_haybale(module_dir) if module_dir else Haybale(name="")
```

Replace line 100 (`name = project.get("name", lib_dir.name)`) with:

```python
    name = declared.name or lib_dir.name
```

Replace line 105 (`author = declared.author_names`) — delete it entirely.

In the `return Haybale(...)` block (line 167), replace `author=author,` with `authors=list(declared.authors),` and add `id=declared.id,` beneath `name=name,`.

Update the comment at lines 95-97 to read:

```python
    # haybale.toml is canon for everything descriptive AND for name/version.
    # Only `require` below is derived from pyproject — it is a projection of
    # [project] dependencies, which pyproject does own.
```

- [ ] **Step 3: Run the affected suites**

Run: `uv run pytest tests/studio/ tests/marketplace/ tests/share_pipeline/ -q`
Expected: PASS. A failure mentioning `author_names` means a site was missed — grep for it.

- [ ] **Step 4: Confirm `read_display` is gone**

Run: `grep -rn --include="*.py" "read_display\|LibraryDisplay\|author_names" packages/ barn/ tests/ scripts/`
Expected: no output.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor: migrate read_display call sites to read_haybale

The publisher now reads name and authors from haybale.toml rather than
pyproject, making the 'only version and require come from pyproject'
comment true."
```

---

### Task 4: `haybale.toml` is canon for `name` and `version`

Implements D6, D7.

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/library/haybale_toml.py:59,209-214`
- Modify: `packages/haywire-core/src/haywire/core/publishing/generate.py:30-34`
- Test: `tests/core/test_library/test_haybale_toml.py`, `tests/studio/test_docs/` (drift)

**Interfaces:**
- Produces: `read_haybale_toml()` now returns a `name` key. `PROJECT_FIELDS` includes `version`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/core/test_library/test_haybale_toml.py`:

```python
def test_read_haybale_toml_returns_name(tmp_path):
    from haywire.core.library.haybale_toml import read_haybale_toml

    fields = read_haybale_toml(
        _write(tmp_path, 'name = "haybale-core"\nid = "core"\nversion = "1.0.0"\n')
    )
    assert fields["name"] == "haybale-core"


def test_version_is_projected_into_pyproject():
    from haywire.core.publishing.generate import PROJECT_FIELDS

    assert PROJECT_FIELDS["version"] == "version"
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/core/test_library/test_haybale_toml.py -k "returns_name or projected_into_pyproject" -v`
Expected: FAIL — `KeyError: 'name'`.

- [ ] **Step 3: Add `name` to `_STR_FIELDS`**

In `haybale_toml.py`, change line 59 to:

```python
_STR_FIELDS = ("id", "name", "label", "on_reload", "description", "version")
```

Update the comment above it (lines 49-58) by replacing its last sentence with:

```python
#: ``name`` and ``version`` are canon here; ``pyproject.toml`` carries generated
#: copies of both, because pip reads that file and cannot read this one.
```

- [ ] **Step 4: Reword the fatal-version message**

Replace the `raise` block at lines 209-214 with:

```python
    if not fields.get("version"):
        raise HaybaleTomlError(
            f"{source}: `version` is required and is canon here — "
            f"`pyproject.toml` carries a generated copy. Bump with "
            f"scripts/bump_version.py or the share wizard rather than by hand."
        )
```

- [ ] **Step 5: Project `version` into pyproject**

In `packages/haywire-core/src/haywire/core/publishing/generate.py`, replace `PROJECT_FIELDS` and its comment (lines 26-34) with:

```python
#: ``[project]`` keys generated from haybale.toml, and where each comes from.
#: ``haybale.toml`` is canon for all of these; ``pyproject.toml`` carries the
#: generated copy because pip, uv and PyPI read that file and cannot read this
#: one. Drift is therefore reported against pyproject, never the other way.
PROJECT_FIELDS = {
    "name": "name",
    "version": "version",
    "description": "description",
    "keywords": "tags",
}
```

- [ ] **Step 6: Run the tests**

Run: `uv run pytest tests/core/test_library/ tests/studio/ tests/share_pipeline/ -q`
Expected: PASS. A drift test asserting `version` is absent from the projection must be updated to expect it — that is the intended behaviour change.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat(library)!: haybale.toml is canon for name and version

pyproject.toml still carries a literal version (pip cannot read haybale.toml),
but it is now a generated copy and drift is reported against it."
```

---

### Task 5: `InstallType.NOT_INSTALLED`

Implements D13.

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/library/install_type.py:8-25`
- Test: `tests/core/test_libraries/test_install_type.py`

**Interfaces:**
- Produces: `InstallType.NOT_INSTALLED`.

- [ ] **Step 1: Write the failing test**

Append to `tests/core/test_libraries/test_install_type.py`:

```python
def test_not_installed_is_not_editable():
    from haywire.core.library.install_type import InstallType

    assert InstallType.NOT_INSTALLED.value == "not_installed"
    assert InstallType.NOT_INSTALLED.is_editable() is False


def test_not_installed_is_not_framework_origin():
    from haywire.core.library.info import LibraryInfo
    from haywire.core.library.install_type import InstallType
    from haywire.core.marketstall import Haybale
    from haywire.core.library.identity import LibraryIdentity
    from haybale_marketplace.library_origin import LibraryOrigin, compute_library_origin

    info = LibraryInfo(
        row=Haybale(name="haybale-x", version="1.0.0", source="pypi"),
        identity=LibraryIdentity(id="x"),
        enabled=False,
        install_type=InstallType.NOT_INSTALLED,
        distribution_name="haybale-x",
    )
    origin = compute_library_origin(info, None, catalog_entry=info.row)
    assert origin is LibraryOrigin.PYPI
    assert origin.is_protected is False
```

> The second test depends on Task 6's `LibraryInfo` shape. Run only the first test until Task 6 lands, then re-run both.

- [ ] **Step 2: Run the first test to verify it fails**

Run: `uv run pytest tests/core/test_libraries/test_install_type.py::test_not_installed_is_not_editable -v`
Expected: FAIL — `AttributeError: NOT_INSTALLED`.

- [ ] **Step 3: Add the member**

In `packages/haywire-core/src/haywire/core/library/install_type.py`, add after the `FOLDER` line:

```python
    NOT_INSTALLED = "not_installed"  # Catalogued but absent from this environment
```

Extend the class docstring:

```python
    """Types of library installations.

    ``NOT_INSTALLED`` means the library is absent from this environment — a
    catalog row the user could install. It does **not** mean "was removed": an
    uninstall leaves no ``LibraryInfo`` at all.
    """
```

- [ ] **Step 4: Run the first test**

Run: `uv run pytest tests/core/test_libraries/test_install_type.py::test_not_installed_is_not_editable -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/library/install_type.py tests/core/test_libraries/test_install_type.py
git commit -m "feat(library): add InstallType.NOT_INSTALLED"
```

---

### Task 6: `LibraryInfo` carries the metadata row

Implements D9.

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/library/info.py`
- Modify: `barn/haybale-marketplace/haybale_marketplace/library_manager.py:690-702`
- Test: `tests/marketplace/test_library_info_row.py` (create)

**Interfaces:**
- Consumes: `Haybale` (Task 1), `read_haybale` (Task 2), `InstallType.NOT_INSTALLED` (Task 5).
- Produces: `LibraryInfo(row, identity, enabled, install_type, distribution_name)`; `LibraryManager.entry_for_haybale(pkg) -> LibraryInfo`.

- [ ] **Step 1: Write the failing tests**

Create `tests/marketplace/test_library_info_row.py`:

```python
"""LibraryInfo carries a Haybale row whether or not the library is installed."""

from haywire.core.library.identity import LibraryIdentity
from haywire.core.library.info import LibraryInfo
from haywire.core.library.install_type import InstallType
from haywire.core.marketstall import Haybale


def test_installed_info_carries_the_row():
    info = LibraryInfo(
        row=Haybale(name="haybale-x", version="1.0.0", label="X", source="local"),
        identity=LibraryIdentity(id="x", label="X", version="1.0.0"),
        enabled=True,
        install_type=InstallType.EDITABLE,
        distribution_name="haybale-x",
    )
    assert info.installed is True
    assert info.row.label == "X"


def test_not_installed_info_has_empty_install_state():
    info = LibraryInfo(
        row=Haybale(name="haybale-x", version="2.0.0", label="X", source="pypi"),
        identity=LibraryIdentity(),
        enabled=False,
        install_type=InstallType.NOT_INSTALLED,
        distribution_name="",
    )
    assert info.installed is False
    assert info.enabled is False
    assert info.row.version == "2.0.0"


def test_entry_for_haybale_builds_a_not_installed_info():
    from haybale_marketplace.library_manager import LibraryManager

    pkg = Haybale(name="haybale-x", version="2.0.0", label="X", source="pypi")
    info = LibraryManager.entry_for_haybale(pkg)
    assert info.installed is False
    assert info.install_type is InstallType.NOT_INSTALLED
    assert info.row is pkg
    assert info.distribution_name == "haybale-x"
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/marketplace/test_library_info_row.py -v`
Expected: FAIL — `TypeError: LibraryInfo.__init__() got an unexpected keyword argument 'row'`.

- [ ] **Step 3: Widen `LibraryInfo`**

Replace the whole body of `packages/haywire-core/src/haywire/core/library/info.py` with:

```python
# packages/haywire-core/src/haywire/core/library/info.py
"""
LibraryInfo — a library as the Library Manager sees it.

Pairs the library's declared metadata (a ``Haybale``, read from its own
``haybale.toml`` or taken from a marketstall row) with the install state
discovered during scanning. Built for catalogued-but-absent libraries too, so
the browser and the detail editor consume one type either way.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .identity import LibraryIdentity
from .install_type import InstallType

if TYPE_CHECKING:
    from haywire.core.marketstall.types import Haybale


@dataclass(frozen=True)
class LibraryInfo:
    """A library and, when it is installed here, its install state.

    Attributes:
        row:               Declared metadata. The same shape whether it came from
                           the library's ``haybale.toml`` or from a feed.
        identity:          Runtime handles (``folder_path``, ``module_name``,
                           ``linked_libraries``). Empty when not installed.
        enabled:           Whether the library is currently enabled. ``False``
                           when not installed.
        install_type:      How the library reached this environment, or
                           ``NOT_INSTALLED``.
        distribution_name: Pip package name. Empty for folder installs.
    """

    row: "Haybale"
    identity: LibraryIdentity = field(default_factory=LibraryIdentity)
    enabled: bool = False
    install_type: InstallType = InstallType.NOT_INSTALLED
    distribution_name: str = ""

    @property
    def installed(self) -> bool:
        """Whether this library is present in this Python environment."""
        return self.install_type is not InstallType.NOT_INSTALLED
```

- [ ] **Step 4: Update the constructor and add the catalog path**

In `barn/haybale-marketplace/haybale_marketplace/library_manager.py`, replace `get_installed_library` (lines 690-702) with:

```python
    def get_installed_library(self, library_id: str) -> LibraryInfo:
        """Return summary information for one installed library."""
        identity = self.registry.get_library_identity(library_id)
        install_type = self.registry.get_library_install_type(library_id)
        enabled = self.registry.is_library_enabled(library_id)
        dist_name = self.registry.get_library_distribution_name(library_id)

        # Metadata comes off haybale.toml at the point of use, not off the
        # identity built at import — that is what makes an edit visible without
        # a reload.
        row = read_haybale(Path(identity.folder_path)) if identity.folder_path else Haybale(name="")

        return LibraryInfo(
            row=row,
            identity=identity,
            enabled=enabled,
            install_type=install_type or InstallType.FOLDER,
            distribution_name=dist_name or "",
        )

    @staticmethod
    def entry_for_haybale(pkg: "Haybale") -> LibraryInfo:
        """Wrap a catalog row as a not-installed :class:`LibraryInfo`.

        The counterpart to :meth:`get_installed_library` for libraries that
        exist only in a feed, so the browser and the detail editor consume one
        type regardless of install state.
        """
        return LibraryInfo(
            row=pkg,
            identity=LibraryIdentity(),
            enabled=False,
            install_type=InstallType.NOT_INSTALLED,
            distribution_name=pkg.name,
        )
```

Add to that file's imports (top of file, alongside the existing `haywire.core` imports):

```python
from haywire.core.library.haybale_toml import read_haybale
from haywire.core.library.identity import LibraryIdentity
from haywire.core.marketstall import Haybale
```

`Path` and `LibraryInfo` are already imported there; confirm with `grep -n "^from\|^import" barn/haybale-marketplace/haybale_marketplace/library_manager.py | head -30`.

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/marketplace/test_library_info_row.py tests/core/test_libraries/test_install_type.py -v`
Expected: PASS (both tests from Task 5 now pass too).

- [ ] **Step 6: Fix remaining `LibraryInfo(` construction sites**

Run: `grep -rn --include="*.py" "LibraryInfo(" packages/ barn/ tests/`

Every site must now pass `row=`. For test fixtures, `row=Haybale(name="haybale-x", version="1.0.0")` is sufficient unless the test asserts on metadata.

- [ ] **Step 7: Full gate and commit**

Run: `uv run pytest -m "not browser and not perf" -q > /tmp/t6.log 2>&1; echo "exit=$?"; grep -E "^FAILED|^ERROR" /tmp/t6.log`
Expected: `exit=0`.

```bash
git add -A
git commit -m "feat(library)!: LibraryInfo carries its metadata row

BREAKING CHANGE: LibraryInfo gains a required `row: Haybale` field and now
represents catalogued-but-not-installed libraries, discriminated by
InstallType.NOT_INSTALLED."
```

---

### Task 7: One-parameter rendering

Implements D9's editor changes and D12.

**Files:**
- Modify: `barn/haybale-marketplace/haybale_marketplace/editors/library_browser_editor.py:37-76,413-644,646-700,735-745`
- Modify: `barn/haybale-marketplace/haybale_marketplace/editors/library_overview_editor.py:121-155,202-250,289-350,381-388,622-645`
- Modify: `barn/haybale-marketplace/haybale_marketplace/editors/_overview_install_flow.py:81`
- Test: `tests/marketplace/test_overview_links.py`

**Interfaces:**
- Consumes: `LibraryInfo` with `row` (Task 6), `LibraryManager.entry_for_haybale` (Task 6).
- Produces: `collect_overview_links(row: Haybale) -> list[tuple[str, str]]` including an Issues link; `_render_center(info: LibraryInfo, context)`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/marketplace/test_overview_links.py`. That file's existing line 2 imports
`Haybale` from the deep path; leave it for now — Task 9 converts it, and these new tests
already use the canonical path.

```python
def test_issues_url_is_surfaced():
    from haybale_marketplace.editors.library_overview_editor import collect_overview_links
    from haywire.core.marketstall import Haybale

    links = collect_overview_links(
        Haybale(name="haybale-x", version="1.0.0", issues_url="https://issues.test")
    )
    assert ("Issues", "https://issues.test") in links


def test_links_render_for_a_project_local_row():
    """A library with no feed row still surfaces what its haybale.toml declares."""
    from haybale_marketplace.editors.library_overview_editor import collect_overview_links
    from haywire.core.marketstall import Haybale

    links = collect_overview_links(
        Haybale(
            name="haybale-x",
            version="1.0.0",
            source="local",
            origin="https://github.test/o/r",
            homepage_url="https://home.test",
            documentation_url="https://docs.test",
            issues_url="https://issues.test",
        )
    )
    labels = [label for label, _ in links]
    assert labels == ["Source", "Documentation", "Issues"]


def test_no_links_when_nothing_declared():
    from haybale_marketplace.editors.library_overview_editor import collect_overview_links
    from haywire.core.marketstall import Haybale

    assert collect_overview_links(Haybale(name="haybale-x", version="1.0.0")) == []
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/marketplace/test_overview_links.py -k "issues or project_local" -v`
Expected: FAIL — Issues is absent from the returned list.

- [ ] **Step 3: Add the Issues link**

In `library_overview_editor.py`, in `collect_overview_links`, after the `documentation_url` block, insert:

```python
    if pkg.issues_url:
        links.append(("Issues", pkg.issues_url))
```

Add to that function's docstring, after the `documentation_url` paragraph:

```
    ``issues_url`` is likewise absolute and used verbatim.
```

- [ ] **Step 4: Collapse `_rebuild` and `_render_center` to one parameter**

In `library_overview_editor.py`, replace the `_rebuild` dispatch (lines 218-227) with:

```python
        if lib is None:
            self._render_placeholder()
            return

        self._render_center(lib, context)
```

Change the `_render_center` signature (line 289) to:

```python
    def _render_center(self, info: "LibraryInfo", context: "SessionContext"):
```

Update its docstring to:

```python
        """Render one library — installed or merely catalogued.

        Takes a single :class:`LibraryInfo`: metadata comes off ``info.row``
        whatever its source, and install-state branches read ``info.installed``.
        """
```

Delete `_lookup_marketplace_pkg` entirely (lines 229-249) — the update check now compares `info.row.version` against the installed version.

Replace the display-property block (lines 331-349) with:

```python
        row = info.row
        name = row.label or row.name
        version = row.version
        description = row.description
        tags = list(row.tags)
        installed_lib = info if info.installed else None
```

Replace every later reference to `marketplace_pkg` with `row`, and every `installed_lib.identity.X` with `info.identity.X`. Replace the `_title_url` line (381) with:

```python
                        _title_url = row.homepage_url
```

Replace the author block (lines 622-632, as amended earlier) with:

```python
                if row.authors:
                    with ui.row().classes("items-center gap-1"):
                        ui.label("By").classes("text-xs hw-text-dim")
                        for i, (_name, _url) in enumerate(row.authors):
                            if i:
                                ui.label(",").classes("text-xs hw-text-dim")
                            if _url.startswith("http"):
                                ui.link(_name, _url, new_tab=True).classes("text-xs hw-text-accent")
                            else:
                                ui.label(_name).classes("text-xs hw-text-dim")
```

Replace the links call (line 635) with:

```python
                _links = collect_overview_links(row)
```

- [ ] **Step 5: Delete `_LibView` and route the browser through `LibraryInfo`**

In `library_browser_editor.py`, delete the `_LibView` class and `_lib_view` function (lines 37-76). Remove the now-unused `NamedTuple` and `read_display`/`read_haybale` imports if nothing else uses them.

In `_render_list`, wrap catalog rows as they are collected. Replace the three helper closures (lines 483-497) with:

```python
        def _label(info) -> str:
            return info.row.label or info.row.name

        def _enabled(info) -> bool:
            return info.enabled

        def matches(info) -> bool:
            if not q:
                return True
            row = info.row
            return (
                q in (row.label or row.name).lower()
                or bool(row.description and q in row.description.lower())
                or any(q in t.lower() for t in row.tags)
            )
```

Where the available-package list is built, wrap each `Haybale` with `manager.entry_for_haybale(entry)` so every list holds `LibraryInfo`.

Replace the head of `_library_item` (lines 654-659) with:

```python
        row = lib.row
        label = row.label or row.name or "?"
        version = row.version
```

and replace the later `getattr(lib, "stale", ...)` / `getattr(lib, "last_seen", ...)` / `getattr(lib, "name", ...)` probes with `row.stale`, `row.last_seen`, `row.name`.

In `_overview_install_flow.py` line 82, replace the probe with:

```python
        if active is not None and active.row.name == pkg.name:
```

- [ ] **Step 6: Run the marketplace suite**

Run: `uv run pytest tests/marketplace/ tests/studio/ -q`
Expected: PASS.

- [ ] **Step 7: Verify in the running studio**

Run: `uv run haywire` and open the Marketplace. Check, in order:
1. A `barn/` library (e.g. `haybale-example`) shows **Source / Documentation / Issues** links — previously it showed none.
2. A not-yet-installed catalog entry shows its author and homepage.
3. A library with two authors shows both, each linked when it declares a URL.

Stop the studio with Ctrl-C.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat(marketplace): render the library detail page from one row

_render_center takes a single LibraryInfo, so links now render for
project-local libraries and issues_url is surfaced. Deletes _LibView and the
hasattr/getattr probing it duplicated."
```

---

### Task 8: Delete `LibraryIdentity`'s transitional fields

Implements D10. Sequenced last so it can be dropped without unpicking the rest.

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/library/identity.py:63-104`
- Modify: `packages/haywire-core/src/haywire/core/library/haybale_toml.py:155-175`
- Modify: `packages/haywire-core/src/haywire/ui/themes/registry.py:18-28`
- Modify: `packages/haywire-core/src/haywire/core/settings/registry.py:38-48`
- Modify: `packages/haywire-core/src/haywire/core/library/utils.py:69-80`

**Interfaces:**
- Produces: `LibraryIdentity` without `description`, `url`, `author`, `author_url`, `tags`.

> Scope note: a grep for readers of these five fields returns **zero production
> hits** — the migration the docstring describes is already complete. Only the
> declarations, the `_fields_from` projection, three framework constructors and
> ~15 test fixtures still mention them.

- [ ] **Step 1: Confirm there are no readers**

Run: `grep -rn --include="*.py" -e "identity\.author_url" -e "identity\.url\b" packages/ barn/ scripts/`
Expected: no output. If there are hits, migrate each to `read_haybale(Path(identity.folder_path)).<field>` before continuing.

- [ ] **Step 2: Delete the fields**

In `packages/haywire-core/src/haywire/core/library/identity.py`, delete these five lines from the dataclass:

```python
    description: str = ""
    url: str = ""
    author: str = ""
    author_url: str = ""
    tags: list[str] | None = None  # Searchable tags for marketplace/discovery
```

In `__post_init__`, delete:

```python
        if self.tags is None:
            self.tags = []
```

Replace the docstring paragraph about transitional fields with:

```python
    """A library as loaded in this process.

    Populated by ``@library(...)``: ``id``, ``folder_path``, ``module_name`` and
    ``file_watcher`` from the call itself, the rest — including ``version`` —
    read out of ``haybale.toml``.

    Carries only what cannot be answered by a file read: ``label`` (logged and
    rendered from inside the registry), ``linked_libraries`` (read during module
    registration, inside the import machinery), and ``on_reload`` (read by
    ``_hints_for_library`` *after* a library is evicted, when its files may
    already be gone). Everything descriptive is read at the point of use with
    ``read_haybale()``, so an edit is visible without a reload.
    """
```

- [ ] **Step 3: Delete the projection block**

In `haybale_toml.py`, delete the whole transitional block in `_fields_from` — the comment beginning "Two fields whose file spelling differs" through the end of the `authors` handling (currently lines 155-175). The function now ends with the `_LIST_FIELDS` loop followed by `return fields`.

- [ ] **Step 4: Fix the three framework constructors**

In `packages/haywire-core/src/haywire/ui/themes/registry.py`, `packages/haywire-core/src/haywire/core/settings/registry.py` and `packages/haywire-core/src/haywire/core/library/utils.py`, delete the `description=`, `url=`, `author=`, `author_url=` kwargs from each `LibraryIdentity(...)` call. Keep `label`, `version`, `id`, `module_name`, `folder_path` and any others.

- [ ] **Step 5: Run the full gate**

Run: `uv run pytest -m "not browser and not perf" -q > /tmp/t8.log 2>&1; echo "exit=$?"; grep -E "^FAILED|^ERROR" /tmp/t8.log`
Expected: `exit=0`. Failures will be test fixtures passing the removed kwargs — delete those kwargs from each fixture.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor(library)!: drop LibraryIdentity's transitional fields

BREAKING CHANGE: LibraryIdentity no longer carries description, url, author,
author_url or tags. Read them from haybale.toml with read_haybale() instead.
Completes the migration ADR 0025 began."
```

---

### Task 9: Import discipline

Implements D11.

**Files:**
- Modify: `pyproject.toml:96-118`
- Modify: `barn/haybale-marketplace/haybale_marketplace/library_origin.py:29`
- Modify: `tests/studio/test_share_examples.py:15`
- Modify: `tests/share_pipeline/test_haybale_preconditions.py:279`
- Modify: `tests/marketplace/test_overview_links.py:2`
- Modify: `tests/marketplace/test_install_flow.py`, `tests/marketplace/test_add_source_flow.py`, and any other `tests/marketplace/*` hit by the grep in Step 1

- [ ] **Step 1: Find and fix every deep import outside the allowed paths**

Run: `grep -rln --include="*.py" "from haywire.core.marketstall.types import" packages/ barn/ tests/ scripts/ | grep -v "core/marketstall/" | grep -v "tests/marketstall/"`

In each file listed, change `from haywire.core.marketstall.types import Haybale` to
`from haywire.core.marketstall import Haybale`. Where the line imports other names too
(e.g. `Haybale, ProjectMarketplaceFile`), check each against
`packages/haywire-core/src/haywire/core/marketstall/__init__.py`'s `__all__`; names that
are re-exported move to the package import, names that are not stay on the deep import
line.

- [ ] **Step 2: Add the ruff rule**

In the root `pyproject.toml`, add to `[tool.ruff.lint]`:

```toml
extend-select = ["E501", "PT", "B", "TID"]
```

Then add these sections after `[tool.ruff.lint]`:

```toml
[tool.ruff.lint.flake8-tidy-imports.banned-api]
# Haybale is re-exported from the package root, and only that path is stable:
# the type is expected to move to haywire.core.library eventually, and a deep
# import turns that one-file move into an archaeology exercise.
"haywire.core.marketstall.types.Haybale".msg = "Import from haywire.core.marketstall instead."
```

And to `[tool.ruff.lint.per-file-ignores]`:

```toml
# The module's own siblings and its dedicated tests legitimately reach for the
# deep path — they move with the file.
"packages/haywire-core/src/haywire/core/marketstall/*" = ["TID251"]
"tests/marketstall/*" = ["TID251"]
```

- [ ] **Step 3: Verify the rule fires and the repo is clean**

Run: `uv run ruff check . 2>&1 | tail -5`
Expected: `All checks passed!`

Then prove the rule works — temporarily add `from haywire.core.marketstall.types import Haybale` to `barn/haybale-example/haybale_example/__init__.py`, run `uv run ruff check barn/haybale-example/`, confirm it reports `TID251`, then remove the line.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: pin Haybale's canonical import path

Deep imports of marketstall.types.Haybale are banned outside the module and
its own tests, so relocating the type later is a one-file change."
```

---

### Task 10: Documentation

Implements the §3 corrections from the decision record.

**Files:**
- Modify: `docs/reference/files/haybale-toml.md:148,154,161,165,168-171,329-333`
- Modify: `docs/reference/files/marketstall-toml.md:135,150,191`

- [ ] **Step 1: Correct the haybale.toml field matrix**

In `docs/reference/files/haybale-toml.md`, edit the matrix rows so they read:

```
| `name` | string | yes | ● | ● | `name` | Pip distribution name. Canon here; pyproject carries the generated copy. Immutable |
| `id` | string | yes | ● | ● | | Prefixes every component's registry key (`core:node:Add`). Immutable |
| `version` | string | yes | ● | ● | `version` | PEP 440, no `v`. Canon here; pyproject carries the generated copy. The git tag is derived from it |
| `os` | list[str] | no | ● | ● | | `macos`/`linux`/`windows`. Empty = everywhere. The only field that blocks installation |
| `tests_path` | string | no | ● | ● | | Project-relative path. Not surfaced in the UI |
| `[[authors]]` | table[] | no | ● | ● | `authors` | Repeatable `name` + optional `url`. The url reaches the marketstall but not pyproject |
```

- [ ] **Step 2: Correct the reader table**

Replace the `read_display` row (line 331) with:

```
| `read_haybale(package_dir)` | Rendering; returns a `Haybale` | Returns an empty row; cached on mtime |
```

- [ ] **Step 3: Correct the marketstall doc**

In `docs/reference/files/marketstall-toml.md`:

Line 135 — replace the `authors` row's transform column with `copy — repeatable [[authors]] tables, each with an optional url`.

Line 150 — replace the `source` row's value column with `generated — "git"` (wizard) / `"pypi"` (CI script) / `"local"` (a row read from a haybale.toml on disk, never published)`.

Line 191 — replace that inheritance row with:

```
| `[[authors]]` (repeatable, each with an optional `url`) | `[[authors]]` | Copied verbatim, URLs included |
```

- [ ] **Step 4: Verify the docs build**

Run: `uv run mkdocs build --strict 2>&1 | tail -5`
Expected: no warnings about the edited files.

- [ ] **Step 5: Commit**

```bash
git add docs/
git commit -m "docs: correct the haybale.toml and marketstall.toml field tables

os and tests_path are authored locally; name and version are canon in
haybale.toml; authors carry their URLs into the row; source may be 'local'."
```

---

## Final Verification

- [ ] **Full gate**

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-marketplace/haybale_marketplace/ barn/haybale-share/haybale_share/ barn/haybale-graph-editor/haybale_graph_editor/ barn/haybale-haystack/haybale_haystack/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-TEST_A/haybale_test_a/ tests/
uv run pytest -m "not browser and not perf" -q > /tmp/final.log 2>&1; echo "exit=$?"
grep -E "^FAILED|^ERROR" /tmp/final.log
```

Expected: ruff clean, mypy `Success`, pytest `exit=0`.

- [ ] **Regenerate library docs** (metadata reaches generated output)

```bash
uv run haywire docs --all
git diff --stat
```

Expected: either no diff, or diffs only where a library's declared metadata legitimately now flows through. Commit any regeneration separately.

## Out of scope

- Moving `Haybale` to `haywire.core.library` — Task 9 makes it a one-file change later.
- `LibraryIdentity.version` — read by the compatibility checker and hot-reload paths; revisit separately.
- Deleting `scripts/generate_marketstall.py` (dead — `ast`-parses `@library` fields ADR 0025 removed). Needs a CI check first; `bump_version.py`'s docstring cites it as a CI consumer of release config.
- Any rethink of the detail page's link presentation or information hierarchy.
