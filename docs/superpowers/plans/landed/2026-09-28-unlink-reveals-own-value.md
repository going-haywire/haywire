# Unlinking Reveals a Port's Own Value (Edge Kinds, Step 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every inlet shows its **linked value** while an edge feeds it and its **own value** otherwise, so removing an edge shows the user's value again — one rule for every port, edge kind and propagation mode, promoted settings included.

**Architecture:** `DataField` keeps the own value in its subclass storage and the linked value in a second instance of the same class; a write with a `source_id` (an edge) sets the linked value, any other write the own value. Field classes implement only `_get_own`/`_set_own`. When an inlet's last edge goes, the port drops the linked value and tells its node through its propagation mode. Only own values are saved; promoted settings read the shared field, so they follow the same rule. Callback defaults become ordinary values, so step 1's callback absence storage goes away.

**Tech Stack:** Python 3.12, NiceGUI (widgets), pytest (+ xdist), uv, ruff, mypy, mkdocs.

**Settled in:** the inquisition of 2026-09-28 (decisions Q1–Q9, 3bA, 4bA, 8bA). Sequence: [2026-09-28-edge-kinds.md](../2026-09-28-edge-kinds.md) step 2. Supersedes [2026-09-28-immediate-reset-to-default.md](../2026-09-28-immediate-reset-to-default.md).

## Global Constraints

- Work on branch `unlink-own-value`. Every commit message ends with `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- Decisions to honour: own/linked vocabulary (Q1); only the own value is saved, `StoreStrategy.WHEN_LINKED` removed (Q2); a widget on a linked inlet shows the linked value and refuses writes, the view snapping back, one widget kind (3bA); a multi-link inlet keeps its linked value until its last edge goes (Q4) and DATA inlets are single-link unless pooled (4bA); a removed edge's pending lazy pull is dropped (Q5); promotion marks nothing locally set (Q6); the field event fires on any stored change with the effective value, the node's `on_change` only when the value the node sees changes (Q7); `CALLBACK`'s default is `""`, no callback absence storage, an immediate pool drops an entry equal to its element's default (Q8); `@type` rejects a primitive type with no usable default (8bA); the linked value lives in the `DataField` base (Q9).
- Out of scope: outlets and config ports (never linked), Subgraph boundaries (edge-kinds step 4), EdgeKind (step 5), an explicit "override the linked value" action (an idea, not built).
- Breaking changes are allowed; no migration of saved graphs.
- Glossary, ADR and architecture-doc edits happen only in Task 9, with the code.
- Docstrings and comments follow `.claude/rules/python-docs.md`; class docstrings of registered components (types, widgets, nodes) are displayed Markdown (single backticks, no reST).
- Node registry keys in tests come from `Cls.class_identity.registry_key`.
- Commit every change under `barn/haybale-testing/` before running the full suite (`tests/studio/test_docs/test_generate.py` reverts that directory).
- "Ruff check" means `uv run ruff check <path>` and `uv run ruff format --check <path>`; line length 109. Pre-commit gate: `uv run pytest -m "not browser and not perf" -n 4`.
- A test failing outside the files a task names means it depends on freeze-on-disconnect somewhere unexpected: stop and report it by name; do not rewrite it on the spot.

---

## File Structure

| File | Responsibility | Tasks |
|---|---|---|
| `packages/haywire-core/src/haywire/core/types/fields.py` | own/linked values in `DataField`; `PrimitiveField`/`BaseField` hooks | 1 |
| `packages/haywire-core/src/haywire/barn/builtin/types/specs.py` | `INTField`/`FLOATField` hooks | 1, 7 |
| `packages/haywire-core/src/haywire/barn/builtin/types/add.py` | `ADDField` hooks | 1 |
| `barn/haybale-core/haybale_core/types/array_type.py`, `pooled_type.py` | `ArrayField`/`PooledField` hooks; pool drops the element default | 1, 7 |
| `barn/haybale-core/haybale_core/types/specs.py` | `CALLBACK` default `""` | 7 |
| `barn/haybale-example/haybale_example/types/maps_string_type.py` | `MapsStringField` hooks | 1 |
| `barn/haybale-testing/haybale_testing/types/test_types.py` | `TEST_INTField`/`TEST_FLOATField` hooks | 1 |
| `packages/haywire-core/src/haywire/core/types/base.py` | absence storage back to `OPTIONAL` only | 1, 7 |
| `packages/haywire-core/src/haywire/core/types/interface.py` | `create_field` without callback wrapping; `StoreStrategy` docstrings | 4, 7 |
| `packages/haywire-core/src/haywire/core/types/port.py` | reveal on unlink, own writes while linked, pending lazy pulls, DATA inlet arity, save call | 1–4 |
| `packages/haywire-core/src/haywire/core/types/pipe.py` | `Pipe.edge_id` | 2 |
| `packages/haywire-core/src/haywire/core/edge/edge_wrapper.py` | reveal call in `unlink`/`detach` | 2 |
| `packages/haywire-core/src/haywire/core/types/enums.py` | `StoreStrategy` without `WHEN_LINKED`; `FlowType.is_immediate` docstring | 4, 7 |
| `packages/haywire-core/src/haywire/core/settings/settings.py`, `descriptor.py` | own value for save, reset and the write guard | 5 |
| `packages/haywire-core/src/haywire/core/node/promotion.py` | no promote-time mark; demote drops the linked value | 5 |
| `packages/haywire-core/src/haywire/ui/widget/base.py`, `binding.py` | widgets refuse writes while linked | 6 |
| `packages/haywire-core/src/haywire/core/types/decorator.py` | primitive default check | 8 |
| docs (`glossary.md`, `settings-arch.md`, `setting-canon.md`, `edges-arch.md`, `callbacks-arch.md`, `datatype-canon.md`, ADRs 0014/0033/0036, new 0040, the edge-kinds overview) | land with the code | 9 |

---

### Task 0: Baseline

- [ ] **Step 1: Branch and tree**

```bash
git branch --show-current
git status --short
```

Expected: `unlink-own-value`; empty status.

- [ ] **Step 2: Lint and types for the areas this plan touches**

```bash
uv run ruff check packages/haywire-core/src/haywire barn/haybale-core barn/haybale-example barn/haybale-testing tests/core tests/ui
uv run ruff format --check packages/haywire-core/src/haywire barn/haybale-core barn/haybale-example barn/haybale-testing tests/core tests/ui
uv run mypy packages/haywire-core/src/ barn/haybale-core/haybale_core/ barn/haybale-example/haybale_example/ barn/haybale-testing/haybale_testing/ tests/
```

Expected: clean. Otherwise stop and raise it with the user.

- [ ] **Step 3: Acceptance state**

Run: `uv run pytest tests/core/test_edge/test_disconnect_semantics.py -q -p no:randomly`
Expected: `7 passed, 2 xfailed`.

- [ ] **Step 4: Benchmark baseline** (clean tree required)

Run: `uv run python benchmarks/run.py`
Expected: a table of cases (`graph_loop`, `node_execute_bare`, …). Note each case's `min`. The runner appended rows to `benchmarks/results/results.jsonl`.

- [ ] **Step 5: Commit the baseline rows**

```bash
git add benchmarks/results/results.jsonl
git commit -m "bench: baseline before unlinking reveals the own value

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 1: Two values in the field

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/types/fields.py` (`DataField` docstring, `__post_init__`, core API at 71-99; `PrimitiveField.get_value`/`set_value` at 244-263; `BaseField.get_value`/`set_value` at 332-346)
- Modify: `packages/haywire-core/src/haywire/barn/builtin/types/specs.py` (`INTField.set_value`, `FLOATField.set_value`)
- Modify: `packages/haywire-core/src/haywire/barn/builtin/types/add.py` (`ADDField.get_value`/`set_value`)
- Modify: `barn/haybale-core/haybale_core/types/array_type.py` (`ArrayField.get_value`/`set_value`)
- Modify: `barn/haybale-core/haybale_core/types/pooled_type.py` (new `_get_own`/`_set_own`)
- Modify: `barn/haybale-example/haybale_example/types/maps_string_type.py` (`MapsStringField.get_value`/`set_value`)
- Modify: `barn/haybale-testing/haybale_testing/types/test_types.py` (`TEST_INTField.set_value`, `TEST_FLOATField.set_value`)
- Modify: `packages/haywire-core/src/haywire/core/types/base.py` (`absence_capable_field`'s inner `set_value` and `to_dict`)
- Modify: `packages/haywire-core/src/haywire/core/types/port.py` (`_reset_if_unlinked`)
- Test: `tests/core/test_types/test_own_and_linked_value.py` (create)

**Interfaces:**
- Produces: `DataField.get_value()` (linked value while linked, else own), `DataField.get_own_value()`, `DataField.set_value(value, source_id=None)` (a `source_id` sets the linked value), `DataField.has_linked_value() -> bool`, `DataField.clear_linked() -> None`; abstract hooks `DataField._get_own() -> T | None` and `DataField._set_own(value) -> None` (check, coerce and store the own value, fire nothing). `PooledField` keeps its own public `get_value`/`set_value` and never holds a linked value.

- [ ] **Step 1: Write the failing tests**

Create `tests/core/test_types/test_own_and_linked_value.py`:

```python
"""A field keeps its own value and, while an edge feeds it, the linked value in front of it."""

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture
def float_field(library_system):
    from haywire.barn.builtin.types import FLOAT

    return FLOAT.create_field()


class TestTwoValues:
    def test_a_write_without_a_source_is_the_own_value(self, float_field):
        float_field.set_value(7.0)

        assert float_field.get_value() == 7.0
        assert float_field.get_own_value() == 7.0
        assert not float_field.has_linked_value()

    def test_a_write_with_a_source_stands_in_front_of_the_own_value(self, float_field):
        float_field.set_value(7.0)

        float_field.set_value(42.0, source_id="e1")

        assert float_field.has_linked_value()
        assert float_field.get_value() == 42.0
        assert float_field.get_own_value() == 7.0

    def test_an_own_write_while_linked_changes_only_the_own_value(self, float_field):
        float_field.set_value(42.0, source_id="e1")

        float_field.set_value(5.0)

        assert float_field.get_value() == 42.0
        assert float_field.get_own_value() == 5.0

    def test_clearing_the_linked_value_reveals_the_own_value(self, float_field):
        float_field.set_value(7.0)
        float_field.set_value(42.0, source_id="e1")

        float_field.clear_linked()

        assert not float_field.has_linked_value()
        assert float_field.get_value() == 7.0

    def test_clearing_without_a_linked_value_changes_nothing(self, float_field):
        float_field.set_value(7.0)

        float_field.clear_linked()

        assert float_field.get_value() == 7.0

    def test_only_the_own_value_is_saved(self, float_field):
        float_field.set_value(7.0)
        float_field.set_value(42.0, source_id="e1")

        assert float_field.to_dict() == {"value": 7.0}


class TestEvents:
    def test_every_change_fires_with_the_value_get_value_returns(self, float_field):
        seen: list = []
        float_field.add_observer(lambda change: seen.append((change.old, change.value)))

        float_field.set_value(7.0)
        float_field.set_value(42.0, source_id="e1")
        float_field.set_value(5.0)
        float_field.clear_linked()

        assert seen == [(0.0, 7.0), (7.0, 42.0), (42.0, 42.0), (42.0, 5.0)]


class TestTheFieldChecksBothValues:
    def test_a_linked_value_is_coerced_like_an_own_one(self, library_system):
        from haywire.barn.builtin.types import INT

        field = INT.create_field()

        field.set_value(3.7, source_id="e1")

        assert field.get_value() == 3

    def test_a_rejected_linked_value_leaves_no_linked_value_behind(self, library_system):
        from haybale_core.types import ArrayType
        from haywire.barn.builtin.types import FLOAT

        field = ArrayType[FLOAT].create_field()

        with pytest.raises(TypeError):
            field.set_value("not a list", source_id="e1")
        assert not field.has_linked_value()


class TestPooledFieldsKeepTheirShape:
    def test_a_pooled_field_never_holds_a_linked_value(self, library_system):
        from haybale_core.types import PooledType
        from haywire.barn.builtin.types import FLOAT

        pool = PooledType[FLOAT].create_field()

        pool.set_value(1.0, source_id="e1")

        assert not pool.has_linked_value()
        assert pool.get_value() == {"e1": 1.0}
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/core/test_types/test_own_and_linked_value.py -q -p no:randomly`
Expected: FAIL — `AttributeError: ... 'get_own_value'` / `'has_linked_value'` / `'clear_linked'`; `test_a_linked_value_is_coerced_like_an_own_one` PASSES already.

- [ ] **Step 3: `DataField` — the two values**

In `fields.py`, in the `DataField` class docstring, insert after the line `Each IType declares which DataField class handles its storage.`:

```
    A field holds its **own value** — written by a widget, the node or a
    setting, and the value that is saved — and, while an edge feeds it, the
    **linked value** that edge delivered. ``get_value()`` returns the linked
    value while there is one, else the own value. A subclass stores the own
    value only, through ``_get_own``/``_set_own``; the linked value lives in a
    second instance of the same class, so it gets the same checks and
    coercion.
```

At the end of `DataField.__post_init__`, after `self.field_id: str = ""`, add:

```python
        # The value an edge delivered, in a field of this class; None while nothing feeds it.
        self._linked_slot: DataField[T] | None = None
```

Replace the two abstract methods `get_value` and `set_value` (from `    @abstractmethod\n    def get_value(self) -> T | None:` through the `set_value` docstring's closing `pass`) with:

```python
    def get_value(self) -> T | None:
        """Return the linked value while an edge feeds this field, else the own value.

        Returns data in its most convenient form:
        - PrimitiveField: unwrapped primitive (42.0), or None if no default was
          registered and no value has been set yet.
        - BaseField: BaseType instance (MeshData(...))
        - CompoundField: container (dict, list, etc.)
        """
        slot = self._linked_slot
        if slot is not None:
            return slot._get_own()
        return self._get_own()

    def get_own_value(self) -> T | None:
        """Return the own value, whether or not an edge's value stands in front of it."""
        return self._get_own()

    def set_value(self, value: Any, source_id: str | None = None) -> None:
        """Store *value* and fire ``on_changed`` with what ``get_value()`` returns before and after.

        Args:
            value: IType instance or raw value, checked and coerced by the field.
            source_id: The id of the edge delivering *value*, which stores it as
                the linked value; ``None`` stores the own value.

        Raises:
            TypeError: If the field rejects *value*.
        """
        observed = self.on_changed.has_observers()
        old = self.get_value() if observed else None
        if source_id is None:
            self._set_own(value)
        else:
            # `is None`, not `or`: an empty ArrayField is falsy.
            slot = self._linked_slot
            if slot is None:
                slot = self._new_linked_slot()
            slot._set_own(value)
            self._linked_slot = slot
        self.is_dirty = True
        if observed:
            self.fire(self.get_value(), old)

    def has_linked_value(self) -> bool:
        """True while an edge's value stands in front of the own value."""
        return self._linked_slot is not None

    def clear_linked(self) -> None:
        """Drop the linked value so ``get_value()`` returns the own value again; no-op without one.

        Fires ``on_changed`` with the own value.
        """
        slot = self._linked_slot
        if slot is None:
            return
        self._linked_slot = None
        self.is_dirty = True
        if self.on_changed.has_observers():
            self.fire(self._get_own(), slot._get_own())

    def _new_linked_slot(self) -> "DataField[T]":
        """Return an empty field of this class to hold a linked value."""
        return type(self)(type_cls=self.type_cls, default_kwargs=self.default_kwargs)

    @abstractmethod
    def _get_own(self) -> T | None:
        """Return the own value in its access form (see ``get_value``)."""

    @abstractmethod
    def _set_own(self, value: Any) -> None:
        """Check, coerce and store *value* as the own value, firing nothing.

        Raises:
            TypeError: If *value* cannot be stored in this field.
        """
```

- [ ] **Step 4: `PrimitiveField` and `BaseField` hooks**

In `PrimitiveField`, replace `get_value` and `set_value` (from `    def get_value(self) -> T | None:\n        """Get unwrapped primitive` through `            self.fire(self._value, old)`) with:

```python
    def _get_own(self) -> T | None:
        """Return the unwrapped primitive — O(1) direct access. None when unset."""
        return self._value

    def _set_own(self, value: Any) -> None:
        """Store the primitive as given; a subclass coerces first (see ``INTField``)."""
        self._value = value
```

In `BaseField`, replace `get_value` and `set_value` (from `    def get_value(self) -> BaseType:` through `            self.fire(self._container, old)`) with:

```python
    def _get_own(self) -> BaseType:
        """Return the instance."""
        return self._container

    def _set_own(self, value: Any) -> None:
        """Store a BaseType instance.

        Raises:
            TypeError: If *value* is not an instance of the field's type.
        """
        if not isinstance(value, self.type_cls):
            raise TypeError(f"Expected {self.type_cls.__name__}, got {type(value).__name__}")
        # type_cls is type[IType] at the base; for BaseField it's always type[BaseType].
        self._container = cast(BaseType, value)
```

- [ ] **Step 5: The other field classes**

`packages/haywire-core/src/haywire/barn/builtin/types/specs.py` — in `INTField` replace

```python
    def set_value(self, value, source_id=None):
        value = int(value)
        return super().set_value(value, source_id)
```

with

```python
    def _set_own(self, value):
        super()._set_own(int(value))
```

and in `FLOATField` the same block with `float` for `int`. Do the same in `barn/haybale-testing/haybale_testing/types/test_types.py` for `TEST_INTField` (`int`) and `TEST_FLOATField` (`float`).

`packages/haywire-core/src/haywire/barn/builtin/types/add.py` — in `ADDField` replace

```python
    def get_value(self) -> AnyValue:
        return None

    def set_value(self, value: AnyValue, source_id: "str | None" = None) -> None:
        """Ignore the write; an ``ADD`` pin is replaced before values flow."""
        return None
```

with

```python
    def _get_own(self) -> AnyValue:
        return None

    def _set_own(self, value: AnyValue) -> None:
        """Ignore the write; an ``ADD`` pin is replaced before values flow."""
        return None
```

`barn/haybale-core/haybale_core/types/array_type.py` — replace `ArrayField.get_value` and `ArrayField.set_value` (from `    def get_value(self) -> List[Any]:` through `            self.fire(list(self._items), old)`) with:

```python
    def _get_own(self) -> List[Any]:
        """Return a copy of the list, e.g. ``[42.0, 3.14]`` or ``[MeshData(...)]``."""
        return list(self._items)

    def _set_own(self, value: Any) -> None:
        """Store a list, e.g. ``[1.0, 2.0, 3.0]``.

        Raises:
            TypeError: If *value* is not a list.
        """
        if not isinstance(value, list):
            raise TypeError(f"ArrayField requires list, got {value.__class__.__name__}")
        self._items = value
```

`barn/haybale-example/haybale_example/types/maps_string_type.py` — replace `MapsStringField.get_value` and `MapsStringField.set_value` (from `    def get_value(self) -> Dict[str, Any]:` through `            self.fire(dict(self._items), old)`) with:

```python
    def _get_own(self) -> Dict[str, Any]:
        """Return a copy of the map."""
        return dict(self._items)

    def _set_own(self, value: Any) -> None:
        """Store a string-keyed map.

        Raises:
            TypeError: If *value* is not a dict.
        """
        if not isinstance(value, dict):
            raise TypeError(f"MapsStringField requires dict, got {value.__class__.__name__}")
        self._items = value
```

`barn/haybale-core/haybale_core/types/pooled_type.py` — `PooledField` keeps its own `get_value`/`set_value`. Add after `get_stored_type`:

```python
    def _get_own(self) -> Dict[str, Any]:
        """Return a copy of the per-source values; a pooled field has no value besides them."""
        return dict(self._sources)

    def _set_own(self, value: Any) -> None:
        """Refuse a write without a source.

        Raises:
            ValueError: Always; every pooled write names its source.
        """
        raise ValueError("PooledField requires source_id")
```

- [ ] **Step 6: Keep step 1's callback absence working**

In `packages/haywire-core/src/haywire/core/types/base.py`, inside `absence_capable_field`, replace the inner

```python
        def set_value(self, value: Any, source_id: "str | None" = None) -> None:
            if value is not None:
                super().set_value(value, source_id)
            elif stores_instances:
                # Past BaseField.set_value, whose isinstance check rejects None.
                old: Any = self._container  # type: ignore[has-type]
                self._container = None
                self.is_dirty = True
                if self.on_changed.has_observers():
                    self.fire(None, old)
            else:
                # Past the element's own set_value, whose coercion rejects None.
                PrimitiveField.set_value(self, None, source_id)

        def to_dict(self) -> dict:
            if self.get_value() is not None:
```

with

```python
        def _set_own(self, value: Any) -> None:
            if value is not None:
                super()._set_own(value)
            elif stores_instances:
                # Past BaseField._set_own, whose isinstance check rejects None.
                self._container = None
            else:
                # Past the element's own _set_own, whose coercion rejects None.
                PrimitiveField._set_own(self, None)

        def to_dict(self) -> dict:
            if self._get_own() is not None:
```

In `port.py` `_reset_if_unlinked`, replace

```python
        if self._data.has_data():
            self.set_value(None)
```

with

```python
        if self._data.has_linked_value():
            self._data.clear_linked()
            self.set_value(None)
```

(Task 2 replaces this method; Task 7 removes the absence code.)

- [ ] **Step 7: Check no field still overrides the old public methods**

Run: `grep -rn "def set_value\|def get_value" --include="*.py" packages/haywire-core/src/haywire/core/types/fields.py packages/haywire-core/src/haywire/core/types/base.py packages/haywire-core/src/haywire/barn/builtin/types/ barn/haybale-core/haybale_core/types/ barn/haybale-example/haybale_example/types/ barn/haybale-testing/haybale_testing/types/`
Expected: only `fields.py` (the two `DataField` methods) and `pooled_type.py` (its own `get_value`/`set_value`).

- [ ] **Step 8: Run the tests**

Run: `uv run pytest tests/core tests/ui/widget tests/barn -m "not browser and not perf" -n 4 -q -p no:randomly`
Expected: PASS; `test_disconnect_semantics.py` still `7 passed, 2 xfailed`.

- [ ] **Step 9: Lint, types, commit** (commit before any full-suite run: `barn/haybale-testing` changed)

```bash
uv run ruff check packages/haywire-core/src/haywire barn/haybale-core barn/haybale-example barn/haybale-testing tests/core/test_types
uv run ruff format --check packages/haywire-core/src/haywire barn/haybale-core barn/haybale-example barn/haybale-testing tests/core/test_types
uv run mypy packages/haywire-core/src/ barn/haybale-core/haybale_core/ barn/haybale-example/haybale_example/ barn/haybale-testing/haybale_testing/ tests/core/test_types/
git add -A packages/haywire-core/src/haywire barn/haybale-core barn/haybale-example barn/haybale-testing tests/core/test_types/test_own_and_linked_value.py
git commit -m "feat(types): a field keeps its own value and a linked value

An edge's write (with a source_id) sets the linked value, shown by
get_value() while it lasts; every other write sets the own value, which
is what is saved. Field classes implement _get_own/_set_own; the base
keeps the linked value in a second instance of the same class.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Unlinking reveals the own value

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/types/port.py` (`set_value` inlet branch, `_clear_link`, `_reset_if_unlinked` → `_reveal_own_value_if_unlinked`, new module helper `_same_value`)
- Modify: `packages/haywire-core/src/haywire/core/types/pipe.py` (`Pipe.edge_id`)
- Modify: `packages/haywire-core/src/haywire/core/edge/edge_wrapper.py` (`unlink`, `detach`)
- Modify: `tests/core/test_edge/test_disconnect_semantics.py` (remove the first xfail marker)
- Test: `tests/core/test_edge/test_unlink_reveals_own_value.py` (create)

**Interfaces:**
- Consumes: `DataField.has_linked_value()`, `clear_linked()` (Task 1).
- Produces: `DataPort._reveal_own_value_if_unlinked() -> None`; `Pipe.edge_id -> str`; an own write to a linked inlet fires no `on_change` and marks nothing dirty.

- [ ] **Step 1: Write the failing tests**

Create `tests/core/test_edge/test_unlink_reveals_own_value.py`:

```python
"""Removing an inlet's last edge shows its own value, and the node hears of it through its propagation."""

from typing import Any, cast

import pytest

from haywire.barn.builtin.types import FLOAT
from haywire.core.types import DataPort, FlowType, PortType, Propagation


@pytest.fixture
def linked_pair(graph_with_library_system, library_system):
    """Two Adds joined by an eager data edge; the sink's own value is 7.0 and the edge delivered 42.0."""
    from haybale_testing.nodes.testbed.math_op_node import TestAddFloatNode

    graph = graph_with_library_system
    key = TestAddFloatNode.class_identity.registry_key
    source = graph.create_node_wrapper(key, position=(0, 0))
    sink = graph.create_node_wrapper(key, position=(300, 0))
    inlet = sink.node.ports["value_a"]
    inlet.set_value(7.0)
    edge = graph.create_edge_wrapper(source.node_id, "result", sink.node_id, "value_a")
    source.node.out("result", 42.0)
    assert inlet.get_value() == 42.0
    return graph, source, sink, edge


@pytest.mark.integration
class TestUnlinking:
    def test_the_own_value_shows_and_the_node_is_marked(self, linked_pair):
        graph, _source, sink, edge = linked_pair
        sink.node._has_dirty_ports.clear()

        graph.remove_edge_wrapper(edge.edge_id)

        assert sink.node.ports["value_a"].get_value() == 7.0
        assert "value_a" in sink.node._has_dirty_ports

    def test_an_own_write_while_linked_shows_after_unlinking(self, linked_pair):
        graph, _source, sink, edge = linked_pair
        inlet = sink.node.ports["value_a"]

        inlet.set_value(5.0)

        assert inlet.get_value() == 42.0
        graph.remove_edge_wrapper(edge.edge_id)
        assert inlet.get_value() == 5.0

    def test_an_own_write_while_linked_does_not_mark_the_node(self, linked_pair):
        _graph, _source, sink, _edge = linked_pair
        sink.node._has_dirty_ports.clear()

        sink.node.ports["value_a"].set_value(5.0)

        assert "value_a" not in sink.node._has_dirty_ports

    def test_a_pending_lazy_pull_is_dropped_with_its_edge(self, linked_pair):
        graph, source, sink, edge = linked_pair
        edge.propagation = Propagation.LAZY
        inlet = sink.node.ports["value_a"]
        source.node.out("result", 99.0)
        assert len(inlet._pending_lazy_pipes) == 1

        graph.remove_edge_wrapper(edge.edge_id)
        inlet.resolve_dirty_data()

        assert inlet._pending_lazy_pipes == set()
        assert inlet.get_value() == 7.0


def _inlet() -> DataPort:
    return DataPort(
        registry_id="float",
        registry_key="haybale_core:type:float",
        label="F",
        id="v",
        type_cls=FLOAT,
        port_type=PortType.INLET,
        flow_type=FlowType.DATA,
    )


@pytest.mark.unit
def test_an_inlet_fed_by_two_edges_keeps_the_linked_value_until_the_last_goes():
    port = _inlet()
    port.allow_multiple_links = True
    port.set_value(1.0)
    port._linked_edges["a"] = cast(Any, object())
    port._linked_edges["b"] = cast(Any, object())
    port.set_value(9.0, edge_id="a")

    port._linked_edges.pop("a")
    port._reveal_own_value_if_unlinked()
    assert port.get_value() == 9.0

    port._linked_edges.pop("b")
    port._reveal_own_value_if_unlinked()
    assert port.get_value() == 1.0
```

In `tests/core/test_edge/test_disconnect_semantics.py`, delete the decorator above `test_unlinked_inlet_shows_the_value_it_had_before_linking`:

```python
@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="unlinking keeps the last edge-driven value (ADR 0014 §C3, freeze-on-disconnect)",
)
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/core/test_edge/test_unlink_reveals_own_value.py tests/core/test_edge/test_disconnect_semantics.py -q -p no:randomly`
Expected: FAIL — the inlet still shows 42.0 after unlinking; the own write marks the node; the lazy pull delivers 99.0; `AttributeError: ... '_reveal_own_value_if_unlinked'`; `test_unlinked_inlet_shows_the_value_it_had_before_linking` fails (`42.0 == 7.0`).

- [ ] **Step 3: `Pipe.edge_id`**

In `pipe.py` `class Pipe`, add after `__init__`:

```python
    @property
    def edge_id(self) -> str:
        """The id of the edge this pipe carries."""
        return self._edge_id
```

- [ ] **Step 4: Own writes while linked**

In `port.py` `set_value`, in the docstring replace

```
        For inlets:
        - fire immediately with on_change when
```

with

```
        For inlets:
        - an own write (no edge_id) while an edge feeds the inlet changes only
          the own value: no on_change, no dirty mark
        - fire immediately with on_change when
```

and in the inlet branch, directly after `self._is_set_by_node = False`, insert:

```python
            if edge_id is None and self._data.has_linked_value():
                # The own value changed behind the linked one; the node sees no change.
                return
```

- [ ] **Step 5: Drop a removed edge's pending lazy pull**

In `_clear_link`, after `self._data.remove_source(wrapper_uuid)`, insert:

```python
            # A lazy pull still queued for this edge would deliver after it is gone.
            self._pending_lazy_pipes = {p for p in self._pending_lazy_pipes if p.edge_id != wrapper_uuid}
```

- [ ] **Step 6: The reveal**

Replace the whole `_reset_if_unlinked` method with:

```python
    def _reveal_own_value_if_unlinked(self) -> None:
        """Show the own value again once no edge feeds this inlet.

        The change reaches the node through its propagation: an immediate
        inlet fires ``on_change`` now, a deferred one is marked dirty for its
        node's next execution. Nothing happens while another edge still feeds
        the inlet, or when the own value equals the linked one.
        """
        if not self._is_inlet or self._linked_edges or not self._data.has_linked_value():
            return
        linked = self._data.get_value()
        self._data.clear_linked()
        own = self._data.get_value()
        if _same_value(linked, own):
            return
        if self.on_change is not None and self._is_immediate:
            self._trigger_callback(self.on_change, own)
        else:
            self._mark_as_data_dirty()
```

At module level, after the imports and before `@dataclass class DataPort`, add:

```python
def _same_value(a: Any, b: Any) -> bool:
    """True if *a* and *b* are one object or compare equal; a failing or ambiguous comparison is False."""
    if a is b:
        return True
    try:
        return bool(a == b)
    except Exception:
        return False
```

- [ ] **Step 7: Call it after re-enablement**

In `edge_wrapper.py`, in both `unlink` and `detach`, replace

```python
        # After re-enablement, so a displaced edge that took over leaves the value alone.
        if self._inlet_port:
            self._inlet_port._reset_if_unlinked()
```

with

```python
        # After re-enablement, so a displaced edge that took over keeps showing its value.
        if self._inlet_port:
            self._inlet_port._reveal_own_value_if_unlinked()
```

Run: `grep -rn "_reset_if_unlinked" --include="*.py" packages/ barn/ tests/`
Expected: no output.

- [ ] **Step 8: Run the tests**

Run: `uv run pytest tests/core tests/ui/widget -m "not browser and not perf" -n 4 -q -p no:randomly`
Expected: PASS; `test_disconnect_semantics.py` reports `8 passed, 1 xfailed`.

- [ ] **Step 9: Lint, types, commit**

```bash
uv run ruff check packages/haywire-core/src/haywire/core tests/core/test_edge
uv run ruff format --check packages/haywire-core/src/haywire/core tests/core/test_edge
uv run mypy packages/haywire-core/src/ tests/core/test_edge/
git add -A packages/haywire-core/src/haywire/core tests/core/test_edge
git commit -m "feat(edges): unlinking an inlet reveals its own value

When the last edge goes and no displaced edge takes over, the field drops
the linked value; an immediate inlet fires on_change, a deferred one is
marked dirty. An own write while linked is silent for the node, and a
removed edge's pending lazy pull is dropped.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: A DATA inlet takes one edge unless pooled

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/types/port.py` (connection rules in `__post_init__`)
- Modify: `tests/ui/skin/test_pin_icon_resolution.py`, `tests/ui/skin/test_pin_icon_resolver.py` (`_port` helpers)
- Test: `tests/core/test_types/test_data_inlet_arity.py` (create)

**Interfaces:**
- Produces: `DataPort.__post_init__` sets `allow_multiple_links = False` on every DATA inlet; `PooledType._configure_port` still makes pooled inlets multi-link.

- [ ] **Step 1: Write the failing tests**

Create `tests/core/test_types/test_data_inlet_arity.py`:

```python
"""A DATA inlet takes one edge; only a pooled inlet takes several."""

import pytest

from haywire.barn.builtin.types import FLOAT
from haywire.core.types import DataPort, FlowType, PortType


@pytest.mark.unit
def test_a_data_inlet_is_single_link_whatever_it_declares():
    port = DataPort(
        registry_id="float",
        registry_key="haybale_core:type:float",
        label="F",
        id="v",
        type_cls=FLOAT,
        port_type=PortType.INLET,
        flow_type=FlowType.DATA,
        allow_multiple_links=True,
    )

    assert port.allow_multiple_links is False


@pytest.mark.integration
def test_a_pooled_inlet_still_takes_several_edges(graph_with_library_system, library_system):
    from haybale_testing.nodes.testbed.edge_link_test import EdgeLinkTestNode

    node = graph_with_library_system.create_node_wrapper(
        EdgeLinkTestNode.class_identity.registry_key, position=(0, 0)
    ).node

    assert node.ports["pooled_float_inlet"].allow_multiple_links is True
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/core/test_types/test_data_inlet_arity.py -q -p no:randomly`
Expected: `test_a_data_inlet_is_single_link_whatever_it_declares` FAILS (`True is False`); the pooled test PASSES.

- [ ] **Step 3: The rule**

In `port.py` `__post_init__`, replace

```python
        if self.is_inlet() and self.flow_type == FlowType.CONTROL:
            # Control flow inlets do allow multiple connections by design
            self.allow_multiple_links = True
```

with

```python
        if self.is_inlet() and self.flow_type == FlowType.CONTROL:
            # Control flow inlets do allow multiple connections by design
            self.allow_multiple_links = True

        if self.is_inlet() and self.flow_type == FlowType.DATA:
            # A pooled inlet is made multi-link after construction (PooledType._configure_port).
            self.allow_multiple_links = False
```

- [ ] **Step 4: The icon tests' helpers**

In both `tests/ui/skin/test_pin_icon_resolution.py` and `tests/ui/skin/test_pin_icon_resolver.py`, in `_port`, replace

```python
    spec.update(type_cls=type_cls, flow_type=FlowType.DATA, **kwargs)
    return DataPort(port_type=port_type, **spec)
```

with

```python
    # A multi-link data inlet is set after construction, as PooledType._configure_port does.
    multi = kwargs.pop("allow_multiple_links", None)
    spec.update(type_cls=type_cls, flow_type=FlowType.DATA, **kwargs)
    port = DataPort(port_type=port_type, **spec)
    if multi is not None:
        port.allow_multiple_links = multi
    return port
```

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/core/test_types/ tests/ui/skin/ tests/core/test_graph/test_edges.py -q -p no:randomly -n 4`
Expected: PASS.

- [ ] **Step 6: Lint, types, commit**

```bash
uv run ruff check packages/haywire-core/src/haywire/core/types tests/core/test_types tests/ui/skin
uv run ruff format --check packages/haywire-core/src/haywire/core/types tests/core/test_types tests/ui/skin
uv run mypy packages/haywire-core/src/haywire/core/types/ tests/core/test_types/ tests/ui/skin/
git add packages/haywire-core/src/haywire/core/types/port.py tests/core/test_types/test_data_inlet_arity.py tests/ui/skin/test_pin_icon_resolution.py tests/ui/skin/test_pin_icon_resolver.py
git commit -m "feat(ports): a data inlet takes one edge unless pooled

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Only the own value is saved

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/types/enums.py` (`StoreStrategy`)
- Modify: `packages/haywire-core/src/haywire/core/types/port.py` (`to_dict` save call)
- Modify: `packages/haywire-core/src/haywire/core/types/interface.py` (three `store_strategy` docstring lines: 207, 277, 343)
- Modify tests: `tests/core/test_graph/test_store_strategy.py`, `tests/core/test_node/test_fold.py:106`, `tests/barn/test_signal_types.py:48`

**Interfaces:**
- Produces: `StoreStrategy` without `WHEN_LINKED`; `ALWAYS = HAS_WIDGET | NODE_SET` (10); `StoreStrategy.should_store(*, has_widget: bool, node_set: bool) -> bool`.

- [ ] **Step 1: Update the tests to the new signature**

In `tests/core/test_graph/test_store_strategy.py`, replace `class TestShouldStore:` from its `@pytest.mark.unit` decorator to the end of the class with:

```python
@pytest.mark.unit
class TestShouldStore:
    """Pure truth table — no port needed."""

    def test_never_and_none_never_store(self):
        for ss in (StoreStrategy.NEVER, StoreStrategy.NONE):
            assert ss.should_store(has_widget=True, node_set=True) is False, f"{ss!r} must never store"

    def test_always_always_stores(self):
        assert StoreStrategy.ALWAYS.should_store(has_widget=False, node_set=False) is True

    def test_always_saved_as_14_still_always_stores(self):
        # 14 carries bit 4, which no member uses; IntFlag keeps it and the rest is ALWAYS.
        assert StoreStrategy(14).should_store(has_widget=False, node_set=False) is True

    def test_has_widget_only_stores_with_widget(self):
        ss = StoreStrategy.HAS_WIDGET
        assert ss.should_store(has_widget=True, node_set=False) is True
        assert ss.should_store(has_widget=False, node_set=False) is False

    def test_node_set_only_stores_when_node_set(self):
        ss = StoreStrategy.NODE_SET
        assert ss.should_store(has_widget=False, node_set=True) is True
        assert ss.should_store(has_widget=False, node_set=False) is False

    def test_combined_flags_or_their_states(self):
        ss = StoreStrategy.HAS_WIDGET | StoreStrategy.NODE_SET
        assert ss.should_store(has_widget=True, node_set=False) is True
        assert ss.should_store(has_widget=False, node_set=True) is True
        assert ss.should_store(has_widget=False, node_set=False) is False
```

In `tests/core/test_node/test_fold.py`, replace `fold.store_strategy.should_store(is_linked=False, has_widget=False, node_set=False)` with `fold.store_strategy.should_store(has_widget=False, node_set=False)`.

In `tests/barn/test_signal_types.py`, replace `strategy.should_store(is_linked=True, has_widget=False, node_set=False)` with `strategy.should_store(has_widget=False, node_set=False)`.

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/core/test_graph/test_store_strategy.py tests/core/test_node/test_fold.py tests/barn/test_signal_types.py -q -p no:randomly`
Expected: FAIL — `TypeError: should_store() missing 1 required keyword-only argument: 'is_linked'`.

- [ ] **Step 3: `StoreStrategy`**

In `enums.py`, replace the `StoreStrategy` docstring and body (from `    """\n    Bitwise flags for when a port stores its value.` through the end of `should_store`) with:

```python
    """
    Bitwise flags for when a port saves its own value.

    - NEVER: do not store
    - HAS_WIDGET: store when the port has a widget
    - NODE_SET: store when the value was changed by the node
    - ALWAYS: store in any case

    A port saves only its own value, never what an edge delivers, so link state
    plays no part. Combine flags with OR; they trigger if any flag matches
    (there is no AND combination)::

        store_strategy = StoreStrategy.HAS_WIDGET | StoreStrategy.NODE_SET
    """

    NONE = 0
    NEVER = 1
    HAS_WIDGET = 2
    NODE_SET = 8
    ALWAYS = HAS_WIDGET | NODE_SET  # 10

    def should_store(self, *, has_widget: bool, node_set: bool) -> bool:
        """Resolve whether a port with this strategy should serialize its own value.

        ``NEVER`` and ``NONE`` never store. ``ALWAYS`` always stores. Otherwise
        store if any set flag matches the port's current state (OR semantics —
        there is no AND combination).
        """
        if self & StoreStrategy.NEVER or self == StoreStrategy.NONE:
            return False
        if (self & StoreStrategy.ALWAYS) == StoreStrategy.ALWAYS:
            return True
        return bool(
            (self & StoreStrategy.HAS_WIDGET and has_widget) or (self & StoreStrategy.NODE_SET and node_set)
        )
```

- [ ] **Step 4: The save call and the factory docstrings**

In `port.py` `to_dict`, replace

```python
            if self.store_strategy.should_store(
                is_linked=self.is_linked(),
                has_widget=self.widget_key is not None,
```

with

```python
            if self.store_strategy.should_store(
                has_widget=self.widget_key is not None,
```

In `interface.py`, on the three lines reading `store_strategy (StoreStrategy): NEVER, HAS_WIDGET, WHEN_LINKED, NODE_SET or ALWAYS` (207, 277, 343), replace `WHEN_LINKED, NODE_SET or ALWAYS` with `NODE_SET or ALWAYS`.

Run: `grep -rn "StoreStrategy.WHEN_LINKED\|is_linked=" --include="*.py" packages/ barn/ tests/`
Expected: no output.

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/core tests/barn -m "not browser and not perf" -n 4 -q -p no:randomly`
Expected: PASS.

- [ ] **Step 6: Lint, types, commit**

```bash
uv run ruff check packages/haywire-core/src/haywire/core/types tests/core tests/barn
uv run ruff format --check packages/haywire-core/src/haywire/core/types tests/core tests/barn
uv run mypy packages/haywire-core/src/haywire/core/types/ tests/
git add -A packages/haywire-core/src/haywire/core/types tests/core/test_graph/test_store_strategy.py tests/core/test_node/test_fold.py tests/barn/test_signal_types.py
git commit -m "feat(types): a port saves only its own value; WHEN_LINKED is gone

Link state no longer decides saving: the linked value is never saved.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Promoted settings keep, save and reveal their own value

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/settings/settings.py` (`_local_value`, ~173)
- Modify: `packages/haywire-core/src/haywire/core/settings/descriptor.py` (`setting.__set__`, ~370-385)
- Modify: `packages/haywire-core/src/haywire/core/node/promotion.py` (`_bind_port` 116-128, `promote_setting` docstring ~172, `demote_setting` ~236-251)
- Modify tests: `tests/core/node/test_promotion_single_cell.py` (`test_demote_after_driven_value_keeps_the_cell_value`), `tests/core/node/test_promotion_e2e.py` (step 4), `tests/ui/panel/test_promoted_row_state.py` (three tests), `tests/core/node/test_promote_demote.py` (`test_promoted_config_marks_field_locally_set`), `tests/core/settings/test_promoted_shared_cell.py` (one docstring), `tests/core/test_edge/test_disconnect_semantics.py` (second xfail marker, module docstring)
- Test: `tests/core/node/test_promotion_own_value.py` (create)

**Interfaces:**
- Consumes: `DataField.get_own_value()`, `clear_linked()` (Task 1).
- Produces: settings save, reset and write-guard on the own value; `_bind_port(port, bag, desc)` marks nothing; `demote_setting` drops the cell's linked value before releasing it.

- [ ] **Step 1: Write the failing tests**

Create `tests/core/node/test_promotion_own_value.py`:

```python
"""A linked promoted inlet shows its edge's value; the setting keeps, saves and reveals its own value."""

import pytest

from tests.core.node.test_promotion_single_cell import _link_and_push, _make_mixed_bag_node

pytestmark = pytest.mark.integration


def _promoted_inlet(make_node_with_setting):
    from haywire.core.node.promotion import promote_setting

    node = make_node_with_setting(accessor="filter", field="threshold")
    promote_setting(node, "filter", "threshold")
    return node, type(node.filter).__dict__["threshold"].storage_key


def test_a_setting_write_while_linked_keeps_the_edge_value_in_front(make_node_with_setting):
    node, pid = _promoted_inlet(make_node_with_setting)
    _link_and_push(node, pid, 0.9)

    node.filter.threshold = 0.3

    assert node.filter.threshold == 0.9
    assert node.filter._local_value(type(node.filter).__dict__["threshold"]) == 0.3


def test_a_linked_promoted_inlet_saves_its_own_value(make_node_with_setting):
    node, pid = _promoted_inlet(make_node_with_setting)
    node.filter.threshold = 0.3
    _link_and_push(node, pid, 0.9)

    assert node.filter._to_dict()["values"] == {"threshold": 0.3}


def test_demote_reveals_the_own_value(make_node_with_setting):
    from haywire.core.node.promotion import demote_setting

    node, pid = _promoted_inlet(make_node_with_setting)
    node.filter.threshold = 0.3
    _link_and_push(node, pid, 0.9)

    demote_setting(node, pid)

    assert node.filter.threshold == 0.3


def test_a_promoted_shadow_inlet_keeps_tracking_its_global(library_system):
    from haywire.core.node.promotion import promote_setting
    from haywire.core.types.enums import PortType

    node = _make_mixed_bag_node(library_system)
    registry = library_system.get_settings_registry()
    shadowed_desc = type(node.cfg).__dict__["shadowed"]
    promote_setting(node, "cfg", "shadowed", direction=PortType.INLET)

    registry.set_global(shadowed_desc._mirror_key, 0.9)

    assert node.cfg.shadowed == 0.9
```

In `tests/core/test_edge/test_disconnect_semantics.py`, delete the decorator above `test_linked_promoted_setting_saves_the_users_value`:

```python
@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="a promoted inlet's setting cell holds the edge-driven value, and that is what saves (ADR 0014)",
)
```

and replace its module docstring with:

```python
"""What a port holds once the edge driving it is removed, and callbacks passing through reroutes.

An inlet shows the value its edge delivers while linked and its own value once
the last edge is gone (ADR 0040).
"""
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/core/node/test_promotion_own_value.py tests/core/test_edge/test_disconnect_semantics.py -q -p no:randomly`
Expected: all four new tests FAIL (`_local_value` and `_to_dict` read 0.9; demote keeps 0.9; the shadow inlet stays 0.5), and `test_linked_promoted_setting_saves_the_users_value` FAILS (`0.875 == 0.25`).

- [ ] **Step 3: Save, reset and the write guard read the own value**

In `settings.py`, replace

```python
    def _local_value(self, descriptor: setting) -> Any:
        """Return this field's locally-set value from its cell. Only meaningful
        when the field is in ``_set_keys``."""
        return self._cell_for(descriptor).get_value()
```

with

```python
    def _local_value(self, descriptor: setting) -> Any:
        """Return this field's own value from its cell, whatever an edge delivers to a
        promoted inlet. Only meaningful when the field is in ``_set_keys``."""
        return self._cell_for(descriptor).get_own_value()
```

In `descriptor.py` `setting.__set__`, replace

```python
        # Compared against the resolved value, not _default: for a mirror with
        # no local override that is the mirrored global, and writing it back
        # must not create an override that then defeats reset. It also ends the
        # cross-tab echo loop here, at the model layer.
        old = self.__get__(obj, type(obj))
```

with

```python
        # Compared against the own value, not _default: for a mirror with no
        # local override that is the mirrored global, and writing it back must
        # not create an override that then defeats reset. It also ends the
        # cross-tab echo loop here, at the model layer. An edge's value in
        # front of a promoted inlet's own value plays no part.
        old = obj._cell_for(self).get_own_value()
```

- [ ] **Step 4: Promotion marks nothing; demote drops the linked value**

In `promotion.py`, replace the whole `_bind_port` function with:

```python
def _bind_port(port, bag: "Settings", desc: "setting") -> None:
    """Share the setting's cell into *port*.

    The setting keeps its opinion: an unset mirror field keeps tracking its
    global in the cell's own value while an edge's value stands in front of
    it. See ADR 0040."""
    port.bind_field(bag._cell_for(desc))
```

In `promote_setting`'s docstring, delete the sentence `An inlet or config is\n    also marked locally-set; an outlet is not (see ``_bind_port``).` so the paragraph reads `The port's id is the setting's ``storage_key``, and it borrows the setting's cell by reference, so setting and port are one value. The promotion is recorded on the bag, which is what serializes — the port never does.` (rewrap to the file's width).

In `demote_setting`, replace the docstring's first sentence `Remove the promoted port ``port_id``, release its cell binding, and clear the` / `settings-side promotion record.` with `Remove the promoted port ``port_id``, release its cell binding, and clear the` / `settings-side promotion record. The setting shows its own value again.`, and replace

```python
    node.ports[port_id].unbind_field()
```

with

```python
    # Before releasing the cell: once the port and its edges are gone, nothing clears it.
    node.ports[port_id].data.clear_linked()
    node.ports[port_id].unbind_field()
```

- [ ] **Step 5: Tests that pinned freeze-on-disconnect or the promote-time mark**

`tests/core/node/test_promotion_single_cell.py` — replace the whole `test_demote_after_driven_value_keeps_the_cell_value` with:

```python
def test_demote_after_a_driven_value_reveals_the_own_value(make_node_with_setting):
    """Demote removes the port and its edge; the setting shows its own value again."""
    from haywire.core.node.promotion import (
        demote_setting,
        promote_setting,
    )
    from haywire.core.types.enums import PortType

    node = make_node_with_setting(accessor="filter", field="threshold")
    promote_setting(node, "filter", "threshold", direction=PortType.INLET)
    pid = type(node.filter).__dict__["threshold"].storage_key
    _link_and_push(node, pid, 0.77)
    assert node.filter.threshold == 0.77

    demote_setting(node, pid)

    assert node.filter.threshold == 0.5
```

`tests/core/node/test_promotion_e2e.py` — replace

```python
    # 4. demote; the inlet is gone. §C3 freeze-on-disconnect: the edge-driven
    #    value stays frozen in the cell (recovery is an explicit reset), so the
    #    setting keeps 0.875 rather than snapping back to its default.
    demote_setting(node, pid)
    assert pid not in node.ports
    assert node.example.example_float == 0.875
```

with

```python
    # 4. demote; the inlet and its edge are gone, so the setting shows its own value.
    demote_setting(node, pid)
    assert pid not in node.ports
    assert node.example.example_float == default_value
```

`tests/ui/panel/test_promoted_row_state.py`:

- Replace the whole `test_promoted_inlet_disables_reset_even_when_locally_set` with:

```python
def test_promoted_inlet_leaves_the_field_unset_and_reset_greyed(make_node_with_setting):
    """Promotion marks nothing, and the graph owns an inlet's value, so Reset stays greyed."""
    node = make_node_with_setting(accessor="filter", field="threshold")
    from haywire.core.node.promotion import promote_setting

    promote_setting(node, "filter", "threshold")
    assert not node.filter._is_locally_set("threshold")

    row = _render(node)
    assert row is not None
    assert not _reset_enabled(row), "promoted inlet must grey reset"
    assert not _dirty_label(row)
```

- Replace the whole `test_demoted_unchanged_field_is_dirty_then_reset_clears_it` with:

```python
def test_promote_then_demote_leaves_an_untouched_field_pristine(make_node_with_setting):
    from haywire.core.node.promotion import demote_setting, promote_setting

    node = make_node_with_setting(accessor="filter", field="threshold")
    default = node.filter.threshold  # 0.5, untouched

    promote_setting(node, "filter", "threshold")
    pid = type(node.filter).__dict__["threshold"].storage_key
    demote_setting(node, pid)

    assert not node.filter._is_locally_set("threshold")
    assert node.filter.threshold == default
    row = _render(node)
    assert row is not None
    assert not _reset_enabled(row)
    assert not _dirty_label(row)
```

- In `test_reset_click_clears_chrome_in_place_without_cell_event`, replace

```python
    from haywire.core.node.promotion import demote_setting, promote_setting

    node = make_node_with_setting(accessor="filter", field="threshold")

    promote_setting(node, "filter", "threshold")
    pid = type(node.filter).__dict__["threshold"].storage_key
    demote_setting(node, pid)
    assert node.filter._is_locally_set("threshold")
```

with

```python
    node = make_node_with_setting(accessor="filter", field="threshold")

    # Locally set, and back at the default value: the "inert reset" case.
    node.filter.threshold = 0.9
    node.filter.threshold = 0.5
    assert node.filter._is_locally_set("threshold")
```

`tests/core/node/test_promotion_storage_key.py` — replace the whole `test_promote_marks_field_locally_set` with:

```python
def test_promote_leaves_the_field_unset(make_node_with_setting):
    """Promotion changes where a setting shows, not its opinion: nothing is marked locally set."""
    from haywire.core.node.promotion import promote_setting

    node = make_node_with_setting(accessor="filter", field="threshold")
    desc = type(node.filter).__dict__["threshold"]
    promote_setting(node, "filter", "threshold")
    assert node.filter._is_set(desc) is False
```

and in the docstring of `test_edge_drive_reads_through_setting_without_mark_helper`, replace `is visible via\n    getattr(bag, field) because the field is already locally-set from promote-time.` with `is visible via\n    getattr(bag, field): the setting reads the shared cell, which shows the linked value.`

`tests/core/node/test_promoted_port_write_policy.py` — in `test_an_edge_driven_write_marks_nothing`, delete the now-redundant

```python
        node.example._set_keys.discard(
            type(node.example).__dict__["example_float"].storage_key
        )  # undo promote-time marking, which INLET does deliberately
```

`tests/core/node/test_promotion_single_cell.py` — in the docstring of `test_promoted_outlet_keeps_tracking_global_until_actually_written`, delete the sentence `Only an INLET's edge-driven value needs the\n    locally-set opinion (see _bind_port).` (end the docstring after `unedited shadow field.`).

`tests/core/node/test_promotion_e2e.py` — the comment `# reset restores the resolved default (the recovery path).` becomes `# reset leaves the resolved default in place.`

`tests/core/node/test_promote_demote.py` — replace the whole `test_promoted_config_marks_field_locally_set` with:

```python
def test_promoted_config_leaves_the_field_unset(make_node_with_setting):
    """Promotion marks nothing; a config's widget edit marks the field, as for any setting."""
    node = make_node_with_setting(accessor="filter", field="threshold")
    from haywire.core.node.promotion import promote_setting
    from haywire.core.types.enums import PortType

    promote_setting(node, "filter", "threshold", PortType.CONFIG)
    assert node.filter._is_locally_set("threshold") is False
```

`tests/core/settings/test_promoted_shared_cell.py` — in the docstring of `test_unpromoted_read_does_not_touch_ports`, replace `(the setting is oblivious to ports;\n    an edge-driven promoted inlet marks _set_keys at write time instead)` with `(the setting is oblivious to ports)`.

- [ ] **Step 6: Run the tests**

Run: `uv run pytest tests/core tests/ui/panel tests/ui/widget -m "not browser and not perf" -n 4 -q -p no:randomly`
Expected: PASS; `test_disconnect_semantics.py` reports `9 passed` (no xfails left).

- [ ] **Step 7: Lint, types, commit**

```bash
uv run ruff check packages/haywire-core/src/haywire/core tests/core tests/ui/panel
uv run ruff format --check packages/haywire-core/src/haywire/core tests/core tests/ui/panel
uv run mypy packages/haywire-core/src/ tests/
git add -A packages/haywire-core/src/haywire/core tests/core tests/ui/panel
git commit -m "feat(settings): a promoted inlet's setting keeps, saves and reveals its own value

Save, reset and the write guard read the cell's own value; promotion no
longer marks the field locally set, so a promoted shadow inlet keeps
tracking its global; demote drops the linked value before releasing the
cell. Replaces ADR 0014's freeze-on-disconnect.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: A widget on a linked inlet refuses writes

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/widget/base.py` (`BaseWidget.set_value`, ~59-60)
- Modify: `packages/haywire-core/src/haywire/ui/widget/binding.py` (`sync_to_view` ~117, `_sync_to_model` ~152, `_update_nested_property` ~209)
- Modify: `tests/ui/widget/test_bind_nested.py` (append)
- Test: `tests/ui/widget/test_linked_widget_writes.py` (create)

**Interfaces:**
- Consumes: `DataField.has_linked_value()`, `get_own_value()` (Task 1), through `WidgetModel.data`.
- Produces: while `model.data.has_linked_value()`, `BaseWidget.set_value` and `PropertyBinding._sync_to_model` write nothing and resync the view to the model's value.

- [ ] **Step 1: Write the failing tests**

Create `tests/ui/widget/test_linked_widget_writes.py`:

```python
"""A widget on a linked inlet shows the linked value and refuses writes; the view snaps back."""

from typing import Any, cast

import pytest

from tests.ui.widget._sync_fixtures import _BaseDefaultFloatWidget, make_float_port

pytestmark = pytest.mark.unit


def _linked_widget():
    port = make_float_port()
    widget = _BaseDefaultFloatWidget(port)
    widget.render()
    port._linked_edges["e1"] = cast(Any, object())
    port.set_value(4.0, edge_id="e1")
    return port, widget


def test_the_view_shows_the_linked_value():
    _port, widget = _linked_widget()

    assert widget.el.value == 4.0


def test_a_view_edit_is_refused_and_the_view_snaps_back():
    port, widget = _linked_widget()
    widget.el.value = 9.0

    widget._bindings[0]._sync_to_model(9.0)

    assert port.data.get_own_value() == 0.0
    assert port.get_value() == 4.0
    assert widget.el.value == 4.0


def test_a_direct_widget_write_is_refused_while_linked():
    port, widget = _linked_widget()

    widget.set_value(9.0)

    assert port.data.get_own_value() == 0.0
    assert widget.el.value == 4.0


def test_an_unlinked_widget_still_writes_the_own_value():
    port = make_float_port()
    widget = _BaseDefaultFloatWidget(port)
    widget.render()

    widget._bindings[0]._sync_to_model(9.0)

    assert port.get_value() == 9.0
```

In `tests/ui/widget/test_bind_nested.py`, change `from typing import Any` to `from typing import Any, cast`, and append:

```python
def test_a_nested_view_shows_the_linked_value():
    port = _vec2_port()
    port.set_value(_Vec2(x=1.0, y=2.0))
    w = _Vec2Widget(port)
    w.render()
    port._linked_edges["e1"] = cast(Any, object())

    port.set_value(_Vec2(x=7.0, y=9.0), edge_id="e1")

    assert w.ex.value == 7.0


def test_a_nested_view_edit_is_refused_while_linked():
    port = _vec2_port()
    port.set_value(_Vec2(x=1.0, y=2.0))
    w = _Vec2Widget(port)
    w.render()
    port._linked_edges["e1"] = cast(Any, object())
    port.set_value(_Vec2(x=7.0, y=9.0), edge_id="e1")

    w.ex.value = 3.0
    w.ex.handlers["update:modelValue"](type("E", (), {"sender": w.ex})())

    assert cast(_Vec2, port.data.get_own_value()).x == 1.0
    assert w.ex.value == 7.0
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/ui/widget/test_linked_widget_writes.py tests/ui/widget/test_bind_nested.py -q -p no:randomly`
Expected: the refusal tests FAIL (the own value becomes 9.0 / 3.0), and `test_a_nested_view_shows_the_linked_value` FAILS (`1.0 == 7.0`); `test_the_view_shows_the_linked_value` and `test_an_unlinked_widget_still_writes_the_own_value` PASS.

- [ ] **Step 3: The refusal**

In `base.py`, replace

```python
    def set_value(self, value: Any) -> None:
        self.port.set_value(value)
```

with

```python
    def set_value(self, value: Any) -> None:
        """Write *value* to the model, unless an edge's value stands in front of it.

        While the model's field holds a linked value the write is refused and
        the view shows the model's value again.
        """
        if self.port.data.has_linked_value():
            self.on_model_changed(self.port.get_value())
            return
        self.port.set_value(value)
```

In `binding.py` `_sync_to_model`, directly after `assert self._element is not None and self.converter is not None`, insert:

```python
        if self._element.data.has_linked_value():
            # An edge's value stands in front of the model's own value; show it again.
            self.sync_to_view()
            return
```

In `sync_to_view`, replace `container = field._container` with `container = field.get_value()`. In `_update_nested_property`, replace `container = field._container` with `container = field.get_own_value()`.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/ui -m "not browser and not perf" -n 4 -q -p no:randomly`
Expected: PASS.

- [ ] **Step 5: Lint, types, commit**

```bash
uv run ruff check packages/haywire-core/src/haywire/ui tests/ui/widget
uv run ruff format --check packages/haywire-core/src/haywire/ui tests/ui/widget
uv run mypy packages/haywire-core/src/haywire/ui/ tests/ui/widget/
git add packages/haywire-core/src/haywire/ui/widget/base.py packages/haywire-core/src/haywire/ui/widget/binding.py tests/ui/widget/test_linked_widget_writes.py tests/ui/widget/test_bind_nested.py
git commit -m "feat(widgets): a widget on a linked inlet refuses writes and shows the linked value

One rule in the widget base layer: while the model's field holds a linked
value, a write is refused and the view resyncs. Nested bindings read the
value the node sees.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: Callbacks without absence

**Files:**
- Modify: `barn/haybale-core/haybale_core/types/specs.py` (`CALLBACK` `@type` and docstring)
- Modify: `packages/haywire-core/src/haywire/core/types/base.py` (absence block ~394-500; `WrapperType.__class_getitem__` field_class line)
- Modify: `packages/haywire-core/src/haywire/core/types/interface.py` (import line 5; `create_field`)
- Modify: `packages/haywire-core/src/haywire/barn/builtin/types/specs.py` (`INTField` docstring)
- Modify: `barn/haybale-core/haybale_core/types/pooled_type.py` (fields, `__post_init__`, `set_value`, `accepts_absence`)
- Modify: `packages/haywire-core/src/haywire/core/types/enums.py` (`FlowType.is_immediate` docstring)
- Rename + rewrite: `tests/core/test_types/test_immediate_absence.py` → `tests/core/test_types/test_callback_values.py`
- Modify: `tests/core/test_edge/test_disconnect_semantics.py` (last test)

**Interfaces:**
- Produces: `CALLBACK` default `{"value": ""}`; `_absence_tolerant_field(base_field_cls)` (OPTIONAL only; `absence_capable_field`, `_wrapper_field`, `_ABSENT_KEY` removed); `IType.create_field` builds `cls.field_class` as declared; `PooledField` of an immediate element removes a source's entry when that source sends the element type's default; `PooledField.accepts_absence()` is the base `False`.

- [ ] **Step 1: Rewrite the callback value tests**

```bash
git mv tests/core/test_types/test_immediate_absence.py tests/core/test_types/test_callback_values.py
```

Replace the whole file with:

```python
"""Callback values: an empty name means no subscription and a pool drops it; only OPTIONAL holds absence."""

import pytest

pytestmark = pytest.mark.integration


class TestCallbackFields:
    def test_a_callback_field_defaults_to_an_empty_name(self, library_system):
        from haybale_core.types import CALLBACK

        assert CALLBACK.create_field().get_value() == ""

    def test_a_callback_field_holds_no_absence(self, library_system):
        from haybale_core.types import CALLBACK

        assert not CALLBACK.create_field().accepts_absence()

    def test_a_callback_value_saves_and_loads(self, library_system):
        from haybale_core.types import CALLBACK

        field = CALLBACK.create_field()
        field.set_value("tick")
        restored = CALLBACK.create_field()

        restored.from_dict(field.to_dict())

        assert restored.get_value() == "tick"

    def test_it_still_travels_as_callback(self, library_system):
        from haybale_core.types import CALLBACK

        assert CALLBACK.create_field().get_stored_type() is CALLBACK


class TestDataclassCallbackField:
    def test_it_keeps_plain_storage(self, library_system):
        from haybale_testing.types import TEST_RECORD_CALLBACK

        assert not TEST_RECORD_CALLBACK.create_field().accepts_absence()

    def test_a_present_value_is_still_type_checked(self, library_system):
        from haybale_testing.types import TEST_RECORD_CALLBACK

        with pytest.raises(TypeError):
            TEST_RECORD_CALLBACK.create_field().set_value("not a record")


class TestOptionalKeepsAbsence:
    def test_an_optional_field_accepts_absence(self, library_system):
        from haywire.barn.builtin.types import INT, OPTIONAL

        assert OPTIONAL[INT].create_field().accepts_absence()

    def test_an_optional_field_still_travels_as_its_element(self, library_system):
        from haywire.barn.builtin.types import INT, OPTIONAL

        assert OPTIONAL[INT].create_field().get_stored_type() is INT

    def test_an_optional_field_saves_absence_as_a_null_value(self, library_system):
        from haywire.barn.builtin.types import INT, OPTIONAL

        field = OPTIONAL[INT].create_field()
        field.set_value(None)

        assert field.to_dict() == {"value": None}


class TestPooledFields:
    def test_an_empty_name_from_a_source_removes_its_entry(self, library_system):
        from haybale_core.types import CALLBACK, PooledType

        pool = PooledType[CALLBACK].create_field()
        pool.set_value("a", source_id="e1")
        pool.set_value("b", source_id="e2")

        pool.set_value("", source_id="e1")

        assert pool.get_value() == {"e2": "b"}

    def test_a_dataclass_default_from_a_source_removes_its_entry(self, library_system):
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

    def test_the_default_without_a_source_changes_nothing(self, library_system):
        from haybale_core.types import CALLBACK, PooledType

        pool = PooledType[CALLBACK].create_field()
        pool.set_value("a", source_id="e1")

        pool.set_value("")

        assert pool.get_value() == {"e1": "a"}

    def test_a_pooled_data_field_keeps_every_value(self, library_system):
        from haybale_core.types import PooledType
        from haywire.barn.builtin.types import FLOAT

        pool = PooledType[FLOAT].create_field()

        pool.set_value(0.0, source_id="e1")
        pool.set_value(None, source_id="e2")

        assert not pool.accepts_absence()
        assert pool.get_value() == {"e1": 0.0, "e2": None}
```

In `tests/core/test_edge/test_disconnect_semantics.py`, replace the whole `test_a_graph_holding_an_absent_callback_saves_and_loads` with:

```python
def test_a_graph_whose_reroute_lost_its_input_saves_and_loads(graph_with_library_system, library_system):
    graph = graph_with_library_system
    _event, _emit, edge = _callback_pair(graph)
    reroute_id = _split_with_reroute(graph, edge.edge_id)
    upstream = next(e for e in graph.edge_wrappers.values() if e.sink_node_id == reroute_id)
    graph.remove_edge_wrapper(upstream.edge_id)
    data = graph.to_dict()

    graph.clear()
    graph.load_from_dict(data)

    assert graph.node_wrappers[reroute_id].node.ports["out"].get_value() == ""
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/core/test_types/test_callback_values.py tests/core/test_edge/test_disconnect_semantics.py -q -p no:randomly`
Expected: FAIL — the callback default is `None`, callback fields accept absence, the pools keep `""`/the default instance, the pooled DATA field's `accepts_absence` part passes, and the reroute outlet holds `None`.

- [ ] **Step 3: `CALLBACK`'s default**

In `barn/haybale-core/haybale_core/types/specs.py`, in the `CALLBACK` `@type(...)`, replace `default={},` with `default={"value": ""},`, and replace the class docstring with:

```python
    """
    callback signal type - represents callback flow
    Inherits from STRING for payload compatibility.
    but is by default not serialized, and has no widget.
    An empty name means no subscription: an emitter drops it.
    """
```

- [ ] **Step 4: Absence storage back to `OPTIONAL` only**

In `packages/haywire-core/src/haywire/core/types/base.py`, replace everything from the comment `#: Absence-capable field classes, keyed by the field class they extend.` through `    return _WrapperField` (the end of `_wrapper_field`) with:

```python
#: Absence-tolerant field classes, keyed by the element's own field class.
#: Shared so ``OPTIONAL[INT]`` built twice yields one field class, matching
#: ``_parameterized_cache``'s identity guarantee for the types themselves.
_ABSENCE_TOLERANT_FIELDS: "dict[type, type]" = {}


def _absence_tolerant_field(base_field_cls: type) -> type:
    """Return a subclass of *base_field_cls* whose own value may also be ``None``.

    A present value keeps the element's own storage behaviour, coercion
    included; only ``None`` takes a different path, storing through
    ``PrimitiveField._set_own``. Cached, so one element field class yields
    one subclass.

    Raises:
        TypeError: If *base_field_cls* isn't a ``PrimitiveField`` subclass.
            Absence needs an unwrapped slot to live in, which only that
            storage has.
    """
    from .fields import PrimitiveField

    if not (isinstance(base_field_cls, type) and issubclass(base_field_cls, PrimitiveField)):
        raise TypeError(
            f"a wrapper type cannot wrap an element stored by {base_field_cls.__name__}: "
            f"absence is only defined for PrimitiveField storage (a bare value or None). "
            f"Wrap a primitive-shaped IType instead."
        )

    cached = _ABSENCE_TOLERANT_FIELDS.get(base_field_cls)
    if cached is not None:
        return cached

    class _AbsenceTolerantField(base_field_cls):  # type: ignore[valid-type,misc]
        """``base_field_cls``, plus the ability to hold absence."""

        def _set_own(self, value: Any) -> None:
            if value is None:
                # Past the element's own _set_own, whose coercion rejects None.
                PrimitiveField._set_own(self, None)
                return
            super()._set_own(value)

        def get_stored_type(self) -> "type[IType]":
            """Return the element type, which is what travels on an edge.

            ``type_cls`` stays the wrapper, so a promoted ``OPTIONAL[INT]``
            renders as an ordinary ``INT`` pin and links to one with no
            adapter, while the widget and identity still see the wrapper.
            """
            element = self.type_cls.element_type_cls
            assert element is not None  # __class_getitem__ always sets it
            return element

        def accepts_absence(self) -> bool:
            """Always True: this field class exists to hold ``None``."""
            return True

    _AbsenceTolerantField.__name__ = f"AbsenceTolerant{base_field_cls.__name__}"
    _AbsenceTolerantField.__qualname__ = _AbsenceTolerantField.__name__
    _ABSENCE_TOLERANT_FIELDS[base_field_cls] = _AbsenceTolerantField
    return _AbsenceTolerantField
```

In `WrapperType.__class_getitem__`, replace `"field_class": _wrapper_field(element_field_cls),` with `"field_class": _absence_tolerant_field(element_field_cls),`.

- [ ] **Step 5: `create_field` builds the declared field class**

In `interface.py`, change line 5 back to `from haywire.core.types.enums import PortType, StoreStrategy, default_show_widget`. In `create_field`, delete the docstring paragraph

```
        An immediate type (see ``FlowType.is_immediate``) gets the absence-capable
        form of its field class, so its ports can go absent.
```

and replace

```python
        field_cls = cls.field_class
        identity = getattr(cls, "class_identity", None)
        if identity is not None and FlowType(identity.flow_type).is_immediate:
            from .base import absence_capable_field

            # An immediate port goes absent when its last edge is removed.
            field_cls = absence_capable_field(field_cls)
        return field_cls(type_cls=cls, default_kwargs=default_kwargs)
```

with

```python
        return cls.field_class(type_cls=cls, default_kwargs=default_kwargs)
```

In `packages/haywire-core/src/haywire/barn/builtin/types/specs.py` `INTField`'s docstring, replace `(see ``absence_capable_field``)` with `(see ``_absence_tolerant_field``)`.

- [ ] **Step 6: The pool drops its element's default**

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

        # A callback element's default means "no subscription"; see set_value.
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
        For a callback element, the element type's default (an empty name for
        ``CALLBACK``) means "no subscription" and removes the source's entry.
        """
        if self._drops_default and value == self._element_default:
            # With no source there is no entry to end.
            if source_id is not None:
                self.remove_source(source_id)
            return
```

and delete the whole `accepts_absence` method of `PooledField`.

- [ ] **Step 7: `FlowType.is_immediate`**

In `enums.py`, in `FlowType.is_immediate`'s docstring, replace

```
        Only ``CALLBACK`` is immediate. An immediate inlet fires ``on_change`` for
        edge-driven writes too, a reroute forwards it at once, and it goes absent
        when its last edge is removed.
```

with

```
        Only ``CALLBACK`` is immediate. An immediate inlet fires ``on_change`` for
        edge-driven writes too, and a reroute forwards it at once.
```

- [ ] **Step 8: Check nothing refers to the removed names**

Run: `grep -rnwE "absence_capable_field|_wrapper_field|_ABSENT_KEY|__absent__|_ABSENCE_CAPABLE_FIELDS|_WRAPPER_FIELDS" --include="*.py" packages/ barn/ tests/`
Expected: no output.

- [ ] **Step 9: Run the tests**

Run: `uv run pytest tests/core tests/ui tests/barn -m "not browser and not perf" -n 4 -q -p no:randomly`
Expected: PASS; `test_disconnect_semantics.py` `9 passed`.

- [ ] **Step 10: Lint, types, commit**

```bash
uv run ruff check packages/haywire-core/src/haywire barn/haybale-core tests/core
uv run ruff format --check packages/haywire-core/src/haywire barn/haybale-core tests/core
uv run mypy packages/haywire-core/src/ barn/haybale-core/haybale_core/ tests/
git add -A packages/haywire-core/src/haywire barn/haybale-core tests/core
git commit -m "feat(callbacks): an empty name means no subscription; no callback absence

CALLBACK defaults to \"\", which a relay forwards like any value; an
immediate pool drops an entry equal to its element's default. Absence
storage is OPTIONAL's alone again.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: A primitive type declares a default it can hold

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/types/decorator.py` (after `normalize_and_validate_default`, ~168)
- Test: `tests/core/types/test_primitive_type_default.py` (create)

**Interfaces:**
- Produces: `@type` raises `TypeError` for a `PrimitiveType` whose resolved default has no `"value"` or `"value": None`.

- [ ] **Step 1: Write the failing tests**

Create `tests/core/types/test_primitive_type_default.py`:

```python
"""A primitive type must declare a default value it can hold."""

import pytest

from haywire.core.types.base import PrimitiveType
from haywire.core.types.decorator import type as type_dec

pytestmark = pytest.mark.unit


def test_a_primitive_type_without_a_default_value_is_rejected():
    with pytest.raises(TypeError, match="needs a 'value' that is not None"):

        @type_dec(label="NoValue", default={})
        class NoValue(PrimitiveType[str]):
            pass


def test_a_primitive_type_with_a_none_default_is_rejected():
    with pytest.raises(TypeError, match="OPTIONAL"):

        @type_dec(label="NoneValue", default={"value": None})
        class NoneValue(PrimitiveType[str]):
            pass


def test_a_primitive_type_with_a_value_is_accepted():
    @type_dec(label="HasValue", default={"value": ""})
    class HasValue(PrimitiveType[str]):
        pass

    assert HasValue.class_identity.default == {"value": ""}


def test_a_derived_primitive_type_keeps_its_parents_default():
    from haywire.barn.builtin.types import STRING

    @type_dec(label="Derived")
    class Derived(STRING):
        pass

    assert Derived.class_identity.default == {"value": ""}
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/core/types/test_primitive_type_default.py -q -p no:randomly`
Expected: the two rejection tests FAIL (`DID NOT RAISE`); the two acceptance tests PASS.

- [ ] **Step 3: The check**

In `decorator.py`, replace

```python
        # Normalize and validate default
        identity_dict["default"] = normalize_and_validate_default(
            identity_dict["default"], inner_cls, context="@type decorator"
        )
```

with

```python
        # Normalize and validate default
        identity_dict["default"] = normalize_and_validate_default(
            identity_dict["default"], inner_cls, context="@type decorator"
        )
        # A primitive instance cannot hold None, so a missing value only crashes at the first save.
        if issubclass(inner_cls, PrimitiveType) and identity_dict["default"].get("value") is None:
            raise TypeError(
                f"@type decorator for {inner_cls.__name__}: a primitive type's default needs a "
                f"'value' that is not None, got {identity_dict['default']!r}. For a type whose "
                f"values can be absent, use OPTIONAL[T]."
            )
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/core/types/ tests/core/test_types/ tests/barn/ -m "not browser and not perf" -n 4 -q -p no:randomly`
Expected: PASS (every shipped primitive type has a value; `CALLBACK`'s since Task 7).

- [ ] **Step 5: Lint, types, commit**

```bash
uv run ruff check packages/haywire-core/src/haywire/core/types tests/core/types
uv run ruff format --check packages/haywire-core/src/haywire/core/types tests/core/types
uv run mypy packages/haywire-core/src/haywire/core/types/ tests/core/types/
git add packages/haywire-core/src/haywire/core/types/decorator.py tests/core/types/test_primitive_type_default.py
git commit -m "feat(types): a primitive type must declare a default value it can hold

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: Docs, ADR 0040, full verification

**Files:**
- Modify: `docs/reference/glossary.md` (rows **freeze-on-disconnect**, **CALLBACK port**, **Promotion**)
- Modify: `docs/architecture/settings/settings-arch.md` (freeze paragraph, ~331), `docs/components/settings/setting-canon.md` (~274), `docs/architecture/execution/edges/edges-arch.md` (§3.2 "Unlink reset", §3.4 table), `docs/architecture/execution/callbacks/callbacks-arch.md` (§2.4), `docs/components/datatypes/datatype-canon.md` (§3 `flow_type` and custom-field paragraphs, `default` row)
- Modify: `docs/adr/0003-show-widget-strategy.md`, `docs/adr/0014-promotion-as-direction.md`, `docs/adr/0033-absence-is-a-type.md`, `docs/adr/0036-groups-execute-through-their-boundary-nodes.md`
- Create: `docs/adr/0040-unlinking-reveals-the-own-value.md`
- Modify: `docs/superpowers/plans/2026-09-28-edge-kinds.md` (step 2 row and section)

- [ ] **Step 1: Glossary**

Replace the whole **freeze-on-disconnect** row with these two rows:

```markdown
| **Own value** | What a port or setting holds itself: written by the user (a widget), the node or a setting, else its declared default. It is what is saved, and an edge never overwrites it — while an edge feeds an inlet, the own value is **parked** behind the **linked value**: no widget or settings row shows or edits it, only saving reads it, and a write from code (a mirror sync, reset, undo, a node) lands in it quietly. Removing the last edge shows the own value again. The same rule holds for every port, edge kind and propagation mode. See [ADR 0040](../adr/0040-unlinking-reveals-the-own-value.md) | freeze-on-disconnect (retired), base value |
| **Linked value** | The value an inlet's edge delivered, shown and used while the edge is linked and never saved. A widget on a linked inlet displays it and refuses edits | edge value, driven value |
```

In the **CALLBACK port** row, replace `removing any edge on the path sets the next port to absence, which removes the emitter's entry.` with `removing any edge on the path shows the next port's **own value** — its default, an empty name, which the emitter treats as no subscription and drops.`

In the **Promotion** row, after `` `promote_setting` records the promotion and `demote_setting` clears it (mirror operations).`` insert `` Promotion changes where a setting is visible, not its opinion: it marks nothing locally set, and while an edge drives the inlet the setting keeps, saves and later shows its **own value**.``

- [ ] **Step 2: Settings docs**

In `settings-arch.md` §6.5, three passages change. In **Two directions, two verbs**, replace `` `promote_setting` marks the field locally-set (`storage_key ∈ _set_keys`) for the port's lifetime, so the setting reads the shared cell (incl. any edge-driven value).`` with `` The setting reads the shared cell, so it sees an edge's value while the inlet is linked; promotion marks nothing locally set.``

In **Mirror-cell authority**, replace `Once a cross-mirror field is **promoted**, it is locally-set for the port's lifetime (ADR 0014), so `_on_field_change` no longer updates its read value — the promoted shadow freezes at its promote-time value until demote + `reset`.` with `Promotion does not change this: an unset promoted shadow keeps tracking its global in the cell's own value, behind any linked value (ADR 0040).`

Replace the paragraph starting `**Freeze-on-disconnect.**` with:

```markdown
**Unlinking reveals the own value.** The shared cell holds the setting's own value and, while an edge drives the promoted inlet, the linked value in front of it (`DataField`, ADR 0040). The setting reads what the node uses; saving and `reset` work on the own value; unlinking and demote show the own value again. Promotion marks nothing locally set, so an unset mirror keeps tracking its global.
```

In `setting-canon.md`, replace `` `demote` never resets the value (freeze-on-disconnect) — recovery is an explicit `reset`.`` with `` `demote` shows the setting's own value again; an edge's value is never kept (ADR 0040).``

- [ ] **Step 3: `edges-arch.md`**

Replace the paragraph starting `**Unlink reset.**` with:

```markdown
**Unlinking reveals the own value.** When an inlet loses its last linked edge and no displaced edge takes over, its field drops the linked value (`DataField.clear_linked`) and the own value shows again (ADR 0040). The node learns of it through the port's propagation: an immediate inlet fires `on_change` at once, so a reroute passes it on (see [callbacks-arch §2.4](../callbacks/callbacks-arch.md)); a deferred inlet is marked dirty for its node's next execution. A lazy pull still queued for the removed edge is dropped. A pooled inlet needs nothing extra: `_clear_link` already removed that source's entry.
```

In the §3.4 table, after the row starting `| Widget / programmatic input`, insert:

```markdown
| Own write while linked (no `edge_id`, field holds a linked value) | no | exists | no `on_change`, no dirty mark: the own value changed behind the linked one |
```

- [ ] **Step 4: `callbacks-arch.md` §2.4**

Replace the paragraph starting `Removing any edge on the path unsubscribes.` with:

```markdown
Removing any edge on the path unsubscribes. An inlet left without a linked edge shows its own value (ADR 0040); for a callback port that is its default, an empty name. The reroute forwards it, and the emitter's pooled inlet treats its element type's default as "no subscription" and removes the entry keyed by its own edge. A displaced edge that takes over keeps the subscription in place.
```

- [ ] **Step 5: `datatype-canon.md`**

In the `flow_type` paragraph, replace `` `CONTROL`/`CALLBACK` mark the type as a non-data signal — these get no widget and no meaningful default.`` with `` `CONTROL`/`CALLBACK` mark the type as a non-data signal and get no widget. A `CALLBACK` type's default means "no subscription": an emitter's pool drops a subscription equal to it, so never make it a real one (core `CALLBACK`'s is an empty name; a dataclass callback's default instance carries an empty name).``

In the **Custom field for type coercion** paragraph, replace `define a `PrimitiveField` subclass that overrides `set_value()` and assign it` with `define a `PrimitiveField` subclass that overrides `_set_own()` — the hook that checks, coerces and stores a field's own value, which the framework also runs for an edge's value — and assign it`.

In the `@type` parameter table's `default` row, replace `Constructor kwargs. Primitives: `{'value': v}` or bare `v`. Complex: `{attr: v, ...}`.` with `Constructor kwargs. Primitives: `{'value': v}` or bare `v`, where `v` is not `None` (`@type` rejects it; use `OPTIONAL[T]` for values that can be absent). Complex: `{attr: v, ...}`.`

- [ ] **Step 6: ADR 0040**

Create `docs/adr/0040-unlinking-reveals-the-own-value.md`:

```markdown
---
name: unlinking-reveals-the-own-value
description: A port keeps its own value and, while an edge feeds it, the linked value in front of it; removing the last edge shows the own value — one rule for every port, edge kind and propagation mode; supersedes ADR 0014's freeze-on-disconnect
status: accepted
see-also: ADR-0014, ADR-0016, ADR-0019, ADR-0033, ADR-0036, ADR-0039
level: architectural
---

# Unlinking reveals a port's own value

**Context.** An edge wrote its value into the inlet's field, over whatever the user had set. Unlinking left that last delivered value in place (ADR 0014's freeze-on-disconnect), so the user's value was lost, and a linked promoted setting saved the upstream value over the user's. Callbacks needed a rule of their own — an unlinked callback inlet had to go absent to end a subscription — which set them apart from every other port. Blender keeps the user's value and shows it again after unlinking.

**Decision.** One rule for every inlet, edge kind and propagation mode: an inlet shows its **linked value** while an edge feeds it and its **own value** otherwise.

- *Two values in the field.* `DataField` keeps the own value in its subclass storage and the linked value in a second instance of the same class, so both get the field's checks and coercion. A write with a `source_id` (an edge) sets the linked value; any other write sets the own value. Field classes implement `_get_own`/`_set_own`; `PooledField` keeps one value per source and never holds a linked value.
- *Unlinking.* When the last linked edge goes and no displaced edge takes over, the field drops the linked value. The node learns of it through the port's propagation: an immediate inlet fires `on_change` at once, a deferred one is marked dirty. A lazy pull still queued for the removed edge is dropped. A control inlet with several edges keeps its linked value until the last goes; a DATA inlet takes one edge unless pooled.
- *Parked while linked.* While linked, the own value is parked: no UI shows or edits it — a widget on a linked inlet shows the linked value and refuses edits, the view snapping back, and a promoted inlet's settings row is read-only (ADR 0017) — and only saving reads it. A write from code (a mirror sync, a settings reset, undo, a node) is never refused: it lands in the parked value with no `on_change` and no dirty mark, and the field event still fires, carrying the value `get_value()` returns. Refusing those writes would give each writer its own failure case.
- *Saving.* Only the own value is saved; `StoreStrategy.WHEN_LINKED` is gone.
- *Promoted settings.* A promoted port shares the setting's field (ADR 0014, one cell two views), so the setting reads the linked value while linked and saves, resets and shows its own value. Promotion marks nothing locally set, so an unset mirror keeps tracking its global; demote shows the own value.
- *Callbacks.* A callback's default is an ordinary value (an empty name for `CALLBACK`) that an emitter's pool reads as "no subscription". No callback type needs absence storage, and `@type` rejects a primitive type with no default value.

**Alternatives.** *Freeze-on-disconnect (ADR 0014)* — one value, but user values are lost and callbacks need their own unlink rule. *Snapshot the own value at link time and restore it on unlink* — one stored value, but an own write while linked is overwritten by the next delivery. *Keep the linked value on the port* — promoted settings read the field, so they would need the read-tier bridge ADR 0014 retired. *Widgets write the linked value* — an edit then lasts until the upstream next delivers and is lost on reload. *Refuse every own write while linked* — each writer (mirror sync, reset, undo, node code) then needs its own answer for a dropped write, and the field needs link/unlink signals from the port, since settings write the field directly.

**Consequences.**

- Removing a DATA edge changes the node's input: at its next execution the node sees its own value, not the last delivered one. A DATA reroute that loses its input forwards its type's default.
- A graph saved before this ADR stored a linked inlet's delivered value as the port's value; it loads as the own value. No migration.
- A field class written by a library author renames `get_value`/`set_value` to `_get_own`/`_set_own`.
- EdgeKind (edge-kinds step 5) inherits one unlink rule; "the default means no subscription" moves to the callback kind.
```

- [ ] **Step 7: ADR notes**

In `0014-promotion-as-direction.md`, change the front-matter `description` ending `(superseded in part by ADR 0019)` to `(superseded in part by ADR 0019 and, for freeze-on-disconnect, ADR 0040)`, add `ADR-0040` to `see-also`, and insert after the H1:

```markdown
> **Freeze-on-disconnect is superseded by [ADR 0040](0040-unlinking-reveals-the-own-value.md).** The shared cell now keeps an own value and, while an edge drives the inlet, a linked value in front of it; unlinking and demote show the own value. One cell, two views stands.
```

In `0003-show-widget-strategy.md`, replace `` (`HAS_WIDGET`, `WHEN_LINKED`, `NODE_SET` can each independently be true`` with `` (`HAS_WIDGET` and `NODE_SET` can each independently be true``, and add after that paragraph: `*(2026-09: `StoreStrategy.WHEN_LINKED` was removed by ADR 0040 — only a port's own value is saved.)*`

In `0033-absence-is-a-type.md`, replace the heading `## Amendment — callback ports hold absence too (2026-09)` and its paragraph with:

```markdown
## Amendment — callback absence withdrawn (2026-09)

A callback port briefly held absence so an unlinked callback inlet could end a subscription. ADR 0040 replaced that: a callback's default is an ordinary value (an empty name for `CALLBACK`) that an emitter's pool reads as "no subscription", so absence stays what this ADR says — a value of `OPTIONAL[T]`, for `PrimitiveField`-stored elements only. `@type` now rejects a primitive type whose default holds no value, turning the latent `TypeError` described above into an error at declaration.
```

In `0036-groups-execute-through-their-boundary-nodes.md`, in the 2026-09 amendment, replace `and when its upstream edge is removed the inlet goes absent, so the emitter's pool drops its entry` with `and when its upstream edge is removed the inlet shows its own value — its default, an empty name (ADR 0040) — so the emitter's pool drops its entry`.

- [ ] **Step 8: The overview**

In `docs/superpowers/plans/2026-09-28-edge-kinds.md`:

- step 2's row: status **Built** on branch `unlink-own-value`, not merged; *Next*: merge;
- the step 2 section's first line: **Planned** becomes **Built**;
- the acceptance-test sentence under the table: they now report 9 passed, with no xfails;
- leave the falsy-field trap in *Small items* unless it was fixed on the way.

- [ ] **Step 9: Regenerate library docs and build**

```bash
uv run haywire docs --all
git status --short
uv run mkdocs build --strict -d <scratchpad>/site
```

Expected: regenerated docs change only where `CALLBACK`'s docstring and default appear; the strict build shows exactly one warning, the pre-existing `guides/panels.md` link to `.insights/`.

- [ ] **Step 10: Commit the docs**

```bash
git add -A docs/ barn/
git commit -m "docs: unlinking reveals the own value, ADR 0040

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 11: Full verification**

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-marketplace/haybale_marketplace/ barn/haybale-share/haybale_share/ barn/haybale-graph-editor/haybale_graph_editor/ barn/haybale-haystack/haybale_haystack/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-TEST_A/haybale_test_a/ tests/
uv run pytest -m "not browser and not perf" -n 4 -q > <scratchpad>/t.log 2>&1; echo "exit=$?"; grep -E "^FAILED|^ERROR" <scratchpad>/t.log; grep -E "passed|failed" <scratchpad>/t.log | tail -1
uv run pytest -m browser -n 4 -q > <scratchpad>/b.log 2>&1; echo "exit=$?"; grep -E "^FAILED|^ERROR" <scratchpad>/b.log; grep -E "passed|failed" <scratchpad>/b.log | tail -1
(cd ../haybale-visiongraph && uv run pytest tests/ -q)
git status --short
```

Expected: ruff and mypy clean; both tiers `exit=0` (gate: only the 2 pre-existing xfails in `test_haystack_carve_out.py`); visiongraph passes; clean tree. A failure outside the files this plan names follows the Global Constraint: stop and report. A run that hangs to the 120 s timeout is the known redraw/validation lock cycle (edge-kinds step 3): report it, do not retry it away.

- [ ] **Step 12: Benchmark against the baseline** (clean tree required)

Run: `uv run python benchmarks/run.py`
Expected: every case within 5 % of its Task 0 `min`. If `graph_loop` or `node_execute_bare` is more than 5 % slower, add to `PrimitiveField` in `fields.py`:

```python
    def get_value(self) -> T | None:
        """Return the linked value while an edge feeds this field, else the own value."""
        slot = self._linked_slot
        if slot is not None:
            return slot._value  # type: ignore[attr-defined]
        return self._value
```

commit it (`perf(types): read a primitive field without the hook call`), and run the benchmark again. Commit the appended `benchmarks/results/results.jsonl` rows (`bench: after unlinking reveals the own value`) and report each case's before/after `min`.

---

## Self-review notes

- **Decision coverage:** Q1 → Task 9 glossary; Q2 → Task 4; 3bA → Task 6; Q4 → Task 2 (multi-link unit test); 4bA → Task 3; Q5 → Task 2; Q6 → Task 5; Q7 → Tasks 1 (field event) and 2 (`on_change`); Q8 → Task 7; 8bA → Task 8; Q9 → Task 1.
- **Parked, not refused (user review 2026-09-28):** while linked no UI reaches the own value; writes from code land in it rather than being refused, so no writer needs a failure case. Gap accepted: between linking and the first delivery the port has no linked value yet and shows its own.
- **Order:** Task 1 bridges step 1's `_reset_if_unlinked` (it clears the linked value before writing `None`) so callbacks keep working until Task 2 replaces it; Task 7 removes the absence storage only after the reveal exists; Task 8 follows Task 7, since `CALLBACK`'s old default would fail the new check.
- **Consequence users will notice:** removing a DATA edge now changes the node's input on its next execution (ADR 0040, consequences).

## Execution notes — 2026-09-29

Built inline on `unlink-own-value`. Deviations from the tasks above, each to keep every commit green:

- **Task 1** also took Task 5's `demote_setting` change (`clear_linked()` before `unbind_field()`) and its two test flips (`test_promotion_single_cell.py` demote test, `test_promotion_e2e.py` step 4). With two values in the field, a demoted cell otherwise kept the edge's value and `reset` could not recover it.
- **Task 2** also took Task 7's pool rule (a callback pool drops an entry equal to its element's default), alongside step 1's `None` branch. Once a relay reveals its own value, a dataclass callback's reroute forwards its default instance, which the pool otherwise kept. Task 7 then removed the `None` branch.
- **Task 4:** `ALWAYS = HAS_WIDGET | NODE_SET` made the two flags together unconditional. `ALWAYS` is instead the freed bit 4, a flag of its own; a saved `14` still reads as `ALWAYS`.
- **Task 7:** `test_a_pooled_data_field_keeps_every_value` writes a value before `None`, because `PooledField` skips a write equal to the current entry and a missing entry reads as `None`.
- **Task 9, benchmark:** `graph_loop` measured +10.7%. The Step 12 fallback (`PrimitiveField.get_value` reading `_value` directly) brought it to +5.9%; `INTField`/`FLOATField._set_own` assigning `_value` directly instead of via `super()` brought it to +2.7% (`node_execute_bare` ±0).
- **Task 9:** ADR 0003 line 127 and ADR 0040's consequences (the link-to-first-delivery gap) were added; ADR 0033's amendment states the save crash directly.

