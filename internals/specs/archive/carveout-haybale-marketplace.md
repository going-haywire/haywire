# Carveout: `haybale-marketplace`

Implementation spec for the carve-out decided in [ADR-0001](../../../docs/adr/0001-haybale-marketplace-carveout.md). Reads as a 10-step sequenced plan: prerequisites earlier, dependent moves later. The whole thing is one PR-sized refactor; no step requires further architectural decisions.

Closes the loop opened by `internals/specs/marketstall-distribution.md` §3.1 and §17, which explicitly defer the carve-out.

---

## 1. Vocabulary

- **Library manager** — the `LibraryManager` class today in `packages/haywire-studio/src/haywire_studio/library_manager.py`. ~600 LOC of uv-subprocess orchestration, registry DTO assembly, dependency intelligence, and (currently) persisted-disabled-state.
- **Marketplace editors** — five files in `barn/haybale-studio/haybale_studio/editors/`: `library_browser_editor.py`, `library_overview_editor.py`, `library_component_editor.py`, `library_marketplace_dialog.py`, `component_source_editor.py`.
- **Persistence helpers** — `apply_persisted_state` / `_persist_disabled_state` on `LibraryManager`, plus `get_disabled_libraries` / `set_disabled_libraries` in `packages/haywire-studio/src/haywire_studio/config.py`.
- **Marketplace state** — `MarketplaceState(AppState)` in `barn/haybale-studio/haybale_studio/state/marketplace_state.py`. Owner of `~/.haywire/db/haybale-marketplace/marketplace.toml` and `<project>/.haywire/marketplace.toml`.
- **`haybale-marketplace`** — the new optional library this spec creates, at `barn/haybale-marketplace/`.

---

## 2. End state (target layout)

```
barn/haybale-marketplace/
├── pyproject.toml
└── haybale_marketplace/
    ├── __init__.py                 # @library(...) declaration, register_components()
    ├── library_manager.py          # moved from haywire_studio/
    ├── state/
    │   ├── __init__.py
    │   ├── library_manager_state.py    # NEW: AppState holder for LibraryManager
    │   ├── library_enable_state.py     # NEW: AppState for runtime user disable/enable toggles
    │   └── marketplace_state.py        # moved from haybale_studio/state/
    └── editors/
        ├── __init__.py
        ├── library_browser_editor.py
        ├── library_overview_editor.py
        ├── library_component_editor.py
        ├── library_marketplace_dialog.py
        └── component_source_editor.py

packages/haywire-core/src/haywire/core/library/
├── decorator_io.py                  # NEW: _set_decorator_list_field (extracted)
└── disabled_state_io.py             # NEW: file reader for bootstrap apply path
```

Removed from `haywire-studio`: `library_manager.py`, the `library_manager` field on `IProjectState`, the `self.library_manager = ...` block in `HaywireApp.setup_shared_services`.

Removed from `haybale-studio`: the five editor files, `state/marketplace_state.py`, and any `__init__.py` exports for them.

---

## 3. Sequenced steps

Each step is mechanical once the prerequisites land. The dependency arrows show what cannot be reordered.

### Step 1 — Extract `_set_decorator_list_field` to core
**Prereq:** none.

Move the function (and `_DECLARABLE_OS_VALUES` + `_apply_os_to_pyproject` if they share helpers) from `packages/haywire-studio/src/haywire_studio/library_manager.py` lines 34–88 to a new file:

```
packages/haywire-core/src/haywire/core/library/decorator_io.py
```

Update the two call sites:

- `packages/haywire-studio/src/haywire_studio/share.py:636` — `from .library_manager import _set_decorator_list_field` → `from haywire.core.library.decorator_io import _set_decorator_list_field`.
- (Inside `library_manager.py` itself — call sites in `update_library_identity` etc. become local-package imports.)

Verify: `uv run ruff check packages/haywire-core/src/haywire/core/library/decorator_io.py packages/haywire-studio/src/haywire_studio/share.py` clean. No test changes; helper is pure regex.

### Step 2 — Trim vestigial `is_installed` check in `create_node_panel`
**Prereq:** none.

`barn/haybale-graph-editor/haybale_graph_editor/panels/context_menu/create_node_panel.py:57`:

```python
# before
if node_info.library is not None and ctx.app.library_manager.is_installed(node_info.library.id):
    ctx.active_component = node_info.identity.registry_key

# after
if node_info.library is not None:
    ctx.active_component = node_info.identity.registry_key
```

The `is_installed` clause was originally guarding `from haybale_studio.editors.library_component_editor import LibraryComponentEditor` inside the body (commit `056039ee`); the import was removed in `329e0cc4` but the guard was left behind. Trim it to remove the only `graph-editor → library_manager` dependency.

Verify: existing tests still pass.

### Step 3 — Move persisted-disabled-state out of `LibraryManager`
**Prereq:** Step 1 in spirit (clean baseline), but technically independent.

Create:

```
packages/haywire-core/src/haywire/core/library/disabled_state_io.py
```

Public API:

```python
def read_disabled_ids(project_dir: Path) -> list[str]: ...
def write_disabled_ids(project_dir: Path, ids: list[str]) -> None: ...
```

Move the body of `get_disabled_libraries` / `set_disabled_libraries` from `packages/haywire-studio/src/haywire_studio/config.py` into this file. The studio's `config.py` keeps its other helpers; if those two were its only callers, drop them.

Then wire the bootstrap **apply** path into the library system. In `packages/haywire-core/src/haywire/core/di/config.py`, between `library_registry.scan_for_libraries()` (~line 363) and `library_registry.enable_all_libraries()` (~line 373):

```python
from haywire.core.library.disabled_state_io import read_disabled_ids
from haywire.core.di.context import get_workspace_root

project_dir = get_workspace_root()
if project_dir:
    for lib_id in read_disabled_ids(Path(project_dir)):
        if lib_id in library_registry.list_names():
            library_registry.disable_library(lib_id)
```

Remove from `LibraryManager`: `apply_persisted_state`, `_persist_disabled_state`. The methods `enable_library` / `disable_library` on the manager either (a) become pass-throughs to the registry + `write_disabled_ids` call, or (b) move off the manager entirely once Step 5 introduces `LibraryEnableState` to own the write path. Pick (b): the manager loses these four methods.

Update `HaywireApp.setup_shared_services` (`packages/haywire-studio/src/haywire_studio/app.py:173`) to drop the `self.library_manager.apply_persisted_state()` call — the library system already did it in step-3 wiring.

Verify: existing persistence tests in `tests/` still pass (likely none under that exact name; spot-check `test_library_manager_marketplace_writes.py` for affected assertions).

### Step 4 — Create `barn/haybale-marketplace/` skeleton
**Prereq:** none (but lands together with Step 5+).

Create the package skeleton:

```
barn/haybale-marketplace/pyproject.toml
barn/haybale-marketplace/haybale_marketplace/__init__.py
barn/haybale-marketplace/haybale_marketplace/editors/__init__.py
barn/haybale-marketplace/haybale_marketplace/state/__init__.py
```

`pyproject.toml` mirrors `haybale-graph-editor`'s shape:

```toml
[project]
name = "haybale-marketplace"
version = "0.0.1"
description = "Library installer + browser editors for Haywire"
requires-python = ">=3.10"
license = {text = "MIT"}
dependencies = [
    "haywire-core~=0.0.1",
    "haywire-studio~=0.0.1",
    "toml",
]

[project.entry-points."haywire.libraries"]
marketplace = "haybale_marketplace:Library"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["haybale_marketplace"]

[tool.uv.sources]
haywire-core = { workspace = true }
haywire-studio = { workspace = true }
haybale-core = { workspace = true }
haybale-studio = { workspace = true }
```

`__init__.py` declares the `@library(...)` and registers `state/` + `editors/` (mirroring `haybale-studio/__init__.py`'s `register_components()` pattern):

```python
@library(
    label="Library Marketplace",
    id="marketplace",
    version=_pkg_version("haybale-marketplace"),
    description="Library installer + browser editors",
    dependencies=[],
    tags=[],
    file_watcher=True,
)
class Library(BaseLibrary):
    def register_components(self):
        base_path = Path(__file__).parent
        self.add_folder_to_registry(str(base_path / "state"), LibraryStateRegistry)
        self.add_folder_to_registry(str(base_path / "editors"), EditorTypeRegistry)
```

State **must** be scanned before editors — same reason as in `haybale-studio/__init__.py:53-67`: editor modules transitively import state classes, and reload-order matters.

### Step 5 — Move `LibraryManager` + introduce `LibraryManagerState` and `LibraryEnableState`
**Prereqs:** Step 1, Step 3, Step 4.

Move `packages/haywire-studio/src/haywire_studio/library_manager.py` to `barn/haybale-marketplace/haybale_marketplace/library_manager.py`. Fix imports (the `_set_decorator_list_field` extraction in Step 1 is the prerequisite that makes the file self-contained).

Create `barn/haybale-marketplace/haybale_marketplace/state/library_manager_state.py`:

```python
from haywire.core.state.base import AppState
from haywire.core.state.decorator import state
from haybale_marketplace.library_manager import LibraryManager


@state(label="Library Manager State")
class LibraryManagerState(AppState):
    """Publishes the LibraryManager for editor consumption.

    Composition over inheritance: the manager is a plain class; this AppState
    is purely the publishing vehicle. See ADR-0001.
    """

    def __init__(self) -> None:
        super().__init__()
        self.manager: LibraryManager | None = None

    def on_enable(self) -> None:
        from haywire.core.di.config import get_library_system
        from haywire.core.di.context import get_workspace_root

        registry = get_library_system().get_library_registry()
        self.manager = LibraryManager(registry, project_dir=get_workspace_root())

    def on_disable(self) -> None:
        self.manager = None
```

Create `barn/haybale-marketplace/haybale_marketplace/state/library_enable_state.py`:

```python
from haywire.core.state.base import AppState
from haywire.core.state.decorator import state
from haywire.core.library.disabled_state_io import write_disabled_ids


@state(label="Library Enable State")
class LibraryEnableState(AppState):
    """Owns the write path for persisted-disabled-state.

    Bootstrap read path lives in haywire.core (see disabled_state_io). This
    AppState handles runtime user toggles from the UI.
    """

    def enable(self, library_id: str) -> None:
        from haywire.core.di.config import get_library_system
        from haywire.core.di.context import get_workspace_root

        registry = get_library_system().get_library_registry()
        registry.enable_library(library_id)
        self._persist(registry, get_workspace_root())

    def disable(self, library_id: str) -> None:
        from haywire.core.di.config import get_library_system
        from haywire.core.di.context import get_workspace_root

        registry = get_library_system().get_library_registry()
        registry.disable_library(library_id)
        self._persist(registry, get_workspace_root())

    @staticmethod
    def _persist(registry, project_dir) -> None:
        if not project_dir:
            return
        disabled = [
            lib_id for lib_id in registry.list_names() if not registry.is_library_enabled(lib_id)
        ]
        write_disabled_ids(Path(project_dir), disabled)
```

### Step 6 — Move the five editor files
**Prereqs:** Step 5.

`git mv barn/haybale-studio/haybale_studio/editors/{library_browser_editor,library_overview_editor,library_component_editor,library_marketplace_dialog,component_source_editor}.py barn/haybale-marketplace/haybale_marketplace/editors/`

Rewrite imports in each:

- `from haybale_studio.editors.library_marketplace_dialog import show_add_source_dialog` (in `library_browser_editor.py:187`) → relative `from .library_marketplace_dialog import show_add_source_dialog`.
- `from haybale_studio.editors.library_overview_editor import LibraryOverviewEditor` (in `library_browser_editor.py:571`) → relative `from .library_overview_editor import LibraryOverviewEditor`.
- Every `ctx.app.library_manager.X` → `ctx.app_data[LibraryManagerState].manager.X` (5 known call sites: `library_browser_editor.py:353, 361`, `library_component_editor.py:93`, `library_overview_editor.py:213`, `component_source_editor.py:198`).
- Every `app.library_manager.enable_library(...) / .disable_library(...)` → `ctx.app_data[LibraryEnableState].enable(...) / .disable(...)`.
- Imports at top of each file: add `from haybale_marketplace.state.library_manager_state import LibraryManagerState` and `from haybale_marketplace.state.library_enable_state import LibraryEnableState` as needed.

Remove the five export lines from `barn/haybale-studio/haybale_studio/editors/__init__.py:4-9`.

### Step 7 — Move `MarketplaceState`
**Prereqs:** Step 6 (or together).

`git mv barn/haybale-studio/haybale_studio/state/marketplace_state.py barn/haybale-marketplace/haybale_marketplace/state/marketplace_state.py`

Rewrite imports in the four call sites (all inside editors that moved in Step 6):

- `library_overview_editor.py:1399` and `library_browser_editor.py:204, 277, 531, 543`: `from haybale_studio.state.marketplace_state import MarketplaceState` → `from haybale_marketplace.state.marketplace_state import MarketplaceState`.

`MarketplaceState` is not exported from `haybale_studio/state/__init__.py`, so no `__init__` edit needed in studio.

### Step 8 — Drop `library_manager` from `IProjectState` + `HaywireApp`
**Prereqs:** Steps 2, 5, 6 (so no live references remain).

In `packages/haywire-core/src/haywire/core/session/protocols.py`:

- Remove the `TYPE_CHECKING` import of `LibraryManager` (line 16).
- Remove the `library_manager: "LibraryManager"` field (line 32).

In `packages/haywire-studio/src/haywire_studio/app.py:165-173`:

- Delete the `# Library manager` block (the `from .library_manager import LibraryManager`, the `self.library_manager = LibraryManager(...)`, and the `self.library_manager.apply_persisted_state()` call — the last one already removed in Step 3).

Delete `packages/haywire-studio/src/haywire_studio/library_manager.py` (the file was moved in Step 5; remove the now-empty original).

### Step 9 — Workspace registration
**Prereqs:** Step 4.

In `pyproject.toml` at the repo root:

- Add `haybale-marketplace = { workspace = true }` to `[tool.uv.sources]` (after line 22, alphabetical).
- Add `"haybale-marketplace"` to the workspace `members` list (after line 43).
- Add `"barn/haybale-marketplace"` to whichever list controls inclusion (after line 59).
- Add `"haybale-marketplace"` to the release/tier-1 list if appropriate (line 97 area — match the existing pattern of which haybales are in tier 1 vs tier 2).

In `packages/haywire-studio/src/haywire_studio/init.py` (the `haywire init` scaffolding): add `haybale-marketplace` to the default `dependencies` list it writes into freshly scaffolded `pyproject.toml` files. This is what makes the marketplace appear in every new project by default.

**Do NOT** add `haybale-marketplace` to `haybale-studio`'s `@library(dependencies=[...])`. The whole point of optionality is that studio works without it.

### Step 10 — Relocate tests
**Prereqs:** Steps 5–7.

Files affected (from `tests/`):

- `test_marketplace_state.py` — moves to `tests/marketplace/test_marketplace_state.py` (or wherever the haybale's tests should live; mirror existing per-haybale conventions). Update import: `from haybale_studio.state.marketplace_state import MarketplaceState` → `from haybale_marketplace.state.marketplace_state import MarketplaceState`.
- `test_library_manager_marketplace_writes.py` — same treatment. Update imports of `LibraryManager`.
- `test_library_browser_os_gating.py`, `test_library_browser_provenance.py` — update imports referencing the moved editors.
- `test_update_library_identity_os.py` — update import of the helper if it now lives in `haywire.core.library.decorator_io`.
- `tests/studio/test_library_overview_on_context.py` — update editor imports.

Add new tests for the freshly-introduced classes:

- `LibraryEnableState.enable/disable` round-trips through `write_disabled_ids`.
- The bootstrap-apply path in `create_library_system_service` honors `read_disabled_ids` (integration test that scans a project with a disabled-state file and verifies the named libraries are disabled after `enable_all_libraries`).
- `LibraryManagerState.on_enable` constructs a non-None `manager` and `on_disable` clears it.

---

## 4. Verification

After all steps, the full quality suite must pass on a clean baseline:

```sh
uv run ruff check .
uv run ruff format --check .
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ \
            barn/haybale-studio/haybale_studio/ barn/haybale-marketplace/haybale_marketplace/ \
            barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ \
            barn/haybale-visiongraph/haybale_visiongraph/ barn/haybale-TEST_A/haybale_test_a/
uv run pytest
```

Manual smoke test: `uv run haywire`, confirm the library browser appears in its slot. Then remove `haybale-marketplace` from the project's `pyproject.toml`, `uv sync`, restart — confirm the studio still launches cleanly with the slot simply empty (no errors, no warnings about missing editors).

---

## 5. Non-goals

- **`haywire share` / `haywire init` relocation.** They stay in `haywire-studio`. Whether they eventually move to a separate `haywire-author` package or into the marketplace haybale is a deferred decision (see ADR-0001 "consequences").
- **CLI install/uninstall.** Today the manager has no CLI exposure beyond the GUI editors. A `haywire install <lib>` command is not introduced by this carve-out; it's a follow-on if the headless-author use case materialises.
- **`LibraryRegistry` refactor.** The registry's existing API is unchanged. Persistence is consulted by the library-system bootstrap (Step 3), not folded into the registry's own methods.
- **Migration of older projects.** Any project with a previously-saved disabled-libraries file: the file format and location are unchanged (`disabled_state_io.py` keeps the existing `<project>/.haywire/...` schema). Existing projects continue to work without intervention.
