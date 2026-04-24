# WorkspaceManager Simplification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Strip `WorkspaceManager` down to a dumb file I/O object, move all slot topology and reconciliation knowledge into the slots themselves, make the save action always coordinate haystack + workspace together, and make the startup restore path use the same `open_tab` machinery as the runtime path.

**Architecture:** `WorkspaceManager` holds a raw `snapshot: dict` and only reads/writes JSON. Each `Slot` gains `to_snapshot() -> dict` and `from_snapshot(data, registry, ...)` on the base class — uniform for all slot types. `REQUIRED` editors are never serialized; they are always injected from the registry at construction. `HaywireApp` moves `WorkspaceManager` to app-level (shared, like `Haystack`) and adds `save_workspace()` as the single coordinated save entry point.

**Tech Stack:** Python, NiceGUI, pytest, `haywire-core` + `haywire-studio` packages

---

> **IMPORTANT FOLLOW-UP QUESTION (not in scope here):** `save_workspace()` needs to call `shell.collect_snapshot()` to get current slot state, but `HaywireApp` does not hold a shell reference (shell is per-session). Decide: does `save_workspace(shell)` take the shell as an arg, or does the session hold the shell and `save_workspace` gets it via `session_manager`?

---

## File Map

| File | Change |
|---|---|
| `packages/haywire-core/src/haywire/ui/workspace/manager.py` | Rewrite — dumb I/O only |
| `packages/haywire-core/src/haywire/ui/workspace/workspace_state.py` | Delete entirely |
| `packages/haywire-core/src/haywire/ui/workspace/__init__.py` | Rewrite — export only `WorkspaceManager` |
| `packages/haywire-core/src/haywire/ui/app/slot.py` | Add `to_snapshot()`, `from_snapshot()`, remove `slot_state` wiring |
| `packages/haywire-core/src/haywire/ui/app/tab_slot.py` | Remove `slot_state.tabs` writes, remove `TabState` import |
| `packages/haywire-core/src/haywire/ui/app/shell.py` | Replace `_build_managed_slot`, add `collect_snapshot()`, update `render()` |
| `packages/haywire-studio/src/haywire_studio/app.py` | Move `WorkspaceManager` to `__init__`, add `save_workspace()`, delete `restore_persisted_tabs` |
| `tests/ui/test_workspace_state.py` | Rewrite — new `WorkspaceManager` contract |
| `tests/ui/test_slot.py` | Add `to_snapshot` / `from_snapshot` tests |
| `tests/ui/test_app_shell.py` | Update fake session snapshot format |

---

## Task 1: Rewrite `WorkspaceManager` as dumb I/O

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/workspace/manager.py`
- Modify: `packages/haywire-core/src/haywire/ui/workspace/__init__.py`
- Delete: `packages/haywire-core/src/haywire/ui/workspace/workspace_state.py`
- Modify: `tests/ui/test_workspace_state.py`

- [ ] **Step 1: Write the failing tests**

Replace the entire contents of `tests/ui/test_workspace_state.py` with:

```python
# tests/ui/test_workspace_state.py
"""Tests for the simplified WorkspaceManager (dumb file I/O)."""

import json
from haywire.ui.workspace.manager import WorkspaceManager


class TestWorkspaceManagerLoad:
    def test_load_returns_empty_dict_when_no_file(self, tmp_path):
        wm = WorkspaceManager(project_path=tmp_path)
        assert wm.snapshot == {}

    def test_load_reads_json_file(self, tmp_path):
        state_file = tmp_path / ".haywire" / "workspace_state.json"
        state_file.parent.mkdir()
        state_file.write_text(json.dumps({"haystack": "default", "left": {"active_key": "ed:a"}}))
        wm = WorkspaceManager(project_path=tmp_path)
        assert wm.snapshot["haystack"] == "default"
        assert wm.snapshot["left"]["active_key"] == "ed:a"

    def test_corrupt_file_falls_back_to_empty(self, tmp_path):
        state_file = tmp_path / ".haywire" / "workspace_state.json"
        state_file.parent.mkdir()
        state_file.write_text("{ not valid json")
        wm = WorkspaceManager(project_path=tmp_path)
        assert wm.snapshot == {}


class TestWorkspaceManagerSave:
    def test_save_writes_json_file(self, tmp_path):
        wm = WorkspaceManager(project_path=tmp_path)
        snapshot = {"haystack": "default", "left": {"active_key": "ed:a", "visible": True, "size": 250, "editors": []}}
        wm.save(snapshot)
        state_file = tmp_path / ".haywire" / "workspace_state.json"
        assert state_file.exists()
        data = json.loads(state_file.read_text())
        assert data["haystack"] == "default"
        assert data["left"]["active_key"] == "ed:a"

    def test_save_creates_haywire_dir(self, tmp_path):
        wm = WorkspaceManager(project_path=tmp_path)
        assert not (tmp_path / ".haywire").exists()
        wm.save({"haystack": "x"})
        assert (tmp_path / ".haywire").exists()

    def test_save_updates_snapshot(self, tmp_path):
        wm = WorkspaceManager(project_path=tmp_path)
        wm.save({"haystack": "my_stack"})
        assert wm.snapshot["haystack"] == "my_stack"

    def test_roundtrip(self, tmp_path):
        wm1 = WorkspaceManager(project_path=tmp_path)
        payload = {
            "haystack": "proj",
            "left": {"active_key": "ed:browser", "visible": False, "size": 200, "editors": []},
            "main": {"active_key": "ed:graph::/tmp/a.haywire", "editors": [{"key": "ed:graph", "payload": "/tmp/a.haywire", "label": "a.haywire"}]},
            "bottom": {"active_key": "ed:console", "visible": True, "size": 300, "editors": []},
            "right": {"active_key": "ed:props", "visible": True, "size": 350, "editors": []},
        }
        wm1.save(payload)
        wm2 = WorkspaceManager(project_path=tmp_path)
        assert wm2.snapshot == payload
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo
uv run pytest tests/ui/test_workspace_state.py -v 2>&1 | head -40
```

Expected: FAIL — `WorkspaceManager` still has old signature.

- [ ] **Step 3: Rewrite `WorkspaceManager`**

Replace the entire contents of `packages/haywire-core/src/haywire/ui/workspace/manager.py` with:

```python
# packages/haywire-core/src/haywire/ui/workspace/manager.py
"""
WorkspaceManager — dumb JSON persistence for the workspace snapshot.

Holds a raw ``snapshot`` dict. Knows nothing about slots, editors, or
OpenBehavior. Slots are responsible for interpreting and producing snapshots.
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_STATE_FILENAME = "workspace_state.json"


class WorkspaceManager:
    """
    Loads and saves the workspace snapshot dict to/from disk.

    The snapshot is a plain dict with one key per slot name plus a
    ``"haystack"`` key. The structure of each slot sub-dict is defined and
    interpreted by the slot classes — WorkspaceManager is intentionally
    unaware of it.

    Attributes:
        snapshot: The raw dict loaded from disk, or ``{}`` if no file exists
            or the file failed to parse. Updated by ``save()``.
    """

    def __init__(self, project_path: Path):
        self._project_path = project_path
        self.snapshot: dict = self._load()

    def _load(self) -> dict:
        """Read the snapshot from disk. Returns ``{}`` on missing or corrupt file."""
        state_file = self._project_path / ".haywire" / _STATE_FILENAME
        if not state_file.exists():
            return {}
        try:
            return json.loads(state_file.read_text())
        except Exception as e:
            logger.warning(
                f"WorkspaceManager: failed to load {state_file}: {e}. Starting fresh."
            )
            return {}

    def save(self, snapshot: dict) -> None:
        """Persist ``snapshot`` to disk and update ``self.snapshot``."""
        preset_dir = self._project_path / ".haywire"
        preset_dir.mkdir(parents=True, exist_ok=True)
        state_file = preset_dir / _STATE_FILENAME
        state_file.write_text(json.dumps(snapshot, indent=2))
        self.snapshot = snapshot
        logger.info(f"WorkspaceManager: saved snapshot to {state_file}")
```

- [ ] **Step 4: Update `workspace/__init__.py`**

Replace the entire contents of `packages/haywire-core/src/haywire/ui/workspace/__init__.py` with:

```python
# packages/haywire-core/src/haywire/ui/workspace/__init__.py
"""
Workspace persistence for the Haywire UI layout.

WorkspaceManager handles loading and saving the raw workspace snapshot dict.
Slot classes (IconSlot, TabSlot) own the interpretation of snapshot contents.
"""

from .manager import WorkspaceManager

__all__ = ["WorkspaceManager"]
```

- [ ] **Step 5: Delete `workspace_state.py`**

```bash
rm packages/haywire-core/src/haywire/ui/workspace/workspace_state.py
```

- [ ] **Step 6: Run new tests**

```bash
uv run pytest tests/ui/test_workspace_state.py -v
```

Expected: all PASS.

- [ ] **Step 7: Run full suite to find breakage**

```bash
uv run pytest --tb=no -q 2>&1 | tail -20
```

Note the failing tests — they will be fixed in subsequent tasks.

- [ ] **Step 8: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/workspace/ tests/ui/test_workspace_state.py
git commit -m "refactor: WorkspaceManager is now dumb I/O — holds raw snapshot dict only"
```

---

## Task 2: Add `to_snapshot()` and `from_snapshot()` to `Slot`, remove `slot_state` wiring

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/app/slot.py`
- Modify: `tests/ui/test_slot.py`

The `slot_state` parameter and all writes to it (`_mirror_active_into_state`, `set_visible`, `set_size`) are removed. Instead the slot tracks `_visible`, `_size`, and `_active` as plain Python state (it already does), and exposes them via `to_snapshot()`. `from_snapshot()` is a classmethod that builds constructor kwargs from a raw dict — the shell calls it before constructing a slot.

- [ ] **Step 1: Write the failing tests**

Add this block to the bottom of `tests/ui/test_slot.py`:

```python
# ---------------------------------------------------------------------------
# Slot.to_snapshot / from_snapshot
# ---------------------------------------------------------------------------

class _FakeEditorCls:
    def __init__(self, key, opens=None):
        from haywire.ui.editor.identity import OpenBehavior
        self.class_identity = SimpleNamespace(
            registry_key=key,
            label=key,
            icon="icon",
            opens=opens or OpenBehavior.REQUIRED,
            default_slot="main",
        )

class _FakeRegistry:
    def __init__(self, classes):
        self._classes = classes

    def get_by_key(self, key):
        return self._classes.get(key)

    def get_by_default_slot(self, slot):
        return {k: v for k, v in self._classes.items() if v.class_identity.default_slot == slot}

    def add_batch_event_subscriber(self, _cb):
        pass

    def remove_batch_event_subscriber(self, _cb):
        pass


def _make_tab_slot(bindings, active_key=None, visible=True, size=200):
    """Build a TabSlot without rendering (no NiceGUI context needed)."""
    from haywire.ui.app.tab_slot import TabSlot
    return TabSlot(
        session=SimpleNamespace(context=None, notify_context_changed=lambda _e: None),
        name="main",
        registry=_FakeRegistry({}),
        initial_bindings=bindings,
        active_key=active_key,
        slot_state=None,
        bar_place="top",
        show_fold_toggle=False,
        visible=visible,
        size=size,
    )


class TestSlotToSnapshot:
    def test_to_snapshot_active_key(self):
        from haywire.ui.editor.identity import OpenBehavior
        from haywire.ui.app.slot import EditorBinding
        cls = _FakeEditorCls("ed:graph", OpenBehavior.ON_PAYLOAD)
        binding = EditorBinding(editor_key="ed:graph", editor_cls=cls, payload="/a.haywire")
        slot = _make_tab_slot([binding], active_key="ed:graph::/a.haywire")
        snap = slot.to_snapshot()
        assert snap["active_key"] == "ed:graph::/a.haywire"

    def test_to_snapshot_excludes_required_editors(self):
        from haywire.ui.editor.identity import OpenBehavior
        from haywire.ui.app.slot import EditorBinding
        req_cls = _FakeEditorCls("ed:required", OpenBehavior.REQUIRED)
        pay_cls = _FakeEditorCls("ed:graph", OpenBehavior.ON_PAYLOAD)
        bindings = [
            EditorBinding(editor_key="ed:required", editor_cls=req_cls, payload=None),
            EditorBinding(editor_key="ed:graph", editor_cls=pay_cls, payload="/a.haywire"),
        ]
        slot = _make_tab_slot(bindings, active_key="ed:graph::/a.haywire")
        snap = slot.to_snapshot()
        keys = [e["key"] for e in snap["editors"]]
        assert "ed:required" not in keys
        assert "ed:graph" in keys

    def test_to_snapshot_includes_payload_and_label(self):
        from haywire.ui.editor.identity import OpenBehavior
        from haywire.ui.app.slot import EditorBinding
        cls = _FakeEditorCls("ed:graph", OpenBehavior.ON_PAYLOAD)
        binding = EditorBinding(editor_key="ed:graph", editor_cls=cls, payload="/a.haywire")
        binding.label = "a.haywire"
        slot = _make_tab_slot([binding], active_key="ed:graph::/a.haywire")
        snap = slot.to_snapshot()
        ed = snap["editors"][0]
        assert ed["key"] == "ed:graph"
        assert ed["payload"] == "/a.haywire"

    def test_to_snapshot_visible_and_size(self):
        slot = _make_tab_slot([], visible=False, size=350)
        snap = slot.to_snapshot()
        assert snap["visible"] is False
        assert snap["size"] == 350


class TestSlotFromSnapshot:
    def test_from_snapshot_builds_required_bindings_from_registry(self):
        from haywire.ui.editor.identity import OpenBehavior
        from haywire.ui.app.tab_slot import TabSlot
        cls = _FakeEditorCls("ed:required", OpenBehavior.REQUIRED)
        cls.class_identity.default_slot = "main"
        registry = _FakeRegistry({"ed:required": cls})
        session = SimpleNamespace(context=None, notify_context_changed=lambda _e: None)
        slot = TabSlot.from_snapshot(
            data={},
            registry=registry,
            session=session,
            name="main",
            bar_place="top",
            show_fold_toggle=False,
        )
        keys = [b.editor_key for b in slot.bindings]
        assert "ed:required" in keys

    def test_from_snapshot_restores_on_payload_editors(self):
        from haywire.ui.editor.identity import OpenBehavior
        from haywire.ui.app.tab_slot import TabSlot
        cls = _FakeEditorCls("ed:graph", OpenBehavior.ON_PAYLOAD)
        cls.class_identity.default_slot = "main"
        registry = _FakeRegistry({"ed:graph": cls})
        session = SimpleNamespace(context=None, notify_context_changed=lambda _e: None)
        data = {
            "active_key": "ed:graph::/a.haywire",
            "editors": [{"key": "ed:graph", "payload": "/a.haywire", "label": "a.haywire"}],
        }
        slot = TabSlot.from_snapshot(
            data=data,
            registry=registry,
            session=session,
            name="main",
            bar_place="top",
            show_fold_toggle=False,
        )
        keys = [b.editor_key for b in slot.bindings]
        assert "ed:graph" in keys

    def test_from_snapshot_skips_unknown_editor_key(self):
        from haywire.ui.app.tab_slot import TabSlot
        registry = _FakeRegistry({})
        session = SimpleNamespace(context=None, notify_context_changed=lambda _e: None)
        data = {
            "editors": [{"key": "ed:gone", "payload": "/x.haywire", "label": "x"}],
        }
        slot = TabSlot.from_snapshot(
            data=data,
            registry=registry,
            session=session,
            name="main",
            bar_place="top",
            show_fold_toggle=False,
        )
        assert slot.bindings == []

    def test_from_snapshot_restores_visible_and_size(self):
        from haywire.ui.app.tab_slot import TabSlot
        registry = _FakeRegistry({})
        session = SimpleNamespace(context=None, notify_context_changed=lambda _e: None)
        slot = TabSlot.from_snapshot(
            data={"visible": False, "size": 275},
            registry=registry,
            session=session,
            name="bottom",
            bar_place="top",
            show_fold_toggle=True,
        )
        assert slot.visible is False
        assert slot._size == 275
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/ui/test_slot.py -v -k "snapshot" 2>&1 | tail -20
```

Expected: FAIL — `to_snapshot`, `from_snapshot`, `visible` param, `size` param not yet implemented.

- [ ] **Step 3: Add `_size` and `visible` constructor params, remove `slot_state`**

In `packages/haywire-core/src/haywire/ui/app/slot.py`:

Replace the `__init__` signature (around line 147):

```python
def __init__(
    self,
    session: "Session",
    name: str,
    registry: EditorTypeRegistry,
    initial_bindings: list[EditorBinding],
    active_key: Optional[str] = None,
    on_visibility_change: Optional[Callable[[bool], None]] = None,
    bar_place: Literal["left", "right", "top", "bottom"] = "left",
    show_fold_toggle: bool = False,
    visible: bool = True,
    size: int = 300,
):
```

Remove the `slot_state` parameter entirely. Replace the body assignments that reference it:

```python
    self._session = session
    self.name = name
    self._registry: EditorTypeRegistry = registry
    self._bindings: list[EditorBinding] = list(initial_bindings)
    self._active: Optional[EditorBinding] = self._resolve_initial_active(active_key)
    self._visible: bool = visible
    self._size: int = size
    self._area_panel_container: Optional[ui.element] = None
    self._area_parent_box: Optional[ui.element] = None
    self._panels: dict[str, ui.element] = {}
    self._drawn: set[str] = set()
    self._on_visibility_change = on_visibility_change
    self._bar_place = bar_place
    self._show_fold_toggle = show_fold_toggle
    self._bar_container: Optional[ui.element] = None
    self._fold_button: Optional[ui.element] = None
    self._registry.add_batch_event_subscriber(self._on_editor_lifecycle)
```

Remove `_mirror_active_into_state` method entirely (it wrote to `slot_state`).

Replace `set_visible` to remove the `slot_state` write:

```python
def set_visible(self, visible: bool) -> None:
    if visible == self._visible:
        return
    self._visible = visible
    if self._area_parent_box is not None:
        self._area_parent_box.set_visibility(visible)
    if self._area_panel_container is not None:
        self._area_panel_container.set_visibility(visible)
    if self._on_visibility_change is not None:
        self._on_visibility_change(visible)
    self._refresh_bar()
```

Replace `set_size` to store in `self._size`:

```python
def set_size(self, size_px: int) -> None:
    self._size = int(size_px)
```

Replace `_activate` — remove the `_mirror_active_into_state()` call at the end:

```python
def _activate(self, binding: EditorBinding) -> None:
    self._active = binding
    instance = binding.ensure_instance()
    try:
        instance.on_focus(self._session.context)
    except Exception as exc:
        logger.error(f"Slot '{self.name}': on_focus error for '{binding.binding_id}': {exc}")
    self._ensure_drawn(binding)
    if self._area_panel_container is not None:
        self._area_panel_container.set_value(binding.binding_id)
```

Replace `_create_content_box` to read `self._size` instead of `slot_state`:

```python
def _create_content_box(self) -> "ui.element":
    if self._is_horizontal:
        border = f"border-{self._bar_place}: 1px solid var(--hw-border);"
        col = (
            ui.column()
            .classes("gap-0")
            .style(
                f"width: {self._size}px; min-width: 150px; height: 100%; "
                f"overflow: hidden; background: var(--hw-bg-page); {border}"
            )
        )
    elif self._show_fold_toggle:
        col = (
            ui.column()
            .classes("gap-0")
            .style(f"height: {self._size}px; min-height: 0; width: 100%; overflow: hidden;")
        )
    else:
        col = ui.column().classes("gap-0 w-full").style("flex: 1; min-height: 0; overflow: hidden;")
    col._props["id"] = f"hw-slot-{self.name}"
    return col
```

- [ ] **Step 4: Add `to_snapshot()` to `Slot`**

Add this method to the `Slot` class after `set_size`:

```python
def to_snapshot(self) -> dict:
    """Serialize current slot state to a plain dict for persistence.

    REQUIRED editors are excluded — they are always re-injected from the
    registry at construction and don't need persisting.
    """
    from haywire.ui.editor.identity import OpenBehavior

    editors = []
    for binding in self._bindings:
        opens = getattr(binding.editor_cls.class_identity, "opens", OpenBehavior.REQUIRED)
        if opens is OpenBehavior.REQUIRED:
            continue
        entry: dict = {"key": binding.editor_key}
        if binding.payload is not None:
            entry["payload"] = binding.payload
        label = getattr(binding, "label", None) or getattr(
            binding.editor_cls.class_identity, "label", binding.editor_key
        )
        entry["label"] = label
        editors.append(entry)

    snap: dict = {
        "active_key": self.active_binding_id,
        "visible": self._visible,
        "size": self._size,
        "editors": editors,
    }
    return snap
```

- [ ] **Step 5: Add `from_snapshot()` to `Slot`**

Add this classmethod to the `Slot` class:

```python
@classmethod
def from_snapshot(
    cls,
    data: dict,
    registry: "EditorTypeRegistry",
    session: "Session",
    name: str,
    bar_place: Literal["left", "right", "top", "bottom"] = "left",
    show_fold_toggle: bool = False,
    on_visibility_change: Optional[Callable[[bool], None]] = None,
) -> "Slot":
    """Construct a slot from a raw snapshot dict.

    Injects all REQUIRED editors for this slot unconditionally from the
    registry. Then appends snapshot editors (ON_PAYLOAD / ON_CONTEXT) in
    order. Unknown editor keys are silently skipped.

    Args:
        data: Slot sub-dict from the workspace snapshot, or ``{}`` for defaults.
        registry: The editor type registry.
        session: The owning session.
        name: Slot name (``"left"``, ``"right"``, ``"main"``, ``"bottom"``).
        bar_place: Bar position for rendering.
        show_fold_toggle: Whether to render the fold chevron.
        on_visibility_change: Optional visibility callback.
    """
    from haywire.ui.editor.identity import OpenBehavior

    bindings: list[EditorBinding] = []

    # Always inject REQUIRED editors for this slot from the registry.
    for key, editor_cls in registry.get_by_default_slot(name).items():
        opens = getattr(editor_cls.class_identity, "opens", OpenBehavior.REQUIRED)
        if opens is OpenBehavior.REQUIRED:
            bindings.append(EditorBinding(editor_key=key, editor_cls=editor_cls, payload=None))

    # Restore non-REQUIRED editors from snapshot.
    for entry in data.get("editors", []):
        key = entry.get("key")
        if not key:
            continue
        editor_cls = registry.get_by_key(key)
        if editor_cls is None:
            logger.warning(f"Slot '{name}': snapshot editor '{key}' not in registry — skipping")
            continue
        payload = entry.get("payload")
        binding = EditorBinding(editor_key=key, editor_cls=editor_cls, payload=payload)
        binding.label = entry.get("label", key)
        bindings.append(binding)

    active_key = data.get("active_key")
    visible = data.get("visible", True)
    size = data.get("size", 300)

    return cls(
        session=session,
        name=name,
        registry=registry,
        initial_bindings=bindings,
        active_key=active_key,
        on_visibility_change=on_visibility_change,
        bar_place=bar_place,
        show_fold_toggle=show_fold_toggle,
        visible=visible,
        size=size,
    )
```

Also add `"label"` as a field on `EditorBinding`:

```python
@dataclass
class EditorBinding:
    editor_key: str
    editor_cls: type["BaseEditor"]
    payload: Any = None
    instance: Optional["BaseEditor"] = None
    label: str = ""
```

- [ ] **Step 6: Run snapshot tests**

```bash
uv run pytest tests/ui/test_slot.py -v -k "snapshot" 2>&1 | tail -30
```

Expected: all PASS.

- [ ] **Step 7: Run full slot test suite**

```bash
uv run pytest tests/ui/test_slot.py tests/ui/test_slot_tab.py tests/ui/test_slot_icon.py tests/ui/test_slot_on_focus.py -v 2>&1 | tail -30
```

Fix any failures caused by the removed `slot_state` parameter before proceeding.

- [ ] **Step 8: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/app/slot.py tests/ui/test_slot.py
git commit -m "feat: Slot gains to_snapshot/from_snapshot; slot_state wiring removed"
```

---

## Task 3: Remove `slot_state` writes from `TabSlot`

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/app/tab_slot.py`
- Modify: `tests/ui/test_slot_tab.py`

`TabSlot` currently writes `TabState` objects into `slot_state.tabs` in `open_tab`, `close_tab`, and `repayload_tab`. These writes tracked the tab list in the `WorkspaceState` mirror. With `slot_state` gone, `TabSlot` is the sole owner of its binding list — no mirroring needed.

- [ ] **Step 1: Remove `TabState` import and `slot_state.tabs` writes from `tab_slot.py`**

In `packages/haywire-core/src/haywire/ui/app/tab_slot.py`:

Remove the import:
```python
from haywire.ui.workspace.workspace_state import TabState
```

Replace `open_tab`:
```python
def open_tab(
    self,
    editor_cls: type,
    editor_key: str,
    payload: Optional[str],
    label: str,
) -> bool:
    """Ensure a tab for ``(editor_key, payload)`` exists and make it active.

    Returns ``True`` iff the active tab actually changed.
    """
    existing = self.find_binding(editor_key, payload)
    if existing is not None:
        if self._active is existing:
            return False
        self.switch_to(editor_key, payload)
        self._refresh_bar()
        return True

    binding = EditorBinding(editor_key=editor_key, editor_cls=editor_cls, payload=payload)
    binding.label = label
    self.add_binding(binding, activate=True)
    self._refresh_bar()
    return True
```

Replace `close_tab`:
```python
def close_tab(self, editor_key: str, payload: Optional[str]) -> bool:
    """Close one tab — removes binding; promotes sibling when active."""

    def _cleanup(instance) -> None:
        try:
            instance.cleanup()
        except Exception as exc:
            logger.warning(f"TabSlot '{self.name}': cleanup error: {exc}")

    removed = self.remove_binding(editor_key, payload, cleanup=_cleanup)
    if removed is None:
        return False
    self._refresh_bar()
    return True
```

Replace `repayload_tab`:
```python
def repayload_tab(
    self,
    editor_key: str,
    old_payload: Optional[str],
    new_payload: Optional[str],
    new_label: Optional[str] = None,
) -> bool:
    """Re-key a tab in place (e.g. Save-As). Preserves the editor instance."""
    target = self.find_binding(editor_key, old_payload)
    if not self.repayload_binding(editor_key, old_payload, new_payload):
        return False
    if new_label is not None and target is not None:
        target.label = new_label
    self._refresh_bar()
    return True
```

- [ ] **Step 2: Fix `_render_bar_contents` in `tab_slot.py`**

`_render_bar_contents` currently reads `self._slot_state.tabs` to build the tab bar. Replace with reading `self._bindings` directly:

```python
def _render_bar_contents(self) -> None:
    """Render tab row + optional chevron."""
    if self._bindings:
        active_id = self.active_binding_id
        with (
            ui.tabs(value=active_id, on_change=lambda e: self._on_tab_clicked(e.value))
            .props("dense align=left")
            .classes("hw-slot-bar-tabs")
            .style("flex: 1; min-height: 36px;")
        ):
            for binding in self._bindings:
                tab_el = ui.tab(name=binding.binding_id, label="").props("no-caps")
                with tab_el:
                    with ui.row().classes("items-center gap-1 no-wrap"):
                        ui.label(binding.label or binding.editor_key)
                        if binding.can_close:
                            bid = binding.binding_id
                            (
                                ui.button(
                                    icon="close",
                                    on_click=lambda _e, b=bid: self._on_tab_close_clicked(b),
                                )
                                .props("flat round dense size=xs")
                                .classes("hw-tab-close -mr-1")
                                .on("click.stop", lambda _e: None)
                            )

    if self._show_fold_toggle:
        chevron_icon = "expand_less" if self._visible else "expand_more"
        self._fold_button = (
            ui.button(icon=chevron_icon, on_click=self._on_fold_toggle_clicked)
            .props("flat round dense size=sm")
            .tooltip(f"Toggle {self.name} slot")
            .classes("flex-shrink-0 mr-1")
        )
```

Remove `_tab_close_visible` method — no longer needed (replaced by `binding.can_close` above).

- [ ] **Step 3: Run the tab slot tests**

```bash
uv run pytest tests/ui/test_slot_tab.py -v 2>&1 | tail -30
```

Fix any failures before proceeding.

- [ ] **Step 4: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/app/tab_slot.py tests/ui/test_slot_tab.py
git commit -m "refactor: TabSlot drops slot_state.tabs writes — bindings list is sole source of truth"
```

---

## Task 4: Update `AppShell` to use `from_snapshot` and `collect_snapshot`

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/app/shell.py`
- Modify: `tests/ui/test_app_shell.py`

`AppShell._build_managed_slot` reads from `workspace_manager.active` (the old `WorkspaceState` object). Replace it with `Slot.from_snapshot(snapshot.get(slot_name, {}), registry, ...)`. Add `collect_snapshot()` which iterates `_managed_slots` and calls `to_snapshot()` on each.

- [ ] **Step 1: Update `_FakeSession` in `test_app_shell.py`**

The fake session currently exposes `workspace_manager.active` with `WorkspaceState`-style sub-objects. Replace with the new flat snapshot format:

```python
class _FakeSession:
    def __init__(self) -> None:
        self.workspace_manager = SimpleNamespace(
            snapshot={
                "left":   {"active_key": "left:editor:one", "visible": True,  "size": 300, "editors": []},
                "right":  {"active_key": "right:editor:one", "visible": True,  "size": 300, "editors": []},
                "main":   {"active_key": "main:editor:one",  "editors": []},
                "bottom": {"active_key": None, "visible": False, "size": 200, "editors": []},
            }
        )
        self._editors = {}
        self.notified_events = []

    def set_orchestrator(self, _callback) -> None:
        pass

    def notify_context_changed(self, event) -> None:
        self.notified_events.append(event)
```

- [ ] **Step 2: Run existing shell tests to see what breaks**

```bash
uv run pytest tests/ui/test_app_shell.py -v 2>&1 | tail -30
```

Note each failure.

- [ ] **Step 3: Replace `_build_managed_slot` in `shell.py`**

Replace the entire `_build_managed_slot` method:

```python
def _build_managed_slot(
    self,
    slot_name: str,
    on_visibility_change: Optional[Callable[[bool], None]] = None,
    bar_place: Literal["left", "right", "top", "bottom"] = "left",
    show_fold_toggle: bool = False,
) -> "Slot":
    """Construct and cache a Slot for ``slot_name`` from the workspace snapshot."""
    from haywire.ui.app.slot import Slot

    snapshot = self.session.workspace_manager.snapshot
    data = snapshot.get(slot_name, {})

    slot = Slot.from_snapshot(
        data=data,
        registry=self._editor_registry,
        session=self.session,
        name=slot_name,
        bar_place=bar_place,
        show_fold_toggle=show_fold_toggle,
        on_visibility_change=on_visibility_change,
    )
    self._managed_slots[slot_name] = slot
    return slot
```

- [ ] **Step 4: Update `render()` in `shell.py`**

`render()` currently reads `ws = self.session.workspace_manager.active` and then uses `ws.left.active_tab_key`, `ws.left.visible`, etc. to pass to `_build_managed_slot` and set initial visibility/dividers.

Replace:
```python
ws = self.session.workspace_manager.active
```
with:
```python
snapshot = self.session.workspace_manager.snapshot
```

Then replace each slot construction block. Old pattern:
```python
if ws.left.active_tab_key:
    left_slot = self._build_managed_slot("left", ws.left.active_tab_key)
    left_slot.set_visible(ws.left.visible)
    ...
```

New pattern — `from_snapshot` already reads `visible` and `active_key` from the snapshot, so just build and render:
```python
left_data = snapshot.get("left", {})
if left_data.get("active_key"):
    left_slot = self._build_managed_slot(
        "left", bar_place="left",
        on_visibility_change=None,  # set after construction below
    )
    left_wrapper = ui.element("div").style("height: 100%;")
    left_slot.render(left_wrapper)
    self._left_divider = (
        ui.element("div")
        .classes("hw-area-divider hw-area-divider-left flex-shrink-0")
        .style("width: 5px; height: 100%; cursor: col-resize;")
    )
    self._left_divider.set_visibility(left_slot.visible)
    left_slot._on_visibility_change = self._left_divider.set_visibility
```

Apply the same pattern to `main`, `bottom`, `right` slots, reading visibility from `slot.visible` (which `from_snapshot` set) instead of `ws.*`.

- [ ] **Step 5: Add `collect_snapshot()` to `shell.py`**

Add after `_build_managed_slot`:

```python
def collect_snapshot(self) -> dict:
    """Collect current slot state into a snapshot dict for persistence.

    Called by ``HaywireApp.save_workspace()`` immediately before writing to
    disk. Each managed slot serializes its own state via ``to_snapshot()``.
    The ``"haystack"`` key is NOT included here — the caller adds it.
    """
    return {
        slot_name: slot.to_snapshot()
        for slot_name, slot in self._managed_slots.items()
    }
```

- [ ] **Step 6: Fix shell tests**

Update any remaining test failures in `tests/ui/test_app_shell.py` caused by the `workspace_manager.active` → `workspace_manager.snapshot` change. The `_on_context_changed` signature also currently passes `workspace_manager.active` as second arg — remove that:

In `shell.py`, find:
```python
shell._on_context_changed(event, shell.session.workspace_manager.active)
```
In tests, replace with:
```python
shell._on_context_changed(event, None)
```
And in `shell.py`'s `_on_context_changed` signature, remove the unused `context` parameter if it was only there for the workspace state.

- [ ] **Step 7: Run shell and slot tests**

```bash
uv run pytest tests/ui/test_app_shell.py tests/ui/test_slot.py tests/ui/test_slot_tab.py tests/ui/test_slot_icon.py -v 2>&1 | tail -40
```

Expected: all PASS.

- [ ] **Step 8: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/app/shell.py tests/ui/test_app_shell.py
git commit -m "refactor: AppShell uses Slot.from_snapshot; adds collect_snapshot()"
```

---

## Task 5: Move `WorkspaceManager` to app level; add `save_workspace()`; delete `restore_persisted_tabs`

**Files:**
- Modify: `packages/haywire-studio/src/haywire_studio/app.py`

- [ ] **Step 1: Move `WorkspaceManager` construction to `HaywireApp.__init__`**

In `packages/haywire-studio/src/haywire_studio/app.py`, find where shared services are set up (around where `Haystack` is constructed). Add after the `Haystack` construction:

```python
from haywire.ui.workspace.manager import WorkspaceManager
self.workspace_manager = WorkspaceManager(project_path=Path(self.workspace_root))
```

- [ ] **Step 2: Update `try_load_startup_haystack`**

Replace:
```python
haystack_name = workspace_manager.active.haystack
```
with:
```python
haystack_name = workspace_manager.snapshot.get("haystack")
```

Change the method signature to take `workspace_manager` as an optional parameter, or read from `self.workspace_manager` directly:

```python
def try_load_startup_haystack(self) -> None:
    """Load the last-used haystack on startup (if configured)."""
    haystack_name = self.workspace_manager.snapshot.get("haystack")
    if not haystack_name:
        return
    if self.haystack.all_entries():
        return
    try:
        self.haystack.load_haystack(haystack_name)
        logger.info(f"Startup haystack '{haystack_name}' loaded")
    except Exception as exc:
        logger.warning(f"Failed to load startup haystack '{haystack_name}': {exc}")
```

- [ ] **Step 3: Add `save_workspace()`**

Add to `HaywireApp`:

```python
def save_workspace(self, shell=None, active_graph_path=None) -> None:
    """Save haystack and workspace snapshot atomically.

    Args:
        shell: The active AppShell. When provided, collects the current slot
            snapshot from it. When None (e.g. called before render), saves
            whatever is already in ``workspace_manager.snapshot``.
        active_graph_path: Path of the currently active graph, stored in
            the haystack TOML so it can be restored on next load.

    NOTE: The shell parameter is a temporary design — see the IMPORTANT
    FOLLOW-UP QUESTION at the top of this plan for the correct long-term
    approach.
    """
    haystack_name = self.workspace_manager.snapshot.get("haystack") or "default"
    self.haystack.save_haystack(haystack_name, active_graph_path=active_graph_path)
    snapshot = self.workspace_manager.snapshot.copy()
    if shell is not None:
        slot_data = shell.collect_snapshot()
        snapshot.update(slot_data)
        snapshot["haystack"] = haystack_name
    self.workspace_manager.save(snapshot)
```

- [ ] **Step 4: Update `main_page()` — remove per-session `WorkspaceManager`, wire shared one**

In `main_page()`, remove:
```python
from haywire.ui.workspace.manager import WorkspaceManager
workspace_manager = WorkspaceManager(
    project_path=Path(self.workspace_root),
    editor_registry=editor_registry,
)
self.try_load_startup_haystack(workspace_manager)
...
self.restore_persisted_tabs(workspace_manager, haywire_session.session_id)
```

Replace with:
```python
haywire_session = self.session_manager.create_session(
    project_state=self,
    workspace_manager=self.workspace_manager,
)
```

Call `try_load_startup_haystack` once (guard against multiple sessions):

```python
# Only load haystack on first session connect
if not self.haystack.all_entries():
    self.try_load_startup_haystack()
```

- [ ] **Step 5: Delete `restore_persisted_tabs`**

Remove the entire `restore_persisted_tabs` method from `HaywireApp`.

- [ ] **Step 6: Update TopBar save button in `shell.py`**

In `_render_topbar`, replace:
```python
on_click=lambda: (wm.save(), ui.notify("Workspace saved", position="top-right")),
```
with:
```python
on_click=lambda: (
    self.session.project_state.save_workspace(shell=self),
    ui.notify("Workspace saved", position="top-right"),
),
```

- [ ] **Step 7: Update haystack editor save paths**

In `barn/haybale-studio/haybale_studio/editors/haystack_editor.py`, find the three locations (lines ~698, ~760, ~924) that call `gm.save_haystack(...)` and/or `session.workspace_manager.save()`.

Replace each with a call to `save_workspace` via `context.app`:

```python
context.app.save_workspace(
    shell=None,  # haystack editor doesn't have shell reference — follow-up needed
    active_graph_path=context.active_graph_path,
)
```

- [ ] **Step 8: Run the full test suite**

```bash
uv run pytest --tb=short -q 2>&1 | tail -30
```

Expected: all PASS.

- [ ] **Step 9: Commit**

```bash
git add packages/haywire-studio/src/haywire_studio/app.py \
        packages/haywire-core/src/haywire/ui/app/shell.py \
        barn/haybale-studio/haybale_studio/editors/haystack_editor.py
git commit -m "refactor: WorkspaceManager moved to app level; save_workspace() coordinates haystack+snapshot save"
```

---

## Task 6: Final cleanup — remove `workspace_state.py` references and run full suite

**Files:**
- Modify: Any remaining files that import from `haywire.ui.workspace.workspace_state`

- [ ] **Step 1: Find remaining imports**

```bash
grep -rn "workspace_state\|WorkspaceState\|SlotState\|MainSlotState\|BottomSlotState\|TabState" \
  packages/ barn/ tests/ 2>/dev/null | grep -v __pycache__ | grep -v "test_workspace_state"
```

- [ ] **Step 2: Fix each remaining import**

For each hit, remove the import and replace usage with the new pattern (`slot.to_snapshot()`, `slot.from_snapshot()`, raw dicts). Each file should be straightforward — the dataclasses were only used as typed containers for data that is now plain dicts or slot-owned state.

- [ ] **Step 3: Run linter**

```bash
uv run ruff check packages/haywire-core/src/haywire/ui/ packages/haywire-studio/src/ barn/
```

Fix any lint errors.

- [ ] **Step 4: Run type checker**

```bash
uv run mypy packages/haywire-core/src/
```

Fix any type errors.

- [ ] **Step 5: Run full test suite**

```bash
uv run pytest
```

All tests must pass before this task is complete.

- [ ] **Step 6: Final commit**

```bash
git add -u
git commit -m "chore: remove remaining WorkspaceState dataclass references; all tests green"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task |
|---|---|
| `WorkspaceManager` becomes dumb I/O, holds raw `snapshot: dict` | Task 1 |
| `WorkspaceState` dataclasses deleted | Task 1 (file deleted) + Task 6 (references cleaned) |
| `Slot.to_snapshot()` / `from_snapshot()` on base class | Task 2 |
| `REQUIRED` editors excluded from snapshot, always injected at construction | Task 2 |
| `slot_state` parameter and live mirroring removed from slots | Task 2 |
| `TabSlot` drops `slot_state.tabs` writes | Task 3 |
| `AppShell._build_managed_slot` uses `from_snapshot` | Task 4 |
| `AppShell.collect_snapshot()` added | Task 4 |
| `WorkspaceManager` moved to app level (single instance) | Task 5 |
| `HaywireApp.save_workspace()` coordinates both saves | Task 5 |
| `restore_persisted_tabs` deleted | Task 5 |
| All save entry points route through `save_workspace` | Task 5 |
| `try_load_startup_haystack` reads from `snapshot.get("haystack")` | Task 5 |
| Startup sequence: haystack loads first, then snapshot, then shell constructs slots | Task 5 |
| IMPORTANT FOLLOW-UP: shell reference in `save_workspace` | Marked in Task 5 step 3 |

**Snapshot format consistency:** The format defined in the spec matches what `to_snapshot()` produces and `from_snapshot()` reads across all tasks. The `active_key` field name is used consistently (not `active_tab_key`).

**`EditorBinding.label`:** Added in Task 2 Step 5 and used in Task 3 (`open_tab` sets `binding.label = label`). `to_snapshot()` reads it. Consistent throughout.
