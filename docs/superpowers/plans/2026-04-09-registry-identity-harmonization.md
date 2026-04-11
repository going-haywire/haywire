# Registry Identity Harmonization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unify all registry-managed identity classes under `BaseIdentity`, add `class_name`/`module` source fields to every registered class, delete `NodeSourceInfo`, simplify `NodeInfo`, and introduce `LibraryInfo` to replace the duplicate `InstalledLibrary`.

**Architecture:** `BaseIdentity` becomes the single contract for all registry-managed classes: three required fields (`registry_id`, `registry_key`, `label`) plus optional metadata including new `class_name`/`module` source fields. Every decorator fills those fields from `inner_cls`. `EditorIdentity` and `PanelIdentity` are migrated to extend `BaseIdentity`. On the library side, a new `LibraryInfo` frozen dataclass wraps `LibraryIdentity` with runtime state (`enabled`, `install_type`, `distribution_name`), replacing `InstalledLibrary` in `library_manager.py`.

**Tech Stack:** Python 3.11+, dataclasses, haywire DI framework, pytest.

---

## File Map

| File | Change |
|---|---|
| `packages/haywire-core/src/haywire/core/registry/identity.py` | Make `registry_id`, `registry_key`, `label` required; add `class_name`/`module` |
| `packages/haywire-core/src/haywire/core/node/identity.py` | Remove `registry_id`/`registry_key`/`label` defaults (now required via base) |
| `packages/haywire-core/src/haywire/core/node/info.py` | Delete `NodeSourceInfo`; simplify `NodeInfo` to `(identity, library)` |
| `packages/haywire-core/src/haywire/core/node/__init__.py` | Remove `NodeSourceInfo` exports |
| `packages/haywire-core/src/haywire/core/node/factory.py` | Update `_build_node_info()` — remove `source=` arg |
| `packages/haywire-core/src/haywire/core/node/decorator.py` | Add `class_name`/`module` to identity kwargs |
| `packages/haywire-core/src/haywire/core/types/decorator.py` | Add `class_name`/`module` to identity dict |
| `packages/haywire-core/src/haywire/core/settings/decorator.py` | Add `class_name`/`module` to `SettingsClassIdentity(...)` |
| `packages/haywire-core/src/haywire/core/settings/registry.py` | Add `class_name`/`module` to bare `SettingsClassIdentity(...)` construction |
| `packages/haywire-core/src/haywire/core/adapter/base.py` | Add `class_name`/`module` to kwargs before `AdapterIdentity(**kwargs)` |
| `packages/haywire-core/src/haywire/ui/themes/decorator.py` | Add `class_name`/`module` to `ThemeClassIdentity(...)` |
| `packages/haywire-core/src/haywire/ui/widget/decorator.py` | Add `class_name`/`module` to kwargs before `WidgetIdentity(**kwargs)` |
| `packages/haywire-core/src/haywire/ui/skin/decorator.py` | Add `class_name`/`module` to kwargs before `SkinIdentity(**kwargs)` |
| `packages/haywire-core/src/haywire/ui/editor/identity.py` | Extend `BaseIdentity`; drop duplicated fields |
| `packages/haywire-core/src/haywire/ui/editor/decorator.py` | Add `class_name`/`module` to `EditorIdentity(...)` |
| `packages/haywire-core/src/haywire/ui/panel/identity.py` | Extend `BaseIdentity`; drop duplicated fields |
| `packages/haywire-core/src/haywire/ui/panel/decorator.py` | Add `class_name`/`module` to `PanelIdentity(...)` |
| `packages/haywire-core/src/haywire/core/library/info.py` | **New file** — `LibraryInfo` dataclass |
| `packages/haywire-core/src/haywire/core/library/__init__.py` | **New file** — export `LibraryInfo` |
| `packages/haywire-studio/src/haywire_studio/library_manager.py` | Replace `InstalledLibrary` with `LibraryInfo`; update `get_installed_library()` / `list_installed()` |
| `tests/core/test_node/test_decorator.py` | Add assertions for `class_name`/`module` on `class_identity` |
| `tests/core/test_node/test_factory.py` | Assert `NodeInfo` has no `source` field |

---

### Task 1: Harden `BaseIdentity` — required fields + source info

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/registry/identity.py`

- [ ] **Step 1: Update `BaseIdentity`**

```python
# packages/haywire-core/src/haywire/core/registry/identity.py
"""
Base identity class for all registry components
"""

from dataclasses import dataclass


@dataclass
class BaseIdentity:
    """Base identity class containing common fields for all registry components"""

    registry_id: str          # Unique ID within library - set by user or defaulted to class name
    registry_key: str         # Full unique key including library ID - set by decorator
    label: str                # Human-readable display name
    description: str = ""     # Human-readable description
    deprecation_warning: str = ""  # Optional deprecation warning message
    class_name: str = ""      # Python class name - set by decorator
    module: str = ""          # Python module name - set by decorator
```

- [ ] **Step 2: Run tests to check blast radius**

```bash
cd /Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo
uv run pytest -m "not integration" -x -q 2>&1 | head -60
```

Expected: failures in decorators that construct identity subclasses without the three now-required fields. This tells you exactly what needs fixing in subsequent tasks.

- [ ] **Step 3: Commit**

```bash
git add packages/haywire-core/src/haywire/core/registry/identity.py
git commit -m "feat: harden BaseIdentity — required registry_id/key/label, add class_name/module fields"
```

---

### Task 2: Update `@node` decorator — set `class_name`/`module`

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/node/decorator.py`

The decorator already sets `registry_id`, `registry_key`, and `label` in `identity_kwargs` before constructing `NodeIdentity(**identity_kwargs)`. We only need to add the two new fields.

- [ ] **Step 1: Write failing test**

Add to `tests/core/test_node/test_decorator.py`:

```python
def test_node_decorator_sets_source_info():
    """@node sets class_name and module on the identity."""

    @node(label="Source Test")
    class SourceTestNode(BaseNode):
        pass

    assert SourceTestNode.class_identity.class_name == "SourceTestNode"
    assert SourceTestNode.class_identity.module == __name__
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/core/test_node/test_decorator.py::test_node_decorator_sets_source_info -v
```

Expected: FAIL — `class_name` is `""`.

- [ ] **Step 3: Update the decorator**

In `packages/haywire-core/src/haywire/core/node/decorator.py`, in the `decorator(inner_cls)` function, just before the `NodeIdentity(**identity_kwargs)` construction (around line 243), add:

```python
        # Set source info from the class itself
        identity_kwargs["class_name"] = inner_cls.__name__
        identity_kwargs["module"] = inner_cls.__module__

        # Create and attach identity, behavior, and library
        inner_cls.class_identity = NodeIdentity(**identity_kwargs)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/core/test_node/test_decorator.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/node/decorator.py tests/core/test_node/test_decorator.py
git commit -m "feat: @node sets class_name and module on NodeIdentity"
```

---

### Task 3: Update `@type` decorator — set `class_name`/`module`

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/types/decorator.py`

- [ ] **Step 1: Update the decorator**

In `packages/haywire-core/src/haywire/core/types/decorator.py`, in the `decorator(inner_cls)` function, just before `inner_cls.class_identity = DataTypeIdentity(**identity_dict)` (line 162), add:

```python
        # Set source info from the class itself
        identity_dict["class_name"] = inner_cls.__name__
        identity_dict["module"] = inner_cls.__module__

        # Create and attach identity
        inner_cls.class_identity = DataTypeIdentity(**identity_dict)
```

- [ ] **Step 2: Run tests**

```bash
uv run pytest -m "not integration" -x -q 2>&1 | head -40
```

Expected: all pass (no tests currently assert on type identity source fields — we're just confirming no regression).

- [ ] **Step 3: Commit**

```bash
git add packages/haywire-core/src/haywire/core/types/decorator.py
git commit -m "feat: @type sets class_name and module on DataTypeIdentity"
```

---

### Task 4: Update `@settings` decorator and registry — set `class_name`/`module`

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/settings/decorator.py`
- Modify: `packages/haywire-core/src/haywire/core/settings/registry.py`

- [ ] **Step 1: Update `@settings` decorator**

In `packages/haywire-core/src/haywire/core/settings/decorator.py`, the `SettingsClassIdentity(...)` construction (line 81) becomes:

```python
        inner_cls.class_identity = SettingsClassIdentity(
            namespace=full_namespace,
            registry_id=_registry_id,
            registry_key=registry_key,
            label=label or namespace,
            description=description,
            class_name=inner_cls.__name__,
            module=inner_cls.__module__,
        )
```

- [ ] **Step 2: Update bare `SettingsClassIdentity` construction in registry**

In `packages/haywire-core/src/haywire/core/settings/registry.py` around line 260, the bare construction (used when a settings class has no decorator) becomes:

```python
            schema_cls.class_identity = SettingsClassIdentity(
                namespace=ns,
                registry_id=ns,
                registry_key=reg_key(library_id, "settings", ns),
                label=ns,
                class_name=schema_cls.__name__,
                module=schema_cls.__module__,
            )
```

- [ ] **Step 3: Run tests**

```bash
uv run pytest -m "not integration" -x -q 2>&1 | head -40
```

Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add packages/haywire-core/src/haywire/core/settings/decorator.py packages/haywire-core/src/haywire/core/settings/registry.py
git commit -m "feat: @settings sets class_name and module on SettingsClassIdentity"
```

---

### Task 5: Update `@theme`, `@widget`, `@skin`, `@adapter` decorators

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/themes/decorator.py`
- Modify: `packages/haywire-core/src/haywire/ui/widget/decorator.py`
- Modify: `packages/haywire-core/src/haywire/ui/skin/decorator.py`
- Modify: `packages/haywire-core/src/haywire/core/adapter/base.py`

All four follow the same pattern. For `@theme` (explicit kwargs), for `@widget`/`@skin`/`@adapter` (`**kwargs` style).

- [ ] **Step 1: Update `@theme` decorator**

In `packages/haywire-core/src/haywire/ui/themes/decorator.py`, the `ThemeClassIdentity(...)` construction (line 83) becomes:

```python
        inner_cls.class_identity = ThemeClassIdentity(
            registry_id=_registry_id,
            theme_type=theme_type,
            registry_key=_registry_key,
            label=_label,
            description=description,
            class_name=inner_cls.__name__,
            module=inner_cls.__module__,
        )
```

- [ ] **Step 2: Update `@widget` decorator**

In `packages/haywire-core/src/haywire/ui/widget/decorator.py`, just before `inner_cls.class_identity = WidgetIdentity(**kwargs)` (line 93), add:

```python
        kwargs["class_name"] = inner_cls.__name__
        kwargs["module"] = inner_cls.__module__
        inner_cls.class_identity = WidgetIdentity(**kwargs)
```

- [ ] **Step 3: Update `@skin` decorator**

In `packages/haywire-core/src/haywire/ui/skin/decorator.py`, just before `inner_cls.class_identity = SkinIdentity(**kwargs)` (line 79), add:

```python
        kwargs["class_name"] = inner_cls.__name__
        kwargs["module"] = inner_cls.__module__
        inner_cls.class_identity = SkinIdentity(**kwargs)
```

- [ ] **Step 4: Update `@adapter` decorator**

In `packages/haywire-core/src/haywire/core/adapter/base.py`, just before `inner_cls.class_identity = AdapterIdentity(**kwargs)` (line 93), add:

```python
        kwargs["class_name"] = inner_cls.__name__
        kwargs["module"] = inner_cls.__module__
        inner_cls.class_identity = AdapterIdentity(**kwargs)
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest -m "not integration" -x -q 2>&1 | head -40
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/themes/decorator.py \
        packages/haywire-core/src/haywire/ui/widget/decorator.py \
        packages/haywire-core/src/haywire/ui/skin/decorator.py \
        packages/haywire-core/src/haywire/core/adapter/base.py
git commit -m "feat: @theme/@widget/@skin/@adapter set class_name and module on identity"
```

---

### Task 6: Migrate `EditorIdentity` to extend `BaseIdentity` + update `@editor`

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/editor/identity.py`
- Modify: `packages/haywire-core/src/haywire/ui/editor/decorator.py`

- [ ] **Step 1: Update `EditorIdentity`**

Replace `packages/haywire-core/src/haywire/ui/editor/identity.py` entirely:

```python
# packages/haywire-core/src/haywire/ui/editor/identity.py
"""
EditorIdentity dataclass for the Haywire editor type system.
"""

from dataclasses import dataclass

from haywire.core.registry.identity import BaseIdentity


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
            One of: 'left', 'main', 'right', 'bottom'.
    """

    icon: str = "extension"
    default_slot: str = "main"
```

- [ ] **Step 2: Update `@editor` decorator**

In `packages/haywire-core/src/haywire/ui/editor/decorator.py`, the `EditorIdentity(...)` construction (line 73) becomes:

```python
        inner_cls.class_identity = EditorIdentity(
            registry_id=_registry_id,
            registry_key=_registry_key,
            label=_label,
            icon=icon,
            default_slot=default_slot,
            description=description,
            class_name=inner_cls.__name__,
            module=inner_cls.__module__,
        )
```

- [ ] **Step 3: Run tests**

```bash
uv run pytest tests/ui/test_editor_registry.py -v
uv run pytest -m "not integration" -x -q 2>&1 | head -40
```

Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/editor/identity.py \
        packages/haywire-core/src/haywire/ui/editor/decorator.py
git commit -m "feat: EditorIdentity extends BaseIdentity; @editor sets class_name/module"
```

---

### Task 7: Migrate `PanelIdentity` to extend `BaseIdentity` + update `@panel`

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/panel/identity.py`
- Modify: `packages/haywire-core/src/haywire/ui/panel/decorator.py`

- [ ] **Step 1: Update `PanelIdentity`**

Replace `packages/haywire-core/src/haywire/ui/panel/identity.py` entirely:

```python
# packages/haywire-core/src/haywire/ui/panel/identity.py
"""
PanelIdentity dataclass for the Haywire panel system.
"""

from dataclasses import dataclass, field
from typing import Optional

from haywire.core.registry.identity import BaseIdentity


@dataclass
class PanelIdentity(BaseIdentity):
    """
    Metadata attached to a panel class by the @panel decorator.

    Set once at class-definition time; survives hot-reload.

    Inherits from BaseIdentity:
        registry_id:  Short unique ID, e.g. 'node_transform'.
        registry_key: Fully-qualified key; set by decorator via reg_key().
        label:        Display label shown in the panel header.
        description:  Human-readable description.
        class_name:   Python class name — set by decorator.
        module:       Python module name — set by decorator.

    Additional attributes:
        editor_keys:  One or more editor registry keys this panel belongs to.
        scopes:       One or more scope IDs this panel appears under.
        icon:         Optional Material Design icon name.
        order:        Sort priority (lower = higher in the panel list).
        default_open: Whether the panel starts expanded.
    """

    editor_keys: list[str] = field(default_factory=list)
    scopes: list[str] = field(default_factory=list)
    icon: Optional[str] = None
    order: int = 100
    default_open: bool = True
```

- [ ] **Step 2: Update `@panel` decorator**

In `packages/haywire-core/src/haywire/ui/panel/decorator.py`, the `PanelIdentity(...)` construction (line 82) becomes:

```python
        inner_cls.class_identity = PanelIdentity(
            registry_id=_registry_id,
            registry_key=_registry_key,
            label=_label,
            editor_keys=_editors,
            scopes=_scopes,
            icon=icon,
            order=order,
            default_open=default_open,
            description=description,
            class_name=inner_cls.__name__,
            module=inner_cls.__module__,
        )
```

- [ ] **Step 3: Run tests**

```bash
uv run pytest tests/ui/test_panel_registry.py -v
uv run pytest -m "not integration" -x -q 2>&1 | head -40
```

Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/panel/identity.py \
        packages/haywire-core/src/haywire/ui/panel/decorator.py
git commit -m "feat: PanelIdentity extends BaseIdentity; @panel sets class_name/module"
```

---

### Task 8: Delete `NodeSourceInfo`, simplify `NodeInfo`

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/node/info.py`
- Modify: `packages/haywire-core/src/haywire/core/node/__init__.py`
- Modify: `packages/haywire-core/src/haywire/core/node/factory.py`
- Test: `tests/core/test_node/test_factory.py`

- [ ] **Step 1: Write failing test**

Add to `tests/core/test_node/test_factory.py`:

```python
def test_node_info_has_no_source_field():
    """NodeInfo must not have a 'source' field after NodeSourceInfo removal."""
    from haywire.core.node.info import NodeInfo
    import dataclasses
    field_names = {f.name for f in dataclasses.fields(NodeInfo)}
    assert "source" not in field_names
    assert "identity" in field_names
    assert "library" in field_names
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/core/test_node/test_factory.py::TestNodeFactory::test_node_info_has_no_source_field -v 2>&1 || \
uv run pytest tests/core/test_node/test_factory.py -k "test_node_info_has_no_source_field" -v
```

Expected: FAIL — `source` field exists.

- [ ] **Step 3: Update `node/info.py`**

Replace `packages/haywire-core/src/haywire/core/node/info.py` entirely:

```python
from dataclasses import dataclass
from typing import Optional

from haywire.core.library.identity import LibraryIdentity
from .identity import NodeIdentity


@dataclass(frozen=True)
class NodeInfo:
    """Composed node metadata used by NodeFactory discovery APIs."""

    identity: NodeIdentity
    library: Optional[LibraryIdentity]
```

- [ ] **Step 4: Update `node/__init__.py`**

In `packages/haywire-core/src/haywire/core/node/__init__.py`, remove all references to `NodeSourceInfo`:

- Remove the import line: `from .info import NodeInfo, NodeSourceInfo`
- Replace with: `from .info import NodeInfo`
- Remove `"NodeSourceInfo"` from `__all__`

- [ ] **Step 5: Update `NodeFactory._build_node_info()`**

In `packages/haywire-core/src/haywire/core/node/factory.py`, update the import at line 14:

```python
from .info import NodeInfo
```

And update `_build_node_info()` (lines 210–224):

```python
    def _build_node_info(self, registry_key: str) -> Optional[NodeInfo]:
        """Build composed node metadata from class identity and library information."""
        node_class = self.node_registry.get(registry_key)
        if node_class is None:
            return None

        identity = node_class.class_identity
        library_identity = getattr(node_class, "class_library", None)

        return NodeInfo(
            identity=identity,
            library=library_identity,
        )
```

- [ ] **Step 6: Run tests**

```bash
uv run pytest tests/core/test_node/ -v
uv run pytest -m "not integration" -x -q 2>&1 | head -40
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add packages/haywire-core/src/haywire/core/node/info.py \
        packages/haywire-core/src/haywire/core/node/__init__.py \
        packages/haywire-core/src/haywire/core/node/factory.py \
        tests/core/test_node/test_factory.py
git commit -m "feat: delete NodeSourceInfo, simplify NodeInfo to (identity, library)"
```

---

### Task 9: Add `LibraryInfo` dataclass

**Files:**
- Create: `packages/haywire-core/src/haywire/core/library/info.py`
- Create: `packages/haywire-core/src/haywire/core/library/__init__.py`

- [ ] **Step 1: Create `library/info.py`**

```python
# packages/haywire-core/src/haywire/core/library/info.py
"""
LibraryInfo — composed runtime snapshot for an installed library.

Combines the library's declared identity with runtime state discovered
during scanning: enabled status, install type, and pip distribution name.
"""

from dataclasses import dataclass

from .identity import LibraryIdentity
from .discovery import InstallType


@dataclass(frozen=True)
class LibraryInfo:
    """Runtime snapshot of an installed library.

    Attributes:
        identity:          Declared metadata from the @library decorator.
        enabled:           Whether the library is currently enabled.
        install_type:      How the library was installed (REGULAR, EDITABLE, FOLDER).
        distribution_name: Pip package name, e.g. 'haybale-visiongraph'. Empty string
                           if installed as a folder (no pip distribution).
    """

    identity: LibraryIdentity
    enabled: bool
    install_type: InstallType
    distribution_name: str
```

- [ ] **Step 2: Create `library/__init__.py`**

Check whether this file already exists:

```bash
ls packages/haywire-core/src/haywire/core/library/__init__.py 2>/dev/null || echo "MISSING"
```

If it is missing, create it. If it exists, add the export to it. The file should export `LibraryInfo`:

```python
from .info import LibraryInfo

__all__ = ["LibraryInfo"]
```

If the file already has content, append the import and add `"LibraryInfo"` to `__all__`.

- [ ] **Step 3: Verify import works**

```bash
uv run python -c "from haywire.core.library.info import LibraryInfo; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add packages/haywire-core/src/haywire/core/library/info.py \
        packages/haywire-core/src/haywire/core/library/__init__.py
git commit -m "feat: add LibraryInfo dataclass (identity + runtime state)"
```

---

### Task 10: Replace `InstalledLibrary` with `LibraryInfo` in `library_manager.py`

**Files:**
- Modify: `packages/haywire-studio/src/haywire_studio/library_manager.py`

- [ ] **Step 1: Update imports**

At the top of `library_manager.py`, remove the `InstalledLibrary` dataclass definition (lines 71–88) and add the import:

```python
from haywire.core.library.info import LibraryInfo
from haywire.core.library.discovery import InstallType
```

Remove the `@dataclass class InstalledLibrary:` block entirely.

- [ ] **Step 2: Update `get_installed_library()` return type and body**

Replace the method (lines 423–445):

```python
    def get_installed_library(self, library_id: str) -> LibraryInfo:
        """Return summary information for one installed library."""
        identity = self.registry.get_library_identity(library_id)
        install_type = self.registry.get_library_install_type(library_id)
        enabled = self.registry.is_library_enabled(library_id)
        dist_name = self.registry.get_library_distribution_name(library_id)

        return LibraryInfo(
            identity=identity,
            enabled=enabled,
            install_type=install_type or InstallType.FOLDER,
            distribution_name=dist_name or "",
        )
```

- [ ] **Step 3: Update `list_installed()` return type**

```python
    def list_installed(self) -> list[LibraryInfo]:
        """List all discovered libraries with their status."""
        libraries = []
        for lib_id in self.registry.list_names():
            libraries.append(self.get_installed_library(lib_id))
        return libraries
```

- [ ] **Step 4: Update all callsites within `library_manager.py` that use `InstalledLibrary` fields**

Search for any remaining uses of the old field names within `library_manager.py`:

```bash
grep -n "\.library_id\|\.source_path\|\.distribution_name\|InstalledLibrary" \
  packages/haywire-studio/src/haywire_studio/library_manager.py
```

The only internal use is in `rename_project_library_streaming()` at line 258:
```python
if any(lib.distribution_name.lower() == new_lib_name.lower() for lib in installed):
```

This still works — `LibraryInfo` also has `distribution_name`. No change needed here.

- [ ] **Step 5: Run tests**

```bash
uv run pytest -m "not integration" -x -q 2>&1 | head -40
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add packages/haywire-studio/src/haywire_studio/library_manager.py
git commit -m "feat: replace InstalledLibrary with LibraryInfo in library_manager"
```

---

### Task 11: Full test suite + final verification

- [ ] **Step 1: Run the full test suite**

```bash
uv run pytest -x -q 2>&1 | tail -20
```

Expected: all tests pass, no failures.

- [ ] **Step 2: Verify source info on a node at runtime**

```bash
uv run python -c "
from haywire.core.node import node, BaseNode

@node(label='Verify')
class VerifyNode(BaseNode):
    pass

i = VerifyNode.class_identity
print('class_name:', i.class_name)
print('module:', i.module)
print('registry_id:', i.registry_id)
print('label:', i.label)
assert i.class_name == 'VerifyNode'
assert i.module == '__main__'
print('OK')
"
```

Expected:
```
class_name: VerifyNode
module: __main__
registry_id: VerifyNode
label: Verify
OK
```

- [ ] **Step 3: Verify `NodeInfo` has no source field**

```bash
uv run python -c "
from haywire.core.node.info import NodeInfo
import dataclasses
fields = {f.name for f in dataclasses.fields(NodeInfo)}
print('NodeInfo fields:', fields)
assert 'source' not in fields
assert fields == {'identity', 'library'}
print('OK')
"
```

Expected: `NodeInfo fields: {'identity', 'library'}` then `OK`.

- [ ] **Step 4: Verify `LibraryInfo` import**

```bash
uv run python -c "
from haywire.core.library.info import LibraryInfo
import dataclasses
fields = {f.name for f in dataclasses.fields(LibraryInfo)}
print('LibraryInfo fields:', fields)
assert fields == {'identity', 'enabled', 'install_type', 'distribution_name'}
print('OK')
"
```

Expected: `LibraryInfo fields: {'identity', 'enabled', 'install_type', 'distribution_name'}` then `OK`.

- [ ] **Step 5: Final commit if any cleanup needed**

```bash
git add -p  # review and stage any remaining changes
git commit -m "chore: registry identity harmonization — final cleanup"
```
