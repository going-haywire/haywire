# Callbacks Through Reroutes (Edge Kinds, Step 1) Implementation Plan

**Status — 2026-09-28.** Built on branch `edge-kinds`, not yet merged. Gate 5904 passed, browser 135, visiongraph 29. Deviations: Task 6's test path `tests/core/test_validation/` does not exist, so `tests/core/node/test_boundary_nodes.py` ran instead; after Task 6 the Insert Reroute panel doc was regenerated. The reset-to-`None` rule of Task 7 is to be replaced by edge-kinds step 2 (unlinking reveals the port's own value). Sequence: [../2026-09-28-edge-kinds.md](../2026-09-28-edge-kinds.md).

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A callback subscription reaches the emit node through any chain of reroutes, removing any edge on the chain unsubscribes, and an edge's delivery timing becomes one `Propagation` mode (lazy / eager / immediate) instead of the `is_lazy` flag.

**Architecture:** Immediacy is derived from the flow type (`FlowType.is_immediate`, only `CALLBACK`) and cached on each port. A reroute's inlet forwards immediate writes to its outlet from its `on_change` handler; fields of immediate types can hold absence (`None`); an immediate inlet left without an edge goes absent, and the emitter's pool drops the entry keyed by its own edge. `Edge.propagation` stores the user's lazy/eager choice; `EdgeWrapper.propagation` applies two locks — immediate from the flow type, lazy from a promoted outlet.

**Tech Stack:** Python 3.12, NiceGUI (graph-editor panels), pytest (+ xdist), uv, ruff, mypy, mkdocs.

**Settled in:** the inquisition of 2026-09-27 (decisions 1A–13A). Memory: `project_edge_kinds_disconnect_semantics`.

## Global Constraints

- Work on branch `edge-kinds`. Every commit message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Breaking changes are allowed and saved graphs need no migration: an older graph's `is_lazy` key is ignored and its edges load eager.
- Out of scope: Subgraph boundaries and macros (edge-kinds step 4, own inquisition), a port's own value surviving unlink (step 6, ADR 0014 freeze-on-disconnect), EdgeKind and removing `FlowType`, DATA/CONTROL behaviour, callback routing by event name, `FlowAssemblyManager._process_callback_edges` (statistics), pin glyphs (`PinIconResolver._kind_of`), visiongraph code. Do not "fix" any of these on the way.
- Glossary, ADR and architecture-doc edits happen only in Task 8, with the code — never earlier.
- Docstrings and comments follow `.claude/rules/python-docs.md`. Class docstrings of registered components (nodes, types, panels) are displayed: Markdown, single backticks, no reST.
- Node registry keys in tests come from the class: `Cls.class_identity.registry_key`, never a string literal.
- `tests/studio/test_docs/test_generate.py` runs `git checkout -- barn/haybale-testing` in its teardown: commit every change under `barn/haybale-testing/` before running the full suite.
- Tests: run the smallest tier while iterating; the pre-commit gate is `uv run pytest -m "not browser and not perf" -n 4` (never `-n 8`, never `--dist loadfile`).
- "Ruff check" means both `uv run ruff check <path>` and `uv run ruff format --check <path>`; line length is 109.
- Never re-type a port by assigning `flow_type` without refreshing its immediacy cache (`_cache_immediacy()`).

---

## File Structure

| File | Responsibility | Tasks |
|---|---|---|
| `packages/haywire-core/src/haywire/core/types/enums.py` | `FlowType.is_immediate`; new `Propagation` enum | 1, 4 |
| `packages/haywire-core/src/haywire/core/types/__init__.py` | export `Propagation` | 4 |
| `packages/haywire-core/src/haywire/core/types/port.py` | `_is_immediate` cache + `is_immediate`; `_reset_if_unlinked`; drop lazy forcing in `_refresh_pipes` | 1, 4, 7 |
| `packages/haywire-core/src/haywire/core/types/base.py` | `absence_capable_field` (primitive + base storage), `_wrapper_field` | 2 |
| `packages/haywire-core/src/haywire/core/types/interface.py` | `IType.create_field` picks the absence-capable field for immediate types | 2 |
| `packages/haywire-core/src/haywire/barn/builtin/types/specs.py` | comment reference rename | 2 |
| `barn/haybale-core/haybale_core/types/pooled_type.py` | `PooledField.accepts_absence`, `None` removes a source | 3 |
| `packages/haywire-core/src/haywire/core/edge/edge.py` | `Edge.propagation` replaces `is_lazy` | 4 |
| `packages/haywire-core/src/haywire/core/edge/edge_wrapper.py` | `propagation` / `locked_propagation`; unlink reset call | 4, 7 |
| `packages/haywire-core/src/haywire/core/types/pipe.py` | pipe mode from `propagation` | 4 |
| `packages/haywire-core/src/haywire/core/graph/base.py` | `create_edge_wrapper(propagation=)`, load `propagation` | 4 |
| `packages/haywire-core/src/haywire/core/graph/utils/node_remap.py` | `RemappedEdge.propagation` | 4 |
| `barn/haybale-graph-editor/haybale_graph_editor/surfaces/edge.py` | `EdgeActions` propagation verbs | 5 |
| `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/context_menu.py` | propagation verbs on the provider | 5 |
| `barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/edge/edge.py` | `EdgePropagationMenuPanel`; reroute split offered for callbacks | 5, 6 |
| `barn/haybale-graph-editor/haybale_graph_editor/panels/properties/introspect/edge.py` | `EdgePropagationPanel` | 5 |
| `barn/haybale-graph-editor/haybale_graph_editor/farmhands/editor_tools.py` | `query_graph` edge detail | 5 |
| `packages/haywire-core/src/haywire/barn/builtin/nodes/reroute.py` | `forward_immediate` handler, docstrings | 6 |
| `packages/haywire-core/src/haywire/core/undo/actions/graph_actions.py` | reroute inlet wired to the handler | 6 |
| `packages/haywire-core/src/haywire/core/validation/structural_validator.py` | drop the event-source rule | 6 |
| `barn/haybale-testing/haybale_testing/types/test_types.py` (+ `__init__.py`) | `TEST_RECORD_CALLBACK` dataclass callback type | 2 |
| `barn/haybale-testing/haybale_testing/nodes/testbed/record_callback_nodes.py` (+ `nodes/__init__.py`) | record-callback event and emit test nodes | 7 |
| docs (`glossary.md`, `edges-arch.md`, `callbacks-arch.md`, `settings-arch.md`, ADRs 0033/0036/new 0039) | land with the code | 8 |

---

### Task 0: Baseline and acceptance tests

**Files:**
- Commit: `tests/core/test_edge/test_disconnect_semantics.py` (already written, untracked)

- [ ] **Step 1: Baseline lint and types for the areas this plan touches**

```bash
uv run ruff check packages/haywire-core/src/haywire/core barn/haybale-core barn/haybale-graph-editor barn/haybale-testing
uv run ruff format --check packages/haywire-core/src/haywire/core barn/haybale-core barn/haybale-graph-editor barn/haybale-testing
uv run mypy packages/haywire-core/src/ barn/haybale-core/haybale_core/ barn/haybale-graph-editor/haybale_graph_editor/ barn/haybale-testing/haybale_testing/ tests/
```

Expected: all clean. If not, stop and raise it with the user (CLAUDE.md: the code base has no errors; start an error-fix session instead).

- [ ] **Step 2: Confirm the acceptance tests fail as recorded**

Run: `uv run pytest tests/core/test_edge/test_disconnect_semantics.py -q -p no:randomly`
Expected: `1 passed, 4 xfailed`.

- [ ] **Step 3: Commit**

```bash
git add tests/core/test_edge/test_disconnect_semantics.py
git commit -m "test(edges): acceptance tests for disconnect semantics and callbacks through reroutes

Strict xfail: the Blender own-value model (track A, conflicts with ADR 0014
§C3) and callback edges passing through a reroute (track B, slice 1).

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 1: Immediate flows and the port cache

Replaces `DataPort._is_callback` with `_is_immediate`, derived from `FlowType.is_immediate`. Fixes a stale cache: `PooledType._configure_port` sets a pooled port's `flow_type` after `__post_init__` cached it, so a `PooledType[CALLBACK]` inlet reports `_is_callback == False` today and defers `on_change` — contrary to `callbacks-arch.md` §2.1, which `OakDCameraNode`'s `hb_on_callbacks_changed` relies on.

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/types/enums.py` (class `FlowType`, lines 8-21)
- Modify: `packages/haywire-core/src/haywire/core/types/port.py` (field at 49-51, `__post_init__` 263-267, `set_value` 346-377, `refresh_from` 549-551, `is_callback_pin` area ~783, `from_spec` ~868)
- Test: `tests/core/test_types/test_immediate_flow.py` (create)

**Interfaces:**
- Produces: `FlowType.is_immediate -> bool` (property); `DataPort.is_immediate -> bool` (property); `DataPort._cache_immediacy() -> None`; attribute `DataPort._is_immediate: bool`.

- [ ] **Step 1: Write the failing tests**

Create `tests/core/test_types/test_immediate_flow.py`:

```python
"""Which flows are immediate, and which ports cache it."""

import pytest

from haywire.core.types import FlowType


@pytest.mark.unit
@pytest.mark.parametrize(
    ("flow", "immediate"),
    [
        (FlowType.CALLBACK, True),
        (FlowType.DATA, False),
        (FlowType.CONTROL, False),
        (FlowType.NONE, False),
    ],
)
def test_only_callback_is_immediate(flow, immediate):
    assert flow.is_immediate is immediate


@pytest.mark.integration
class TestPortsCacheImmediacy:
    def test_a_callback_outlet_is_immediate(self, graph_with_library_system, library_system):
        from haybale_testing.nodes.testbed.custom_callback_node import TestCustomCallbackNode

        event = graph_with_library_system.create_node_wrapper(
            TestCustomCallbackNode.class_identity.registry_key, position=(0, 0)
        )

        assert event.node.ports["listen_callback"].is_immediate

    def test_a_pooled_callback_inlet_is_immediate(self, graph_with_library_system, library_system):
        """PooledType sets the flow type after the port is built; the cache follows it."""
        from haybale_testing.nodes.testbed.emit_callback_node import TestEmitCallbackNode

        emit = graph_with_library_system.create_node_wrapper(
            TestEmitCallbackNode.class_identity.registry_key, position=(0, 0)
        )

        assert emit.node.ports["edge_callback"].is_immediate

    def test_a_data_inlet_is_not_immediate(self, graph_with_library_system, library_system):
        from haybale_testing.nodes.testbed.math_op_node import TestAddFloatNode

        add = graph_with_library_system.create_node_wrapper(
            TestAddFloatNode.class_identity.registry_key, position=(0, 0)
        )

        assert not add.node.ports["value_a"].is_immediate

    def test_an_edge_into_a_pooled_callback_inlet_fires_on_change_at_once(
        self, graph_with_library_system, library_system
    ):
        from haybale_testing.nodes.testbed.custom_callback_node import TestCustomCallbackNode
        from haybale_testing.nodes.testbed.emit_callback_node import TestEmitCallbackNode

        graph = graph_with_library_system
        event = graph.create_node_wrapper(TestCustomCallbackNode.class_identity.registry_key, position=(0, 0))
        emit = graph.create_node_wrapper(TestEmitCallbackNode.class_identity.registry_key, position=(300, 0))
        emit.node.callback_index = 5  # the inlet's on_change handler, printout(), resets it to 0

        graph.create_edge_wrapper(event.node_id, "listen_callback", emit.node_id, "edge_callback")

        assert emit.node.callback_index == 0
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/core/test_types/test_immediate_flow.py -q -p no:randomly`
Expected: FAIL — `AttributeError: 'FlowType' object has no attribute 'is_immediate'` and `'DataPort' object has no attribute 'is_immediate'`; the last test fails with `assert 5 == 0`.

- [ ] **Step 3: Add `FlowType.is_immediate`**

In `enums.py`, directly after `NONE = "none"` in `class FlowType`:

```python
    @property
    def is_immediate(self) -> bool:
        """True when a write through this flow takes effect on write, not when the sink executes.

        Only ``CALLBACK`` is immediate. An immediate inlet fires ``on_change`` for
        edge-driven writes too, a reroute forwards it at once, and it goes absent
        when its last edge is removed.
        """
        return self is FlowType.CALLBACK
```

- [ ] **Step 4: Replace the cache field in `port.py`**

Replace lines 49-51 (the `_is_callback` field and its two-line docstring; line 50 ends with a trailing space) with:

```python
    _is_immediate: bool = field(init=False, repr=False, metadata={"serialize": False})
    """Cached ``flow_type.is_immediate``, so the set_value hot path branches on an
    attribute read. Refreshed by ``_cache_immediacy()`` wherever ``flow_type`` is rewritten."""
```

- [ ] **Step 5: Refresh the cache in `__post_init__`, `refresh_from` and `from_spec`**

In `__post_init__`, replace:

```python
        # Cache the immutable flow type for the set_value hot path.
        # It is tempting to give CONTROL Flow types this feature, too, but
        # due to the way Reroute Nodes work, this would actually break.
        # (CALLBACK edges do not allow Reroutes)
        self._is_callback = self.flow_type == FlowType.CALLBACK
```

with:

```python
        # CONTROL stays deferred: a control reroute forwards in its worker, on the VM's schedule.
        self._cache_immediacy()
```

In `refresh_from`, replace `self._is_callback = self.flow_type == FlowType.CALLBACK` (the line after the two-line comment ending "derives it from its element type.") with `self._cache_immediacy()`.

In `from_spec`, replace:

```python
        # Let type configure port (for compound types, etc.)
        type_cls._configure_port(port)
```

with:

```python
        # Let type configure port (for compound types, etc.)
        type_cls._configure_port(port)
        # _configure_port may rewrite flow_type: a pooled port takes its element's.
        port._cache_immediacy()
```

- [ ] **Step 6: Use the cache in `set_value`**

In the `set_value` docstring, replace the line `            - CALLBACK flow_type when edge-driven` with `            - an immediate flow (``is_immediate``) when edge-driven`.

Replace:

```python
            if self.on_change is not None and (edge_id is None or self._is_callback):
                # Widget/programmatic/callback change → fire on_change immediately
```

with:

```python
            if self.on_change is not None and (edge_id is None or self._is_immediate):
                # Widget/programmatic/immediate change → fire on_change immediately
```

- [ ] **Step 7: Add the property and the refresher**

Directly before `def is_callback_pin(self) -> bool:`:

```python
    @property
    def is_immediate(self) -> bool:
        """True when a write to this port takes effect on write. See ``FlowType.is_immediate``."""
        return self._is_immediate

    def _cache_immediacy(self) -> None:
        """Refresh the ``_is_immediate`` cache from ``flow_type``."""
        self._is_immediate = FlowType(self.flow_type).is_immediate
```

- [ ] **Step 8: Check no `_is_callback` reference is left**

Run: `grep -rn "_is_callback" --include="*.py" packages/ barn/ tests/`
Expected: no output.

- [ ] **Step 9: Run the tests**

Run: `uv run pytest tests/core/test_types/test_immediate_flow.py tests/core/test_edge/ tests/core/test_undo/test_collapse_callback_refusal.py tests/core/test_execution/test_interpreter.py -q -p no:randomly`
Expected: PASS (the four xfails in `test_disconnect_semantics.py` stay xfailed).

- [ ] **Step 10: Lint, types, commit**

```bash
uv run ruff check packages/haywire-core/src/haywire/core/types tests/core/test_types/test_immediate_flow.py
uv run ruff format --check packages/haywire-core/src/haywire/core/types tests/core/test_types/test_immediate_flow.py
uv run mypy packages/haywire-core/src/haywire/core/types/
git add packages/haywire-core/src/haywire/core/types/enums.py packages/haywire-core/src/haywire/core/types/port.py tests/core/test_types/test_immediate_flow.py
git commit -m "feat(types): immediate flows; pooled callback inlets fire on_change at once

FlowType.is_immediate (only CALLBACK) replaces the port's _is_callback
cache. from_spec refreshes the cache after _configure_port, which rewrites
a pooled port's flow type: PooledType[CALLBACK] inlets deferred on_change
until now, contrary to callbacks-arch.md.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Fields of immediate types can hold absence

`IType.create_field` gives an immediate type the absence-capable form of its field class. The existing `_absence_tolerant_field` is `OPTIONAL`-specific: its `get_stored_type()` returns the wrapped element, which for `CALLBACK` would be Python's `str`, and saving `CALLBACK(value=None)` raises. So the generic absence storage is split from the wrapper's stored-type rule, and extended to `BaseField` (visiongraph's `MULTIFRAME_CALLBACK` is a dataclass). `OPTIONAL[T]` keeps its primitive-only rule (pinned by `tests/core/test_types/test_wrapper_type.py::test_an_element_stored_by_basefield_is_refused`).

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/types/base.py` (lines 394-455 and the `field_class` line in `WrapperType.__class_getitem__`, ~608)
- Modify: `packages/haywire-core/src/haywire/core/types/interface.py` (import at line 5, `create_field` at 106-133)
- Modify: `packages/haywire-core/src/haywire/barn/builtin/types/specs.py` (comment in `INTField` docstring, ~line 39)
- Modify: `barn/haybale-testing/haybale_testing/types/test_types.py`, `barn/haybale-testing/haybale_testing/types/__init__.py`
- Test: `tests/core/test_types/test_immediate_absence.py` (create)

**Interfaces:**
- Consumes: `FlowType.is_immediate` (Task 1).
- Produces: `haywire.core.types.base.absence_capable_field(base_field_cls: type) -> type`; `haybale_testing.types.TEST_RECORD_CALLBACK` (dataclass `BaseType`, fields `name: str = ""`, `weight: int = 0`, `flow_type=CALLBACK`).

- [ ] **Step 1: Add the dataclass callback test type**

Append to `barn/haybale-testing/haybale_testing/types/test_types.py` (add `from dataclasses import dataclass` and `BaseType` to the imports at the top: `from haywire.core.types import type, FlowType` becomes `from haywire.core.types import type, BaseType, FlowType`):

```python
# ============================================================================
# Callback Types
# ============================================================================


@type(
    flow_type=FlowType.CALLBACK,
    label="Test Record Callback",
    description="Test callback subscription carried as a dataclass",
    default={"name": "", "weight": 0},
    color="#ff3c00",
)
@dataclass
class TEST_RECORD_CALLBACK(BaseType):
    """Test-only callback type whose subscription is a dataclass: a name plus a weight."""

    name: str = ""
    weight: int = 0
```

In `types/__init__.py` add `from .test_types import TEST_RECORD_CALLBACK` and `"TEST_RECORD_CALLBACK",` to `__all__` (keep `__all__` sorted).

- [ ] **Step 2: Write the failing tests**

Create `tests/core/test_types/test_immediate_absence.py`:

```python
"""Fields of immediate types hold absence (``None``), whatever their storage."""

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture
def callback_field(library_system):
    from haybale_core.types import CALLBACK

    return CALLBACK.create_field()


@pytest.fixture
def record_field(library_system):
    from haybale_testing.types import TEST_RECORD_CALLBACK

    return TEST_RECORD_CALLBACK.create_field()


class TestPrimitiveCallbackField:
    def test_it_accepts_absence(self, callback_field):
        assert callback_field.accepts_absence()

    def test_it_stores_none(self, callback_field):
        callback_field.set_value("tick")

        callback_field.set_value(None)

        assert callback_field.get_value() is None
        assert not callback_field.has_data()

    def test_absence_saves_and_loads(self, callback_field):
        from haybale_core.types import CALLBACK

        callback_field.set_value(None)
        restored = CALLBACK.create_field()
        restored.set_value("tick")

        restored.from_dict(callback_field.to_dict())

        assert restored.get_value() is None

    def test_it_still_travels_as_callback(self, callback_field):
        from haybale_core.types import CALLBACK

        assert callback_field.get_stored_type() is CALLBACK


class TestDataclassCallbackField:
    def test_it_accepts_absence(self, record_field):
        assert record_field.accepts_absence()

    def test_it_stores_none(self, record_field):
        record_field.set_value(None)

        assert record_field.get_value() is None
        assert not record_field.has_data()

    def test_a_present_value_is_still_type_checked(self, record_field):
        with pytest.raises(TypeError):
            record_field.set_value("not a record")

    def test_absence_saves_and_loads(self, record_field):
        from haybale_testing.types import TEST_RECORD_CALLBACK

        record_field.set_value(None)
        restored = TEST_RECORD_CALLBACK.create_field()

        restored.from_dict(record_field.to_dict())

        assert restored.get_value() is None

    def test_a_present_value_still_saves_and_loads(self, record_field):
        from haybale_testing.types import TEST_RECORD_CALLBACK

        record_field.set_value(TEST_RECORD_CALLBACK(name="tick", weight=3))
        restored = TEST_RECORD_CALLBACK.create_field()

        restored.from_dict(record_field.to_dict())

        assert restored.get_value() == TEST_RECORD_CALLBACK(name="tick", weight=3)


class TestOtherTypesAreUnchanged:
    def test_a_float_field_does_not_accept_absence(self, library_system):
        from haywire.barn.builtin.types import FLOAT

        assert not FLOAT.create_field().accepts_absence()

    def test_an_optional_field_still_travels_as_its_element(self, library_system):
        from haywire.barn.builtin.types import INT, OPTIONAL

        assert OPTIONAL[INT].create_field().get_stored_type() is INT

    def test_an_optional_field_still_saves_absence_as_a_null_value(self, library_system):
        from haywire.barn.builtin.types import INT, OPTIONAL

        field = OPTIONAL[INT].create_field()
        field.set_value(None)

        assert field.to_dict() == {"value": None}
```

- [ ] **Step 3: Run to verify failure**

Run: `uv run pytest tests/core/test_types/test_immediate_absence.py -q -p no:randomly`
Expected: FAIL — `accepts_absence()` is False for both callback fields, `BaseField.set_value(None)` raises `TypeError: Expected TEST_RECORD_CALLBACK, got NoneType`; the three `TestOtherTypesAreUnchanged` tests PASS.

- [ ] **Step 4: Replace the absence factory in `base.py`**

Replace everything from the comment `#: Absence-tolerant field classes, keyed by the element's own field class.` (line 394) through `return _AbsenceTolerantField` (line 455) with:

```python
#: Absence-capable field classes, keyed by the field class they extend. Shared
#: so one base class yields one subclass, whichever type asks for it.
_ABSENCE_CAPABLE_FIELDS: "dict[type, type]" = {}

#: Wrapper field classes, keyed by the element's own field class. Shared so
#: ``OPTIONAL[INT]`` built twice yields one field class, matching
#: ``_parameterized_cache``'s identity guarantee for the types themselves.
_WRAPPER_FIELDS: "dict[type, type]" = {}

#: Key an absent ``BaseField`` value saves under. A dataclass may have a field
#: named ``value``, which makes the primitive form ``{"value": None}`` ambiguous.
_ABSENT_KEY = "__absent__"


def absence_capable_field(base_field_cls: type) -> type:
    """Return a subclass of *base_field_cls* that can also hold ``None`` as absence.

    A present value keeps the base class's own storage, coercion and type check
    included; ``None`` bypasses them and still fires the change event. Absence
    saves and loads back: as ``{"value": None}`` for primitive storage and as
    ``{"__absent__": True}`` for ``BaseField`` storage. ``accepts_absence()``
    answers ``True``, so ``Pipe.pull`` forwards absence into the field. Cached,
    so one base class yields one subclass.

    Raises:
        TypeError: If *base_field_cls* is neither a ``PrimitiveField`` nor a
            ``BaseField`` subclass.
    """
    from .fields import BaseField, PrimitiveField

    if not (isinstance(base_field_cls, type) and issubclass(base_field_cls, (PrimitiveField, BaseField))):
        name = getattr(base_field_cls, "__name__", base_field_cls)
        raise TypeError(f"absence needs PrimitiveField or BaseField storage; {name} is neither")

    cached = _ABSENCE_CAPABLE_FIELDS.get(base_field_cls)
    if cached is not None:
        return cached

    stores_instances = issubclass(base_field_cls, BaseField)

    class _AbsenceCapableField(base_field_cls):  # type: ignore[valid-type,misc]
        """``base_field_cls``, plus the ability to hold absence."""

        def set_value(self, value: Any, source_id: "str | None" = None) -> None:
            if value is not None:
                super().set_value(value, source_id)
            elif stores_instances:
                # Past BaseField.set_value, whose isinstance check rejects None.
                old = self._container
                self._container = None
                self.is_dirty = True
                if self.on_changed.has_observers():
                    self.fire(None, old)
            else:
                # Past the element's own set_value, whose coercion rejects None.
                PrimitiveField.set_value(self, None, source_id)

        def to_dict(self) -> dict:
            if self.get_value() is not None:
                return super().to_dict()
            return {_ABSENT_KEY: True} if stores_instances else {"value": None}

        def from_dict(self, data: dict) -> None:
            absent = data.get(_ABSENT_KEY) is True if stores_instances else data.get("value") is None
            if not absent:
                super().from_dict(data)
                return
            if stores_instances:
                self._container = None
            else:
                self._value = None
            self.is_dirty = True

        def accepts_absence(self) -> bool:
            """Always True: this field class exists to hold ``None``."""
            return True

    _AbsenceCapableField.__name__ = f"AbsenceCapable{base_field_cls.__name__}"
    _AbsenceCapableField.__qualname__ = _AbsenceCapableField.__name__
    _ABSENCE_CAPABLE_FIELDS[base_field_cls] = _AbsenceCapableField
    return _AbsenceCapableField


def _wrapper_field(element_field_cls: type) -> type:
    """Return the field class for a wrapper whose element is stored by *element_field_cls*.

    The absence-capable form of *element_field_cls*, reporting the element as
    its stored type — what travels on an edge — while ``type_cls`` stays the
    wrapper. Cached per element field class.

    Raises:
        TypeError: If *element_field_cls* isn't a ``PrimitiveField`` subclass.
    """
    from .fields import PrimitiveField

    if not (isinstance(element_field_cls, type) and issubclass(element_field_cls, PrimitiveField)):
        raise TypeError(
            f"a wrapper type cannot wrap an element stored by {element_field_cls.__name__}: "
            f"absence is only defined for PrimitiveField storage (a bare value or None). "
            f"Wrap a primitive-shaped IType instead."
        )

    cached = _WRAPPER_FIELDS.get(element_field_cls)
    if cached is not None:
        return cached

    class _WrapperField(absence_capable_field(element_field_cls)):  # type: ignore[valid-type,misc]
        """An absence-capable element field that reports the element as its stored type."""

        def get_stored_type(self) -> "type[IType]":
            """Return the element type, which is what travels on an edge.

            ``type_cls`` stays the wrapper, so a promoted ``OPTIONAL[INT]``
            renders as an ordinary ``INT`` pin and links to one with no
            adapter, while the widget and identity still see the wrapper.
            """
            element = self.type_cls.element_type_cls
            assert element is not None  # __class_getitem__ always sets it
            return element

    _WrapperField.__name__ = f"Wrapper{element_field_cls.__name__}"
    _WrapperField.__qualname__ = _WrapperField.__name__
    _WRAPPER_FIELDS[element_field_cls] = _WrapperField
    return _WrapperField
```

In `WrapperType.__class_getitem__`, replace `"field_class": _absence_tolerant_field(element_field_cls),` with `"field_class": _wrapper_field(element_field_cls),`.

- [ ] **Step 5: Pick the absence-capable field in `IType.create_field`**

In `interface.py` line 5, change the import to `from haywire.core.types.enums import FlowType, PortType, StoreStrategy, default_show_widget`.

In `create_field`, add this paragraph to the docstring after the first line: `An immediate type (see ``FlowType.is_immediate``) gets the absence-capable form of its field class, so its ports can go absent.` Then replace the last line `return cls.field_class(type_cls=cls, default_kwargs=default_kwargs)` with:

```python
        field_cls = cls.field_class
        identity = getattr(cls, "class_identity", None)
        if identity is not None and FlowType(identity.flow_type).is_immediate:
            from .base import absence_capable_field

            # An immediate port goes absent when its last edge is removed.
            field_cls = absence_capable_field(field_cls)
        return field_cls(type_cls=cls, default_kwargs=default_kwargs)
```

- [ ] **Step 6: Update the comment in `specs.py`**

In the `INTField` docstring, replace `override (see ``_absence_tolerant_field``).` with `override (see ``absence_capable_field``).`

- [ ] **Step 7: Check no old name is left**

Run: `grep -rn "_absence_tolerant_field\|_ABSENCE_TOLERANT_FIELDS\|AbsenceTolerant" --include="*.py" packages/ barn/ tests/`
Expected: no output.

- [ ] **Step 8: Run the tests**

Run: `uv run pytest tests/core/test_types/ tests/core/test_settings/test_optional_setting.py tests/core/node/test_optional_promotion_connections.py tests/ui/widget/test_optional_widget.py -q -p no:randomly`
Expected: PASS.

- [ ] **Step 9: Lint, types, commit** (commit before any full-suite run: `barn/haybale-testing` changed)

```bash
uv run ruff check packages/haywire-core/src/haywire/core/types packages/haywire-core/src/haywire/barn/builtin/types barn/haybale-testing tests/core/test_types
uv run ruff format --check packages/haywire-core/src/haywire/core/types packages/haywire-core/src/haywire/barn/builtin/types barn/haybale-testing tests/core/test_types
uv run mypy packages/haywire-core/src/haywire/core/types/ barn/haybale-testing/haybale_testing/ tests/core/test_types/
git add packages/haywire-core/src/haywire/core/types/base.py packages/haywire-core/src/haywire/core/types/interface.py packages/haywire-core/src/haywire/barn/builtin/types/specs.py barn/haybale-testing/haybale_testing/types/ tests/core/test_types/test_immediate_absence.py
git commit -m "feat(types): fields of immediate types hold absence

absence_capable_field extends PrimitiveField and BaseField storage with
None, saved and loaded back. IType.create_field uses it for immediate
types. OPTIONAL's field keeps its primitive-only rule and its element
stored type, now in _wrapper_field.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: A pooled field of an immediate element drops a source on absence

**Files:**
- Modify: `barn/haybale-core/haybale_core/types/pooled_type.py` (`PooledField.set_value` at 170-204; new `accepts_absence`)
- Test: `tests/core/test_types/test_immediate_absence.py` (append)

**Interfaces:**
- Consumes: `FlowType.is_immediate` (Task 1).
- Produces: `PooledField.accepts_absence() -> bool` (True iff the element type is immediate); `PooledField.set_value(None, source_id)` removes that source's entry for an immediate element.

- [ ] **Step 1: Write the failing tests**

Append to `tests/core/test_types/test_immediate_absence.py`:

```python
class TestPooledFields:
    def test_a_pooled_callback_field_accepts_absence(self, library_system):
        from haybale_core.types import CALLBACK, PooledType

        assert PooledType[CALLBACK].create_field().accepts_absence()

    def test_absence_from_a_source_removes_its_entry(self, library_system):
        from haybale_core.types import CALLBACK, PooledType

        pool = PooledType[CALLBACK].create_field()
        pool.set_value("a", source_id="e1")
        pool.set_value("b", source_id="e2")

        pool.set_value(None, source_id="e1")

        assert pool.get_value() == {"e2": "b"}

    def test_absence_without_a_source_changes_nothing(self, library_system):
        from haybale_core.types import CALLBACK, PooledType

        pool = PooledType[CALLBACK].create_field()
        pool.set_value("a", source_id="e1")

        pool.set_value(None)

        assert pool.get_value() == {"e1": "a"}

    def test_a_pooled_data_field_is_unchanged(self, library_system):
        from haybale_core.types import PooledType
        from haywire.barn.builtin.types import FLOAT

        pool = PooledType[FLOAT].create_field()

        pool.set_value(None, source_id="e1")

        assert not pool.accepts_absence()
        assert pool.get_value() == {"e1": None}
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/core/test_types/test_immediate_absence.py::TestPooledFields -q -p no:randomly`
Expected: FAIL on the first three (`accepts_absence()` False; `{"e1": None, "e2": "b"}` left; `ValueError: PooledField requires source_id`); the DATA test PASSES.

- [ ] **Step 3: Implement**

In `PooledField.set_value`, add to the docstring after the examples block: `For an immediate element (see ``accepts_absence``), ``None`` removes the source's entry.` Then insert before `if source_id is None:`:

```python
        if value is None and self.accepts_absence():
            # Absence from a source ends that source's entry; with no source there is nothing to end.
            if source_id is not None:
                self.remove_source(source_id)
            return
```

Add a method after `get_stored_type`:

```python
    def accepts_absence(self) -> bool:
        """True when the pooled element is an immediate type, for which absence from a source ends its entry."""
        identity = getattr(self.get_stored_type(), "class_identity", None)
        return identity is not None and FlowType(identity.flow_type).is_immediate
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/core/test_types/ tests/core/test_graph/test_edges.py -q -p no:randomly`
Expected: PASS.

- [ ] **Step 5: Lint, types, commit**

```bash
uv run ruff check barn/haybale-core tests/core/test_types && uv run ruff format --check barn/haybale-core tests/core/test_types
uv run mypy barn/haybale-core/haybale_core/ tests/core/test_types/
git add barn/haybale-core/haybale_core/types/pooled_type.py tests/core/test_types/test_immediate_absence.py
git commit -m "feat(pooled): absence from a source removes its entry for immediate elements

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: `Propagation` replaces `is_lazy` in core

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/types/enums.py` (new enum after `FlowType`), `packages/haywire-core/src/haywire/core/types/__init__.py` (line 13 and `__all__`)
- Modify: `packages/haywire-core/src/haywire/core/edge/edge.py`
- Modify: `packages/haywire-core/src/haywire/core/edge/edge_wrapper.py` (import line 10, `__init__` 117-188, `is_lazy` property 248-264)
- Modify: `packages/haywire-core/src/haywire/core/types/pipe.py` (imports, `add_pipe` 82-97)
- Modify: `packages/haywire-core/src/haywire/core/types/port.py` (`is_linked_lazy` docstring ~155, `_on_shared_field_changed` docstring ~427, `_refresh_pipes` ~744-767)
- Modify: `packages/haywire-core/src/haywire/core/graph/base.py` (import line 20, `create_edge_wrapper` ~581-618, `load_from_dict` edge block ~1012-1020)
- Modify: `packages/haywire-core/src/haywire/core/graph/utils/node_remap.py` (lines 39-40, 113)
- Rename + rewrite: `tests/core/test_edge/test_edge_lazy_toggle.py` → `tests/core/test_edge/test_edge_propagation.py`
- Modify tests: `tests/core/test_graph/test_edges.py`, `tests/core/test_assembly/test_subgraph_execution_edges.py`, `tests/core/node/test_promotion_e2e.py`, `tests/core/test_graph/test_clipboard_payload.py`, `tests/core/test_undo/test_paste_action.py`

**Interfaces:**
- Consumes: `FlowType.is_immediate` (Task 1).
- Produces: `haywire.core.types.Propagation` (`LAZY="lazy"`, `EAGER="eager"`, `IMMEDIATE="immediate"`, method `toggled() -> Propagation`); `Edge.propagation: Propagation` (saved as `"propagation"`); `EdgeWrapper(..., propagation: Propagation = Propagation.EAGER)`; `EdgeWrapper.propagation` (get/set), `EdgeWrapper.locked_propagation -> Propagation | None`; `BaseGraph.create_edge_wrapper(..., propagation: Propagation = Propagation.EAGER)`; `RemappedEdge.propagation: str`.

- [ ] **Step 1: Write the new propagation tests**

```bash
git mv tests/core/test_edge/test_edge_lazy_toggle.py tests/core/test_edge/test_edge_propagation.py
```

Replace the whole file with:

```python
"""An edge's propagation: the user's lazy/eager choice, and the modes a flow or outlet locks.

A ``Pipe`` copies its mode at construction, so a change has to rebuild it. The
pin menu and the edge properties panel both write the property directly, which
is the path these cover.
"""

from __future__ import annotations

import pytest

from haywire.core.graph.base import BaseGraph
from haywire.core.types import Propagation

from tests.conftest import make_node

_ADD = "haybale-testing:node:TestAddFloatNode"

pytestmark = [pytest.mark.integration]


def _pipe_modes(outlet) -> list[bool]:
    """``is_lazy`` of every live pipe on ``outlet``."""
    if outlet._pipes is None:
        return []
    return [pipe.is_lazy for pipe in outlet._pipes._pipes.values()]


@pytest.fixture
def linked_pair(graph_with_library_system: BaseGraph):
    """Two Adds joined by one eager data edge, validated."""
    graph = graph_with_library_system
    source, sink = make_node(graph, _ADD), make_node(graph, _ADD)
    edge = graph.create_edge_wrapper(source.node_id, "result", sink.node_id, "value_a")
    assert edge is not None
    graph.force_validation()
    return graph, source, sink, edge


@pytest.fixture
def callback_edge(graph_with_library_system: BaseGraph):
    """An event node joined to an emit node by a callback edge."""
    from haybale_testing.nodes.testbed.custom_callback_node import TestCustomCallbackNode
    from haybale_testing.nodes.testbed.emit_callback_node import TestEmitCallbackNode

    graph = graph_with_library_system
    event = graph.create_node_wrapper(TestCustomCallbackNode.class_identity.registry_key, position=(0, 0))
    emit = graph.create_node_wrapper(TestEmitCallbackNode.class_identity.registry_key, position=(300, 0))
    edge = graph.create_edge_wrapper(event.node_id, "listen_callback", emit.node_id, "edge_callback")
    assert edge is not None
    return event, edge


@pytest.fixture
def promoted_outlet_edge(graph_with_library_system: BaseGraph):
    """An edge out of a promoted setting outlet into an Add."""
    from haybale_testing.nodes.testbed.settings_node import SettingsNode
    from haywire.core.node.promotion import promote_setting
    from haywire.core.types.enums import PortType

    graph = graph_with_library_system
    src = graph.create_node_wrapper(SettingsNode.class_identity.registry_key, position=(0, 0))
    sink = make_node(graph, _ADD)
    promote_setting(src.node, "example", "example_float", direction=PortType.OUTLET)
    pid = type(src.node.example).__dict__["example_float"].storage_key
    edge = graph.create_edge_wrapper(src.node_id, pid, sink.node_id, "value_a")
    assert edge is not None
    return src, pid, edge


class TestChoosingLazyOrEager:
    def test_a_fresh_edge_is_eager(self, linked_pair):
        _graph, source, _sink, edge = linked_pair

        assert edge.propagation is Propagation.EAGER
        assert edge.locked_propagation is None
        assert _pipe_modes(source.node.ports["result"]) == [False]

    def test_choosing_lazy_reaches_the_pipe(self, linked_pair):
        _graph, source, _sink, edge = linked_pair

        edge.propagation = Propagation.LAZY

        assert _pipe_modes(source.node.ports["result"]) == [True]

    def test_choosing_eager_again_reaches_the_pipe(self, linked_pair):
        _graph, source, _sink, edge = linked_pair

        edge.propagation = Propagation.LAZY
        edge.propagation = Propagation.EAGER

        assert _pipe_modes(source.node.ports["result"]) == [False]

    def test_a_lazy_edge_defers_the_write_instead_of_pushing(self, linked_pair):
        _graph, source, sink, edge = linked_pair
        edge.propagation = Propagation.LAZY
        sink_port = sink.node.ports["value_a"]
        sink_port.set_value(0.0)

        source.node.ports["result"].set_value(42.0)

        assert sink_port.get_value() == pytest.approx(0.0)
        assert len(sink_port._pending_lazy_pipes) == 1

    def test_resolving_the_sink_then_pulls_it(self, linked_pair):
        _graph, source, sink, edge = linked_pair
        edge.propagation = Propagation.LAZY
        sink_port = sink.node.ports["value_a"]
        sink_port.set_value(0.0)
        source.node.ports["result"].set_value(42.0)

        sink_port.resolve_dirty_data()

        assert sink_port.get_value() == pytest.approx(42.0)

    def test_an_eager_edge_still_pushes_immediately(self, linked_pair):
        _graph, source, sink, _edge = linked_pair
        sink_port = sink.node.ports["value_a"]

        source.node.ports["result"].set_value(42.0)

        assert sink_port.get_value() == pytest.approx(42.0)

    def test_setting_the_same_mode_is_a_no_op(self, linked_pair):
        """Re-asserting the current mode must not disturb the live pipe."""
        _graph, source, _sink, edge = linked_pair
        edge.propagation = Propagation.LAZY
        pipe_before = next(iter(source.node.ports["result"]._pipes._pipes.values()))

        edge.propagation = Propagation.LAZY

        pipe_after = next(iter(source.node.ports["result"]._pipes._pipes.values()))
        assert pipe_after is pipe_before

    def test_the_other_edges_on_the_outlet_keep_their_own_mode(self, linked_pair):
        """A rebuild re-reads every edge, so a sibling must not be flipped too."""
        graph, source, _sink, edge = linked_pair
        third = make_node(graph, _ADD)
        graph.create_edge_wrapper(source.node_id, "result", third.node_id, "value_a")
        graph.force_validation()

        edge.propagation = Propagation.LAZY

        assert sorted(_pipe_modes(source.node.ports["result"])) == [False, True]

    def test_immediate_cannot_be_chosen(self, linked_pair):
        _graph, _source, _sink, edge = linked_pair

        with pytest.raises(ValueError, match="cannot be chosen"):
            edge.propagation = Propagation.IMMEDIATE

    def test_immediate_cannot_be_passed_at_creation(self, graph_with_library_system):
        graph = graph_with_library_system
        source, sink = make_node(graph, _ADD), make_node(graph, _ADD)

        with pytest.raises(ValueError, match="cannot be chosen"):
            graph.create_edge_wrapper(
                source.node_id, "result", sink.node_id, "value_a", propagation=Propagation.IMMEDIATE
            )


class TestLockedModes:
    def test_a_callback_edge_is_locked_immediate(self, callback_edge):
        event, edge = callback_edge

        assert edge.locked_propagation is Propagation.IMMEDIATE
        assert edge.propagation is Propagation.IMMEDIATE
        assert _pipe_modes(event.node.ports["listen_callback"]) == [False]

    def test_a_locked_edge_refuses_a_choice(self, callback_edge):
        _event, edge = callback_edge

        with pytest.raises(ValueError, match="locked"):
            edge.propagation = Propagation.LAZY

    def test_an_edge_out_of_a_promoted_outlet_is_locked_lazy(self, promoted_outlet_edge):
        src, pid, edge = promoted_outlet_edge

        assert edge.locked_propagation is Propagation.LAZY
        assert edge.propagation is Propagation.LAZY
        assert _pipe_modes(src.node.ports[pid]) == [True]
        with pytest.raises(ValueError, match="locked"):
            edge.propagation = Propagation.EAGER


class TestSaving:
    def test_the_edge_saves_the_chosen_mode(self, linked_pair):
        _graph, _source, _sink, edge = linked_pair
        edge.propagation = Propagation.LAZY

        saved = edge.edge.to_dict()

        assert saved["propagation"] == "lazy"
        assert "is_lazy" not in saved

    def test_a_locked_mode_is_not_saved(self, callback_edge):
        _event, edge = callback_edge

        assert edge.edge.to_dict()["propagation"] == "eager"

    def test_loading_restores_the_chosen_mode(self, linked_pair):
        graph, _source, _sink, edge = linked_pair
        edge.propagation = Propagation.LAZY
        edge_id = edge.edge_id
        data = graph.to_dict()

        graph.clear()
        graph.load_from_dict(data)

        assert graph.get_edge_wrapper(edge_id).propagation is Propagation.LAZY

    def test_an_unknown_saved_mode_drops_the_edge(self, linked_pair):
        graph, _source, _sink, edge = linked_pair
        edge_id = edge.edge_id
        data = graph.to_dict()
        data["edges"][edge_id]["propagation"] = "sideways"

        graph.clear()
        graph.load_from_dict(data)

        assert graph.get_edge_wrapper(edge_id) is None


class TestToggling:
    def test_eager_toggles_to_lazy_and_back(self):
        assert Propagation.EAGER.toggled() is Propagation.LAZY
        assert Propagation.LAZY.toggled() is Propagation.EAGER

    def test_immediate_does_not_toggle(self):
        with pytest.raises(ValueError, match="cannot be toggled"):
            Propagation.IMMEDIATE.toggled()
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/core/test_edge/test_edge_propagation.py -q -p no:randomly`
Expected: FAIL at import — `ImportError: cannot import name 'Propagation' from 'haywire.core.types'`.

- [ ] **Step 3: Add the `Propagation` enum**

In `enums.py`, after the `FlowType` class:

```python
class Propagation(Enum):
    """When a value written to an outlet takes effect at the inlet across an edge.

    - ``LAZY``: the inlet pulls the outlet's current value when its node next executes.
    - ``EAGER``: pushed on write; takes effect when the inlet's node next executes.
    - ``IMMEDIATE``: pushed on write and takes effect on write. Assigned from an
      immediate flow (see ``FlowType.is_immediate``), never chosen by a user.

    Wire values are the member strings, as saved in a graph's edge block.
    """

    LAZY = "lazy"
    EAGER = "eager"
    IMMEDIATE = "immediate"

    def toggled(self) -> "Propagation":
        """Return the other user-selectable mode: ``LAZY`` for ``EAGER``, and back.

        Raises:
            ValueError: For ``IMMEDIATE``, which has no user-selectable counterpart.
        """
        if self is Propagation.IMMEDIATE:
            raise ValueError("immediate propagation cannot be toggled")
        return Propagation.LAZY if self is Propagation.EAGER else Propagation.EAGER
```

In `types/__init__.py`, add `Propagation` to the line-13 import from `.enums` and `"Propagation",` to `__all__` next to `"PortType",`.

- [ ] **Step 4: `Edge.propagation`**

In `edge.py`, change `from ..types import FlowType` to `from ..types import FlowType, Propagation`. Replace:

```python
    # Lazy propagation
    is_lazy: bool = False
    """If True, data is pulled on-demand instead of pushed eagerly."""
```

with:

```python
    propagation: Propagation = Propagation.EAGER
    """The mode chosen for this edge. A locked mode overrides it; see ``EdgeWrapper.propagation``."""
```

In `to_dict`, replace `"is_lazy": self.is_lazy,` with `"propagation": self.propagation.value,`.

- [ ] **Step 5: `EdgeWrapper.propagation` and `locked_propagation`**

In `edge_wrapper.py`, change line 10 to `from ..types import FlowType, Propagation`.

In `__init__`, replace the parameter `lazy: bool = False,` with `propagation: Propagation = Propagation.EAGER,`; in its docstring replace `lazy: If True, edge uses lazy (pull-on-demand) propagation` with:

```
            propagation: The mode chosen for the edge, ``LAZY`` or ``EAGER``.

        Raises:
            ValueError: If *propagation* is ``IMMEDIATE``, which only a flow type assigns.
```

At the top of the `__init__` body (before `self.source_node_id = source_node_id`):

```python
        if propagation is Propagation.IMMEDIATE:
            raise ValueError("immediate propagation comes from the flow type; it cannot be chosen")
```

In the `Edge(...)` construction replace `is_lazy=lazy,` with `propagation=propagation,`.

Replace the whole `is_lazy` property and setter (from `    @property\n    def is_lazy(self) -> bool:` through `self._outlet_port._housekeeping()`) with:

```python
    @property
    def locked_propagation(self) -> Optional[Propagation]:
        """The mode this edge is fixed to, or ``None`` when the user may choose one.

        An immediate flow locks ``IMMEDIATE``; an edge out of an ``is_linked_lazy``
        outlet (every promoted outlet) locks ``LAZY``. The second is known once the
        edge has resolved its outlet port during ``build()``.
        """
        if self._edge_type is not None and self._edge_type.is_immediate:
            return Propagation.IMMEDIATE
        if self._outlet_port is not None and self._outlet_port.is_linked_lazy:
            return Propagation.LAZY
        return None

    @property
    def propagation(self) -> Propagation:
        """The mode in effect: the locked mode when there is one, else the one chosen for the edge."""
        return self.locked_propagation or self._edge.propagation

    @propagation.setter
    def propagation(self, value: Propagation) -> None:
        """Choose ``LAZY`` or ``EAGER`` for this edge and rebuild its pipe.

        Raises:
            ValueError: If *value* is ``IMMEDIATE``, or the edge's mode is locked.
        """
        if value is Propagation.IMMEDIATE:
            raise ValueError("immediate propagation comes from the flow type; it cannot be chosen")
        locked = self.locked_propagation
        if locked is not None:
            raise ValueError(f"edge {self._edge_id} is locked to {locked.value} propagation")
        if self._edge.propagation is value:
            return
        self._edge.propagation = value
        # A Pipe copies its mode at construction, so the live pipe keeps the old
        # one until the outlet rebuilds it.
        if self._outlet_port is not None:
            self._outlet_port._mark_as_structuraly_dirty()
            self._outlet_port._housekeeping()
```

- [ ] **Step 6: Pipes read the mode in effect**

In `pipe.py`, add `from haywire.core.types.enums import Propagation` after `from haywire.core.edge.edge_wrapper import EdgeWrapper`. In `Pipes.add_pipe`, replace `is_lazy=edge_wrapper.is_lazy,` with `is_lazy=edge_wrapper.propagation is Propagation.LAZY,`.

- [ ] **Step 7: Drop the silent forcing in `_refresh_pipes`**

In `port.py`, replace:

```python
                for wrapper in self.get_valid_edges():
                    # A promoted outlet writes its cell OUTSIDE the scheduler frame
                    # (widget / registry / edge) — an eager pull then is unsafe.
                    # Forcing the edge lazy defers each consumer's pull to its next
                    # execution; add_pipe reads is_lazy below.
                    if self.is_linked_lazy:
                        wrapper.is_lazy = True
                    self._pipes.add_pipe(wrapper)
```

with:

```python
                # An is_linked_lazy outlet's edges report LAZY themselves; see
                # EdgeWrapper.locked_propagation.
                for wrapper in self.get_valid_edges():
                    self._pipes.add_pipe(wrapper)
```

Change the `is_linked_lazy` field docstring from `"""Force any linked edge to lazy (pull-on-demand) propagation"""` to `"""Lock every linked edge to lazy (pull-on-demand) propagation. See ``EdgeWrapper.locked_propagation``."""`, and in the `_on_shared_field_changed` docstring replace `(forced by ``is_linked_lazy``)` with `(locked by ``is_linked_lazy``)`.

- [ ] **Step 8: Graph creation and loading**

In `graph/base.py`, change line 20 to `from ..types import FlowType, Propagation`. In `create_edge_wrapper`, replace the parameter `lazy: bool = False,` with `propagation: Propagation = Propagation.EAGER,`; replace the docstring entry `lazy: When ``True`` the edge uses lazy (pull-on-demand) propagation.` with `propagation: The mode chosen for the edge; a locked mode overrides it (see ``EdgeWrapper.locked_propagation``).`; add to its `Raises:` `ValueError: If *propagation* is ``IMMEDIATE``.`; replace `lazy=lazy,` with `propagation=propagation,`.

In `load_from_dict`, replace `lazy=edge_data.get("is_lazy", False),` with `propagation=Propagation(edge_data.get("propagation", Propagation.EAGER.value)),`.

- [ ] **Step 9: Copy/paste remap**

In `node_remap.py`, replace `    is_lazy: bool = False` with:

```python
    propagation: str = "eager"
    """The chosen ``Propagation`` value as serialized, e.g. ``"eager"``."""
```

and `is_lazy=edge.get("is_lazy", False),` with `propagation=edge.get("propagation", "eager"),`.

- [ ] **Step 10: Update the remaining tests**

`tests/core/test_graph/test_edges.py`: add `from haywire.core.types import Propagation` to the imports; in `_link`, keep the `lazy: bool = False` parameter and replace `lazy=lazy` in the call with `propagation=Propagation.LAZY if lazy else Propagation.EAGER`. In `test_lazy_edge_creation` change the docstring to `"""create_edge_wrapper(..., propagation=LAZY) should set it on the edge."""` and the two asserts to `assert edge.propagation is Propagation.LAZY` and `assert edge.edge.propagation is Propagation.LAZY`. In `test_lazy_edge_serialization` change the docstring to `"""The chosen propagation should survive to_dict()."""`, `assert edge_dict["is_lazy"] is True` to `assert edge_dict["propagation"] == "lazy"`, the comment `# Eager edge should serialize as False` to `# Eager edge should serialize as "eager"`, and `assert eager_edge.edge.to_dict()["is_lazy"] is False` to `assert eager_edge.edge.to_dict()["propagation"] == "eager"`.

`tests/core/test_assembly/test_subgraph_execution_edges.py`: add `from haywire.core.types import Propagation`; replace `lazy_edge.is_lazy = True` with `lazy_edge.propagation = Propagation.LAZY`, `assert edges[0].is_lazy is True` with `assert edges[0].propagation is Propagation.LAZY`, and `out_edge.is_lazy = True` with `out_edge.propagation = Propagation.LAZY`.

`tests/core/node/test_promotion_e2e.py`: in `test_promoted_outlet_drives_consumer_lazily`, change the docstring phrase `The linked edge is forced is_lazy.` to `The linked edge is locked lazy.`, the comment `# The linked edge was forced lazy by the is_linked_lazy outlet.` to `# The is_linked_lazy outlet locks the linked edge to lazy.`, and `assert edge.is_lazy is True` to:

```python
    from haywire.core.types import Propagation

    assert edge.locked_propagation is Propagation.LAZY
```

`tests/core/test_graph/test_clipboard_payload.py` (lines 44 and 54) and `tests/core/test_undo/test_paste_action.py` (lines 117 and 308): replace each `"is_lazy": False,` with `"propagation": "eager",`.

- [ ] **Step 11: Check no `is_lazy` API use is left in core or tests**

Run: `grep -rn "\.is_lazy\b\|is_lazy=\|\"is_lazy\"\|lazy=lazy\|lazy=True\|lazy=False" --include="*.py" packages/haywire-core/src/ tests/ | grep -v "pipe.is_lazy\|self.is_lazy\|is_lazy=edge_wrapper.propagation\|is_linked_lazy"`
Expected: only `tests/core/test_graph/test_edges.py` lines calling `_link(..., lazy=True|False)` (the helper keeps its bool parameter).

- [ ] **Step 12: Run the tests**

Run: `uv run pytest tests/core/test_edge/ tests/core/test_graph/ tests/core/test_assembly/test_subgraph_execution_edges.py tests/core/node/ tests/core/test_undo/ -q -p no:randomly`
Expected: PASS.

- [ ] **Step 13: Lint, types, commit**

```bash
uv run ruff check packages/haywire-core/src/haywire/core tests/core && uv run ruff format --check packages/haywire-core/src/haywire/core tests/core
uv run mypy packages/haywire-core/src/ tests/
git add -A packages/haywire-core/src/haywire/core tests/core
git commit -m "feat(edges): Propagation mode (lazy/eager/immediate) replaces is_lazy

Edge.propagation stores the user's choice and saves as \"propagation\".
EdgeWrapper.propagation applies two locks: IMMEDIATE from an immediate flow,
LAZY from an is_linked_lazy outlet. The promoted-outlet lock was a silent
override in _refresh_pipes that reverted a user's eager choice.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Propagation in the graph editor and Farmhand

**Files:**
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/surfaces/edge.py` (`EdgeActions`)
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/context_menu.py` (`set_edge_lazy` / `edge_is_lazy` / `toggle_edge_lazy`, ~477-510)
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/edge/edge.py` (`LazyEdgeMenuPanel`, ~205-265)
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/panels/properties/introspect/edge.py` (`EdgeLazyPanel`, ~106-142)
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/farmhands/editor_tools.py` (`_edge_row` ~491, `query_graph` instructions ~529-530)
- Test: `tests/ui/graph_canvas/test_session_context_menu_provider.py` (append)

**Interfaces:**
- Consumes: `Propagation`, `EdgeWrapper.propagation`, `EdgeWrapper.locked_propagation` (Task 4).
- Produces: `EdgeActions.edge_propagation(edge_id) -> Propagation | None`, `EdgeActions.edge_propagation_locked(edge_id) -> bool`, `EdgeActions.toggle_edge_propagation(edge_id) -> Propagation | None`; panels `EdgePropagationMenuPanel`, `EdgePropagationPanel`; `query_graph` detail keys `propagation`, `propagation_locked`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/ui/graph_canvas/test_session_context_menu_provider.py`:

```python
class _FakeEdge:
    """Just enough of an EdgeWrapper for the propagation verbs."""

    def __init__(self, chosen, locked=None):
        self.chosen = chosen
        self.locked_propagation = locked
        self.redraws = 0

    @property
    def propagation(self):
        return self.locked_propagation or self.chosen

    @propagation.setter
    def propagation(self, value):
        self.chosen = value

    def redraw(self):
        self.redraws += 1


def _provider_with_edge(edge: _FakeEdge) -> SessionContextMenuProvider:
    provider = _make_provider()
    stub = cast(Any, provider)._test_edit_stub
    stub.active_graph = SimpleNamespace(get_edge_wrapper=lambda edge_id: edge if edge_id == "e1" else None)
    return provider


def test_toggle_edge_propagation_switches_eager_to_lazy():
    from haywire.core.types import Propagation

    edge = _FakeEdge(Propagation.EAGER)
    provider = _provider_with_edge(edge)

    assert provider.toggle_edge_propagation("e1") is Propagation.LAZY
    assert edge.chosen is Propagation.LAZY
    assert edge.redraws == 1


def test_toggle_edge_propagation_leaves_a_locked_edge_alone():
    from haywire.core.types import Propagation

    edge = _FakeEdge(Propagation.EAGER, locked=Propagation.IMMEDIATE)
    provider = _provider_with_edge(edge)

    assert provider.toggle_edge_propagation("e1") is Propagation.IMMEDIATE
    assert edge.chosen is Propagation.EAGER
    assert edge.redraws == 0


def test_edge_propagation_reports_the_mode_and_the_lock():
    from haywire.core.types import Propagation

    provider = _provider_with_edge(_FakeEdge(Propagation.EAGER, locked=Propagation.LAZY))

    assert provider.edge_propagation("e1") is Propagation.LAZY
    assert provider.edge_propagation_locked("e1") is True


def test_an_unknown_edge_has_no_propagation():
    from haywire.core.types import Propagation

    provider = _provider_with_edge(_FakeEdge(Propagation.EAGER))

    assert provider.edge_propagation("nope") is None
    assert provider.edge_propagation_locked("nope") is False
    assert provider.toggle_edge_propagation("nope") is None
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/ui/graph_canvas/test_session_context_menu_provider.py -q -p no:randomly`
Expected: the four new tests FAIL with `AttributeError: 'SessionContextMenuProvider' object has no attribute 'toggle_edge_propagation'` (and `edge_propagation`).

- [ ] **Step 3: The `EdgeActions` protocol**

In `surfaces/edge.py`, add `from haywire.core.types.enums import Propagation` under the `if TYPE_CHECKING:` block, and replace the three lazy verbs with:

```python
    def edge_propagation(self, edge_id: str) -> "Propagation | None": ...
    def edge_propagation_locked(self, edge_id: str) -> bool: ...
    def toggle_edge_propagation(self, edge_id: str) -> "Propagation | None": ...
```

- [ ] **Step 4: The provider's verbs**

In `context_menu.py`, add under a `TYPE_CHECKING` guard (create one after the `typing` import if the module has none: `from typing import TYPE_CHECKING, Any, Callable, Optional, Tuple`):

```python
if TYPE_CHECKING:
    from haywire.core.edge.edge_wrapper import EdgeWrapper
    from haywire.core.types.enums import Propagation
```

Replace `set_edge_lazy`, `edge_is_lazy` and `toggle_edge_lazy` with:

```python
    def edge_propagation(self, edge_id: str) -> "Propagation | None":
        """Return the propagation mode in effect on edge ``edge_id``, or ``None`` if there is no such edge."""
        wrapper = self._active_edge_wrapper(edge_id)
        return None if wrapper is None else wrapper.propagation

    def edge_propagation_locked(self, edge_id: str) -> bool:
        """True when edge ``edge_id`` exists and its propagation mode is locked."""
        wrapper = self._active_edge_wrapper(edge_id)
        return wrapper is not None and wrapper.locked_propagation is not None

    def toggle_edge_propagation(self, edge_id: str) -> "Propagation | None":
        """Switch an edge between lazy and eager, redraw it, and report the new mode.

        Decided here, on each click, for the same reason as
        ``toggle_selection_collapsed``: the menu stays open after the row's
        click, so a value captured at draw time would only ever apply once.
        Returns a locked edge's mode unchanged, or ``None`` when there is no
        such edge.
        """
        wrapper = self._active_edge_wrapper(edge_id)
        if wrapper is None:
            return None
        if wrapper.locked_propagation is None:
            wrapper.propagation = wrapper.propagation.toggled()
            wrapper.redraw()
        return wrapper.propagation

    def _active_edge_wrapper(self, edge_id: str) -> "EdgeWrapper | None":
        graph = self._context.data[EditState].active_graph
        return None if graph is None else graph.get_edge_wrapper(edge_id)
```

- [ ] **Step 5: The edge menu row**

In `panels/graph/menu/edge/edge.py`, add `from haywire.core.types.enums import Propagation` to the imports. Replace the whole `LazyEdgeMenuPanel` class (keep its `@panel(...)` decorator unchanged) with:

```python
class EdgePropagationMenuPanel(BasePanel):
    """Show an edge's propagation mode and switch it between lazy and eager.

    **The row rewrites itself on click rather than closing over its state**,
    for the same reason as `CollapseSelectionMenuPanel`: `hui.menu_row` does
    not dismiss its popup, so a handler that captured the mode at draw time
    would keep re-sending that value and the toggle would work exactly once.
    The current mode is asked for on every click (`toggle_edge_propagation`
    decides and returns the new one).

    The icon and label both name the current mode: propagation is a standing
    property of the edge, so the row reads "Propagation: Lazy/Eager/Immediate"
    rather than a command. A mode the connection fixes draws a disabled row.
    """

    actions: EdgeActions

    _LABELS = {Propagation.LAZY: "Lazy", Propagation.EAGER: "Eager", Propagation.IMMEDIATE: "Immediate"}
    _ICONS = {
        Propagation.LAZY: hui.icon.edge_lazy,
        Propagation.EAGER: hui.icon.edge_eager,
        Propagation.IMMEDIATE: hui.icon.edge_propagation,
    }
    _LOCKED_TOOLTIPS = {
        Propagation.IMMEDIATE: "Callback connections always take effect immediately.",
        Propagation.LAZY: "Connections from a promoted setting are always lazy.",
    }

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return ctx.data[EditState].active_edge is not None

    @classmethod
    def _row_text(cls, mode: Propagation) -> str:
        return f"Propagation: {cls._LABELS[mode]}"

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        edge = ctx.data[EditState].active_edge
        if edge is None:
            return
        edge_id = edge.edge_id
        mode = self.actions.edge_propagation(edge_id)
        if mode is None:
            return
        locked = self.actions.edge_propagation_locked(edge_id)

        with layout:
            row = hui.menu_row(
                self._row_text(mode),
                icon=self._ICONS[mode],
                enabled=not locked,
                tooltip=(
                    self._LOCKED_TOOLTIPS[mode]
                    if locked
                    else "Lazy propagation pulls data on demand instead of pushing it on write."
                ),
            )
        if locked:
            return

        icon_el = next((c for c in row.default_slot.children if isinstance(c, ui.icon)), None)
        label_el = next((c for c in row.default_slot.children if isinstance(c, ui.label)), None)

        def _toggle() -> None:
            now = self.actions.toggle_edge_propagation(edge_id)
            if now is None:
                return
            if label_el is not None:
                label_el.set_text(self._row_text(now))
            if icon_el is not None:
                icon_el.set_name(self._ICONS[now])

        row.on("click", lambda _e=None: _toggle())
```

- [ ] **Step 6: The properties panel**

In `panels/properties/introspect/edge.py`, add `from haywire.core.types.enums import Propagation` to the imports. Replace the whole `EdgeLazyPanel` class (keep its `@panel(...)` decorator) with:

```python
class EdgePropagationPanel(BasePanel):
    """Switch the active edge between eager and lazy propagation, or show the mode it is fixed to.

    Writes `EdgeWrapper.propagation` directly, like `EdgeStatsPanel` and
    `EdgePathPanel` read it — `EdgeInspector` declares no `provides`, so its
    panels have no action host to route the write through.
    """

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return ctx.data[EditState].active_edge is not None

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        edge_wrapper = ctx.data[EditState].active_edge
        if edge_wrapper is None:
            return

        locked = edge_wrapper.locked_propagation
        if locked is not None:
            with layout:
                with ui.row().classes("w-full items-center gap-1 py-0.5"):
                    ui.icon(hui.icon.edge_propagation).classes("text-lg")
                    ui.label(f"{locked.value.capitalize()} (fixed by the connection)").classes(
                        "text-xs hw-text-muted"
                    )
            return

        def _on_change(e) -> None:
            edge_wrapper.propagation = Propagation.LAZY if e.value else Propagation.EAGER
            edge_wrapper.redraw()

        with layout:
            with ui.row().classes("w-full items-center gap-1 py-0.5"):
                ui.icon(hui.icon.edge_eager).classes("text-lg")
                ui.switch(
                    value=edge_wrapper.propagation is Propagation.LAZY, on_change=_on_change
                ).props("dense")
                ui.icon(hui.icon.edge_lazy).classes("text-lg")
```

- [ ] **Step 7: Farmhand `query_graph`**

In `editor_tools.py` `_edge_row`, replace `"is_lazy": edge.is_lazy,` with:

```python
                "propagation": edge.propagation.value,
                "propagation_locked": edge.locked_propagation is not None,
```

In the `query_graph` instructions string replace `"is_lazy, adapter_chain, has_adapters, error); default returns the base id/direction/"` with `"propagation, propagation_locked, adapter_chain, has_adapters, error); default returns the "` and the next line `"flow_type per port and id/topology/flow_type per edge."` with `"base id/direction/flow_type per port and id/topology/flow_type per edge."` (keep the string's lines under 109 characters).

- [ ] **Step 8: Check no lazy verb or panel name is left**

Run: `grep -rn "is_lazy\|edge_is_lazy\|toggle_edge_lazy\|set_edge_lazy\|LazyEdgeMenuPanel\|EdgeLazyPanel" --include="*.py" barn/ packages/ tests/ | grep -v "pipe.is_lazy\|self.is_lazy\|is_lazy=edge_wrapper\|is_linked_lazy\|_pipe_modes"`
Expected: no output.

- [ ] **Step 9: Run the tests**

Run: `uv run pytest tests/ui/graph_canvas/ tests/farmhand/ tests/ui/panel/ -q -p no:randomly`
Expected: PASS.

- [ ] **Step 10: Regenerate the graph-editor library docs**

Run: `uv run haywire docs barn/haybale-graph-editor`
Expected: the generated OVERVIEW/QUICKREF/docs files update the two panel names; review the diff (`git diff --stat barn/haybale-graph-editor`).

- [ ] **Step 11: Lint, types, commit**

```bash
uv run ruff check barn/haybale-graph-editor tests/ui && uv run ruff format --check barn/haybale-graph-editor tests/ui
uv run mypy barn/haybale-graph-editor/haybale_graph_editor/ tests/
git add -A barn/haybale-graph-editor tests/ui/graph_canvas/test_session_context_menu_provider.py
git commit -m "feat(graph-editor): propagation row and panel; locked modes read-only

EdgePropagationMenuPanel and EdgePropagationPanel replace the lazy toggles
and show a locked mode (immediate, promoted lazy) disabled. Farmhand
query_graph reports propagation and propagation_locked.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Reroutes relay callbacks

**Files:**
- Modify: `packages/haywire-core/src/haywire/barn/builtin/nodes/reroute.py` (module docstring 1-24, `@node(description=...)` 38, new method)
- Modify: `packages/haywire-core/src/haywire/core/undo/actions/graph_actions.py` (constants 30-31, `_AddReroutePortsAction` 599-641, `SplitEdgeWithRerouteAction` docstring + construction 649-719)
- Modify: `packages/haywire-core/src/haywire/core/validation/structural_validator.py` (`validate_edge` + `_validate_callback_edge`, 508-567)
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/edge/edge.py` (`InsertRerouteMenuPanel` docstring + poll, ~96-116)
- Modify tests: `tests/core/test_undo/test_split_edge_reroute.py`, `tests/core/test_edge/test_disconnect_semantics.py`

**Interfaces:**
- Consumes: `DataPort.is_immediate` (Task 1).
- Produces: `RerouteNode.forward_immediate(port: DataPort, value: Any) -> None`; `_AddReroutePortsAction(..., inlet_on_change: Optional[str] = None)`; constant `_REROUTE_FORWARD_HANDLER = "forward_immediate"` in `graph_actions.py`.

- [ ] **Step 1: Update and add the failing tests**

In `tests/core/test_edge/test_disconnect_semantics.py`, delete the `@pytest.mark.xfail(...)` decorator (all four lines) above `test_callback_through_a_reroute_reaches_the_emit_node`.

In `tests/core/test_undo/test_split_edge_reroute.py`:

1. In `test_split_action_resolves_outlet_type_and_builds_children`, after `assert (addports.inlet_id, addports.outlet_id) == (_RR_IN, _RR_OUT)` add:

```python
    # The inlet forwards immediate (callback) values through the reroute's handler.
    assert addports.inlet_on_change == "forward_immediate"
```

2. In `test_add_ports_action_rejigs_to_new_type`, change the fake's `def as_inlet(id, label=""):` to `def as_inlet(id, label="", **kwargs):`.

3. Replace the whole `test_callback_edge_from_reroute_is_invalid` function with:

```python
def test_callback_edge_from_reroute_is_valid():
    """A reroute may be the source of a CALLBACK edge: it relays the subscription."""
    from haywire.core.validation.structural_validator import StructuralValidator
    from haywire.core.node.behavior import NodeBehaviorFlags, NodeType
    from haywire.core.types.enums import FlowType

    class _Node:
        behavior = NodeBehaviorFlags(node_type=NodeType.REROUTE)
        node_id = "reroute_1"

    class _SourceWrapper:
        node = _Node()

    class _EdgeWrapper:
        _edge_type = FlowType.CALLBACK
        _source_wrapper = _SourceWrapper()
        source_node_id = "reroute_1"

    validator = StructuralValidator.__new__(StructuralValidator)
    ok, err, _ = validator.validate_edge(cast(Any, _EdgeWrapper()))
    assert ok
    assert err is None
```

4. Add to `class TestSplitEdgeRerouteIntegration`:

```python
    def test_a_data_reroute_still_forwards_only_when_it_runs(self, graph_with_library_system, library_system):
        """The inlet's on_change handler forwards immediate values only; DATA waits for the worker."""
        from haywire.core.undo.actions.graph_actions import SplitEdgeWithRerouteAction

        graph = graph_with_library_system
        node_a, node_b, edge = self._two_connected_nodes(graph)
        action = SplitEdgeWithRerouteAction(
            graph=cast(Any, graph), edge_id=edge.edge_id, position=(200.0, 200.0), **self._reroute_args()
        )
        action._execute_impl()
        reroute = graph.node_wrappers[action.reroute_node_id].node
        sink = node_b.node.ports["value_a"]

        node_a.node.out("result", 42.0)
        reroute.ports["in"].resolve_dirty_data()  # fires the deferred on_change

        assert reroute.ports["in"].get_value() == 42.0
        assert sink.get_value() != 42.0
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/core/test_undo/test_split_edge_reroute.py tests/core/test_edge/test_disconnect_semantics.py -q -p no:randomly`
Expected: FAIL — `addports.inlet_on_change` missing (`AttributeError`), `test_callback_edge_from_reroute_is_valid` (`assert False`), `test_callback_through_a_reroute_reaches_the_emit_node` (`assert all(...)` false). `test_a_data_reroute_still_forwards_only_when_it_runs` PASSES already (it guards Step 3).

- [ ] **Step 3: The reroute's forwarding handler**

In `reroute.py`, replace the module-docstring paragraph

```
CALLBACK edges are NOT supported: the flow assembly manager reads the
subscription key from the reroute outlet at wiring time — before any worker
has run to forward it — so the listener flow would never register.
```

with:

```
CALLBACK edges pass through too. A callback inlet is immediate, so the split
action wires it to ``forward_immediate``, which copies each write to the outlet
at once: the emitter downstream sees a subscription at wiring time, and its
absence as soon as an edge upstream is removed.
```

Change the `@node` description to `"Pass-through node for bending wires. Supports DATA, CONTROL and CALLBACK edges."`. Add `from typing import TYPE_CHECKING, Any` after `from __future__ import annotations`, and after the imports:

```python
if TYPE_CHECKING:
    from haywire.core.types.port import DataPort
```

Add this method after `worker`:

```python
    def forward_immediate(self, port: DataPort, value: Any) -> None:
        """Copy an immediate inlet's value to the outlet as soon as it is written.

        Wired as the inlet's ``on_change`` by the edge-split action. A deferred
        inlet also calls it, when the node resolves before executing; the worker
        forwards that value, so this returns without writing.
        """
        if not port.is_immediate:
            return
        outlets = self.get_ports(is_port_type=PortType.OUTLET, has_pin=True)
        if outlets:
            outlets[0].set_value(value)
```

- [ ] **Step 4: The split action wires the handler**

In `graph_actions.py`, after `_REROUTE_OUTLET_ID = "out"` add:

```python
#: The reroute node's handler its inlet calls on change; it forwards immediate values.
_REROUTE_FORWARD_HANDLER = "forward_immediate"
```

In `_AddReroutePortsAction`: add the parameter `inlet_on_change: Optional[str] = None,` after `outlet_id: str,`; add to the class docstring the sentence `` ``inlet_on_change`` names the node method the inlet calls when its value changes, or ``None`` for none.``; store `self.inlet_on_change = inlet_on_change`; and change the inlet line to:

```python
            node.add(self.itype.as_inlet(id=self.inlet_id, label="", on_change=self.inlet_on_change))
```

In `SplitEdgeWithRerouteAction`, change the first docstring line to `"""Split an edge and insert a reroute node in between.` and pass `inlet_on_change=_REROUTE_FORWARD_HANDLER,` to `_AddReroutePortsAction(...)` after `outlet_id=_REROUTE_OUTLET_ID,`.

- [ ] **Step 5: Drop the event-source rule**

In `structural_validator.py`, replace the body of `validate_edge` after its docstring (from `# Check edge type-specific rules` through `return (True, None, [])`) with:

```python
        # No flow type adds an edge-level rule; data cycles are validated graph-wide.
        return (True, None, [])
```

and delete the whole `_validate_callback_edge` method.

- [ ] **Step 6: The menu offers the split on callback edges**

In `panels/graph/menu/edge/edge.py` `InsertRerouteMenuPanel`, replace the docstring with `"""Split the active edge and insert a reroute node in between. Available for every edge."""` and, in `poll`, replace `return not edge.is_callback_edge()` with `return True`.

- [ ] **Step 7: Run the tests**

Run: `uv run pytest tests/core/test_undo/ tests/core/test_edge/ tests/core/node/test_boundary_nodes.py -q -p no:randomly`
Expected: PASS; `test_disconnect_semantics.py` reports `2 passed, 3 xfailed`.

- [ ] **Step 8: Lint, types, commit**

```bash
uv run ruff check packages/haywire-core/src/haywire barn/haybale-graph-editor tests/core && uv run ruff format --check packages/haywire-core/src/haywire barn/haybale-graph-editor tests/core
uv run mypy packages/haywire-core/src/ barn/haybale-graph-editor/haybale_graph_editor/ tests/
git add -A packages/haywire-core/src/haywire barn/haybale-graph-editor tests/core
git commit -m "feat(reroute): callback edges pass through reroutes

The split action wires the reroute inlet to forward_immediate, which
copies immediate writes to the outlet at once. The structural rule that a
callback edge's source is an event node is gone, and the edge menu offers
Insert Reroute on callback edges.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Unlinking an immediate inlet unsubscribes downstream

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/types/port.py` (new `_reset_if_unlinked`, near `_try_reenable` ~681)
- Modify: `packages/haywire-core/src/haywire/core/edge/edge_wrapper.py` (`unlink` 350-375, `detach` 377-399)
- Create: `barn/haybale-testing/haybale_testing/nodes/testbed/record_callback_nodes.py`; modify `barn/haybale-testing/haybale_testing/nodes/__init__.py`
- Modify tests: `tests/core/test_edge/test_disconnect_semantics.py`

**Interfaces:**
- Consumes: absence-capable fields (Task 2), pooled absence (Task 3), `is_immediate` (Task 1), `forward_immediate` (Task 6).
- Produces: `DataPort._reset_if_unlinked() -> None`; test nodes `TestRecordEventNode` (outlet `subscription`, `TEST_RECORD_CALLBACK`) and `TestRecordEmitNode` (inlet `subscriptions`, `PooledType[TEST_RECORD_CALLBACK]`).

- [ ] **Step 1: The dataclass-callback test nodes**

Create `barn/haybale-testing/haybale_testing/nodes/testbed/record_callback_nodes.py`:

```python
from haywire.core.execution.event_source import CallbackEvent
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode, NodeType


@node(
    label="Test Record Event",
    description="Test event node whose subscription is a dataclass callback value",
    menu="testing/callbacks",
    search_tags=["test", "callback", "event", "record"],
    node_type=NodeType.EVENT,
)
class TestRecordEventNode(BaseNode):
    """Test-only event node publishing a `TEST_RECORD_CALLBACK` subscription named after itself."""

    def init(self):
        from haybale_core.types import EXEC
        from haybale_testing.types import TEST_RECORD_CALLBACK

        self.add(
            TEST_RECORD_CALLBACK.as_outlet(
                "subscription",
                label="Listen",
                default={"name": self.node_id, "weight": 1},
                allow_multiple_links=True,
            )
        )
        self.add(EXEC.as_outlet("triggered", label="Triggered"))

    def post_init(self):
        self.event_subscription = CallbackEvent(event_name=self.node_id)

    def worker(self, context: ExecutionContext) -> str | None:
        return "triggered"


@node(
    label="Test Record Emit",
    description="Test control node emitting to every dataclass subscription in its pool",
    menu="testing/callbacks",
    search_tags=["test", "callback", "emit", "record"],
    node_type=NodeType.CONTROL,
)
class TestRecordEmitNode(BaseNode):
    """Test-only emitter collecting `TEST_RECORD_CALLBACK` subscriptions in a pooled inlet."""

    def init(self):
        from haybale_core.types import EXEC, PooledType
        from haybale_testing.types import TEST_RECORD_CALLBACK

        self.add(EXEC.as_inlet("execute", label="Execute"))
        self.add(PooledType[TEST_RECORD_CALLBACK].as_inlet("subscriptions", label="Trigger"))
        self.add(EXEC.as_outlet("exec", label="Then"))

    def worker(self, context: ExecutionContext) -> str | None:
        for record in self.value("subscriptions").values():
            context.emit_callback(event_name=record.name, payload={"weight": record.weight})
        return "exec"
```

In `nodes/__init__.py` add `from .testbed.record_callback_nodes import TestRecordEmitNode, TestRecordEventNode` (keep the import list sorted) and add both names to `__all__` if the module defines one.

- [ ] **Step 2: Write the failing tests**

In `tests/core/test_edge/test_disconnect_semantics.py`:

1. Delete the `@pytest.mark.xfail(...)` decorator above `test_removing_the_edge_before_a_reroute_unsubscribes_the_emit_node`.

2. Replace the module docstring with:

```python
"""What a port holds once the edge driving it is removed, and callbacks passing through reroutes.

The ``xfail(strict=True)`` tests describe the Blender model — an inlet keeps
the value the user gave it while linked and shows it again after unlinking.
Current code keeps the last edge-driven value instead (ADR 0014 §C3,
freeze-on-disconnect). Strict markers turn each into a failure the moment it
starts passing, so the marker is removed with the change that fixes it.
"""
```

3. Append:

```python
def _record_pair(graph):
    """Create a record event node and a record emit node joined by a direct callback edge."""
    from haybale_testing.nodes.testbed.record_callback_nodes import TestRecordEmitNode, TestRecordEventNode

    event = graph.create_node_wrapper(TestRecordEventNode.class_identity.registry_key, position=(0, 0))
    emit = graph.create_node_wrapper(TestRecordEmitNode.class_identity.registry_key, position=(400, 0))
    edge = graph.create_edge_wrapper(event.node_id, "subscription", emit.node_id, "subscriptions")
    return event, emit, edge


def test_a_displaced_edge_taking_over_keeps_the_emit_node_subscribed(
    graph_with_library_system, library_system
):
    from haybale_testing.nodes.testbed.custom_callback_node import TestCustomCallbackNode

    graph = graph_with_library_system
    first, emit, edge = _callback_pair(graph)
    reroute_id = _split_with_reroute(graph, edge.edge_id)
    second = graph.create_node_wrapper(TestCustomCallbackNode.class_identity.registry_key, position=(0, 200))
    newer = graph.create_edge_wrapper(second.node_id, "listen_callback", reroute_id, "in")
    assert _subscriptions(emit) == [second.node.value("listen_callback")]
    seen: list = []
    emit.node.ports["edge_callback"].data.add_observer(lambda change: seen.append(change.value))

    graph.remove_edge_wrapper(newer.edge_id)

    assert _subscriptions(emit) == [first.node.value("listen_callback")]
    assert all(seen), "the emit node's pool went empty while the displaced edge took over"


def test_a_dataclass_subscription_passes_through_a_reroute(graph_with_library_system, library_system):
    graph = graph_with_library_system
    event, emit, edge = _record_pair(graph)

    _split_with_reroute(graph, edge.edge_id)

    records = list(emit.node.ports["subscriptions"].get_value().values())
    assert [record.name for record in records] == [event.node_id]


def test_removing_the_edge_before_a_reroute_drops_a_dataclass_subscription(
    graph_with_library_system, library_system
):
    graph = graph_with_library_system
    _event, emit, edge = _record_pair(graph)
    reroute_id = _split_with_reroute(graph, edge.edge_id)
    upstream = next(e for e in graph.edge_wrappers.values() if e.sink_node_id == reroute_id)

    graph.remove_edge_wrapper(upstream.edge_id)

    assert emit.node.ports["subscriptions"].get_value() == {}


def test_a_graph_holding_an_absent_callback_saves_and_loads(graph_with_library_system, library_system):
    graph = graph_with_library_system
    _event, _emit, edge = _callback_pair(graph)
    reroute_id = _split_with_reroute(graph, edge.edge_id)
    upstream = next(e for e in graph.edge_wrappers.values() if e.sink_node_id == reroute_id)
    graph.remove_edge_wrapper(upstream.edge_id)
    data = graph.to_dict()

    graph.clear()
    graph.load_from_dict(data)

    assert graph.node_wrappers[reroute_id].node.ports["out"].get_value() is None
```

- [ ] **Step 3: Run to verify failure**

Run: `uv run pytest tests/core/test_edge/test_disconnect_semantics.py -q -p no:randomly`
Expected: FAIL — `test_removing_the_edge_before_a_reroute_unsubscribes_the_emit_node` and `..._drops_a_dataclass_subscription` (entry left in the pool), `test_a_graph_holding_an_absent_callback_saves_and_loads` (reroute outlet still holds the name). The displacement and pass-through tests PASS; the two edge-kinds step-6 tests stay xfailed.

- [ ] **Step 4: The port's reset**

In `port.py`, add after `_try_reenable`:

```python
    def _reset_if_unlinked(self) -> None:
        """Set an immediate inlet that no edge feeds any more to absence.

        Fires ``on_change`` like any widget write, so a reroute passes the
        absence on and the emitter at the end of the chain drops the entry.
        A pooled inlet has nothing left to clear: unlinking already removed
        each source's entry.
        """
        if not (self._is_inlet and self._is_immediate) or self._linked_edges:
            return
        if self._data.has_data():
            self.set_value(None)
```

- [ ] **Step 5: Call it after re-enablement**

In `edge_wrapper.py`, in both `unlink` and `detach`, directly after `self._try_reenable_on_ports()` insert:

```python
        # After re-enablement, so a displaced edge that took over leaves the value alone.
        if self._inlet_port:
            self._inlet_port._reset_if_unlinked()
```

- [ ] **Step 6: Run the tests**

Run: `uv run pytest tests/core/test_edge/ tests/core/test_undo/ tests/core/test_types/ tests/core/test_graph/ -q -p no:randomly`
Expected: PASS; `test_disconnect_semantics.py` reports `7 passed, 2 xfailed`.

- [ ] **Step 7: Regenerate the testing library docs**

Run: `uv run haywire docs barn/haybale-testing`
Expected: new entries for the two record nodes and `TEST_RECORD_CALLBACK`; review `git diff --stat barn/haybale-testing`.

- [ ] **Step 8: Lint, types, commit** (commit before running the full suite: `barn/haybale-testing` changed)

```bash
uv run ruff check packages/haywire-core/src/haywire/core barn/haybale-testing tests/core && uv run ruff format --check packages/haywire-core/src/haywire/core barn/haybale-testing tests/core
uv run mypy packages/haywire-core/src/ barn/haybale-testing/haybale_testing/ tests/
git add -A packages/haywire-core/src/haywire/core barn/haybale-testing tests/core/test_edge/test_disconnect_semantics.py
git commit -m "feat(edges): an unlinked immediate inlet goes absent

After re-enablement, an immediate inlet left without a linked edge is set
to None and fires on_change, so a reroute forwards the absence and the
emitter's pool drops the entry keyed by its own edge. Adds record-callback
test nodes for a dataclass callback type.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Docs, glossary, ADRs, full verification

**Files:**
- Modify: `docs/reference/glossary.md`, `docs/architecture/execution/edges/edges-arch.md`, `docs/architecture/execution/callbacks/callbacks-arch.md`, `docs/architecture/settings/settings-arch.md`, `docs/adr/0033-absence-is-a-type.md`, `docs/adr/0036-groups-execute-through-their-boundary-nodes.md`
- Create: `docs/adr/0039-propagation-mode-replaces-is-lazy.md`

- [ ] **Step 1: Glossary**

In `docs/reference/glossary.md`:

- **EdgeWrapper** row: replace `and the `is_lazy` flag` with `and its **Propagation**`.
- **CALLBACK port** row: replace the definition with: `A port used for event-style signalling; no hardcoded multiplicity rules, and **immediate** propagation (see **Propagation**). A callback edge carries the listener's subscription as the source port's *value* — whatever the callback type defines (the event name for core `CALLBACK`, a dataclass for visiongraph's `MULTIFRAME_CALLBACK`) — pooled on the emitter keyed by the edge. It may pass through **Reroute nodes**, which forward it on write; removing any edge on the path sets the next port to absence, which removes the emitter's entry. It cannot cross a Subgraph boundary yet. See [architecture/execution/callbacks](../architecture/execution/callbacks/callbacks-arch.md) and [ADR 0036](../adr/0036-groups-execute-through-their-boundary-nodes.md)`. Keep the avoid-column value.
- **Reroute node** row: replace from `Supports **DATA** and **CONTROL** edges.` through the end of that CALLBACK sentence with `Supports **DATA**, **CONTROL** and **CALLBACK** edges. On a callback edge the inlet is immediate, so `forward_immediate` copies each write to the outlet at once and the emitter downstream sees the subscription without any worker running.`
- Replace the **Eager push** and **Lazy pull** rows with one row: `| **Propagation** | When a value written to an outlet takes effect at the inlet across an edge: **lazy** (the inlet pulls the current value when its node executes), **eager** (pushed on write, takes effect when the inlet's node executes) or **immediate** (pushed on write and takes effect on write). Users choose lazy or eager per edge; **immediate** comes from the flow type (`CALLBACK`) and is locked, and an edge out of a promoted outlet is locked lazy. Eager and immediate both push — they differ in when the inlet acts on the value. See [ADR 0039](../adr/0039-propagation-mode-replaces-is-lazy.md) | Eager push / Lazy pull (now two of its values), immediate push |`
- Relationships bullet: replace `the Pipe's `is_lazy` flag comes from the **EdgeWrapper**, not the port` with `the Pipe's mode comes from the **EdgeWrapper**'s **Propagation**, not the port`.
- Example dialogue: replace `can be eager or lazy depending on whether you want immediate push or always-latest pull.` with `can be eager or lazy, depending on whether you want the value pushed on write or pulled, always-latest, when the node runs.`

- [ ] **Step 2: `edges-arch.md`**

- §1: replace `lazy flag)` with `propagation mode)`.
- §2.1 snippet: replace `lazy=False)` with `propagation=Propagation.EAGER)`.
- §2.2 diagram: replace `domain rules (e.g. callback source must be event node)` with `domain rules (none per edge today)`.
- §3.2: append the paragraph `**Unlink reset.** When an immediate inlet loses its active edge and no displaced edge takes over, the inlet is set to absence (`None`) and fires `on_change`, so a reroute passes the absence on (see [callbacks-arch §2.4](../callbacks/callbacks-arch.md)). A pooled inlet needs nothing extra: `_clear_link` already removed that source's entry.`
- §3.3: rename the heading to `### 3.3 Propagation and the unified dirty model`; replace the paragraph from `Edges support two propagation modes via` through `...for backward compatibility.` with:

```markdown
Each edge has a **propagation** mode (`Propagation`, per edge, not per port):

- **Eager** (default): outlet value is transformed through the adapter chain and pushed to the inlet immediately. The inlet is marked dirty; `on_change` is deferred to execution time.
- **Lazy**: no transform or push at propagation time. The inlet is marked dirty with a reference to the pipe. At execution time, `resolve_dirty_data()` pulls the outlet's *current* value (always-latest semantics) through the adapter chain.
- **Immediate**: pushed like eager, and the inlet acts on it at once (see the exception below).

Users choose lazy or eager per edge, and different edges to the same inlet can differ. `create_edge_wrapper(propagation=...)` stores the choice on the `Edge`, and `to_dict()` saves it under `propagation`. Two modes are locked and never read from a saved graph: `immediate` on an immediate flow, and `lazy` on an edge out of an `is_linked_lazy` outlet (every promoted outlet). `EdgeWrapper.locked_propagation` names the lock; `EdgeWrapper.propagation` is the mode in effect. See [ADR 0039](../../../adr/0039-propagation-mode-replaces-is-lazy.md).
```

  and replace the exception paragraph with `**Exception: immediate inlets fire at once.** An inlet on an immediate flow (`FlowType.is_immediate`, i.e. `CALLBACK`) is exempt from the deferral above — `set_value()` fires its `on_change` synchronously at push time even when `edge_id` is set, same as the widget/programmatic path.`
- §3.4 table: replace the row label `CALLBACK flow_type` with `Immediate flow (CALLBACK)`.
- §3.5 table: replace the `is_lazy` row's purpose with `Whether the edge's propagation is lazy, copied from the edge when the pipe is built`.
- Appendix: replace the `Edge.is_lazy` row with `| `Edge.propagation` | Chosen propagation mode (default `EAGER`); `EdgeWrapper.propagation` applies the locks |`; in Key files replace `(includes `is_lazy` flag)` with `(includes the chosen propagation)`.

- [ ] **Step 3: `callbacks-arch.md`**

- §2.1 "on_change timing": replace `CALLBACK-flow inlets are the one exception:` with `Immediate inlets — every CALLBACK flow (`FlowType.is_immediate`) — are the one exception:`.
- §2.1 paragraph ending `...(`PooledField.remove_source`). Assembly does not read callback edges to route anything — see §3.1.`: insert ` Longer paths are covered in §2.4.` after `(`PooledField.remove_source`).`.
- Add after §2.3:

```markdown
### 2.4 Through reroutes

A callback edge may pass through reroutes. Every port on a callback flow is **immediate**: an edge-driven write fires `on_change` at once, and a reroute's inlet forwards to its outlet from that handler (`RerouteNode.forward_immediate`), so the subscription reaches the emitter without any node executing. Callback edges always have `immediate` propagation, locked — see [edges-arch §3.3](../edges/edges-arch.md).

Removing any edge on the path unsubscribes. An immediate inlet left without a linked edge is set to absence (`None`), which the reroute forwards; the emitter's pooled inlet then removes the entry keyed by its own edge. A displaced edge that takes over keeps the subscription in place. Fields of immediate types hold absence whatever their storage, dataclass types included (ADR 0033, amendment).

Subgraph boundaries do not relay callbacks yet: collapsing a selection that a callback edge would cross is still refused.
```

- [ ] **Step 4: `settings-arch.md`**

In the "Freshness" paragraph replace `(1) a linked edge on an `is_linked_lazy` outlet is forced `is_lazy`,` with `(1) every linked edge on an `is_linked_lazy` outlet is locked to lazy propagation (`EdgeWrapper.locked_propagation`),`.

- [ ] **Step 5: ADR 0039**

Create `docs/adr/0039-propagation-mode-replaces-is-lazy.md`:

```markdown
---
name: propagation-mode-replaces-is-lazy
description: An edge's delivery timing is one Propagation mode — lazy, eager or immediate — replacing the is_lazy flag; immediate is locked by the flow type and a promoted outlet's edges are locked lazy
status: accepted
see-also: ADR-0014, ADR-0033, ADR-0036
level: architectural
---

# An edge's delivery timing is one Propagation mode, and some modes are locked

**Context.** An edge carried one flag, `is_lazy`, while the timing of a delivered value depended on more: whether the pipe pushes or pulls, whether the receiving port acts on the value at once (callback inlets did, through a cached `_is_callback`), and an override behind the user's back — edges out of a promoted outlet were forced lazy in `_refresh_pipes`, so switching one to eager in the menu was silently undone. Letting callbacks pass through reroutes added a case the flag could not express safely: a lazy edge into a reroute never delivers, because nothing on a callback path executes to pull it.

**Decision.** `Edge.is_lazy` becomes `Edge.propagation`, one of three `Propagation` values:

- **lazy** — the inlet pulls the outlet's current value when its node executes;
- **eager** — pushed on write, takes effect when the inlet's node executes;
- **immediate** — pushed on write and takes effect on write.

The fourth combination, pulled but acting at once, has no meaning, so one axis describes delivery completely.

Users choose lazy or eager. Two modes are **locked**, derived when asked and never read from a saved graph: `immediate` on an immediate flow (`FlowType.is_immediate`, only `CALLBACK` today), and `lazy` on an edge out of an `is_linked_lazy` outlet (every promoted outlet, ADR 0014). `EdgeWrapper.locked_propagation` names the lock; choosing `immediate`, or any mode on a locked edge, raises. Both edge panels show a locked mode read-only. A saved graph stores only the chosen mode, under `propagation`.

**Alternatives.** *Keep `is_lazy` and hide the toggle on callback edges* — smaller, but it adds a second silent override next to the promoted one, and EdgeKind would inherit a boolean that cannot name the callback case. *Let users choose `immediate` on DATA edges* — live updates, but `on_change` would fire on DATA nodes outside the scheduler frame, which is what ADR 0014 locks promoted outlets lazy to avoid.

**Consequences.**
- Saved graphs carry `propagation`; an older graph's `is_lazy` is ignored and its edges load eager. No migration.
- Farmhand `query_graph` detail reports `propagation` and `propagation_locked` instead of `is_lazy`.
- Copy/paste and Subgraph instantiation create edges eager, as they did before; locks apply to them as to any edge.
- EdgeKind can declare its allowed and locked modes per kind; a visual-only kind may allow none.
```

- [ ] **Step 6: Amendments to ADR 0033 and 0036**

Append to `docs/adr/0033-absence-is-a-type.md`:

```markdown

---

## Amendment — callback ports hold absence too (2026-09)

Immediate types (`FlowType.is_immediate`, today every `CALLBACK` flow) hold absence in their own fields, so an unlinked callback inlet can go absent and carry that to the emitter. `IType.create_field` gives such a type the absence-capable form of its field class (`absence_capable_field`), which covers `BaseField` storage as well as `PrimitiveField` — visiongraph's `MULTIFRAME_CALLBACK` is a dataclass. An absent `BaseField` value saves as `{"__absent__": true}`, since a dataclass may have a field named `value`. The restriction above still holds for wrappers: `OPTIONAL[T]` wraps only `PrimitiveField`-stored elements. A pooled field accepts absence when its element is immediate; absence from a source removes that source's entry.
```

Append to `docs/adr/0036-groups-execute-through-their-boundary-nodes.md`:

```markdown

---

## Amendment — reroutes carry callbacks (2026-09)

The reroute half of "a callback edge runs straight from its event node" is lifted. On a callback edge a reroute's inlet is immediate: the reroute forwards each write at once (`RerouteNode.forward_immediate`), and when its upstream edge is removed the inlet goes absent, so the emitter's pool drops its entry through its own edge instead of keeping a stale one. The structural rule that a callback edge's source is an event node is gone. The Subgraph-boundary half of this ADR's argument still holds: collapse keeps refusing callback crossings until boundary nodes get the same relay.
```

- [ ] **Step 7: Build the docs**

Run: `uv run mkdocs build --strict -d /tmp/site`
Expected: exactly one warning, the one that exists before this plan: `guides/panels.md` links to `../../.insights/project_surface_popup_emptiness_contract.md`. Any other warning is from this task — fix it.

- [ ] **Step 8: Commit the docs**

```bash
git add docs/
git commit -m "docs: Propagation, callbacks through reroutes, ADR 0039

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 9: Full verification**

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-marketplace/haybale_marketplace/ barn/haybale-share/haybale_share/ barn/haybale-graph-editor/haybale_graph_editor/ barn/haybale-haystack/haybale_haystack/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-TEST_A/haybale_test_a/ tests/
uv run pytest -m "not browser and not perf" -n 4 -q > /tmp/t.log 2>&1; echo "exit=$?"; grep -E "^FAILED|^ERROR" /tmp/t.log; grep -E "passed|failed" /tmp/t.log | tail -1
uv run pytest -m browser -n 4 -q > /tmp/b.log 2>&1; echo "exit=$?"; grep -E "^FAILED|^ERROR" /tmp/b.log; grep -E "passed|failed" /tmp/b.log | tail -1
(cd ../haybale-visiongraph && uv run pytest tests/ -q)
git status --short
```

Expected: ruff and mypy clean; both test tiers `exit=0` (the gate reports `2 xfailed` from `test_disconnect_semantics.py` plus the pre-existing 2 in `test_haystack_carve_out.py`); visiongraph tests pass; `git status` shows no uncommitted change under `barn/haybale-testing`. Report the pass/xfail counts. `OakDCameraNode.hb_on_callbacks_changed` now fires on edge-driven writes (Task 1): if a visiongraph test fails there, stop and report it rather than changing visiongraph.

---

## Self-review notes

- **Spec coverage:** 3A → Task 1; 5A → Task 6; 6A/6bA → Tasks 2-3; 7A → Task 7; 8A → Task 6; 9A superseded by 12A → Tasks 4-5; 11A scope → Global Constraints; menu split on callback edges → Task 6; glossary/ADR/doc list → Task 8; acceptance tests → Tasks 0, 6, 7.
- **Found while planning, fixed in Task 1:** `PooledType[CALLBACK]` inlets cached `_is_callback == False` (flow type set after `__post_init__`), so their `on_change` was deferred.
- **Behaviour kept as it was:** paste and Subgraph instantiation still create edges eager (they ignored `is_lazy` before).
