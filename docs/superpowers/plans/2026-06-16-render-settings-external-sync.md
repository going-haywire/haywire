# render_settings External Model Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `render_settings` widgets reflect changes made to the underlying `Settings` object from *outside* the panel (another browser tab editing the shared `props` object, a worker, or mirror/global propagation).

**Architecture:** `render_settings` subscribes once to the `Settings` instance via its existing `subscribe(callback)` API. On any `_on_property_change`, the callback dispatches by field name to that row's *in-place* display updater — mutating the existing widget's `.value` and the label/reset chrome (NiceGUI "Case 3", safe from any asyncio task), never rebuilding elements. The echo loop self-terminates because both `BindableProperty.__set__` and `setting.__set__` short-circuit on unchanged values. The subscription is torn down when the rendered column leaves the DOM, using the `_handle_delete` anchor pattern already used by `NodePortsPanel`.

**Tech Stack:** Python, NiceGUI (Quasar/Vue 3), haywire reactive `setting` descriptors, Playwright (UI harness tests at `tests/ui/harness/`).

---

## Background: why this design (read before starting)

Five facts from the codebase that the implementation depends on. Do not re-litigate them — they were verified during design.

1. **`Settings.subscribe(cb)`** ([settings.py:147](../../../packages/haywire-core/src/haywire/core/settings/settings.py#L147)) registers `cb(name, value, old)`, fired by `_on_property_change` on *every* value change — direct `setattr`, mirror propagation ([settings.py:141](../../../packages/haywire-core/src/haywire/core/settings/settings.py#L141)), and `reset()`. `name` is always the field's `attr_name` (no key translation needed). Pair it with `unsubscribe(cb)`.

2. **The echo loop self-terminates by value-equality short-circuit — this is the house pattern, not a hack.** `setting.__set__` only fires `_on_property_change` when `value != old` ([descriptor.py:280](../../../packages/haywire-core/src/haywire/core/settings/descriptor.py#L280)). NiceGUI's `BindableProperty.__set__` only fires its change handler when the value actually changed (`.venv/.../nicegui/binding.py` ~L273). So setting `widget.value = current_model_value` is a no-op when unchanged, and writing an already-equal model value back does not re-fire.

   **This is exactly how the established widget system works.** `PropertyBinding.sync_to_view` ([binding.py:127](../../../packages/haywire-core/src/haywire/ui/widget/binding.py#L127)) does a plain `setattr(ui_element, "value", view_value)` with **no suppression flag**; `BaseWidget` avoids echo *structurally* by not subscribing the view→model loop back to the model (`subscribe_model_to_view=False`, [base.py:99](../../../packages/haywire-core/src/haywire/ui/widget/base.py#L99)), then relying on the same equality short-circuit. We follow the same model→view discipline: a plain `.value` set, no per-write fire-suppression flag. **Do not invent a suppression/origin flag — it would be *less* idiomatic than the existing widget system.** What we DO make explicit is the structural guarantee (Task 2, Step 4 below): a test that fails loudly if the loop ever stops self-terminating.

3. **In-place mutation is the only foreign-task-safe update.** Per [.insights/feedback_nicegui_async.md](../../../.insights/feedback_nicegui_async.md): mutating an existing element's `.value`/`.props()`/`.set_visibility()`/`.text` (Case 3) is safe from any asyncio task; creating/rebuilding elements (Case 2, e.g. `@ui.refreshable.refresh()`) is NOT safe from a foreign task. A cross-tab write runs *our* callback on the *writer's* asyncio task, so the callback must only do Case-3 mutations. **Never call `row_content.refresh()` from the subscription callback.**

4. **`NumberDrag.value` setter is echo-safe** — it writes `_props` only and does not call its change handler ([drag.py:64](../../../packages/haywire-core/src/haywire/ui/components/number/drag.py#L64)). Stock NiceGUI `ValueElement`s (`ui.select`, `ui.switch`, `ui.input`, `ui.color_input`) DO fire their handler on `.value =`, but fact 2 makes that harmless.

5. **Teardown anchor pattern** — `NodePortsPanel._anchor_cleanup_to_element` ([node_ports.py:92-110](../../../barn/haybale-graph-editor/haybale_graph_editor/panels/properties/introspect/node_ports.py#L92-L110)) wraps `element._handle_delete` so cleanup fires on both redraw (`content.clear()`) and page close. Use the same technique to call `obj.unsubscribe(cb)`. (Sibling precedent: `BaseWidget.cleanup` is idempotent and drops its `port.data.on_changed` subscription the same way, [base.py:114-133](../../../packages/haywire-core/src/haywire/ui/widget/base.py#L114-L133).)

## Relationship to `BaseWidget` (read this — it is the closest existing pattern)

`BaseWidget` ([base.py](../../../packages/haywire-core/src/haywire/ui/widget/base.py)) already implements model→view sync for **port** widgets: subscribe to the model's change channel (`port.data.on_changed`), dispatch to `on_model_changed(value)`, mutate the element in place, sync once at render, tear down idempotently. This plan deliberately **mirrors that shape** for `Settings` panels but does **not** share its code, because the two reactive substrates are genuinely different animals:

- `BaseWidget` binds **one `DataPort` → one value** (`port.data.on_changed` carries a single value; `bind()` maps it to one element prop).
- `render_settings` renders **one `Settings` object → N fields** (`Settings.subscribe` carries `(name, value, old)`; dispatch is *by field name* to N row updaters).

Unifying them behind one helper would mean parameterizing away the single-value-vs-multi-field difference that makes each simple — a net loss. So: same discipline (subscribe → in-place apply → idempotent teardown → explicit initial sync), separate implementations. A future unification is possible but is an explicit class-hierarchy decision (CLAUDE.md: confirm before touching `BaseWidget`), **out of scope here**.

## Design summary (locked decisions)

- **Channel:** `Settings.subscribe`, not the signal bus (catches non-UI writers too). Mirrors `BaseWidget`'s "subscribe to the model's own change channel" discipline.
- **Mechanism:** in-place widget mutation (Case 3); no rebuilds. Echo handled the same way `BaseWidget`/`PropertyBinding` handle it: plain `.value` set + value-equality short-circuit, **no fire-suppression flag** (see background fact 2).
- **Explicit initial sync:** after wiring the subscription, call each row updater once so the apply path is exercised at render — same as `BaseWidget.render` calling `on_model_changed` once ([base.py:107](../../../packages/haywire-core/src/haywire/ui/widget/base.py#L107)). This makes "the widget shows the model" a property of the *apply path*, not an accident of how the widget was constructed.
- **Override chrome:** reset button is *always* rendered and toggled via `set_visibility(is_locally_set)`; the `•` prefix is a mutable `label.text`. No conditional element creation.
- **Shape:** `_render_widget_impl` returns an `apply(value)` closure. `_render_vec_field_rows` returns one too. `_render_field_row` (registry path) discards the return.
- **Subscription model:** one `obj.subscribe(cb)` per `render_settings(obj)` call; dispatch by `name` to a `{attr_name: apply}` map; anchored to the outer `ui.column`.
- **Scope (NOT in this change):** no core/settings edits, no `@panel` decorator edits, no new Signal, no `render_keys`/`render_schema` subscription (those render registry definitions, not a single `Settings` instance — out of scope).

---

## File Structure

- **Modify:** `packages/haywire-core/src/haywire/ui/panel/render_utils.py`
  - `_render_widget_impl` → return `Callable[[Any], None]` (an `apply(value)` updater).
  - `_render_vec_field_rows` → return `Callable[[Any], None]`.
  - `_render_label` (inside `_render_reactive_field_row`) → always render reset button, expose label + button for in-place mutation.
  - `_render_reactive_field_row` → build a per-row `apply` and register it in a shared dispatch map; stop relying on `row_content.refresh()` for value/override changes.
  - `render_settings` → create the dispatch map, `obj.subscribe(cb)`, anchor `obj.unsubscribe(cb)` to the column's `_handle_delete`.
- **Create:** `tests/ui/harness/test_external_sync.py` (Playwright UI tests — the model→view sync behavior).
- **Create:** `tests/ui/panel/test_render_settings_echo.py` (unit test — pins the echo-self-termination guarantee at the model layer; no browser).
- **Modify:** `tests/ui/harness/routes.py` — add a `/node-live` page exposing a server-side "mutate the model" button per field, so a test can trigger an external write and assert the widget updates without UI interaction.

> Decomposition note: all production changes live in one file (`render_utils.py`) because they are a single cohesive behavior and the functions are tightly coupled through closures. Splitting would fragment the closures. This matches the file's existing structure.

---

## Task 1: `_render_widget_impl` returns an `apply(value)` updater

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/panel/render_utils.py` (`_render_widget_impl`, lines ~293-428)
- Test: `tests/ui/harness/test_external_sync.py`, `tests/ui/harness/routes.py`

The function currently returns `None` from every branch. Change every branch to build and return a closure `apply(value)` that mutates the *existing* widget in place (Case 3). The reactive caller will store these; the registry caller discards them.

- [ ] **Step 1: Add the `/node-live` harness route (test infrastructure)**

In `tests/ui/harness/routes.py`, inside `register_routes(...)`, after the existing `/node` page (after line ~241), add a new page that keeps the `Settings` instance in scope and exposes one button per field that performs a *server-side* `setattr` (simulating an external/cross-tab write):

```python
    # -------------------------------------------------------------------------
    # GET /node-live?class=<dotted.ClassName>&bag=<bag_name>
    #
    # Like /node, but additionally mounts a server-side "external write" button
    # per field. Clicking a button does setattr(instance, field, value) WITHOUT
    # touching the rendered widget — simulating a change from another tab /
    # worker / mirror propagation. Backs test_external_sync.py.
    # -------------------------------------------------------------------------

    @ui.page("/node-live")
    async def node_live_page(request: Request):
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
                settings_instance = settings_cls(registry=registry)
                render_settings(settings_instance)

                # External-write triggers. Each button mutates the model only.
                def _ext_set(field: str, value):
                    def _do():
                        setattr(settings_instance, field, value)
                    return _do

                ui.button("ext-string", on_click=_ext_set("example_string", "EXTERNAL")).props(
                    'data-testid="ext-string"'
                )
                ui.button("ext-float", on_click=_ext_set("persistent_value", 9.0)).props(
                    'data-testid="ext-float"'
                )
                ui.button("ext-bool", on_click=_ext_set("example_bool", True)).props(
                    'data-testid="ext-bool"'
                )
                ui.button("ext-choice", on_click=_ext_set("example_choices", "option_b")).props(
                    'data-testid="ext-choice"'
                )
                ui.button("ext-mirror", on_click=_ext_set("intensity", 0.7)).props(
                    'data-testid="ext-mirror"'
                )
            except Exception as exc:
                ui.label(f"Error: {exc}").classes("text-red-400 text-xs")
```

> Note: `example_choices` options — confirm `option_b` is a valid choice key by reading [settings_node.py:51-57](../../../barn/haybale-testing/haybale_testing/nodes/testbed/settings_node.py#L51-L57). If the keys differ, use a real one.

- [ ] **Step 2: Write the failing test (string field external sync)**

Create `tests/ui/harness/test_external_sync.py`:

```python
"""
External-sync tests: a value changed on the Settings model from outside the
panel (another tab / worker / mirror) must update the rendered widget in place,
without a panel rebuild.
"""

import pytest
from playwright.sync_api import Page, expect

_LIVE_URL = (
    "http://localhost:8090/node-live"
    "?class=haybale_testing.nodes.testbed.settings_node.SettingsNode&bag=example"
)

pytestmark = pytest.mark.ui


def test_external_string_change_updates_widget(page: Page, harness):
    """setattr on the model (external write) updates the string field's data-value."""
    page.goto(_LIVE_URL)
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="example_string"]')
    wrapper = row.locator("[data-value]")
    expect(wrapper).to_have_attribute("data-value", "default string")

    page.locator('[data-testid="ext-string"]').click()
    page.wait_for_timeout(300)

    expect(wrapper).to_have_attribute("data-value", "EXTERNAL")
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `uv run pytest tests/ui/harness/test_external_sync.py::test_external_string_change_updates_widget -v`
Expected: FAIL — `data-value` stays `"default string"` (no subscription yet).

- [ ] **Step 4: Refactor `_render_widget_impl` to return `apply(value)`**

In `render_utils.py`, change the signature and every branch. Full replacement of `_render_widget_impl` (lines ~293-428):

```python
def _render_widget_impl(defn: "setting", value: Any, make_setter) -> Callable[[Any], None]:
    """Shared widget dispatch. make_setter(coerce) -> on_change handler.

    Returns an ``apply(value)`` callback that updates the rendered widget IN
    PLACE (NiceGUI "Case 3" — safe from any asyncio task) when the model value
    changes externally. Setting an existing element's ``.value`` to a value it
    already holds is a no-op (BindableProperty / NumberDrag short-circuit), so
    no echo guard is needed.
    """
    # Escape for safe embedding in props strings (newlines etc. break ast.literal_eval)
    str_value = (str(value) if value is not None else "").encode("unicode_escape").decode()

    if defn._widget == "label":
        lbl = ui.label(str_value).classes(
            f"text-xs text-right truncate hw-text-muted {_WIDGET_CLASSES}"
        ).props(f'data-value="{str_value}"')

        def _apply_label(v, _lbl=lbl):
            s = (str(v) if v is not None else "").encode("unicode_escape").decode()
            _lbl.set_text(str(v) if v is not None else "")
            _lbl.props(f'data-value="{s}"')

        return _apply_label

    if defn._widget == "color":
        wrapper = ui.element("div").classes(_WIDGET_CLASSES).props(f'data-value="{str_value}"')
        with wrapper:

            def _color_handler(e, _w=wrapper, _s=make_setter(str)):
                _w.props(f'data-value="{e.value}"')
                _s(e)

            color_el = (
                ui.color_input(value=value or "#ffffff")
                .classes("w-full")
                .props("dense hide-bottom-space")
                .on_value_change(_color_handler)
            )

        def _apply_color(v, _w=wrapper, _el=color_el):
            _el.value = v or "#ffffff"
            _w.props(f'data-value="{(str(v) if v is not None else "")}"')

        return _apply_color

    resolved_choices = defn.choices
    if resolved_choices is not None:
        wrapper = (
            ui.element("div")
            .classes(f"{_WIDGET_CLASSES} overflow-hidden")
            .props(f'data-value="{str_value}"')
        )
        options_keys = (
            resolved_choices if isinstance(resolved_choices, list) else list(resolved_choices.keys())
        )
        with wrapper:

            def _select_handler(e, _w=wrapper, _s=make_setter(lambda v: v)):
                _s(e)
                _w.props(f'data-value="{str(e.value)}"')

            select_el = (
                ui.select(
                    options=resolved_choices,
                    value=value if value in options_keys else None,
                )
                .classes("w-full text-xs")
                .props("dense hide-bottom-space")
                .on_value_change(_select_handler)
            )

        def _apply_select(v, _w=wrapper, _el=select_el, _keys=options_keys):
            _el.value = v if v in _keys else None
            _w.props(f'data-value="{str(v)}"')

        return _apply_select

    if defn._type is bool:
        wrapper = ui.element("div").props(f'data-value="{str(bool(value)).lower()}"')
        with wrapper:

            def _bool_handler(e, _w=wrapper, _s=make_setter(bool)):
                _s(e)
                _w.props(f'data-value="{str(bool(e.value)).lower()}"')

            switch_el = ui.switch(value=bool(value)).props("dense").on_value_change(_bool_handler)

        def _apply_bool(v, _w=wrapper, _el=switch_el):
            _el.value = bool(v)
            _w.props(f'data-value="{str(bool(v)).lower()}"')

        return _apply_bool

    if defn._type in (int, float):
        kwargs: dict = {}
        if defn._min is not None:
            kwargs["min"] = defn._min
        if defn._max is not None:
            kwargs["max"] = defn._max
        if defn._type is int:
            kwargs["step"] = 1
            kwargs["precision"] = 0
        elif defn._type is float:
            kwargs["step"] = _float_step_from_default(defn._default)
        coerce = defn._type
        handler = make_setter(coerce)

        class _E:
            __slots__ = ("value",)
            value: Any

        nd_ref: list[NumberDrag | None] = [None]

        def _on_number_change(e, _h=handler, _c=coerce):
            ev = _E()
            ev.value = _c(e.args)
            _h(ev)
            if nd_ref[0] is not None:
                nd_ref[0].props(f'data-value="{str(ev.value)}"')

        nd = (
            NumberDrag(value=value if value is not None else 0, on_change=_on_number_change, **kwargs)
            .classes(_WIDGET_CLASSES)
            .props(f'data-value="{str_value}"')
        )
        nd_ref[0] = nd

        def _apply_number(v, _nd=nd, _c=coerce):
            coerced = _c(v) if v is not None else 0
            _nd.value = coerced
            _nd.props(f'data-value="{str(coerced)}"')

        return _apply_number

    # str fallback — inline input + expand-to-modal button
    wrapper = (
        ui.element("div")
        .classes(f"flex items-center gap-1 {_WIDGET_CLASSES}")
        .props(f'data-value="{str_value}"')
    )
    with wrapper:
        current_value = [str(value) if value is not None else ""]

        def _str_handler(e, _w=wrapper, _s=make_setter(str), _cv=current_value):
            _cv[0] = str(e.value)
            _s(e)
            _w.props(f'data-value="{str(e.value).encode("unicode_escape").decode()}"')

        def _str_validation(v, _defn=defn):
            return None if _defn.validate(str(v) if v is not None else "") else "Invalid value"

        input_el = ui.input(
            value=current_value[0],
            on_change=_str_handler,
            validation=_str_validation,
        ).classes("flex-1 text-xs").props("dense debounce=500")

        def _open_modal(_cv=current_value, _s=make_setter(str), _w=wrapper):
            with ui.dialog() as dlg, hui.dialog_card("w-[480px]"):
                ta = ui.textarea(value=_cv[0]).classes("w-full text-xs").props("dense autogrow")

                def _confirm():
                    v = ta.value
                    _cv[0] = v

                    class _Ev:
                        value = v

                    _s(_Ev())
                    _w.props(f'data-value="{v.encode("unicode_escape").decode()}"')
                    dlg.close()

                hui.dialog_actions(on_confirm=_confirm, on_cancel=dlg.close)
            dlg.open()

        ui.button(icon=hui.icon.expand_full, on_click=_open_modal).props("flat dense size=xs").tooltip(
            "Edit in full"
        )

    def _apply_str(v, _w=wrapper, _el=input_el, _cv=current_value):
        s = str(v) if v is not None else ""
        _cv[0] = s
        _el.value = s
        _w.props(f'data-value="{s.encode("unicode_escape").decode()}"')

    return _apply_str
```

Add `Callable` to the imports at the top of the file. Find the existing typing import line (`from typing import TYPE_CHECKING, Any`) and change it to:

```python
from typing import TYPE_CHECKING, Any, Callable
```

- [ ] **Step 5: Update the registry-path caller to discard the return**

`_render_field_row` (line ~144) calls `_render_widget_impl(defn, value, make_setter)` and ignores the result. No change needed there — Python discards an unused return value. Verify by reading [render_utils.py:134-144](../../../packages/haywire-core/src/haywire/ui/panel/render_utils.py#L134-L144); leave it as-is.

- [ ] **Step 6: Run the test — still expected to FAIL**

Run: `uv run pytest tests/ui/harness/test_external_sync.py::test_external_string_change_updates_widget -v`
Expected: still FAIL — the `apply` closures exist but nobody subscribes/calls them yet. (Wiring happens in Task 2.) The widget render itself must still work; if the page now shows an Error label, fix the closure before moving on.

- [ ] **Step 7: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/panel/render_utils.py tests/ui/harness/routes.py tests/ui/harness/test_external_sync.py
git commit -m "refactor(settings-panel): _render_widget_impl returns in-place apply() updater

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Subscribe `render_settings` to the model and dispatch to row updaters

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/panel/render_utils.py` (`render_settings` ~34-60, `_render_reactive_field_row` ~147-201)
- Test: `tests/ui/harness/test_external_sync.py`

Wire a per-render dispatch map `{attr_name: apply}`, subscribe once to `obj`, and anchor `unsubscribe` to the column teardown. Each reactive row registers its `apply` (built from Task 1's return) into the map.

- [ ] **Step 1: Change `_render_reactive_field_row` to accept and populate a dispatch map**

Replace `_render_reactive_field_row` (lines ~147-201) with this version. It (a) accepts an `updaters` dict, (b) always renders the reset button and toggles visibility, (c) registers a per-row `apply` that updates value + override chrome in place:

```python
def _render_reactive_field_row(
    obj: "Settings",
    attr_name: str,
    defn: "setting",
    updaters: dict[str, Callable[[], None]],
) -> None:
    """Render a single reactive field row.

    Registers an entry in *updaters* keyed by ``attr_name``: a zero-arg callback
    that re-reads the current model value and applies it to the rendered widget
    and override chrome IN PLACE (no element rebuild), so external changes to the
    model (other tab / worker / mirror) are reflected. See the plan background.
    """

    @ui.refreshable
    def row_content():
        is_mirrored = bool(defn._mirror_key)
        base_label = defn._label or attr_name

        def _label_text(locally_set: bool) -> str:
            return f"• {base_label}" if (is_mirrored and locally_set) else base_label

        is_locally_overridden = is_mirrored and obj.is_locally_set(attr_name)

        # Mutable references the apply() closure updates in place.
        label_ref: list[Any] = [None]
        reset_btn_ref: list[Any] = [None]
        value_apply_ref: list[Callable[[Any], None] | None] = [None]

        def _render_label():
            def _on_reset_click():
                obj.reset(attr_name)
                # reset() fires _on_property_change -> the subscription updater
                # refreshes value + chrome in place; nothing else to do here.

            with ui.row().classes("items-center gap-0 shrink-0 sf-label"):
                lbl = ui.label(_label_text(is_locally_overridden)).classes("text-xs truncate")
                if defn._description:
                    lbl.tooltip(defn._description)
                label_ref[0] = lbl
                # Always render the reset button; gate it with visibility so the
                # override chrome can be toggled in place (Case 3), never rebuilt.
                reset_btn = (
                    ui.button(icon=hui.icon.reset)
                    .props("flat dense size=xs")
                    .tooltip("Reset to global default")
                    .on("click", _on_reset_click)
                )
                reset_btn.set_visibility(is_mirrored and is_locally_overridden)
                reset_btn_ref[0] = reset_btn

        vec_meta = get_vec_meta(defn._type)
        if vec_meta is not None:
            make_setter = _make_reactive_setter(obj, attr_name, on_change_callback=None)
            value_apply_ref[0] = _render_vec_field_rows(
                base_label,
                defn._description,
                vec_meta,
                getattr(obj, attr_name),
                make_setter,
                attr_name,
                render_label=_render_label,
            )
        else:
            # String fields use ui.input(validation=) for inline error display;
            # int/float/bool use the manual error_container.
            needs_manual_error = defn._type in (int, float) or defn._type is bool
            error_container = ui.element("div").classes("w-full") if needs_manual_error else None

            with ui.row().classes(_ROW_CLASSES).props(f'data-field="{attr_name}"'):
                _render_label()
                value_apply_ref[0] = _render_widget_impl(
                    defn,
                    getattr(obj, attr_name),
                    _make_reactive_setter(obj, attr_name, error_container, on_change_callback=None),
                )

        def _apply_external():
            """Re-read model, update widget value + override chrome in place."""
            apply_value = value_apply_ref[0]
            if apply_value is not None:
                apply_value(getattr(obj, attr_name))
            if is_mirrored:
                locally_set = obj.is_locally_set(attr_name)
                if label_ref[0] is not None:
                    label_ref[0].set_text(_label_text(locally_set))
                if reset_btn_ref[0] is not None:
                    reset_btn_ref[0].set_visibility(locally_set)

        updaters[attr_name] = _apply_external

    row_content()
```

> **Key change:** `on_change_callback` is now `None` everywhere. The old code rebuilt the row via `row_content.refresh()` when override-state flipped; that rebuild is now replaced by the in-place chrome toggle in `_apply_external`. We no longer need the refresh callback at all for value/override changes.

- [ ] **Step 2: Wire subscription + teardown in `render_settings`**

Replace the body of `render_settings` (lines ~34-60). Keep the docstring; change the rendering loop and add subscribe/teardown:

```python
def render_settings(obj: "Settings") -> None:
    """Render all ``field()`` fields of a ``Settings`` instance as labelled form rows.

    - Fields with ``read_only=True`` are skipped (not rendered).
    - Fields with ``mirrors=`` that are locally overridden show a reset-to-global button.
    - Subscribes to *obj* so external changes (another tab / worker / mirror
      propagation) update the rendered widgets in place. The subscription is
      removed when the rendered column leaves the DOM.
    """

    fields = type(obj)._property_settings()
    # Exclude read-only fields from rendering
    visible_fields = {name: defn for name, defn in fields.items() if not defn._read_only}
    if not visible_fields:
        ui.label("No fields defined.").classes("text-xs hw-text-muted px-2 py-1")
        return

    sorted_fields = sorted(
        visible_fields.items(),
        key=lambda item: (
            "" if item[1]._category.lower() == "root" else item[1]._category,
            item[1]._order,
            item[0],
        ),
    )

    # attr_name -> zero-arg updater that re-reads the model and updates the
    # widget + override chrome in place. Populated by _render_reactive_field_row.
    updaters: dict[str, Callable[[], None]] = {}

    column = ui.column().classes("w-full gap-0 compact-fields").style(_COLUMN_STYLE)
    with column:
        for category, group in _group_by_category(sorted_fields, key=lambda item: item[1]._category):
            with hui.category_group(category):
                for attr_name, defn in group:
                    _render_reactive_field_row(obj, attr_name, defn, updaters)

    def _on_model_change(name: str, value: Any, old: Any) -> None:
        # Dispatch by field name to that row's in-place updater. Only Case-3
        # mutations happen inside, so this is safe even when fired from another
        # session's asyncio task (cross-tab write).
        updater = updaters.get(name)
        if updater is not None:
            updater()

    obj.subscribe(_on_model_change)

    # Explicit initial sync — exercise every row's apply() path once at render,
    # so "the widget shows the model" is a property of the apply path, not of how
    # the widget happened to be constructed. Mirrors BaseWidget.render() calling
    # on_model_changed() once after wiring its dispatch (widget/base.py:107).
    for _updater in updaters.values():
        _updater()

    # Tear down the subscription when the column leaves the DOM (redraw via
    # content.clear() or page close), mirroring NodePortsPanel's cleanup anchor.
    _original_handle_delete = column._handle_delete

    def _handle_delete() -> None:
        try:
            obj.unsubscribe(_on_model_change)
        except Exception:
            pass
        _original_handle_delete()

    column._handle_delete = _handle_delete  # type: ignore[method-assign]
```

- [ ] **Step 3: Run the string-sync test — expected to PASS**

Run: `uv run pytest tests/ui/harness/test_external_sync.py::test_external_string_change_updates_widget -v`
Expected: PASS — clicking `ext-string` flips `data-value` to `"EXTERNAL"`.

- [ ] **Step 4: Add tests for float, bool, choice, and mirror-chrome sync**

Append to `tests/ui/harness/test_external_sync.py`:

```python
def test_external_float_change_updates_numberdrag(page: Page, harness):
    """External setattr updates a NumberDrag float field's data-value."""
    page.goto(_LIVE_URL)
    page.wait_for_selector("[data-field]")

    nd = page.locator('[data-field="persistent_value"] [data-number_drag]')
    expect(nd).to_have_attribute("data-value", "1.0")

    page.locator('[data-testid="ext-float"]').click()
    page.wait_for_timeout(300)

    expect(nd).to_have_attribute("data-value", "9.0")


def test_external_bool_change_updates_switch(page: Page, harness):
    """External setattr updates a bool field's data-value wrapper."""
    page.goto(_LIVE_URL)
    page.wait_for_selector("[data-field]")

    wrapper = page.locator('[data-field="example_bool"] [data-value]')
    expect(wrapper).to_have_attribute("data-value", "false")

    page.locator('[data-testid="ext-bool"]').click()
    page.wait_for_timeout(300)

    expect(wrapper).to_have_attribute("data-value", "true")


def test_external_choice_change_updates_select(page: Page, harness):
    """External setattr updates a choices field's data-value wrapper."""
    page.goto(_LIVE_URL)
    page.wait_for_selector("[data-field]")

    wrapper = page.locator('[data-field="example_choices"] [data-value]')
    page.locator('[data-testid="ext-choice"]').click()
    page.wait_for_timeout(300)

    expect(wrapper).to_have_attribute("data-value", "option_b")


def test_external_mirror_change_shows_dot_and_reset(page: Page, harness):
    """External local override of a mirror field adds • and reveals reset button."""
    page.goto(_LIVE_URL)
    page.wait_for_selector("[data-field]")

    row = page.locator('[data-field="intensity"]')
    label = row.locator(".text-xs").first
    assert not label.inner_text().startswith("•")

    page.locator('[data-testid="ext-mirror"]').click()
    page.wait_for_timeout(300)

    updated = page.locator('[data-field="intensity"]')
    assert updated.locator(".text-xs").first.inner_text().startswith("•")
    expect(updated.locator('button:has-text("restart_alt")')).to_be_visible()
```

> If `example_choices` does not accept `"option_b"`, or `intensity` is not a mirror that becomes locally-set on direct `setattr`, adjust the harness values in Task 1 Step 1 accordingly (read [settings_node.py:51-117](../../../barn/haybale-testing/haybale_testing/nodes/testbed/settings_node.py#L51-L117)).

- [ ] **Step 4b: Add the echo-discipline regression test (makes background fact 2 explicit & enforced)**

The whole design rests on the model→view→model loop self-terminating after one hop. Rather than trust the dual short-circuit silently, assert it. This is a *unit* test on the model layer (no browser): it proves that applying a value the model already holds does NOT re-fire `_on_property_change`, which is precisely what stops the cross-tab loop. If a future NiceGUI/descriptor change breaks the short-circuit, this fails loudly instead of producing a two-tab write storm in production.

Create `tests/ui/panel/test_render_settings_echo.py`:

```python
"""
Echo-discipline regression for render_settings external sync.

The cross-tab update path (render_utils._on_model_change -> apply -> widget.value
-> widget on_change -> setattr(model)) is only safe because writing a value the
model already holds does NOT re-fire _on_property_change. This test pins that
guarantee at the model layer, independent of the browser.
"""

import pytest

# Per CLAUDE.md test trap: import editor before other haywire modules.
import haywire.core.graph.editor  # noqa: F401

from haybale_testing.nodes.testbed.settings_node import SettingsNode

pytestmark = pytest.mark.unit


def _make_bag(settings_registry):
    """A real SettingsNode.example bag wired to the registry (extended mode)."""
    return SettingsNode.example(registry=settings_registry)


def test_setting_write_of_equal_value_does_not_refire(settings_registry):
    """Writing the current value back fires NO change callback (loop terminator)."""
    bag = _make_bag(settings_registry)
    calls = []
    bag.subscribe(lambda name, value, old: calls.append((name, value)))

    # First write changes the value -> exactly one callback.
    bag.example_string = "alpha"
    assert calls == [("example_string", "alpha")]

    # Writing the SAME value back must not fire again — this is what makes the
    # model->view->model echo self-terminate after one hop.
    bag.example_string = "alpha"
    assert calls == [("example_string", "alpha")], f"echo re-fired: {calls}"


def test_distinct_then_equal_write_fires_exactly_once(settings_registry):
    """A change then a redundant write yields exactly one callback total per change."""
    bag = _make_bag(settings_registry)
    calls = []
    bag.subscribe(lambda name, value, old: calls.append(value))

    bag.persistent_value = 5.0
    bag.persistent_value = 5.0  # redundant — must be a no-op
    bag.persistent_value = 6.0

    assert calls == [5.0, 6.0], f"expected one callback per real change, got {calls}"
```

- [ ] **Step 4c: Run the echo test**

Run: `uv run pytest tests/ui/panel/test_render_settings_echo.py -v`
Expected: PASS.

> If there is no `settings_registry` fixture, look at how `tests/ui/harness/` and `tests/core/test_state/` construct a registry (e.g. `library_service.get_settings_registry()` in [routes.py:204](../../../tests/ui/harness/routes.py#L204)) and add a local fixture in this test file. If `SettingsNode.example` requires more wiring than a bare registry, fall back to the smallest schema class that has a plain `setting[str]` and a `setting[float]` field.

- [ ] **Step 5: Run all external-sync tests**

Run: `uv run pytest tests/ui/harness/test_external_sync.py -v`
Expected: all PASS.

- [ ] **Step 6: Run the existing interaction/structural tests — no regressions**

The override chrome changed from "conditionally created" to "always created + visibility toggle". Confirm the existing `•`/reset tests still pass.

Run: `uv run pytest tests/ui/harness/test_interaction.py tests/ui/harness/test_structural.py -v`
Expected: all PASS. If `test_reset_button_appears_after_override` fails because the button is now always in the DOM, note the assertion uses `to_be_visible()` (not `to_be_attached()`), so visibility-gating satisfies it — but verify.

- [ ] **Step 7: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/panel/render_utils.py tests/ui/harness/routes.py tests/ui/harness/test_external_sync.py
git commit -m "feat(settings-panel): reflect external model changes in render_settings

Subscribe each render_settings() call to the Settings instance and update
widgets + override chrome in place on change, so edits from another tab,
a worker, or mirror propagation are shown live. Subscription is torn down
when the rendered column leaves the DOM.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: `_render_vec_field_rows` returns an `apply(value)` updater

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/panel/render_utils.py` (`_render_vec_field_rows` ~209-274)
- Test: `tests/ui/harness/test_external_sync.py`, `tests/ui/harness/routes.py`

Task 2 stores `_render_vec_field_rows(...)`'s return as the vec row's value updater, but the function currently returns `None`. Make it return an `apply(value)` that sets each component `NumberDrag.value` in place.

- [ ] **Step 1: Add a vec external-write button to the harness**

In `tests/ui/harness/routes.py`, inside `/node-live`, add another button alongside the others (use a real vec field — `example_vec3f` from [settings_node.py:71](../../../barn/haybale-testing/haybale_testing/nodes/testbed/settings_node.py#L71)):

```python
                ui.button("ext-vec", on_click=_ext_set("example_vec3f", (1.0, 2.0, 3.0))).props(
                    'data-testid="ext-vec"'
                )
```

> Confirm the vec field's coercion accepts a tuple; if it requires a specific Vec type, import and construct it (read [settings_node.py:71-83](../../../barn/haybale-testing/haybale_testing/nodes/testbed/settings_node.py#L71-L83)).

- [ ] **Step 2: Write the failing vec test**

Append to `tests/ui/harness/test_external_sync.py`:

```python
def test_external_vec_change_updates_components(page: Page, harness):
    """External setattr on a vec field updates each component NumberDrag in place."""
    page.goto(_LIVE_URL)
    page.wait_for_selector("[data-field]")

    page.locator('[data-testid="ext-vec"]').click()
    page.wait_for_timeout(300)

    nds = page.locator('[data-field="example_vec3f"] [data-number_drag]')
    expect(nds.nth(0)).to_have_attribute("data-value", "1.0")
    expect(nds.nth(1)).to_have_attribute("data-value", "2.0")
    expect(nds.nth(2)).to_have_attribute("data-value", "3.0")
```

- [ ] **Step 3: Run to verify it fails**

Run: `uv run pytest tests/ui/harness/test_external_sync.py::test_external_vec_change_updates_components -v`
Expected: FAIL — vec components don't update (vec apply returns `None`).

- [ ] **Step 4: Make `_render_vec_field_rows` return `apply(value)`**

Change the signature to return `Callable[[Any], None]`, collect the per-component `NumberDrag` references during the build loop, and return a closure that sets each one. Replace the function body (lines ~209-274), keeping the docstring intro:

```python
def _render_vec_field_rows(
    label_text: str,
    description: str,
    vec_meta,
    value: Any,
    make_setter,
    attr_name: str = "",
    render_label=None,
) -> Callable[[Any], None]:
    """Render a vector field as a tight column of rows aligned to the panel grid.

    Returns an ``apply(value)`` callback that updates each component NumberDrag in
    place when the model changes externally.
    """
    current = list(value) if value is not None else [0] * vec_meta.length
    while len(current) < vec_meta.length:
        current.append(0)
    current = current[: vec_meta.length]

    step = 1 if vec_meta.element_type is int else None
    precision = 0 if vec_meta.element_type is int else None
    coerce = vec_meta.element_type

    class _E:
        __slots__ = ("value",)
        value: list

    def _make_component_setter(idx, _cv=current, _ms=make_setter, _c=coerce):
        handler = _ms(lambda v: v)

        def _on_change(e, _i=idx, _h=handler, _cv=_cv, _c=_c):
            _cv[_i] = _c(e.args)
            ev = _E()
            ev.value = list(_cv)
            _h(ev)

        return _on_change

    nd_kwargs: dict = {}
    if step is not None:
        nd_kwargs["step"] = step
        nd_kwargs["precision"] = precision

    prop = f'data-field="{attr_name}"' if attr_name else ""
    component_nds: list[NumberDrag] = []

    # Outer row: label left, component column right.
    with ui.row().classes(_ROW_CLASSES.replace("items-center", "items-start") + " py-1").props(prop):
        if render_label is not None:
            render_label()
        else:
            lbl = ui.label(label_text).classes(_LABEL_CLASSES)
            if description:
                lbl.tooltip(description)
        with ui.column().classes("gap-0 flex-1 pb-1").style("--hw-compact-row-min-h: 22px;"):
            for i, component_label in enumerate(vec_meta.labels):
                with ui.row().classes("w-full items-center gap-1"):
                    ui.label(component_label).classes("text-xs w-4 text-right hw-text-muted shrink-0")
                    nd = NumberDrag(
                        value=coerce(current[i]),
                        on_change=_make_component_setter(i),
                        **nd_kwargs,
                    ).classes("flex-1")
                    component_nds.append(nd)

    def _apply_vec(v, _nds=component_nds, _c=coerce, _len=vec_meta.length):
        seq = list(v) if v is not None else [0] * _len
        while len(seq) < _len:
            seq.append(0)
        for i, nd in enumerate(_nds):
            coerced = _c(seq[i])
            nd.value = coerced
            nd.props(f'data-value="{str(coerced)}"')

    return _apply_vec
```

- [ ] **Step 5: Run the vec test — expected to PASS**

Run: `uv run pytest tests/ui/harness/test_external_sync.py::test_external_vec_change_updates_components -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/panel/render_utils.py tests/ui/harness/routes.py tests/ui/harness/test_external_sync.py
git commit -m "feat(settings-panel): in-place vec field sync on external model change

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Quality gates and full-suite verification

**Files:** none (verification only)

- [ ] **Step 1: Lint the touched file**

Run: `uv run ruff check packages/haywire-core/src/haywire/ui/panel/render_utils.py tests/ui/harness/`
Expected: no errors. Fix any that are new (per CLAUDE.md, the baseline is clean).

- [ ] **Step 2: Format check**

Run: `uv run ruff format --check packages/haywire-core/src/haywire/ui/panel/render_utils.py tests/ui/harness/`
Expected: no drift. If it reports drift: `uv run ruff format packages/haywire-core/src/haywire/ui/panel/render_utils.py tests/ui/harness/` then re-stage.

- [ ] **Step 3: Type-check**

Run: `uv run mypy packages/haywire-core/src/`
Expected: no new errors. The `Callable` return-type annotations must line up; if mypy complains about `column._handle_delete` assignment, keep the `# type: ignore[method-assign]` comment (matches the NodePortsPanel precedent).

- [ ] **Step 4: Run the settings-panel UI + echo test group**

Run: `uv run pytest tests/ui/panel/test_render_settings_echo.py tests/ui/harness/test_external_sync.py tests/ui/harness/test_interaction.py tests/ui/harness/test_structural.py tests/ui/harness/test_validation.py tests/ui/harness/test_mirror.py -v`
Expected: all PASS.

- [ ] **Step 5: Run the full suite (per CLAUDE.md, required after a multi-file change)**

Run: `uv run pytest -m "not perf"`
Expected: all PASS. Investigate any failure before claiming done.

- [ ] **Step 6: Final commit if Step 2 reformatted anything**

```bash
git add -A
git commit -m "style(settings-panel): apply ruff format

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review notes (for the executing engineer)

- **Spec coverage:** Q1 external source → Task 2 subscription. Q2 channel (subscribe) → Task 2. Q3 in-place mutation → Tasks 1 & 3 `apply()` closures. Q4 override chrome in place → Task 2 Step 1 (`set_visibility` + `set_text`). Q5 `_render_widget_impl` returns updater → Task 1. Q6 one subscription per render, dispatch-by-name, teardown anchor → Task 2 Step 2.
- **Type consistency:** `apply`/`_apply_*` always takes a single model value; the row-level `_apply_external` is zero-arg and re-reads `getattr(obj, attr_name)`. `_render_widget_impl` and `_render_vec_field_rows` both return `Callable[[Any], None]`. `render_settings`' `updaters` is `dict[str, Callable[[], None]]` (zero-arg, the row wrappers).
- **No suppression flag** is intentional (background fact 2) and matches the established widget system (`PropertyBinding.sync_to_view` does a plain `.value` set; `BaseWidget` avoids echo structurally, not with a flag). The self-termination guarantee is now *enforced* by `tests/ui/panel/test_render_settings_echo.py` (Task 2 Step 4b), not merely trusted. Do not add a fire-suppression flag even if a self-write seems to "double fire" — verify with that test first.
- **`BaseWidget` is the sibling pattern, not a base class.** This plan mirrors its discipline (subscribe → in-place apply → idempotent teardown → explicit initial sync) but keeps a separate implementation because `Settings` (multi-field, dispatch-by-name) and `DataPort` (single value) are different reactive substrates. Unifying them is a deliberate class-hierarchy decision and is explicitly out of scope.
- **Explicit initial sync** (Task 2 Step 2: loop over `updaters` once after subscribing) makes correctness a property of the apply path, paralleling `BaseWidget.render()`'s one-shot `on_model_changed`.
- **Harness field-name assumptions** (`example_choices` → `option_b`, `intensity` mirror, `example_vec3f`) must be verified against [settings_node.py](../../../barn/haybale-testing/haybale_testing/nodes/testbed/settings_node.py); adjust the harness button values if reality differs.
