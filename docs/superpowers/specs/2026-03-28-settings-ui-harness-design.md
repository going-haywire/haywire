# Settings UI Harness — Design Spec

**Date:** 2026-03-28
**Status:** Approved
**Goal:** Replace the manual "spin up full app → load graph → select node → open panel" workflow with a fast isolated harness that renders any settings class directly, and a Playwright-based agent test suite that verifies structural, interaction, mirror, and validation behavior.

---

## Problem

Developing and debugging the Settings UI requires navigating the full Haywire app to get a settings panel on screen. This is slow (~10s startup), manual, and not automatable. The settings system has rich behavior (mirrors, validators, widget dispatch, reset buttons) that has no automated UI verification path.

---

## Architecture

Three components:

```
tests/ui/harness/
├── __init__.py
├── app.py              # HarnessApp — boots library system, NiceGUI on port 8090
├── routes.py           # URL route handlers: /node, /schema, /status, /api/set
├── conftest.py         # pytest fixture: subprocess harness, polls /status, base_url
├── test_structural.py  # field presence, widget types, category groups, labels
├── test_interaction.py # value set/read-back, reset button, mirror indicator
├── test_mirror.py      # global LibrarySetting change → NodeSetting mirror updates
└── test_validation.py  # invalid values → error indicator in DOM
```

One targeted production code change: `NumberDrag` renders `data-value="{current}"` on its root element to support DOM-based value read-back.

---

## Component 1: Harness App (`app.py`)

**Startup:**
- Calls `create_library_system_service(workspace_root=..., library_paths=[barn/], enable_file_watching=False, watch_settings=False)` — same DI initialization as the main app, so all haybale libraries load and mirror references resolve.
- Loads the default workbench theme so CSS variables (`hw-text-muted`, etc.) render correctly, matching what the real app shows.
- Runs NiceGUI on fixed port `8090`.

**Why full library system:** Mirror resolution (e.g. `intensity` → `TestingSettings.default_intensity`) requires the referenced `LibrarySettings` class to be registered in the `SettingsRegistry`. The full library boot ensures this automatically for any settings class, present or future.

---

## Component 2: Routes (`routes.py`)

### `GET /status`
Returns `{"status": "ok"}`. Used by the pytest fixture to poll until the harness is ready.

### `GET /node?class=<dotted.ClassName>&bag=<bag_name>`
Renders a `NodeSettings` bag as a panel page.

- `class` — dotted Python path to the node class (e.g. `haybale_testing.nodes.testbed.settings_node.SettingsNode`)
- `bag` — name of the inner `NodeSettings` class (e.g. `example`)

Resolution:
1. `importlib.import_module(module_part)` + `getattr(mod, class_name)` to get the node class
2. Get the inner `NodeSettings` class by name (`getattr(node_cls, bag_name)`) and instantiate it directly — no node instance needed, since `NodeSettings` is self-contained and DI-independent
3. Call `render_reactive(settings_instance)` inside a `ui.card`

### `GET /schema?class=<dotted.ClassName>`
Renders a `LibrarySettings` or `FrameworkSettings` class as a panel page.

- `class` — dotted Python path to the schema class (e.g. `haybale_testing.settings.testing.TestingSettings`)

Resolution:
1. Import and resolve the class
2. Get the `SettingsRegistry` from the DI injector
3. Call `render_schema(schema_cls, registry)` inside a `ui.card`

### `POST /api/set?key=<setting_key>&value=<value>`
Writes a value to the `SettingsRegistry` workspace tier. Used by mirror propagation tests to change a global setting and observe the effect on node mirrors.

- Resolves the setting definition to determine the correct type (int, float, str, bool)
- Calls `registry.set_global(key, coerced_value, SettingMode.SET)`

---

## Component 3: DOM Attributes

Each field row rendered by `render_reactive()` and `render_schema()` must carry:

- `data-field="{attr_name}"` on the row container div (added in `_render_field_row` and `_render_reactive_field_row`)
- `data-value="{current_value}"` on the widget container element (added in `_render_widget_impl` for each widget type)

Standard NiceGUI widgets do not use a consistent attribute for their current value across types (`ui.input` uses `value`, `ui.switch` uses `aria-checked`, etc.), so `_render_widget_impl` must explicitly set `data-value` on the wrapping element for every branch. `NumberDrag` gets the same addition on its root element.

This ensures Playwright can always read `[data-field="intensity"] [data-value]` regardless of widget type.

---

## Component 4: Test Fixture (`conftest.py`)

```python
@pytest.fixture(scope="session")
def harness():
    proc = subprocess.Popen(["uv", "run", "python", "tests/ui/harness/app.py"])
    deadline = time.time() + 15
    while time.time() < deadline:
        try:
            if requests.get("http://localhost:8090/status", timeout=1).status_code == 200:
                break
        except Exception:
            time.sleep(0.3)
    else:
        proc.terminate()
        raise RuntimeError("Harness did not start within 15s")
    yield "http://localhost:8090"
    proc.terminate()
```

All test files receive `harness` (the base URL) and a Playwright `page` fixture.

**Test isolation:** The `/node` route creates a fresh node instance per request, so `NodeSettings` state does not leak between tests. The `/api/set` endpoint mutates the shared `SettingsRegistry`; tests that use it must reset the key in teardown (or use a dedicated fixture that resets after each test).

---

## Component 5: Test Files

### `test_structural.py`
Verifies that the correct fields, widgets, and categories render for a given settings class.

- Navigate to `/node?class=...SettingsNode&bag=example`
- Assert field rows exist for each declared field (`data-field` attributes present)
- Assert `example_float` renders a `NumberDrag` (not `ui.input`)
- Assert `example_string` renders `ui.input`
- Assert `intensity` renders `NumberDrag` (float mirror field)
- Assert `even_int` renders `NumberDrag` with `step=1`
- Assert category expansion headings: "Type", "Stored", "Mirrors", "Validator"
- Assert `read_only_value` is **not** rendered (read_only=True fields are skipped)
- Navigate to `/schema?class=...TestingSettings`
- Assert `default_intensity` field row is present

### `test_interaction.py`
Verifies that setting values via the UI are accepted and reflected back.

- Navigate to `/node?class=...SettingsNode&bag=example`
- Set `example_string` to `"hello"` via Playwright, assert `data-value="hello"` on widget
- Set `persistent_value` to `0.7` via NumberDrag, assert `data-value="0.7"`
- Assert `intensity` field row label does **not** have `•` prefix (not locally overridden)
- Set `intensity` to `0.3` (locally overriding the mirror), assert `•` prefix appears on label
- Assert reset button (`restart_alt` icon) appears next to `intensity`
- Click reset button, assert `•` prefix disappears

### `test_mirror.py`
Verifies that changing a global `LibrarySetting` propagates to mirrored `NodeSettings` fields.

- Navigate to `/node?class=...SettingsNode&bag=example`
- Read current `data-value` of `intensity` field (should be `0.5`, the default)
- `POST /api/set?key=testing.default_intensity&value=0.9`
- Re-navigate or trigger refresh, assert `intensity` `data-value` is now `0.9`
- Also navigate to `/schema?class=...TestingSettings`, change `default_intensity` via the UI, assert the change is reflected

### `test_validation.py`
Verifies that invalid values surface an error state in the DOM.

- Navigate to `/node?class=...SettingsNode&bag=example`
- Set `even_int` to `3` (odd — fails validator), assert error indicator element is present
- Set `clamped_positive` to `-1` (negative — fails validator), assert error indicator
- Set `even_int` to `4` (valid), assert error indicator disappears
- Set `example_float` to `2.0` (exceeds `max=1.0`), assert clamp or error behavior

---

## Dependencies

Add to dev dependencies:
```
playwright
pytest-playwright
```

Run once after install:
```sh
playwright install chromium
```

Run tests:
```sh
uv run pytest tests/ui/harness/ -m "not integration"
```

The harness subprocess is session-scoped — it starts once and all test files share it.

---

## Non-Goals

- No new rendering logic — harness reuses `render_reactive()` and `render_schema()` unchanged
- No graph setup, no node ports, no execution pipeline
- No CI integration in this spec (can be added later)
- No hot-reload in the harness (file watching disabled for faster startup)
