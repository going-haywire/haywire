# Haywire UI Architecture Specification

## Overview & Motivation

Haywire's current UI architecture is limited to rendering node bodies inside a monolithic graph canvas. There is no concept of separate editors, properties panels, context-driven UI, or workspaces. This specification defines a multi-editor workspace system inspired by Blender's UI architecture and VS Code's layout model, implemented on top of NiceGUI.

The goal is to introduce a structured, extensible UI framework where:

- Multiple editor types coexist in a configurable workspace layout
- Panels register declaratively to editors with context-driven visibility
- The existing renderer and widget systems are preserved and integrated
- Multiple browser sessions can connect to the same project simultaneously
- Library developers can ship panels and editors that "just appear" in the right place

---

## 1. Architecture Overview

### 1.1 Layout Model

```
┌──────────────────────────────────────────────────────────────┐
│                          TopBar                              │
├────┬──────────┬─────────────────────┬──────────────┬─────────┤
│    │          │    Middle Area      │              │         │
│    │          │  ┌────┬────┬──┐    │              │         │
│    │          │  │Tab1│Tab2│+ │    │              │         │
│    │          │  ├────┴────┴──┤    │              │         │
│ A  │  Left    │  │            │    │    Right     │  C      │
│ c  │  Area    │  │   Main     │    │    Area      │  o      │
│ t  │          │  │  Editor    │    │              │  n      │
│ i  │ (driven  │  │  (Graph)   │    │  (context-   │  t      │
│ v  │  by      │  │            │    │   aware      │  e      │
│ i  │  activ-  │  ├────────────┤    │   editors)   │  x      │
│ t  │  ity     │  │  Bottom    │    │              │  t      │
│ y  │  bar)    │  │  Area      │    │  (driven by  │         │
│    │          │  │ (console,  │    │   context    │  B      │
│ B  │          │  │  terminal, │    │   bar)       │  a      │
│ a  │          │  │  logs)     │    │              │  r      │
│ r  │          │  └────────────┘    │              │         │
├────┴──────────┴─────────────────────┴──────────────┴─────────┤
│                        StatusBar                             │
└──────────────────────────────────────────────────────────────┘
```

**Layout zones (left to right):**

1. **ActivityBar** (left edge) — Vertical icon strip. Clicking an icon switches which editor is shown in the Left Area. Think VS Code's sidebar icons (Explorer, Search, Git, Extensions).
2. **Left Area** — Hosts activity-driven editors (Library Browser, Project Explorer, Search).
3. **Middle Area** — The primary workspace. Supports tabbed editors (mainly the Graph Editor). Can be split horizontally to reveal a Bottom Area.
4. **Bottom Area** — Split off from the Middle Area. Hosts real-time feedback editors (Console, Terminal, Log Viewer, Data Inspector).
5. **Right Area** — Hosts context-aware editors (Properties Editor, Node Inspector). Content changes based on selection.
6. **ContextBar** (right edge) — Vertical icon strip. Clicking an icon switches which editor is shown in the Right Area.
7. **TopBar** — Application menu, workspace selector, global controls.
8. **StatusBar** — Execution status, notifications, quick info.

**Key behaviors:**

- Any editor type can be placed in any area (no hard restrictions)
- The Left Area, Bottom Area, and Right Area can each be collapsed/hidden
- The Middle Area supports multiple tabs (e.g., multiple graphs open simultaneously). Only
  `opens='required'` main editors auto-populate at startup; `on_context` and `on_payload`
  editors are opened on demand via `reveal_editor`. On save, main tabs without a payload are
  stripped; on load, `required` main tabs are re-derived from the registry and persisted
  `on_payload` tabs are added back.
- The Bottom Area splits off from the Middle Area and can be toggled
- ActivityBar drives the Left Area; ContextBar drives the Right Area

### 1.2 State Ownership

```
Server (one per project, shared across all sessions):
├── ProjectState
│     ├── Graph(s) data model          ← shared, mutation-notified
│     ├── Project settings             ← shared
│     └── Library system               ← shared
├── Global Registries                  ← shared, read-only for sessions; all DI-managed singletons
│     ├── EditorTypeRegistry           ← extends BaseRegistry; hot-reload capable
│     ├── PanelRegistry                ← extends BaseRegistry; hot-reload capable
│     ├── SkinRegistry             (NodeBody renderers, consumed by GraphEditor)
│     └── WidgetRegistry
└── SessionManager
      ├── Session A (browser window 1)
      │     ├── SessionContext           (selection, mode, cursor position, active library/component)
      │     ├── WorkspaceState           (layout, active editors, split ratios)
      │     └── UI instances             (NiceGUI elements, per-session DOM)
      └── Session B (browser window 2)
            ├── SessionContext
            ├── WorkspaceState
            └── UI instances
```

**Multi-session rules:**

- Data mutations (graph changes, node value changes) propagate to all sessions
- Selection state is per-session (User A selecting a node does not affect User B)
- Workspace/layout state is per-session
- Undo/redo stacks are per-session
- Concurrent edit conflict resolution: last-write-wins (OT/CRDT deferred to future work)

### 1.3 Registry Architecture

All registries are global singletons provided by the DI container (`HaywireModule`). `EditorTypeRegistry` and `PanelRegistry` extend `BaseRegistry` — the same base used by `SkinRegistry`, `NodeRegistry`, `WidgetRegistry`, etc. — gaining hot-reload support via folder scanning, lifecycle events, dependency tracking, and snapshot rollback.

Editors and panels contributed by libraries are registered via `add_folder()` in `register_components()`, following the identical pattern as nodes and renderers. Built-in framework editors and panels (those that ship inside `haywire-core` itself) are bootstrapped directly in the DI provider via `register_builtin_editors()` and `register_builtin_panels()`, analogous to `register_builtin_settings()`.

```
Global Registries (shared infrastructure, all DI-managed, all extending BaseRegistry):
├── EditorTypeRegistry        — Registers editor types
├── PanelRegistry             — Panels declare which editor + context they target
├── SkinRegistry          — Node body renderers (existing, narrowed scope)
└── WidgetRegistry            — Atomic UI elements (existing, unchanged)

Editors consume registries:
├── GraphEditor               → SkinRegistry, WidgetRegistry
├── PropertiesEditor          → PanelRegistry, WidgetRegistry
├── LibraryBrowser            → (haywire-app; emits ACTIVE_LIBRARY_CHANGED /
│                                ACTIVE_COMPONENT_CHANGED context events;
│                                drives LibraryDetailEditor + ComponentDetailEditor)
├── ConsoleEditor             → (no registry dependencies)
└── ...
```

The GraphEditor owns the node rendering pipeline:

```
GraphEditor
  └── SkinRegistry        — How nodes look inside the graph canvas
        └── WidgetRegistry    — Widgets used for inline port controls
```

---

## 2. Core Abstractions

### 2.1 SessionContext

The central state object that flows through the entire UI hierarchy. Each browser session has its own instance. This is the equivalent of Blender's `bContext`.

```python
# packages/haywire-core/src/haywire/ui/context.py

from dataclasses import dataclass, field
from typing import Optional, Set, Any, Dict
from enum import Enum


class InteractionMode(Enum):
    """Current user interaction mode."""
    IDLE = "idle"
    EDITING = "editing"          # editing node values
    CONNECTING = "connecting"    # dragging a connection
    SELECTING = "selecting"      # box selection
    PANNING = "panning"          # panning the canvas


@dataclass
class SessionContext:
    """
    Per-session context carrying current UI state.

    This is the primary mechanism for context-driven panel visibility.
    Panels receive this in their poll() and draw() methods and use it
    to decide what to show.

    Attributes:
        session_id: Unique identifier for this browser session.
        active_graph: The currently viewed graph (if any).
        active_node: The currently selected/focused node wrapper (if any).
        active_edge: The currently selected edge (if any).
        selected_nodes: Set of currently selected node IDs.
        selected_edges: Set of currently selected edge IDs.
        interaction_mode: What the user is currently doing.
        active_editor: The editor type currently focused.
        active_library: Library selected in LibraryBrowser (InstalledLibrary |
            MarketplaceEntry, or None). Drives LibraryDetailEditor.
        active_component: Component selected in LibraryBrowser (node/widget/renderer
            class or metadata, or None). Drives ComponentDetailEditor.
        metadata: Extensible dict for editor-specific state.
    """
    session_id: str
    active_graph: Optional[Any] = None          # HaywireGraph
    active_node: Optional[Any] = None           # NodeWrapper
    active_edge: Optional[Any] = None           # Edge
    selected_nodes: Set[str] = field(default_factory=set)
    selected_edges: Set[str] = field(default_factory=set)
    interaction_mode: InteractionMode = InteractionMode.IDLE
    active_editor: Optional[str] = None         # editor registry key
    active_library: Optional[Any] = None        # InstalledLibrary | MarketplaceEntry
    active_component: Optional[Any] = None      # node/widget/renderer class or metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
```

### 2.2 ContextChanged Event

When the SessionContext changes, a notification is broadcast so all editors in that session can re-evaluate their panels.

```python
# packages/haywire-core/src/haywire/ui/context_events.py

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Optional


class ContextChangeType(Enum):
    """What aspect of the context changed."""
    SELECTION_CHANGED = auto()        # node/edge selection changed
    ACTIVE_GRAPH_CHANGED = auto()     # switched to a different graph
    MODE_CHANGED = auto()             # interaction mode changed
    EDITOR_FOCUSED = auto()           # different editor gained focus
    WORKSPACE_CHANGED = auto()        # workspace preset switched
    DATA_MUTATED = auto()             # graph data changed (node values, structure)
    ACTIVE_LIBRARY_CHANGED = auto()   # library selected in LibraryBrowser
    ACTIVE_COMPONENT_CHANGED = auto() # component (node/widget/renderer) selected in LibraryBrowser
    CUSTOM = auto()                   # extensible


@dataclass
class ContextChangedEvent:
    """
    Broadcast when SessionContext changes.

    Editors subscribe to these events and re-evaluate their panels
    (re-run poll(), re-render draw() if needed).

    Attributes:
        change_type: What category of change occurred.
        source_editor: Which editor originated the change (if any).
        detail: Optional additional information about the change.
    """
    change_type: ContextChangeType
    source_editor: Optional[str] = None
    detail: Optional[Any] = None
```

### 2.3 EditorType Registry & Base Class

Editor types follow the same registration pattern as nodes and renderers: the `@editor` decorator **only sets class attributes** (`class_identity`); actual registration in `EditorTypeRegistry` happens when the library calls `add_folder()` in `register_components()`. The registry extends `BaseRegistry` and is provided as a DI singleton.

**Identity dataclass:**

```python
# packages/haywire-core/src/haywire/ui/editor/identity.py

from dataclasses import dataclass, field


@dataclass
class EditorIdentity:
    """
    Metadata attached to an editor class by the @editor decorator.

    Set once at class-definition time; survives hot-reload.
    Analogous to RendererIdentity / NodeIdentity in the existing registries.
    """
    registry_id: str            # e.g. 'graph_editor'
    label: str                  # e.g. 'Graph Editor'
    icon: str = 'extension'     # Material Design icon name
    default_slot: str = 'main'
    description: str = ''
    registry_key: str = ''      # fully-qualified key; set by decorator via reg_key()
```

**Base class:**

```python
# packages/haywire-core/src/haywire/ui/editor/base.py

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar

from .identity import EditorIdentity

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext
    from haywire.ui.context_events import ContextChangedEvent
    from nicegui.element import Element


class BaseEditor(ABC):
    """
    Abstract base class for all editor types.

    An editor is a self-contained UI module that renders into a slot
    of the workspace layout. Each editor instance is per-session — when
    two browser windows are open, each has its own editor instances.

    Subclasses must implement:
        - render(container, context): Build the editor UI into the given container.
        - on_context_changed(event, context): React to context changes.

    Class attributes (set by @editor decorator):
        - class_identity: EditorIdentity with registry_key, label, icon, default_slot.
        - class_library: LibraryIdentity of the owning library (None for builtins).
    """

    class_identity: ClassVar[EditorIdentity]

    @abstractmethod
    def render(self, container: 'Element', context: "SessionContext") -> None:
        """
        Build the editor UI into the given NiceGUI container element.

        This is called once when the editor is first placed into a slot,
        and again if the editor is swapped out and back in.

        Args:
            container: NiceGUI parent element (typically a ui.column or ui.card).
            context: The current session context.
        """
        ...

    @abstractmethod
    def on_context_changed(
        self, event: 'ContextChangedEvent', context: "SessionContext"
    ) -> None:
        """
        Called when the SessionContext changes.

        The editor should re-evaluate which panels to show, update
        displayed data, etc.

        Args:
            event: Describes what changed.
            context: The updated session context.
        """
        ...

    def cleanup(self) -> None:
        """
        Optional cleanup when the editor is removed from a slot.
        Override to release resources, unsubscribe from events, etc.
        """
        pass

    def get_tab_label(self, context: "SessionContext") -> str:
        """
        Return the label to show in a tab header (for tabbed slots like main/bottom).
        Defaults to class_identity.label. Override for dynamic labels (e.g., graph name).
        """
        return self.class_identity.label
```

**Decorator (sets class_identity only — no registration):**

```python
# packages/haywire-core/src/haywire/ui/editor/decorator.py

from haywire.core.library.utils import derive_library_identity, reg_key

from .base import BaseEditor
from .identity import EditorIdentity


def editor(
    cls=None, /, *,
    registry_id: str = None,
    label: str = None,
    icon: str = 'extension',
    default_slot: str = 'main',
    description: str = '',
):
    """
    Decorator to mark a class as an editor type.

    Sets class_identity on the class. Does NOT register the class —
    registration happens when the library calls add_folder() in
    register_components(), following the same pattern as @renderer and @widget.

    For built-in framework editors, registration is bootstrapped directly
    in the DI provider via register_builtin_editors().

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
            raise TypeError(
                f"@editor can only be applied to BaseEditor subclasses, got {inner_cls}"
            )

        _registry_id = registry_id or inner_cls.__name__
        _label = label or inner_cls.__name__

        library_identity = derive_library_identity(inner_cls)
        library_id = library_identity.id if library_identity else None
        _registry_key = reg_key(library_id, 'editor', _registry_id)

        inner_cls.class_identity = EditorIdentity(
            registry_id=_registry_id,
            label=_label,
            icon=icon,
            default_slot=default_slot,
            description=description,
            registry_key=_registry_key,
        )
        inner_cls.class_library = library_identity
        return inner_cls

    return decorator if cls is None else decorator(cls)
```

**Registry (extends BaseRegistry):**

```python
# packages/haywire-core/src/haywire/ui/editor/registry.py

import inspect
import logging
from typing import Optional, Dict

from haywire.core.registry.base import BaseRegistry
from haywire.core.library.identity import LibraryIdentity

from .base import BaseEditor


class EditorTypeRegistry(BaseRegistry):
    """
    Registry of editor types.

    Extends BaseRegistry for hot-reload support, folder scanning, lifecycle
    events, dependency tracking, and snapshot rollback. Provided as a DI
    singleton by HaywireModule.

    Libraries register editors via add_folder() in register_components().
    Built-in framework editors are bootstrapped via register_builtin_editors()
    called from the DI provider, analogous to register_builtin_settings().
    """

    def _class_filter(self, cls) -> bool:
        try:
            return (
                inspect.isclass(cls)
                and issubclass(cls, BaseEditor)
                and cls is not BaseEditor
                and hasattr(cls, 'class_identity')
            )
        except TypeError:
            return False

    def _register_class(
        self, cls: type, library_identity: Optional[LibraryIdentity] = None
    ) -> str | None:
        registry_key = cls.class_identity.registry_key
        logging.debug(f"EditorTypeRegistry: Registering '{registry_key}' ({cls.__name__})")
        return super()._register(registry_key, cls, library_identity)

    def _unregister_class(self, registry_key: str) -> type | None:
        return super()._unregister(registry_key)

    def get_by_default_slot(self, slot: str) -> Dict[str, type]:
        """Get all editor classes suggested for a given default slot."""
        return {
            k: v for k, v in self._classes.items()
            if v.class_identity.default_slot == slot
        }
```

### 2.4 Panel Registry & Base Class

Panels are collapsible sections that render inside editors. They follow the same registration pattern as editors — the `@panel` decorator only sets `class_identity`; actual registration happens via `add_folder()`. The editor queries the PanelRegistry for matching panels, runs `poll()` on each, and renders those that return True.

**Identity dataclass:**

```python
# packages/haywire-core/src/haywire/ui/panel/identity.py

from dataclasses import dataclass
from typing import Optional


@dataclass
class PanelIdentity:
    """
    Metadata attached to a panel class by the @panel decorator.

    Set once at class-definition time; survives hot-reload.
    """
    registry_id: str            # e.g. 'node_transform'
    editor_key: str             # which editor type this panel belongs to
    context: str                # context filter string (e.g. 'node', 'graph', 'edge')
    label: str                  # display label shown in panel header
    icon: Optional[str] = None  # Material Design icon name
    order: int = 100            # sort priority (lower = higher in list)
    default_open: bool = True   # whether panel starts expanded
    description: str = ''
    registry_key: str = ''      # fully-qualified key; set by decorator via reg_key()
```

**Base class:**

```python
# packages/haywire-core/src/haywire/ui/panel/base.py

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar

from .identity import PanelIdentity

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext


class PanelLayout:
    """
    Layout helper passed to panel draw() methods.

    Wraps NiceGUI layout primitives and provides convenience methods
    for adding widgets, rows, columns, labels, separators, etc.

    This abstraction isolates panel authors from direct NiceGUI API
    calls, enabling potential backend swaps and consistent styling.

    Methods (non-exhaustive, expand as needed):
        widget(widget_key, port, **config): Render a registered widget.
        label(text, **style): Add a text label.
        row(): Context manager for a horizontal row.
        column(): Context manager for a vertical column.
        separator(): Add a visual divider.
        button(text, on_click, **style): Add a button.
        expansion(title, icon): Collapsible sub-section.
    """

    def __init__(self, container):
        """
        Args:
            container: NiceGUI parent element to render into.
        """
        self._container = container

    # Implementation methods will wrap NiceGUI calls.
    # Detailed implementation deferred to implementation phase.


class BasePanel(ABC):
    """
    Abstract base class for all panels.

    A panel is a collapsible section that appears inside an editor,
    filtered by context. Panels are the primary extension point for
    library developers to add custom UI.

    Class attributes (set by @panel decorator via class_identity):
        - class_identity.registry_key: Unique registry key.
        - class_identity.editor_key: Which editor type this panel belongs to.
        - class_identity.context: Context filter string.
        - class_identity.label: Display label shown in the panel header.
        - class_identity.icon: Optional Material icon.
        - class_identity.order: Sort priority (lower = higher in the list).
        - class_identity.default_open: Whether the panel starts expanded.

    Lifecycle:
        1. Editor receives ContextChangedEvent.
        2. Editor queries PanelRegistry for panels matching its editor_key.
        3. For each panel, editor calls poll(context).
        4. If poll() returns True, editor calls draw(context, layout).
        5. If poll() returns False, panel is hidden.
    """

    class_identity: ClassVar[PanelIdentity]

    @classmethod
    def poll(cls, context: "SessionContext") -> bool:
        """
        Determine if this panel should be visible given the current context.

        Called every time the context changes. Should be fast — avoid
        expensive computation here.

        Args:
            context: Current session context.

        Returns:
            True if the panel should be shown, False to hide it.
        """
        return True

    @abstractmethod
    def draw(self, context: "SessionContext", layout: PanelLayout) -> None:
        """
        Render the panel contents.

        Called when poll() returns True and the panel needs to display.
        Use the layout helper to add widgets and UI elements.

        Args:
            context: Current session context.
            layout: PanelLayout helper for building the UI.
        """
        ...

    def on_context_changed(
        self, context: "SessionContext", layout: PanelLayout
    ) -> None:
        """
        Optional incremental update when context changes without full redraw.

        Override for panels that can update in-place rather than fully
        re-rendering. If not overridden, the editor will clear and re-call draw().
        """
        pass
```

**Decorator (sets class_identity only — no registration):**

```python
# packages/haywire-core/src/haywire/ui/panel/decorator.py

from typing import Optional

from haywire.core.library.utils import derive_library_identity, reg_key

from .base import BasePanel
from .identity import PanelIdentity


def panel(
    cls=None, /, *,
    registry_id: str = None,
    editor: str,
    context: str,
    label: str = None,
    icon: Optional[str] = None,
    order: int = 100,
    default_open: bool = True,
    description: str = '',
):
    """
    Decorator to mark a class as a panel.

    Sets class_identity on the class. Does NOT register the class —
    registration happens when the library calls add_folder() in
    register_components(), following the same pattern as @renderer and @widget.

    Usage:
        @panel(
            editor='properties',
            context='node',
            label='Transform',
            icon='open_with',
            order=10,
        )
        class TransformPanel(BasePanel):
            @classmethod
            def poll(cls, ctx):
                return ctx.active_node is not None

            def draw(self, ctx, layout):
                node = ctx.active_node
                layout.widget('number', node.settings.x, label="X")
    """
    def decorator(inner_cls):
        if not issubclass(inner_cls, BasePanel):
            raise TypeError(
                f"@panel can only be applied to BasePanel subclasses, got {inner_cls}"
            )

        _registry_id = registry_id or inner_cls.__name__
        _label = label or inner_cls.__name__

        library_identity = derive_library_identity(inner_cls)
        library_id = library_identity.id if library_identity else None
        _registry_key = reg_key(library_id, 'panel', _registry_id)

        inner_cls.class_identity = PanelIdentity(
            registry_id=_registry_id,
            editor_key=editor,
            context=context,
            label=_label,
            icon=icon,
            order=order,
            default_open=default_open,
            description=description,
            registry_key=_registry_key,
        )
        inner_cls.class_library = library_identity
        return inner_cls

    return decorator if cls is None else decorator(cls)
```

**Registry (extends BaseRegistry):**

```python
# packages/haywire-core/src/haywire/ui/panel/registry.py

import inspect
import logging
from typing import Dict, List, Optional

from haywire.core.registry.base import BaseRegistry
from haywire.core.library.identity import LibraryIdentity

from .base import BasePanel


class PanelRegistry(BaseRegistry):
    """
    Registry of panels.

    Extends BaseRegistry for hot-reload support, folder scanning, lifecycle
    events, and snapshot rollback. Provided as a DI singleton by HaywireModule.

    Panels are indexed by (editor_key, context) for fast lookup. When a
    panel class is reloaded (hot-reload), the index is updated automatically
    via the lifecycle event system.
    """

    def __init__(self):
        super().__init__()
        # Secondary index: (editor_key, context) -> sorted list of panel classes
        self._index: Dict[tuple, List[type]] = {}

    def _class_filter(self, cls) -> bool:
        try:
            return (
                inspect.isclass(cls)
                and issubclass(cls, BasePanel)
                and cls is not BasePanel
                and hasattr(cls, 'class_identity')
            )
        except TypeError:
            return False

    def _register_class(
        self, cls: type, library_identity: Optional[LibraryIdentity] = None
    ) -> str | None:
        registry_key = cls.class_identity.registry_key
        result = super()._register(registry_key, cls, library_identity)
        if result:
            self._index_panel(cls)
        logging.debug(
            f"PanelRegistry: Registered '{registry_key}' -> "
            f"editor='{cls.class_identity.editor_key}', context='{cls.class_identity.context}'"
        )
        return result

    def _unregister_class(self, registry_key: str) -> type | None:
        removed = super()._unregister(registry_key)
        if removed:
            self._deindex_panel(removed)
        return removed

    def _index_panel(self, cls: type) -> None:
        idx_key = (cls.class_identity.editor_key, cls.class_identity.context)
        if idx_key not in self._index:
            self._index[idx_key] = []
        if cls not in self._index[idx_key]:
            self._index[idx_key].append(cls)
        self._index[idx_key].sort(key=lambda c: c.class_identity.order)

    def _deindex_panel(self, cls: type) -> None:
        idx_key = (cls.class_identity.editor_key, cls.class_identity.context)
        if idx_key in self._index and cls in self._index[idx_key]:
            self._index[idx_key].remove(cls)

    def get_panels(self, editor_key: str, context: str) -> List[type]:
        """Get all panels for a given editor type and context, sorted by order."""
        return list(self._index.get((editor_key, context), []))

    def get_all_for_editor(self, editor_key: str) -> Dict[str, List[type]]:
        """Get all panels for an editor, grouped by context."""
        result: Dict[str, List[type]] = {}
        for (ek, ctx), panels in self._index.items():
            if ek == editor_key:
                result[ctx] = list(panels)
        return result
```

### 2.5 Workspace System

```python
# packages/haywire-core/src/haywire/ui/workspace/workspace_state.py

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class SlotState:
    """
    State of a left or right slot in the workspace layout.

    Attributes:
        active_tab_key: Registry key of the editor currently in this slot.
        visible: Whether the slot's area is visible/expanded.
        size: Size in pixels (width for left/right).
    """
    active_tab_key: Optional[str] = None
    visible: bool = True
    size: int = 300


@dataclass
class TabState:
    """
    State of a single tab in a tabbed slot (main or bottom).

    Attributes:
        editor_key: Registry key of the editor in this tab.
        label: Tab display label.
        metadata: Editor-specific state (e.g., which graph is open).
    """
    editor_key: Optional[str] = None
    label: str = 'Graph'
    metadata: Dict[str, Any] = field(default_factory=dict)
@dataclass
class MainSlotState:
    """
    State of the main slot — the primary tabbed editor region.

    Attributes:
        tabs: List of open tabs.
        active_tab_key: Registry key of the active tab.
    """
    tabs: List[TabState] = field(default_factory=lambda: [TabState()])
    active_tab_key: Optional[str] = None


@dataclass
class BottomSlotState:
    """
    State of the bottom slot — a retractable tabbed slot below main.

    Attributes:
        tabs: Runtime-only tab list, re-derived from the editor registry on load.
        active_tab_key: Registry key of the active bottom tab.
        visible: Whether the content area is expanded.
        size: Height of the expanded content area in pixels.
    """
    tabs: List[TabState] = field(default_factory=list)
    active_tab_key: Optional[str] = None
    visible: bool = False
    size: int = 200


@dataclass
class WorkspaceState:
    """
    Complete workspace configuration.

    Serializable to JSON for persistence. Each named workspace
    is a saved instance of this class.

    Attributes:
        name: Workspace name (e.g., "Graph Editing", "Development").
        left: Left slot state (ActivityBar-driven).
        right: Right slot state (ContextBar-driven).
        main: Main slot state (MainTabBar-driven, tabbed).
        bottom: Bottom slot state (BottomTabBar-driven, tabbed, retractable).
    """
    name: str = "default"
    left: SlotState = field(default_factory=SlotState)
    right: SlotState = field(default_factory=SlotState)
    main: MainSlotState = field(default_factory=MainSlotState)
    bottom: BottomSlotState = field(default_factory=BottomSlotState)
```

**Workspace Manager:**

```python
# packages/haywire-core/src/haywire/ui/workspace/manager.py

from typing import Dict, Optional, List
import json
import logging
from pathlib import Path

from haywire.ui.workspace.workspace_state import (
    WorkspaceState, SlotState, MainSlotState, BottomSlotState, TabState
)


class WorkspaceManager:
    """
    Manages workspace presets.

    Handles creating, saving, loading, and switching workspaces.
    Each session has its own WorkspaceManager instance with its
    own active workspace, but the saved presets are shared (stored
    in the project folder).

    Default workspaces shipped with Haywire:
        - "Graph Editing": Graph in main slot, Properties on right, Library on left
        - "Development": Code Editor in main slot, Console in bottom, Library on left
        - "Debugging": Graph in main slot, Data Inspector in bottom, Log Viewer on right

    Attributes:
        active: The currently active WorkspaceState.
        presets: Dict of saved workspace presets by name.
    """

    DEFAULT_PRESETS: Dict[str, WorkspaceState] = {
        "Graph Editing": WorkspaceState(
            name="Graph Editing",
            left=SlotState(active_tab_key='library_browser', visible=True, size=250),
            main=MainSlotState(
                tabs=[TabState(editor_key='graph_editor', label='Graph')],
                active_tab_key='graph_editor',
            ),
            bottom=BottomSlotState(visible=False),
            right=SlotState(active_tab_key='properties', visible=True, size=350),
        ),
    }

    def __init__(self, project_path: Optional[Path] = None):
        self._project_path = project_path
        self.presets: Dict[str, WorkspaceState] = dict(self.DEFAULT_PRESETS)
        self.active: WorkspaceState = self.presets["Graph Editing"]

        if project_path:
            self._load_user_presets(project_path)

    def switch(self, name: str) -> WorkspaceState:
        """Switch to a named workspace preset."""
        if name not in self.presets:
            raise KeyError(f"Workspace '{name}' not found")
        self.active = self.presets[name]
        logging.info(f"WorkspaceManager: Switched to workspace '{name}'")
        return self.active

    def save_current(self, name: Optional[str] = None) -> None:
        """Save the current workspace state as a preset."""
        save_name = name or self.active.name
        self.active.name = save_name
        self.presets[save_name] = self.active
        if self._project_path:
            self._persist_presets()

    def get_preset_names(self) -> List[str]:
        return list(self.presets.keys())

    def _load_user_presets(self, project_path: Path) -> None:
        """Load saved workspace presets from project .haywire/ folder."""
        preset_file = project_path / '.haywire' / 'workspaces.json'
        if preset_file.exists():
            try:
                data = json.loads(preset_file.read_text())
                for name, state_dict in data.items():
                    self.presets[name] = WorkspaceState(**state_dict)
            except Exception as e:
                logging.warning(f"Failed to load workspace presets: {e}")

    def _persist_presets(self) -> None:
        """Save workspace presets to project .haywire/ folder."""
        if not self._project_path:
            return
        preset_dir = self._project_path / '.haywire'
        preset_dir.mkdir(parents=True, exist_ok=True)
        preset_file = preset_dir / 'workspaces.json'
        # Serialization logic — convert dataclasses to dicts
        data = {}
        for name, ws in self.presets.items():
            from dataclasses import asdict
            data[name] = asdict(ws)
        preset_file.write_text(json.dumps(data, indent=2))
```

### 2.6 Session & App Shell

```python
# packages/haywire-core/src/haywire/ui/session.py

from typing import Dict, Optional, List, Callable
import uuid
import logging

from haywire.ui.context import SessionContext
from haywire.ui.context_events import ContextChangedEvent, ContextChangeType
from haywire.ui.workspace.manager import WorkspaceManager
from haywire.ui.editor.base import BaseEditor


class Session:
    """
    Represents a single browser session (one connected browser tab).

    Each session owns:
        - A SessionContext (selection, mode, active state)
        - A WorkspaceManager (layout, which editors where)
        - Editor instances (one per area slot)
        - Context change subscriptions

    The Session is the bridge between the shared server-side data model
    and the per-client NiceGUI UI tree.

    Lifecycle:
        1. Created on client connect (NiceGUI app.on_connect)
        2. Builds the workspace layout shell
        3. Instantiates editors into areas based on active workspace
        4. Subscribes to data model changes for cross-session sync
        5. Destroyed on client disconnect
    """

    def __init__(self, project_state, project_path=None):
        self.session_id = str(uuid.uuid4())
        self.context = SessionContext(session_id=self.session_id)
        self.workspace_manager = WorkspaceManager(project_path=project_path)
        self.project_state = project_state

        # Active editor instances (keyed by area slot)
        self._editors: Dict[str, BaseEditor] = {}

        # Context change subscribers (editors register here)
        self._context_subscribers: List[Callable] = []

        logging.info(f"Session created: {self.session_id}")

    def notify_context_changed(self, event: ContextChangedEvent) -> None:
        """
        Broadcast a context change to all editors in this session.

        Called when selection changes, graph switches, mode changes, etc.
        Each editor will re-evaluate its panels.
        """
        for subscriber in self._context_subscribers:
            try:
                subscriber(event, self.context)
            except Exception as e:
                logging.error(f"Context subscriber error: {e}")

    def subscribe_context_changes(self, callback: Callable) -> None:
        if callback not in self._context_subscribers:
            self._context_subscribers.append(callback)

    def unsubscribe_context_changes(self, callback: Callable) -> None:
        if callback in self._context_subscribers:
            self._context_subscribers.remove(callback)

    def cleanup(self) -> None:
        """Clean up all editor instances and subscriptions."""
        for editor in self._editors.values():
            editor.cleanup()
        self._editors.clear()
        self._context_subscribers.clear()
        logging.info(f"Session cleaned up: {self.session_id}")
```

**App Shell (the main NiceGUI page):**

```python
# packages/haywire-core/src/haywire/ui/app_shell.py

"""
AppShell renders the workspace layout using NiceGUI.

This is the top-level UI component that creates the ActivityBar,
ContextBar, Left/Middle/Right/Bottom areas, TopBar, and StatusBar.

It reads the current WorkspaceState to determine which editors go
where, instantiates them, and wires up context change notifications.

The AppShell is created once per browser session via NiceGUI's
@ui.page decorator or app.on_connect handler. The haywire-app
package is responsible for constructing the Session and calling
AppShell.render() from within a NiceGUI page handler.
"""

from nicegui import ui, app


class AppShell:
    """
    Renders the workspace layout for a single session.

    Structure:
        TopBar          → ui.header or fixed top row
        ActivityBar     → ui.column, fixed left, icon buttons
        Left Area       → ui.column, resizable width
        Middle Area     → ui.column with ui.tabs for multiple editors
          Bottom Area   → ui.column, split from middle via ui.splitter
        Right Area      → ui.column, resizable width
        ContextBar      → ui.column, fixed right, icon buttons
        StatusBar       → ui.footer or fixed bottom row

    NiceGUI implementation approach:
        - Overall layout: CSS Grid or nested flexbox via Tailwind classes
        - Area resizing: ui.splitter() for the major splits, or CSS resize
        - Area collapse: toggle visibility via .set_visibility()
        - Tabs: ui.tabs() + ui.tab_panels() for the middle area
        - ActivityBar/ContextBar: ui.column() with ui.button(icon=...) items

    The AppShell does NOT contain business logic. It delegates to:
        - Session for context and state management
        - WorkspaceManager for layout state
        - EditorTypeRegistry for editor instantiation
        - Individual editors for their content
    """

    def __init__(self, session):
        self.session = session

    def render(self) -> None:
        """Build the complete workspace layout."""
        ws = self.session.workspace_manager.active

        # The actual NiceGUI layout construction goes here.
        # This is the primary implementation task.
        # See Section 6 (Implementation Plan) for phased approach.
        pass
```

### 2.7 Dependency Injection Integration

`EditorTypeRegistry` and `PanelRegistry` are added to `HaywireModule` as DI singletons, following the same pattern as `SkinRegistry` and `NodeRegistry`. Built-in framework editors/panels are bootstrapped in the provider.

```python
# Addition to packages/haywire-core/src/haywire/core/di/config.py

from ...ui.editor.registry import EditorTypeRegistry
from ...ui.panel.registry import PanelRegistry
from ...ui.editors.builtins import register_builtin_editors
from ...ui.panels.builtins import register_builtin_panels

# Inside HaywireModule:

    @provider
    @singleton
    def provide_editor_type_registry(self) -> EditorTypeRegistry:
        """Provide singleton EditorTypeRegistry.

        Built-in framework editors (GraphEditor, PropertiesEditor, ConsoleEditor)
        are registered directly here. Library-contributed editors are registered
        later via add_folder() in register_components().
        """
        registry = EditorTypeRegistry()
        register_builtin_editors(registry)
        return registry

    @provider
    @singleton
    def provide_panel_registry(self) -> PanelRegistry:
        """Provide singleton PanelRegistry.

        Built-in framework panels are registered directly here. Library-
        contributed panels are registered later via add_folder().
        """
        registry = PanelRegistry()
        register_builtin_panels(registry)
        return registry
```

`register_builtin_editors()` and `register_builtin_panels()` call `_register_class()` directly on the registry (no folder scan), as built-in editors are part of the installed package and do not need hot-reload. Library-contributed editors/panels do get full hot-reload via the normal `add_folder()` path.

---

## 3. Initial Editor Types

**Note on folder rename (prerequisite for all editors below):** The existing `packages/haywire-core/src/haywire/ui/editor/` folder contains graph canvas code. Before adding the new editor framework, this folder must be renamed to `graph_canvas/`. This is Phase 2 of the implementation plan. All editors below assume this rename has occurred.

### 3.1 GraphEditor

Wraps the existing `GraphCanvasManager` and graph canvas Vue component. This is largely a refactor of existing code into the new editor abstraction.

```python
# packages/haywire-core/src/haywire/ui/editors/graph_editor.py

from haywire.ui.editor.decorator import editor
from haywire.ui.editor.base import BaseEditor

from haywire.ui import elements as hui

@editor(
    label='Graph Editor',
    icon=hui.icons.graph_editor,
    default_slot='main',
    opens='on_payload',
    description='Visual node graph editor for wiring data processing pipelines.',
)
class GraphEditor(BaseEditor):
    """
    The graph canvas editor.

    Wraps the existing GraphCanvasManager and its Vue component.
    Owns the SkinRegistry consumption for node body rendering.

    Context changes this editor EMITS:
        - SELECTION_CHANGED: when user selects/deselects nodes or edges
        - MODE_CHANGED: when interaction mode changes
        - DATA_MUTATED: when graph structure changes (add/remove nodes/edges)

    Context changes this editor CONSUMES:
        - ACTIVE_GRAPH_CHANGED: swap to a different graph
        - DATA_MUTATED (from other sessions): sync graph changes

    Integration with existing code:
        - GraphCanvasManager → becomes internal to this editor
        - GraphCanvasVue → unchanged, still the Vue component
        - UINode → unchanged, still manages per-node UI lifecycle
        - RenderFactory → unchanged, still manages renderer instances
        - PopupContextMenu → unchanged, still the right-click menu
    """

    def render(self, container, context):
        # Instantiate GraphCanvasManager inside container
        # Wire up selection changes to emit context events
        ...

    def on_context_changed(self, event, context):
        # Handle ACTIVE_GRAPH_CHANGED to swap graphs
        # Handle DATA_MUTATED from other sessions
        ...
```

### 3.2 PropertiesEditor

A new editor that displays context-sensitive panels based on the current selection.

```python
# packages/haywire-core/src/haywire/ui/editors/properties_editor.py

from haywire.ui.editor.decorator import editor
from haywire.ui.editor.base import BaseEditor


@editor(
    label='Properties',
    icon='tune',
    default_slot='right',
    description='Context-sensitive property panels for the active selection.',
)
class PropertiesEditor(BaseEditor):
    """
    Displays panels registered to the 'properties' editor.

    This editor has NO hardcoded content. It queries the PanelRegistry
    for all panels with editor_key='properties', filters by the current
    context (based on what's selected), runs poll() on each, and renders
    those that return True.

    The context determination logic:
        - If active_node is set → context = 'node'
        - If active_edge is set → context = 'edge'
        - If active_graph is set but nothing selected → context = 'graph'
        - Multiple contexts can be active (show panels from all matching)

    Panel rendering:
        1. Query PanelRegistry.get_panels('properties', context)
        2. For each panel class, call poll(session_context)
        3. For each passing panel, create a ui.expansion() (collapsible)
        4. Inside the expansion, create a PanelLayout and call panel.draw()
        5. On context change, re-evaluate: hide panels that no longer poll(),
           show new ones that now poll()
    """

    def render(self, container, context):
        ...

    def on_context_changed(self, event, context):
        ...
```

### 3.3 ConsoleEditor

```python
# packages/haywire-core/src/haywire/ui/editors/console_editor.py

from haywire.ui.editor.decorator import editor
from haywire.ui.editor.base import BaseEditor


@editor(
    label='Console',
    icon='terminal',
    default_slot='bottom',
    description='Python console and execution log output.',
)
class ConsoleEditor(BaseEditor):
    """
    Displays execution output, log messages, and optionally a Python REPL.

    Subscribes to the execution engine's log stream and displays
    messages with timestamps, severity levels, and source attribution.

    No panel registry dependency — this editor has its own internal UI.
    """

    def render(self, container, context):
        ...

    def on_context_changed(self, event, context):
        # Mostly a no-op, console doesn't change with selection
        pass
```

### 3.4 LibraryBrowser

Lives in `haywire-app` because library install/uninstall/marketplace operations are app-level concerns, not framework concerns.

**Reference implementation:** The existing `library_manager_ui.py` (`LibraryManagerPage`) is a monolithic prototype that already implements the full three-panel layout now being split across three separate editors. The left panel of `LibraryManagerPage` — a searchable, filterable list of installed libraries and marketplace entries with Enabled / Disabled / Available tabs — directly defines what LibraryBrowser should implement. `library_manager.py` defines the data model (`InstalledLibrary`, `MarketplaceEntry`) and service operations that the new editors will work with.

When the user selects a library, LibraryBrowser emits `ACTIVE_LIBRARY_CHANGED`. When a specific node/widget/renderer is selected, it emits `ACTIVE_COMPONENT_CHANGED`. These drive `LibraryDetailEditor` (Section 3.5) and `ComponentDetailEditor` (Section 3.6) respectively.

```python
# packages/haywire-app/src/haywire_app/editors/library_browser.py

from haywire.ui.editor.decorator import editor
from haywire.ui.editor.base import BaseEditor
from haywire.ui.context_events import ContextChangedEvent, ContextChangeType


@editor(
    label='Library Browser',
    icon='library_books',
    default_slot='left',
    description='Browse available node libraries and marketplace.',
)
class LibraryBrowser(BaseEditor):
    """
    Left-panel editor: searchable / filterable library list.

    Fresh implementation of the left panel of the prototypical
    LibraryManagerPage (library_manager_ui.py).

    Features:
        - Tabbed list: Enabled / Disabled / Available (marketplace)
        - Search and filter controls
        - Shows InstalledLibrary and MarketplaceEntry entries

    Context events this editor EMITS:
        - ACTIVE_LIBRARY_CHANGED: when user clicks a library in the list.
          Sets context.active_library to the selected InstalledLibrary or
          MarketplaceEntry. Drives LibraryDetailEditor in the middle area.
        - ACTIVE_COMPONENT_CHANGED: when user selects a node/widget/renderer
          within a library list entry. Sets context.active_component. Drives
          ComponentDetailEditor in the right area.
    """

    def render(self, container, context):
        # Build tabbed list: Enabled / Disabled / Available
        # Wire selection events to emit context changes
        ...

    def on_context_changed(self, event, context):
        # React to library system changes (installs, uninstalls, hot-reloads)
        ...
```

### 3.5 LibraryDetailEditor

Fresh implementation of the **center panel** of the prototypical `LibraryManagerPage`. Lives in `haywire-app` alongside LibraryBrowser.

```python
# packages/haywire-app/src/haywire_app/editors/library_detail_editor.py

from haywire.ui.editor.decorator import editor
from haywire.ui.editor.base import BaseEditor
from haywire.ui.context_events import ContextChangeType


@editor(
    label='Library Detail',
    icon='info',
    default_slot='main',
    opens='on_context',
    description='Detail view for the selected library.',
)
class LibraryDetailEditor(BaseEditor):
    """
    Center-panel editor: unified library detail view.

    Fresh implementation of the center panel of the prototypical
    LibraryManagerPage (library_manager_ui.py): marketplace header +
    installed-library tabs (nodes, widgets, renderers, types, adapters).

    Consumes ACTIVE_LIBRARY_CHANGED from the session context.

    Content:
        - Marketplace header: description, author, version, tags, source,
          docs link, install/uninstall action button
        - For installed libraries: tabbed inventory of registered
          nodes / widgets / renderers / types / adapters with counts
        - Enable / Disable / Rename controls
        - Documentation rendered from OVERVIEW.md (if available)

    When context.active_library is None, shows a placeholder prompt.
    """

    def render(self, container, context):
        ...

    def on_context_changed(self, event, context):
        if event.change_type == ContextChangeType.ACTIVE_LIBRARY_CHANGED:
            # Re-render for the newly selected library
            ...
```

### 3.6 ComponentDetailEditor

Fresh implementation of the **right panel** of the prototypical `LibraryManagerPage`. Lives in `haywire-app`.

```python
# packages/haywire-app/src/haywire_app/editors/component_detail_editor.py

from haywire.ui.editor.decorator import editor
from haywire.ui.editor.base import BaseEditor
from haywire.ui.context_events import ContextChangeType


@editor(
    label='Component Detail',
    icon='widgets',
    default_slot='right',
    description='Documentation and details for the selected node or widget.',
)
class ComponentDetailEditor(BaseEditor):
    """
    Right-panel editor: per-component documentation.

    Fresh implementation of the right panel of the prototypical
    LibraryManagerPage (library_manager_ui.py): shown when a node,
    widget, or renderer is clicked in the library detail view.

    Consumes ACTIVE_COMPONENT_CHANGED from the session context.

    Content (for nodes):
        - Node identity: label, registry_key, library, description
        - Port listing: inlets, outlets, config ports with types
        - Live widget preview (for widget components)
        - QUICKREF.md documentation block (if available)

    Content adapts based on component type (node / widget / renderer /
    type / adapter). Hidden (or shows placeholder) when no component
    is selected (context.active_component is None).
    """

    def render(self, container, context):
        ...

    def on_context_changed(self, event, context):
        if event.change_type == ContextChangeType.ACTIVE_COMPONENT_CHANGED:
            # Re-render for the newly selected component
            ...
```

---

## 4. File Structure

All new framework files live under `packages/haywire-core/src/haywire/ui/`. All new app-specific files live under `packages/haywire-app/src/haywire_app/`. Existing files are preserved; the refactoring wraps them rather than replacing them.

### 4.1 haywire-core

**Prerequisite rename:** The existing `haywire/ui/editor/` folder (graph canvas code) must be renamed to `haywire/ui/graph_canvas/` before the new `editor/` framework folder is created. All imports from `haywire.ui.editor.*` must be updated to `haywire.ui.graph_canvas.*`. This is an atomic operation (Phase 2).

```
packages/haywire-core/src/haywire/ui/
├── __init__.py
├── context.py                          # NEW: SessionContext, InteractionMode
├── context_events.py                   # NEW: ContextChangedEvent, ContextChangeType
├── session.py                          # NEW: Session class
├── app_shell.py                        # NEW: AppShell layout renderer
│
├── editor/                             # NEW: Editor framework
│   ├── __init__.py
│   ├── identity.py                     # EditorIdentity dataclass
│   ├── base.py                         # BaseEditor ABC
│   ├── decorator.py                    # @editor decorator (sets class_identity only)
│   └── registry.py                     # EditorTypeRegistry (extends BaseRegistry)
│
├── panel/                              # NEW: Panel framework
│   ├── __init__.py
│   ├── identity.py                     # PanelIdentity dataclass
│   ├── base.py                         # BasePanel ABC, PanelLayout
│   ├── decorator.py                    # @panel decorator (sets class_identity only)
│   └── registry.py                     # PanelRegistry (extends BaseRegistry)
│
├── workspace/                          # NEW: Workspace system
│   ├── __init__.py
│   ├── workspace_state.py              # WorkspaceState, SlotState, MainSlotState, BottomSlotState, TabState
│   └── manager.py                      # WorkspaceManager
│
├── editors/                            # NEW: Built-in editor implementations (framework)
│   ├── __init__.py
│   ├── builtins.py                     # register_builtin_editors() bootstrap function
│   ├── graph_editor.py                 # GraphEditor (wraps existing GraphCanvasManager)
│   ├── properties_editor.py            # PropertiesEditor (panel-driven)
│   └── console_editor.py              # ConsoleEditor
│
├── panels/                             # NEW: Built-in panel implementations (framework)
│   ├── __init__.py
│   ├── builtins.py                     # register_builtin_panels() bootstrap function
│   ├── node_properties_panel.py        # Node name, class, library info
│   ├── node_ports_panel.py             # Port listing and configuration
│   ├── node_settings_panel.py          # Node settings (LOCAL_ONLY, etc.)
│   ├── graph_info_panel.py             # Graph-level properties and stats
│   └── edge_info_panel.py             # Edge/connection details
│
├── graph_canvas/                       # EXISTING (renamed from editor/): graph canvas code
│   ├── graph_canvas_manager.py         # GraphCanvasManager → internal to GraphEditor
│   ├── graph_canvas_vue.py             # GraphCanvasVue component
│   ├── popup_context_menu.py           # Right-click menu
│   ├── event_definitions.py            # Graph events
│   └── event_handlers.py              # Event handler system
│
├── renderer/                           # EXISTING: Preserved, unchanged
│   ├── __init__.py
│   ├── base.py
│   ├── decorator.py
│   ├── factory.py
│   └── registry.py
│
├── widget/                             # EXISTING: Preserved, unchanged
│   ├── __init__.py
│   ├── base.py
│   ├── binding.py
│   ├── converters.py
│   ├── decorator.py
│   ├── factory.py
│   └── registry.py
│
├── ui_node.py                          # EXISTING: UINode (unchanged)
├── ui_nodecard.py                      # EXISTING: UINodeCard (unchanged)
└── themes/                             # EXISTING: unchanged
```

### 4.2 haywire-app

```text
packages/haywire-app/src/haywire_app/
├── app.py                              # EXISTING: HaywireApp (~1800 lines)
│                                       #   gains: on_connect → Session creation,
│                                       #           AppShell.render() call
├── config.py                           # EXISTING: unchanged
├── library_manager.py                  # EXISTING: prototypical library service (reference)
├── library_manager_ui.py               # EXISTING: prototypical 3-panel UI (reference for editors)
├── init.py                             # EXISTING: CLI subcommand
├── share.py                            # EXISTING: CLI subcommand
│
└── editors/                            # NEW: App-specific editor implementations
    ├── __init__.py
    ├── library_browser.py              # LibraryBrowser (depends on library_manager.py)
    ├── library_detail_editor.py        # LibraryDetailEditor (middle area)
    └── component_detail_editor.py      # ComponentDetailEditor (right area)
```

---

## 5. Integration with Existing Systems

### 5.1 SkinRegistry (Existing → Narrowed Scope)

No code changes needed. The SkinRegistry continues to work exactly as it does today. The only conceptual change is that it is now understood as being consumed exclusively by the GraphEditor. Its scope narrows from "the rendering system" to "how nodes look inside the graph canvas."

### 5.2 WidgetRegistry (Existing → Shared)

No code changes needed. Widgets are the shared atomic UI elements used by both node body renderers (inside the GraphEditor) and panels (inside the PropertiesEditor and others). The WidgetFactory may need a minor enhancement to support rendering widgets outside of a node context (i.e., into a PanelLayout rather than a UINodeCard), but the registry and widget base classes remain unchanged.

### 5.3 Hot Reload

The existing hot-reload system (file watcher → registry events → factory cache clear → UINode re-render) continues to work for node body rendering. For editors and panels, hot-reload is handled by the same `BaseRegistry` machinery: when a library's editor or panel file changes, the file watcher triggers `EditorTypeRegistry.event_dispatcher()` or `PanelRegistry.event_dispatcher()`, which reloads the class and fires lifecycle events. Sessions react to these events by re-querying the registry and re-rendering affected areas.

Built-in framework editors and panels (bootstrapped directly in the DI provider) are part of the installed package and do not participate in hot-reload. Only library-contributed editors/panels (registered via `add_folder()`) support hot-reload.

### 5.4 Event System

The existing graph event system (`event_definitions.py`, `event_handlers.py`) stays internal to the GraphEditor (now under `graph_canvas/`). The new `ContextChangedEvent` system operates at the session level, bridging events from any editor to all other editors in the same session.

### 5.5 Multi-Session Data Sync

When Session A mutates graph data:

1. Mutation goes through the graph model's mutation API
2. Graph model emits a change notification
3. SessionManager iterates all connected sessions
4. Each session receives a `ContextChangedEvent(DATA_MUTATED)`
5. Each session's GraphEditor updates its canvas
6. Each session's PropertiesEditor re-evaluates panels (if they display mutated data)

---

## 6. Implementation Plan

### Phase 1: Foundation (No UI changes visible yet)

**Goal:** Create the abstract framework — registries, base classes, decorators, context system. Nothing renders yet, but the infrastructure is testable.

**Files to create:**
1. `packages/haywire-core/src/haywire/ui/context.py` — SessionContext, InteractionMode
2. `packages/haywire-core/src/haywire/ui/context_events.py` — ContextChangedEvent, ContextChangeType
3. `packages/haywire-core/src/haywire/ui/editor/identity.py` — EditorIdentity
4. `packages/haywire-core/src/haywire/ui/editor/base.py` — BaseEditor
5. `packages/haywire-core/src/haywire/ui/editor/decorator.py` — @editor
6. `packages/haywire-core/src/haywire/ui/editor/registry.py` — EditorTypeRegistry (extends BaseRegistry)
7. `packages/haywire-core/src/haywire/ui/panel/identity.py` — PanelIdentity
8. `packages/haywire-core/src/haywire/ui/panel/base.py` — BasePanel, PanelLayout
9. `packages/haywire-core/src/haywire/ui/panel/decorator.py` — @panel
10. `packages/haywire-core/src/haywire/ui/panel/registry.py` — PanelRegistry (extends BaseRegistry)
11. `packages/haywire-core/src/haywire/ui/workspace/workspace_state.py` — dataclasses
12. `packages/haywire-core/src/haywire/ui/workspace/manager.py` — WorkspaceManager
13. `packages/haywire-core/src/haywire/ui/session.py` — Session

**DI config additions:**

- Add `provide_editor_type_registry()` and `provide_panel_registry()` to `HaywireModule`
- Create `editors/builtins.py` and `panels/builtins.py` stub bootstrap functions (initially empty)

**Validation:** Unit tests for registries (register, query, hot-reload lifecycle). Unit tests for WorkspaceState serialization.

### Phase 2: Rename & Refactor Existing

**Goal:** Rename existing `haywire/ui/editor/` to `haywire/ui/graph_canvas/` and update all imports. This clears the namespace for the new editor framework. This must be a single atomic commit.

**Steps:**

1. `git mv packages/haywire-core/src/haywire/ui/editor packages/haywire-core/src/haywire/ui/graph_canvas`
2. Global search-and-replace all imports from `haywire.ui.editor.` → `haywire.ui.graph_canvas.`
3. Verify all tests pass
4. Update `__init__.py` exports if needed

### Phase 3: App Shell & Layout

**Goal:** Implement the AppShell that renders the workspace layout. At this point the layout is visible but editors are placeholder stubs.

**Files to create:**

1. `packages/haywire-core/src/haywire/ui/app_shell.py` — full NiceGUI layout implementation

**NiceGUI approach:**

- CSS Grid for the overall layout (ActivityBar | Left | Middle+Bottom | Right | ContextBar)
- `ui.splitter()` or CSS flexbox for resizable areas
- `ui.tabs()` + `ui.tab_panels()` for Middle Area tabs
- `ui.button(icon=...)` for ActivityBar and ContextBar items
- Tailwind utility classes for sizing and spacing

**Validation:** Layout renders correctly with placeholder content. Areas can be collapsed/expanded. Tabs work. ActivityBar/ContextBar switch editors.

### Phase 4: Wrap Existing Graph Editor

**Goal:** Wrap the existing GraphCanvasManager (now under `graph_canvas/`) into a GraphEditor class that implements the BaseEditor interface.

**Files to create:**

1. `packages/haywire-core/src/haywire/ui/editors/graph_editor.py`

**Changes to existing code:**

- GraphCanvasManager selection events → emit ContextChangedEvent(SELECTION_CHANGED) to the session
- GraphCanvasManager graph mutations → emit ContextChangedEvent(DATA_MUTATED)
- The GraphEditor's `render()` instantiates GraphCanvasManager into the provided container
- Update `editors/builtins.py` to register GraphEditor

**Validation:** The graph editor works exactly as before, but now inside the AppShell's middle area.

### Phase 5: Properties Editor & Panels

**Goal:** Implement the PropertiesEditor and a set of initial panels.

**Files to create:**

1. `packages/haywire-core/src/haywire/ui/editors/properties_editor.py`
2. `packages/haywire-core/src/haywire/ui/panels/node_properties_panel.py`
3. `packages/haywire-core/src/haywire/ui/panels/node_ports_panel.py`
4. `packages/haywire-core/src/haywire/ui/panels/node_settings_panel.py`
5. `packages/haywire-core/src/haywire/ui/panels/graph_info_panel.py`
6. `packages/haywire-core/src/haywire/ui/panels/edge_info_panel.py`
7. `packages/haywire-core/src/haywire/ui/panels/builtins.py` (register all built-in panels)

**PanelLayout implementation:** Flesh out the PanelLayout class to wrap NiceGUI primitives (ui.label, ui.row, ui.column, ui.expansion, etc.) and support the WidgetFactory for rendering port widgets.

**Validation:** Selecting a node in the graph → Properties Editor shows relevant panels. Deselecting → panels disappear. Different node types show different panels via poll().

### Phase 6: Console Editor

**Files to create:**

1. `packages/haywire-core/src/haywire/ui/editors/console_editor.py`

### Phase 7: Library Browser & Detail Editors

**Goal:** Implement the LibraryBrowser, LibraryDetailEditor, and ComponentDetailEditor in haywire-app.

**Files to create:**

1. `packages/haywire-app/src/haywire_app/editors/library_browser.py`
2. `packages/haywire-app/src/haywire_app/editors/library_detail_editor.py`
3. `packages/haywire-app/src/haywire_app/editors/component_detail_editor.py`

**Reference implementation:**

The existing `library_manager.py` and `library_manager_ui.py` are prototypical implementations that define the full feature set these three editors must cover. `LibraryManagerPage` in `library_manager_ui.py` already implements the exact three-panel layout (left = list, center = detail, right = component docs) as a monolithic class; the new editors are fresh, proper `BaseEditor` subclasses that implement the same panels individually. Study both files before implementing.

- Selection events wire through `session.notify_context_changed()` with `ACTIVE_LIBRARY_CHANGED` / `ACTIVE_COMPONENT_CHANGED`
- Register these editors in `haywire-app`'s startup (not via `register_builtin_editors()` — that's framework-only)

**Validation:** Clicking a library in the list → LibraryDetailEditor updates in the middle area. Clicking a node → ComponentDetailEditor updates in the right area.

### Phase 8: Multi-Session Support

**Goal:** Wire up the SessionManager so multiple browser windows see synchronized graph state.

**Changes:**

1. Create SessionManager that tracks all active sessions
2. Wire graph mutation notifications to all sessions
3. Ensure selection state remains per-session
4. Test: two browser windows, add a node in one, it appears in both

### Phase 9: Workspace Persistence

**Goal:** Implement save/load of workspace presets.

**Changes:**

1. Implement WorkspaceManager._persist_presets() and _load_user_presets()
2. Add workspace switcher UI to TopBar
3. Add "Save Workspace" and "Reset Workspace" controls
4. Ship default workspace presets

---

## 7. Design Principles

1. **Registries are global, editors are per-session.** Registries hold class references and metadata. Editors hold instance state tied to a specific browser client.

2. **Panels are the extension point.** Library developers extend the UI by shipping panels, not by modifying editors. A panel declares where it goes and when it's visible; the editor handles the rest.

3. **Context flows down, events flow up.** The SessionContext is the primary data carrier flowing into poll() and draw(). ContextChangedEvents flow up from editors to the session and then broadcast to all editors.

4. **The graph canvas is not special.** It's just another editor type. The SkinRegistry and node body rendering are internal concerns of the GraphEditor, not framework-level concepts.

5. **Widgets are shared atoms.** The same WidgetRegistry and widget classes are used in node bodies (inside the graph canvas) and in panels (inside the PropertiesEditor).

6. **Workspaces are just layout data.** A workspace is a serializable configuration of which editors are in which areas at what sizes. No behavior, just data.

7. **Last-write-wins for now.** Multi-session editing uses optimistic concurrency without conflict resolution. OT/CRDT is deferred.

8. **EditorTypeRegistry and PanelRegistry follow the BaseRegistry contract.** They participate in the same lifecycle event system, hot-reload chain, and DI pattern as all other registries. No special-casing or global singletons outside DI.

---

## 8. Risks & Open Questions

1. **NiceGUI layout performance.** The CSS Grid + nested splitters approach needs to be validated for smooth resizing and area collapse/expand. If NiceGUI's splitter has limitations, a custom Vue layout component may be needed (similar to how the graph canvas is a custom Vue component).

2. **Panel redraw cost.** If many panels exist and context changes are frequent, the poll/draw cycle could become expensive. Mitigation: panels opt into incremental updates via on_context_changed() rather than full re-renders.

3. **WidgetFactory in panel context.** The current WidgetFactory is tightly coupled to the node rendering pipeline (it tracks node IDs for hot-reload). Using widgets in panels requires either generalizing the factory or creating a lightweight panel-aware wrapper.

4. **graph_canvas/ rename scope.** The existing `editor/` folder rename (Phase 2) touches many imports. This should be done as a single atomic commit with comprehensive import verification.

5. **ActivityBar/ContextBar icon set.** Need to finalize which editors appear in each bar and their icons. LibraryBrowser, LibraryDetailEditor, and ComponentDetailEditor form a natural group in the ActivityBar (library browsing workflow).

6. **Tab management in Middle Area.** How tabs are created (user action? programmatic?), how they relate to graphs (one tab per graph?), and how tab state persists need detailed design during Phase 3.

7. **Library-contributed editors in haywire-app.** The LibraryBrowser, LibraryDetailEditor, and ComponentDetailEditor live in haywire-app and are bootstrapped by the app startup, not by `register_builtin_editors()`. A clear protocol for how haywire-app registers its own editors (without going through the library entry-point system) needs to be established in Phase 7.
