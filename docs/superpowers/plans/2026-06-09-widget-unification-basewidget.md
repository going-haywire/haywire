# Widget Unification (BaseWidget) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collapse Haywire's two widget base classes (`SimpleWidget` + `BaseWidget`) into one canonical `BaseWidget` with a general "floor" (`build()` + `on_model_changed()`) and a `bind()` sugar layer, delete the dead "Pile B" binding machinery, migrate all 8 production widgets, and rewrite the docs to describe only the new reality.

**Architecture:** One `BaseWidget` in `haywire.ui.widget`. Authors implement `build()` to construct any NiceGUI tree; they call `self.bind(element, to="x")` for flat-scalar fields (the sugar) or override `on_model_changed(value)` for arbitrary model→view sync (the floor). Primitives are the degenerate `to="value"` case. Base public methods (`cleanup`, model-change dispatch) are final (template-method); subclasses override protected hooks (`_on_cleanup()`). Bindings register inline during `build()` and activate exactly once, centrally, in `render()` — eliminating the old double-activation bug. The agnostic boundary stays at `haywire.core` (NiceGUI-free) vs `haywire.ui` (NiceGUI-native). See `docs/adr/0007-widget-unification-basewidget.md`.

**Tech Stack:** Python 3.12, NiceGUI, pytest, ruff, ty (type checker). Reactive `DataPort` / `DataField` model from `haywire.core.types`.

**Decision record:** `docs/adr/0007-widget-unification-basewidget.md` is authoritative. This plan implements it.

---

## Pre-flight: read these before starting

- `docs/adr/0007-widget-unification-basewidget.md` — every decision and its rationale.
- `docs/plans/widget-unification-perf-verification.md` — why there is **no fast-path** (Finding B: perf-irrelevant).
- Current code under change: `packages/haywire-core/src/haywire/ui/widget/{base,simple,binding,converters,interface,factory}.py`.
- Existing tests: `tests/ui/widget/{test_sync_path_parity,test_sync_path_perf,_sync_fixtures}.py`.
- The 8 widgets to migrate: `barn/haybale-core/haybale_core/widgets/basic_widgets.py` (7), `barn/haybale-visiongraph/haybale_visiongraph/widgets/opencv_viewer_widget.py` (1).

## Pre-flight: establish the baseline (CLAUDE.md mandate)

- [ ] **Step 0: Capture a clean baseline before touching anything.**

Run:
```bash
uv run ruff check packages/haywire-core/src/haywire/ui/widget/
uv run mypy packages/haywire-core/src/haywire/ui/widget/
uv run pytest tests/ui/widget/ -m "not perf"
```
Expected: all clean / all pass. If anything fails here, STOP and resolve with the user — per CLAUDE.md the baseline must be clean, and any pre-existing failure would be misattributed to this work.

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `packages/haywire-core/src/haywire/ui/widget/base.py` | The single canonical `BaseWidget`: floor (`build`, `on_model_changed`) + `bind()` sugar + final `cleanup`/dispatch | **Rewrite** |
| `packages/haywire-core/src/haywire/ui/widget/binding.py` | `PropertyBinding`: model↔view sync, value + nested-property paths, converters. Pile B removed. | **Trim** |
| `packages/haywire-core/src/haywire/ui/widget/converters.py` | `BindingConverter` ABC, `PrimitiveUnwrappingConverter`, `RangeValidatingConverter`, `CompositeConverter`, `Converters` facade. Orphans removed. | **Trim** |
| `packages/haywire-core/src/haywire/ui/widget/simple.py` | (was `SimpleWidget`) | **Delete** |
| `packages/haywire-core/src/haywire/ui/widget/interface.py` | `IWidget` minimal contract | Edit docstring (drop SimpleWidget mention) |
| `barn/haybale-core/haybale_core/widgets/basic_widgets.py` | 7 production primitive widgets | **Migrate** to BaseWidget |
| `barn/haybale-example/haybale_example/widgets/{example_widget,knob_widget}.py` | demo widgets | **Migrate** to new API |
| `barn/haybale-visiongraph/.../opencv_viewer_widget.py` | streaming viewer (floor-only) | **Migrate** to BaseWidget |
| `tests/ui/widget/_sync_fixtures.py` | shared sync-path scaffolding | **Rewrite** (drop SimpleWidget shapes) |
| `tests/ui/widget/test_sync_path_parity.py` | parity / double-activation guard | **Retarget** to `bind()` |
| `docs/components/widgets/widget-canon.md` | widget authoring guide | **Rewrite** (Phase 5) |
| `docs/guides/ports.md`, `docs/reference/glossary.md`, `mkdocs.yml` | inbound references | Edit (Phase 5) |

**Sequencing rationale:** Phase 1 (trim dead code) is pure deletion, lowest risk, behavior-preserving. Phase 2 builds the new `BaseWidget` API beside the old one. Phase 3 migrates all widgets. Phase 4 deletes `SimpleWidget`. Phase 5 rewrites docs **after all code lands**, so docs describe shipped reality.

---

# PHASE 1 — Trim dead "Pile B" machinery (pure deletion, behavior-preserving)

Nested-property navigation is **kept** (Pile A — Vector/Matrix need it). Cut only the provably-dead: debounce/trigger variants, the `validation`/`on_error` callback path, and four orphan converters.

### Task 1: Remove the debounce / UpdateTrigger machinery from PropertyBinding

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/widget/binding.py`

- [ ] **Step 1: Confirm zero callers of the trigger/debounce features.**

Run:
```bash
grep -rn "UpdateTrigger\|update_trigger\|update_delay\|DEBOUNCED\|ON_BLUR\|ON_ENTER\|_debounce_timer" barn/ packages/ tests/ | grep -v "packages/haywire-core/src/haywire/ui/widget/" | grep -v ".pyc"
```
Expected: no output (no callers outside the widget module itself). If any appear, STOP and report — they must be migrated first.

- [ ] **Step 2: Delete the debounce timer field.**

In `binding.py`, remove the `_debounce_timer` field from the `PropertyBinding` dataclass (currently around line 61):
```python
    _debounce_timer: Optional[threading.Timer] = field(default=None, init=False, repr=False)
```
Also remove `import threading` (top of file) if no longer used.

- [ ] **Step 3: Delete `update_trigger` and `update_delay` fields.**

Remove from the dataclass body:
```python
    update_trigger: UpdateTrigger = UpdateTrigger.IMMEDIATE
    ...
    update_delay: float = 0.0
```

- [ ] **Step 4: Simplify `_setup_view_to_model` to immediate-only.**

Replace the trigger-branching `_setup_view_to_model` body with the immediate path only:
```python
    def _setup_view_to_model(self) -> None:
        """Setup View → Model data flow (immediate update on the target event)."""
        handler = self._create_immediate_handler()
        assert self._ui_element is not None
        ui_element = self._ui_element
        ui_element.on(self.target_event, handler)
        self._cleanup_callbacks.append(
            lambda: self._safe_remove_handler(ui_element, self.target_event, handler)
        )
```

- [ ] **Step 5: Delete `_create_debounced_handler`.**

Remove the entire `_create_debounced_handler` method.

- [ ] **Step 6: Remove debounce-timer teardown from `deactivate`.**

In `deactivate`, delete:
```python
        if self._debounce_timer:
            self._debounce_timer.cancel()
            self._debounce_timer = None
```

- [ ] **Step 7: Remove the `UpdateTrigger` import.**

In `binding.py`, remove `UpdateTrigger` from the `from haywire.ui.widget.converters import (...)` block.

- [ ] **Step 8: Run the existing parity test — behavior must be unchanged.**

Run:
```bash
uv run pytest tests/ui/widget/test_sync_path_parity.py -v
```
Expected: PASS (debounce was never on the tested path).

- [ ] **Step 9: Commit.**

```bash
git add packages/haywire-core/src/haywire/ui/widget/binding.py
git commit -m "refactor(ui/widget): drop dead debounce/UpdateTrigger machinery from PropertyBinding"
```

### Task 2: Remove the validation / on_error callback path from PropertyBinding

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/widget/binding.py`

- [ ] **Step 1: Confirm zero callers pass `validation=` or `on_error=`.**

Run:
```bash
grep -rn "on_error\|validation=" barn/ packages/ tests/ | grep -v "packages/haywire-core/src/haywire/ui/widget/" | grep -v "ui/panel/render_utils" | grep -v "core/assembly"
```
Expected: no output. (`render_utils.py` `validation=` is NiceGUI's native arg — unrelated. `core/assembly` is graph validation — unrelated.)

- [ ] **Step 2: Delete the `validation` and `on_error` dataclass fields.**

In `PropertyBinding`, remove:
```python
    validation: Optional[Callable[[Any], tuple[bool, Optional[str]]]] = None
    on_error: Optional[Callable[[str], None]] = None
```

- [ ] **Step 3: Strip `on_error` guards from `_sync_to_view`.**

Replace the `try/except` in `_sync_to_view` so the except re-raises nothing silently. New body:
```python
    def _sync_to_view(self) -> None:
        """Synchronize model value to view."""
        assert self._element is not None and self.converter is not None
        if self.source_property == "value":
            model_value = self._element.get_value()
        else:
            field = self._element._data
            if isinstance(field, BaseField):
                container = field._container
                model_value = self._navigate_path(container, self.source_property)
            elif isinstance(field, PrimitiveField):
                raise ValueError(
                    f"PrimitiveField only supports source_property='value', got '{self.source_property}'"
                )
            else:
                raise ValueError(f"Property navigation not supported for {type(field).__name__}")

        view_value = self.converter.to_view(model_value)
        setattr(self._ui_element, self.target_property, view_value)
```

- [ ] **Step 4: Strip validation + on_error from `_sync_to_model`.**

Replace `_sync_to_model` body (keep `converter.validate()` as the sole remaining reject mechanism, but drop the callbacks):
```python
    def _sync_to_model(self, view_value: Any) -> None:
        """Synchronize view value to model."""
        assert self._element is not None and self.converter is not None
        is_valid, _error_msg = self.converter.validate(view_value)
        if not is_valid:
            return

        model_value = self.converter.to_model(view_value)

        if self.source_property == "value":
            self._element.set_value(model_value)
        else:
            self._update_nested_property(self.source_property, model_value)
```

- [ ] **Step 5: Remove the now-unused `Callable` import if nothing else uses it.**

Run:
```bash
grep -n "Callable" packages/haywire-core/src/haywire/ui/widget/binding.py
```
If `Callable` still appears in `_cleanup_callbacks: List[Callable]` or handler return types, keep the import. Otherwise remove it.

- [ ] **Step 6: Run parity test.**

Run:
```bash
uv run pytest tests/ui/widget/test_sync_path_parity.py -v
```
Expected: PASS.

- [ ] **Step 7: Type-check the trimmed module.**

Run:
```bash
uv run mypy packages/haywire-core/src/haywire/ui/widget/binding.py
```
Expected: clean.

- [ ] **Step 8: Commit.**

```bash
git add packages/haywire-core/src/haywire/ui/widget/binding.py
git commit -m "refactor(ui/widget): drop dead validation/on_error callback path (re-addable as bind kwargs)"
```

### Task 3: Remove orphan converters

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/widget/converters.py`

- [ ] **Step 1: Confirm the orphan converters have no callers.**

Run:
```bash
grep -rn "PropertyPathConverter\|ExtractorConverter\|IdentityConverter\|FormattingConverter\|Converters.identity\|Converters.format\|Converters.property_path\|Converters.extractor" barn/ packages/ tests/ | grep -v "ui/widget/converters.py" | grep -v ".pyc"
```
Expected: no output (these are docstring-only). If any real caller appears, STOP and report.

- [ ] **Step 2: Delete the four orphan converter classes.**

Remove from `converters.py`: `IdentityConverter`, `FormattingConverter`, `PropertyPathConverter`, `ExtractorConverter` (whole class bodies).

- [ ] **Step 3: Delete their facade methods on `Converters`.**

Remove the `identity()`, `format()`, `property_path()`, and `extractor()` static methods from the `Converters` class. Keep `primitive()`, `range()`, and `chain()`.

- [ ] **Step 4: Remove now-unused imports.**

Run:
```bash
uv run ruff check packages/haywire-core/src/haywire/ui/widget/converters.py --fix
```
Expected: removes any imports orphaned by the deletions (e.g. `Callable` if only `format` used it).

- [ ] **Step 5: Verify the kept converters still import and the demo still references valid names.**

Run:
```bash
uv run python -c "from haywire.ui.widget.converters import BindingConverter, PrimitiveUnwrappingConverter, RangeValidatingConverter, CompositeConverter, Converters, BindingMode; print('ok')"
```
Expected: `ok`.

- [ ] **Step 6: Type-check.**

Run:
```bash
uv run mypy packages/haywire-core/src/haywire/ui/widget/converters.py
```
Expected: clean.

- [ ] **Step 7: Commit.**

```bash
git add packages/haywire-core/src/haywire/ui/widget/converters.py
git commit -m "refactor(ui/widget): remove orphan converters (PropertyPath/Extractor/Identity/Formatting)"
```

---

# PHASE 2 — Build the unified BaseWidget API

Add the new floor + `bind()` sugar to `BaseWidget`, with final `cleanup`/dispatch and single-activation timing. Build it TDD-first against the existing fixture scaffolding.

### Task 4: Add the `on_model_changed` floor hook + final dispatch to BaseWidget

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/widget/base.py`
- Test: `tests/ui/widget/test_base_floor.py` (create)

- [ ] **Step 1: Write the failing test for the floor dispatch hook.**

Create `tests/ui/widget/test_base_floor.py`:
```python
import haywire.core.graph.editor  # noqa: F401  (circular-import guard, see CLAUDE.md)

import pytest
from typing import Any

from haywire.ui.widget.base import BaseWidget
from tests.ui.widget._sync_fixtures import make_float_port, _StandInElement

pytestmark = pytest.mark.unit


class _FloorWidget(BaseWidget):
    """Floor-only widget: no bind(), records every model change."""

    def __init__(self, port):
        super().__init__(port)
        self.seen: list[Any] = []

    def build(self) -> Any:
        return _StandInElement()

    def on_model_changed(self, value: Any) -> None:
        self.seen.append(value)


def test_on_model_changed_fires_on_port_change_and_at_render():
    port = make_float_port()
    port.set_value(7.0)
    w = _FloorWidget(port)
    w.render()
    assert w.seen[-1] == 7.0           # initial sync at render
    port.set_value(9.0)
    assert w.seen[-1] == 9.0           # subsequent change dispatched
```

- [ ] **Step 2: Run it — expect failure.**

Run:
```bash
uv run pytest tests/ui/widget/test_base_floor.py -v
```
Expected: FAIL (`BaseWidget` has abstract `configure_bindings`/`create_element`, no `build`/`on_model_changed`/floor dispatch yet).

- [ ] **Step 3: Rewrite `BaseWidget` with the floor + final dispatch.**

Replace the body of `base.py` with:
```python
from abc import ABC, abstractmethod
import logging
from typing import Any, Optional

from haywire.core.types import DataPort
from haywire.ui.widget.binding import PropertyBinding
from haywire.ui.widget.converters import BindingConverter, BindingMode, PrimitiveUnwrappingConverter
from haywire.ui.widget.interface import IWidget


class BaseWidget(IWidget, ABC):
    """The single canonical widget base.

    Floor (always available, serves any BaseType):
      - ``build()``            : construct & return the NiceGUI root element.
      - ``on_model_changed(v)``: override for arbitrary model→view sync. Fires on
                                 every port change and once at render. Default
                                 refreshes any ``bind()``-registered bindings.

    Sugar (flat-scalar convenience):
      - ``bind(element, to=...)``: register a two-way (or one-way) binding from a
                                   model field to a NiceGUI element property.
    """

    def __init__(self, port: DataPort):
        self.port = port
        self.port_id: str = port.id
        widget_config = port.widget_config if hasattr(port, "widget_config") and port.widget_config else {}
        self._config: dict[str, Any] = widget_config

        self.ui_element: Optional[Any] = None
        self._bindings: list[PropertyBinding] = []
        self._model_dispatch_cb: Optional[Any] = None
        self._cleaned_up: bool = False
        self.logger = logging.getLogger(__name__)

    # ---- FLOOR ----------------------------------------------------------
    @abstractmethod
    def build(self) -> Any:
        """Construct and return the NiceGUI root element for this widget."""
        ...

    def get_value(self) -> Any:
        return self.port.get_value()

    def set_value(self, value: Any) -> None:
        self.port.set_value(value)

    def on_model_changed(self, value: Any) -> None:
        """Override for custom model→view sync. Default drives bind()-ings.

        Subclasses that override should call ``super().on_model_changed(value)``
        to keep their bind()-registered elements live, or omit the super() call
        to take full ownership of sync.
        """
        for binding in self._bindings:
            binding._sync_to_view()

    # ---- SUGAR ----------------------------------------------------------
    def bind(
        self,
        element: Any,
        *,
        to: str = "value",
        prop: str = "value",
        event: str = "update:modelValue",
        converter: Optional[BindingConverter] = None,
        one_way: bool = False,
    ) -> Any:
        """Register a binding from model field ``to`` to ``element.prop``.

        ``to="value"`` (default) binds the whole port value (primitive case).
        ``to="x"`` / ``to="position.x"`` navigates a BaseType field path.
        Returns ``element`` so it composes inside ``with ui.row():`` blocks.
        """
        binding = PropertyBinding(
            source_property=to,
            target_property=prop,
            target_event=event,
            converter=converter or PrimitiveUnwrappingConverter(),
            mode=BindingMode.ONE_WAY if one_way else BindingMode.TWO_WAY,
        )
        binding._pending_element = element  # activated once, in render()
        self._bindings.append(binding)
        return element

    # ---- RENDER + LIFECYCLE (final) -------------------------------------
    def render(self) -> Any:
        """Build the element, activate bindings exactly once, wire dispatch."""
        if self.ui_element is None:
            self.ui_element = self.build()

            # Activate each bind()-ed binding once, against its pending element.
            for binding in self._bindings:
                binding.activate(self.port, binding._pending_element)

            # Single model→view dispatch channel → on_model_changed.
            self._model_dispatch_cb = lambda _: self.on_model_changed(self.port.get_value())
            self.port._data.on_changed += self._model_dispatch_cb

            # Initial sync.
            self.on_model_changed(self.port.get_value())

            if hasattr(self.ui_element, "client"):
                self.ui_element.client.on_disconnect(self.cleanup)

        return self.ui_element

    def cleanup(self) -> None:
        """Final teardown. Drops the dispatch subscription, deactivates bindings,
        then calls the subclass hook ``_on_cleanup()``. Idempotent."""
        if self._cleaned_up:
            return
        if self._model_dispatch_cb is not None and self.port is not None:
            try:
                self.port._data.on_changed -= self._model_dispatch_cb
            except Exception as e:
                self.logger.warning(f"Failed to drop model dispatch: {e}", exc_info=True)
        self._model_dispatch_cb = None

        for binding in self._bindings:
            binding.deactivate()
        self._bindings.clear()

        self._on_cleanup()

        self.ui_element = None
        self._cleaned_up = True

    def _on_cleanup(self) -> None:
        """Override to release subclass-owned resources (e.g. a backend).
        Called by the final ``cleanup()``; do NOT override ``cleanup()`` itself."""
        ...
```

- [ ] **Step 4: Add the `_pending_element` slot to `PropertyBinding`.**

In `binding.py`, add to the internal-state fields of the dataclass:
```python
    _pending_element: Optional[Any] = field(default=None, init=False, repr=False)
```

- [ ] **Step 5: Run the floor test — expect pass.**

Run:
```bash
uv run pytest tests/ui/widget/test_base_floor.py -v
```
Expected: PASS.

- [ ] **Step 6: Commit.**

```bash
git add packages/haywire-core/src/haywire/ui/widget/base.py packages/haywire-core/src/haywire/ui/widget/binding.py tests/ui/widget/test_base_floor.py
git commit -m "feat(ui/widget): BaseWidget floor — build() + on_model_changed() + final cleanup"
```

### Task 5: Test the `bind()` sugar — primitive (`to="value"`) and one-way

**Files:**
- Test: `tests/ui/widget/test_bind_sugar.py` (create)

- [ ] **Step 1: Write the failing test.**

Create `tests/ui/widget/test_bind_sugar.py`:
```python
import haywire.core.graph.editor  # noqa: F401

import pytest
from typing import Any

from haywire.ui.widget.base import BaseWidget
from tests.ui.widget._sync_fixtures import make_float_port, _StandInElement

pytestmark = pytest.mark.unit


class _PrimitiveWidget(BaseWidget):
    def build(self) -> Any:
        self.el = _StandInElement()
        return self.bind(self.el)            # to="value" default


class _ReadonlyWidget(BaseWidget):
    def build(self) -> Any:
        self.el = _StandInElement()
        return self.bind(self.el, prop="text", one_way=True)


def test_primitive_bind_two_way_model_to_view():
    port = make_float_port()
    port.set_value(3.0)
    w = _PrimitiveWidget(port)
    w.render()
    assert w.el.value == 3.0
    port.set_value(5.0)
    assert w.el.value == 5.0


def test_primitive_bind_two_way_view_to_model():
    port = make_float_port()
    w = _PrimitiveWidget(port)
    w.render()
    w.el.value = 8.0
    # simulate the UI event the binding listens for
    w._bindings[0]._sync_to_model(8.0)
    assert port.get_value() == 8.0


def test_readonly_bind_does_not_write_model():
    port = make_float_port()
    w = _ReadonlyWidget(port)
    w.render()
    # one-way: no view→model handler registered; model stays None/default
    assert port.get_value() is None or port.get_value() == 0.0
```

- [ ] **Step 2: Run — expect pass (the API from Task 4 already supports this).**

Run:
```bash
uv run pytest tests/ui/widget/test_bind_sugar.py -v
```
Expected: PASS. If `test_readonly_bind_does_not_write_model` fails, verify `BindingMode.ONE_WAY` skips `_setup_view_to_model` in `binding.py` `activate()` (it should — only `TWO_WAY` sets up view→model).

- [ ] **Step 3: Commit.**

```bash
git add tests/ui/widget/test_bind_sugar.py
git commit -m "test(ui/widget): bind() sugar — primitive two-way + one-way readonly"
```

### Task 6: Test the `bind()` sugar — nested field path (`to="x"`) with a stand-in BaseType

**Files:**
- Test: `tests/ui/widget/test_bind_nested.py` (create)

- [ ] **Step 1: Write the failing test using a minimal BaseType.**

Create `tests/ui/widget/test_bind_nested.py`:
```python
import haywire.core.graph.editor  # noqa: F401

import pytest
from dataclasses import dataclass
from typing import Any

from haywire.core.types.base import BaseType
from haywire.core.types.port import DataPort
from haywire.core.types.enums import FlowType, PortType
from haywire.ui.widget.base import BaseWidget
from tests.ui.widget._sync_fixtures import _StandInElement

pytestmark = pytest.mark.unit


@dataclass
class _Vec2(BaseType):
    x: float = 0.0
    y: float = 0.0


def _vec2_port() -> DataPort:
    return DataPort(
        registry_id="vec2",
        registry_key="test:type:vec2",
        label="V",
        id="v",
        type_cls=_Vec2,
        port_type=PortType.INLET,
        flow_type=FlowType.DATA,
    )


class _Vec2Widget(BaseWidget):
    def build(self) -> Any:
        self.ex = _StandInElement()
        self.ey = _StandInElement()
        self.bind(self.ex, to="x")
        self.bind(self.ey, to="y")
        return self.ex


def test_nested_field_path_model_to_view():
    port = _vec2_port()
    port.set_value(_Vec2(x=1.0, y=2.0))
    w = _Vec2Widget(port)
    w.render()
    assert w.ex.value == 1.0
    assert w.ey.value == 2.0
```

- [ ] **Step 2: Run — expect pass (nested-path engine was kept in Phase 1).**

Run:
```bash
uv run pytest tests/ui/widget/test_bind_nested.py -v
```
Expected: PASS. If the `_navigate_path` raises, confirm `_Vec2` is a `BaseField`-backed type (it is — `BaseType` subclasses use `BaseField`).

- [ ] **Step 3: Commit.**

```bash
git add tests/ui/widget/test_bind_nested.py
git commit -m "test(ui/widget): bind(to='x') nested field-path binding for BaseType"
```

### Task 7: Prove the double-activation bug is designed out

**Files:**
- Test: `tests/ui/widget/test_single_activation.py` (create)

- [ ] **Step 1: Write the failing test asserting exactly one subscription after render.**

Create `tests/ui/widget/test_single_activation.py`:
```python
import haywire.core.graph.editor  # noqa: F401

import pytest
from typing import Any

from haywire.ui.widget.base import BaseWidget
from tests.ui.widget._sync_fixtures import make_float_port, _StandInElement

pytestmark = pytest.mark.unit


class _OneBind(BaseWidget):
    def build(self) -> Any:
        self.el = _StandInElement()
        return self.bind(self.el)


def test_render_subscribes_once_and_cleanup_removes_it():
    port = make_float_port()
    w = _OneBind(port)
    before = len(port._data.on_changed)
    w.render()
    after = len(port._data.on_changed)
    # exactly one dispatch subscription added (no double-activation)
    assert after - before == 1
    w.cleanup()
    assert len(port._data.on_changed) == before
    assert w._cleaned_up is True


def test_render_is_idempotent():
    port = make_float_port()
    w = _OneBind(port)
    w.render()
    n = len(port._data.on_changed)
    w.render()  # second call must not re-subscribe
    assert len(port._data.on_changed) == n
```

- [ ] **Step 2: Run — expect pass.**

Run:
```bash
uv run pytest tests/ui/widget/test_single_activation.py -v
```
Expected: PASS. (`Event` supports `len()`; if not, substitute the project's observer-count accessor — check `haywire/core/events` for `has_observers`/length.)

- [ ] **Step 3: Verify the `Event` length accessor exists; adapt if needed.**

Run:
```bash
grep -n "def __len__\|has_observers\|self._observers\|self._handlers" packages/haywire-core/src/haywire/core/events/*.py
```
If `__len__` is absent, replace `len(port._data.on_changed)` in the test with the available accessor (e.g. `port._data.on_changed.has_observers()` returning bool — then assert presence/absence rather than count).

- [ ] **Step 4: Commit.**

```bash
git add tests/ui/widget/test_single_activation.py
git commit -m "test(ui/widget): prove single-activation + clean teardown (no double-subscribe)"
```

### Task 8: Remove the old `add_binding` / `configure_bindings` / `create_element` API surface

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/widget/base.py` (already rewritten in Task 4 — verify no remnants)
- Modify: `packages/haywire-core/src/haywire/ui/widget/binding.py`

- [ ] **Step 1: Confirm the old methods are gone from base.py.**

Run:
```bash
grep -n "add_binding\|configure_bindings\|create_element\|create_default_binding\|_ui_element_refs\|_activate_all_bindings" packages/haywire-core/src/haywire/ui/widget/base.py
```
Expected: no output. (Task 4's rewrite already dropped them. If any remain, remove them.)

- [ ] **Step 2: Remove the `_navigate_path`/`_update_nested_property` dead branches' callers check.**

These stay (Pile A), but confirm they're only reached via `bind(to=...)`. Run:
```bash
uv run pytest tests/ui/widget/test_bind_nested.py -v
```
Expected: PASS (proves the kept engine is reachable through the new API).

- [ ] **Step 3: Commit (if any edits were needed; otherwise skip).**

```bash
git add packages/haywire-core/src/haywire/ui/widget/base.py packages/haywire-core/src/haywire/ui/widget/binding.py
git commit -m "refactor(ui/widget): drop legacy add_binding/configure_bindings surface"
```

---

# PHASE 3 — Migrate all widgets to the unified API

### Task 9: Migrate the 7 primitive widgets in basic_widgets.py

**Files:**
- Modify: `barn/haybale-core/haybale_core/widgets/basic_widgets.py`

- [ ] **Step 1: Replace the import.**

Change line 9 from:
```python
from haywire.ui.widget.simple import SimpleWidget
```
to:
```python
from haywire.ui.widget.base import BaseWidget
```

- [ ] **Step 2: Migrate `NumberWidget`.**

Replace its class body:
```python
@widget(description="Fast number input widget", compatible_types=[FLOAT, INT])
class NumberWidget(BaseWidget):
    """Blender-style number input widget for float and int ports. (docstring unchanged)"""

    def build(self) -> Any:
        props = self._config.get("properties", {})
        kwargs: dict[str, Any] = {"value": 0}
        for prop in ["min", "max", "step", "precision", "prefix", "suffix", "sensitivity"]:
            if prop in props:
                kwargs[prop] = props[prop]
        return self.bind(NumberDrag(**kwargs).classes("w-full"))
```
(Keep the existing docstring text verbatim. `get_default_value` is gone — `None` from an unset port now flows through the converter's `default_value`; NumberDrag already starts at `value=0`.)

- [ ] **Step 3: Migrate `TextWidget`.**

```python
@widget(description="Fast text input widget", compatible_types=[STRING])
class TextWidget(BaseWidget):
    """(docstring unchanged)"""

    def build(self) -> Any:
        props = self._config.get("properties", {})
        return self.bind(ui.input(
            value="",
            label=props.get("label", ""),
            placeholder=props.get("placeholder", ""),
            password=props.get("password", False),
        ).classes("w-full"))
```

- [ ] **Step 4: Migrate `CheckboxWidget` and `SwitchWidget`.**

```python
@widget(description="checkbox widget", compatible_types=[BOOL])
class CheckboxWidget(BaseWidget):
    """(docstring unchanged)"""

    def build(self) -> Any:
        props = self._config.get("properties", {})
        return self.bind(ui.checkbox(value=False, text=props.get("text", "")).classes("w-full"))


@widget(description="switch widget", compatible_types=[BOOL])
class SwitchWidget(BaseWidget):
    """(docstring unchanged)"""

    def build(self) -> Any:
        props = self._config.get("properties", {})
        return self.bind(ui.switch(value=False, text=props.get("text", "")).classes("w-full text-xs"))
```

- [ ] **Step 5: Migrate `SliderWidget`.**

```python
@widget(description="slider widget", compatible_types=[FLOAT, INT])
class SliderWidget(BaseWidget):
    """(docstring unchanged)"""

    def build(self) -> Any:
        props = self._config.get("properties", {})
        kwargs: dict[str, Any] = {
            "value": 0,
            "min": props.get("min", 0),
            "max": props.get("max", 100),
            "step": props.get("step", 1),
        }
        return self.bind(ui.slider(**kwargs).classes("w-full text-xs").props("label-always"))
```

- [ ] **Step 6: Migrate `SelectWidget`.**

```python
@widget(description="select widget", compatible_types=[INT, STRING])
class SelectWidget(BaseWidget):
    """(docstring unchanged)"""

    def build(self) -> Any:
        props = self._config.get("properties", {})
        kwargs: dict[str, Any] = {"options": props.get("options", []), "value": None}
        for prop in ["clearable", "multiple"]:
            if prop in props:
                kwargs[prop] = props[prop]
        return self.bind(ui.select(**kwargs).classes("w-full text-xs"))
```

- [ ] **Step 7: Migrate `SimpleLabelWidget` (readonly, `text` prop).**

```python
@widget(description="Simple label for display only", compatible_types=[STRING, FLOAT, INT])
class SimpleLabelWidget(BaseWidget):
    """(docstring unchanged)"""

    def build(self) -> Any:
        return self.bind(ui.label("").classes("text-base text-xs"), prop="text", one_way=True)
```

- [ ] **Step 8: Type-check the migrated module.**

Run:
```bash
uv run mypy barn/haybale-core/haybale_core/widgets/basic_widgets.py
```
Expected: clean.

- [ ] **Step 9: Run the integration suite that renders these widgets.**

Run:
```bash
uv run pytest tests/ -k "widget" -m "not perf"
```
Expected: PASS.

- [ ] **Step 10: Commit.**

```bash
git add barn/haybale-core/haybale_core/widgets/basic_widgets.py
git commit -m "feat(haybale-core): migrate 7 primitive widgets to unified BaseWidget API"
```

### Task 10: Migrate the OpencvViewerWidget (floor-only, `_on_cleanup`)

**Files:**
- Modify: `barn/haybale-visiongraph/haybale_visiongraph/widgets/opencv_viewer_widget.py`

- [ ] **Step 1: Replace the class with the floor-based implementation.**

```python
from typing import Any
from haybale_visiongraph.types.frame_type import FRAME
import numpy as np
from nicegui import ui

from haywire.ui.widget.base import BaseWidget
from haywire.ui.widget.decorator import widget

from haybale_visiongraph.widgets.components.streaming_viewer import StreamingBackend, StreamingViewer


@widget(description="Streaming video viewer for numpy arrays", compatible_types=[FRAME])
class OpencvViewerWidget(BaseWidget):
    """Displays numpy arrays as streaming MJPEG video inside a node.

    Config options (via ``OpencvViewerWidget.config(properties={...})``): see
    ``quality``, ``width``, ``height``, ``frame_queue_size``, ``block_on_full``.
    """

    def __init__(self, port):
        super().__init__(port)
        self._backend: StreamingBackend | None = None

    def build(self) -> Any:
        props = self._config.get("properties", {})
        if self._backend is None:
            self._backend = StreamingBackend(
                quality=props.get("quality", 80),
                frame_queue_size=props.get("frame_queue_size", 1),
                block_on_full=props.get("block_on_full", False),
            )
        width = props.get("width", "100%")
        height = props.get("height", "auto")
        with ui.card().classes("w-full") as container:
            StreamingViewer(self._backend).style(f"width: {width}; height: {height};")
        return container

    def on_model_changed(self, frame: Any) -> None:
        if self._backend is None or not self._backend._is_running:
            return
        frame_data = frame.data if hasattr(frame, "data") else frame
        if isinstance(frame_data, np.ndarray) and frame_data.size:
            try:
                self._backend.stream(frame_data)
            except Exception as e:
                if self._backend and self._backend._is_running:
                    print(f"[OpencvViewerWidget] Error streaming frame: {e}")

    def _on_cleanup(self) -> None:
        if self._backend:
            try:
                self._backend.cleanup()
            except Exception as e:
                print(f"[OpencvViewerWidget] Viewer cleanup warning: {e}")
            self._backend = None
```

Note: it does **not** call `super().on_model_changed()` — it has no `bind()`-ings, so it owns sync entirely. It does **not** override `cleanup()` — the final base handles the subscription drop, then calls `_on_cleanup()`.

- [ ] **Step 2: Type-check.**

Run:
```bash
uv run mypy barn/haybale-visiongraph/haybale_visiongraph/widgets/opencv_viewer_widget.py
```
Expected: clean. (Note: `haybale-visiongraph` is a local symlink — if mypy can't resolve it, run the import smoke test instead in Step 3.)

- [ ] **Step 3: Smoke-test import.**

Run:
```bash
uv run python -c "from haybale_visiongraph.widgets.opencv_viewer_widget import OpencvViewerWidget; print('ok')"
```
Expected: `ok`.

- [ ] **Step 4: Commit.**

```bash
git add barn/haybale-visiongraph/haybale_visiongraph/widgets/opencv_viewer_widget.py
git commit -m "feat(haybale-visiongraph): migrate OpencvViewerWidget to BaseWidget floor"
```

### Task 11: Migrate the demo widgets (knob + example)

**Files:**
- Modify: `barn/haybale-example/haybale_example/widgets/knob_widget.py`
- Modify: `barn/haybale-example/haybale_example/widgets/example_widget.py`

- [ ] **Step 1: Read the knob widget to get its exact current body.**

Run:
```bash
sed -n '1,60p' barn/haybale-example/haybale_example/widgets/knob_widget.py
```

- [ ] **Step 2: Migrate `KnobWidget` to BaseWidget.**

Change its base import to `BaseWidget`, rename `create_element` → `build`, and wrap the returned element in `self.bind(...)`. The `ui.knob` uses default `value`/`update:modelValue`, so:
```python
    def build(self) -> Any:
        props = self._config.get("properties", {})
        kwargs: dict[str, Any] = {"value": 0}
        for prop in ["min", "max", "step", "color", "size"]:
            if prop in props:
                kwargs[prop] = props[prop]
        return self.bind(ui.knob(**kwargs))
```
Remove `get_default_value` (handled by converter default).

- [ ] **Step 3: Migrate `ValidatedNumberWidget` (example_widget.py).**

```python
@widget(description="Number widget with range clamping", compatible_types=[FLOAT, INT])
class ValidatedNumberWidget(BaseWidget):
    def build(self) -> Any:
        props = self._config.get("properties", {})
        el = ui.number(
            value=0, label=props.get("label", ""), min=props.get("min"), max=props.get("max"),
            step=props.get("step", 1), precision=props.get("precision"),
            prefix=props.get("prefix", ""), suffix=props.get("suffix", ""),
        ).classes("w-full")
        min_val, max_val = props.get("min"), props.get("max")
        if min_val is not None or max_val is not None:
            return self.bind(el, converter=Converters.chain(
                Converters.primitive(default_value=0),
                Converters.range(min_value=min_val, max_value=max_val, clamp=True),
            ))
        return self.bind(el)
```

- [ ] **Step 4: Migrate `TemperatureWidget` (multi-element + converter + readonly display).**

```python
@widget(description="Temperature with unit conversion", compatible_types=[Temperature])
class TemperatureWidget(BaseWidget):
    def __init__(self, port):
        super().__init__(port)
        self.unit = self._config.get("properties", {}).get("unit", "celsius")

    def build(self) -> Any:
        with ui.column().classes("w-full") as root:
            temp_input = ui.number(
                value=0, suffix="°C" if self.unit == "celsius" else "°F", step=0.1, precision=1,
            ).classes("w-full")
            self.bind(temp_input, converter=UnitConversionConverter(self.unit))

            label = ui.label("").classes("text-sm text-gray-500")
            self.bind(label, prop="text", one_way=True, converter=ConversionDisplayConverter(self.unit))
        return root
```
(The two custom converter classes `UnitConversionConverter` / `ConversionDisplayConverter` stay unchanged at the bottom of the file.)

- [ ] **Step 5: Type-check / smoke-test the demo library.**

Run:
```bash
uv run python -c "import haybale_example.widgets.example_widget, haybale_example.widgets.knob_widget; print('ok')"
```
Expected: `ok`.

- [ ] **Step 6: Commit.**

```bash
git add barn/haybale-example/haybale_example/widgets/
git commit -m "feat(haybale-example): migrate demo widgets to unified BaseWidget API"
```

---

# PHASE 4 — Delete SimpleWidget and retarget shared tests

### Task 12: Retarget the sync-path fixtures and parity test to the unified base

**Files:**
- Modify: `tests/ui/widget/_sync_fixtures.py`
- Modify: `tests/ui/widget/test_sync_path_parity.py`
- Modify: `tests/ui/widget/test_sync_path_perf.py`

- [ ] **Step 1: Remove the `SimpleWidget` import and `SimpleFloatWidget` shape from `_sync_fixtures.py`.**

Delete `from haywire.ui.widget.simple import SimpleWidget`, the `SimpleFloatWidget` class, and the `build_simple()` builder. Update the module docstring to drop the "vs SimpleWidget" framing — it now scaffolds the unified-base sync path only.

- [ ] **Step 2: Rewrite the remaining fixture shapes onto the new `bind()` API.**

Replace `BaseDefaultFloatWidget` / `BaseConverterFloatWidget` `configure_bindings` with `build()` + `bind()`:
```python
class BaseDefaultFloatWidget(BaseWidget):
    def build(self) -> Any:
        self.el = _StandInElement()
        return self.bind(self.el)

class BaseConverterFloatWidget(BaseWidget):
    def build(self) -> Any:
        self.el = _StandInElement()
        return self.bind(self.el, converter=Converters.chain(
            Converters.primitive(default_value=0),
            Converters.range(min_value=-1e9, max_value=1e9, clamp=True),
        ))
```
Update `_build_base` to call `w.build()` then activate `w._bindings[0]` against `w.el` (mirror the old logic but via the public single-binding list). Delete `_main_binding` (was for the old `_bindings` dict). Delete `build_simple` references.

- [ ] **Step 3: Update `test_sync_path_parity.py` to drop the Simple-vs-Base comparison.**

The parity test compared SimpleWidget against BaseWidget. With one base, repoint its assertions to verify the unified path's correctness (initial sync, model→view, view→model, readonly, cleanup-drops-subscription). Remove any `build_simple`/`SimpleWidget` references. Keep the cleanup/double-activation assertion (now covered also by `test_single_activation.py`).

- [ ] **Step 4: Update `test_sync_path_perf.py` to drop the `build_simple` baseline.**

The microbenchmark's `simple` arm is gone. Either delete the ratio assertion (perf is no longer a gate — see ADR-0007) or repoint it to compare default-bind vs converter-bind only. Simplest: keep `base_default` and `base_converter` timings as informational prints, drop the `simple` arm and the `assert default <= 1.5 * simple` line.

- [ ] **Step 5: Run the retargeted tests.**

Run:
```bash
uv run pytest tests/ui/widget/ -m "not perf" -v
uv run pytest tests/ui/widget/ -m perf -s
```
Expected: unit tests PASS; perf prints its table (no hard ratio gate).

- [ ] **Step 6: Commit.**

```bash
git add tests/ui/widget/_sync_fixtures.py tests/ui/widget/test_sync_path_parity.py tests/ui/widget/test_sync_path_perf.py
git commit -m "test(ui/widget): retarget sync-path fixtures/parity/perf to unified BaseWidget"
```

### Task 13: Delete simple.py and purge all SimpleWidget references

**Files:**
- Delete: `packages/haywire-core/src/haywire/ui/widget/simple.py`
- Modify: `packages/haywire-core/src/haywire/ui/widget/interface.py`

- [ ] **Step 1: Find every remaining reference to SimpleWidget.**

Run:
```bash
grep -rn "SimpleWidget\|widget.simple\|from haywire.ui.widget.simple" packages/ barn/ tests/ docs/ | grep -v ".pyc"
```
Expected after Phases 1–3: only `interface.py` (docstring) and possibly `widget-canon.md`/glossary (handled in Phase 5). If any **code** reference remains outside `interface.py`, fix it before deleting.

- [ ] **Step 2: Delete the file.**

Run:
```bash
git rm packages/haywire-core/src/haywire/ui/widget/simple.py
```

- [ ] **Step 3: Update the `IWidget` docstring in interface.py.**

Replace the "Use SimpleWidget for… / Use BaseWidget for…" lines (around line 19-22) with:
```python
    """
    Minimal widget interface.

    Subclass ``BaseWidget`` for the standard authoring surface (``build()`` plus
    the ``bind()`` sugar / ``on_model_changed()`` floor). Implement ``IWidget``
    directly only for a fully custom widget that needs neither.
    """
```

- [ ] **Step 4: Full type-check of all type-checked packages (CLAUDE.md command).**

Run:
```bash
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-TEST_A/haybale_test_a/
```
Expected: clean.

- [ ] **Step 5: Commit.**

```bash
git add packages/haywire-core/src/haywire/ui/widget/interface.py
git commit -m "refactor(ui/widget): delete SimpleWidget — BaseWidget is the sole base"
```

### Task 14: Full-suite green gate

**Files:** none (verification only)

- [ ] **Step 1: Run the full quality suite (CLAUDE.md mandate after multi-file change).**

Run:
```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-TEST_A/haybale_test_a/
uv run pytest -m "not integration"
uv run pytest -m integration
```
Expected: all clean / all pass. Fix any fallout before proceeding to docs. If `ruff format --check` reports drift, run `uv run ruff format .` and amend the relevant commit.

- [ ] **Step 2: Commit any formatting fixups.**

```bash
git add -u
git commit -m "style(ui/widget): ruff format after unification"
```

---

# PHASE 5 — Rewrite the docs to the new reality (after all code has landed)

> Per the spec: this is a big-bang change with no migration. Docs describe **only** the new reality — no `SimpleWidget`, no "graduate from X to Y", no before/after, no reference to the old approach. Write as if the unified `BaseWidget` is how it has always been.

### Task 15: Rewrite widget-canon.md

**Files:**
- Modify (rewrite): `docs/components/widgets/widget-canon.md`

- [ ] **Step 1: Verify the canonical-example doc template to follow.**

Run:
```bash
sed -n '1,15p' docs/components/datatypes/datatype-canon.md
```
Match its frontmatter shape (`status`, `doc_template: canonical-example`, `scope`, `see-also`) and section structure (`## 1. What it solves`, `## 2. How it fits`, `## 3. Important concepts`, `## 4. Live example`, `## Quick reference`).

- [ ] **Step 2: Rewrite the frontmatter and section 1–2.**

Replace the top of `widget-canon.md`:
```markdown
---
status: stable
doc_template: canonical-example
scope: Authoring widgets — BaseWidget subclasses, the @widget decorator, the build()/bind() surface, the on_model_changed() floor, lifecycle
see-also:
  - ../datatypes/datatype-canon.md
  - ../../guides/ports.md
  - ../adapters/adapter-canon.md
  - ../../reference/glossary.md
---

# Widget — Canonical Example

## 1. What it solves

A **widget** is the inline UI control rendered inside a port on a node card. It
binds to the port's value: editing the control writes the port; a worker writing
the port updates the control. You author a widget so node authors declare a port
type and get the right control for free.

You author a widget when a datatype needs its own control (a `Color` picker, a
`Vector3` with three coupled inputs, a streaming image preview), or when you want
a richer control than the default for a type.

A widget is **not** an editor or a panel (those are workspace-level). A widget
lives inside a port row on a node card.

## 2. How it fits

\```text
@widget(compatible_types=[Vector3])  ──► WidgetRegistry ──► port renders the widget
class Vector3Widget(BaseWidget):                            when the canvas draws
    def build(self):                                        the node card
        with ui.row():
            self.bind(ui.number(), to="x")
            self.bind(ui.number(), to="y")
            self.bind(ui.number(), to="z")
\```

Every widget subclasses **`BaseWidget`** and implements **`build()`**. Inside
`build()` you either call the **`bind()`** sugar to wire a NiceGUI element to a
model field, or — for arbitrary widgets — override the **`on_model_changed()`**
floor hook and drive the view yourself. `BaseWidget` implements `IWidget`; the
`@widget` decorator registers `compatible_types` and attaches `class_identity`
for the registry / hot-reload.
```

- [ ] **Step 3: Rewrite section 3 (Important concepts) around the new model.**

Write these subsections (full prose, no placeholders):
- **The `@widget` decorator** — `compatible_types` list, `class_identity`, when a widget is offered for a port (port type in/inherits a compatible type). Reuse the existing accurate text.
- **`build()`** — required; construct and return the NiceGUI root element; call `bind()` inline as you create elements.
- **The `bind()` sugar** — signature `bind(element, *, to="value", prop="value", event="update:modelValue", converter=None, one_way=False)`. `to="value"` binds the whole port value (primitive case, the default); `to="x"` / `to="position.x"` navigates a `BaseType` field path. `prop`/`event` for elements that don't use `value`/`update:modelValue` (e.g. a label uses `prop="text"`). `one_way=True` for read-only display. Returns the element so it composes in `with ui.row():`.
- **The `on_model_changed()` floor** — override for whole-value or non-field widgets (image preview, swatch). Fires on every port change and once at render. Call `super().on_model_changed(value)` to keep `bind()`-ings live, or omit it to own sync entirely.
- **`config()` call-site pattern** — `Widget.config(properties={...})` returns the `{key, config}` dict passed to `as_inlet(widget=...)`. Unchanged.
- **`_on_cleanup()`** — override to release subclass resources (a backend, a timer). The base `cleanup()` is final: it drops the model subscription and deactivates bindings, then calls `_on_cleanup()`. Never override `cleanup()`.
- **Hot-reload** — `WidgetRegistry` re-registers on library reload; running widgets aren't swapped, new ones pick up the new class. (Reuse existing text.)
- **Imports:**
  ```python
  from haywire.ui.widget.base import BaseWidget
  from haywire.ui.widget.decorator import widget
  from haywire.ui.widget.binding import PropertyBinding   # only for advanced manual bindings
  from haywire.ui.widget.converters import Converters, BindingConverter
  ```

- [ ] **Step 4: Rewrite section 4 (Live example) to a real migrated widget.**

Point the example at `KnobWidget` (primitive `bind()`) and add a short multi-element snippet. Use the literal migrated `KnobWidget.build()` from Task 11. Keep the `as_inlet(widget=KnobWidget.config(...))` call-site example. Add a "multi-element" callout showing the `Vector3Widget.build()` three-`bind` pattern from section 2.

- [ ] **Step 5: Rewrite the Quick reference.**

Authoring checklist:
```markdown
- [ ] `@widget(description='...', compatible_types=[Type1, Type2])`
- [ ] Subclass `BaseWidget`, implement `build()` returning a NiceGUI element
- [ ] Call `self.bind(element, to=...)` for each value-bound element
- [ ] Use `prop=` / `event=` when the element isn't `value` / `update:modelValue`
- [ ] Use `one_way=True` for read-only display
- [ ] Override `on_model_changed()` (call `super()`) for whole-value / custom sync
- [ ] Override `_on_cleanup()` to release subclass resources
```
Common `prop` / `event` pairs table: keep the existing element rows but relabel the columns `prop` / `event` (not `UI_PROPERTY`/`UI_EVENT`). Remove the "graduate to BaseWidget" table and any SimpleWidget row.

- [ ] **Step 6: Confirm no stale vocabulary remains in the doc.**

Run:
```bash
grep -n "SimpleWidget\|create_element\|UI_PROPERTY\|UI_EVENT\|IS_READONLY\|configure_bindings\|add_binding\|graduate" docs/components/widgets/widget-canon.md
```
Expected: no output.

- [ ] **Step 7: Build the docs site to catch broken snippet includes / links.**

Run:
```bash
uv run mkdocs build --strict 2>&1 | tail -20
```
Expected: builds clean (no warnings on the widget page). Fix any `--8<--` include path or broken link it flags.

- [ ] **Step 8: Commit.**

```bash
git add docs/components/widgets/widget-canon.md
git commit -m "docs(widgets): rewrite widget-canon for the unified BaseWidget reality"
```

### Task 16: Update inbound references (ports guide, glossary, interface docstring already done)

**Files:**
- Modify: `docs/guides/ports.md`
- Verify: `docs/reference/glossary.md` (already updated this session — confirm consistency)

- [ ] **Step 1: Check ports.md for any old widget framing.**

Run:
```bash
grep -n "SimpleWidget\|create_element\|graduate\|widget_key\|widget_config\|widget-canon" docs/guides/ports.md
```
The `widget_key` / `widget_config` rows (lines ~62-63) and the `widget-canon` link (line ~42) are still accurate — leave them. Only edit if any line implies the two-base split or `SimpleWidget`. (Per the earlier scan, ports.md has no SimpleWidget reference — likely no change needed.)

- [ ] **Step 2: Confirm the glossary `BaseWidget` entry matches the shipped API.**

Run:
```bash
grep -n "BaseWidget\|SimpleWidget" docs/reference/glossary.md
```
Verify the `BaseWidget` row describes `build()` + `bind()`/`on_model_changed()` and notes `SimpleWidget` removed. The `Widget` and `ShowWidgetStrategy` rows are unaffected. If the row drifted from the final API (e.g. mentions a method that changed name), fix it to match `base.py`.

- [ ] **Step 3: Confirm no SimpleWidget anywhere in docs.**

Run:
```bash
grep -rn "SimpleWidget" docs/ | grep -v "adr/0007" | grep -v "plans/widget-unification-perf-verification"
```
Expected: no output. (ADR-0007 and the perf-verification plan are historical records — they legitimately name SimpleWidget and must NOT be edited; they document the decision/measurement, not current authoring.)

- [ ] **Step 4: Commit any edits.**

```bash
git add docs/guides/ports.md docs/reference/glossary.md
git commit -m "docs: align ports guide + glossary with unified widget API"
```

### Task 17: Mark the superseded planning docs and final docs gate

**Files:**
- Modify: `internals/handoff/widget-unification.md`
- Modify: `docs/plans/widget-unification-perf-verification.md`

- [ ] **Step 1: Add a superseded banner to the handoff.**

At the top of `internals/handoff/widget-unification.md`, under the title, add:
```markdown
> **SUPERSEDED (2026-06-09).** All open decisions in this handoff are resolved by
> [`docs/adr/0007-widget-unification-basewidget.md`](../../docs/adr/0007-widget-unification-basewidget.md)
> and implemented per
> [`docs/superpowers/plans/2026-06-09-widget-unification-basewidget.md`](../../docs/superpowers/plans/2026-06-09-widget-unification-basewidget.md).
> Retained as the measurement/analysis record only.
```

- [ ] **Step 2: Fill in the perf-verification results verdict.**

In `docs/plans/widget-unification-perf-verification.md`, append a closing note that the verdict was GREEN per Finding B (perf-irrelevant; no fast-path), and that unification proceeded under ADR-0007. Do not delete the plan — it is the measurement record.

- [ ] **Step 3: Final docs build.**

Run:
```bash
uv run mkdocs build --strict 2>&1 | tail -20
```
Expected: clean.

- [ ] **Step 4: Commit.**

```bash
git add internals/handoff/widget-unification.md docs/plans/widget-unification-perf-verification.md
git commit -m "docs: mark widget-unification handoff superseded; record GREEN perf verdict"
```

---

## Final verification (whole feature)

- [ ] **Step 1: One clean run of everything.**

Run:
```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-TEST_A/haybale_test_a/
uv run pytest -m "not integration"
uv run pytest -m integration
uv run mkdocs build --strict
```
Expected: all green.

- [ ] **Step 2: Confirm SimpleWidget is fully gone from code.**

Run:
```bash
grep -rn "SimpleWidget" packages/ barn/ tests/ | grep -v ".pyc"
```
Expected: no output.

---

## Notes / gotchas (from CLAUDE.md and the codebase)

- **Test-file convention:** `import haywire.core.graph.editor` first to avoid a circular import (every new test file above does this).
- **`haybale-visiongraph` is a gitignored local symlink** — excluded from the CI mypy command; use the import smoke test for it.
- **Perf tests are excluded by default** (`-m "not perf"` in addopts). Run explicitly with `-s` to see tables.
- **ADR-0007 and the perf-verification plan must NOT be scrubbed of "SimpleWidget"** — they are historical decision/measurement records. Only authoring-facing docs get the no-old-approach treatment.
- **`config()` lives on `IWidget`** (classmethod) — unchanged by this work; all `Widget.config(...)` call sites keep working.
- **`RangeValidatingConverter` / `CompositeConverter` are kept** (used by the demo's clamp path); only the four orphan converters are deleted.
