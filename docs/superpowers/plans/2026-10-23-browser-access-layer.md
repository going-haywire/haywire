# Browser Access Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The browser's access decisions (pointer, keyboard, gestures; canvases and panels) are derived from the server's rules and enforced by one core component; a tier change reloads the pages it affects.

**Architecture:** One rule function (`required_mode`) feeds both `EditRoute` and widget-model construction; models carry `requires`, from which one attribute `data-hw-requires` is stamped. A shell-mounted Vue component `AccessGate` owns the gate CSS, a `focusin` blur and `<html data-hw-session-mode>`. Canvas gestures read a `{event_type: mode}` map built from the server's `@handles_event(access=)` table, which becomes mandatory.

**Tech Stack:** Python 3.12, NiceGUI 3.x (custom Vue elements), Vue 3, pytest + Playwright harness.

**Spec:** `docs/superpowers/plans/2026-10-23-browser-access-layer-spec.md`

## Global Constraints

- Mode names on the wire: `"view"`, `"operate"`, `"edit"` (`LevelMode.value`). Rank view < operate < edit.
- Attribute `data-hw-requires="view|operate|edit"` replaces `data-hw-readable` and `data-hw-operable` everywhere (code, tests, docs). No alias period.
- Card content (`.ui-node-slot` descendants): unmarked counts as `edit` (negative gate, fails closed). Panel content under `[data-hw-mode-scope="session"]`: only stamped elements are gated (positive).
- Mode changes stay O(1): one attribute on a canvas root or on `<html>`, never per-widget messages.
- Unknown gesture event type in the browser: `console.error` and refused in every mode. Undeclared handler on the server: impossible (decoration `TypeError`); a handler without the marker found at dispatch is refused and logged.
- Greyed panel writers use design guide §2.11 input value: `opacity: 0.5` (with `pointer-events: none`).
- No relative imports under `barn/` (ruff TID252). App never imports a barn library.
- Glossary and ADR edits land in Task 9, with the code (not inline during earlier tasks).
- Pre-edit baseline for each task touching >1 file: `uv run ruff check <paths>` and `uv run mypy <paths>` before and after.
- Commit `barn/haybale-testing` changes before running the suite (docs test reverts it).

## Review Focus

1. **Tier unchanged by a roster edit** (another principal changed): the session must NOT reload. → Task 8 test `test_roster_change_for_another_principal_does_not_reload`.
2. **Mode drops while a panel input has focus** (lock toggled with the caret in a settings field): the field must lose focus and stop taking keys. → Task 6 test `test_lock_while_focused_blurs_the_panel_field`.
3. **Level-free settings in the Properties editor** (run settings, `render_schema` global settings) stay operable in `view`. → Task 6 test `test_unstamped_panel_widget_stays_live_in_view`.
4. **Right-click below `edit`** neither replaces the selection nor emits a context-menu event; the native menu stays suppressed. → Task 7 test `test_view_right_click_keeps_selection_and_opens_no_menu`.
5. **A widget rendered without a route** (an Inset whose host has none; test renders) carries no `data-hw-requires`, so on a card it is gated as `edit` and in a panel it is free. → Task 5 test `test_routeless_widget_is_not_stamped`.

---

### Task 1: One required-mode rule

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/access/level_mode.py` (add function), `packages/haywire-core/src/haywire/core/access/__init__.py` (export)
- Modify: `packages/haywire-core/src/haywire/core/graph/edit_route.py:102,166-171`
- Test: `tests/core/test_access/test_level_mode.py`

**Interfaces:**
- Produces: `required_mode(minimum: LevelMode, operable: bool) -> LevelMode` exported from `haywire.core.access`.

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.parametrize("minimum", list(LevelMode))
def test_required_mode_of_an_operable_target_is_its_minimum(minimum):
    assert required_mode(minimum, True) is minimum

@pytest.mark.parametrize("minimum", list(LevelMode))
def test_required_mode_of_a_non_operable_target_is_edit(minimum):
    assert required_mode(minimum, False) is LevelMode.EDIT
```

- [ ] **Step 2:** `uv run pytest tests/core/test_access/test_level_mode.py -v` → FAIL (ImportError).
- [ ] **Step 3: Implement** `required_mode` in `level_mode.py`; `EditRoute.set_port` calls `required_mode(minimum, self._port_operable(...))`; `_minimum_for` returns `required_mode(minimum, all(...operable...))`.
- [ ] **Step 4:** `uv run pytest tests/core/test_access/ tests/core/test_graph/test_edit_route.py -v` → PASS.
- [ ] **Step 5: Commit** `refactor(access): one required_mode rule for the edit route`

---

### Task 2: Strict access coercion in the decorators

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/access/tier.py` (add helper), `__init__.py` (export)
- Modify: `packages/haywire-core/src/haywire/ui/panel/decorator.py:119-121`, `packages/haywire-core/src/haywire/ui/editor/decorator.py:95-97`, `packages/haywire-core/src/haywire/core/farmhand/decorator.py:90-92`
- Test: `tests/core/test_access/test_tier.py`

**Interfaces:**
- Produces: `coerce_access(value: object) -> AccessTier` — returns an `AccessTier` as given; a plain `str` that is not a `LevelMode` via `AccessTier(value)` (`ValueError` on an unknown name); raises `TypeError` for a `LevelMode` or any other type.

- [ ] **Step 1: Write the failing tests**

```python
def test_coerce_access_keeps_a_tier():
    assert coerce_access(AccessTier.ADMIN) is AccessTier.ADMIN

def test_coerce_access_reads_a_tier_name():
    assert coerce_access("operate") is AccessTier.OPERATE

def test_coerce_access_rejects_an_unknown_name():
    with pytest.raises(ValueError):
        coerce_access("admni")

def test_coerce_access_rejects_a_level_mode():
    with pytest.raises(TypeError):
        coerce_access(LevelMode.EDIT)

def test_panel_decorator_rejects_a_level_mode():
    with pytest.raises(TypeError):
        panel(label="X", access=LevelMode.EDIT)(type("P", (BasePanel,), {}))
```
(Use the same base class the existing `@panel` tests use; mirror the last test for `@editor` and `@farmhand`.)

- [ ] **Step 2:** run `uv run pytest tests/core/test_access/test_tier.py -v` → FAIL.
- [ ] **Step 3: Implement** `coerce_access`; replace the two coercion lines in each decorator with `identity_kwargs["access"] = coerce_access(access)`. `required_access` stays as is (its fallback now only covers hand-built identities); update its docstring's third bullet to say decorators reject invalid values.
- [ ] **Step 4:** `uv run pytest tests/core/test_access/ tests/ui/panel/ tests/farmhand/ -q` → PASS.
- [ ] **Step 5: Commit** `fix(access): reject a level mode or unknown name as a surface's access tier`

---

### Task 3: Mandatory handler access

**Files:**
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/event_handlers.py:17-46`
- Modify: every `@handles_event` without `access=` (survey list): `handlers/interaction.py:69,77,86,94`, `handlers/selection.py:133,183`, `handlers/visual_layer.py:988,1037,1064,1097,1107,1117,1125,1137,1173,1201,1253,1311,1348,1487,1511,1534,1543` → `access=LevelMode.EDIT`
- Modify: `handlers/context_menu.py:910-940` → `access=LevelMode.EDIT`; drop the inner `if not self._allows(LevelMode.EDIT): return` (keep `close_open_menu()` first)
- Modify: `graph_canvas_manager.py:383-412` (refuse unknown)
- Test: `tests/graph_editor/test_canvas_event_gating.py`; update `tests/ui/test_canvas_handlers/test_event_routing.py:30,45,50,68,73,87` to pass `access=`

**Interfaces:**
- Produces: `handles_event(*event_classes, access: LevelMode)` (keyword-only, required); `handler_access(handler) -> LevelMode | None` (`None` when the marker is missing).

- [ ] **Step 1: Write the failing tests**

```python
def test_handles_event_without_access_is_a_type_error():
    with pytest.raises(TypeError):
        handles_event(UserRemoveEvent)

def test_a_handler_without_a_declared_access_is_refused_in_edit(manager_in_edit, caplog):
    # register a plain function carrying _handles_event_classes but no _handles_event_access
    ...
    assert not called
    assert "no access declared" in caplog.text

def test_context_menu_events_need_edit():
    assert handler_access(ContextMenuHandlers.process_context_menu) is LevelMode.EDIT
```

- [ ] **Step 2:** `uv run pytest tests/graph_editor/test_canvas_event_gating.py -v` → FAIL.
- [ ] **Step 3: Implement.** `handles_event` signature `(*event_classes, access: LevelMode)`; `handler_access` returns `getattr(handler, "_handles_event_access", None)`. In `_handle_canvas_event`, a `None` access logs `warning("Refused %s: no access declared", event_type)` and returns before dispatch (the drag/resize resync branch applies to it too). Context menu: below `EDIT` the menu cannot be open (`refresh_mode` closes it), so the handler moving to `EDIT` changes nothing a user sees.
- [ ] **Step 4:** `uv run pytest tests/graph_editor/ tests/ui/test_canvas_handlers/ -q` → PASS.
- [ ] **Step 5: Commit** `feat(graph-editor): every canvas event handler declares its level mode`

---

### Task 4: The session's level mode is core

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/session/context.py:48-81` (add field)
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/state/edit_state.py:24` (remove `active_mode`)
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_editor.py:987-1003` (claim writes/reads `context.level_mode`)
- Modify: `barn/haybale-haystack/haybale_haystack/editors/haystack_editor.py:538`
- Modify tests that read/write `EditState.active_mode` (survey list): `tests/graph_editor/test_graph_editor_lock.py:54,106,110,115`, `test_graph_editor_session_claim.py` (10 sites), `test_port_pen.py:42,44,56,113`, `tests/haystack/test_update_macro.py:124`, `tests/ui/panel/test_ports_panel_reorder.py:65`, `tests/studio/test_graph_editor_on_focus.py:30`, `tests/graph_editor/test_appearance_dropdown.py:72`, `test_graph_editor_levels.py:327`, `test_level_routes.py:152`, `test_graph_editor_views.py:107`
- Test: `tests/graph_editor/test_graph_editor_session_claim.py`

**Interfaces:**
- Produces: `SessionContext.level_mode: LevelMode = signal_field(LevelMode.VIEW)` — "the level mode of the level on screen in this session, as last claimed". Subscribable as `session.subscribe(SessionContext.level_mode, cb)`.

- [ ] **Step 1:** Rewrite the session-claim assertions to read `context.level_mode`; add `test_a_lock_toggle_publishes_the_session_level_mode` (subscribe to `SessionContext.level_mode`, toggle lock on the active level, assert one signal and `context.level_mode is LevelMode.OPERATE`).
- [ ] **Step 2:** run the file → FAIL.
- [ ] **Step 3: Implement** the field; move the two writers; delete `EditState.active_mode`.
- [ ] **Step 4:** `uv run pytest tests/graph_editor/ tests/haystack/ tests/ui/panel/ tests/studio/test_graph_editor_on_focus.py -q` → PASS. `git grep -n "active_mode"` returns only docs to be updated in Task 9.
- [ ] **Step 5: Commit** `refactor(session): the session's level mode moves to SessionContext`

---

### Task 5: One stamp, derived from the model

**Files:**
- Create: `packages/haywire-core/src/haywire/ui/access_stamp.py`
- Modify: `packages/haywire-core/src/haywire/ui/panel/setting_widget_model.py` (add `requires`)
- Modify: `packages/haywire-core/src/haywire/ui/widget/factory.py:24-47,70-93,136-200`
- Modify: `packages/haywire-core/src/haywire/ui/panel/render_utils.py:904-960` (`_resolve_widget_instance` takes and stamps `requires`; `render_settings` passes `required_mode(LevelMode.EDIT, defn.operable)` when it has a route, else `None`)
- Modify: `packages/haywire-core/src/haywire/ui/skin/base.py:179,196-197,230,251-252` (drop stamping and docstring sentences)
- Modify: `packages/haywire-core/src/haywire/ui/skin/pin_render.py:125,145-146`, `barn/haybale-graph-editor/haybale_graph_editor/skins/node_skin.py:821,856` → `stamp_requires(el, LevelMode.VIEW)`
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/panels/properties/introspect/node_ports.py:174-179,250-252`, `.../introspect/edge.py:176-193` → `stamp_requires(el, LevelMode.EDIT)` on pen button, drag handle, switch
- Modify: `packages/haywire-core/src/haywire/ui/components/graph/canvas.vue` — CSS gate (4510-4518), `keepsPress` (1797-1799), `_isInteractiveWidgetElement` (3957) and contract block (105-115) to `data-hw-requires`
- Modify tests using the old attributes: `tests/ui/skin/test_render_setting_widget.py:89,93`, `test_operable_stamp.py`, `test_fold_header.py:48`, `test_widget_node_skin.py:84,96,168,236`, `tests/ui/harness/test_widget_nodes.py:98-152`, `tests/ui/harness/test_level_mode_gate.py`
- Test: `tests/ui/skin/test_operable_stamp.py` (rename to `test_requires_stamp.py`)

**Interfaces:**
- Consumes: `required_mode` (Task 1).
- Produces: `stamp_requires(element: ui.element, mode: LevelMode) -> None` (sets prop `data-hw-requires="<mode.value>"`); `SettingWidgetModel(..., requires: LevelMode | None = None)` with attribute `requires`. `WidgetFactory.render_widget` stamps the returned element from `model.requires` when not `None`.

- [ ] **Step 1: Write the failing tests** (in `test_requires_stamp.py`, render through `SkinFactory.render(..., route=route)` as the existing operable-stamp tests do)

```python
def test_an_operable_card_widget_requires_operate(): ...      # data-hw-requires == "operate"
def test_a_non_operable_card_widget_requires_edit(): ...     # == "edit"
def test_a_setting_widget_requires_its_rule(): ...           # operable field "operate", non-operable "edit"
def test_routeless_widget_is_not_stamped(): ...              # SkinFactory.render(route=None) → no data-hw-requires
def test_a_panel_settings_widget_requires_edit(): ...        # render_settings(route=...) → widget cell "edit"
def test_a_panel_without_route_stamps_nothing(): ...         # render_settings(route=None)
def test_a_readable_pin_requires_view(): ...                 # add_pin_tooltip without trigger
def test_no_old_marker_remains():
    assert not subprocess.run(["git", "grep", "-nE", "data-hw-(readable|operable)", "--", "packages", "barn", "tests"],
                              capture_output=True).stdout
```

- [ ] **Step 2:** `uv run pytest tests/ui/skin/test_requires_stamp.py -v` → FAIL.
- [ ] **Step 3: Implement.** `_widget_model_for` sets `requires=required_mode(minimum, port.operable)` when route and node exist; `setting_widget_model` sets `required_mode(minimum, descriptor.operable)` when route is not `None`. CSS gate keeps its structure with `[data-hw-requires="view"]` (view) and additionally `[data-hw-requires="operate"]` (operate) as the exempt roots; `keepsPress` becomes "a `[data-hw-requires]` ancestor whose mode ranks ≤ `levelMode`"; `_isInteractiveWidgetElement` matches `[data-hw-requires="operate"]`.
- [ ] **Step 4:** `uv run pytest tests/ui/skin/ tests/ui/panel/ tests/ui/widget/ -q` then `uv run pytest tests/ui/harness/test_level_mode_gate.py tests/ui/harness/test_widget_nodes.py tests/ui/harness/test_inset.py -n 4 -q` → PASS.
- [ ] **Step 5: Commit** `refactor(ui): one data-hw-requires stamp, derived from the widget model`

---

### Task 6: AccessGate — one browser enforcer for canvas and panels

**Files:**
- Create: `packages/haywire-core/src/haywire/ui/components/access_gate/__init__.py`, `access_gate.py`, `access_gate.vue`
- Modify: `packages/haywire-core/src/haywire/ui/app/shell.py` (mount in `render()` beside `_mount_keymap_listener`, ~:993; subscribe `SessionContext.level_mode`; unsubscribe via `_lifecycle_unsubs`)
- Modify: `packages/haywire-core/src/haywire/ui/components/graph/canvas.vue:4501-4520` (move the level gate CSS out; Inset rules 4522-4528 and cursor rules stay)
- Modify: `barn/haybale-studio/haybale_studio/editors/properties_editor.py:168-172` (`.props('data-hw-mode-scope="session"')` on `_content`)
- Modify: `tests/ui/harness/routes.py` (mount `AccessGate` in `_mount_graph_canvas` pages; new `/access-gate` page)
- Test: `tests/ui/harness/test_access_gate.py`, `tests/ui/harness/test_level_mode_gate.py`, `tests/ui/test_app_shell.py`

**Interfaces:**
- Consumes: `SessionContext.level_mode` (Task 4), `data-hw-requires` (Task 5).
- Produces: `class AccessGate(ui.element, component="access_gate.vue")` with `__init__(self, *, session_mode: LevelMode = LevelMode.VIEW)` and `set_session_mode(mode: LevelMode) -> None` (prop `sessionMode`, `update()`). The `.vue` writes `document.documentElement.dataset.hwSessionMode` in `mounted` **and** in a `watch` on `sessionMode` (KeymapListener has no watcher; this one needs it). It exports one JS function `isGated(el)` used by the `focusin` capture listener on `document` (blur when gated) and exposed as `window.hwAccess.isGated` for tests.

`isGated(el)` decides:
- inside `.ui-node-slot` of an element with `data-hw-level-mode`: required = nearest `[data-hw-requires]` value, else `"edit"`; gated when it ranks above the canvas root's mode;
- inside `[data-hw-mode-scope="session"]`: gated only when a `[data-hw-requires]` ancestor ranks above `<html data-hw-session-mode>` (absent → `"view"`);
- otherwise not gated.

The `<style>` block expresses the same: the canvas rules moved from `canvas.vue` (scope selector `[data-hw-level-mode="…"] .ui-node-slot`), and for panels `html[data-hw-session-mode="view"] [data-hw-mode-scope="session"] :is([data-hw-requires="operate"],[data-hw-requires="edit"])` (operate: `edit` only) with `opacity: 0.5` on the stamped element and `pointer-events: none !important` on it and its descendants. CSS and `isGated` live in this one file; a parity test keeps them in step.

- [ ] **Step 1: Write the failing tests** (`test_access_gate.py`, page `/access-gate`: an `AccessGate`, a scope column with an input stamped `edit`, an unstamped input, and a level-mode canvas from `_mount_graph_canvas`; F9/F10/F8 switch session mode)

```python
def test_html_carries_the_session_mode(page): ...                 # after F10: documentElement.dataset.hwSessionMode == "edit"
def test_stamped_panel_input_is_gated_and_greyed_in_view(page): ... # pointer-events none, opacity 0.5
def test_unstamped_panel_widget_stays_live_in_view(page): ...
def test_panel_input_takes_focus_only_in_edit(page): ...          # Tab / click into it: activeElement != input in view
def test_lock_while_focused_blurs_the_panel_field(page): ...      # focus in edit, switch to view, type → value unchanged
def test_view_card_input_takes_no_keyboard_focus(page): ...       # canvas widget: focus() → blurred
def test_css_and_isGated_agree(page):
    # for every element under the canvas slot and the scope column, in each mode:
    # (getComputedStyle(el).pointerEvents === "none") === window.hwAccess.isGated(el)
```
Plus in `tests/ui/test_app_shell.py`: `test_shell_pushes_the_session_level_mode_to_the_gate` (set `context.level_mode = LevelMode.EDIT`, assert gate prop `sessionMode == "edit"`).

- [ ] **Step 2:** `uv run pytest tests/ui/harness/test_access_gate.py -n 4 -v` → FAIL.
- [ ] **Step 3: Implement** as specified above.
- [ ] **Step 4:** `uv run pytest tests/ui/harness/test_access_gate.py tests/ui/harness/test_level_mode_gate.py tests/ui/harness/test_inset.py tests/ui/harness/test_stacking.py tests/ui/test_app_shell.py -n 4 -q` → PASS.
- [ ] **Step 5: Commit** `feat(ui): AccessGate enforces the level mode for canvas and panels, pointer and keyboard`

---

### Task 7: Canvas gestures read the server's table

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/components/graph/canvas.py:75-93,186-196` (new prop + method; fix `set_level_mode` docstring: click and box select work in every mode)
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/graph_canvas_manager.py:227-246` (push map after `build_event_handler_map`)
- Modify: `packages/haywire-core/src/haywire/ui/components/graph/canvas.vue` gates (survey lines): resize 742/826, drag 2167 and `createUserDragStart` 2259, `_syncEdgeReconnect` 1656, paste 1216, context menu 1972/1996 and the `contextMenu*` emits, `handleDoubleClick` 1864, `_enterActiveEdge` 2878; contract block 151-169
- Test: `tests/graph_editor/test_gesture_access_map.py`, `tests/ui/harness/test_level_mode_gate.py`

**Interfaces:**
- Consumes: `handler_access` (Task 3).
- Produces: `GraphCanvasVue.set_gesture_access(access: Mapping[str, LevelMode]) -> None` (prop `gestureAccess`: `{event_type: mode.value}`); in `canvas.vue` `_allows(eventType) -> boolean`.

Gesture → event type checked:

| Gesture | `_allows(...)` |
|---|---|
| resize grips | `"userResizeEnd"` |
| node drag (start, update, end; start no longer emitted when refused) | `"userDragStart"` |
| connection drag from a pin | `"edgeCreated"` |
| reconnect | `"edgeReconnectStarted"` |
| paste request | `"userPasteClipboard"` |
| right-click (replace-then-act and every `contextMenu*` emit) | `"contextMenuSelected"` |
| double-click Enter | `"enterGroup"` |

- [ ] **Step 1: Write the failing tests**

```python
# tests/graph_editor/test_gesture_access_map.py
GESTURE_EVENT_TYPES = {"userResizeEnd", "userDragStart", "userDragUpdate", "userDragEnd", "edgeCreated",
                       "edgeReconnectStarted", "userPasteClipboard", "contextMenuSelected", "contextMenuCanvas",
                       "contextMenuEdge", "contextMenuPort", "contextMenuSurface", "enterGroup", "selectionChanged"}

def test_every_gesture_event_type_has_a_declared_access(manager):
    assert GESTURE_EVENT_TYPES <= manager.canvas_vue._props["gestureAccess"].keys()

def test_every_type_the_canvas_checks_is_a_gesture_event_type():
    checked = set(re.findall(r"_allows\('(\w+)'\)", CANVAS_VUE.read_text()))
    assert checked <= GESTURE_EVENT_TYPES
```
Harness (`test_level_mode_gate.py`):
```python
def test_view_right_click_keeps_selection_and_opens_no_menu(page): ...
def test_view_press_and_move_emits_no_drag_start(page): ...   # harness event log has no userDragStart
def test_an_unknown_gesture_type_is_refused_and_logged(page):
    # evaluate canvas._allows('noSuchEvent') in edit → false; console has "[GraphCanvas]" error
```

- [ ] **Step 2:** run both files → FAIL.
- [ ] **Step 3: Implement.** `_allows(type)`: look up `gestureAccess[type]`; missing → `console.error('[GraphCanvas] no access declared for', type)` and `false`; else rank of `levelMode` ≥ rank of the entry. Replace every listed `editing` / `levelMode === 'view'` check with it. The `editing` watcher (377-383) stays: it reacts to a mode change, not a gesture.
- [ ] **Step 4:** `uv run pytest tests/graph_editor/test_gesture_access_map.py -q` and `uv run pytest -m browser -n 4 -q` → PASS.
- [ ] **Step 5: Commit** `feat(canvas): gestures take their level mode from the server's handler table`

---

### Task 8: A tier change reloads the affected page

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/app/shell.py:1192-1215` (replace the keymap's `RosterChanged` subscription)
- Test: `tests/ui/test_app_shell.py`

**Interfaces:**
- Produces: `AppShell._on_roster_changed(self, _signal: RosterChanged) -> None`. The shell records `self._tier = resolve_tier(principal)` at render.

- [ ] **Step 1: Write the failing tests** (patch `resolve_tier` and `ui.navigate.reload`)

```python
def test_roster_change_that_changes_this_tier_notifies_and_reloads(shell, monkeypatch): ...
def test_roster_change_for_another_principal_does_not_reload(shell, monkeypatch): ...
```

- [ ] **Step 2:** `uv run pytest tests/ui/test_app_shell.py -k roster -v` → FAIL.
- [ ] **Step 3: Implement.** Compare `resolve_tier(self.session.context.principal)` with `self._tier`; on a difference, under the keymap listener's client (`with self._keymap_listener.client:`) `ui.notify("Your access changed — reloading")` and `ui.navigate.reload()`. Remove `RosterChanged` from `_mount_keymap_listener` (the reload rebuilds the keymap); update that docstring.
- [ ] **Step 4:** `uv run pytest tests/ui/test_app_shell.py tests/ui/test_shell_keymap.py -q` → PASS.
- [ ] **Step 5: Commit** `feat(shell): a tier change reloads the pages of that principal`

Known limitation (record in Task 9's ADR): edits to the security document made outside the app publish no `RosterChanged`, so they reload nothing; `RosterCache` picks them up lazily on the next check.

---

### Task 9: Docs land with the code

**Files:**
- Create: `docs/adr/0060-the-browser-projects-the-route.md` (supersedes ADR 0055 § "The browser layer"; records decisions Q4–Q13, the parity test standing in for a generated stylesheet, the context-menu handler at `EDIT`, the out-of-app roster limitation)
- Modify: `docs/adr/0055-every-user-edit-takes-the-edit-route.md` (browser-layer paragraph → "Superseded by ADR 0060"; `active_mode` mention → `SessionContext.level_mode`)
- Modify: `docs/adr/0027-*.md` (amendment: decorators reject a `LevelMode` or unknown name via `coerce_access`)
- Modify: `docs/reference/glossary.md:382` (Operable widget → **Requires (marker)** `data-hw-requires`), add **Session level mode**, update :381 Level mode
- Modify: `docs/components/skins/skin-canon.md:377-451` (pointer input below `edit` → `data-hw-requires`; tooltip triggers on gated content show only from the mode that operates them)
- Rewrite: `.insights/project_level_mode_pointer_gate.md` (new mechanism; traps: unmarked card content is `edit`; `!important` vs `.connection-pin`; inheritance + `:where()`; CSS and `isGated` must agree — parity test); update its line in `CLAUDE.md`
- Modify: `internals/handoff/level-mode-press-filter.md` (status: superseded by this plan), `docs/superpowers/plans/2026-10-22-open-follow-ups.md` (#5 part 1 → closed as known limitation)

- [ ] **Step 1:** Write the docs.
- [ ] **Step 2:** `uv run mkdocs build --strict` → no warnings; `git grep -nE "data-hw-(readable|operable)|active_mode"` → only ADR history lines.
- [ ] **Step 3:** Full gate: `uv run ruff check . && uv run ruff format --check . && uv run mypy <CLAUDE.md path list>` and `uv run pytest -m "not browser and not perf" -n 4 -q > /tmp/t.log 2>&1; echo "exit=$?"`, then `uv run pytest -m browser -n 4 -q` → all PASS.
- [ ] **Step 4: Commit** `docs: the browser access layer (ADR 0060)`
