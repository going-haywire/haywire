# Framework Version Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make it impossible for a marketplace haybale install to silently move the running framework out from under the studio, give the user an in-app way to update the framework, and let a haybale author declare which framework versions their library needs.

**Architecture:** Five independent-but-ordered parts. (1) `LibraryManager.dry_run()`/`install()` pass `uv pip install -c <constraints>` pinning `haywire-core`/`haywire-studio`/`nicegui` to their **installed** versions, so an unsafe resolution fails at the resolver instead of succeeding silently. (2) The misnamed `Haybale.min_version` becomes `Haybale.version` (hard rename, strict parse). (3) A new `Haybale.requires_haywire` field carries a PEP 440 specifier, authored once per project at share time and written into two disjoint carriers (the wheel's `Requires-Dist` floor and the marketstall entry). (4) A check-for-updates control in the app shell writes a new pin into the root `pyproject.toml`, verifies it with `uv sync --dry-run` diffed against a baseline, then calls `app.shutdown()` and prints an `atexit` banner. (5) The scaffold pin becomes `>=X.Y.Z`.

**Tech Stack:** Python 3.11+, `packaging` (`Version`, `SpecifierSet`, `Requirement`), `toml`, `importlib.metadata`, `uv` (subprocess), NiceGUI 3.x, pytest + anyio.

## Global Constraints

- **Framework-owned packages** (the constraint set, exactly these three, no more): `haywire-core`, `haywire-studio`, `nicegui`. NOT the full `pip_publish_order` set — the in-monorepo `haybale-*` libraries are exactly what marketplace installs are supposed to upgrade.
- Constraints pin to **currently-installed exact versions**, read via `importlib.metadata.version()`. Never to a declared `Requires-Dist`.
- `dry_run()` and `install()` must pass **identical** uv flags. Divergence makes the pre-eviction set disagree with the real install (same rule as the existing `--no-sources`).
- **No back-compat alias** for `min_version`. Hard rename to `version` everywhere.
- `Haybale.version` is a strict `x.y.z` string parsed with `packaging.version.Version`. A `[[haybales]]` entry **without** `version` raises `MalformedMarketplaceError` — never parse to `""`.
- `[[caches]]` are **discarded and refetched** on parse failure (they are derived artifacts; a strict parser must not block the refresh that heals the file).
- `requires_haywire` stores a **full PEP 440 specifier** (`>=0.0.31`, `~=0.0.31`, `>=0.0.31,<1.0.0`), never a bare version.
- Specifier equality is **always** compared as parsed `SpecifierSet` objects, never as raw strings — `packaging` reorders on `str()` (`>=0.0.31,<1.0.0` → `<1.0.0,>=0.0.31`).
- **One project-wide** framework-requirement answer (lockstep, ADR 0023). Not per-library.
- `--yes` with no `--requires-haywire` flag **keeps the declared floor** (inert default, no refusal). Raising a floor always requires the explicit flag.
- **No ceiling by default.** The scaffold and the recommended option never emit an upper bound.
- The framework-update conflict check is worded **"No conflicts found"** — never a promise that the next launch will succeed.
- Line length 109 (`ruff`). CI runs both `ruff check` and `ruff format --check`.

### Pre-edit baseline (run before Task 1, and before each part)

```sh
uv run ruff check .
uv run ruff format --check .
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-TEST_A/haybale_test_a/
uv run pytest -m "not browser and not perf"
```

The codebase has no errors. Anything new after your edit is yours.

### Testing posture for this plan

Reuse existing test files. New test **files** are justified only for genuinely novel seams (the constraint-file builder, the pin writer, the conflict-check differ, the framework-requirement step). Everything else — the rename, `requires_haywire` parsing/serialization, the CLI flag — extends tests that already exist.

---

## Part 1 — Constraint-file gate

### Task 1: Framework constraint file

**Files:**
- Modify: `barn/haybale-marketplace/haybale_marketplace/library_manager.py:273-335`
- Test: `tests/test_library_manager_dry_run.py` (existing file — extend)

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `FRAMEWORK_PACKAGES: tuple[str, ...]` — module-level constant in `library_manager.py`.
  - `LibraryManager._framework_constraints(self) -> list[str]` — returns `["haywire-core==0.0.34", ...]` lines for packages that are installed; skips packages that are not.
  - `LibraryManager._write_constraints_file(self) -> Path | None` — writes the lines to a temp file, returns its path, or `None` when no framework package is installed.
  - `LibraryManager.FRAMEWORK_CONFLICT_MESSAGE: str` — the user-facing remedy text.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_library_manager_dry_run.py`:

```python
@pytest.mark.unit
def test_framework_constraints_pins_installed_versions():
    """The constraint set is exactly core/studio/nicegui, pinned == to what is
    installed — never to a declared Requires-Dist, which can itself be stale."""
    from haybale_marketplace.library_manager import FRAMEWORK_PACKAGES

    mgr = _make_manager()

    def fake_version(name: str) -> str:
        return {"haywire-core": "0.0.34", "haywire-studio": "0.0.34", "nicegui": "3.13.0"}[name]

    with patch("importlib.metadata.version", side_effect=fake_version):
        lines = mgr._framework_constraints()

    assert lines == ["haywire-core==0.0.34", "haywire-studio==0.0.34", "nicegui==3.13.0"]
    assert FRAMEWORK_PACKAGES == ("haywire-core", "haywire-studio", "nicegui")


@pytest.mark.unit
def test_framework_constraints_skips_missing_packages():
    """A package that isn't installed contributes no constraint — pinning a
    version we don't have would make every install unsatisfiable."""
    import importlib.metadata as _meta

    mgr = _make_manager()

    def fake_version(name: str) -> str:
        if name == "nicegui":
            raise _meta.PackageNotFoundError(name)
        return "0.0.34"

    with patch("importlib.metadata.version", side_effect=fake_version):
        lines = mgr._framework_constraints()

    assert lines == ["haywire-core==0.0.34", "haywire-studio==0.0.34"]


@pytest.mark.unit
async def test_dry_run_passes_constraints_file():
    """dry_run() must pass -c <file> so a haybale that needs a different core
    version fails at the resolver instead of silently moving the framework."""
    mgr = _make_manager()
    captured: dict[str, list[str]] = {}

    async def fake_run(args, on_output):
        captured["args"] = list(args)
        idx = args.index("-c")
        captured["body"] = Path(args[idx + 1]).read_text()
        return True, ""

    with patch.object(mgr, "_framework_constraints", return_value=["haywire-core==0.0.34"]):
        with patch.object(mgr, "_run_uv_streaming", side_effect=fake_run):
            await mgr.dry_run("haybale-foo")

    assert "-c" in captured["args"]
    assert captured["body"] == "haywire-core==0.0.34\n"


@pytest.mark.unit
async def test_install_passes_identical_flags_to_dry_run():
    """install() and dry_run() must agree on every resolver-affecting flag, or
    the pre-eviction set and the actual install diverge."""
    mgr = _make_manager()
    seen: list[list[str]] = []

    async def fake_run(args, on_output):
        seen.append(list(args))
        return True, ""

    mgr.registry.list_names.return_value = []
    with patch.object(mgr, "_framework_constraints", return_value=["haywire-core==0.0.34"]):
        with patch.object(mgr, "_run_uv_streaming", side_effect=fake_run):
            await mgr.install("haybale-foo", lambda line: None)

    dry_flags = [a for a in seen[0] if a.startswith("-") and a != "-c"]
    install_flags = [a for a in seen[1] if a.startswith("-") and a != "-c"]
    assert dry_flags == ["--dry-run", "--no-sources"]
    assert install_flags == ["--no-sources"]
    assert "-c" in seen[0] and "-c" in seen[1]


@pytest.mark.unit
async def test_dry_run_resolver_failure_names_the_shell_control():
    """A framework-blocked install must tell the user where the remedy lives —
    the shell's check-for-updates control — not dump raw resolver text alone."""
    mgr = _make_manager()

    async def fake_run(args, on_output):
        return False, "error: no solution found: haywire-core==0.0.34 is unsatisfiable"

    with patch.object(mgr, "_framework_constraints", return_value=["haywire-core==0.0.34"]):
        with patch.object(mgr, "_run_uv_streaming", side_effect=fake_run):
            with pytest.raises(RuntimeError) as exc:
                await mgr.dry_run("haybale-foo")

    assert "Check for updates" in str(exc.value)
    assert "no solution found" in str(exc.value)
```

Add `from pathlib import Path` to the imports at the top of that test file.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_library_manager_dry_run.py -v`
Expected: the five new tests FAIL with `ImportError: cannot import name 'FRAMEWORK_PACKAGES'` / `AttributeError: ... has no attribute '_framework_constraints'`. The nine pre-existing tests still PASS.

- [ ] **Step 3: Implement the constraint builder**

In `barn/haybale-marketplace/haybale_marketplace/library_manager.py`, add after `_DECLARABLE_OS_VALUES` (line 35):

```python
# Packages the marketplace must never move. Pinned to their installed exact
# versions on every install, so a haybale whose tree wants a different
# framework version fails at uv's resolver instead of silently swapping the
# framework out from under the running studio. Deliberately NOT the full
# publish set: the in-monorepo haybale-* libraries are exactly what a
# marketplace install is supposed to upgrade.
FRAMEWORK_PACKAGES: tuple[str, ...] = ("haywire-core", "haywire-studio", "nicegui")
```

Then add these three members to `LibraryManager`, immediately before `dry_run()`:

```python
    FRAMEWORK_CONFLICT_MESSAGE = (
        "This library needs a different version of the Haywire framework than the "
        "one you are running. Update Haywire first — use “Check for updates” in the "
        "top bar — then install this library again."
    )

    def _framework_constraints(self) -> list[str]:
        """``name==version`` lines pinning every installed framework package.

        Read from the running venv, not from any declared ``Requires-Dist``:
        a declared want can itself be stale, whereas what is running cannot.
        A package that isn't installed contributes nothing — pinning a version
        we do not have would make every install unsatisfiable.
        """
        lines: list[str] = []
        for name in FRAMEWORK_PACKAGES:
            try:
                lines.append(f"{name}=={importlib.metadata.version(name)}")
            except importlib.metadata.PackageNotFoundError:
                continue
        return lines

    def _write_constraints_file(self) -> Path | None:
        """Write the framework constraints to a temp file; return its path.

        Returns None when nothing is installed to constrain, so the caller
        omits ``-c`` entirely rather than passing an empty file.
        """
        import tempfile

        lines = self._framework_constraints()
        if not lines:
            return None
        handle = tempfile.NamedTemporaryFile(
            "w", suffix=".txt", prefix="haywire-constraints-", delete=False
        )
        with handle:
            handle.write("\n".join(lines) + "\n")
        return Path(handle.name)
```

- [ ] **Step 4: Pass `-c` from `dry_run()` and translate the failure**

Replace the body of `dry_run()` (lines 284-305) with:

```python
        constraints = self._write_constraints_file()
        if Path(install_spec).is_dir():
            args = ["install", "--dry-run", "-e", install_spec]
        else:
            # --no-sources: ignore [tool.uv.sources] inside the resolved tree.
            # A published haybale's git+URL may clone into a workspace whose
            # root pyproject.toml has dev-time path overrides (uv treats the
            # subdirectory as a workspace member and applies them). Without
            # this flag the resolver replaces already-installed editable
            # haywire packages with bogus path-traversal git URLs.
            args = ["install", "--dry-run", "--no-sources", install_spec]
        if constraints is not None:
            args += ["-c", str(constraints)]

        collected: list[str] = []

        def _collect(line: str) -> None:
            collected.append(line)

        success, stderr = await self._run_uv_streaming(args, _collect)
        if not success:
            raise RuntimeError(f"{self.FRAMEWORK_CONFLICT_MESSAGE}\n\n{stderr}")

        full_output = "\n".join(collected)
        return self._parse_dry_run_removals(full_output)
```

- [ ] **Step 5: Pass the identical `-c` from `install()`**

Replace lines 320-325 of `install()` with:

```python
        constraints = self._write_constraints_file()
        if Path(install_spec).is_dir():
            args = ["install", "-e", install_spec]
        else:
            # --no-sources and -c: see dry_run() for rationale. Must match the
            # dry-run flags exactly or the pre-eviction set and the actual
            # install diverge.
            args = ["install", "--no-sources", install_spec]
        if constraints is not None:
            args += ["-c", str(constraints)]
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest tests/test_library_manager_dry_run.py tests/test_library_manager_hints.py -v`
Expected: PASS (all, including the pre-existing ones).

- [ ] **Step 7: Lint, type-check, commit**

```bash
uv run ruff check barn/haybale-marketplace/ tests/test_library_manager_dry_run.py
uv run ruff format --check barn/haybale-marketplace/ tests/test_library_manager_dry_run.py
uv run pytest -m "not browser and not perf"
git add barn/haybale-marketplace/haybale_marketplace/library_manager.py tests/test_library_manager_dry_run.py
git commit -m "fix(marketplace): pin framework packages during haybale installs

uv pip install resolves fresh against the requested spec's tree, so an
already-installed haywire-core is only a reuse candidate. A haybale update
could silently move the framework out from under the running studio
(old studio + new core = ImportError). Pass -c pinning core/studio/nicegui
to their installed exact versions in both dry_run() and install(), and
point the resulting resolver failure at the shell's update control."
```

---

## Part 2 — `min_version` → `version`

Parts 2 and 3 are coupled and must land in this order, or the schema churns twice.

### Task 2: Rename the field and make it required

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/marketstall/types.py:19,44`
- Modify: `packages/haywire-core/src/haywire/core/marketstall/parsing.py:29-52`
- Modify: `packages/haywire-core/src/haywire/core/marketstall/refresh.py:41-67,158`
- Modify: `barn/haybale-marketplace/haybale_marketplace/editors/library_overview_editor.py:333,343,349,402`
- Modify: `barn/haybale-marketplace/haybale_marketplace/editors/library_browser_editor.py:516,521,537`
- Modify: `packages/haywire-studio/src/haywire_studio/packaging/share/marketstall.py:140`
- Modify: `scripts/generate_marketstall.py:166,205`
- Test: `tests/marketstall/test_haybale_dataclass.py`, `tests/marketstall/test_parsing.py`, `tests/marketstall/test_refresh.py` (existing files — extend + sweep)

**Interfaces:**
- Consumes: nothing.
- Produces: `Haybale.version: str` replaces `Haybale.min_version: str`. `_parse_haybale_entry` raises `MalformedMarketplaceError` when `version` is absent or empty.

- [ ] **Step 1: Write the failing tests**

Append to `tests/marketstall/test_parsing.py`:

```python
@pytest.mark.unit
def test_parse_haybale_entry_requires_version():
    """`version` is required. Parsing to "" silently disables update reporting
    (refresh skips entries with a falsy version), so absence must be loud."""
    from haywire.core.marketstall.errors import MalformedMarketplaceError
    from haywire.core.marketstall.parsing import _parse_haybale_entry

    with pytest.raises(MalformedMarketplaceError, match="version"):
        _parse_haybale_entry({"name": "haybale-foo"})


@pytest.mark.unit
def test_parse_haybale_entry_rejects_empty_version():
    from haywire.core.marketstall.errors import MalformedMarketplaceError
    from haywire.core.marketstall.parsing import _parse_haybale_entry

    with pytest.raises(MalformedMarketplaceError, match="version"):
        _parse_haybale_entry({"name": "haybale-foo", "version": ""})


@pytest.mark.unit
def test_parse_haybale_entry_no_longer_reads_min_version():
    """Hard rename, no back-compat alias: a legacy `min_version` key is not a
    substitute for `version`."""
    from haywire.core.marketstall.errors import MalformedMarketplaceError
    from haywire.core.marketstall.parsing import _parse_haybale_entry

    with pytest.raises(MalformedMarketplaceError, match="version"):
        _parse_haybale_entry({"name": "haybale-foo", "min_version": "0.1.0"})
```

Append to `tests/marketstall/test_refresh.py`:

```python
@pytest.mark.unit
def test_malformed_caches_are_discarded_not_fatal(tmp_path):
    """[[caches]] are derived artifacts refetched on every refresh. A strict
    parser must not let a malformed cache block the refresh that heals it."""
    from haywire.core.marketstall.parsing import parse_project_marketplace

    project = tmp_path / "marketplace.toml"
    project.write_text('[[caches]]\nname = "haybale-foo"\n')  # no version

    pm = parse_project_marketplace(project)

    assert pm.caches == []


@pytest.mark.unit
def test_malformed_caches_do_not_discard_heaps(tmp_path):
    """Only [[caches]] are derived. [[heaps]] are user-authored and must survive."""
    from haywire.core.marketstall.parsing import parse_project_marketplace

    project = tmp_path / "marketplace.toml"
    project.write_text(
        '[[heaps]]\nname = "haybale-local"\npath = "barn/haybale-local"\n\n'
        '[[caches]]\nname = "haybale-foo"\n'
    )

    pm = parse_project_marketplace(project)

    assert pm.caches == []
    assert [h["name"] for h in pm.heaps] == ["haybale-local"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/marketstall/test_parsing.py tests/marketstall/test_refresh.py -v -k "requires_version or empty_version or no_longer_reads or malformed_caches"`
Expected: FAIL — `_parse_haybale_entry` currently returns a `Haybale` with `min_version=""` instead of raising; `parse_project_marketplace` currently propagates the error.

- [ ] **Step 3: Rename the dataclass field**

In `packages/haywire-core/src/haywire/core/marketstall/types.py`, change line 19:

```python
    version: str
```

and line 44 inside `_TOML_FIELDS`:

```python
        "version",
```

- [ ] **Step 4: Make the parser strict and discard malformed caches**

In `parsing.py`, replace `_parse_haybale_entry` (lines 29-52) with:

```python
def _parse_haybale_entry(raw: dict) -> Haybale:
    """Parse one [[haybales]] (or [[caches]]) TOML entry into a Haybale.

    ``version`` is required. Defaulting it to "" would silently disable
    update reporting — refresh skips falsy-version entries — so an absent
    version is an error, matching the existing ``name`` check.
    """
    name = raw.get("name")
    if not isinstance(name, str) or not name:
        raise MalformedMarketplaceError("[[haybales]] entry missing required `name` field")
    version = raw.get("version")
    if not isinstance(version, str) or not version:
        raise MalformedMarketplaceError(f"[[haybales]] entry {name!r} missing required `version` field")
    return Haybale(
        name=name,
        version=version,
        label=raw.get("label", ""),
        description=raw.get("description", ""),
        author=raw.get("author", ""),
        source=raw.get("source", "pypi"),
        install_spec=raw.get("install_spec", name),
        tags=list(raw.get("tags", [])),
        os=list(raw.get("os", [])),
        dependencies=list(raw.get("dependencies", [])),
        source_url=raw.get("source_url", ""),
        docs_url=raw.get("docs_url", ""),
        examples_url=raw.get("examples_url", ""),
        tests_url=raw.get("tests_url", ""),
        via=raw.get("via", ""),
        last_seen=raw.get("last_seen", ""),
        stale=bool(raw.get("stale", False)),
    )
```

Replace the `caches` line in `parse_project_marketplace` (line 124) with:

```python
    # [[caches]] are derived artifacts, refetched on every refresh. A strict
    # parser must not block the very refresh that would heal a malformed file,
    # and _merge_cache reads the previous cache — so discard and refetch.
    # Cost: one cycle of `stale` bookkeeping. [[heaps]] above are user-authored
    # and stay strict.
    try:
        caches = [_parse_haybale_entry(raw) for raw in data.get("caches", [])]
    except MalformedMarketplaceError:
        caches = []
```

- [ ] **Step 5: Rename the remaining production usages**

`refresh.py` — replace `_count_updates_available` (lines 41-67):

```python
def _count_updates_available(final: list[Haybale]) -> int:
    """For each non-stale cached haybale, compare its
    `version` against the installed distribution version. Count
    entries where ``installed < cache.version``.

    Stale entries are skipped (the upstream wasn't reachable; the stored
    version is the old value and would falsely report "up-to-date").
    Uninstalled haybales are skipped (nothing to update).
    """
    import importlib.metadata as _meta

    from packaging.version import InvalidVersion, Version

    count = 0
    for h in final:
        if h.stale or not h.version:
            continue
        try:
            installed = _meta.version(h.name)
        except _meta.PackageNotFoundError:
            continue
        try:
            if Version(installed) < Version(h.version):
                count += 1
        except InvalidVersion:
            continue
    return count
```

`refresh.py:158` inside `mark_stale_against_previous`:

```python
                version=prev.version,
```

`packages/haywire-studio/src/haywire_studio/packaging/share/marketstall.py:140`:

```python
        version=version,
```

`scripts/generate_marketstall.py:166`:

```python
        "version": version,
```

and line 205 (inside the field-order tuple):

```python
    "version",
```

`barn/haybale-marketplace/haybale_marketplace/editors/library_overview_editor.py` — line 333 → `version = marketplace_pkg.version`; line 343 → `and marketplace_pkg.version`; line 349 → `update_available = Version(marketplace_pkg.version) > Version(`; line 402 → `hui.tag(f"v{marketplace_pkg.version} available", color="orange")`.

`barn/haybale-marketplace/haybale_marketplace/editors/library_browser_editor.py` — line 516 → `if not entry.version or not entry.name:`; line 521 → `if Version(entry.version) > Version(lib.identity.version):`; line 537 → `version="0.0.0",` (a synthesized heap entry: `version` is now required, and a heap has no published version, so the placeholder must at least parse as a `Version`).

- [ ] **Step 6: Sweep the existing tests**

Every test listed below constructs `Haybale(...)` or TOML bodies with `min_version`. Rename the keyword/key in place — these are existing tests being kept working, not new coverage:

```bash
grep -rl "min_version" tests/ | xargs sed -i '' 's/min_version/version/g'
```

Then fix the two docstrings that now read awkwardly, in `tests/marketstall/test_refresh.py`:
- line ~446: `"""An installed dist whose version is below the cache \`version\` counts` — leave as is after the sweep, it reads correctly.
- line ~486: `"""Stale cache entries hold OLD version values from a previous refresh` — likewise.

Then sweep any TOML bodies in tests that now lack a required `version` (the sweep above renames rather than removes, so this should be none — verify):

Run: `uv run pytest tests/marketstall/ tests/marketplace/ tests/scripts/test_generate_marketstall.py tests/test_marketplace_state.py tests/test_library_browser_os_gating.py tests/test_library_browser_provenance.py -v`
Expected: all PASS. Any failure naming a missing `version` field is a test body that needs one added.

- [ ] **Step 7: Sweep in-repo marketstall/stall files**

```bash
grep -rln "min_version" --include="*.toml" . | grep -v "/.venv/"
```

For each hit, rename the key to `version`. Then regenerate to confirm the generator agrees:

Run: `uv run python scripts/generate_marketstall.py --help` (confirm it still loads), then `uv run pytest tests/scripts/test_generate_marketstall.py -v`
Expected: PASS.

- [ ] **Step 8: Verify no `min_version` remains in code**

Run: `grep -rn "min_version" --include="*.py" --include="*.toml" . | grep -v "/.venv/" | grep -v "^./internals/"`
Expected: no output. (Docs are Task 12; `internals/` design notes stay as written.)

- [ ] **Step 9: Full suite, lint, type-check, commit**

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-TEST_A/haybale_test_a/
uv run pytest -m "not browser and not perf"
git add -A
git commit -m "refactor(marketstall)!: rename Haybale.min_version to version

The field was never a floor: it is written as the published version, shown
as the version, and compared as the version. Nothing resolves against it,
and the docs had to disclaim it. With requires_haywire (a real specifier)
arriving next, keeping a bare version called min_version would mislead.

Hard rename, no alias. version is now required — parsing to \"\" silently
disabled update reporting. [[caches]] are discarded and refetched on parse
failure so a malformed cache cannot block the refresh that heals it."
```

- [ ] **Step 10: Fix the one external stall**

The visiongraph marketstall (`haybale-visiongraph`, a gitignored local-only symlink in this repo, published from its own repo) still advertises `min_version`. Its `marketstall.toml` must be updated to `version` and re-published. If the repo is not available in this working tree, record the follow-up:

```bash
grep -rn "min_version" barn/haybale-visiongraph/ 2>/dev/null || echo "visiongraph not checked out — file a follow-up to rename its marketstall key"
```

---

## Part 3 — `requires_haywire`

### Task 3: The `requires_haywire` field

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/marketstall/types.py`
- Modify: `packages/haywire-core/src/haywire/core/marketstall/parsing.py:_parse_haybale_entry`
- Modify: `packages/haywire-core/src/haywire/core/marketstall/refresh.py:mark_stale_against_previous`
- Test: `tests/marketstall/test_haybale_dataclass.py`, `tests/marketstall/test_parsing.py` (existing files — extend)

**Interfaces:**
- Consumes: `Haybale.version` (Task 2).
- Produces: `Haybale.requires_haywire: str = ""` — a full PEP 440 specifier string. Optional (absent = no declared requirement). Included in `_TOML_FIELDS`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/marketstall/test_haybale_dataclass.py`:

```python
@pytest.mark.unit
def test_requires_haywire_defaults_empty_and_round_trips():
    """requires_haywire holds a FULL PEP 440 specifier, not a bare version —
    the author picks the operator. Absent means no declared requirement."""
    from haywire.core.marketstall import Haybale

    bare = Haybale(name="haybale-foo", version="0.1.0")
    assert bare.requires_haywire == ""
    assert "requires_haywire" not in bare.to_dict()

    declared = Haybale(name="haybale-foo", version="0.1.0", requires_haywire=">=0.0.31,<1.0.0")
    assert declared.to_dict()["requires_haywire"] == ">=0.0.31,<1.0.0"
```

Append to `tests/marketstall/test_parsing.py`:

```python
@pytest.mark.unit
def test_parse_haybale_entry_reads_requires_haywire():
    from haywire.core.marketstall.parsing import _parse_haybale_entry

    h = _parse_haybale_entry(
        {"name": "haybale-foo", "version": "0.1.0", "requires_haywire": ">=0.0.31"}
    )
    assert h.requires_haywire == ">=0.0.31"


@pytest.mark.unit
def test_requires_haywire_is_optional():
    """Unlike `version`, an absent framework requirement is legitimate — it
    means the author declared none."""
    from haywire.core.marketstall.parsing import _parse_haybale_entry

    h = _parse_haybale_entry({"name": "haybale-foo", "version": "0.1.0"})
    assert h.requires_haywire == ""
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/marketstall/test_haybale_dataclass.py tests/marketstall/test_parsing.py -v -k "requires_haywire"`
Expected: FAIL with `TypeError: Haybale.__init__() got an unexpected keyword argument 'requires_haywire'`.

- [ ] **Step 3: Add the field**

In `types.py`, add after `version: str` (line 19):

```python
    # Full PEP 440 specifier for the framework this library needs
    # (">=0.0.31", "~=0.0.31", ">=0.0.31,<1.0.0") — the author picks the
    # operator, so this is never a bare version. Empty means undeclared.
    requires_haywire: str = ""
```

Add `"requires_haywire",` to `_TOML_FIELDS` immediately after `"version",`.

In `parsing.py`, add to the `Haybale(...)` construction in `_parse_haybale_entry`, after `version=version,`:

```python
        requires_haywire=raw.get("requires_haywire", ""),
```

In `refresh.py`, add to the `Haybale(...)` construction inside `mark_stale_against_previous`, after `version=prev.version,`:

```python
                requires_haywire=prev.requires_haywire,
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/marketstall/ -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/marketstall/ tests/marketstall/
git commit -m "feat(marketstall): add Haybale.requires_haywire

A full PEP 440 specifier naming the framework versions a library needs.
Optional: absent means the author declared none. The marketplace will use
it as a pre-emptive gate; the wheel's Requires-Dist floor guards the bare
\`uv add\` path. The two carriers are disjoint, not redundant."
```

### Task 4: Framework-requirement pipeline step

**Files:**
- Create: `packages/haywire-studio/src/haywire_studio/packaging/share/pipeline/steps/framework.py`
- Modify: `packages/haywire-studio/src/haywire_studio/packaging/share/pipeline/results.py`
- Modify: `packages/haywire-studio/src/haywire_studio/packaging/share/pipeline/pipeline.py`
- Modify: `packages/haywire-studio/src/haywire_studio/packaging/share/pipeline/__init__.py`
- Test: `tests/share_pipeline/test_framework_step.py` (new — this is a genuinely novel seam: the option-generation and dual-write logic exists nowhere else)
- Test: `tests/share_pipeline/test_vocabulary.py`, `tests/share_pipeline/test_public_surface.py` (existing — extend)

**Interfaces:**
- Consumes: `SharePipeline`, `PreconditionFailure` (`results.py`), `barn_library_dirs`.
- Produces:
  - `FrameworkOption` (frozen dataclass): `specifier: str`, `label: str`, `consequence: str`, `recommended: bool = False`.
  - `FrameworkPlan` (frozen dataclass): `installed: str`, `declared: str`, `options: list[FrameworkOption]`.
  - `SharePipeline.plan_framework() -> FrameworkPlan`
  - `SharePipeline.apply_framework(specifier: str) -> list[Path]` — validates, writes the `haywire-core` floor into every `barn/*/pyproject.toml`, records the written paths, stores the answer on `pipeline.requires_haywire`, and returns the paths.
  - `SharePipeline.requires_haywire: str | None` — instance attribute, `None` until `apply_framework` runs.
  - `haywire_core_floor(lib_dir: Path) -> str` — the library's currently declared `haywire-core` specifier, `""` when undeclared.
  - `InvalidSpecifierError(VersionError)` — raised on a specifier that `SpecifierSet` rejects.

- [ ] **Step 1: Write the failing tests**

Create `tests/share_pipeline/test_framework_step.py`:

```python
"""The framework-requirement step: option generation, validation, dual write.

A floor is a restriction on CONSUMERS, not a record of what the author
tested. Raising it forces every consumer to upgrade their project first, so
the recommended option is always the lowest necessary one — keep what is
already declared.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import toml

from haywire_studio.packaging.share.pipeline import SharePipeline

pytestmark = pytest.mark.unit


def _project(tmp_path: Path, *, floor: str = ">=0.0.31") -> Path:
    lib = tmp_path / "barn" / "haybale-alpha"
    lib.mkdir(parents=True)
    (lib / "pyproject.toml").write_text(
        textwrap.dedent(f"""
            [project]
            name = "haybale-alpha"
            version = "0.1.0"
            dependencies = ["haywire-core{floor}", "numpy>=1.0"]
        """).lstrip()
    )
    return tmp_path


def test_plan_offers_keep_raise_and_compatible(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "haywire_studio.packaging.share.pipeline.steps.framework._installed_core_version",
        lambda: "0.0.34",
    )
    plan = SharePipeline(_project(tmp_path)).plan_framework()

    assert plan.installed == "0.0.34"
    assert plan.declared == ">=0.0.31"
    assert [o.specifier for o in plan.options] == [">=0.0.31", ">=0.0.34", "~=0.0.31"]


def test_keeping_the_declared_floor_is_the_recommended_option(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "haywire_studio.packaging.share.pipeline.steps.framework._installed_core_version",
        lambda: "0.0.34",
    )
    plan = SharePipeline(_project(tmp_path)).plan_framework()

    recommended = [o for o in plan.options if o.recommended]
    assert len(recommended) == 1
    assert recommended[0].specifier == ">=0.0.31"


def test_raise_option_counts_the_consumers_it_locks_out(tmp_path, monkeypatch):
    """Consequence-annotated, following the deps-drift precedent: the option
    that excludes consumers must say so concretely."""
    monkeypatch.setattr(
        "haywire_studio.packaging.share.pipeline.steps.framework._installed_core_version",
        lambda: "0.0.34",
    )
    plan = SharePipeline(_project(tmp_path)).plan_framework()

    raise_option = next(o for o in plan.options if o.specifier == ">=0.0.34")
    assert "0.0.31" in raise_option.consequence
    assert "0.0.33" in raise_option.consequence


def test_no_ceiling_in_any_default_option(tmp_path, monkeypatch):
    """A <0.1.0 stamped today becomes a lie the moment 0.1.0 ships. Authors who
    want a ceiling type one; ~= is offered but never recommended."""
    monkeypatch.setattr(
        "haywire_studio.packaging.share.pipeline.steps.framework._installed_core_version",
        lambda: "0.0.34",
    )
    plan = SharePipeline(_project(tmp_path)).plan_framework()

    recommended = next(o for o in plan.options if o.recommended)
    assert "<" not in recommended.specifier


def test_apply_writes_the_floor_into_every_barn_library(tmp_path):
    root = _project(tmp_path)
    second = root / "barn" / "haybale-beta"
    second.mkdir()
    (second / "pyproject.toml").write_text(
        '[project]\nname = "haybale-beta"\nversion = "0.1.0"\n'
        'dependencies = ["haywire-core>=0.0.31"]\n'
    )
    pipeline = SharePipeline(root)

    written = pipeline.apply_framework(">=0.0.34")

    assert len(written) == 2
    for lib in ("haybale-alpha", "haybale-beta"):
        deps = toml.loads((root / "barn" / lib / "pyproject.toml").read_text())["project"][
            "dependencies"
        ]
        assert "haywire-core>=0.0.34" in deps
        assert "numpy>=1.0" in deps or lib == "haybale-beta"
    assert pipeline.requires_haywire == ">=0.0.34"


def test_apply_adds_the_dependency_when_undeclared(tmp_path):
    root = tmp_path
    lib = root / "barn" / "haybale-alpha"
    lib.mkdir(parents=True)
    (lib / "pyproject.toml").write_text(
        '[project]\nname = "haybale-alpha"\nversion = "0.1.0"\ndependencies = ["numpy>=1.0"]\n'
    )

    SharePipeline(root).apply_framework(">=0.0.34")

    deps = toml.loads((lib / "pyproject.toml").read_text())["project"]["dependencies"]
    assert "haywire-core>=0.0.34" in deps


def test_apply_rejects_an_invalid_specifier(tmp_path):
    from haywire_studio.packaging.share.pipeline import InvalidSpecifierError

    with pytest.raises(InvalidSpecifierError):
        SharePipeline(_project(tmp_path)).apply_framework("not a specifier")


def test_apply_rejects_a_bare_version(tmp_path):
    """requires_haywire is a specifier, never a bare version — "0.0.34" alone
    is not a valid SpecifierSet."""
    from haywire_studio.packaging.share.pipeline import InvalidSpecifierError

    with pytest.raises(InvalidSpecifierError):
        SharePipeline(_project(tmp_path)).apply_framework("0.0.34")


def test_reordered_equivalent_specifiers_are_not_drift(tmp_path):
    """packaging reorders on str(): ">=0.0.31,<1.0.0" round-trips as
    "<1.0.0,>=0.0.31". Comparing raw strings would report false drift."""
    from haywire_studio.packaging.share.pipeline.steps.framework import specifiers_equal

    assert specifiers_equal(">=0.0.31,<1.0.0", "<1.0.0,>=0.0.31")
    assert not specifiers_equal(">=0.0.31", ">=0.0.34")
```

Extend `tests/share_pipeline/test_vocabulary.py` — add `FrameworkOption` and `FrameworkPlan` to its import block at the top, and append:

```python
def test_framework_plan_carries_installed_declared_and_options() -> None:
    option = FrameworkOption(
        specifier=">=0.0.31", label="keep the current declaration", consequence="", recommended=True
    )
    plan = FrameworkPlan(installed="0.0.34", declared=">=0.0.31", options=[option])
    assert plan.options[0].recommended
    assert plan.installed == "0.0.34"
```

Extend `tests/share_pipeline/test_public_surface.py` — add `"FrameworkPlan"` and `"FrameworkOption"` to `_WIZARD_IMPORTS`, and add `"InvalidSpecifierError"` to the error-hierarchy loop in `test_share_error_hierarchy_is_intact`.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/share_pipeline/test_framework_step.py -v`
Expected: FAIL with `ModuleNotFoundError: ... steps.framework`.

- [ ] **Step 3: Add the result dataclasses**

In `packages/haywire-studio/src/haywire_studio/packaging/share/pipeline/results.py`, append:

```python
@dataclass(frozen=True)
class FrameworkOption:
    """One framework-requirement the author can publish.

    ``consequence`` states, in concrete counted terms, who this option locks
    out — following the deps-drift precedent, where the words alone cannot
    carry the semantics. Empty when there is no consequence.
    """

    specifier: str
    label: str
    consequence: str = ""
    recommended: bool = False


@dataclass(frozen=True)
class FrameworkPlan:
    """What the framework-requirement step offers, before the author picks.

    ``declared`` is the ``haywire-core`` specifier the barn libraries carry
    today (empty when undeclared); ``installed`` is the running framework
    version. One project-wide answer, matching lockstep versioning (ADR 0023).
    """

    installed: str
    declared: str
    options: list[FrameworkOption]
```

- [ ] **Step 4: Add the error type**

In `packages/haywire-studio/src/haywire_studio/packaging/share/pipeline/errors.py`, append (next to `VersionError`):

```python
class InvalidSpecifierError(VersionError):
    """The author typed something that is not a valid PEP 440 specifier.

    A bare version ("0.0.34") lands here too: requires_haywire always carries
    the operator, so the author's intent (>=? ~=? ==?) is never guessed.
    """
```

- [ ] **Step 5: Write the step module**

Create `packages/haywire-studio/src/haywire_studio/packaging/share/pipeline/steps/framework.py`:

```python
"""Framework-requirement step — one project-wide answer, two carriers.

A floor is a restriction on CONSUMERS, not a record of what the author
tested: raising it forces every consumer to upgrade their project before
they can install, and some cannot. So the recommended option is always the
lowest necessary one — keep what is already declared — and raising it is a
deliberate, consequence-annotated choice.

The single answer is written into two disjoint carriers:

  * the ``haywire-core`` floor in each library's ``pyproject.toml``, which is
    the ONLY guard on the bare ``uv add haybale-foo`` path (no UI to warn
    anyone), and
  * ``requires_haywire`` in the marketstall entry, which the marketplace uses
    as a pre-emptive gate before the constraint file refuses the install.

Never a ceiling by default: a ``<0.1.0`` stamped today becomes a lie the
moment 0.1.0 ships and nobody will remember to update it.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

import toml
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import Version

from haywire_studio.packaging.share.pipeline.errors import InvalidSpecifierError
from haywire_studio.packaging.share.pipeline.results import FrameworkOption, FrameworkPlan

if TYPE_CHECKING:
    from haywire_studio.packaging.share.pipeline.pipeline import SharePipeline

_CORE = "haywire-core"


def _installed_core_version() -> str:
    """The running ``haywire-core`` version. Patched wholesale in tests."""
    import importlib.metadata as _meta

    try:
        return _meta.version(_CORE)
    except _meta.PackageNotFoundError:
        return ""


def _dep_name(entry: str) -> str:
    """The bare package name from a PEP 508 dependency string."""
    head = entry.split(";", 1)[0].split(" @ ", 1)[0]
    return re.split(r"[\[<>=!~ ]", head, maxsplit=1)[0].strip()


def haywire_core_floor(lib_dir: Path) -> str:
    """The ``haywire-core`` specifier this library declares, or "" if none."""
    pyproject = lib_dir / "pyproject.toml"
    if not pyproject.is_file():
        return ""
    data = toml.loads(pyproject.read_text())
    for entry in data.get("project", {}).get("dependencies", []) or []:
        if _dep_name(entry).lower() == _CORE:
            return entry[len(_dep_name(entry)) :].strip()
    return ""


def specifiers_equal(left: str, right: str) -> bool:
    """Compare two specifiers as parsed sets, never as raw strings.

    ``packaging`` reorders on ``str()`` — ``">=0.0.31,<1.0.0"`` round-trips as
    ``"<1.0.0,>=0.0.31"`` — so a string comparison yields false drift.
    """
    try:
        return SpecifierSet(left) == SpecifierSet(right)
    except InvalidSpecifier:
        return left.strip() == right.strip()


def parse_specifier(raw: str) -> SpecifierSet:
    """Validate an authored specifier. Raises InvalidSpecifierError."""
    text = (raw or "").strip()
    if not text:
        raise InvalidSpecifierError("A framework requirement cannot be empty.")
    try:
        return SpecifierSet(text)
    except InvalidSpecifier as exc:
        raise InvalidSpecifierError(
            f"{text!r} is not a valid PEP 440 specifier. Include the operator, "
            f"e.g. '>=0.0.31', '~=0.0.31', or '>=0.0.31,<1.0.0'."
        ) from exc


def _declared_floor(pipeline: "SharePipeline") -> str:
    """The specifier the barn libraries agree on, or the first one found.

    One project-wide answer: libraries built and tested against one installed
    framework have no honest basis for differing floors, so a disagreement is
    resolved by this step writing them all to the same value.
    """
    for lib_dir in pipeline._barn_library_dirs():
        floor = haywire_core_floor(lib_dir)
        if floor:
            return floor
    return ""


def _excluded_range(declared: str, installed: str) -> str:
    """Human phrasing for who a raise to *installed* would lock out."""
    try:
        low = SpecifierSet(declared)
        floors = [Version(spec.version) for spec in low if spec.operator in (">=", "~=", "==")]
    except (InvalidSpecifier, ValueError):
        floors = []
    if not floors:
        return f"Consumers below Haywire {installed} must update their project before installing."
    lowest = min(floors)
    target = Version(installed)
    if lowest >= target:
        return ""
    below = Version(f"{target.major}.{target.minor}.{max(target.micro - 1, 0)}")
    return (
        f"Consumers on {lowest}–{below} must update their project "
        f"before they can install this library."
    )


def plan(pipeline: "SharePipeline") -> FrameworkPlan:
    """The framework requirement on offer, before the author picks."""
    installed = _installed_core_version()
    declared = _declared_floor(pipeline)

    options: list[FrameworkOption] = []
    if declared:
        options.append(
            FrameworkOption(
                specifier=declared,
                label="keep the current declaration",
                consequence=f"Usable by projects on Haywire {declared.lstrip('>=~^ ')} and newer. "
                f"No consumer has to upgrade.",
                recommended=True,
            )
        )
    if installed:
        raise_spec = f">={installed}"
        if not declared or not specifiers_equal(declared, raise_spec):
            options.append(
                FrameworkOption(
                    specifier=raise_spec,
                    label="require the version you built against",
                    consequence=_excluded_range(declared, installed),
                    recommended=not declared,
                )
            )
    if declared and declared.startswith(">="):
        compatible = f"~={declared.removeprefix('>=').strip()}"
        options.append(
            FrameworkOption(
                specifier=compatible,
                label="compatible release",
                consequence="Also excludes Haywire 0.1.0 and newer.",
            )
        )
    return FrameworkPlan(installed=installed, declared=declared, options=options)


def apply(pipeline: "SharePipeline", specifier: str) -> list[Path]:
    """Write *specifier* as the ``haywire-core`` floor in every barn library.

    Stores the answer on the pipeline so step 5's marketstall rebuild can emit
    the same value as ``requires_haywire`` — one authored answer, two carriers.
    """
    parsed = parse_specifier(specifier)
    text = str(parsed)

    written: list[Path] = []
    for lib_dir in pipeline._barn_library_dirs():
        pyproject = lib_dir / "pyproject.toml"
        if not pyproject.is_file():
            continue
        data = toml.loads(pyproject.read_text())
        project = data.setdefault("project", {})
        deps: list[str] = project.setdefault("dependencies", [])
        new_deps: list[str] = []
        found = False
        for entry in deps:
            if _dep_name(entry).lower() == _CORE:
                new_deps.append(f"{_CORE}{text}")
                found = True
            else:
                new_deps.append(entry)
        if not found:
            new_deps.append(f"{_CORE}{text}")
        project["dependencies"] = new_deps
        pyproject.write_text(toml.dumps(data))
        written.append(pyproject)

    pipeline.requires_haywire = text
    pipeline.record(written)
    return written
```

- [ ] **Step 6: Wire it into the pipeline**

In `pipeline.py`, add the import:

```python
from haywire_studio.packaging.share.pipeline.steps import framework as steps_framework
```

add `FrameworkPlan` to the `results` import block, add to `__init__`:

```python
        # The one project-wide framework requirement, set by apply_framework().
        # Step 5 reads it so the marketstall entry and the pyproject floor
        # carry the same authored answer.
        self.requires_haywire: str | None = None
```

and add the two methods, between the drift block and the version block:

```python
    # ── Step 2b: framework requirement ───────────────────────────────────────

    def plan_framework(self) -> FrameworkPlan:
        """The framework requirement on offer: keep, raise, or compatible."""
        return steps_framework.plan(self)

    def apply_framework(self, specifier: str) -> list[Path]:
        """Write *specifier* as the haywire-core floor in every barn library."""
        return steps_framework.apply(self, specifier)
```

In `pipeline/__init__.py`, export `FrameworkOption`, `FrameworkPlan`, and `InvalidSpecifierError` alongside the existing names (match the file's existing import/`__all__` style).

- [ ] **Step 7: Run the tests to verify they pass**

Run: `uv run pytest tests/share_pipeline/ -v`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
uv run ruff check packages/haywire-studio/ tests/share_pipeline/
uv run ruff format --check packages/haywire-studio/ tests/share_pipeline/
git add packages/haywire-studio/src/haywire_studio/packaging/share/pipeline/ tests/share_pipeline/
git commit -m "feat(share): framework-requirement step

One project-wide PEP 440 specifier, offered with counted consequences:
keep the declared floor (recommended, locks nobody out), raise it to what
you built against, or compatible-release. No ceiling by default. Specifier
comparison is always SpecifierSet-based — packaging reorders on str()."
```

### Task 5: Dual write + consistency precondition

**Files:**
- Modify: `packages/haywire-studio/src/haywire_studio/packaging/share/marketstall.py:28-155`
- Modify: `packages/haywire-studio/src/haywire_studio/packaging/share/pipeline/steps/commit.py:18-41`
- Modify: `packages/haywire-studio/src/haywire_studio/packaging/share/pipeline/steps/preconditions.py`
- Test: `tests/share_pipeline/test_framework_step.py` (extend), `tests/share_pipeline/test_preconditions.py` (extend)

**Interfaces:**
- Consumes: `SharePipeline.requires_haywire` (Task 4), `haywire_core_floor`, `specifiers_equal` (Task 4), `Haybale.requires_haywire` (Task 3).
- Produces: `_build_entry_for_library(lib_dir, *, tag=None, requires_haywire="")` — new keyword-only parameter, default `""`. `write_marketstall(repo_root, *, tag=None, requires_haywire="")` — same.

- [ ] **Step 1: Write the failing tests**

Append to `tests/share_pipeline/test_framework_step.py`:

```python
def test_marketstall_entry_carries_the_same_answer_as_the_pyproject_floor(tmp_path, monkeypatch):
    """One authored answer, two disjoint carriers: the wheel's Requires-Dist
    floor guards `uv add`, requires_haywire guards the marketplace install."""
    from haywire_studio.packaging.share.marketstall import _build_entry_for_library

    root = _project(tmp_path)
    pipeline = SharePipeline(root)
    pipeline.apply_framework(">=0.0.34")

    entry = _build_entry_for_library(
        root / "barn" / "haybale-alpha", requires_haywire=pipeline.requires_haywire
    )

    assert entry["requires_haywire"] == ">=0.0.34"
    deps = toml.loads((root / "barn" / "haybale-alpha" / "pyproject.toml").read_text())["project"][
        "dependencies"
    ]
    assert "haywire-core>=0.0.34" in deps


def test_entry_omits_requires_haywire_when_undeclared(tmp_path):
    """A standalone write_marketstall() outside the pipeline declares nothing;
    the key is simply absent rather than an empty string."""
    from haywire_studio.packaging.share.marketstall import _build_entry_for_library

    root = _project(tmp_path)
    entry = _build_entry_for_library(root / "barn" / "haybale-alpha")

    assert "requires_haywire" not in entry
```

Append to `tests/share_pipeline/test_preconditions.py` (adapt `_repo`/fixture naming to whatever that file already uses for building a test repo):

```python
def test_requires_haywire_drift_is_reported(tmp_path, monkeypatch):
    """The marketstall's requires_haywire and the library's actual haywire-core
    specifier must agree — they are the two carriers of one answer."""
    from haywire_studio.packaging.share.pipeline.steps.preconditions import (
        check_framework_consistency,
    )

    lib = tmp_path / "barn" / "haybale-alpha"
    lib.mkdir(parents=True)
    (lib / "pyproject.toml").write_text(
        '[project]\nname = "haybale-alpha"\nversion = "0.1.0"\n'
        'dependencies = ["haywire-core>=0.0.31"]\n'
    )
    (tmp_path / "marketstall.toml").write_text(
        '[[haybales]]\nname = "haybale-alpha"\nversion = "0.1.0"\n'
        'requires_haywire = ">=0.0.34"\n'
    )

    failures = check_framework_consistency(SharePipeline(tmp_path))

    assert len(failures) == 1
    assert "haywire-core" in failures[0].message


def test_reordered_specifier_is_not_reported_as_drift(tmp_path):
    """packaging reorders on str(); comparing raw strings would fail here."""
    from haywire_studio.packaging.share.pipeline.steps.preconditions import (
        check_framework_consistency,
    )

    lib = tmp_path / "barn" / "haybale-alpha"
    lib.mkdir(parents=True)
    (lib / "pyproject.toml").write_text(
        '[project]\nname = "haybale-alpha"\nversion = "0.1.0"\n'
        'dependencies = ["haywire-core>=0.0.31,<1.0.0"]\n'
    )
    (tmp_path / "marketstall.toml").write_text(
        '[[haybales]]\nname = "haybale-alpha"\nversion = "0.1.0"\n'
        'requires_haywire = "<1.0.0,>=0.0.31"\n'
    )

    assert check_framework_consistency(SharePipeline(tmp_path)) == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/share_pipeline/test_framework_step.py tests/share_pipeline/test_preconditions.py -v -k "requires_haywire or reordered or carries_the_same"`
Expected: FAIL — `_build_entry_for_library() got an unexpected keyword argument`, and `check_framework_consistency` does not exist.

- [ ] **Step 3: Thread `requires_haywire` through the marketstall writer**

In `marketstall.py`, change the `_build_entry_for_library` signature (line 28) to:

```python
def _build_entry_for_library(
    lib_dir: Path, *, tag: str | None = None, requires_haywire: str = ""
) -> dict | None:
```

and append to its docstring:

```
    `requires_haywire` is the project-wide framework specifier the share
    pipeline authored (step 2b). Empty for standalone calls — the key is then
    omitted from the entry entirely rather than written as "", so an absent
    declaration stays absent.
```

Add `requires_haywire=requires_haywire,` to the `Haybale(...)` construction (after `version=version,`). `Haybale.to_dict()` already omits falsy fields, so `""` produces no key.

Find `write_marketstall`'s signature in the same file and add the same keyword-only parameter, forwarding it to every `_build_entry_for_library` call:

```python
def write_marketstall(
    repo_root: Path, *, tag: str | None = None, requires_haywire: str = ""
) -> MarketstallWriteResult:
```

- [ ] **Step 4: Pass the pipeline's answer at step 5**

In `pipeline/steps/commit.py`, in `apply_marketstall` (line 35-37):

```python
    tag = f"v{pipeline.version}" if pipeline.version else None
    try:
        result = write_marketstall(
            pipeline.repo_root, tag=tag, requires_haywire=pipeline.requires_haywire or ""
        )
```

- [ ] **Step 5: Add the consistency precondition**

In `pipeline/steps/preconditions.py`, add the import:

```python
from haywire_studio.packaging.share.pipeline.steps.framework import haywire_core_floor, specifiers_equal
```

and add this function at module level:

```python
def check_framework_consistency(pipeline: "SharePipeline") -> list[PreconditionFailure]:
    """The published ``requires_haywire`` vs each library's actual floor.

    The two are carriers of ONE authored answer, so a disagreement means one
    of them was hand-edited. Compared as parsed ``SpecifierSet`` objects, never
    as raw strings — ``packaging`` reorders on ``str()``, so
    ``">=0.0.31,<1.0.0"`` and ``"<1.0.0,>=0.0.31"`` are the same requirement
    and a string comparison would report false drift.
    """
    stall = pipeline.repo_root / "marketstall.toml"
    if not stall.is_file():
        return []
    try:
        data = toml.loads(stall.read_text())
    except toml.TomlDecodeError:
        # A malformed marketstall is rebuilt from disk in step 5 anyway.
        return []

    published: dict[str, str] = {}
    for raw in data.get("haybales", []) or []:
        name = raw.get("name")
        declared = raw.get("requires_haywire", "")
        if isinstance(name, str) and isinstance(declared, str) and declared:
            published[name] = declared

    failures: list[PreconditionFailure] = []
    for lib_dir in pipeline._barn_library_dirs():
        declared = published.get(lib_dir.name)
        if not declared:
            continue
        actual = haywire_core_floor(lib_dir)
        if actual and not specifiers_equal(actual, declared):
            failures.append(
                PreconditionFailure(
                    message=(
                        f"{lib_dir.name}: marketstall.toml publishes "
                        f"requires_haywire = {declared!r}, but its pyproject.toml declares "
                        f"haywire-core{actual}."
                    ),
                    remedy=(
                        "These are two carriers of one answer. Re-run the framework "
                        "requirement step to set both, or edit one to match the other."
                    ),
                )
            )
    return failures
```

Add `import toml` to that module's imports, and call it from `check()` — insert immediately before the `remote = git([...])` block (line 132):

```python
    failures.extend(check_framework_consistency(pipeline))
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest tests/share_pipeline/ -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
uv run ruff check packages/haywire-studio/ tests/share_pipeline/
uv run ruff format --check packages/haywire-studio/ tests/share_pipeline/
uv run pytest -m "not browser and not perf"
git add packages/haywire-studio/ tests/share_pipeline/
git commit -m "feat(share): write requires_haywire to both carriers

The pyproject haywire-core floor guards the bare 'uv add' path (no UI to
warn anyone); requires_haywire in the marketstall entry gates the
marketplace install. Disjoint, not redundant. A precondition compares the
two as parsed SpecifierSets so a reordered-but-equivalent specifier is not
reported as drift."
```

### Task 6: CLI flag + interactive prompt

**Files:**
- Modify: `packages/haywire-studio/src/haywire_studio/cli/share.py`
- Modify: `packages/haywire-studio/src/haywire_studio/packaging/share/cli.py`
- Test: `tests/share_pipeline/test_framework_step.py` (extend)

**Interfaces:**
- Consumes: `SharePipeline.plan_framework()`, `SharePipeline.apply_framework(specifier)` (Task 4).
- Produces: `run_share_cli(*, repo_root, yes, bump, message, requires_haywire: str | None = None) -> int`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/share_pipeline/test_framework_step.py`:

```python
def test_yes_without_the_flag_keeps_the_declared_floor(tmp_path, monkeypatch):
    """--yes with no --requires-haywire changes nothing and locks nobody out.
    Unlike the drift precedent (where BOTH options mutate and one is lossy),
    doing nothing here is safe, so a refusal would be pointless friction."""
    from haywire_studio.packaging.share import cli as share_cli

    applied: list[str] = []
    monkeypatch.setattr(
        SharePipeline, "apply_framework", lambda self, spec: applied.append(spec) or []
    )

    assert share_cli._resolve_framework_answer(SharePipeline(_project(tmp_path)), None) is None
    assert applied == []


def test_yes_with_the_flag_raises_the_floor(tmp_path, monkeypatch):
    """Raising a floor — the consumer-excluding direction — always requires the
    explicit flag."""
    from haywire_studio.packaging.share import cli as share_cli

    applied: list[str] = []
    monkeypatch.setattr(
        SharePipeline, "apply_framework", lambda self, spec: applied.append(spec) or []
    )

    pipeline = SharePipeline(_project(tmp_path))
    assert share_cli._resolve_framework_answer(pipeline, ">=0.0.34") == ">=0.0.34"
    assert applied == [">=0.0.34"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/share_pipeline/test_framework_step.py -v -k "yes_with"`
Expected: FAIL — `_resolve_framework_answer` does not exist.

- [ ] **Step 3: Add the argparse flag**

In `packages/haywire-studio/src/haywire_studio/cli/share.py`, add after the `--bump` argument:

```python
    parser.add_argument(
        "--requires-haywire",
        type=str,
        default=None,
        metavar="SPECIFIER",
        help="PEP 440 specifier for the framework this project needs "
        "(e.g. '>=0.0.31', '~=0.0.31'). Written to every barn library's "
        "haywire-core floor AND to the marketstall entry. Omitted: the "
        "declared floor is kept unchanged.",
    )
```

and thread it through `_run`:

```python
    return run_share_cli(
        repo_root=Path.cwd(),
        yes=args.yes,
        bump=args.bump,
        message=args.message,
        requires_haywire=args.requires_haywire,
    )
```

- [ ] **Step 4: Wire it into the share CLI**

In `packages/haywire-studio/src/haywire_studio/packaging/share/cli.py`, change `run_share_cli`'s signature and dispatch:

```python
def run_share_cli(
    *,
    repo_root: Path,
    yes: bool,
    bump: str | None,
    message: str | None,
    requires_haywire: str | None = None,
) -> int:
    """Dispatch to one of the two modes and return the process exit code."""
    pipeline = SharePipeline(repo_root)
    try:
        if yes:
            return _run_yes(pipeline, bump=bump, message=message, requires_haywire=requires_haywire)
        return _run_interactive(pipeline)
    except ShareError as exc:
        print(f"\n✗ {exc}")
        return EXIT_FAILED
```

Add the shared helper, above `_run_yes`:

```python
def _resolve_framework_answer(pipeline: SharePipeline, specifier: str | None) -> str | None:
    """Apply a supplied framework specifier, or leave the declaration alone.

    No flag means keep the declared floor. That default is INERT — it changes
    nothing and locks nobody out — which is exactly what --yes is for. This
    differs from the drift precedent, which refuses in --yes mode because both
    of its options mutate and one is lossy. Raising a floor, the
    consumer-excluding direction, always needs the explicit flag.
    """
    if specifier is None:
        return None
    pipeline.apply_framework(specifier)
    return pipeline.requires_haywire
```

In `_run_yes`, change the signature to accept `requires_haywire: str | None` and insert after the drift block (after `print("✓ No dependency drift")`):

```python
    answer = _resolve_framework_answer(pipeline, requires_haywire)
    if answer:
        print(f"✓ Framework requirement set to {answer}")
    else:
        print("✓ Framework requirement unchanged")
```

- [ ] **Step 5: Add the interactive prompt**

In `_run_interactive`, insert between the drift block and `print("\n── 3. Version ──")`:

```python
    print("\n── 2b. Framework requirement ──")
    fw = pipeline.plan_framework()
    print(f"  haywire-core, installed: {fw.installed or '(unknown)'}")
    for index, option in enumerate(fw.options, start=1):
        mark = "  [recommended]" if option.recommended else ""
        print(f"  {index}. {option.specifier}   {option.label}{mark}")
        if option.consequence:
            print(f"       {option.consequence}")
    print(f"  {len(fw.options) + 1}. custom …   any valid PEP 440 specifier")
    choice = _ask("Choose", default="1")
    if choice.strip() == str(len(fw.options) + 1):
        pipeline.apply_framework(_ask("Specifier (e.g. >=0.0.31)"))
        print(f"✓ Framework requirement set to {pipeline.requires_haywire}")
    else:
        try:
            picked = fw.options[int(choice) - 1]
        except (ValueError, IndexError):
            print("✗ Not one of the offered options.")
            return EXIT_FAILED
        pipeline.apply_framework(picked.specifier)
        print(f"✓ Framework requirement set to {pipeline.requires_haywire}")
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest tests/share_pipeline/ -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
uv run ruff check packages/haywire-studio/ && uv run ruff format --check packages/haywire-studio/
git add packages/haywire-studio/
git commit -m "feat(share): --requires-haywire flag and interactive prompt

--yes with no flag keeps the declared floor: that default is inert, which
is exactly what --yes is for. Raising a floor always needs the flag."
```

### Task 7: Share-wizard framework panel

**Files:**
- Modify: `barn/haybale-marketplace/haybale_marketplace/editors/_share_wizard/_state.py`
- Modify: `barn/haybale-marketplace/haybale_marketplace/editors/_share_wizard/copy.py`
- Modify: `barn/haybale-marketplace/haybale_marketplace/editors/_share_wizard/panels.py`
- Modify: `barn/haybale-marketplace/haybale_marketplace/editors/_share_wizard/chrome.py`
- Test: `tests/share_pipeline/test_step_sequence.py` (existing — extend)

**Interfaces:**
- Consumes: `SharePipeline.plan_framework()`, `apply_framework()`, `FrameworkPlan`, `FrameworkOption`.
- Produces: `ShareWizard.framework_plan: FrameworkPlan | None`; `ShareWizard.advance_from_framework(specifier: str) -> None`; new step name `"framework"` between `"drift"` and `"version"`.

- [ ] **Step 1: Write the failing test**

Append to `tests/share_pipeline/test_step_sequence.py` (match the file's existing fixture/import conventions):

```python
def test_framework_step_sits_between_drift_and_version():
    """The framework requirement is authored BEFORE the version bump, so the
    version step's write set and the framework write set land in one commit."""
    from haybale_marketplace.editors._share_wizard.copy import STEPS

    assert STEPS.index("drift") < STEPS.index("framework") < STEPS.index("version")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/share_pipeline/test_step_sequence.py -v -k framework`
Expected: FAIL with `ValueError: tuple.index(x): x not in tuple`.

- [ ] **Step 3: Add the step to the wizard's vocabulary**

In `copy.py`, change `STEPS` (line 5) and `_STEP_TITLES`:

```python
STEPS = ("preconditions", "checked", "drift", "framework", "version", "docs", "commit", "push", "done")

_STEP_TITLES = {
    "preconditions": "Check the project",
    "checked": "Scan dependencies",
    "drift": "Dependencies",
    "framework": "Framework requirement",
    "version": "Version",
    "docs": "Documentation",
    "commit": "Review and commit",
    "push": "Publish",
    "done": "Shared",
}
```

- [ ] **Step 4: Add the state transition**

In `_state.py`, add `FrameworkPlan` to the pipeline import block, add to `__init__` (after `self.drift_choice`):

```python
        self.framework_plan: FrameworkPlan | None = None
```

Change the tail of `advance_from_drift` — replace `self.version_plan = await asyncio.to_thread(self.pipeline.plan_version)` / `self.step = "version"` with:

```python
            self.framework_plan = await asyncio.to_thread(self.pipeline.plan_framework)
        except ShareError as exc:
            self._fail(exc)
            return
        self.step = "framework"
```

and add the new transition immediately after it:

```python
    async def advance_from_framework(self, specifier: str) -> None:
        """Write the one project-wide framework requirement, then plan the bump.

        An invalid specifier raises InvalidSpecifierError (a ShareError), which
        keeps the user on this step with the message inline — same retry-in-place
        posture as every other step.
        """
        self.retry()
        try:
            self.pipeline.apply_framework(specifier)
            self.version_plan = await asyncio.to_thread(self.pipeline.plan_version)
        except ShareError as exc:
            self._fail(exc)
            return
        self.step = "version"
```

- [ ] **Step 5: Add the panel**

In `panels.py`, add before `_panel_version`:

```python
def _panel_framework(wizard: ShareWizard, rerender: Callable[[], None]) -> None:
    """One project-wide framework requirement, with counted consequences.

    A floor restricts CONSUMERS rather than recording what you tested, so the
    recommended option keeps the current declaration — it locks nobody out.
    """
    plan = wizard.framework_plan
    if plan is None:
        return

    hui.section_label("Framework requirement")
    ui.label(f"haywire-core, installed: {plan.installed or 'unknown'}").classes(
        "text-xs hw-text-dim font-mono"
    )

    options = {opt.specifier: f"{opt.specifier} — {opt.label}" for opt in plan.options}
    options["custom"] = "custom…"
    default = next((o.specifier for o in plan.options if o.recommended), next(iter(options)))
    # in_popup for the same reason as the drift and version selects.
    choice = hui.select_field(options=options, value=default, label="Requires", in_popup=True).classes(
        "w-full"
    )
    custom = hui.input_field(placeholder=">=0.0.31")
    custom.bind_visibility_from(choice, "value", lambda v: v == "custom")

    consequences = {opt.specifier: opt.consequence for opt in plan.options}
    note = ui.label("").classes("text-xs hw-text-dim")

    def _describe() -> None:
        note.text = consequences.get(str(choice.value), "")

    _describe()
    choice.on_value_change(lambda _: _describe())

    def _spec() -> str:
        return (custom.value or "").strip() if choice.value == "custom" else str(choice.value)

    with ui.row().classes("w-full justify-end gap-2"):
        ui.button(
            "Continue",
            on_click=lambda: _advance(wizard, rerender, lambda: wizard.advance_from_framework(_spec())),
        ).props("flat dense").style("color: var(--hw-positive);")
```

- [ ] **Step 6: Route the panel**

In `chrome.py`, add a branch between the `"drift"` and `"version"` branches (lines 137-139):

```python
    elif wizard.step == "framework":
        _panel_framework(wizard, rerender)
```

and add `_panel_framework` to the `panels` import at the top of that file.

- [ ] **Step 7: Run the tests to verify they pass**

Run: `uv run pytest tests/share_pipeline/ -v`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
uv run ruff check barn/haybale-marketplace/ && uv run ruff format --check barn/haybale-marketplace/
uv run pytest -m "not browser and not perf"
git add barn/haybale-marketplace/ tests/share_pipeline/
git commit -m "feat(share-wizard): framework-requirement panel

Sits between drift and version so the floor write and the version bump land
in one commit. Recommended option keeps the current declaration."
```

---

## Part 4 — Shell check-for-updates

### Task 8: PyPI version query + pin writer

**Files:**
- Create: `packages/haywire-core/src/haywire/core/update/__init__.py`
- Create: `packages/haywire-core/src/haywire/core/update/check.py`
- Create: `packages/haywire-core/src/haywire/core/update/pin.py`
- Test: `tests/update/__init__.py`, `tests/update/test_update_check.py` (new — novel seam: nothing in the repo queries PyPI for the framework or rewrites the root pin)

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `UpdateStatus` (frozen dataclass): `installed: str`, `latest: str | None`, `reachable: bool`. Property `available: bool` — True iff reachable and `Version(latest) > Version(installed)`.
  - `check_for_update(dist: str = "haywire-studio", *, timeout: float = 10.0) -> UpdateStatus`
  - `LOCKSTEP_DISTS: tuple[str, ...]` — the dists whose root-`pyproject.toml` pins move together.
  - `rewrite_pins(pyproject_path: Path, version: str) -> str` — returns the NEW file text without writing it (so the conflict check can write-resolve-restore).
  - `declared_floor(pyproject_path: Path, dist: str = "haywire-studio") -> str` — the declared specifier, `""` when absent.
  - `startup_mismatch(pyproject_path: Path) -> str | None` — the "environment wasn't synced" notice text, or `None`.

- [ ] **Step 1: Write the failing tests**

Create `tests/update/__init__.py` (empty) and `tests/update/test_update_check.py`:

```python
"""Framework update check: PyPI query, pin rewrite, startup mismatch notice."""

from __future__ import annotations

import textwrap
import urllib.error
from pathlib import Path
from unittest.mock import patch

import pytest
import toml

pytestmark = pytest.mark.unit


def _root_pyproject(tmp_path: Path, pin: str = "~=0.0.34") -> Path:
    path = tmp_path / "pyproject.toml"
    path.write_text(
        textwrap.dedent(f"""
            [project]
            name = "my-project"
            version = "0.1.0"
            dependencies = [
                "haywire-studio{pin}",
                "haybale-marketplace{pin}",
                "numpy>=1.0",
            ]
        """).lstrip()
    )
    return path


def test_update_available_when_pypi_is_ahead():
    from haywire.core.update.check import check_for_update

    with patch("haywire.core.update.check._installed_version", return_value="0.0.34"):
        with patch("haywire.core.update.check._latest_on_pypi", return_value="0.0.35"):
            status = check_for_update()

    assert status.available
    assert status.latest == "0.0.35"


def test_no_update_when_installed_matches_latest():
    from haywire.core.update.check import check_for_update

    with patch("haywire.core.update.check._installed_version", return_value="0.0.35"):
        with patch("haywire.core.update.check._latest_on_pypi", return_value="0.0.35"):
            status = check_for_update()

    assert not status.available
    assert status.reachable


def test_offline_is_reported_as_unreachable_not_as_up_to_date():
    """"Couldn't reach PyPI" and "you're up to date" are different answers —
    collapsing them would tell the user a comforting lie."""
    from haywire.core.update.check import check_for_update

    with patch("haywire.core.update.check._installed_version", return_value="0.0.34"):
        with patch(
            "haywire.core.update.check._latest_on_pypi",
            side_effect=urllib.error.URLError("no route"),
        ):
            status = check_for_update()

    assert not status.reachable
    assert not status.available
    assert status.latest is None


def test_rewrite_pins_moves_every_lockstep_dist(tmp_path):
    from haywire.core.update.pin import rewrite_pins

    path = _root_pyproject(tmp_path)
    new_text = rewrite_pins(path, "0.0.35")
    deps = toml.loads(new_text)["project"]["dependencies"]

    assert "haywire-studio~=0.0.35" in deps
    assert "haybale-marketplace~=0.0.35" in deps
    assert "numpy>=1.0" in deps


def test_rewrite_pins_does_not_write_the_file(tmp_path):
    """The conflict check needs write-resolve-restore, so the rewrite must be a
    pure text transform the caller controls."""
    from haywire.core.update.pin import rewrite_pins

    path = _root_pyproject(tmp_path)
    before = path.read_text()
    rewrite_pins(path, "0.0.35")

    assert path.read_text() == before


def test_rewrite_pins_preserves_the_declared_operator(tmp_path):
    """A project pinned with >= keeps >=; the update moves the version, not the
    author's chosen operator."""
    from haywire.core.update.pin import rewrite_pins

    path = _root_pyproject(tmp_path, pin=">=0.0.34")
    deps = toml.loads(rewrite_pins(path, "0.0.35"))["project"]["dependencies"]

    assert "haywire-studio>=0.0.35" in deps


def test_startup_mismatch_fires_when_the_pin_is_ahead_of_the_installed(tmp_path):
    """Derived, not stored: pin-vs-installed IS the condition and is always
    current, whereas a stored marker goes stale on a hand-edited pin."""
    from haywire.core.update.pin import startup_mismatch

    path = _root_pyproject(tmp_path, pin=">=0.0.35")
    with patch("haywire.core.update.pin._installed_version", return_value="0.0.34"):
        notice = startup_mismatch(path)

    assert notice is not None
    assert "0.0.35" in notice and "0.0.34" in notice
    assert "uv run haywire" in notice


def test_no_startup_mismatch_when_synced(tmp_path):
    from haywire.core.update.pin import startup_mismatch

    path = _root_pyproject(tmp_path, pin=">=0.0.34")
    with patch("haywire.core.update.pin._installed_version", return_value="0.0.34"):
        assert startup_mismatch(path) is None


def test_no_startup_mismatch_when_installed_is_ahead(tmp_path):
    """Installed > floor is the normal state, not a fault."""
    from haywire.core.update.pin import startup_mismatch

    path = _root_pyproject(tmp_path, pin=">=0.0.31")
    with patch("haywire.core.update.pin._installed_version", return_value="0.0.34"):
        assert startup_mismatch(path) is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/update/ -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'haywire.core.update'`.

- [ ] **Step 3: Write the PyPI check**

Create `packages/haywire-core/src/haywire/core/update/__init__.py`:

```python
"""Framework self-update: version check, pin rewrite, restart banner.

Updating the framework is NOT a marketplace concern — the marketplace depends
on the framework it would be updating — so this lives in haywire-core and is
surfaced by the app shell.
"""

from haywire.core.update.check import UpdateStatus, check_for_update
from haywire.core.update.pin import (
    LOCKSTEP_DISTS,
    declared_floor,
    rewrite_pins,
    startup_mismatch,
)

__all__ = [
    "LOCKSTEP_DISTS",
    "UpdateStatus",
    "check_for_update",
    "declared_floor",
    "rewrite_pins",
    "startup_mismatch",
]
```

Create `packages/haywire-core/src/haywire/core/update/check.py`:

```python
"""Is a newer Haywire released? A PyPI query, nothing more."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

from packaging.version import InvalidVersion, Version


@dataclass(frozen=True)
class UpdateStatus:
    """The answer to "is there a newer Haywire?".

    ``reachable`` is False only when PyPI could not be queried. "Couldn't
    reach PyPI" and "you're up to date" are DIFFERENT answers — collapsing
    them would tell the user a comforting lie about an unanswered question.
    """

    installed: str
    latest: str | None
    reachable: bool

    @property
    def available(self) -> bool:
        if not self.reachable or not self.latest or not self.installed:
            return False
        try:
            return Version(self.latest) > Version(self.installed)
        except InvalidVersion:
            return False


def _installed_version(dist: str) -> str:
    import importlib.metadata as _meta

    try:
        return _meta.version(dist)
    except _meta.PackageNotFoundError:
        return ""


def _latest_on_pypi(dist: str, timeout: float) -> str:
    """The newest non-prerelease version PyPI lists for *dist*."""
    with urllib.request.urlopen(f"https://pypi.org/pypi/{dist}/json", timeout=timeout) as resp:
        data = json.loads(resp.read())
    candidates: list[Version] = []
    for raw in data.get("releases", {}):
        try:
            parsed = Version(raw)
        except InvalidVersion:
            continue
        if not parsed.is_prerelease:
            candidates.append(parsed)
    return str(max(candidates)) if candidates else ""


def check_for_update(dist: str = "haywire-studio", *, timeout: float = 10.0) -> UpdateStatus:
    """Compare the installed *dist* against the newest release on PyPI."""
    installed = _installed_version(dist)
    try:
        latest = _latest_on_pypi(dist, timeout)
    except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError):
        return UpdateStatus(installed=installed, latest=None, reachable=False)
    return UpdateStatus(installed=installed, latest=latest or None, reachable=True)
```

Create `packages/haywire-core/src/haywire/core/update/pin.py`:

```python
"""Rewriting the root project's framework pins.

Only the ROOT pyproject.toml is touched — every lockstep dist is declared
there. A scaffolded barn library's own ``haywire-core`` floor is left alone:
``~=0.0.31`` already admits ``0.0.34`` (``~=X.Y.Z`` ≡ ``>=X.Y.Z, ==X.Y.*``),
so it is not a hazard for patch moves. It only bites at ``0.1.0``.
"""

from __future__ import annotations

import re
from pathlib import Path

import toml
from packaging.requirements import InvalidRequirement, Requirement
from packaging.version import InvalidVersion, Version

# Dists released in lockstep with the framework. A pin bump moves all of them.
LOCKSTEP_DISTS: tuple[str, ...] = ("haywire-studio", "haywire-core", "haybale-marketplace")


def _installed_version(dist: str) -> str:
    import importlib.metadata as _meta

    try:
        return _meta.version(dist)
    except _meta.PackageNotFoundError:
        return ""


def _dep_name(entry: str) -> str:
    head = entry.split(";", 1)[0].split(" @ ", 1)[0]
    return re.split(r"[\[<>=!~ ]", head, maxsplit=1)[0].strip()


def _operator(entry: str, name: str) -> str:
    """The operator the author already chose (``~=`` / ``>=`` / ``==``).

    Preserved rather than normalized: an update moves the version, never the
    author's declared compatibility policy.
    """
    tail = entry[len(name) :].strip()
    for op in ("~=", ">=", "==", ">"):
        if tail.startswith(op):
            return op
    return ">="


def rewrite_pins(pyproject_path: Path, version: str) -> str:
    """The new file TEXT with every lockstep pin moved to *version*.

    Returns text rather than writing, because the conflict check needs
    write-resolve-restore: it holds the original in memory, writes this,
    resolves, and restores in a ``finally``.
    """
    data = toml.loads(pyproject_path.read_text(encoding="utf-8"))
    deps = data.get("project", {}).get("dependencies", []) or []
    lockstep = {d.lower() for d in LOCKSTEP_DISTS}

    new_deps: list[str] = []
    for entry in deps:
        name = _dep_name(entry)
        if name.lower() in lockstep:
            new_deps.append(f"{name}{_operator(entry, name)}{version}")
        else:
            new_deps.append(entry)
    data.setdefault("project", {})["dependencies"] = new_deps
    return toml.dumps(data)


def declared_floor(pyproject_path: Path, dist: str = "haywire-studio") -> str:
    """The version *dist* is pinned to in the root pyproject, or "".

    Parsed with ``Requirement`` so the specifier's structure — not its raw
    text — decides what the floor is.
    """
    if not pyproject_path.is_file():
        return ""
    data = toml.loads(pyproject_path.read_text(encoding="utf-8"))
    for entry in data.get("project", {}).get("dependencies", []) or []:
        if _dep_name(entry).lower() != dist.lower():
            continue
        try:
            requirement = Requirement(entry)
        except InvalidRequirement:
            return ""
        floors = [s.version for s in requirement.specifier if s.operator in (">=", "~=", "==")]
        return max(floors, key=Version) if floors else ""
    return ""


def startup_mismatch(pyproject_path: Path, dist: str = "haywire-studio") -> str | None:
    """The "environment wasn't synced" notice, or None when there is nothing to say.

    Derived, never stored: a stored marker goes stale (hand-edited pin, upgrade
    by other means), whereas pin-vs-installed IS the condition and is always
    current. Success needs no acknowledgement — the notice simply stops
    appearing.

    What this really catches is a BYPASSED sync (``--no-sync``/``UV_FROZEN``, a
    bare ``.venv/bin/haywire``, an IDE run config), not a failed one: if the
    resolve fails at launch, studio never starts and there is no UI to report
    it. That population — developer machines — is exactly where the original
    version skew arose.
    """
    floor = declared_floor(pyproject_path, dist)
    installed = _installed_version(dist)
    if not floor or not installed:
        return None
    try:
        if Version(floor) <= Version(installed):
            return None
    except InvalidVersion:
        return None
    return (
        f"pyproject.toml requests {floor} but {installed} is running — this "
        f"environment wasn't synced. Launch with `uv run haywire`."
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/update/ -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
uv run ruff check packages/haywire-core/src/haywire/core/update/ tests/update/
uv run ruff format --check packages/haywire-core/src/haywire/core/update/ tests/update/
uv run mypy packages/haywire-core/src/
git add packages/haywire-core/src/haywire/core/update/ tests/update/
git commit -m "feat(core): framework update check and pin rewriting

check_for_update() distinguishes offline from up-to-date. rewrite_pins()
returns text rather than writing, so the conflict check can
write-resolve-restore. startup_mismatch() derives the 'environment wasn't
synced' notice from pin-vs-installed rather than a marker that can go stale."
```

### Task 9: Conflict check (baseline-diffed `uv sync --dry-run`)

**Files:**
- Create: `packages/haywire-core/src/haywire/core/update/conflict.py`
- Modify: `packages/haywire-core/src/haywire/core/update/__init__.py`
- Test: `tests/update/test_update_conflict.py` (new — novel seam: baseline-diffing a resolver's noisy output exists nowhere else)

**Interfaces:**
- Consumes: `rewrite_pins` (Task 8).
- Produces:
  - `ConflictResult` (frozen dataclass): `ok: bool`, `message: str`, `changes: list[str]`.
  - `check_pin_conflict(project_root: Path, version: str) -> ConflictResult`
  - `diff_resolutions(baseline: str, proposed: str) -> list[str]` — lines present in `proposed` but not `baseline`.

- [ ] **Step 1: Write the failing tests**

Create `tests/update/test_update_conflict.py`:

```python
"""The pre-write conflict check.

`uv sync --dry-run` output is noisy with PRE-EXISTING venv drift — a real run
reported "Would uninstall 33 packages" purely because the venv held packages
the lockfile didn't. So the check diffs against a baseline run and reports only
what OUR pin changes.
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.unit


def _project(tmp_path: Path) -> Path:
    (tmp_path / "pyproject.toml").write_text(
        textwrap.dedent("""
            [project]
            name = "my-project"
            version = "0.1.0"
            dependencies = ["haywire-studio~=0.0.34"]
        """).lstrip()
    )
    return tmp_path


def test_preexisting_drift_is_not_reported_as_ours():
    from haywire.core.update.conflict import diff_resolutions

    baseline = " - haybale-visiongraph==0.0.5\n - opencv-python==4.9.0\n"
    proposed = " - haybale-visiongraph==0.0.5\n - opencv-python==4.9.0\n + haywire-core==0.0.35\n"

    assert diff_resolutions(baseline, proposed) == ["+ haywire-core==0.0.35"]


def test_identical_resolutions_diff_to_nothing():
    from haywire.core.update.conflict import diff_resolutions

    same = " - haybale-visiongraph==0.0.5\n"
    assert diff_resolutions(same, same) == []


def test_unsatisfiable_pin_is_reported_as_a_conflict(tmp_path):
    from haywire.core.update.conflict import check_pin_conflict

    root = _project(tmp_path)
    calls: list[str] = []

    def fake_sync(cwd):
        calls.append("run")
        if len(calls) == 1:
            return True, " - nothing\n"
        return False, "error: no solution found: haybale-foo requires haywire-core<0.0.35"

    with patch("haywire.core.update.conflict._uv_sync_dry_run", side_effect=fake_sync):
        result = check_pin_conflict(root, "0.0.35")

    assert not result.ok
    assert "no solution found" in result.message


def test_a_clean_resolution_never_promises_a_successful_launch(tmp_path):
    """Resolution is not installation: the real sync happens later inside
    `uv run`, unsupervised, after all our UI is gone."""
    from haywire.core.update.conflict import check_pin_conflict

    root = _project(tmp_path)

    with patch("haywire.core.update.conflict._uv_sync_dry_run", return_value=(True, " - x==1\n")):
        result = check_pin_conflict(root, "0.0.35")

    assert result.ok
    assert "No conflicts found" in result.message
    assert "will succeed" not in result.message


def test_the_original_pyproject_is_restored_after_the_check(tmp_path):
    """Write-resolve-restore: a temp-dir copy would resolve DIFFERENTLY —
    [tool.uv.sources] carries {workspace = true} and absolute dev paths — so
    the check runs against the real workspace and must put it back."""
    from haywire.core.update.conflict import check_pin_conflict

    root = _project(tmp_path)
    before = (root / "pyproject.toml").read_text()

    with patch("haywire.core.update.conflict._uv_sync_dry_run", return_value=(True, "")):
        check_pin_conflict(root, "0.0.35")

    assert (root / "pyproject.toml").read_text() == before


def test_the_original_is_restored_even_when_the_resolve_raises(tmp_path):
    from haywire.core.update.conflict import check_pin_conflict

    root = _project(tmp_path)
    before = (root / "pyproject.toml").read_text()

    with patch("haywire.core.update.conflict._uv_sync_dry_run", side_effect=OSError("uv is gone")):
        with pytest.raises(OSError):
            check_pin_conflict(root, "0.0.35")

    assert (root / "pyproject.toml").read_text() == before
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/update/test_update_conflict.py -v`
Expected: FAIL with `ModuleNotFoundError: ... update.conflict`.

- [ ] **Step 3: Write the conflict checker**

Create `packages/haywire-core/src/haywire/core/update/conflict.py`:

```python
"""Pre-write conflict check for a proposed framework pin.

Runs against the REAL workspace, never a temp-dir copy: a copy resolves
differently, because ``[tool.uv.sources]`` carries ``{workspace = true}`` and,
under ``--dev``, absolute dev-repo paths. So: write-resolve-restore — hold the
original text in memory, write the proposed pin, resolve, restore in a
``finally``.

What the check is worth: it reliably BLOCKS a bad pin — an unsatisfiable
resolution (a barn library whose floor excludes the new core) is deterministic
and knowable now. It does NOT bless a good one: resolution is not installation,
and the real sync happens later inside ``uv run`` (downloads, sdist builds, a
possibly-moved index). Hence "No conflicts found", never "your next launch will
succeed".
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from haywire.core.update.pin import rewrite_pins


@dataclass(frozen=True)
class ConflictResult:
    """Whether the proposed pin resolves, and what it would change.

    ``changes`` holds only the lines the pin ADDED relative to the baseline
    run — the raw output is noisy with pre-existing venv drift (a real run
    reported "Would uninstall 33 packages" that had nothing to do with the
    pin), and showing that unfiltered would alarm the user with removals we
    did not cause.
    """

    ok: bool
    message: str
    changes: list[str] = field(default_factory=list)


def _uv_sync_dry_run(cwd: Path) -> tuple[bool, str]:
    """``uv sync --dry-run`` in *cwd*. Returns (ok, merged output)."""
    proc = subprocess.run(
        ["uv", "sync", "--dry-run"],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=120,
    )
    return proc.returncode == 0, f"{proc.stdout}\n{proc.stderr}"


def diff_resolutions(baseline: str, proposed: str) -> list[str]:
    """Lines in *proposed* that the *baseline* run did not also produce."""
    seen = {line.strip() for line in baseline.splitlines() if line.strip()}
    out: list[str] = []
    for line in proposed.splitlines():
        stripped = line.strip()
        if stripped and stripped not in seen:
            out.append(stripped)
    return out


def check_pin_conflict(project_root: Path, version: str) -> ConflictResult:
    """Resolve the proposed pin against the real workspace, then restore it."""
    pyproject = project_root / "pyproject.toml"
    original = pyproject.read_text(encoding="utf-8")

    _, baseline_output = _uv_sync_dry_run(project_root)

    try:
        pyproject.write_text(rewrite_pins(pyproject, version), encoding="utf-8")
        ok, proposed_output = _uv_sync_dry_run(project_root)
    finally:
        pyproject.write_text(original, encoding="utf-8")

    if not ok:
        return ConflictResult(ok=False, message=proposed_output.strip())
    return ConflictResult(
        ok=True,
        message="No conflicts found.",
        changes=diff_resolutions(baseline_output, proposed_output),
    )
```

Add to `update/__init__.py`:

```python
from haywire.core.update.conflict import ConflictResult, check_pin_conflict, diff_resolutions
```

and add `"ConflictResult"`, `"check_pin_conflict"`, `"diff_resolutions"` to `__all__`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/update/ -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
uv run ruff check packages/haywire-core/ tests/update/ && uv run ruff format --check packages/haywire-core/ tests/update/
git add packages/haywire-core/src/haywire/core/update/ tests/update/
git commit -m "feat(core): baseline-diffed pin conflict check

uv sync --dry-run output is noisy with pre-existing venv drift, so the
proposed resolution is diffed against a baseline run. Write-resolve-restore
against the real workspace — a temp-dir copy resolves differently. Result is
worded 'No conflicts found', never a promise about the next launch."
```

### Task 10: Update-confirmed flag, exit code, and `atexit` banner

**Files:**
- Create: `packages/haywire-core/src/haywire/core/update/confirmed.py`
- Modify: `packages/haywire-core/src/haywire/core/update/__init__.py`
- Modify: `packages/haywire-studio/src/haywire_studio/app.py:317-357`
- Test: `tests/update/test_update_confirmed.py` (new — novel seam: one flag driving two outputs that must never disagree)

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `UPDATE_EXIT_CODE: int = 100` — the sentinel a future supervisor reads (Home Assistant's `RESTART_EXIT_CODE`).
  - `confirm_update(from_version: str, to_version: str) -> None` — sets the flag and registers the `atexit` banner exactly once.
  - `update_confirmed() -> tuple[str, str] | None` — `(from, to)` when confirmed, else `None`.
  - `exit_code() -> int` — `UPDATE_EXIT_CODE` when confirmed, else `0`.
  - `reset_for_tests() -> None`
  - `run_app() -> int` (changed return type); `main()` propagates it via `raise SystemExit(...)` on the app path.

- [ ] **Step 1: Write the failing tests**

Create `tests/update/test_update_confirmed.py`:

```python
"""One update-confirmed flag drives BOTH the terminal banner and the exit code.

They are not the same mechanism — the banner is for the human at the terminal,
the exit code is for a future supervisor — but they must never disagree. A
single source means an exit WITHOUT an update (cancel, crash, ordinary quit)
cannot print "Haywire updated".
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _clean_flag():
    from haywire.core.update import confirmed

    confirmed.reset_for_tests()
    yield
    confirmed.reset_for_tests()


def test_an_ordinary_exit_reports_no_update():
    from haywire.core.update import confirmed

    assert confirmed.update_confirmed() is None
    assert confirmed.exit_code() == 0


def test_confirming_sets_both_outputs_from_one_call():
    from haywire.core.update import confirmed

    confirmed.confirm_update("0.0.34", "0.0.35")

    assert confirmed.update_confirmed() == ("0.0.34", "0.0.35")
    assert confirmed.exit_code() == confirmed.UPDATE_EXIT_CODE


def test_the_sentinel_is_distinct_from_a_normal_exit():
    from haywire.core.update import confirmed

    assert confirmed.UPDATE_EXIT_CODE != 0


def test_the_banner_names_both_versions_and_the_relaunch_command():
    from haywire.core.update import confirmed

    text = confirmed.banner_text("0.0.34", "0.0.35")

    assert "0.0.34" in text and "0.0.35" in text
    assert "uv run haywire" in text


def test_confirming_twice_registers_one_banner():
    """atexit handlers are additive; a double-confirm must not print twice."""
    from haywire.core.update import confirmed

    registered: list[object] = []
    confirmed._register = registered.append  # type: ignore[assignment]

    confirmed.confirm_update("0.0.34", "0.0.35")
    confirmed.confirm_update("0.0.34", "0.0.35")

    assert len(registered) == 1
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/update/test_update_confirmed.py -v`
Expected: FAIL with `ModuleNotFoundError: ... update.confirmed`.

- [ ] **Step 3: Write the flag module**

Create `packages/haywire-core/src/haywire/core/update/confirmed.py`:

```python
"""The update-confirmed flag — one source for the banner and the exit code.

They are not the same mechanism: the banner is for the human at the terminal,
the exit code is for a future supervisor. But they must never disagree, so a
single flag produces both. An exit WITHOUT an update — cancel, crash, ordinary
quit — therefore cannot print "Haywire updated", and making the banner
conditional under a supervisor later becomes one check rather than reconciling
two states.

The banner is registered via ``atexit``, not ``app.on_shutdown``: atexit
handlers run during interpreter shutdown, AFTER uvicorn's own shutdown
logging, so the banner is genuinely the last thing on screen. That ordering
does not cost the exit code — ``SystemExit`` has already propagated by then
and the code still arrives intact.
"""

from __future__ import annotations

import atexit

# Sentinel a supervisor reads to tell "restart me" from "user quit"; today
# every exit looks identical from outside. Mirrors Home Assistant's
# RESTART_EXIT_CODE = 100. Nothing in this plan reads it — it is the seam that
# makes a supervisor additive rather than an entry-point refactor.
UPDATE_EXIT_CODE = 100

_confirmed: tuple[str, str] | None = None
_register = atexit.register


def banner_text(from_version: str, to_version: str) -> str:
    """The terminal banner printed after uvicorn's own shutdown lines."""
    rule = "─" * 45
    return (
        f"\n{rule}\n"
        f" Haywire updated:  {from_version} → {to_version}  (pinned)\n"
        f" Restart to load it:   uv run haywire\n"
        f"{rule}\n"
    )


def confirm_update(from_version: str, to_version: str) -> None:
    """Record that the user confirmed an update. Idempotent.

    Registering twice would print the banner twice — atexit handlers are
    additive and never deduplicated.
    """
    global _confirmed
    if _confirmed is not None:
        return
    _confirmed = (from_version, to_version)
    _register(lambda: print(banner_text(from_version, to_version)))


def update_confirmed() -> tuple[str, str] | None:
    """``(from, to)`` when an update was confirmed, else None."""
    return _confirmed


def exit_code() -> int:
    """The process exit code implied by the flag."""
    return UPDATE_EXIT_CODE if _confirmed is not None else 0


def reset_for_tests() -> None:
    """Clear the flag. Tests only — the flag is one-way in a real run."""
    global _confirmed, _register
    _confirmed = None
    _register = atexit.register
```

Add to `update/__init__.py`:

```python
from haywire.core.update.confirmed import (
    UPDATE_EXIT_CODE,
    confirm_update,
    exit_code,
    update_confirmed,
)
```

and add those four names to `__all__`.

- [ ] **Step 4: Make `run_app()` return an exit code**

In `packages/haywire-studio/src/haywire_studio/app.py`, change `run_app` (line 317-330):

```python
def run_app() -> int:
    """Launch the Haywire application. Returns the process exit code.

    Subcommands already propagate a code (`raise SystemExit(handler(args))`);
    the app path did not, so every exit looked identical from outside. A
    supervisor distinguishes "user quit" from "restart me" by a sentinel code,
    so the app path returns one too. Nothing reads it today — this is the seam
    that keeps a supervisor additive.
    """
```

and change its tail (after `app_instance.run()`):

```python
    app_instance.run()

    from haywire.core.update.confirmed import exit_code

    return exit_code()
```

In `main()`, change the app path (lines 353-357):

```python
    handler = getattr(args, "handler", None)
    if handler is None:
        raise SystemExit(run_app())
    raise SystemExit(handler(args))
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/update/ -v && uv run pytest -m "not browser and not perf" -k "app or cli"`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
uv run ruff check packages/ tests/update/ && uv run ruff format --check packages/ tests/update/
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/
git add packages/haywire-core/src/haywire/core/update/ packages/haywire-studio/src/haywire_studio/app.py tests/update/
git commit -m "feat(core): update-confirmed flag drives banner and exit code

One flag, two outputs that must never disagree. atexit (not on_shutdown) so
the banner lands after uvicorn's shutdown logging. run_app() now returns an
exit code and main() propagates it — the seam a supervisor needs, unused
today."
```

### Task 11: Shell control and update dialog

**Files:**
- Create: `packages/haywire-core/src/haywire/ui/modals/update_dialog.py`
- Modify: `packages/haywire-core/src/haywire/ui/app/shell.py:656-690` (`_render_topbar`, `_render_statusbar`)
- Test: manual verification (this is UI wiring over already-tested logic; the state it drives is covered by Tasks 8–10)

**Interfaces:**
- Consumes: `check_for_update`, `check_pin_conflict`, `rewrite_pins`, `confirm_update`, `startup_mismatch` (Tasks 8–10).
- Produces: `open_update_dialog(project_root: Path) -> None` — the whole ⟳ flow.

- [ ] **Step 1: Write the dialog**

Create `packages/haywire-core/src/haywire/ui/modals/update_dialog.py`:

```python
"""The framework update flow, behind the shell's ⟳ control.

Pin-bump only — no in-process ``uv sync``. ``uv run`` syncs by default, so
``uv run haywire`` installs the new pin at launch. Deferring the sync collapses
the mixed-version window to zero and sidesteps the Windows lock on the running
``haywire.exe`` entirely (upgrading haywire-studio means replacing it while it
runs, and DeleteFileW fails on files with open handles).

Flow: check → what-happens explainer → conflict check → unsaved-work
confirmation → pin write → app.shutdown().
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from nicegui import app, ui

from haywire.ui.components import hui
from haywire.core.update import check_for_update, check_pin_conflict, rewrite_pins
from haywire.core.update.confirmed import confirm_update


def open_update_dialog(project_root: Path) -> None:
    """Run the whole check-and-pin flow in one dialog."""
    with hui.dialog_card() as dialog:
        body = ui.column().classes("gap-2 min-w-[26rem]")
        dialog.open()

    async def _check() -> None:
        body.clear()
        with body:
            ui.label("Checking PyPI…").classes("text-sm hw-text-muted")
        status = await asyncio.to_thread(check_for_update)

        body.clear()
        with body:
            if not status.reachable:
                # "Couldn't reach PyPI" and "you're up to date" are different
                # answers; collapsing them would be a comforting lie.
                ui.label("Couldn't reach PyPI. Try again later.").classes("text-sm")
                ui.button("Close", on_click=dialog.close).props("flat dense")
                return
            if not status.available:
                ui.label(f"Haywire {status.installed} — you're up to date.").classes("text-sm")
                ui.button("Close", on_click=dialog.close).props("flat dense")
                return
            _render_explainer(status.installed, status.latest or "")

    def _render_explainer(installed: str, latest: str) -> None:
        ui.label(f"Haywire {latest} is available").classes("text-base font-bold")
        ui.label(f"You're on {installed}.").classes("text-xs hw-text-muted")
        hui.section_label("What happens")
        with ui.column().classes("gap-0.5 ml-1"):
            ui.label("1. Your pyproject.toml pin is updated").classes("text-xs")
            ui.label("2. Studio quits").classes("text-xs")
            ui.label("3. You run `uv run haywire` — the new version installs on launch").classes(
                "text-xs"
            )
        with ui.row().classes("w-full justify-end gap-2"):
            ui.button("Cancel", on_click=dialog.close).props("flat dense")
            ui.button(
                "Continue",
                on_click=lambda: _run_conflict_check(installed, latest),
            ).props("flat dense").style("color: var(--hw-positive);")

    async def _run_conflict_check(installed: str, latest: str) -> None:
        body.clear()
        with body:
            ui.label("checking…").classes("text-sm hw-text-muted")
        result = await asyncio.to_thread(check_pin_conflict, project_root, latest)

        body.clear()
        with body:
            if not result.ok:
                ui.label("Update blocked").classes("text-base font-bold")
                ui.label(result.message).classes("text-xs font-mono whitespace-pre-wrap")
                ui.label("Update or remove the conflicting library first. Nothing was written.").classes(
                    "text-xs hw-text-muted"
                )
                ui.button("Close", on_click=dialog.close).props("flat dense")
                return
            # Framing matters: resolution is not installation. The real sync
            # happens later inside `uv run`, unsupervised.
            ui.label("No conflicts found.").classes("text-sm")
            if result.changes:
                with ui.column().classes("gap-0 ml-1 max-h-40 overflow-auto"):
                    for line in result.changes:
                        ui.label(line).classes("text-xs font-mono hw-text-muted")
            ui.label("Unsaved work will be lost.").classes("text-xs").style("color: var(--hw-warning);")
            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Cancel", on_click=dialog.close).props("flat dense")
                ui.button(
                    "Continue anyway",
                    on_click=lambda: _write_and_quit(installed, latest),
                ).props("flat dense").style("color: var(--hw-warning);")

    def _write_and_quit(installed: str, latest: str) -> None:
        pyproject = project_root / "pyproject.toml"
        pyproject.write_text(rewrite_pins(pyproject, latest), encoding="utf-8")
        # One flag, so the banner and the exit code cannot disagree.
        confirm_update(installed, latest)
        dialog.close()
        # Graceful: under reload=False this takes the should_exit branch, so
        # lifespan handlers run and the Farmhand MCP host stops cleanly — the
        # exact path os.execv would have bypassed.
        app.shutdown()

    ui.timer(0.05, _check, once=True)
```

- [ ] **Step 2: Add the shell control**

In `packages/haywire-core/src/haywire/ui/app/shell.py`, inside `_render_topbar`, after the save button:

```python
            def _on_check_updates() -> None:
                from haywire.ui.modals.update_dialog import open_update_dialog

                open_update_dialog(Path.cwd())

            ui.button(
                icon="autorenew",
                on_click=_on_check_updates,
            ).props("flat round dense").tooltip("Check for Haywire updates")
```

Add `from pathlib import Path` to that module's imports if it is not already present.

- [ ] **Step 3: Add the startup mismatch notice**

In `_render_statusbar`, after the session label:

```python
            from haywire.core.update import startup_mismatch

            notice = startup_mismatch(Path.cwd() / "pyproject.toml")
            if notice:
                ui.label(notice).classes("text-xs").style("color: var(--hw-warning);")
```

- [ ] **Step 4: Verify by hand**

Run: `uv run haywire`

Check, in order:
1. The ⟳ control appears in the top bar with the tooltip "Check for Haywire updates".
2. Clicking it shows "Checking PyPI…", then either the up-to-date line or the explainer.
3. With networking disabled, it shows "Couldn't reach PyPI. Try again later."
4. `git status` reports `pyproject.toml` unmodified after cancelling at any stage.

- [ ] **Step 5: Lint, type-check, commit**

```bash
uv run ruff check packages/haywire-core/ && uv run ruff format --check packages/haywire-core/
uv run mypy packages/haywire-core/src/
uv run pytest -m "not browser and not perf"
git add packages/haywire-core/src/haywire/ui/
git commit -m "feat(shell): check-for-updates control

Explainer → conflict check → unsaved-work confirmation → pin write →
app.shutdown(). No unsaved-work detection: GraphEntry.unsaved lives in
haybale-haystack, which haywire-core cannot import, and the user is better
placed to know. Statusbar carries the 'environment wasn't synced' notice."
```

---

## Part 5 — Scaffold default and docs

### Task 12: Scaffold `>=` instead of `~=`

**Files:**
- Modify: `packages/haywire-studio/src/haywire_studio/init.py:23-39`
- Test: `tests/test_init_scaffolding.py` (existing — extend)

**Interfaces:**
- Consumes: nothing.
- Produces: `_release_pin(dist="haywire-studio") -> str` now returns `>=X.Y.Z`. Both call sites (`init.py:100`, `:147`) are unchanged.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_init_scaffolding.py`:

```python
def test_scaffold_pin_has_no_ceiling():
    """A floor restricts consumers; a ceiling stamped at scaffold time becomes
    a lie the moment the excluded version ships. Authors who want one type it."""
    from haywire_studio.init import _release_pin

    pin = _release_pin()

    assert pin.startswith(">=")
    assert "<" not in pin
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_init_scaffolding.py -v -k ceiling`
Expected: FAIL — `assert '~=0.0.34'.startswith('>=')`.

- [ ] **Step 3: Change the pin**

In `packages/haywire-studio/src/haywire_studio/init.py`, replace `_release_pin` (lines 23-39):

```python
def _release_pin(dist: str = "haywire-studio") -> str:
    """Return a floor specifier (``>=X.Y.Z``) for the running haywire release,
    so scaffolded projects pin to the version that created them rather than a
    stale hardcoded literal.

    A floor, not a compatible-release (``~=``): ``~=X.Y.Z`` also stamps a
    ceiling, and a ceiling written at scaffold time becomes a lie the moment
    the excluded version ships — nobody will remember to update it. Authors
    who want one type it themselves.

    Reads the installed version of ``dist`` — when invoked via
    ``uvx --from haywire-studio[==X] haywire init``, that is exactly the
    version the user chose. Raises if it can't be determined, rather than
    guessing a pin that would mislead the generated pyproject.
    """
    try:
        return f">={version(dist)}"
    except PackageNotFoundError as exc:
        raise RuntimeError(
            f"Cannot determine the installed {dist} version to pin scaffolded "
            f"dependencies. Is haywire installed correctly?"
        ) from exc
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_init_scaffolding.py -v`
Expected: PASS (the two pre-existing `_release_pin` assertions compose the pin from the function itself, so they follow the change).

- [ ] **Step 5: Commit**

```bash
uv run ruff check packages/haywire-studio/ && uv run ruff format --check packages/haywire-studio/
git add packages/haywire-studio/src/haywire_studio/init.py tests/test_init_scaffolding.py
git commit -m "feat(init): scaffold >=X.Y.Z instead of ~=X.Y.Z

A ceiling stamped at scaffold time becomes a lie the moment the excluded
version ships. Lowest necessary floor; authors who want a ceiling type one."
```

### Task 13: Glossary, docs, and the release checklist

**Files:**
- Modify: `docs/reference/glossary.md:40,217,235`
- Modify: `docs/haybale/haybale-package-canon.md:378,393`
- Modify: `docs/haybale/marketplace/haybale-marketplace-arch.md:72,173,348`
- Modify: `docs/guides/subscribing-to-marketplaces.md:90,166`
- Modify: `docs/guides/sharing-libraries.md:143,159`
- Modify: `.claude/skills/haywire-release/SKILL.md` (or wherever the release checklist lives — locate it first)

**Interfaces:** documentation only.

- [ ] **Step 1: Update the glossary**

`docs/reference/glossary.md:40` — in the `Haybale` (dataclass) row, replace `min_version` with `version` and add `requires_haywire` to the field list.

`:217` — same substitution in the second `Haybale (dataclass)` row; drop the `MarketplaceEntry` alias column change (leave it as-is) and add `requires_haywire` to the field list.

`:235` — the `updates_available` row: replace `cache \`min_version\`` with `cache \`version\``.

Add two new rows, in the table's existing alphabetical position:

```markdown
| **`version`** (Haybale field) | The version a marketstall entry advertises — the version its author published. NOT a floor: nothing resolves against it; its only job is the update comparison (`installed < version` ⇒ update available). Required; an entry without one raises `MalformedMarketplaceError`. Renamed from `min_version`, which was never a minimum. | `min_version` (legacy name) |
| **`requires_haywire`** (Haybale field) | A full PEP 440 specifier naming the framework versions a library needs (`>=0.0.31`, `~=0.0.31`, `>=0.0.31,<1.0.0`) — the author picks the operator, so never a bare version. Authored once per project at share time and written to two disjoint carriers: the wheel's `Requires-Dist` floor (the only guard on the bare `uv add` path) and the marketstall entry (the marketplace's pre-emptive gate). Optional; empty means undeclared. | framework requirement |
```

- [ ] **Step 2: Update the marketplace architecture doc**

`docs/haybale/marketplace/haybale-marketplace-arch.md:72` — replace the `min_version` table row with:

```markdown
| `version` | string | yes | The version this entry advertises — what the author published. Not a floor; nothing resolves against it. Its only job is the update comparison. |
| `requires_haywire` | string | no | Full PEP 440 specifier for the framework this library needs (`>=0.0.31`). Absent means undeclared. |
```

`:173` — `updates_available`: `min_version` → `version`.

`:348` — the TOML example: `min_version  = "0.1.0"` → `version = "0.1.0"`, and add `requires_haywire = ">=0.0.31"` beneath it.

Add a short section documenting the constraint gate:

```markdown
### Framework version gate

Every marketplace install (`dry_run()` and `install()` alike, with identical
flags) passes `uv pip install -c <constraints>` pinning `haywire-core`,
`haywire-studio`, and `nicegui` to their **currently-installed exact versions**
— read from the running venv, because a declared `Requires-Dist` can itself be
stale while what is running cannot.

`uv pip install <spec>` resolves fresh against the requested spec's tree;
already-installed packages are only reuse candidates. Without the constraint
file, taking a haybale update can pull `haywire-core` forward while
`haywire-studio` stays put — old studio + new core is an `ImportError` at
runtime. With it, that resolution simply fails, and the failure names the
shell's "Check for updates" control as the remedy.

The `haybale-*` libraries are deliberately **not** constrained: upgrading them
is exactly what a marketplace install is for.
```

- [ ] **Step 3: Update the package canon and both guides**

`docs/haybale/haybale-package-canon.md:378,393` — in both TOML examples, `min_version  = "1.0.0"` → `version = "1.0.0"`, each followed by `requires_haywire = ">=0.0.31"`.

`docs/guides/subscribing-to-marketplaces.md:90,166` — `min_version` → `version` in both sentences.

`docs/guides/sharing-libraries.md:143` — `min_version  = "0.1.0"` → `version = "0.1.0"` plus a `requires_haywire = ">=0.0.31"` line.

`:159` — replace the disclaimer (`min_version` is a *floor*, not "latest") with:

```markdown
- `version` is the version this entry advertises — what you published. It is not
  a floor and nothing resolves against it; its only job is the update comparison.
- `requires_haywire` declares which framework versions your library needs, as a
  full PEP 440 specifier. Keep it as low as your library actually allows: a floor
  restricts *consumers*, and raising it forces every one of them to update their
  project before they can install you.
```

- [ ] **Step 4: Add the release-checklist item**

Locate the release checklist:

```bash
grep -rn "checklist\|Gate tests\|bump_version" .claude/skills/haywire-release/SKILL.md | head
```

Add to it:

```markdown
- **At `0.1.0`: revisit every published framework floor.** `~=0.0.X` specifiers
  in the wild exclude `0.1.0` by construction. Every haybale published with a
  compatible-release requirement will stop being installable on the new
  framework unless its author republishes with a widened specifier. Announce it
  and sweep the in-repo barns before tagging.
```

- [ ] **Step 5: Verify the docs build and nothing stale remains**

```bash
grep -rn "min_version" docs/ .claude/ | grep -v Binary
uv run mkdocs build --strict
```

Expected: the grep returns nothing; the build succeeds.

- [ ] **Step 6: Commit**

```bash
git add docs/ .claude/
git commit -m "docs: version/requires_haywire, framework gate, 0.1.0 checklist

Documents the rename (and drops the 'floor, not latest' disclaimer that was
a doc patch over a misnomer), the new requires_haywire field and its two
disjoint carriers, the constraint-file gate, and the 0.1.0 obligation to
revisit every published framework floor."
```

### Task 14: Full-suite verification

**Files:** none (verification only)

- [ ] **Step 1: Run every check**

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-TEST_A/haybale_test_a/
uv run pytest
```

Expected: all four clean. Anything failing that passed at the pre-edit baseline is yours to fix.

- [ ] **Step 2: Verify the whole gate by hand**

```bash
uv run haywire
```

1. Open the Library Browser. Installed haybales still show their version, and any with a newer catalog entry still show the ▲ "vX available" tag (Task 2 renamed the field these read).
2. Trigger a marketplace install of any haybale. It still succeeds — the constraint file pins what is already installed, so a well-behaved haybale resolves unchanged.
3. Click ⟳ in the top bar. It reports up-to-date, offline, or offers the update.

- [ ] **Step 3: Verify a share run end to end**

```bash
uv run haywire share --yes --bump patch --requires-haywire '>=0.0.31'
```

Expected: the framework step reports the requirement, `marketstall.toml` carries `requires_haywire = ">=0.0.31"` on every entry, and each `barn/*/pyproject.toml` declares `haywire-core>=0.0.31`. Reset with `git reset --hard HEAD~1 && git tag -d v<version>` afterwards if this was a throwaway run.

---

## Deferred (explicitly NOT in this plan)

- **Supervisor-parent restart** for true one-click. Blocked on verifying uv's install atomicity (hardlink-vs-copy, write atomicity, behaviour when the env is in use) and on Windows testing. The exit-code seam is built here (Task 10), so what remains is the supervisor itself. **Undecided, needs its own design session:** the `haywire` console script is owned by `haywire-studio`, so a supervisor shipped there would upgrade *itself*, reintroducing the Windows entry-point lock this design avoids. Do not pre-empt it.
- **Share-time framework floor lag warning.** `_detect_pyproject_version_lag()` skips non-haybale dists, so a stale `haywire-core` floor is invisible today. Advisory-only, no auto-fix: for haybale deps the correct floor is mechanically "what's installed" (lockstep), but for `haywire-core` the installed version is only an upper bound on what the library needs. Separate issue.
- **MCP carrier for `requires_haywire`.** Share Farmhand tools were planned but dropped; only `catalog_tools.py` and `install_tools.py` exist. If they are ever built they inherit the same optional parameter.
