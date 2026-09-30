# Immediate Ports Return to Their Default (Edge Kinds, Step 2) Implementation Plan

**Superseded — 2026-09-28.** Do not execute. Step 2 became one unlink rule for every port (unlinking reveals the port's own value), so a reset for callback ports alone is replaced; see [2026-09-28-edge-kinds.md](2026-09-28-edge-kinds.md) step 2. The pooled rule (Task 1) and the fallback test node (Task 2) are expected to carry over into its plan.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** An immediate (callback) inlet left without an edge returns to its own default instead of `None`, and an emitter's pool drops an entry equal to its element type's default, so the author decides what is sent while nothing is connected.

**Architecture:** `DataPort._reset_if_unlinked` writes the port's own default (its declared `default`, else its type's) through `set_value`, so `on_change` fires and a reroute forwards it. `PooledField` of an immediate element removes a source's entry when that source sends `None` or the element type's default; a DATA pool keeps every value. A new `DataField.stores_per_source()` lets the port skip pooled inlets without core knowing about `PooledField`. With the default as the reset value, `BaseField` no longer needs absence storage, so that branch of `absence_capable_field` is removed.

**Tech Stack:** Python 3.12, pytest (+ xdist), uv, ruff, mypy, mkdocs.

**Builds on:** [landed/2026-09-27-callbacks-through-reroutes.md](landed/2026-09-27-callbacks-through-reroutes.md) (edge-kinds step 1, on branch `edge-kinds`). Place in the sequence: [2026-09-28-edge-kinds.md](2026-09-28-edge-kinds.md).

## Global Constraints

- Work on branch `edge-kinds`, before it is merged. Every commit message ends with `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- Out of scope: DATA and CONTROL ports (edge-kinds step 6), Subgraph boundaries (step 4), EdgeKind (step 5). A DATA pool must behave exactly as today.
- The reset value is the port's own default: `type_cls.create_field(default_override=port.default).get_value()`. Never `DataField.reset()`, which does not fire `on_change`.
- The pooled rule applies only to immediate elements (`FlowType.is_immediate`). `0.0` or `False` from a DATA source are real values.
- Glossary, ADR and architecture-doc edits happen only in Task 4, with the code.
- Docstrings and comments follow `.claude/rules/python-docs.md`; the class docstring of a registered node is displayed Markdown (single backticks, no reST).
- Node registry keys in tests come from `Cls.class_identity.registry_key`.
- Commit every change under `barn/haybale-testing/` before running the full suite (`tests/studio/test_docs/test_generate.py` reverts that directory).
- "Ruff check" means `uv run ruff check <path>` and `uv run ruff format --check <path>`; line length 109. Pre-commit gate: `uv run pytest -m "not browser and not perf" -n 4`.

---

## File Structure

| File | Responsibility | Tasks |
|---|---|---|
| `packages/haywire-core/src/haywire/core/types/fields.py` | `DataField.stores_per_source()` | 1 |
| `barn/haybale-core/haybale_core/types/pooled_type.py` | immediate pools drop `None` and the element default; `stores_per_source()` | 1 |
| `packages/haywire-core/src/haywire/core/types/port.py` | `_reset_if_unlinked` writes the port's own default | 2 |
| `packages/haywire-core/src/haywire/core/types/enums.py` | `FlowType.is_immediate` docstring | 2 |
| `barn/haybale-testing/haybale_testing/nodes/testbed/callback_fallback_node.py` (+ `nodes/__init__.py`) | relay test node with a declared fallback default | 2 |
| `packages/haywire-core/src/haywire/core/types/base.py` | `absence_capable_field` back to `PrimitiveField` only | 3 |
| `packages/haywire-core/src/haywire/core/types/interface.py` | `create_field` wraps only primitive-stored immediate types | 3 |
| `tests/core/test_types/test_immediate_absence.py`, `tests/core/test_edge/test_disconnect_semantics.py` | tests | 1-3 |
| docs (`glossary.md`, `callbacks-arch.md`, `edges-arch.md`, `datatype-canon.md`, ADRs 0033/0036, new 0040) | land with the code | 4 |

---

### Task 0: Baseline

- [ ] **Step 1: Confirm the branch and the acceptance state**

```bash
git branch --show-current
uv run pytest tests/core/test_edge/test_disconnect_semantics.py -q -p no:randomly
```

Expected: `edge-kinds`; `7 passed, 2 xfailed`.

- [ ] **Step 2: Baseline lint and types**

```bash
uv run ruff check packages/haywire-core/src/haywire/core/types barn/haybale-core barn/haybale-testing tests/core
uv run ruff format --check packages/haywire-core/src/haywire/core/types barn/haybale-core barn/haybale-testing tests/core
uv run mypy packages/haywire-core/src/ barn/haybale-core/haybale_core/ barn/haybale-testing/haybale_testing/ tests/
```

Expected: all clean. If not, stop and raise it with the user.

---

### Task 1: Immediate pools drop the element default

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/types/fields.py` (after `DataField.remove_source`, ~line 151)
- Modify: `barn/haybale-core/haybale_core/types/pooled_type.py` (`PooledField` fields, `__post_init__`, `set_value`, `accepts_absence`)
- Test: `tests/core/test_types/test_immediate_absence.py` (append to `TestPooledFields`)

**Interfaces:**
- Produces: `DataField.stores_per_source() -> bool` (default `False`; `PooledField` returns `True`); `PooledField.set_value(v, source_id)` removes the entry when the element is immediate and `v` is `None` or equals the element type's default.

- [ ] **Step 1: Write the failing tests**

Append to class `TestPooledFields` in `tests/core/test_types/test_immediate_absence.py`:

```python
    def test_the_element_default_from_a_source_removes_its_entry(self, library_system):
        from haybale_core.types import PooledType
        from haybale_testing.types import TEST_RECORD_CALLBACK

        pool = PooledType[TEST_RECORD_CALLBACK].create_field()
        pool.set_value(TEST_RECORD_CALLBACK(name="a", weight=1), source_id="e1")

        pool.set_value(TEST_RECORD_CALLBACK(), source_id="e1")

        assert pool.get_value() == {}

    def test_a_value_other_than_the_default_keeps_its_entry(self, library_system):
        from haybale_core.types import PooledType
        from haybale_testing.types import TEST_RECORD_CALLBACK

        pool = PooledType[TEST_RECORD_CALLBACK].create_field()

        pool.set_value(TEST_RECORD_CALLBACK(name="", weight=2), source_id="e1")

        assert pool.get_value() == {"e1": TEST_RECORD_CALLBACK(name="", weight=2)}

    def test_a_pooled_data_field_keeps_a_default_value(self, library_system):
        from haybale_core.types import PooledType
        from haywire.barn.builtin.types import FLOAT

        pool = PooledType[FLOAT].create_field()

        pool.set_value(0.0, source_id="e1")

        assert pool.get_value() == {"e1": 0.0}

    def test_only_a_pooled_field_stores_per_source(self, library_system):
        from haybale_core.types import CALLBACK, PooledType

        assert PooledType[CALLBACK].create_field().stores_per_source()
        assert not CALLBACK.create_field().stores_per_source()
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/core/test_types/test_immediate_absence.py::TestPooledFields -q -p no:randomly`
Expected: `test_the_element_default_from_a_source_removes_its_entry` FAILS (`{'e1': TEST_RECORD_CALLBACK(name='', weight=0)} == {}`), `test_only_a_pooled_field_stores_per_source` FAILS (`AttributeError: ... 'stores_per_source'`); the other new tests and the existing four PASS.

- [ ] **Step 3: `DataField.stores_per_source()`**

In `fields.py`, directly after

```python
    def remove_source(self, source_id: str) -> None:
        """Remove a disconnected source."""
        pass
```

add:

```python

    def stores_per_source(self) -> bool:
        """Whether this field keeps one value per source (``source_id``) instead of a single value.

        A field that does requires ``source_id`` in ``set_value`` and drops a
        source's value through ``remove_source``.
        """
        return False
```

- [ ] **Step 4: The pooled rule**

In `pooled_type.py` `PooledField`, replace

```python
    _sources: Dict[str, Any] = field(default_factory=dict, init=False, repr=False)
    _default_kwargs: Dict[str, Any] = field(default_factory=dict)
```

with

```python
    _sources: Dict[str, Any] = field(default_factory=dict, init=False, repr=False)
    _default_kwargs: Dict[str, Any] = field(default_factory=dict)
    _drops_default: bool = field(default=False, init=False, repr=False)
    _element_default: Any = field(default=None, init=False, repr=False)
```

At the end of `__post_init__`, after `self._sources = dict(initial_dict)`, add:

```python

        # An immediate element's default means "nothing from this source"; see set_value.
        element = getattr(self.type_cls, "element_type_cls", None)
        identity = getattr(element, "class_identity", None)
        self._drops_default = identity is not None and FlowType(identity.flow_type).is_immediate
        if self._drops_default:
            self._element_default = element.create_field().get_value()
```

In `set_value`, replace

```python
        For an immediate element (see ``accepts_absence``), ``None`` removes the source's entry.
        """
        if value is None and self.accepts_absence():
            # Absence from a source ends that source's entry; with no source there is nothing to end.
            if source_id is not None:
                self.remove_source(source_id)
            return
```

with

```python
        For an immediate element (see ``accepts_absence``), ``None`` or a value
        equal to the element type's default removes the source's entry: that
        default means "no subscription".
        """
        if self._drops_default and (value is None or value == self._element_default):
            # With no source there is no entry to end.
            if source_id is not None:
                self.remove_source(source_id)
            return
```

Replace the body of `accepts_absence` (keep its signature):

```python
    def accepts_absence(self) -> bool:
        """True when the pooled element is an immediate type; absence from a source then ends its entry."""
        return self._drops_default
```

Add after `remove_source`:

```python
    def stores_per_source(self) -> bool:
        """Always True: each source's value is kept under its own key."""
        return True
```

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/core/test_types/ tests/core/test_edge/ tests/core/test_graph/test_edges.py -q -p no:randomly -n 4`
Expected: PASS; `test_disconnect_semantics.py` still `7 passed, 2 xfailed`.

- [ ] **Step 6: Lint, types, commit**

```bash
uv run ruff check barn/haybale-core packages/haywire-core/src/haywire/core/types tests/core/test_types
uv run ruff format --check barn/haybale-core packages/haywire-core/src/haywire/core/types tests/core/test_types
uv run mypy barn/haybale-core/haybale_core/ packages/haywire-core/src/haywire/core/types/ tests/core/test_types/
git add packages/haywire-core/src/haywire/core/types/fields.py barn/haybale-core/haybale_core/types/pooled_type.py tests/core/test_types/test_immediate_absence.py
git commit -m "feat(pooled): an immediate pool drops a source that sends its element default

DataField.stores_per_source() names the fields that key values by source.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: An unlinked immediate inlet returns to its own default

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/types/port.py` (`_reset_if_unlinked`, ~lines 701-712)
- Modify: `packages/haywire-core/src/haywire/core/types/enums.py` (`FlowType.is_immediate` docstring)
- Create: `barn/haybale-testing/haybale_testing/nodes/testbed/callback_fallback_node.py`; modify `barn/haybale-testing/haybale_testing/nodes/__init__.py`
- Test: `tests/core/test_edge/test_disconnect_semantics.py` (append)

**Interfaces:**
- Consumes: `DataField.stores_per_source()`, the pooled rule (Task 1).
- Produces: `DataPort._reset_if_unlinked()` writes `type_cls.create_field(default_override=self.default).get_value()`; test node `TestCallbackFallbackNode` (CONTROL; inlet `subscription_in` `CALLBACK` default `"fallback"`, `on_change="forward"`; outlet `subscription_out` `CALLBACK` default `"fallback"`; attribute `received: list`).

- [ ] **Step 1: The fallback relay test node**

Create `barn/haybale-testing/haybale_testing/nodes/testbed/callback_fallback_node.py`:

```python
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode, NodeType


@node(
    label="Test Callback Fallback",
    description="Test relay that passes a callback subscription on, or `fallback` while nothing is connected",
    menu="testing/callbacks",
    search_tags=["test", "callback", "relay", "fallback"],
    node_type=NodeType.CONTROL,
)
class TestCallbackFallbackNode(BaseNode):
    """Test-only relay: forwards its `In` subscription to `Out`, and `fallback` while `In` is unconnected."""

    def init(self):
        from haybale_core.types import CALLBACK

        self.add(CALLBACK.as_inlet("subscription_in", label="In", default="fallback", on_change="forward"))
        self.add(CALLBACK.as_outlet("subscription_out", label="Out", default="fallback"))

    def post_init(self):
        self.received: list = []

    def forward(self, port, value) -> None:
        self.received.append(value)
        self.ports["subscription_out"].set_value(value)

    def worker(self, context: ExecutionContext) -> str | None:
        return None
```

In `nodes/__init__.py` add `from .testbed.callback_fallback_node import TestCallbackFallbackNode` (keep the imports sorted by module) and `"TestCallbackFallbackNode",` to `__all__` (sorted).

- [ ] **Step 2: Write the failing tests**

Append to `tests/core/test_edge/test_disconnect_semantics.py`:

```python
def _fallback_chain(graph):
    """Join an event node to an emit node through a callback relay whose inlet declares a fallback."""
    from haybale_testing.nodes.testbed.callback_fallback_node import TestCallbackFallbackNode
    from haybale_testing.nodes.testbed.custom_callback_node import TestCustomCallbackNode
    from haybale_testing.nodes.testbed.emit_callback_node import TestEmitCallbackNode

    event = graph.create_node_wrapper(TestCustomCallbackNode.class_identity.registry_key, position=(0, 0))
    relay = graph.create_node_wrapper(TestCallbackFallbackNode.class_identity.registry_key, position=(200, 0))
    emit = graph.create_node_wrapper(TestEmitCallbackNode.class_identity.registry_key, position=(400, 0))
    upstream = graph.create_edge_wrapper(event.node_id, "listen_callback", relay.node_id, "subscription_in")
    graph.create_edge_wrapper(relay.node_id, "subscription_out", emit.node_id, "edge_callback")
    return event, relay, emit, upstream


def test_an_unlinked_callback_inlet_returns_to_its_declared_default(
    graph_with_library_system, library_system
):
    graph = graph_with_library_system
    event, relay, _emit, upstream = _fallback_chain(graph)
    inlet = relay.node.ports["subscription_in"]
    assert inlet.get_value() == event.node.value("listen_callback")

    graph.remove_edge_wrapper(upstream.edge_id)

    assert inlet.get_value() == "fallback"
    assert relay.node.received[-1] == "fallback"


def test_a_declared_default_reaches_the_emitter(graph_with_library_system, library_system):
    graph = graph_with_library_system
    _event, _relay, emit, upstream = _fallback_chain(graph)

    graph.remove_edge_wrapper(upstream.edge_id)

    assert _subscriptions(emit) == ["fallback"]


def test_an_inlet_already_at_its_default_is_not_written_again(graph_with_library_system, library_system):
    graph = graph_with_library_system
    event, relay, _emit, upstream = _fallback_chain(graph)
    event.node.ports["listen_callback"].set_value("fallback")
    writes = len(relay.node.received)

    graph.remove_edge_wrapper(upstream.edge_id)

    assert len(relay.node.received) == writes
```

- [ ] **Step 3: Run to verify failure**

Run: `uv run pytest tests/core/test_edge/test_disconnect_semantics.py -q -p no:randomly`
Expected: the three new tests FAIL — the inlet holds `None` instead of `"fallback"`, the emitter's pool is empty, and the reset writes `None` a second time. The existing tests still report `7 passed, 2 xfailed`.

- [ ] **Step 4: Reset to the own default**

In `port.py`, replace the whole `_reset_if_unlinked` method with:

```python
    def _reset_if_unlinked(self) -> None:
        """Return an immediate inlet that no edge feeds any more to its own default.

        The default is the port's declared ``default``, else its type's. The
        write fires ``on_change`` like a widget write, so a reroute passes it
        on, and an emitter's pooled inlet drops an entry equal to its element
        type's default. An inlet already at its default is not written. A field
        that stores a value per source is left alone: unlinking already removed
        that source's value.
        """
        if not (self._is_inlet and self._is_immediate) or self._linked_edges:
            return
        if self._data.stores_per_source():
            return
        assert self.type_cls is not None  # __post_init__ enforces this
        default = self.type_cls.create_field(default_override=self.default).get_value()
        if self._data.get_value() != default:
            self.set_value(default)
```

In `enums.py` `FlowType.is_immediate`, replace `edge-driven writes too, a reroute forwards it at once, and it goes absent` / `when its last edge is removed.` with `edge-driven writes too, a reroute forwards it at once, and it returns to its` / `default when its last edge is removed.` (keep the docstring's line breaks under 109 characters).

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/core/test_edge/ tests/core/test_undo/ tests/core/test_types/ tests/core/test_graph/ -q -p no:randomly -n 4`
Expected: PASS; `test_disconnect_semantics.py` reports `10 passed, 2 xfailed`. `test_removing_the_edge_before_a_reroute_drops_a_dataclass_subscription` now passes through the pooled default rule (the reroute's inlet resets to `TEST_RECORD_CALLBACK()`).

- [ ] **Step 6: Lint, types, commit** (before any full-suite run: `barn/haybale-testing` changed)

```bash
uv run ruff check packages/haywire-core/src/haywire/core/types barn/haybale-testing tests/core
uv run ruff format --check packages/haywire-core/src/haywire/core/types barn/haybale-testing tests/core
uv run mypy packages/haywire-core/src/ barn/haybale-testing/haybale_testing/ tests/
git add packages/haywire-core/src/haywire/core/types/port.py packages/haywire-core/src/haywire/core/types/enums.py barn/haybale-testing/haybale_testing/nodes tests/core/test_edge/test_disconnect_semantics.py
git commit -m "feat(edges): an unlinked immediate inlet returns to its own default

The port's declared default, else its type's. A declared default is a
fallback subscription that reaches the emitter; the type default means
none and the emitter's pool drops it.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Absence storage only for primitive fields

With Task 2, a dataclass callback inlet resets to its default instance, so nothing puts `None` into a `BaseField` any more. Core `CALLBACK` still needs absence storage: its default is `None`, and its ports carry and save it.

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/types/base.py` (`_ABSENT_KEY` and `absence_capable_field`)
- Modify: `packages/haywire-core/src/haywire/core/types/interface.py` (`create_field` docstring and immediate branch)
- Test: `tests/core/test_types/test_immediate_absence.py` (module docstring, `TestDataclassCallbackField`)

**Interfaces:**
- Produces: `absence_capable_field(base_field_cls)` raises `TypeError` unless *base_field_cls* is a `PrimitiveField` subclass; `IType.create_field` applies it only to immediate types stored by a `PrimitiveField`.

- [ ] **Step 1: Update the tests**

In `tests/core/test_types/test_immediate_absence.py`, replace the module docstring with:

```python
"""Absence in immediate types: primitive fields hold ``None``; immediate pools drop a source on it."""
```

Replace the whole `class TestDataclassCallbackField:` block (from its `class` line through `test_a_present_value_still_saves_and_loads`) with:

```python
class TestDataclassCallbackField:
    def test_it_keeps_plain_storage(self, record_field):
        assert not record_field.accepts_absence()

    def test_a_present_value_is_still_type_checked(self, record_field):
        with pytest.raises(TypeError):
            record_field.set_value("not a record")

    def test_a_present_value_still_saves_and_loads(self, record_field):
        from haybale_testing.types import TEST_RECORD_CALLBACK

        record_field.set_value(TEST_RECORD_CALLBACK(name="tick", weight=3))
        restored = TEST_RECORD_CALLBACK.create_field()

        restored.from_dict(record_field.to_dict())

        assert restored.get_value() == TEST_RECORD_CALLBACK(name="tick", weight=3)

    def test_absence_needs_primitive_storage(self, library_system):
        from haywire.core.types import BaseField
        from haywire.core.types.base import absence_capable_field

        with pytest.raises(TypeError, match="PrimitiveField"):
            absence_capable_field(BaseField)
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/core/test_types/test_immediate_absence.py::TestDataclassCallbackField -q -p no:randomly`
Expected: `test_it_keeps_plain_storage` FAILS (`accepts_absence()` is True) and `test_absence_needs_primitive_storage` FAILS (`DID NOT RAISE`); the other two PASS.

- [ ] **Step 3: Primitive-only `absence_capable_field`**

In `base.py`, delete the `_ABSENT_KEY` constant with its two-line `#:` comment, and replace the whole `absence_capable_field` function (from `def absence_capable_field` through `return _AbsenceCapableField`) with:

```python
def absence_capable_field(base_field_cls: type) -> type:
    """Return a subclass of *base_field_cls* that can also hold ``None`` as absence.

    A present value keeps the base class's own storage, coercion included;
    ``None`` bypasses it and still fires the change event. Absence saves as
    ``{"value": None}`` and loads back. ``accepts_absence()`` answers ``True``,
    so ``Pipe.pull`` forwards absence into the field. Cached, so one base class
    yields one subclass.

    Raises:
        TypeError: If *base_field_cls* isn't a ``PrimitiveField`` subclass.
    """
    from .fields import PrimitiveField

    if not (isinstance(base_field_cls, type) and issubclass(base_field_cls, PrimitiveField)):
        name = getattr(base_field_cls, "__name__", base_field_cls)
        raise TypeError(f"absence needs PrimitiveField storage; {name} is not a PrimitiveField")

    cached = _ABSENCE_CAPABLE_FIELDS.get(base_field_cls)
    if cached is not None:
        return cached

    class _AbsenceCapableField(base_field_cls):  # type: ignore[valid-type,misc]
        """``base_field_cls``, plus the ability to hold absence."""

        def set_value(self, value: Any, source_id: "str | None" = None) -> None:
            if value is None:
                # Past the element's own set_value, whose coercion rejects None.
                PrimitiveField.set_value(self, None, source_id)
                return
            super().set_value(value, source_id)

        def to_dict(self) -> dict:
            if self.get_value() is None:
                return {"value": None}
            return super().to_dict()

        def from_dict(self, data: dict) -> None:
            if data.get("value") is None:
                self._value = None
                self.is_dirty = True
                return
            super().from_dict(data)

        def accepts_absence(self) -> bool:
            """Always True: this field class exists to hold ``None``."""
            return True

    _AbsenceCapableField.__name__ = f"AbsenceCapable{base_field_cls.__name__}"
    _AbsenceCapableField.__qualname__ = _AbsenceCapableField.__name__
    _ABSENCE_CAPABLE_FIELDS[base_field_cls] = _AbsenceCapableField
    return _AbsenceCapableField
```

- [ ] **Step 4: Wrap only primitive-stored immediate types**

In `interface.py` `create_field`, replace the docstring paragraph

```
        An immediate type (see ``FlowType.is_immediate``) gets the absence-capable
        form of its field class, so its ports can go absent.
```

with

```
        An immediate type (see ``FlowType.is_immediate``) stored by a
        ``PrimitiveField`` gets its absence-capable form, so its ports can
        carry and save ``None``.
```

and replace

```python
        if identity is not None and FlowType(identity.flow_type).is_immediate:
            from .base import absence_capable_field

            # An immediate port goes absent when its last edge is removed.
            field_cls = absence_capable_field(field_cls)
```

with

```python
        if identity is not None and FlowType(identity.flow_type).is_immediate:
            from .base import absence_capable_field
            from .fields import PrimitiveField

            # An immediate primitive type's default can be absence (core CALLBACK's is).
            if issubclass(field_cls, PrimitiveField):
                field_cls = absence_capable_field(field_cls)
```

- [ ] **Step 5: Check nothing refers to the removed key**

Run: `grep -rn "_ABSENT_KEY\|__absent__" --include="*.py" packages/ barn/ tests/`
Expected: no output.

- [ ] **Step 6: Run the tests**

Run: `uv run pytest tests/core/test_types/ tests/core/test_edge/ tests/core/test_settings/test_optional_setting.py tests/core/node/test_optional_promotion_connections.py tests/ui/widget/test_optional_widget.py -q -p no:randomly -n 4`
Expected: PASS; `test_disconnect_semantics.py` still `10 passed, 2 xfailed`.

- [ ] **Step 7: Lint, types, commit**

```bash
uv run ruff check packages/haywire-core/src/haywire/core/types tests/core/test_types
uv run ruff format --check packages/haywire-core/src/haywire/core/types tests/core/test_types
uv run mypy packages/haywire-core/src/haywire/core/types/ tests/core/test_types/
git add packages/haywire-core/src/haywire/core/types/base.py packages/haywire-core/src/haywire/core/types/interface.py tests/core/test_types/test_immediate_absence.py
git commit -m "refactor(types): absence storage only for primitive fields

A dataclass callback inlet resets to its default instance, so BaseField
needs no absence. Core CALLBACK keeps it: its default is None.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Docs, ADR 0040, full verification

**Files:**
- Modify: `docs/reference/glossary.md` (row **CALLBACK port**), `docs/architecture/execution/callbacks/callbacks-arch.md` (§2.4), `docs/architecture/execution/edges/edges-arch.md` (§3.2 "Unlink reset"), `docs/components/datatypes/datatype-canon.md` (§3 `flow_type` paragraph), `docs/adr/0033-absence-is-a-type.md` (2026-09 amendment), `docs/adr/0036-groups-execute-through-their-boundary-nodes.md` (2026-09 amendment)
- Create: `docs/adr/0040-immediate-ports-return-to-their-default.md`

- [ ] **Step 1: Glossary**

In the **CALLBACK port** row, replace `It may pass through **Reroute nodes**, which forward it on write; removing any edge on the path sets the next port to absence, which removes the emitter's entry.` with `It may pass through **Reroute nodes**, which forward it on write; removing any edge on the path returns the next port to its default — a default declared on the port is a fallback subscription, the type's default means none and removes the emitter's entry.`

- [ ] **Step 2: `callbacks-arch.md` §2.4**

Replace the paragraph starting `Removing any edge on the path unsubscribes.` with:

```markdown
Removing any edge on the path ends or replaces the subscription. An immediate inlet left without a linked edge returns to its own default, which the reroute forwards. A default declared on the port is a fallback subscription and reaches the emitter like any other; the type's default means "no subscription", and the emitter's pooled inlet removes the entry keyed by its own edge when it receives that default or `None`. A displaced edge that takes over keeps the subscription in place. See [ADR 0040](../../../adr/0040-immediate-ports-return-to-their-default.md).
```

- [ ] **Step 3: `edges-arch.md` §3.2**

In the **Unlink reset** paragraph, replace `the inlet is set to absence (`None`) and fires `on_change`, so a reroute passes the absence on` with `the inlet returns to its own default (the port's declared default, else its type's) and fires `on_change`, so a reroute passes it on`.

- [ ] **Step 4: `datatype-canon.md` — the author rule**

In the `flow_type` paragraph of §3, replace `` `CONTROL`/`CALLBACK` mark the type as a non-data signal — these get no widget and no meaningful default.`` with:

```markdown
`CONTROL`/`CALLBACK` mark the type as a non-data signal and get no widget. A `CALLBACK` type's default means "no subscription": an unlinked callback inlet returns to it, and an emitter drops a subscription equal to it, so never make it a real subscription. Core `CALLBACK`'s default is `None`; a dataclass callback type's default instance carries an empty name. To send a fallback subscription while an inlet is unconnected, declare a `default` on that port.
```

- [ ] **Step 5: ADR amendments**

In `0033-absence-is-a-type.md`, replace the paragraph under `## Amendment — callback ports hold absence too (2026-09)` with:

```markdown
Immediate types (`FlowType.is_immediate`, today every `CALLBACK` flow) stored by a `PrimitiveField` hold absence in their own fields: core `CALLBACK`'s default is absence, and an unlinked callback inlet returns to its default (ADR 0040), so its ports carry and save `None`. `IType.create_field` gives such a type the absence-capable form of its field class (`absence_capable_field`). The restriction above holds for both uses: absence needs `PrimitiveField` storage. A pooled field of an immediate element accepts absence; absence, or the element's default, from a source removes that source's entry.
```

In `0036-groups-execute-through-their-boundary-nodes.md`, in the paragraph under `## Amendment — reroutes carry callbacks (2026-09)`, replace `and when its upstream edge is removed the inlet goes absent, so` with `and when its upstream edge is removed the inlet returns to its default (ADR 0040), so`.

- [ ] **Step 6: ADR 0040**

Create `docs/adr/0040-immediate-ports-return-to-their-default.md`:

```markdown
---
name: immediate-ports-return-to-their-default
description: An immediate inlet left without an edge returns to its own default — the port's declared default, else its type's — and an immediate pool drops an entry equal to its element type's default, so an immediate type's default means "none"
status: accepted
see-also: ADR-0014, ADR-0033, ADR-0036, ADR-0039
level: architectural
---

# An unlinked immediate inlet returns to its default

**Context.** Callbacks can pass through reroutes (ADR 0036, amendment). When an edge on such a path is removed, the next immediate inlet has to tell the emitter that the subscription ended. The first cut reset that inlet to absence (`None`). It gave the node author no say in what is sent while nothing is connected, and it set immediate ports apart from the rule planned for every port — unlinking restores the port's own value, which is not built and needs ADR 0014 §C3 revisited. It also needed absence storage for dataclass callback types, which `BaseField` has nowhere else.

**Decision.**

- An immediate inlet left without a linked edge returns to its own default: the port's declared `default`, else its type's. The write fires `on_change`, so a reroute forwards it. An inlet already at its default is not written again. A field that stores a value per source (`DataField.stores_per_source()`: pooled inlets) is left alone, since unlinking already removed that source's value.
- A pooled field of an immediate element treats `None`, or a value equal to the element type's default, as "nothing from this source" and removes the source's entry. DATA pools are unchanged: `0.0` or `False` from a source are real values.
- So an immediate type's default means "no subscription", and a default declared on a port is a fallback subscription chosen by the node author, which reaches the emitter like any other.
- Absence storage stays for immediate primitive types, because core `CALLBACK`'s default is `None`; `BaseField` gets none.

**Alternatives.** *Reset to absence* — a value no subscription can collide with, but no author control and a rule of its own. *Pools ignore the default instead of removing the entry* — leaves exactly the stale subscription the reset exists to end.

**Consequences.**

- Authors of immediate types must never make the type's default a real subscription (see the datatype canon). Core `CALLBACK`'s default is `None`; haybale-visiongraph's `MULTIFRAME_CALLBACK` defaults to an empty name.
- The default is a value that also means "nothing" — the kind of sentinel ADR 0033 warns against. Here it is harmless: a subscription equal to the type default names no listener.
- If DATA ports come to restore their own value on unlink (ADR 0014 §C3 revisited), they follow the same rule, with the user's widget value as the own value.
```

- [ ] **Step 7: Regenerate the testing library docs**

Run: `uv run haywire docs barn/haybale-testing`
Expected: a new `haybale-testing.node.TestCallbackFallbackNode.md` and updated OVERVIEW/QUICKREF/README.

- [ ] **Step 8: Build the docs**

Run: `uv run mkdocs build --strict -d <scratchpad>/site`
Expected: exactly one warning, the pre-existing `guides/panels.md` link to `.insights/`.

- [ ] **Step 9: Commit the docs**

```bash
git add docs/ barn/haybale-testing
git commit -m "docs: immediate ports return to their default, ADR 0040

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 10: Full verification**

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-marketplace/haybale_marketplace/ barn/haybale-share/haybale_share/ barn/haybale-graph-editor/haybale_graph_editor/ barn/haybale-haystack/haybale_haystack/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-TEST_A/haybale_test_a/ tests/
uv run pytest -m "not browser and not perf" -n 4 -q > <scratchpad>/t.log 2>&1; echo "exit=$?"; grep -E "^FAILED|^ERROR" <scratchpad>/t.log; grep -E "passed|failed" <scratchpad>/t.log | tail -1
uv run pytest -m browser -n 4 -q > <scratchpad>/b.log 2>&1; echo "exit=$?"; grep -E "passed|failed" <scratchpad>/b.log | tail -1
(cd ../haybale-visiongraph && uv run pytest tests/ -q)
git status --short
```

Expected: ruff and mypy clean; both tiers `exit=0` (gate: `4 xfailed` — 2 in `test_disconnect_semantics.py`, 2 pre-existing in `test_haystack_carve_out.py`); visiongraph passes; clean tree. A run that hangs to the 120 s timeout is the known redraw/validation lock-order cycle (edge-kinds step 3), not this change: report it, do not retry it away.

---

## Self-review notes

- **Coverage:** reset to own default → Task 2; pooled drop only for immediate elements → Task 1 (with a DATA-pool guard test); reset through `set_value` so `on_change` fires → Task 2 Step 4; author rule → Task 4 Step 4 and ADR 0040; `BaseField` absence removed → Task 3.
- **Order:** Task 1 before Task 2, so the dataclass reroute test keeps passing when its reset value changes from `None` to the default instance. Task 3 after Task 2, once nothing writes `None` into a `BaseField`.
- **Unchanged on purpose:** the event node's outlet is never reset (outlets hold the upstream subscription); a pooled inlet is skipped by `stores_per_source()`.
