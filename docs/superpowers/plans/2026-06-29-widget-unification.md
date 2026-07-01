# Widget Unification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the settings properties panel render its value controls by reusing the same `BaseWidget` port widgets ports use — selected by IType — instead of its own raw-NiceGUI renderer; hoist those widgets into the framework `builtin` library; let each type declare its default widget; delete the dead `compatible_types` machinery; and hard-cut every `setting[<pytype>]` to `setting[<IType>]`.

**Architecture:** Hoist the 7 `BaseWidget` subclasses into the `builtin` library created by Plan 1. Lift the discouraged `@type(widget_key=...)` field to the canonical "type → default widget" link (string key → no import cycle). Desugar panel signals (`choices`, `min`/`max`, `widget='label'`) into widget metadata at setting-construction time, then have the panel resolve a widget by `widget_key` (explicit → type default) and render the shared `BaseWidget`, keeping the panel's own chrome (override `•`/reset, category groups, validation, vec layout). Delete `compatible_types`/`is_widget_compatible` (uncalled). Hard-cutover: `setting[FLOAT]` becomes the only legal form; `_type` is always an IType; Python-type inference is removed.

**Tech Stack:** Python 3.10+, NiceGUI/Quasar, the haywire widget system (`BaseWidget`, `WidgetRegistry`, `@widget`, `@type`), the settings descriptor system, pytest, ruff, mypy.

---

## Task 0: Verification Gate — confirm Plan 1 landed as required

**This plan depends on Plan 1 (type-floor hoist). Do NOT edit anything until this gate passes.**

**Files:**

- Read: `docs/superpowers/plans/2026-06-28-type-floor-hoist-DEVIATIONS.md`

- [ ] **Step 1: Read the Plan 1 deviations file**

Run: `cat docs/superpowers/plans/2026-06-28-type-floor-hoist-DEVIATIONS.md`
If the file does not exist, STOP — Plan 1 has not completed its handoff task. Do not proceed.
Record the **actual** values for: the type key pattern, the export surface of
`haywire.barn.builtin.types`, and which decorator (`@type`/`@primitive_type`) the scalars use.
Every concrete name in the tasks below assumes `builtin:type:*` and `@type` — if the deviations
file says otherwise, substitute the actual values throughout before editing.

- [ ] **Step 2: Probe the live prerequisite state**

Run:
```bash
uv run python -c "import haywire.core.graph.editor; \
from haywire.barn.builtin.types import INT, FLOAT, STRING, BOOL, COLOR, VEC3F; \
print('types import OK'); print('INT key:', INT.class_identity.registry_key)"
uv run pytest -m "not integration" -q
```
Expected: the import succeeds, the INT key matches the deviations file, and the suite is green.
If the import fails or the key differs from what Plan 2's tasks assume, STOP and reconcile
(update this plan's literal keys/names to match reality) before any edit.

- [ ] **Step 3: Confirm the widget machinery is still where this plan expects**

Run:
```bash
grep -n "class .*Widget" barn/haybale-core/haybale_core/widgets/basic_widgets.py
grep -n "def _build_field_widget\|def _value_widget_spec\|def is_widget_compatible" \
  packages/haywire-core/src/haywire/ui/panel/render_utils.py \
  packages/haywire-core/src/haywire/ui/widget/globals.py
grep -rn "compatible_types" packages/haywire-core/src/haywire/ui/widget/decorator.py
```
Expected: the 7 widgets still in `haybale-core/widgets/`, `_build_field_widget`/`_value_widget_spec`
still in the panel, `is_widget_compatible` still in `globals.py`, `compatible_types` still required
by the decorator. If any have already moved/changed (e.g. Plan 1 touched them unexpectedly per the
deviations file), reconcile before proceeding.

---

## Scope

**This plan (Plan 2 of 3)** does widgets + the IType hard-cutover. It does NOT implement
promote-to-inlet (Plan 3). It must leave a working app: the properties panel renders every
setting via shared widgets, all settings declare ITypes, the app boots.

### Self-contained floor grows

The `builtin` library gains a `widgets/` folder. The floor is now: types + vec + color +
basic adapters (Plan 1) **+ the 7 basic widgets** (this plan).

---

## File Structure

**New — hoisted widgets:**
- `packages/haywire-core/src/haywire/barn/builtin/widgets/__init__.py`
- `packages/haywire-core/src/haywire/barn/builtin/widgets/basic_widgets.py` — the 7 widgets, moved
- `packages/haywire-core/src/haywire/barn/builtin/widgets/vec_widget.py` — new VecWidget (X/Y/Z component editor)
- `packages/haywire-core/src/haywire/barn/builtin/widgets/color_widget.py` — new ColorWidget

**Modified — registration & type-default-widget:**
- `packages/haywire-core/src/haywire/barn/builtin/__init__.py` — register `widgets/`
- `packages/haywire-core/src/haywire/barn/builtin/types/specs.py` — add `widget_key=` to each scalar `@type`
- `.../types/vectors.py`, `.../types/color.py` — add `widget_key=`

**Modified — widget decorator & registry (delete dead path):**
- `packages/haywire-core/src/haywire/ui/widget/decorator.py` — drop the mandatory `compatible_types` arg
- `packages/haywire-core/src/haywire/ui/widget/identity.py` — drop the `compatible_types` field
- `packages/haywire-core/src/haywire/ui/widget/globals.py` — delete `is_widget_compatible`

**Modified — settings descriptor (desugar + hard cutover):**
- `packages/haywire-core/src/haywire/core/settings/base.py` — `_type` is an IType; reject non-ITypes
- `packages/haywire-core/src/haywire/core/settings/descriptor.py` — desugar `choices`/`min`/`max`/`widget` → `widget_key`+`widget_config`; remove Python-type inference

**Modified — panel renderer (reuse widgets):**
- `packages/haywire-core/src/haywire/ui/panel/render_utils.py` — replace `_build_field_widget`'s raw-NiceGUI body with widget resolution by `widget_key`; keep chrome

**Modified — the hard cutover (20 files):**
- every `setting[float|int|str|bool|Color|Vec*]` site → `setting[FLOAT|INT|STRING|BOOL|COLOR|VEC*]`

**Modified — slim the plugin:**
- delete `barn/haybale-core/haybale_core/widgets/basic_widgets.py`

**Tests:**
- `tests/barn/builtin/test_widgets_hoisted.py`
- `tests/barn/builtin/test_type_default_widget.py`
- `tests/core/settings/test_itype_cutover.py`
- `tests/core/settings/test_desugar.py`
- `tests/ui/panel/test_panel_reuses_widgets.py`
- `tests/ui/widget/test_compatible_types_removed.py`

---

## Pre-flight Baseline

- [ ] **Step 0: Baseline**

Run:
```sh
uv run ruff check packages/haywire-core/src/ barn/haybale-core/
uv run mypy packages/haywire-core/src/ barn/haybale-core/haybale_core/
uv run pytest -m "not integration" -q
```
Expected: clean (Plan 1 left it clean). If not, STOP and reconcile with the user.

---

## Task 1: Hoist the 7 basic widgets into `builtin`

**Files:**
- Create: `packages/haywire-core/src/haywire/barn/builtin/widgets/__init__.py`
- Create: `packages/haywire-core/src/haywire/barn/builtin/widgets/basic_widgets.py`
- Modify: `packages/haywire-core/src/haywire/barn/builtin/__init__.py`
- Test: `tests/barn/builtin/test_widgets_hoisted.py`

- [ ] **Step 1: Write the failing test**

`tests/barn/builtin/test_widgets_hoisted.py`:
```python
import haywire.core.graph.editor  # noqa: F401

from haywire.barn.builtin.widgets.basic_widgets import (
    NumberWidget, TextWidget, CheckboxWidget, SwitchWidget,
    SliderWidget, SelectWidget, SimpleLabelWidget,
)


def test_widget_keys_are_builtin_namespaced():
    assert NumberWidget.class_identity.registry_key == "builtin:widget:NumberWidget"
    assert SelectWidget.class_identity.registry_key == "builtin:widget:SelectWidget"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/barn/builtin/test_widgets_hoisted.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Move the widgets**

Read `barn/haybale-core/haybale_core/widgets/basic_widgets.py` in full. Copy it to
`packages/haywire-core/src/haywire/barn/builtin/widgets/basic_widgets.py`, with two edits:
1. Change the type import:
   ```python
   # was: from haybale_core.types import BOOL, FLOAT, INT, STRING
   from haywire.barn.builtin.types import BOOL, FLOAT, INT, STRING
   ```
2. Remove the `compatible_types=[...]` kwarg from every `@widget(...)` decorator (Task 5 deletes
   that arg from the decorator entirely; removing it here first keeps each commit runnable). Keep
   `description=` and any other kwargs.

`packages/haywire-core/src/haywire/barn/builtin/widgets/__init__.py`:
```python
from .basic_widgets import (
    NumberWidget, TextWidget, CheckboxWidget, SwitchWidget,
    SliderWidget, SelectWidget, SimpleLabelWidget,
)

__all__ = [
    "NumberWidget", "TextWidget", "CheckboxWidget", "SwitchWidget",
    "SliderWidget", "SelectWidget", "SimpleLabelWidget",
]
```

- [ ] **Step 4: Register the widgets folder**

In `packages/haywire-core/src/haywire/barn/builtin/__init__.py` `register_components`, add:
```python
        from haywire.ui.widget.registry import WidgetRegistry

        self.add_folder_to_registry(
            folder_path=str(base_path / "widgets"), registry_cls=WidgetRegistry
        )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/barn/builtin/test_widgets_hoisted.py -v`
Expected: PASS

- [ ] **Step 6: Delete the plugin copy and repoint imports**

Run:
```bash
git rm barn/haybale-core/haybale_core/widgets/basic_widgets.py
grep -rln "from haybale_core.widgets" barn/ packages/ tests/
```
Rewrite every hit to `from haywire.barn.builtin.widgets...`. Update
`barn/haybale-core/haybale_core/widgets/__init__.py` to drop the removed module.

- [ ] **Step 7: Type-check + commit**

Run: `uv run mypy packages/haywire-core/src/ barn/haybale-core/haybale_core/`
Expected: clean.
```bash
git add -A
git commit -m "feat(widgets): hoist basic widgets into builtin library

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Add VecWidget and ColorWidget

**Files:**
- Create: `packages/haywire-core/src/haywire/barn/builtin/widgets/vec_widget.py`
- Create: `packages/haywire-core/src/haywire/barn/builtin/widgets/color_widget.py`
- Modify: `.../widgets/__init__.py`
- Test: `tests/barn/builtin/test_widgets_hoisted.py` (extend)

- [ ] **Step 1: Write the failing test**

Append to `tests/barn/builtin/test_widgets_hoisted.py`:
```python
def test_vec_and_color_widgets_exist():
    from haywire.barn.builtin.widgets.vec_widget import VecWidget
    from haywire.barn.builtin.widgets.color_widget import ColorWidget

    assert VecWidget.class_identity.registry_key == "builtin:widget:VecWidget"
    assert ColorWidget.class_identity.registry_key == "builtin:widget:ColorWidget"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/barn/builtin/test_widgets_hoisted.py::test_vec_and_color_widgets_exist -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement ColorWidget**

Read `NumberWidget` in the hoisted `basic_widgets.py` for the exact `BaseWidget`/`@widget`/`build()`
shape. Read the panel's existing color rendering for the control:
`packages/haywire-core/src/haywire/ui/panel/render_utils.py` (`_value_widget_spec`, the
`defn._widget == "color"` branch — it uses `ui.color_input`).

`packages/haywire-core/src/haywire/barn/builtin/widgets/color_widget.py`:
```python
"""ColorWidget — color picker for COLOR ports (and the COLOR setting type)."""

from typing import Any
from nicegui import ui

from haywire.ui.widget.decorator import widget
from haywire.ui.widget.base import BaseWidget
from haywire.ui.widget.converters import PrimitiveUnwrappingConverter


@widget(description="Color picker widget")
class ColorWidget(BaseWidget):
    def build(self) -> Any:
        return self.bind(
            ui.color_input(value="#ffffff").classes("w-full").props("dense hide-bottom-space"),
            converter=PrimitiveUnwrappingConverter(default_value="#ffffff"),
        )
```

- [ ] **Step 4: Implement VecWidget**

Read the panel's `_render_vec_field_rows` (in `render_utils.py`) for how component rows + X/Y/Z
labels are built today, and `get_vec_meta` usage. The VecWidget renders one `NumberDrag` per
component, reads `VecMeta` (length, labels) from the port's `widget_config`.

`packages/haywire-core/src/haywire/barn/builtin/widgets/vec_widget.py`:
```python
"""VecWidget — N-component numeric editor for VEC* ports.

Reads length + component labels from widget_config['vec_meta'] (set by the VEC* type's
widget_config). Falls back to a single row if absent.
"""

from typing import Any
from nicegui import ui

from haywire.ui.widget.decorator import widget
from haywire.ui.widget.base import BaseWidget
from haywire.ui.components.number.drag import NumberDrag


@widget(description="Vector component editor widget")
class VecWidget(BaseWidget):
    def build(self) -> Any:
        cfg = self._config.get("properties", {})
        meta = cfg.get("vec_meta", {})
        length = int(meta.get("length", 3))
        labels = meta.get("labels", tuple(f"[{i}]" for i in range(length)))

        current = self.get_value() or [0] * length
        with ui.row().classes("w-full gap-1 no-wrap") as root:
            self._fields = []
            for i in range(length):
                val = current[i] if i < len(current) else 0
                drag = NumberDrag(value=val, prefix=f"{labels[i]} ").classes("flex-1")
                drag.on_value_change(lambda e, idx=i: self._on_component(idx, e))
                self._fields.append(drag)
        return root

    def _on_component(self, idx: int, e: Any) -> None:
        vec = list(self.get_value() or [])
        while len(vec) <= idx:
            vec.append(0)
        vec[idx] = e.value if hasattr(e, "value") else e
        self.set_value(vec)

    def on_model_changed(self, value: Any) -> None:
        if not value:
            return
        for i, f in enumerate(getattr(self, "_fields", [])):
            if i < len(value):
                f.value = value[i]
```
**Verify before relying on it:** confirm `NumberDrag`'s constructor args (`value=`, `prefix=`)
and `on_value_change` against `packages/haywire-core/src/haywire/ui/components/number/drag.py`.
Match the `BaseWidget.build()`/`on_model_changed` contract to how `NumberWidget` does it.

- [ ] **Step 5: Export both**

Update `.../widgets/__init__.py` to import + `__all__` `VecWidget`, `ColorWidget`.

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run pytest tests/barn/builtin/test_widgets_hoisted.py::test_vec_and_color_widgets_exist -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add packages/haywire-core/src/haywire/barn/builtin/widgets/ tests/barn/builtin/test_widgets_hoisted.py
git commit -m "feat(widgets): add VecWidget and ColorWidget to builtin

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Each builtin type declares its default widget_key

**Files:**
- Modify: `packages/haywire-core/src/haywire/barn/builtin/types/specs.py`
- Modify: `packages/haywire-core/src/haywire/barn/builtin/types/vectors.py`
- Modify: `packages/haywire-core/src/haywire/barn/builtin/types/color.py`
- Test: `tests/barn/builtin/test_type_default_widget.py`

- [ ] **Step 1: Write the failing test**

`tests/barn/builtin/test_type_default_widget.py`:
```python
import haywire.core.graph.editor  # noqa: F401

from haywire.barn.builtin.types import FLOAT, INT, STRING, BOOL, COLOR, VEC3F


def test_each_type_declares_a_default_widget_key():
    assert FLOAT.class_identity.widget_key == "builtin:widget:NumberWidget"
    assert INT.class_identity.widget_key == "builtin:widget:NumberWidget"
    assert STRING.class_identity.widget_key == "builtin:widget:TextWidget"
    assert BOOL.class_identity.widget_key == "builtin:widget:SwitchWidget"
    assert COLOR.class_identity.widget_key == "builtin:widget:ColorWidget"
    assert VEC3F.class_identity.widget_key == "builtin:widget:VecWidget"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/barn/builtin/test_type_default_widget.py -v`
Expected: FAIL — `widget_key` is None/empty.
**First confirm the attribute name:** read `packages/haywire-core/src/haywire/core/types/identity.py`
for the field that stores the type's widget (the `@type` docstring referenced `widget_key`). If the
stored attribute differs, update the test assertions to the real attribute name.

- [ ] **Step 3: Add widget_key to each type decorator**

In `specs.py`, add to each scalar's `@type(...)`:
```python
@type(..., widget_key="builtin:widget:NumberWidget")   # FLOAT, INT
@type(..., widget_key="builtin:widget:TextWidget")     # STRING
@type(..., widget_key="builtin:widget:SwitchWidget")   # BOOL
```
In `color.py`: `widget_key="builtin:widget:ColorWidget"`.
In `vectors.py`: `widget_key="builtin:widget:VecWidget"` on all six VEC* classes, and pass the
`VecMeta` into `widget_config` so VecWidget can read it:
```python
from haywire.core.settings.types import get_vec_meta

def _vec_widget_config(vec_cls):
    m = get_vec_meta(vec_cls)
    return {"properties": {"vec_meta": {"length": m.length, "labels": list(m.labels)}}}

@type(..., widget_key="builtin:widget:VecWidget", widget_config=_vec_widget_config(Vec3f))
class VEC3F(PrimitiveType[Vec3f]):
    ...
```
Confirm `@type` accepts `widget_key=` and `widget_config=` (the decorator docstring lists both as
"NOT RECOMENDED" — they exist; this plan promotes them to canonical).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/barn/builtin/test_type_default_widget.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/barn/builtin/types/ tests/barn/builtin/test_type_default_widget.py
git commit -m "feat(types): builtin types declare default widget_key

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Settings descriptor — hard cutover to ITypes + reject Python types

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/settings/base.py`
- Modify: `packages/haywire-core/src/haywire/core/settings/descriptor.py`
- Test: `tests/core/settings/test_itype_cutover.py`

**Background:** today `_type` holds a Python type (`base.py:__set_name__` refines from annotations;
`descriptor.py:189` infers `type(default)`). After cutover `_type` is always an IType subclass.

- [ ] **Step 1: Write the failing test**

`tests/core/settings/test_itype_cutover.py`:
```python
import haywire.core.graph.editor  # noqa: F401
import pytest

from haywire.core.settings import NodeSettings, setting
from haywire.barn.builtin.types import FLOAT, STRING


def test_setting_accepts_itype():
    class bag(NodeSettings):
        x = setting[FLOAT](1.0)
    assert bag.__dict__["x"]._type is FLOAT


def test_setting_rejects_python_type():
    with pytest.raises(TypeError):
        class bag(NodeSettings):
            x = setting[float](1.0)   # python type no longer allowed
        _ = bag
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/settings/test_itype_cutover.py -v`
Expected: FAIL — `setting[float]` is currently accepted (no rejection).

- [ ] **Step 3: Enforce IType in the descriptor**

In `descriptor.py __init__`, replace the inference line
(`self._type = type_ if type_ is not None else (type(default) ...)`) with IType enforcement:
```python
from haywire.core.types.interface import IType

resolved_type = type_ if type_ is not None else self._infer_itype_from_generic()
if resolved_type is None or not (isinstance(resolved_type, type) and issubclass(resolved_type, IType)):
    raise TypeError(
        f"setting field '{label or '?'}' must be typed with an IType "
        f"(e.g. setting[FLOAT]); got {resolved_type!r}. Python types are no longer accepted."
    )
self._type = resolved_type
```
In `base.py __set_name__`, change the annotation/generic refinement so it only accepts an IType
subclass (the `setting[FLOAT]` generic arg flows via `__orig_class__`); drop the
`type(default)` fallback. Add a small `_infer_itype_from_generic()` helper on the descriptor that
reads `__orig_class__`'s arg and returns it only if it's an IType subclass, else None.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/settings/test_itype_cutover.py -v`
Expected: PASS. (The whole rest of the repo's `setting[float]` sites now break — Task 7 fixes them;
expect the broader suite to be red until then. That is intended for this commit boundary.)

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/settings/ tests/core/settings/test_itype_cutover.py
git commit -m "feat(settings)!: require IType for setting fields, drop python-type inference

BREAKING: setting[float] etc. are rejected; use setting[FLOAT].

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: Desugar panel signals into widget metadata; delete `compatible_types`

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/settings/descriptor.py` (desugar)
- Modify: `packages/haywire-core/src/haywire/ui/widget/decorator.py` (drop required arg)
- Modify: `packages/haywire-core/src/haywire/ui/widget/identity.py` (drop field)
- Modify: `packages/haywire-core/src/haywire/ui/widget/globals.py` (delete `is_widget_compatible`)
- Test: `tests/core/settings/test_desugar.py`, `tests/ui/widget/test_compatible_types_removed.py`

- [ ] **Step 1: Write the failing desugar test**

`tests/core/settings/test_desugar.py`:
```python
import haywire.core.graph.editor  # noqa: F401

from haywire.core.settings import NodeSettings, setting
from haywire.barn.builtin.types import INT, FLOAT


def test_choices_desugar_to_select_widget():
    class bag(NodeSettings):
        mode = setting[INT](0, choices={0: "Off", 1: "On"})
    d = bag.__dict__["mode"]
    assert d.resolved_widget_key == "builtin:widget:SelectWidget"
    assert d.resolved_widget_config["properties"]["options"] == {0: "Off", 1: "On"}


def test_min_max_desugar_to_number_config():
    class bag(NodeSettings):
        x = setting[FLOAT](0.5, min=0.0, max=1.0)
    d = bag.__dict__["x"]
    # No explicit widget_key, no choices -> type default (NumberWidget), bounds in config.
    assert d.resolved_widget_config["properties"]["min"] == 0.0
    assert d.resolved_widget_config["properties"]["max"] == 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/settings/test_desugar.py -v`
Expected: FAIL — `resolved_widget_key`/`resolved_widget_config` don't exist.

- [ ] **Step 3: Implement desugaring on the descriptor**

Add to `descriptor.py` two computed properties that desugar the legacy signals into widget
metadata, with this precedence: explicit `widget`/`widget_key` arg → `choices` ⇒ SelectWidget →
else the field's IType default `widget_key`:
```python
@property
def resolved_widget_key(self) -> str:
    if self._widget == "label":
        return "builtin:widget:SimpleLabelWidget"
    if self._choices is not None:
        return "builtin:widget:SelectWidget"
    # IType default
    return getattr(self._type.class_identity, "widget_key", "") or ""

@property
def resolved_widget_config(self) -> dict:
    props: dict = {}
    if self._choices is not None:
        props["options"] = self.choices
    for k in ("min", "max"):
        v = getattr(self, f"_{k}")
        if v is not None:
            props[k] = v
    # vec types carry their meta on the type's widget_config
    type_cfg = getattr(self._type.class_identity, "widget_config", {}) or {}
    merged = {**type_cfg.get("properties", {}), **props}
    return {"properties": merged}
```
(Confirm the IType identity attribute names `widget_key`/`widget_config` from Task 3 Step 2;
substitute if they differ.)

- [ ] **Step 4: Write the failing `compatible_types`-removal test**

`tests/ui/widget/test_compatible_types_removed.py`:
```python
import haywire.core.graph.editor  # noqa: F401
import pytest

from haywire.ui.widget.decorator import widget
from haywire.ui.widget.base import BaseWidget


def test_widget_decorator_no_longer_requires_compatible_types():
    @widget(description="no types declared")
    class W(BaseWidget):
        def build(self):
            return None
    assert W is not None


def test_is_widget_compatible_is_gone():
    import haywire.ui.widget.globals as g
    assert not hasattr(g, "is_widget_compatible")
```

- [ ] **Step 5: Run it to verify failure**

Run: `uv run pytest tests/ui/widget/test_compatible_types_removed.py -v`
Expected: FAIL — decorator still requires `compatible_types`; `is_widget_compatible` still present.

- [ ] **Step 6: Delete the dead path**

- `decorator.py`: remove the block (lines ~61-74) that raises when `compatible_types` is absent and
  validates its shape. Drop `compatible_types` from any kwargs it forwards.
- `identity.py`: remove the `compatible_types` field from `WidgetIdentity`.
- `globals.py`: delete the `is_widget_compatible` function entirely (verified: zero callers).
- Grep and remove any lingering references:
  ```bash
  grep -rn "compatible_types\|is_widget_compatible" packages/ barn/ tests/
  ```
  Remove each remaining hit (decorator call-site kwargs were already dropped in Task 1 Step 3).

- [ ] **Step 7: Run both test files**

Run: `uv run pytest tests/core/settings/test_desugar.py tests/ui/widget/test_compatible_types_removed.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat(widgets)!: desugar setting signals to widget_key; delete compatible_types

BREAKING: @widget no longer accepts compatible_types; is_widget_compatible removed.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: Panel renders via shared widgets (keep chrome)

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/panel/render_utils.py`
- Test: `tests/ui/panel/test_panel_reuses_widgets.py`

**Background:** `_build_field_widget` (render_utils.py:339) currently builds raw NiceGUI via
`_value_widget_spec`. Replace its body to resolve a `BaseWidget` by `resolved_widget_key` and render
it, while the surrounding row chrome (`_render_label`, override `•`/reset, category groups, error
container, vec multi-row) stays as-is. The vec special-case at lines 240/296 is now handled by
VecWidget, so the `get_vec_meta` branch can route through the same widget path.

- [ ] **Step 1: Write the failing test**

`tests/ui/panel/test_panel_reuses_widgets.py`:
```python
import haywire.core.graph.editor  # noqa: F401
import pytest

pytestmark = pytest.mark.integration


def test_panel_resolves_widget_from_registry(monkeypatch):
    """_build_field_widget asks the widget registry for resolved_widget_key, not raw ui.*"""
    from haywire.ui.panel import render_utils

    calls = []
    real = render_utils._resolve_widget_instance  # the new helper added in Step 3

    def spy(defn, value, make_setter):
        calls.append(defn.resolved_widget_key)
        return real(defn, value, make_setter)

    monkeypatch.setattr(render_utils, "_resolve_widget_instance", spy)
    # Build a settings bag and render one field through the public entry point.
    # (Mirror an existing panel render test in tests/ui/panel/ for the harness setup.)
    ...
```
Read an existing panel render test under `tests/ui/panel/` first and reuse its NiceGUI test
harness (client/context fixture) to drive a real render; replace the `...` with that setup. If no
panel render test exists, assert at the unit level instead: that `_resolve_widget_instance(defn,...)`
returns a `BaseWidget` whose `class_identity.registry_key == defn.resolved_widget_key`.

- [ ] **Step 2: Run it to verify failure**

Run: `uv run pytest tests/ui/panel/test_panel_reuses_widgets.py -v`
Expected: FAIL — `_resolve_widget_instance` doesn't exist yet.

- [ ] **Step 3: Replace `_build_field_widget`'s body**

Add a helper and rewrite `_build_field_widget` to use it; delete `_value_widget_spec` and the
raw-NiceGUI `_WidgetSpec` catalog once nothing references them:
```python
from haywire.ui.widget.globals import get_widget_class

def _resolve_widget_instance(defn, value, make_setter):
    """Build the shared BaseWidget for *defn* by its resolved widget_key.

    The widget owns the control; the panel keeps the surrounding chrome.
    """
    key = defn.resolved_widget_key
    widget_cls = get_widget_class(key)
    if widget_cls is None:
        # last-resort: a read-only label, never a silent blank
        return _build_label_widget(value)
    # Instantiate against a lightweight settings-backed model adapter so the widget's
    # get_value/set_value route to the setting (see widget base contract). Reuse the
    # existing settings-widget adapter if Plan 3 added one; otherwise wire make_setter.
    inst = widget_cls(...)  # match BaseWidget.__init__ — read base.py
    ...
    return apply_callable
```
**This is the hardest task — do it carefully.** `BaseWidget.__init__(self, port: DataPort)` binds to
a *port*, but here we render a *setting*. For Plan 2 the panel still owns value flow via
`make_setter`/`getattr(obj, attr_name)`. Two acceptable approaches, pick the one matching the
codebase:
  (a) give `BaseWidget` a settings-backed construction path (a small model adapter exposing
      `get_value`/`set_value`/`on_changed`) and pass it instead of a port; or
  (b) keep the panel's existing draw+link mechanism but select the *NiceGUI element* the widget
      would build, by extracting each widget's `build()` element — only if (a) is too invasive.
Prefer (a). Read `packages/haywire-core/src/haywire/ui/widget/base.py:25-50` for the exact
constructor + `get_value`/`set_value`/`on_model_changed` surface and design the adapter to satisfy
it. Keep `_render_label`, the reset button, category grouping, and the error container untouched.

- [ ] **Step 4: Route vec fields through the widget too**

Remove the `get_vec_meta`-based `_render_vec_field_rows` *selection* branches at lines ~240 and
~296 so vec settings resolve `VecWidget` via `resolved_widget_key` like everything else. Keep
`_render_vec_field_rows` only if VecWidget delegates to it; otherwise delete it once unreferenced.

- [ ] **Step 5: Run test + a broad panel render check**

Run:
```bash
uv run pytest tests/ui/panel/test_panel_reuses_widgets.py -v
uv run pytest tests/ui/panel/ -q
```
Expected: PASS. Investigate any panel test asserting the old raw-`ui.*` DOM; update its expectation
to the shared-widget DOM (the `data-value`/`data-field` contract is preserved, so most should pass).

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(panel): render settings via shared builtin widgets, keep panel chrome

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 7: Hard-cutover sweep — every `setting[<pytype>]` → `setting[<IType>]`

**Files:**
- Modify: all ~20 files containing `setting[float|int|str|bool|Color|Vec*]`

- [ ] **Step 1: Enumerate every site**

Run:
```bash
grep -rn "setting\[float\]\|setting\[int\]\|setting\[str\]\|setting\[bool\]\|setting\[Color\]\|setting\[Vec[0-9][if]\]" packages/ barn/ tests/
```

- [ ] **Step 2: Rewrite each, adding the IType import**

Per file, map: `float→FLOAT`, `int→INT`, `str→STRING`, `bool→BOOL`, `Color→COLOR`,
`Vec3f→VEC3F`, `Vec2i→VEC2I`, etc. Add at the top:
```python
from haywire.barn.builtin.types import FLOAT, INT, STRING, BOOL, COLOR, VEC3F  # import only those used
```
Remove now-unused `from haywire.core.settings import ... Color, Vec3f` imports where the alias was
only used as a `setting[...]` arg. `shadow()`/`watch()` sites need NO change (type inherited from
source). This is a string-reference sweep — run the `/check-rename` skill afterward to catch
`patch("...")`, doc citations, and `importlib` references the IDE misses.

- [ ] **Step 3: Lint + type-check clean**

Run:
```bash
uv run ruff check packages/ barn/
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-TEST_A/haybale_test_a/
```
Expected: clean. Remaining errors are missed `setting[<pytype>]` sites or stale alias imports.

- [ ] **Step 4: Full non-integration suite**

Run: `uv run pytest -m "not integration" -q`
Expected: PASS. Failures are likely settings tests asserting `_type is float` — update to
`_type is FLOAT`.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor(settings)!: convert all setting[pytype] to setting[IType]

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 8: End-to-end verification

**Files:**
- Test: `tests/ui/panel/test_widget_unification_e2e.py`

- [ ] **Step 1: Write the integration test**

`tests/ui/panel/test_widget_unification_e2e.py`:
```python
import pytest
import haywire.core.graph.editor  # noqa: F401

pytestmark = pytest.mark.integration


def test_setting_and_port_share_widget_class():
    """A FLOAT setting and a FLOAT port resolve the SAME widget class."""
    from haywire.ui.widget.globals import get_widget_class
    from haywire.barn.builtin.types import FLOAT

    type_default = FLOAT.class_identity.widget_key
    assert get_widget_class(type_default) is not None
    # The panel's resolved_widget_key for a plain FLOAT setting equals the type default.
    from haywire.core.settings import NodeSettings, setting

    class bag(NodeSettings):
        x = setting[FLOAT](1.0)
    assert bag.__dict__["x"].resolved_widget_key == type_default
```

- [ ] **Step 2: Run it**

Run: `uv run pytest tests/ui/panel/test_widget_unification_e2e.py -v -m integration`
Expected: PASS

- [ ] **Step 3: Full suite + boot**

Run:
```bash
uv run pytest -q
uv run haywire   # boot, confirm panels render, no widget-resolution errors in log, then stop
```
Expected: green suite; app boots; selecting a node shows the properties panel with shared widgets.

- [ ] **Step 4: Full quality gate**

Run:
```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-TEST_A/haybale_test_a/
uv run pytest -q
```
Expected: all clean.

- [ ] **Step 5: Commit**

```bash
git add tests/ui/panel/test_widget_unification_e2e.py
git commit -m "test(widgets): end-to-end widget unification verification

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 9: Handoff — record divergences for Plan 3

**Files:**

- Create: `docs/superpowers/plans/2026-06-29-widget-unification-DEVIATIONS.md`

- [ ] **Step 1: Probe landed state**

Run:
```bash
uv run python -c "import haywire.core.graph.editor; from haywire.core.settings import NodeSettings, setting; from haywire.barn.builtin.types import FLOAT; \
class b(NodeSettings):\n x=setting[FLOAT](1.0)
print('resolved_widget_key:', b.__dict__['x'].resolved_widget_key)"
grep -n "def _resolve_widget_instance\|def resolved_widget_key\|def resolved_widget_config" \
  packages/haywire-core/src/haywire/ui/panel/render_utils.py \
  packages/haywire-core/src/haywire/core/settings/descriptor.py
grep -n "class .*BaseWidget\|def __init__" packages/haywire-core/src/haywire/ui/widget/base.py
```

- [ ] **Step 2: Write the deviations file**

Create `docs/superpowers/plans/2026-06-29-widget-unification-DEVIATIONS.md` recording, for Plan 3:
- the exact name/signature of the settings→widget model adapter chosen in Task 6 (approach a vs b),
- whether `BaseWidget.__init__` gained a settings-backed path (Plan 3's optional on-card widget reuses it),
- the final `resolved_widget_key`/`resolved_widget_config` property names,
- any panel tests whose DOM expectations changed,
- anything else Plan 3 would be wrong to assume.

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/plans/2026-06-29-widget-unification-DEVIATIONS.md
git commit -m "docs(plan): record Plan 2 landed-state deviations for Plan 3

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review Notes

- **Hardest task is Task 6** (panel reuses the port-bound `BaseWidget` for a setting). It hinges on
  a settings-backed model adapter; the plan names two approaches and tells the engineer to read
  `widget/base.py` and prefer (a). If (a) proves large, it is acceptable to land Task 6 with the
  panel selecting the widget's *element* while keeping the panel's link mechanism, and note it in
  the deviations file for Plan 3.
- **Commit boundaries are intentionally red between Task 4 and Task 7:** the IType cutover breaks all
  `setting[pytype]` sites until the sweep. Each commit is internally coherent; the suite is green
  again at Task 7 Step 4.
- **Depends on Plan 1.** Task 0 is the gate. If the deviations file reports non-`builtin:*` keys or a
  different decorator, substitute throughout before editing.
- **Out of scope:** promote-to-inlet (Plan 3). The on-card widget for a promoted inlet is explicitly
  deferred (Plan 3 ships no-widget v1), so Task 6's adapter is for the *panel*, not the node card.