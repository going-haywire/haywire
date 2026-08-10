# Linked Libraries: One Auto-Correct Rule, Three Surfaces

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Rewritten 2026-08-10.** Supersedes two earlier drafts. The first was written pre-`f8fd8a7c` and used the retired `decorator_*` vocabulary. The second rebased that but still modelled the editor as a multi-select with two-directional drift. Investigating how the share pipeline actually handles `linked_libraries` collapsed the design: the pipeline's rule is *add what is provably imported, never remove, never ask*, and the editor should do exactly that and nothing more. It also surfaced a live bug — the share **wizard** displays registrations it never writes. See "What the investigation found" below.

**Goal:** Make `linked_libraries` auto-correction behave identically on all three surfaces that touch it — `haywire share` CLI, the share wizard, and the Library Overview Editor's Edit dialog.

**Architecture:** There is one rule, already implemented and already documented: `apply_linked_registrations()` unions `DepDrift.linked_missing` into `haybale.toml`, never removing. The CLI honors it. The wizard renders it and then drops it on the floor — Task 1 fixes that. The editor does not have it — Tasks 3–4 give it the same rule behind a Refresh button, staged in memory until Save.

**Tech Stack:** Python, NiceGUI, pytest.

## Global Constraints

- **One direction only.** `linked_missing` (declared-side gap) is added. Nothing is ever removed automatically, on any surface. The reverse direction — declared-but-no-longer-imported — is explicitly **out of scope**; see "Dropped from the previous draft".
- `linked_libraries` is the only field this touches. No surface here reads or writes `[project] dependencies`. Pip-dependency drift stays a Share-flow concern.
- The editor writes nothing on Refresh. Only its existing Save Changes action writes, through the existing `write_haybale_fields` path.
- The editor's control stays a **read-only label** plus a Refresh button. Not a multi-select: an author-editable control implies the author has a decision to make, and for this field they do not.
- Editor Refresh is **heap-only**, matching the `os` field. This is a correctness gate, not just UX — see "The library-root problem".
- Use `linked_missing` / `linked_libraries` vocabulary throughout. Never `decorator_*` or `@library(dependencies=[...])` — both were retired (ADR-0025, `f8fd8a7c`).

---

## What the investigation found

Verified by reading the source and by running it, not by inference.

### The rule, and where it lives

Detection is shared and pure: [`pipeline/steps/detect.py::check()`](../../../packages/haywire-core/src/haywire/core/publishing/pipeline/steps/detect.py) loops barn libraries through `detect_share_drift()` and writes nothing.

The single writer is `apply_linked_registrations()` in `pipeline/steps/dependencies.py`:

```python
declared = read_haybale_toml_lenient(module_dir).get("linked_libraries") or []
merged = list(declared) + [n for n in names if n not in declared]
write_haybale_fields(module_dir, {"linked_libraries": merged})
```

Union mode. `haybale.toml` only — a dedicated test (`test_linked_registrations_never_touch_pyproject`) pins that it never touches `pyproject.toml`. Its docstring states the reasoning: every entry is provably true because `detect_deps` emits a name only when the source imports it AND it resolves to an installed, registered haywire library; it carries no version specifier and narrows nothing for consumers.

"Which entries need no author input" is answered once, in `DriftReport.linked_registrations` (`pipeline/results.py:145`), whose docstring records *why* it is centralized:

> Lives here rather than in each caller because it is a *pipeline* decision […] It was duplicated in both, divergently, before this property existed.

It reads `self.libraries` (drifted **+** findings_only), because a missing registration is not drift — a library whose only gap is this never appears in `drifted`.

`ShareDecisions.registrations` is explicitly **not** a decision:

> `registrations` is not a decision (see `DriftReport.linked_registrations`); it travels here only so `apply_all` can write it in the same pass.

### The bug: the wizard shows it and never writes it

`panel_review` computes `registrations = report.linked_registrations` and passes it to `_render_clean_lines`, which renders each entry as a static, non-interactive line under a "Library dependencies" heading:

```
linked_libraries = [..., haybale_studio]  in haybale-alpha
```

Then `_collect()` builds the decision set — and never sets `registrations`:

```python
return ShareDecisions(
    framework=framework,
    removals=removals,
    additions=additions,
    floors=floors,
    undeclared_acknowledged=skipped,
)
```

It defaults to `{}`, and `apply_all` skips empty mappings. So the wizard promises the write on screen and does not perform it.

Confirmed three ways: no assignment to `.registrations` exists anywhere under `barn/haybale-share/` or `haywire_studio/packaging/`; no other `write_haybale_fields` call exists in the wizard; and introspecting `_collect`'s source at runtime shows the five fields above and no sixth.

The CLI (`share_cli.py:124-130`) does it correctly and unconditionally, before the drift branch. **CLI behavior is the target for all surfaces.**

Two notes for whoever fixes it. `apply_all`'s docstring already reasons carefully about registration *ordering* ("Registrations follow immediately, at the first writing step, so they land exactly once") for a mapping that arrives empty — the plumbing was built and then not connected. And `tests/share_flow/test_review_collection.py` opens by asserting `_collect` "is pure — no file is touched", which is true and is precisely why nobody noticed it was also incomplete: every existing test asks what `_collect` *writes*, none asks what it *carries*.

### The library-root problem (Task 4 depends on this)

`detect_share_drift(lib_dir)` needs the **library root** — the `pyproject.toml` directory, with the Python package as a child:

```
barn/haybale-marketplace/          ← lib_dir (library root): has pyproject.toml
└── haybale_marketplace/           ← module_dir (package): has __init__.py + haybale.toml
```

Both production callers get that path by **filesystem scan, never registry identity**. `detect.py::check()` loops `pipeline._barn_library_dirs()`; `deps.py::run_deps_check_cli()` loops `barn_library_dirs(repo_root)`. Both bottom out in `publishing/barn.py`:

```python
d.is_dir() and not d.is_symlink() and (d / "pyproject.toml").is_file()
```

Presence of `pyproject.toml` *is* the membership test, and symlinks are excluded.

The editor has no `repo_root` and no scan. It has a `LibraryInfo`, whose `identity.folder_path` is the **package** directory — every existing use in the dialog confirms it (`read_display(folder_path)` and `read_haybale_toml_lenient(folder_path)` both take a `package_dir` and read `package_dir/haybale.toml`).

Passing `folder_path` straight to `find_module_dir` fails **silently** — verified by running it:

```
find_module_dir(LIB ROOT) = /tmp/…/haybale-fake/haybale_fake
find_module_dir(PKG DIR ) = None          ← the earlier draft's path
```

`None` means the Refresh button renders permanently disabled and looks like intended behavior for a perfectly inspectable library.

**The fix is `folder_path.parent`, gated on the existing `_is_heap` flag.** The gate is what makes `.parent` provable rather than a guess: `is_project_library()` already tests `Path(folder_path).is_relative_to(workspace_root / "barn")`, and that `barn/` is exactly the tree `barn_library_dirs()` scans. So a heap library's `folder_path` is `barn/<lib>/<module>/` and `.parent` is the `barn/<lib>/` the pipeline itself would use. Verified: every in-repo barn library uses the flat layout (no `barn/*/src` exists), which is what `.parent` resolves correctly.

For a non-heap library `.parent` is *unsound* — an installed wheel's `folder_path` is `site-packages/<module>/`, whose parent is `site-packages/`: no `pyproject.toml`, and `find_module_dir` would return some unrelated neighboring package. Hence the heap gate, which the editor already applies to `os` for the independent reason that site-packages edits are lost on reinstall.

One inherited quirk, worth noting and not worth coding around: `barn_library_dirs` skips symlinks but `is_relative_to` does not resolve them, so a symlinked barn entry (e.g. the gitignored `haybale-visiongraph`) passes the editor's heap test while being invisible to the pipeline. Refresh will work on it; it just detects for a library `haywire share` would not publish.

### Detection resolves through the real venv

`detect_deps` maps module names to distributions via `importlib.metadata.packages_distributions()` with a `find_spec` fallback. An invented module name lands in `unresolved` and **never** reaches `linked_missing`. Verified:

```
library_linked = ['haybale_core']
unresolved     = ['haybale_dep']   ← invented name
```

A fake `HaywireLibrarySource` filters only *after* resolution and cannot conjure an uninstalled dist. **Every test fixture in this plan therefore imports `haybale_core`, a really-installed registered library.** The earlier draft's fixtures used invented names and could not have passed.

---

## Dropped from the previous draft

| Dropped | Why |
| --- | --- |
| `DepDrift.linked_unused` field + its detection | The reverse direction has no consumer once the editor is a label. The pipeline does not compute it, does not want it, and the editor no longer has a chip for the author to delete. Adding an unused field to a core dataclass to serve a UI affordance that this rewrite removes is backwards. |
| Editable multi-select, `use-chips`, `new-value-mode=add-unique` | A control that invites editing implies a decision the author does not have. It also created a real failure mode: a free-typed hyphenated chip (`haybale-studio`) passes the UI and then fails `_validate_linked_libraries` at save time. Removing the control removes the bug. |
| "Stale entry" warning notification | Nothing computes staleness anymore. |
| `linked_unused` glossary row | Follows the field. |
| The old Task 3 (fix `dep_detect` docstring) | Already done — `dep_detect.py:102` reads `library_linked`, and `grep "@library(dependencies" dep_detect.py` returns nothing. |

Net effect: `haywire-core`'s drift model and detector are **untouched** by this plan. The only core change is the one-keyword `libraries` param on `detect_share_drift`, needed so the editor can inject the live registry.

---

## File Structure

| File | Responsibility |
| --- | --- |
| `barn/haybale-share/haybale_share/_flow/panels.py` | Thread `registrations` into `_collect`'s `ShareDecisions` (modify) |
| `tests/share_flow/test_review_collection.py` | Test that the wizard carries registrations (modify) |
| `packages/haywire-core/src/haywire/core/publishing/drift/detect.py` | Injectable `libraries` param on `detect_share_drift()` (modify) |
| `tests/test_share_drift.py` | Test the injectable param (modify) |
| `barn/haybale-marketplace/haybale_marketplace/editors/_overview_edit_dialog.py` | Refresh button beside the linked_libraries label (modify) |
| `tests/marketplace/test_overview_edit_dialog_linked_libraries.py` | Tests for the Refresh helper (create) |
| `docs/haybale/marketplace/haybale-marketplace-arch.md` | Rewrite §6 (modify) |
| `docs/reference/glossary.md` | Note the three surfaces on the "one authoring path" line (modify) |

---

### Task 1: Fix the wizard — carry registrations into the decision set

**Files:**
- Modify: `barn/haybale-share/haybale_share/_flow/panels.py`
- Test: `tests/share_flow/test_review_collection.py`

**Interfaces:**
- Consumes: `DriftReport.linked_registrations` (existing), already computed in `panel_review` and in scope at the call site.
- Produces: `_collect(controls, framework, *, registrations)` — one new keyword-only param, forwarded to `ShareDecisions.registrations`. No pipeline change: `apply_all` already writes registrations first and skips empty mappings.

This task is independent of every other task and fixes a live bug. Do it first.

- [ ] **Step 1: Write the failing tests**

Add to `tests/share_flow/test_review_collection.py`. Note the existing `_controls()` helper and `_Control` stub are reused as-is.

```python
def test_registrations_are_carried_into_the_decision_set() -> None:
    """The Review screen renders each registration as a promise to write it.

    `_collect` must carry them through: they are not a decision (no control
    exists for them) but they ARE a write, and apply_all is the only thing
    that performs it. Omitting them made the screen name a file edit it never
    made — the CLI applied the same registrations unconditionally, so the two
    surfaces disagreed on identical input.
    """
    decisions = _collect(
        _controls(),
        None,
        registrations={ALPHA: ["haybale_studio"]},
    )

    assert decisions.registrations == {ALPHA: ["haybale_studio"]}


def test_no_registrations_stays_an_empty_mapping() -> None:
    """apply_all skips empty mappings, so nothing-to-register stays a no-op."""
    decisions = _collect(_controls(), None, registrations={})

    assert decisions.registrations == {}
```

Then update the existing `test_untouched_controls_produce_an_inert_decision_set` to assert the inert case explicitly, so "writes nothing" keeps meaning what the docstring claims:

```python
    assert decisions.registrations == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/share_flow/test_review_collection.py -v`
Expected: FAIL — `TypeError: _collect() got an unexpected keyword argument 'registrations'`

- [ ] **Step 3: Implement**

In `barn/haybale-share/haybale_share/_flow/panels.py`, change `_collect`'s signature and docstring:

```python
def _collect(
    controls: dict,
    framework: str | None,
    *,
    registrations: dict[Path, list[str]],
) -> ShareDecisions:
    """Read every control into the decision set. Touches no file.

    ``registrations`` has no control to read — it is not a decision (see
    ``DriftReport.linked_registrations``). It is threaded through because
    ``apply_all`` is the single write pass, so anything the Review screen
    promised on-screen has to reach it. It was omitted here once, and the
    wizard rendered registrations it never wrote while the CLI applied them.
    """
```

and add the field to the return:

```python
    return ShareDecisions(
        framework=framework,
        registrations=registrations,
        removals=removals,
        additions=additions,
        floors=floors,
        undeclared_acknowledged=skipped,
    )
```

Then update the single call site in `panel_review` — `registrations` is already computed two lines above it:

```python
    async def _go() -> None:
        await flow.advance_from_review(
            _collect(controls, framework_spec(), registrations=registrations),
            version_spec=version_spec(),
        )
```

Keyword-only is deliberate: it makes every existing positional call fail loudly rather than silently defaulting to `{}` again.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/share_flow/ -v`
Expected: PASS

- [ ] **Step 5: Run the pipeline-side tests that pin the write**

Run: `uv run pytest tests/share_pipeline/ -v`
Expected: PASS — `test_linked_registrations_are_applied_in_union_mode`, `test_linked_registrations_never_touch_pyproject`, and the `apply_all` ordering test all already exist and are unaffected; they were passing before because they test the pipeline directly, which is why the wizard gap survived.

- [ ] **Step 6: Lint + type-check**

```sh
uv run ruff check barn/haybale-share/haybale_share/_flow/panels.py tests/share_flow/test_review_collection.py
uv run ruff format --check barn/haybale-share/haybale_share/_flow/panels.py tests/share_flow/test_review_collection.py
uv run mypy barn/haybale-share/haybale_share/
```

- [ ] **Step 7: Manual verification**

Run `uv run haywire`, open the Share flow on a repo where at least one barn library imports a registered haywire library it does not declare (add `import haybale_core` to one if needed).

1. On the Review screen, confirm the "Library dependencies" section names the entry.
2. Click Apply and bump.
3. Confirm that library's `haybale.toml` now lists the entry in `linked_libraries`. Before this fix it did not.
4. `git diff` the file to confirm only `linked_libraries` changed and `pyproject.toml` is untouched.

- [ ] **Step 8: Commit**

```bash
git add barn/haybale-share/haybale_share/_flow/panels.py tests/share_flow/test_review_collection.py
git commit -m "fix(share): wizard applies the linked_libraries registrations it displays

The Review screen rendered each registration as a promise to write it, but
_collect never set ShareDecisions.registrations, so apply_all skipped the
empty mapping. The CLI applied the same registrations unconditionally, so
the two surfaces disagreed on identical input."
```

---

### Task 2: Injectable library source on `detect_share_drift()`

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/publishing/drift/detect.py`
- Test: `tests/test_share_drift.py`

**Interfaces:**
- Consumes: `HaywireLibrarySource` (existing `@runtime_checkable` Protocol at `dep_detect.py:46`).
- Produces: `detect_share_drift(lib_dir: Path, *, libraries: HaywireLibrarySource | None = None) -> DepDrift`. Defaults to `EntryPointLibrarySource()`, so both existing callers keep working unchanged. Consumed by Task 4.

This is the whole core-side change. `DepDrift` is untouched.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_share_drift.py`. Uses the existing `_make_library` fixture (kwarg is `linked_libraries=`) and the existing `_FakeLibrarySource`.

```python
@pytest.mark.unit
def test_detect_share_drift_accepts_injected_library_source(tmp_path: Path, monkeypatch) -> None:
    """A caller holding a live registry — the marketplace editor — can inject it
    instead of relying on EntryPointLibrarySource, same as detect_deps already
    allows via its own `libraries` param.

    Proof the param is honored rather than ignored: haybale_core IS installed
    and resolves to the dist haybale-core, so the default source classifies the
    import as a registered haywire library. A source that lists nothing must
    classify the same import as an ordinary pyproject dep, leaving
    linked_missing empty.
    """
    import importlib.metadata as _meta

    monkeypatch.setattr(_meta, "version", lambda dist: "0.0.1")
    lib = _make_library(
        tmp_path,
        pyproject_deps=[],
        linked_libraries=[],
        init_body_imports="import haybale_core\n",
    )

    assert "haybale_core" in detect_share_drift(lib).linked_missing
    assert detect_share_drift(lib, libraries=_FakeLibrarySource([])).linked_missing == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_share_drift.py -k injected_library_source -v`
Expected: FAIL — `TypeError: detect_share_drift() got an unexpected keyword argument 'libraries'`

- [ ] **Step 3: Implement**

Four surgical edits to `packages/haywire-core/src/haywire/core/publishing/drift/detect.py`. **Do not replace the whole file** — it is already post-`f8fd8a7c` (imports `norm_dep` from `dep_edit`, reads `detected.library_linked`), and a wholesale replacement is how an earlier draft would have silently reverted that rename.

Edit 1 — add `HaywireLibrarySource` to the existing `dep_detect` import block:

```python
from haywire.core.library.dep_detect import (
    DetectedDeps,
    EntryPointLibrarySource,
    HaywireLibrarySource,
    detect_deps,
    find_module_dir,
)
```

Edit 2 — the signature:

```python
def detect_share_drift(lib_dir: Path, *, libraries: HaywireLibrarySource | None = None) -> DepDrift:
```

Edit 3 — replace this docstring paragraph:

```python
    Uses :class:`EntryPointLibrarySource` so the gate works without a live
    haywire registry — any installed dist with a ``haywire.libraries`` entry
    point counts as a haywire library.
```

with:

```python
    ``libraries`` decides "is this distribution a registered haywire library"
    for the ``linked_libraries`` side of the comparison. Defaults to
    :class:`EntryPointLibrarySource`, so the gate works without a live haywire
    registry — any installed dist with a ``haywire.libraries`` entry point
    counts. A caller that already holds a live ``LibraryRegistry`` — the
    marketplace editor's Refresh button — should pass it instead, since it
    reflects installed/enabled state more accurately than entry-point metadata.
```

Edit 4 — replace the body's first line:

```python
    libraries = EntryPointLibrarySource()
```

with:

```python
    if libraries is None:
        libraries = EntryPointLibrarySource()
```

and widen `_detect_pyproject_version_lag`'s annotation from `EntryPointLibrarySource` to `HaywireLibrarySource`, since it may now receive either:

```python
def _detect_pyproject_version_lag(
    declared: list[str],
    *,
    libraries: HaywireLibrarySource,
) -> list[tuple[str, str, str]]:
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_share_drift.py -v`
Expected: PASS (all — `libraries=None` defaulting to `EntryPointLibrarySource()` preserves prior behavior exactly)

- [ ] **Step 5: Run the dependent suites + type-check**

```sh
uv run pytest tests/test_dep_detect.py tests/share_pipeline/ -v
uv run pytest tests/ -k "deps_check" -v
uv run mypy packages/haywire-core/src/haywire/core/publishing/drift/
```

Expected: PASS / no new errors. These cover the two production callers that must keep working with no `libraries` argument.

- [ ] **Step 6: Commit**

```bash
git add packages/haywire-core/src/haywire/core/publishing/drift/detect.py tests/test_share_drift.py
git commit -m "feat(drift): injectable library source on detect_share_drift"
```

---

### Task 3: The Refresh helper

**Files:**
- Modify: `barn/haybale-marketplace/haybale_marketplace/editors/_overview_edit_dialog.py`
- Test: `tests/marketplace/test_overview_edit_dialog_linked_libraries.py` (create)

**Interfaces:**
- Consumes: `detect_share_drift(lib_dir, *, libraries=...)` (Task 2), `DepDrift.linked_missing`, `find_module_dir`, `HaywireLibrarySource`.
- Produces: `_refresh_linked_libraries(lib_dir, *, current, libraries) -> _RefreshResult`. Pure — no writes. Consumed by Task 4.

Split from Task 4 so the union rule is tested without a browser.

- [ ] **Step 1: Write the failing tests**

Create `tests/marketplace/test_overview_edit_dialog_linked_libraries.py`:

```python
"""Tests for the linked_libraries Refresh helper behind the Edit dialog.

Refresh applies the same rule the share pipeline's apply_linked_registrations
uses: union in what the source provably imports, never remove. The editor
stages the result in memory; only Save Changes writes.

Fixtures import `haybale_core` rather than an invented module name: detect_deps
resolves modules through real venv metadata, so an uninstalled name lands in
`unresolved` and never reaches `linked_missing`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from haybale_marketplace.editors._overview_edit_dialog import _refresh_linked_libraries

pytestmark = pytest.mark.unit


class _FakeRegistry:
    """Minimal HaywireLibrarySource stand-in for LibraryRegistry."""

    def __init__(self, dists: dict[str, str]) -> None:
        self._dists = dists  # lib_id -> dist name

    def list_names(self) -> list[str]:
        return list(self._dists.keys())

    def get_library_distribution_name(self, library_id: str) -> str | None:
        return self._dists.get(library_id)


def _make_library(
    tmp_path: Path,
    *,
    module_name: str = "haybale_fake",
    linked_libraries: list[str] | None = None,
    init_body_imports: str = "",
) -> Path:
    """Scaffold a library root: pyproject.toml, plus a package with haybale.toml.

    Returns the LIBRARY ROOT (the pyproject.toml dir) — what detect_share_drift
    and find_module_dir both expect. See "The library-root problem" in the plan.
    """
    lib_dir = tmp_path / "haybale-fake"
    lib_dir.mkdir(parents=True)
    (lib_dir / "pyproject.toml").write_text('[project]\nname = "haybale-fake"\nversion = "0.0.1"\n')
    pkg_dir = lib_dir / module_name
    pkg_dir.mkdir()
    linked = linked_libraries or []
    linked_toml = "[" + ", ".join(f'"{n}"' for n in linked) + "]"
    (pkg_dir / "haybale.toml").write_text(
        'name = "haybale-fake"\nid = "fake"\nlabel = "Fake"\n' f"linked_libraries = {linked_toml}\n"
    )
    (pkg_dir / "__init__.py").write_text(f"{init_body_imports}\n")
    return lib_dir


def test_refresh_adds_a_detected_import() -> None:
    """The only thing Refresh does."""


def test_refresh_adds_missing_linked_library(tmp_path: Path) -> None:
    lib_dir = _make_library(tmp_path, linked_libraries=[], init_body_imports="import haybale_core\n")

    result = _refresh_linked_libraries(
        lib_dir, current=[], libraries=_FakeRegistry({"core": "haybale-core"})
    )

    assert result.added == ["haybale_core"]
    assert result.merged == ["haybale_core"]
    assert result.no_module_dir is False


def test_refresh_is_idempotent_for_an_already_declared_entry(tmp_path: Path) -> None:
    lib_dir = _make_library(
        tmp_path, linked_libraries=["haybale_core"], init_body_imports="import haybale_core\n"
    )

    result = _refresh_linked_libraries(
        lib_dir, current=["haybale_core"], libraries=_FakeRegistry({"core": "haybale-core"})
    )

    assert result.added == []
    assert result.merged == ["haybale_core"]


def test_refresh_never_removes_an_undetected_entry(tmp_path: Path) -> None:
    """Union, exactly as apply_linked_registrations does it.

    A declared entry the scanner no longer sees is indistinguishable from a
    dynamic import it never could see, so it survives untouched.
    """
    lib_dir = _make_library(tmp_path, linked_libraries=["haybale_core"], init_body_imports="")

    result = _refresh_linked_libraries(
        lib_dir, current=["haybale_core"], libraries=_FakeRegistry({"core": "haybale-core"})
    )

    assert result.added == []
    assert result.merged == ["haybale_core"]


def test_refresh_preserves_entries_the_scan_cannot_prove(tmp_path: Path) -> None:
    """`current` is preserved wholesale, additions merge on top."""
    lib_dir = _make_library(
        tmp_path, linked_libraries=["haybale_hand_added"], init_body_imports="import haybale_core\n"
    )

    result = _refresh_linked_libraries(
        lib_dir, current=["haybale_hand_added"], libraries=_FakeRegistry({"core": "haybale-core"})
    )

    assert result.added == ["haybale_core"]
    assert result.merged == ["haybale_core", "haybale_hand_added"]


def test_refresh_reports_no_module_dir_when_source_is_missing(tmp_path: Path) -> None:
    lib_dir = tmp_path / "haybale-empty"
    lib_dir.mkdir()
    (lib_dir / "pyproject.toml").write_text('[project]\nname = "haybale-empty"\nversion = "0.0.1"\n')

    result = _refresh_linked_libraries(lib_dir, current=[], libraries=_FakeRegistry({}))

    assert result.no_module_dir is True
    assert result.added == []
```

Delete the stub `test_refresh_adds_a_detected_import` placeholder before committing — it is listed above only to make the intent ordering readable; it has no body and must not ship.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/marketplace/test_overview_edit_dialog_linked_libraries.py -v`
Expected: FAIL — `ImportError: cannot import name '_refresh_linked_libraries'`

- [ ] **Step 3: Implement**

In `barn/haybale-marketplace/haybale_marketplace/editors/_overview_edit_dialog.py`.

Append to the module docstring, after the `[deprecated]` bullet:

```python
``linked_libraries`` is the one exception to "no detection here", and it is a
narrow one: a Refresh button applies the same rule the share pipeline's
``apply_linked_registrations`` applies — union in what the source provably
imports, never remove, never ask. It is a fact, not an authored decision like a
pip dependency's version floor, which is why it needs no control beyond a
button. This does NOT extend to pip dependencies: ``[project] dependencies``
stays exclusively a ``haywire share`` concern (see marketplace-arch.md §6).
"""
```

Add `dataclass` to the stdlib imports and two haywire imports in alphabetical position:

```python
from dataclasses import dataclass, field
```

```python
from haywire.core.library.dep_detect import HaywireLibrarySource, find_module_dir
from haywire.core.library.haybale_toml import read_display, read_haybale_toml_lenient
from haywire.core.library.identity import LibraryReloadAction
from haywire.core.library.info import LibraryInfo
from haywire.core.publishing.drift.detect import detect_share_drift
```

After `logger = logging.getLogger(__name__)`, before `build_edit_dialog`:

```python
@dataclass(frozen=True)
class _RefreshResult:
    """Outcome of one Refresh click — never written to disk by this module."""

    added: list[str] = field(default_factory=list)
    """Detected entries that were not already declared."""
    merged: list[str] = field(default_factory=list)
    """`current` ∪ `added`, sorted — the value to stage. Never smaller than
    `current`: Refresh is union-only."""
    no_module_dir: bool = False
    """True when the library has no inspectable source — nothing to scan."""


def _refresh_linked_libraries(
    lib_dir: Path,
    *,
    current: list[str],
    libraries: HaywireLibrarySource,
) -> _RefreshResult:
    """Detect the library's imported haywire libraries and union them in.

    Pure — no writes. The rule is the share pipeline's, deliberately:
    ``apply_linked_registrations`` merges ``linked_missing`` into the declared
    list and drops nothing, because ``detect_deps`` emits a name only when the
    source imports it AND it resolves to an installed registered library. A
    declared entry the scan does not see is indistinguishable from a dynamic
    import it cannot see, so removal is never inferred — on any surface.

    ``lib_dir`` is the LIBRARY ROOT (the ``pyproject.toml`` directory), NOT the
    package dir: ``detect_share_drift`` reads ``lib_dir/pyproject.toml`` and
    finds the package itself via ``find_module_dir``.
    ``LibraryInfo.identity.folder_path`` is the *package* dir, so the caller
    passes its ``.parent`` — sound only for heap libraries, whose folder_path is
    provably ``barn/<lib>/<module>/``. See :func:`build_edit_dialog`.

    Only ``linked_missing`` is read. The pyproject-dependency fields on the
    returned ``DepDrift`` are deliberately ignored: pip-dependency authoring
    stays out of this dialog (see the module docstring).
    """
    if find_module_dir(lib_dir) is None:
        return _RefreshResult(no_module_dir=True)

    drift = detect_share_drift(lib_dir, libraries=libraries)
    current_set = set(current)
    added = sorted(n for n in drift.linked_missing if n not in current_set)
    return _RefreshResult(added=added, merged=sorted(current_set | set(added)), no_module_dir=False)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/marketplace/test_overview_edit_dialog_linked_libraries.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add barn/haybale-marketplace/haybale_marketplace/editors/_overview_edit_dialog.py tests/marketplace/test_overview_edit_dialog_linked_libraries.py
git commit -m "feat(marketplace): _refresh_linked_libraries — union rule, no writes"
```

---

### Task 4: Wire the label + Refresh button into the dialog

**Files:**
- Modify: `barn/haybale-marketplace/haybale_marketplace/editors/_overview_edit_dialog.py`

**Interfaces:**
- Consumes: `_refresh_linked_libraries` (Task 3), `manager.registry: LibraryRegistry` (`library_manager.py:189` — structurally satisfies `HaywireLibrarySource` via `list_names()` / `get_library_distribution_name()`), `is_project_library` (already imported).
- Produces: `build_edit_dialog(...)` signature unchanged; the identity dict gains `"linked_libraries": list[str]` **only for heap libraries whose value Refresh actually changed**. Consumed by the existing `manager.update_library_identity` → `write_haybale_fields` path — `linked_libraries` is already in `EDITABLE_FIELDS`, so nothing there changes.

**Read "The library-root problem" before starting.**

- [ ] **Step 1: Move the `_is_heap` computation up**

It currently sits next to the `os` field, below where `linked_libraries` renders. Delete it from there:

```python
        _is_heap = is_project_library(lib, marketplace_path)
        current_os = list(read_haybale_toml_lenient(Path(lib.identity.folder_path)).get("os") or [])
```

leaving:

```python
        current_os = list(read_haybale_toml_lenient(Path(lib.identity.folder_path)).get("os") or [])
```

- [ ] **Step 2: Replace the read-only label block**

Find:

```python
        # linked_libraries is maintained by `haywire share`'s drift detector,
        # which can prove what a library actually imports.
        ui.label(
            f"Linked libraries: {', '.join(lib.identity.linked_libraries or []) or '(none)'}"
            " (maintained by Share)"
        ).classes("text-xs hw-text-dim")
```

Replace with:

```python
        # Still a label, not an input: the author has nothing to decide here.
        # Refresh applies the pipeline's own rule (union what is provably
        # imported, never remove), so the only affordance needed is the button.
        #
        # Heap-gated for the same reason `os` is — an installed wheel lives in
        # site-packages, where an edit is lost on the next reinstall. It is also
        # a correctness gate: detect_share_drift needs the LIBRARY ROOT, and
        # folder_path.parent only reaches it for heaps, whose folder_path is
        # provably barn/<lib>/<module>/ (exactly what is_project_library
        # checks). For a site-packages wheel the parent is site-packages itself.
        _is_heap = is_project_library(lib, marketplace_path)
        _pkg_dir = Path(lib.identity.folder_path)
        # Read the file, not lib.identity: identity carries the value loaded at
        # startup, so a previous save in this session would render stale.
        _linked: list[str] = list(read_haybale_toml_lenient(_pkg_dir).get("linked_libraries") or [])
        _linked_staged: list[str] = list(_linked)

        with ui.row().classes("items-center gap-2"):
            linked_label = ui.label().classes("text-xs hw-text-dim")

            def _render_linked() -> None:
                shown = ", ".join(_linked_staged) or "(none)"
                linked_label.set_text(f"Linked libraries: {shown}")

            _render_linked()

            if _is_heap:
                _lib_root = _pkg_dir.parent

                def _do_refresh(m=manager, lib_root=_lib_root) -> None:
                    result = _refresh_linked_libraries(
                        lib_root, current=list(_linked_staged), libraries=m.registry
                    )
                    if result.no_module_dir:
                        ui.notify("No inspectable source found — nothing to detect.", type="warning")
                        return
                    if not result.added:
                        ui.notify("Nothing new detected.", type="info")
                        return
                    _linked_staged[:] = result.merged
                    _render_linked()
                    ui.notify(
                        f"Added: {', '.join(result.added)}. Click Save Changes to write.",
                        type="positive",
                    )

                _refresh_button = ui.button(icon="refresh", on_click=_do_refresh).props(
                    "size=sm flat dense"
                )
                if find_module_dir(_lib_root) is None:
                    _refresh_button.disable()
                    _refresh_button.tooltip("No inspectable source found for this library.")
                else:
                    _refresh_button.tooltip("Detect imported haywire libraries and add any missing.")
```

`_linked_staged[:] = ...` mutates in place rather than rebinding, so the closure and `_save` observe the same list without a `nonlocal`.

- [ ] **Step 3: Persist it in `_save()`**

Amend the comment and add the conditional write alongside the existing `os` one:

```python
        async def _save():
            # Only the keys this dialog owns. write_haybale_fields edits in
            # place, so an omitted key is left alone rather than erased — which
            # is why [deprecated] survives a save untouched, and why an
            # unrefreshed linked_libraries is left exactly as the file has it.
            identity = {
                "label": label_input.value.strip(),
                "description": desc_input.value.strip(),
                "homepage_url": url_input.value.strip(),
                "documentation_url": docs_url_input.value.strip(),
                "issues_url": issues_url_input.value.strip(),
                "tags": [t.strip() for t in tags_input.value.split(",") if t.strip()],
                "on_reload": on_reload_select.value or LibraryReloadAction.NONE.value,
            }
            # `os` only when its multi-select was rendered (heap libraries).
            if os_select is not None:
                identity["os"] = list(os_select.value or [])
            # linked_libraries only when Refresh actually changed it — an
            # untouched dialog must not rewrite a hand-authored list.
            if _linked_staged != _linked:
                identity["linked_libraries"] = list(_linked_staged)
            edit_popup.close()
            await on_save(identity)
```

The `!=` guard matters: without it every Save rewrites `linked_libraries` with what it just read, churning a hand-authored file for no reason.

**Validation note:** `write_haybale_fields` runs `_validate_linked_libraries`, which requires bare module names (`^[A-Za-z_][A-Za-z0-9_]*$`). Every value here comes from `norm_dep`, which emits underscored names, so this cannot fail — and with no free-text control there is no path for a user to introduce a hyphen. This is a direct benefit of dropping the multi-select.

- [ ] **Step 4: Run the marketplace suite**

Run: `uv run pytest tests/marketplace/ tests/test_library_manager_marketplace_writes.py -v`
Expected: PASS — `update_library_identity` tests call the manager directly with a hand-built dict, not through `_save`.

- [ ] **Step 5: Lint + type-check**

```sh
uv run ruff check barn/haybale-marketplace/haybale_marketplace/editors/_overview_edit_dialog.py
uv run ruff format --check barn/haybale-marketplace/haybale_marketplace/editors/_overview_edit_dialog.py
uv run mypy barn/haybale-marketplace/haybale_marketplace/
```

- [ ] **Step 6: Manual verification in the running studio**

Run: `uv run haywire`

1. Open the Library Overview Editor for a **heap** library, click Edit. Confirm "Linked libraries: …" renders as a label with a small refresh icon button beside it.
2. Confirm the button is **enabled**. (This is the specific regression an earlier draft would have shipped: passing `folder_path` instead of `.parent` leaves it permanently disabled and looking intentional.)
3. Add a real undeclared import to that library's source (`import haybale_core` where it wasn't), save the file, reopen the dialog, click Refresh. Confirm the label gains the entry and the notification says it needs Save.
4. Click Save Changes; confirm `haybale.toml` on disk now lists it.
5. Reopen, click Refresh again. Confirm "Nothing new detected." and no label change.
6. Remove the import from source, click Refresh. Confirm the entry is **not** removed — union only.
7. Open the dialog, change only the Label, Save. Confirm `git diff` on `haybale.toml` shows no `linked_libraries` churn.
8. Open a **non-heap** (installed-wheel) library. Confirm the label renders and no Refresh button appears.

- [ ] **Step 7: Commit**

```bash
git add barn/haybale-marketplace/haybale_marketplace/editors/_overview_edit_dialog.py
git commit -m "feat(marketplace): Refresh button applies linked_libraries registrations in the Edit dialog"
```

---

### Task 5: Rewrite marketplace-arch.md §6

**Files:**
- Modify: `docs/haybale/marketplace/haybale-marketplace-arch.md`

The current §6 (verified at lines 362–381, ending before `## 7. Failure surfaces`) documents the **retired** Detect Dependencies button with its Union/Replace modes and still says `@library` deps.

- [ ] **Step 1: Replace §6**

Verify the range (`grep -n "^## 6\.\|^## 7\." docs/haybale/marketplace/haybale-marketplace-arch.md`), then replace from `## 6.` up to but not including `## 7.`:

```markdown
## 6. Linked-libraries registration at edit time

The Library Overview Editor's Edit dialog can register imported haywire libraries into `haybale.toml`'s `linked_libraries` without going through `haywire share`. It applies the same rule the share pipeline applies, deliberately: **union in what the source provably imports; never remove; never ask.**

**Why this field and no other.** `linked_libraries` is the one dependency-shaped field this editor authors. Every other dependency concern — `[project] dependencies` in the library's pyproject — stays exclusively a `haywire share` concern. The distinction is decision vs. fact: a pip dependency's version floor is an authored choice with real tradeoffs (which floor, whether a lagging version matters). A missing `linked_libraries` entry is provably true — `detect_deps` emits a name only when the source imports it *and* it resolves to an installed, registered haywire library — so there is nothing to decide, only to apply.

That is why the control is a **label and a button**, not an editable field. An input would imply a judgement the author does not have to make, and would invite a hand-typed value that `_validate_linked_libraries` rejects at write time.

### How it works

1. "Linked libraries" renders as a read-only label of the current declared list, read from `haybale.toml` rather than from `LibraryInfo.identity` (identity holds the startup value and would render stale after an in-session save).
2. A **Refresh** button — heap libraries only, the same rule `os` follows — runs `detect_share_drift(lib_root, libraries=manager.registry)`, the same function `haywire share` uses, passed the studio's live `LibraryRegistry` instead of the CLI's entry-point-derived source.
3. Detected entries not already declared are unioned into a staged list and the label re-renders. Nothing else changes: an entry the scan no longer sees is left alone, because a dynamic import the scanner cannot see is indistinguishable from an obsolete one.
4. Refresh writes nothing. Only **Save Changes** writes, through the same `write_haybale_fields` path every other field uses — and only when Refresh actually changed the list, so an untouched dialog never churns a hand-authored file.

### The library-root subtlety

`detect_share_drift` takes the **library root** (the `pyproject.toml` directory) and locates the package itself via `find_module_dir`. Both CLI callers get that path from a filesystem scan — `barn_library_dirs(repo_root)`, which selects non-symlinked children of `barn/` that have a `pyproject.toml`.

The editor has no such scan; it has a `LibraryInfo` whose `identity.folder_path` is the **package** directory (it is what `read_display` and `read_haybale_toml_lenient` are given). The editor therefore passes `folder_path.parent`, which is correct precisely because of the heap gate: `is_project_library` establishes that `folder_path` sits under the workspace's `barn/`, so its parent is the `barn/<lib>/` directory the pipeline would have scanned. For a site-packages wheel the parent is `site-packages/` — no `pyproject.toml`, no valid detection. Passing `folder_path` directly fails silently: `find_module_dir` returns `None` and the button renders permanently disabled, looking like correct behavior.

### One rule, three surfaces

| Surface | How registrations are applied |
| --- | --- |
| `haywire share` CLI | Unconditionally, before the drift branch; each entry printed as it is applied |
| Share wizard | Named on the Review screen, applied by `apply_all` in the single write pass |
| Edit dialog Refresh | Staged into the label on click, written by Save Changes |

All three read the same `DriftReport.linked_registrations` / `linked_missing` and apply the same union. That property is load-bearing and was not always true: the wizard rendered registrations it never wrote, because `_collect` omitted them from the `ShareDecisions` it handed `apply_all`, while the CLI applied the same registrations on identical input. `DriftReport.linked_registrations` exists as a single hoisted property for exactly this reason — its docstring records that the logic "was duplicated in both, divergently, before this property existed."

### Not a return of the old Detect Dependencies button

An earlier version of this dialog had a "Detect Dependencies" button that scanned *both* `linked_libraries` and pip dependencies, offering Union/Replace across both. It was removed because the pip-dependency side created two uncoordinated writers to the same `[project] dependencies` list — this button and the Share wizard's own writer — which is what let the framework floor get silently clobbered. That bug never existed on the `linked_libraries` side: those entries were already "applied automatically, never a choice" even inside the Share flow, so a second surface applying the same provably-true rule does not recreate the conflict. Note also that only Union survives here; Replace was the destructive half and has no equivalent on any surface.

The same detection backs the CLI: step 2 of `SharePipeline` and `haywire deps check` both call `detect_share_drift()` ([share-pipeline-arch §2.2](../../architecture/sharing/share-pipeline-arch.md#22-step-2-dependency-drift)). For the author-facing workflow, see the [sharing-libraries guide §3](../../guides/sharing-libraries.md#63-keeping-the-manifests-honest).
```

- [ ] **Step 2: Verify the doc builds**

Run: `uv run mkdocs build --strict 2>&1 | grep -i "haybale-marketplace-arch\|warning" | head -30`
Expected: no new warnings. The two carried-over links are preserved verbatim from the old §6, so they were already valid.

- [ ] **Step 3: Commit**

```bash
git add docs/haybale/marketplace/haybale-marketplace-arch.md
git commit -m "docs(marketplace-arch): rewrite §6 for linked_libraries registration at edit time"
```

---

### Task 6: Glossary update

**Files:**
- Modify: `docs/reference/glossary.md`

The glossary is already post-`f8fd8a7c`: line 263's `DepDrift` row lists `linked_missing` and line 270 is **Linked registration**, which flags "decorator registration" as retired. No new term is needed — this feature adds a surface, not a concept. Do not add any `decorator_*` term.

- [ ] **Step 1: Update the "one authoring path" line**

Replace line 477:

```
- A library's published manifest survives `haywire share` only if the **Three manifest layers** agree. The **Detect step** reports divergence; the Share flow's Review screen reconciles it. The Library Overview Editor is read-only for dependencies — one authoring path, not two.
```

with:

```
- A library's published manifest survives `haywire share` only if the **Three manifest layers** agree. The **Detect step** reports divergence; the Share flow's Review screen reconciles it. The Library Overview Editor is read-only for **library pyproject** dependencies — one authoring path, not two. `linked_libraries` is the exception, and not a second authoring path: the Edit dialog's Refresh button applies the same union rule the CLI and wizard apply, because a **Linked registration** is provably true and carries no author decision a second writer could clobber.
```

- [ ] **Step 2: Extend the `Linked registration` row**

Append to the line-270 row's definition, before its aliases column:

```
Applied identically on all three surfaces that touch it — `haywire share` CLI, the Share wizard's Review screen, and the Library Overview Editor's Refresh button — all reading `DriftReport.linked_registrations`.
```

- [ ] **Step 3: Fix the stale Q&A answer**

Run: `grep -n "shows dependencies read-only" docs/reference/glossary.md`

Line 543's domain-expert answer says "the editor shows dependencies read-only" without qualification, which Step 1 just narrowed. Add the same exception clause so the two do not contradict. Leave line 545 alone — it is about `haywire share`'s own modes and is unaffected.

- [ ] **Step 4: Verify no retired phrasing crept in**

Run: `grep -n "decorator_missing\|decorator_unused\|@library(dependencies" docs/reference/glossary.md`
Expected: only the existing "aliases to avoid" mentions documenting the retired names.

- [ ] **Step 5: Commit**

```bash
git add docs/reference/glossary.md
git commit -m "docs(glossary): note linked_libraries registration is one rule on three surfaces"
```

---

### Task 7: Full-suite gate

- [ ] **Step 1: Pre-commit gate**

```sh
uv run pytest -m "not browser and not perf" -q > /tmp/linked-libs.log 2>&1; echo "exit=$?"
grep -E "^FAILED|^ERROR" /tmp/linked-libs.log
grep -E "passed|failed" /tmp/linked-libs.log | tail -1
```

Expected: exit=0. Use a timeout ≥ 600000 ms.

- [ ] **Step 2: Repo-wide lint + type-check**

```sh
uv run ruff check .
uv run ruff format --check .
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-marketplace/haybale_marketplace/ barn/haybale-share/haybale_share/ barn/haybale-graph-editor/haybale_graph_editor/ barn/haybale-haystack/haybale_haystack/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-TEST_A/haybale_test_a/ tests/
```

Expected: all clean.

---

## Verified facts this plan rests on

Each was checked against the working tree or by running it, not inferred from docstrings.

| Claim | How verified |
| --- | --- |
| `_collect` omits `registrations`; wizard never writes them | Read the return; runtime introspection of `_collect`'s source; no `.registrations` assignment anywhere in `haybale-share/` or `haywire_studio/packaging/`; no other `write_haybale_fields` call in the wizard |
| CLI applies them unconditionally | `share_cli.py:124-130`, before the `needs_decision` branch |
| `apply_all` skips empty mappings | `pipeline.py:193` — `if decisions.registrations:` |
| `linked_registrations` reads drifted + findings_only | `results.py:145-158` |
| Union rule, `haybale.toml` only | `steps/dependencies.py:122`; `test_linked_registrations_never_touch_pyproject` |
| `find_module_dir(package_dir)` returns `None` | Ran it: lib root → package path, package dir → `None` |
| Invented module names never reach `linked_missing` | Ran `detect_deps`: `library_linked=['haybale_core']`, `unresolved=['haybale_dep']` |
| `folder_path` is the package dir | `read_display(folder_path)` / `read_haybale_toml_lenient(folder_path)` both take `package_dir` |
| `.parent` is the pipeline's `lib_dir` for heaps | `is_project_library` asserts `folder_path` under `workspace_root/barn`; `barn_library_dirs` scans the same tree |
| All barn libs are flat layout | No `barn/*/src` exists |
| `linked_libraries` already writable | `EDITABLE_FIELDS` in `haybale_toml.py:339` |
| `norm_dep` output passes validation | Emits underscored names; `_MODULE_NAME` is `^[A-Za-z_][A-Za-z0-9_]*$` |
| `manager.registry` satisfies the Protocol | `library_manager.py:189`; `HaywireLibrarySource` is `@runtime_checkable` at `dep_detect.py:46` |

## Open follow-up, deliberately not in scope

The wizard's Review screen renders registrations under a "Library dependencies" heading with no indication they are unconditional, sitting among sections that *are* choices. Task 1 makes the write real, which is the correctness fix. Whether that section should read differently now that it actually does something is a UX question worth asking separately, with the fix in hand.
