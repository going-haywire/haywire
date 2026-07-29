# NodeInstanceInspector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce a core `NodeInstanceInspector` that wraps a live `BaseNode` instance and answers its port/setting *schema* questions, then converge the existing `GraphEditorInspectNode` tool onto it so there is one port/setting walker instead of two.

**Architecture:** The inspector is a thin, read-only question-answerer over an already-constructed `BaseNode` — it does **not** instantiate anything (the caller owns the instance) and it reports only the static authored schema (labels, types, defaults, validators), never live wiring (`is_linked`, current values, promotion). Live overlay stays in `GraphEditorInspectNode`, which after this plan builds its rows *on top of* the inspector's `PortInfo`/`SettingInfo` dataclasses. This is the shared engine that a later plan's `haywire docs` generator and `StudioDescribeComponent` reuse.

**Tech Stack:** Python 3.10+, dataclasses, pytest (anyio for the Farmhand tool tests), the haywire DI framework (`test_injector` fixture), ruff, mypy.

## Global Constraints

- Line length = 109 (ruff).
- CI runs BOTH `ruff check` and `ruff format --check` — run both locally.
- mypy must stay clean on `packages/haywire-core/src/` and `barn/haybale-graph-editor/`.
- Fast test loop: `uv run pytest -m "not browser and not perf"`.
- The inspector lives in `haywire-core` and imports nothing from any `barn/` package (barns depend on core, never the reverse).
- The inspector NEVER constructs a node, never reads `port.get_value()`, `port.is_linked()`, `port.promoted`, or any settings *value* — those are live-state, out of scope. It reads only class/instance *schema*.
- Never call `create_test_injector()` directly in a test — use the `test_injector` fixture (see `tests/conftest.py:258` and the ambient-DI trap in `.insights/project_playwright_asyncio_order_trap.md`).

---

## File Structure

- Create: `packages/haywire-core/src/haywire/core/node/inspector.py` — the `NodeInstanceInspector` + `PortInfo` + `SettingInfo` dataclasses. One responsibility: answer schema questions about one node instance.
- Create: `tests/core/test_node/test_inspector.py` — unit tests for the inspector against real, library-loaded node instances.
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/farmhands/editor_tools.py` — `_port_type_key`, `_port_row`, `_inspect_port_row`, `_settings_payload`, `_inspect_setting_row` re-expressed on top of the inspector.

**Interfaces produced by this plan (later plans rely on these exact names/types):**

```python
# packages/haywire-core/src/haywire/core/node/inspector.py

@dataclass(frozen=True)
class PortInfo:
    id: str
    direction: str            # "inlet" | "outlet"
    label: str
    description: str
    flow_type: str            # port.flow_type.value: "data" | "control" | "callback" | "none"
    data_type: str | None     # the type's registry_key, or None
    hidden: bool
    deprecation: str

@dataclass(frozen=True)
class SettingInfo:
    name: str
    bag: str                  # the accessor attribute name on the node
    label: str
    description: str
    category: str             # "root" when the author set none
    default: Any              # callable defaults already resolved
    type_name: str | None     # descriptor._type.__name__, or None
    validator_name: str | None
    validator_doc: str | None # first line of the validator's docstring, or None

class NodeInstanceInspector:
    def __init__(self, node: BaseNode) -> None: ...
    def ports(self) -> list[PortInfo]: ...
    def settings(self) -> list[SettingInfo]: ...
```

---

### Task 1: `PortInfo` + `NodeInstanceInspector.ports()`

**Files:**
- Create: `packages/haywire-core/src/haywire/core/node/inspector.py`
- Test: `tests/core/test_node/test_inspector.py`

**Interfaces:**
- Consumes: `BaseNode.ports: dict[str, DataPort]`; `DataPort.label/.description/.hidden/.deprecation_warning`, `DataPort.flow_type.value`, `DataPort.is_inlet()`, `DataPort.type_cls.class_identity.registry_key`.
- Produces: `PortInfo`, `NodeInstanceInspector(node).ports() -> list[PortInfo]`.

- [ ] **Step 1: Write the failing test**

Uses the same library-loaded graph pattern as `tests/core/test_node/test_base.py`: build a graph from the test library system, create a real node wrapper, wrap its `.node` in the inspector.

```python
# tests/core/test_node/test_inspector.py
from haywire.core.node.inspector import NodeInstanceInspector, PortInfo


def test_ports_returns_portinfo_with_schema_shape(graph_with_library_system):
    graph = graph_with_library_system
    available = graph.node_registry.list_visible_names()
    key = next(k for k in available if k.split(":")[1] == "node")

    wrapper = graph.create_node_wrapper(key, position=(0, 0))
    inspector = NodeInstanceInspector(wrapper.node)

    ports = inspector.ports()
    assert isinstance(ports, list)
    for p in ports:
        assert isinstance(p, PortInfo)
        assert isinstance(p.id, str) and p.id
        assert p.direction in ("inlet", "outlet")
        assert p.flow_type in ("data", "control", "callback", "none")
        assert isinstance(p.hidden, bool)
```

If a `graph_with_library_system` fixture does not exist in scope, add it to `tests/core/test_node/conftest.py` mirroring the construction in `tests/core/test_node/test_base.py` (build a `BaseGraph` from `create_test_library_system(test_injector)`); reuse that test's exact fixture wiring — do not invent a new injector path.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_node/test_inspector.py::test_ports_returns_portinfo_with_schema_shape -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'haywire.core.node.inspector'`

- [ ] **Step 3: Write minimal implementation**

```python
# packages/haywire-core/src/haywire/core/node/inspector.py
"""Read-only schema introspection over a single live BaseNode instance.

Answers "what ports/settings does this node declare" from an already-built
instance. Does NOT construct nodes and does NOT read live state (values,
links, promotion) — that overlay belongs to callers that hold a NodeWrapper.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from haywire.core.node.base import BaseNode


@dataclass(frozen=True)
class PortInfo:
    id: str
    direction: str
    label: str
    description: str
    flow_type: str
    data_type: str | None
    hidden: bool
    deprecation: str


def _port_type_key(port: Any) -> str | None:
    """The concrete data-type registry key, or None.

    Defensive: type_cls or its class_identity can be absent on edge cases, so
    miss quietly rather than raise inside a read-only inspector.
    """
    identity = getattr(port.type_cls, "class_identity", None)
    return getattr(identity, "registry_key", None)


class NodeInstanceInspector:
    """Wrap a built BaseNode and answer its schema questions."""

    def __init__(self, node: "BaseNode") -> None:
        self._node = node

    def ports(self) -> list[PortInfo]:
        rows: list[PortInfo] = []
        for pid, port in self._node.ports.items():
            rows.append(
                PortInfo(
                    id=pid,
                    direction="inlet" if port.is_inlet() else "outlet",
                    label=port.label or "",
                    description=port.description or "",
                    flow_type=port.flow_type.value,
                    data_type=_port_type_key(port),
                    hidden=bool(port.hidden),
                    deprecation=port.deprecation_warning or "",
                )
            )
        return rows
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/test_node/test_inspector.py::test_ports_returns_portinfo_with_schema_shape -v`
Expected: PASS

- [ ] **Step 5: Lint, type-check, commit**

```bash
uv run ruff check packages/haywire-core/src/haywire/core/node/inspector.py tests/core/test_node/test_inspector.py
uv run ruff format packages/haywire-core/src/haywire/core/node/inspector.py tests/core/test_node/test_inspector.py
uv run mypy packages/haywire-core/src/haywire/core/node/inspector.py
git add packages/haywire-core/src/haywire/core/node/inspector.py tests/core/test_node/test_inspector.py
git commit -m "feat(introspect): NodeInstanceInspector.ports() over a live node instance

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AHzvrVo7ngFfubhzjWqZU7"
```

---

### Task 2: `SettingInfo` + `NodeInstanceInspector.settings()`

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/node/inspector.py`
- Test: `tests/core/test_node/test_inspector.py`

**Interfaces:**
- Consumes: `BaseNode.list_setting_bags() -> dict[str, Settings]`; `type(bag)._property_settings() -> dict[str, descriptor]`; descriptor `._label/._description/._category/._default/._validator/._type`.
- Produces: `SettingInfo`, `NodeInstanceInspector(node).settings() -> list[SettingInfo]`.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/core/test_node/test_inspector.py
from haywire.core.node.inspector import SettingInfo


def test_settings_returns_settinginfo_with_resolved_defaults(graph_with_library_system):
    graph = graph_with_library_system
    # Find a node that declares at least one settings bag, else the assertion
    # set is vacuous but still valid (empty list is a legal answer).
    key = next(
        k for k in graph.node_registry.list_visible_names() if k.split(":")[1] == "node"
    )
    wrapper = graph.create_node_wrapper(key, position=(0, 0))
    inspector = NodeInstanceInspector(wrapper.node)

    settings = inspector.settings()
    assert isinstance(settings, list)
    for s in settings:
        assert isinstance(s, SettingInfo)
        assert isinstance(s.name, str) and s.name
        assert isinstance(s.bag, str) and s.bag
        assert isinstance(s.category, str) and s.category  # never "" — "root" default
        # default must be a plain value, never a zero-arg callable left unresolved
        assert not callable(s.default)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_node/test_inspector.py::test_settings_returns_settinginfo_with_resolved_defaults -v`
Expected: FAIL with `ImportError: cannot import name 'SettingInfo'`

- [ ] **Step 3: Write minimal implementation**

Add to `inspector.py` — the `SettingInfo` dataclass and the `settings()` method. Mirror the descriptor reads from `_inspect_setting_row` in `editor_tools.py` (label/description/category/default/validator), resolving callable defaults.

```python
# add near PortInfo
@dataclass(frozen=True)
class SettingInfo:
    name: str
    bag: str
    label: str
    description: str
    category: str
    default: Any
    type_name: str | None
    validator_name: str | None
    validator_doc: str | None


def _validator_fields(descriptor: Any) -> tuple[str | None, str | None]:
    validator = getattr(descriptor, "_validator", None)
    if validator is None:
        return None, None
    name = getattr(validator, "__name__", None)
    doc_lines = (getattr(validator, "__doc__", None) or "").strip().splitlines()
    doc = doc_lines[0].strip() if doc_lines else None
    return name, doc
```

```python
# add as a method on NodeInstanceInspector
    def settings(self) -> list[SettingInfo]:
        rows: list[SettingInfo] = []
        for accessor, bag in self._node.list_setting_bags().items():
            for name, descriptor in type(bag)._property_settings().items():
                default = descriptor._default
                resolved = default() if callable(default) else default
                itype = getattr(descriptor, "_type", None)
                vname, vdoc = _validator_fields(descriptor)
                rows.append(
                    SettingInfo(
                        name=name,
                        bag=accessor,
                        label=descriptor._label or "",
                        description=descriptor._description or "",
                        category=descriptor._category or "root",
                        default=resolved,
                        type_name=getattr(itype, "__name__", None),
                        validator_name=vname,
                        validator_doc=vdoc,
                    )
                )
        return rows
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/test_node/test_inspector.py -v`
Expected: PASS (both inspector tests)

- [ ] **Step 5: Lint, type-check, commit**

```bash
uv run ruff check packages/haywire-core/src/haywire/core/node/inspector.py tests/core/test_node/test_inspector.py
uv run ruff format packages/haywire-core/src/haywire/core/node/inspector.py tests/core/test_node/test_inspector.py
uv run mypy packages/haywire-core/src/haywire/core/node/inspector.py
git add packages/haywire-core/src/haywire/core/node/inspector.py tests/core/test_node/test_inspector.py
git commit -m "feat(introspect): NodeInstanceInspector.settings() with resolved defaults

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AHzvrVo7ngFfubhzjWqZU7"
```

---

### Task 3: Converge `GraphEditorInspectNode` port walking onto the inspector

**Files:**
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/farmhands/editor_tools.py` (`_port_type_key` at line 58, `_port_row` at ~76, `_inspect_port_row` at ~189)
- Test: `tests/` — the existing InspectNode/QueryGraph tests must stay green (no new test; this is a refactor guarded by existing coverage).

**Interfaces:**
- Consumes: `NodeInstanceInspector(node).ports() -> list[PortInfo]` (Task 1).
- Produces: no new public surface; the tool's JSON output is unchanged.

- [ ] **Step 1: Establish the green baseline**

Run: `uv run pytest tests/ -k "inspect_node or query_graph" -m "not browser and not perf" -v`
Expected: PASS (record the count; this is the regression gate for the refactor).

- [ ] **Step 2: Delete the duplicated helper and import the core one**

Remove the local `_port_type_key` (lines 58–67) from `editor_tools.py` and import it from core instead. At the top of `editor_tools.py`, add:

```python
from haywire.core.node.inspector import NodeInstanceInspector, PortInfo
from haywire.core.node.inspector import _port_type_key  # single source of the type-key rule
```

- [ ] **Step 3: Re-express the `info`-depth port row on `PortInfo`**

In `_inspect_port_row`, the `data == "info"` branch currently reads `port.label/.description/.flow_type.value/_port_type_key(port)` field-by-field. Replace that branch's body so it builds from a `PortInfo` computed once. Keep the hidden-collapse and live-state (`data != "info"`) branches exactly as they are — those read `get_value()`/`is_linked()`/`promoted`, which are live overlay and stay in this tool.

```python
def _inspect_port_row(pid: str, port, data: str, expand: bool = False) -> dict:
    row: dict = {"name": pid}
    if port.hidden and not expand:
        return {"name": pid, "hidden": True}
    if data == "info":
        info = PortInfo(
            id=pid,
            direction="inlet" if port.is_inlet() else "outlet",
            label=port.label or "",
            description=port.description or "",
            flow_type=port.flow_type.value,
            data_type=_port_type_key(port),
            hidden=bool(port.hidden),
            deprecation=port.deprecation_warning or "",
        )
        row["label"] = info.label
        row["description"] = info.description
        row["flow_type"] = info.flow_type
        row["data_type"] = info.data_type
        if info.hidden:
            row["hidden"] = True
        if info.deprecation:
            row["deprecated"] = info.deprecation
        return row
    # ... live-state branch unchanged ...
```

- [ ] **Step 4: Run the regression gate**

Run: `uv run pytest tests/ -k "inspect_node or query_graph" -m "not browser and not perf" -v`
Expected: PASS with the same count as Step 1.

- [ ] **Step 5: Lint, type-check, commit**

```bash
uv run ruff check barn/haybale-graph-editor/haybale_graph_editor/farmhands/editor_tools.py
uv run ruff format barn/haybale-graph-editor/haybale_graph_editor/farmhands/editor_tools.py
uv run mypy barn/haybale-graph-editor/
git add barn/haybale-graph-editor/haybale_graph_editor/farmhands/editor_tools.py
git commit -m "refactor(farmhand): inspect_node port walking builds on NodeInstanceInspector

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AHzvrVo7ngFfubhzjWqZU7"
```

---

### Task 4: Converge `GraphEditorInspectNode` settings walking onto the inspector

**Files:**
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/farmhands/editor_tools.py` (`_inspect_setting_row` at ~233, `_settings_payload` at ~378)
- Test: existing InspectNode settings tests are the regression gate.

**Interfaces:**
- Consumes: `NodeInstanceInspector(node).settings() -> list[SettingInfo]` (Task 2).
- Produces: no new public surface.

- [ ] **Step 1: Establish the green baseline**

Run: `uv run pytest tests/ -k "inspect_node and setting" -m "not browser and not perf" -v`
Expected: PASS (record the count).

- [ ] **Step 2: Build a name→SettingInfo lookup in `_settings_payload`**

At the top of `_settings_payload`, build the inspector's view once and key it by `(bag, name)` so the `info`-depth branch can read label/description/category/default/validator from it instead of re-deriving from the descriptor. Leave the live-state fields (`is_set`, `is_mirror`, `promoted_as`, `ui_state`, constraints) reading from the bag/descriptor as they do now — those are live overlay.

```python
def _settings_payload(node, accessors, data, filters):
    from haywire.core.node.inspector import NodeInstanceInspector

    schema = {(s.bag, s.name): s for s in NodeInstanceInspector(node).settings()}
    # ... existing loop, but the info-depth row reads label/description/category
    #     from schema[(accessor, name)] rather than descriptor._label etc. ...
```

- [ ] **Step 3: Re-express the `info`-depth settings row on `SettingInfo`**

In `_inspect_setting_row`, the `data == "info"` branch currently reads `descriptor._label/._description/._category`. Have the caller pass the matching `SettingInfo` (or look it up) and read those three from it. The `data == "value"`/`"all"` branches (which read the live `getattr(bag, name)`, `is_set`, ui_state, constraints) stay unchanged.

Concretely, thread the `SettingInfo` through: change the `info`-branch of `_inspect_setting_row` to accept the row's schema entry and set `row["label"] = info.label`, `row["description"] = info.description`, `row["category"] = info.category`.

- [ ] **Step 4: Run the regression gate + full fast suite**

```bash
uv run pytest tests/ -k "inspect_node and setting" -m "not browser and not perf" -v
uv run pytest -m "not browser and not perf"
```
Expected: settings gate PASS with the Step-1 count; full fast suite green.

- [ ] **Step 5: Lint, type-check, commit**

```bash
uv run ruff check barn/haybale-graph-editor/haybale_graph_editor/farmhands/editor_tools.py
uv run ruff format --check barn/haybale-graph-editor/haybale_graph_editor/farmhands/editor_tools.py
uv run mypy packages/haywire-core/src/ barn/haybale-graph-editor/
git add barn/haybale-graph-editor/haybale_graph_editor/farmhands/editor_tools.py
git commit -m "refactor(farmhand): inspect_node settings walking builds on NodeInstanceInspector

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AHzvrVo7ngFfubhzjWqZU7"
```

---

## Self-Review

**Spec coverage** (against the settled design, inspector subsystem):
- Inspector wraps an instance, does not instantiate → Task 1 `__init__(node)`, caller passes `wrapper.node`. ✓
- Static schema only, no live state → constraint enforced; live reads stay in `editor_tools`. ✓
- Node-only (other 10 kinds read from the class) → inspector is node-typed; out of scope for this plan. ✓
- One walker, InspectNode converged now (Q5-A) → Tasks 3 & 4. ✓
- Shared type-key rule single-sourced → Task 3 Step 2 deletes the barn copy, imports core `_port_type_key`. ✓

**Placeholder scan:** No TBD/TODO; every code step shows the code; the one conditional ("if the fixture does not exist") points at a concrete existing test to mirror, not a vague instruction.

**Type consistency:** `PortInfo`/`SettingInfo`/`NodeInstanceInspector.ports()/.settings()` names identical across Tasks 1–4 and the interface header. `_port_type_key` imported in Task 3 is the same symbol defined in Task 1.

**Carried risk:** headless node instantiation needs a DI-context graph. Task 1 Step 1 resolves it by reusing the `test_injector` + library-system graph pattern from `tests/core/test_node/test_base.py`; if `create_node_wrapper` fails for a given node outside a full session, narrow the test to a known-simple node from `haybale_testing` (e.g. `TestPrintNode`) rather than the first available.
