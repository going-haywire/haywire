# Panel Actions as Annotation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the `@panel(action=...)` decorator argument with an `actions: SomeProtocol` class-body type annotation. Split the panel registry's query API so each surface (PropertiesEditor / context menus) has a dedicated method. Delete the vestigial `PropertiesEditorActions` Protocol.

**Architecture:** Three orthogonal facets per panel — focus (routing topic), `actions:` annotation (verb surface), `redraw_on` (refresh signals). Single source of truth: the annotation tells both the framework what protocol to inject and the type checker what `self.actions` is. Framework reads annotations with `typing.get_type_hints(cls)` once at decoration time and stores the resolved protocol on `PanelIdentity`. Hard cutover, one feature branch.

**Tech Stack:** Python 3.11+, `typing.get_type_hints`, Protocol with `@runtime_checkable`, pytest. Codebase uses `from __future__ import annotations` widely — annotations live as strings and need resolution.

---

## Design context

This plan implements decisions reached in [handoff-panel-shape-annotation-actions.md](../../handoffs/handoff-panel-shape-annotation-actions.md) and refined in a follow-up inquisition session. Locked decisions:

- **D1 annotation-only** — no decorator argument. The `actions:` annotation is the single source of truth.
- **Decorator does the introspection** — not `__init_subclass__`. `@panel(...)` calls `typing.get_type_hints(cls)` and stores the resolved protocol.
- **`BasePanel.actions: Any = None`** as fallback. Display panels inherit `None`; action panels override with their narrower annotation.
- **`Optional[T]` stripped to `T`** — hard requirement, no opt-in-and-handle-missing pattern.
- **Hard cutover in one PR.**
- **Two registry methods**, each scoped to one surface:
  - `get_panels_for_focus(focus)` — PropertiesEditor; returns panels whose `action_protocol is None` AND focus matches
  - `get_panels_for_action(action_protocol, focus)` — context menus; returns panels whose `action_protocol` matches the host AND focus matches
- **One redraw method**: `get_redraw_signals_for_focus(focus)`. Context menus are ephemeral; no subscription set.
- **`get_focuses_for(...)` is reshaped** into `get_display_focuses()` returning focuses of all action-less (display) panels, deduped by `Focus.id`. PropertiesEditor uses this to build its toolbar.

### Open assumption flagged for confirmation before execution

The literal Q5 answer in the inquisition resolved `get_panels_for_action(action_protocol)` — focus-less. But [context_menu.py:252-269](../../../barn/haybale-studio/haybale_studio/editors/graph_canvas/handlers/context_menu.py#L252-L269) routes by both `(action_protocol, focus)` (e.g., `PortContextActions` with different focuses resolved from DOM scopes). This plan adopts the two-argument signature. **If you prefer focus-less context-menu queries, stop and adjust Task 2 before continuing.**

---

## File map

### Framework (modified)
- [packages/haywire-core/src/haywire/ui/panel/decorator.py](../../../packages/haywire-core/src/haywire/ui/panel/decorator.py) — drop `action=` arg; read `actions:` annotation via `get_type_hints`
- [packages/haywire-core/src/haywire/ui/panel/base.py](../../../packages/haywire-core/src/haywire/ui/panel/base.py) — add `actions: Any = None`; change `draw()` signature from `(self, ctx, layout, actions)` to `(self, ctx, layout)`
- [packages/haywire-core/src/haywire/ui/panel/identity.py](../../../packages/haywire-core/src/haywire/ui/panel/identity.py) — rename `action: Optional[type]` → `action_protocol: Optional[type]`
- [packages/haywire-core/src/haywire/ui/panel/registry.py](../../../packages/haywire-core/src/haywire/ui/panel/registry.py) — replace `get_panels_for` / `get_focuses_for` / `get_redraw_signals_for` with `get_panels_for_focus` / `get_panels_for_action` / `get_display_focuses` / `get_redraw_signals_for_focus`
- [packages/haywire-core/src/haywire/ui/panel/__init__.py](../../../packages/haywire-core/src/haywire/ui/panel/__init__.py) — update docstring

### Hosts (modified)
- [barn/haybale-studio/haybale_studio/editors/_context_menu_base.py](../../../barn/haybale-studio/haybale_studio/editors/_context_menu_base.py) — `_open_menu`: call `get_panels_for_action(action, focus)`; inject `self` into `panel.actions` before draw; drop the third positional arg to `draw()`
- [barn/haybale-studio/haybale_studio/editors/properties_editor.py](../../../barn/haybale-studio/haybale_studio/editors/properties_editor.py) — switch calls to `get_panels_for_focus`, `get_display_focuses`, `get_redraw_signals_for_focus`; remove `clear_selection()`; drop the `, self` arg in the `panel.draw(...)` call
- [barn/haybale-studio/haybale_studio/editors/graph_canvas/handlers/context_menu.py](../../../barn/haybale-studio/haybale_studio/editors/graph_canvas/handlers/context_menu.py) — no API changes (subclass passes the same `(action, focus, pos)` to the base's `_open_menu`)

### Deleted
- [barn/haybale-studio/haybale_studio/editors/properties_editor_actions.py](../../../barn/haybale-studio/haybale_studio/editors/properties_editor_actions.py) — entire file
- [barn/haybale-studio/haybale_studio/editors/__init__.py](../../../barn/haybale-studio/haybale_studio/editors/__init__.py) — drop `PropertiesEditorActions` import + `__all__` entry

### Panel sweep — properties-pane (~13 files)
For each file: remove the `from haybale_studio.editors.properties_editor_actions import PropertiesEditorActions` import, remove `action=PropertiesEditorActions,` from every `@panel(...)` call, change every `def draw(self, ctx, layout, actions: PropertiesEditorActions)` to `def draw(self, ctx, layout)`.

- [barn/haybale-studio/haybale_studio/panels/app_panels.py](../../../barn/haybale-studio/haybale_studio/panels/app_panels.py) (3 panels)
- [barn/haybale-studio/haybale_studio/panels/canvas_settings.py](../../../barn/haybale-studio/haybale_studio/panels/canvas_settings.py) (5 panels)
- [barn/haybale-studio/haybale_studio/panels/debug_panel.py](../../../barn/haybale-studio/haybale_studio/panels/debug_panel.py) (1 panel)
- [barn/haybale-studio/haybale_studio/panels/edge_panels.py](../../../barn/haybale-studio/haybale_studio/panels/edge_panels.py) (4 panels)
- [barn/haybale-studio/haybale_studio/panels/execution_panel.py](../../../barn/haybale-studio/haybale_studio/panels/execution_panel.py) (1 panel)
- [barn/haybale-studio/haybale_studio/panels/graph_info_panel.py](../../../barn/haybale-studio/haybale_studio/panels/graph_info_panel.py) (1 panel)
- [barn/haybale-studio/haybale_studio/panels/node_ports_panel.py](../../../barn/haybale-studio/haybale_studio/panels/node_ports_panel.py) (1 panel)
- [barn/haybale-studio/haybale_studio/panels/node_props_panel.py](../../../barn/haybale-studio/haybale_studio/panels/node_props_panel.py) (2 panels)
- [barn/haybale-studio/haybale_studio/panels/node_settings.py](../../../barn/haybale-studio/haybale_studio/panels/node_settings.py) (1 panel)
- [barn/haybale-studio/haybale_studio/panels/node_status.py](../../../barn/haybale-studio/haybale_studio/panels/node_status.py) (1 panel)
- [barn/haybale-studio/haybale_studio/panels/context_menu/node_errors.py](../../../barn/haybale-studio/haybale_studio/panels/context_menu/node_errors.py) — **note: file lives in `context_menu/` dir but uses `PropertiesEditorActions`. Treat as properties-pane.**

### Panel sweep — context-menu (~6 files)
For each file: remove `action=SomeContextActions,` from every `@panel(...)`, add `actions: SomeContextActions` as a class-body annotation under the class declaration, change `def draw(self, ctx, layout, actions: SomeContextActions)` to `def draw(self, ctx, layout)`, replace every `actions.X(...)` with `self.actions.X(...)`. Imports of the protocol stay (now used in the annotation).

- [barn/haybale-studio/haybale_studio/panels/context_menu/create_node_panel.py](../../../barn/haybale-studio/haybale_studio/panels/context_menu/create_node_panel.py)
- [barn/haybale-studio/haybale_studio/panels/context_menu/edge_actions.py](../../../barn/haybale-studio/haybale_studio/panels/context_menu/edge_actions.py)
- [barn/haybale-studio/haybale_studio/panels/context_menu/file_actions.py](../../../barn/haybale-studio/haybale_studio/panels/context_menu/file_actions.py)
- [barn/haybale-studio/haybale_studio/panels/context_menu/node_actions.py](../../../barn/haybale-studio/haybale_studio/panels/context_menu/node_actions.py)
- [barn/haybale-studio/haybale_studio/panels/context_menu/port_info.py](../../../barn/haybale-studio/haybale_studio/panels/context_menu/port_info.py)
- [barn/haybale-studio/haybale_studio/panels/context_menu/selection_actions.py](../../../barn/haybale-studio/haybale_studio/panels/context_menu/selection_actions.py)
- [barn/haybale-haystack/haybale_haystack/panels/file_browser/open_in_haystack.py](../../../barn/haybale-haystack/haybale_haystack/panels/file_browser/open_in_haystack.py)

### Panel sweep — testing library (5 files)
- [barn/haybale-testing/haybale_testing/panels/test_create_node_panel.py](../../../barn/haybale-testing/haybale_testing/panels/test_create_node_panel.py)
- [barn/haybale-testing/haybale_testing/panels/test_edge_panels.py](../../../barn/haybale-testing/haybale_testing/panels/test_edge_panels.py)
- [barn/haybale-testing/haybale_testing/panels/test_node_panels.py](../../../barn/haybale-testing/haybale_testing/panels/test_node_panels.py)
- [barn/haybale-testing/haybale_testing/panels/test_selection_panels.py](../../../barn/haybale-testing/haybale_testing/panels/test_selection_panels.py)
- [barn/haybale-testing/haybale_testing/panels/test_session_state_panel.py](../../../barn/haybale-testing/haybale_testing/panels/test_session_state_panel.py)

### Tests (modified)
- [tests/ui/panel/test_panel_decorator.py](../../../tests/ui/panel/test_panel_decorator.py) — assert new annotation behaviour; drop `action=` assertions
- [tests/ui/panel/test_panel_base.py](../../../tests/ui/panel/test_panel_base.py) — update for new `draw()` signature + `actions` attribute
- [tests/ui/panel/test_panel_registry_class_keyed.py](../../../tests/ui/panel/test_panel_registry_class_keyed.py) — rename / split tests for the new registry methods
- [tests/ui/panel/test_phase1_integration.py](../../../tests/ui/panel/test_phase1_integration.py) — update to new methods
- [tests/ui/test_panel_registry.py](../../../tests/ui/test_panel_registry.py) — same
- [tests/ui/test_panel_redraw_union.py](../../../tests/ui/test_panel_redraw_union.py) — rename to `_for_focus`, update fixtures
- [tests/ui/properties_editor/test_toolbar_discovery.py](../../../tests/ui/properties_editor/test_toolbar_discovery.py) — drop `PropertiesEditorActions` references; use display-focus query
- [tests/ui/properties_editor/test_event_bus_migration.py](../../../tests/ui/properties_editor/test_event_bus_migration.py) — same
- [tests/ui/test_file_browser_menu/test_session_file_menu_provider.py](../../../tests/ui/test_file_browser_menu/test_session_file_menu_provider.py) — update mock to new registry method names
- [tests/ui/test_canvas_handlers/test_session_context_menu_provider.py](../../../tests/ui/test_canvas_handlers/test_session_context_menu_provider.py) — same
- [tests/ui/graph_canvas/test_session_context_menu_provider.py](../../../tests/ui/graph_canvas/test_session_context_menu_provider.py) — same
- [tests/ui/test_canvas_handlers/test_haybale_context_menu_panels.py](../../../tests/ui/test_canvas_handlers/test_haybale_context_menu_panels.py) — update panel instantiation
- [tests/ui/test_canvas_handlers/test_create_node_panel.py](../../../tests/ui/test_canvas_handlers/test_create_node_panel.py) — same
- [tests/haystack/test_open_in_haystack_panel.py](../../../tests/haystack/test_open_in_haystack_panel.py) — same

### Docs (modified)
- [docs/components/panels/panel-canon.md](../../../docs/components/panels/panel-canon.md) — replace `action=` documentation with annotation pattern
- [docs/components/editors/editor-canon.md](../../../docs/components/editors/editor-canon.md) — update registry-query examples

---

## Tasks

### Task 1: Establish pre-edit baseline

CLAUDE.md mandates this for substantial multi-file refactors.

- [ ] **Step 1: Lint baseline for the framework area**

```bash
uv run ruff check packages/haywire-core/src/haywire/ui/panel/ barn/haybale-studio/haybale_studio/editors/ barn/haybale-studio/haybale_studio/panels/ barn/haybale-haystack/haybale_haystack/panels/ barn/haybale-testing/haybale_testing/panels/
```

Expected: clean (no errors). If there are pre-existing warnings, record them — anything new after the refactor is yours.

- [ ] **Step 2: Mypy baseline for the same area**

```bash
uv run mypy packages/haywire-core/src/haywire/ui/panel/ barn/haybale-studio/haybale_studio/editors/ barn/haybale-studio/haybale_studio/panels/ barn/haybale-haystack/haybale_haystack/panels/ barn/haybale-testing/haybale_testing/panels/
```

Expected: clean. Same rule — note pre-existing noise.

- [ ] **Step 3: Test baseline (relevant tests only)**

```bash
uv run pytest tests/ui/panel/ tests/ui/properties_editor/ tests/ui/test_panel_registry.py tests/ui/test_panel_redraw_union.py tests/ui/test_canvas_handlers/ tests/ui/test_file_browser_menu/ tests/ui/graph_canvas/test_session_context_menu_provider.py tests/haystack/test_open_in_haystack_panel.py -v
```

Expected: all pass. If any fail pre-edit, stop and investigate before continuing.

- [ ] **Step 4: Create the feature branch**

```bash
git checkout -b panel-actions-annotation
```

---

### Task 2: Refactor framework atomically

All five framework files change together in one commit. Intermediate states (between file edits within this task) will have broken tests — that's fine; the commit boundary is what matters.

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/panel/identity.py`
- Modify: `packages/haywire-core/src/haywire/ui/panel/base.py`
- Modify: `packages/haywire-core/src/haywire/ui/panel/decorator.py`
- Modify: `packages/haywire-core/src/haywire/ui/panel/registry.py`
- Modify: `packages/haywire-core/src/haywire/ui/panel/__init__.py`

- [ ] **Step 1: Update `PanelIdentity` — rename `action` to `action_protocol`**

Open [identity.py](../../../packages/haywire-core/src/haywire/ui/panel/identity.py). Replace lines 49-56 with:

```python
    editor_keys: list[str] = field(default_factory=list)
    scopes: list[str] = field(default_factory=list)
    icon: Optional[str] = None
    order: int = 100
    default_open: bool = True
    action_protocol: Optional[type] = None
    focus: Optional[type] = None
    redraw_on: Tuple[type["Signal"], ...] = ()
```

Update the docstring around lines 38-46 to describe `action_protocol` as "the Protocol/ABC class resolved from the panel's `actions:` annotation; `None` for display panels." Remove any mention of `action=` decorator argument.

- [ ] **Step 2: Update `BasePanel` — add `actions: Any = None`, drop `actions` from `draw`**

Open [base.py](../../../packages/haywire-core/src/haywire/ui/panel/base.py). Replace lines 26-71 with:

```python
class BasePanel(ABC):
    """Base class for panels.

    Subclasses are decorated with `@panel(...)` and inherit from `BasePanel`:

        @panel(focus=NodeFocus, label="Delete Node")
        class DeleteNodePanel(BasePanel):
            actions: NodeContextActions  # framework injects host at mount

            def draw(self, ctx, layout):
                self.actions.delete_node(...)

    Panels with no `actions:` annotation are display-only — `self.actions`
    stays `None`.
    """

    # Set by @panel decorator.
    class_identity: ClassVar["PanelIdentity"]

    # Host instance injected at mount time when the panel declares an
    # ``actions:`` annotation whose Protocol the host satisfies. Display
    # panels (no annotation) leave it as None.
    actions: Any = None

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        """Return whether the panel should currently be visible."""
        return True

    @abstractmethod
    def draw(
        self,
        ctx: "SessionContext",
        layout: "PanelLayout",
    ) -> None:
        """Render the panel's content. Called only when poll returned True."""
```

- [ ] **Step 3: Rewrite `@panel` decorator — drop `action=`, introspect annotations**

Open [decorator.py](../../../packages/haywire-core/src/haywire/ui/panel/decorator.py). Replace the file with:

```python
# packages/haywire-core/src/haywire/ui/panel/decorator.py
"""
@panel decorator for marking classes as Haywire panel types.

Resolves the panel's `actions:` annotation at decoration time via
`typing.get_type_hints`, records the protocol on PanelIdentity, and
sets class_identity. Does NOT register the class — registration happens
when the library calls add_folder() in register_components().

Usage::

    @panel(focus=NodeFocus, label='Delete Node')
    class DeleteNodePanel(BasePanel):
        actions: NodeContextActions   # framework injects host at mount

        def draw(self, ctx, layout):
            self.actions.delete_node(...)

Display panels omit the `actions:` annotation:

    @panel(focus=SettingsFocus, label='Workbench Settings')
    class ThemeSettingsPanel(BasePanel):
        def draw(self, ctx, layout):
            ...
"""

from __future__ import annotations

import typing
from typing import Any, Optional, Tuple, Union, get_args, get_origin

from haywire.core.library.utils import derive_library_identity, reg_key
from haywire.core.session.handlers import validate_signal_types

from .focus import Focus
from .identity import PanelIdentity
from .base import BasePanel


def _resolve_action_protocol(cls: type) -> Optional[type]:
    """Read the panel's `actions:` annotation and return the Protocol class.

    Returns None when the class (or any ancestor) does not declare its own
    `actions:` annotation narrower than BasePanel's `Any` fallback.

    `Optional[T]` / `Union[T, None]` is stripped to `T` per the locked
    design decision — annotations are hard requirements; no opt-in pattern.
    """
    own_annotations = cls.__dict__.get("__annotations__", {})
    if "actions" not in own_annotations:
        return None
    hints = typing.get_type_hints(cls)
    declared = hints.get("actions")
    if declared is None or declared is Any:
        return None
    origin = get_origin(declared)
    if origin is Union:
        non_none = [a for a in get_args(declared) if a is not type(None)]
        if len(non_none) != 1:
            raise TypeError(
                f"@panel: {cls.__name__}.actions must be a single Protocol/ABC "
                f"(Optional[T] is allowed and stripped to T); got Union of {non_none!r}"
            )
        declared = non_none[0]
    if not isinstance(declared, type):
        raise TypeError(
            f"@panel: {cls.__name__}.actions annotation must resolve to a class "
            f"(Protocol/ABC), got {declared!r}"
        )
    return declared


def panel(
    *,
    focus: Optional[type] = None,
    label: Optional[str] = None,
    icon: Optional[str] = None,
    order: int = 100,
    default_open: bool = True,
    description: str = "",
    registry_id: Optional[str] = None,
    redraw_on: Tuple[Any, ...] = (),
):
    """Decorator to mark a class as a panel.

    Always invoked with parentheses — `@panel(...)`. `focus=` and `label=`
    are required. The verb surface (if any) is declared via an `actions:`
    type annotation on the class body, not via this decorator.

    Args:
        focus:  Focus subclass that discriminates which session states this
                panel applies to. Required.
        label:  Human-readable display label. Required.
        icon:   Optional Material Design icon name.
        order:  Sort priority (lower = higher in the panel list). Default 100.
        default_open: Whether the panel starts expanded. Defaults to True.
        description:  Human-readable description.
        registry_id:  Unique ID for this panel. Defaults to the class name.
        redraw_on:    Tuple of Signal subclasses the panel wants its host
                      editor to redraw on. Empty tuple means no subscriptions.

    Raises:
        ValueError: If focus= or label= is missing.
        TypeError:  If focus is not a Focus subclass, the decorated class is
                    not a BasePanel subclass, the `actions:` annotation is
                    malformed, or any redraw_on= entry is not a Signal subclass.
    """
    if focus is None:
        raise ValueError("@panel requires focus= (Focus subclass).")
    if not (isinstance(focus, type) and issubclass(focus, Focus)):
        raise TypeError(f"@panel: focus= must be a Focus subclass, got {focus!r}")
    if label is None:
        raise ValueError("@panel requires label=.")

    validated_redraw_on = validate_signal_types(
        "@panel(..., redraw_on=...)", tuple(redraw_on), allow_empty=True
    )

    def decorator(inner_cls):
        if not issubclass(inner_cls, BasePanel):
            raise TypeError(f"@panel can only be applied to BasePanel subclasses, got {inner_cls}")

        action_protocol = _resolve_action_protocol(inner_cls)

        _registry_id = registry_id or inner_cls.__name__
        library_identity = derive_library_identity(inner_cls)
        _registry_key = reg_key(library_identity.id, "panel", _registry_id)

        inner_cls.class_identity = PanelIdentity(
            registry_id=_registry_id,
            registry_key=_registry_key,
            label=label,
            editor_keys=[],
            scopes=[],
            icon=icon,
            order=order,
            default_open=default_open,
            description=description,
            class_name=inner_cls.__name__,
            module=inner_cls.__module__,
            action_protocol=action_protocol,
            focus=focus,
            redraw_on=validated_redraw_on,
        )
        inner_cls.class_library = library_identity
        return inner_cls

    return decorator
```

- [ ] **Step 4: Rewrite `PanelRegistry` — split query methods**

Open [registry.py](../../../packages/haywire-core/src/haywire/ui/panel/registry.py). Replace the file with:

```python
# packages/haywire-core/src/haywire/ui/panel/registry.py
"""
PanelRegistry for managing panel registrations.

Extends BaseRegistry. Two query surfaces:
  - get_panels_for_focus(focus): display panels for PropertiesEditor —
    panels with no `action_protocol` whose focus matches.
  - get_panels_for_action(action_protocol, focus): action panels for
    context-menu hosts — panels whose `action_protocol` matches AND
    whose focus matches.
Focus matching is by Focus.id (stable across hot-reload).
"""

import inspect
import logging
from typing import Iterable, List, Set, TYPE_CHECKING

from haywire.core.registry.base import BaseRegistry
from haywire.core.library.identity import LibraryIdentity

from .base import BasePanel

if TYPE_CHECKING:
    from haywire.core.session.signals import Signal

logger = logging.getLogger(__name__)


class PanelRegistry(BaseRegistry):
    """Registry of panels.

    Provided as a DI singleton by HaywireModule.
    """

    def __init__(self):
        super().__init__()

    def _class_filter(self, cls) -> bool:
        """Return True if cls is a valid, decorated Panel subclass."""
        try:
            if not inspect.isclass(cls):
                return False
            if not hasattr(cls, "class_identity"):
                return False
            if cls is BasePanel:
                return False
            return issubclass(cls, BasePanel)
        except TypeError:
            return False

    def _register_class(self, cls: type[BasePanel], library_identity: LibraryIdentity) -> "str | None":
        registry_key = cls.class_identity.registry_key
        result = super()._register(registry_key, cls, library_identity)
        if result:
            action_protocol = getattr(cls.class_identity, "action_protocol", None)
            focus = getattr(cls.class_identity, "focus", None)
            logger.debug(
                f"PanelRegistry: Registered '{registry_key}' -> "
                f"action_protocol={getattr(action_protocol, '__name__', 'None')}, "
                f"focus={getattr(focus, '__name__', '?')}"
            )
        return result

    def _unregister_class(self, registry_key: str) -> "type | None":
        return super()._unregister(registry_key)

    # ------------------------------------------------------------------
    # Query API
    # ------------------------------------------------------------------

    def get_panels_for_focus(self, focus: type) -> List[type[BasePanel]]:
        """Display panels for the given focus.

        Returns panels whose ``action_protocol is None`` AND whose
        ``focus.id`` matches the given focus's id. Sorted by ``order``.

        Used by PropertiesEditor (long-lived, focus-routed surface).
        """
        wanted_id = getattr(focus, "id", None)
        result: List[type[BasePanel]] = []
        for cls in self._all_panel_classes():
            identity = getattr(cls, "class_identity", None)
            if identity is None:
                continue
            if getattr(identity, "action_protocol", None) is not None:
                continue
            panel_focus = getattr(identity, "focus", None)
            if panel_focus is None or getattr(panel_focus, "id", None) != wanted_id:
                continue
            result.append(cls)
        result.sort(key=lambda c: getattr(getattr(c, "class_identity", None), "order", 100))
        return result

    def get_panels_for_action(
        self,
        action_protocol: type,
        focus: type,
    ) -> List[type[BasePanel]]:
        """Action panels for the given (action_protocol, focus) pair.

        Returns panels whose ``action_protocol is action_protocol`` AND
        whose ``focus.id`` matches. Sorted by ``order``.

        Used by context-menu hosts. The host satisfies action_protocol
        structurally; mount-time injection sets ``panel.actions = host``.
        """
        wanted_focus_id = getattr(focus, "id", None)
        result: List[type[BasePanel]] = []
        for cls in self._all_panel_classes():
            identity = getattr(cls, "class_identity", None)
            if identity is None:
                continue
            if getattr(identity, "action_protocol", None) is not action_protocol:
                continue
            panel_focus = getattr(identity, "focus", None)
            if panel_focus is None or getattr(panel_focus, "id", None) != wanted_focus_id:
                continue
            result.append(cls)
        result.sort(key=lambda c: getattr(getattr(c, "class_identity", None), "order", 100))
        return result

    def get_display_focuses(self) -> List[type]:
        """Distinct focuses referenced by display panels (no action_protocol).

        Deduplicated by Focus.id. Used by PropertiesEditor to build its
        focus toolbar.
        """
        focuses: List[type] = []
        seen_ids: set[str] = set()
        for cls in self._all_panel_classes():
            identity = getattr(cls, "class_identity", None)
            if identity is None:
                continue
            if getattr(identity, "action_protocol", None) is not None:
                continue
            focus = getattr(identity, "focus", None)
            if focus is None:
                continue
            focus_id = getattr(focus, "id", None)
            if focus_id is None or focus_id in seen_ids:
                continue
            seen_ids.add(focus_id)
            focuses.append(focus)
        return focuses

    def get_redraw_signals_for_focus(self, focus: type) -> Set[type["Signal"]]:
        """Union of redraw_on signal types contributed by display panels
        for the given focus.

        Context-menu surfaces are ephemeral (open, draw, dismiss) and do
        not maintain a subscription set; only PropertiesEditor consumes
        this. Matching mirrors get_panels_for_focus.
        """
        wanted_id = getattr(focus, "id", None)
        signals: Set[type["Signal"]] = set()
        for cls in self._all_panel_classes():
            identity = getattr(cls, "class_identity", None)
            if identity is None:
                continue
            if getattr(identity, "action_protocol", None) is not None:
                continue
            panel_focus = getattr(identity, "focus", None)
            if panel_focus is None or getattr(panel_focus, "id", None) != wanted_id:
                continue
            signals.update(getattr(identity, "redraw_on", ()))
        return signals

    def _all_panel_classes(self) -> Iterable[type]:
        return self._classes.values()
```

- [ ] **Step 5: Update the package `__init__.py` docstring**

Open [packages/haywire-core/src/haywire/ui/panel/__init__.py](../../../packages/haywire-core/src/haywire/ui/panel/__init__.py). Replace any doctring lines mentioning `get_panels_for(actions_provider, focus)` with the two-method API; replace any `action=` examples with the annotation form. (Don't change the exported symbols unless the file re-exports something that was renamed.)

- [ ] **Step 6: Commit the framework refactor**

```bash
git add packages/haywire-core/src/haywire/ui/panel/
git commit -m "refactor(panel): replace action= decorator arg with actions: annotation

Framework-only commit. Hosts and panels are updated in subsequent commits.
- @panel(...) no longer takes action=; resolves actions: annotation via get_type_hints
- BasePanel.draw signature becomes (ctx, layout); host injection sets self.actions
- PanelRegistry splits queries: get_panels_for_focus, get_panels_for_action,
  get_display_focuses, get_redraw_signals_for_focus"
```

---

### Task 3: Update PropertiesEditor to the new registry API

**Files:**
- Modify: `barn/haybale-studio/haybale_studio/editors/properties_editor.py`

- [ ] **Step 1: Drop the `PropertiesEditorActions` Protocol implementation method**

Remove [properties_editor.py:283-294](../../../barn/haybale-studio/haybale_studio/editors/properties_editor.py#L283-L294) (the `# PropertiesEditorActions Protocol implementation` block plus the `clear_selection` method). Verified unused: `grep -rn "clear_selection" barn/ packages/ tests/` returns only this declaration.

- [ ] **Step 2: Switch `_compute_toolbar_focuses` to `get_display_focuses`**

Replace [properties_editor.py:334-337](../../../barn/haybale-studio/haybale_studio/editors/properties_editor.py#L334-L337):

```python
    def _compute_toolbar_focuses(self, panel_registry: PanelRegistry) -> list[type[Focus]]:
        """Compute toolbar focuses from the panel registry, sorted by Focus.order."""
        focuses = panel_registry.get_display_focuses()
        return sorted(focuses, key=lambda f: f.order)
```

- [ ] **Step 3: Switch `_mount_panels_for_active_focus` to `get_panels_for_focus`**

Replace [properties_editor.py:408-412](../../../barn/haybale-studio/haybale_studio/editors/properties_editor.py#L408-L412):

```python
    def _mount_panels_for_active_focus(
        self, panel_registry: PanelRegistry, focus: type[Focus]
    ) -> list[type[BasePanel]]:
        """Mount panels matching the active focus (display panels only)."""
        return panel_registry.get_panels_for_focus(focus)
```

- [ ] **Step 4: Switch `_rebuild_panel_event_subscriptions` to per-focus redraw union**

Replace [properties_editor.py:153-176](../../../barn/haybale-studio/haybale_studio/editors/properties_editor.py#L153-L176):

```python
    def _rebuild_panel_event_subscriptions(self) -> None:
        """Recompute the panel-contributed event-bus subscription set.

        Drops current subs, queries the registry for the union of
        redraw_on signals across display panels of every focus this
        editor exposes, and re-subscribes.
        """
        self._unsubscribe_panel_event_handlers()
        registry = self._attached_panel_registry
        context = self._context
        if registry is None or context is None:
            return
        signal_types: set = set()
        try:
            for focus in self._compute_toolbar_focuses(registry):
                signal_types |= registry.get_redraw_signals_for_focus(focus)
        except Exception as exc:
            logger.warning(f"PropertiesEditor: get_redraw_signals_for_focus raised: {exc}")
            return
        if not signal_types:
            return
        bus_subscribe = context.session.subscribe
        redraw_closure = self._make_panel_redraw_closure()
        for signal_type in signal_types:
            self._panel_bus_unsubscribes.append(bus_subscribe(signal_type, redraw_closure))
```

- [ ] **Step 5: Drop the `, self` host arg from the `panel.draw(...)` call**

Replace [properties_editor.py:457-458](../../../barn/haybale-studio/haybale_studio/editors/properties_editor.py#L457-L458):

```python
                    try:
                        panel_cls().draw(context, layout)
```

(Display panels have no `actions:` annotation; the framework leaves `panel.actions = None`. They never reference `self.actions`.)

- [ ] **Step 6: Update the module docstring**

Replace the docstring at the top of the file (lines 1-17) — drop the `actions_provider, focus` lookup mention; describe the new API:

```python
"""
PropertiesEditor — focus-driven properties sidebar.

Displays a left-hand icon toolbar (one button per Focus) and a content area
showing display panels registered against the active Focus. The toolbar is
sourced from ``registry.get_display_focuses()``; panels are mounted via
``registry.get_panels_for_focus(focus)``.

Active-focus state is held per-editor on ``self._active_focus_id``. The
active focus is never changed automatically once set.
"""
```

- [ ] **Step 7: Commit**

```bash
git add barn/haybale-studio/haybale_studio/editors/properties_editor.py
git commit -m "refactor(properties-editor): use focus-only registry queries

- Toolbar uses get_display_focuses
- Content uses get_panels_for_focus
- Redraw union summed across focuses via get_redraw_signals_for_focus
- Drops clear_selection (unused) and the actions positional in draw()"
```

---

### Task 4: Update the context-menu base provider

**Files:**
- Modify: `barn/haybale-studio/haybale_studio/editors/_context_menu_base.py`

- [ ] **Step 1: Rewrite `_open_menu` to use the new API + injection**

Replace [_context_menu_base.py:50-88](../../../barn/haybale-studio/haybale_studio/editors/_context_menu_base.py#L50-L88):

```python
    def _open_menu(
        self,
        action: type,
        focus: type,
        pos: Tuple[float, float],
        on_close: Optional[Callable[[], None]] = None,
    ) -> None:
        """Build popup, query panels for (action, focus), inject self as the
        actions provider on each mounted panel, draw matched ones.

        on_close: subclass-supplied additional cleanup, called when the
        popup closes (after the base clears _open_popup).
        """
        popup = self._build_popup(pos)
        self._open_popup = popup

        def _wrapped_on_close() -> None:
            self._open_popup = None
            if on_close is not None:
                try:
                    on_close()
                except Exception as exc:
                    logger.exception(f"on_close handler raised: {exc}")

        popup.on_close(_wrapped_on_close)

        panel_classes = self._panel_registry.get_panels_for_action(action, focus)
        visible = [cls for cls in panel_classes if cls.poll(self._context)]
        if not visible:
            return

        layout = PanelLayout(popup.content)
        for cls in visible:
            try:
                instance = cls()
                instance.actions = self  # host injection — see BasePanel.actions
                instance.draw(self._context, layout)
            except Exception as exc:
                logger.exception(f"Error drawing context menu panel {cls.__name__}: {exc}")
        popup.open()
```

- [ ] **Step 2: Commit**

```bash
git add barn/haybale-studio/haybale_studio/editors/_context_menu_base.py
git commit -m "refactor(context-menu): query by (action, focus) and inject host into panel.actions"
```

---

### Task 5: Delete the vestigial PropertiesEditorActions Protocol

**Files:**
- Delete: `barn/haybale-studio/haybale_studio/editors/properties_editor_actions.py`
- Modify: `barn/haybale-studio/haybale_studio/editors/__init__.py`

- [ ] **Step 1: Delete the file**

```bash
git rm barn/haybale-studio/haybale_studio/editors/properties_editor_actions.py
```

- [ ] **Step 2: Remove the export**

Open [editors/__init__.py](../../../barn/haybale-studio/haybale_studio/editors/__init__.py). Delete line 11 (`from .properties_editor_actions import PropertiesEditorActions`) and the `"PropertiesEditorActions",` entry from `__all__` (line 24).

- [ ] **Step 3: Commit**

```bash
git add barn/haybale-studio/haybale_studio/editors/__init__.py
git commit -m "chore: delete vestigial PropertiesEditorActions Protocol

Empty marker Protocol; no callers ever invoked its single declared
method (clear_selection)."
```

---

### Task 6: Sweep properties-pane panels (drop action=, drop draw arg)

**Files (apply the pattern below to each):**

- `barn/haybale-studio/haybale_studio/panels/app_panels.py`
- `barn/haybale-studio/haybale_studio/panels/canvas_settings.py`
- `barn/haybale-studio/haybale_studio/panels/debug_panel.py`
- `barn/haybale-studio/haybale_studio/panels/edge_panels.py`
- `barn/haybale-studio/haybale_studio/panels/execution_panel.py`
- `barn/haybale-studio/haybale_studio/panels/graph_info_panel.py`
- `barn/haybale-studio/haybale_studio/panels/node_ports_panel.py`
- `barn/haybale-studio/haybale_studio/panels/node_props_panel.py`
- `barn/haybale-studio/haybale_studio/panels/node_settings.py`
- `barn/haybale-studio/haybale_studio/panels/node_status.py`
- `barn/haybale-studio/haybale_studio/panels/context_menu/node_errors.py`

**Pattern per file (same in every one):**

- [ ] **Step 1: Drop the import**

Remove the line:

```python
from haybale_studio.editors.properties_editor_actions import PropertiesEditorActions
```

- [ ] **Step 2: Drop `action=PropertiesEditorActions,` from every `@panel(...)` call**

For each decorator in the file:

```python
# Before
@panel(
    action=PropertiesEditorActions,
    focus=SomeFocus,
    label="...",
    ...
)

# After
@panel(
    focus=SomeFocus,
    label="...",
    ...
)
```

- [ ] **Step 3: Change every `draw` method signature**

For each `class XxxPanel(BasePanel):` in the file:

```python
# Before
    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: PropertiesEditorActions,
    ) -> None:
        ...

# After
    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        ...
```

If any panel body references `actions.xxx(...)`, that's a bug pre-existing in the codebase (the protocol was empty); flag it but do NOT silently delete the call. Stop and ask.

- [ ] **Step 4: Verify the file lints + types**

```bash
uv run ruff check <file>
uv run mypy <file>
```

Both should be clean. If `mypy` complains about the unused `PropertiesEditorActions` import, you forgot Step 1.

- [ ] **Step 5: Run tests for this panel group (after all files in the group are done)**

```bash
uv run pytest tests/ui/properties_editor/ tests/ui/panel/ -v
```

Some tests will still be broken (Task 9). That's OK at this step — just check that the failures are about test code, not about your panel edits.

- [ ] **Step 6: Commit (group all properties-pane panel files into one commit)**

```bash
git add barn/haybale-studio/haybale_studio/panels/app_panels.py \
        barn/haybale-studio/haybale_studio/panels/canvas_settings.py \
        barn/haybale-studio/haybale_studio/panels/debug_panel.py \
        barn/haybale-studio/haybale_studio/panels/edge_panels.py \
        barn/haybale-studio/haybale_studio/panels/execution_panel.py \
        barn/haybale-studio/haybale_studio/panels/graph_info_panel.py \
        barn/haybale-studio/haybale_studio/panels/node_ports_panel.py \
        barn/haybale-studio/haybale_studio/panels/node_props_panel.py \
        barn/haybale-studio/haybale_studio/panels/node_settings.py \
        barn/haybale-studio/haybale_studio/panels/node_status.py \
        barn/haybale-studio/haybale_studio/panels/context_menu/node_errors.py
git commit -m "refactor(panels): drop PropertiesEditorActions from display panels"
```

---

### Task 7: Sweep context-menu panels (drop action=, add actions: annotation)

**Files:**

- `barn/haybale-studio/haybale_studio/panels/context_menu/create_node_panel.py`
- `barn/haybale-studio/haybale_studio/panels/context_menu/edge_actions.py`
- `barn/haybale-studio/haybale_studio/panels/context_menu/file_actions.py`
- `barn/haybale-studio/haybale_studio/panels/context_menu/node_actions.py`
- `barn/haybale-studio/haybale_studio/panels/context_menu/port_info.py`
- `barn/haybale-studio/haybale_studio/panels/context_menu/selection_actions.py`
- `barn/haybale-haystack/haybale_haystack/panels/file_browser/open_in_haystack.py`

**Pattern per file (illustrated against `node_actions.py`; apply identically to others):**

- [ ] **Step 1: Drop `action=...,` from every `@panel(...)` call**

```python
# Before
@panel(
    action=NodeContextActions,
    focus=NodeFocus,
    label="Delete Node",
    icon=hui.icon.delete,
    order=10,
)

# After
@panel(
    focus=NodeFocus,
    label="Delete Node",
    icon=hui.icon.delete,
    order=10,
)
```

- [ ] **Step 2: Add the `actions:` class-body annotation**

For each panel class, add the annotation immediately under the `class` line, BEFORE `poll` / `draw`:

```python
# Before
class DeleteNodePanel(BasePanel):
    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return ctx.data[EditState].active_node is not None

# After
class DeleteNodePanel(BasePanel):
    actions: NodeContextActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return ctx.data[EditState].active_node is not None
```

- [ ] **Step 3: Change `draw` signature and access `self.actions`**

For each panel:

```python
# Before
    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: NodeContextActions,
    ) -> None:
        node = ctx.data[EditState].active_node
        if node is None:
            return
        node_id = node.node_id
        layout.button(
            "Delete Node",
            icon=hui.icon.delete,
            on_click=lambda: actions.delete_node(node_id),
        )

# After
    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        node = ctx.data[EditState].active_node
        if node is None:
            return
        node_id = node.node_id
        layout.button(
            "Delete Node",
            icon=hui.icon.delete,
            on_click=lambda: self.actions.delete_node(node_id),
        )
```

Imports of the protocol stay (now consumed by the annotation).

- [ ] **Step 4: Verify the file lints + types**

```bash
uv run ruff check <file>
uv run mypy <file>
```

If mypy reports `self.actions` as `Any` instead of `NodeContextActions`, double-check the annotation line lives at class-body level (not inside a method).

- [ ] **Step 5: Commit (group all context-menu panel files into one commit)**

```bash
git add barn/haybale-studio/haybale_studio/panels/context_menu/create_node_panel.py \
        barn/haybale-studio/haybale_studio/panels/context_menu/edge_actions.py \
        barn/haybale-studio/haybale_studio/panels/context_menu/file_actions.py \
        barn/haybale-studio/haybale_studio/panels/context_menu/node_actions.py \
        barn/haybale-studio/haybale_studio/panels/context_menu/port_info.py \
        barn/haybale-studio/haybale_studio/panels/context_menu/selection_actions.py \
        barn/haybale-haystack/haybale_haystack/panels/file_browser/open_in_haystack.py
git commit -m "refactor(panels): context-menu panels use actions: annotation"
```

---

### Task 8: Sweep the haybale-testing library panels

**Files:**
- `barn/haybale-testing/haybale_testing/panels/test_create_node_panel.py`
- `barn/haybale-testing/haybale_testing/panels/test_edge_panels.py`
- `barn/haybale-testing/haybale_testing/panels/test_node_panels.py`
- `barn/haybale-testing/haybale_testing/panels/test_selection_panels.py`
- `barn/haybale-testing/haybale_testing/panels/test_session_state_panel.py`

- [ ] **Step 1: Inspect each file to determine which pattern applies**

For each file, grep for the action protocol imported. If it's `PropertiesEditorActions`, apply Task 6's pattern. Otherwise apply Task 7's pattern.

```bash
grep -n "action=" barn/haybale-testing/haybale_testing/panels/*.py
```

- [ ] **Step 2: Apply the appropriate pattern per file**

(Same as Task 6 or Task 7; refer to those.)

- [ ] **Step 3: Verify lints + types**

```bash
uv run ruff check barn/haybale-testing/haybale_testing/panels/
uv run mypy barn/haybale-testing/haybale_testing/panels/
```

- [ ] **Step 4: Commit**

```bash
git add barn/haybale-testing/haybale_testing/panels/
git commit -m "refactor(haybale-testing): update test-library panels to annotation pattern"
```

---

### Task 9: Update registry-API tests

**Files:**
- `tests/ui/test_panel_registry.py`
- `tests/ui/test_panel_redraw_union.py`
- `tests/ui/panel/test_panel_registry_class_keyed.py`
- `tests/ui/panel/test_phase1_integration.py`

For each test file, the editing pattern is the same:

- [ ] **Step 1: Rename references to old methods**

| Old call | New call |
|---|---|
| `reg.get_panels_for(actions_provider=p, focus=F)` | If `p` is a "host" stub satisfying a protocol → `reg.get_panels_for_action(SomeProtocol, F)`. If `p` is a no-op stub for a display panel test → `reg.get_panels_for_focus(F)` |
| `reg.get_focuses_for(actions_provider=p)` | `reg.get_display_focuses()` (and adjust the test to register display panels, not action panels) |
| `reg.get_redraw_signals_for(p)` | `reg.get_redraw_signals_for_focus(F)` |

- [ ] **Step 2: Update test panel declarations**

Any `@panel(action=..., focus=...)` in a test fixture becomes `@panel(focus=...)` with an `actions: ProtoT` annotation if the test exercises the action path, or no annotation if it's a display panel test.

- [ ] **Step 3: Run the file in isolation after edits**

```bash
uv run pytest <test_file> -v
```

Expected: all tests pass.

- [ ] **Step 4: Commit per-file or batch-commit**

```bash
git add tests/ui/test_panel_registry.py tests/ui/test_panel_redraw_union.py \
        tests/ui/panel/test_panel_registry_class_keyed.py \
        tests/ui/panel/test_phase1_integration.py
git commit -m "test(panel-registry): update for split query API"
```

---

### Task 10: Update panel-shape tests (decorator, base, mount sites)

**Files:**
- `tests/ui/panel/test_panel_decorator.py` — assert `@panel` no longer accepts `action=`; assert annotation introspection populates `class_identity.action_protocol`
- `tests/ui/panel/test_panel_base.py` — assert `BasePanel.actions is None`; assert `draw` signature change
- `tests/ui/panel/test_panel_error_boundary.py` — update any panel fixtures
- `tests/ui/properties_editor/test_toolbar_discovery.py` — drop `PropertiesEditorActions` import/use; switch to display panels
- `tests/ui/properties_editor/test_event_bus_migration.py` — same
- `tests/ui/test_file_browser_menu/test_session_file_menu_provider.py` — update mock to new method names
- `tests/ui/test_canvas_handlers/test_session_context_menu_provider.py` — same
- `tests/ui/graph_canvas/test_session_context_menu_provider.py` — same
- `tests/ui/test_canvas_handlers/test_haybale_context_menu_panels.py` — update panel instantiation; panels are now mounted as `cls(); instance.actions = host; instance.draw(ctx, layout)`
- `tests/ui/test_canvas_handlers/test_create_node_panel.py` — same
- `tests/haystack/test_open_in_haystack_panel.py` — same
- `tests/ui/graph_canvas/test_context_menu_actions.py` — verify whether anything in it touches the actions plumbing; if so, update
- `tests/ui/harness/test_graph_context_menu.py` — same

Pattern for "mount and exercise a panel" tests:

```python
# Before
panel = MyPanel()
panel.draw(ctx, layout, host)

# After
panel = MyPanel()
panel.actions = host  # explicit injection (or skip for display panels)
panel.draw(ctx, layout)
```

Pattern for "registry returns the right panel" tests:

```python
# Before
panels = reg.get_panels_for(actions_provider=host, focus=NodeFocus)
# After (context-menu flavour)
panels = reg.get_panels_for_action(NodeContextActions, NodeFocus)
# After (properties-pane flavour)
panels = reg.get_panels_for_focus(SettingsFocus)
```

- [ ] **Step 1: Update each test file using the patterns above**
- [ ] **Step 2: Run the full test sweep**

```bash
uv run pytest tests/ui/panel/ tests/ui/properties_editor/ tests/ui/test_canvas_handlers/ tests/ui/test_file_browser_menu/ tests/ui/graph_canvas/ tests/ui/harness/ tests/haystack/ tests/ui/test_panel_registry.py tests/ui/test_panel_redraw_union.py -v
```

Expected: all pass.

- [ ] **Step 3: Commit**

```bash
git add tests/
git commit -m "test: update mount sites and host stubs for annotation-based actions"
```

---

### Task 11: Update documentation

**Files:**
- `docs/components/panels/panel-canon.md`
- `docs/components/editors/editor-canon.md`

- [ ] **Step 1: Read `panel-canon.md` and locate every `action=` mention**

```bash
grep -n "action=" docs/components/panels/panel-canon.md
```

- [ ] **Step 2: Replace each example**

For every `@panel(action=X, focus=Y, label='Z')` example: drop `action=X,` and add `actions: X` to the class body (action-panel examples) or leave it off entirely (display-panel examples). Update the prose describing the three primitives — focus/annotation/redraw — to match the implemented model from the handoff:

> A panel has three orthogonal facets: focus (where it appears), the `actions:` annotation (what it can invoke on its host), and `redraw_on` (when it re-renders). The `actions:` annotation is read by the framework at decoration time via `typing.get_type_hints` and stored on `PanelIdentity.action_protocol`. At mount time the framework sets `panel.actions = host` if the host satisfies the protocol.

- [ ] **Step 3: Update `editor-canon.md` registry-query examples**

```bash
grep -n "get_panels_for\|get_focuses_for\|get_redraw_signals_for" docs/components/editors/editor-canon.md
```

Replace each example to use the four new methods, with a note that display vs action surfaces use distinct queries.

- [ ] **Step 4: Preview the docs site to confirm rendering**

```bash
uv run mkdocs serve
```

Browse to `http://127.0.0.1:8000` and visit the panel and editor canon pages. Ctrl-C when done.

- [ ] **Step 5: Commit**

```bash
git add docs/components/panels/panel-canon.md docs/components/editors/editor-canon.md
git commit -m "docs: update panel and editor canons for annotation-based actions"
```

---

### Task 12: Full verification

- [ ] **Step 1: Full lint**

```bash
uv run ruff check .
```

Expected: clean (compare to Task 1 baseline; nothing new).

- [ ] **Step 2: Full format check**

```bash
uv run ruff format --check .
```

If anything diverges, run `uv run ruff format .` and amend the most recent commit, or open a small fixup commit.

- [ ] **Step 3: Full mypy**

```bash
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-visiongraph/haybale_visiongraph/ barn/haybale-TEST_A/haybale_test_a/
```

Expected: clean (compare to Task 1 baseline). Any new errors are yours; fix them.

- [ ] **Step 4: Full test suite — non-integration**

```bash
uv run pytest -m "not integration" -v
```

Expected: all pass.

- [ ] **Step 5: Full test suite — integration**

```bash
uv run pytest -m integration -v
```

Expected: all pass. Slower; budget time.

- [ ] **Step 6: Manual smoke**

```bash
uv run haywire
```

In the running app:
1. Open a graph. Confirm the properties editor's focus tabs render (Settings, Graph, etc.).
2. Click a node — confirm node-specific properties panels appear.
3. Right-click the node — confirm Delete/Copy/Redraw/Revalidate/Reset all appear and work.
4. Right-click an edge — confirm Delete + Reconnect appear and work.
5. Right-click a port — confirm port-info panel appears.
6. Right-click on empty canvas — confirm Create-Node + Paste appear.
7. Open the file browser, right-click a file — confirm "Open in Haystack" + file actions appear.

If any context menu is empty when it shouldn't be, the focus/protocol routing is wrong — check the relevant `get_panels_for_action` call and the panel's `focus=` / `actions:` declaration.

Ctrl-C when done.

- [ ] **Step 7: Commit anything that came out of verification, then push**

```bash
git status                              # confirm clean working tree
git push -u origin panel-actions-annotation
```

- [ ] **Step 8: Open PR (only when user confirms)**

Do not auto-open the PR. Report the branch name + commit log to the user; let them decide when to publish.

---

## Self-review notes

The plan was checked against the handoff and the inquisition resolutions:

- **D1 annotation-only**: Task 2 Step 3 (decorator rewrite) drops `action=` entirely; Task 2 Step 4 reads the annotation via `get_type_hints`.
- **Decorator does introspection (not `__init_subclass__`)**: Task 2 Step 3 places `_resolve_action_protocol(inner_cls)` inside the decorator's inner function, not in `BasePanel`.
- **`actions: Any = None` fallback**: Task 2 Step 2.
- **`Optional[T]` stripped**: `_resolve_action_protocol` handles this explicitly in Task 2 Step 3.
- **Hard cutover**: every commit lives on one feature branch; the PR squashes-or-merges as one unit.
- **`get_type_hints` once at decoration time**: Task 2 Step 3.
- **Two registry methods + display-focus helper**: Task 2 Step 4.
- **Single redraw method (focus-only)**: Task 2 Step 4.
- **Hot-reload behaviour**: class-identity `is` matching for `action_protocol` (Task 2 Step 4), `Focus.id` matching for focus — matches the existing precedent in the registry.

Type consistency: `action_protocol` is the field name on `PanelIdentity` (Task 2 Step 1) and the parameter name on `get_panels_for_action` (Task 2 Step 4) — no drift. `get_display_focuses` (Task 2 Step 4) is the same name PropertiesEditor calls (Task 3 Step 2).

Placeholder scan: no "TBD" / "implement appropriately" / "similar to above" instances. Every code-changing step shows the exact code to write.

Spec gap check: every locked decision from the handoff is implemented by an enumerated task. The one open assumption (`get_panels_for_action(action_protocol, focus)` — two args, not one) is flagged at the top under "Open assumption flagged for confirmation before execution."
