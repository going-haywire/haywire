# Settings UI Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an isolated NiceGUI harness app and Playwright test suite that lets developers and agents verify Settings UI rendering without spinning up the full Haywire application.

**Architecture:** A standalone `HarnessApp` at `tests/ui/harness/app.py` boots the full library system (same DI path as the main app), registers NiceGUI routes that render any `NodeSettings` bag or `LibrarySettings` schema by URL parameter, and runs on port 8090. Playwright tests in `tests/ui/harness/` use a session-scoped subprocess fixture to drive those routes and assert on DOM `data-field`/`data-value` attributes. Two targeted production changes add those attributes to the settings panel renderer and `NumberDrag`.

**Tech Stack:** Python, NiceGUI, Playwright, pytest-playwright, importlib, requests (for fixture polling)

---

## File Map

**New files:**
- `tests/ui/harness/__init__.py` — empty, marks package
- `tests/ui/harness/app.py` — `HarnessApp`: boots library system, theme CSS, NiceGUI routes, port 8090
- `tests/ui/harness/routes.py` — `/status`, `/node`, `/schema`, `/api/set` route handlers
- `tests/ui/harness/conftest.py` — session-scoped subprocess fixture + `reset_setting` fixture
- `tests/ui/harness/test_structural.py` — field presence, widget types, categories
- `tests/ui/harness/test_interaction.py` — value set/read-back, reset button, mirror indicator
- `tests/ui/harness/test_mirror.py` — global setting change → mirror field propagation
- `tests/ui/harness/test_validation.py` — validator failures → error indicator in DOM

**Modified files:**
- `barn/haybale-core/haybale_core/panels/_settings_panel_base.py` — add `data-field` to row containers, `data-value` wrapper to `_render_widget_impl`
- `packages/haywire-core/src/haywire/ui/components/number_drag.py` — add `data-value` prop to root element
- `pyproject.toml` — add `playwright`, `pytest-playwright`, `requests` to dev dependencies

---

## Task 1: Add dev dependencies

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add playwright and pytest-playwright to dev deps**

Edit `pyproject.toml`, add to the `dev` dependency group:

```toml
[dependency-groups]
dev = [
    "pytest",
    "pytest-cov",
    "mypy",
    "ruff",
    "pyinstaller>=6.14.1",
    "playwright",
    "pytest-playwright",
    "requests",
    "haywire-core",
    "haywire-studio",
    "haybale-core",
    "haybale-studio",
    "haybale-example",
    "haybale-testing",
    "haybale-visiongraph",
    "haybale-TEST_A",
]
```

- [ ] **Step 2: Install dependencies and Playwright browsers**

```bash
uv sync
uv run playwright install chromium
```

Expected: chromium browser installs without error.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add playwright, pytest-playwright, requests dev deps"
```

---

## Task 2: Add `data-field` / `data-value` DOM attributes to settings panel renderer

**Files:**
- Modify: `barn/haybale-core/haybale_core/panels/_settings_panel_base.py`

These attributes let Playwright locate field rows and read current values uniformly regardless of widget type.

- [ ] **Step 1: Add `data-field` to `_render_field_row` and `data-value` wrapper to each widget branch in `_render_widget_impl`**

Replace the entire file content. The key changes are:
1. `_render_field_row` passes `attr_name` to a `data-field` attribute on the row container
2. `_render_widget_impl` wraps each widget in a `ui.element("div")` that carries `data-value`
3. `_render_reactive_field_row` passes `attr_name` as `data_field` to `_render_field_row`

Open `barn/haybale-core/haybale_core/panels/_settings_panel_base.py` and make these targeted edits:

**Edit 1** — update `_render_field_row` signature and add `data-field` attribute:

```python
def _render_field_row(label_text: str, description: str, defn, value, make_setter, attr_name: str = ""):
    """Render a single label + widget row."""
    with ui.row().classes(_ROW_CLASSES).props(f'data-field="{attr_name}"' if attr_name else ""):
        lbl = ui.label(label_text).classes(_LABEL_CLASSES)
        if description:
            lbl.tooltip(description)
        _render_widget_impl(defn, value, make_setter)
```

**Edit 2** — update `_render_reactive_field_row` to pass `attr_name` down:

```python
def _render_reactive_field_row(obj: "Settings", attr_name: str, defn: "FieldDescriptor") -> None:
    """Render a single reactive field row, with optional reset button for mirrored fields."""
    container = ui.element("div").classes("w-full")

    def _build_row():
        container.clear()
        with container:
            is_mirrored = bool(defn._mirror_key)
            is_locally_overridden = is_mirrored and obj.is_locally_set(attr_name)

            label_text = defn._label or attr_name
            if is_locally_overridden:
                label_text = f"• {label_text}"

            with ui.row().classes(_ROW_CLASSES).props(f'data-field="{attr_name}"'):
                lbl = ui.label(label_text).classes(_LABEL_CLASSES)
                if defn._description:
                    lbl.tooltip(defn._description)
                _render_widget_impl(defn, getattr(obj, attr_name), _make_reactive_setter(obj, attr_name))
                if is_locally_overridden:
                    ui.button(icon="restart_alt").props("flat dense size=xs").tooltip(
                        "Reset to global default"
                    ).on("click", lambda _o=obj, _n=attr_name: (_o.reset(_n), _build_row()))

    _build_row()
```

**Edit 3** — update `render_schema` to pass `attr_name` (the last segment of the field key) to `_render_field_row`:

```python
def render_schema(schema_cls: type, registry: "SettingsRegistry") -> None:
    """Render all fields of *schema_cls* as labelled form rows."""

    defns = registry.definitions_for_schema(schema_cls)
    if not defns:
        ui.label("No settings defined.").classes("text-xs text-gray-400 px-2 py-1")
        return

    sorted_defns = sorted(defns.values(), key=lambda d: (d._category, d._order, d._field_key))
    with ui.column().classes("w-full gap-0 compact-fields"):
        for category, group in _group_by_category(sorted_defns):
            with _render_category_group(category):
                for defn in group:
                    key = defn._field_key
                    try:
                        value, _ = registry.resolve(key)
                    except KeyError:
                        continue
                    attr_name = defn._attr_name or key.split(".")[-1]
                    _render_field_row(
                        defn._label or attr_name,
                        defn._description,
                        defn,
                        value,
                        lambda coerce, k=key: _make_setter(registry, k, coerce),
                        attr_name=attr_name,
                    )
```

**Edit 4** — update `_render_widget_impl` to wrap each branch in a `data-value` div:

```python
def _render_widget_impl(defn: "FieldDescriptor", value: Any, make_setter) -> None:
    """Shared widget dispatch. make_setter(coerce) -> on_change handler."""
    str_value = str(value) if value is not None else ""

    if defn._widget == "color":
        with ui.element("div").props(f'data-value="{str_value}"'):
            ui.color_input(value=value or "#ffffff").classes("flex-1 min-w-0").on(
                "change", make_setter(str)
            )
        return

    resolved_choices = defn.choices
    if resolved_choices is not None:
        with ui.element("div").props(f'data-value="{str_value}"'):
            ui.select(
                options=resolved_choices,
                value=value,
                on_change=make_setter(lambda v: v),
            ).classes("flex-1 min-w-0 text-xs").props("dense")
        return

    if defn._type is bool:
        with ui.element("div").props(f'data-value="{str(bool(value)).lower()}"'):
            ui.switch(value=bool(value), on_change=make_setter(bool)).props("dense")
        return

    if defn._type in (int, float):
        kwargs: dict = {}
        if defn._min is not None:
            kwargs["min"] = defn._min
        if defn._max is not None:
            kwargs["max"] = defn._max
        if defn._type is int:
            kwargs["step"] = 1
            kwargs["precision"] = 0
        coerce = defn._type
        handler = make_setter(coerce)

        class _E:
            __slots__ = ("value",)

        def _on_number_change(e, _h=handler, _c=coerce):
            ev = _E()
            ev.value = _c(e.args)
            _h(ev)

        NumberDrag(value=value if value is not None else 0, on_change=_on_number_change, **kwargs).classes(
            "flex-1 min-w-0"
        ).props(f'data-value="{str_value}"')
        return

    with ui.element("div").props(f'data-value="{str_value}"'):
        ui.input(
            value=str(value) if value is not None else "",
            on_change=make_setter(str),
        ).classes("flex-1 min-w-0 text-xs").props("dense")
```

- [ ] **Step 2: Run existing panel tests to confirm nothing broke**

```bash
uv run pytest tests/ui/test_panel_registry.py -v
```

Expected: all tests PASS.

- [ ] **Step 3: Commit**

```bash
git add barn/haybale-core/haybale_core/panels/_settings_panel_base.py
git commit -m "feat: add data-field/data-value DOM attributes to settings panel renderer"
```

---

## Task 3: Add `data-value` to `NumberDrag`

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/components/number_drag.py`

`NumberDrag` is a Vue component; NiceGUI passes `_props` to the root element. Adding `data-value` to `_props` on init and on every value update means Playwright can read it directly from the DOM.

- [ ] **Step 1: Update `NumberDrag.__init__` and `handle_update` to keep `data-value` in sync**

```python
def __init__(
    self,
    value: float = 0,
    *,
    min: float = float("-inf"),
    max: float = float("inf"),
    step: float = 0.1,
    precision: int = -1,
    prefix: str = "",
    suffix: str = "",
    sensitivity: float = 1.0,
    on_change: Optional[Callable[..., Any]] = None,
) -> None:
    super().__init__()
    self._props["model-value"] = value
    self._props["data-value"] = str(value)
    if math.isfinite(min):
        self._props["min"] = min
    if math.isfinite(max):
        self._props["max"] = max
    self._props["step"] = step
    self._props["precision"] = precision
    self._props["prefix"] = prefix
    self._props["suffix"] = suffix
    self._props["sensitivity"] = sensitivity

    self._change_handler = on_change

    def handle_update(e):
        self._props["model-value"] = e.args
        self._props["data-value"] = str(e.args)
        self.update()
        if self._change_handler is not None:
            self._change_handler(e)

    self.on("update:modelValue", handle_update)

@property
def value(self) -> float:
    return self._props.get("model-value", 0)

@value.setter
def value(self, v: float) -> None:
    self._props["model-value"] = v
    self._props["data-value"] = str(v)
    self.update()
```

- [ ] **Step 2: Run all tests to confirm nothing broke**

```bash
uv run pytest -m "not integration" -q
```

Expected: all tests PASS.

- [ ] **Step 3: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/components/number_drag.py
git commit -m "feat: add data-value attribute to NumberDrag for Playwright test access"
```

---

## Task 4: Build the harness app and routes

**Files:**
- Create: `tests/ui/harness/__init__.py`
- Create: `tests/ui/harness/app.py`
- Create: `tests/ui/harness/routes.py`

- [ ] **Step 1: Create `tests/ui/harness/__init__.py`**

Empty file:

```python
```

- [ ] **Step 2: Create `tests/ui/harness/routes.py`**

```python
"""
Harness route handlers for the Settings UI test harness.

Routes:
  GET  /status               — liveness probe, returns {"status": "ok"}
  GET  /node?class=...&bag=  — render a NodeSettings bag via render_reactive()
  GET  /schema?class=...     — render a LibrarySettings/FrameworkSettings via render_schema()
  POST /api/set?key=&value=  — write a value to the SettingsRegistry workspace tier
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

from fastapi import Request
from fastapi.responses import JSONResponse
from nicegui import ui

from haybale_core.panels._settings_panel_base import render_reactive, render_schema
from haywire.core.settings.enums import SettingMode

if TYPE_CHECKING:
    from haywire.core.settings.registry import SettingsRegistry


def _resolve_class(dotted: str):
    """Import a dotted class path like 'a.b.c.MyClass' and return the class."""
    parts = dotted.rsplit(".", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid class path: {dotted!r}")
    module_path, class_name = parts
    mod = importlib.import_module(module_path)
    return getattr(mod, class_name)


def _build_theme_css(registry: "SettingsRegistry", theme_registry) -> str:
    """Build :root CSS block from the first available workbench theme."""
    valid_keys = [k for k in theme_registry.list_workbench_keys() if not k.startswith("__system__:")]
    if not valid_keys:
        return ""
    theme_key, _ = registry.resolve("workbench.theme")
    if theme_key not in valid_keys:
        theme_key = valid_keys[0]
    theme = theme_registry.get_workbench(theme_key)
    vars_str = " ".join(f"{k}: {v};" for k, v in theme.to_css_vars().items())
    return f":root {{ {vars_str} }}"


def register_routes(library_service) -> None:
    """Register all harness routes with NiceGUI/FastAPI."""

    registry: "SettingsRegistry" = library_service.get_settings_registry()
    theme_registry = library_service.get_theme_registry()
    theme_css = _build_theme_css(registry, theme_registry)

    # -------------------------------------------------------------------------
    # GET /status
    # -------------------------------------------------------------------------

    @ui.page("/status")
    async def status_page(request: Request):
        return JSONResponse({"status": "ok"})

    # -------------------------------------------------------------------------
    # GET /node?class=<dotted.ClassName>&bag=<bag_name>
    # -------------------------------------------------------------------------

    @ui.page("/node")
    async def node_page(request: Request):
        params = dict(request.query_params)
        class_path = params.get("class", "")
        bag_name = params.get("bag", "")

        if theme_css:
            ui.add_css(theme_css)

        with ui.card().classes("w-full max-w-md mx-auto mt-8 p-4"):
            if not class_path or not bag_name:
                ui.label("Missing ?class= or ?bag= parameter").classes("text-red-400")
                return

            try:
                node_cls = _resolve_class(class_path)
                settings_cls = getattr(node_cls, bag_name)
                settings_instance = settings_cls()
                render_reactive(settings_instance)
            except Exception as exc:
                ui.label(f"Error: {exc}").classes("text-red-400 text-xs")

    # -------------------------------------------------------------------------
    # GET /schema?class=<dotted.ClassName>
    # -------------------------------------------------------------------------

    @ui.page("/schema")
    async def schema_page(request: Request):
        params = dict(request.query_params)
        class_path = params.get("class", "")

        if theme_css:
            ui.add_css(theme_css)

        with ui.card().classes("w-full max-w-md mx-auto mt-8 p-4"):
            if not class_path:
                ui.label("Missing ?class= parameter").classes("text-red-400")
                return

            try:
                schema_cls = _resolve_class(class_path)
                render_schema(schema_cls, registry)
            except Exception as exc:
                ui.label(f"Error: {exc}").classes("text-red-400 text-xs")

    # -------------------------------------------------------------------------
    # POST /api/set?key=<key>&value=<value>
    # -------------------------------------------------------------------------

    from nicegui import app as nicegui_app

    @nicegui_app.post("/api/set")
    async def api_set(request: Request):
        params = dict(request.query_params)
        key = params.get("key", "")
        raw_value = params.get("value", "")
        if not key:
            return JSONResponse({"error": "missing key"}, status_code=400)
        try:
            defn = registry.get_definition(key)
            if defn is None:
                return JSONResponse({"error": f"unknown key: {key}"}, status_code=404)
            # Coerce to the correct type
            type_ = defn._type or str
            if type_ is bool:
                coerced = raw_value.lower() in ("true", "1", "yes")
            else:
                coerced = type_(raw_value)
            registry.set_global(key, coerced, SettingMode.SET)
            return JSONResponse({"ok": True, "key": key, "value": coerced})
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=500)
```

- [ ] **Step 3: Create `tests/ui/harness/app.py`**

```python
"""
HarnessApp — isolated NiceGUI app for settings UI development and testing.

Usage:
    uv run python tests/ui/harness/app.py

Runs on http://localhost:8090.

Routes:
    GET  /status               — liveness probe
    GET  /node?class=...&bag=  — render a NodeSettings bag
    GET  /schema?class=...     — render a LibrarySettings/FrameworkSettings schema
    POST /api/set?key=&value=  — write to SettingsRegistry (for test teardown)
"""

import os
from pathlib import Path

from nicegui import ui, app

from haywire.core.di.config import create_library_system_service, set_library_system, set_global_injector

# Resolve barn/ relative to repo root (two levels up from tests/ui/harness/)
_HERE = Path(__file__).resolve()
_REPO_ROOT = _HERE.parent.parent.parent.parent  # tests/ui/harness/app.py → repo root
_BARN = str(_REPO_ROOT / "barn")


def main():
    workspace_root = str(_REPO_ROOT)

    library_paths = [_BARN] if os.path.isdir(_BARN) else []

    library_service = create_library_system_service(
        workspace_root=workspace_root,
        library_paths=library_paths,
        enable_file_watching=False,
        watch_settings=False,
    )
    set_library_system(library_service)
    set_global_injector(library_service.injector)

    # Register routes (imports NiceGUI page decorators — must happen after library boot)
    from tests.ui.harness.routes import register_routes
    register_routes(library_service)

    app.on_shutdown(lambda: library_service.cleanup() if hasattr(library_service, "cleanup") else None)

    ui.run(
        port=8090,
        show=False,
        title="Haywire Settings Harness",
        reload=False,
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Verify harness starts manually**

```bash
uv run python tests/ui/harness/app.py &
sleep 4
curl -s http://localhost:8090/status
kill %1
```

Expected output: `{"status":"ok"}`

- [ ] **Step 5: Commit**

```bash
git add tests/ui/harness/__init__.py tests/ui/harness/app.py tests/ui/harness/routes.py
git commit -m "feat: add settings UI harness app with /node, /schema, /status, /api/set routes"
```

---

## Task 5: Build the pytest fixture

**Files:**
- Create: `tests/ui/harness/conftest.py`

- [ ] **Step 1: Create `tests/ui/harness/conftest.py`**

```python
"""
Pytest fixtures for the settings UI harness tests.

harness (session-scoped):
    Starts HarnessApp as a subprocess, polls /status until ready, yields base URL.
    Terminates the subprocess on teardown.

reset_setting (function-scoped):
    Yields a callable reset(key, original_value) that POSTs /api/set to restore
    a setting to its original value after a test that mutated it.
"""

import subprocess
import sys
import time
from pathlib import Path

import pytest
import requests

_BASE_URL = "http://localhost:8090"
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


@pytest.fixture(scope="session")
def harness():
    """Start the harness app subprocess and wait until it is ready."""
    proc = subprocess.Popen(
        ["uv", "run", "python", "tests/ui/harness/app.py"],
        cwd=str(_REPO_ROOT),
    )
    deadline = time.time() + 20
    while time.time() < deadline:
        try:
            r = requests.get(f"{_BASE_URL}/status", timeout=1)
            if r.status_code == 200:
                break
        except Exception:
            pass
        time.sleep(0.4)
    else:
        proc.terminate()
        raise RuntimeError("Harness did not become ready within 20s")
    yield _BASE_URL
    proc.terminate()
    proc.wait(timeout=5)


@pytest.fixture
def reset_setting(harness):
    """
    Fixture that provides a callable to reset a registry key after a test.

    Usage in a test:
        def test_something(page, harness, reset_setting):
            reset_setting("testing.default_intensity", 0.5)
            # test body that changes testing.default_intensity
            # after the test, the fixture resets it back to 0.5
    """
    resets = []

    def _schedule_reset(key: str, original_value):
        resets.append((key, original_value))

    yield _schedule_reset

    for key, val in resets:
        try:
            requests.post(f"{harness}/api/set", params={"key": key, "value": str(val)}, timeout=2)
        except Exception:
            pass
```

- [ ] **Step 2: Commit**

```bash
git add tests/ui/harness/conftest.py
git commit -m "feat: add harness pytest fixture with subprocess boot and reset_setting helper"
```

---

## Task 6: Structural tests

**Files:**
- Create: `tests/ui/harness/test_structural.py`

These tests verify that the correct fields, widget types, and category groups render.

- [ ] **Step 1: Create `tests/ui/harness/test_structural.py`**

```python
"""
Structural tests: verify that the correct fields, widget types, and category
headings render for SettingsNode.example and TestingSettings.
"""

import pytest
from playwright.sync_api import Page, expect

_NODE_URL = (
    "http://localhost:8090/node"
    "?class=haybale_testing.nodes.testbed.settings_node.SettingsNode"
    "&bag=example"
)
_SCHEMA_URL = (
    "http://localhost:8090/schema"
    "?class=haybale_testing.settings.testing.TestingSettings"
)

pytestmark = pytest.mark.ui


def test_node_fields_present(page: Page, harness):
    """All non-read-only fields in SettingsNode.example appear as data-field rows."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")

    expected_fields = [
        "example_string",
        "example_float",
        "persistent_value",
        "transient_value",
        "intensity",
        "clamped_positive",
        "even_int",
    ]
    for field in expected_fields:
        expect(page.locator(f'[data-field="{field}"]')).to_be_visible()


def test_read_only_field_not_rendered(page: Page, harness):
    """read_only=True fields must NOT appear in the rendered panel."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")
    expect(page.locator('[data-field="read_only_value"]')).not_to_be_attached()


def test_float_field_uses_number_drag(page: Page, harness):
    """A float field (example_float) renders a NumberDrag, not a plain input."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")
    row = page.locator('[data-field="example_float"]')
    # NumberDrag renders a custom Vue element; NiceGUI mounts it as <number-drag>
    expect(row.locator("number-drag")).to_be_attached()
    expect(row.locator("input[type=text]")).not_to_be_attached()


def test_string_field_uses_input(page: Page, harness):
    """A string field (example_string) renders a plain text input."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")
    row = page.locator('[data-field="example_string"]')
    expect(row.locator("input")).to_be_attached()
    expect(row.locator("number-drag")).not_to_be_attached()


def test_int_field_step_one(page: Page, harness):
    """An int field (even_int) renders a NumberDrag with step=1."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")
    row = page.locator('[data-field="even_int"]')
    nd = row.locator("number-drag")
    expect(nd).to_be_attached()
    # step=1 is passed as a prop
    step_attr = nd.get_attribute("step")
    assert step_attr == "1", f"expected step=1, got {step_attr!r}"


def test_category_headings_present(page: Page, harness):
    """Category expansion headings Type, Stored, Mirrors, Validator are all visible."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")
    for heading in ["Type", "Stored", "Mirrors", "Validator"]:
        expect(page.get_by_text(heading, exact=True).first).to_be_visible()


def test_schema_field_present(page: Page, harness):
    """TestingSettings.default_intensity field row appears in /schema route."""
    page.goto(_SCHEMA_URL)
    page.wait_for_selector("[data-field]")
    expect(page.locator('[data-field="default_intensity"]')).to_be_visible()
```

- [ ] **Step 2: Run structural tests (harness must be running)**

Start harness in background first, then run:

```bash
uv run python tests/ui/harness/app.py &
sleep 5
uv run pytest tests/ui/harness/test_structural.py -v
kill %1
```

Expected: all 6 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/ui/harness/test_structural.py
git commit -m "test: add structural settings UI harness tests"
```

---

## Task 7: Interaction tests

**Files:**
- Create: `tests/ui/harness/test_interaction.py`

These tests verify value set/read-back, mirror indicator rendering, and the reset button.

- [ ] **Step 1: Create `tests/ui/harness/test_interaction.py`**

```python
"""
Interaction tests: verify value write/read-back, mirror indicator (• prefix),
and the reset-to-global button.
"""

import pytest
from playwright.sync_api import Page, expect

_NODE_URL = (
    "http://localhost:8090/node"
    "?class=haybale_testing.nodes.testbed.settings_node.SettingsNode"
    "&bag=example"
)

pytestmark = pytest.mark.ui


def test_set_string_value_reflects_in_data_value(page: Page, harness):
    """Setting example_string to 'hello' updates the widget's data-value attribute."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="example_string"]')
    input_el = row.locator("input")
    input_el.triple_click()
    input_el.fill("hello")
    input_el.press("Tab")  # trigger on_change

    # data-value on the wrapping div should now be "hello"
    wrapper = row.locator("[data-value]")
    expect(wrapper).to_have_attribute("data-value", "hello")


def test_set_float_value_reflects_in_data_value(page: Page, harness):
    """Setting persistent_value via NumberDrag updates data-value to '0.7'."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="persistent_value"]')
    nd = row.locator("number-drag")
    # Trigger double-click to enter edit mode, then type value
    nd.dblclick()
    edit_input = row.locator("input")
    edit_input.fill("0.7")
    edit_input.press("Enter")

    expect(nd).to_have_attribute("data-value", "0.7")


def test_mirror_field_no_dot_prefix_initially(page: Page, harness):
    """The intensity mirror field label has no • prefix when not locally overridden."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="intensity"]')
    label_text = row.locator("label, .text-xs").first.inner_text()
    assert not label_text.startswith("•"), f"Expected no • prefix, got: {label_text!r}"


def test_mirror_field_dot_prefix_after_local_override(page: Page, harness):
    """Overriding the intensity mirror locally adds • to the label."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="intensity"]')
    nd = row.locator("number-drag")
    nd.dblclick()
    edit_input = row.locator("input")
    edit_input.fill("0.3")
    edit_input.press("Enter")
    # Page re-renders the row after local override
    page.wait_for_timeout(300)

    updated_row = page.locator('[data-field="intensity"]')
    label_text = updated_row.locator("label, .text-xs").first.inner_text()
    assert label_text.startswith("•"), f"Expected • prefix after override, got: {label_text!r}"


def test_reset_button_appears_after_override(page: Page, harness):
    """After overriding intensity locally, the reset (restart_alt) button appears."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="intensity"]')
    nd = row.locator("number-drag")
    nd.dblclick()
    edit_input = row.locator("input")
    edit_input.fill("0.3")
    edit_input.press("Enter")
    page.wait_for_timeout(300)

    updated_row = page.locator('[data-field="intensity"]')
    # NiceGUI renders Material icon buttons with the icon name as text content
    reset_btn = updated_row.locator('button:has-text("restart_alt")')
    expect(reset_btn).to_be_visible()


def test_reset_button_removes_dot_prefix(page: Page, harness):
    """Clicking the reset button on intensity removes the • prefix."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")

    # Override intensity
    row = page.locator('[data-field="intensity"]')
    nd = row.locator("number-drag")
    nd.dblclick()
    edit_input = row.locator("input")
    edit_input.fill("0.2")
    edit_input.press("Enter")
    page.wait_for_timeout(300)

    # Click reset
    updated_row = page.locator('[data-field="intensity"]')
    reset_btn = updated_row.locator('button:has-text("restart_alt")')
    reset_btn.click()
    page.wait_for_timeout(300)

    # • prefix should be gone
    final_row = page.locator('[data-field="intensity"]')
    label_text = final_row.locator("label, .text-xs").first.inner_text()
    assert not label_text.startswith("•"), f"Expected no • after reset, got: {label_text!r}"
```

- [ ] **Step 2: Run interaction tests**

```bash
uv run python tests/ui/harness/app.py &
sleep 5
uv run pytest tests/ui/harness/test_interaction.py -v
kill %1
```

Expected: all 6 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/ui/harness/test_interaction.py
git commit -m "test: add interaction tests for settings UI harness"
```

---

## Task 8: Mirror propagation tests

**Files:**
- Create: `tests/ui/harness/test_mirror.py`

These tests verify that changing a global `LibrarySetting` via `/api/set` propagates to the mirrored node field on re-render.

- [ ] **Step 1: Create `tests/ui/harness/test_mirror.py`**

```python
"""
Mirror propagation tests: verify that changing a global LibrarySetting via
/api/set propagates to the mirrored NodeSettings field on re-render.
"""

import pytest
import requests
from playwright.sync_api import Page, expect

_NODE_URL = (
    "http://localhost:8090/node"
    "?class=haybale_testing.nodes.testbed.settings_node.SettingsNode"
    "&bag=example"
)
_BASE_URL = "http://localhost:8090"

pytestmark = pytest.mark.ui


def test_intensity_mirror_shows_default_value(page: Page, harness, reset_setting):
    """intensity field shows the library default (0.5) when not locally overridden."""
    reset_setting("testing.default_intensity", 0.5)

    # Ensure default is set
    requests.post(f"{_BASE_URL}/api/set", params={"key": "testing.default_intensity", "value": "0.5"})

    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="intensity"]')
    nd = row.locator("number-drag")
    expect(nd).to_have_attribute("data-value", "0.5")


def test_global_setting_change_propagates_to_mirror(page: Page, harness, reset_setting):
    """Changing testing.default_intensity to 0.9 and re-navigating shows 0.9 in intensity."""
    reset_setting("testing.default_intensity", 0.5)

    # Change global default
    r = requests.post(
        f"{_BASE_URL}/api/set",
        params={"key": "testing.default_intensity", "value": "0.9"},
    )
    assert r.json()["ok"] is True

    # Re-navigate to get a fresh render with the new global value
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="intensity"]')
    nd = row.locator("number-drag")
    expect(nd).to_have_attribute("data-value", "0.9")


def test_schema_page_shows_library_default(page: Page, harness, reset_setting):
    """TestingSettings schema page renders default_intensity with its current value."""
    reset_setting("testing.default_intensity", 0.5)

    requests.post(f"{_BASE_URL}/api/set", params={"key": "testing.default_intensity", "value": "0.5"})

    page.goto(
        "http://localhost:8090/schema"
        "?class=haybale_testing.settings.testing.TestingSettings"
    )
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="default_intensity"]')
    nd = row.locator("number-drag")
    expect(nd).to_have_attribute("data-value", "0.5")


def test_schema_page_reflects_api_set_change(page: Page, harness, reset_setting):
    """After /api/set changes default_intensity to 0.7, schema page shows 0.7."""
    reset_setting("testing.default_intensity", 0.5)

    requests.post(f"{_BASE_URL}/api/set", params={"key": "testing.default_intensity", "value": "0.7"})

    page.goto(
        "http://localhost:8090/schema"
        "?class=haybale_testing.settings.testing.TestingSettings"
    )
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="default_intensity"]')
    nd = row.locator("number-drag")
    expect(nd).to_have_attribute("data-value", "0.7")
```

- [ ] **Step 2: Run mirror tests**

```bash
uv run python tests/ui/harness/app.py &
sleep 5
uv run pytest tests/ui/harness/test_mirror.py -v
kill %1
```

Expected: all 4 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/ui/harness/test_mirror.py
git commit -m "test: add mirror propagation tests for settings UI harness"
```

---

## Task 9: Validation tests

**Files:**
- Create: `tests/ui/harness/test_validation.py`

These tests verify that invalid values (failed validator, out-of-range) surface an error indicator in the DOM.

> **Note on error indicator:** The current `_render_widget_impl` silently swallows exceptions in the setter (the `try/except pass` block in `_make_reactive_setter`). Before these tests can pass, `_render_reactive_field_row` needs to render an error indicator div when the last write was rejected. This task includes that targeted addition to `_settings_panel_base.py`.

- [ ] **Step 1: Add error indicator rendering to `_render_reactive_field_row` in `_settings_panel_base.py`**

The setter must capture validation failures and trigger a DOM update. Replace `_make_reactive_setter` with a version that tracks error state, and update `_render_reactive_field_row` to render an error div:

```python
def _make_reactive_setter(obj: "Settings", attr_name: str, error_container=None):
    """Return a make_setter(coerce) factory that writes to a Settings instance."""

    def make_setter(coerce):
        def handler(e):
            try:
                setattr(obj, attr_name, coerce(e.value))
                # Clear any previous error
                if error_container is not None:
                    error_container.clear()
            except Exception as exc:
                if error_container is not None:
                    error_container.clear()
                    with error_container:
                        ui.label(str(exc)).classes(
                            "text-xs text-red-400 px-2"
                        ).props('data-error="true"')

        return handler

    return make_setter
```

And update `_render_reactive_field_row` to create the error container and pass it:

```python
def _render_reactive_field_row(obj: "Settings", attr_name: str, defn: "FieldDescriptor") -> None:
    """Render a single reactive field row, with optional reset button for mirrored fields."""
    container = ui.element("div").classes("w-full")

    def _build_row():
        container.clear()
        with container:
            is_mirrored = bool(defn._mirror_key)
            is_locally_overridden = is_mirrored and obj.is_locally_set(attr_name)

            label_text = defn._label or attr_name
            if is_locally_overridden:
                label_text = f"• {label_text}"

            error_container = ui.element("div").classes("w-full")

            with ui.row().classes(_ROW_CLASSES).props(f'data-field="{attr_name}"'):
                lbl = ui.label(label_text).classes(_LABEL_CLASSES)
                if defn._description:
                    lbl.tooltip(defn._description)
                _render_widget_impl(
                    defn,
                    getattr(obj, attr_name),
                    _make_reactive_setter(obj, attr_name, error_container),
                )
                if is_locally_overridden:
                    ui.button(icon="restart_alt").props("flat dense size=xs").tooltip(
                        "Reset to global default"
                    ).on("click", lambda _o=obj, _n=attr_name: (_o.reset(_n), _build_row()))

    _build_row()
```

- [ ] **Step 2: Run existing tests to confirm nothing regressed**

```bash
uv run pytest tests/ui/test_panel_registry.py -v
uv run pytest tests/ui/harness/test_structural.py tests/ui/harness/test_interaction.py -v
```

Expected: all tests PASS.

- [ ] **Step 3: Create `tests/ui/harness/test_validation.py`**

```python
"""
Validation tests: verify that invalid values surface a data-error DOM element.
"""

import pytest
from playwright.sync_api import Page, expect

_NODE_URL = (
    "http://localhost:8090/node"
    "?class=haybale_testing.nodes.testbed.settings_node.SettingsNode"
    "&bag=example"
)

pytestmark = pytest.mark.ui


def test_odd_integer_fails_validator(page: Page, harness):
    """Setting even_int to 3 (odd) produces a data-error element."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="even_int"]')
    nd = row.locator("number-drag")
    nd.dblclick()
    edit_input = row.locator("input")
    edit_input.fill("3")
    edit_input.press("Enter")
    page.wait_for_timeout(300)

    expect(page.locator('[data-error="true"]').first).to_be_visible()


def test_negative_clamped_positive_fails_validator(page: Page, harness):
    """Setting clamped_positive to -1 (negative) produces a data-error element."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="clamped_positive"]')
    nd = row.locator("number-drag")
    nd.dblclick()
    edit_input = row.locator("input")
    edit_input.fill("-1")
    edit_input.press("Enter")
    page.wait_for_timeout(300)

    expect(page.locator('[data-error="true"]').first).to_be_visible()


def test_valid_value_clears_error(page: Page, harness):
    """After fixing even_int to 4 (even), the data-error element disappears."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")

    # First produce an error
    row = page.locator('[data-field="even_int"]')
    nd = row.locator("number-drag")
    nd.dblclick()
    edit_input = row.locator("input")
    edit_input.fill("3")
    edit_input.press("Enter")
    page.wait_for_timeout(300)
    expect(page.locator('[data-error="true"]').first).to_be_visible()

    # Now fix it
    nd.dblclick()
    edit_input = row.locator("input")
    edit_input.fill("4")
    edit_input.press("Enter")
    page.wait_for_timeout(300)

    expect(page.locator('[data-error="true"]')).not_to_be_attached()


def test_float_exceeding_max_is_clamped(page: Page, harness):
    """example_float with max=1.0: setting 2.0 should be clamped to 1.0 by NumberDrag."""
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="example_float"]')
    nd = row.locator("number-drag")
    nd.dblclick()
    edit_input = row.locator("input")
    edit_input.fill("2.0")
    edit_input.press("Enter")
    page.wait_for_timeout(300)

    # NumberDrag clamps at max — data-value should be "1.0", not "2.0"
    val = nd.get_attribute("data-value")
    assert float(val) <= 1.0, f"Expected clamped value ≤ 1.0, got {val!r}"
```

- [ ] **Step 4: Run validation tests**

```bash
uv run python tests/ui/harness/app.py &
sleep 5
uv run pytest tests/ui/harness/test_validation.py -v
kill %1
```

Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add barn/haybale-core/haybale_core/panels/_settings_panel_base.py \
        tests/ui/harness/test_validation.py
git commit -m "feat: add error indicator to settings panel renderer; add validation UI tests"
```

---

## Task 10: Full suite run and final commit

- [ ] **Step 1: Run the full harness test suite**

```bash
uv run python tests/ui/harness/app.py &
sleep 5
uv run pytest tests/ui/harness/ -v
kill %1
```

Expected: all tests in all 4 files PASS.

- [ ] **Step 2: Run the full project test suite to check for regressions**

```bash
uv run pytest -m "not integration" -q
```

Expected: all tests PASS with no new failures.

- [ ] **Step 3: Final commit**

```bash
git add -u
git commit -m "feat: settings UI harness complete — structural, interaction, mirror, validation tests"
```

---

## Running the harness manually

```bash
# Start harness (stays running, open browser to inspect)
uv run python tests/ui/harness/app.py

# Render SettingsNode.example bag
# http://localhost:8090/node?class=haybale_testing.nodes.testbed.settings_node.SettingsNode&bag=example

# Render TestingSettings schema
# http://localhost:8090/schema?class=haybale_testing.settings.testing.TestingSettings

# Run all harness tests (harness must already be running)
uv run pytest tests/ui/harness/ -v

# Or run a specific file
uv run pytest tests/ui/harness/test_structural.py -v
```
