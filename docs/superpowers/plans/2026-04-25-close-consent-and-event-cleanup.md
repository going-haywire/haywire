# Close Consent + Event-Bus Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a close-consent gate so editors can veto/dialog when a tab is closed (with a dirty-state flag and bar badge for unsaved-work indication), and clean up the now-vestigial `TAB_CLOSE_REQUESTED` / `TAB_REPAYLOAD_REQUESTED` events that route editor→shell→slot only because the editor used to have no direct path to its slot.

**Architecture:** `EditorWrapper` becomes the editor's direct handle to its slot via a new `_slot` reference. New methods on the wrapper: `set_dirty(value)`, `request_close()` (async, awaits `instance.handle_close_request()`), `close()` (async, asks consent then closes), `force_close()` (sync, programmatic). `BaseEditor` gets a default async `handle_close_request() -> True`. Tab bar prefixes labels with `"• "` when `wrapper.state.is_dirty`. The X-button path becomes async, awaits consent. Two `ContextChangeType` enum values + their shell handlers + their event emissions in `graph_editor.py` are deleted entirely — the editor calls wrapper methods directly. Shell stays as a routing switchboard for genuinely cross-slot concerns only.

**Tech Stack:** Python 3.12, NiceGUI, pytest, ruff, mypy. Existing haywire `EditorWrapper` / `Slot` / `Shell` infrastructure (squashed at commit `41695d8`).

---

## File Structure

**No new files.** This is a focused refactor + feature on existing modules.

**Modified files:**
- `packages/haywire-core/src/haywire/ui/editor/wrapper.py` — `_slot` reference, `is_dirty` state, `set_dirty`, `request_close`, `close`, `force_close`; `repayload` extended; `_on_lifecycle_event` clears `is_dirty` on class swap
- `packages/haywire-core/src/haywire/ui/editor/base.py` — `async def handle_close_request() -> bool` returning `True`
- `packages/haywire-core/src/haywire/ui/app/slot.py` — `add_binding` sets `wrapper._slot`; `remove_binding` clears it
- `packages/haywire-core/src/haywire/ui/app/tab_slot.py` — `_on_tab_close_clicked` becomes async, awaits `wrapper.close()`; `_render_bar_contents` adds dirty-prefix
- `packages/haywire-core/src/haywire/ui/app/shell.py` — delete `_handle_tab_close_requested`, `_handle_tab_repayload_requested`, their dispatch in `_on_context_changed`
- `packages/haywire-core/src/haywire/ui/context_events.py` — delete `TAB_CLOSE_REQUESTED`, `TAB_REPAYLOAD_REQUESTED` enum values
- `barn/haybale-studio/haybale_studio/editors/graph_editor.py` — replace event emissions with `wrapper.force_close()` and `wrapper.repayload(...)`
- `tests/ui/test_editor_wrapper.py` — new tests for set_dirty, request_close, close, force_close, lifecycle clears dirty
- `tests/ui/test_slot_tab.py` — new tests for async X-button consent flow, repayload via wrapper
- `tests/ui/test_app_shell.py` — delete tests for removed shell handlers
- `tests/studio/test_graph_editor_on_focus.py` — update assertion away from event-type check

---

## Definitions Used Across Tasks

These method signatures appear repeatedly. Defined once here so later tasks reference consistent names.

```python
# In wrapper.py — new methods on EditorWrapper

def set_dirty(self, value: bool) -> None:
    """Mark the wrapped editor's content as dirty (or not).
    
    Called by editors when in-memory state diverges from disk. The bar's
    dirty badge reads state.is_dirty on the next render — no immediate
    refresh is triggered (lazy).
    """
    self._state.is_dirty = bool(value)

async def request_close(self) -> bool:
    """Ask the editor whether it allows closing. Returns True if allowed,
    False if the editor vetoed (e.g. user cancelled save dialog).
    
    No-op-allows when there's no instance (broken / unloaded wrapper has
    nothing to ask).
    """
    if self._instance is None:
        return True
    try:
        return bool(await self._instance.handle_close_request())
    except Exception as exc:
        logger.warning(
            f"EditorWrapper '{self.editor_key}': handle_close_request raised "
            f"({exc}); allowing close to avoid a stuck tab."
        )
        return True

async def close(self) -> bool:
    """User-initiated close. Asks consent; closes if allowed.
    
    Returns True if the close happened, False if the editor vetoed.
    """
    if not await self.request_close():
        return False
    self.force_close()
    return True

def force_close(self) -> None:
    """Programmatic close. Skips consent. For editor self-initiated paths
    where the data source vanished or the editor has already decided."""
    if self._slot is not None:
        self._slot.close_tab(self.editor_key, self.payload)
```

```python
# In wrapper.py — extended repayload (currently a one-line setter)

def repayload(self, new_payload: Optional[str], new_label: Optional[str] = None) -> None:
    """Update the payload (and optional label) in place. Calls slot to
    update DOM-side housekeeping (panel name, set_value, bar refresh).
    
    Editor authors call this from save-as / rename flows. The slot owns
    collision detection.
    """
    if self._slot is None:
        # Detached wrapper (e.g. test) — just update the field.
        self.payload = new_payload
        if new_label is not None:
            self.label = new_label
        return
    self._slot.repayload_tab(
        self.editor_key,
        self.payload,
        new_payload,
        new_label,
    )
```

```python
# In base.py — new method on BaseEditor

async def handle_close_request(self) -> bool:
    """Called when the user attempts to close this editor's tab.
    
    Override to show a save / discard / cancel dialog when the editor has
    unsaved state. Return True to allow close, False to veto.
    
    The default implementation always allows close.
    """
    return True
```

---

### Task 1: Add `is_dirty` field + `set_dirty` method on the wrapper

**Why:** Foundation for the bar badge and the consent-gate UX. No consumers yet — pure additive change.

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/editor/wrapper.py`
- Modify: `tests/ui/test_editor_wrapper.py`

- [ ] **Step 1.1: Write failing tests for `is_dirty` and `set_dirty`**

Append to `tests/ui/test_editor_wrapper.py` (after the existing repayload tests at the bottom):

```python
def test_state_default_is_not_dirty():
    state = EditorWrapperState()
    assert state.is_dirty is False


def test_set_dirty_updates_state_flag():
    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="fake:editor:1",
        editor_cls=_FakeEditorCls,
        registry=reg,
        session=_make_session(),
    )
    assert w.state.is_dirty is False
    w.set_dirty(True)
    assert w.state.is_dirty is True
    w.set_dirty(False)
    assert w.state.is_dirty is False


def test_set_dirty_coerces_truthy_values_to_bool():
    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="fake:editor:1",
        editor_cls=_FakeEditorCls,
        registry=reg,
        session=_make_session(),
    )
    w.set_dirty(1)  # truthy non-bool
    assert w.state.is_dirty is True
    assert isinstance(w.state.is_dirty, bool)
```

- [ ] **Step 1.2: Run tests — verify they fail**

Run: `uv run pytest tests/ui/test_editor_wrapper.py -v -k "dirty"`
Expected: FAIL — `EditorWrapperState` has no `is_dirty` attribute and `EditorWrapper` has no `set_dirty` method.

- [ ] **Step 1.3: Add `is_dirty` field to `EditorWrapperState`**

Edit `packages/haywire-core/src/haywire/ui/editor/wrapper.py`. Find the `EditorWrapperState` dataclass (around line 30) and add a new field after the existing fields (after `error_runtime`):

```python
@dataclass
class EditorWrapperState:
    # ... existing fields (is_imported, error_import, error_instantiate, error_runtime) ...

    is_dirty: bool = False
    """True when the editor's in-memory content differs from disk.

    Editors set this via :meth:`EditorWrapper.set_dirty` to drive the tab's
    dirty badge and the close-consent gate. Framework clears it automatically
    on hot-reload class swap (the new instance starts fresh)."""
```

- [ ] **Step 1.4: Add `set_dirty` method to `EditorWrapper`**

In the same file, find a good spot in `EditorWrapper` (after `set_redraw_callback` around line 185, in the "Wiring" section). Add:

```python
    def set_dirty(self, value: bool) -> None:
        """Mark the wrapped editor's content as dirty (or not).

        Called by editors when in-memory state diverges from disk. The
        tab bar reads ``state.is_dirty`` on its next render to show the
        unsaved-work badge — no immediate refresh is triggered (lazy
        update is acceptable since the next user action repaints the bar).
        """
        self._state.is_dirty = bool(value)
```

- [ ] **Step 1.5: Run tests — verify they pass**

Run: `uv run pytest tests/ui/test_editor_wrapper.py -v -k "dirty"`
Expected: PASS — 3 new tests.

- [ ] **Step 1.6: Run full wrapper tests + lint**

Run: `uv run pytest tests/ui/test_editor_wrapper.py && uv run ruff check packages/haywire-core/src/haywire/ui/editor/wrapper.py tests/ui/test_editor_wrapper.py && uv run ruff format --check packages/haywire-core/src/haywire/ui/editor/wrapper.py tests/ui/test_editor_wrapper.py`
Expected: all PASS, ruff clean.

- [ ] **Step 1.7: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/editor/wrapper.py tests/ui/test_editor_wrapper.py
git commit -m "$(cat <<'EOF'
feat(editor-wrapper): add is_dirty state + set_dirty mutator

EditorWrapperState gains an is_dirty bool flag (default False). Editors
call wrapper.set_dirty(bool) when in-memory content diverges from disk.
No callbacks fired — the next bar render reads state.is_dirty and acts
accordingly. Lazy update is acceptable because user actions naturally
trigger bar refreshes within seconds.

Foundation for the dirty badge and close-consent gate; no consumers
hooked up yet.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Add `_slot` back-reference on `EditorWrapper`

**Why:** Wrapper needs to call back into the slot for `close_tab` and `repayload_tab`. The slot sets the reference in `add_binding`, clears it in `remove_binding` and `cleanup`.

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/editor/wrapper.py`
- Modify: `packages/haywire-core/src/haywire/ui/app/slot.py`
- Modify: `tests/ui/test_editor_wrapper.py`

- [ ] **Step 2.1: Write failing test for slot reference lifecycle**

Append to `tests/ui/test_editor_wrapper.py`:

```python
def test_wrapper_slot_starts_as_none():
    """Until a slot adopts the wrapper via add_binding, _slot is None."""
    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="fake:editor:1",
        editor_cls=_FakeEditorCls,
        registry=reg,
        session=_make_session(),
    )
    assert w._slot is None


def test_wrapper_cleanup_clears_slot_reference():
    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="fake:editor:1",
        editor_cls=_FakeEditorCls,
        registry=reg,
        session=_make_session(),
    )
    # Simulate slot adoption (slot would do this in add_binding).
    sentinel_slot = object()
    w._slot = sentinel_slot
    assert w._slot is sentinel_slot
    w.cleanup()
    assert w._slot is None
```

- [ ] **Step 2.2: Run tests — verify they fail**

Run: `uv run pytest tests/ui/test_editor_wrapper.py -v -k "slot_reference or slot_starts"`
Expected: FAIL — `EditorWrapper._slot` attribute doesn't exist.

- [ ] **Step 2.3: Add `_slot` field to `EditorWrapper`**

Edit `wrapper.py`. In `EditorWrapper.__init__`, after the existing field initializations (after `self._redraw_callback = None`):

```python
        # The slot that owns this wrapper. Set by Slot.add_binding when the
        # wrapper is adopted; cleared on cleanup. Used by close()/force_close()/
        # repayload() to call back into the slot's mutation methods.
        self._slot: Any = None
```

(`Any` is already imported from earlier slot work.)

In `EditorWrapper.cleanup`, add `self._slot = None` to the existing teardown sequence:

```python
    def cleanup(self) -> None:
        """Tear down the wrapper. Idempotent."""
        try:
            self._registry.remove_event_subscriber(self.editor_key, self._on_lifecycle_event)
        except Exception as exc:
            logger.warning(f"EditorWrapper '{self.editor_key}': failed to unsubscribe from registry: {exc}")
        if self._instance is not None:
            try:
                self._instance.cleanup()
            except Exception as exc:
                logger.warning(f"EditorWrapper '{self.editor_key}': instance.cleanup() raised: {exc}")
            self._instance = None
        self._state = None
        self._session = None
        self._redraw_callback = None
        self._slot = None
```

- [ ] **Step 2.4: Run wrapper-side tests**

Run: `uv run pytest tests/ui/test_editor_wrapper.py -v -k "slot_reference or slot_starts"`
Expected: PASS.

- [ ] **Step 2.5: Set `_slot` on the wrapper from `Slot.add_binding`**

Edit `packages/haywire-core/src/haywire/ui/app/slot.py`. Find `add_binding` (around line 535). After the wrapper is constructed and before `set_redraw_callback`, add:

```python
        wrapper = EditorWrapper(
            editor_key=editor_key,
            editor_cls=editor_cls,
            registry=self._registry,
            session=self._session,
            payload=payload,
        )
        wrapper._slot = self  # ← ADD THIS LINE
        wrapper.set_redraw_callback(lambda w=wrapper: self._redraw(w))
        # ... rest of add_binding unchanged ...
```

(Find the exact insertion point — it's right after `wrapper = EditorWrapper(...)` and before `wrapper.set_redraw_callback(...)`.)

- [ ] **Step 2.6: Run the full slot test suite to confirm no regression**

Run: `uv run pytest tests/ui/ tests/studio/ -v 2>&1 | tail -20`
Expected: PASS. No test count change yet (we only added one assignment).

- [ ] **Step 2.7: Run lint + format**

Run: `uv run ruff check packages/haywire-core/src/haywire/ui/editor/wrapper.py packages/haywire-core/src/haywire/ui/app/slot.py tests/ui/test_editor_wrapper.py && uv run ruff format --check packages/haywire-core/src/haywire/ui/editor/wrapper.py packages/haywire-core/src/haywire/ui/app/slot.py tests/ui/test_editor_wrapper.py`
Expected: clean.

- [ ] **Step 2.8: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/editor/wrapper.py packages/haywire-core/src/haywire/ui/app/slot.py tests/ui/test_editor_wrapper.py
git commit -m "$(cat <<'EOF'
feat(editor-wrapper): add _slot back-reference

Wrapper now carries a reference to its host slot. Set in
Slot.add_binding when the wrapper is adopted; cleared in
wrapper.cleanup. Foundation for upcoming wrapper.close() /
wrapper.force_close() / wrapper.repayload() — these will call
slot mutation methods directly, replacing the editor→shell→slot
event-bus relay that exists today only because the editor had
no direct path to its slot.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Add `BaseEditor.handle_close_request` (default returns True)

**Why:** The contract editors override to opt into the consent gate. Default impl is a no-veto so existing editors keep working unchanged.

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/editor/base.py`
- Modify: `tests/ui/test_editor_wrapper.py`

- [ ] **Step 3.1: Write failing test for default `handle_close_request`**

Append to `tests/ui/test_editor_wrapper.py`:

```python
import asyncio


def test_base_editor_handle_close_request_defaults_to_true():
    """The framework default is 'allow close' — editors override to veto."""
    from haywire.ui.editor.base import BaseEditor
    from haywire.ui.editor.identity import EditorIdentity

    class _MinimalEditor(BaseEditor):
        class_identity = EditorIdentity(
            registry_key="test:close-default",
            label="Test",
            icon=None,
            default_slot="main",
        )

        def draw(self, context, container):
            pass

    editor = _MinimalEditor()
    result = asyncio.run(editor.handle_close_request())
    assert result is True
```

- [ ] **Step 3.2: Run test — verify it fails**

Run: `uv run pytest tests/ui/test_editor_wrapper.py -v -k "handle_close_request_defaults"`
Expected: FAIL — `handle_close_request` doesn't exist on `BaseEditor`.

- [ ] **Step 3.3: Add `handle_close_request` to `BaseEditor`**

Edit `packages/haywire-core/src/haywire/ui/editor/base.py`. After `cleanup()` (around line 122), add:

```python
    async def handle_close_request(self) -> bool:
        """Decide whether to allow this editor's tab to close.

        Called when the user clicks the X on the tab (the slot awaits this
        before removing the wrapper). Override to show a save / discard /
        cancel dialog when the editor has unsaved content; await the user's
        choice; return True to allow the close, False to veto.

        The default implementation always allows close. Editors that don't
        track dirty state can ignore this method entirely.

        Read ``self.wrapper.state.is_dirty`` to check whether to prompt.
        Editors are responsible for their own dialog UI — the framework
        provides the gate but no default dialog.
        """
        return True
```

- [ ] **Step 3.4: Run test — verify it passes**

Run: `uv run pytest tests/ui/test_editor_wrapper.py -v -k "handle_close_request_defaults"`
Expected: PASS.

- [ ] **Step 3.5: Run full wrapper tests + lint**

Run: `uv run pytest tests/ui/test_editor_wrapper.py && uv run ruff check packages/haywire-core/src/haywire/ui/editor/base.py && uv run ruff format --check packages/haywire-core/src/haywire/ui/editor/base.py`
Expected: all PASS, ruff clean.

- [ ] **Step 3.6: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/editor/base.py tests/ui/test_editor_wrapper.py
git commit -m "$(cat <<'EOF'
feat(editor): add BaseEditor.handle_close_request consent hook

Async method, default returns True (allow close). Editors override to
show save/discard/cancel dialogs when state.is_dirty is set. Framework
provides the gate; UI of the dialog is each editor's concern.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Add `EditorWrapper.request_close` + `close` + `force_close`

**Why:** The wrapper-side close API. `request_close` only asks the gate. `close` (async) asks then closes. `force_close` (sync) skips consent.

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/editor/wrapper.py`
- Modify: `tests/ui/test_editor_wrapper.py`

- [ ] **Step 4.1: Write failing tests**

Append to `tests/ui/test_editor_wrapper.py`:

```python
def test_request_close_returns_true_when_no_instance():
    """A wrapper with no instance allows close (nothing to ask)."""
    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="fake:editor:1",
        editor_cls=_FakeEditorCls,
        registry=reg,
        session=_make_session(),
    )
    # No instance yet (lazy)
    assert w._instance is None
    result = asyncio.run(w.request_close())
    assert result is True


class _ConsentingEditorCls:
    """Stub editor that records handle_close_request calls and returns a
    configurable value."""
    class_identity = SimpleNamespace(
        registry_key="consent:editor:1",
        label="Consent",
        default_slot="main",
        opens=None,
    )

    def __init__(self):
        self.wrapper = None
        self.consent_calls = 0
        self.consent_response = True

    async def handle_close_request(self):
        self.consent_calls += 1
        return self.consent_response


def test_request_close_delegates_to_instance_handle_close_request():
    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="consent:editor:1",
        editor_cls=_ConsentingEditorCls,
        registry=reg,
        session=_make_session(),
    )
    w._instantiate()  # force instance creation
    result = asyncio.run(w.request_close())
    assert result is True
    assert w._instance.consent_calls == 1


def test_request_close_returns_false_when_editor_vetoes():
    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="consent:editor:1",
        editor_cls=_ConsentingEditorCls,
        registry=reg,
        session=_make_session(),
    )
    w._instantiate()
    w._instance.consent_response = False
    result = asyncio.run(w.request_close())
    assert result is False


def test_request_close_allows_when_handle_close_request_raises():
    """A buggy handle_close_request must not strand the user with an
    unclosable tab. Allow close on exception."""
    class _RaisingConsentCls:
        class_identity = SimpleNamespace(
            registry_key="rc:editor:1",
            label="RC",
            default_slot="main",
            opens=None,
        )

        def __init__(self):
            self.wrapper = None

        async def handle_close_request(self):
            raise RuntimeError("buggy editor")

    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="rc:editor:1",
        editor_cls=_RaisingConsentCls,
        registry=reg,
        session=_make_session(),
    )
    w._instantiate()
    result = asyncio.run(w.request_close())
    assert result is True


class _FakeSlot:
    """Stub slot that records close_tab calls."""

    def __init__(self):
        self.close_calls: list = []

    def close_tab(self, editor_key, payload):
        self.close_calls.append((editor_key, payload))
        return True


def test_force_close_calls_slot_close_tab():
    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="fake:editor:1",
        editor_cls=_FakeEditorCls,
        registry=reg,
        session=_make_session(),
        payload="/tmp/x",
    )
    fake_slot = _FakeSlot()
    w._slot = fake_slot
    w.force_close()
    assert fake_slot.close_calls == [("fake:editor:1", "/tmp/x")]


def test_force_close_no_op_when_no_slot():
    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="fake:editor:1",
        editor_cls=_FakeEditorCls,
        registry=reg,
        session=_make_session(),
    )
    # No slot attached — must not raise
    w.force_close()


def test_close_calls_slot_close_tab_on_consent():
    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="consent:editor:1",
        editor_cls=_ConsentingEditorCls,
        registry=reg,
        session=_make_session(),
    )
    w._instantiate()
    fake_slot = _FakeSlot()
    w._slot = fake_slot
    closed = asyncio.run(w.close())
    assert closed is True
    assert len(fake_slot.close_calls) == 1


def test_close_does_not_call_slot_when_editor_vetoes():
    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="consent:editor:1",
        editor_cls=_ConsentingEditorCls,
        registry=reg,
        session=_make_session(),
    )
    w._instantiate()
    w._instance.consent_response = False
    fake_slot = _FakeSlot()
    w._slot = fake_slot
    closed = asyncio.run(w.close())
    assert closed is False
    assert fake_slot.close_calls == []
```

- [ ] **Step 4.2: Run tests — verify they fail**

Run: `uv run pytest tests/ui/test_editor_wrapper.py -v -k "request_close or force_close or test_close_"`
Expected: FAIL — methods don't exist.

- [ ] **Step 4.3: Implement `request_close`, `close`, `force_close`**

Edit `packages/haywire-core/src/haywire/ui/editor/wrapper.py`. Find the `repayload` method (around line 360) and add the three new methods before it (so the close methods are grouped together logically). Insert this block:

```python
    async def request_close(self) -> bool:
        """Ask the editor whether it allows closing.

        Returns True if the close should proceed, False if the editor
        vetoed (e.g. user cancelled at a save dialog).

        No-op-allows when there's no instance — a broken or unloaded
        wrapper has nothing to ask. If ``handle_close_request`` raises,
        the close is allowed (better to lose veto than strand the user
        with an unclosable tab).
        """
        if self._instance is None:
            return True
        try:
            return bool(await self._instance.handle_close_request())
        except Exception as exc:
            logger.warning(
                f"EditorWrapper '{self.editor_key}': handle_close_request "
                f"raised ({exc}); allowing close to avoid a stuck tab."
            )
            return True

    async def close(self) -> bool:
        """User-initiated close. Asks consent, closes if allowed.

        Returns True if the close happened, False if the editor vetoed.
        Use :meth:`force_close` for programmatic closes that should skip
        the consent gate.
        """
        if not await self.request_close():
            return False
        self.force_close()
        return True

    def force_close(self) -> None:
        """Programmatic close. Skips the consent gate.

        For editor self-initiated paths where the data source vanished
        or the editor has already decided. Calls into the slot directly
        — no-op if the wrapper isn't attached to a slot (defensive).
        """
        if self._slot is None:
            logger.debug(
                f"EditorWrapper '{self.editor_key}': force_close called but "
                f"no slot attached; nothing to do."
            )
            return
        self._slot.close_tab(self.editor_key, self.payload)
```

- [ ] **Step 4.4: Run tests — verify they pass**

Run: `uv run pytest tests/ui/test_editor_wrapper.py -v`
Expected: PASS — all wrapper tests pass.

- [ ] **Step 4.5: Run full unit suite + lint**

Run: `uv run pytest -m "not integration" 2>&1 | tail -3 && uv run ruff check packages/haywire-core/src/haywire/ui/editor/wrapper.py tests/ui/test_editor_wrapper.py && uv run ruff format --check packages/haywire-core/src/haywire/ui/editor/wrapper.py tests/ui/test_editor_wrapper.py`
Expected: PASS, ruff clean.

- [ ] **Step 4.6: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/editor/wrapper.py tests/ui/test_editor_wrapper.py
git commit -m "$(cat <<'EOF'
feat(editor-wrapper): add request_close, close, force_close

Three close-related methods on the wrapper:
- request_close (async): ask the editor's handle_close_request hook
  whether closing is allowed; defaults to True when no instance; allows
  close on exception to avoid stuck tabs
- close (async): high-level user-initiated path; awaits consent then
  calls slot.close_tab via force_close
- force_close (sync): programmatic close, skips consent; for editor
  self-initiated paths (e.g. data source vanished)

Wrapper is now the single authoritative place for closing an editor.
Slot-side / shell-side relays will be migrated to this API in upcoming
tasks.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Extend `EditorWrapper.repayload` to call slot directly

**Why:** Today `repayload` is a one-line setter. Editors that want to actually re-key the tab (e.g. graph save-as) currently emit a `TAB_REPAYLOAD_REQUESTED` event that the shell relays to `slot.repayload_tab`. Wrapper should do this directly.

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/editor/wrapper.py`
- Modify: `tests/ui/test_editor_wrapper.py`

- [ ] **Step 5.1: Update existing repayload tests + add new tests for slot delegation**

The existing tests `test_repayload_updates_payload_and_binding_id` and `test_repayload_to_none_removes_suffix` work on detached wrappers (no `_slot`). They should keep passing as a "no-slot fallback" path. Verify by reading them — they don't set `_slot`, so the new logic's `if self._slot is None:` branch handles them.

Append new tests to `tests/ui/test_editor_wrapper.py`:

```python
class _RepayloadTrackingSlot:
    """Stub slot recording repayload_tab calls."""

    def __init__(self):
        self.repayload_calls: list = []

    def repayload_tab(self, editor_key, old_payload, new_payload, new_label):
        self.repayload_calls.append((editor_key, old_payload, new_payload, new_label))
        return True

    def close_tab(self, editor_key, payload):
        return True


def test_repayload_with_slot_delegates_to_slot_repayload_tab():
    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="fake:editor:1",
        editor_cls=_FakeEditorCls,
        registry=reg,
        session=_make_session(),
        payload="__unsaved_3__",
    )
    fake_slot = _RepayloadTrackingSlot()
    w._slot = fake_slot
    w.repayload("/tmp/saved.haywire", new_label="saved.haywire")
    assert fake_slot.repayload_calls == [
        ("fake:editor:1", "__unsaved_3__", "/tmp/saved.haywire", "saved.haywire")
    ]


def test_repayload_without_slot_just_updates_field():
    """Detached wrapper (no slot) — repayload still updates payload field
    so unit tests can verify identity changes without a slot."""
    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="fake:editor:1",
        editor_cls=_FakeEditorCls,
        registry=reg,
        session=_make_session(),
        payload="x",
    )
    # No _slot set
    w.repayload("y", new_label="Y")
    assert w.payload == "y"
    assert w.label == "Y"


def test_repayload_label_is_optional():
    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="fake:editor:1",
        editor_cls=_FakeEditorCls,
        registry=reg,
        session=_make_session(),
        payload="x",
    )
    w.repayload("y")  # no new_label
    assert w.payload == "y"
```

- [ ] **Step 5.2: Run new tests — verify they fail**

Run: `uv run pytest tests/ui/test_editor_wrapper.py -v -k "repayload"`
Expected: FAIL — current `repayload` doesn't accept `new_label` and doesn't delegate to slot.

- [ ] **Step 5.3: Replace `repayload` with the extended version**

Edit `packages/haywire-core/src/haywire/ui/editor/wrapper.py`. Find the existing `repayload` method (one-liner, around line 360 after the close methods we just added) and replace it:

```python
    def repayload(self, new_payload: Optional[str], new_label: Optional[str] = None) -> None:
        """Update the payload (and optional label) in place.

        When attached to a slot, delegates to ``slot.repayload_tab`` for
        DOM-side housekeeping (panel name, set_value, bar refresh, collision
        detection). When detached (e.g. unit tests with no slot), updates
        the wrapper's fields directly so identity helpers like
        ``binding_id`` reflect the change.

        Editor authors call this from save-as / rename flows. The slot
        owns collision detection — if ``new_payload`` collides with another
        wrapper's binding_id, the slot logs a warning and the call is a
        no-op.
        """
        if self._slot is None:
            self.payload = new_payload
            if new_label is not None:
                self.label = new_label
            return
        self._slot.repayload_tab(
            self.editor_key,
            self.payload,
            new_payload,
            new_label,
        )
```

- [ ] **Step 5.4: Run tests — verify they pass**

Run: `uv run pytest tests/ui/test_editor_wrapper.py -v -k "repayload"`
Expected: PASS — all repayload tests (existing + new).

- [ ] **Step 5.5: Run full unit suite to confirm no regression elsewhere**

Run: `uv run pytest -m "not integration" 2>&1 | tail -3`
Expected: PASS.

- [ ] **Step 5.6: Lint + format**

Run: `uv run ruff check packages/haywire-core/src/haywire/ui/editor/wrapper.py tests/ui/test_editor_wrapper.py && uv run ruff format --check packages/haywire-core/src/haywire/ui/editor/wrapper.py tests/ui/test_editor_wrapper.py`
Expected: clean.

- [ ] **Step 5.7: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/editor/wrapper.py tests/ui/test_editor_wrapper.py
git commit -m "$(cat <<'EOF'
feat(editor-wrapper): extend repayload to call slot.repayload_tab

When attached to a slot, repayload now delegates to
slot.repayload_tab (DOM updates, bar refresh, collision detection).
When detached (e.g. unit tests), updates fields directly. Adds
optional new_label parameter so save-as flows can update both
payload and label in one call.

Replaces the editor->shell->slot relay path that uses
TAB_REPAYLOAD_REQUESTED today.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: Clear `is_dirty` on hot-reload class swap

**Why:** When the editor class is reloaded (`CLASS_RELOADED` or `CLASS_ADDED` after recovery), the instance is replaced. Whatever was "dirty" in the old instance's memory is gone — the dirty flag is meaningless. Clear it.

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/editor/wrapper.py`
- Modify: `tests/ui/test_editor_wrapper.py`

- [ ] **Step 6.1: Write failing test**

Append to `tests/ui/test_editor_wrapper.py`:

```python
def test_lifecycle_class_reloaded_clears_is_dirty():
    """Hot-reload replaces the instance; in-memory unsaved state is gone
    along with it, so the dirty flag must clear."""
    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="fake:editor:1",
        editor_cls=_FakeEditorCls,
        registry=reg,
        session=_make_session(),
    )
    w.set_dirty(True)
    assert w.state.is_dirty is True

    event = LifeCycleEvent(
        event_type=LifeCycleEventType.CLASS_RELOADED,
        registry_key="fake:editor:1",
        affected_class=_NewFakeEditorCls,
    )
    w._on_lifecycle_event(event)

    assert w.state.is_dirty is False
```

(`_NewFakeEditorCls` is already defined in the existing lifecycle tests.)

- [ ] **Step 6.2: Run test — verify it fails**

Run: `uv run pytest tests/ui/test_editor_wrapper.py -v -k "class_reloaded_clears_is_dirty"`
Expected: FAIL — `_on_lifecycle_event` doesn't clear `is_dirty`.

- [ ] **Step 6.3: Update `_on_lifecycle_event` to clear `is_dirty` on success path**

Edit `packages/haywire-core/src/haywire/ui/editor/wrapper.py`. Find `_on_lifecycle_event` (around line 199). In the "Successful event with new class" branch (where `editor_cls` is updated and `_instance` is cleared), add `self._state.is_dirty = False`:

```python
        # Successful event with new class
        if event.affected_class is not None:
            self.editor_cls = event.affected_class
            self._state.is_imported = True
            self._state.error_import = None
            self._state.is_dirty = False  # ← ADD THIS LINE
            # Clear instance so next draw lazy-instantiates with new class
            if self._instance is not None:
                try:
                    self._instance.cleanup()
                except Exception as exc:
                    logger.warning(
                        f"EditorWrapper '{self.editor_key}': "
                        f"instance.cleanup() raised during reload: {exc}"
                    )
                self._instance = None
            if self._redraw_callback is not None:
                self._redraw_callback(self)
```

- [ ] **Step 6.4: Run test — verify it passes**

Run: `uv run pytest tests/ui/test_editor_wrapper.py -v -k "class_reloaded_clears_is_dirty"`
Expected: PASS.

- [ ] **Step 6.5: Run full wrapper tests + lint**

Run: `uv run pytest tests/ui/test_editor_wrapper.py && uv run ruff check packages/haywire-core/src/haywire/ui/editor/wrapper.py && uv run ruff format --check packages/haywire-core/src/haywire/ui/editor/wrapper.py`
Expected: PASS, ruff clean.

- [ ] **Step 6.6: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/editor/wrapper.py tests/ui/test_editor_wrapper.py
git commit -m "$(cat <<'EOF'
fix(editor-wrapper): clear is_dirty on hot-reload class swap

CLASS_RELOADED / CLASS_ADDED replace the instance and discard
its in-memory state. The dirty flag is part of that state; carrying
it across the swap is meaningless because the new instance has no
unsaved content yet. Clear it alongside the existing class/instance
swap.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: Migrate the X-button path — slot calls `wrapper.close()` directly, no event

**Why:** The slot's X-button handler currently emits `TAB_CLOSE_REQUESTED` so the shell can relay it back to the same slot. With wrapper-direct close, the slot calls `wrapper.close()` itself.

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/app/tab_slot.py`
- Modify: `tests/ui/test_slot_tab.py`

- [ ] **Step 7.1: Read the current `_on_tab_close_clicked` to understand what we're replacing**

Read `packages/haywire-core/src/haywire/ui/app/tab_slot.py` around line 116-125. The current implementation:

```python
def _on_tab_close_clicked(self, tab_id: str) -> None:
    """Emit TAB_CLOSE_REQUESTED so host apps can run domain cleanup."""
    editor_key, payload = EditorWrapper.split_id(tab_id)
    self._session.notify_context_changed(
        ContextChangedEvent(
            change_type=ContextChangeType.TAB_CLOSE_REQUESTED,
            source_editor="app_shell",
            detail={"slot_name": self.name, "editor_key": editor_key, "payload": payload},
        )
    )
```

- [ ] **Step 7.2: Write failing test for the new async X-button behavior**

Append to `tests/ui/test_slot_tab.py`:

```python
import asyncio


class _VetoEditor:
    """Editor that vetoes close on first click, allows on second."""
    class_identity = SimpleNamespace(
        registry_key="veto:editor:1",
        label="Veto",
        default_slot="main",
        opens=None,
    )

    def __init__(self):
        self.wrapper = None
        self.consent_calls = 0
        self.allow = False

    async def handle_close_request(self):
        self.consent_calls += 1
        return self.allow

    def draw(self, context, container):
        pass


def test_on_tab_close_clicked_calls_wrapper_close():
    reg = _FakeRegistry()
    sess = _session_with_context()
    slot = TabSlot(session=sess, name="main", registry=reg)
    slot.add_binding(editor_key="veto:editor:1", editor_cls=_VetoEditor)
    slot.add_binding(editor_key="other:editor", editor_cls=_FakeEditor)
    target = slot.find_binding("veto:editor:1")
    slot._active = target
    # Force instance creation so handle_close_request can run
    target._instantiate()
    target._instance.allow = True

    # Simulate the click; coroutine returned for async _on_tab_close_clicked
    asyncio.run(slot._on_tab_close_clicked("veto:editor:1"))

    # The veto editor should have been asked
    assert target._instance is not None or target not in slot.bindings
    # Tab should be gone after consent allowed
    assert slot.find_binding("veto:editor:1") is None


def test_on_tab_close_clicked_respects_veto():
    reg = _FakeRegistry()
    sess = _session_with_context()
    slot = TabSlot(session=sess, name="main", registry=reg)
    slot.add_binding(editor_key="veto:editor:1", editor_cls=_VetoEditor)
    target = slot.find_binding("veto:editor:1")
    slot._active = target
    target._instantiate()
    target._instance.allow = False  # veto

    asyncio.run(slot._on_tab_close_clicked("veto:editor:1"))

    # Tab should still be there
    assert slot.find_binding("veto:editor:1") is target


def test_on_tab_close_clicked_no_longer_emits_tab_close_requested():
    """Regression: the X-button must NOT emit TAB_CLOSE_REQUESTED anymore.
    The slot calls wrapper.close() directly."""
    reg = _FakeRegistry()
    sess = _session_with_context()
    events_seen: list = []
    sess._notify_callback = events_seen.append  # capture all session events
    slot = TabSlot(session=sess, name="main", registry=reg)
    slot.add_binding(editor_key="fake:editor:1", editor_cls=_FakeEditor)
    target = slot.find_binding("fake:editor:1")
    slot._active = target

    asyncio.run(slot._on_tab_close_clicked("fake:editor:1"))

    # No events emitted to session by the close path
    assert events_seen == []
```

If `_session_with_context` doesn't provide a `_notify_callback` hook, replace the assertion with:

```python
    # The session's notify_context_changed must not have been called for close
    # (test via the session's notification recorder if your test harness exposes one).
    # If no recorder is available, this assertion is OK to remove and rely on
    # the type-check that the new code path doesn't reference TAB_CLOSE_REQUESTED.
```

Verify the existing test harness setup by reading `tests/ui/test_slot_tab.py` — adapt the assertion to whatever notification-recording fixture exists. If no recorder exists, drop this third test (the wrapper-side test in Task 4 already proves the close path works without events).

- [ ] **Step 7.3: Run new tests — verify they fail**

Run: `uv run pytest tests/ui/test_slot_tab.py -v -k "on_tab_close_clicked"`
Expected: FAIL — current `_on_tab_close_clicked` is sync and emits an event.

- [ ] **Step 7.4: Replace `_on_tab_close_clicked` with async wrapper-direct version**

Edit `packages/haywire-core/src/haywire/ui/app/tab_slot.py`. Replace the existing method (around line 116) with:

```python
    async def _on_tab_close_clicked(self, tab_id: str) -> None:
        """Ask the editor whether to close, then close if allowed.

        Replaces the previous TAB_CLOSE_REQUESTED event emission — the
        slot now calls into the wrapper directly. The wrapper awaits
        ``handle_close_request`` on the editor instance (which can show
        a save-or-discard dialog) and only invokes ``slot.close_tab``
        if the editor allows the close.
        """
        editor_key, payload = EditorWrapper.split_id(tab_id)
        wrapper = self.find_binding(editor_key, payload)
        if wrapper is None:
            return
        await wrapper.close()
```

NiceGUI's `on_click` accepts async callbacks — no change needed at the `ui.button(...)` site.

- [ ] **Step 7.5: Run tests — verify they pass**

Run: `uv run pytest tests/ui/test_slot_tab.py -v -k "on_tab_close_clicked"`
Expected: PASS.

- [ ] **Step 7.6: Run full suite — verify no slot-level regressions**

Run: `uv run pytest -m "not integration" 2>&1 | tail -3`
Expected: PASS.

- [ ] **Step 7.7: Lint + format**

Run: `uv run ruff check packages/haywire-core/src/haywire/ui/app/tab_slot.py tests/ui/test_slot_tab.py && uv run ruff format --check packages/haywire-core/src/haywire/ui/app/tab_slot.py tests/ui/test_slot_tab.py`
Expected: clean.

- [ ] **Step 7.8: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/app/tab_slot.py tests/ui/test_slot_tab.py
git commit -m "$(cat <<'EOF'
refactor(tab-slot): X-button calls wrapper.close() directly, no event

_on_tab_close_clicked becomes async. Awaits wrapper.close() (which
asks the editor's handle_close_request consent gate), then closes the
tab if allowed. NiceGUI's on_click supports async callbacks natively.

The TAB_CLOSE_REQUESTED event is no longer emitted by the X-button
path. Subsequent tasks will migrate the editor self-close path
(graph_editor) and delete the event entirely.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: Migrate `graph_editor.py` self-close + save-as to wrapper-direct calls

**Why:** Graph editor emits `TAB_CLOSE_REQUESTED` (when the underlying graph entry vanishes) and `TAB_REPAYLOAD_REQUESTED` (after save-as). Replace both with direct wrapper calls.

**Files:**
- Modify: `barn/haybale-studio/haybale_studio/editors/graph_editor.py`
- Modify: `tests/studio/test_graph_editor_on_focus.py`

- [ ] **Step 8.1: Update the on-focus self-close test**

Read `tests/studio/test_graph_editor_on_focus.py` around line 117 — there's an assertion checking `change_type == TAB_CLOSE_REQUESTED`.

The new behavior: graph_editor calls `self.wrapper.force_close()`. Update the test:

Find the test that asserts the TAB_CLOSE_REQUESTED event. Replace the event assertion with one that verifies `wrapper._slot.close_tab` was called. The exact replacement depends on the test setup — look at how the test wires the wrapper's slot.

If the test currently uses a fake session/event recorder:

```python
# OLD (around line 117):
assert ev.change_type == ContextChangeType.TAB_CLOSE_REQUESTED

# NEW: the test needs to verify slot.close_tab was called.
# Inject a fake slot on the wrapper and assert the call.
```

Concrete replacement:

```python
def test_on_focus_when_entry_missing_force_closes_via_wrapper(...):
    # ... existing setup (graph_editor instance, wrapper, etc.) ...
    # Replace the event recorder with a fake slot
    from types import SimpleNamespace

    close_calls: list = []
    fake_slot = SimpleNamespace(
        close_tab=lambda key, payload: close_calls.append((key, payload)) or True,
    )
    editor.wrapper._slot = fake_slot

    # Trigger the on_focus path that should detect missing entry
    editor.on_focus(context)

    assert len(close_calls) == 1
    # Optionally assert the editor_key and payload that was closed
```

(Adapt to the actual test structure — the existing test reads the wrapper from the editor and has access to it.)

- [ ] **Step 8.2: Run the existing test — verify it fails (expected behavior changed)**

Run: `uv run pytest tests/studio/test_graph_editor_on_focus.py -v 2>&1 | tail -20`
Expected: the test that previously asserted TAB_CLOSE_REQUESTED should now fail because the production code still emits the event (we haven't changed it yet). Note the failure for reference — this is the test we're updating to.

- [ ] **Step 8.3: Replace the self-close event emission with `wrapper.force_close()`**

Edit `barn/haybale-studio/haybale_studio/editors/graph_editor.py` lines 117-130. The current code:

```python
        if entry is None:
            if session is not None:
                session.notify_context_changed(
                    ContextChangedEvent(
                        change_type=ContextChangeType.TAB_CLOSE_REQUESTED,
                        source_editor="graph_editor",
                        detail={
                            "slot_name": "main",
                            "editor_key": self.wrapper.editor_key,
                            "payload": payload,
                        },
                    )
                )
            return
```

Replace with:

```python
        if entry is None:
            # Graph entry vanished from the haystack — close ourselves.
            # Programmatic close (no consent dialog needed; the user
            # already removed the underlying graph).
            if self.wrapper is not None:
                self.wrapper.force_close()
            return
```

- [ ] **Step 8.4: Replace the save-as repayload event with `wrapper.repayload(...)`**

Edit `barn/haybale-studio/haybale_studio/editors/graph_editor.py` lines 488-501. The current code:

```python
            if session is not None and self.wrapper is not None and old_payload != new_payload:
                session.notify_context_changed(
                    ContextChangedEvent(
                        change_type=ContextChangeType.TAB_REPAYLOAD_REQUESTED,
                        source_editor="graph_editor",
                        detail={
                            "slot_name": "main",
                            "editor_key": self.wrapper.editor_key,
                            "old_payload": old_payload,
                            "new_payload": new_payload,
                            "new_label": entry.display_name,
                        },
                    )
                )
```

Replace with:

```python
            if self.wrapper is not None and old_payload != new_payload:
                # Save-as renamed the graph entry — re-key the tab so the
                # wrapper's payload + label reflect the new file path.
                self.wrapper.repayload(new_payload, new_label=entry.display_name)
```

- [ ] **Step 8.5: Run tests — verify they pass**

Run: `uv run pytest tests/studio/test_graph_editor_on_focus.py -v`
Expected: PASS.

- [ ] **Step 8.6: Run full studio + ui suite**

Run: `uv run pytest -m "not integration" 2>&1 | tail -3 && uv run pytest -m integration 2>&1 | tail -3`
Expected: PASS on both. Integration suite exercises real wrappers + real slots, so this is the catch-net for any wiring miss.

- [ ] **Step 8.7: Lint + format**

Run: `uv run ruff check barn/haybale-studio/haybale_studio/editors/graph_editor.py tests/studio/test_graph_editor_on_focus.py && uv run ruff format --check barn/haybale-studio/haybale_studio/editors/graph_editor.py tests/studio/test_graph_editor_on_focus.py`
Expected: clean.

- [ ] **Step 8.8: Commit**

```bash
git add barn/haybale-studio/haybale_studio/editors/graph_editor.py tests/studio/test_graph_editor_on_focus.py
git commit -m "$(cat <<'EOF'
refactor(graph-editor): use wrapper.force_close + wrapper.repayload

Graph editor's two close/repayload event emissions become direct
wrapper calls:
- on_focus self-close (entry vanished from haystack) -> wrapper.force_close()
- save-as repayload -> wrapper.repayload(new_payload, new_label=...)

The wrapper now reaches its slot directly via the _slot back-reference,
so the editor->shell->slot relay through the event bus is no longer
needed for these two paths.

Test updated to assert slot.close_tab was called instead of asserting
the now-deleted event type.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 9: Delete `TAB_CLOSE_REQUESTED` and `TAB_REPAYLOAD_REQUESTED` events + shell handlers

**Why:** Now that no code emits them, the enum values, shell handlers, and dispatch lines are dead code. Clean delete.

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/context_events.py`
- Modify: `packages/haywire-core/src/haywire/ui/app/shell.py`
- Modify: `tests/ui/test_app_shell.py`

- [ ] **Step 9.1: Confirm no remaining references in production code**

Run:
```bash
grep -rn "TAB_CLOSE_REQUESTED\|TAB_REPAYLOAD_REQUESTED" packages/ barn/ --include="*.py" 2>/dev/null
```
Expected: only references in `context_events.py` (definition), `shell.py` (handlers), and possibly comments. **Zero references in `tab_slot.py`, `graph_editor.py`, or any other emitter.**

If there ARE remaining references, they're stragglers from Tasks 7-8 and need to be cleaned up before proceeding.

- [ ] **Step 9.2: Delete the enum values from `context_events.py`**

Edit `packages/haywire-core/src/haywire/ui/context_events.py`. Find the two enum lines (around line 29-30):

```python
    TAB_CLOSE_REQUESTED = auto()  # editor (or caller) is asking the shell to close a tab
    TAB_REPAYLOAD_REQUESTED = auto()  # re-key a tab after save-as / rename
```

Delete both lines.

- [ ] **Step 9.3: Delete the shell handler methods**

Edit `packages/haywire-core/src/haywire/ui/app/shell.py`.

Delete the entire method `_handle_tab_close_requested` (around lines 602-613).

Delete the entire method `_handle_tab_repayload_requested` (around lines 615-631).

In `_on_context_changed` (around lines 587-594), delete the two dispatch lines:

```python
def _on_context_changed(self, event: ContextChangedEvent) -> None:
    """Orchestrator callback: run the poll/draw cycle on every managed slot."""
    if event.change_type == ContextChangeType.TAB_CLOSE_REQUESTED:        # ← DELETE
        self._handle_tab_close_requested(event)                            # ← DELETE
    elif event.change_type == ContextChangeType.TAB_REPAYLOAD_REQUESTED:  # ← DELETE
        self._handle_tab_repayload_requested(event)                        # ← DELETE
    elif event.change_type == ContextChangeType.GRAPH_REMOVED:
        self._handle_graph_removed(event)

    if event.reveal_editor is not None:
        ...
```

After deletion the block becomes:

```python
def _on_context_changed(self, event: ContextChangedEvent) -> None:
    """Orchestrator callback: run the poll/draw cycle on every managed slot."""
    if event.change_type == ContextChangeType.GRAPH_REMOVED:
        self._handle_graph_removed(event)

    if event.reveal_editor is not None:
        self._reveal_editor(event.reveal_editor, event.reveal_payload, event.reveal_label)

    for slot in self._managed_slots.values():
        slot.handle_context_event(event)
```

- [ ] **Step 9.4: Delete the obsolete shell-handler tests**

Edit `tests/ui/test_app_shell.py`. Find the section with the comment around line 237:

```python
# TAB_CLOSE_REQUESTED / TAB_REPAYLOAD_REQUESTED / GRAPH_REMOVED dispatch
```

Delete every test in that section that exercises `TAB_CLOSE_REQUESTED` or `TAB_REPAYLOAD_REQUESTED` (look for them around lines 283-310). Keep tests for `GRAPH_REMOVED` — that handler still exists.

To find them precisely:

```bash
grep -n "TAB_CLOSE_REQUESTED\|TAB_REPAYLOAD_REQUESTED" tests/ui/test_app_shell.py
```

Delete the test functions that contain those references. If a single test exercises multiple change_types, only delete the assertions / event-creation calls that reference the deleted enum values; keep the GRAPH_REMOVED parts.

- [ ] **Step 9.5: Run the test suite — confirm everything still passes**

Run: `uv run pytest -m "not integration" 2>&1 | tail -3`
Expected: PASS. Test count drops by however many tests we deleted.

Run integration: `uv run pytest -m integration 2>&1 | tail -3`
Expected: 68 passed.

- [ ] **Step 9.6: Final straggler check**

Run:
```bash
grep -rn "TAB_CLOSE_REQUESTED\|TAB_REPAYLOAD_REQUESTED\|_handle_tab_close_requested\|_handle_tab_repayload_requested" packages/ barn/ tests/ --include="*.py" 2>/dev/null
```
Expected: ZERO matches. If there are any, fix them.

- [ ] **Step 9.7: Lint + format**

Run: `uv run ruff check packages/haywire-core/src/haywire/ui/context_events.py packages/haywire-core/src/haywire/ui/app/shell.py tests/ui/test_app_shell.py && uv run ruff format --check packages/haywire-core/src/haywire/ui/context_events.py packages/haywire-core/src/haywire/ui/app/shell.py tests/ui/test_app_shell.py`
Expected: clean.

- [ ] **Step 9.8: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/context_events.py packages/haywire-core/src/haywire/ui/app/shell.py tests/ui/test_app_shell.py
git commit -m "$(cat <<'EOF'
refactor(events): delete TAB_CLOSE_REQUESTED + TAB_REPAYLOAD_REQUESTED

Both events existed solely to bridge editor->shell->slot, because
the editor had no direct path to its slot. The EditorWrapper refactor
gave wrappers a _slot back-reference; the X-button path and editor
self-close paths now call wrapper.close() / wrapper.force_close() /
wrapper.repayload() directly.

With no producers and no remaining consumers, the enum values, the
shell's relay handlers, and their dispatch lines in _on_context_changed
are dead code. Tests covering the relay behavior are also gone.

Shell stays a routing switchboard, but only for genuinely cross-slot
concerns (GRAPH_REMOVED fans out across slots; reveal_editor finds
the target slot from editor identity). Lifecycle stays at the
slot/wrapper layer.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 10: Add the dirty badge to the tab bar

**Why:** Visible UI feedback for the dirty flag. Trivial — prefix the label with `"• "` when `wrapper.state.is_dirty`.

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/app/tab_slot.py`
- Modify: `tests/ui/test_slot_tab.py`

- [ ] **Step 10.1: Write failing test**

Append to `tests/ui/test_slot_tab.py`:

```python
def test_dirty_wrapper_label_has_bullet_prefix(monkeypatch):
    """When state.is_dirty is True, the bar's tab label is prefixed
    with '• ' so the user sees there's unsaved work."""
    captured_labels: list = []

    class _LabelCapture:
        def __init__(self, text):
            captured_labels.append(text)

    # Stub ui.label to record what text was rendered
    import haywire.ui.app.tab_slot as tab_slot_mod
    monkeypatch.setattr(tab_slot_mod.ui, "label", _LabelCapture)
    # Stub other ui.* calls used in _render_bar_contents minimally
    # (or use the existing test harness fixtures if available)
    # ... existing setup pattern from this file ...

    reg = _FakeRegistry()
    sess = _session_with_context()
    slot = TabSlot(session=sess, name="main", registry=reg)
    slot.add_binding(editor_key="fake:editor:1", editor_cls=_FakeEditor)
    target = slot.find_binding("fake:editor:1")
    slot._active = target
    target.set_dirty(True)

    # Render the bar (the existing test harness should expose a way to
    # invoke _render_bar_contents — check this file for the pattern)
    slot._render_bar_contents()

    # The label rendered for this tab should be prefixed with "• "
    matching = [t for t in captured_labels if t.endswith("fake:editor:1") or "fake:editor:1" in t]
    assert any(t.startswith("• ") for t in captured_labels), (
        f"No dirty-prefixed label found in {captured_labels}"
    )
```

If the test harness uses different stubbing for `ui.label` / `ui.tab` / `ui.button`, adapt the test to match how other `_render_bar_contents`-related tests in this file work. The intent is: render the bar with a dirty wrapper, assert the rendered label starts with `"• "`.

- [ ] **Step 10.2: Run test — verify it fails**

Run: `uv run pytest tests/ui/test_slot_tab.py -v -k "dirty_wrapper_label"`
Expected: FAIL.

- [ ] **Step 10.3: Add the dirty prefix in `_render_bar_contents`**

Edit `packages/haywire-core/src/haywire/ui/app/tab_slot.py`. Find the label-resolution block in `_render_bar_contents` (around line 76-80):

```python
                    with tab_el:
                        with ui.row().classes("items-center gap-1 no-wrap"):
                            label = wrapper.label or getattr(
                                wrapper.editor_cls.class_identity, "label", wrapper.editor_key
                            )
                            ui.label(label)
```

Update to:

```python
                    with tab_el:
                        with ui.row().classes("items-center gap-1 no-wrap"):
                            label = wrapper.label or getattr(
                                wrapper.editor_cls.class_identity, "label", wrapper.editor_key
                            )
                            if wrapper.state is not None and wrapper.state.is_dirty:
                                label = f"• {label}"
                            ui.label(label)
```

(`wrapper.state is not None` guard handles the post-cleanup edge case — defensive, since `cleanup()` sets `_state = None`.)

- [ ] **Step 10.4: Run test — verify it passes**

Run: `uv run pytest tests/ui/test_slot_tab.py -v -k "dirty_wrapper_label"`
Expected: PASS.

- [ ] **Step 10.5: Run full suite + lint**

Run: `uv run pytest -m "not integration" 2>&1 | tail -3 && uv run pytest -m integration 2>&1 | tail -3 && uv run ruff check packages/haywire-core/src/haywire/ui/app/tab_slot.py tests/ui/test_slot_tab.py && uv run ruff format --check packages/haywire-core/src/haywire/ui/app/tab_slot.py tests/ui/test_slot_tab.py`
Expected: PASS, clean.

- [ ] **Step 10.6: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/app/tab_slot.py tests/ui/test_slot_tab.py
git commit -m "$(cat <<'EOF'
feat(tab-slot): show '•' prefix in tab label when state.is_dirty

When the wrapper's state.is_dirty flag is True, the tab label is
rendered as '• {label}' so the user can see there's unsaved work
without clicking the tab.

Minimal styling for now — a leading bullet character. Polish (separate
DOM element, custom CSS, animation) is a follow-up.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 11: Final verification

**Why:** Catch regressions, confirm the squashed feature works end-to-end, smoke-test in the running app.

- [ ] **Step 11.1: Run the full quality gate**

Run:
```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest -m "not integration"
uv run pytest -m integration
```

Expected:
- `ruff check`: All checks passed!
- `ruff format --check`: clean
- Unit suite: PASS, count slightly different from baseline (additions in test_editor_wrapper.py and test_slot_tab.py; deletions in test_app_shell.py)
- Integration suite: 68 passed

- [ ] **Step 11.2: Sanity grep for residue**

Run:
```bash
grep -rn "TAB_CLOSE_REQUESTED\|TAB_REPAYLOAD_REQUESTED" packages/ barn/ tests/ --include="*.py" 2>/dev/null
grep -rn "_handle_tab_close_requested\|_handle_tab_repayload_requested" packages/ barn/ tests/ --include="*.py" 2>/dev/null
```
Expected: ZERO matches.

- [ ] **Step 11.3: Smoke test in the running app**

Run: `uv run haywire`

In the browser:
1. Open a graph editor tab. Verify it opens.
2. Edit something in the graph (move a node, etc.).
3. Save the graph (this exercises the repayload path on save-as if it's an unsaved file).
4. Click the X on the graph tab. Verify it closes (no warning yet — graph_editor doesn't override `handle_close_request`, so consent defaults to True).
5. Open multiple graph tabs and close them in different orders. Verify sibling promotion works.

Stop the server with Ctrl-C.

- [ ] **Step 11.4: Note any deferred work**

Document for future tasks (no code change here — just awareness):

- GraphEditor doesn't yet implement `handle_close_request` to track dirty state. When implemented, clicking X on a dirty graph tab will show the editor's confirmation dialog.
- Other editors (file viewer, settings panels) don't yet use `set_dirty` — they don't currently have meaningful dirty state.
- The `"• "` prefix is minimal styling. A separate task could move it to a styled DOM element with proper CSS.

These are intentional follow-ups — the framework is in place, individual editors opt in over time.

- [ ] **Step 11.5: No commit needed for verification**

If the smoke test surfaced anything broken, fix and commit per the relevant earlier task. If everything works, proceed.

---

## Self-Review

**1. Spec coverage check** (against the Q1-Q8 decisions from the inquisition):

- Q1 (1B-iii: `set_dirty` method, no callback) → Task 1 ✓
- Q2 (Option 4: `close()` async + `force_close()` sync) → Task 4 ✓
- Q3 (A: framework provides machinery, no default dialog) → Task 3 + Task 10 ✓ (no helper added; just the gate + badge)
- Q4 (A: `"• "` prefix) → Task 10 ✓
- Q5 (B only: clear `is_dirty` on hot-reload) → Task 6 ✓
- Q6 (C: unit + integration tests) → Tasks 1-10 throughout ✓
- Q7 (A: leave GraphEditor with default `handle_close_request`) → Task 8 only migrates emit-paths, no dirty tracking ✓
- Q8 (full scope confirmed) → All 11 tasks combined ✓

**2. Placeholder scan:** No "TBD", "TODO", or "implement later" in any task. Each step has actual code or commands. The Step 11.4 note is explicit about scope, not placeholder work.

**3. Type / method-signature consistency:**
- `set_dirty(value: bool) -> None` — Task 1, 7, 10 (used consistently)
- `request_close() -> async bool` — Task 4 (single definition, referenced in close)
- `close() -> async bool` — Task 4 (used by Task 7 X-button)
- `force_close() -> None` — Task 4 (used by Task 8 graph_editor self-close)
- `repayload(new_payload, new_label=None) -> None` — Task 5 (used by Task 8 graph_editor save-as)
- `handle_close_request() -> async bool` — Task 3 (called by Task 4 request_close)
- `_slot: Optional[Slot]` — Task 2 (read by Task 4 force_close, Task 5 repayload)
- `_state.is_dirty: bool` — Task 1 (mutated by set_dirty, read by Task 6 lifecycle, Task 10 bar)

All consistent.

**4. Spec-requirement gap check:**
- Wrapper-direct close: ✓ (Tasks 2, 4, 7)
- Wrapper-direct repayload: ✓ (Tasks 2, 5, 8)
- Consent gate: ✓ (Tasks 3, 4, 7)
- Dirty flag + badge: ✓ (Tasks 1, 6, 10)
- Event cleanup: ✓ (Task 9)
- Hot-reload clears dirty: ✓ (Task 6)
- BaseEditor default `handle_close_request`: ✓ (Task 3)

No gaps.

---

Plan complete and saved to `docs/superpowers/plans/2026-04-25-close-consent-and-event-cleanup.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
