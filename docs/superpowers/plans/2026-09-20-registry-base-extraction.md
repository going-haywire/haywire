# Registry Base Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract the kind-agnostic registry plumbing out of `BaseRegistry` into a new `ComponentRegistry` base, so a future file-backed `DocumentRegistry` can inherit it without dragging module/`sys.modules` reload machinery along.

**Architecture:** Insert one class between `HotReloadRegistry` and `BaseRegistry`. `ComponentRegistry` owns the storage dict, the folder→library map, the lifecycle-event queue, both subscriber lists and the `get`/`has`/`list_*`/last-event readers. `BaseRegistry` keeps everything module-centric: `FolderScanMixin`, `importlib`/`sys.modules` reload, `DependencyGraph`, rollback snapshots, and the `.py` filter in `event_dispatcher`. This is step 1 of [03-macro.md](03-macro.md) (decision 3) and is a **pure move** — no behaviour change, no macro code.

**Tech Stack:** Python 3.12, mypy (strict-ish, per repo config), ruff (line-length 109), pytest.

## Global Constraints

- **No behaviour change.** Every moved method keeps its body byte-for-byte unless a step says otherwise. This is the whole point of the step; a "small improvement" made in passing is out of scope and hides a regression.
- **No macro code.** No `DocumentRegistry`, no `MacroRegistry`, no `.hwm`, no kind-map entries. Those are steps 2–3 of 03-macro.md.
- **Full registry suite green:** `uv run pytest tests/core/test_libraries/ tests/core/test_node/test_factory.py tests/ui/test_panel_registry.py tests/ui/test_editor_registry.py tests/ui/test_theme_registry.py -q` must pass at every commit.
- **Gate before the final commit:** `uv run ruff check .` AND `uv run ruff format --check .` (both — CI runs both), `uv run mypy` over the repo's configured paths, and `uv run pytest -m "not browser and not perf"`.
- **Baseline is already established and clean** on `registry/` + `library/`: ruff 0 errors, format 0 drift, mypy "Success: no issues found in 21 source files" (only `annotation-unchecked` notes, which are pre-existing and not errors). Anything new is yours.
- **Generic parameter stays `T`**, bound to `RegisteredClass`. `ComponentRegistry` is `Generic[T]`; `BaseRegistry(ComponentRegistry[T])` re-parametrizes rather than re-declaring the bound.
- **`event_dispatcher` stays one method on `HotReloadRegistry`** — `_HaybaleTomlWatcher` implements that interface alone and must not inherit the new plumbing.
- Docstrings follow [.claude/rules/python-docs.md](../../../.claude/rules/python-docs.md): reST, no history ("used to", "moved from"), no ALL-CAPS emphasis.

---

## File Structure

| File | Responsibility after this step |
|---|---|
| `packages/haywire-core/src/haywire/core/registry/component.py` | **Create.** `ComponentRegistry` — kind-agnostic storage, folder bookkeeping, lifecycle queue, subscribers, read API. |
| `packages/haywire-core/src/haywire/core/registry/base.py` | **Modify.** Keeps `FileEventType`, `FileChangeEvent`, `HotReloadRegistry`, `RegisteredClass`, `T`; `BaseRegistry` narrows to module-backed reload. |
| `packages/haywire-core/src/haywire/core/library/base.py` | **Modify.** `BaseLibrary.registries` / `_registry_folders` key on `ComponentRegistry`. |
| `packages/haywire-core/src/haywire/core/library/registry.py` | **Modify.** `_class_registries` / `add_class_registry` widen to `ComponentRegistry`. |
| `packages/haywire-core/src/haywire/core/library/file_watcher.py` | **Verify only.** Already types on `HotReloadRegistry`; the plan asserts no change is needed. |
| `tests/core/test_registry/test_component_registry.py` | **Create.** Guards the contract split: what lives on the base vs. what stays module-specific. |

`RegisteredClass`, `T`, `FileChangeEvent`, `FileEventType` and `HotReloadRegistry` **stay in `base.py`**. Moving them would churn ~15 import sites for no gain, and `component.py` can import them.

**Import direction:** `component.py` imports from `base.py`. `base.py` then imports `ComponentRegistry` from `component.py` — a cycle. Task 1 resolves this by putting the shared vocabulary in a third module. See Task 1 Step 1.

---

## Task 1: Break the import cycle — move shared vocabulary to `events.py`

`component.py` needs `FileChangeEvent`/`HotReloadRegistry`/`RegisteredClass`/`T`; `base.py` needs `ComponentRegistry`. Without this task the two modules import each other.

**Files:**
- Create: `packages/haywire-core/src/haywire/core/registry/events.py`
- Modify: `packages/haywire-core/src/haywire/core/registry/base.py:1-77`
- Test: `tests/core/test_registry/test_component_registry.py` (created here, extended in Task 3)

**Interfaces:**
- Consumes: nothing (first task).
- Produces: `haywire.core.registry.events` exporting `FileEventType`, `FileChangeEvent`, `HotReloadRegistry`, `RegisteredClass`, `T`. `base.py` re-exports all five under their existing names so **every existing import site keeps working unchanged**.

- [ ] **Step 1: Create `events.py` by moving lines 24-76 of `base.py` verbatim**

Create `packages/haywire-core/src/haywire/core/registry/events.py`:

```python
"""File-change vocabulary and the structural bounds every registry shares.

Separate from ``base`` so a registry module may depend on this vocabulary
without importing the module-reload machinery.
"""

from typing import Protocol, TypeVar
from abc import ABC, abstractmethod
from dataclasses import dataclass, field as dc_field
from enum import Enum

from ..library.identity import LibraryIdentity
from .identity import BaseIdentity


class FileEventType(Enum):
    """Enum for file change event types"""

    CREATED = "creation"
    MODIFIED = "modification"
    DELETED = "deletion"
    DETECTED = "detection"


@dataclass
class FileChangeEvent:
    """Represents a file change event"""

    file_path: str
    event_type: FileEventType  # 'created', 'modified', 'deleted', 'detected'
    library_identity: LibraryIdentity
    timestamp: float
    reloaded_modules: set[str] = dc_field(default_factory=set)
    """Track modules already reloaded in this event chain"""
    dependency_event: bool = False  # Whether this event is due to dependency reload
    """indicates if this event is a result of a dependency change (detected by a different registry)"""


class HotReloadRegistry(ABC):
    """Abstract base class for registries that support hot-reloading"""

    @abstractmethod
    def event_dispatcher(self, event: FileChangeEvent):
        """Handle creation of a module"""
        pass


class RegisteredClass(Protocol):
    """Structural bound for registry element types.

    The registry contract: every managed class carries both a
    ``class_identity`` (its registry metadata) and a ``class_library`` (the
    owning library, used for hot-reload) — set by its component decorator.

    Both are typed as read-only properties so concrete element classes may
    declare them as ``ClassVar`` of narrower subtypes (``NodeIdentity``,
    ``AdapterIdentity``, ...). A writable Protocol member (plain annotation
    or ``ClassVar``) would be invariant and reject them.
    """

    @property
    def class_identity(self) -> BaseIdentity: ...

    @property
    def class_library(self) -> LibraryIdentity: ...


T = TypeVar("T", bound=RegisteredClass)
```

- [ ] **Step 2: Delete lines 24-76 from `base.py` and re-export from `events.py`**

In `base.py`, delete the `FileEventType`, `FileChangeEvent`, `HotReloadRegistry`, `RegisteredClass` class bodies and the `T = TypeVar(...)` line. Replace the import block at the top. The file currently opens:

```python
from typing import Dict, Any, Generic, Optional, Protocol, Type, TypeVar, List, Tuple, cast
from abc import ABC, abstractmethod
from dataclasses import dataclass, field as dc_field
from enum import Enum
import importlib
from pathlib import Path
import sys
import logging

from ..errors import HaywireException
from ..library.identity import LibraryIdentity
from .dependency_graph import DependencyGraph
from .identity import BaseIdentity
from .folder_scan import FolderScanMixin
from .lifecycle_event import LifeCycleEvent, LifeCycleEventType, LifeCycleBatchCallback
```

Make it:

```python
from typing import Dict, Any, Optional, Type, List, cast
from abc import abstractmethod
import importlib
from pathlib import Path
import sys
import logging

from ..errors import HaywireException
from ..library.identity import LibraryIdentity
from .dependency_graph import DependencyGraph
from .identity import BaseIdentity
from .events import (
    FileChangeEvent,
    FileEventType,
    HotReloadRegistry,
    RegisteredClass,
    T,
)
from .folder_scan import FolderScanMixin
from .lifecycle_event import LifeCycleEvent, LifeCycleEventType, LifeCycleBatchCallback

__all__ = [
    "BaseRegistry",
    "FileChangeEvent",
    "FileEventType",
    "HotReloadRegistry",
    "RegisteredClass",
    "T",
]
```

`__all__` is what keeps `from ..registry.base import HotReloadRegistry, FileChangeEvent, FileEventType` (file_watcher.py:12) and the ~15 other sites working, and stops ruff flagging the re-exports as unused imports.

Note `Generic`, `Protocol`, `TypeVar`, `ABC`, `dataclass`, `dc_field`, `Enum`, `Tuple` leave the import list — they were only used by the moved code. `Generic` returns in Task 2.

- [ ] **Step 3: Run the registry suite — it must be green with zero source changes elsewhere**

Run:
```bash
uv run pytest tests/core/test_libraries/ tests/core/test_node/test_factory.py -q
```
Expected: PASS (same count as baseline). This proves the re-export is transparent.

- [ ] **Step 4: Run ruff and mypy**

Run:
```bash
uv run ruff check packages/haywire-core/src/haywire/core/registry/
uv run ruff format --check packages/haywire-core/src/haywire/core/registry/
uv run mypy packages/haywire-core/src/haywire/core/registry/ packages/haywire-core/src/haywire/core/library/
```
Expected: "All checks passed!", "N files already formatted", "Success: no issues found".

If ruff reports `F401` on a re-exported name, the `__all__` entry for it is missing — add it rather than deleting the import.

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/registry/events.py packages/haywire-core/src/haywire/core/registry/base.py
git commit -m "refactor(registry) move file-change vocabulary to events.py

Breaks the import cycle ComponentRegistry would otherwise create between
base and the new component module. base re-exports every name, so no
import site changes.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 2: Create `ComponentRegistry` and reparent `BaseRegistry`

**Files:**
- Create: `packages/haywire-core/src/haywire/core/registry/component.py`
- Modify: `packages/haywire-core/src/haywire/core/registry/base.py` (`BaseRegistry.__init__`, class header; delete the moved methods)

**Interfaces:**
- Consumes: `haywire.core.registry.events` — `FileChangeEvent`, `HotReloadRegistry`, `RegisteredClass`, `T` (Task 1).
- Produces: `ComponentRegistry(HotReloadRegistry, Generic[T])` with:
  - `__init__(self) -> None`
  - `get(self, registry_key: str) -> type[T] | None`
  - `has(self, registry_key: str) -> bool`
  - `list_names(self) -> list[str]`
  - `list_visible_names(self) -> list[str]`
  - `get_lastevent(self, registry_key: str) -> LifeCycleEvent | None`
  - `add_folder(self, folder_path: str, library_identity: LibraryIdentity, exclude_patterns: Optional[list[str]] = None)` — **abstract**
  - `remove_folder(self, folder_path: str, library_identity: LibraryIdentity, exclude_patterns: Optional[list[str]] = None)` — **abstract**
  - `add_batch_event_subscriber(self, callback: LifeCycleBatchCallback) -> None`
  - `remove_batch_event_subscriber(self, callback: LifeCycleBatchCallback) -> None`
  - `add_registry_subscriber(self, registry: HotReloadRegistry) -> None`
  - `remove_registry_subscriber(self, registry: HotReloadRegistry) -> None`
  - `_queue_lifecycle_event(self, event: LifeCycleEvent) -> None`
  - `_notify_batch_event_subscribers(self) -> None`
  - `_notify_registry_subscribers(self, event: FileChangeEvent) -> None`
  - `_register(...)` / `_unregister(...)` stay on `BaseRegistry` — they write `_regkey_to_class_name` and `_module_to_registry_keys`, which are module bookkeeping.
  - Attributes owned: `_classes`, `_folder_to_library`, `_regkey_to_last_lifecycle_event`, `_lifecycle_event_queue`, `_registry_subscribers`, `_batch_event_subscribers`, `logger`.

- [ ] **Step 1: Create `component.py`**

```python
"""The registry contract shared by class-backed and file-backed registries.

``ComponentRegistry`` owns what every registry does regardless of what it
stores: the key→element map, which library claimed which folder, the
lifecycle-event queue and its two subscriber lists, and the read API
consumers use. Module reload, ``sys.modules`` and ``importlib`` belong to
``BaseRegistry`` alone.
"""

from typing import Dict, Generic, List, Optional, cast
from abc import abstractmethod
import logging

from ..library.identity import LibraryIdentity
from .events import FileChangeEvent, HotReloadRegistry, T
from .identity import BaseIdentity
from .lifecycle_event import LifeCycleEvent, LifeCycleBatchCallback

logger = logging.getLogger(__name__)


class ComponentRegistry(HotReloadRegistry, Generic[T]):
    """Storage, folder bookkeeping and lifecycle notification for one component kind.

    Generic over ``T``, the element type a concrete registry stores. A
    subclass decides where elements come from: ``BaseRegistry`` imports them
    from Python modules, a document registry parses them from files.
    """

    def __init__(self):
        self._classes: Dict[str, type[T]] = {}  # registry_key -> class

        # stores the last life-cycle event for each class that has been processed
        # it keeps track of what was the last event type for each class,
        # even those that have been removed
        # registry_key -> event
        self._regkey_to_last_lifecycle_event: Dict[str, LifeCycleEvent] = {}

        # folder_path -> library_identity
        self._folder_to_library: Dict[str, LibraryIdentity] = {}

        # Queue of events to process after reload
        self._lifecycle_event_queue: List[LifeCycleEvent] = []

        # Other registries that depend on this one
        self._registry_subscribers: List[HotReloadRegistry] = []
        # Direct consumers (factories, etc.)
        self._batch_event_subscribers: List[LifeCycleBatchCallback] = []

        self.logger = logging.getLogger(__name__)

    # ============================================================================
    # Folder registration
    # ============================================================================

    @abstractmethod
    def add_folder(
        self,
        folder_path: str,
        library_identity: LibraryIdentity,
        exclude_patterns: Optional[list[str]] = None,
    ):
        """Scan ``folder_path`` and register everything it holds.

        Called by the library when it is enabled.

        Args:
            folder_path: Path to the folder to scan.
            exclude_patterns: Filename patterns to exclude.
        """
        pass

    @abstractmethod
    def remove_folder(
        self,
        folder_path: str,
        library_identity: LibraryIdentity,
        exclude_patterns: Optional[list[str]] = None,
    ):
        """Unregister everything ``folder_path`` contributed.

        Called by the library when it is disabled.

        Args:
            folder_path: Path to the folder to remove.
            exclude_patterns: Filename patterns to exclude.
        """
        pass

    # ============================================================================
    # Read API
    # ============================================================================

    def get(self, registry_key: str) -> type[T] | None:
        """Retrieve a registered class by its haywire registry_key"""
        return self._classes.get(registry_key)

    def has(self, registry_key: str) -> bool:
        """Check if a class is registered"""
        return registry_key in self._classes

    def list_names(self) -> list[str]:
        """List all classes registry_keys in this registry."""
        return list(self._classes.keys())

    def list_visible_names(self) -> list[str]:
        """List registry_keys of non-hidden classes.
        for those offered as a choice in author-facing selection UIs (menus, pickers).
        """
        return [
            key for key, cls in self._classes.items() if not cast(BaseIdentity, cls.class_identity).hidden
        ]

    def get_lastevent(self, registry_key: str) -> LifeCycleEvent | None:
        """Return the most recent lifecycle event for ``registry_key``, or ``None``.

        Survives removal: a key unregistered by a failed reload still reports
        the event that removed it.
        """
        return self._regkey_to_last_lifecycle_event.get(registry_key)

    # ============================================================================
    # Hot Reload Callback Management
    # ============================================================================

    def add_batch_event_subscriber(self, callback: LifeCycleBatchCallback) -> None:
        """
        Register a customer callback to be notified of hot reload events.

        Customer callbacks are invoked immediately after a class is reloaded,
        added, or removed. They receive a LifeCycleEvent batch with complete context.

        Args:
            callback: Function to call on life cycle events with signature:
                     (event: List[LifeCycleEvent]) -> None
        """
        if callback not in self._batch_event_subscribers:
            self._batch_event_subscribers.append(callback)
            self.logger.debug(
                f"Registered customer callback: {getattr(callback, '__name__', repr(callback))}"
            )

    def remove_batch_event_subscriber(self, callback: LifeCycleBatchCallback) -> None:
        """
        Unregister a customer callback.

        Args:
            callback: The callback to remove
        """
        if callback in self._batch_event_subscribers:
            self._batch_event_subscribers.remove(callback)
            self.logger.debug(f"Removed customer callback: {getattr(callback, '__name__', repr(callback))}")

    def add_registry_subscriber(self, registry: HotReloadRegistry) -> None:
        """
        Register another registry to be notified of hot reload events.

        Registry subscribers are invoked after customer callbacks and receive
        complete FileChangeEvent information for their own processing.

        Args:
            registry: Another registry that needs to react to changes in this registry
        """
        if registry not in self._registry_subscribers:
            self._registry_subscribers.append(registry)
            self.logger.debug(
                f"{self.__class__.__name__}: Registered registry subscriber: {registry.__class__.__name__}"
            )

    def remove_registry_subscriber(self, registry: HotReloadRegistry) -> None:
        """
        Unregister a registry subscriber.

        Args:
            registry: The registry to unsubscribe
        """
        if registry in self._registry_subscribers:
            self._registry_subscribers.remove(registry)
            self.logger.debug(f"Removed registry subscriber: {registry.__class__.__name__}")

    def _queue_lifecycle_event(self, event: LifeCycleEvent) -> None:
        """
        Queues a hot reload event.

        This method is called internally during hot reload operations.
        Errors in individual callbacks are logged but don't stop generation of events.

        Args:
            event: The hot reload event with complete context
        """
        self._regkey_to_last_lifecycle_event[event.registry_key] = event

        self._lifecycle_event_queue.append(event)

    def _notify_batch_event_subscribers(self) -> None:
        """
        Batch notify all customer callbacks about hot reload events.

        This method is called internally during hot reload operations.

        Callbacks receive the complete event information.:

        """

        for callback in self._batch_event_subscribers[:]:
            callback(self._lifecycle_event_queue)

        self._lifecycle_event_queue.clear()

    def _notify_registry_subscribers(self, event: FileChangeEvent) -> None:
        """
        Notify all registry subscribers about a hot reload event.

        This method is called after customer callbacks have been notified.
        Registry subscribers receive the complete event information and can
        perform their own dependency analysis and reloading.

        Args:
            event: The file change event that triggered the reload
        """
        for registry in self._registry_subscribers[:]:
            try:
                registry.event_dispatcher(event)
            except Exception as e:
                self.logger.error(
                    f"Registry subscriber '{registry.__class__.__name__}' "
                    f"callback failed for {event.file_path}: {e}",
                    exc_info=True,
                )
```

- [ ] **Step 2: Reparent `BaseRegistry` and trim its `__init__`**

In `base.py`, change the class header (line 79):

```python
class BaseRegistry(HotReloadRegistry, FolderScanMixin, Generic[T]):
```

to:

```python
class BaseRegistry(ComponentRegistry[T], FolderScanMixin):
```

Add `from .component import ComponentRegistry` to the import block, and drop `Generic` from the `typing` import (it moved to `component.py`; `ComponentRegistry[T]` supplies the parametrization).

Replace `BaseRegistry.__init__` (lines 88-118) with:

```python
    def __init__(self):
        super().__init__()

        self._dependency_graph = DependencyGraph()  # For hot-reload dependency tracking

        # BaseClassRegistry specific attributes
        self._regkey_to_class_name: Dict[str, str] = {}  # registry_key -> class name
        # module -> list of registry_keys
        self._module_to_registry_keys: Dict[str, list[str]] = {}

        self._dependency_module_lifecycle_events: Dict[str, LifeCycleEvent] = {}
        """Track errors during dependency module reloads and store them by registry_key"""
```

`_classes`, `_regkey_to_last_lifecycle_event`, `_folder_to_library`, `_lifecycle_event_queue`, `_registry_subscribers`, `_batch_event_subscribers` and `self.logger` now come from `super().__init__()`. Do not re-assign them — a second assignment would silently shadow the base's and is exactly the bug this step can introduce.

- [ ] **Step 3: Delete the moved method bodies from `BaseRegistry`**

Delete these methods from `base.py` — they are now inherited verbatim from `ComponentRegistry`:

`get`, `has`, `list_names`, `list_visible_names` (lines 141-159), and `add_batch_event_subscriber`, `remove_batch_event_subscriber`, `add_registry_subscriber`, `remove_registry_subscriber`, `_queue_lifecycle_event`, `_notify_batch_event_subscribers`, `_notify_registry_subscribers` (lines 969-1072).

**Keep** on `BaseRegistry`: `_class_filter`, `_register_class`, `_unregister_class` (abstract), `_register`, `_unregister`, `add_folder`, `remove_folder` (concrete overrides of the new abstracts), `event_dispatcher`, `_on_creation`, `_on_change`, `_reload_unmanaged_module`, `_reload_managed_module`, `_is_demoted_component`, `_on_delete`, `_create_rollback_snapshot`, `_rollback_snapshot`, `_get_tracking_scopes`.

- [ ] **Step 4: Run the registry suite**

Run:
```bash
uv run pytest tests/core/test_libraries/ tests/core/test_node/test_factory.py tests/ui/test_panel_registry.py tests/ui/test_editor_registry.py tests/ui/test_theme_registry.py -q
```
Expected: PASS, same counts as baseline.

A failure here almost certainly means an attribute was initialized twice (Step 2) or a method was deleted that had a `BaseRegistry`-specific override body. Compare against `git show HEAD:packages/haywire-core/src/haywire/core/registry/base.py` rather than reconstructing from memory.

- [ ] **Step 5: Run ruff and mypy**

Run:
```bash
uv run ruff check packages/haywire-core/src/haywire/core/registry/
uv run ruff format --check packages/haywire-core/src/haywire/core/registry/
uv run mypy packages/haywire-core/src/haywire/core/registry/ packages/haywire-core/src/haywire/core/library/
```
Expected: clean, "Success: no issues found".

- [ ] **Step 6: Commit**

```bash
git add packages/haywire-core/src/haywire/core/registry/component.py packages/haywire-core/src/haywire/core/registry/base.py
git commit -m "refactor(registry) extract ComponentRegistry from BaseRegistry

Storage, folder bookkeeping, the lifecycle queue, both subscriber lists
and the read API are kind-agnostic; module reload is not. A file-backed
registry can now inherit the contract without sys.modules machinery.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 3: Pin the contract with tests

Without this, nothing stops step 2's `DocumentRegistry` from finding `sys.modules` code on its base.

**Files:**
- Create: `tests/core/test_registry/__init__.py` (empty — sibling dirs like `tests/core/test_node/` each carry one)
- Create: `tests/core/test_registry/test_component_registry.py`

**Interfaces:**
- Consumes: `ComponentRegistry` from Task 2, with exactly the signatures in Task 2's Produces block.
- Produces: nothing consumed by later tasks.

- [ ] **Step 1: Write the failing test**

```python
"""``ComponentRegistry`` is the kind-agnostic half of the registry contract."""

import inspect

import pytest

pytestmark = pytest.mark.unit


class _Element:
    """Minimal ``RegisteredClass``: a class_identity with a ``hidden`` flag."""

    class class_identity:  # noqa: N801 - stands in for a BaseIdentity
        hidden = False
        label = "Element"

    class class_library:  # noqa: N801
        label = "testlib"


class _HiddenElement(_Element):
    class class_identity:  # noqa: N801
        hidden = True
        label = "Hidden"


def _identity():
    """A throwaway LibraryIdentity — LifeCycleEvent requires one."""
    from haywire.core.library.identity import LibraryIdentity

    return LibraryIdentity(label="testlib")


def _event(registry_key="k"):
    """A CLASS_ADDED event. ``affected_class`` and ``library_identity`` are required."""
    from haywire.core.registry.lifecycle_event import LifeCycleEvent, LifeCycleEventType

    return LifeCycleEvent(
        registry_key=registry_key,
        event_type=LifeCycleEventType.CLASS_ADDED,
        affected_class=_Element,
        library_identity=_identity(),
    )


def _registry():
    """A concrete ComponentRegistry with the folder abstracts stubbed out."""
    from haywire.core.registry.component import ComponentRegistry

    class _Fake(ComponentRegistry):
        def add_folder(self, folder_path, library_identity, exclude_patterns=None):
            self._folder_to_library[folder_path] = library_identity

        def remove_folder(self, folder_path, library_identity, exclude_patterns=None):
            del self._folder_to_library[folder_path]

        def event_dispatcher(self, event):
            return None

    return _Fake()


def test_read_api_reports_registered_elements():
    reg = _registry()
    assert reg.get("k") is None
    assert reg.has("k") is False

    reg._classes["k"] = _Element
    assert reg.get("k") is _Element
    assert reg.has("k") is True
    assert reg.list_names() == ["k"]


def test_list_visible_names_drops_hidden_elements():
    reg = _registry()
    reg._classes["shown"] = _Element
    reg._classes["hidden"] = _HiddenElement

    assert reg.list_visible_names() == ["shown"]
    assert set(reg.list_names()) == {"shown", "hidden"}


def test_queued_events_reach_batch_subscribers_then_drain():
    from haywire.core.registry.lifecycle_event import LifeCycleEvent

    reg = _registry()
    seen: list[list[LifeCycleEvent]] = []
    reg.add_batch_event_subscriber(lambda batch: seen.append(list(batch)))

    reg._queue_lifecycle_event(_event())
    reg._notify_batch_event_subscribers()

    assert [e.registry_key for e in seen[0]] == ["k"]
    assert reg._lifecycle_event_queue == []


def test_last_event_survives_the_queue_drain():
    from haywire.core.registry.lifecycle_event import LifeCycleEventType

    reg = _registry()
    reg._queue_lifecycle_event(_event())
    reg._notify_batch_event_subscribers()

    assert reg.get_lastevent("k").event_type is LifeCycleEventType.CLASS_ADDED
    assert reg.get_lastevent("absent") is None


def test_a_subscriber_that_raises_does_not_stop_the_others():
    """The error branch logs ``event.file_path``, so pass a real event."""
    from haywire.core.registry.events import FileChangeEvent, FileEventType

    reg = _registry()
    reached = []

    class _Boom:
        def event_dispatcher(self, event):
            raise RuntimeError("boom")

    class _Ok:
        def event_dispatcher(self, event):
            reached.append(event)

    reg.add_registry_subscriber(_Boom())
    reg.add_registry_subscriber(_Ok())
    reg._notify_registry_subscribers(
        FileChangeEvent(
            file_path="/x.py",
            event_type=FileEventType.MODIFIED,
            library_identity=_identity(),
            timestamp=0.0,
        )
    )

    assert len(reached) == 1


def test_base_is_free_of_module_reload_machinery():
    """The point of the split: no sys.modules/importlib on the shared base.

    A document registry inherits this class, and must not carry a reload
    path that only makes sense for Python modules.
    """
    from haywire.core.registry import component

    source = inspect.getsource(component)
    for banned in ("sys.modules", "importlib", "DependencyGraph"):
        assert banned not in source


def test_folder_registration_is_abstract():
    from haywire.core.registry.component import ComponentRegistry

    assert getattr(ComponentRegistry.add_folder, "__isabstractmethod__", False)
    assert getattr(ComponentRegistry.remove_folder, "__isabstractmethod__", False)


def test_baseregistry_still_satisfies_the_contract():
    """The class-backed registry is one implementation of the new base."""
    from haywire.core.registry.base import BaseRegistry
    from haywire.core.registry.component import ComponentRegistry

    assert issubclass(BaseRegistry, ComponentRegistry)
    for name in ("get", "has", "list_names", "list_visible_names", "get_lastevent"):
        assert hasattr(BaseRegistry, name)
```

- [ ] **Step 2: Run it**

Run:
```bash
uv run pytest tests/core/test_registry/test_component_registry.py -v
```
Expected: 8 passed. Task 2 already built the implementation, so this locks the contract in rather than driving it.

`LifeCycleEvent` requires `affected_class` and `library_identity` alongside `registry_key`/`event_type` — `_event()` supplies all four. If a field is added to that dataclass later, extend `_event()`; do not change the dataclass.

- [ ] **Step 3: Commit**

```bash
git add tests/core/test_registry/
git commit -m "test(registry) pin the ComponentRegistry contract

Guards the split for the document registry that inherits it: read API,
lifecycle queue drain, last-event retention, and the absence of module
reload machinery on the shared base.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 4: Retype the consumers

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/library/base.py:66`, `:70`
- Modify: `packages/haywire-core/src/haywire/core/library/registry.py:54`, `:109`
- Verify: `packages/haywire-core/src/haywire/core/library/file_watcher.py` (expected: no change)

**Interfaces:**
- Consumes: `ComponentRegistry` (Task 2).
- Produces: `BaseLibrary.registries: Dict[Type[ComponentRegistry[Any]], Any]`, `BaseLibrary._registry_folders: Dict[Type[ComponentRegistry[Any]], Tuple[str, Optional[List[str]]]]`, `LibraryRegistry.add_class_registry(cls: Type[ComponentRegistry], instance: ComponentRegistry)`.

- [ ] **Step 1: Widen `BaseLibrary`'s registry typing**

In `library/base.py`, add `ComponentRegistry` to the existing import:

```python
from haywire.core.registry.base import BaseRegistry, FileChangeEvent, HotReloadRegistry
from haywire.core.registry.component import ComponentRegistry
```

Then in `__init__`, change:

```python
        self.registries: Dict[Type[BaseRegistry[Any]], Any] = {}
```
to:
```python
        self.registries: Dict[Type[ComponentRegistry[Any]], Any] = {}
```

and:

```python
        self._registry_folders: Dict[Type[BaseRegistry[Any]], Tuple[str, Optional[List[str]]]] = {}
```
to:
```python
        self._registry_folders: Dict[Type[ComponentRegistry[Any]], Tuple[str, Optional[List[str]]]] = {}
```

If `BaseRegistry` becomes unused in the file after this, delete it from the import — ruff will say so.

- [ ] **Step 2: Widen `LibraryRegistry`**

In `library/registry.py`, add the import:

```python
from ..registry.component import ComponentRegistry
```

Change line 54:
```python
        self._class_registries: Dict[Type[BaseRegistry], BaseRegistry] = {}
```
to:
```python
        self._class_registries: Dict[Type[ComponentRegistry], ComponentRegistry] = {}
```

Change line 109:
```python
    def add_class_registry(self, cls: Type[BaseRegistry], instance: BaseRegistry):
```
to:
```python
    def add_class_registry(self, cls: Type[ComponentRegistry], instance: ComponentRegistry):
```

Read the method body before editing: if it calls anything module-specific on `instance` (a `_module_to_registry_keys` read, say), stop and report it — that would mean the seam is drawn in the wrong place and the plan needs revising, not a cast.

- [ ] **Step 3: Verify `file_watcher.py` needs no change**

Run:
```bash
grep -n "BaseRegistry\|HotReloadRegistry\|ComponentRegistry" packages/haywire-core/src/haywire/core/library/file_watcher.py
```
Expected: only `HotReloadRegistry` (lines 12, 44, 49, 68, 88, 108, 117, 245, 296, 329). The watcher calls `event_dispatcher` and nothing else, so `HotReloadRegistry` is already the right type and **must stay** — widening it to `ComponentRegistry` would wrongly exclude `_HaybaleTomlWatcher`.

If the grep shows a `BaseRegistry` annotation, widen that one to `ComponentRegistry`; leave every `HotReloadRegistry` alone.

- [ ] **Step 4: Run the registry and library suites**

Run:
```bash
uv run pytest tests/core/test_libraries/ tests/core/test_registry/ tests/core/test_node/test_factory.py -q
```
Expected: PASS.

- [ ] **Step 5: Run ruff and mypy over both packages**

Run:
```bash
uv run ruff check packages/haywire-core/src/haywire/core/registry/ packages/haywire-core/src/haywire/core/library/
uv run ruff format --check packages/haywire-core/src/haywire/core/registry/ packages/haywire-core/src/haywire/core/library/
uv run mypy packages/haywire-core/src/haywire/core/registry/ packages/haywire-core/src/haywire/core/library/
```
Expected: clean; mypy "Success: no issues found in 22 source files" (21 baseline + `component.py`; 23 if `events.py` counts in this path too).

- [ ] **Step 6: Commit**

```bash
git add packages/haywire-core/src/haywire/core/library/base.py packages/haywire-core/src/haywire/core/library/registry.py
git commit -m "refactor(library) type registry slots on ComponentRegistry

A library's registry map and the library registry accept any component
registry, not only class-backed ones. The watcher keeps HotReloadRegistry:
it calls event_dispatcher and nothing more.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 5: Full gate

**Files:** none modified — this task only verifies.

**Interfaces:**
- Consumes: all prior tasks.
- Produces: a green tree fit for step 2 of 03-macro.md.

- [ ] **Step 1: Commit `barn/haybale-testing` if it has uncommitted work**

Run:
```bash
git status --porcelain barn/haybale-testing
```
Expected: empty. If it is **not** empty, commit it before going further — `tests/studio/test_docs/test_generate.py`'s teardown runs `git checkout -- barn/haybale-testing` and silently discards uncommitted edits there. See [.insights/project_docs_test_reverts_barn_testing.md](../../../.insights/project_docs_test_reverts_barn_testing.md).

- [ ] **Step 2: Repo-wide ruff (both commands — CI runs both)**

Run:
```bash
uv run ruff check .
uv run ruff format --check .
```
Expected: "All checks passed!" and "N files already formatted".

- [ ] **Step 3: Repo-wide mypy**

Run:
```bash
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-marketplace/haybale_marketplace/ barn/haybale-share/haybale_share/ barn/haybale-graph-editor/haybale_graph_editor/ barn/haybale-haystack/haybale_haystack/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-TEST_A/haybale_test_a/ tests/
```
Expected: "Success: no issues found".

- [ ] **Step 4: Full non-browser suite**

Run:
```bash
uv run pytest -m "not browser and not perf" -q > /tmp/gate.log 2>&1; echo "exit=$?"
grep -E "^FAILED|^ERROR" /tmp/gate.log
grep -E "passed|failed" /tmp/gate.log | tail -1
```
Expected: `exit=0`, no FAILED/ERROR lines, and a passed count matching the pre-step baseline (**5560 passed, 142 deselected, 2 xfailed** as of `3d27c117`). Use a timeout of at least 600000 ms.

A *higher* passed count is expected and correct — Task 3 adds 8 tests, so **5568** is the target.

- [ ] **Step 5: Confirm no macro code leaked in**

Run:
```bash
grep -rn "MacroRegistry\|DocumentRegistry\|\.hwm\|MacroNode" --include="*.py" packages/ barn/ tests/
```
Expected: **no output**. This step is step 1 of the macro plan; any hit means scope crept.

---

## Notes for the implementer

- **The safety net is the existing suite, not the new tests.** This is a pure move: if `tests/core/test_libraries/` passes, the move is faithful. Task 3's tests document the seam for the next step.
- **`_register`/`_unregister` deliberately stay on `BaseRegistry`.** They maintain `_regkey_to_class_name` and `_module_to_registry_keys` — module bookkeeping. A document registry will write `self._classes` through its own path. Do not "helpfully" pull them down to the base.
- **Two registries reach into `_regkey_to_last_lifecycle_event` directly** (`ui/skin/registry.py:195`, `ui/widget/registry.py:81`) and `node/registry.py:164` wraps it as `get_node_lastevent`. All three keep working — the attribute is still there, just initialized one class up. `get_lastevent` is added as the public reader; **leave the three existing call sites alone** in this step.
- **`event_dispatcher` stays abstract on `HotReloadRegistry` and concrete on `BaseRegistry`.** `ComponentRegistry` does not implement it — a document registry will supply its own. That is why `_Fake` in Task 3 defines it.
