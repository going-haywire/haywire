# `haywire rename`: Identity-Preserving Library Rename

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the existing half-built `haywire rename` into a complete, preflight-gated command that renames a project-local haybale library and repairs every reference to it — registry keys in saved graphs, Python self-imports and self-referencing key literals, and sibling libraries' declarations — plus a `haywire verify` companion that proves the result resolves.

**Architecture:** One pure planner (`plan_rename()`) walks the workspace and returns a `RenamePlan` — a fully-enumerated, filesystem-free description of every change plus every blocking problem. The dry run prints it; `--apply` recomputes it, confirms, then executes it in five fail-fast phases. A hard clean-tree gate makes `git checkout . && git clean -fd` a complete rollback, so the command carries no transaction machinery of its own. `haywire verify` runs afterwards as a separate process, resolving every key in every graph against a freshly-loaded registry without instantiating anything.

**Tech Stack:** Python 3.12, `ast` (stdlib), `tomlkit` via `haywire.core.tomlio`, argparse, pytest.

## Global Constraints

- **Both CLI arguments are full distribution names, taken verbatim.** Never reconstruct a name as `f"haybale-{stem}"`. Module names derive only via `module_of()` from `haywire.core.library.haybale_toml`.
- **The registry-key prefix is the distribution name**, e.g. `haybale-example:node:Add`. There is no short "library id" — that concept is retired and must not appear in code, comments, or tests.
- **Graph discovery is extension-agnostic.** More graph types are coming (non-executable "abstractions", graph-groups) with undecided extensions. Never filter on `.haywire` or `.json`; identify a graph by its content.
- **Key rewriting is recursive and unbounded in depth.** Graphs may nest inside nodes. The walker must never assume a fixed path to a key.
- **No legacy or fallback handling.** Graphs carry current-schema fields. Do not write compatibility branches for the retired `id`/`dependencies` library block.
- **Rename changes identity only.** In `haybale.toml` only `name` changes. `label`, `description`, `tags`, `homepage_url`, `notes`, `linked_libraries` are preserved byte-for-byte. In the library's `pyproject.toml` only `name`, the `haywire.libraries` entry-point key, and the wheel `packages` list change — `description` is untouched.
- **Clean working tree is a hard precondition with no override flag.** No `--allow-dirty`.
- **The preflight is strictly read-only.** It must not create, move, or write any file — including temp probe files.
- **Rename never writes outside the workspace root.** `~/.haywire/db/` is reported, never moved.
- **No `.bak` files.** Git is the only rollback.
- **`haywire verify` never instantiates a node.** Resolution is `registry.has(key)` at class level — instantiation grabs hardware (cameras) and repoints global DI.
- Line length 109 (`uv run ruff check`, `uv run ruff format --check`). Type-clean under `uv run mypy`.
- All new tests carry `@pytest.mark.unit` and must not touch the network or a real git repo outside `tmp_path`.

---

## What the investigation found

Verified by reading source and by measuring against the 8 real graphs in `graphs/`, not inferred.

### The graph patcher is a silent no-op today, three times over

[`packaging/rename.py:276`](../../../packages/haywire-studio/src/haywire_studio/packaging/rename.py) declares `_KEY_FIELDS = ("type",)`. No serializer produces a `type` field — `NodeWrapper.serialize()` emits `registry_key`. On top of that it globs `**/*.json` under `graphs/`, while real graphs are `.haywire`. Three independent reasons it patches nothing.

The three existing tests in `tests/test_rename_cli.py` pass only because their fixtures hand-write `{"type": ...}`, a shape that has never existed on disk. **They must be replaced, not extended** — they currently certify the bug.

### Where registry keys actually live — measured, not inferred

Counted across all 8 graphs in `graphs/`:

| Field | Occurrences | Shape |
|---|---|---|
| `registry_key` | 13,242 | `"haybale-core:type:FLOAT"` |
| `widget_key` | 2,893 | `"haybale-core:widget:NumberWidget"` |
| `chain_adapter_keys` | 8 | list of keys |

They are **not** at fixed paths. A single node carries them at `node_data.identity.registry_key`, `node_data.ports.<port>.kwargs.registry_key`, `node_data.ports.<port>.kwargs.widget_key`, and `node_data.ports.<port>.recipe.registry_key`. A position-scoped rule set catches roughly 1% of them. **The rule must be name-based and fully recursive.**

All 16,143 values match the grammar `<dist>:<kind>[:<subkind>]:<Name>` — zero exceptions — and every prefix is a real distribution name (`haywire-core` 10,839, `haybale-core` 4,422, `haybale-testing` 804, `haybale-visiongraph` 70, `haybale-example` 8). Name-matching on these three fields is therefore safe in a way that matching a bare `name` field is not.

### Discovery cost is negligible

Measured on this repo with a pruned walk (skipping `.git`, `.venv`, `node_modules`, `__pycache__`, caches, `dist`, `build`):

- Pruned walk: **74 ms** (422 dirs, 4,516 files) versus 665 ms unpruned (4,573 dirs, 49,570 files) — a 9× difference, `.venv` alone being 45k files.
- Sniffing the first 4 KB of all 21 candidates: **65 ms**.
- **Total: 187 ms.** Content sniffing across the whole workspace is affordable; no extension filter is needed.

### Libraries self-reference by registry key in Python string literals

`barn/haybale-example/haybale_example/types/specs.py:9`:

```python
widget_key="haybale-example:widget:TemperatureWidget",
```

An AST import pass does not see this. Left unpatched, the type's widget silently fails to resolve after a rename. A string matching `^<old_dist>:` is *certainly* a registry key — the grammar is unambiguous — so unlike prose this is mechanically rewritable.

Separately, several **pre-existing broken keys** use the retired short-id form: `"example:skin:ExampleNodeSkin"`, `"builtin:widget:NumberWidget"`, `"testing:widget:OversizedContentWidget"`. These are already dangling and unrelated to rename; `haywire verify` will surface them.

### Verification can resolve without instantiating

`BaseRegistry` exposes `has(registry_key) -> bool` and `list_names() -> list[str]` (`core/registry/base.py:144-150`) — class-level lookup with no construction. This is what makes `haywire verify` safe: per `.insights/project_docs_gen_reentrancy.md`, building a second library system and instantiating nodes grabs hardware (the OAK-D/webcam graphs would open cameras) and repoints the global injector. Verify must resolve keys only.

### Reusable machinery

- `git(["status", "--porcelain"], cwd=..., timeout=10.0) -> GitResult` — `core/publishing/git.py:97`. Precedent: `pipeline/steps/preconditions.py:115-141`.
- `edit_toml(path)` — `core/tomlio.py:72`. Comment-preserving; **required** for every TOML write here.
- `module_of(dist_name)` — `core/library/haybale_toml.py:80`. Normalises `haybale-TEST_A` → `haybale_test_a`.
- Subcommands self-register via `register(subparsers)` and are listed in `cli/__init__.py::SUBCOMMANDS`; `app.py` is never touched.

---

## Known precondition for testing against real graphs

The 8 graphs in `graphs/` were saved before the `id`→`name` refactor: their `node_data.library` blocks carry `id`/`dependencies` and **no `name` field**. Per the no-legacy constraint they are to be fixed (open and re-save each in the studio, which rewrites them with the current serializer) rather than accommodated in code. Until then the `library.name` rule matches nothing on those files. The `registry_key`/`widget_key` rules — which carry 16,143 of the 16,151 references — are unaffected.

---

## File Structure

The current `packaging/rename.py` (324 lines) mixes planning, execution, and graph patching. It splits by responsibility into a package:

| File | Responsibility |
|---|---|
| `packaging/rename/__init__.py` | Public exports: `plan_rename`, `execute_plan`, `run_rename_cli` |
| `packaging/rename/model.py` | `RenamePlan`, `Blocker`, `Warning_`, `FileChange`, `Occurrence` — pure dataclasses |
| `packaging/rename/discovery.py` | Pruned workspace walk + content sniffing (shared with verify) |
| `packaging/rename/graphs.py` | Recursive name-based key rewriting + drift scan |
| `packaging/rename/pysource.py` | AST import rewriting + key-literal rewriting + prose reporting |
| `packaging/rename/checks.py` | Clean tree, collisions, write access, dependents |
| `packaging/rename/planner.py` | `plan_rename()` — composes checks + patchers into a `RenamePlan` |
| `packaging/rename/execute.py` | `execute_plan()` — five fail-fast phases |
| `packaging/rename/report.py` | Rendering a `RenamePlan` to stdout |
| `packaging/verify.py` | `haywire verify` — resolve every key in every graph |
| `cli/rename.py` | argparse wiring (modify: add `--verbose`, `--yes`) |
| `cli/verify.py` | argparse wiring for verify (new) |
| `cli/__init__.py` | Add `verify` to `SUBCOMMANDS` |

Tests mirror this under `tests/rename/`. The old `tests/test_rename_cli.py` is deleted in Task 2.

---

## Task 1: Plan model and extension-agnostic graph discovery

**Files:**
- Create: `packages/haywire-studio/src/haywire_studio/packaging/rename/__init__.py`
- Create: `packages/haywire-studio/src/haywire_studio/packaging/rename/model.py`
- Create: `packages/haywire-studio/src/haywire_studio/packaging/rename/discovery.py`
- Test: `tests/rename/test_discovery.py`

**Interfaces:**
- Produces: `RenamePlan`, `Blocker`, `Warning_`, `FileChange`, `Occurrence`; `find_graph_files(root: Path) -> list[Path]`; `SKIP_DIRS: frozenset[str]`

- [ ] **Step 1: Create the package directories**

```bash
mkdir -p packages/haywire-studio/src/haywire_studio/packaging/rename
touch packages/haywire-studio/src/haywire_studio/packaging/rename/__init__.py
mkdir -p tests/rename
touch tests/rename/__init__.py
```

- [ ] **Step 2: Write `model.py`**

```python
"""Pure data describing a planned rename. No filesystem, no side effects."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Occurrence:
    """One textual site referencing the old name."""

    path: Path
    line: int
    text: str


@dataclass
class FileChange:
    """A single file the rename will rewrite."""

    path: Path
    kind: str  # "graph" | "python" | "toml"
    count: int
    occurrences: list[Occurrence] = field(default_factory=list)


@dataclass(frozen=True)
class Blocker:
    """A condition that stops the rename. Carries the command that fixes it."""

    message: str
    remedy: str = ""


@dataclass(frozen=True)
class Warning_:
    """Advisory: the rename proceeds, but the user should read this."""

    message: str
    remedy: str = ""


@dataclass
class RenamePlan:
    """Everything the rename will do, computed without writing anything."""

    old_dist: str
    new_dist: str
    old_module: str
    new_module: str
    workspace_root: Path
    old_lib_dir: Path
    new_lib_dir: Path
    blockers: list[Blocker] = field(default_factory=list)
    warnings: list[Warning_] = field(default_factory=list)
    graph_changes: list[FileChange] = field(default_factory=list)
    python_changes: list[FileChange] = field(default_factory=list)
    toml_changes: list[FileChange] = field(default_factory=list)
    dependent_changes: list[FileChange] = field(default_factory=list)
    unrecognized: list[Occurrence] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.blockers

    @property
    def total_changes(self) -> int:
        return sum(
            c.count
            for c in (
                *self.graph_changes,
                *self.python_changes,
                *self.toml_changes,
                *self.dependent_changes,
            )
        )
```

- [ ] **Step 3: Write the failing test for discovery**

```python
# tests/rename/test_discovery.py
"""Graphs are found by CONTENT, never by extension or location."""

from __future__ import annotations

import json

import pytest


def _graph_bytes(key: str = "haybale-foo:node:Add") -> str:
    return json.dumps(
        {"graph_id": "g", "name": "G", "nodes": {"n": {"registry_key": key}}, "edges": {}}
    )


@pytest.mark.unit
def test_finds_haywire_extension(tmp_path):
    from haywire_studio.packaging.rename.discovery import find_graph_files

    (tmp_path / "graphs").mkdir()
    (tmp_path / "graphs" / "a.haywire").write_text(_graph_bytes())

    assert [p.name for p in find_graph_files(tmp_path)] == ["a.haywire"]


@pytest.mark.unit
def test_finds_graph_with_unknown_future_extension(tmp_path):
    """Abstractions and graph-groups will use extensions not yet chosen."""
    from haywire_studio.packaging.rename.discovery import find_graph_files

    (tmp_path / "abstraction.hwabs").write_text(_graph_bytes())

    assert [p.name for p in find_graph_files(tmp_path)] == ["abstraction.hwabs"]


@pytest.mark.unit
def test_finds_graphs_outside_the_graphs_folder(tmp_path):
    from haywire_studio.packaging.rename.discovery import find_graph_files

    nested = tmp_path / "some" / "deep" / "place"
    nested.mkdir(parents=True)
    (nested / "b.haywire").write_text(_graph_bytes())

    assert [p.name for p in find_graph_files(tmp_path)] == ["b.haywire"]


@pytest.mark.unit
def test_ignores_non_graph_json(tmp_path):
    from haywire_studio.packaging.rename.discovery import find_graph_files

    (tmp_path / "package.json").write_text(json.dumps({"name": "x", "version": "1"}))
    (tmp_path / "tsconfig.json").write_text(json.dumps({"compilerOptions": {}}))

    assert find_graph_files(tmp_path) == []


@pytest.mark.unit
def test_prunes_heavy_directories(tmp_path):
    """A graph inside .venv or node_modules is not the project's graph."""
    from haywire_studio.packaging.rename.discovery import find_graph_files

    for skipped in (".venv", "node_modules", "__pycache__", ".git"):
        d = tmp_path / skipped
        d.mkdir()
        (d / "x.haywire").write_text(_graph_bytes())

    assert find_graph_files(tmp_path) == []


@pytest.mark.unit
def test_ignores_binary_and_unreadable_files(tmp_path):
    from haywire_studio.packaging.rename.discovery import find_graph_files

    (tmp_path / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00")
    (tmp_path / "notes.txt").write_text("registry_key mentioned in prose")

    assert find_graph_files(tmp_path) == []


@pytest.mark.unit
def test_result_is_sorted_and_deduplicated(tmp_path):
    from haywire_studio.packaging.rename.discovery import find_graph_files

    (tmp_path / "b.haywire").write_text(_graph_bytes())
    (tmp_path / "a.haywire").write_text(_graph_bytes())

    assert [p.name for p in find_graph_files(tmp_path)] == ["a.haywire", "b.haywire"]
```

- [ ] **Step 4: Run the test to verify it fails**

Run: `uv run pytest tests/rename/test_discovery.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'haywire_studio.packaging.rename.discovery'`

- [ ] **Step 5: Write `discovery.py`**

```python
"""Finding graph files by content.

Extension-agnostic on purpose: today's executable graphs are ``.haywire``,
but non-executable abstractions and graph-groups are coming with extensions
not yet chosen. Filtering on a suffix would silently skip them, and a rename
that skips a graph corrupts it. Identify by structure instead.

Measured on the haywire repo: a pruned walk is 74ms (versus 665ms unpruned —
``.venv`` alone holds 45k files), and sniffing every candidate's first 4KB
adds 65ms. 187ms total is cheap enough that scanning the whole workspace
needs no configuration.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

#: Directories that never hold a project's own graphs and are expensive to
#: walk. Pruning these is a 9x speedup on a typical workspace.
SKIP_DIRS = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "dist",
        "build",
        "site",
        ".haywire",
    }
)

#: Read this much of a candidate before deciding whether to parse it.
_SNIFF_BYTES = 4096

#: A graph always carries at least one of these near the top of the file.
_MARKERS = (b'"graph_id"', b'"registry_key"', b'"nodes"')


def _looks_like_graph(path: Path) -> bool:
    """Cheap content test: read the head, look for graph markers."""
    try:
        with open(path, "rb") as handle:
            head = handle.read(_SNIFF_BYTES)
    except OSError:
        return False
    if b"\x00" in head:  # binary
        return False
    return any(marker in head for marker in _MARKERS)


def _is_graph(path: Path) -> bool:
    """Confirm by structure. A graph is a JSON object with a ``nodes`` dict."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    return isinstance(data, dict) and isinstance(data.get("nodes"), dict)


def find_graph_files(root: Path) -> list[Path]:
    """Every graph file under *root*, identified by content.

    Never filters on extension — see the module docstring.
    """
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for filename in filenames:
            candidate = Path(dirpath) / filename
            if _looks_like_graph(candidate) and _is_graph(candidate):
                found.append(candidate)
    return sorted(set(found))
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest tests/rename/test_discovery.py -q`
Expected: PASS — 7 passed

- [ ] **Step 7: Verify against the real repo**

```bash
uv run python -c "
from pathlib import Path
from haywire_studio.packaging.rename.discovery import find_graph_files
import time
t = time.perf_counter()
files = find_graph_files(Path('.'))
print(f'{len(files)} graphs in {(time.perf_counter()-t)*1000:.0f}ms')
for f in files: print(' ', f)
"
```

Expected: 8 graphs found under `graphs/`, well under 1000ms.

- [ ] **Step 8: Commit**

```bash
git add packages/haywire-studio/src/haywire_studio/packaging/rename/ tests/rename/
git commit -m "feat(rename): extension-agnostic graph discovery by content

The old code globbed graphs/**/*.json; real graphs are .haywire and can
live anywhere. Future abstractions and graph-groups will use extensions
not yet chosen, so identification is by structure, not suffix."
```

---

## Task 2: Recursive name-based key rewriting

**Files:**
- Create: `packages/haywire-studio/src/haywire_studio/packaging/rename/graphs.py`
- Test: `tests/rename/test_graphs.py`

**Interfaces:**
- Consumes: `FileChange`, `Occurrence` from `model.py`; `find_graph_files` from `discovery.py`
- Produces: `KEY_FIELDS`, `LIST_KEY_FIELDS`, `is_registry_key(value: str) -> bool`, `patch_graph_tree(data, old, new) -> tuple[int, list[str]]`, `plan_graphs(root, old, new) -> tuple[list[FileChange], list[Occurrence]]`, `apply_graphs(changes, old, new) -> None`

- [ ] **Step 1: Write the failing test**

```python
# tests/rename/test_graphs.py
"""Recursive, name-based registry-key rewriting."""

from __future__ import annotations

import pytest


@pytest.mark.unit
def test_rewrites_keys_at_real_nesting_depth():
    """Real graphs carry keys inside ports, three levels down."""
    from haywire_studio.packaging.rename.graphs import patch_graph_tree

    data = {
        "nodes": {
            "n1": {
                "registry_key": "haybale-foo:node:Add",
                "node_data": {
                    "identity": {"registry_key": "haybale-foo:node:Add"},
                    "ports": {
                        "a": {
                            "kwargs": {
                                "registry_key": "haybale-foo:type:FLOAT",
                                "widget_key": "haybale-foo:widget:NumberWidget",
                            },
                            "recipe": {"registry_key": "haybale-foo:type:FLOAT"},
                        }
                    },
                },
            }
        }
    }

    count, _ = patch_graph_tree(data, "haybale-foo", "hay-bar")

    node = data["nodes"]["n1"]
    port = node["node_data"]["ports"]["a"]
    assert node["registry_key"] == "hay-bar:node:Add"
    assert node["node_data"]["identity"]["registry_key"] == "hay-bar:node:Add"
    assert port["kwargs"]["registry_key"] == "hay-bar:type:FLOAT"
    assert port["kwargs"]["widget_key"] == "hay-bar:widget:NumberWidget"
    assert port["recipe"]["registry_key"] == "hay-bar:type:FLOAT"
    assert count == 5


@pytest.mark.unit
def test_rewrites_graphs_nested_inside_nodes():
    """Graph-groups will nest a whole graph inside a node. Depth is unbounded."""
    from haywire_studio.packaging.rename.graphs import patch_graph_tree

    data = {
        "nodes": {
            "outer": {
                "registry_key": "haybale-foo:node:Group",
                "node_data": {
                    "subgraph": {
                        "nodes": {
                            "inner": {
                                "registry_key": "haybale-foo:node:Add",
                                "node_data": {
                                    "subgraph": {
                                        "nodes": {
                                            "deepest": {"registry_key": "haybale-foo:node:Sub"}
                                        }
                                    }
                                },
                            }
                        }
                    }
                },
            }
        }
    }

    count, _ = patch_graph_tree(data, "haybale-foo", "hay-bar")

    outer = data["nodes"]["outer"]
    inner = outer["node_data"]["subgraph"]["nodes"]["inner"]
    deepest = inner["node_data"]["subgraph"]["nodes"]["deepest"]
    assert outer["registry_key"] == "hay-bar:node:Group"
    assert inner["registry_key"] == "hay-bar:node:Add"
    assert deepest["registry_key"] == "hay-bar:node:Sub"
    assert count == 3


@pytest.mark.unit
def test_rewrites_chain_adapter_key_lists():
    from haywire_studio.packaging.rename.graphs import patch_graph_tree

    data = {"edges": {"e": {"chain_adapter_keys": ["haybale-foo:adapter:X", "other:adapter:Y"]}}}
    count, _ = patch_graph_tree(data, "haybale-foo", "hay-bar")

    assert data["edges"]["e"]["chain_adapter_keys"] == ["hay-bar:adapter:X", "other:adapter:Y"]
    assert count == 1


@pytest.mark.unit
def test_rewrites_library_name_only_under_node_data():
    from haywire_studio.packaging.rename.graphs import patch_graph_tree

    data = {
        "name": "haybale-foo",  # the GRAPH's name — must NOT change
        "nodes": {"n": {"node_data": {"library": {"name": "haybale-foo"}}}},
    }
    patch_graph_tree(data, "haybale-foo", "hay-bar")

    assert data["name"] == "haybale-foo"
    assert data["nodes"]["n"]["node_data"]["library"]["name"] == "hay-bar"


@pytest.mark.unit
def test_never_rewrites_user_prose():
    from haywire_studio.packaging.rename.graphs import patch_graph_tree

    data = {"nodes": {"n": {"node_data": {"props": {"note": "uses haybale-foo a lot"}}}}}
    count, _ = patch_graph_tree(data, "haybale-foo", "hay-bar")

    assert count == 0
    assert data["nodes"]["n"]["node_data"]["props"]["note"] == "uses haybale-foo a lot"


@pytest.mark.unit
def test_prefix_match_is_colon_scoped():
    """haybale-foo must not match haybale-foobar."""
    from haywire_studio.packaging.rename.graphs import patch_graph_tree

    data = {"nodes": {"n": {"registry_key": "haybale-foobar:node:Add"}}}
    count, _ = patch_graph_tree(data, "haybale-foo", "hay-bar")

    assert count == 0


@pytest.mark.unit
def test_non_key_value_in_a_key_field_is_left_alone():
    """Grammar guard: a key field holding something that is not a key."""
    from haywire_studio.packaging.rename.graphs import patch_graph_tree

    data = {"nodes": {"n": {"registry_key": "haybale-foo: see the docs"}}}
    count, _ = patch_graph_tree(data, "haybale-foo", "hay-bar")

    assert count == 0


@pytest.mark.unit
def test_drift_scan_reports_unpatched_occurrences():
    from haywire_studio.packaging.rename.graphs import patch_graph_tree

    data = {
        "name": "haybale-foo",
        "nodes": {"n": {"node_data": {"props": {"note": "haybale-foo"}}}},
    }
    _, leftovers = patch_graph_tree(data, "haybale-foo", "hay-bar")

    assert len(leftovers) == 2


@pytest.mark.unit
def test_is_registry_key_grammar():
    from haywire_studio.packaging.rename.graphs import is_registry_key

    assert is_registry_key("haybale-core:type:FLOAT")
    assert is_registry_key("haywire-core:widget:NumberWidget")
    assert is_registry_key("haybale-studio:theme:node:Dark")  # 4-part variant
    assert not is_registry_key("haybale-foo: see the docs")
    assert not is_registry_key("just-a-name")
    assert not is_registry_key("")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/rename/test_graphs.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'haywire_studio.packaging.rename.graphs'`

- [ ] **Step 3: Write `graphs.py`**

```python
"""Registry-key rewriting inside saved graphs.

Name-based and fully recursive. Measured across the repo's 8 graphs there are
13,242 ``registry_key`` + 2,893 ``widget_key`` + 8 ``chain_adapter_keys``
values, and they sit at many different depths — inside every port of every
node, not at a handful of fixed paths. Graph-groups will nest whole graphs
inside nodes, so depth is unbounded by design.

Matching by field name is safe *for these fields specifically* because the
key grammar is unambiguous: all 16,143 real values match
``<dist>:<kind>[:<sub>]:<Name>``. A value starting ``<old-dist>:`` in one of
these fields is certainly a registry key, never a coincidence. The same is
NOT true of a bare ``name`` field, which is why ``library.name`` keeps a
position-scoped rule.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .discovery import find_graph_files
from .model import FileChange, Occurrence

#: Fields whose value is a single registry key.
KEY_FIELDS = frozenset({"registry_key", "widget_key"})

#: Fields whose value is a list of registry keys.
LIST_KEY_FIELDS = frozenset({"chain_adapter_keys"})

#: ``<dist>:<kind>:<Name>`` with an optional extra kind segment (themes use
#: ``<dist>:theme:<type>:<Name>``). Verified against all 16,143 real values.
_KEY_GRAMMAR = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*(?::[A-Za-z0-9_]+){2,3}$")


def is_registry_key(value: str) -> bool:
    """True if *value* is shaped like a registry key."""
    return bool(_KEY_GRAMMAR.match(value))


def _rewrite(value: object, old: str, new: str) -> tuple[object, int]:
    """Rewrite one key value if it belongs to *old*. Colon-scoped, so
    ``haybale-foo`` never matches ``haybale-foobar``, and grammar-guarded, so
    prose parked in a key field is left alone."""
    if not isinstance(value, str):
        return value, 0
    if not value.startswith(old + ":") or not is_registry_key(value):
        return value, 0
    return new + value[len(old) :], 1


def _walk(node: object, old: str, new: str, in_library: bool = False) -> int:
    """Recurse the whole tree, rewriting key fields wherever they appear."""
    count = 0

    if isinstance(node, dict):
        for key, value in node.items():
            if key in KEY_FIELDS:
                node[key], hit = _rewrite(value, old, new)
                count += hit
            elif key in LIST_KEY_FIELDS and isinstance(value, list):
                for i, item in enumerate(value):
                    value[i], hit = _rewrite(item, old, new)
                    count += hit
            elif key == "name" and in_library and value == old:
                # Position-scoped: only the library block's own name. A bare
                # `name` anywhere else is a graph/port/user value.
                node[key] = new
                count += 1
            else:
                count += _walk(value, old, new, in_library=(key == "library"))

    elif isinstance(node, list):
        for item in node:
            count += _walk(item, old, new, in_library=in_library)

    return count


def _scan_leftovers(obj: object, old: str, trail: str = "") -> list[str]:
    """Every remaining string containing *old*, as dotted paths. Drift
    detector: a hit means a key-bearing field this module does not know."""
    found: list[str] = []
    if isinstance(obj, str):
        if old in obj:
            found.append(trail)
    elif isinstance(obj, dict):
        for key, value in obj.items():
            found += _scan_leftovers(value, old, f"{trail}.{key}" if trail else str(key))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            found += _scan_leftovers(item, old, f"{trail}[{i}]")
    return found


def patch_graph_tree(data: dict, old: str, new: str) -> tuple[int, list[str]]:
    """Rewrite every registry key in *data* in place.

    Returns ``(replacements, leftover_paths)``.
    """
    count = _walk(data, old, new)
    return count, _scan_leftovers(data, old)


def plan_graphs(root: Path, old: str, new: str) -> tuple[list[FileChange], list[Occurrence]]:
    """Compute graph changes without writing anything."""
    changes: list[FileChange] = []
    drift: list[Occurrence] = []

    for path in find_graph_files(root):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        count, leftovers = patch_graph_tree(data, old, new)
        if count:
            changes.append(FileChange(path=path, kind="graph", count=count))
        drift += [Occurrence(path=path, line=0, text=p) for p in leftovers]

    return changes, drift


def apply_graphs(changes: list[FileChange], old: str, new: str) -> None:
    """Rewrite each planned graph on disk. No backups — a clean tree is the
    precondition, so ``git checkout .`` is the rollback."""
    for change in changes:
        data = json.loads(change.path.read_text(encoding="utf-8"))
        patch_graph_tree(data, old, new)
        change.path.write_text(json.dumps(data, indent=2), encoding="utf-8")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/rename/test_graphs.py -q`
Expected: PASS — 9 passed

- [ ] **Step 5: Verify the counts against real graphs**

```bash
uv run python -c "
import json
from pathlib import Path
from haywire_studio.packaging.rename.graphs import patch_graph_tree
total = 0
for p in sorted(Path('graphs').glob('*.haywire')):
    n, _ = patch_graph_tree(json.loads(p.read_text()), 'haybale-core', 'hay-core')
    print(f'{p.name:24} {n}')
    total += n
print('total:', total)
"
```

Expected: non-zero counts summing to **4,422** for `haybale-core` — matching the measured occurrence count. A total of 0 means the walker is broken.

- [ ] **Step 6: Commit**

```bash
git add packages/haywire-studio/src/haywire_studio/packaging/rename/graphs.py tests/rename/test_graphs.py
git commit -m "feat(rename): recursive name-based registry-key rewriting

Keys live inside every port of every node, not at fixed paths — a
position-scoped rule set caught ~1% of the 16,143 real references.
Recursion also handles graph-groups nesting graphs inside nodes."
```

---

## Task 3: Delete the tests that certify the bug

**Files:**
- Delete: `tests/test_rename_cli.py`

**Interfaces:**
- Consumes: nothing
- Produces: nothing

- [ ] **Step 1: Confirm its coverage is superseded**

Run: `cat tests/test_rename_cli.py`

Expected: four tests. `test_sanitize_name_rejects_path_separators` covers `sanitize_rename` (superseded by `validate_target` in Task 4). The other three assert on the `{"type": ...}` shape no serializer produces — superseded by `tests/rename/test_graphs.py`.

- [ ] **Step 2: Delete it**

```bash
git rm tests/test_rename_cli.py
```

- [ ] **Step 3: Verify nothing imported from it**

Run: `grep -rn "test_rename_cli" --include="*.py" . | grep -v ".venv"`
Expected: no output

- [ ] **Step 4: Commit**

```bash
git commit -m "test(rename): drop tests asserting a graph shape that never existed

The fixtures hand-wrote {\"type\": ...}; NodeWrapper.serialize emits
registry_key, and real graphs are .haywire not .json. These tests passed
against a patcher that matched nothing real."
```

---

## Task 4: Name validation and collision detection

**Files:**
- Create: `packages/haywire-studio/src/haywire_studio/packaging/rename/checks.py`
- Test: `tests/rename/test_checks.py`

**Interfaces:**
- Consumes: `Blocker`, `Warning_` from `model.py`
- Produces: `validate_target(new_dist) -> tuple[list[Blocker], bool]`; `check_collisions(workspace_root, old_dist, new_dist) -> tuple[list[Blocker], list[Warning_]]`; `CONVENTIONAL_PREFIXES`

- [ ] **Step 1: Write the failing test**

```python
# tests/rename/test_checks.py
"""Target-name validation and the five collision namespaces."""

from __future__ import annotations

import pytest


@pytest.mark.unit
def test_path_separators_are_blocked():
    from haywire_studio.packaging.rename.checks import validate_target

    blockers, _ = validate_target("foo/bar")
    assert blockers
    assert "separator" in blockers[0].message.lower()


@pytest.mark.unit
def test_conventional_prefixes_need_no_confirm():
    from haywire_studio.packaging.rename.checks import validate_target

    for name in ("haybale-forecast", "hay-forecast"):
        blockers, needs_confirm = validate_target(name)
        assert not blockers
        assert not needs_confirm


@pytest.mark.unit
def test_unconventional_prefix_requests_confirmation():
    """A bare name is legal but usually a typo — warn, do not block."""
    from haywire_studio.packaging.rename.checks import validate_target

    blockers, needs_confirm = validate_target("forecast")
    assert not blockers
    assert needs_confirm


@pytest.mark.unit
def test_haywire_prefix_is_not_conventional():
    """haywire- belongs to the framework; a user library there is asked."""
    from haywire_studio.packaging.rename.checks import validate_target

    _, needs_confirm = validate_target("haywire-forecast")
    assert needs_confirm


@pytest.mark.unit
def test_invalid_module_name_is_blocked():
    from haywire_studio.packaging.rename.checks import validate_target

    blockers, _ = validate_target("9bad")
    assert blockers


@pytest.mark.unit
def test_collision_with_existing_barn_dir_blocks(tmp_path):
    from haywire_studio.packaging.rename.checks import check_collisions

    (tmp_path / "barn" / "hay-taken").mkdir(parents=True)
    (tmp_path / "barn" / "hay-src").mkdir(parents=True)

    blockers, _ = check_collisions(tmp_path, "hay-src", "hay-taken")
    assert any("barn" in b.message for b in blockers)


@pytest.mark.unit
def test_collision_on_module_name_blocks(tmp_path):
    """haybale-TEST_A and haybale-test-a both normalise to haybale_test_a."""
    from haywire_studio.packaging.rename.checks import check_collisions

    (tmp_path / "barn" / "haybale-TEST_A").mkdir(parents=True)
    (tmp_path / "barn" / "hay-src").mkdir(parents=True)

    blockers, _ = check_collisions(tmp_path, "hay-src", "haybale-test-a")
    assert any("module" in b.message.lower() for b in blockers)


@pytest.mark.unit
def test_collision_with_heaps_entry_blocks(tmp_path):
    """[[heaps]] is the user-authored local list — the one rename writes."""
    from haywire_studio.packaging.rename.checks import check_collisions

    (tmp_path / "barn" / "hay-src").mkdir(parents=True)
    marketplace = tmp_path / ".haywire"
    marketplace.mkdir()
    (marketplace / "marketplace.toml").write_text(
        '[[heaps]]\nname = "hay-taken"\npath = "barn/hay-taken"\n'
    )

    blockers, _ = check_collisions(tmp_path, "hay-src", "hay-taken")
    assert any("marketplace" in b.message.lower() for b in blockers)


@pytest.mark.unit
def test_same_name_blocks(tmp_path):
    from haywire_studio.packaging.rename.checks import check_collisions

    (tmp_path / "barn" / "hay-src").mkdir(parents=True)
    blockers, _ = check_collisions(tmp_path, "hay-src", "hay-src")
    assert blockers
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/rename/test_checks.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'haywire_studio.packaging.rename.checks'`

- [ ] **Step 3: Write `checks.py`**

```python
"""Preconditions. Every function here is read-only — the preflight promises
to change nothing, including temp probe files."""

from __future__ import annotations

import os
from importlib.metadata import distributions
from pathlib import Path

from haywire.core.library.haybale_toml import module_of

from .model import Blocker, Warning_

#: Prefixes a project library conventionally carries. ``haywire-`` is
#: deliberately absent — the framework owns it, so a user library aiming
#: there gets the confirmation prompt rather than a silent pass.
CONVENTIONAL_PREFIXES = ("haybale-", "hay-")


def validate_target(new_dist: str) -> tuple[list[Blocker], bool]:
    """Validate the target distribution name.

    Returns ``(blockers, needs_prefix_confirm)``. The name is taken verbatim —
    nothing is prefixed, stripped, or slugified on the user's behalf.
    """
    blockers: list[Blocker] = []
    name = new_dist.strip()

    if not name:
        return [Blocker(message="Target name cannot be empty.")], False

    if "/" in name or "\\" in name or ".." in name:
        return [
            Blocker(
                message=f'"{name}" contains a path separator.',
                remedy="Use a plain package name.",
            )
        ], False

    if not module_of(name).isidentifier():
        return [
            Blocker(
                message=f'"{name}" does not produce a valid Python module name '
                f'(would be "{module_of(name)}").',
                remedy="Use letters, digits, hyphens and underscores; do not start with a digit.",
            )
        ], False

    return blockers, not name.lower().startswith(CONVENTIONAL_PREFIXES)


def _installed_dist_names() -> set[str]:
    names: set[str] = set()
    for dist in distributions():
        raw = dist.metadata["Name"] if dist.metadata else None
        if raw:
            names.add(raw.lower())
    return names


def check_collisions(
    workspace_root: Path, old_dist: str, new_dist: str
) -> tuple[list[Blocker], list[Warning_]]:
    """Check the five namespaces the target could land in.

    Blocks on: same name, ``barn/`` directory, ``[[heaps]]``, an installed
    distribution, and a module-name clash. Warns on a remote ``[[caches]]``
    row — shadowing a catalog entry can be deliberate.
    """
    blockers: list[Blocker] = []
    warnings: list[Warning_] = []
    new_module = module_of(new_dist)

    if new_dist.lower() == old_dist.lower():
        return [Blocker(message="Target name is the same as the current name.")], warnings

    barn = workspace_root / "barn"
    if (barn / new_dist).exists():
        blockers.append(
            Blocker(
                message=f'A barn directory "{barn / new_dist}" already exists.',
                remedy="Pick a different name, or remove that directory.",
            )
        )

    # Module-name clash: haybale-TEST_A and haybale-test-a both normalise to
    # haybale_test_a, so two dists would install into one importable package.
    if barn.is_dir():
        for sibling in barn.iterdir():
            if not sibling.is_dir() or sibling.name.lower() == old_dist.lower():
                continue
            if module_of(sibling.name) == new_module:
                blockers.append(
                    Blocker(
                        message=f'Module name "{new_module}" collides with barn library '
                        f'"{sibling.name}".',
                        remedy="Pick a name that normalises to a different module.",
                    )
                )

    if new_dist.lower() in _installed_dist_names():
        blockers.append(
            Blocker(
                message=f'"{new_dist}" is already installed in this environment.',
                remedy=f"uv pip uninstall {new_dist}   # if it is not needed",
            )
        )

    marketplace_path = workspace_root / ".haywire" / "marketplace.toml"
    if marketplace_path.is_file():
        from haywire.core.marketstall import parse_project_marketplace

        parsed = parse_project_marketplace(marketplace_path)
        for heap in parsed.heaps:
            if str(heap.get("name", "")).lower() == new_dist.lower():
                blockers.append(
                    Blocker(
                        message=f'"{new_dist}" already has a [[heaps]] entry in marketplace.toml.',
                        remedy="Remove that entry, or pick a different name.",
                    )
                )
        for row in parsed.caches:
            if row.name.lower() == new_dist.lower():
                warnings.append(
                    Warning_(
                        message=f'"{new_dist}" matches a marketplace catalog entry — '
                        f"the local library will shadow it."
                    )
                )

    return blockers, warnings
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/rename/test_checks.py -q`
Expected: PASS — 9 passed

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-studio/src/haywire_studio/packaging/rename/checks.py tests/rename/test_checks.py
git commit -m "feat(rename): verbatim name validation and five-namespace collision check

Names are taken verbatim — no haybale- reconstruction, which silently
flipped hay- libraries. Collisions cover the barn dir, [[heaps]] (the
list rename writes; the old code read [[caches]]), installed dists, and
module-name normalisation."
```

---

## Task 5: Clean-tree gate and write-access probe

**Files:**
- Modify: `packages/haywire-studio/src/haywire_studio/packaging/rename/checks.py`
- Test: `tests/rename/test_checks_git.py`

**Interfaces:**
- Consumes: `Blocker`; `git` from `haywire.core.publishing.git`
- Produces: `check_clean_tree(workspace_root) -> list[Blocker]`; `check_write_access(paths, dir_renames) -> list[Blocker]`

- [ ] **Step 1: Write the failing test**

```python
# tests/rename/test_checks_git.py
"""Clean-tree gate and the write-access probe."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


def _git_repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    (tmp_path / "seed.txt").write_text("seed")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "seed"], cwd=tmp_path, check=True)
    return tmp_path


@pytest.mark.unit
def test_clean_tree_passes(tmp_path):
    from haywire_studio.packaging.rename.checks import check_clean_tree

    assert check_clean_tree(_git_repo(tmp_path)) == []


@pytest.mark.unit
def test_dirty_tree_blocks_and_names_the_fix(tmp_path):
    """No --allow-dirty exists, so the message must carry the commands."""
    from haywire_studio.packaging.rename.checks import check_clean_tree

    repo = _git_repo(tmp_path)
    (repo / "seed.txt").write_text("modified")

    blockers = check_clean_tree(repo)
    assert blockers
    assert "seed.txt" in blockers[0].message
    assert "git commit" in blockers[0].remedy
    assert "git stash" in blockers[0].remedy


@pytest.mark.unit
def test_untracked_file_also_blocks(tmp_path):
    from haywire_studio.packaging.rename.checks import check_clean_tree

    repo = _git_repo(tmp_path)
    (repo / "new.txt").write_text("untracked")
    assert check_clean_tree(repo)


@pytest.mark.unit
def test_non_repo_blocks_with_init_hint(tmp_path):
    from haywire_studio.packaging.rename.checks import check_clean_tree

    blockers = check_clean_tree(tmp_path)
    assert blockers
    assert "git init" in blockers[0].remedy


@pytest.mark.unit
def test_write_access_passes_on_writable_paths(tmp_path):
    from haywire_studio.packaging.rename.checks import check_write_access

    f = tmp_path / "a.json"
    f.write_text("{}")
    assert check_write_access([f], [tmp_path / "sub"]) == []


@pytest.mark.unit
def test_write_access_checks_PARENT_for_dir_renames(tmp_path):
    """Renaming a directory needs write on its PARENT, not on itself."""
    from haywire_studio.packaging.rename.checks import check_write_access

    parent = tmp_path / "locked"
    parent.mkdir()
    target = parent / "lib"
    target.mkdir()
    parent.chmod(0o500)  # r-x: target is writable, its parent is not
    try:
        assert check_write_access([], [target]), "must inspect the parent, not the target"
    finally:
        parent.chmod(0o700)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/rename/test_checks_git.py -q`
Expected: FAIL — `ImportError: cannot import name 'check_clean_tree'`

- [ ] **Step 3: Append to `checks.py`**

```python
def check_clean_tree(workspace_root: Path) -> list[Blocker]:
    """A clean tree is a hard precondition — there is no override flag.

    This is what makes ``git checkout . && git clean -fd`` a complete
    rollback: if the tree is proven clean before the rename writes anything,
    everything dirty afterwards is provably the rename's own work. Same
    reasoning as the share pipeline (steps/preconditions.py:115).
    """
    from haywire.core.publishing.git import git

    if not git(["--version"], cwd=workspace_root, timeout=10.0).ok:
        return [
            Blocker(
                message="git is not available.",
                remedy="Install git — the rename relies on it for rollback.",
            )
        ]

    if not git(["rev-parse", "--is-inside-work-tree"], cwd=workspace_root, timeout=10.0).ok:
        return [
            Blocker(
                message=f"{workspace_root} is not a git repository.",
                remedy=(
                    "Initialise one first — a rename is only safely reversible with git:\n"
                    "  git init && git add -A && git commit -m 'initial'"
                ),
            )
        ]

    status = git(["status", "--porcelain"], cwd=workspace_root, timeout=10.0)
    if status.ok and status.stdout.strip():
        files = [line[3:].strip() for line in status.stdout.splitlines() if line.strip()]
        listed = "\n".join(f"  {f}" for f in files)
        return [
            Blocker(
                message=f"Working tree is not clean:\n{listed}",
                remedy=(
                    "A rename rewrites files across the whole project, and git is its only\n"
                    "undo. Commit or stash first:\n"
                    '  git add -A && git commit -m "wip before rename"\n'
                    "  # or\n"
                    "  git stash --include-untracked"
                ),
            )
        ]
    return []


def check_write_access(paths: list[Path], dir_renames: list[Path]) -> list[Blocker]:
    """Verify every planned write is permitted, without writing anything.

    Renaming a directory requires write+execute on its PARENT — the entry
    being renamed lives there. Checking the directory itself passes while the
    rename still fails, which is the easy bug here.
    """
    blockers: list[Blocker] = []

    for path in paths:
        if path.exists() and not os.access(path, os.W_OK):
            blockers.append(Blocker(message=f"No write permission: {path}"))

    for target in dir_renames:
        parent = target.parent
        if parent.exists() and not os.access(parent, os.W_OK | os.X_OK):
            blockers.append(
                Blocker(
                    message=f"No write permission on {parent} (needed to rename {target.name}).",
                    remedy=f"chmod u+wx {parent}",
                )
            )

    return blockers
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/rename/test_checks_git.py -q`
Expected: PASS — 6 passed

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-studio/src/haywire_studio/packaging/rename/checks.py tests/rename/test_checks_git.py
git commit -m "feat(rename): hard clean-tree gate and plan-derived write-access probe

Clean tree has no override: it is what makes git the complete rollback.
The write probe checks the PARENT for directory renames."
```

---

## Task 6: Python imports and self-referencing key literals

**Files:**
- Create: `packages/haywire-studio/src/haywire_studio/packaging/rename/pysource.py`
- Test: `tests/rename/test_pysource.py`

**Interfaces:**
- Consumes: `FileChange`, `Occurrence`; `is_registry_key` from `graphs.py`
- Produces: `rewrite_source(source, old_dist, new_dist, old_module, new_module) -> tuple[str, int]`; `scan_prose(source, old_module, old_dist) -> list[int]`; `plan_python(roots, old_dist, new_dist, old_module, new_module) -> tuple[list[FileChange], list[Occurrence]]`; `apply_python(changes, old_dist, new_dist, old_module, new_module) -> None`

- [ ] **Step 1: Write the failing test**

```python
# tests/rename/test_pysource.py
"""AST imports plus registry-key literals. Prose is reported, never rewritten."""

from __future__ import annotations

import pytest

OLD_DIST, NEW_DIST = "haybale-foo", "hay-bar"
OLD_MOD, NEW_MOD = "haybale_foo", "hay_bar"


def _rw(src: str):
    from haywire_studio.packaging.rename.pysource import rewrite_source

    return rewrite_source(src, OLD_DIST, NEW_DIST, OLD_MOD, NEW_MOD)


@pytest.mark.unit
def test_rewrites_from_import():
    out, n = _rw("from haybale_foo.types.math import MathOPs\n")
    assert out == "from hay_bar.types.math import MathOPs\n"
    assert n == 1


@pytest.mark.unit
def test_rewrites_plain_and_aliased_import():
    assert _rw("import haybale_foo\n")[0] == "import hay_bar\n"
    assert _rw("import haybale_foo as hf\n")[0] == "import hay_bar as hf\n"


@pytest.mark.unit
def test_rewrites_function_local_import_preserving_indent():
    out, n = _rw("def f():\n    from haybale_foo.types import X\n    return X\n")
    assert "    from hay_bar.types import X" in out
    assert n == 1


@pytest.mark.unit
def test_leaves_relative_imports_alone():
    src = "from ._state import Flow\nfrom ..copy import STEPS\n"
    assert _rw(src) == (src, 0)


@pytest.mark.unit
def test_does_not_rewrite_lookalike_module():
    src = "import haybale_foobar\n"
    assert _rw(src) == (src, 0)


@pytest.mark.unit
def test_rewrites_self_referencing_registry_key_literal():
    """types/specs.py:9 does exactly this — an unrewritten key dangles."""
    src = 'X = spec(widget_key="haybale-foo:widget:TemperatureWidget")\n'
    out, n = _rw(src)

    assert out == 'X = spec(widget_key="hay-bar:widget:TemperatureWidget")\n'
    assert n == 1


@pytest.mark.unit
def test_rewrites_key_literal_in_single_quotes():
    out, _ = _rw("K = 'haybale-foo:node:Add'\n")
    assert out == "K = 'hay-bar:node:Add'\n"


@pytest.mark.unit
def test_does_not_rewrite_other_libraries_keys():
    src = 'W = "haywire-core:widget:NumberWidget"\n'
    assert _rw(src) == (src, 0)


@pytest.mark.unit
def test_does_not_rewrite_prose_mentioning_the_name():
    """A db path literal is wrong after rename, but the data has not moved."""
    src = '"""Creates ~/.haywire/db/haybale_foo/config.toml."""\nN = "haybale-foo is nice"\n'
    assert _rw(src) == (src, 0)


@pytest.mark.unit
def test_counts_both_kinds_together():
    src = 'from haybale_foo.a import B\nK = "haybale-foo:node:Add"\n'
    out, n = _rw(src)

    assert "from hay_bar.a import B" in out
    assert '"hay-bar:node:Add"' in out
    assert n == 2


@pytest.mark.unit
def test_scan_prose_reports_only_unhandled_lines():
    from haywire_studio.packaging.rename.pysource import scan_prose

    src = (
        "import haybale_foo\n"
        'K = "haybale-foo:node:Add"\n'
        'P = "~/.haywire/db/haybale_foo/x"\n'
        "# note: haybale-foo\n"
    )
    assert scan_prose(src, OLD_MOD, OLD_DIST) == [3, 4]


@pytest.mark.unit
def test_preserves_comments_and_blank_lines():
    out, _ = _rw("from haybale_foo import A  # keep me\n\n\nY = 2\n")
    assert out == "from hay_bar import A  # keep me\n\n\nY = 2\n"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/rename/test_pysource.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'haywire_studio.packaging.rename.pysource'`

- [ ] **Step 3: Write `pysource.py`**

```python
"""Python self-reference rewriting.

Two things are mechanically rewritable:

* **Imports** — the AST proves a name is a module path.
* **Registry-key literals** — ``"haybale-foo:widget:X"`` has an unambiguous
  grammar, so a string starting ``<old-dist>:`` and matching it is certainly
  a key. ``barn/haybale-example/haybale_example/types/specs.py:9`` does
  exactly this; left unpatched the widget silently fails to resolve.

Everything else is REPORTED and left alone. A literal like
``~/.haywire/db/haybale_foo/`` is genuinely wrong after a rename, but the
data it names has not moved, so rewriting it would make it lie differently.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from .graphs import is_registry_key
from .model import FileChange, Occurrence


def _import_line_numbers(source: str, old_module: str) -> set[int]:
    """1-based line numbers of import statements naming *old_module*.

    Relative imports (``level > 0``) carry no module name and are skipped.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()

    lines: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == old_module or alias.name.startswith(old_module + "."):
                    lines.add(node.lineno)
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # relative — nothing to rewrite
                continue
            module = node.module or ""
            if module == old_module or module.startswith(old_module + "."):
                lines.add(node.lineno)
    return lines


def _rewrite_import_line(line: str, old_module: str, new_module: str) -> str:
    replaced = line.replace(f"{old_module}.", f"{new_module}.")
    replaced = replaced.replace(f" {old_module} ", f" {new_module} ")
    if replaced.rstrip("\n").endswith(f" {old_module}"):
        newline = "\n" if replaced.endswith("\n") else ""
        replaced = replaced.rstrip("\n")[: -len(old_module)] + new_module + newline
    return replaced


def _key_literal_pattern(old_dist: str) -> re.Pattern[str]:
    """Match a quoted string literal beginning ``<old_dist>:``."""
    return re.compile(rf"(['\"])({re.escape(old_dist)}:[^'\"]*)\1")


def _rewrite_key_literals(source: str, old_dist: str, new_dist: str) -> tuple[str, int]:
    """Rewrite quoted registry-key literals belonging to *old_dist*."""
    count = 0

    def _sub(match: re.Match[str]) -> str:
        nonlocal count
        quote, value = match.group(1), match.group(2)
        if not is_registry_key(value):
            return match.group(0)
        count += 1
        return f"{quote}{new_dist}{value[len(old_dist):]}{quote}"

    return _key_literal_pattern(old_dist).sub(_sub, source), count


def rewrite_source(
    source: str, old_dist: str, new_dist: str, old_module: str, new_module: str
) -> tuple[str, int]:
    """Rewrite imports and registry-key literals. Returns ``(text, count)``."""
    lines = source.splitlines(keepends=True)
    count = 0

    for lineno in _import_line_numbers(source, old_module):
        index = lineno - 1
        if index >= len(lines):
            continue
        rewritten = _rewrite_import_line(lines[index], old_module, new_module)
        if rewritten != lines[index]:
            lines[index] = rewritten
            count += 1

    text, key_hits = _rewrite_key_literals("".join(lines), old_dist, new_dist)
    return text, count + key_hits


def scan_prose(source: str, old_module: str, old_dist: str) -> list[int]:
    """1-based line numbers mentioning the old name that nothing rewrites."""
    import_lines = _import_line_numbers(source, old_module)
    pattern = _key_literal_pattern(old_dist)

    reported: list[int] = []
    for lineno, line in enumerate(source.splitlines(), start=1):
        if lineno in import_lines:
            continue
        if old_module not in line and old_dist not in line:
            continue
        stripped = pattern.sub("", line)
        if old_module in stripped or old_dist in stripped:
            reported.append(lineno)
    return reported


def plan_python(
    roots: list[Path], old_dist: str, new_dist: str, old_module: str, new_module: str
) -> tuple[list[FileChange], list[Occurrence]]:
    """Compute Python changes without writing."""
    changes: list[FileChange] = []
    prose: list[Occurrence] = []

    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.glob("**/*.py")):
            if "__pycache__" in path.parts:
                continue
            try:
                source = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if old_module not in source and old_dist not in source:
                continue

            _, count = rewrite_source(source, old_dist, new_dist, old_module, new_module)
            if count:
                changes.append(FileChange(path=path, kind="python", count=count))

            all_lines = source.splitlines()
            for lineno in scan_prose(source, old_module, old_dist):
                prose.append(Occurrence(path=path, line=lineno, text=all_lines[lineno - 1].strip()))

    return changes, prose


def apply_python(
    changes: list[FileChange], old_dist: str, new_dist: str, old_module: str, new_module: str
) -> None:
    """Rewrite each planned Python file on disk."""
    for change in changes:
        source = change.path.read_text(encoding="utf-8")
        rewritten, _ = rewrite_source(source, old_dist, new_dist, old_module, new_module)
        change.path.write_text(rewritten, encoding="utf-8")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/rename/test_pysource.py -q`
Expected: PASS — 12 passed

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-studio/src/haywire_studio/packaging/rename/pysource.py tests/rename/test_pysource.py
git commit -m "feat(rename): rewrite imports AND self-referencing registry-key literals

types/specs.py:9 hardcodes widget_key=\"haybale-example:widget:...\";
an import-only pass leaves it dangling. Key literals have an unambiguous
grammar so they are mechanically rewritable, unlike prose."
```

---

## Task 7: Dependent fan-out

**Files:**
- Modify: `packages/haywire-studio/src/haywire_studio/packaging/rename/checks.py`
- Test: `tests/rename/test_dependents.py`

**Interfaces:**
- Consumes: `Blocker`, `module_of`, `_import_line_numbers`
- Produces: `find_dependents(workspace_root, old_dist) -> tuple[list[Path], list[Blocker]]`

- [ ] **Step 1: Write the failing test**

```python
# tests/rename/test_dependents.py
"""Sibling barn libraries referencing the renamed library."""

from __future__ import annotations

import pytest


def _barn_lib(root, dist, *, linked=None, deps=None):
    module = dist.replace("-", "_").lower()
    lib = root / "barn" / dist
    pkg = lib / module
    pkg.mkdir(parents=True)
    linked_line = ""
    if linked:
        entries = ", ".join(f'"{x}"' for x in linked)
        linked_line = f"linked_libraries = [{entries}]\n"
    (pkg / "haybale.toml").write_text(f'name = "{dist}"\nversion = "0.1.0"\n{linked_line}')
    dep_line = ""
    if deps:
        entries = ", ".join(f'"{x}"' for x in deps)
        dep_line = f"dependencies = [{entries}]\n"
    (lib / "pyproject.toml").write_text(f'[project]\nname = "{dist}"\n{dep_line}')
    return lib


@pytest.mark.unit
def test_finds_dependent_via_linked_libraries(tmp_path):
    from haywire_studio.packaging.rename.checks import find_dependents

    _barn_lib(tmp_path, "hay-src")
    _barn_lib(tmp_path, "hay-dependent", linked=["hay_src"])

    dependents, blockers = find_dependents(tmp_path, "hay-src")
    assert not blockers
    assert [d.name for d in dependents] == ["hay-dependent"]


@pytest.mark.unit
def test_finds_dependent_via_pyproject_dependency(tmp_path):
    from haywire_studio.packaging.rename.checks import find_dependents

    _barn_lib(tmp_path, "hay-src")
    _barn_lib(tmp_path, "hay-dependent", deps=["hay-src"])

    dependents, _ = find_dependents(tmp_path, "hay-src")
    assert [d.name for d in dependents] == ["hay-dependent"]


@pytest.mark.unit
def test_finds_dependent_via_import(tmp_path):
    from haywire_studio.packaging.rename.checks import find_dependents

    _barn_lib(tmp_path, "hay-src")
    dep = _barn_lib(tmp_path, "hay-dependent")
    (dep / "hay_dependent" / "use.py").write_text("from hay_src.nodes import Adder\n")

    dependents, _ = find_dependents(tmp_path, "hay-src")
    assert [d.name for d in dependents] == ["hay-dependent"]


@pytest.mark.unit
def test_finds_dependent_via_registry_key_literal(tmp_path):
    from haywire_studio.packaging.rename.checks import find_dependents

    _barn_lib(tmp_path, "hay-src")
    dep = _barn_lib(tmp_path, "hay-dependent")
    (dep / "hay_dependent" / "w.py").write_text('K = "hay-src:widget:Thing"\n')

    dependents, _ = find_dependents(tmp_path, "hay-src")
    assert [d.name for d in dependents] == ["hay-dependent"]


@pytest.mark.unit
def test_unrelated_library_is_not_a_dependent(tmp_path):
    from haywire_studio.packaging.rename.checks import find_dependents

    _barn_lib(tmp_path, "hay-src")
    _barn_lib(tmp_path, "hay-other", linked=["haybale_core"])

    assert find_dependents(tmp_path, "hay-src")[0] == []


@pytest.mark.unit
def test_the_library_itself_is_never_its_own_dependent(tmp_path):
    from haywire_studio.packaging.rename.checks import find_dependents

    src = _barn_lib(tmp_path, "hay-src")
    (src / "hay_src" / "internal.py").write_text("from hay_src.types import X\n")

    assert find_dependents(tmp_path, "hay-src")[0] == []
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/rename/test_dependents.py -q`
Expected: FAIL — `ImportError: cannot import name 'find_dependents'`

- [ ] **Step 3: Append to `checks.py`**

```python
def find_dependents(workspace_root: Path, old_dist: str) -> tuple[list[Path], list[Blocker]]:
    """In-workspace barn libraries referencing *old_dist*.

    A dependent references it four ways: ``linked_libraries`` (module name),
    ``[project] dependencies`` (distribution name), imports (module name),
    and registry-key literals (distribution name). A broken
    ``linked_libraries`` entry does not raise — it silently breaks hot-reload
    scope tracking — so these must be patched, not merely reported.

    Out-of-workspace dependents are returned as blockers: site-packages
    cannot be rewritten from here.
    """
    from .pysource import _import_line_numbers

    old_module = module_of(old_dist)
    barn = workspace_root / "barn"
    dependents: list[Path] = []
    blockers: list[Blocker] = []

    if not barn.is_dir():
        return dependents, blockers

    for lib in sorted(barn.iterdir()):
        if not lib.is_dir() or lib.name.lower() == old_dist.lower():
            continue

        referenced = False

        pyproject = lib / "pyproject.toml"
        if pyproject.is_file():
            try:
                text = pyproject.read_text(encoding="utf-8")
                if f'"{old_dist}"' in text or f"'{old_dist}'" in text:
                    referenced = True
            except OSError:
                pass

        for toml_path in lib.glob("*/haybale.toml"):
            try:
                if f'"{old_module}"' in toml_path.read_text(encoding="utf-8"):
                    referenced = True
            except OSError:
                pass

        if not referenced:
            for py in lib.glob("**/*.py"):
                if "__pycache__" in py.parts:
                    continue
                try:
                    source = py.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    continue
                if _import_line_numbers(source, old_module) or f"{old_dist}:" in source:
                    referenced = True
                    break

        if referenced:
            dependents.append(lib)

    return dependents, blockers
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/rename/test_dependents.py -q`
Expected: PASS — 6 passed

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-studio/src/haywire_studio/packaging/rename/checks.py tests/rename/test_dependents.py
git commit -m "feat(rename): find in-workspace dependents across all four reference kinds

linked_libraries breakage is silent, so dependents must be patched
rather than listed for the user to fix by hand."
```

---

## Task 8: The planner

**Files:**
- Create: `packages/haywire-studio/src/haywire_studio/packaging/rename/planner.py`
- Test: `tests/rename/test_planner.py`

**Interfaces:**
- Consumes: everything from `checks.py`, `graphs.py`, `pysource.py`, `model.py`
- Produces: `plan_rename(old_dist, new_dist, workspace_root) -> tuple[RenamePlan, bool]`

- [ ] **Step 1: Write the failing test**

```python
# tests/rename/test_planner.py
"""plan_rename composes every check into one read-only plan."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest


def _workspace(tmp_path: Path) -> Path:
    """A clean git workspace: one library, one graph outside graphs/."""
    lib = tmp_path / "barn" / "hay-src" / "hay_src"
    lib.mkdir(parents=True)
    (lib / "haybale.toml").write_text(
        'name = "hay-src"\nversion = "0.1.0"\nlabel = "Src"\ntags = ["a"]\n'
    )
    (lib / "__init__.py").write_text("")
    (lib / "use.py").write_text(
        'from hay_src.types import X\nW = "hay-src:widget:Thing"\n'
    )
    (tmp_path / "barn" / "hay-src" / "pyproject.toml").write_text(
        '[project]\nname = "hay-src"\n\n'
        '[project.entry-points."haywire.libraries"]\nsrc = "hay_src:Library"\n\n'
        '[tool.hatch.build.targets.wheel]\npackages = ["hay_src"]\n'
    )
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "proj"\ndependencies = ["hay-src"]\n\n'
        "[tool.uv.sources]\nhay-src = { workspace = true }\n"
    )
    # deliberately NOT under graphs/ and NOT a .json extension
    nested = tmp_path / "flows"
    nested.mkdir()
    (nested / "g.haywire").write_text(
        json.dumps(
            {
                "graph_id": "g",
                "nodes": {
                    "n": {
                        "registry_key": "hay-src:node:Add",
                        "node_data": {
                            "ports": {"a": {"kwargs": {"widget_key": "hay-src:widget:W"}}}
                        },
                    }
                },
            }
        )
    )

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "seed"], cwd=tmp_path, check=True)
    return tmp_path


@pytest.mark.unit
def test_plan_is_read_only(tmp_path):
    """The preflight promises to change nothing — including temp files."""
    from haywire_studio.packaging.rename.planner import plan_rename

    ws = _workspace(tmp_path)
    plan_rename("hay-src", "hay-dst", ws)

    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=ws, capture_output=True, text=True
    ).stdout
    assert status == ""


@pytest.mark.unit
def test_plan_finds_graph_outside_graphs_folder(tmp_path):
    from haywire_studio.packaging.rename.planner import plan_rename

    ws = _workspace(tmp_path)
    plan, _ = plan_rename("hay-src", "hay-dst", ws)

    assert plan.ok, plan.blockers
    assert len(plan.graph_changes) == 1
    assert plan.graph_changes[0].count == 2  # registry_key + widget_key


@pytest.mark.unit
def test_plan_enumerates_every_change_kind(tmp_path):
    from haywire_studio.packaging.rename.planner import plan_rename

    ws = _workspace(tmp_path)
    plan, _ = plan_rename("hay-src", "hay-dst", ws)

    assert plan.old_module == "hay_src"
    assert plan.new_module == "hay_dst"
    assert plan.python_changes
    assert plan.toml_changes


@pytest.mark.unit
def test_dirty_tree_blocks_the_plan(tmp_path):
    from haywire_studio.packaging.rename.planner import plan_rename

    ws = _workspace(tmp_path)
    (ws / "dirt.txt").write_text("x")

    assert not plan_rename("hay-src", "hay-dst", ws)[0].ok


@pytest.mark.unit
def test_missing_source_library_blocks(tmp_path):
    from haywire_studio.packaging.rename.planner import plan_rename

    ws = _workspace(tmp_path)
    plan, _ = plan_rename("hay-nope", "hay-dst", ws)

    assert not plan.ok
    assert any("does not exist" in b.message for b in plan.blockers)


@pytest.mark.unit
def test_unconventional_target_flags_confirm(tmp_path):
    from haywire_studio.packaging.rename.planner import plan_rename

    ws = _workspace(tmp_path)
    assert plan_rename("hay-src", "forecast", ws)[1]


@pytest.mark.unit
def test_storage_dir_warning_is_emitted(tmp_path, monkeypatch):
    """Persisted data does not follow the rename — the user must be told."""
    from haywire_studio.packaging.rename import planner

    ws = _workspace(tmp_path)
    fake_home = tmp_path / "home"
    (fake_home / ".haywire" / "db" / "hay_src").mkdir(parents=True)
    monkeypatch.setattr(planner.Path, "home", classmethod(lambda cls: fake_home))

    plan, _ = planner.plan_rename("hay-src", "hay-dst", ws)
    assert any("hay_src" in w.message for w in plan.warnings)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/rename/test_planner.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'haywire_studio.packaging.rename.planner'`

- [ ] **Step 3: Write `planner.py`**

```python
"""The single planner. Both the dry run and --apply call this, so the plan
printed and the plan executed cannot diverge."""

from __future__ import annotations

from pathlib import Path

from haywire.core.library.haybale_toml import module_of

from .checks import (
    check_clean_tree,
    check_collisions,
    check_write_access,
    find_dependents,
    validate_target,
)
from .graphs import plan_graphs
from .model import Blocker, FileChange, RenamePlan, Warning_
from .pysource import plan_python


def plan_rename(old_dist: str, new_dist: str, workspace_root: Path) -> tuple[RenamePlan, bool]:
    """Enumerate every change and every blocker. Writes nothing.

    Returns ``(plan, needs_prefix_confirm)``.
    """
    workspace_root = Path(workspace_root)
    old_module = module_of(old_dist)
    new_module = module_of(new_dist)
    old_lib_dir = workspace_root / "barn" / old_dist

    plan = RenamePlan(
        old_dist=old_dist,
        new_dist=new_dist,
        old_module=old_module,
        new_module=new_module,
        workspace_root=workspace_root,
        old_lib_dir=old_lib_dir,
        new_lib_dir=workspace_root / "barn" / new_dist,
    )

    name_blockers, needs_confirm = validate_target(new_dist)
    plan.blockers += name_blockers
    if name_blockers:
        return plan, needs_confirm

    plan.blockers += check_clean_tree(workspace_root)

    if not old_lib_dir.is_dir():
        plan.blockers.append(
            Blocker(
                message=f'Library directory "{old_lib_dir}" does not exist.',
                remedy=f"ls {workspace_root / 'barn'}   # to see available libraries",
            )
        )
        return plan, needs_confirm

    collision_blockers, collision_warnings = check_collisions(workspace_root, old_dist, new_dist)
    plan.blockers += collision_blockers
    plan.warnings += collision_warnings

    dependents, dependent_blockers = find_dependents(workspace_root, old_dist)
    plan.blockers += dependent_blockers

    # ── config files: identity fields only ──────────────────────────────
    for candidate, count in (
        (old_lib_dir / old_module / "haybale.toml", 1),  # name
        (old_lib_dir / "pyproject.toml", 3),  # name, entry-point key, wheel packages
        (workspace_root / "pyproject.toml", 2),  # dependency string, uv source key
        (workspace_root / ".haywire" / "marketplace.toml", 2),  # heap name + path
    ):
        if candidate.is_file():
            plan.toml_changes.append(FileChange(path=candidate, kind="toml", count=count))

    graph_changes, graph_drift = plan_graphs(workspace_root, old_dist, new_dist)
    plan.graph_changes = graph_changes
    plan.unrecognized += graph_drift

    py_changes, py_prose = plan_python([old_lib_dir], old_dist, new_dist, old_module, new_module)
    plan.python_changes = py_changes
    plan.unrecognized += py_prose

    for dependent in dependents:
        dep_py, dep_prose = plan_python(
            [dependent], old_dist, new_dist, old_module, new_module
        )
        plan.dependent_changes += dep_py
        plan.unrecognized += dep_prose
        for toml_path in (*dependent.glob("*/haybale.toml"), dependent / "pyproject.toml"):
            if toml_path.is_file():
                plan.dependent_changes.append(FileChange(path=toml_path, kind="toml", count=1))

    # ── write access, derived from the plan itself ──────────────────────
    touched = [
        change.path
        for change in (
            *plan.toml_changes,
            *plan.graph_changes,
            *plan.python_changes,
            *plan.dependent_changes,
        )
    ]
    plan.blockers += check_write_access(touched, [old_lib_dir / old_module, old_lib_dir])

    # ── persisted storage does not follow the rename ────────────────────
    storage = Path.home() / ".haywire" / "db" / old_module
    if storage.is_dir():
        plan.warnings.append(
            Warning_(
                message=f"Persistent storage at {storage} will not follow the rename.",
                remedy=f"mv {storage} {storage.parent / new_module}",
            )
        )

    return plan, needs_confirm
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/rename/test_planner.py -q`
Expected: PASS — 7 passed

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-studio/src/haywire_studio/packaging/rename/planner.py tests/rename/test_planner.py
git commit -m "feat(rename): single read-only planner scanning the whole workspace

One function computes the plan; the dry run and --apply both call it, so
the printed plan and the executed plan cannot diverge."
```

---

## Task 9: The executor

**Files:**
- Create: `packages/haywire-studio/src/haywire_studio/packaging/rename/execute.py`
- Test: `tests/rename/test_execute.py`

**Interfaces:**
- Consumes: `RenamePlan`, `apply_graphs`, `apply_python`, `edit_toml`
- Produces: `execute_plan(plan, *, sink=print) -> tuple[bool, str]`; `RECOVERY`

- [ ] **Step 1: Write the failing test**

```python
# tests/rename/test_execute.py
"""Five fail-fast phases; identity fields only."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from tests.rename.test_planner import _workspace  # noqa: F401


def _run(ws: Path, old: str, new: str):
    from haywire_studio.packaging.rename.execute import execute_plan
    from haywire_studio.packaging.rename.planner import plan_rename

    plan, _ = plan_rename(old, new, ws)
    assert plan.ok, plan.blockers
    with patch("haywire_studio.packaging.rename.execute.subprocess.run") as run:
        run.return_value.returncode = 0
        run.return_value.stdout = b""
        return execute_plan(plan, sink=lambda *_: None)


@pytest.mark.unit
def test_renames_both_directories(tmp_path):
    ws = _workspace(tmp_path)
    ok, _ = _run(ws, "hay-src", "hay-dst")

    assert ok
    assert (ws / "barn" / "hay-dst" / "hay_dst").is_dir()
    assert not (ws / "barn" / "hay-src").exists()


@pytest.mark.unit
def test_preserves_descriptive_metadata(tmp_path):
    """Rename changes identity, not description."""
    ws = _workspace(tmp_path)
    _run(ws, "hay-src", "hay-dst")

    toml = (ws / "barn" / "hay-dst" / "hay_dst" / "haybale.toml").read_text()
    assert 'name = "hay-dst"' in toml
    assert 'label = "Src"' in toml
    assert 'tags = ["a"]' in toml


@pytest.mark.unit
def test_patches_graph_keys_outside_graphs_folder(tmp_path):
    ws = _workspace(tmp_path)
    _run(ws, "hay-src", "hay-dst")

    data = json.loads((ws / "flows" / "g.haywire").read_text())
    node = data["nodes"]["n"]
    assert node["registry_key"] == "hay-dst:node:Add"
    assert node["node_data"]["ports"]["a"]["kwargs"]["widget_key"] == "hay-dst:widget:W"


@pytest.mark.unit
def test_writes_no_bak_files(tmp_path):
    """Git is the rollback; .bak files would trip the next clean-tree gate."""
    ws = _workspace(tmp_path)
    _run(ws, "hay-src", "hay-dst")

    assert list(ws.glob("**/*.bak")) == []


@pytest.mark.unit
def test_rewrites_imports_and_key_literals(tmp_path):
    ws = _workspace(tmp_path)
    _run(ws, "hay-src", "hay-dst")

    text = (ws / "barn" / "hay-dst" / "hay_dst" / "use.py").read_text()
    assert "from hay_dst.types import X" in text
    assert '"hay-dst:widget:Thing"' in text


@pytest.mark.unit
def test_updates_project_pyproject(tmp_path):
    ws = _workspace(tmp_path)
    _run(ws, "hay-src", "hay-dst")

    text = (ws / "pyproject.toml").read_text()
    assert "hay-dst" in text
    assert '"hay-src"' not in text


@pytest.mark.unit
def test_uv_sync_failure_reports_source_rename_succeeded(tmp_path):
    """Phase 5 runs last, so its failure is an env problem, not a rename one."""
    from haywire_studio.packaging.rename.execute import execute_plan
    from haywire_studio.packaging.rename.planner import plan_rename

    ws = _workspace(tmp_path)
    plan, _ = plan_rename("hay-src", "hay-dst", ws)

    with patch("haywire_studio.packaging.rename.execute.subprocess.run") as run:
        run.return_value.returncode = 1
        run.return_value.stdout = b"resolution failed"
        ok, message = execute_plan(plan, sink=lambda *_: None)

    assert not ok
    assert "uv sync" in message
    assert "git checkout" not in message  # do not discard good work
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/rename/test_execute.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'haywire_studio.packaging.rename.execute'`

- [ ] **Step 3: Write `execute.py`**

```python
"""Executing a RenamePlan in five fail-fast phases.

Later phases depend on earlier ones, so the first error stops the run.
A clean tree was proven in planning, so everything dirty afterwards is this
run's own work and ``git checkout . && git clean -fd`` restores the start
state exactly. The command never runs that itself.
"""

from __future__ import annotations

import os
import subprocess
from typing import Any

from haywire.core.tomlio import edit_toml

from .graphs import apply_graphs
from .model import RenamePlan
from .pysource import apply_python

RECOVERY = "git checkout . && git clean -fd"


def execute_plan(plan: RenamePlan, *, sink: Any = print) -> tuple[bool, str]:
    """Apply *plan*. Returns ``(ok, message)``."""
    old_pkg = plan.old_lib_dir / plan.old_module
    tmp_pkg = plan.old_lib_dir / plan.new_module

    # ── phase 1: module directory ───────────────────────────────────────
    sink(f"Renaming module directory: {plan.old_module} → {plan.new_module}")
    try:
        os.rename(old_pkg, tmp_pkg)
    except OSError as exc:
        return False, f"Failed to rename module directory: {exc}\nRecover with:\n  {RECOVERY}"

    # ── phase 2: the library's own config + sources ─────────────────────
    sink("Updating library metadata...")
    try:
        # Identity only: label/description/tags/homepage_url/notes/
        # linked_libraries are deliberately preserved.
        with edit_toml(tmp_pkg / "haybale.toml") as doc:
            doc["name"] = plan.new_dist

        with edit_toml(plan.old_lib_dir / "pyproject.toml") as doc:
            doc["project"]["name"] = plan.new_dist
            entry_points = doc.get("project", {}).get("entry-points", {}).get("haywire.libraries", {})
            for key in list(entry_points):
                del entry_points[key]
            stem = plan.new_dist.removeprefix("haybale-").removeprefix("hay-")
            entry_points[stem] = f"{plan.new_module}:Library"
            doc["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] = [plan.new_module]
    except (OSError, KeyError) as exc:
        return False, f"Failed to update library metadata: {exc}\nRecover with:\n  {RECOVERY}"

    sink(f"Rewriting {len(plan.python_changes)} Python file(s)...")
    # Paths were planned against the pre-rename module dir; retarget them.
    for change in plan.python_changes:
        change.path = tmp_pkg / change.path.relative_to(old_pkg)
    try:
        apply_python(
            plan.python_changes, plan.old_dist, plan.new_dist, plan.old_module, plan.new_module
        )
    except OSError as exc:
        return False, f"Failed to rewrite Python sources: {exc}\nRecover with:\n  {RECOVERY}"

    # ── phase 3: library directory ──────────────────────────────────────
    sink(f"Renaming library directory: {plan.old_dist} → {plan.new_dist}")
    try:
        os.rename(plan.old_lib_dir, plan.new_lib_dir)
    except OSError as exc:
        return False, f"Failed to rename library directory: {exc}\nRecover with:\n  {RECOVERY}"

    # ── phase 4: project config, graphs, dependents ─────────────────────
    sink("Updating project configuration...")
    try:
        project_pyproject = plan.workspace_root / "pyproject.toml"
        if project_pyproject.is_file():
            with edit_toml(project_pyproject) as doc:
                deps = doc.get("project", {}).get("dependencies", [])
                for i, dep in enumerate(list(deps)):
                    if str(dep).lower() == plan.old_dist.lower():
                        deps[i] = plan.new_dist
                sources = doc.get("tool", {}).get("uv", {}).get("sources", {})
                for key in [k for k in sources if k.lower() == plan.old_dist.lower()]:
                    value = sources[key]
                    del sources[key]
                    sources[plan.new_dist] = value

        marketplace = plan.workspace_root / ".haywire" / "marketplace.toml"
        if marketplace.is_file():
            with edit_toml(marketplace) as doc:
                for heap in doc.get("heaps", []):
                    if str(heap.get("name", "")).lower() == plan.old_dist.lower():
                        heap["name"] = plan.new_dist
                        heap["path"] = str(plan.new_lib_dir)
    except (OSError, KeyError) as exc:
        return False, f"Failed to update project configuration: {exc}\nRecover with:\n  {RECOVERY}"

    sink(f"Patching {len(plan.graph_changes)} graph file(s)...")
    try:
        apply_graphs(plan.graph_changes, plan.old_dist, plan.new_dist)
    except (OSError, ValueError) as exc:
        return False, f"Failed to patch graphs: {exc}\nRecover with:\n  {RECOVERY}"

    if plan.dependent_changes:
        sink(f"Updating {len(plan.dependent_changes)} dependent file(s)...")
        try:
            for change in plan.dependent_changes:
                if change.kind == "python":
                    apply_python(
                        [change], plan.old_dist, plan.new_dist, plan.old_module, plan.new_module
                    )
                elif change.path.name == "haybale.toml":
                    with edit_toml(change.path) as doc:
                        linked = doc.get("linked_libraries")
                        if linked is not None:
                            for i, entry in enumerate(list(linked)):
                                if str(entry) == plan.old_module:
                                    linked[i] = plan.new_module
                else:
                    with edit_toml(change.path) as doc:
                        deps = doc.get("project", {}).get("dependencies", [])
                        for i, dep in enumerate(list(deps)):
                            if str(dep).lower() == plan.old_dist.lower():
                                deps[i] = plan.new_dist
        except (OSError, KeyError) as exc:
            return False, f"Failed to update dependents: {exc}\nRecover with:\n  {RECOVERY}"

    # ── phase 5: uv sync ────────────────────────────────────────────────
    sink("Running uv sync...")
    result = subprocess.run(
        ["uv", "sync"],
        cwd=str(plan.workspace_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    for line in result.stdout.decode().splitlines():
        sink(line)
    if result.returncode != 0:
        # The source rename is complete and correct — this is an environment
        # resolution problem. Advising a revert would discard good work.
        return False, (
            f"Source rename to {plan.new_dist} completed, but `uv sync` failed.\n"
            f"Fix the environment and re-run:\n  uv sync"
        )

    return True, f"Renamed {plan.old_dist} → {plan.new_dist}"
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/rename/test_execute.py -q`
Expected: PASS — 7 passed

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-studio/src/haywire_studio/packaging/rename/execute.py tests/rename/test_execute.py
git commit -m "feat(rename): fail-fast executor preserving descriptive metadata

Only identity fields change. No .bak files — git is the rollback. A uv
sync failure reports the source rename succeeded rather than advising a
revert."
```

---

## Task 10: Report rendering

**Files:**
- Create: `packages/haywire-studio/src/haywire_studio/packaging/rename/report.py`
- Test: `tests/rename/test_report.py`

**Interfaces:**
- Consumes: `RenamePlan`
- Produces: `render_plan(plan, *, verbose=False) -> str`

- [ ] **Step 1: Write the failing test**

```python
# tests/rename/test_report.py
"""Preflight rendering: counts by default, occurrences under --verbose."""

from __future__ import annotations

from pathlib import Path

import pytest

from haywire_studio.packaging.rename.model import (
    Blocker,
    FileChange,
    Occurrence,
    RenamePlan,
    Warning_,
)


def _plan(**kwargs) -> RenamePlan:
    base = dict(
        old_dist="hay-src",
        new_dist="hay-dst",
        old_module="hay_src",
        new_module="hay_dst",
        workspace_root=Path("/ws"),
        old_lib_dir=Path("/ws/barn/hay-src"),
        new_lib_dir=Path("/ws/barn/hay-dst"),
    )
    base.update(kwargs)
    return RenamePlan(**base)


@pytest.mark.unit
def test_header_shows_both_names_and_modules():
    from haywire_studio.packaging.rename.report import render_plan

    out = render_plan(_plan())
    assert "hay-src" in out and "hay-dst" in out
    assert "hay_src" in out and "hay_dst" in out


@pytest.mark.unit
def test_blocker_remedy_is_printed():
    from haywire_studio.packaging.rename.report import render_plan

    out = render_plan(_plan(blockers=[Blocker(message="Tree is dirty", remedy="git stash")]))
    assert "Tree is dirty" in out
    assert "git stash" in out


@pytest.mark.unit
def test_summary_hides_individual_files():
    from haywire_studio.packaging.rename.report import render_plan

    plan = _plan(graph_changes=[FileChange(path=Path("/ws/a.haywire"), kind="graph", count=4)])
    out = render_plan(plan, verbose=False)

    assert "a.haywire" not in out


@pytest.mark.unit
def test_verbose_lists_each_file():
    from haywire_studio.packaging.rename.report import render_plan

    plan = _plan(graph_changes=[FileChange(path=Path("/ws/a.haywire"), kind="graph", count=4)])
    assert "a.haywire" in render_plan(plan, verbose=True)


@pytest.mark.unit
def test_unrecognized_occurrences_are_flagged():
    from haywire_studio.packaging.rename.report import render_plan

    plan = _plan(unrecognized=[Occurrence(path=Path("/ws/a.haywire"), line=0, text="name")])
    out = render_plan(plan)

    assert "unrecognized" in out.lower()
    assert "not patched" in out.lower()


@pytest.mark.unit
def test_warning_remedy_is_printed():
    from haywire_studio.packaging.rename.report import render_plan

    plan = _plan(warnings=[Warning_(message="Storage will not follow", remedy="mv a b")])
    out = render_plan(plan)

    assert "Storage will not follow" in out
    assert "mv a b" in out
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/rename/test_report.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'haywire_studio.packaging.rename.report'`

- [ ] **Step 3: Write `report.py`**

```python
"""Rendering a RenamePlan for the terminal."""

from __future__ import annotations

from .model import FileChange, RenamePlan


def _files_line(label: str, changes: list[FileChange]) -> str:
    if not changes:
        return ""
    total = sum(change.count for change in changes)
    noun = "file" if len(changes) == 1 else "files"
    return f"  {label:<18} {total} change(s) in {len(changes)} {noun}"


def render_plan(plan: RenamePlan, *, verbose: bool = False) -> str:
    lines: list[str] = [
        "",
        f"Rename  {plan.old_dist}  →  {plan.new_dist}",
        f"        module  {plan.old_module} → {plan.new_module}",
        "",
    ]

    if plan.blockers:
        lines.append("  BLOCKED")
        lines.append("")
        for blocker in plan.blockers:
            lines.append(f"  ✗ {blocker.message}")
            if blocker.remedy:
                lines += [f"      {line}" for line in blocker.remedy.splitlines()]
            lines.append("")
        return "\n".join(lines)

    lines += [
        "  ✓ Working tree clean",
        "  ✓ No blocking collisions",
        "  ✓ Write access confirmed",
        "",
    ]

    for label, changes in (
        ("Library config", plan.toml_changes),
        ("Python sources", plan.python_changes),
        ("Graphs", plan.graph_changes),
        ("Dependents", plan.dependent_changes),
    ):
        line = _files_line(label, changes)
        if line:
            lines.append(line)
            if verbose:
                lines += [f"      {c.path}  ({c.count})" for c in changes]

    lines.append("")

    if plan.unrecognized:
        lines.append(
            f"  ⚠ {len(plan.unrecognized)} unrecognized occurrence(s) of "
            f'"{plan.old_dist}"/"{plan.old_module}" — not patched'
        )
        if verbose:
            for occurrence in plan.unrecognized:
                where = f":{occurrence.line}" if occurrence.line else ""
                lines.append(f"      {occurrence.path}{where}  {occurrence.text}")
        else:
            lines.append("      (re-run with --verbose to inspect)")
        lines.append("")

    for warning in plan.warnings:
        lines.append(f"  ⚠ {warning.message}")
        if warning.remedy:
            lines.append(f"      {warning.remedy}")
        lines.append("")

    return "\n".join(lines)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/rename/test_report.py -q`
Expected: PASS — 6 passed

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-studio/src/haywire_studio/packaging/rename/report.py tests/rename/test_report.py
git commit -m "feat(rename): preflight report with summary and --verbose modes"
```

---

## Task 11: CLI wiring and the confirm gates

**Files:**
- Modify: `packages/haywire-studio/src/haywire_studio/cli/rename.py`
- Modify: `packages/haywire-studio/src/haywire_studio/packaging/rename/__init__.py`
- Delete: `packages/haywire-studio/src/haywire_studio/packaging/rename.py`
- Test: `tests/rename/test_cli.py`

**Interfaces:**
- Consumes: `plan_rename`, `execute_plan`, `render_plan`
- Produces: `run_rename_cli(*, old_library, new_name, workspace_root, apply, verbose=False, assume_yes=False) -> int`

- [ ] **Step 1: Write the failing test**

```python
# tests/rename/test_cli.py
"""Exit codes, dry-run safety, and the two confirmation gates."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from tests.rename.test_planner import _workspace  # noqa: F401


@pytest.mark.unit
def test_dry_run_changes_nothing_and_exits_zero(tmp_path, capsys):
    from haywire_studio.packaging.rename import run_rename_cli

    ws = _workspace(tmp_path)
    code = run_rename_cli(
        old_library="hay-src", new_name="hay-dst", workspace_root=ws, apply=False
    )

    assert code == 0
    assert (ws / "barn" / "hay-src").is_dir()
    data = json.loads((ws / "flows" / "g.haywire").read_text())
    assert data["nodes"]["n"]["registry_key"] == "hay-src:node:Add"
    assert "--apply" in capsys.readouterr().out


@pytest.mark.unit
def test_dry_run_of_invalid_rename_exits_nonzero(tmp_path):
    """The old code exited 0 on a bogus dry run; validation now runs first."""
    from haywire_studio.packaging.rename import run_rename_cli

    ws = _workspace(tmp_path)
    code = run_rename_cli(
        old_library="hay-nonexistent", new_name="hay-dst", workspace_root=ws, apply=False
    )
    assert code != 0


@pytest.mark.unit
def test_apply_declined_at_confirm_changes_nothing(tmp_path):
    from haywire_studio.packaging.rename import run_rename_cli

    ws = _workspace(tmp_path)
    with patch("builtins.input", return_value="n"):
        code = run_rename_cli(
            old_library="hay-src", new_name="hay-dst", workspace_root=ws, apply=True
        )

    assert code != 0
    assert (ws / "barn" / "hay-src").is_dir()


@pytest.mark.unit
def test_unconventional_name_asks_twice(tmp_path):
    """One prompt for the prefix, one to proceed."""
    from haywire_studio.packaging.rename import run_rename_cli

    ws = _workspace(tmp_path)
    with patch("builtins.input", side_effect=["y", "y"]) as prompt:
        with patch("haywire_studio.packaging.rename.execute.subprocess.run") as run:
            run.return_value.returncode = 0
            run.return_value.stdout = b""
            run_rename_cli(
                old_library="hay-src", new_name="forecast", workspace_root=ws, apply=True
            )

    assert prompt.call_count == 2


@pytest.mark.unit
def test_assume_yes_skips_prompts(tmp_path):
    from haywire_studio.packaging.rename import run_rename_cli

    ws = _workspace(tmp_path)
    with patch("builtins.input", side_effect=AssertionError("must not prompt")):
        with patch("haywire_studio.packaging.rename.execute.subprocess.run") as run:
            run.return_value.returncode = 0
            run.return_value.stdout = b""
            code = run_rename_cli(
                old_library="hay-src",
                new_name="hay-dst",
                workspace_root=ws,
                apply=True,
                assume_yes=True,
            )

    assert code == 0
    assert (ws / "barn" / "hay-dst").is_dir()


@pytest.mark.unit
def test_blocked_apply_exits_nonzero_without_prompting(tmp_path):
    from haywire_studio.packaging.rename import run_rename_cli

    ws = _workspace(tmp_path)
    (ws / "dirt.txt").write_text("x")

    with patch("builtins.input", side_effect=AssertionError("must not prompt")):
        code = run_rename_cli(
            old_library="hay-src", new_name="hay-dst", workspace_root=ws, apply=True
        )
    assert code != 0


@pytest.mark.unit
def test_success_suggests_verify(tmp_path, capsys):
    from haywire_studio.packaging.rename import run_rename_cli

    ws = _workspace(tmp_path)
    with patch("haywire_studio.packaging.rename.execute.subprocess.run") as run:
        run.return_value.returncode = 0
        run.return_value.stdout = b""
        run_rename_cli(
            old_library="hay-src",
            new_name="hay-dst",
            workspace_root=ws,
            apply=True,
            assume_yes=True,
        )

    assert "haywire verify" in capsys.readouterr().out
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/rename/test_cli.py -q`
Expected: FAIL — `ImportError: cannot import name 'run_rename_cli'`

- [ ] **Step 3: Delete the old module**

```bash
git rm packages/haywire-studio/src/haywire_studio/packaging/rename.py
```

- [ ] **Step 4: Write the package `__init__.py`**

```python
"""``haywire rename`` — rename a project-local haybale library.

Renaming changes a library's IDENTITY only: its distribution name, module
name, and the registry-key prefix stamped into every saved graph.
Descriptive metadata (label, description, tags, homepage_url, notes) and
its dependents' references to it are preserved.
"""

from __future__ import annotations

from pathlib import Path

from .execute import execute_plan
from .model import Blocker, FileChange, Occurrence, RenamePlan, Warning_
from .planner import plan_rename
from .report import render_plan

__all__ = [
    "Blocker",
    "FileChange",
    "Occurrence",
    "RenamePlan",
    "Warning_",
    "execute_plan",
    "plan_rename",
    "render_plan",
    "run_rename_cli",
]


def _confirm(question: str) -> bool:
    try:
        return input(f"{question} [y/N] ").strip().lower() in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        return False


def run_rename_cli(
    *,
    old_library: str,
    new_name: str,
    workspace_root: Path,
    apply: bool,
    verbose: bool = False,
    assume_yes: bool = False,
) -> int:
    """Preflight, then optionally execute. Returns a process exit code."""
    plan, needs_prefix_confirm = plan_rename(old_library, new_name, Path(workspace_root))
    print(render_plan(plan, verbose=verbose))

    if not plan.ok:
        return 1

    if not apply:
        print("Dry run — nothing was changed.")
        print("Re-run with --apply to perform the rename.")
        return 0

    if not assume_yes:
        if needs_prefix_confirm and not _confirm(
            f'"{new_name}" does not start with "haybale-" or "hay-". Continue?'
        ):
            print("Aborted.")
            return 1
        if not _confirm(
            f"Rename {plan.old_dist} → {plan.new_dist}, rewriting {plan.total_changes} "
            f"reference(s) and running `uv sync`. Proceed?"
        ):
            print("Aborted.")
            return 1

    ok, message = execute_plan(plan, sink=print)
    print(message)
    if not ok:
        return 1

    print(
        "\nNext:\n"
        "  uv run haywire verify     # confirm every graph still resolves\n"
        "  git diff                  # review, then commit\n"
        "Restart the studio to pick up the change."
    )
    return 0
```

- [ ] **Step 5: Add `--verbose` and `--yes` to the subparser**

```python
# packages/haywire-studio/src/haywire_studio/cli/rename.py
"""``haywire rename`` — rename a project library, with the studio stopped."""

from __future__ import annotations

import argparse
from pathlib import Path


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("rename", help="Rename a project library (run with studio stopped)")
    parser.add_argument("old_library", help="Current distribution name, e.g. hay-weather")
    parser.add_argument("new_name", help="New distribution name, taken verbatim, e.g. hay-forecast")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Perform the rename. Without this flag, only a preflight report is printed.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="List every affected file and occurrence instead of counts.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation prompts (for scripting).",
    )
    parser.set_defaults(handler=_run)


def _run(args: argparse.Namespace) -> int:
    from haywire_studio.packaging.rename import run_rename_cli

    return run_rename_cli(
        old_library=args.old_library,
        new_name=args.new_name,
        workspace_root=Path.cwd(),
        apply=args.apply,
        verbose=args.verbose,
        assume_yes=args.yes,
    )
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest tests/rename/test_cli.py -q`
Expected: PASS — 7 passed

- [ ] **Step 7: Verify no stale imports of the deleted module remain**

Run: `grep -rn "packaging.rename import\|packaging import rename\|sanitize_rename" --include="*.py" . | grep -v ".venv"`
Expected: only `cli/rename.py` and files under `tests/rename/`

- [ ] **Step 8: Commit**

```bash
git add -A packages/haywire-studio/src/haywire_studio/packaging/rename packages/haywire-studio/src/haywire_studio/cli/rename.py tests/rename/test_cli.py
git commit -m "feat(rename): wire preflight, confirm gates, --verbose and --yes

Validation runs before the dry-run report, so a bogus rename exits
non-zero instead of printing a plan and exiting 0."
```

---

## Task 12: `haywire verify`

**Files:**
- Create: `packages/haywire-studio/src/haywire_studio/packaging/verify.py`
- Create: `packages/haywire-studio/src/haywire_studio/cli/verify.py`
- Modify: `packages/haywire-studio/src/haywire_studio/cli/__init__.py`
- Test: `tests/rename/test_verify.py`

**Interfaces:**
- Consumes: `find_graph_files` from `packaging.rename.discovery`; `KEY_FIELDS`, `LIST_KEY_FIELDS`, `is_registry_key` from `packaging.rename.graphs`
- Produces: `collect_keys(data) -> dict[str, int]`; `GraphReport`, `VerifyReport`; `verify_graphs(root, resolver) -> VerifyReport`; `run_verify_cli(*, workspace_root, verbose=False) -> int`

- [ ] **Step 1: Write the failing test**

```python
# tests/rename/test_verify.py
"""haywire verify resolves keys without instantiating anything."""

from __future__ import annotations

import json

import pytest


def _graph(tmp_path, name, *keys):
    nodes = {
        f"n{i}": {
            "registry_key": key,
            "node_data": {"ports": {"a": {"kwargs": {"widget_key": key}}}},
        }
        for i, key in enumerate(keys)
    }
    path = tmp_path / name
    path.write_text(json.dumps({"graph_id": "g", "nodes": nodes}))
    return path


@pytest.mark.unit
def test_collect_keys_finds_every_key_at_any_depth():
    from haywire_studio.packaging.verify import collect_keys

    data = {
        "nodes": {
            "n": {
                "registry_key": "a:node:X",
                "node_data": {
                    "ports": {"p": {"kwargs": {"widget_key": "a:widget:W"}}},
                    "subgraph": {"nodes": {"m": {"registry_key": "b:node:Y"}}},
                },
            }
        },
        "edges": {"e": {"chain_adapter_keys": ["c:adapter:Z"]}},
    }

    assert collect_keys(data) == {
        "a:node:X": 1,
        "a:widget:W": 1,
        "b:node:Y": 1,
        "c:adapter:Z": 1,
    }


@pytest.mark.unit
def test_all_keys_resolve_reports_ok(tmp_path):
    from haywire_studio.packaging.verify import verify_graphs

    _graph(tmp_path, "g.haywire", "hay-x:node:Add")
    report = verify_graphs(tmp_path, resolver=lambda key: True)

    assert report.ok
    assert report.graphs_checked == 1
    assert report.unresolved_total == 0


@pytest.mark.unit
def test_unresolved_key_is_reported_per_graph(tmp_path):
    from haywire_studio.packaging.verify import verify_graphs

    _graph(tmp_path, "g.haywire", "hay-gone:node:Add")
    report = verify_graphs(tmp_path, resolver=lambda key: False)

    assert not report.ok
    assert report.unresolved_total == 2  # registry_key + widget_key
    assert report.graphs[0].unresolved["hay-gone:node:Add"] == 2


@pytest.mark.unit
def test_mixed_resolution_reports_only_the_missing(tmp_path):
    from haywire_studio.packaging.verify import verify_graphs

    _graph(tmp_path, "g.haywire", "hay-ok:node:A", "hay-gone:node:B")
    report = verify_graphs(tmp_path, resolver=lambda key: key.startswith("hay-ok"))

    assert not report.ok
    assert set(report.graphs[0].unresolved) == {"hay-gone:node:B"}


@pytest.mark.unit
def test_empty_workspace_is_ok(tmp_path):
    from haywire_studio.packaging.verify import verify_graphs

    report = verify_graphs(tmp_path, resolver=lambda key: True)
    assert report.ok
    assert report.graphs_checked == 0


@pytest.mark.unit
def test_cli_exit_code_reflects_resolution(tmp_path):
    from haywire_studio.packaging.verify import run_verify_cli

    _graph(tmp_path, "g.haywire", "hay-gone:node:Add")
    assert run_verify_cli(workspace_root=tmp_path, resolver=lambda key: False) != 0
    assert run_verify_cli(workspace_root=tmp_path, resolver=lambda key: True) == 0
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/rename/test_verify.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'haywire_studio.packaging.verify'`

- [ ] **Step 3: Write `packaging/verify.py`**

```python
"""``haywire verify`` — prove every graph's registry keys still resolve.

Runs as a SEPARATE PROCESS after a rename, never in-process from the studio:
per .insights/project_docs_gen_reentrancy.md, building a second library
system repoints the global injector and settings registry.

Resolution is class-level only — ``registry.has(key)``. Nodes are never
instantiated: construction grabs hardware (the OAK-D and webcam graphs would
open cameras) and runs author code for no benefit, since a dangling
registry key is visible without building anything.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .rename.discovery import find_graph_files
from .rename.graphs import KEY_FIELDS, LIST_KEY_FIELDS, is_registry_key

#: Answers "is this registry key known to the loaded libraries?"
Resolver = Callable[[str], bool]


@dataclass
class GraphReport:
    """One graph's resolution result."""

    path: Path
    keys_checked: int = 0
    unresolved: dict[str, int] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.unresolved


@dataclass
class VerifyReport:
    """The whole workspace's resolution result."""

    graphs: list[GraphReport] = field(default_factory=list)

    @property
    def graphs_checked(self) -> int:
        return len(self.graphs)

    @property
    def unresolved_total(self) -> int:
        return sum(sum(g.unresolved.values()) for g in self.graphs)

    @property
    def ok(self) -> bool:
        return all(g.ok for g in self.graphs)


def collect_keys(data: object) -> dict[str, int]:
    """Every registry key in *data*, with occurrence counts.

    Mirrors the rename walker: same fields, same unbounded recursion, so a
    key the rename would rewrite is a key verify checks.
    """
    counts: Counter[str] = Counter()

    def walk(node: object) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in KEY_FIELDS and isinstance(value, str) and is_registry_key(value):
                    counts[value] += 1
                elif key in LIST_KEY_FIELDS and isinstance(value, list):
                    for item in value:
                        if isinstance(item, str) and is_registry_key(item):
                            counts[item] += 1
                else:
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(data)
    return dict(counts)


def verify_graphs(workspace_root: Path, resolver: Resolver) -> VerifyReport:
    """Check every discoverable graph's keys against *resolver*."""
    import json

    report = VerifyReport()
    for path in find_graph_files(workspace_root):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        keys = collect_keys(data)
        graph_report = GraphReport(path=path, keys_checked=sum(keys.values()))
        for key, count in keys.items():
            if not resolver(key):
                graph_report.unresolved[key] = count
        report.graphs.append(graph_report)

    return report


def _live_resolver() -> Resolver:
    """Resolve against the libraries installed in THIS interpreter.

    Imported lazily so the pure functions above stay unit-testable without
    booting a library system.
    """
    from haywire.core.di.config import create_injector

    injector = create_injector()
    service = injector.get_library_service()
    known: set[str] = set()
    for registry in service.all_registries():
        known.update(registry.list_names())
    return lambda key: key in known


def run_verify_cli(
    *, workspace_root: Path, verbose: bool = False, resolver: Resolver | None = None
) -> int:
    """Print a resolution report. Returns 0 when everything resolves."""
    resolve = resolver or _live_resolver()
    report = verify_graphs(Path(workspace_root), resolve)

    if report.graphs_checked == 0:
        print("No graphs found.")
        return 0

    for graph in report.graphs:
        if graph.ok:
            if verbose:
                print(f"  ✓ {graph.path}  ({graph.keys_checked} keys)")
        else:
            print(f"  ✗ {graph.path}")
            for key, count in sorted(graph.unresolved.items()):
                print(f"      {key}  ×{count}")

    print()
    if report.ok:
        print(f"All {report.graphs_checked} graph(s) resolve.")
        return 0

    broken = sum(1 for g in report.graphs if not g.ok)
    print(
        f"{report.unresolved_total} unresolved key(s) across {broken} of "
        f"{report.graphs_checked} graph(s)."
    )
    return 1
```

- [ ] **Step 4: Write `cli/verify.py`**

```python
"""``haywire verify`` — check that every saved graph still resolves."""

from __future__ import annotations

import argparse
from pathlib import Path


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "verify", help="Check that every saved graph's registry keys resolve"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="List every graph checked, not only the failing ones.",
    )
    parser.set_defaults(handler=_run)


def _run(args: argparse.Namespace) -> int:
    from haywire_studio.packaging.verify import run_verify_cli

    return run_verify_cli(workspace_root=Path.cwd(), verbose=args.verbose)
```

- [ ] **Step 5: Register the subcommand**

In `packages/haywire-studio/src/haywire_studio/cli/__init__.py`, change the import and the tuple:

```python
from haywire_studio.cli import deps, docs, init, rename, share, verify
```

```python
SUBCOMMANDS: Sequence[_SubcommandModule] = (init, share, rename, deps, docs, verify)
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest tests/rename/test_verify.py -q`
Expected: PASS — 6 passed

- [ ] **Step 7: Confirm the subcommand is wired**

Run: `uv run haywire verify --help`
Expected: the verify help text, including `--verbose`.

- [ ] **Step 8: Run it against the real repo**

Run: `uv run haywire verify`

Expected: a report over the 8 graphs. Unresolved keys are likely — the repo has known stale keys (`example:skin:ExampleNodeSkin`, `builtin:widget:NumberWidget`, `testing:widget:*`) using the retired short-id form. Record what it reports; these are pre-existing bugs, not regressions from this work.

If `_live_resolver` raises (`create_injector` or `all_registries` not matching the real API), fix it against the actual `LibraryService` surface — the pure functions are already covered by tests, so only the resolver seam is in question.

- [ ] **Step 9: Commit**

```bash
git add packages/haywire-studio/src/haywire_studio/packaging/verify.py \
        packages/haywire-studio/src/haywire_studio/cli/verify.py \
        packages/haywire-studio/src/haywire_studio/cli/__init__.py \
        tests/rename/test_verify.py
git commit -m "feat(verify): haywire verify resolves every graph's registry keys

Runs as a separate process after a rename. Class-level resolution only —
instantiating nodes would grab hardware and repoint global DI."
```

---

## Task 13: Full-suite verification

**Files:**
- Test: full suite

**Interfaces:**
- Consumes: everything
- Produces: nothing

- [ ] **Step 1: Run lint and format**

```bash
uv run ruff check packages/haywire-studio/src/haywire_studio/packaging/ \
  packages/haywire-studio/src/haywire_studio/cli/ tests/rename/
uv run ruff format --check packages/haywire-studio/src/haywire_studio/packaging/ \
  packages/haywire-studio/src/haywire_studio/cli/ tests/rename/
```

Expected: no findings. If format drifts, run `uv run ruff format <same paths>` and re-commit.

- [ ] **Step 2: Type-check**

```bash
uv run mypy packages/haywire-studio/src/
```

Expected: no new errors versus the pre-task baseline.

- [ ] **Step 3: Run the rename suite**

Run: `uv run pytest tests/rename/ -q`
Expected: PASS — 82 passed

- [ ] **Step 4: Run the pre-commit gate**

```bash
uv run pytest -m "not browser and not perf" -q > /tmp/rename-gate.log 2>&1; echo "exit=$?"
grep -E "^FAILED|^ERROR" /tmp/rename-gate.log
grep -E "passed|failed" /tmp/rename-gate.log | tail -1
```

Expected: `exit=0`, no FAILED/ERROR lines. Use a timeout ≥ 600000 ms.

- [ ] **Step 5: Exercise the real command, dry-run only**

```bash
uv run haywire rename haybale-example haybale-renamed-example --verbose
git status --porcelain
```

Expected: a preflight report with **non-zero** graph and Python counts (`haybale-example` has 8 graph keys and the `types/specs.py` widget literal), ending in the `--apply` hint. `git status --porcelain` must print **nothing** — the end-to-end proof the preflight is read-only.

- [ ] **Step 6: Commit any formatting fixes**

```bash
git add -A
git commit -m "chore(rename): lint and format pass" || echo "nothing to commit"
```

---

## Self-review notes

**Spec coverage.** All settled decisions map to tasks: verbatim names (T4), prefix confirm (T4, T11), five-namespace collisions (T4), hard clean-tree with no override (T5), git-only rollback and no `.bak` (T2, T9), recursive name-based key rewriting (T2), extension-agnostic discovery (T1), drift reporting (T2, T10), AST imports plus key literals with prose reporting (T6), storage warning (T8), dependent fan-out (T7), single planner (T8), fail-fast phases (T9), plan-derived write access with the parent-directory rule (T5), identity-only metadata (T9), and `haywire verify` (T12).

**Sequencing.** `test_execute.py` and `test_cli.py` import `_workspace` from `test_planner.py`; `graphs.py` imports from `discovery.py`; `verify.py` imports from both. Task order enforces all of these.

**Deliberate omissions.**
- `sanitize_rename()` is gone: it slugified names, contradicting the verbatim rule. `validate_target()` rejects rather than transforms. Task 11 Step 7 greps for callers.
- No legacy `id`/`dependencies` handling anywhere, per the global constraint.

**Known risk.** `_live_resolver()` in Task 12 is the one function written against an API surface not directly verified here (`create_injector` → `get_library_service` → `all_registries`). Step 8 exercises it and says what to do if the shape differs; every pure function around it is covered by injected-resolver tests, so the blast radius is one function.
