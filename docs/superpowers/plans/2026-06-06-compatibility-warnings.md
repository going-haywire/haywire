# Compatibility Warnings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When a graph is loaded from a file saved by an older library version, surface author-declared, advisory Compatibility Warnings on the affected nodes (per-node badge + on-open summary) so the user knows which nodes predate a behavioural change — without ever mutating the saved data.

**Architecture:** Library authors declare an append-only history of `CompatibilityWarning` entries on their `BaseLibrary` subclass. A stateless, unit-testable `CompatibilityChecker` runs once inside `Graph.load_from_dict` (after the node-build loop): for each node it compares the *saved* `library.version` against each warning's `version` and, on `saved < warning.version`, writes a `NodeWarning` record into a new `NodeWrapperState.warnings` list. The studio node skin renders a warnings badge (mirroring the existing errors badge), and the graph editor shows a one-time summary on open. The feature is read-only; the existing **Reset Node** action (full `init()` rebuild) is the user-driven remedy, *suggested not promised* (it is lossy for dynamically-created ports).

**Tech Stack:** Python 3.12, dataclasses, NiceGUI (studio skins / graph-editor panels), pytest (`-m unit` / `-m integration`), ruff, mypy.

---

## Background context (read before starting)

The root bug this addresses (verified empirically): a graph saved by an old library stores port state that the load path reads from the file rather than re-deriving from code. Example: `WebcamFrameInfoDisplayNode`'s `frame` inlet declares `show_widget=WHEN_LINKED` in `init()`, but `init()` is **not** called on load — ports are rebuilt purely from the saved spec (`packages/haywire-core/src/haywire/core/node/node_wrapper.py:341-344` → `_initialize_from_dict` → `_deserialize_ports`). An old file lacking `show_widget` falls back to the dataclass default `NOT_LINKED`, hiding the widget. We **cannot** auto-fix this (dynamic ports make the file authoritative for topology; a stranded value may be intentional), so the feature only *detects and surfaces*.

Key facts the tasks rely on:

- **Saved version source:** each node serializes `"library": asdict(self.library)` (`node/base.py:1292`). So `node_data["library"]["version"]` is the version the file was saved with, and `node_data["library"]["id"]` is the library id.
- **Current/live data:** a built `NodeWrapper` exposes its node class via `self._node_cls`; the class carries `class_identity` (`NodeIdentity`, has `.registry_key`) and `class_library` (`LibraryIdentity`, has `.version`, `.id`). See `node/base.py:49-51`.
- **Live library instances** live in `LibraryRegistry._libraries: Dict[str, BaseLibrary]` keyed by library id (`library/registry.py:55`). Accessible in production via `get_library_system().get_library_registry()` (`di/config.py:655, 851`).
- **Load hook point:** `Graph.load_from_dict` builds all nodes, then all edges, then runs `_housekeeping()` per wrapper, then returns (`graph/base.py:911-999`). The checker call goes after the node-build loop / `_housekeeping`.
- **Node state today** (`NodeWrapperState`, `node/node_wrapper.py:30-105`) has a rich error model but **no warnings field** — unlike `EdgeWrapperState` which has `warnings: List[str]` (`edge/edge_wrapper.py:48`). This asymmetry is closed by Task 4.
- **Skin error badge pattern:** `default_skin.render` calls `runtime_errors = wrapper.state.get_errors()` then `self._render_errors_button(...)` (`barn/haybale-studio/haybale_studio/skins/default_skin.py:43-45`). The warnings badge mirrors this.
- **Test import rule (CLAUDE.md):** test files must `import haywire.core.graph.editor` *before* other haywire modules to avoid circular imports.
- **Integration fixtures:** `library_system`, `graph_with_library_system` (full library system, real nodes); mark with `@pytest.mark.integration`. Unit tests for the checker use plain fakes and are `@pytest.mark.unit`.

---

## File Structure

**New files**

- `packages/haywire-core/src/haywire/core/library/compatibility.py` — the `CompatibilityWarning` dataclass, semver parsing/validation, and the `CompatibilityChecker` (pure logic). One responsibility: deciding which warnings fire for a saved graph.
- `packages/haywire-core/src/haywire/core/node/node_warning.py` — the `NodeWarning` record stored on node state. Tiny, dependency-free; lives next to the node model.
- `tests/core/test_library/test_compatibility.py` — unit tests for semver parse + `CompatibilityChecker` trigger logic.
- `tests/core/test_graph/test_compatibility_on_load.py` — integration test: real graph load populates `state.warnings`.
- `docs/adr/0005-compatibility-warnings.md` — the decision record (final task).

**Modified files**

- `packages/haywire-core/src/haywire/core/library/base.py` — add `compatibility_warnings()` hook on `BaseLibrary`.
- `packages/haywire-core/src/haywire/core/node/node_wrapper.py` — add `warnings: list[NodeWarning]` to `NodeWrapperState` + `add_warning`/`has_warning`/`clear_warnings`.
- `packages/haywire-core/src/haywire/core/graph/base.py` — invoke `CompatibilityChecker` from `load_from_dict`.
- `barn/haybale-studio/haybale_studio/skins/default_skin.py` — render the per-node warnings badge.
- `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/visual_layer.py` — emit the one-time on-open summary in `sync_with_graph`.
- `docs/reference/glossary.md` — add the Compatibility Warning terms (final task).
- `docs/components/...` / library authoring docs — document the authoring API (final task).

---

## Task 1: `CompatibilityWarning` dataclass + semver validation

**Files:**
- Create: `packages/haywire-core/src/haywire/core/library/compatibility.py`
- Test: `tests/core/test_library/test_compatibility.py`

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_library/test_compatibility.py`:

```python
"""Unit tests for Compatibility Warning semver parsing + trigger logic."""

import haywire.core.graph.editor  # noqa: F401  circular-import guard (CLAUDE.md)

import pytest

from haywire.core.library.compatibility import (
    CompatibilityWarning,
    parse_semver,
    SemverError,
)


@pytest.mark.unit
class TestParseSemver:
    def test_parses_dotted_triplet(self):
        assert parse_semver("0.0.14") == (0, 0, 14)

    def test_ordering_is_numeric_not_lexical(self):
        # 0.0.9 < 0.0.10 must hold (string compare would get this wrong)
        assert parse_semver("0.0.9") < parse_semver("0.0.10")

    def test_rejects_underscore_form(self):
        with pytest.raises(SemverError) as exc:
            parse_semver("0_0_14")
        assert "MAJOR.MINOR.PATCH" in str(exc.value)

    def test_rejects_v_prefix(self):
        with pytest.raises(SemverError):
            parse_semver("v0.0.14")

    def test_rejects_two_part(self):
        with pytest.raises(SemverError):
            parse_semver("0.0")


@pytest.mark.unit
class TestCompatibilityWarningValidation:
    def test_valid_warning_constructs(self):
        w = CompatibilityWarning(
            version="0.0.14",
            component=None,
            message="A library-wide change.",
        )
        assert w.version_tuple == (0, 0, 14)

    def test_malformed_version_fails_loud_with_context(self):
        with pytest.raises(SemverError) as exc:
            CompatibilityWarning(version="0_0_14", component=None, message="x")
        # Message must name the expected form so an author can self-correct.
        assert "0.0.14" in str(exc.value)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_library/test_compatibility.py -m unit -v`
Expected: FAIL — `ModuleNotFoundError: haywire.core.library.compatibility`.

- [ ] **Step 3: Write minimal implementation**

Create `packages/haywire-core/src/haywire/core/library/compatibility.py`:

```python
"""Compatibility Warnings — advisory, author-declared notices that a graph
saved by an older library version may not reflect a later behavioural change.

This module is pure logic: the dataclass an author writes, semver parsing,
and the CompatibilityChecker that decides which warnings fire for a saved
graph. It never mutates graph data — see ADR 0005.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

_SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


class SemverError(ValueError):
    """Raised when a version string is not strict MAJOR.MINOR.PATCH semver."""


def parse_semver(version: str) -> tuple[int, int, int]:
    """Parse a strict dotted ``MAJOR.MINOR.PATCH`` string into a comparable tuple.

    Raises:
        SemverError: if the string is not exactly three dot-separated integers.
    """
    match = _SEMVER_RE.match(version.strip()) if isinstance(version, str) else None
    if match is None:
        raise SemverError(
            f"version {version!r} is not valid semver; "
            f"use 'MAJOR.MINOR.PATCH', e.g. '0.0.14'"
        )
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))


@dataclass
class CompatibilityWarning:
    """An author-declared advisory about a behavioural change in a library.

    Fields:
        version: The version in which the change landed (strict semver string).
            A graph whose saved node was stored with a library version *below*
            this value triggers the warning. This is a historical fact and is
            ALWAYS explicit — never derived from the library's current version.
        component: Anything exposing ``class_identity`` + ``class_library``
            (e.g. a node class), or ``None`` for a library-wide warning. A
            non-None component is matched against saved nodes by registry_key.
        message: Human-readable description of what changed and what to review.
    """

    version: str
    component: Optional[Any]
    message: str
    version_tuple: tuple[int, int, int] = field(init=False)

    def __post_init__(self) -> None:
        # Fail loud and early (at library load) on a malformed authored version.
        self.version_tuple = parse_semver(self.version)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/test_library/test_compatibility.py -m unit -v`
Expected: PASS (all tests in both classes).

- [ ] **Step 5: Lint & type-check the new file**

Run: `uv run ruff check packages/haywire-core/src/haywire/core/library/compatibility.py && uv run mypy packages/haywire-core/src/haywire/core/library/compatibility.py`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add packages/haywire-core/src/haywire/core/library/compatibility.py tests/core/test_library/test_compatibility.py
git commit -m "feat: CompatibilityWarning dataclass + strict semver validation"
```

---

## Task 2: `CompatibilityChecker` trigger logic

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/library/compatibility.py`
- Test: `tests/core/test_library/test_compatibility.py:append`

The checker is a pure function of (saved node entries, library warning histories) → resolved findings. To keep it unit-testable without a full library system, it takes a small callable that yields a library's warnings by id, and operates on lightweight inputs rather than live wrappers.

- [ ] **Step 1: Write the failing test**

Append to `tests/core/test_library/test_compatibility.py`:

```python
from haywire.core.library.compatibility import (
    CompatibilityChecker,
    SavedNode,
    CompatibilityFinding,
)


def _history_lookup(table):
    """Return a warnings-by-library-id lookup backed by a dict."""
    return lambda lib_id: table.get(lib_id, [])


@pytest.mark.unit
class TestCompatibilityChecker:
    def test_node_warning_fires_when_saved_below_version(self):
        warnings = [
            CompatibilityWarning(
                version="0.0.14",
                component="visiongraph:node:WebcamFrameInfoDisplayNode",
                message="inlet widget strategy became author-declared",
            )
        ]
        checker = CompatibilityChecker(_history_lookup({"visiongraph": warnings}))
        saved = [
            SavedNode(
                node_id="n1",
                registry_key="visiongraph:node:WebcamFrameInfoDisplayNode",
                library_id="visiongraph",
                saved_version="0.0.13",
            )
        ]
        findings = checker.check(saved)
        assert findings == [
            CompatibilityFinding(
                node_id="n1",
                message="inlet widget strategy became author-declared",
                source_version="0.0.13",
            )
        ]

    def test_does_not_fire_when_saved_equals_or_above_version(self):
        warnings = [
            CompatibilityWarning(
                version="0.0.14",
                component="visiongraph:node:WebcamFrameInfoDisplayNode",
                message="x",
            )
        ]
        checker = CompatibilityChecker(_history_lookup({"visiongraph": warnings}))
        saved = [
            SavedNode("n1", "visiongraph:node:WebcamFrameInfoDisplayNode", "visiongraph", "0.0.14"),
            SavedNode("n2", "visiongraph:node:WebcamFrameInfoDisplayNode", "visiongraph", "0.1.0"),
        ]
        assert checker.check(saved) == []

    def test_node_warning_matches_by_registry_key(self):
        warnings = [
            CompatibilityWarning(version="0.0.14", component="visiongraph:node:Other", message="x")
        ]
        checker = CompatibilityChecker(_history_lookup({"visiongraph": warnings}))
        saved = [SavedNode("n1", "visiongraph:node:WebcamFrameInfoDisplayNode", "visiongraph", "0.0.13")]
        assert checker.check(saved) == []  # different node, no match

    def test_missing_saved_version_treated_as_infinitely_old(self):
        warnings = [
            CompatibilityWarning(version="0.0.14", component="visiongraph:node:Foo", message="x")
        ]
        checker = CompatibilityChecker(_history_lookup({"visiongraph": warnings}))
        saved = [SavedNode("n1", "visiongraph:node:Foo", "visiongraph", saved_version=None)]
        findings = checker.check(saved)
        assert findings == [CompatibilityFinding("n1", "x", source_version=None)]

    def test_library_wide_warning_fires_once_per_graph(self):
        warnings = [CompatibilityWarning(version="0.0.14", component=None, message="lib-wide")]
        checker = CompatibilityChecker(_history_lookup({"visiongraph": warnings}))
        saved = [
            SavedNode("n1", "visiongraph:node:Foo", "visiongraph", "0.0.13"),
            SavedNode("n2", "visiongraph:node:Bar", "visiongraph", "0.0.13"),
        ]
        findings = checker.check(saved)
        # Exactly one library-wide finding, not one per node. node_id is None.
        lib_wide = [f for f in findings if f.node_id is None]
        assert lib_wide == [CompatibilityFinding(None, "lib-wide", source_version=None)]

    def test_library_wide_does_not_fire_if_all_nodes_current(self):
        warnings = [CompatibilityWarning(version="0.0.14", component=None, message="lib-wide")]
        checker = CompatibilityChecker(_history_lookup({"visiongraph": warnings}))
        saved = [SavedNode("n1", "visiongraph:node:Foo", "visiongraph", "0.0.14")]
        assert checker.check(saved) == []

    def test_unknown_library_yields_no_findings(self):
        checker = CompatibilityChecker(_history_lookup({}))
        saved = [SavedNode("n1", "ghost:node:Foo", "ghost", "0.0.1")]
        assert checker.check(saved) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_library/test_compatibility.py::TestCompatibilityChecker -m unit -v`
Expected: FAIL — `ImportError: cannot import name 'CompatibilityChecker'`.

- [ ] **Step 3: Write minimal implementation**

Append to `packages/haywire-core/src/haywire/core/library/compatibility.py`:

```python
from typing import Callable, Iterable


@dataclass(frozen=True)
class SavedNode:
    """The minimal facts the checker needs about one node read from a file."""

    node_id: str
    registry_key: str
    library_id: str
    saved_version: Optional[str]  # None for files predating the library.version field


@dataclass(frozen=True)
class CompatibilityFinding:
    """A resolved warning to apply. node_id=None means a library-wide finding."""

    node_id: Optional[str]
    message: str
    source_version: Optional[str]


# Yields the append-only CompatibilityWarning history for a given library id.
HistoryLookup = Callable[[str], list[CompatibilityWarning]]


def _component_registry_key(component: Any) -> Optional[str]:
    """Resolve a warning's component to a registry_key, or None for library-wide.

    Accepts either a class exposing ``class_identity.registry_key`` or a plain
    registry_key string (used in unit tests and equally valid for authors).
    """
    if component is None:
        return None
    if isinstance(component, str):
        return component
    identity = getattr(component, "class_identity", None)
    return getattr(identity, "registry_key", None)


def _is_older(saved_version: Optional[str], warning: CompatibilityWarning) -> bool:
    """True if the saved version is strictly below the warning's version.

    A missing saved version is treated as infinitely old (every warning fires).
    """
    if saved_version is None:
        return True
    try:
        return parse_semver(saved_version) < warning.version_tuple
    except SemverError:
        # A saved file with a junk version is treated as old, not crashed on.
        return True


class CompatibilityChecker:
    """Decides which Compatibility Warnings fire for a set of saved nodes.

    Pure logic, no UI and no graph mutation. ``history_lookup`` supplies a
    library's append-only warning list by id (in production, from the live
    LibraryRegistry; in tests, from a dict).
    """

    def __init__(self, history_lookup: HistoryLookup):
        self._history = history_lookup

    def check(self, saved_nodes: Iterable[SavedNode]) -> list[CompatibilityFinding]:
        saved_list = list(saved_nodes)
        findings: list[CompatibilityFinding] = []

        # Collect library ids present in the graph (preserve first-seen order).
        lib_ids: list[str] = []
        for node in saved_list:
            if node.library_id not in lib_ids:
                lib_ids.append(node.library_id)

        for lib_id in lib_ids:
            warnings = self._history(lib_id)
            if not warnings:
                continue
            nodes_for_lib = [n for n in saved_list if n.library_id == lib_id]

            for warning in warnings:
                target_key = _component_registry_key(warning.component)

                if target_key is None:
                    # Library-wide: one finding if ANY node is below the version.
                    if any(_is_older(n.saved_version, warning) for n in nodes_for_lib):
                        findings.append(
                            CompatibilityFinding(
                                node_id=None,
                                message=warning.message,
                                source_version=None,
                            )
                        )
                    continue

                # Node-specific: one finding per matched node below the version.
                for node in nodes_for_lib:
                    if node.registry_key == target_key and _is_older(node.saved_version, warning):
                        findings.append(
                            CompatibilityFinding(
                                node_id=node.node_id,
                                message=warning.message,
                                source_version=node.saved_version,
                            )
                        )

        return findings
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/test_library/test_compatibility.py -m unit -v`
Expected: PASS (all classes).

- [ ] **Step 5: Lint & type-check**

Run: `uv run ruff check packages/haywire-core/src/haywire/core/library/compatibility.py && uv run mypy packages/haywire-core/src/haywire/core/library/compatibility.py`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add packages/haywire-core/src/haywire/core/library/compatibility.py tests/core/test_library/test_compatibility.py
git commit -m "feat: CompatibilityChecker trigger logic (node + library-wide)"
```

---

## Task 3: `BaseLibrary.compatibility_warnings()` authoring hook

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/library/base.py`
- Test: `tests/core/test_library/test_compatibility.py:append`

- [ ] **Step 1: Write the failing test**

Append to `tests/core/test_library/test_compatibility.py`:

```python
@pytest.mark.unit
class TestBaseLibraryHook:
    def test_default_compatibility_warnings_is_empty(self):
        # A library that declares nothing returns an empty history.
        from haywire.core.library.base import BaseLibrary

        # BaseLibrary is abstract; build a minimal concrete subclass.
        class _Lib(BaseLibrary):
            def register_components(self):  # pragma: no cover - not exercised
                pass

            def validate(self) -> bool:  # pragma: no cover - not exercised
                return True

        # compatibility_warnings is a plain method with a default; callable on the class.
        assert _Lib.compatibility_warnings(object.__new__(_Lib)) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_library/test_compatibility.py::TestBaseLibraryHook -m unit -v`
Expected: FAIL — `AttributeError: ... has no attribute 'compatibility_warnings'`.

- [ ] **Step 3: Write minimal implementation**

In `packages/haywire-core/src/haywire/core/library/base.py`, add the import near the other imports and add the method to `BaseLibrary` (place it just after the `identity` property at line ~81).

Add import (top of file, with existing imports):

```python
from haywire.core.library.compatibility import CompatibilityWarning
```

Add method to `BaseLibrary`:

```python
def compatibility_warnings(self) -> list[CompatibilityWarning]:
    """Author-declared, APPEND-ONLY history of compatibility notices.

    Override in a library subclass to advise users when a graph saved by an
    older version of this library may not reflect a later behavioural change.
    Entries are NEVER removed or re-dated — a graph saved at any past version
    must still trigger the right historical entries. See ADR 0005.

    Example::

        def compatibility_warnings(self) -> list[CompatibilityWarning]:
            return [
                CompatibilityWarning(
                    version="0.0.14",                       # where the change landed
                    component=WebcamFrameInfoDisplayNode,   # or None for library-wide
                    message="The 'frame' inlet widget strategy became "
                            "author-declared; graphs saved before 0.0.14 may "
                            "hide the preview widget. Reset the node to "
                            "re-derive it from current code.",
                ),
            ]

    Returns an empty list by default (no warnings declared).
    """
    return []
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/test_library/test_compatibility.py::TestBaseLibraryHook -m unit -v`
Expected: PASS.

- [ ] **Step 5: Lint & type-check**

Run: `uv run ruff check packages/haywire-core/src/haywire/core/library/base.py && uv run mypy packages/haywire-core/src/haywire/core/library/base.py`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add packages/haywire-core/src/haywire/core/library/base.py tests/core/test_library/test_compatibility.py
git commit -m "feat: BaseLibrary.compatibility_warnings() authoring hook"
```

---

## Task 4: `NodeWarning` record + `NodeWrapperState.warnings`

**Files:**
- Create: `packages/haywire-core/src/haywire/core/node/node_warning.py`
- Modify: `packages/haywire-core/src/haywire/core/node/node_wrapper.py:30-105`
- Test: `tests/core/test_graph/test_node_warnings.py`

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_graph/test_node_warnings.py`:

```python
"""NodeWrapperState carries advisory warnings, separate from errors."""

import haywire.core.graph.editor  # noqa: F401  circular-import guard (CLAUDE.md)

import pytest

from haywire.core.node.node_warning import NodeWarning
from haywire.core.node.node_wrapper import NodeWrapperState


@pytest.mark.unit
class TestNodeWrapperStateWarnings:
    def test_new_state_has_no_warnings(self):
        state = NodeWrapperState()
        assert state.warnings == []
        assert state.has_warning() is False

    def test_add_warning_records_it(self):
        state = NodeWrapperState()
        w = NodeWarning(message="old graph", source_version="0.0.13", kind="compatibility")
        state.add_warning(w)
        assert state.warnings == [w]
        assert state.has_warning() is True

    def test_warnings_do_not_affect_validity(self):
        # A warning must NOT make a node invalid (advisory only).
        state = NodeWrapperState(
            is_registered=True,
            is_imported=True,
            is_instantiated=True,
            is_initialized=True,
            is_structural=True,
            has_test_passed=True,
        )
        assert state.is_valid() is True
        state.add_warning(NodeWarning("x", None, "compatibility"))
        assert state.is_valid() is True

    def test_clear_warnings_empties_the_list(self):
        state = NodeWrapperState()
        state.add_warning(NodeWarning("x", None, "compatibility"))
        state.clear_warnings()
        assert state.warnings == []
        assert state.has_warning() is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_graph/test_node_warnings.py -m unit -v`
Expected: FAIL — `ModuleNotFoundError: haywire.core.node.node_warning`.

- [ ] **Step 3a: Create the record**

Create `packages/haywire-core/src/haywire/core/node/node_warning.py`:

```python
"""Advisory warning record carried on a node's wrapper state.

Distinct from errors (which make a node invalid). A warning is informational;
the first writer is the Compatibility Warning feature (kind="compatibility").
See ADR 0005.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class NodeWarning:
    """One advisory notice attached to a node.

    Fields:
        message: Human-readable text shown in the badge tooltip / summary.
        source_version: For compatibility warnings, the library version the
            graph was saved with (None if the saved file predated the field).
        kind: Discriminator for the warning type. "compatibility" today;
            a "compatibility" warning implies the suggested remedy is the
            Reset Node action (re-derives the node from current code).
    """

    message: str
    source_version: Optional[str]
    kind: str = "compatibility"
```

- [ ] **Step 3b: Add the warnings list to `NodeWrapperState`**

In `packages/haywire-core/src/haywire/core/node/node_wrapper.py`, add the import near the top (with the other `from ..` / `from .` imports):

```python
from haywire.core.node.node_warning import NodeWarning
```

In the `NodeWrapperState` dataclass (starts at line 30), add the field after `test_execution_time_ns` (line 63) — note the `field(default_factory=list)` so each state gets its own list:

```python
    warnings: list[NodeWarning] = field(default_factory=list)
    """Advisory, non-fatal notices (e.g. compatibility warnings). Does NOT
    affect is_valid() — these are informational only. See ADR 0005."""
```

Ensure `field` is imported. Check the existing imports at the top of `node_wrapper.py`; if `field` is not already imported from `dataclasses`, change the dataclass import to include it (the file already uses `@dataclass`):

```python
from dataclasses import dataclass, field
```

Then add three methods to `NodeWrapperState` (after `_clear_errors`, ~line 105):

```python
    def add_warning(self, warning: NodeWarning) -> None:
        """Append an advisory warning."""
        self.warnings.append(warning)

    def has_warning(self) -> bool:
        """True if any advisory warning is present."""
        return bool(self.warnings)

    def clear_warnings(self) -> None:
        """Drop all advisory warnings (e.g. before a re-check)."""
        self.warnings.clear()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/test_graph/test_node_warnings.py -m unit -v`
Expected: PASS.

- [ ] **Step 5: Lint & type-check**

Run: `uv run ruff check packages/haywire-core/src/haywire/core/node/node_warning.py packages/haywire-core/src/haywire/core/node/node_wrapper.py && uv run mypy packages/haywire-core/src/haywire/core/node/node_warning.py packages/haywire-core/src/haywire/core/node/node_wrapper.py`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add packages/haywire-core/src/haywire/core/node/node_warning.py packages/haywire-core/src/haywire/core/node/node_wrapper.py tests/core/test_graph/test_node_warnings.py
git commit -m "feat: NodeWrapperState.warnings (advisory channel, parity with edges)"
```

---

## Task 5: Wire `CompatibilityChecker` into `load_from_dict`

This adds the one hook point. The graph builds `SavedNode` inputs from the just-loaded data, resolves each library's history from the live `LibraryRegistry`, runs the checker, and applies findings to `state.warnings`. Library-wide findings (node_id=None) are collected onto the graph for the summary (Task 7) via a transient attribute.

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/graph/base.py:911-999`
- Test: `tests/core/test_graph/test_compatibility_on_load.py`

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_graph/test_compatibility_on_load.py`:

```python
"""Integration: loading a graph applies Compatibility Warnings to node state."""

import haywire.core.graph.editor  # noqa: F401  circular-import guard (CLAUDE.md)

import pytest

from haywire.core.graph.base import BaseGraph
from haywire.core.graph.scheduler import SyncScheduler
from haywire.core.library.compatibility import CompatibilityWarning


@pytest.mark.integration
def test_load_applies_node_compatibility_warning(library_system, monkeypatch):
    reg = library_system.get_node_registry()
    disp_key = next(k for k in reg.list_names() if "WebcamFrameInfoDisplay" in k)

    # Author a warning on the visiongraph library, landing in a FUTURE version
    # relative to whatever the live library is, so a saved-below-version node fires.
    lib_registry = library_system.get_library_registry()
    visiongraph = lib_registry._libraries["visiongraph"]
    live_version = visiongraph.identity.version  # e.g. "0.0.16"

    # Pick a warning version strictly ABOVE the saved version we will fake below.
    warning = CompatibilityWarning(
        version="999.0.0",
        component=disp_key,  # registry_key string is accepted
        message="frame inlet widget strategy became author-declared",
    )
    monkeypatch.setattr(
        type(visiongraph), "compatibility_warnings", lambda self: [warning], raising=False
    )

    # Build a one-node graph, serialize, then force the saved library.version low.
    g1 = BaseGraph(graph_id="g1", name="g1", validation_scheduler=SyncScheduler())
    a = g1.create_node_wrapper(disp_key, position=(100, 100))
    data = g1.to_dict(include_data=False)
    # Stamp an OLD saved version on the node's library block.
    data["nodes"][a.node_id]["node_data"]["library"]["version"] = "0.0.1"

    g2 = BaseGraph(graph_id="g2", name="g2", validation_scheduler=SyncScheduler())
    assert g2.load_from_dict(data) is True

    state = g2.get_node_wrapper(a.node_id).state
    assert state.has_warning() is True
    assert any(
        w.kind == "compatibility" and "author-declared" in w.message for w in state.warnings
    )
    assert live_version  # sanity: live version was readable


@pytest.mark.integration
def test_load_does_not_warn_when_saved_version_current(library_system, monkeypatch):
    reg = library_system.get_node_registry()
    disp_key = next(k for k in reg.list_names() if "WebcamFrameInfoDisplay" in k)
    lib_registry = library_system.get_library_registry()
    visiongraph = lib_registry._libraries["visiongraph"]

    warning = CompatibilityWarning(version="0.0.2", component=disp_key, message="x")
    monkeypatch.setattr(
        type(visiongraph), "compatibility_warnings", lambda self: [warning], raising=False
    )

    g1 = BaseGraph(graph_id="g1", name="g1", validation_scheduler=SyncScheduler())
    a = g1.create_node_wrapper(disp_key, position=(100, 100))
    data = g1.to_dict(include_data=False)
    data["nodes"][a.node_id]["node_data"]["library"]["version"] = "9.9.9"  # newer than warning

    g2 = BaseGraph(graph_id="g2", name="g2", validation_scheduler=SyncScheduler())
    g2.load_from_dict(data)
    assert g2.get_node_wrapper(a.node_id).state.has_warning() is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_graph/test_compatibility_on_load.py -m integration -v`
Expected: FAIL — `state.has_warning()` is False (checker not wired yet).

- [ ] **Step 3: Write the implementation**

In `packages/haywire-core/src/haywire/core/graph/base.py`, add a private helper and call it from `load_from_dict`.

3a. Add the call inside `load_from_dict`, immediately after the `_housekeeping()` loop and before `return True` (currently lines 996-999):

```python
            for wrapper in self.node_wrappers.values():
                wrapper._housekeeping()

            # Apply author-declared Compatibility Warnings for nodes whose saved
            # library version predates a behavioural change. Advisory only — never
            # mutates node data. See ADR 0005.
            self._apply_compatibility_warnings(data)

            return True
```

3b. Add the helper method to the graph class (place it near `load_from_dict`, after line 1003):

```python
    # Holds library-wide compatibility findings (component=None) discovered on
    # the last load, for the editor's on-open summary. Reset each load.
    library_compatibility_findings: list[str] = []

    def _apply_compatibility_warnings(self, data: Dict[str, Any]) -> None:
        """Run the CompatibilityChecker over just-loaded nodes and apply findings.

        Reads each node's SAVED library version from ``data`` (not the live
        class), resolves each library's append-only warning history from the
        live LibraryRegistry, and writes NodeWarning records onto node state.
        Library-wide findings are stashed on ``library_compatibility_findings``
        for the editor summary. Best-effort: never raises into the load path.
        """
        from haywire.core.library.compatibility import (
            CompatibilityChecker,
            SavedNode,
        )
        from haywire.core.node.node_warning import NodeWarning

        try:
            from haywire.core.di.config import get_library_system

            lib_registry = get_library_system().get_library_registry()
        except Exception as exc:  # no library system (bare graph) — nothing to check
            logger.debug(f"Compatibility check skipped (no library system): {exc}")
            return

        def history_lookup(lib_id: str):
            lib = lib_registry._libraries.get(lib_id)
            if lib is None:
                return []
            try:
                return lib.compatibility_warnings()
            except Exception as exc:
                logger.warning(f"compatibility_warnings() failed for '{lib_id}': {exc}")
                return []

        # Build SavedNode inputs from the serialized data.
        saved_nodes: list[SavedNode] = []
        for node_id, wrapper_data in data.get("nodes", {}).items():
            node_data = wrapper_data.get("node_data", {})
            library_block = node_data.get("library", {})
            registry_key = wrapper_data.get("registry_key", "")
            saved_nodes.append(
                SavedNode(
                    node_id=node_id,
                    registry_key=registry_key,
                    library_id=library_block.get("id", ""),
                    saved_version=library_block.get("version"),
                )
            )

        checker = CompatibilityChecker(history_lookup)
        findings = checker.check(saved_nodes)

        self.library_compatibility_findings = []
        for finding in findings:
            if finding.node_id is None:
                self.library_compatibility_findings.append(finding.message)
                continue
            wrapper = self.node_wrappers.get(finding.node_id)
            if wrapper is not None:
                wrapper.state.add_warning(
                    NodeWarning(
                        message=finding.message,
                        source_version=finding.source_version,
                        kind="compatibility",
                    )
                )
```

Note: `Dict` and `Any` are already imported in `base.py` (used by `load_from_dict`); `logger` is already module-level. Confirm with `grep -n "^from typing\|^import logging\|logger = " packages/haywire-core/src/haywire/core/graph/base.py` before editing if unsure.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/test_graph/test_compatibility_on_load.py -m integration -v`
Expected: PASS (both tests).

- [ ] **Step 5: Lint & type-check**

Run: `uv run ruff check packages/haywire-core/src/haywire/core/graph/base.py && uv run mypy packages/haywire-core/src/haywire/core/graph/base.py`
Expected: no errors.

- [ ] **Step 6: Run the full core test suite for regressions**

Run: `uv run pytest tests/core -m "not integration" -q`
Expected: PASS (load path unchanged for graphs without warnings).

- [ ] **Step 7: Commit**

```bash
git add packages/haywire-core/src/haywire/core/graph/base.py tests/core/test_graph/test_compatibility_on_load.py
git commit -m "feat: run CompatibilityChecker on graph load, apply to node state"
```

---

## Task 6: Per-node warnings badge in the studio skin

Mirror the existing errors badge. The default skin already renders an errors button from `wrapper.state.get_errors()`; add a sibling warnings button from `wrapper.state.warnings`.

**Files:**
- Modify: `barn/haybale-studio/haybale_studio/skins/default_skin.py:31-101` (call site)
- Modify: `barn/haybale-studio/haybale_studio/skins/node_skin.py` (add `_render_warnings_button` on the base `NodeSkin`, alongside `_render_errors_button` at line 377, so `DefaultNodeSkin` and `ErrorNodeSkin` both inherit it)
- Test: `tests/graph_editor/test_warning_badge.py`

> Verified: `DefaultNodeSkin(NodeSkin)` (default_skin.py:20); `_render_errors_button` is defined on the base `NodeSkin` (node_skin.py:377) and inherited; the existing badge uses `ui.button(icon=hui.icon.warning, color="red")` (node_skin.py:390). Put `_render_warnings_button` next to it on `NodeSkin`.

- [ ] **Step 1: Write the failing test**

Create `tests/graph_editor/test_warning_badge.py`:

```python
"""The default skin exposes a render path for node warnings."""

import haywire.core.graph.editor  # noqa: F401  circular-import guard (CLAUDE.md)

import pytest

from haybale_studio.skins.default_skin import DefaultNodeSkin


@pytest.mark.unit
def test_skin_has_warnings_button_renderer():
    # The skin must provide a dedicated method to render the warnings badge,
    # parallel to the existing _render_errors_button.
    assert hasattr(DefaultNodeSkin, "_render_warnings_button")
    assert callable(DefaultNodeSkin._render_warnings_button)
```

Note: confirm the skin class name with `grep -n "class .*Skin" barn/haybale-studio/haybale_studio/skins/default_skin.py` and adjust the import/class in the test if it differs from `DefaultNodeSkin`.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/graph_editor/test_warning_badge.py -m unit -v`
Expected: FAIL — `AttributeError: ... no attribute '_render_warnings_button'`.

- [ ] **Step 3: Write the implementation**

In `barn/haybale-studio/haybale_studio/skins/default_skin.py`, inside `render` (after the existing errors block at lines 43-45), add the warnings block:

```python
            # Runtime errors indicator with popup
            runtime_errors = wrapper.state.get_errors()
            if runtime_errors:
                self._render_errors_button(runtime_errors, wrapper.node_id)

            # Advisory warnings indicator (e.g. compatibility warnings).
            if wrapper.state.has_warning():
                self._render_warnings_button(wrapper.state.warnings, wrapper.node_id)
```

Then add the method (model it on `_render_errors_button`; find that method's body with `grep -n "_render_errors_button" barn/haybale-studio/haybale_studio/skins/node_skin.py barn/haybale-studio/haybale_studio/skins/default_skin.py` and mirror its structure). A minimal correct implementation:

```python
    def _render_warnings_button(self, warnings, node_id: str) -> None:
        """Render a non-fatal warnings badge with a popup listing the messages.

        Advisory only — these never make a node invalid. For compatibility
        warnings, the suggested remedy is the Reset Node action (re-derives the
        node from current code; note it discards dynamically-created ports).
        """
        from nicegui import ui
        from haywire.ui import elements as hui

        btn = ui.button(icon=hui.icon.warning, color="amber").props("flat dense round")
        with btn:
            with ui.menu():
                with ui.column().classes("p-2 gap-1 max-w-sm"):
                    ui.label("Compatibility warnings").classes("text-sm font-bold")
                    for w in warnings:
                        ui.label(w.message).classes("text-xs hw-text-warning")
                    ui.label(
                        "Tip: 'Reset Node' re-derives this node from current code "
                        "(note: this discards any dynamically-added ports)."
                    ).classes("text-xs hw-text-dim mt-1")
```

Confirm `hui.icon.warning` exists with `grep -n "warning" packages/haywire-core/src/haywire/ui/themes/icons.py`; if the attribute differs, use the same icon reference `_render_errors_button` uses for its warning/error icon.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/graph_editor/test_warning_badge.py -m unit -v`
Expected: PASS.

- [ ] **Step 5: Lint & type-check**

Run: `uv run ruff check barn/haybale-studio/haybale_studio/skins/default_skin.py && uv run mypy barn/haybale-studio/haybale_studio/skins/default_skin.py`
Expected: no errors. (If mypy flags the untyped `warnings` param, annotate it `list["NodeWarning"]` with a `TYPE_CHECKING` import of `NodeWarning`.)

- [ ] **Step 6: Commit**

```bash
git add barn/haybale-studio/haybale_studio/skins/default_skin.py tests/graph_editor/test_warning_badge.py
git commit -m "feat: per-node compatibility warnings badge in default skin"
```

---

## Task 7: On-open summary in the graph editor

When the canvas first syncs a loaded graph, show a single non-blocking notification summarising compatibility findings: count of affected nodes plus any library-wide messages. The data is already on the graph (`library_compatibility_findings`) and on node state (per-node warnings).

**Files:**
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/visual_layer.py:148-164`
- Test: `tests/graph_editor/test_compatibility_summary.py`

- [ ] **Step 1: Write the failing test**

Create `tests/graph_editor/test_compatibility_summary.py`:

```python
"""The visual layer can summarise compatibility findings for the on-open notice."""

import haywire.core.graph.editor  # noqa: F401  circular-import guard (CLAUDE.md)

import pytest

from haybale_graph_editor.editors.graph_canvas.handlers.visual_layer import (
    summarize_compatibility,
)
from haywire.core.node.node_warning import NodeWarning


@pytest.mark.unit
class TestSummarizeCompatibility:
    def test_none_when_no_findings(self):
        assert summarize_compatibility(node_warning_count=0, library_messages=[]) is None

    def test_counts_affected_nodes(self):
        msg = summarize_compatibility(node_warning_count=3, library_messages=[])
        assert "3" in msg
        assert "node" in msg.lower()

    def test_includes_library_wide_messages(self):
        msg = summarize_compatibility(
            node_warning_count=0, library_messages=["FRAME default changed"]
        )
        assert "FRAME default changed" in msg

    def test_combines_both(self):
        msg = summarize_compatibility(
            node_warning_count=2, library_messages=["lib change"]
        )
        assert "2" in msg and "lib change" in msg
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/graph_editor/test_compatibility_summary.py -m unit -v`
Expected: FAIL — `ImportError: cannot import name 'summarize_compatibility'`.

- [ ] **Step 3: Write the implementation**

3a. Add a module-level pure function to `visual_layer.py` (top level, after imports):

```python
def summarize_compatibility(node_warning_count: int, library_messages: list[str]) -> str | None:
    """Build the on-open compatibility summary text, or None if nothing to report.

    Pure/UI-free so it is unit-testable. Library-wide messages are listed
    verbatim; per-node warnings are summarised as a count (the badges carry
    the detail per node).
    """
    if node_warning_count == 0 and not library_messages:
        return None
    parts: list[str] = []
    if node_warning_count:
        noun = "node" if node_warning_count == 1 else "nodes"
        parts.append(
            f"{node_warning_count} {noun} were saved with an older library "
            f"version and may not reflect later changes (see the warning badges)."
        )
    parts.extend(library_messages)
    return " ".join(parts)
```

3b. Emit the notice once at the end of `sync_with_graph` (the synthetic full-add at lines 148-164). After `self.on_validated(synthetic_result)` succeeds, add:

```python
            self.on_validated(synthetic_result)
            logger.info("✅ Initial sync completed via validation pipeline")

            # One-time compatibility summary for this load.
            node_warning_count = sum(
                1
                for w in self.graph.node_wrappers.values()
                if w.state.has_warning()
            )
            library_messages = list(
                getattr(self.graph, "library_compatibility_findings", [])
            )
            summary = summarize_compatibility(node_warning_count, library_messages)
            if summary:
                from nicegui import ui

                ui.notify(summary, type="warning", multi_line=True, timeout=0, close_button=True)
```

Note: `ui.notify` with `timeout=0` stays until dismissed — appropriate for an advisory the user should consciously see. Confirm `logger` and the `ValidationResult`/`ChangeReason` imports already exist in this file (they do — used by `sync_with_graph`).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/graph_editor/test_compatibility_summary.py -m unit -v`
Expected: PASS.

- [ ] **Step 5: Lint & type-check**

Run: `uv run ruff check barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/visual_layer.py && uv run mypy barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/visual_layer.py`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/visual_layer.py tests/graph_editor/test_compatibility_summary.py
git commit -m "feat: on-open compatibility summary notice in graph editor"
```

---

## Task 8: End-to-end verification with a real authored warning

Prove the whole chain with the actual motivating node, declaring a real warning on the visiongraph library and confirming a node saved below the version gets a warning, while a current one does not. This reuses the integration test file from Task 5 (extend, don't duplicate).

**Files:**
- Modify: `tests/core/test_graph/test_compatibility_on_load.py:append`

- [ ] **Step 1: Write the failing test**

Append to `tests/core/test_graph/test_compatibility_on_load.py`:

```python
@pytest.mark.integration
def test_library_wide_finding_lands_on_graph(library_system, monkeypatch):
    reg = library_system.get_node_registry()
    disp_key = next(k for k in reg.list_names() if "WebcamFrameInfoDisplay" in k)
    lib_registry = library_system.get_library_registry()
    visiongraph = lib_registry._libraries["visiongraph"]

    warning = CompatibilityWarning(
        version="999.0.0", component=None, message="A library-wide convention changed."
    )
    monkeypatch.setattr(
        type(visiongraph), "compatibility_warnings", lambda self: [warning], raising=False
    )

    g1 = BaseGraph(graph_id="g1", name="g1", validation_scheduler=SyncScheduler())
    a = g1.create_node_wrapper(disp_key, position=(100, 100))
    data = g1.to_dict(include_data=False)
    data["nodes"][a.node_id]["node_data"]["library"]["version"] = "0.0.1"

    g2 = BaseGraph(graph_id="g2", name="g2", validation_scheduler=SyncScheduler())
    g2.load_from_dict(data)

    # Library-wide finding stashed on the graph; node itself has no per-node badge.
    assert "A library-wide convention changed." in g2.library_compatibility_findings
    assert g2.get_node_wrapper(a.node_id).state.has_warning() is False
```

- [ ] **Step 2: Run test to verify it fails or passes**

Run: `uv run pytest tests/core/test_graph/test_compatibility_on_load.py::test_library_wide_finding_lands_on_graph -m integration -v`
Expected: PASS (Task 5 already implements library-wide stashing). If it FAILS, the bug is in Task 5's library-wide branch — fix there, not here.

- [ ] **Step 3: Commit**

```bash
git add tests/core/test_graph/test_compatibility_on_load.py
git commit -m "test: end-to-end compatibility warning on real visiongraph load"
```

---

## Task 9: Full quality gate

- [ ] **Step 1: Run the full quality suite**

Run:
```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-TEST_A/haybale_test_a/
uv run pytest -m "not integration" -q
uv run pytest -m integration -q
```
Expected: all pass. If `ruff format --check` reports drift, run `uv run ruff format .` and re-commit.

- [ ] **Step 2: Manual smoke test (optional but recommended)**

Run: `uv run haywire`, open a graph saved by an older library (e.g. `graphs/webcam.haywire` — provided a warning is declared on visiongraph). Confirm: the on-open notice appears, affected nodes show the amber warning badge, and pressing **Reset Node** clears the badge (re-derives from current code). Per CLAUDE.md, do not commit changes to transient graph files.

- [ ] **Step 3: Commit any formatting fixes**

```bash
git add -A
git commit -m "chore: formatting + quality gate for compatibility warnings"
```

---

## Task 10: Land docs — ADR, glossary, authoring guide (AFTER the feature works)

Per the user's instruction, documentation lands last, once the feature is verified.

**Files:**
- Create: `docs/adr/0005-compatibility-warnings.md`
- Modify: `docs/reference/glossary.md`
- Modify: the library authoring canon (find with `grep -rl "compatibility_warnings\|BaseLibrary" docs/` and the library-canon doc referenced in `CLAUDE.md`: `docs/components/.../library-canon.md` or `docs/haybale/library-canon.md`).

- [ ] **Step 1: Write the ADR**

Create `docs/adr/0005-compatibility-warnings.md`:

```markdown
# Compatibility Warnings are advisory-only, append-only, and node-keyed

**Context.** Graphs are deserialized purely from the saved spec; node `init()`
is not re-run on load (`NodeWrapper._initialize` calls `_initialize_from_dict`,
not `init()`). So any code-defined port attribute absent from an older file
silently reverts to its dataclass default — e.g. an inlet's `show_widget`
strategy reverting from `WHEN_LINKED` to `NOT_LINKED`, hiding its widget.

**Decision.** We surface, but never auto-fix, this drift. A library author
declares an APPEND-ONLY history of `CompatibilityWarning` entries on its
`BaseLibrary`; on load, a stateless `CompatibilityChecker` compares each node's
SAVED `library.version` against each warning's explicit `version` and, on
`saved < version`, attaches an advisory `NodeWarning` (per-node badge) or a
graph-level library-wide notice (on-open summary). The existing Reset Node
action (full `init()` rebuild) is the suggested — not promised — remedy.

**Why not auto-migrate.** Ports can be created dynamically, outside `init()`.
Re-running `init()` on load to "correct" attributes would drop those dynamic
ports and their wiring — data loss. And a stranded value may be exactly what
the user intends. There is no sound automatic reconciliation, so the feature
is strictly read-only.

**Why explicit, append-only versions.** The version a change landed in is a
historical fact; deriving it from the library's current version would re-date
every entry on each release and break the `saved < version` trigger for users
who saved in between. Entries are therefore never removed or re-dated.

**Consequences.** Re-saving an old graph silences the warning by advancing the
saved version without fixing the underlying value — accepted: the warning's
contract ends at *surfacing*; fixing is the user's judgement (Reset, or leave
as-is). Nodes gained a `warnings` channel on `NodeWrapperState`, closing a
prior asymmetry with `EdgeWrapperState`.
```

- [ ] **Step 2: Update the glossary**

In `docs/reference/glossary.md`, under the `## Library & Plugin System` section (after the `entry_point` / `Post-install requirements` rows), add:

```markdown
| **Compatibility Warning** | An advisory, author-declared notice that a graph saved by an older library version may not reflect a later behavioural change. Declared as an append-only history via `BaseLibrary.compatibility_warnings()`; each entry is a `CompatibilityWarning(version, component, message)`. On load, the `CompatibilityChecker` fires it when a node's saved `library.version` is *below* the entry's `version`. Read-only — never mutates saved data; the suggested remedy is the Reset Node action. See [ADR-0005](../adr/0005-compatibility-warnings.md). | migration (implies data transformation — this never transforms), changelog |
| **CompatibilityChecker** | The stateless service run once inside `Graph.load_from_dict` that resolves which Compatibility Warnings fire for a loaded graph and writes `NodeWarning` records onto node state. Pure logic; takes a library-history lookup, returns findings. | — |
| **NodeWarning** | An advisory record on `NodeWrapperState.warnings` (distinct from errors; does not affect `is_valid()`). First writer is the Compatibility Warning feature (`kind="compatibility"`). | node error (errors invalidate; warnings advise) |
```

- [ ] **Step 3: Update the library authoring guide**

Find the library authoring canon: `grep -rln "register_components\|@library" docs/`. In that file, add a short "Compatibility Warnings" subsection documenting `compatibility_warnings()` with the example from Task 3's docstring, and the rules: explicit semver `version`, append-only (never remove/re-date), `component` is a node class or `None`, advisory-only.

- [ ] **Step 4: Preview the docs site (optional)**

Run: `uv run mkdocs serve` and confirm the new ADR, glossary rows, and authoring subsection render and cross-link correctly. Stop the server when done.

- [ ] **Step 5: Commit**

```bash
git add docs/adr/0005-compatibility-warnings.md docs/reference/glossary.md docs/
git commit -m "docs: ADR 0005, glossary, and authoring guide for compatibility warnings"
```

---

## Self-Review notes (for the implementer)

- **Spec coverage:** Q1 advisory-only (Task 5 read-only + ADR), Q4 Python authoring (Task 3), Q5 trigger `saved < version` + missing=infinitely-old (Task 2), Q6 semver validation loud/early (Task 1), Q10 `component` via class_identity/registry_key + `None` (Task 2), Q11 append-only (documented in Task 3 docstring + ADR), Q12 badge + summary (Tasks 6, 7), Q15 Reset suggested-not-promised (Task 6 tooltip + ADR), Q16 `NodeWrapperState.warnings` separate from errors (Task 4), Q17 structured `NodeWarning` (Task 4), Q18 `CompatibilityChecker` unit at the `load_from_dict` hook (Tasks 2, 5). Docs last (Task 10) per the user's instruction.
- **Type consistency:** `CompatibilityWarning(version, component, message)`, `SavedNode(node_id, registry_key, library_id, saved_version)`, `CompatibilityFinding(node_id, message, source_version)`, `NodeWarning(message, source_version, kind)` are used identically across Tasks 1–8.
- **Known follow-ups (out of scope):** unify node/edge warning shapes; type/adapter/widget structural matching; guard Reset against dynamic-port data loss; `min_supported_version` floor to collapse ancient-file noise.
- **Verify-before-edit reminders:** confirm the skin class name (Task 6), `hui.icon.warning` (Task 6), and that `field`/`Dict`/`Any`/`logger` imports exist before editing (Tasks 4, 5).
```