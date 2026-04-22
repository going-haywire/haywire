# Editor `opens` Behavior Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an `opens` kwarg to `@editor(...)` that declares how tabs for each editor class come into being (auto at startup, singleton-on-demand tracking context, or one-per-payload), replacing the current "every main-slot editor auto-populates" behavior.

**Architecture:** A new `OpenBehavior` enum with three values (`required`, `on_context`, `on_payload`) is stored on `EditorIdentity`. `WorkspaceManager._auto_populate` filters main-slot tabs to `required` editors only. The persistence rule is "save tabs where `payload is not None`"; on load, `required` tabs are re-derived from the registry and persisted `on_payload` tabs are added. The shell's `_reveal_editor` gains dispatch that (a) warns on payload-less reveal of `on_payload` editors, (b) opens-or-switches a singleton tab for `on_context`. Tab close buttons key off `opens`, not payload presence. `GraphEditor` and `FileViewerEditor` migrate to `on_payload`; `LibraryOverviewEditor` migrates to `on_context`.

**Tech Stack:** Python 3.10+, NiceGUI, pytest, existing haywire editor framework.

---

## File Structure

**New:**
- No new files — `OpenBehavior` enum is added to the existing `editor/identity.py`.

**Modified (haywire-core):**
- `packages/haywire-core/src/haywire/ui/editor/identity.py` — add `OpenBehavior` enum + `opens` field on `EditorIdentity`.
- `packages/haywire-core/src/haywire/ui/editor/decorator.py` — accept/coerce/validate `opens` kwarg.
- `packages/haywire-core/src/haywire/ui/workspace/manager.py` — filter `_auto_populate`, strip payload-less tabs on save, merge registry+persisted on load.
- `packages/haywire-core/src/haywire/ui/app/shell.py` — `_reveal_editor` dispatch; `_render_slot_tabs` close-button rule; `_follow_main_tab_context` FileViewer mirroring.

**Modified (haybale-studio editors):**
- `barn/haybale-studio/haybale_studio/editors/graph_editor.py` — add `opens="on_payload"`.
- `barn/haybale-studio/haybale_studio/editors/file_viewer.py` — add `opens="on_payload"`, read content from `binding.payload`.
- `barn/haybale-studio/haybale_studio/editors/file_browser.py` — pass `reveal_payload=str(path)`.
- `barn/haybale-studio/haybale_studio/editors/library_overview_editor.py` — add `opens="on_context"`.

**Tests:**
- `tests/ui/test_editor_registry.py` — decorator coverage for `opens`.
- `tests/ui/test_workspace_state.py` — auto-populate filtering, save-strip, load-merge.
- `tests/ui/test_app_shell.py` — reveal dispatch, close-button visibility.
- `tests/ui/test_reveal_on_context.py` — new file, regression test for `on_context` cardinality.
- `tests/studio/test_file_viewer_per_file.py` — new file, E2E for per-file FileViewer tabs.
- `tests/studio/test_library_overview_on_context.py` — new file, E2E for LibraryOverview on-demand.

**Docs:**
- `docs/documentation/build_editors.md`
- `docs/UBIQUITOUS_LANGUAGE.md`
- `docs/documentation/architecture/app_ui/haywire-ui-architecture-spec_details.md`
- `docs/documentation/architecture/haywire_app.md`
- `.codemap/modules/core-ui.md`
- `.codemap/modules/haybale-studio.md`

---

## Task 1: Add `OpenBehavior` enum and `opens` field to `EditorIdentity`

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/editor/identity.py`
- Test: `tests/ui/test_editor_registry.py`

- [ ] **Step 1: Write the failing tests**

Add these to `tests/ui/test_editor_registry.py` after the existing `TestEditorDecorator` class (around line 88):

```python
# ---------------------------------------------------------------------------
# OpenBehavior / opens kwarg tests
# ---------------------------------------------------------------------------


from haywire.ui.editor.identity import OpenBehavior


class TestOpenBehavior:
    def test_enum_has_three_values(self):
        assert OpenBehavior.REQUIRED.value == "required"
        assert OpenBehavior.ON_CONTEXT.value == "on_context"
        assert OpenBehavior.ON_PAYLOAD.value == "on_payload"

    def test_default_opens_is_required(self):
        assert _TestEditor.class_identity.opens is OpenBehavior.REQUIRED
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/ui/test_editor_registry.py::TestOpenBehavior -v`
Expected: FAIL with `ImportError: cannot import name 'OpenBehavior'`

- [ ] **Step 3: Add the enum and identity field**

Replace the contents of `packages/haywire-core/src/haywire/ui/editor/identity.py` with:

```python
"""
EditorIdentity dataclass for the Haywire editor type system.
"""

from dataclasses import dataclass, field
from enum import Enum

from haywire.core.registry.identity import BaseIdentity


class OpenBehavior(Enum):
    """How an editor's tabs come into being and how many can exist.

    - REQUIRED: shell guarantees exactly one tab, auto-populated at startup.
      Uncloseable. Content typically reads from session context.
    - ON_CONTEXT: singleton tab, on-demand. Content mirrors a slice of
      session context (e.g. active_library). No payload. Closeable.
    - ON_PAYLOAD: per-payload tab, on-demand. Payload is both the tab's
      identity and its content source. N tabs allowed. Closeable.
    """

    REQUIRED = "required"
    ON_CONTEXT = "on_context"
    ON_PAYLOAD = "on_payload"


@dataclass
class EditorIdentity(BaseIdentity):
    """
    Metadata attached to an editor class by the @editor decorator.

    Set once at class-definition time; survives hot-reload.

    Inherits from BaseIdentity:
        registry_id: Short unique ID, e.g. 'graph_editor'.
        registry_key: Fully-qualified registry key; set by decorator via reg_key().
        label: Human-readable display name, e.g. 'Graph Editor'.
        description: Human-readable description.
        class_name: Python class name — set by decorator.
        module: Python module name — set by decorator.

    Additional attributes:
        icon: Material Design icon name, e.g. 'account_tree'.
        default_slot: Which workspace slot this editor belongs in by default.
            One of: 'left', 'right', 'main', 'bottom'.
        opens: Instance-creation behavior. See OpenBehavior.
    """

    icon: str = "extension"
    default_slot: str = "main"
    opens: OpenBehavior = field(default=OpenBehavior.REQUIRED)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/ui/test_editor_registry.py::TestOpenBehavior -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Run the full editor-registry test file to confirm no regressions**

Run: `uv run pytest tests/ui/test_editor_registry.py -v`
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/editor/identity.py tests/ui/test_editor_registry.py
git commit -m "feat(editor): add OpenBehavior enum and opens field on EditorIdentity"
```

---

## Task 2: Accept and validate `opens` in the `@editor` decorator

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/editor/decorator.py`
- Test: `tests/ui/test_editor_registry.py`

- [ ] **Step 1: Write the failing tests**

Append to `TestOpenBehavior` in `tests/ui/test_editor_registry.py`:

```python
    def test_opens_accepts_string(self):
        @editor(registry_id="op_str", default_slot="main", opens="on_payload")
        class _OpensStrEditor(BaseEditor):
            def draw(self, context, container):
                pass

        assert _OpensStrEditor.class_identity.opens is OpenBehavior.ON_PAYLOAD

    def test_opens_accepts_enum(self):
        @editor(registry_id="op_enum", default_slot="main", opens=OpenBehavior.ON_CONTEXT)
        class _OpensEnumEditor(BaseEditor):
            def draw(self, context, container):
                pass

        assert _OpensEnumEditor.class_identity.opens is OpenBehavior.ON_CONTEXT

    def test_opens_rejects_typo(self):
        with pytest.raises(ValueError):
            @editor(registry_id="op_bad", default_slot="main", opens="per_documnt")
            class _OpensTypoEditor(BaseEditor):
                def draw(self, context, container):
                    pass

    def test_opens_non_required_rejected_on_left(self):
        with pytest.raises(ValueError):
            @editor(registry_id="op_left", default_slot="left", opens="on_payload")
            class _OpensLeftEditor(BaseEditor):
                def draw(self, context, container):
                    pass

    def test_opens_non_required_rejected_on_right(self):
        with pytest.raises(ValueError):
            @editor(registry_id="op_right", default_slot="right", opens="on_context")
            class _OpensRightEditor(BaseEditor):
                def draw(self, context, container):
                    pass

    def test_opens_required_ok_on_left(self):
        @editor(registry_id="op_left_req", default_slot="left", opens="required")
        class _OpensLeftReqEditor(BaseEditor):
            def draw(self, context, container):
                pass

        assert _OpensLeftReqEditor.class_identity.opens is OpenBehavior.REQUIRED
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/ui/test_editor_registry.py::TestOpenBehavior -v`
Expected: new tests FAIL with `TypeError: editor() got an unexpected keyword argument 'opens'`.

- [ ] **Step 3: Update the decorator**

Replace the contents of `packages/haywire-core/src/haywire/ui/editor/decorator.py` with:

```python
# packages/haywire-core/src/haywire/ui/editor_framework/decorator.py
"""
@editor decorator for marking classes as Haywire editor types.

Sets class_identity on the class. Does NOT register the class —
registration happens when the library calls add_folder() in
register_components(), following the same pattern as @renderer and @widget.

For built-in framework editors, registration is bootstrapped directly
in the DI provider via register_builtin_editors().
"""

from typing import Optional, Union

from haywire.core.library.utils import derive_library_identity, reg_key

from .base import BaseEditor
from .identity import EditorIdentity, OpenBehavior


def editor(
    cls=None,
    /,
    *,
    label: Optional[str] = None,
    description: str = "",
    icon: str = "extension",
    default_slot: str = "main",
    opens: Union[OpenBehavior, str] = OpenBehavior.REQUIRED,
    registry_id: Optional[str] = None,
):
    """
    Decorator to mark a class as an editor type.

    Sets class_identity on the class. Does NOT register the class —
    registration happens when the library calls add_folder() in
    register_components(), following the same pattern as @renderer and @widget.

    For built-in framework editors, registration is bootstrapped directly
    in the DI provider via register_builtin_editors().

    Args:
        label: Human-readable display name. Defaults to class name.
        icon: Material Design icon name. Defaults to 'extension'.
        default_slot: Which slot this editor belongs in by default.
            One of: 'left', 'right', 'main', 'bottom'. Defaults to 'main'.
        opens: Instance-creation behavior. One of 'required', 'on_context',
            'on_payload'. Defaults to 'required'. Only 'required' is
            permitted on 'left' / 'right' slots today.
        description: Human-readable description.
        registry_id: Unique ID for this editor, e.g. 'graph_editor'.
            Defaults to the class name if not provided.

    Usage:
        @editor(
            label='Graph Editor',
            icon='account_tree',
            default_slot='main',
            opens='on_payload',
            description='Visual node graph editor',
        )
        class GraphEditor(BaseEditor):
            ...
    """

    def decorator(inner_cls):
        if not issubclass(inner_cls, BaseEditor):
            raise TypeError(f"@editor can only be applied to BaseEditor subclasses, got {inner_cls}")

        # Coerce string to enum; raises ValueError at class-definition time on typo.
        opens_enum = OpenBehavior(opens) if isinstance(opens, str) else opens

        if default_slot in ("left", "right") and opens_enum is not OpenBehavior.REQUIRED:
            raise ValueError(
                f"@editor {inner_cls.__name__}: opens={opens_enum.value!r} is not allowed on "
                f"default_slot={default_slot!r}. Left/right slots only support opens='required'."
            )

        _registry_id = registry_id or inner_cls.__name__
        _label = label or inner_cls.__name__

        library_identity = derive_library_identity(inner_cls)
        library_id = library_identity.id if library_identity else None
        _registry_key = reg_key(library_id, "editor", _registry_id)

        inner_cls.class_identity = EditorIdentity(
            registry_id=_registry_id,
            registry_key=_registry_key,
            label=_label,
            icon=icon,
            default_slot=default_slot,
            opens=opens_enum,
            description=description,
            class_name=inner_cls.__name__,
            module=inner_cls.__module__,
        )
        inner_cls.class_library = library_identity
        return inner_cls

    return decorator if cls is None else decorator(cls)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/ui/test_editor_registry.py -v`
Expected: all tests pass (old and new).

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/editor/decorator.py tests/ui/test_editor_registry.py
git commit -m "feat(editor): accept and validate opens kwarg in @editor decorator"
```

---

## Task 3: Filter `_auto_populate` by `opens == REQUIRED`

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/workspace/manager.py:156-190`
- Test: `tests/ui/test_workspace_state.py`

- [ ] **Step 1: Extend the fake editor class in the workspace test to carry `opens`**

Find `_FakeIdentity` and `_FakeEditorClass` in `tests/ui/test_workspace_state.py` (around line 100) and replace with:

```python
from haywire.ui.editor.identity import OpenBehavior


class _FakeIdentity:
    def __init__(self, label: str, opens: OpenBehavior = OpenBehavior.REQUIRED):
        self.label = label
        self.opens = opens


class _FakeEditorClass:
    def __init__(self, label: str, opens: OpenBehavior = OpenBehavior.REQUIRED):
        self.class_identity = _FakeIdentity(label, opens)
```

Then find `_make_registry` below it and replace with:

```python
def _make_registry(**slots) -> _FakeEditorRegistry:
    """Build a fake registry from slot -> [(key, label) | (key, label, opens)] pairs."""
    by_slot: dict[str, dict[str, _FakeEditorClass]] = {}
    for slot, entries in slots.items():
        by_slot[slot] = {}
        for entry in entries:
            if len(entry) == 2:
                key, label = entry
                opens = OpenBehavior.REQUIRED
            else:
                key, label, opens = entry
            by_slot[slot][key] = _FakeEditorClass(label, opens)
    return _FakeEditorRegistry(by_slot)
```

- [ ] **Step 2: Write the failing tests**

Append to `TestWorkspaceManagerAutoPopulate` in `tests/ui/test_workspace_state.py`:

```python
    def test_auto_populate_skips_on_payload_main_editors(self, tmp_path):
        """Main-slot auto-populate must exclude opens='on_payload' editors."""
        registry = _make_registry(
            main=[
                ("editor:required", "Required", OpenBehavior.REQUIRED),
                ("editor:doc", "Document", OpenBehavior.ON_PAYLOAD),
            ],
        )
        manager = WorkspaceManager(project_path=tmp_path, editor_registry=registry)
        keys = [t.editor_key for t in manager.active.main.tabs]
        assert keys == ["editor:required"]

    def test_auto_populate_skips_on_context_main_editors(self, tmp_path):
        """Main-slot auto-populate must exclude opens='on_context' editors."""
        registry = _make_registry(
            main=[
                ("editor:required", "Required", OpenBehavior.REQUIRED),
                ("editor:ctx", "Contextual", OpenBehavior.ON_CONTEXT),
            ],
        )
        manager = WorkspaceManager(project_path=tmp_path, editor_registry=registry)
        keys = [t.editor_key for t in manager.active.main.tabs]
        assert keys == ["editor:required"]

    def test_auto_populate_main_all_on_payload_leaves_empty(self, tmp_path):
        """When every main editor is on_payload, main tab list has one empty placeholder."""
        registry = _make_registry(
            main=[
                ("editor:doc_a", "Doc A", OpenBehavior.ON_PAYLOAD),
                ("editor:doc_b", "Doc B", OpenBehavior.ON_PAYLOAD),
            ],
        )
        manager = WorkspaceManager(project_path=tmp_path, editor_registry=registry)
        # Matches the existing empty-registry contract: one placeholder TabState.
        assert len(manager.active.main.tabs) == 1
        assert manager.active.main.tabs[0].editor_key is None
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/ui/test_workspace_state.py::TestWorkspaceManagerAutoPopulate -v`
Expected: the three new tests FAIL (main tabs include all editors, not only required).

- [ ] **Step 4: Update `_auto_populate`**

In `packages/haywire-core/src/haywire/ui/workspace/manager.py`, find `_auto_populate` (line 156) and replace the `main_editors` line and the `if main_editors:` block:

```python
    @staticmethod
    def _auto_populate(editor_registry: "EditorTypeRegistry") -> WorkspaceState:
        """Build a fresh WorkspaceState from whatever editors are registered.

        The layout rule is: for each slot, look up every editor whose
        ``default_slot`` matches. The main slot gets one tab per main-slot
        editor whose ``opens`` value is ``REQUIRED`` — editors declared
        ``on_context`` or ``on_payload`` materialize only when triggered.
        The bottom slot is hidden by default; its tab list is populated
        separately by :meth:`_refresh_bottom_tabs`.
        """
        from haywire.ui.editor.identity import OpenBehavior

        left_editors = editor_registry.get_by_default_slot("left")
        right_editors = editor_registry.get_by_default_slot("right")
        main_editors_all = editor_registry.get_by_default_slot("main")
        main_editors = {
            key: cls
            for key, cls in main_editors_all.items()
            if cls.class_identity.opens is OpenBehavior.REQUIRED
        }

        left_first = next(iter(left_editors), None)
        right_first = next(iter(right_editors), None)

        if main_editors:
            tabs = [
                TabState(editor_key=key, label=cls.class_identity.label) for key, cls in main_editors.items()
            ]
        else:
            tabs = [TabState()]

        main_first = tabs[0].editor_key

        return WorkspaceState(
            name="default",
            left=SlotState(active_tab_key=left_first, visible=left_first is not None, size=250),
            right=SlotState(active_tab_key=right_first, visible=right_first is not None, size=350),
            main=MainSlotState(
                tabs=tabs,
                active_tab_key=main_first,
            ),
            bottom=BottomSlotState(),
        )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/ui/test_workspace_state.py::TestWorkspaceManagerAutoPopulate -v`
Expected: all tests in the class pass.

- [ ] **Step 6: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/workspace/manager.py tests/ui/test_workspace_state.py
git commit -m "feat(workspace): filter main auto-populate to opens=required editors"
```

---

## Task 4: Strip payload-less main tabs on save

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/workspace/manager.py:73-89`
- Test: `tests/ui/test_workspace_state.py`

- [ ] **Step 1: Write the failing test**

Append to `TestWorkspaceManagerPersistence` in `tests/ui/test_workspace_state.py`:

```python
    def test_save_strips_payload_less_main_tabs(self, tmp_path):
        """Save must not persist main tabs without a payload — they are
        re-derived from the registry on load, same pattern as bottom."""
        manager = WorkspaceManager(project_path=tmp_path, editor_registry=self._registry())
        # Add a payload-less tab (would be a `required` singleton) and a
        # payload-carrying tab (an `on_payload` document).
        manager.active.main.tabs = [
            TabState(editor_key="editor:required", label="Required"),
            TabState(
                editor_key="editor:graph",
                label="loop.haywire",
                metadata={"payload": "/tmp/loop.haywire"},
            ),
        ]
        manager.active.main.active_tab_key = "editor:graph::/tmp/loop.haywire"
        manager.save()

        data = json.loads((tmp_path / ".haywire" / "workspace_state.json").read_text())
        main_tabs = data["main"]["tabs"]
        assert len(main_tabs) == 1
        assert main_tabs[0]["editor_key"] == "editor:graph"
        assert main_tabs[0]["metadata"]["payload"] == "/tmp/loop.haywire"
```

Make sure `TabState` is imported at the top of the file. If not, add:

```python
from haywire.ui.workspace.workspace_state import TabState
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/ui/test_workspace_state.py::TestWorkspaceManagerPersistence::test_save_strips_payload_less_main_tabs -v`
Expected: FAIL — both tabs are persisted.

- [ ] **Step 3: Update `save`**

In `packages/haywire-core/src/haywire/ui/workspace/manager.py`, replace the `save` method:

```python
    def save(self) -> None:
        """Persist the current active workspace state to disk.

        Two kinds of data are stripped before serialization:

        * The bottom slot's tab list — always re-derived from the editor
          registry on load so newly-installed bottom editors appear in
          existing sessions.
        * Main-slot tabs without a payload — these are ``required`` /
          ``on_context`` singletons that are re-derived (required) or
          re-triggered (on_context) on load; persisting them would
          prevent new ``required`` editors from showing up and would
          resurrect closed ``on_context`` tabs.
        """
        preset_dir = self._project_path / ".haywire"
        preset_dir.mkdir(parents=True, exist_ok=True)
        state_file = preset_dir / _STATE_FILENAME
        payload = asdict(self.active)
        # Drop the runtime-only bottom tab list.
        if "bottom" in payload and isinstance(payload["bottom"], dict):
            payload["bottom"].pop("tabs", None)
        # Drop payload-less main tabs — they are re-derived from the
        # registry / retrigger flow on load.
        if "main" in payload and isinstance(payload["main"], dict):
            main_tabs = payload["main"].get("tabs", [])
            payload["main"]["tabs"] = [
                t for t in main_tabs
                if isinstance(t, dict) and t.get("metadata", {}).get("payload") is not None
            ]
        state_file.write_text(json.dumps(payload, indent=2))
        logger.info(f"WorkspaceManager: Persisted workspace state to {state_file}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/ui/test_workspace_state.py::TestWorkspaceManagerPersistence -v`
Expected: all tests in the class pass.

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/workspace/manager.py tests/ui/test_workspace_state.py
git commit -m "feat(workspace): strip payload-less main tabs on save"
```

---

## Task 5: Re-derive `required` main tabs on load; merge with persisted `on_payload`

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/workspace/manager.py:59-70, 114-150, 192-220`
- Test: `tests/ui/test_workspace_state.py`

- [ ] **Step 1: Write the failing tests**

Append to `TestWorkspaceManagerPersistence` in `tests/ui/test_workspace_state.py`:

```python
    def test_load_injects_missing_required_main_tabs(self, tmp_path):
        """If a `required` main editor has no persisted tab, inject it on load."""
        # Save with only a payload-carrying main tab persisted.
        m1 = WorkspaceManager(project_path=tmp_path, editor_registry=self._registry())
        m1.active.main.tabs = [
            TabState(
                editor_key="editor:graph",
                label="loop.haywire",
                metadata={"payload": "/tmp/loop.haywire"},
            ),
        ]
        m1.active.main.active_tab_key = "editor:graph::/tmp/loop.haywire"
        m1.save()

        # On load, registry still has the required "editor:graph" — it must be
        # injected in addition to the persisted payload-carrying tab.
        m2 = WorkspaceManager(project_path=tmp_path, editor_registry=self._registry())
        keys = [t.editor_key for t in m2.active.main.tabs]
        # editor:graph REQUIRED tab + the persisted payload tab
        assert keys.count("editor:graph") == 2
        # One is payload-less, one carries the path.
        payloads = [t.payload for t in m2.active.main.tabs]
        assert None in payloads
        assert "/tmp/loop.haywire" in payloads

    def test_load_drops_payload_tabs_whose_editor_is_unregistered(self, tmp_path):
        """A persisted on_payload tab whose editor is gone from registry is skipped."""
        m1 = WorkspaceManager(project_path=tmp_path, editor_registry=self._registry())
        m1.active.main.tabs = [
            TabState(
                editor_key="editor:unknown",
                label="gone.haywire",
                metadata={"payload": "/tmp/gone.haywire"},
            ),
        ]
        m1.save()

        m2 = WorkspaceManager(project_path=tmp_path, editor_registry=self._registry())
        keys = [t.editor_key for t in m2.active.main.tabs]
        assert "editor:unknown" not in keys

    def test_load_only_on_payload_registry_restores_payload_tabs(self, tmp_path):
        """A persisted payload tab whose editor is opens=on_payload is restored."""
        registry = _make_registry(
            main=[("editor:graph", "Graph", OpenBehavior.ON_PAYLOAD)],
        )
        m1 = WorkspaceManager(project_path=tmp_path, editor_registry=registry)
        m1.active.main.tabs = [
            TabState(
                editor_key="editor:graph",
                label="a.haywire",
                metadata={"payload": "/tmp/a.haywire"},
            ),
            TabState(
                editor_key="editor:graph",
                label="b.haywire",
                metadata={"payload": "/tmp/b.haywire"},
            ),
        ]
        m1.active.main.active_tab_key = "editor:graph::/tmp/b.haywire"
        m1.save()

        m2 = WorkspaceManager(project_path=tmp_path, editor_registry=registry)
        payloads = sorted(t.payload or "" for t in m2.active.main.tabs)
        assert payloads == ["/tmp/a.haywire", "/tmp/b.haywire"]
        assert m2.active.main.active_tab_key == "editor:graph::/tmp/b.haywire"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/ui/test_workspace_state.py::TestWorkspaceManagerPersistence -v`
Expected: the three new tests FAIL — `required` tabs are not re-derived on load; unknown-class tabs are kept.

- [ ] **Step 3: Add a `_refresh_main_tabs` helper and call it from `__init__`**

In `packages/haywire-core/src/haywire/ui/workspace/manager.py`:

Find `__init__` (around line 51-67) and replace with:

```python
    def __init__(
        self,
        project_path: Path,
        editor_registry: "EditorTypeRegistry",
    ):
        self._project_path = project_path
        self._editor_registry = editor_registry

        loaded = self._load()
        if loaded is not None:
            self.active = loaded
        else:
            self.active = self._auto_populate(editor_registry)

        # Bottom tabs are runtime-only and must always reflect the current
        # registry, so refresh them after both load and auto-populate paths.
        self._refresh_bottom_tabs(self.active, editor_registry)
        # Main tabs are a merge of registry-derived `required` tabs and
        # persisted payload-carrying tabs. After load, reconcile both.
        self._refresh_main_tabs(self.active, editor_registry)
```

Then at the end of the class, after `_refresh_bottom_tabs`, add:

```python
    @staticmethod
    def _refresh_main_tabs(
        workspace: WorkspaceState,
        editor_registry: "EditorTypeRegistry",
    ) -> None:
        """Reconcile main tab list against the current editor registry.

        Rules:
          * Drop persisted tabs whose ``editor_key`` is unknown to the
            registry (editor class was uninstalled).
          * Drop persisted tabs whose editor is no longer ``on_payload``
            (semantic changed — shouldn't be a payload-carrying tab).
          * Ensure every ``opens=REQUIRED`` main editor has a tab. Inject
            one at the head of the list if missing. Idempotent.
          * Resolve ``active_tab_key`` against the reconciled list; fall
            back to the first tab if the persisted key is no longer
            present.
        """
        from haywire.ui.editor.identity import OpenBehavior

        main_editors = editor_registry.get_by_default_slot("main")

        def _keep(tab: TabState) -> bool:
            if tab.editor_key is None:
                # Placeholder from empty-registry path — keep if nothing else.
                return True
            cls = main_editors.get(tab.editor_key)
            if cls is None:
                return False
            opens = getattr(cls.class_identity, "opens", OpenBehavior.REQUIRED)
            if tab.payload is not None and opens is not OpenBehavior.ON_PAYLOAD:
                return False
            return True

        kept = [t for t in workspace.main.tabs if _keep(t)]
        # Drop the lone placeholder when anything real is being added.
        required_editors = {
            key: cls
            for key, cls in main_editors.items()
            if cls.class_identity.opens is OpenBehavior.REQUIRED
        }
        if required_editors:
            kept = [t for t in kept if t.editor_key is not None]

        existing_required_keys = {t.editor_key for t in kept if t.payload is None}
        injected: list[TabState] = []
        for key, cls in required_editors.items():
            if key not in existing_required_keys:
                injected.append(TabState(editor_key=key, label=cls.class_identity.label))
        workspace.main.tabs = injected + kept

        if not workspace.main.tabs:
            workspace.main.tabs = [TabState()]

        valid_ids = {t.tab_id for t in workspace.main.tabs if t.editor_key is not None}
        if workspace.main.active_tab_key not in valid_ids:
            workspace.main.active_tab_key = (
                workspace.main.tabs[0].editor_key if workspace.main.tabs else None
            )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/ui/test_workspace_state.py -v`
Expected: all tests pass — new and existing.

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/workspace/manager.py tests/ui/test_workspace_state.py
git commit -m "feat(workspace): re-derive required main tabs on load; merge with persisted"
```

---

## Task 6: Shell reveal dispatch — `on_payload` no-payload warning

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/app/shell.py:904-958`
- Test: `tests/ui/test_app_shell.py`

- [ ] **Step 1: Inspect the existing test helper `_make_editor_cls`**

Read `tests/ui/test_app_shell.py` lines 225-260 to confirm the helper signature. If `_make_editor_cls` does not accept an `opens` parameter, extend it.

Run: `uv run pytest tests/ui/test_app_shell.py -v -x --co | head -40`
Expected: lists available shell tests. Note the file's existing fixtures.

- [ ] **Step 2: Write the failing test**

Add to `tests/ui/test_app_shell.py` (at the end of the file — preserve existing imports):

```python
# ---------------------------------------------------------------------------
# Reveal-dispatch by `opens` value
# ---------------------------------------------------------------------------


from haywire.ui.editor.identity import OpenBehavior


def _make_editor_cls_with_opens(registry_key: str, default_slot: str, opens: OpenBehavior) -> type:
    """Variant of _make_editor_cls that sets the opens field.

    Kept separate so existing tests (which use _make_editor_cls with default
    opens=REQUIRED) are unaffected.
    """
    cls = _make_editor_cls(registry_key, default_slot)
    cls.class_identity.opens = opens
    return cls


class TestRevealDispatchOpens:
    def test_on_payload_without_payload_logs_warning(self, caplog):
        """_reveal_editor on an opens='on_payload' editor with no payload
        must log a warning and no-op (no tab created)."""
        # This test should be written using the existing AppShell fixtures.
        # Replace <FIXTURE> with the shell/session fixture in this test file.
        import logging
        # See existing tests in this file for how to spin up an AppShell.
        # The key assertions: (1) no tab is created; (2) a warning is logged.
        # The scaffolding below mirrors the pattern of other reveal tests:
        shell, session = _build_test_shell_with_editors([
            ("studio:editor:Doc", "main", OpenBehavior.ON_PAYLOAD),
        ])
        with caplog.at_level(logging.WARNING):
            shell._reveal_editor("studio:editor:Doc", payload=None)
        # No binding should have been created.
        main_slot = shell._managed_slots["main"]
        assert main_slot.find_binding("studio:editor:Doc", None) is None
        assert any("on_payload" in r.message and "payload" in r.message for r in caplog.records)
```

NOTE: `_build_test_shell_with_editors` is a helper you will create next; see Step 3.

- [ ] **Step 3: Add the `_build_test_shell_with_editors` helper**

In `tests/ui/test_app_shell.py`, near the top (after existing helpers), add:

```python
from haywire.ui.editor.registry import EditorTypeRegistry


def _build_test_shell_with_editors(entries):
    """Build an AppShell + Session with a registry seeded from `entries`.

    entries: list of (registry_key, default_slot, OpenBehavior) tuples.
    Returns: (shell, session).

    Callers are responsible for NOT rendering the shell (no NiceGUI UI
    dependency) — this helper is for exercising the shell's dispatch
    helpers (`_reveal_editor`, `open_in_tab`) in isolation.
    """
    # Use the same fixture pattern the other tests in this file rely on.
    # If an existing helper exists to build a session + managed_slots map,
    # reuse it. Otherwise, inline the minimal setup.
    registry = EditorTypeRegistry()
    for registry_key, default_slot, opens in entries:
        cls = _make_editor_cls_with_opens(registry_key, default_slot, opens)
        registry._classes[registry_key] = cls
    # Re-use whatever fixture builds the shell+session in the existing tests.
    # If there is a `_make_shell(registry=...)` or similar, call that.
    # Otherwise, adapt from the file's existing tests.
    shell, session = _make_shell(registry=registry)  # existing helper — adapt as needed
    return shell, session
```

If `_make_shell` does not exist, find the equivalent pattern in `test_app_shell.py` and mirror it.

- [ ] **Step 4: Run tests to verify they fail**

Run: `uv run pytest tests/ui/test_app_shell.py::TestRevealDispatchOpens -v`
Expected: FAIL (no warning logged, or binding created).

- [ ] **Step 5: Update `_reveal_editor` to warn on payload-less `on_payload` reveal**

In `packages/haywire-core/src/haywire/ui/app/shell.py`, find `_reveal_editor` (around line 904-958) and locate the block:

```python
        # For tabbed slots, auto-create a tab when payload has no match.
        if slot_name in ("main", "bottom") and payload is not None:
            slot = self._managed_slots[slot_name]
            if slot.find_binding(editor_key, payload) is None:
                tab_label = label or editor_cls.class_identity.label
                self.open_in_tab(slot_name, editor_key, payload, tab_label)
```

Add immediately before it:

```python
        from haywire.ui.editor.identity import OpenBehavior

        opens = getattr(editor_cls.class_identity, "opens", OpenBehavior.REQUIRED)

        if opens is OpenBehavior.ON_PAYLOAD and payload is None:
            logger.warning(
                f"AppShell: reveal of opens='on_payload' editor "
                f"'{editor_key}' requires a payload; dropping."
            )
            return
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/ui/test_app_shell.py::TestRevealDispatchOpens -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/app/shell.py tests/ui/test_app_shell.py
git commit -m "feat(shell): warn on payload-less reveal of on_payload editors"
```

---

## Task 7: Shell reveal dispatch — `on_context` open-or-switch

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/app/shell.py` (same `_reveal_editor` region as Task 6)
- Test: `tests/ui/test_reveal_on_context.py` (new file)

- [ ] **Step 1: Write the failing tests**

Create `tests/ui/test_reveal_on_context.py`:

```python
"""Regression tests for on_context reveal dispatch (singleton tab per class)."""

from haywire.ui.editor.identity import OpenBehavior

from tests.ui.test_app_shell import (
    _build_test_shell_with_editors,
)


class TestOnContextRevealDispatch:
    def test_first_reveal_opens_payload_less_tab(self):
        shell, session = _build_test_shell_with_editors([
            ("studio:editor:Ctx", "main", OpenBehavior.ON_CONTEXT),
        ])
        shell._reveal_editor("studio:editor:Ctx", payload=None)
        main_slot = shell._managed_slots["main"]
        binding = main_slot.find_binding("studio:editor:Ctx", None)
        assert binding is not None
        assert binding.payload is None

    def test_second_reveal_does_not_duplicate(self):
        shell, session = _build_test_shell_with_editors([
            ("studio:editor:Ctx", "main", OpenBehavior.ON_CONTEXT),
        ])
        shell._reveal_editor("studio:editor:Ctx", payload=None)
        shell._reveal_editor("studio:editor:Ctx", payload=None)
        main_slot = shell._managed_slots["main"]
        matching = [b for b in main_slot.bindings if b.editor_key == "studio:editor:Ctx"]
        assert len(matching) == 1

    def test_second_reveal_activates_existing_tab(self):
        shell, session = _build_test_shell_with_editors([
            ("studio:editor:Ctx", "main", OpenBehavior.ON_CONTEXT),
            ("studio:editor:Other", "main", OpenBehavior.REQUIRED),
        ])
        shell._reveal_editor("studio:editor:Ctx", payload=None)
        main_slot = shell._managed_slots["main"]
        # Simulate switching to a different tab.
        main_slot.switch_to("studio:editor:Other", None)
        assert main_slot.active_key == "studio:editor:Other"
        # Reveal again — should switch back, not create a duplicate.
        shell._reveal_editor("studio:editor:Ctx", payload=None)
        assert main_slot.active_key == "studio:editor:Ctx"
        matching = [b for b in main_slot.bindings if b.editor_key == "studio:editor:Ctx"]
        assert len(matching) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/ui/test_reveal_on_context.py -v`
Expected: FAIL — `_reveal_editor` with `on_context` target and no payload currently does not open a new tab (it only switches to an existing one).

- [ ] **Step 3: Update `_reveal_editor` to auto-open for `on_context`**

In `packages/haywire-core/src/haywire/ui/app/shell.py`, locate the block added in Task 6:

```python
        if opens is OpenBehavior.ON_PAYLOAD and payload is None:
            logger.warning(...)
            return
```

Add immediately after it (before the existing `if slot_name in ("main", "bottom") and payload is not None:` block):

```python
        if (
            opens is OpenBehavior.ON_CONTEXT
            and slot_name in ("main", "bottom")
        ):
            slot = self._managed_slots[slot_name]
            if slot.find_binding(editor_key, None) is None:
                tab_label = label or editor_cls.class_identity.label
                self.open_in_tab(slot_name, editor_key, None, tab_label)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/ui/test_reveal_on_context.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Run the shell test suite to confirm no regressions**

Run: `uv run pytest tests/ui/test_app_shell.py tests/ui/test_reveal_on_context.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/app/shell.py tests/ui/test_reveal_on_context.py
git commit -m "feat(shell): on_context reveal opens singleton tab or switches to it"
```

---

## Task 8: Close-button visibility keyed on `opens`

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/app/shell.py:706-755`
- Test: `tests/ui/test_app_shell.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/ui/test_app_shell.py`:

```python
class TestTabCloseButtonVisibility:
    def test_required_tab_has_no_close_button(self):
        """opens=REQUIRED tabs must not render a close button."""
        shell, session = _build_test_shell_with_editors([
            ("studio:editor:Req", "main", OpenBehavior.REQUIRED),
        ])
        ws = session.workspace_manager.active
        tab = ws.main.tabs[0]  # required editor is auto-populated
        # Helper assertion — actual DOM check depends on your fixture.
        assert shell._tab_close_visible(tab) is False

    def test_on_payload_tab_has_close_button(self):
        shell, session = _build_test_shell_with_editors([
            ("studio:editor:Doc", "main", OpenBehavior.ON_PAYLOAD),
        ])
        shell.open_in_tab("main", "studio:editor:Doc", payload="/tmp/a", label="a")
        ws = session.workspace_manager.active
        tab = next(t for t in ws.main.tabs if t.payload == "/tmp/a")
        assert shell._tab_close_visible(tab) is True

    def test_on_context_tab_has_close_button(self):
        shell, session = _build_test_shell_with_editors([
            ("studio:editor:Ctx", "main", OpenBehavior.ON_CONTEXT),
        ])
        shell._reveal_editor("studio:editor:Ctx", payload=None)
        ws = session.workspace_manager.active
        tab = next(t for t in ws.main.tabs if t.editor_key == "studio:editor:Ctx")
        assert shell._tab_close_visible(tab) is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/ui/test_app_shell.py::TestTabCloseButtonVisibility -v`
Expected: FAIL — `_tab_close_visible` does not exist.

- [ ] **Step 3: Extract close-visibility into a helper and use it in `_render_slot_tabs`**

In `packages/haywire-core/src/haywire/ui/app/shell.py`, add this method on `AppShell` (near the other private rendering helpers, right before `_render_slot_tabs`):

```python
    def _tab_close_visible(self, tab) -> bool:
        """Return True if the tab should render a close (×) button.

        Rule: every tab whose editor class declares ``opens != REQUIRED``
        is closeable. ``required`` tabs are always-present singletons and
        have no close button.

        Unknown editor classes default to closeable — better to let the
        user remove a tab whose class is gone than strand it.
        """
        from haywire.ui.editor.identity import OpenBehavior

        if tab.editor_key is None:
            return False
        cls = self._editor_registry.get_by_key(tab.editor_key) if self._editor_registry else None
        if cls is None:
            return True
        opens = getattr(cls.class_identity, "opens", OpenBehavior.REQUIRED)
        return opens is not OpenBehavior.REQUIRED
```

Then, in `_render_slot_tabs`, replace the close-button check:

```python
                        if on_close is not None and tab.payload is not None:
```

with:

```python
                        if on_close is not None and self._tab_close_visible(tab):
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/ui/test_app_shell.py::TestTabCloseButtonVisibility -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Run the full shell + workspace test suite**

Run: `uv run pytest tests/ui/test_app_shell.py tests/ui/test_workspace_state.py tests/ui/test_slot.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/app/shell.py tests/ui/test_app_shell.py
git commit -m "feat(shell): tab close button keyed on opens, not payload"
```

---

## Task 9: Migrate `GraphEditor` to `opens="on_payload"`

**Files:**
- Modify: `barn/haybale-studio/haybale_studio/editors/graph_editor.py:34-39`

- [ ] **Step 1: Add `opens="on_payload"` to the decorator**

In `barn/haybale-studio/haybale_studio/editors/graph_editor.py`, update the `@editor(...)` block (lines 34-39):

```python
@editor(
    label="Graph Editor",
    icon=hui.icon.graph,
    default_slot="main",
    opens="on_payload",
    description="Visual node graph editor for wiring data processing pipelines.",
)
class GraphEditor(BaseEditor):
```

- [ ] **Step 2: Run the existing graph-related tests**

Run: `uv run pytest tests/studio/ tests/ui/ -v -k "graph or editor or workspace"`
Expected: all pass — the decorator change is behavior-preserving for `GraphEditor` because it already follows the `on_payload` pattern.

- [ ] **Step 3: Commit**

```bash
git add barn/haybale-studio/haybale_studio/editors/graph_editor.py
git commit -m "refactor(graph_editor): declare opens=on_payload"
```

---

## Task 10: Migrate `FileViewerEditor` to read content from `binding.payload`

**Files:**
- Modify: `barn/haybale-studio/haybale_studio/editors/file_viewer.py`
- Test: `tests/studio/test_file_viewer_per_file.py` (new)

- [ ] **Step 1: Write the failing tests**

Create `tests/studio/test_file_viewer_per_file.py`:

```python
"""E2E: FileViewer is opens='on_payload'; one tab per file; re-clicking dedupes."""

from pathlib import Path

import pytest

from haybale_studio.editors.file_viewer import FileViewerEditor
from haywire.ui.editor.identity import OpenBehavior


@pytest.mark.unit
def test_file_viewer_declares_on_payload():
    assert FileViewerEditor.class_identity.opens is OpenBehavior.ON_PAYLOAD


@pytest.mark.unit
def test_file_viewer_reads_payload_from_binding(tmp_path):
    """FileViewerEditor.draw must render the file indicated by binding.payload,
    not context.active_file."""
    path = tmp_path / "hello.txt"
    path.write_text("hello world")

    viewer = FileViewerEditor()

    # Simulate binding attachment the way EditorBinding.ensure_instance does.
    class _FakeBinding:
        editor_key = FileViewerEditor.class_identity.registry_key
        payload = str(path)

    viewer.binding = _FakeBinding()

    # draw() requires a nicegui container; we only need _last_file resolution.
    # The new implementation must set _last_file from binding.payload before
    # _render_content is called.
    # Use a thin draw invocation through a nicegui auto_index client is not
    # practical here — instead, assert the helper that resolves the path:
    assert viewer._resolve_path() == path
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/studio/test_file_viewer_per_file.py -v`
Expected: FAIL — FileViewer does not declare `opens="on_payload"` and does not expose `_resolve_path`.

- [ ] **Step 3: Update `FileViewerEditor`**

In `barn/haybale-studio/haybale_studio/editors/file_viewer.py`, replace the `@editor(...)` block and the relevant methods:

Find:

```python
@editor(
    label="File Viewer",
    icon=hui.icon.library_component,
    default_slot="main",
    description="Displays the contents of a file selected in the Files browser.",
)
```

Replace with:

```python
@editor(
    label="File Viewer",
    icon=hui.icon.library_component,
    default_slot="main",
    opens="on_payload",
    description="Displays the contents of a file selected in the Files browser.",
)
```

Find the `poll`, `draw`, and `get_tab_label` methods (lines 63-97 and 154-158). Replace the entire `FileViewerEditor` class body from `def __init__` to the end of `cleanup` with:

```python
    def __init__(self):
        self._last_file: Optional[Path] = None

    def _resolve_path(self) -> Optional[Path]:
        """Return the file path this tab is pinned to, via binding.payload."""
        if self.binding is None or self.binding.payload is None:
            return None
        return Path(self.binding.payload)

    def poll(self, context: "SessionContext", event: "ContextChangedEvent") -> bool:
        """Redraw when DATA_MUTATED touches this file, otherwise stay put.

        Each FileViewer instance is pinned to one file via its binding
        payload. FILE_SELECTED events no longer drive redraws — a different
        file means a different tab.
        """
        return False

    def draw(self, context: "SessionContext", container: "Element") -> None:
        self._last_file = self._resolve_path()

        with container:
            with ui.column().classes("w-full h-full gap-0"):
                # Slim header showing the open file path
                with (
                    ui.row()
                    .classes("w-full items-center px-3 gap-2 flex-shrink-0 border-b")
                    .style("min-height: 32px; background: var(--hw-bg-page);")
                ):
                    ui.icon("description", size="14px").classes("hw-text-dim")
                    label_text = str(self._last_file) if self._last_file else "No file open"
                    label_cls = "hw-text-body" if self._last_file else "hw-text-muted"
                    ui.label(label_text).classes(f"text-xs {label_cls} truncate font-mono flex-1")

                # Content area
                with ui.scroll_area().classes("flex-1 w-full"):
                    with ui.column().classes("w-full"):
                        if self._last_file is not None:
                            self._render_content(self._last_file)
                        else:
                            hui.empty_state(
                                "Select a file from the Files panel",
                                icon=hui.icon.folder_open,
                            )

    def get_tab_label(self, context: "SessionContext") -> str:
        path = self._resolve_path()
        if path is not None:
            return path.name
        return self.class_identity.label

    def cleanup(self) -> None:
        pass
```

Keep `_render_content` and the module-level constants unchanged.

Remove the now-unused import of `ContextChangeType` if nothing else in the file references it. Run `uv run ruff check barn/haybale-studio/haybale_studio/editors/file_viewer.py` after committing to confirm no unused-import warnings.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/studio/test_file_viewer_per_file.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add barn/haybale-studio/haybale_studio/editors/file_viewer.py tests/studio/test_file_viewer_per_file.py
git commit -m "refactor(file_viewer): read file path from binding.payload; declare opens=on_payload"
```

---

## Task 11: Update `FileBrowserEditor` to open FileViewer with payload

**Files:**
- Modify: `barn/haybale-studio/haybale_studio/editors/file_browser.py:185-198`
- Test: extend `tests/studio/test_file_viewer_per_file.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/studio/test_file_viewer_per_file.py`:

```python
@pytest.mark.unit
def test_file_browser_reveal_includes_payload(tmp_path, monkeypatch):
    """FileBrowser._open_in_file_viewer must supply reveal_payload=<path>."""
    from haybale_studio.editors.file_browser import FileBrowserEditor

    browser = FileBrowserEditor()
    path = tmp_path / "a.txt"
    path.write_text("x")

    captured = []

    class _FakeSession:
        def notify_context_changed(self, event):
            captured.append(event)

    class _FakeContext:
        session = _FakeSession()
        active_file = None

    browser._open_in_file_viewer(path, _FakeContext())

    assert len(captured) == 1
    event = captured[0]
    assert event.reveal_editor == FileViewerEditor.class_identity.registry_key
    assert event.reveal_payload == str(path)
    assert event.reveal_label == path.name
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/studio/test_file_viewer_per_file.py::test_file_browser_reveal_includes_payload -v`
Expected: FAIL — no `reveal_payload` on the event.

- [ ] **Step 3: Update `_open_in_file_viewer`**

In `barn/haybale-studio/haybale_studio/editors/file_browser.py`, replace the `_open_in_file_viewer` method (lines 185-198):

```python
    def _open_in_file_viewer(self, path: Path, context: "SessionContext") -> None:
        """Reveal a FileViewer tab pinned to this file's path.

        Uses the ``reveal_payload`` channel so ``AppShell._reveal_editor``
        dedupes on ``(editor_key, payload)`` — re-clicking an open file
        switches to the existing tab instead of opening a duplicate.
        """
        session = context.session
        if session is None:
            return
        from haybale_studio.editors.file_viewer import FileViewerEditor

        session.notify_context_changed(
            ContextChangedEvent(
                change_type=ContextChangeType.FILE_SELECTED,
                source_editor="file_browser",
                detail=path,
                reveal_editor=FileViewerEditor.class_identity.registry_key,
                reveal_payload=str(path),
                reveal_label=path.name,
            )
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/studio/test_file_viewer_per_file.py -v`
Expected: all tests pass (3 tests).

- [ ] **Step 5: Commit**

```bash
git add barn/haybale-studio/haybale_studio/editors/file_browser.py tests/studio/test_file_viewer_per_file.py
git commit -m "refactor(file_browser): open FileViewer with reveal_payload=<path>"
```

---

## Task 12: Extend `_follow_main_tab_context` for FileViewer

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/app/shell.py:1541-1572`

NOTE: `_follow_main_tab_context` lives in haywire-core (the shell), so it cannot reference `FileViewerEditor` from `haybale-studio` directly. The shell must discover the registry key by looking up editor classes whose behavior it cares about without importing them.

The approach: haybale-studio passes a small dispatch table (or the shell checks `editor_key` against `context.active_file` / `context.active_graph_path` fields via a registered hook). To avoid a layering violation, add a protocol: `_follow_main_tab_context` dispatches on `editor_key` prefix matches against a small registry of "active-<kind>-path" context fields that the host app registers.

For this task, keep the change minimal: the shell-side hook reads the active binding's `editor_cls.class_identity.registry_key` and `module` and applies a small rule: if the active binding's editor module path contains `file_viewer`, mirror to `context.active_file`. This is ugly but avoids a framework expansion in scope.

Alternatively, extend the existing Graph-specific handling to be field-name-driven: the shell inspects the active binding's editor class for a `class_identity.context_field` attribute, if present, and mirrors `binding.payload` into `context.<context_field>`.

Simpler path: add `context_field` as an optional attribute on `EditorIdentity` (default `None`), set to `"active_file"` on FileViewer and `"active_graph_path"` on GraphEditor. The shell's `_follow_main_tab_context` dispatches on it.

- [ ] **Step 1: Add `context_field` attribute to `EditorIdentity`**

In `packages/haywire-core/src/haywire/ui/editor/identity.py`, add a field:

```python
    icon: str = "extension"
    default_slot: str = "main"
    opens: OpenBehavior = field(default=OpenBehavior.REQUIRED)
    context_field: Optional[str] = None
```

Add the import at the top:

```python
from typing import Optional
```

- [ ] **Step 2: Add `context_field` kwarg to the `@editor` decorator**

In `packages/haywire-core/src/haywire/ui/editor/decorator.py`, update the signature and `EditorIdentity(...)` construction to accept `context_field: Optional[str] = None` and pass it through. Pattern identical to `opens`.

Find the signature:

```python
def editor(
    cls=None,
    /,
    *,
    label: Optional[str] = None,
    description: str = "",
    icon: str = "extension",
    default_slot: str = "main",
    opens: Union[OpenBehavior, str] = OpenBehavior.REQUIRED,
    registry_id: Optional[str] = None,
):
```

Replace with:

```python
def editor(
    cls=None,
    /,
    *,
    label: Optional[str] = None,
    description: str = "",
    icon: str = "extension",
    default_slot: str = "main",
    opens: Union[OpenBehavior, str] = OpenBehavior.REQUIRED,
    context_field: Optional[str] = None,
    registry_id: Optional[str] = None,
):
```

And in the `inner_cls.class_identity = EditorIdentity(...)` call, add `context_field=context_field,` before `description=description,`.

- [ ] **Step 3: Write the failing test**

Add to `tests/ui/test_app_shell.py`:

```python
class TestFollowMainTabContextByField:
    def test_active_binding_with_context_field_mirrors_payload(self):
        """When the active main binding has a context_field, the shell
        mirrors binding.payload into context.<field> and emits a change."""
        shell, session = _build_test_shell_with_editors([
            ("studio:editor:F", "main", OpenBehavior.ON_PAYLOAD),
        ])
        # Manually attach context_field to the class identity for the test:
        cls = shell._editor_registry.get_by_key("studio:editor:F")
        cls.class_identity.context_field = "active_file"

        shell.open_in_tab("main", "studio:editor:F", payload="/tmp/a.txt", label="a.txt")

        assert str(session.context.active_file) == "/tmp/a.txt"
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `uv run pytest tests/ui/test_app_shell.py::TestFollowMainTabContextByField -v`
Expected: FAIL.

- [ ] **Step 5: Extend `_follow_main_tab_context`**

In `packages/haywire-core/src/haywire/ui/app/shell.py`, locate `_follow_main_tab_context` (line 1541). Replace with:

```python
    def _follow_main_tab_context(self, payload: Optional[str]) -> None:
        """Mirror the active main tab's identity into session context.

        Per-tab editors (GraphEditor, FileViewerEditor) read their own
        binding payload for rendering; this exists for peer editors and
        panels that still consume ``context.active_graph_path`` /
        ``context.active_file`` / etc.

        The target context field is named on the editor's class identity
        (``EditorIdentity.context_field``) so the shell doesn't need to
        know about specific editor classes. The GraphEditor-specific
        haystack lookup is preserved because haystack entries are first-
        class in the project state.
        """
        context = self.session.context

        slot = self._managed_slots.get("main")
        active_binding = slot.active_binding if slot is not None else None
        if active_binding is None:
            return
        editor_cls = active_binding.editor_cls
        context_field = getattr(editor_cls.class_identity, "context_field", None)

        # Graph-specific path — resolve through haystack entries so
        # consumers that read ``active_graph`` keep working.
        if context_field == "active_graph_path":
            if payload is None:
                return
            app = context.app
            if app is None or not hasattr(app, "haystack"):
                return
            entry = app.haystack.get_by_key(payload)
            if entry is None:
                return
            if context.active_graph is entry.graph and context.active_graph_path == entry.path:
                return
            context.active_graph = entry.graph
            context.active_graph_path = entry.path
            self.session.notify_context_changed(
                ContextChangedEvent(
                    change_type=ContextChangeType.ACTIVE_GRAPH_CHANGED,
                    source_editor="app_shell",
                    detail=entry,
                )
            )
            return

        # Generic payload → context.<field> mirror.
        if context_field is not None:
            from pathlib import Path
            new_value = Path(payload) if payload is not None else None
            if getattr(context, context_field, None) == new_value:
                return
            setattr(context, context_field, new_value)
            self.session.notify_context_changed(
                ContextChangedEvent(
                    change_type=ContextChangeType.FILE_SELECTED
                    if context_field == "active_file"
                    else ContextChangeType.CUSTOM,
                    source_editor="app_shell",
                    detail=new_value,
                )
            )
```

- [ ] **Step 6: Set `context_field` on GraphEditor and FileViewer**

In `barn/haybale-studio/haybale_studio/editors/graph_editor.py`, update the decorator:

```python
@editor(
    label="Graph Editor",
    icon=hui.icon.graph,
    default_slot="main",
    opens="on_payload",
    context_field="active_graph_path",
    description="Visual node graph editor for wiring data processing pipelines.",
)
```

In `barn/haybale-studio/haybale_studio/editors/file_viewer.py`, update the decorator:

```python
@editor(
    label="File Viewer",
    icon=hui.icon.library_component,
    default_slot="main",
    opens="on_payload",
    context_field="active_file",
    description="Displays the contents of a file selected in the Files browser.",
)
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest tests/ui/test_app_shell.py tests/studio/test_file_viewer_per_file.py tests/studio/ -v`
Expected: all tests pass.

- [ ] **Step 8: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/editor/identity.py packages/haywire-core/src/haywire/ui/editor/decorator.py packages/haywire-core/src/haywire/ui/app/shell.py barn/haybale-studio/haybale_studio/editors/graph_editor.py barn/haybale-studio/haybale_studio/editors/file_viewer.py tests/ui/test_app_shell.py
git commit -m "feat(shell): mirror active-binding payload into context.<field> via EditorIdentity.context_field"
```

---

## Task 13: Migrate `LibraryOverviewEditor` to `opens="on_context"`

**Files:**
- Modify: `barn/haybale-studio/haybale_studio/editors/library_overview_editor.py:69-74`
- Test: `tests/studio/test_library_overview_on_context.py` (new)

- [ ] **Step 1: Write the failing tests**

Create `tests/studio/test_library_overview_on_context.py`:

```python
"""E2E: LibraryOverview is opens='on_context'; no auto-populate; first click opens
a singleton tab; second click with different library switches the same tab."""

import pytest

from haybale_studio.editors.library_overview_editor import LibraryOverviewEditor
from haywire.ui.editor.identity import OpenBehavior


@pytest.mark.unit
def test_library_overview_declares_on_context():
    assert LibraryOverviewEditor.class_identity.opens is OpenBehavior.ON_CONTEXT


@pytest.mark.unit
def test_library_overview_not_auto_populated_in_main(tmp_path):
    """WorkspaceManager._auto_populate must skip LibraryOverview now."""
    from haywire.ui.workspace.manager import WorkspaceManager
    from haywire.ui.editor.registry import EditorTypeRegistry

    registry = EditorTypeRegistry()
    registry._classes[LibraryOverviewEditor.class_identity.registry_key] = LibraryOverviewEditor

    manager = WorkspaceManager(project_path=tmp_path, editor_registry=registry)
    keys = [t.editor_key for t in manager.active.main.tabs]
    assert LibraryOverviewEditor.class_identity.registry_key not in keys
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/studio/test_library_overview_on_context.py -v`
Expected: FAIL — LibraryOverview defaults to `REQUIRED`, auto-populates.

- [ ] **Step 3: Update the decorator**

In `barn/haybale-studio/haybale_studio/editors/library_overview_editor.py`, update the `@editor(...)` block:

```python
@editor(
    label="Library Detail",
    icon=hui.icon.node_info,
    default_slot="main",
    opens="on_context",
    description="Detailed information for the selected library.",
)
class LibraryOverviewEditor(BaseEditor):
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/studio/test_library_overview_on_context.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Run the full studio test suite**

Run: `uv run pytest tests/studio/ -v`
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add barn/haybale-studio/haybale_studio/editors/library_overview_editor.py tests/studio/test_library_overview_on_context.py
git commit -m "refactor(library_overview): declare opens=on_context (singleton on demand)"
```

---

## Task 14: Update `docs/documentation/build_editors.md`

**Files:**
- Modify: `docs/documentation/build_editors.md`

- [ ] **Step 1: Read the current document to find insertion points**

Run: `uv run pytest tests/ui/test_editor_registry.py -v` to re-confirm the decorator shape is what the docs should describe.

Read `docs/documentation/build_editors.md` to find:
- The `@editor` signature example around line 80-90.
- The "reveal" / "switching tabs" section around line 325-346.
- The `default_slot` guidance around line 453.

- [ ] **Step 2: Update the `@editor` signature example**

In `docs/documentation/build_editors.md`, find the signature around line 85 and replace the relevant lines with:

```python
@editor(
    label='Graph Editor',
    icon='account_tree',
    default_slot='main',            # 'left' | 'right' | 'main' | 'bottom'
    opens='on_payload',             # 'required' | 'on_context' | 'on_payload'
    context_field='active_graph_path',  # optional; field on SessionContext to mirror
    description='Visual node graph editor',
)
```

- [ ] **Step 3: Add a new subsection after the signature, titled "Instance behavior: `opens`"**

Insert after the signature block:

````markdown
### Instance behavior: `opens`

The `opens` kwarg declares how an editor's tabs come into being and how
many can exist. Three values:

- **`required`** (default) — the shell guarantees one tab at startup.
  Uncloseable. Content typically reads from session context. Use for
  persistent panels (left/right side editors, bottom terminal, rarely
  main).

- **`on_context`** — singleton tab, on-demand. The tab's content mirrors
  a slice of session context (e.g. `active_library`). Opened when
  something fires `reveal_editor=...` with no payload; a second reveal
  with different context just redraws the same tab via `poll()`.
  Closeable. Not persisted across restart.

- **`on_payload`** — per-payload tab, on-demand. The tab's identity and
  content are determined by its `binding.payload`. Opened when the
  reveal fires `reveal_editor=... reveal_payload=<value>`; N distinct
  payloads means N distinct tabs. Closeable. Persisted across restart.

**Constraint:** `default_slot='left'` and `'right'` only support
`opens='required'`. Bars don't have a tab structure to host on-demand
or multi-instance editors — the decorator raises `ValueError` at
class-definition time if you try.

**`context_field`** (optional) names a `SessionContext` attribute that
the shell should mirror `binding.payload` into whenever this editor's
tab becomes active. Only meaningful for `on_payload` editors in the
main slot. Example: a FileViewer declares `context_field='active_file'`
so any peer editor reading `context.active_file` sees the currently-
focused file.
````

- [ ] **Step 4: Update the "reveal" / "switch to tab" section**

Find the section around line 346 ("### Switching tabs in main / bottom slots"). Add a paragraph:

```markdown
When the target editor is `opens='on_payload'`, a reveal without a
`reveal_payload` is a no-op with a warning — payloads are mandatory for
per-payload editors. When the target is `opens='on_context'` and no
matching tab exists, the shell auto-creates a payload-less tab.
```

- [ ] **Step 5: Update the `default_slot` guidance at line 453**

Find: `**Use `default_slot` as a hint, not a mandate.**`

Replace the paragraph with:

```markdown
**`default_slot` is where the editor lives; `opens` is how its tabs
appear.** Set `default_slot` to place the editor in the right slot.
Set `opens` to say whether it auto-populates (`required`) or waits to
be triggered (`on_context` / `on_payload`). Workspace configs override
`default_slot` entirely; `opens` is a property of the editor class.
```

- [ ] **Step 6: Commit**

```bash
git add docs/documentation/build_editors.md
git commit -m "docs(build_editors): document opens kwarg and context_field"
```

---

## Task 15: Update `docs/UBIQUITOUS_LANGUAGE.md`

**Files:**
- Modify: `docs/UBIQUITOUS_LANGUAGE.md`

- [ ] **Step 1: Find the right section**

Read `docs/UBIQUITOUS_LANGUAGE.md` and locate the section that covers editor terms (near the `default_slot` / `"middle" vs "main"` entries around line 241).

- [ ] **Step 2: Add glossary entries**

Insert after the existing editor-related definitions:

```markdown
- **`OpenBehavior`** — Enum on `EditorIdentity` declaring how an editor's
  tabs come into being. Three values:
  - **`required`**: exactly one tab, always present, auto-populated at
    startup, uncloseable.
  - **`on_context`**: singleton tab, on-demand. Content mirrors a slice
    of session context; the tab has no payload. Closeable. Not persisted.
  - **`on_payload`**: per-payload tab, on-demand. The `binding.payload`
    is both the tab's identity and its content source. N tabs allowed.
    Closeable. Persisted across restart.
- **`payload` (tab)** — A `str` that disambiguates per-payload tabs of
  the same editor class. For GraphEditor the payload is the graph path;
  for FileViewer it is the file path. Stored in `TabState.metadata.payload`
  and mirrored in `EditorBinding.payload`.
- **`context_field`** — Optional attribute on `EditorIdentity` naming a
  `SessionContext` field the shell mirrors `binding.payload` into when
  the active main tab changes. Enables peer editors to read the current
  subject (e.g. `context.active_file`) without subscribing to tab events.
```

- [ ] **Step 3: Commit**

```bash
git add docs/UBIQUITOUS_LANGUAGE.md
git commit -m "docs(glossary): add OpenBehavior, payload (tab), context_field"
```

---

## Task 16: Update `docs/documentation/architecture/app_ui/haywire-ui-architecture-spec_details.md`

**Files:**
- Modify: `docs/documentation/architecture/app_ui/haywire-ui-architecture-spec_details.md`

- [ ] **Step 1: Read the relevant `@editor` examples**

Read the spec document's `@editor` examples at lines 374-377 and 1173-1176 to confirm the current form.

- [ ] **Step 2: Update both `@editor` examples**

In `docs/documentation/architecture/app_ui/haywire-ui-architecture-spec_details.md`, find:

```python
    label='Graph Editor',
    icon='account_tree',
    default_slot='main',
    description='Visual node graph editor',
```

(Appears twice — around lines 374-377 and 1173-1176.) In both places, add an `opens='on_payload',` line between `default_slot` and `description`:

```python
    label='Graph Editor',
    icon='account_tree',
    default_slot='main',
    opens='on_payload',
    description='Visual node graph editor',
```

Then find the Library Detail example at line 1360-1363 and update:

```python
    label='Library Detail',
    icon='info',
    default_slot='main',
    opens='on_context',
    description='Detail view for the selected library.',
```

- [ ] **Step 3: Update the auto-populate and persistence rules**

Search the document for the phrases "auto-populate" or "auto populates" and update any paragraph that describes main-slot behavior to reflect:

- Only `opens='required'` main editors auto-populate.
- On save, tabs without a payload are stripped.
- On load, `required` main tabs are re-derived from the registry; persisted `on_payload` tabs are added.

- [ ] **Step 4: Commit**

```bash
git add docs/documentation/architecture/app_ui/haywire-ui-architecture-spec_details.md
git commit -m "docs(architecture): update spec with opens + new auto-populate/persistence rules"
```

---

## Task 17: Update `docs/documentation/architecture/haywire_app.md`

**Files:**
- Modify: `docs/documentation/architecture/haywire_app.md`

- [ ] **Step 1: Find `@editor` references**

Run: `uv run grep -n "@editor" docs/documentation/architecture/haywire_app.md` (or use Grep tool).

- [ ] **Step 2: Update any `@editor` signature examples**

For each `@editor(...)` example in the file, add the `opens` kwarg appropriate to the example editor (most likely `opens='on_payload'` for GraphEditor illustrations, `opens='required'` for side-panel editors).

- [ ] **Step 3: Commit**

```bash
git add docs/documentation/architecture/haywire_app.md
git commit -m "docs(haywire_app): include opens in @editor examples"
```

---

## Task 18: Update `.codemap/modules/core-ui.md` and `.codemap/modules/haybale-studio.md`

**Files:**
- Modify: `.codemap/modules/core-ui.md`
- Modify: `.codemap/modules/haybale-studio.md`

- [ ] **Step 1: Identify mentions of `@editor` / `default_slot` / "auto-populate" in each codemap file**

Run: `uv run grep -n "default_slot\|@editor\|auto-populate\|auto populate" .codemap/modules/core-ui.md .codemap/modules/haybale-studio.md`

- [ ] **Step 2: Update `core-ui.md`**

In `.codemap/modules/core-ui.md`, wherever the `@editor` decorator or `EditorIdentity` is described, add a bullet or sentence:

```markdown
- `opens` (enum `OpenBehavior`): instance-creation behavior. `required`
  auto-populates and is uncloseable; `on_context` is a singleton tab
  opened on demand (content mirrors session context); `on_payload` is
  one tab per distinct payload, opened on demand (payload drives content).
- `context_field` (optional): `SessionContext` attribute the shell
  mirrors `binding.payload` into when the active main tab changes.
```

Wherever "auto-populate" or "first-launch tab" is described for the main slot, add:

```markdown
Only `opens='required'` main editors auto-populate; `on_context` and
`on_payload` editors start with zero tabs.
```

- [ ] **Step 3: Update `haybale-studio.md`**

In `.codemap/modules/haybale-studio.md`, find the section listing editors provided by the library. Add an "instance mode" column or bullet to each:

- `GraphEditor` → `opens=on_payload` (one tab per graph).
- `FileViewerEditor` → `opens=on_payload` (one tab per file).
- `LibraryOverviewEditor` → `opens=on_context` (singleton, tracks `context.active_library`).
- `FileBrowserEditor`, `HaystackEditor`, `LibraryBrowserEditor`, `PropertiesEditor`, `LibraryComponentEditor`, `TerminalEditor` → `opens=required` (default).

- [ ] **Step 4: Commit**

```bash
git add .codemap/modules/core-ui.md .codemap/modules/haybale-studio.md
git commit -m "docs(codemap): note opens behavior across core-ui and haybale-studio modules"
```

---

## Task 19: Final full-suite verification

**Files:** none (verification only)

- [ ] **Step 1: Run the complete test suite**

Run: `uv run pytest -v`
Expected: all tests pass.

- [ ] **Step 2: Run lint and format checks**

Run: `uv run ruff check .`
Expected: clean.

Run: `uv run ruff format --check .`
Expected: clean.

- [ ] **Step 3: Run type checker**

Run: `uv run mypy packages/haywire-core/src/`
Expected: clean (or matches pre-change baseline).

- [ ] **Step 4: Start the app and smoke-test the UX**

Run: `uv run haywire`

Manually verify:
- On first launch (or after deleting `.haywire/workspace_state.json`), the main slot shows no GraphEditor or FileViewer tab. No library overview either, unless a library is actively selected.
- Clicking a `.haywire` file in the File Browser opens a new GraphEditor tab pinned to that graph.
- Clicking a second `.haywire` file opens a second tab. Clicking the first file again switches to the existing tab (no duplicate).
- Clicking a non-graph file opens a new FileViewer tab pinned to that file. Clicking a different file opens a second FileViewer tab.
- Clicking a library in the Library Browser opens a LibraryOverview tab. Clicking a different library reuses the same tab.
- Closing a FileViewer or GraphEditor tab works via the × button. Attempting to close a left/right editor has no close button (unchanged). Required bottom editors (Terminal) have no close button.
- Restart the app: open graph tabs come back, FileViewer tabs come back (because they have payloads), LibraryOverview does not (no payload).

- [ ] **Step 5: Commit any cleanup**

If manual testing surfaced issues that required code changes, fix them and commit:

```bash
git add <files>
git commit -m "fix(opens): <describe fix>"
```

- [ ] **Step 6: Summary of change**

Run: `git log --oneline main..HEAD` to list commits. Verify the branch is clean (`git status`) and the working tree has no uncommitted changes.

---

## Self-Review Notes

**Spec coverage (from the inquisition):**

- Q1–Q9 (enum design, decorator shape, validation) → Tasks 1, 2.
- Q2 (auto-populate filtering) → Task 3.
- Q3 (reveal warning for on_payload) → Task 6.
- Q4, Q5 (FileViewer per-file, context mirroring) → Tasks 10, 11, 12.
- Q11 (left/right constraint) → Task 2.
- Q13 (close button rule) → Task 8.
- Q14, Q15 (persistence rules) → Tasks 4, 5.
- Q17, Q18 (on_context dispatch) → Task 7.
- Q19 (tests) → every task is test-first; regression test for on_context in Task 7.
- Q20 (docs) → Tasks 14–18.
- Task 13 covers LibraryOverview migration.

**Deferred (out of scope, noted):**

- Welcome editor / main-slot empty state UX.
- `on_context` persistence across restart.
- Runtime add-to-bar for left/right slots.
- Declarative `tracks=` kwarg.
- Backward-compat for old `workspace_state.json` (payload-less entries self-heal on next save).
