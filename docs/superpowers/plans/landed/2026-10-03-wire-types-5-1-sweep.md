# Wire types and the FlowType sweep (edge-kinds step 5.1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` (recommended) or `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every port and edge takes its wire type from its data type, framework code asks a wire type's role instead of a `FlowType`, and `FlowType` is deleted. Behaviour stays as it is, apart from the decided changes listed under Global Constraints.

**Architecture:** A wire type is a class that is never instantiated (the Surface pattern, ADR 0009). `haywire.core.types.wire` holds `WireRole`, the `WireType` base with its id map, and the helpers `wire_type_of` and `wires_match`. Builtin ships `DataWire`, `ControlWire` and `CallbackWire` in `haywire.barn.builtin.wires`. `@type(wire_type=…)` stores the wire type on the type's identity. `DataPort.wire_type` is derived from the port's type and is never passed or saved. An edge's wire type is derived from its ports. The sweep runs expand, migrate, contract, so every task leaves the suite green:

1. Tasks 1-2 add the model and derive it, while `FlowType` stays and is filled from the declared wire type.
2. Tasks 4-9 move every reader to wire types.
3. Task 10 deletes `FlowType`.

**Tech Stack:** Python 3.12, pytest (+ xdist, Playwright browser tier), uv, ruff, mypy; Vue 3 (`canvas.vue`) for the pin attributes; NiceGUI for the edge panels.

**Settled in:** [2026-10-02-wire-types.md](../2026-10-02-wire-types.md), the step 5 design. The decisions this plan implements are Q2, Q3, Q5, Q7a-d, Q8a, Q9b, Q12, Q15 (deletions 1-8, 10-12) and Q19, Q20, Q29, Q30, Q31. Its review and second inquisition (2026-10-03) moved Q8b, Q21 and the ADD↔ADD refusal into 5.2.

## Global Constraints

- **Two repos.**
  - This repo: `/Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo`.
  - haybale-visiongraph: `/Volumes/Ddrive/06_open_tracking_tool/haywire/haybale-visiongraph`, linked here as the symlink `barn/haybale-visiongraph`. Edit its files through the symlink; run git for them in the visiongraph repo.
- **Branch.** `wire-types-5-1` in both repos, created from `master` in Task 0. Never push; the user pushes.
- **Commit trailer.** Every commit message ends with `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- **Uncommitted user changes.** They exist under `docs/superpowers/plans/` and in `internals/handoff/graph-loop-benchmark-drift.md`, and must never be committed by this plan. Always `git add` explicit paths, never `-A` or `.`. This plan file and `2026-10-02-wire-types.md` are also left for the user to commit.
- **Commit `barn/haybale-testing/` first.** Commit every change there before running the full suite: `tests/studio/test_docs/test_generate.py` runs `git checkout -- barn/haybale-testing` in its teardown.
- **Behaviour-preserving.** A red behavioural test is a sweep bug. The only intended changes are these, each with its test edit named in its task:
  1. A callback edge has no propagation (Q19): `EdgeWrapper.propagation is None`, the edge menu's propagation row and the inspector's propagation panel hide, Farmhand reports `propagation: null`, and the edge saves no `propagation` key.
  2. Farmhand, `PortInfo` and the generated type docs report `wire_type` (an id) and `role` in place of `flow_type`.
  3. Saved `edge_type` and port `flow_type` keys are ignored on load and never written (Q12). An edge whose saved `edge_type` cannot be parsed now loads.
  4. A port's wire type is derived (Q8a): config ports and folds have none, `ADD[T]` takes `T`'s, and a saved flow no longer overrides the type.
  5. The ghost-pin marker is `data-pin-ghost` (Q31); `data-pin-flow-type` and `data-pin-any-flow` are gone.
  6. A pin whose type declares no wire type draws the fallback glyph instead of no pin. Only test-only types are affected.
- **Out of scope** (later sub-plans):
  - 5.2: link-limit attributes and honouring a port's own `allow_multiple_links`; Q8b (refusing a value type with no wire type); dropping the widget rule and the container refusals; `OPTIONAL[T]` taking `T`'s wire type (Q21); refusing ADD↔ADD; the `VISUAL` role in use.
  - 5.3: `holds_absence` and the immediate-path guards.
  - 5.4: `style` and `EdgeSettings`.
  - In 5.1 a `WireType` carries only `role`, `propagation`, `pin_kind` and `id`.
- **Compare wire types by `.id`**, never with `is` or `issubclass` on the class. A hot reload makes several class objects for one wire type. Comparing `WireRole` members with `is` is fine.
- **Docstrings and comments** follow `.claude/rules/python-docs.md`. Docstrings of registered components (types, nodes, panels) are displayed: Markdown, single backticks, no reST.
- **"Ruff check"** means both `uv run ruff check <paths>` and `uv run ruff format --check <paths>`; line length 109.
- **Pre-commit gate:**
  `uv run pytest -m "not browser and not perf" -n 4 -q > /tmp/t.log 2>&1; echo "exit=$?"`
  then `grep -E "^FAILED|^ERROR" /tmp/t.log`. Use a timeout of at least 600000 ms.
- **Browser tier:** `uv run pytest -m browser -n 4 -q > /tmp/b.log 2>&1; echo "exit=$?"`.
- **visiongraph tests:** from this repo, `uv run pytest ../haybale-visiongraph/tests -q -p no:randomly`.
- **mypy set** (from CLAUDE.md):
  `uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-marketplace/haybale_marketplace/ barn/haybale-share/haybale_share/ barn/haybale-graph-editor/haybale_graph_editor/ barn/haybale-haystack/haybale_haystack/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-TEST_A/haybale_test_a/ tests/`
- **A failing test outside the files a task names:** stop and report it by name.

---

## Names this plan introduces

| Name | Where | Task |
|---|---|---|
| `WireRole` (`DEPENDENT`, `SEQUENCE`, `IMMEDIATE`, `VISUAL`) | `haywire.core.types.wire` | 1 |
| `WireType` (`role`, `propagation`, `pin_kind`, `id`, `clamp(mode)`) | `haywire.core.types.wire` | 1 |
| `get_wire_type(wire_id)`, `wire_type_of(type_cls)`, `wires_match(a, b)`, `WILDCARD` | `haywire.core.types.wire` | 1 |
| `WIRE = "wire"` | `haywire.core.library.utils` | 1 |
| `DataWire`, `ControlWire`, `CallbackWire` | `haywire.barn.builtin.wires` | 2 |
| `DataTypeIdentity.wire_type` | `haywire.core.types.identity` | 2 |
| `DataPort.wire_type`, `DataPort.wire_key`, `DataPort.has_role(role)`, `DataPort.is_dependent`, `DataPort._derive_wire()` | `haywire.core.types.port` | 2 |
| `EdgeWrapper.wire_type`, `EdgeWrapper._fit_propagation()` | `haywire.core.edge.edge_wrapper` | 4, 5 |
| `NodeData.get_ports(is_role=, is_not_role=)`, `NodeData.has_sequence_pins()` | `haywire.core.node.data` | 6 |
| `PortInfo.wire_type`, `PortInfo.role` | `haywire.core.node.inspector` | 7 |
| `ContextMenuCanvasEvent.pendingWire` | `haywire.ui.components.graph.event_definitions` | 8 |

`DataPort.is_dependent` is true for a port on a `DEPENDENT` wire and for a bare `ADD` slot. Today a bare `ADD` slot counts as a DATA port: the data walk follows it, a DATA node may have one as its only outlet (`AddPortTestNode`), and it gets DATA's link limits. Its wire type is `None` (it is the wildcard), so `is_dependent` is how 5.1 keeps those three behaviours.

## File structure

| File | Change | Task |
|---|---|---|
| `packages/haywire-core/src/haywire/core/types/wire.py` | new: the wire-type model | 1 |
| `packages/haywire-core/src/haywire/core/library/utils.py` | `WIRE` segment | 1 |
| `packages/haywire-core/src/haywire/core/types/__init__.py` | exports; `FlowType` removed in 10 | 1, 10 |
| `tests/core/test_types/test_wire.py` | new | 1 |
| `packages/haywire-core/src/haywire/barn/builtin/wires.py` | new: the three builtin wire types | 2 |
| `packages/haywire-core/src/haywire/core/types/identity.py` | `wire_type` field; `flow_type` removed in 10 | 2, 10 |
| `packages/haywire-core/src/haywire/core/types/decorator.py` | accepts `wire_type`; widget rule by role in 10 | 2, 10 |
| `packages/haywire-core/src/haywire/core/types/utils.py` | spec leaves `wire_type` out | 2 |
| `packages/haywire-core/src/haywire/core/types/port.py` | derived wire type; immediacy and link rules by role; legacy key ignored | 2, 9, 10 |
| 42 `@type` declarations (builtin, haybale-core, -example, -TEST_A, -testing, visiongraph, 2 test files) | `wire_type=` | 2 |
| `tests/core/test_types/test_wire_derivation.py` | new | 2 |
| `tests/core/test_libraries/test_wire_type_hot_reload.py` | new | 3 |
| `packages/haywire-core/src/haywire/core/edge/edge_wrapper.py`, `edge.py` | edge wire type, `wires_match`, propagation by wire type, deletions 3, 4, 5, 8 | 4, 5 |
| `packages/haywire-core/src/haywire/core/graph/base.py`, `graph/utils/node_remap.py` | creation and load without `edge_type`; `control_transitions` by role | 4, 6 |
| `packages/haywire-core/src/haywire/core/validation/interface.py`, `structural_validator.py` | deletion 8; node rules by role | 4, 6 |
| `packages/haywire-core/src/haywire/core/assembly/flow_assembly_manager.py`, `core/execution/interpreter.py` | deletion 7 | 4 |
| `packages/haywire-core/src/haywire/core/types/enums.py` | `Propagation.IMMEDIATE` (5), `FlowType` (10) removed | 5, 10 |
| `barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/edge/edge.py`, `panels/properties/introspect/edge.py`, `editors/graph_canvas/handlers/context_menu.py` | propagation UI | 5, 8 |
| `barn/haybale-graph-editor/haybale_graph_editor/farmhands/editor_tools.py` | `wire_type`/`role` rows | 4, 5, 7 |
| `packages/haywire-core/src/haywire/core/node/data.py` | `get_ports(is_role=…)`, `has_sequence_pins()` | 6 |
| `packages/haywire-core/src/haywire/core/assembly/data_flow_builder.py`, `assembly/flat_view.py` | by role | 6 |
| `packages/haywire-core/src/haywire/barn/builtin/nodes/graph_node.py`, `subgraph_io.py`, `reroute.py` | by role; mirrors stop passing a flow | 6, 9 |
| `packages/haywire-core/src/haywire/core/types/registry.py` | Python-type lookup by role | 6 |
| `packages/haywire-core/src/haywire/core/node/inspector.py`, `packages/haywire-studio/src/haywire_studio/packaging/docs/extract.py` | `wire_type`/`role` | 7 |
| `packages/haywire-core/src/haywire/ui/skin/pin_render.py`, `ui/skin/pin_icons.py`, `ui/components/graph/canvas.vue`, `event_definitions.py`, `generated/graph_events.js`, `barn/.../handlers/visual_layer.py` | pins and canvas | 8 |
| `packages/haywire-core/src/haywire/core/types/interface.py`, `barn/haybale-core/haybale_core/types/array_type.py`, `pooled_type.py`, `core/undo/actions/graph_actions.py`, `core/graph/subgraph_collapse.py` | ports derive everything | 9 |
| `packages/haywire-core/src/haywire/barn/builtin/types/add.py` | bare `ADD` declares no flow | 10 |
| `docs/reference/glossary.md`, `docs/adr/0042-*.md` (new), `docs/adr/0039-*.md`, architecture docs, guides, `CLAUDE.md`, generated library docs (both repos) | docs | 11 |

---

### Task 0: Branches, baselines and a saved-graph snapshot

**Files:**
- Create (uncommitted, deleted in Task 12): `tests/core/test_zz_graph_snapshot.py`

**Interfaces:**
- Consumes: nothing.
- Produces: branch `wire-types-5-1` in both repos; `/tmp/graph_snapshot_before.json`, which Task 12 compares against.

- [ ] **Step 1: Create the branches**

```bash
cd /Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo && git switch -c wire-types-5-1
cd /Volumes/Ddrive/06_open_tracking_tool/haywire/haybale-visiongraph && git switch -c wire-types-5-1
```

Expected: both report `Switched to a new branch 'wire-types-5-1'`. The haywire-repo working tree still shows the user's uncommitted plan edits; leave them.

- [ ] **Step 2: Lint and type-check baseline**

From haywire-repo run the ruff check on the whole repo (`uv run ruff check . && uv run ruff format --check .`), then the mypy set from Global Constraints.

Expected: no errors. If there are any, stop and report: CLAUDE.md requires a clean baseline before a multi-file refactor.

- [ ] **Step 3: Test baseline**

Run the pre-commit gate, the browser tier and the visiongraph tests (commands in Global Constraints).

Expected: all exit 0. On 2026-10-03, before this plan: 5975 passed and 2 xfailed in the gate, 29 passed in visiongraph.

- [ ] **Step 4: Snapshot every saved graph's validity**

Create `tests/core/test_zz_graph_snapshot.py`. It is a scratch file and is not committed:

```python
"""Scratch, not committed: record every saved graph's node and edge validity."""

import json
import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

# The camera graphs instantiate visiongraph capture nodes; leave hardware out of it.
_SKIP = {"webcam.haywire", "oakNwebCam.haywire"}


def test_snapshot_saved_graphs(graph_with_library_system):
    graph = graph_with_library_system
    repo = Path(__file__).resolve().parents[2]
    snapshot = {}
    for path in sorted(repo.glob("graphs/*.haywire")):
        if path.name in _SKIP:
            continue
        graph.clear()
        assert graph.load_from_file(str(path)), path.name
        graph.force_validation()
        snapshot[path.name] = {
            "nodes": {nid: w.is_valid() for nid, w in graph.node_wrappers.items()},
            "edges": {eid: e.state.is_valid() for eid, e in graph.edge_wrappers.items()},
        }
    Path(os.environ["HW_GRAPH_SNAPSHOT"]).write_text(json.dumps(snapshot, indent=1, sort_keys=True))
```

Run: `HW_GRAPH_SNAPSHOT=/tmp/graph_snapshot_before.json uv run pytest tests/core/test_zz_graph_snapshot.py -q -p no:randomly`

Expected: 1 passed, and `/tmp/graph_snapshot_before.json` exists. Leave the test file untracked. Never `git add` it.

No commit in this task.

---

### Task 1: The wire-type model

**Files:**
- Create: `packages/haywire-core/src/haywire/core/types/wire.py`
- Modify: `packages/haywire-core/src/haywire/core/library/utils.py:9-21` (segment constants), `packages/haywire-core/src/haywire/core/types/__init__.py`
- Test: `tests/core/test_types/test_wire.py` (create)

**Interfaces:**
- Consumes: `derive_library_identity`, `reg_key` (`haywire.core.library.utils`), `Propagation` (`haywire.core.types.enums`).
- Produces:
  - `WireRole`.
  - `WireType`, with class attributes `role: WireRole`, `propagation: tuple[Propagation, ...] = ()`, `pin_kind: str = ""`, `id: str`, and the classmethod `clamp(mode: Propagation | None) -> Propagation | None`.
  - `get_wire_type(wire_id: str) -> type[WireType] | None`.
  - `wire_type_of(type_cls: Any) -> type[WireType] | None`.
  - `wires_match(a: str | None, b: str | None) -> bool`.
  - `WILDCARD = "*"`.
  - All exported from `haywire.core.types`.

- [ ] **Step 1: Write the failing tests**

Create `tests/core/test_types/test_wire.py`:

```python
"""The wire-type model: ids, the id map, clamping, derivation and matching."""

from types import SimpleNamespace

import pytest

from haywire.core.types import Propagation
from haywire.core.types import wire as wire_module
from haywire.core.types.wire import (
    WILDCARD,
    WireRole,
    WireType,
    get_wire_type,
    wire_type_of,
    wires_match,
)

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _isolated_id_map(monkeypatch):
    """Each test registers into a copy, so its wire types never leak into the next."""
    monkeypatch.setattr(wire_module, "_WIRE_BY_ID", dict(wire_module._WIRE_BY_ID))


def _wire(name: str, module: str = __name__, **attrs) -> type[WireType]:
    """A wire type class named *name*, defined as if in *module*."""
    namespace = {"__module__": module, "__qualname__": name, "role": WireRole.DEPENDENT, **attrs}
    return type(name, (WireType,), namespace)


class TestIds:
    def test_a_wire_type_is_named_by_its_library_and_class(self):
        plain = _wire("PlainWire")

        assert plain.id == "__system__:wire:PlainWire"
        assert get_wire_type(plain.id) is plain

    def test_id_replaces_the_last_segment(self):
        named = _wire("NamedWire", id="Renamed")

        assert named.id == "__system__:wire:Renamed"

    def test_a_base_without_a_role_is_not_registered(self):
        abstract = type("AbstractWire", (WireType,), {"__module__": __name__, "__qualname__": "AbstractWire"})

        assert not hasattr(abstract, "id") or get_wire_type(abstract.id) is not abstract

    def test_the_same_class_defined_again_replaces_the_old_one(self):
        first = _wire("ReloadedWire")
        second = _wire("ReloadedWire")

        assert second.id == first.id
        assert get_wire_type(first.id) is second

    def test_the_same_id_from_another_module_is_refused(self):
        _wire("ClashingWire")

        with pytest.raises(ValueError, match="collision"):
            _wire("ClashingWire", module="some.other.module")


class TestClamp:
    def test_an_allowed_mode_is_kept(self):
        both = _wire("BothWire", propagation=(Propagation.EAGER, Propagation.LAZY))

        assert both.clamp(Propagation.LAZY) is Propagation.LAZY

    def test_a_disallowed_mode_takes_the_default(self):
        eager_only = _wire("EagerOnlyWire", propagation=(Propagation.EAGER,))

        assert eager_only.clamp(Propagation.LAZY) is Propagation.EAGER
        assert eager_only.clamp(None) is Propagation.EAGER

    def test_a_wire_type_without_propagation_clamps_to_none(self):
        none = _wire("NoneWire", propagation=())

        assert none.clamp(Propagation.EAGER) is None


class TestWireTypeOf:
    def test_a_type_answers_with_its_declared_wire_type(self):
        declared = _wire("DeclaredWire")
        value = SimpleNamespace(class_identity=SimpleNamespace(wire_type=declared))

        assert wire_type_of(value) is declared

    def test_a_container_answers_with_its_elements_through_nesting(self):
        declared = _wire("ElementWire")
        element = SimpleNamespace(class_identity=SimpleNamespace(wire_type=declared))
        inner = SimpleNamespace(class_identity=SimpleNamespace(wire_type=None), element_type_cls=element)
        outer = SimpleNamespace(class_identity=SimpleNamespace(wire_type=None), element_type_cls=inner)

        assert wire_type_of(outer) is declared

    def test_a_type_without_identity_or_element_answers_none(self):
        assert wire_type_of(SimpleNamespace()) is None
        assert wire_type_of(None) is None

    def test_an_element_that_is_a_plain_python_type_ends_the_walk(self):
        container = SimpleNamespace(class_identity=SimpleNamespace(wire_type=None), element_type_cls=float)

        assert wire_type_of(container) is None


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        ("lib:wire:A", "lib:wire:A", True),
        ("lib:wire:A", "lib:wire:B", False),
        (WILDCARD, "lib:wire:A", True),
        ("lib:wire:A", WILDCARD, True),
        (WILDCARD, WILDCARD, True),
        (None, "lib:wire:A", False),
        ("lib:wire:A", None, False),
        (None, None, False),
    ],
)
def test_wires_match(a, b, expected):
    assert wires_match(a, b) is expected
```

- [ ] **Step 2: Run the tests**

Run: `uv run pytest tests/core/test_types/test_wire.py -q`
Expected: collection fails with `ModuleNotFoundError: No module named 'haywire.core.types.wire'`.

- [ ] **Step 3: Add the `WIRE` segment**

In `packages/haywire-core/src/haywire/core/library/utils.py`, add after `FARMHAND = "farmhand"`:

```python
WIRE = "wire"
```

- [ ] **Step 4: Create the module**

Create `packages/haywire-core/src/haywire/core/types/wire.py`:

```python
"""Wire types: how a value travels between ports, and what the framework does with the edge.

Every port has a data type, and the data type declares its wire type. The data
type says what the value is; the wire type says how it travels. A wire type is
a class that is never instantiated. Its metadata is class attributes, and
``__init_subclass__`` gives it an id and records it in an id map. Framework
code branches on a wire type's ``role``, never on which wire type it is.

Two pins connect when their wire keys match (``wires_match``): equal wire type
ids, or a bare ``ADD`` slot, whose key is ``WILDCARD``.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, ClassVar

from haywire.core.library.utils import WIRE, derive_library_identity, reg_key
from haywire.core.types.enums import Propagation

#: The wire key of a bare ``ADD`` slot, which any wire type connects to.
WILDCARD = "*"

# id -> WireType subclass, filled by WireType.__init_subclass__.
_WIRE_BY_ID: dict[str, type["WireType"]] = {}


class WireRole(Enum):
    """What the framework does with an edge, decided by the edge's wire type.

    The set is closed: framework code branches on the role, so a new role is a
    framework change.

    - ``DEPENDENT``: assembly walks it backward from the node that needs the value.
    - ``SEQUENCE``: the VM walks it forward, in execution order.
    - ``IMMEDIATE``: takes effect on write, with no engine involved.
    - ``VISUAL``: drawn and saved, never executed.
    """

    DEPENDENT = "dependent"
    SEQUENCE = "sequence"
    IMMEDIATE = "immediate"
    VISUAL = "visual"


class WireType:
    """How a value travels between two ports, and how its pins look.

    Subclass it and name the subclass in ``@type(wire_type=...)``. It is never
    instantiated. A subclass that sets ``role`` is registered under the id
    ``"<library>:wire:<ClassName>"``; setting ``id`` replaces the last segment.
    Compare wire types by ``id``: a hot reload makes a new class object under
    the same id.

    Attributes:
        role: What the framework does with an edge of this wire type.
        propagation: The modes an edge may take. The first is the default, a
            single entry locks it, and an empty tuple means the edge has none.
        pin_kind: The key the skin's ``PinIconResolver`` looks up in its icon
            map, such as ``"control"``. It is not an icon; a type names its own.
        id: The registry id, set when the class is defined.

    Raises:
        ValueError: When a class from another module already holds the derived id.

    Example::

        class ControlWire(WireType):
            role = WireRole.SEQUENCE
            propagation = (Propagation.EAGER, Propagation.LAZY)
            pin_kind = "control"

        @type(wire_type=ControlWire, default={"value": {}})
        class EXEC(PrimitiveType[dict]): ...

        ControlWire.id  # "haywire-core:wire:ControlWire"
    """

    role: ClassVar[WireRole]
    propagation: ClassVar[tuple[Propagation, ...]] = ()
    pin_kind: ClassVar[str] = ""
    id: ClassVar[str]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if getattr(cls, "role", None) is None:
            return
        segment = cls.__dict__.get("id", cls.__name__)
        wire_id = reg_key(derive_library_identity(cls).name, WIRE, segment)
        existing = _WIRE_BY_ID.get(wire_id)
        if existing is not None and (existing.__module__, existing.__qualname__) != (
            cls.__module__,
            cls.__qualname__,
        ):
            raise ValueError(
                f"Wire type id collision: {cls.__module__}.{cls.__qualname__} and "
                f"{existing.__module__}.{existing.__qualname__} both derive id={wire_id!r}"
            )
        # The same module and qualname is a hot reload: the new class replaces the old.
        cls.id = wire_id
        _WIRE_BY_ID[wire_id] = cls

    @classmethod
    def clamp(cls, mode: Propagation | None) -> Propagation | None:
        """Return *mode* when this wire type allows it, else its default; ``None`` when it allows none."""
        if not cls.propagation:
            return None
        return mode if mode in cls.propagation else cls.propagation[0]


def get_wire_type(wire_id: str) -> type[WireType] | None:
    """Return the wire type registered under *wire_id*, or ``None``."""
    return _WIRE_BY_ID.get(wire_id)


def wire_type_of(type_cls: Any) -> type[WireType] | None:
    """Return the wire type values of *type_cls* travel on, or ``None``.

    A type answers with the wire type its identity declares. A container or
    wrapper that declares none (``ArrayType[T]``, ``PooledType[T]``, ``ADD[T]``)
    answers with its element's, through any nesting. A bare ``ADD``, a type
    without an identity and ``None`` answer ``None``.
    """
    current = type_cls
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        identity = getattr(current, "class_identity", None)
        wire = getattr(identity, "wire_type", None)
        if wire is not None:
            return wire
        current = getattr(current, "element_type_cls", None)
    return None


def wires_match(a: str | None, b: str | None) -> bool:
    """Return whether two pins with wire keys *a* and *b* may be linked.

    True for equal wire type ids, and when either key is ``WILDCARD`` (a bare
    ``ADD`` slot). A key of ``None`` (a port without a wire type) matches nothing.
    """
    if a is None or b is None:
        return False
    return a == b or a == WILDCARD or b == WILDCARD
```

- [ ] **Step 5: Export from `haywire.core.types`**

In `packages/haywire-core/src/haywire/core/types/__init__.py`, add after the `.enums` import line:

```python
from .wire import WILDCARD, WireRole, WireType, get_wire_type, wire_type_of, wires_match
```

and add to `__all__`, after `"StoreStrategy",`:

```python
    # Wire types
    "WILDCARD",
    "WireRole",
    "WireType",
    "get_wire_type",
    "wire_type_of",
    "wires_match",
```

- [ ] **Step 6: Run the tests**

Run: `uv run pytest tests/core/test_types/test_wire.py -q`
Expected: all pass.

`test_a_base_without_a_role_is_not_registered` holds because `WireType` declares `role` as an annotation only, so `getattr(cls, "role", None)` is `None` for a class that sets none.

- [ ] **Step 7: Ruff and mypy**

Run the ruff check and mypy on `packages/haywire-core/src/haywire/core/types/wire.py`, `packages/haywire-core/src/haywire/core/library/utils.py`, `packages/haywire-core/src/haywire/core/types/__init__.py` and `tests/core/test_types/test_wire.py`.

Expected: no errors.

- [ ] **Step 8: Commit**

```bash
git add packages/haywire-core/src/haywire/core/types/wire.py packages/haywire-core/src/haywire/core/library/utils.py packages/haywire-core/src/haywire/core/types/__init__.py tests/core/test_types/test_wire.py
git commit -m "feat(types): the wire-type model

WireRole, WireType with a derived id and an id map (the Surface pattern),
wire_type_of and wires_match. Nothing declares or reads a wire type yet.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Builtin wire types; types declare them and ports derive them

From here on, every value type declares a wire type and every port derives one. `FlowType` keeps working unchanged: until Task 10, `@type` fills a type's `flow_type` from the role of the wire type it declares. Bare `ADD` declares no wire type (it is the wildcard), so it keeps its explicit `flow_type=FlowType.DATA` until Task 10.

**Files:**
- Create: `packages/haywire-core/src/haywire/barn/builtin/wires.py`
- Modify:
  - `packages/haywire-core/src/haywire/core/types/identity.py:20-75`
  - `packages/haywire-core/src/haywire/core/types/decorator.py`
  - `packages/haywire-core/src/haywire/core/types/utils.py:81-87`
  - `packages/haywire-core/src/haywire/core/types/port.py` (field, `__post_init__`, `refresh_from`, new members)
- Modify (declarations, table in Step 6): 16 builtin, 12 barn, 9 visiongraph, 4 in tests
- Test: `tests/core/test_types/test_wire_derivation.py` (create)

**Interfaces:**
- Consumes: Task 1's `WireRole`, `WireType`, `WILDCARD`, `wire_type_of`.
- Produces:
  - `haywire.barn.builtin.wires.DataWire` (`DEPENDENT`, `(EAGER, LAZY)`, `"data"`), `ControlWire` (`SEQUENCE`, `(EAGER, LAZY)`, `"control"`) and `CallbackWire` (`IMMEDIATE`, `()`, `"callback"`). Their ids are `haywire-core:wire:DataWire`, `…:ControlWire` and `…:CallbackWire`.
  - `DataTypeIdentity.wire_type: type[WireType] | None = None`, inherited by derived types.
  - `DataPort.wire_type` (a derived, unsaved field), `DataPort.wire_key -> str | None`, `DataPort.has_role(role) -> bool` and `DataPort.is_dependent -> bool`.
  - `DataPort._derive_wire() -> None`, run in `__post_init__` and `refresh_from`.

- [ ] **Step 1: Write the failing tests**

Create `tests/core/test_types/test_wire_derivation.py`:

```python
"""Types declare a wire type, and every port derives its own from its type."""

import pytest

from haywire.core.types import PortType, WireRole
from haywire.core.types.wire import WILDCARD

from tests.conftest import make_node


@pytest.mark.unit
class TestBuiltinWireTypes:
    def test_ids(self):
        from haywire.barn.builtin.wires import CallbackWire, ControlWire, DataWire

        assert DataWire.id == "haywire-core:wire:DataWire"
        assert ControlWire.id == "haywire-core:wire:ControlWire"
        assert CallbackWire.id == "haywire-core:wire:CallbackWire"

    def test_roles_and_pin_kinds(self):
        from haywire.barn.builtin.wires import CallbackWire, ControlWire, DataWire

        assert (DataWire.role, DataWire.pin_kind) == (WireRole.DEPENDENT, "data")
        assert (ControlWire.role, ControlWire.pin_kind) == (WireRole.SEQUENCE, "control")
        assert (CallbackWire.role, CallbackWire.pin_kind) == (WireRole.IMMEDIATE, "callback")


@pytest.mark.unit
class TestTypesDeclare:
    def test_each_builtin_signal_type_names_its_wire_type(self):
        from haywire.barn.builtin.types import CALLBACK, EXEC, FLOAT
        from haywire.barn.builtin.wires import CallbackWire, ControlWire, DataWire

        assert FLOAT.class_identity.wire_type.id == DataWire.id
        assert EXEC.class_identity.wire_type.id == ControlWire.id
        assert CALLBACK.class_identity.wire_type.id == CallbackWire.id

    def test_a_derived_type_inherits_its_parents_wire_type(self):
        from haywire.barn.builtin.types import FLOAT
        from haywire.barn.builtin.wires import DataWire
        from haywire.core.types import type as haywire_type

        @haywire_type(label="Derived")
        class Derived(FLOAT):
            """A FLOAT variant."""

        assert Derived.class_identity.wire_type.id == DataWire.id

    def test_a_port_spec_carries_no_wire_type(self):
        from haywire.barn.builtin.types import FLOAT

        assert "wire_type" not in FLOAT.as_inlet("x")["kwargs"]


@pytest.mark.integration
class TestPortsDerive:
    def test_a_data_inlet(self, graph_with_library_system):
        from haybale_testing.nodes.testbed.math_op_node import TestAddFloatNode

        from haywire.barn.builtin.wires import DataWire

        node = make_node(graph_with_library_system, TestAddFloatNode.class_identity.registry_key).node
        port = node.ports["value_a"]

        assert port.wire_type.id == DataWire.id
        assert port.wire_key == DataWire.id
        assert port.has_role(WireRole.DEPENDENT)
        assert port.is_dependent

    def test_a_pooled_callback_inlet_takes_its_elements(self, graph_with_library_system):
        from haybale_testing.nodes.testbed.emit_callback_node import TestEmitCallbackNode

        from haywire.barn.builtin.wires import CallbackWire, ControlWire

        node = make_node(graph_with_library_system, TestEmitCallbackNode.class_identity.registry_key).node

        assert node.ports["edge_callback"].wire_type.id == CallbackWire.id
        assert node.ports["exec"].wire_type.id == ControlWire.id
        assert not node.ports["edge_callback"].is_dependent

    def test_an_array_outlet_takes_its_elements(self, graph_with_library_system):
        from haybale_testing.nodes.testbed.edge_link_test import EdgeLinkTestNode

        from haywire.barn.builtin.wires import DataWire

        node = make_node(graph_with_library_system, EdgeLinkTestNode.class_identity.registry_key).node

        assert node.ports["array_float_outlet"].wire_type.id == DataWire.id

    def test_config_ports_and_folds_have_none(self, graph_with_library_system):
        from haybale_testing.nodes.testbed.fold_probe import FoldProbeNode

        node = make_node(graph_with_library_system, FoldProbeNode.class_identity.registry_key).node
        config = node.ports["substeps"]
        folds = [p for p in node.ports.values() if p.is_fold]

        assert config.port_type is PortType.CONFIG
        assert config.wire_type is None
        assert config.wire_key is None
        assert folds
        assert all(f.wire_type is None for f in folds)

    def test_a_bare_add_slot_is_the_wildcard_and_counts_as_dependent(self, graph_with_library_system):
        from haybale_testing.nodes.testbed.add_port_test import AddPortTestNode

        from haywire.barn.builtin.wires import DataWire

        node = make_node(graph_with_library_system, AddPortTestNode.class_identity.registry_key).node
        bare = node.ports["add_out_0"]
        decided = node.ports["str_in_0"]

        assert bare.wire_type is None
        assert bare.wire_key == WILDCARD
        assert bare.is_dependent
        assert not bare.has_role(WireRole.DEPENDENT)
        assert decided.wire_type.id == DataWire.id
```

- [ ] **Step 2: Run the tests**

Run: `uv run pytest tests/core/test_types/test_wire_derivation.py -q`
Expected: FAIL. `haywire.barn.builtin.wires` does not exist, and `wire_type` is not an attribute of the identity or the port.

- [ ] **Step 3: Create the builtin wire types**

Create `packages/haywire-core/src/haywire/barn/builtin/wires.py`:

```python
"""The wire types the framework ships: data, control and callback.

A value type travels on one of these unless its library defines its own wire
type (see ``haywire.core.types.wire``). Import them from this module; types in
the builtin library import them relatively.
"""

from haywire.core.types.enums import Propagation
from haywire.core.types.wire import WireRole, WireType


class DataWire(WireType):
    """Values, pulled by assembly for the node that needs them."""

    role = WireRole.DEPENDENT
    propagation = (Propagation.EAGER, Propagation.LAZY)
    pin_kind = "data"


class ControlWire(WireType):
    """Execution order, walked forward by the VM."""

    role = WireRole.SEQUENCE
    propagation = (Propagation.EAGER, Propagation.LAZY)
    pin_kind = "control"


class CallbackWire(WireType):
    """Subscriptions, which take effect as soon as they are written."""

    role = WireRole.IMMEDIATE
    propagation = ()
    pin_kind = "callback"
```

- [ ] **Step 4: The identity field, the decorator, the spec**

In `packages/haywire-core/src/haywire/core/types/identity.py`:

1. Under `if TYPE_CHECKING:` add `from haywire.core.types.wire import WireType`.
2. In the class docstring's attribute list, after the `flow_type` line, add:
   `wire_type: The wire type values of this type travel on; None for a container, which takes its element's`.
3. After the `flow_type` field add:

```python
    wire_type: type[WireType] | None = None
    """The wire type values of this type travel on. ``None`` for a container, which
    takes its element's; see ``wire_type_of``."""
```

In `packages/haywire-core/src/haywire/core/types/decorator.py`:

1. Add `from .wire import WireRole` next to the other relative imports.
2. Add the transitional map below the imports:

```python
# Until FlowType is deleted, a declared wire type also sets the flow it replaces.
_FLOW_FOR_ROLE = {
    WireRole.DEPENDENT: FlowType.DATA,
    WireRole.SEQUENCE: FlowType.CONTROL,
    WireRole.IMMEDIATE: FlowType.CALLBACK,
}
```

3. In the `Args:` docstring, after the `flow_type` entry, add:
   `wire_type (type[WireType], optional): The wire type values travel on; inherited by derived types.`
4. Directly before the line `flow = identity_dict.get("flow_type", FlowType.NONE)`, add:

```python
        wire = identity_dict.get("wire_type")
        if wire is not None:
            identity_dict["flow_type"] = _FLOW_FOR_ROLE[wire.role]
```

In `packages/haywire-core/src/haywire/core/types/utils.py`, replace the `merged_kwargs` block (lines 81-87) with:

```python
    # Build spec: identity as defaults, kwargs override
    # The spec becomes the self-contained truth. A port derives its wire type from
    # its type, so the identity's is left out and a wire_type kwarg is refused.
    identity = {k: v for k, v in asdict(type_cls.class_identity).items() if k != "wire_type"}
    merged_kwargs = {
        **identity,  # Identity defaults
        "id": id,
        "port_type": port_type,
        **kwargs,  # User overrides
    }
```

- [ ] **Step 5: The port derives its wire type**

In `packages/haywire-core/src/haywire/core/types/port.py`:

1. Add the import after the `identity` import:

```python
from haywire.core.types.wire import WILDCARD, WireRole, WireType, wire_type_of
```

2. Directly after the `type_cls` field and its docstring, add:

```python
    wire_type: type[WireType] | None = field(
        default=None, init=False, repr=False, compare=False, metadata={"serialize": False}
    )
    """The wire type this port's values travel on, derived from ``type_cls``. ``None`` for
    a config port, a fold, a bare ``ADD`` slot and a type that declares none. Read-only:
    set by ``_derive_wire``."""
```

3. In `__post_init__`, directly after `self._is_inlet = self.port_type == PortType.INLET`, add:

```python
        self._derive_wire()
```

4. In `refresh_from`, directly before the comment `# set_value reads this cache rather than flow_type…`, add:

```python
        self._derive_wire()
```

5. In the `PORT TYPE CHECKS` section, directly after `has_pin`, add:

```python
    def _derive_wire(self) -> None:
        """Set ``wire_type`` from the port's type; a config port and a fold have none."""
        self.wire_type = None if self.is_config() or self.is_fold else wire_type_of(self.type_cls)

    @property
    def wire_key(self) -> str | None:
        """The key this pin matches other pins by: its wire type's id, ``WILDCARD`` for a
        bare ``ADD`` slot, or ``None`` for a port without a wire type. See ``wires_match``."""
        if self.wire_type is not None:
            return self.wire_type.id
        if self.has_pin() and self.type_cls is not None and self.type_cls._is_any:
            return WILDCARD
        return None

    def has_role(self, role: WireRole) -> bool:
        """True if this port's wire type has *role*; False for a port without a wire type."""
        return self.wire_type is not None and self.wire_type.role is role

    @property
    def is_dependent(self) -> bool:
        """True for a port on a ``DEPENDENT`` wire, and for a bare ``ADD`` slot, which
        counts as one until it grows."""
        return self.has_role(WireRole.DEPENDENT) or self.wire_key == WILDCARD
```

- [ ] **Step 6: Every type declares its wire type**

In each line below, replace `flow_type=FlowType.<X>,` with `wire_type=<X>Wire,`, mapping DATA to `DataWire`, CONTROL to `ControlWire` and CALLBACK to `CallbackWire`. Then add the wire import and remove `FlowType` from the file's imports where nothing else in the file uses it.

- **Builtin types.** Import relatively: `from ..wires import DataWire` (or `ControlWire` / `CallbackWire`).
- **Everywhere else.** Import `from haywire.barn.builtin.wires import DataWire`.
- **Leave `add.py` alone.** Bare `ADD` declares no wire type, and its `flow_type=FlowType.DATA` stays until Task 10.

| File | Lines (`flow_type=`) | Wire |
|---|---|---|
| `packages/haywire-core/src/haywire/barn/builtin/types/specs.py` | 11, 53, 88, 112 | DataWire |
| `…/builtin/types/vectors.py` | 66, 80, 94, 108, 122, 136 | DataWire |
| `…/builtin/types/color.py` | 17 | DataWire |
| `…/builtin/types/choices.py` | 8 | DataWire |
| `…/builtin/types/fold.py` | 7 | DataWire |
| `…/builtin/types/optional.py` | 12 | DataWire |
| `…/builtin/types/exec.py` | 7 | ControlWire |
| `…/builtin/types/callback.py` | 9 | CallbackWire |
| `barn/haybale-core/haybale_core/types/specs.py` | 9, 36, 54 | DataWire |
| `barn/haybale-example/haybale_example/types/fill.py` | 69 | DataWire |
| `barn/haybale-example/haybale_example/types/maps_string_type.py` | 15 | DataWire |
| `barn/haybale-TEST_A/haybale_test_a/types/data.py` | 18 | DataWire |
| `barn/haybale-testing/haybale_testing/types/test_types.py` | 16, 48, 82, 105, 126 | DataWire |
| `barn/haybale-testing/haybale_testing/types/test_types.py` | 145 | CallbackWire |
| `barn/haybale-visiongraph/haybale_visiongraph/types/frame_type.py` | 76, 89, 107 | DataWire |
| `barn/haybale-visiongraph/haybale_visiongraph/types/result_type.py` | 80, 94, 108, 122, 136 | DataWire |
| `barn/haybale-visiongraph/haybale_visiongraph/types/multiframe_callback_type.py` | 34 | CallbackWire |
| `tests/core/test_types/test_type_for_python_type.py` | 12 / 17 | DataWire / ControlWire |
| `tests/barn/builtin/test_type_default_widget.py` | 35-40, 56 | see below |

In `tests/barn/builtin/test_type_default_widget.py`:
- In `test_control_and_callback_flow_types_reject_widget_key`, replace the `FlowType` import and the `flow_type = …` line with:

```python
    from haywire.barn.builtin.wires import CallbackWire, ControlWire

    wire_type = ControlWire if flow == "control" else CallbackWire
```

  and pass `wire_type=wire_type` instead of `flow_type=flow_type`.
- In `test_inherited_widget_key_on_signal_type_is_rejected`, replace the `FlowType` import with `from haywire.barn.builtin.wires import CallbackWire`, and pass `wire_type=CallbackWire` instead of `flow_type=FlowType.CALLBACK`.

In `multiframe_callback_type.py`, also replace the docstring sentence at lines 5-7, which says the type is "declared with ``flow_type=FlowType.CALLBACK``" and identified "via the edge's flow_type". The new text: "declared on `CallbackWire`, so the framework recognises a callback edge by its wire type's role."

Then check that nothing is missed:

Run: `grep -rn "flow_type=FlowType" --include='*.py' packages barn tests | grep -v "/docs/"`
Expected: only `packages/haywire-core/src/haywire/barn/builtin/types/add.py:52` (plus any `DataPort(… flow_type=FlowType.DATA …)` constructions in tests, which Task 10 handles).

- [ ] **Step 7: Run the new tests and the type tests**

Run: `uv run pytest tests/core/test_types/ tests/barn/builtin/ -q -n 4`
Expected: PASS.

- [ ] **Step 8: Ruff, mypy, commit haywire-repo, then the gate**

Run the ruff check and mypy on every file changed in this task. Expected: no errors.

```bash
git add packages/haywire-core/src/haywire/barn/builtin/wires.py packages/haywire-core/src/haywire/core/types/identity.py packages/haywire-core/src/haywire/core/types/decorator.py packages/haywire-core/src/haywire/core/types/utils.py packages/haywire-core/src/haywire/core/types/port.py packages/haywire-core/src/haywire/barn/builtin/types/ barn/haybale-core/haybale_core/types/specs.py barn/haybale-example/haybale_example/types/fill.py barn/haybale-example/haybale_example/types/maps_string_type.py barn/haybale-TEST_A/haybale_test_a/types/data.py barn/haybale-testing/haybale_testing/types/test_types.py tests/core/test_types/test_type_for_python_type.py tests/barn/builtin/test_type_default_widget.py tests/core/test_types/test_wire_derivation.py
git commit -m "feat(types): types declare a wire type and ports derive one

DataWire, ControlWire and CallbackWire ship in builtin. @type(wire_type=...)
replaces flow_type= on every value type; until FlowType goes, the declared
wire type also fills the flow. A port derives wire_type from its type and
never saves it; config ports and folds have none, and a bare ADD slot is the
wildcard.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

In the visiongraph repo:

```bash
cd /Volumes/Ddrive/06_open_tracking_tool/haywire/haybale-visiongraph
git add barn/haybale-visiongraph/haybale_visiongraph/types/frame_type.py barn/haybale-visiongraph/haybale_visiongraph/types/result_type.py barn/haybale-visiongraph/haybale_visiongraph/types/multiframe_callback_type.py
git commit -m "refactor(types): declare wire types instead of flow types

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

Then run the pre-commit gate and the visiongraph tests. Expected: both green.

---

### Task 3: Verify first: a library's wire type hot-reloads

The design rests on one assumption: an edited wire-type module reloads as an unmanaged module, and the dependency graph then reloads the type modules that import it. This task checks that for a module at the library root and for one inside `types/`, before anything is built on it.

**If either test fails for a reason other than a mistake in the test, stop and report to the user. Do not change the registry in this plan.**

**Files:**
- Test: `tests/core/test_libraries/test_wire_type_hot_reload.py` (create)

**Interfaces:**
- Consumes: `TypeRegistry.add_folder`, `TypeRegistry.event_dispatcher`, `FileChangeEvent`, Task 1's `get_wire_type`, Task 2's `@type(wire_type=…)`.
- Produces: nothing for later tasks. Task 11 records the result as authoring guidance.

- [ ] **Step 1: Write the test**

Create `tests/core/test_libraries/test_wire_type_hot_reload.py`:

```python
"""A wire type defined in a library hot-reloads into the types that use it.

A wire-type module is no registered component. It reloads as an unmanaged
module, and the dependency graph reloads the type modules importing it.
"""

import sys
import time

import pytest

from haywire.core.library.identity import LibraryIdentity
from haywire.core.registry.base import FileChangeEvent, FileEventType
from haywire.core.types import wire as wire_module
from haywire.core.types.registry import TypeRegistry
from haywire.core.types.wire import get_wire_type

pytestmark = [pytest.mark.unit, pytest.mark.core]

# No Library class in the temp package, so both ids take the '__system__' prefix.
WIRE_ID = "__system__:wire:DemoWire"
TYPE_KEY = "__system__:type:DemoValue"

_WIRE_SOURCE = """
from haywire.core.types.wire import WireRole, WireType


class DemoWire(WireType):
    role = WireRole.DEPENDENT
    pin_kind = "{kind}"
"""

_TYPE_SOURCE = """
from haywire.core.types import PrimitiveType, type

from {wire_module} import DemoWire


@type(wire_type=DemoWire, default={{"value": 0}})
class DemoValue(PrimitiveType[int]):
    '''A value on the demo wire.'''
"""


def _drop_demo_modules() -> None:
    for name in [m for m in sys.modules if m.startswith("haybale_wiredemo")]:
        del sys.modules[name]


@pytest.fixture(params=["root", "types"])
def library(request, tmp_path, monkeypatch):
    """A library whose type imports a wire type from the root, or from inside types/."""
    monkeypatch.setattr(wire_module, "_WIRE_BY_ID", dict(wire_module._WIRE_BY_ID))
    root = tmp_path / "haybale_wiredemo"
    (root / "types").mkdir(parents=True)
    (root / "__init__.py").write_text("")
    (root / "types" / "__init__.py").write_text("")
    if request.param == "root":
        wire_path, wire_module_name = root / "wires.py", "haybale_wiredemo.wires"
    else:
        wire_path, wire_module_name = root / "types" / "wires.py", "haybale_wiredemo.types.wires"
    wire_path.write_text(_WIRE_SOURCE.format(kind="original"))
    (root / "types" / "demo_value.py").write_text(_TYPE_SOURCE.format(wire_module=wire_module_name))

    monkeypatch.syspath_prepend(str(tmp_path))
    _drop_demo_modules()
    identity = LibraryIdentity(
        name="wiredemo", label="Wire demo", folder_path=str(root), module_name="haybale_wiredemo"
    )
    yield root, identity, wire_path
    _drop_demo_modules()


def test_editing_a_wire_type_reaches_the_types_on_it(library):
    root, identity, wire_path = library
    registry = TypeRegistry()
    registry.add_folder(str(root / "types"), identity)
    assert registry.get(TYPE_KEY).class_identity.wire_type.pin_kind == "original"

    wire_path.write_text(_WIRE_SOURCE.format(kind="edited"))
    registry.event_dispatcher(
        FileChangeEvent(
            file_path=str(wire_path),
            event_type=FileEventType.MODIFIED,
            library_identity=identity,
            timestamp=time.time(),
        )
    )

    reloaded = registry.get(TYPE_KEY).class_identity.wire_type
    assert reloaded.id == WIRE_ID
    assert reloaded.pin_kind == "edited", "the type must be rebuilt on the edited wire type"
    assert get_wire_type(WIRE_ID).pin_kind == "edited", "the id map must hold the edited class"
```

- [ ] **Step 2: Run it**

Run: `uv run pytest tests/core/test_libraries/test_wire_type_hot_reload.py -q -p no:randomly`

Expected: 2 passed. The `types` case may log a re-promote warning from `_is_demoted_component`; that is expected.

On failure:
- Check the test against `tests/core/test_libraries/test_managed_module_demotion.py`, which drives the same API.
- If the test is right, stop and report which case fails and how.

- [ ] **Step 3: Ruff and commit**

Run the ruff check on the test file.

```bash
git add tests/core/test_libraries/test_wire_type_hot_reload.py
git commit -m "test(types): a library wire type hot-reloads into the types on it

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Edges derive their wire type

An edge stores no wire type. It answers with its outlet's, or with its inlet's when the outlet is a bare `ADD` slot or missing. The formal check uses `wires_match`.

Removed in this task:
- the saved `edge_type`;
- the dead `_edge_type is None` branch (deletion 4);
- `is_*_edge` (deletion 5);
- the callback statistics (deletion 7);
- `validate_edge`, together with the edge's structural step, which did nothing else (deletion 8);
- `_accepts_any_flow` and `edge_flow_type` (deletion 3);
- `RemappedEdge.edge_type` (deletion 12).

`create_edge_wrapper` no longer looks the outlet up, so a missing outlet no longer raises `KeyError`. The edge is added and fails validation, as on load (Q20).

**Files:**
- Modify:
  - `packages/haywire-core/src/haywire/core/edge/edge_wrapper.py`, `packages/haywire-core/src/haywire/core/edge/edge.py`
  - `packages/haywire-core/src/haywire/core/graph/base.py:591-633, 1022-1044`
  - `packages/haywire-core/src/haywire/core/graph/utils/node_remap.py:29-43, 107-117`
  - `packages/haywire-core/src/haywire/core/validation/interface.py:44-54`, `packages/haywire-core/src/haywire/core/validation/structural_validator.py:508-523`
  - `packages/haywire-core/src/haywire/core/assembly/flow_assembly_manager.py`, `packages/haywire-core/src/haywire/core/execution/interpreter.py:374-383`
  - `barn/haybale-graph-editor/haybale_graph_editor/farmhands/editor_tools.py:474-498, 527-533`
  - `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/connection_info_popup.py:46`
- Test:
  - `tests/core/test_edge/test_edge_wire_type.py` (create)
  - modify: `tests/core/graph/test_load_degradation.py`, `tests/core/test_graph/test_any_flow_slot.py`, `tests/core/test_undo/test_split_edge_reroute.py`, `tests/core/test_execution/test_control_payload.py`, `tests/farmhand/test_graph_editor_tools.py`

**Interfaces:**
- Consumes: Task 2's `DataPort.wire_type` and `wire_key`; Task 1's `wires_match`.
- Produces:
  - `EdgeWrapper.wire_type -> type[WireType] | None`.
  - The `EdgeWrapper(graph, source_node_id, outlet_port_id, sink_node_id, inlet_port_id, propagation=…)` constructor, with no `edge_type`.
  - `Edge` without `edge_type`.
  - Farmhand edge rows `{"wire_type": <id or None>, "role": <value or None>}`.
  - Until Task 5, `locked_propagation` answers `IMMEDIATE` for an edge on an `IMMEDIATE` wire.

- [ ] **Step 1: Write the failing tests**

Create `tests/core/test_edge/test_edge_wire_type.py`:

```python
"""An edge's wire type comes from its ports, and nothing about it is saved."""

import pytest

from haywire.core.graph.subgraph import SubgraphDefinition

from tests.conftest import make_node

pytestmark = pytest.mark.integration

_ADD = "haybale-testing:node:TestAddFloatNode"
_INPUT = "haywire-core:node:SubgraphInputNode"
_EMIT = "haybale-testing:node:TestEmitCallbackNode"


def test_a_data_edge_carries_its_outlets_wire_type(graph_with_library_system):
    from haywire.barn.builtin.wires import DataWire

    graph = graph_with_library_system
    source, sink = make_node(graph, _ADD), make_node(graph, _ADD)
    edge = graph.create_edge_wrapper(source.node_id, "result", sink.node_id, "value_a")

    assert edge.wire_type.id == DataWire.id


def test_an_edge_out_of_a_bare_add_slot_carries_what_it_feeds(graph_with_library_system):
    from haywire.barn.builtin.wires import CallbackWire

    definition = graph_with_library_system.add_subgraph(SubgraphDefinition(key="sg_wire", label="G"))
    input_node = make_node(definition, _INPUT)
    emitter = make_node(definition, _EMIT)
    slot = next(p for p in input_node.node.ports.values() if p.id.startswith("slot_"))
    edge = definition.create_edge_wrapper(input_node.node_id, slot.id, emitter.node_id, "edge_callback")

    assert edge.wire_type.id == CallbackWire.id


def test_ports_on_different_wire_types_do_not_link(graph_with_library_system):
    graph = graph_with_library_system
    emit, add = make_node(graph, _EMIT), make_node(graph, _ADD)
    edge = graph.create_edge_wrapper(emit.node_id, "exec", add.node_id, "value_a")

    assert not edge.state.is_formally_validated
    assert "Wire type mismatch" in edge.state.get_error().message


def test_an_edge_with_a_missing_outlet_is_kept_and_takes_its_inlets_wire_type(graph_with_library_system):
    from haywire.barn.builtin.wires import DataWire

    graph = graph_with_library_system
    source, sink = make_node(graph, _ADD), make_node(graph, _ADD)
    edge = graph.create_edge_wrapper(source.node_id, "gone", sink.node_id, "value_a")

    assert edge is not None
    assert not edge.state.is_valid()
    assert edge.wire_type.id == DataWire.id


def test_an_edge_saves_no_wire_type_and_ignores_a_saved_edge_type(graph_with_library_system):
    graph = graph_with_library_system
    source, sink = make_node(graph, _ADD), make_node(graph, _ADD)
    edge = graph.create_edge_wrapper(source.node_id, "result", sink.node_id, "value_a")
    data = graph.to_dict()
    assert "edge_type" not in data["edges"][edge.edge_id]

    data["edges"][edge.edge_id]["edge_type"] = "not-a-real-flow-type"
    graph.clear()
    graph.load_from_dict(data)

    assert graph.get_edge_wrapper(edge.edge_id) is not None
```

- [ ] **Step 2: Run them**

Run: `uv run pytest tests/core/test_edge/test_edge_wire_type.py -q`

Expected: FAIL.
- `EdgeWrapper` has no `wire_type`.
- The mismatch error says "Flow type mismatch".
- `create_edge_wrapper` raises `KeyError` on the missing outlet.
- `edge_type` is saved.
- The poisoned edge is dropped.

- [ ] **Step 3: `edge.py`**

In `packages/haywire-core/src/haywire/core/edge/edge.py`:
- Change the import to `from ..types import Propagation`.
- Delete the `# Edge classification` comment and the `edge_type: FlowType` field.
- Delete the `"edge_type": self.edge_type.value,` line from `to_dict`.

- [ ] **Step 4: `edge_wrapper.py`**

In `packages/haywire-core/src/haywire/core/edge/edge_wrapper.py`:

1. Imports. Replace `from ..types import FlowType, Propagation` with:

```python
from ..types import Propagation
from ..types.wire import WireRole, WireType, wires_match
```

and delete `from ..validation.interface import IStructuralValidator`.

2. **`EdgeWrapperState`.**
   - Delete the fields `is_structural` and `error_structural` with their docstrings.
   - In `is_valid`, return `self.is_functional() and self.is_linked`.
   - In `get_error`, delete the `error_structural` branch.

3. Delete `_accepts_any_flow` and `edge_flow_type` (lines 101-112).

4. **`__init__`.**
   - Delete the `edge_type: FlowType,` parameter and its `Args:` line.
   - Delete `self._edge_type = edge_type` and its comment.
   - Delete the `edge_type=self._edge_type,` argument to `Edge(...)`.
   - Delete the last line, `self._structural_validator: "IStructuralValidator" = self._graph._structural`.

5. Delete `is_callback_edge`, `is_control_edge` and `is_data_edge`.

6. Replace the `edge_type` property with:

```python
    @property
    def wire_type(self) -> Optional[type[WireType]]:
        """The wire type this edge carries: its outlet's, else its inlet's.

        An edge out of a bare ``ADD`` slot carries what it feeds. ``None`` until an
        end resolves (before the first build, or with both ports gone).
        """
        for port in (self._outlet_port, self._inlet_port):
            if port is not None and port.wire_type is not None:
                return port.wire_type
        return None
```

7. In `locked_propagation`, replace the `if self._edge_type is not None and self._edge_type.is_immediate:` test with:

```python
        wire = self.wire_type
        if wire is not None and wire.role is WireRole.IMMEDIATE:
```

and say "an immediate wire type" instead of "An immediate flow" in its docstring.

8. In `build`, replace the nested ifs with:

```python
        if self._formal_validation():
            if self._build_adapter_chain():
                if self._test():
                    logger.debug(".. rebuilding edge done.")
                    return
```

and delete the whole `_structural_validation` method.

9. **`_formal_validation`.**
   - Delete the lines `# Determine edge type if not set` / `if self._edge_type is None:` / `self._edge_type = self._outlet_port.flow_type`.
   - Replace the flow-type check (the `if self._outlet_port.flow_type != …` block) with:

```python
            if not wires_match(self._outlet_port.wire_key, self._inlet_port.wire_key):
                raise Exception(
                    f"Wire type mismatch between outlet ({self._outlet_port.wire_key}) and inlet "
                    f"({self._inlet_port.wire_key}) on edge {self._edge_id}"
                )
```

   - In the `except` block's suggestions, replace `"Check port flow types for compatibility"` with `"Check that both ports are on the same wire type"`.

10. In `__repr__`, replace the `type=` line with:

```python
            f"wire={self.wire_type.id if self.wire_type is not None else 'unknown'}, "
```

- [ ] **Step 5: Graph creation, load, remap**

In `packages/haywire-core/src/haywire/core/graph/base.py`, `create_edge_wrapper`:
- Delete the docstring line `The edge takes its flow type from the source outlet.`
- Replace the body down to the constructor with:

```python
        from ..edge.edge_wrapper import EdgeWrapper

        edge_wrapper = EdgeWrapper(
            graph=self,
            source_node_id=source_node_id,
            outlet_port_id=outlet_port_id,
            sink_node_id=sink_node_id,
            inlet_port_id=inlet_port_id,
            propagation=propagation,
        )
```

In `load_from_dict`, delete the line `edge_type=FlowType(edge_data["edge_type"]),`. A saved `edge_type` is no longer read.

Keep the `FlowType` import in `base.py`: `control_transitions` still uses it until Task 6.

In `packages/haywire-core/src/haywire/core/graph/utils/node_remap.py`, delete the `edge_type: str` field with its docstring, and the line `edge_type=edge["edge_type"],`.

- [ ] **Step 6: Delete `validate_edge` and the callback statistics**

- **`validation/interface.py`:** delete the abstract `validate_edge` method (lines 44-54) and any import used only by it.
- **`validation/structural_validator.py`:** delete `validate_edge` (lines 508-523).
- **`assembly/flow_assembly_manager.py`:**
  - Delete the two lines `# Process callback edges for observability` / `self._process_callback_edges(graph, flows)`.
  - Delete `_process_callback_edges`, `get_callback_edges` and `get_callback_triggers`.
  - Delete the `FlowType` import.
  - In `get_statistics`:
    - delete the `callback_edges` and `callback_triggers` locals;
    - delete the `"callback_edges"` and `"callback_topology"` keys;
    - delete the `"emits_callbacks"` and `"receives_callbacks"` entries of each flow row;
    - say "Assembly statistics" instead of "including callback topology" in the docstring.
- **`execution/interpreter.py`:** delete the `"callback_topology": …` line and the words "including callback topology" from the docstring.

Then check for stragglers:

Run: `grep -rn "validate_edge\|callback_topology\|get_callback_edges\|get_callback_triggers\|_process_callback_edges\|is_structural\|error_structural\|_structural_validator" --include='*.py' packages barn tests`

Expected:

- Hits in `core/node/node_wrapper.py` only: the node's own structural state and validator, which stay.
- The one test hit, `tests/core/test_undo/test_split_edge_reroute.py::test_callback_edge_from_reroute_is_valid`, is deleted in Step 8.
- Any other hit is a reader to update the same way.

- [ ] **Step 7: Farmhand and the info popup**

In `barn/haybale-graph-editor/haybale_graph_editor/farmhands/editor_tools.py`, `_edge_row`, replace the `"flow_type": …` line with:

```python
        "wire_type": edge.wire_type.id if edge.wire_type is not None else None,
        "role": edge.wire_type.role.value if edge.wire_type is not None else None,
```

In the `query_graph` instructions string, replace `id/topology/flow_type per edge` with `id/topology/wire_type/role per edge`.

In `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/connection_info_popup.py:46`, replace the label text `f"{edge.edge_type}"` with:

```python
edge.wire_type.id if edge.wire_type is not None else ""
```

- [ ] **Step 8: Update the existing tests**

- **`tests/core/graph/test_load_degradation.py`**, `test_poisoned_edge_skips_only_itself`:
  - Replace the poison line `data["edges"][first_edge_id]["edge_type"] = "not-a-real-flow-type"` with `del data["edges"][first_edge_id]["source_node_id"]`.
  - Replace the comment above it with: `# Poison the first edge with a missing key, which raises KeyError in the loop body.`
- **`tests/core/test_graph/test_any_flow_slot.py`**, line 60: replace `assert edge.edge_type is FlowType.CALLBACK` with the snippet below. Lines 61-62 change in Tasks 5 and 6.

```python
from haywire.barn.builtin.wires import CallbackWire

assert edge.wire_type.id == CallbackWire.id
```

- **`tests/core/test_undo/test_split_edge_reroute.py`:**
  - Line 424: replace `assert edge._edge_type == FlowType.CONTROL` with the snippet below (import inside the test).

```python
from haywire.barn.builtin.wires import ControlWire

assert edge.wire_type.id == ControlWire.id
```

  - Delete `test_callback_edge_from_reroute_is_valid` (lines 502-523).
- **`tests/core/test_execution/test_control_payload.py:38`:** replace `assert edge.is_control_edge()` with the snippet below (import at the top of the file).

```python
from haywire.core.types import WireRole

assert edge.wire_type.role is WireRole.SEQUENCE
```

- **`tests/farmhand/test_graph_editor_tools.py`:**
  - `test_query_labels_callback_ports_and_edges`: replace `cb_edges = [e for e in graph["edges"] if e["flow_type"] == "callback"]` with:

```python
cb_edges = [e for e in graph["edges"] if e["role"] == "immediate"]
```

    and update the docstring's "flow_type='callback'" to "role 'immediate'". The port assertion at line 143 changes in Task 7.
  - `test_query_edge_detail_reports_health_and_adapter_chain`: in the plain-edge key set, replace `"flow_type"` with `"wire_type", "role"`.

- [ ] **Step 9: Run the edge tests, then the gate**

Run: `uv run pytest tests/core/test_edge tests/core/graph tests/core/test_graph tests/core/test_undo tests/core/test_execution tests/farmhand -q -n 4`
Expected: PASS.

Run the ruff check and mypy on the changed files, then the pre-commit gate. Expected: green.

- [ ] **Step 10: Commit**

```bash
git add packages/haywire-core/src/haywire/core/edge/ packages/haywire-core/src/haywire/core/graph/base.py packages/haywire-core/src/haywire/core/graph/utils/node_remap.py packages/haywire-core/src/haywire/core/validation/interface.py packages/haywire-core/src/haywire/core/validation/structural_validator.py packages/haywire-core/src/haywire/core/assembly/flow_assembly_manager.py packages/haywire-core/src/haywire/core/execution/interpreter.py barn/haybale-graph-editor/haybale_graph_editor/farmhands/editor_tools.py barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/connection_info_popup.py tests/core/test_edge/test_edge_wire_type.py tests/core/graph/test_load_degradation.py tests/core/test_graph/test_any_flow_slot.py tests/core/test_undo/test_split_edge_reroute.py tests/core/test_execution/test_control_payload.py tests/farmhand/test_graph_editor_tools.py
git commit -m "refactor(edges): an edge derives its wire type from its ports

Edges no longer store or save an edge_type; a saved one is ignored. The
formal check is wires_match. A missing outlet no longer raises on creation:
the edge is kept and fails validation, like a loaded one.

Removes the no-op validate_edge with the edge's structural step, the
callback statistics nothing read, is_*_edge, and RemappedEdge.edge_type.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Propagation comes from the wire type; callback edges have none (Q19)

`Propagation` keeps `LAZY` and `EAGER`.
- An edge's mode must be in its wire type's `propagation`.
- A wire type with an empty tuple gives the edge no propagation: `EdgeWrapper.propagation is None`, the pipe pushes, and nothing is saved.
- The chosen mode is fitted to the wire type only once the edge has validated (Q20). An edge that fails validation keeps what it loaded.

**Files:**
- Modify:
  - `packages/haywire-core/src/haywire/core/types/enums.py:33-56`
  - `packages/haywire-core/src/haywire/core/edge/edge.py`, `packages/haywire-core/src/haywire/core/edge/edge_wrapper.py`, `packages/haywire-core/src/haywire/core/graph/base.py:597-612` (docstring)
  - `barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/edge/edge.py:200-279`
  - `barn/haybale-graph-editor/haybale_graph_editor/panels/properties/introspect/edge.py:107-154`
  - `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/context_menu.py:495-504`
  - `barn/haybale-graph-editor/haybale_graph_editor/farmhands/editor_tools.py:488-492`
- Test: modify `tests/core/test_edge/test_edge_propagation.py`, `tests/core/test_graph/test_any_flow_slot.py:61`, `tests/ui/graph_canvas/test_session_context_menu_provider.py`; create `tests/ui/panels/test_edge_propagation_panel_poll.py`

**Interfaces:**
- Consumes: Task 4's `EdgeWrapper.wire_type`; Task 1's `WireType.clamp`.
- Produces:
  - `EdgeWrapper.propagation -> Propagation | None`.
  - `EdgeWrapper.locked_propagation -> Propagation | None`: a single allowed mode, or `LAZY` out of an `is_linked_lazy` outlet.
  - `Edge.propagation: Propagation | None`.
  - `Propagation` with two members.

- [ ] **Step 1: Write the failing tests**

In `tests/core/test_edge/test_edge_propagation.py`:
- Change the module docstring's first line to: `An edge's propagation: the user's lazy/eager choice, the mode an outlet locks, and edges that have none.`
- Delete `test_immediate_cannot_be_chosen`, `test_immediate_cannot_be_passed_at_creation` and `test_immediate_does_not_toggle`.
- Replace `TestLockedModes.test_a_callback_edge_is_locked_immediate` and `test_a_locked_edge_refuses_a_choice` with:

```python
    def test_a_callback_edge_has_no_propagation(self, callback_edge):
        event, edge = callback_edge

        assert edge.propagation is None
        assert edge.locked_propagation is None
        assert _pipe_modes(event.node.ports["listen_callback"]) == [False]

    def test_a_callback_edge_refuses_a_choice(self, callback_edge):
        _event, edge = callback_edge

        with pytest.raises(ValueError, match="cannot take"):
            edge.propagation = Propagation.LAZY
```

- Replace `TestSaving.test_a_locked_mode_is_not_saved` with:

```python
    def test_a_callback_edge_saves_no_propagation(self, callback_edge):
        _event, edge = callback_edge

        assert "propagation" not in edge.edge.to_dict()

    def test_a_mode_loaded_into_an_edge_that_fails_validation_is_kept(self, linked_pair):
        """Q20: an edge that does not validate is never rewritten."""
        graph, _source, _sink, edge = linked_pair
        edge.propagation = Propagation.LAZY
        edge_id = edge.edge_id
        data = graph.to_dict()
        data["edges"][edge_id]["inlet_port_id"] = "gone"

        graph.clear()
        graph.load_from_dict(data)
        reloaded = next(iter(graph.edge_wrappers.values()))

        assert not reloaded.state.is_valid()
        assert reloaded.edge.to_dict()["propagation"] == "lazy"
```

In `tests/core/test_graph/test_any_flow_slot.py:61`, replace `assert edge.propagation is Propagation.IMMEDIATE` with `assert edge.propagation is None`, and drop `Propagation` from the import if nothing else uses it.

In `tests/ui/graph_canvas/test_session_context_menu_provider.py`, replace `test_toggle_edge_propagation_leaves_a_locked_edge_alone` with:

```python
def test_toggle_edge_propagation_leaves_a_locked_edge_alone():
    from haywire.core.types import Propagation

    edge = _FakeEdge(Propagation.EAGER, locked=Propagation.LAZY)
    provider = _provider_with_edge(edge)

    assert provider.toggle_edge_propagation("e1") is Propagation.LAZY
    assert edge.chosen is Propagation.EAGER
    assert edge.redraws == 0


def test_toggle_edge_propagation_leaves_an_edge_without_propagation_alone():
    edge = _FakeEdge(None)
    provider = _provider_with_edge(edge)

    assert provider.toggle_edge_propagation("e1") is None
    assert edge.redraws == 0
```

Create `tests/ui/panels/test_edge_propagation_panel_poll.py` (create the directory if it is missing, with an empty `__init__.py` only if sibling test directories have one):

```python
"""The edge inspector's propagation panel applies only to an edge that has propagation."""

from types import SimpleNamespace

import pytest

from haybale_graph_editor.panels.properties.introspect.edge import EdgePropagationPanel
from haybale_graph_editor.state.edit_state import EditState
from haywire.core.types import Propagation

pytestmark = pytest.mark.unit


def _ctx(edge):
    return SimpleNamespace(data={EditState: SimpleNamespace(active_edge=edge)})


def test_it_applies_to_an_edge_with_propagation():
    assert EdgePropagationPanel.poll(_ctx(SimpleNamespace(propagation=Propagation.EAGER)))


def test_it_does_not_apply_to_an_edge_without_propagation():
    assert not EdgePropagationPanel.poll(_ctx(SimpleNamespace(propagation=None)))


def test_it_does_not_apply_without_an_edge():
    assert not EdgePropagationPanel.poll(_ctx(None))
```

- [ ] **Step 2: Run them**

Run: `uv run pytest tests/core/test_edge/test_edge_propagation.py tests/core/test_graph/test_any_flow_slot.py tests/ui/graph_canvas/test_session_context_menu_provider.py tests/ui/panels/test_edge_propagation_panel_poll.py -q`

Expected: the new and changed tests FAIL.
- A callback edge reports `IMMEDIATE`.
- `to_dict` writes `"propagation"`.
- The toggle calls `None.toggled()`.
- The panel polls true for an edge without propagation.

`test_a_mode_loaded_into_an_edge_that_fails_validation_is_kept` already passes: it guards Q20 through the change.

- [ ] **Step 3: `Propagation`**

In `packages/haywire-core/src/haywire/core/types/enums.py`, replace the `Propagation` class with:

```python
class Propagation(Enum):
    """When a value written to an outlet takes effect at the inlet across an edge.

    - ``LAZY``: the inlet pulls the outlet's current value when its node next executes.
    - ``EAGER``: pushed on write; takes effect when the inlet's node next executes.

    Which modes an edge may take is its wire type's ``propagation``. An edge on a
    wire type that allows none has no propagation (``None``): callback edges take
    effect on write, by their role. Wire values are the member strings, as saved
    in a graph's edge block.
    """

    LAZY = "lazy"
    EAGER = "eager"

    def toggled(self) -> "Propagation":
        """Return the other mode: ``LAZY`` for ``EAGER``, and back."""
        return Propagation.LAZY if self is Propagation.EAGER else Propagation.EAGER
```

- [ ] **Step 4: `Edge` and `EdgeWrapper`**

In `packages/haywire-core/src/haywire/core/edge/edge.py`, replace the `propagation` field and its docstring with:

```python
    propagation: Propagation | None = Propagation.EAGER
    """The mode chosen for this edge, ``None`` once fitted to a wire type that allows none.
    A locked mode overrides it; see ``EdgeWrapper.propagation``."""
```

and in `to_dict`, return the dict without the `propagation` key, then add it only when set:

```python
        data: dict[str, Any] = {
            "source_node_id": self.source_node_id,
            "outlet_port_id": self.outlet_port_id,
            "sink_node_id": self.sink_node_id,
            "inlet_port_id": self.inlet_port_id,
            "chain_adapter_keys": self.chain_adapter_keys,
        }
        if self.propagation is not None:
            data["propagation"] = self.propagation.value
        return data
```

In `packages/haywire-core/src/haywire/core/edge/edge_wrapper.py`:

1. In `__init__`:
   - Delete the `IMMEDIATE` refusal (the two lines `if propagation is Propagation.IMMEDIATE:` / `raise ValueError(...)`) and its `Raises:` section.
   - Change the `propagation` arg doc to: `propagation: The mode chosen for the edge. It is fitted to the wire type once the edge validates.`
2. Delete `WireRole` from the `..types.wire` import.
3. Replace `locked_propagation`, the `propagation` getter and the setter with:

```python
    @property
    def locked_propagation(self) -> Optional[Propagation]:
        """The mode this edge is fixed to, or ``None`` when the user may choose one.

        An edge out of an ``is_linked_lazy`` outlet (every promoted outlet) is locked
        ``LAZY``, and a wire type that allows a single mode locks that mode. An edge
        whose wire type allows no mode has no lock and no propagation.
        """
        if self._outlet_port is not None and self._outlet_port.is_linked_lazy:
            return Propagation.LAZY
        wire = self.wire_type
        if wire is not None and len(wire.propagation) == 1:
            return wire.propagation[0]
        return None

    @property
    def propagation(self) -> Optional[Propagation]:
        """The mode in effect, or ``None`` for an edge whose wire type allows none."""
        wire = self.wire_type
        if wire is not None and not wire.propagation:
            return None
        return self.locked_propagation or self._edge.propagation

    @propagation.setter
    def propagation(self, value: Propagation) -> None:
        """Choose a mode for this edge and rebuild its pipe.

        Raises:
            ValueError: If the edge's wire type does not allow *value* (a callback edge
                allows none), or the edge's mode is locked.
        """
        wire = self.wire_type
        if wire is not None and value not in wire.propagation:
            raise ValueError(f"edge {self._edge_id} on {wire.id} cannot take {value.value} propagation")
        locked = self.locked_propagation
        if locked is not None:
            raise ValueError(f"edge {self._edge_id} is locked to {locked.value} propagation")
        if self._edge.propagation is value:
            return
        self._edge.propagation = value
        if self._outlet_port is not None:
            self._outlet_port._mark_as_structuraly_dirty()
            self._outlet_port._housekeeping()
```

   The last three lines repeat the existing setter's tail. Keep whatever the current tail does, verbatim.

4. In `build`, fit the mode right after a successful formal validation:

```python
        if self._formal_validation():
            self._fit_propagation()
            if self._build_adapter_chain():
```

   and add the method after `build`:

```python
    def _fit_propagation(self) -> None:
        """Fit the chosen mode to the wire type; runs only once the edge has validated."""
        wire = self.wire_type
        if wire is not None:
            self._edge.propagation = wire.clamp(self._edge.propagation)
```

In `packages/haywire-core/src/haywire/core/graph/base.py`, in `create_edge_wrapper`'s docstring, change the `propagation` arg to: `propagation: The mode chosen for the edge; the wire type fits or locks it.` Then delete the `Raises:` line about `IMMEDIATE`.

- [ ] **Step 5: The edge panels, the toggle, Farmhand**

**Edge menu** (`barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/edge/edge.py`, `EdgePropagationMenuPanel`):
- Delete the `Propagation.IMMEDIATE` entries from `_LABELS`, `_ICONS` and `_LOCKED_TOOLTIPS`.
- In the docstring, change "Propagation: Lazy/Eager/Immediate" to "Propagation: Lazy/Eager".
- Add the sentence "An edge without propagation (a callback edge) draws no row." to the docstring. The `if mode is None: return` already does this.

**Inspector panel** (`barn/haybale-graph-editor/haybale_graph_editor/panels/properties/introspect/edge.py`, `EdgePropagationPanel`): replace `poll` with:

```python
    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        edge = ctx.data[EditState].active_edge
        return edge is not None and edge.propagation is not None
```

**Toggle** (`barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/context_menu.py`, `toggle_edge_propagation`): replace the body after the `wrapper is None` check with:

```python
        if wrapper.propagation is not None and wrapper.locked_propagation is None:
            wrapper.propagation = wrapper.propagation.toggled()
            wrapper.redraw()
        return wrapper.propagation
```

**Farmhand** (`barn/haybale-graph-editor/haybale_graph_editor/farmhands/editor_tools.py`, `_edge_row`): replace `"propagation": edge.propagation.value,` with:

```python
                "propagation": edge.propagation.value if edge.propagation is not None else None,
```

- [ ] **Step 6: Run the tests, then the gate**

Run the four files from Step 2, then `uv run pytest tests/core/test_edge tests/ui -m "not browser" -q -n 4`.
Expected: PASS.

Then: `grep -rn "Propagation.IMMEDIATE\|IMMEDIATE.toggled" --include='*.py' packages barn tests`
Expected: no hits.

Run the ruff check and mypy on the changed files, then the pre-commit gate. Expected: green.

- [ ] **Step 7: Commit**

```bash
git add packages/haywire-core/src/haywire/core/types/enums.py packages/haywire-core/src/haywire/core/edge/ packages/haywire-core/src/haywire/core/graph/base.py barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/edge/edge.py barn/haybale-graph-editor/haybale_graph_editor/panels/properties/introspect/edge.py barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/context_menu.py barn/haybale-graph-editor/haybale_graph_editor/farmhands/editor_tools.py tests/core/test_edge/test_edge_propagation.py tests/core/test_graph/test_any_flow_slot.py tests/ui/graph_canvas/test_session_context_menu_provider.py tests/ui/panels/
git commit -m "feat(edges): propagation comes from the wire type; callback edges have none

Propagation keeps lazy and eager. A wire type lists the modes its edges may
take; one entry locks it, none means the edge has no propagation. A callback
edge now has none: its menu row and inspector panel hide, Farmhand reports
null, and nothing is saved. The chosen mode is fitted to the wire type only
once the edge validates, so an edge that fails keeps what it loaded.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Nodes, assembly and validation ask the role

`NodeData.get_ports` filters by role, and `NodeData.has_sequence_pins()` replaces three separate "is control crossing" checks. The data walk and the DATA-node outlet rule use `DataPort.is_dependent`, so a bare `ADD` slot still counts as data.

**Files:**
- Modify:
  - `packages/haywire-core/src/haywire/core/node/data.py:609-634`
  - `packages/haywire-core/src/haywire/core/graph/base.py:722`
  - `packages/haywire-core/src/haywire/core/assembly/flat_view.py:38, 148, 163, 210, 228, 248, 320-322`
  - `packages/haywire-core/src/haywire/core/assembly/data_flow_builder.py:20, 59, 135-137, 150, 185, 251`
  - `packages/haywire-core/src/haywire/core/validation/structural_validator.py:16, 147, 176-192, 231-241, 416`
  - `packages/haywire-core/src/haywire/barn/builtin/nodes/graph_node.py:39, 310, 334, 336`
  - `packages/haywire-core/src/haywire/barn/builtin/nodes/subgraph_io.py:235, 295`
  - `packages/haywire-core/src/haywire/core/types/registry.py:11, 119-140`
- Test: create `tests/core/test_node/test_ports_by_role.py`; modify `tests/core/test_undo/test_split_edge_reroute.py:214-330`, `tests/core/node/test_boundary_nodes.py:33`, `tests/core/test_graph/test_any_flow_slot.py:37, 49, 62`

**Interfaces:**
- Consumes: Task 2's `DataPort.has_role`, `is_dependent`, `wire_key`.
- Produces:
  - `NodeData.get_ports(is_port_type=None, has_pin=None, is_role: WireRole | None = None, is_not_role: WireRole | None = None, has_widget=None)`. `is_not_role` keeps only ports *with* a wire type whose role differs.
  - `NodeData.has_sequence_pins() -> bool`.

- [ ] **Step 1: Write the failing tests**

Create `tests/core/test_node/test_ports_by_role.py`:

```python
"""Port queries by wire role, and the one check for control crossing a node."""

import pytest

from haywire.core.types import PortType, WireRole

from tests.conftest import make_node

pytestmark = pytest.mark.integration


def test_get_ports_by_role(graph_with_library_system):
    from haybale_testing.nodes.testbed.emit_callback_node import TestEmitCallbackNode

    node = make_node(graph_with_library_system, TestEmitCallbackNode.class_identity.registry_key).node

    sequence = {p.id for p in node.get_ports(is_role=WireRole.SEQUENCE)}
    immediate = {p.id for p in node.get_ports(is_port_type=PortType.INLET, is_role=WireRole.IMMEDIATE)}

    assert sequence == {"execute", "exec"}
    assert immediate == {"edge_callback"}


def test_is_not_role_leaves_out_ports_without_a_wire_type(graph_with_library_system):
    from haybale_testing.nodes.testbed.add_port_test import AddPortTestNode

    node = make_node(graph_with_library_system, AddPortTestNode.class_identity.registry_key).node

    assert node.get_ports(is_not_role=WireRole.DEPENDENT, has_pin=True) == []


def test_has_sequence_pins(graph_with_library_system):
    from haybale_testing.nodes.testbed.emit_callback_node import TestEmitCallbackNode
    from haybale_testing.nodes.testbed.math_op_node import TestAddFloatNode

    graph = graph_with_library_system
    emit = make_node(graph, TestEmitCallbackNode.class_identity.registry_key).node
    add = make_node(graph, TestAddFloatNode.class_identity.registry_key).node

    assert emit.has_sequence_pins()
    assert not add.has_sequence_pins()


def test_a_data_node_whose_only_outlet_is_a_bare_add_slot_is_valid(graph_with_library_system):
    from haybale_testing.nodes.testbed.add_port_test import AddPortTestNode

    wrapper = make_node(graph_with_library_system, AddPortTestNode.class_identity.registry_key)
    graph_with_library_system.force_validation()

    assert wrapper.is_valid()
```

- [ ] **Step 2: Run them**

Run: `uv run pytest tests/core/test_node/test_ports_by_role.py -q`

Expected: the first three FAIL, because `get_ports` has no `is_role`/`is_not_role` and there is no `has_sequence_pins`. The fourth passes already: it guards the change.

- [ ] **Step 3: `NodeData`**

In `packages/haywire-core/src/haywire/core/node/data.py`:
- Import: replace `from ..types.enums import FlowType, PortOrigin, PortType` with:

```python
from ..types.enums import PortOrigin, PortType
from ..types.wire import WireRole
```

- Replace `get_ports` with:

```python
    def get_ports(
        self,
        is_port_type: Optional[PortType] = None,
        has_pin: Optional[bool] = None,
        is_role: Optional[WireRole] = None,
        is_not_role: Optional[WireRole] = None,
        has_widget: Optional[bool] = None,
    ) -> list[DataPort]:
        """Return the ports matching every filter given. ``None`` disables a filter.

        Args:
            is_port_type: Keep ports of this ``PortType``.
            has_pin: Keep ports that do, or do not, draw a visual pin.
            is_role: Keep ports whose wire type has this role.
            is_not_role: Keep ports that have a wire type, of another role. A port
                without a wire type (a config port, a bare ``ADD`` slot) is left out.
            has_widget: Keep ports that do, or do not, carry a widget.
        """
        return [
            port
            for port in self.ports.values()
            if (is_port_type is None or is_port_type == port.port_type)
            and (has_pin is None or has_pin == port.has_pin())
            and (is_role is None or port.has_role(is_role))
            and (is_not_role is None or (port.wire_type is not None and not port.has_role(is_not_role)))
            and (has_widget is None or has_widget == port.widget_key is not None)
        ]

    def has_sequence_pins(self) -> bool:
        """True if this node carries a pin on a ``SEQUENCE`` wire, a control pin."""
        return bool(self.get_ports(is_role=WireRole.SEQUENCE, has_pin=True))
```

- Then: `grep -n "FlowType" packages/haywire-core/src/haywire/core/node/data.py`. Expected: no hits.

- [ ] **Step 4: The callers**

**`core/graph/base.py:722`:** use `is_role=WireRole.SEQUENCE` in place of `is_flow_type=FlowType.CONTROL`. Import `WireRole` from `..types.wire`. Remove `FlowType` from the `..types` import if nothing else uses it.

**`core/assembly/flat_view.py`:**
- Lines 148 and 163: `is_role=WireRole.SEQUENCE` in place of `is_flow_type=FlowType.CONTROL`.
- Delete `_is_control_crossed` (lines 320-322). At its three call sites (210, 228, 248), use `<wrapper>.node.has_sequence_pins()` with the same negation the call site has today.
- Import `WireRole` from `haywire.core.types.wire`; drop `FlowType` from the `enums` import.

**`core/assembly/data_flow_builder.py`:**
- The four port filters (59, 150, 185, 251): replace `port.flow_type == FlowType.DATA and port.is_inlet()` with `port.is_dependent and port.is_inlet()`, and likewise for `is_outlet()`.
- Lines 135-137: replace the `is_control = any(...)` expression with `is_control = source_node.has_sequence_pins()`.
- Delete the `FlowType` import.

**`core/validation/structural_validator.py`:**
- Line 147: `node.get_ports(is_port_type=PortType.OUTLET, is_role=WireRole.SEQUENCE)`.
- Line 176: `node.get_ports(is_not_role=WireRole.DEPENDENT, has_pin=True)`, with the message "Data nodes cannot have pins on control or callback ports".
- Lines 188-192:

```python
        # A bare ADD slot counts: it is a data outlet until it grows.
        if not any(port.is_dependent for port in node.get_ports(is_port_type=PortType.OUTLET)):
            return (
                False,
                "Data nodes must have at least one data outlet",
                ["Add at least one outlet on a data wire type to the node"],
            )
```

- Lines 231-241, the reroute rule, compare wire keys:

```python
        # The inlet and outlet must carry the same wire type.
        inlet_wire = inlets[0].wire_key
        outlet_wire = outlets[0].wire_key
        if inlet_wire != outlet_wire:
            return (
                False,
                (
                    f"A reroute's inlet and outlet must be on the same wire type "
                    f"(inlet={inlet_wire}, outlet={outlet_wire})"
                ),
                ["Reroute passes one type straight through; inlet and outlet must match"],
            )
```

- Line 416: `is_role=WireRole.SEQUENCE`.
- Replace the `FlowType` import with `from haywire.core.types.wire import WireRole`.
- Update the reroute docstring's "same FlowType" / "Mixed FlowTypes" to "same wire type" / "Different wire types".

**`barn/builtin/nodes/graph_node.py`:**
- Line 310: `control = self.has_sequence_pins()`.
- Lines 334, 336: `is_role=WireRole.SEQUENCE`.
- Replace the `FlowType` import with `from haywire.core.types.wire import WireRole`.

**`barn/builtin/nodes/subgraph_io.py`:** lines 235 and 295 become `if outlet.has_role(WireRole.SEQUENCE):` / `if inlet.has_role(WireRole.SEQUENCE):`. Add `from haywire.core.types.wire import WireRole`. `FlowType` stays imported until Task 9.

**`core/types/registry.py`, `get_type_for_python_type`:**
- Replace the filter `and FlowType(cls.class_identity.flow_type) is FlowType.DATA` with:

```python
            and _is_value_type(cls)
```

- Add, above the class:

```python
def _is_value_type(cls: type) -> bool:
    """True for a type on a ``DEPENDENT`` wire: one whose values a setting can hold."""
    wire = wire_type_of(cls)
    return wire is not None and wire.role is WireRole.DEPENDENT
```

- Import `from .wire import WireRole, wire_type_of`; drop `FlowType`.
- In the docstring: "Only types on a ``DEPENDENT`` wire are candidates".

Then: `grep -rn "is_flow_type\|is_not_flow_type\|_is_control_crossed" --include='*.py' packages barn`. Expected: no hits.

- [ ] **Step 5: Update the test fakes and assertions**

**`tests/core/test_undo/test_split_edge_reroute.py`:** replace `_reroute_validator_with_ports` with:

```python
def _reroute_validator_with_ports(ports):
    """Build a StructuralValidator + a fake REROUTE wrapper holding `ports`.

    Each port is (port_type, wire_type, has_pin).
    """
    from haywire.barn.builtin import wires
    from haywire.core.validation.structural_validator import StructuralValidator
    from haywire.core.node.behavior import NodeBehaviorFlags, NodeType
    from haywire.core.types.enums import PortType

    class _Port:
        def __init__(self, port_type, wire_type, has_pin):
            self.id = f"{port_type}-{wire_type.id}"
            self.port_type = port_type
            self.wire_key = wire_type.id
            self.widget_key = None
            self._has_pin = has_pin

        def has_pin(self):
            return self._has_pin

    port_objs = [_Port(pt, wt, hp) for (pt, wt, hp) in ports]

    class _Node:
        behavior = NodeBehaviorFlags(node_type=NodeType.REROUTE)

        def __init__(self):
            self.ports = {p.id: p for p in port_objs}

        def get_ports(self, is_port_type=None, has_pin=None, **_filters):
            return [
                p
                for p in self.ports.values()
                if (is_port_type is None or is_port_type == p.port_type)
                and (has_pin is None or has_pin == p.has_pin())
            ]

    class _Wrapper:
        node = _Node()

    validator = StructuralValidator.__new__(StructuralValidator)
    return validator, _Wrapper(), wires, PortType
```

In the six tests using it, unpack `wires` in place of `FlowType`:

```python
_, _, wires, PortType = _reroute_validator_with_ports([])
```

and write `wires.DataWire`, `wires.ControlWire`, `wires.CallbackWire` in place of `FlowType.DATA`, `FlowType.CONTROL`, `FlowType.CALLBACK`. In `test_validate_reroute_rejects_mixed_flow_types`, say "different wire types" in the docstring. The reroute port assertions in `test_split_control_edge_inserts_reroute` (lines 450-451) become:

```python
        assert reroute.ports["in"].wire_type.id == ControlWire.id
        assert reroute.ports["out"].wire_type.id == ControlWire.id
```

Remove the now-unused `FlowType` imports from the file.

**`tests/core/node/test_boundary_nodes.py:33`:** rename the fake's `is_flow_type=None` parameter to `is_role=None`.

**`tests/core/test_graph/test_any_flow_slot.py`:**
- Lines 37, 49, 62 assert a port's flow. Replace them with `ports[slot.id].wire_type.id == ControlWire.id` (37), `… == CallbackWire.id` (49) and `input_node.node.ports[slot.id].wire_type.id == CallbackWire.id` (62), importing the wires at the top.
- Drop the `FlowType` import.
- Module docstring: "grows a port of whatever wire type connects to it".

- [ ] **Step 6: Run the tests, then the gate**

Run: `uv run pytest tests/core/test_node tests/core/test_undo tests/core/node tests/core/test_graph tests/core/test_types tests/core/test_assembly tests/core/test_validation -q -n 4`. Any of those directories that does not exist is skipped by pytest with "file or directory not found". Drop it from the command.
Expected: PASS.

Run the ruff check and mypy on the changed files, then the pre-commit gate. Expected: green.

- [ ] **Step 7: Commit**

```bash
git add packages/haywire-core/src/haywire/core/node/data.py packages/haywire-core/src/haywire/core/graph/base.py packages/haywire-core/src/haywire/core/assembly/flat_view.py packages/haywire-core/src/haywire/core/assembly/data_flow_builder.py packages/haywire-core/src/haywire/core/validation/structural_validator.py packages/haywire-core/src/haywire/barn/builtin/nodes/graph_node.py packages/haywire-core/src/haywire/barn/builtin/nodes/subgraph_io.py packages/haywire-core/src/haywire/core/types/registry.py tests/core/test_node/test_ports_by_role.py tests/core/test_undo/test_split_edge_reroute.py tests/core/node/test_boundary_nodes.py tests/core/test_graph/test_any_flow_slot.py
git commit -m "refactor(nodes): nodes, assembly and validation ask the wire role

get_ports filters by role, and has_sequence_pins() replaces the data walk's
stop, flat_view._is_control_crossed and the Graph-node's own check. The data
walk and the DATA-node outlet rule count a bare ADD slot as data, as before.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: Introspection reports `wire_type` and `role`

**Files:**
- Modify:
  - `packages/haywire-core/src/haywire/core/node/inspector.py:17-27, 76-89`
  - `barn/haybale-graph-editor/haybale_graph_editor/farmhands/editor_tools.py:70-85, 128-149, 198-214, 235-237, 527-533`
  - `packages/haywire-studio/src/haywire_studio/packaging/docs/extract.py:18-24`
- Test: modify `tests/core/test_node/test_inspector.py:23`, `tests/studio/test_docs/test_render.py:76, 101-103`, `tests/farmhand/test_graph_editor_tools.py:71, 95, 135, 143`; create `tests/studio/test_docs/test_extract_wire_type.py`

**Interfaces:**
- Consumes: Task 2's `DataPort.wire_type` and `wire_key`, and `DataTypeIdentity.wire_type`.
- Produces:
  - `PortInfo(id, direction, label, description, wire_type: str | None, role: str | None, data_type, hidden, deprecation)`.
  - Farmhand port rows with `"wire_type"` (the `wire_key`, so `"*"` for a bare `ADD` slot) and `"role"`.
  - The docs extractor's `"wire_type"` key (an id, or `None`, which the renderer skips).

- [ ] **Step 1: Write the failing tests**

**`tests/core/test_node/test_inspector.py:23`.** Replace `assert p.flow_type in ("data", "control", "callback", "none")` with:

```python
        assert p.role in ("dependent", "sequence", "immediate", None)
        assert p.wire_type is None or ":wire:" in p.wire_type or p.wire_type == "*"
```

**`tests/studio/test_docs/test_render.py`.** In the four positional `PortInfo(...)` calls, replace the single `"data"` argument with the two arguments `"haywire-core:wire:DataWire", "dependent"`.

**`tests/farmhand/test_graph_editor_tools.py`:**
- Line 71: `assert set(port) == {"id", "direction", "wire_type", "role"}`.
- Line 95: `data_port = next(p for p in node["ports"] if p["role"] == "dependent")`.
- Line 143: `assert outlet["role"] == "immediate"`.
- Line 135 and the comment at 140 already changed in Task 4.
- The docstring at 103: "Callback ports carry role 'immediate'".

Create `tests/studio/test_docs/test_extract_wire_type.py`:

```python
"""The generated type docs name a type's wire type, and a container's has none."""

import pytest

from haywire_studio.packaging.docs.extract import _extra_for_kind

pytestmark = pytest.mark.unit


def test_a_value_type_names_its_wire_type():
    from haywire.barn.builtin.types import EXEC

    assert _extra_for_kind("type", EXEC, EXEC.class_identity)["wire_type"] == "haywire-core:wire:ControlWire"


def test_a_container_names_none():
    from haybale_core.types import ArrayType

    assert _extra_for_kind("type", ArrayType, ArrayType.class_identity)["wire_type"] is None
```

- [ ] **Step 2: Run them**

Run: `uv run pytest tests/core/test_node/test_inspector.py tests/studio/test_docs/test_render.py tests/studio/test_docs/test_extract_wire_type.py tests/farmhand/test_graph_editor_tools.py -q -n 4`
Expected: FAIL. `PortInfo` has `flow_type`, and the extractor emits `flow_type`.

- [ ] **Step 3: `PortInfo` and the inspector**

In `packages/haywire-core/src/haywire/core/node/inspector.py`, replace the `flow_type: str` field with:

```python
    wire_type: str | None
    """The wire type's id, ``"*"`` for a bare ``ADD`` slot, ``None`` for a config port."""
    role: str | None
    """The wire type's role value, such as ``"dependent"``; ``None`` without a wire type."""
```

and in `ports()`, replace `flow_type=port.flow_type.value,` with:

```python
                    wire_type=port.wire_key,
                    role=port.wire_type.role.value if port.wire_type is not None else None,
```

- [ ] **Step 4: Farmhand port rows**

In `barn/haybale-graph-editor/haybale_graph_editor/farmhands/editor_tools.py`:
- Add a helper above `_port_row`:

```python
def _wire_fields(port) -> dict:
    """The port's wire key and role, as Farmhand reports them."""
    return {
        "wire_type": port.wire_key,
        "role": port.wire_type.role.value if port.wire_type is not None else None,
    }
```

- `_port_row`: `row = {"id": pid, "direction": _port_direction(port), **_wire_fields(port)}`.
- The `data == "info"` branch:
  - in the `PortInfo(...)` call, replace `flow_type=port.flow_type.value,` with `**_wire_fields(port),`;
  - replace `row["flow_type"] = info.flow_type` with `row["wire_type"] = info.wire_type` and `row["role"] = info.role`.
- The `data == "all"` branch: replace `row["flow_type"] = port.flow_type.value` with `row.update(_wire_fields(port))`.
- `_RESERVED_ROW_KEYS`: replace `"flow_type",` with `"wire_type",` and `"role",`.
- The `query_graph` instructions: replace `base id/direction/flow_type per port` with `base id/direction/wire_type/role per port`.

- [ ] **Step 5: The docs extractor**

In `packages/haywire-studio/src/haywire_studio/packaging/docs/extract.py`, replace the `"flow_type": …` line with:

```python
            "wire_type": identity.wire_type.id if getattr(identity, "wire_type", None) is not None else None,
```

- [ ] **Step 6: Run the tests, then the gate**

Run the Step 2 command. Expected: PASS.

Run: `grep -rn "flow_type" barn/haybale-graph-editor/haybale_graph_editor packages/haywire-core/src/haywire/core/node packages/haywire-studio/src --include='*.py'`
Expected: no hits.

Run the ruff check and mypy on the changed files, then the pre-commit gate. Expected: green.

- [ ] **Step 7: Commit**

```bash
git add packages/haywire-core/src/haywire/core/node/inspector.py barn/haybale-graph-editor/haybale_graph_editor/farmhands/editor_tools.py packages/haywire-studio/src/haywire_studio/packaging/docs/extract.py tests/core/test_node/test_inspector.py tests/studio/test_docs/test_render.py tests/studio/test_docs/test_extract_wire_type.py tests/farmhand/test_graph_editor_tools.py
git commit -m "refactor(farmhand): ports and type docs report wire_type and role

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: Pins and the canvas match by wire key

**Files:**
- Modify:
  - `packages/haywire-core/src/haywire/ui/skin/pin_render.py:213-231, 256-290, 299-353`
  - `packages/haywire-core/src/haywire/ui/skin/pin_icons.py`
  - `packages/haywire-core/src/haywire/ui/components/graph/canvas.vue:58-92, 1536, 1550, 1664-1669, 1770-1786, 2735, 3632-3657`
  - `packages/haywire-core/src/haywire/ui/components/graph/event_definitions.py:145, 356`
  - `packages/haywire-core/src/haywire/ui/components/graph/generated/graph_events.js` (regenerated)
  - `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/context_menu.py:868-883`
  - `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/visual_layer.py:1050-1086`
  - `barn/haybale-studio/haybale_studio/skins/node_skin.py:53` (docstring)
- Test: rewrite `tests/ui/skin/test_pin_any_flow.py` as `tests/ui/skin/test_pin_wire_attribute.py`; modify `tests/ui/skin/test_pin_icon_resolver.py:126-130`, `tests/ui/harness/test_node_sizing.py:301`, `tests/ui/harness/test_edge_drag_cost.py:56`, `tests/ui/harness/test_boundary_skin.py:35, 57, 65`; create `tests/ui/skin/test_pin_kind.py`

**Interfaces:**
- Consumes: Task 2's `DataPort.wire_key`, `wire_type` and `has_pin()`; Task 1's `wires_match`.
- Produces:
  - DOM: `data-pin-wire="<wire key or ''>"` on every real pin; `data-pin-ghost` (an attribute with no value) on ghost pins.
  - The event field `ContextMenuCanvasEvent.pendingWire`, in the slot `pendingFlowType` held.
  - The pending-connection dict key `"wire"`.
  - `PinIconResolver` reads `wire_type.pin_kind`.

- [ ] **Step 1: Write the failing tests**

Delete `tests/ui/skin/test_pin_any_flow.py`. Create `tests/ui/skin/test_pin_wire_attribute.py`:

```python
"""Every pin tells the canvas its wire key, and a ghost pin says it is one."""

import pytest

from haywire.barn.builtin.types import ADD, FLOAT
from haywire.barn.builtin.wires import DataWire
from haywire.core.types import DataPort, PortType
from haywire.core.types.enums import LayoutDirection
from haywire.ui.skin.pin_render import render_ghost_pin, render_pin

pytestmark = pytest.mark.unit


def _port(type_cls) -> DataPort:
    return DataPort(
        registry_id="p",
        registry_key=type_cls.class_identity.registry_key,
        label="P",
        id="p",
        type_cls=type_cls,
        port_type=PortType.INLET,
    )


def _render(port):
    return render_pin(port, "node-1", pin_gutter=20, card_padding=16, pin_protrusion=0)


def test_a_typed_pin_carries_its_wire_types_id(nicegui_slot_context):
    props = _render(_port(FLOAT))._props
    assert props.get("data-pin-wire") == DataWire.id
    assert "data-pin-flow-type" not in props
    assert "data-pin-any-flow" not in props


def test_a_bare_add_pin_carries_the_wildcard(nicegui_slot_context):
    assert _render(_port(ADD))._props.get("data-pin-wire") == "*"


def test_a_ghost_pin_is_marked_and_carries_no_wire(nicegui_slot_context):
    ghost = render_ghost_pin("node-1", layout=LayoutDirection.L2R, is_inlet=True, offset=8)
    assert "data-pin-ghost" in ghost._props
    assert "data-pin-wire" not in ghost._props
```

Before using `LayoutDirection.L2R`, check the member name in `packages/haywire-core/src/haywire/core/types/enums.py`. Use the left-to-right member as it is spelled there.

Create `tests/ui/skin/test_pin_kind.py`:

```python
"""A pin's icon kind comes from its wire type's pin_kind."""

import pytest

from haywire.core.types import PortType

from tests.conftest import make_node

pytestmark = pytest.mark.integration


def test_callback_and_control_pins_take_their_wire_types_kind(graph_with_library_system):
    from haybale_testing.nodes.testbed.emit_callback_node import TestEmitCallbackNode

    from haywire.ui.skin.pin_icons import DEFAULT_PIN_ICONS

    node = make_node(graph_with_library_system, TestEmitCallbackNode.class_identity.registry_key).node

    assert DEFAULT_PIN_ICONS.role_of(node.ports["edge_callback"]) == "callback_in_multi"
    assert DEFAULT_PIN_ICONS.role_of(node.ports["exec"]) == "control_out"


def test_a_config_port_resolves_to_no_icon(graph_with_library_system):
    from haybale_testing.nodes.testbed.fold_probe import FoldProbeNode

    from haywire.ui.skin.pin_icons import DEFAULT_PIN_ICONS

    node = make_node(graph_with_library_system, FoldProbeNode.class_identity.registry_key).node
    config = node.ports["substeps"]

    assert config.port_type is PortType.CONFIG
    assert DEFAULT_PIN_ICONS.resolve(config) is None
```

In `tests/ui/skin/test_pin_icon_resolver.py`, replace `test_a_pinless_flow_type_resolves_to_no_icon` with:

```python
    def test_a_port_without_a_pin_resolves_to_no_icon(self):
        """``render_pin`` draws nothing for it, which an icon would contradict."""
        port = _port(_typed(**_BARE), PortType.INLET)
        port.is_fold = True
        assert DEFAULT_PIN_ICONS.resolve(port) is None
```

and rename `test_a_role_falls_back_to_its_flow_type` / `test_a_narrower_role_wins_over_its_flow_type` to `…_its_kind` (the assertions stay).

The harness tests:
- `tests/ui/harness/test_node_sizing.py:301` and `tests/ui/harness/test_edge_drag_cost.py:56`: replace `.filter(p => p.dataset.pinFlowType !== 'ghost')` with `.filter(p => !('pinGhost' in p.dataset))`.
- `tests/ui/harness/test_boundary_skin.py:35`: replace `flow: p.dataset.pinFlowType,` with `ghost: 'pinGhost' in p.dataset,`. At lines 57 and 65, replace `r["flow"] == "ghost"` / `row["flow"] == "ghost"` with `r["ghost"]` / `row["ghost"]`.

- [ ] **Step 2: Run them**

Run: `uv run pytest tests/ui/skin -q`
Expected: the new and changed tests FAIL, because there is no `data-pin-wire` attribute yet and the resolver keys on flow.

- [ ] **Step 3: `pin_render.py`**

In `render_pin`'s `common_props`, replace the line `f'data-pin-flow-type="{pin.flow_type.value}" '` with:

```python
        f'data-pin-wire="{pin.wire_key or ""}" '
```

and delete the two any-flow lines (the comment `# A bare ADD grows a port of any flow…` and the `+ (' data-pin-any-flow="true"' …)` line).

Replace the comment above the `icon is None` test with `# A port without a pin (config, fold) draws nothing.`, and update the other comments at 259-269 and 284 that speak of "flow type":
- "Resolve the pin's icon from its type and wire type"
- "Connection validity keys off the wire key".

In `render_ghost_pin`'s `.props(...)`, replace `data-pin-flow-type="ghost" ` with `data-pin-ghost `.

- [ ] **Step 4: `pin_icons.py`**

- Replace the import line with `from haywire.core.types import CompoundType, DataPort`.
- In the class docstring:
  - replace "any role the map omits degrades to its flow type, then to ``"fallback"``. A pin therefore always gets an icon — only a flow type that draws no pin at all resolves to ``None``." with "any role the map omits degrades to its kind, then to ``"fallback"``. A pin therefore always gets an icon; only a port without a pin resolves to ``None``.";
  - replace "where *kind* is ``data``, ``compound``, ``control`` or ``callback``" with "where *kind* is the wire type's ``pin_kind`` (``data``, ``control``, ``callback`` for the builtin wire types), or ``compound`` for a container on a data wire";
  - replace "keeps that glyph even across flow types" with "keeps that glyph even across wire types".
- In the `ICONS` comment, replace "falls back to its flow type" with "falls back to its kind".
- Replace `resolve`, `role_of`, `_kind_of` and `_from_map` with:

```python
    def resolve(self, pin: DataPort) -> str | None:
        """Return the glyph *pin* draws, or ``None`` for a port without a pin.

        The port answers first: ``icon_in``/``icon_out`` and their ``_multi``
        variants carry what the type declared, already resolved through
        ``DataTypeIdentity.__post_init__``, plus any per-port override.
        """
        if not pin.has_pin():
            return None
        return self._declared(pin) or self._from_map(self._kind_of(pin), pin)

    def role_of(self, pin: DataPort) -> str:
        """Return the :attr:`ICONS` key for *pin*, e.g. ``"data_in_multi"``."""
        return self._role(self._kind_of(pin) or "data", pin)

    def _kind_of(self, pin: DataPort) -> str | None:
        """The map's *kind* segment for *pin*, or ``None`` for a pin without a wire type."""
        wire = pin.wire_type
        if wire is None:
            return None
        if wire.pin_kind == "data" and pin.type_cls is not None and issubclass(pin.type_cls, CompoundType):
            return "compound"
        return wire.pin_kind
```

   and in `_from_map`, accept `kind: str | None` and build the key list as:

```python
        keys = []
        if kind is not None:
            if pin.allow_multiple_links:
                keys.append(f"{kind}_{direction}_multi")
            keys += [f"{kind}_{direction}", kind]
        keys.append("fallback")
```

In `barn/haybale-studio/haybale_studio/skins/node_skin.py:53`, change "a role falls back to its flow type" to "a role falls back to its kind".

- [ ] **Step 5: The canvas**

In `packages/haywire-core/src/haywire/ui/components/graph/canvas.vue`:

1. In the DOM contract header, after the `data-pin-dir-x/y` entry and before the line `All three written by…`, insert:

```
 *   data-pin-wire       A pin's wire key: its wire type's id, or '*' for a bare
 *                       ADD slot. Two pins may link when _wiresMatch says so,
 *                       the mirror of wires_match in core/types/wire.py.
 *   data-pin-ghost      Present on a node's root ghost pins. A ghost is the
 *                       fallback anchor for an edge whose port is missing: it
 *                       never starts, ends or joins a drag.
```

   and change "All three written by ui/skin/pin_render.py." to "All of these written by ui/skin/pin_render.py."

2. At 1536, write `if (pin && !('pinGhost' in pin.dataset)) {`. At 1550, write `if ('pinGhost' in pin.dataset) return;`.

3. Replace the comment at 1664-1667 with:

```js
            // A ghost pin is a fallback anchor, not a port: its id names no
            // entry in node.ports, so it is no menu target.
```

   and change the selector at 1669 to `'[data-pin-id]:not([data-pin-ghost]), [data-port-id]'`.

4. At 1770-1786:
   - rename the local `pendingFlowType` to `pendingWire`;
   - read `pendingWire = sp.pinWire || '';`;
   - pass `pendingWire` in the same argument position.

5. At 2735: `if ('pinGhost' in pin.dataset) return;`.

6. Replace `_isValidEdge` (3632-3657) with:

```js
        _isValidEdge(startPin, endPin) {
            if (!startPin || !endPin || startPin === endPin) return false;

            if (startPin.dataset.nodeId === endPin.dataset.nodeId) {
                return false;
            }

            if (!this._wiresMatch(startPin.dataset.pinWire, endPin.dataset.pinWire)) {
                return false;
            }

            const startDir = startPin.dataset.pinDir;
            const endDir = endPin.dataset.pinDir;
            return (startDir === 'outlet' && endDir === 'inlet') ||
                (startDir === 'inlet' && endDir === 'outlet');
        },

        /** Mirror of wires_match (core/types/wire.py): equal wire keys, or either the '*' wildcard. */
        _wiresMatch(a, b) {
            if (!a || !b) return false;
            return a === b || a === '*' || b === '*';
        },
```

- [ ] **Step 6: The pending connection and auto-wire**

**`event_definitions.py`:**
- In `ContextMenuCanvasEvent`, replace `pendingFlowType: str = ""  # 'data' | 'control' | 'callback' | ''` with:

```python
    pendingWire: str = ""  # the dragged pin's wire key ('*' for a bare ADD slot) or ''
```

- In the `NodeCreateRequestEvent` comment (line 145), replace `flow_type` with `wire`.

Regenerate the JS from the repo root:

Run: `uv run python ./scripts/generate_vue_events.py`

Expected: `generated/graph_events.js` changes. `pendingFlowType` becomes `pendingWire` in `createContextMenuCanvas`, its `data` and its `requiredFields`. The diff also adds the three events the committed file lacks today (`promoteToMacro`, `openNewNodeWizard`, `detachFromMacro`); keep them, since the file was behind its generator.

**`context_menu.py:876`:** replace `"flow_type": event.pendingFlowType,` with `"wire": event.pendingWire,`.

**`visual_layer.py`, `_try_auto_wire`:**
- Docstring: `pin_dir, wire, data_type`.
- Replace `pending_flow = pending.get("flow_type", "")` with `pending_wire = pending.get("wire", "")`.
- Replace the flow comment and check with:

```python
            # The wire types must match, as a drag onto the pin would require.
            if pending_wire and not wires_match(pending_wire, port.wire_key):
                continue
```

- Add `from haywire.core.types.wire import wires_match` to the module imports.

- [ ] **Step 7: Run the tests, then the browser tier and the gate**

Run: `uv run pytest tests/ui/skin tests/ui/graph_canvas -q -n 4`. Expected: PASS.

Run: `grep -rn "pinFlowType\|pin-flow-type\|pinAnyFlow\|pin-any-flow\|pendingFlowType\|pending_flow" packages barn tests .scratch --include='*.py' --include='*.vue' --include='*.js'`

Expected: no hits except `.scratch/pan-perf/eventcensus.py:164`. Change that one to `'pinGhost' in p.dataset` (`.scratch` is untracked; edit it, nothing to commit).

Run the ruff check and mypy on the changed Python files, the browser tier, and the pre-commit gate. Expected: green.

- [ ] **Step 8: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/skin/pin_render.py packages/haywire-core/src/haywire/ui/skin/pin_icons.py packages/haywire-core/src/haywire/ui/components/graph/canvas.vue packages/haywire-core/src/haywire/ui/components/graph/event_definitions.py packages/haywire-core/src/haywire/ui/components/graph/generated/graph_events.js barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/context_menu.py barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/visual_layer.py barn/haybale-studio/haybale_studio/skins/node_skin.py tests/ui/skin/test_pin_any_flow.py tests/ui/skin/test_pin_wire_attribute.py tests/ui/skin/test_pin_kind.py tests/ui/skin/test_pin_icon_resolver.py tests/ui/harness/test_node_sizing.py tests/ui/harness/test_edge_drag_cost.py tests/ui/harness/test_boundary_skin.py
git commit -m "refactor(canvas): pins match by wire key; ghost pins carry their own marker

Every pin carries data-pin-wire and the canvas links two pins when their
keys match, the mirror of wires_match. A ghost pin is marked data-pin-ghost:
it is the fallback anchor for an edge whose port is missing and never takes
part in a drag, so _isValidEdge's ghost branch goes. Pin icons key on the
wire type's pin_kind, and has_pin() alone decides that a port draws none.
Auto-wire matches wire keys. graph_events.js is regenerated, which also
restores three events it had fallen behind on.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: Ports derive everything from their wire type

**What changes:**
- **`DataPort`.** Immediacy and link limits are decided by the role. A legacy saved `flow_type` is ignored.
- **Config ports and containers.** Config ports stop setting a flow. Containers stop rewriting one.
- **Mirrors.** They stop passing a flow.
- **Deleted:** `is_*_pin` (deletion 6).

After this task, nothing reads `flow_type`. Task 10 deletes it.

**Files:**
- Modify:
  - `packages/haywire-core/src/haywire/core/types/port.py:59-61, 270-295, 560-568, 818-837, 868-914`
  - `packages/haywire-core/src/haywire/core/types/interface.py:311-370`
  - `barn/haybale-core/haybale_core/types/array_type.py:45-95`, `barn/haybale-core/haybale_core/types/pooled_type.py:47-118, 160-166`
  - `packages/haywire-core/src/haywire/barn/builtin/nodes/graph_node.py:267-276`, `packages/haywire-core/src/haywire/barn/builtin/nodes/subgraph_io.py:50, 131-138`
  - `packages/haywire-core/src/haywire/core/undo/actions/graph_actions.py:1114-1129`
  - `packages/haywire-core/src/haywire/core/graph/subgraph_collapse.py:18, 42, 110, 231`
- Test: create `tests/core/test_types/test_port_derives_from_wire.py`; modify `tests/core/test_types/test_immediate_flow.py`, `tests/core/test_types/test_array_type_port_config.py`

**Interfaces:**
- Consumes: Task 2's port members.
- Produces:
  - `DataPort._derive_wire()` also sets `_is_immediate`.
  - `_cache_immediacy` is gone.
  - `DataPort.from_spec` pops a saved `flow_type` and never passes one.
  - `BoundaryPort` has no `flow_type` field.

- [ ] **Step 1: Write the failing tests**

Create `tests/core/test_types/test_port_derives_from_wire.py`:

```python
"""A port's immediacy and link limits come from its wire type, never from a saved flow."""

import pytest

from tests.conftest import make_node

pytestmark = pytest.mark.integration


def test_a_saved_flow_is_ignored_on_load(graph_with_library_system):
    from haybale_testing.nodes.testbed.math_op_node import TestAddFloatNode

    from haywire.barn.builtin.wires import DataWire

    graph = graph_with_library_system
    node = make_node(graph, TestAddFloatNode.class_identity.registry_key)
    data = graph.to_dict()
    ports = data["nodes"][node.node_id]["node_data"]["ports"]
    for spec in ports.values():
        spec["kwargs"]["flow_type"] = "callback"

    graph.clear()
    graph.load_from_dict(data)
    port = graph.node_wrappers[node.node_id].node.ports["value_a"]

    assert port.wire_type.id == DataWire.id
    assert not port.is_immediate


def test_a_config_port_of_a_callback_type_is_not_immediate(graph_with_library_system):
    from haybale_testing.nodes.testbed.emit_callback_node import TestEmitCallbackNode

    node = make_node(graph_with_library_system, TestEmitCallbackNode.class_identity.registry_key).node
    configs = [p for p in node.ports.values() if p.is_config()]

    assert configs
    assert not any(p.is_immediate for p in configs)


def test_link_limits_follow_the_role(graph_with_library_system):
    from haybale_testing.nodes.testbed.add_port_test import AddPortTestNode
    from haybale_testing.nodes.testbed.emit_callback_node import TestEmitCallbackNode
    from haybale_testing.nodes.testbed.math_op_node import TestAddFloatNode

    graph = graph_with_library_system
    add = make_node(graph, TestAddFloatNode.class_identity.registry_key).node
    emit = make_node(graph, TestEmitCallbackNode.class_identity.registry_key).node
    slots = make_node(graph, AddPortTestNode.class_identity.registry_key).node

    assert add.ports["result"].allow_multiple_links is True
    assert add.ports["value_a"].allow_multiple_links is False
    assert emit.ports["exec"].allow_multiple_links is False
    assert emit.ports["execute"].allow_multiple_links is True
    assert emit.ports["edge_callback"].allow_multiple_links is True
    # A bare ADD outlet slot keeps a data outlet's limit, as before.
    assert slots.ports["add_out_0"].allow_multiple_links is True
```

Before running it, check the key path: open a saved graph (`graphs/loop.haywire`) and confirm that a node's ports serialize under `["node_data"]["ports"]` with a `"kwargs"` dict per port. If the path differs, adjust the test to the real one. The point of the test is that a saved `flow_type` under a port's kwargs is ignored.

In `tests/core/test_types/test_immediate_flow.py`:
- Module docstring: "Which wire roles are immediate, and which ports cache it."
- Replace the `FlowType` import and `test_only_callback_is_immediate` with:

```python
@pytest.mark.unit
def test_only_the_callback_wire_type_is_immediate():
    from haywire.barn.builtin.wires import CallbackWire, ControlWire, DataWire
    from haywire.core.types import WireRole

    assert CallbackWire.role is WireRole.IMMEDIATE
    assert DataWire.role is not WireRole.IMMEDIATE
    assert ControlWire.role is not WireRole.IMMEDIATE
```

- In `test_a_pooled_callback_inlet_is_immediate`, change the docstring to: "A pooled port's wire type is its element's; the cache follows it."

In `tests/core/test_types/test_array_type_port_config.py`:
- Rewrite the module docstring as: "An ArrayType port takes its element's wire type and colour, and an array outlet on a data wire allows several links like any data outlet."
- Replace `assert outlet.flow_type == FlowType.DATA` (line 36) and `assert inlet.flow_type == FlowType.DATA` (line 47) with `assert outlet.wire_type.id == DataWire.id` / `assert inlet.wire_type.id == DataWire.id`, importing `from haywire.barn.builtin.wires import DataWire` in place of `FlowType`.
- Update the inlet test's comment: "Wrapped in PooledType, whose own _configure_port sets multi-link; the ArrayType layer beneath it still resolves to the data wire."
- Update `test_array_outlet_color_follows_element_type`'s docstring: "_configure_port takes the colour from the element that declares the wire type."

- [ ] **Step 2: Run them**

Run: `uv run pytest tests/core/test_types/test_port_derives_from_wire.py tests/core/test_types/test_immediate_flow.py tests/core/test_types/test_array_type_port_config.py -q`

Expected: `test_a_saved_flow_is_ignored_on_load` FAILs, because `from_spec` reads the saved flow and the port is immediate. The rest pass (they guard the change).

- [ ] **Step 3: `port.py`**

1. **`_is_immediate`.** Change the field's docstring to: "Cached: the wire type's role is ``IMMEDIATE``, so the set_value hot path branches on an attribute read. Refreshed by ``_derive_wire()``."

2. **`__post_init__`.**
   - Delete the comment `# CONTROL stays deferred…` and the call `self._cache_immediacy()`. `_derive_wire()` now does both.
   - Replace the whole "Hardcoded connection rules" block, through the trailing "callback flow" comment, with:

```python
        # Link limits by role. A pooled inlet is made multi-link after construction
        # (PooledType._configure_port); a callback port keeps whatever it declares.
        if self.is_dependent:
            self.allow_multiple_links = self.is_outlet()
        elif self.has_role(WireRole.SEQUENCE):
            # The VM keeps one transition per control outlet; a control inlet takes many.
            self.allow_multiple_links = self.is_inlet()
```

   This keeps today's rules: a DATA outlet allows many links and a DATA inlet one; a CONTROL outlet allows one and a CONTROL inlet many; a CALLBACK port is untouched; a bare `ADD` slot counts as DATA. A config port matches no branch, as before.

3. **`_derive_wire`:**

```python
    def _derive_wire(self) -> None:
        """Set ``wire_type`` from the port's type, and the immediacy cache from its role.

        A config port and a fold have no wire type.
        """
        self.wire_type = None if self.is_config() or self.is_fold else wire_type_of(self.type_cls)
        self._is_immediate = self.has_role(WireRole.IMMEDIATE)
```

4. **`refresh_from`.** Delete the comment `# set_value reads this cache rather than flow_type…` and the call `self._cache_immediacy()` that follows `self._derive_wire()`.

5. Delete `_cache_immediacy`, `is_callback_pin`, `is_control_pin` and `is_data_pin`. Change the `is_immediate` property's docstring to: "True when a write to this port takes effect on write: its wire type's role is ``IMMEDIATE``."

6. **`from_spec`.**
   - Replace `flow_type = FlowType(kwargs.pop("flow_type", FlowType.DATA.value))` with:

```python
        # A key saved before wire types; a port derives its wire type from its type.
        kwargs.pop("flow_type", None)
```

   - Delete `"flow_type": flow_type,` from `port_kwargs`.
   - Delete the comment `# _configure_port may rewrite flow_type…` and the call `port._cache_immediacy()` after `type_cls._configure_port(port)`.

- [ ] **Step 4: Config ports, containers, mirrors**

**`packages/haywire-core/src/haywire/core/types/interface.py`, `as_config`:**
- Delete `from haywire.core.types.enums import FlowType` and `kwargs["flow_type"] = FlowType.NONE`.
- Replace the docstring sentence "``flow_type`` is forced to ``NONE``, so a config can never be linked, and its value is saved with the graph." with "A config port has no pin and no wire type, so it is never linked; its value is saved with the graph."

**`barn/haybale-core/haybale_core/types/array_type.py`:**
- Change the class docstring's IMPORTANT note to: "It travels on the element type's wire type; a wire type declared on the array has no effect."
- Change the hook line to: "_configure_port: takes the element's colour, and refuses a control or callback element".
- Replace `_configure_port` with:

```python
    @classmethod
    def _configure_port(cls, port, **context) -> None:
        """Take the colour of the element that declares the wire type, and refuse a control
        or callback element. An array outlet on a data wire allows several links."""
        current_type = port.type_cls.element_type_cls
        while current_type is not None:
            identity = getattr(current_type, "class_identity", None)
            wire = getattr(identity, "wire_type", None)
            if wire is not None:
                port.color = identity.color
                if port.is_outlet():
                    port.allow_multiple_links = wire.role is WireRole.DEPENDENT
                if wire.role is WireRole.SEQUENCE:
                    raise ValueError("ArrayType cannot have a control element type")
                if wire.role is WireRole.IMMEDIATE:
                    raise ValueError("ArrayType cannot have a callback element type")
                return
            current_type = getattr(current_type, "element_type_cls", None)
```

- Import: replace `FlowType` in `from haywire.core.types import type, FlowType, DataField, CompoundType` with nothing, and add `from haywire.core.types.wire import WireRole`.

**`barn/haybale-core/haybale_core/types/pooled_type.py`:**
- Change the IMPORTANT note to: "It travels on the element type's wire type; a wire type declared in as_inlet() has no effect."
- In `_configure_port`, keep `port.allow_multiple_links = True` and replace the loop with:

```python
        current_type = port.type_cls.element_type_cls
        while current_type is not None:
            identity = getattr(current_type, "class_identity", None)
            wire = getattr(identity, "wire_type", None)
            if wire is not None:
                port.color = identity.color
                if wire.role is WireRole.SEQUENCE:
                    raise ValueError("PooledType cannot have a control element type")
                return
            current_type = getattr(current_type, "element_type_cls", None)
```

  and change the docstring's "Set flow type based on element type" to "Take the element's colour; refuse a control element".
- Replace line 164 with:

```python
        self._drops_default = wire_type_of(element) is not None and wire_type_of(element).role is WireRole.IMMEDIATE
```

  Ruff may ask for a local: `element_wire = wire_type_of(element)`, then test `element_wire is not None and element_wire.role is WireRole.IMMEDIATE`.
- Imports: drop `FlowType`; add `from haywire.core.types.wire import WireRole, wire_type_of`.

Both loops always advance to the next element. The old ones advanced only when the element had an identity, so a container whose element had none looped forever (a fact in the design's "Facts found" table).

**`packages/haywire-core/src/haywire/barn/builtin/nodes/graph_node.py`, `_mirror`:** delete `"flow_type": port.flow_type,`. The card's pin derives its wire type from `port.type_cls`. Interface ports exclude `ADD`, so this matches what the port carried.

**`packages/haywire-core/src/haywire/barn/builtin/nodes/subgraph_io.py`, `hb_grow`:** replace

```python
        if (
            self._SLOT_PORT_TYPE is PortType.INLET
            and FlowType(incoming.class_identity.flow_type).is_immediate
        ):
```

with

```python
        incoming_wire = wire_type_of(incoming)
        if (
            self._SLOT_PORT_TYPE is PortType.INLET
            and incoming_wire is not None
            and incoming_wire.role is WireRole.IMMEDIATE
        ):
```

Then replace `from haywire.core.types import FlowType, PortOrigin` with `from haywire.core.types import PortOrigin`, and extend the `wire` import to `from haywire.core.types.wire import WireRole, wire_type_of`.

**`packages/haywire-core/src/haywire/core/undo/actions/graph_actions.py:1114-1129`, `_build_boundary`:**
- Delete `"flow_type": port.flow_type,` from `kwargs`.
- Before `kwargs`, add:

```python
                port_wire = wire_type_of(port.itype)
                immediate = port_wire is not None and port_wire.role is WireRole.IMMEDIATE
```

- Use `if not immediate:` and `if not is_input and immediate:` in place of the two `port.flow_type.is_immediate` tests.
- Import `from ...types.wire import WireRole, wire_type_of` next to the function's other local imports.

**`packages/haywire-core/src/haywire/core/graph/subgraph_collapse.py`:**
- Delete the `flow_type: FlowType` field from `BoundaryPort` (line 110), `flow_type=naming.flow_type,` (line 231) and the `FlowType` import (line 18).
- Change line 42's "Both flow types count." to "Both wire types count."

Then: `grep -rn "\.flow_type\|flow_type=" --include='*.py' packages barn | grep -v "/docs/"`

Expected hits, all removed in Task 10:
- `port.py`'s `to_dict` enum transform;
- `identity.py`;
- `decorator.py`;
- `add.py:52`;
- `pin_render`'s docstring prose.

Any other hit is a reader this task missed: switch it to the role.

- [ ] **Step 5: Run the tests, then the gate**

Run: `uv run pytest tests/core/test_types tests/core/test_graph tests/core/test_undo tests/core/node tests/barn -q -n 4`
Expected: PASS.

Commit the haybale-core edits before the gate (no haybale-testing edits in this task). Run the ruff check and mypy on the changed files, then the pre-commit gate and the visiongraph tests. Expected: green.

- [ ] **Step 6: Commit**

```bash
git add packages/haywire-core/src/haywire/core/types/port.py packages/haywire-core/src/haywire/core/types/interface.py barn/haybale-core/haybale_core/types/array_type.py barn/haybale-core/haybale_core/types/pooled_type.py packages/haywire-core/src/haywire/barn/builtin/nodes/graph_node.py packages/haywire-core/src/haywire/barn/builtin/nodes/subgraph_io.py packages/haywire-core/src/haywire/core/undo/actions/graph_actions.py packages/haywire-core/src/haywire/core/graph/subgraph_collapse.py tests/core/test_types/test_port_derives_from_wire.py tests/core/test_types/test_immediate_flow.py tests/core/test_types/test_array_type_port_config.py
git commit -m "refactor(ports): immediacy and link limits come from the wire role

A port's immediacy and its link limits follow its wire type's role; a bare
ADD slot keeps a data port's limits. A saved flow_type is ignored on load.
Config ports, containers and the Graph-node and collapse mirrors no longer
set a flow. The container element walk always advances now, so an element
without an identity no longer loops. Removes is_*_pin.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 10: Delete `FlowType`

**Files:**
- Modify:
  - `packages/haywire-core/src/haywire/core/types/enums.py:8-30`
  - `packages/haywire-core/src/haywire/core/types/__init__.py`
  - `packages/haywire-core/src/haywire/core/types/identity.py`
  - `packages/haywire-core/src/haywire/core/types/decorator.py`
  - `packages/haywire-core/src/haywire/core/types/port.py:12, 951-953`
  - `packages/haywire-core/src/haywire/barn/builtin/types/add.py:8, 52, 111-113`
  - `packages/haywire-core/src/haywire/core/types/interface.py:195-196, 265-266, 285`
  - prose in `packages/haywire-core/src/haywire/core/node/promotion.py:170`, `core/node/behavior.py:29`, `core/graph/subgraph_crossing.py`, `barn/builtin/nodes/reroute.py:8-16, 45`, `barn/builtin/nodes/subgraph_io.py` prose, `barn/builtin/nodes/graph_node.py` prose, `core/undo/actions/graph_actions.py:758-790`
- Test: every test still constructing a `DataPort(..., flow_type=…)` or popping `"flow_type"` (Step 4)

**Interfaces:**
- Consumes: Tasks 4-9, which left no reader.
- Produces:
  - No `FlowType`, no `DataTypeIdentity.flow_type`, no `DataPort.flow_type`.
  - Bare `ADD` declares no wire type and no flow.
  - The `@type` widget rule keyed on role (5.2 drops it).

- [ ] **Step 1: Write the failing test**

Append to `tests/core/test_types/test_wire_derivation.py`:

```python
@pytest.mark.unit
def test_flow_type_is_gone():
    import haywire.core.types as types_pkg
    from haywire.core.types import DataTypeIdentity, enums

    assert not hasattr(types_pkg, "FlowType")
    assert not hasattr(enums, "FlowType")
    assert "flow_type" not in DataTypeIdentity.__dataclass_fields__


@pytest.mark.unit
def test_a_bare_add_declares_no_wire_type():
    from haywire.barn.builtin.types import ADD

    assert ADD.class_identity.wire_type is None
```

Run: `uv run pytest tests/core/test_types/test_wire_derivation.py -q`
Expected: the two new tests FAIL.

- [ ] **Step 2: Delete it in the type layer**

- **`enums.py`:** delete the `FlowType` class.
- **`types/__init__.py`:** drop `FlowType` from the enums import and from `__all__`.
- **`identity.py`:**
  - drop the `FlowType` import;
  - delete the `flow_type` field and its comment line `# Override flow_type to make it required for ports`;
  - delete the docstring entry `flow_type: DATA, CTRL, or NONE`.
- **`decorator.py`:**
  - delete the `FlowType` import, `_FLOW_FOR_ROLE` with its comment, and the three lines that fill `flow_type`;
  - delete the `flow_type` entry in the `Args:` docstring;
  - replace the widget rule (the comment block and the `flow = …` / `flow_value = …` / `if flow_value in (…)` lines through the `raise`) with:

```python
        # A control or callback type is a signal, not an editable value. This also
        # catches the inheritance trap: a signal type derived from a scalar inherits
        # the parent's widget_key through asdict(); pass widget_key=None to clear it.
        wire = identity_dict.get("wire_type")
        if (
            wire is not None
            and wire.role in (WireRole.SEQUENCE, WireRole.IMMEDIATE)
            and identity_dict.get("widget_key")
        ):
            raise TypeError(
                f"@type decorator for {inner_cls.__name__}: a type on {wire.id} cannot have a "
                f"widget_key (got {identity_dict['widget_key']!r}). Control and callback pins "
                f"are signals, not editable values. If this type inherits a widget_key from a "
                f"parent (e.g. a scalar base), pass widget_key=None to clear it."
            )
```

  The test's `match="cannot have a widget_key"` still matches.
- **`port.py`:** drop `FlowType` from the enums import, and delete `if isinstance(value, FlowType): value = value.value` in `to_dict`.
- **`add.py`:**
  - delete `flow_type=FlowType.DATA,` and the `FlowType` import;
  - replace the docstring paragraph "A bare `ADD` accepts an edge of any flow…" with: "A bare `ADD` accepts an edge of any wire type (data, control or callback), and the edge carries the other end's, so a pin grown from it can be any of them. A typed `ADD[T]` travels on `T`'s wire type."

- [ ] **Step 3: Prose**

Run: `grep -rn "FlowType\|flow_type\|flow type\|Flow type" --include='*.py' packages barn | grep -v "/docs/"`

For each remaining docstring or comment, say "wire type" or name the role, as the sentence needs. The known ones:
- `interface.py:195-196, 265-266` (`flow_type (FlowType)` entries in `as_inlet`/`as_outlet`): delete them; a port takes no wire type.
- `interface.py:285`: "(default: True for an outlet on a data wire)".
- `promotion.py:170`: "A promoted config port has no pin and no wire type".
- `behavior.py:29`: "any passthrough pair on one wire type".
- `reroute.py:8-16, 45`: "data, control and callback edges" / "on one wire type".
- `subgraph_io.py`, `graph_node.py`, `subgraph_crossing.py`, `graph_actions.py:758-790`: prose about "flow" becomes the wire type or role.
- `pin_render.py` and `pin_icons.py`: anything left from Task 8.

Expected after this step: the grep shows only `port.py`'s `kwargs.pop("flow_type", None)` with its comment.

- [ ] **Step 4: Tests that construct ports with a flow**

Run: `grep -rln "flow_type\|FlowType" tests ../haybale-visiongraph/tests`

For each hit, delete the `flow_type=FlowType.DATA` argument (the port derives `DataWire` from its type), any `"flow_type"` in a `spec.pop(...)` loop, and the `FlowType` import. The known sites:
- `tests/ui/widget/_sync_fixtures.py:30`
- `tests/ui/widget/test_number_widget_int_precision.py:28`
- `tests/ui/widget/test_select_widget_options.py:31`
- `tests/ui/widget/test_bind_nested.py:28`. Its `_Vec2` has no identity, so its port has no wire type, which the widget tests do not read.
- `tests/ui/skin/test_pin_icon_resolver.py:33, 40`
- `tests/ui/skin/test_pin_icon_resolution.py:41, 49`
- `tests/ui/skin/test_pin_native_tag_contract.py:46`
- `tests/ui/skin/test_pin_render_layout.py:40`
- `tests/core/test_types/test_data_inlet_arity.py:18`
- `tests/core/test_types/test_add_type.py:144`
- `tests/core/test_graph/test_store_strategy.py:54` (docstring)
- `test_unlink_reveals_own_value` (find it with the grep)

Expected after this step: the grep shows no hits, except `tests/core/test_types/test_port_derives_from_wire.py`. That file writes the legacy key on purpose.

- [ ] **Step 5: Run everything**

Run: `uv run pytest tests/core/test_types tests/ui/widget tests/ui/skin -q -n 4`. Expected: PASS.

Run the ruff check on the whole repo, the mypy set, the pre-commit gate, the browser tier and the visiongraph tests. Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add packages/haywire-core/src/haywire/core/types/ packages/haywire-core/src/haywire/barn/builtin/ packages/haywire-core/src/haywire/core/node/promotion.py packages/haywire-core/src/haywire/core/node/behavior.py packages/haywire-core/src/haywire/core/graph/subgraph_crossing.py packages/haywire-core/src/haywire/core/undo/actions/graph_actions.py packages/haywire-core/src/haywire/ui/skin/ tests/
git status --short
```

Check `git status --short`: nothing under `docs/superpowers/plans/`, `internals/` or `tests/core/test_zz_graph_snapshot.py` may be staged. If anything is, run `git restore --staged <path>` for it before committing.

```bash
git commit -m "refactor(types): delete FlowType

Every type declares a wire type, and ports and edges derive theirs, so the
flow enum, the identity field and the decorator's transitional mapping go.
Bare ADD declares no wire type: it is the wildcard. The widget rule for
signal types now keys on the wire role.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 11: Docs, glossary, ADRs and the generated library docs

The glossary and ADR edits land with the code: the design collected them as candidates, not as inline edits.

**Files:**
- Create: `docs/adr/0042-wire-types-replace-flowtype.md`
- Modify:
  - `docs/adr/0039-propagation-mode-replaces-is-lazy.md`
  - `docs/reference/glossary.md:53-58, 98-106, 143, 513, 586` (+ the section heading)
  - `docs/architecture/execution/callbacks/callbacks-arch.md:20`, `docs/architecture/execution/edges/edges-arch.md`, `docs/architecture/execution/assembly/assembly-arch.md`, `docs/architecture/hot-reload/hot-reload-arch.md:19, 91, 208`
  - `docs/components/datatypes/datatype-canon.md:19, 50, 132, 149`, `docs/components/skins/skin-canon.md:328-338`
  - `docs/guides/node-roles.md`, `docs/guides/ports.md`
  - `CLAUDE.md` (the "Canvas pin DOM attributes" trap line)
  - generated docs under `packages/haywire-core/src/haywire/barn/builtin/docs`, `barn/*/docs`, visiongraph `barn/haybale-visiongraph/docs`

**Interfaces:**
- Consumes: everything landed in Tasks 1-10.
- Produces: docs that describe the code as it now is.

- [ ] **Step 1: ADR 0042**

Create `docs/adr/0042-wire-types-replace-flowtype.md`:

```markdown
---
name: wire-types-replace-flowtype
description: A port's transport is a wire type its data type declares — a never-instantiated class with a closed role — derived for ports and edges, never stored; FlowType is gone
status: accepted
see-also: ADR-0009, ADR-0039, ADR-0041
level: architectural
---

# Wire types replace FlowType

**Context.** `FlowType` was a closed enum (DATA, CONTROL, CALLBACK, NONE) that every type, port and edge carried and saved. A library could not add a kind of edge, three places decided what may connect (the server's formal check, the canvas and auto-wire) and drifted apart, a config port reloaded as DATA because the saved flow beat the type, and `ADD[T]` was DATA whatever `T` was.

**Decision.** A **wire type** is a class that is never instantiated, following the Surface pattern (ADR 0009): its metadata is class attributes, `__init_subclass__` derives its id `"<library>:wire:<ClassName>"` and records it in an id map, and everything compares it by id. A data type names one with `@type(wire_type=…)`; a derived type inherits it, and a container or wrapper without one takes its element's. A wire type picks one of four **roles** — `DEPENDENT`, `SEQUENCE`, `IMMEDIATE`, `VISUAL` — and framework code branches on the role, never on which wire type it is; a new role is a framework change. A port's wire type is derived from its type and never passed or saved (config ports and folds have none); an edge's comes from its ports. Two pins connect when their **wire keys** match: equal ids, or a bare `ADD` slot's wildcard `*`. One function, `wires_match`, decides it on the server, and its mirror on the canvas.

An edge that fails validation is never rewritten: while it fails, its wire type comes from whichever end resolves, for drawing only, and its saved propagation and style are fitted to the wire type only once it validates again. A missing port must never cost the user work — the ghost pin anchors the edge until the port returns.

**Alternatives.** *Keep the enum and add members* — a new kind of edge would still be a framework change, and the drift between the three checks would stay. *A registry with a DI provider* — wire types have no lifecycle of their own beyond their module; the type registry's unmanaged-module reload already reaches them. *Store the wire type on edges and ports* — the stored value is what made a config port reload as DATA; derive it instead.

**Consequences.** A non-builtin wire type is an island: adapters do not bridge two wire types, so a library that wants its types convertible keeps them on `DataWire`. Saved `edge_type` and port `flow_type` keys are ignored; re-saving a graph drops them. A library defines its wire types in a module it imports by full path (`from mylib.wires import MyWire`): the reload cascade follows module imports, and `from mylib import MyWire` does not reach it.
```

- [ ] **Step 2: Amend ADR 0039**

In `docs/adr/0039-propagation-mode-replaces-is-lazy.md`:
- Frontmatter:
  - `status: superseded-in-part by ADR-0042`;
  - append `, ADR-0042` to `see-also`;
  - append to `description`: `(immediate is now a wire role, not a mode — ADR 0042)`.
- After the title, add:

```markdown
> **The immediate mode is superseded by [ADR 0042](0042-wire-types-replace-flowtype.md).** Immediate is the `IMMEDIATE` wire role, not a propagation mode: `Propagation` keeps lazy and eager, a wire type lists the modes its edges may take, and a callback edge, whose wire type allows none, has no propagation at all. Lazy, eager and the promoted outlet's lazy lock stand.
```

- [ ] **Step 3: Glossary**

In `docs/reference/glossary.md`:

1. **Section heading.**
   - Rename `## Flow Types & Port Kinds` to `## Wire Types & Port Kinds`.
   - In the **EXEC port** entry, change the link `#flow-types-port-kinds` to `#wire-types-port-kinds`.
   - In `docs/architecture/execution/callbacks/callbacks-arch.md:20`, change the link text and anchor the same way.
2. Replace the **FlowType** row with these rows:

```markdown
| **Wire type** | How a port's values travel and what the framework does with its edges. A data type declares one with `@type(wire_type=…)` and derived types inherit it; a container takes its element's. A class never instantiated, identified by the id `"<library>:wire:<ClassName>"`. Builtin ships `DataWire`, `ControlWire` and `CallbackWire`. Ports and edges derive theirs and never save it; a config port has none. See [ADR 0042](../adr/0042-wire-types-replace-flowtype.md) | FlowType (removed), flow type, edge kind |
| **WireRole** | What the framework does with an edge, picked by its wire type: **dependent** (assembly walks it backward — data), **sequence** (the VM walks it forward — control), **immediate** (takes effect on write — callbacks), **visual** (drawn and saved, never executed). Closed: framework code branches on the role | Flow |
| **Wire key** | What a pin is matched by: its wire type's id, or `*` for a bare `ADD` slot, which matches any. Two pins may link when their keys match (`wires_match`) | — |
| **Pin kind** | The key a wire type gives its pins for the skin's icon map, such as `control`. Not an icon: a type names its own icon | Glyph (means the drawn icon) |
```

3. **DATA port**, **EXEC port** and **CALLBACK port.** Where they speak of flow, name the wire type:
   - "a port on `DataWire`";
   - "a port on `ControlWire`";
   - for CALLBACK, "a port on `CallbackWire` (the immediate role); its edges have no propagation" in place of "and **immediate** propagation (see **Propagation**)".
   - Leave the empty-name sentence of CALLBACK port alone: 5.3 changes it.
4. **Propagation.** Replace the definition with:

```markdown
When a value written to an outlet takes effect at the inlet across an edge: **lazy** (the inlet pulls the current value when its node executes; the write only marks it dirty, which is what lets a DATA node skip its worker) or **eager** (pushed on write, takes effect when the inlet's node executes). An edge's wire type lists the modes it may take: one entry locks it, and a wire type that allows none gives the edge no propagation — a callback edge takes effect on write by its role. An edge out of a promoted outlet is locked lazy. See [ADR 0039](../adr/0039-propagation-mode-replaces-is-lazy.md) and [ADR 0042](../adr/0042-wire-types-replace-flowtype.md)
```

   with aliases `Eager push / Lazy pull (two of its values), immediate (a role, not a mode)`.
5. **Pin.** Replace "whatever its FlowType" with "whatever its wire type". In "spelled `PinMenu` / `data-pin-id` / `PinGlyph`", add `data-pin-wire`.
6. **Ghost pin.** Replace the definition with:

```markdown
A node's fallback anchor — the `root_in` / `root_out` pins rendered by node skins in `--hw-ghost-pin` (low-opacity, dashed) and marked `data-pin-ghost` — for an edge whose port is missing or that found no matching port (auto-wire). Its id names **no entry in `node.ports`**, so it never starts, ends or joins a user drag, takes no part in wire matching, and has no pin menu — see [skin-canon](../components/skins/skin-canon.md#ghost-pins-are-excluded-from-pin-detection). Removing a pin from the pin menu keeps its edges: they are drawn to the ghost and resolve to the pin again when a port with that id returns, so the user never redraws them. A port hidden by a collapsed group renders an ordinary **Pin** in the card header, not a ghost.
```

   Keep the aliases column as it is.
7. **Line 586.** Replace "they must share the same **FlowType**" with "their pins' **Wire keys** must match".
8. **Prose.** Search the glossary for prose that says "the wire" meaning an edge, and say "the edge" instead. **Edge** keeps *wire* on its avoid list.

- [ ] **Step 4: Architecture docs, canons, guides, CLAUDE.md**

Run: `grep -rn "FlowType\|flow_type\|flow type\|EdgeRegistry\|data-pin-flow-type\|drop affordance" docs CLAUDE.md .insights --include='*.md' | grep -v "docs/superpowers\|docs/adr/00[0-3]\|docs/archive"`

Rewrite each hit so it describes the current code:
- **`hot-reload-arch.md:19, 91, 208`.** There is no `EdgeRegistry`. Edges rebuild through the node registry and their adapter chains. Add one paragraph: a wire-type module reloads as an unmanaged module and its importers reload after it. Name the authoring rule from ADR 0042: import a wire type by its module path.
- **`datatype-canon.md:19, 50, 132, 149`.** `wire_type=` replaces `flow_type=`. Line 50 currently says CONTROL/CALLBACK types get no widget; say it as "a type on a control or callback wire type gets no widget (5.2 lifts this)". Drop that parenthesis if 5.2 has landed by the time this runs.
- **`skin-canon.md:328-338`.**
  - The selector is `[data-pin-id]:not([data-pin-ghost]), [data-port-id]`.
  - Replace "A ghost pin is a drop affordance (the temporary target shown while dragging a connection to an empty area of a node)" with "A ghost pin is a node's fallback anchor for an edge whose port is missing; it never takes part in a drag".
  - A skin emitting ghost pins marks them `data-pin-ghost`.
- **`edges-arch.md`, `assembly-arch.md`, `callbacks-arch.md`, `guides/node-roles.md`, `guides/ports.md`.** Flow categories become wire types and roles. A callback edge has no propagation.
- **`CLAUDE.md`**, the trap line starting "Canvas pin DOM attributes: use `pin.flow_type.value`…". Replace it with:

```markdown
- Canvas pin DOM attributes carry the pin's **wire key**: `data-pin-wire="{pin.wire_key or ''}"` — the wire type's id, or `*` for a bare ADD slot — and ghost pins carry `data-pin-ghost`; see `pin_render.py`. Relatedly, [project_layout_direction_pin_contract.md](.insights/project_layout_direction_pin_contract.md) — a pin's CSS side and its `data-pin-dir-x/y` vector must both come from `LayoutDirection`; a mismatch is silent (right edge, wrong curves). Skin-authoring side is in `docs/components/skins/skin-canon.md`.
```

Check every `.insights/` hit the same way, and update it to the current code.

Expected after this step: the grep shows hits only in `docs/archive/`, in ADRs 0000-0039 (records of past decisions, left as written apart from 0039's amendment), and in `docs/superpowers/`.

- [ ] **Step 5: Regenerate the library docs**

Run: `uv run haywire docs --all`
Expected: the generated type docs under `packages/haywire-core/src/haywire/barn/builtin/docs` and `barn/*/docs` show `- **wire_type**: \`haywire-core:wire:DataWire\`` (and so on) in place of `flow_type`. `ArrayType` and `PooledType` lose the line. `query_graph.md` shows the new instructions.

Visiongraph is not covered by `--all`, because its symlink resolves outside the repo root.

Run: `uv run haywire docs barn/haybale-visiongraph`
Expected: its 9 type docs change the same way.

Run: `grep -rln "flow_type" packages/haywire-core/src/haywire/barn/builtin/docs barn/*/docs barn/haybale-visiongraph/docs`
Expected: no hits.

- [ ] **Step 6: Docs build**

Run: `uv run mkdocs build --strict > /tmp/mk.log 2>&1; echo "exit=$?"; grep -n "WARNING" /tmp/mk.log | head -20`

Expected: the only warnings are the one that exists today (`docs/guides/panels.md` links into `.insights/`, a known small item). Fix any warning that names a file this task touched.

- [ ] **Step 7: Commit both repos**

```bash
cd /Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo
git add docs/adr/0042-wire-types-replace-flowtype.md docs/adr/0039-propagation-mode-replaces-is-lazy.md docs/reference/glossary.md docs/architecture docs/components docs/guides CLAUDE.md .insights packages/haywire-core/src/haywire/barn/builtin/docs barn/haybale-core/haybale_core/docs barn/haybale-example/haybale_example/docs barn/haybale-testing/haybale_testing/docs barn/haybale-TEST_A barn/haybale-graph-editor/haybale_graph_editor/docs
git status --short
```

Unstage anything under `docs/superpowers/` or `internals/`. Some `git add` paths may not exist, because the generated docs folders differ per library; use `git status` after `uv run haywire docs --all` to see the real changed paths and add exactly those.

```bash
git commit -m "docs: wire types replace FlowType

ADR 0042 records the model; ADR 0039 is amended (immediate is a role, a
callback edge has no propagation). Glossary: Wire type, WireRole, Wire key,
Pin kind; the Ghost pin is a fallback anchor, never a drag target, and
removing a pin keeps its edges. Architecture docs, canons, guides and the
generated library docs follow.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"

cd /Volumes/Ddrive/06_open_tracking_tool/haywire/haybale-visiongraph
git add barn/haybale-visiongraph/docs
git commit -m "docs: regenerate type docs for wire types

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 12: Verify the whole sweep

**Files:**
- Delete (never committed): `tests/core/test_zz_graph_snapshot.py`
- Modify (uncommitted, for the user): `docs/superpowers/plans/2026-10-02-wire-types.md` (status)

**Interfaces:**
- Consumes: Task 0's `/tmp/graph_snapshot_before.json`.

- [ ] **Step 1: Saved graphs behave as before**

Run: `HW_GRAPH_SNAPSHOT=/tmp/graph_snapshot_after.json uv run pytest tests/core/test_zz_graph_snapshot.py -q -p no:randomly`

Then compare:

```bash
uv run python - <<'EOF'
import json
before = json.load(open("/tmp/graph_snapshot_before.json"))
after = json.load(open("/tmp/graph_snapshot_after.json"))
assert before.keys() == after.keys(), (before.keys() ^ after.keys())
bad = []
for name in before:
    for kind in ("nodes", "edges"):
        if before[name][kind] != after[name][kind]:
            diff = {k: (before[name][kind].get(k), after[name][kind].get(k))
                    for k in before[name][kind].keys() | after[name][kind].keys()
                    if before[name][kind].get(k) != after[name][kind].get(k)}
            bad.append((name, kind, diff))
print("IDENTICAL" if not bad else bad)
EOF
```

Expected: `IDENTICAL`. Any difference is a sweep bug: stop and report it, with the graph and the node or edge id.

Then delete the scratch test: `rm tests/core/test_zz_graph_snapshot.py`.

- [ ] **Step 2: Full checks**

Run, from haywire-repo:
- the ruff check on the whole repo;
- the mypy set;
- the pre-commit gate;
- the browser tier;
- the visiongraph tests;
- `uv run pytest -m perf -q` if the perf tier exists and ran green in Task 0's baseline. Skip it otherwise and say so.

Expected: all green. Report the counts.

Then run:

```bash
grep -rn "FlowType\|flow_type\|edge_type\|is_flow_type\|_accepts_any_flow\|edge_flow_type\|pin-flow-type\|pinFlowType\|any-flow\|pendingFlowType\|Propagation.IMMEDIATE" --include='*.py' --include='*.vue' --include='*.js' packages barn tests
```

Expected: only `port.py`'s legacy `kwargs.pop("flow_type", None)` and `tests/core/test_types/test_port_derives_from_wire.py`.

- [ ] **Step 3: The running studio**

Unit tests do not see canvas behaviour (`.insights/project_multi_canvas_dom_globals.md`). Start the studio with the `haywire-live-studio` skill (or `uv run haywire`). Open `graphs/loop.haywire` and `graphs/any_and_nonde.haywire`, which hold callback edges, and check:

1. A callback edge's right-click menu has no "Propagation" row, and its inspector shows no propagation panel. A data edge shows both, and toggling lazy/eager works.
2. Dragging from a data outlet suggests data inlets only. Dragging from a control outlet suggests control inlets only. Dragging onto a Subgraph boundary node's bare `ADD` slot is accepted from any wire type, and the slot grows.
3. The pins draw today's icons: data, control and callback glyphs, the `ADD` glyph on slots, and compound glyphs on array ports.
4. Remove a grown pin from a boundary node's pin menu: its edge stays, drawn to the node's ghost pin.
5. Right-click on a ghost pin opens the node's menu, not a pin menu.
6. Save the graph, reload it: every edge is where it was, and the saved file holds no `"edge_type"` and no port `"flow_type"`.

visiongraph's tests do not cover the OAK-D or webcam callback path. If a camera is attached, open `graphs/webcam.haywire` and check that frames still reach the display node.

Report each check as passed or failed. A failure is a sweep bug: stop and report.

- [ ] **Step 4: Status**

In `docs/superpowers/plans/2026-10-02-wire-types.md`, set the 5.1 row to:

```markdown
| 5.1 | Wire types and the FlowType sweep, behaviour-preserving | **Landed** on branch `wire-types-5-1` (both repos), not merged | [2026-10-03-wire-types-5-1-sweep.md](2026-10-03-wire-types-5-1-sweep.md) | merge |
```

Add one line under the table: "5.1 also made an unknown `pin_kind` draw the fallback glyph (`_from_map` always ends in `fallback`), so 5.4 has no fallback-glyph work left."

Leave both plan files uncommitted for the user, as the Global Constraints say. Report the branch state of both repos, and the commits made.

---

## Self-review (done while writing)

- **Spec coverage.** The design's 5.1 scope maps to tasks as follows:
  - `WireRole` and `WireType` with the id map: Task 1.
  - The three standard wire types, `@type(wire_type=…)` and the derivation on ports: Task 2.
  - `Propagation` with allowed sets and locks, Q19: Task 5.
  - `wires_match` on the server (Task 4) and in `canvas.vue` with `data-pin-wire` (Task 8).
  - `data-pin-ghost`: Task 8.
  - `get_ports(is_role=…)` and `has_sequence_pins()`: Task 6.
  - Serialization (Q12): Tasks 4 and 9.
  - Farmhand fields: Tasks 4, 5 and 7.
  - Deletions:
    - 1: Task 10
    - 2: Task 5
    - 3, 4, 5, 7, 8, 12: Task 4
    - 6: Task 9
    - 10, 11: Task 8
    - 9 is 5.3's.
  - Q20: Tasks 4 and 5. Q29/Q30 `pin_kind`: Tasks 2 and 8. Q31: Tasks 8 and 11.
  - Verify-first hot reload: Task 3.
  - Docs, glossary and ADR candidates for 5.1: Task 11.
- **Behaviour guards.** Task 0 and Task 12 snapshot every saved graph's validity. Bare `ADD` keeps its DATA behaviour through `DataPort.is_dependent` (data walk, DATA-node outlet rule, link limits). Each is guarded by a named test.
- **Types.**
  - `wire_type` is a class everywhere; `wire_key` is a `str | None` everywhere.
  - Comparisons use `.id` or the role.
  - `PortInfo` gains `wire_type` and `role` in the slot where `flow_type` was, which the positional test constructions follow.
