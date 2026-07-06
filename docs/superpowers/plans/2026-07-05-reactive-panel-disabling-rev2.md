# Reactive Panel Disabling Implementation Plan (rev 2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Changes from rev 1 (review findings):** (1) `set_ui_disabled` no longer signals the panel by firing a no-op `cell.set_value(cell.get_value())` echo — that broadcast reached EVERY cell subscriber (`OakDCameraNode.hb_on_color_changed`/`hb_on_ir_changed` would have re-pushed ~21 controls to a live camera on every requirements gather) and set `is_dirty` on cells that promoted ports share. UI-disabled state now travels on its own dedicated channel (`subscribe_ui_state`), mirroring NiceGUI's per-concern `BindableProperty` design where `enabled` can never cross-fire into `value`. (2) Widgets are disabled natively: `BaseWidget.set_enabled()` delegates to Quasar `:disable` when the widget root is a NiceGUI `DisableableElement` — which design-guide.md §2.11 explicitly prefers over manual styles — with the §2.11 CSS as fallback for container roots and the label fallback. (3) Rev 1's `.style("")` "clear" was a verified no-op on NiceGUI 3.13 (styles are only removed via `style(remove=...)`); all style-clearing here uses add/remove pairs. (4) `set_ui_disabled` fires only on an actual flag transition, so steady-state re-gathers cost nothing. (5) A bulk `set_ui_disabled_all(disabled)` covers whole-bag gating, replacing rev 1's hand-maintained per-stream field-name tuples (and their typo-warning scaffolding) in the OAK-D consumer.

**Goal:** Let a `setting()` field render as visibly disabled (Quasar `:disable` or reduced opacity + no interaction) in the properties panel — either because node code says so at runtime, or because another field on the same bag currently has the "wrong" value — while the field stays a completely normal, fully-writable setting from the code's perspective.

**Architecture:** Two composable, OR'd mechanisms on the existing `Settings` base class:
1. **Imperative** — a new `_ui_disabled_keys: set[str]` on every `Settings` instance, driven by `set_ui_disabled(name, bool)` / read via `is_ui_disabled(name)`. Can be seeded at construction time by a new `ui_disabled: bool = False` kwarg on `setting()`. State changes are announced on a **dedicated UI-state channel** (`subscribe_ui_state`/`unsubscribe_ui_state`) — never on the value/cell channel, which stays value-only.
2. **Declarative** — a dependent field declares `metadata={"enabled_when": (controller_field_name, expected_value)}`. The panel auto-subscribes to the controller field (that IS a value change, so it rides the existing `subscribe_field` cell channel) and live-toggles the dependent row's disabled state with no node code required.

The panel's row renderer (`_render_reactive_field_row` in `render_utils.py`, the *instance* rendering path only — not the registry-backed `LibrarySettings`/`FrameworkSettings` path) computes `disabled = is_ui_disabled(attr_name) OR enabled_when-violated` and pushes it into the widget via a new `BaseWidget.set_enabled(bool)`: Quasar `:disable` when the widget root supports it, the documented §2.11 CSS (`opacity: 0.5; pointer-events: none`, applied/removed via `style(add=)`/`style(remove=)`) otherwise.

**Tech Stack:** Python, NiceGUI/Quasar (3.13: `DisableableElement`, `Element.style(add=/remove=)` semantics), existing Haywire settings/reactive-props system (`haywire.core.settings`, `haywire.ui.widget.base`, `haywire.ui.panel.render_utils`).

## Global Constraints

- **UI-disabled state never touches a `DataField` cell.** No `set_value` (not even same-value echoes), no `is_dirty` mutation, no `on_changed` firing. The cell event keeps meaning exactly "the value changed" — one channel per concern, per the NiceGUI `BindableProperty` model. Task 1 has an explicit regression test for this.
- `set_ui_disabled` fires its listeners **only on an actual flag transition** (idempotent calls are silent no-ops).
- No changes to serialization (`to_dict()`/`from_dict()`) — `_ui_disabled_keys` is transient, never persisted.
- No changes to the registry-backed rendering path (`render_schema`, `_render_field_row`, `_render_definitions`) — this feature is instance-path only (`render_settings`, `_render_reactive_field_row`).
- No server-side write guard in the settings layer — disabling is a display/interaction concern; node code and any direct `setattr` continue to work regardless of disabled state. (Widgets whose root is a `DisableableElement` additionally get NiceGUI's built-in server-side event dropping for free — that is a bonus, not a contract.)
- Style clearing MUST use `element.style(remove=...)` — `element.style("")` does NOT clear previously applied styles (verified empirically on NiceGUI 3.13.0).
- `enabled_when` supports exact-match only: `(field_name, expected_value)`. No callables/predicates.
- `enabled_when` is same-bag only (`type(obj)._property_settings()`, not cross-node).
- An unresolvable `enabled_when` controller name fails soft: log a warning, skip the subscription, field renders normally (never auto-disabled).
- Composition rule: a row is disabled if EITHER `is_ui_disabled(name)` is `True` OR the field's live `enabled_when` condition currently evaluates to disabled. One flat OR, no precedence rules.
- Naming: `ui_disabled` (the `setting()` kwarg, the descriptor's `_ui_disabled` attribute), `Settings.set_ui_disabled`/`set_ui_disabled_all`/`is_ui_disabled`, `Settings.subscribe_ui_state`/`unsubscribe_ui_state` (listener signature `(name: str, disabled: bool)`), `BaseWidget.set_enabled(enabled: bool)`.
- Ruff (`ruff check .`, `ruff format --check .`) and mypy must stay clean on every touched file, per CLAUDE.md. Run the baseline (`uv run ruff check <path>` / `uv run mypy <path>`) before each task's edits and re-run after.

---

## File Structure

| File | Responsibility |
|---|---|
| `packages/haywire-core/src/haywire/core/settings/descriptor.py` | Add `ui_disabled: bool = False` kwarg to `setting.__init__`, stored as `self._ui_disabled`. |
| `packages/haywire-core/src/haywire/core/settings/settings.py` | Add `_ui_disabled_keys: set[str]` + `_ui_state_listeners: list` to `Settings.__init__`, `set_ui_disabled`/`set_ui_disabled_all`/`is_ui_disabled`, `subscribe_ui_state`/`unsubscribe_ui_state`, listener clearing in `cleanup()`. |
| `packages/haywire-core/src/haywire/ui/widget/base.py` | Add `DISABLED_STYLE` constant and `BaseWidget.set_enabled(bool)` (Quasar `:disable` / CSS fallback). |
| `packages/haywire-core/src/haywire/ui/panel/render_utils.py` | `render_settings`: subscribe the UI-state channel. `_render_reactive_field_row`: `enabled_when` resolution + live subscription, row marker, push disabled state into the widget. `_resolve_widget_instance`/`_build_label_widget`: return a `set_enabled` callable alongside the existing apply callback. |
| `tests/core/test_settings/test_ui_disabled.py` | New: `ui_disabled` kwarg seeding, `set_ui_disabled`/`is_ui_disabled`, transition-only channel firing, unsubscribe/cleanup, cell-untouched regression guard. No NiceGUI. |
| `tests/ui/widget/test_set_enabled.py` | New: `BaseWidget.set_enabled` — Quasar branch, CSS-fallback branch (add AND remove), unrendered-widget no-op. |
| `tests/ui/panel/test_ui_disabled_row_state.py` | New: panel-level integration — row state reflects `ui_disabled`/`enabled_when` live over the new channel, fail-soft on a bad `enabled_when` reference, OR composition. |
| `docs/components/settings/setting-canon.md` | Document `ui_disabled=`, the runtime API + UI-state channel, `enabled_when`; fix the pre-existing `render_reactive` → `render_settings` doc-drift bug. |
| `barn/haybale-visiongraph/haybale_visiongraph/nodes/oak_d_camera_node.py` | Wire the imperative mechanism: `hb_gather_requirements()` calls `set_ui_disabled_all` on the `depth`/`ir`/`color` bags based on the callback-edge requirement union. |
| `barn/haybale-visiongraph/notes.md` | Record the OAK-D stream-status-indication decision. |

---

### Task 1: `ui_disabled` flag + dedicated UI-state channel on `Settings`

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/settings/descriptor.py:151-191` (`setting.__init__`)
- Modify: `packages/haywire-core/src/haywire/core/settings/settings.py:77-94` (`__init__`), `:377-390` (`cleanup`), after `:396-401` (`is_locally_set`)
- Test: `tests/core/test_settings/test_ui_disabled.py` (new file)

**Interfaces:**
- Consumes: nothing new — existing `setting.__init__` signature, existing `Settings.__init__`/`cleanup`.
- Produces (relied on by Tasks 3 and 5):
  - `setting(..., ui_disabled: bool = False)` — stored as `self._ui_disabled: bool`.
  - `Settings.set_ui_disabled(name: str, disabled: bool) -> None` — transition-only; fires UI-state listeners; warns + ignores unknown names; NEVER touches the field's cell.
  - `Settings.set_ui_disabled_all(disabled: bool) -> None` — bulk form over every declared field on the bag; same per-field contract (transition-only, cell-free).
  - `Settings.is_ui_disabled(name: str) -> bool` — `False` for unknown names.
  - `Settings.subscribe_ui_state(callback: Callable[[str, bool], None]) -> None` / `Settings.unsubscribe_ui_state(callback) -> None`.

- [x] **Step 1: Baseline check**

Run: `uv run ruff check packages/haywire-core/src/haywire/core/settings/ && uv run mypy packages/haywire-core/src/haywire/core/settings/`
Expected: both clean (no pre-existing errors). If not clean, stop and raise it — do not proceed on a dirty baseline.

- [x] **Step 2: Write the failing tests**

Create `tests/core/test_settings/test_ui_disabled.py`:

```python
# tests/core/test_settings/test_ui_disabled.py
"""
Tests for the ui_disabled mechanism on Settings/setting():

- ui_disabled= kwarg seeds initial disabled state
- set_ui_disabled()/set_ui_disabled_all()/is_ui_disabled() runtime API
- the dedicated UI-state channel (subscribe_ui_state/unsubscribe_ui_state):
  transition-only firing, teardown, cleanup()
- the hard invariant that UI-disabled state never touches the field's
  DataField cell (no on_changed, no is_dirty) — the value channel stays
  value-only. The panel-side wiring (enabled_when, widget disabling) is
  tested in tests/ui/panel/test_ui_disabled_row_state.py.
"""

import logging

from haywire.core.settings import Settings, setting
from haywire.barn.builtin.types import BOOL, FLOAT


class UiDisabledSettings(Settings):
    normal = setting[FLOAT](1.0, label="Normal")
    starts_disabled = setting[FLOAT](2.0, label="Starts Disabled", ui_disabled=True)
    flag = setting[BOOL](True, label="Flag")


class TestUiDisabledDefault:
    def test_field_without_ui_disabled_starts_enabled(self):
        bag = UiDisabledSettings()
        assert bag.is_ui_disabled("normal") is False

    def test_field_with_ui_disabled_true_starts_disabled(self):
        bag = UiDisabledSettings()
        assert bag.is_ui_disabled("starts_disabled") is True

    def test_ui_disabled_default_does_not_affect_value_or_writes(self):
        bag = UiDisabledSettings()
        assert bag.starts_disabled == 2.0
        bag.starts_disabled = 5.0
        assert bag.starts_disabled == 5.0


class TestSetUiDisabled:
    def test_set_ui_disabled_true_then_false(self):
        bag = UiDisabledSettings()
        assert bag.is_ui_disabled("normal") is False
        bag.set_ui_disabled("normal", True)
        assert bag.is_ui_disabled("normal") is True
        bag.set_ui_disabled("normal", False)
        assert bag.is_ui_disabled("normal") is False

    def test_set_ui_disabled_does_not_affect_value_or_writes(self):
        bag = UiDisabledSettings()
        bag.set_ui_disabled("normal", True)
        assert bag.normal == 1.0
        bag.normal = 9.0
        assert bag.normal == 9.0
        assert bag.is_ui_disabled("normal") is True  # unaffected by the value write

    def test_set_ui_disabled_on_a_default_disabled_field_can_re_enable(self):
        bag = UiDisabledSettings()
        assert bag.is_ui_disabled("starts_disabled") is True
        bag.set_ui_disabled("starts_disabled", False)
        assert bag.is_ui_disabled("starts_disabled") is False

    def test_is_ui_disabled_unknown_field_returns_false(self):
        bag = UiDisabledSettings()
        assert bag.is_ui_disabled("nonexistent") is False

    def test_set_ui_disabled_unknown_field_warns_and_ignores(self, caplog):
        bag = UiDisabledSettings()
        with caplog.at_level(logging.WARNING):
            bag.set_ui_disabled("nonexistent", True)
        assert any("nonexistent" in rec.message for rec in caplog.records)
        assert bag.is_ui_disabled("nonexistent") is False


class TestSetUiDisabledAll:
    def test_bulk_disable_covers_every_field(self):
        bag = UiDisabledSettings()
        bag.set_ui_disabled_all(True)
        assert bag.is_ui_disabled("normal") is True
        assert bag.is_ui_disabled("starts_disabled") is True
        assert bag.is_ui_disabled("flag") is True

    def test_bulk_enable_clears_seeded_defaults_too(self):
        bag = UiDisabledSettings()
        bag.set_ui_disabled_all(False)
        assert bag.is_ui_disabled("starts_disabled") is False

    def test_bulk_fires_one_transition_per_changed_field(self):
        bag = UiDisabledSettings()
        calls: list[tuple[str, bool]] = []
        bag.subscribe_ui_state(lambda name, disabled: calls.append((name, disabled)))
        bag.set_ui_disabled_all(True)
        # starts_disabled was already disabled (kwarg seed) — no event for it.
        assert sorted(calls) == [("flag", True), ("normal", True)]
        calls.clear()
        bag.set_ui_disabled_all(True)  # idempotent — fully silent second time
        assert calls == []


class TestUiStateChannel:
    def test_listener_fires_on_transition_only(self):
        bag = UiDisabledSettings()
        calls: list[tuple[str, bool]] = []
        bag.subscribe_ui_state(lambda name, disabled: calls.append((name, disabled)))
        bag.set_ui_disabled("normal", True)
        bag.set_ui_disabled("normal", True)  # idempotent — must NOT fire again
        bag.set_ui_disabled("normal", False)
        bag.set_ui_disabled("normal", False)  # idempotent — must NOT fire again
        assert calls == [("normal", True), ("normal", False)]

    def test_seeded_disable_then_redundant_set_does_not_fire(self):
        bag = UiDisabledSettings()
        calls: list[tuple[str, bool]] = []
        bag.subscribe_ui_state(lambda name, disabled: calls.append((name, disabled)))
        bag.set_ui_disabled("starts_disabled", True)  # already disabled via kwarg seed
        assert calls == []

    def test_unsubscribe_stops_delivery(self):
        bag = UiDisabledSettings()
        calls: list[tuple[str, bool]] = []

        def listener(name: str, disabled: bool) -> None:
            calls.append((name, disabled))

        bag.subscribe_ui_state(listener)
        bag.set_ui_disabled("normal", True)
        bag.unsubscribe_ui_state(listener)
        bag.set_ui_disabled("normal", False)
        assert calls == [("normal", True)]

    def test_cleanup_clears_listeners(self):
        bag = UiDisabledSettings()
        calls: list[tuple[str, bool]] = []
        bag.subscribe_ui_state(lambda name, disabled: calls.append((name, disabled)))
        bag.cleanup()
        bag.set_ui_disabled("normal", True)
        assert calls == []

    def test_raising_listener_does_not_break_others(self):
        bag = UiDisabledSettings()
        calls: list[tuple[str, bool]] = []

        def bad(_name: str, _disabled: bool) -> None:
            raise RuntimeError("boom")

        bag.subscribe_ui_state(bad)
        bag.subscribe_ui_state(lambda name, disabled: calls.append((name, disabled)))
        bag.set_ui_disabled("normal", True)
        assert calls == [("normal", True)]


class TestCellIsNeverTouched:
    """THE rev-2 invariant: UI-disabled state must not leak onto the value channel.

    Rev 1 signalled the panel via cell.set_value(cell.get_value()); that echo
    reached every cell subscriber (e.g. OakDCameraNode's live-control handlers,
    which push straight to camera hardware) and set is_dirty on cells that
    promoted ports share. These tests pin the fix.
    """

    def test_set_ui_disabled_fires_no_cell_event(self):
        bag = UiDisabledSettings()
        events: list[str] = []
        bag.subscribe(lambda name, value, old: events.append(name))
        bag.set_ui_disabled("normal", True)
        bag.set_ui_disabled("normal", False)
        assert events == []

    def test_set_ui_disabled_does_not_mark_cell_dirty(self):
        bag = UiDisabledSettings()
        descriptor = type(bag)._property_settings()["normal"]
        cell = bag._cell_for(descriptor)
        cell.is_dirty = False
        bag.set_ui_disabled("normal", True)
        assert cell.is_dirty is False
```

- [x] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/core/test_settings/test_ui_disabled.py -v`
Expected: FAIL — `TypeError: setting() got an unexpected keyword argument 'ui_disabled'` (or `AttributeError: ... has no attribute 'is_ui_disabled'`, whichever the collector hits first).

- [x] **Step 4: Add the `ui_disabled` kwarg to `setting.__init__`**

In `packages/haywire-core/src/haywire/core/settings/descriptor.py`:

Docstring addition — insert after the `metadata` parameter doc block (currently ending at line 148, before the closing `"""`):

```python
    ui_disabled : bool
        When ``True``, the field starts in a disabled state in the panel —
        rendered via Quasar ``:disable`` (or reduced opacity for container
        widgets) and blocked from user interaction — without affecting
        reads/writes at all (a normal ``setattr`` still works). This is only
        the SEED for ``Settings._ui_disabled_keys``; the live per-instance
        state is controlled via ``Settings.set_ui_disabled(name, bool)`` /
        ``is_ui_disabled(name)`` and announced on the dedicated UI-state
        channel (``subscribe_ui_state``) — never on the value/cell channel.
        See also the ``enabled_when`` metadata convention for declarative,
        same-bag reactive disabling (documented in setting-canon.md).
```

Signature change (currently lines 151-168) — add `ui_disabled` after `metadata`:

```python
    def __init__(
        self,
        default: "Any | Callable[[], Any]" = None,
        *,
        label: str = "",
        description: str = "",
        category: str = "root",
        order: int = 0,
        min: Any = None,
        max: Any = None,
        widget: "dict | None" = None,
        widget_config: "dict | None" = None,
        mirrors: "SettingDescriptor | str | None" = None,
        read_only: bool = False,
        type_: "type[T] | None" = None,
        validator: "Callable | None" = None,
        metadata: "dict | None" = None,
        ui_disabled: bool = False,
    ) -> None:
```

Storage — insert after the existing `self._metadata: dict = metadata or {}` line (currently line 191):

```python
        self._ui_disabled: bool = ui_disabled
```

- [x] **Step 5: Add the disabled-key set, the UI-state channel, and the public API to `Settings`**

In `packages/haywire-core/src/haywire/core/settings/settings.py`:

Add the new state to `__init__`, right after the existing `self._set_keys: set[str] = set()` line (currently line 89):

```python
        # UI-only disabled-state opinion (never persisted, never affects
        # reads/writes, NEVER touches a field's cell — the cell event keeps
        # meaning "the value changed"). Seeded from any field declared
        # setting(..., ui_disabled=True); grown/shrunk later via
        # set_ui_disabled(), which announces transitions on the dedicated
        # UI-state channel below. Declarative same-bag gating (enabled_when)
        # composes with this via OR in the panel — see render_utils.py.
        self._ui_disabled_keys: set[str] = set()
        for _name, _descriptor in type(self)._property_settings().items():
            if _descriptor._ui_disabled:
                self._ui_disabled_keys.add(_descriptor.storage_key)
        # Dedicated UI-state channel: callback(name, disabled) on each flag
        # transition. Separate from the cell/value channel by design (one
        # channel per concern — the NiceGUI BindableProperty model): a
        # chrome change must be structurally incapable of reaching value
        # subscribers (widgets, live-control node handlers, promoted ports).
        self._ui_state_listeners: list[Callable[[str, bool], None]] = []
```

Add the four public methods right after `is_locally_set` (currently lines 396-401, in the "Introspection" section):

```python
    def set_ui_disabled(self, name: str, disabled: bool) -> None:
        """Set or clear the UI-disabled flag for *name*.

        Purely a display/interaction concern for the properties panel — the
        field's value and writability are completely unaffected; node code
        keeps reading/writing it normally regardless of this flag. Fires the
        UI-state listeners (``subscribe_ui_state``) on an actual transition
        only; idempotent calls are silent. Never touches the field's cell.
        Unknown *name*: logs a warning and ignores (catches typos in
        hand-maintained field-name lists).
        """
        fields = type(self)._property_settings()
        if name not in fields:
            logger.warning(
                "set_ui_disabled: unknown field %r on %s — ignored", name, type(self).__name__
            )
            return
        key = fields[name].storage_key
        if (key in self._ui_disabled_keys) == disabled:
            return  # no transition — stay silent
        if disabled:
            self._ui_disabled_keys.add(key)
        else:
            self._ui_disabled_keys.discard(key)
        for listener in list(self._ui_state_listeners):
            try:
                listener(name, disabled)
            except Exception as e:
                logger.error(f"ui-state listener error for '{name}': {e}")

    def set_ui_disabled_all(self, disabled: bool) -> None:
        """Set or clear the UI-disabled flag for EVERY field on this bag.

        The bulk form of :meth:`set_ui_disabled`, for whole-bag gating (e.g.
        a node disabling an entire per-stream settings category at once).
        Iterates the bag's own declared fields, so callers need no
        hand-maintained field-name lists. Same contract per field:
        display-only, transition-only listener firing (fields already in the
        target state stay silent), never touches cells.
        """
        for name in type(self)._property_settings():
            self.set_ui_disabled(name, disabled)

    def is_ui_disabled(self, name: str) -> bool:
        """Return True if *name* is currently UI-disabled (manually or by seed).

        This is only HALF the disabled-state check the panel performs — the
        other half, ``enabled_when`` metadata (same-bag declarative gating),
        lives in ``haywire.ui.panel.render_utils`` since it needs the render
        pipeline's own subscription wiring. The panel combines both via OR.
        """
        fields = type(self)._property_settings()
        if name not in fields:
            return False
        return fields[name].storage_key in self._ui_disabled_keys

    def subscribe_ui_state(self, callback: Callable[[str, bool], None]) -> None:
        """Register ``callback(name, disabled)`` for UI-disabled flag transitions.

        The UI-state analogue of :meth:`subscribe` — but a separate channel:
        it fires ONLY for ``set_ui_disabled`` transitions, never for value
        changes, and value subscribers never hear UI-state changes.
        Idempotent per callback."""
        if callback not in self._ui_state_listeners:
            self._ui_state_listeners.append(callback)

    def unsubscribe_ui_state(self, callback: Callable[[str, bool], None]) -> None:
        """Remove a previously registered UI-state callback (no-op if absent)."""
        try:
            self._ui_state_listeners.remove(callback)
        except ValueError:
            pass
```

Extend `cleanup()` (currently lines 377-390) — add one line after the existing `for callback in list(self._subscriptions): self.unsubscribe(callback)` loop:

```python
        self._ui_state_listeners.clear()
```

- [x] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_settings/test_ui_disabled.py -v`
Expected: PASS, all 18 tests green.

- [x] **Step 7: Run the existing settings suite for regressions**

Run: `uv run pytest tests/core/test_settings/ -q`
Expected: PASS, no regressions (the only touched existing code paths are `Settings.__init__` and `cleanup()`).

- [x] **Step 8: Full baseline re-check**

Run: `uv run ruff check packages/haywire-core/src/haywire/core/settings/ && uv run ruff format --check packages/haywire-core/src/haywire/core/settings/ && uv run mypy packages/haywire-core/src/haywire/core/settings/`
Expected: all clean.

- [x] **Step 9: Commit**

```bash
git add packages/haywire-core/src/haywire/core/settings/descriptor.py packages/haywire-core/src/haywire/core/settings/settings.py tests/core/test_settings/test_ui_disabled.py
git commit -m "feat(settings): ui_disabled flag with dedicated UI-state channel (no cell echo)"
```

---

### Task 2: `BaseWidget.set_enabled` — Quasar `:disable` with §2.11 CSS fallback

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/widget/base.py:1-8` (imports), `:49-53` (after `set_value`, in the FLOOR section)
- Test: `tests/ui/widget/test_set_enabled.py` (new file)

**Interfaces:**
- Consumes: `self.ui_element` (existing — the NiceGUI root element captured by `render()`, reset to `None` by `cleanup()`).
- Produces (relied on by Task 3):
  - `haywire.ui.widget.base.DISABLED_STYLE: str` — the §2.11 style string, importable by the panel for the label fallback.
  - `BaseWidget.set_enabled(enabled: bool) -> None` — Quasar `:disable` when the root is a `DisableableElement`, CSS add/remove otherwise; safe no-op before `render()` and after `cleanup()`.

- [x] **Step 1: Baseline check**

Run: `uv run ruff check packages/haywire-core/src/haywire/ui/widget/base.py && uv run mypy packages/haywire-core/src/haywire/ui/widget/base.py`
Expected: both clean.

- [x] **Step 2: Write the failing tests**

Create `tests/ui/widget/test_set_enabled.py`:

```python
# tests/ui/widget/test_set_enabled.py
"""
BaseWidget.set_enabled(bool):

- root is a NiceGUI DisableableElement  -> Quasar :disable prop toggles
- root is a plain container element     -> design-guide §2.11 CSS is
  applied via style(add=) and — critically — REMOVED via style(remove=)
  (style("") does NOT clear on NiceGUI 3.x, which is why the pair exists)
- unrendered / cleaned-up widget        -> silent no-op

Real NiceGUI elements need a Client slot context, hence the integration
marker (same pattern as tests/ui/panel/test_promoted_row_state.py).
"""

# Per CLAUDE.md test trap: import editor before other haywire modules.
import haywire.core.graph.editor  # noqa: F401

from typing import Any

import pytest
from nicegui import Client, ui

from haywire.ui.widget.base import BaseWidget
from tests.ui.widget._sync_fixtures import make_float_port

pytestmark = pytest.mark.integration


def _noop_page() -> None:  # registration target for a headless Client
    pass


class _NumberRootWidget(BaseWidget):
    """Root is ui.number — a DisableableElement (Quasar :disable branch)."""

    def build(self) -> Any:
        return ui.number(value=0.0)


class _ContainerRootWidget(BaseWidget):
    """Root is a plain div — NOT disableable (CSS-fallback branch)."""

    def build(self) -> Any:
        with ui.element("div") as root:
            ui.number(value=0.0)
        return root


def _rendered(widget_cls) -> BaseWidget:
    w = widget_cls(make_float_port())
    client = Client(_noop_page, request=None)
    with client:
        w.render()
    return w


class TestQuasarBranch:
    def test_disable_sets_quasar_disable_prop(self):
        w = _rendered(_NumberRootWidget)
        w.set_enabled(False)
        assert w.ui_element._props.get("disable") is True

    def test_reenable_clears_quasar_disable_prop(self):
        w = _rendered(_NumberRootWidget)
        w.set_enabled(False)
        w.set_enabled(True)
        assert w.ui_element._props.get("disable") is False


class TestCssFallbackBranch:
    def test_disable_applies_211_style(self):
        w = _rendered(_ContainerRootWidget)
        w.set_enabled(False)
        style = w.ui_element._style
        assert style.get("opacity") == "0.5"
        assert style.get("pointer-events") == "none"

    def test_reenable_removes_211_style(self):
        w = _rendered(_ContainerRootWidget)
        w.set_enabled(False)
        w.set_enabled(True)
        style = w.ui_element._style
        assert "opacity" not in style
        assert "pointer-events" not in style


class TestLifecycleGuards:
    def test_set_enabled_before_render_is_a_noop(self):
        w = _NumberRootWidget(make_float_port())
        w.set_enabled(False)  # must not raise
        assert w.ui_element is None

    def test_set_enabled_after_cleanup_is_a_noop(self):
        w = _rendered(_NumberRootWidget)
        w.cleanup()
        w.set_enabled(False)  # must not raise
```

- [x] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/ui/widget/test_set_enabled.py -v`
Expected: FAIL on every test — `AttributeError: '_NumberRootWidget' object has no attribute 'set_enabled'`.

- [x] **Step 4: Implement `DISABLED_STYLE` + `set_enabled`**

In `packages/haywire-core/src/haywire/ui/widget/base.py`:

Add the import to the existing import block at the top (currently lines 1-8):

```python
from nicegui.elements.mixins.disableable_element import DisableableElement
```

Add the constant right after the imports, before `class BaseWidget`:

```python
# design-guide.md §2.11: the manual disabled treatment for elements that
# don't support Quasar :disable. Always applied/removed as a pair via
# style(add=)/style(remove=) — Element.style("") does NOT clear styles.
DISABLED_STYLE = "opacity: 0.5; pointer-events: none;"
```

Add the method to `BaseWidget`, right after `set_value` (currently lines 52-53, in the FLOOR section):

```python
    def set_enabled(self, enabled: bool) -> None:
        """Enable/disable this widget's rendered root element.

        Display/interaction only — the model stays fully writable; external
        cell changes keep syncing into the view. Prefers Quasar ``:disable``
        (design-guide §2.11) when the root is a NiceGUI DisableableElement;
        container roots fall back to the §2.11 opacity+pointer-events style,
        removed again on re-enable via ``style(remove=...)``. Safe no-op
        before ``render()`` and after ``cleanup()`` (``ui_element is None``),
        and for stand-in elements without ``.style()`` (headless tests).
        """
        el = self.ui_element
        if el is None:
            return
        if isinstance(el, DisableableElement):
            el.set_enabled(enabled)
        elif hasattr(el, "style"):
            if enabled:
                el.style(remove=DISABLED_STYLE)
            else:
                el.style(add=DISABLED_STYLE)
```

- [x] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/ui/widget/test_set_enabled.py -v`
Expected: PASS, all 6 tests green.

- [x] **Step 6: Run the existing widget suite for regressions**

Run: `uv run pytest tests/ui/widget/ -q`
Expected: PASS, no regressions (this task only adds a method and a constant).

- [x] **Step 7: Full baseline re-check**

Run: `uv run ruff check packages/haywire-core/src/haywire/ui/widget/ && uv run ruff format --check packages/haywire-core/src/haywire/ui/widget/ && uv run mypy packages/haywire-core/src/haywire/ui/widget/`
Expected: all clean.

- [x] **Step 8: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/widget/base.py tests/ui/widget/test_set_enabled.py
git commit -m "feat(widget): BaseWidget.set_enabled with Quasar :disable and §2.11 CSS fallback"
```

---

### Task 3: Panel rendering — imperative channel + declarative `enabled_when`

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/panel/render_utils.py:53-104` (`render_settings`), `:242-383` (`_render_reactive_field_row`), `:391-471` (`_resolve_widget_instance`, `_build_label_widget`), `:215-239` (`_render_field_row`, call-site compile fix only)
- Test: `tests/ui/panel/test_ui_disabled_row_state.py` (new file)

**Interfaces:**
- Consumes: `Settings.is_ui_disabled(name)`, `Settings.subscribe_ui_state`/`unsubscribe_ui_state` (Task 1); `BaseWidget.set_enabled`, `haywire.ui.widget.base.DISABLED_STYLE` (Task 2); `Settings.subscribe_field(name, callback)` / `unsubscribe(callback)` (existing, unchanged).
- Produces: every `_render_reactive_field_row`-rendered row carries `data-ui-disabled="true"`/`"false"` in its props, and the widget is disabled/enabled live via `set_enabled`. `_resolve_widget_instance` changes its return contract from `Callable[[Any], None] | None` to `tuple[Callable[[Any], None] | None, Callable[[bool], None]]` — a breaking change to its one other call site (`_render_field_row`, registry path), updated in Step 7. No new public function signatures.

- [x] **Step 1: Baseline check**

Run: `uv run ruff check packages/haywire-core/src/haywire/ui/panel/render_utils.py && uv run mypy packages/haywire-core/src/haywire/ui/panel/render_utils.py`
Expected: both clean.

- [x] **Step 2: Write the failing tests**

Create `tests/ui/panel/test_ui_disabled_row_state.py`:

```python
# tests/ui/panel/test_ui_disabled_row_state.py
"""
Reactive panel disabling: a row rendered by _render_reactive_field_row must
reflect Settings.is_ui_disabled() (imperative — delivered over the dedicated
UI-state channel, NOT a cell event) and the enabled_when metadata convention
(declarative, same-bag, delivered over the controller field's cell channel),
both live — no full panel redraw required — and both compose via OR.

The disabled check is mechanism-agnostic: depending on which widget class the
field resolves to, disabling lands either as Quasar :disable on a
DisableableElement root or as the §2.11 CSS on a container root / label
fallback. _widget_is_disabled() accepts either signal.
"""

import logging

import pytest

# Per CLAUDE.md test trap: import editor before other haywire modules.
import haywire.core.graph.editor  # noqa: F401

from nicegui import Client, ui

from haywire.core.settings import Settings, setting
from haywire.ui.panel.render_utils import render_settings
from haywire.barn.builtin.types import BOOL, FLOAT

pytestmark = pytest.mark.integration


def _noop_page() -> None:  # registration target for a headless Client
    pass


def _walk(element):
    """Depth-first walk over a NiceGUI element tree."""
    yield element
    for child in element.default_slot.children:
        yield from _walk(child)


def _find_field_row(root, attr_name: str):
    """Find the ``ui.row`` element carrying ``data-field="<attr_name>"``."""
    for el in _walk(root):
        props = getattr(el, "_props", {})
        if props.get("data-field") == attr_name:
            return el
    return None


def _widget_is_disabled(row) -> bool:
    """True if any element under *row* is disabled by EITHER mechanism:
    Quasar ``disable`` prop (DisableableElement root) or the §2.11 CSS
    (container root / label fallback)."""
    for el in _walk(row):
        if getattr(el, "_props", {}).get("disable") is True:
            return True
        style = getattr(el, "_style", {}) or {}
        if style.get("opacity") == "0.5" and style.get("pointer-events") == "none":
            return True
    return False


class ImperativeSettings(Settings):
    plain = setting[FLOAT](1.0, label="Plain")
    starts_disabled = setting[FLOAT](2.0, label="Starts Disabled", ui_disabled=True)


class EnabledWhenSettings(Settings):
    enable_color = setting[BOOL](True, label="Enable Color")
    exposure = setting[FLOAT](
        20000.0,
        label="Exposure",
        metadata={"enabled_when": ("enable_color", True)},
    )
    typo_gated = setting[FLOAT](
        1.0,
        label="Typo Gated",
        metadata={"enabled_when": ("does_not_exist", True)},
    )


def _render(bag) -> "ui.column":
    client = Client(_noop_page, request=None)
    with client:
        anchor = ui.column()
        with anchor:
            render_settings(bag)
    return anchor


class TestImperativeUiDisabled:
    def test_plain_field_row_not_disabled(self):
        bag = ImperativeSettings()
        anchor = _render(bag)
        row = _find_field_row(anchor, "plain")
        assert row is not None
        assert row._props.get("data-ui-disabled") != "true"
        assert not _widget_is_disabled(row)

    def test_ui_disabled_default_field_row_is_disabled(self):
        bag = ImperativeSettings()
        anchor = _render(bag)
        row = _find_field_row(anchor, "starts_disabled")
        assert row is not None
        assert row._props.get("data-ui-disabled") == "true"
        assert _widget_is_disabled(row)

    def test_set_ui_disabled_live_toggle_no_redraw(self):
        bag = ImperativeSettings()
        anchor = _render(bag)
        row = _find_field_row(anchor, "plain")

        bag.set_ui_disabled("plain", True)
        assert row._props.get("data-ui-disabled") == "true"
        assert _widget_is_disabled(row)

        bag.set_ui_disabled("plain", False)
        assert row._props.get("data-ui-disabled") != "true"
        assert not _widget_is_disabled(row)

    def test_live_toggle_fires_no_cell_event(self):
        """The rev-2 invariant, asserted at panel level: toggling disabled
        state while a panel is live must not echo through the value channel."""
        bag = ImperativeSettings()
        _render(bag)
        events: list[str] = []
        bag.subscribe(lambda name, value, old: events.append(name))
        bag.set_ui_disabled("plain", True)
        bag.set_ui_disabled("plain", False)
        assert events == []


class TestEnabledWhenDeclarative:
    def test_dependent_row_disabled_when_controller_condition_is_false(self):
        bag = EnabledWhenSettings()
        bag.enable_color = False
        anchor = _render(bag)
        row = _find_field_row(anchor, "exposure")
        assert row is not None
        assert row._props.get("data-ui-disabled") == "true"
        assert _widget_is_disabled(row)

    def test_dependent_row_enabled_when_controller_condition_is_true(self):
        bag = EnabledWhenSettings()
        assert bag.enable_color is True  # default
        anchor = _render(bag)
        row = _find_field_row(anchor, "exposure")
        assert row is not None
        assert row._props.get("data-ui-disabled") != "true"
        assert not _widget_is_disabled(row)

    def test_toggling_controller_live_updates_dependent_row_no_redraw(self):
        bag = EnabledWhenSettings()
        anchor = _render(bag)
        row = _find_field_row(anchor, "exposure")

        bag.enable_color = False
        assert row._props.get("data-ui-disabled") == "true"
        assert _widget_is_disabled(row)

        bag.enable_color = True
        assert row._props.get("data-ui-disabled") != "true"
        assert not _widget_is_disabled(row)

    def test_unresolvable_controller_name_fails_soft(self, caplog):
        bag = EnabledWhenSettings()
        with caplog.at_level(logging.WARNING):
            anchor = _render(bag)
        row = _find_field_row(anchor, "typo_gated")
        assert row is not None
        assert row._props.get("data-ui-disabled") != "true"
        assert not _widget_is_disabled(row)
        assert any("does_not_exist" in rec.message for rec in caplog.records)


class TestComposition:
    def test_manual_and_enabled_when_compose_via_or(self):
        bag = EnabledWhenSettings()
        assert bag.enable_color is True  # enabled_when says enabled
        bag.set_ui_disabled("exposure", True)  # manual override says disabled
        anchor = _render(bag)
        row = _find_field_row(anchor, "exposure")
        assert row._props.get("data-ui-disabled") == "true", "manual flag must win via OR"
```

- [x] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/ui/panel/test_ui_disabled_row_state.py -v`
Expected: FAIL on every test — `data-ui-disabled` is never set today, and nothing is ever disabled.

- [x] **Step 4: Add the module logger and the `enabled_when` resolution to `_render_reactive_field_row`**

In `packages/haywire-core/src/haywire/ui/panel/render_utils.py`:

This file has no module logger today (confirmed). Add `import logging` to the stdlib import group at the top (alongside `from itertools import groupby`, currently line 29), the `DISABLED_STYLE` import to the haywire import group (alongside `from haywire.ui.utils import anchor_cleanup_to_element`, currently line 35), and the logger after the imports (before `_ROW_CLASSES`, currently line 42):

```python
import logging
```

```python
from haywire.ui.widget.base import DISABLED_STYLE
```

```python
logger = logging.getLogger(__name__)
```

(`DISABLED_STYLE` is used only by `_build_label_widget` in Step 6 — the real-widget path delegates the style choice entirely to `BaseWidget.set_enabled`.)

Inside `_render_reactive_field_row`, after the existing promoted-inlet block (currently ending at line 280, right before the `_has_local_opinion` closure at line 289), add:

```python
    # Declarative same-bag gating (enabled_when metadata convention, composes
    # with the imperative Settings.is_ui_disabled/set_ui_disabled via OR — see
    # setting-canon.md). Resolved once per row build; the live part is the
    # subscribe_field wired below (a controller-VALUE change is a genuine cell
    # event), plus the bag's UI-state channel subscribed in render_settings
    # for the imperative flag.
    enabled_when = defn._metadata.get("enabled_when") if defn._metadata else None
    enabled_when_controller: str | None = None
    enabled_when_value: Any = None
    if enabled_when is not None:
        controller_name, expected_value = enabled_when
        if controller_name in type(obj)._property_settings():
            enabled_when_controller = controller_name
            enabled_when_value = expected_value
        else:
            logger.warning(
                "enabled_when=%r on field %r references unknown field %r on %s "
                "— ignoring (field will never be auto-disabled by this rule)",
                enabled_when,
                attr_name,
                controller_name,
                type(obj).__name__,
            )

    def _is_ui_disabled() -> bool:
        if obj.is_ui_disabled(attr_name):
            return True
        if enabled_when_controller is not None:
            return getattr(obj, enabled_when_controller) != enabled_when_value
        return False
```

- [x] **Step 5: Apply the disabled state at render, wire the live subscriptions**

Still inside `_render_reactive_field_row`, find the row-building block (currently lines 350-360):

```python
    row_props = f'data-field="{attr_name}"'
    if is_promoted:
        row_props += ' data-promoted="true"'
        if port is not None:
            row_props += f' data-promoted-direction="{"inlet" if is_promoted_inlet else "outlet"}"'

    with ui.row().classes(row_classes).props(row_props):
        _render_label()
        if is_promoted_inlet is False:
            on_edit = _bag_on_edit(obj, attr_name, error_container)
            value_apply = _resolve_widget_instance(defn, on_edit, bag=obj)
```

Replace it with:

```python
    row_props = f'data-field="{attr_name}"'
    if is_promoted:
        row_props += ' data-promoted="true"'
        if port is not None:
            row_props += f' data-promoted-direction="{"inlet" if is_promoted_inlet else "outlet"}"'
    if _is_ui_disabled():
        row_props += ' data-ui-disabled="true"'

    widget_set_enabled: Callable[[bool], None] | None = None
    with ui.row().classes(row_classes).props(row_props) as row_element:
        _render_label()
        if is_promoted_inlet is False:
            on_edit = _bag_on_edit(obj, attr_name, error_container)
            value_apply, widget_set_enabled = _resolve_widget_instance(defn, on_edit, bag=obj)
```

(A promoted-inlet row renders no widget: `widget_set_enabled` stays `None` and only the row marker below applies — no new branch needed.)

Then add the marker refresher and the `enabled_when` live subscription, right after the row's `with` block closes (before the existing `def _refresh_chrome():` at line 362):

```python
    def _refresh_row_disabled_marker() -> None:
        disabled = _is_ui_disabled()
        row_element.props(f'data-ui-disabled="{"true" if disabled else "false"}"')
        if widget_set_enabled is not None:
            widget_set_enabled(not disabled)

    if enabled_when_controller is not None:

        def _on_controller_changed(_value: Any, _old: Any) -> None:
            _refresh_row_disabled_marker()

        obj.subscribe_field(enabled_when_controller, _on_controller_changed)
        anchor_cleanup_to_element(row_element, lambda: obj.unsubscribe(_on_controller_changed))
```

(No explicit initial `_refresh_row_disabled_marker()` call here: `render_settings` already runs every row's updater once at render — Step 6 folds the marker into that updater — and the row props / seed state were applied at build above.)

- [x] **Step 6: Fold the marker into `_refresh_chrome`, subscribe the UI-state channel in `render_settings`**

Modify the existing `_refresh_chrome` (currently lines 362-383) — one added line before the closing of the function:

```python
    def _refresh_chrome():
        # Real widgets bind the shared cell directly (on_changed), so
        # re-pushing their value here would be a structural no-op — verified:
        # value_apply is None for every case except the unknown-widget label
        # fallback, which owns no cell subscription of its own and needs this
        # to reflect external changes at all. Everything else in this callback
        # is pure override chrome: the • prefix, reset-button visibility, and
        # the ui-disabled marker.
        #
        # Applies to plain fields too (decision Q1): editing a plain field's widget
        # writes its cell, and the • / reset must appear live rather than waiting
        # for the next full panel redraw. is_promoted_inlet is a per-render constant
        # (structural, needs a redraw to change), so a cell-value change only flips
        # the is_locally_set half — recomputed here.
        if value_apply is not None:
            value_apply(getattr(obj, attr_name))
        dirty = _has_local_opinion()
        if label is not None:
            label.set_text(_label_text(dirty))
        if reset_btn is not None:
            reset_btn.set_visibility(dirty)
        _refresh_row_disabled_marker()

    updaters[attr_name] = _refresh_chrome
```

Then in `render_settings` (currently lines 53-104), replace the subscription/teardown block (currently lines 94-104):

```python
    obj.subscribe(_on_model_change)

    # Explicit initial sync — exercise every row's apply() path once at render,
    # so "the widget shows the model" is a property of the apply path. Mirrors
    # BaseWidget.render() calling on_model_changed() once after wiring dispatch.
    for _updater in updaters.values():
        _updater()

    # Tear down the subscription when the column leaves the DOM (redraw via
    # content.clear() or page close).
    anchor_cleanup_to_element(column, lambda: obj.unsubscribe(_on_model_change))
```

with:

```python
    def _on_ui_state_change(name: str, _disabled: bool) -> None:
        # Same dispatch shape as _on_model_change, arriving on the DEDICATED
        # ui-state channel — set_ui_disabled never echoes through the cells,
        # so value subscribers (widgets, node live-control handlers, promoted
        # ports) never hear chrome changes.
        updater = updaters.get(name)
        if updater is not None:
            updater()

    obj.subscribe(_on_model_change)
    obj.subscribe_ui_state(_on_ui_state_change)

    # Explicit initial sync — exercise every row's apply() path once at render,
    # so "the widget shows the model" is a property of the apply path. Mirrors
    # BaseWidget.render() calling on_model_changed() once after wiring dispatch.
    for _updater in updaters.values():
        _updater()

    # Tear down both subscriptions when the column leaves the DOM (redraw via
    # content.clear() or page close).
    def _teardown() -> None:
        obj.unsubscribe(_on_model_change)
        obj.unsubscribe_ui_state(_on_ui_state_change)

    anchor_cleanup_to_element(column, _teardown)
```

- [x] **Step 7: Change `_resolve_widget_instance` / `_build_label_widget` to also return a `set_enabled` callable, and update the registry call site**

Modify `_resolve_widget_instance` (currently lines 391-450) — new return type, docstring, and both return statements:

```python
def _resolve_widget_instance(
    defn: "setting",
    on_edit: Callable[[Any], None],
    bag: "Settings | None" = None,
    cell: "DataField | None" = None,
) -> tuple[Callable[[Any], None] | None, Callable[[bool], None]]:
    """Build the shared ``BaseWidget`` for *defn* via a ``SettingWidgetModel``.

    Falls back to a read-only label when the resolved widget key is unknown, so
    a missing widget never renders a silent blank. The model always binds the
    field's shared ``DataField`` cell: *cell* when given (the
    registry-owned cell, registry path), else *bag*'s instance cell. Writes
    route through *on_edit* — the write-policy closure (``_bag_on_edit`` /
    ``_registry_on_edit``) — never raw into the cell.

    Returns ``(apply_callback, set_enabled)``. ``apply_callback`` is ``None``
    for a real widget (it hears cell writes directly via ``on_changed``, so
    there is nothing left for a caller to push) or the label fallback's
    ``apply(value)`` when the widget key is unknown (that display has no cell
    binding of its own). ``set_enabled(bool)`` toggles the widget's
    disabled state — ``BaseWidget.set_enabled`` (Quasar ``:disable`` / §2.11
    CSS fallback) for a real widget, a style toggle on the label fallback —
    and is never ``None``.
    """
    from haywire.ui.widget.globals import get_widget_class
    from haywire.ui.panel.setting_widget_model import SettingWidgetModel

    key = defn.widget_key
    widget_cls = get_widget_class(key)
    if widget_cls is None:
        shared_cell = cell if cell is not None else (bag._cell_for(defn) if bag is not None else None)
        value = shared_cell.get_value() if shared_cell is not None else None
        return _build_label_widget(value)
```

The real-widget branch (currently lines 421-450) is unchanged except the final `return None`, which becomes:

```python
    return None, widget.set_enabled
```

(`widget.set_enabled` is a bound method on the `BaseWidget` from Task 2; after the row's teardown runs `widget.cleanup()`, `ui_element` is `None` and the method is a safe no-op — no stale-element access.)

Modify `_build_label_widget` (currently lines 453-471) to return the pair:

```python
def _build_label_widget(value: Any) -> tuple[Callable[[Any], None], Callable[[bool], None]]:
    """Display-only ``label`` widget — no ``.value`` (set_text, not BindableProperty).

    ``apply(value)`` exists solely for this label fallback (no cell binding);
    real widgets hear the cell directly. ``set_enabled(bool)`` applies/removes
    the §2.11 disabled style directly on the label (a ui.label is not a
    DisableableElement, so there is no Quasar :disable to prefer here).
    """
    str_value = _escape(value)
    lbl = (
        ui.label(str_value)
        .classes(f"text-xs text-right truncate hw-text-muted {_WIDGET_CLASSES}")
        .props(f'data-value="{str_value}"')
    )

    def _apply_label(v, _lbl=lbl):
        s = _escape(v)
        _lbl.set_text(s)
        _lbl.props(f'data-value="{s}"')

    def _set_label_enabled(enabled: bool, _lbl=lbl) -> None:
        if enabled:
            _lbl.style(remove=DISABLED_STYLE)
        else:
            _lbl.style(add=DISABLED_STYLE)

    return _apply_label, _set_label_enabled
```

Finally, the registry-path call site: `_render_field_row` (currently lines 215-239) returns `_resolve_widget_instance(...)` directly on its last line. The registry path is out of scope for this feature (Global Constraints), and its own return value is discarded by `_render_definitions._render_one` — so just unpack and preserve `_render_field_row`'s existing contract. Replace the last line:

```python
        return _resolve_widget_instance(defn, on_edit, cell=cell)
```

with:

```python
        callback, _set_enabled = _resolve_widget_instance(defn, on_edit, cell=cell)
        return callback
```

- [x] **Step 8: Run tests to verify they pass**

Run: `uv run pytest tests/ui/panel/test_ui_disabled_row_state.py -v`
Expected: PASS, all 9 tests green.

- [x] **Step 9: Run the full existing panel test suite for regressions**

The `_resolve_widget_instance` return-type change is the riskiest part of this task — run every test that touches `render_utils.py`:

Run: `uv run pytest tests/ui/panel/ tests/haystack/test_graph_run_settings_panel.py -v`
Expected: PASS, no regressions (in particular `test_promoted_row_state.py`, `test_render_settings_subscription.py`, and `test_render_settings_echo.py`, which exercise `_render_reactive_field_row` and `_resolve_widget_instance` heavily).

- [x] **Step 10: Full baseline re-check**

Run: `uv run ruff check packages/haywire-core/src/haywire/ui/panel/ && uv run ruff format --check packages/haywire-core/src/haywire/ui/panel/ && uv run mypy packages/haywire-core/src/haywire/ui/panel/`
Expected: all clean.

- [x] **Step 11: Run the full fast test suite**

Run: `uv run pytest -m "not integration" -q` and `uv run pytest -m integration tests/ui/ -q`
Expected: all passing (matching the pre-existing pass count, plus this plan's new tests). Note: the new panel and widget test files use `pytestmark = pytest.mark.integration` (they need a NiceGUI `Client`), matching `test_promoted_row_state.py` — make sure they're picked up by the integration run, not silently skipped by `-m "not integration"`.

- [x] **Step 12: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/panel/render_utils.py tests/ui/panel/test_ui_disabled_row_state.py
git commit -m "feat(panel): reactive ui_disabled rendering + enabled_when declarative gating"
```

---

### Task 4: Documentation — `setting-canon.md`

**Files:**
- Modify: `docs/components/settings/setting-canon.md`

**Interfaces:**
- Consumes: the finished `ui_disabled=`/`set_ui_disabled`/`is_ui_disabled`/`subscribe_ui_state`/`enabled_when` API from Tasks 1-3 (must be written and tested first, so the docs describe real, verified behavior).
- Produces: nothing consumed by later tasks — purely documentation.

- [x] **Step 1: Fix the pre-existing `render_reactive` → `render_settings` doc-drift**

In `docs/components/settings/setting-canon.md`, find the line (currently line 178):

```markdown
**Panel rendering rules.** When the properties panel calls `render_reactive(node.filter)`:
```

Replace with:

```markdown
**Panel rendering rules.** When the properties panel calls `render_settings(node.filter)`:
```

- [x] **Step 2: Extend the DOM structure block with the disabled marker**

Find the DOM contract block (currently lines 185-192) and change only its first line:

```text
div[data-field="<attr_name>"]        ← row container (data-ui-disabled="true" when disabled)
```

(the remaining lines of the block stay exactly as they are).

- [x] **Step 3: Add the `ui_disabled` / `enabled_when` section**

Find the existing "Promoting a setting to a port" section (currently lines 225-236, ending right before `## 3a. Using LibrarySettings...`). Insert a new subsection immediately after it (before the `## 3a.` heading):

```markdown
**Disabling a setting in the panel (`ui_disabled` / `enabled_when`).** A setting can render as disabled — Quasar `:disable` where the widget root supports it, the §2.11 opacity treatment otherwise — while staying a completely normal, fully-writable field from the code's perspective. This is purely a panel-display concern: node code and any direct `setattr` keep working regardless of disabled state; there is no write guard in the settings layer.

Two composable mechanisms, combined via OR (either one disabling the field is enough):

```python
from haywire.core.settings import NodeSettings, setting
from haywire.barn.builtin.types import BOOL, FLOAT

class color(NodeSettings):
    enable_color = setting[BOOL](True, label="Enable Color")

    # Declarative: disabled whenever enable_color != True. Same-bag only,
    # exact-match only (no predicates). Live — toggling enable_color in the
    # panel immediately disables exposure, no redraw needed.
    exposure = setting[FLOAT](
        20000.0,
        label="Exposure",
        metadata={"enabled_when": ("enable_color", True)},
    )

    # Imperative: starts disabled until something says otherwise.
    manual_gain = setting[FLOAT](1.0, label="Manual Gain", ui_disabled=True)
```

```python
# Runtime API on any Settings instance — for gating driven by something
# OTHER than a sibling setting (e.g. a different node's wiring state):
bag.set_ui_disabled("manual_gain", False)   # re-enable
bag.is_ui_disabled("manual_gain")           # -> False
bag.set_ui_disabled_all(True)               # bulk: every field on the bag
```

**One channel per concern.** `set_ui_disabled` announces transitions on a dedicated UI-state channel (`bag.subscribe_ui_state(cb)` with `cb(name, disabled)`, removed via `unsubscribe_ui_state` / `cleanup()`), which the panel subscribes to. It never fires the field's cell event — the cell event keeps meaning exactly "the value changed", so value subscribers (widgets, node live-control handlers, promoted ports) are structurally incapable of hearing chrome changes. This mirrors NiceGUI's own design, where `enabled` and `value` are independent bindable properties. `set_ui_disabled` is transition-only: redundant calls fire nothing, so recomputing disabled state in a hot path is free in steady state.

`enabled_when` is a `(field_name, expected_value)` tuple stored in `metadata` — a string field reference, not validated at class-definition time. If the referenced field doesn't exist on the same bag, the panel logs a warning and the field renders normally (never auto-disabled) rather than raising. `enabled_when` only ever expresses a same-bag relationship; cross-bag or cross-node gating (e.g. one node's callback-edge wiring determining another's field state) uses `set_ui_disabled` from whatever code owns that external state.

Neither mechanism is persisted — disabled state is always transient, recomputed at construction (`ui_disabled=`) or by whatever runtime code calls `set_ui_disabled`.
```

- [x] **Step 4: Preview the docs site to sanity-check rendering**

Run: `uv run mkdocs serve` and visit `http://127.0.0.1:8000` → navigate to the settings canon page. Confirm the new section renders with correct code-block formatting and no broken markdown. Stop the server after checking (Ctrl+C).

- [x] **Step 5: Commit**

```bash
git add docs/components/settings/setting-canon.md
git commit -m "docs(settings): document ui_disabled/enabled_when + UI-state channel; fix render_reactive doc drift"
```

---

### Task 5: OAK-D node — wire stream-status indication

**Files:**
- Modify: `barn/haybale-visiongraph/haybale_visiongraph/nodes/oak_d_camera_node.py`
- Modify: `barn/haybale-visiongraph/notes.md`

> **Repo note:** `barn/haybale-visiongraph` inside haywire-repo is a **gitignored local symlink** into the separate haybale-visiongraph repository (`/Volumes/Ddrive/06_open_tracking_tool/haywire/haybale-visiongraph`). Every command in this task — including the `git add`/`git commit` in Step 7 — must run from that repository's root, NOT from haywire-repo; a `git add` from haywire-repo would silently hit the ignore rule.

**Interfaces:**
- Consumes: `Settings.set_ui_disabled_all(bool)` from Task 1 (via `self.depth`/`self.ir`/`self.color`, the existing `NodeSettings` bags on `OakDCameraNode`). Because the ui-disabled API never touches cells, this task fires NOTHING into `hb_on_ir_changed`/`hb_on_color_changed` (the bag subscriptions that push straight to camera hardware) — and because it is transition-only, steady-state re-gathers are completely silent. The bulk form iterates each bag's own declared fields, so this task maintains no field-name lists at all.
- Produces: nothing consumed by later tasks — this is the terminal consumer.

- [x] **Step 1: Baseline check**

Run:
```bash
cd /Volumes/Ddrive/06_open_tracking_tool/haywire/haybale-visiongraph
uv run ruff check barn/haybale-visiongraph/haybale_visiongraph/nodes/oak_d_camera_node.py
uv run mypy barn/haybale-visiongraph/haybale_visiongraph/nodes/oak_d_camera_node.py
```
Expected: clean (matches the state left at the end of the prior OAK-D work in this same file).

- [x] **Step 2: Add stream-based disabling to `hb_gather_requirements`**

Find `hb_gather_requirements` (currently lines 479-489):

```python
    def hb_gather_requirements(self):
        """Union the per-stream requirements across all pooled subscribers."""
        subs = self.value("callbacks") or {}
        want_rgb = want_depth = want_ir = False
        for sub in subs.values():
            want_rgb = want_rgb or bool(getattr(sub, "rgb", False))
            want_depth = want_depth or bool(getattr(sub, "depth", False))
            want_ir = want_ir or bool(getattr(sub, "ir", False))
        self.hb_want_rgb = want_rgb
        self.hb_want_depth = want_depth
        self.hb_want_ir = want_ir
```

Replace with:

```python
    def hb_gather_requirements(self):
        """Union the per-stream requirements across all pooled subscribers."""
        subs = self.value("callbacks") or {}
        want_rgb = want_depth = want_ir = False
        for sub in subs.values():
            want_rgb = want_rgb or bool(getattr(sub, "rgb", False))
            want_depth = want_depth or bool(getattr(sub, "depth", False))
            want_ir = want_ir or bool(getattr(sub, "ir", False))
        self.hb_want_rgb = want_rgb
        self.hb_want_depth = want_depth
        self.hb_want_ir = want_ir
        self.hb_refresh_stream_status_indication()

    def hb_refresh_stream_status_indication(self):
        """Disable each stream's settings in the panel when nobody currently
        wants that stream (per the union gathered in hb_gather_requirements).

        Purely visual, and genuinely side-effect-free: the ui-disabled API
        rides the dedicated UI-state channel and never fires cell events, so
        the bag subscriptions that push live settings to the device
        (hb_on_ir_changed/hb_on_color_changed) never hear these calls, and
        transition-only firing makes steady-state re-gathers silent. The
        bulk form iterates each bag's own declared fields — no field-name
        list to maintain here. This is the cross-bag/external case
        set_ui_disabled exists for: the gating condition lives on THIS node
        (hb_want_rgb/depth/ir, derived from a different node's callback
        edge), not on a sibling setting within the same bag — so it cannot
        be expressed via the enabled_when metadata convention (same-bag
        only).
        """
        self.depth.set_ui_disabled_all(not self.hb_want_depth)
        self.ir.set_ui_disabled_all(not self.hb_want_ir)
        self.color.set_ui_disabled_all(not self.hb_want_rgb)
```

- [x] **Step 3: Verify manually via the running app**

Start the app and confirm the feature works end-to-end (this node only ships frames on real OAK-D hardware, but the panel behavior is verifiable without a device — the simplest case is a graph with NO event node attached, which yields `want_rgb=want_depth=want_ir=False`):

Run (from haywire-repo): `uv run haywire`

In the app: create an `OAK-D Camera` node with no `Frame Event` node attached, open its properties panel, and pulse `start` (or trigger `on_startup`) so `hb_gather_requirements` runs. Expected: all `depth`, `ir`, and `color` category fields render disabled since nothing subscribes to any stream. Attach a `NumpyFrameEventNode` with `rgb=True`, rewire the callback edge, and pulse `start` again — the `color` category's fields become enabled while `depth`/`ir` stay disabled (only `rgb` was requested). Known limitation (accepted): the disabled state refreshes only when `hb_gather_requirements` runs (startup / start pulse), so rewiring alone doesn't update the panel until the next start.

- [x] **Step 4: Full baseline re-check**

Run:
```bash
cd /Volumes/Ddrive/06_open_tracking_tool/haywire/haybale-visiongraph
uv run ruff check barn/haybale-visiongraph/haybale_visiongraph/nodes/oak_d_camera_node.py
uv run ruff format --check barn/haybale-visiongraph/haybale_visiongraph/nodes/oak_d_camera_node.py
uv run mypy barn/haybale-visiongraph/haybale_visiongraph/nodes/oak_d_camera_node.py
```
Expected: all clean.

- [x] **Step 5: Run the main repo's fast test suite once more (this node is exercised by the library-load integration test)**

Run: `cd /Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo && uv run pytest -m "not integration" -q`
Expected: all passing, same count as at the end of Task 3 (this change only affects `OakDCameraNode`'s runtime behavior, not its port/settings declarations).

- [x] **Step 6: Record the decision in `notes.md` and commit — in the haybale-visiongraph repo**

Append to `barn/haybale-visiongraph/notes.md` (path relative to the haybale-visiongraph repo root), after the existing "Depth-quality / IR / color live-control knobs (fourth inquisition — BUILT)" section:

```markdown
## Stream-status indication via reactive panel disabling (fifth inquisition — BUILT)

Problem: `depth`/`ir`/`color` settings are gated by a DIFFERENT node's wiring
(the event node's callback-edge requirement union, gathered in
`hb_gather_requirements`), but the panel gave no visual indication of which
streams were actually active versus dormant.

Solved by a new framework primitive (`Settings.set_ui_disabled`/
`set_ui_disabled_all`/`is_ui_disabled` riding a dedicated UI-state channel,
plus a same-bag declarative `enabled_when` metadata convention) rather than
anything OAK-D-specific — see `docs/components/settings/setting-canon.md`
for the general API. `hb_gather_requirements` now calls
`hb_refresh_stream_status_indication()`, which bulk-disables each stream's
whole settings bag (`depth`/`ir`/`color`) via `set_ui_disabled_all` when
its corresponding `hb_want_*` flag is False — the bulk form iterates each
bag's own declared fields, so this node maintains no field-name lists.

This is the CROSS-BAG case the imperative `set_ui_disabled` primitive exists
for — `enabled_when` (same-bag only) could not express it, since the gating
condition (`hb_want_rgb` etc.) lives on the node itself, derived from a
different node's edge, not from a sibling setting on `color`/`ir`/`depth`.

Genuinely side-effect-free by construction: `set_ui_disabled` never fires
cell events (the UI-state channel is separate from the value channel, per
the framework's one-channel-per-concern rule), so this node's own
live-control subscriptions (`hb_on_ir_changed`/`hb_on_color_changed`, which
push straight to camera hardware) never hear these calls, and
`hb_apply_live_settings` / the depth-quality assignments in
`hb_handle_start` are unaffected. `self.depth`/`self.ir`/`self.color`
remain fully writable regardless of disabled state.
```

While in `notes.md`, also fix the stale non-goals list: it still names frame-alignment control as unbuilt, but `depth.frame_alignment` shipped in the fourth round — annotate that entry (e.g. "~~frame-alignment control~~ — shipped in the fourth round as `depth.frame_alignment`") rather than silently deleting it.

Then commit from the haybale-visiongraph repo root:

```bash
cd /Volumes/Ddrive/06_open_tracking_tool/haywire/haybale-visiongraph
git add barn/haybale-visiongraph/haybale_visiongraph/nodes/oak_d_camera_node.py barn/haybale-visiongraph/notes.md
git commit -m "feat(oak-d): disable depth/ir/color settings when their stream isn't requested"
```

---

## Self-Review

**Spec coverage** (against the settled design plus the rev-2 review findings):
- ✅ `ui_disabled` kwarg on `setting()`, seeding `_ui_disabled_keys` at construction — Task 1.
- ✅ `set_ui_disabled(name, bool)` / `is_ui_disabled(name)` on `Settings` — Task 1.
- ✅ **Dedicated UI-state channel, value channel untouched** (rev-2 finding 1) — Task 1 (`subscribe_ui_state`/`unsubscribe_ui_state`, cleanup clearing), pinned by `TestCellIsNeverTouched` (core) and `test_live_toggle_fires_no_cell_event` (panel).
- ✅ **Transition-only firing** — Task 1, `test_listener_fires_on_transition_only` / `test_seeded_disable_then_redundant_set_does_not_fire`.
- ✅ **Bulk `set_ui_disabled_all`** (whole-bag gating) — Task 1, tested by `TestSetUiDisabledAll` including per-field transition semantics; sole consumer is Task 5, which therefore maintains no field-name lists.
- ✅ **Native Quasar `:disable` with §2.11 CSS fallback** (design-guide preference) — Task 2 (`BaseWidget.set_enabled`), consumed by Task 3.
- ✅ **`style(add=)`/`style(remove=)` pairs everywhere** (rev-2 finding 3: `style("")` doesn't clear) — Task 2 implementation + `test_reenable_removes_211_style`; Task 3's label fallback.
- ✅ Visual-only enforcement, no settings-layer write guard — Task 1 tests assert writes still work; Tasks 2-3 only touch rendering.
- ✅ Transient, never serialized — no `to_dict`/`from_dict` changes anywhere in the plan.
- ✅ `enabled_when` metadata convention, exact-match tuple, same-bag only, fail-soft warning — Task 3, tested by `test_unresolvable_controller_name_fails_soft`.
- ✅ Live reactivity: imperative via the UI-state channel (bag-level, dispatched through `updaters`), declarative via `subscribe_field` with per-row cleanup via `anchor_cleanup_to_element` — Task 3, tested by both live-toggle tests.
- ✅ OR-composition — Task 3's `_is_ui_disabled()`, tested by `test_manual_and_enabled_when_compose_via_or`.
- ✅ Instance-path only; registry path gets a compile-only call-site fix (Task 3 Step 7), no behavior change.
- ✅ Promoted-inlet rows need no new branch: no widget is rendered, `widget_set_enabled` stays `None`, only the row marker applies — Task 3 Step 5.
- ✅ Documentation incl. the channel model and the `render_reactive` drift fix — Task 4.
- ✅ OAK-D concrete consumer, now provably free of the rev-1 camera re-push hazard, with the correct commit repo called out (rev-1 would have `git add`ed through a gitignored symlink) — Task 5. Uses the bulk API, so the hand-maintained per-stream field-name tuples and their typo-warning scaffolding are gone entirely.

**Placeholder scan:** No TBD/TODO markers; every step has literal, complete code; no step corrects an earlier code block in-place (rev 1's Task 2 Step 5 "Wait —" pattern removed — each step shows only final code).

**Type consistency check:** `_resolve_widget_instance` returns `tuple[Callable[[Any], None] | None, Callable[[bool], None]]` (Task 3 Step 7), matched by `_build_label_widget`'s return, the instance call site (`value_apply, widget_set_enabled = ...`, Step 5), and the registry call site (`callback, _set_enabled = ...; return callback`, Step 7). `BaseWidget.set_enabled(enabled: bool) -> None` (Task 2) matches its use as `Callable[[bool], None]` via the bound-method reference in Task 3. `subscribe_ui_state` listener signature `(name: str, disabled: bool)` matches `_on_ui_state_change(name, _disabled)` in Task 3 and every Task 1 test. `set_ui_disabled`/`is_ui_disabled` signatures match all call sites in Tasks 3 and 5. `DISABLED_STYLE` is defined once in `widget/base.py` (Task 2) and imported by `render_utils.py` (Task 3) — no duplicated literal. `set_ui_disabled_all(disabled: bool)` (Task 1) matches its three call sites in Task 5's `hb_refresh_stream_status_indication`.
