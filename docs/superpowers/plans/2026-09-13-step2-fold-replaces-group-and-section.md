# Fold Replaces Group And Section Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `group()` and `section()` with a single `fold()` — a pin-less, widget-less boolean port opened by a disclosure triangle, which the author declares by name alone.

**Architecture:** A fold is a real port, as a group already is: it holds the open/closed state, serializes, and parents its children through `parent_group`. What changes is that the author supplies only a name — the framework mints a `BOOL` config port (config ⇒ `has_pin()` false ⇒ no edge handle) with its widget explicitly cleared, so the disclosure triangle is the only affordance. `section()` is deleted outright: no node in the repository declares one, and its `is_section` flag is dead code. See [ADR-0035](../../adr/0035-fold-replaces-group-and-section.md).

**Tech Stack:** Python 3.12, NiceGUI 3.13, pytest.

## Global Constraints

- **Depends on:** Step 1 (`2026-09-13-step1-fold-depth-indentation.md`) must land first. Nesting is only safe once depth insets the content column rather than the whole row.
- Line length 109 (`ruff`). CI runs BOTH `ruff check .` and `ruff format --check .`.
- `fold()` mints the port via `BOOL.as_config(...)`, which resolves `store_strategy` to `ALWAYS` (`interface.py:366`) because `BOOL`'s identity sets none. **Do not** let it inherit `BOOL`'s `widget_key=SWITCH_WIDGET` — pass `widget_key=None` explicitly, or the fold renders a switch.
- A fold takes exactly one direction, inferred from its children. Mixing raises at declaration time.
- Folds nest to any depth.
- The label is a section name, not an imperative — reflect that in docstrings and in the migrated call sites.

### ⚠️ How to build a test node with real ports

**There is no fixture that builds an inline test node.** `test_node_factory`
does not exist; `node_factory` is a DI `NodeFactory` keyed by *registry key*,
and a `@node` class declared inside a test file is never registered (registration
is a library folder scan, not the decorator). So a `@node` probe class written in
a test module cannot be built and has no ports.

The pattern every existing port-level test uses (see
`tests/core/test_types/test_add_type.py:227-233`):

1. Add the probe node as a real module under
   `barn/haybale-testing/haybale_testing/nodes/testbed/`, decorated with
   `@node(..., menu="testing/testbed")` — copy
   `dynamic_port_test.py` for shape.
2. In the test, take the `graph_with_library_system` fixture and build it:

```python
def _make_probe(graph, position=(100.0, 100.0)):
    from haybale_testing.nodes.testbed.fold_probe import FoldProbeNode

    wrapper = graph.create_node_wrapper(
        FoldProbeNode.class_identity.registry_key, position=position
    )
    assert wrapper is not None, "node creation failed"
    return wrapper.node
```

Consequences that change what the tests in this plan look like:

- These are **integration** tests. `graph_with_library_system` depends on
  `library_system`, so mark them `pytestmark = pytest.mark.integration`, NOT
  `pytest.mark.unit`. Run them with `uv run pytest -m integration`.
- Every probe node in this plan's tests must become a file under
  `barn/haybale-testing/.../testbed/`, and the test imports it by that path.
- ⚠️ **`tests/studio/test_docs/test_generate.py:31` runs
  `git checkout -- barn/haybale-testing` in its teardown**, which deletes
  untracked files there. **Commit each new probe node before running any suite
  that includes that test**, or it vanishes and the failure surfaces somewhere
  else entirely.

Tests that only inspect a *class* (e.g. `class_identity`, a signature, an
`inspect.getsource` assertion) need none of this and stay unit tests.

## Pre-Flight Baseline

```sh
uv run ruff check packages/haywire-core/src/haywire/core/node/ packages/haywire-core/src/haywire/core/types/
uv run mypy packages/haywire-core/src/haywire/core/
uv run pytest tests/core/test_node/ -q
```

All clean before starting.

## File Structure

| File | Responsibility |
|---|---|
| `packages/haywire-core/src/haywire/core/node/data.py` | Owns `add`, `group`, `section`, `rejig`, the iteration helpers. Gains `fold()`; loses `section()` and every section-only helper. |
| `packages/haywire-core/src/haywire/core/types/port.py` | Owns `DataPort`. Loses `section` and the dead `is_section`. |
| `barn/haybale-studio/haybale_studio/skins/stacked_skin.py` | Renders the fold header as a disclosure triangle instead of a switch widget. |
| `barn/haybale-*/…` (5 call sites) | Migrated from `self.group(GROUP.as_config(...))` to `self.fold(...)`. |
| `tests/core/test_node/test_fold.py` | New. Minting, direction scoping, nesting, persistence. |

---

### Task 1: `fold()` mints a pin-less, widget-less container port

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/node/data.py:189-226` (add `fold` beside `group`)
- Test: `tests/core/test_node/test_fold.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `NodeData.fold(self, label: str, *, default: bool = True, **kwargs) -> ContextManager[DataPort]`
  - `NodeData._fold_id(label: str) -> str` — derives a port id from a label.
  - Tasks 2-5 rely on both names exactly.

- [x] **Step 1: Write the failing test**

Create `tests/core/test_node/test_fold.py`:

```python
"""fold() mints one container port: no pin, no widget, state persists."""

from __future__ import annotations

import pytest

from haywire.core.node import BaseNode, NodeType, node
from haywire.core.execution.execution_context import ExecutionContext

# Integration: building a node with real ports needs the library system.
pytestmark = pytest.mark.integration


def _make_probe(graph, position=(100.0, 100.0)):
    from haybale_testing.nodes.testbed.fold_probe import FoldProbeNode

    wrapper = graph.create_node_wrapper(
        FoldProbeNode.class_identity.registry_key, position=position
    )
    assert wrapper is not None, "node creation failed"
    return wrapper.node


def test_fold_id_is_derived_from_the_label() -> None:
    from haywire.core.node.data import NodeData

    assert NodeData._fold_id("Solver") == "solver"
    assert NodeData._fold_id("Interpolation Range") == "interpolation_range"
    assert NodeData._fold_id("Custom Name") == "custom_name"


def test_fold_mints_a_port_with_no_pin(graph_with_library_system) -> None:
    probe = _make_probe(graph_with_library_system)
    fold = probe.ports["solver"]
    assert fold.has_pin() is False
    assert fold.is_config() is True


def test_fold_carries_no_widget(graph_with_library_system) -> None:
    """BOOL declares SWITCH_WIDGET; a fold must not inherit it."""
    probe = _make_probe(graph_with_library_system)
    assert probe.ports["solver"].widget_key is None


def test_fold_persists_its_open_state(graph_with_library_system) -> None:
    """A widget-less port only stores when the strategy says ALWAYS."""
    from haywire.core.types.enums import StoreStrategy

    probe = _make_probe(graph_with_library_system)
    fold = probe.ports["solver"]
    assert fold.store_strategy.should_store(
        is_linked=False, has_widget=False, node_set=False
    ), "a fold that does not store forgets whether it was open"
    assert fold.store_strategy & StoreStrategy.ALWAYS


def test_fold_parents_its_children(graph_with_library_system) -> None:
    probe = _make_probe(graph_with_library_system)
    assert probe.ports["substeps"].parent_group == "solver"
    assert probe.ports["out"].parent_group is None


def test_fold_is_marked_as_a_group(graph_with_library_system) -> None:
    probe = _make_probe(graph_with_library_system)
    assert probe.ports["solver"].is_group is True


def test_fold_defaults_to_open(graph_with_library_system) -> None:
    probe = _make_probe(graph_with_library_system)
    assert probe.value("solver") is True
```

**First create the probe node** at
`barn/haybale-testing/haybale_testing/nodes/testbed/fold_probe.py`:

```python
"""Fold probe — a node whose ports exercise fold()."""

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode, NodeType


@node(
    label="Fold Probe",
    description="Tests fold() minting and nesting",
    search_tags=["testing", "fold"],
    menu="testing/testbed",
    node_type=NodeType.DATA,
)
class FoldProbeNode(BaseNode):
    """Test-only."""

    def init(self):
        from haywire.barn.builtin.types import FLOAT, STRING

        self.add(STRING.as_outlet("out"))
        with self.fold("Solver"):
            self.add(FLOAT.as_config("substeps", default=10.0))

    def worker(self, context: ExecutionContext) -> str | None:
        return None
```

Commit it before running any suite containing `tests/studio/test_docs/`.

- [x] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_node/test_fold.py -v`
Expected: FAIL with `AttributeError: 'NodeData' object has no attribute 'fold'`

- [x] **Step 3: Implement `fold()`**

In `packages/haywire-core/src/haywire/core/node/data.py`, add beside `group()`:

```python
    @staticmethod
    def _fold_id(label: str) -> str:
        """Return the port id a fold takes from its ``label``."""
        return re.sub(r"[^a-z0-9]+", "_", label.strip().lower()).strip("_")

    @contextmanager
    def fold(self, label: str, *, default: bool = True, **kwargs):
        """Add a collapsible fold; every port added inside becomes its child.

        The fold is a port with no pin and no widget: the disclosure triangle on
        the node card is its only control, and its value is the open state. It
        persists, so a node reopens as the user left it, and a node may read it
        or pass ``on_change=`` to reconfigure itself when the user folds.

        Its id is derived from ``label``. Ports added inside take the fold's
        direction; mixing directions inside one fold raises. Folds nest.

        Label a fold as a section ("Custom Name"), not as an imperative
        ("Use Custom Name") — it names what is inside, and the user opens it
        rather than deciding something.

        Args:
            label: The header text, and the source of the fold's port id.
            default: Whether the fold starts open.
            **kwargs: Forwarded to the port spec — ``on_change``, ``description``
                and the rest of ``as_config``'s keywords.

        Raises:
            ValueError: If the fold's id already exists on this node.

        Examples:
            # A fold over two config ports
            with self.fold('Solver'):
                self.add(INT.as_config('substeps', default=10))
                self.add(INT.as_config('iterations', default=1))

            # Closed until the user opens it
            with self.fold('Advanced', default=False):
                self.add(FLOAT.as_config('epsilon', default=1e-6))

            # Reconfigure the node when the user folds
            with self.fold('Custom Name', on_change='hb_change'):
                self.add(STRING.as_config('name', default='my_callback'))
        """
        from haywire.barn.builtin.types import BOOL

        fold_id = self._fold_id(label)
        # widget_key=None: BOOL's identity declares SWITCH_WIDGET, and a fold
        # whose state is reached by the disclosure triangle must not also render
        # one. as_config resolves store_strategy to ALWAYS (BOOL sets none), so
        # a widget-less fold still persists its open state.
        spec = BOOL.as_config(
            fold_id,
            label=label,
            default=default,
            widget_key=None,
            **kwargs,
        )
        fold_port = self.add(spec)
        fold_port.is_group = True

        self._group_stack.append(fold_port.id)
        try:
            yield fold_port
        finally:
            self._group_stack.pop()
```

Add `import re` at the top of `data.py` if it is not already imported (it is —
`_push` uses `re.compile`; verify rather than duplicating).

- [x] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/test_node/test_fold.py -v`
Expected: PASS (7 tests)

- [x] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/node/data.py tests/core/test_node/test_fold.py
git commit -m "feat(node): add fold() — a pin-less, widget-less container port

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: One direction per fold

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/node/data.py` (`add`, `fold`)
- Test: `tests/core/test_node/test_fold.py`

**Interfaces:**
- Consumes: `fold()` from Task 1.
- Produces: `ValueError` raised from `add()` when a port's direction disagrees with its enclosing fold's established direction.

Skins render inlets, outlets and configs in separate lanes. A fold spanning two
lanes would need its header drawn twice, so mixing is an authoring error and is
reported as one at declaration time.

- [x] **Step 1: Write the failing test**

Append to `tests/core/test_node/test_fold.py`:

> ⚠️ **Every function-local `@node` class below is a placeholder for a REGISTERED
> probe.** A `@node` declared inside a test function is never registered, so
> `create_node_wrapper` cannot build it. Before writing these tests, add each
> shape as its own module under
> `barn/haybale-testing/haybale_testing/nodes/testbed/` and build it with
> `_make_probe`-style helpers, exactly as the Global Constraints section shows.
> The class bodies below give the port declarations to copy; the test then calls
> the registered node, not a local class.


```python
def test_mixing_directions_in_one_fold_raises(graph_with_library_system) -> None:
    @node(
        label="Mixed Fold",
        description="fixture",
        menu="testing/fold",
        node_type=NodeType.DATA,
    )
    class _MixedFold(BaseNode):
        """Test-only."""

        def init(self):
            from haywire.barn.builtin.types import FLOAT, STRING

            self.add(STRING.as_outlet("out"))
            with self.fold("Mixed"):
                self.add(FLOAT.as_inlet("an_inlet"))
                self.add(FLOAT.as_outlet("an_outlet"))

        def worker(self, context: ExecutionContext) -> str | None:
            return None

    with pytest.raises(ValueError, match="one direction"):
        _make_probe(graph_with_library_system)  # was: test_node_factory(_MixedFold)


def test_a_fold_of_inlets_is_fine(graph_with_library_system) -> None:
    @node(
        label="Inlet Fold",
        description="fixture",
        menu="testing/fold",
        node_type=NodeType.DATA,
    )
    class _InletFold(BaseNode):
        """Test-only."""

        def init(self):
            from haywire.barn.builtin.types import FLOAT, STRING

            self.add(STRING.as_outlet("out"))
            with self.fold("Inputs"):
                self.add(FLOAT.as_inlet("a"))
                self.add(FLOAT.as_inlet("b"))

        def worker(self, context: ExecutionContext) -> str | None:
            return None

    probe = _make_probe(graph_with_library_system)
    assert probe.ports["a"].parent_group == "inputs"
    assert probe.ports["b"].parent_group == "inputs"
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_node/test_fold.py::test_mixing_directions_in_one_fold_raises -v`
Expected: FAIL — `DID NOT RAISE`

- [x] **Step 3: Track and check the fold's direction**

In `NodeData.__init__`, beside `self._group_stack`, add:

```python
        self._fold_direction: Dict[str, PortType] = {}
        """The direction each open fold has committed to, by fold port id."""
```

Import `PortType` in `data.py` if it is not already imported.

In `add()`, immediately after the `parent_group` assignment block, add:

```python
        if port.parent_group:
            # A fold renders in one lane. Two lanes would need its header drawn
            # twice, so a mixed fold is an authoring error, not a layout to
            # resolve at render time.
            committed = self._fold_direction.get(port.parent_group)
            if committed is None:
                self._fold_direction[port.parent_group] = port.port_type
            elif committed is not port.port_type:
                raise ValueError(
                    f"Fold {port.parent_group!r} holds {committed.value} ports; "
                    f"{port.id!r} is {port.port_type.value}. A fold holds one direction."
                )
```

In `fold()`'s `finally` block, clear the entry so a re-run of `init()` starts
clean:

```python
        finally:
            self._group_stack.pop()
            self._fold_direction.pop(fold_port.id, None)
```

- [x] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_node/test_fold.py -v`
Expected: PASS (9 tests)

- [x] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/node/data.py tests/core/test_node/test_fold.py
git commit -m "feat(node): a fold holds one direction

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Nesting

**Files:**
- Test: `tests/core/test_node/test_fold.py`

**Interfaces:**
- Consumes: `fold()` from Tasks 1-2. No production change expected — `_group_stack` already nests and `_is_any_ancestor_collapsed` already walks ancestors.
- Produces: nothing new; this task proves nesting works and locks it with a test.

- [x] **Step 1: Write the test**

Append to `tests/core/test_node/test_fold.py`:

```python
def test_folds_nest(graph_with_library_system) -> None:
    @node(
        label="Nested Fold",
        description="fixture",
        menu="testing/fold",
        node_type=NodeType.DATA,
    )
    class _NestedFold(BaseNode):
        """Test-only."""

        def init(self):
            from haywire.barn.builtin.types import FLOAT, STRING

            self.add(STRING.as_outlet("out"))
            with self.fold("Solver"):
                self.add(FLOAT.as_config("substeps", default=10.0))
                with self.fold("Interpolation Range"):
                    self.add(FLOAT.as_config("begin", default=0.0))
                    self.add(FLOAT.as_config("end", default=1.0))

        def worker(self, context: ExecutionContext) -> str | None:
            return None

    probe = _make_probe(graph_with_library_system)
    assert probe.ports["substeps"].parent_group == "solver"
    assert probe.ports["interpolation_range"].parent_group == "solver"
    assert probe.ports["begin"].parent_group == "interpolation_range"
    assert probe.ports["end"].parent_group == "interpolation_range"


def test_a_closed_outer_fold_hides_a_nested_fold_child(graph_with_library_system) -> None:
    """_is_any_ancestor_collapsed walks the whole chain, not just one level."""

    @node(
        label="Nested Closed",
        description="fixture",
        menu="testing/fold",
        node_type=NodeType.DATA,
    )
    class _NestedClosed(BaseNode):
        """Test-only."""

        def init(self):
            from haywire.barn.builtin.types import FLOAT, STRING

            self.add(STRING.as_outlet("out"))
            with self.fold("Solver", default=False):
                with self.fold("Interpolation Range"):
                    self.add(FLOAT.as_config("begin", default=0.0))

        def worker(self, context: ExecutionContext) -> str | None:
            return None

    probe = _make_probe(graph_with_library_system)
    visible = {p.id for p in probe.get_visible_ports()}
    assert "begin" not in visible
    assert "interpolation_range" not in visible
    assert "solver" in visible
```

- [x] **Step 2: Run the tests**

Run: `uv run pytest tests/core/test_node/test_fold.py -v`
Expected: PASS (11 tests). If the nesting tests fail, the bug is in
`_is_any_ancestor_collapsed` or `_group_stack` — fix it there, not in the test.

- [x] **Step 3: Commit**

```bash
git add tests/core/test_node/test_fold.py
git commit -m "test(node): lock fold nesting and ancestor collapse

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Render the fold header as a disclosure triangle

**Files:**
- Modify: `barn/haybale-studio/haybale_studio/skins/stacked_skin.py:264-324` (`_render_group`)
- Test: `tests/ui/skin/test_fold_header.py`

**Interfaces:**
- Consumes: `fold()` from Task 1, and `depth=` from the fold-depth-indentation plan.
- Produces: a fold header element carrying `data-hw-fold-id` and `data-hw-fold-open`.

The existing `_render_group` renders the group's *widget* as the control. A fold
has no widget, so the header becomes a triangle plus the label.

- [x] **Step 1: Write the failing test**

Create `tests/ui/skin/test_fold_header.py`:

```python
"""A fold's header is a disclosure triangle, never a widget."""

from __future__ import annotations

import inspect

import pytest

pytestmark = pytest.mark.unit


def test_group_header_renders_no_widget() -> None:
    """A fold carries no widget; the header must not try to render one."""
    from haybale_studio.skins.stacked_skin import StackedNodeSkin

    source = inspect.getsource(StackedNodeSkin._render_group)
    assert "render_widget" not in source


def test_group_header_emits_fold_attributes() -> None:
    from haybale_studio.skins.stacked_skin import StackedNodeSkin

    source = inspect.getsource(StackedNodeSkin._render_group)
    assert "data-hw-fold-id" in source
    assert "data-hw-fold-open" in source


def test_group_header_uses_the_central_icon_tokens() -> None:
    """Icons come from hui.icon.*, never raw Material strings."""
    from haybale_studio.skins.stacked_skin import StackedNodeSkin

    source = inspect.getsource(StackedNodeSkin._render_group)
    assert "fold_open" in source and "fold_closed" in source
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/ui/skin/test_fold_header.py -v`
Expected: FAIL — `assert "render_widget" not in source`

- [x] **Step 3: Replace the header block**

First add the `hui` import — `stacked_skin.py` does not have one (its imports are
`typing.List`, `nicegui.ui`, `NodeWrapper`, `DataPort`, the enums, `skin`,
`NodeSkin`). After `from nicegui import ui`:

```python
from haywire.ui import elements as hui
```

`hui.icon.fold_open` / `hui.icon.fold_closed` are the disclosure tokens
(`packages/haywire-core/src/haywire/ui/elements/icons.py`) — never raw Material
strings, so the vocabulary stays in one registry.

Then replace the header block inside `_render_group`. The existing block is:

```python
            # Group header with toggle
            with ui.row().classes("w-full items-center gap-1"):
                # Render group toggle widget
                if group_port.widget_key is not None and group_port.should_show_widget():
                    self.render_widget(group_port, wrapper.node_id, classes="zoom-pan-lod2 hw-detail-widget")
```

Replace with:

```python
            # Fold header: a disclosure triangle and the label. A fold carries
            # no widget — the triangle is the whole control — so nothing here
            # consults widget_key.
            header_indent = self._content_inset(depth)
            with (
                ui.row()
                .classes("w-full items-center gap-1 cursor-pointer zoom-pan-lod2 hw-detail-label")
                .style(f"padding-left: {header_indent}px;")
                .props(
                    f'data-hw-fold-id="{group_port.id}" '
                    f'data-hw-fold-open="{str(bool(is_expanded)).lower()}"'
                )
                .on("click", lambda pid=group_port.id: self._toggle_fold(wrapper, pid))
            ):
                ui.icon(hui.icon.fold_open if is_expanded else hui.icon.fold_closed).classes(
                    "text-sm"
                )
                ui.label(group_port.label).classes("text-xs")
```

Add the toggle helper to `StackedNodeSkin`:

```python
    def _toggle_fold(self, wrapper: NodeWrapper, fold_id: str) -> None:
        """Flip a fold's open state. The port's own on_change fires from the write."""
        node = wrapper.node
        node.ports[fold_id].set_value(not node.value(fold_id))
```

Also update `_render_group`'s docstring, replacing the bullet list:

```
        Folds are rendered with:
        - A disclosure-triangle header (no widget — a fold carries none)
        - Children indented via their own content column, never the container
        - Child ports only while open
```

- [x] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/ui/skin/test_fold_header.py -v`
Expected: PASS (3 tests)

- [x] **Step 5: Run the skin suite**

Run: `uv run pytest tests/ui/skin/ -q`
Expected: all pass.

- [x] **Step 6: Commit**

```bash
git add barn/haybale-studio/haybale_studio/skins/stacked_skin.py tests/ui/skin/test_fold_header.py
git commit -m "feat(skin): render a fold header as a disclosure triangle

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Migrate the five `group()` call sites

**Files:**
- Modify: `barn/haybale-example/haybale_example/nodes/emits/custom_callback.py:32`
- Modify: `barn/haybale-example/haybale_example/nodes/emits/emit_callback.py:35`
- Modify: `barn/haybale-testing/haybale_testing/nodes/testbed/custom_callback_node.py:22`
- Modify: `barn/haybale-testing/haybale_testing/nodes/testbed/group_and_sections.py:22`
- Modify: `barn/haybale-testing/haybale_testing/nodes/testbed/emit_callback_node.py:23`

**Interfaces:**
- Consumes: `fold()` from Task 1.
- Produces: no `self.group(` call sites left in the repository.

⚠️ **`tests/studio/test_docs/test_generate.py`'s teardown runs
`git checkout -- barn/haybale-testing`, discarding uncommitted edits there.**
Commit this task before running the full suite.

- [x] **Step 1: Read each call site before editing**

```sh
grep -rn "self.group(" --include="*.py" barn/
```

Each passes `GROUP.as_config(<id>, default=..., label=..., on_change=...)`.

- [x] **Step 2: Migrate `custom_callback_node.py`**

Replace:

```python
        with self.group(
            GROUP.as_config("mode_switch", default=False, label="Use Custom Name", on_change="redraw")
        ):
```

with:

```python
        with self.fold("Custom Name", default=False, on_change="redraw"):
```

Drop `GROUP` from that file's type imports if nothing else uses it.

- [x] **Step 3: Rename every `mode_switch` consumer — this breaks a worker contract**

⚠️ **The id change from `mode_switch` to `custom_name` is not cosmetic.**
`mode_switch` is a **required worker parameter** in two nodes:

- `barn/haybale-example/haybale_example/nodes/emits/emit_callback.py:79` (`mode_switch: bool,`) and its body at `:86` (`if mode_switch:`)
- `barn/haybale-testing/haybale_testing/nodes/testbed/emit_callback_node.py:63` and `:70`

`_analyze_worker_signature` binds worker parameters by port id and raises
`ValueError(f"Required worker parameter '{name}' has no matching port.")`
(`data.py:653`) when a required parameter names no port. Leave either one and the
node fails at executor-build time.

Rename the parameter and its uses in both files alongside the fold. Then sweep
the value-setters:

```sh
grep -rn "mode_switch" --include="*.py" . | grep -v "\.venv\|__pycache__"
```

Known consumers to update: `tests/core/test_execution/test_interpreter.py:144,155`,
`tests/core/test_execution/test_event_source_queue_mode.py:47`, and
`playground/execution_examples.py:250,265` — each does
`ports["mode_switch"].set_value(...)`.

**Then the generated docs**, which the `--include="*.py"` grep above misses and
which `tests/studio/test_docs/test_generate.py` regenerates and diffs — leaving
them stale fails the Task 6 gate:

```sh
grep -rln "mode_switch\|GROUP" barn/*/*/docs/ barn/*/*/QUICKREF.md
```

Known: `barn/haybale-example/haybale_example/docs/haybale-example.node.EmitCallbackNode.md:15`,
`…node.CustomCallbackNode.md:11`,
`barn/haybale-testing/haybale_testing/docs/haybale-testing.node.TestCustomCallbackNode.md:11`,
`…node.TestEmitCallbackNode.md:15`, `…node.TestGroupAndSectionNode.md:14`, and
`barn/haybale-testing/haybale_testing/QUICKREF.md:20`.

Regenerate rather than hand-edit:

```sh
uv run haywire docs --all
```

- [x] **Step 4: Migrate the remaining four the same way**

For each, read the existing `GROUP.as_config(...)` call and map it:
`label=` becomes the positional argument, `default=` and `on_change=` carry over
unchanged, the old explicit id is dropped. Re-label imperatives as section names
(`"Use Custom Name"` → `"Custom Name"`).

Repeat Step 3's worker-parameter and doc sweep for each id you change.

After each file: `grep -n "GROUP" <file>` and remove the import if unused.

- [x] **Step 4: Verify no call sites remain**

```sh
grep -rn "self.group(" --include="*.py" . | grep -v "\.venv\|__pycache__"
```

Expected: no output.

- [x] **Step 5: Run the affected tests**

```sh
uv run pytest tests/core/test_node/ tests/ui/skin/ -q
uv run pytest -k "callback" -q
```

Expected: all pass.

- [x] **Step 6: Commit immediately**

```bash
git add barn/
git commit -m "refactor(nodes): migrate group() call sites to fold()

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Delete `section()` and `group()`

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/node/data.py` — remove `section()`, `group()`, `iter_section_ports`, `get_section_ports`, `_section_stack`, and the `include_sections` parameter from `iter_visible_ports` / `get_visible_ports`
- Modify: `packages/haywire-core/src/haywire/core/types/port.py:125-126,134-135` — remove `section` and `is_section`
- Modify: `barn/haybale-testing/haybale_testing/nodes/testbed/group_and_sections.py` — rename the node to `TestFoldNode`, label `"Fold"`
- Test: `tests/core/test_node/test_fold.py`

**Interfaces:**
- Consumes: Task 5 (no call sites left).
- Produces: `iter_visible_ports(self)` and `get_visible_ports(self)` — both now take no arguments.

- [x] **Step 1: Find every consumer**

```sh
grep -rn "include_sections\|iter_section_ports\|get_section_ports\|is_section\|\.section\b" \
  --include="*.py" packages/ barn/ tests/ | grep -v __pycache__
```

Every hit must be removed or updated. `is_section` has exactly one hit (its own
declaration) — it is dead.

**One existing test is known to depend on `section` and must be rewritten, not
just deleted:** `tests/core/test_node/test_get_folded_ports.py` builds a
`_FakePort(..., section=None, ...)` (line 20-23) and
`test_drops_sections_and_group_controls` (line 69) asserts a sectioned port is
dropped from a folded card. With sections gone, that test keeps its other half.
Rewrite it as:

```python
    def test_drops_group_controls(self):
        """A group control port is never linked anyway, so it falls out twice over."""
        group = _FakePort("grp", order=2, linked=True, is_group=True)
        real = _FakePort("real", order=3, linked=True)
        node = _fake_node([group, real])

        assert _get_folded_ports(node) == [real]
```

and drop `section` from `_FakePort.__init__` and its body.

- [x] **Step 2: Write the failing test**

Append to `tests/core/test_node/test_fold.py`:

```python
def test_section_api_is_gone() -> None:
    from haywire.core.node.data import NodeData
    from haywire.core.types import DataPort

    assert not hasattr(NodeData, "section")
    assert not hasattr(NodeData, "group")
    assert not hasattr(NodeData, "iter_section_ports")
    assert not hasattr(NodeData, "get_section_ports")
    assert "section" not in {f.name for f in DataPort.__dataclass_fields__.values()}
    assert "is_section" not in {f.name for f in DataPort.__dataclass_fields__.values()}


def test_visible_ports_takes_no_section_argument() -> None:
    import inspect

    from haywire.core.node.data import NodeData

    assert "include_sections" not in inspect.signature(NodeData.get_visible_ports).parameters
    assert "include_sections" not in inspect.signature(NodeData.iter_visible_ports).parameters
```

- [x] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/core/test_node/test_fold.py::test_section_api_is_gone -v`
Expected: FAIL — `assert not hasattr(NodeData, "section")`

- [x] **Step 4: Delete section and group**

In `data.py`:
- Delete the `section()` context manager and the `group()` context manager.
- Delete `self._section_stack` from `__init__` and the `port.section` assignment in `add()`.
- Delete `iter_section_ports` (data.py:451) and `get_section_ports` (data.py:464).
- Simplify `iter_visible_ports`:

```python
    def iter_visible_ports(self) -> Iterator[DataPort]:
        """Yield the ports drawn on the node card, in display order.

        A port inside a closed fold is skipped.
        """
        for port in self._iter_ports():
            if port.parent_group and self._is_any_ancestor_collapsed(port):
                continue
            yield port

    def get_visible_ports(self) -> List[DataPort]:
        """The ports drawn on the node card, as a list. See ``iter_visible_ports``."""
        return list(self.iter_visible_ports())
```

- Remove `not port.section` / `port.section` conditions from `get_folded_ports`
  (around line 448) and `iter_hidden_connected_ports` (around line 546).

In `port.py`, delete the `section` and `is_section` field declarations.

Update every caller found in Step 1 that passed `include_sections`.

- [x] **Step 5: Rename the testbed node**

In `group_and_sections.py`, rename the class to `TestFoldNode`, set
`label="Fold"` and `description="Tests fold rendering"`, drop `"section"` from
`search_tags`, and rename the file to `fold.py`. Update
`barn/haybale-testing/haybale_testing/nodes/__init__.py` if it names the class.

Then run the rename checker: `/check-rename` — string-based references
(`patch("...")`, doc citations) are not caught by an IDE rename.

- [x] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_node/test_fold.py -v`
Expected: PASS (13 tests)

- [x] **Step 7: Run the full gate**

```sh
uv run pytest -m "not browser and not perf" -q > /tmp/fold.log 2>&1; echo "exit=$?"
grep -E "^FAILED|^ERROR" /tmp/fold.log
grep -E "passed|failed" /tmp/fold.log | tail -1
```

Expected: `exit=0`.

- [x] **Step 8: Lint, format, type-check**

```sh
uv run ruff check .
uv run ruff format --check .
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-graph-editor/haybale_graph_editor/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ tests/
```

Expected: clean.

- [x] **Step 9: Commit**

```bash
git add -A
git commit -m "refactor(node)!: fold replaces group and section

section had zero adoption — no node in the repo declared one — and its
is_section flag was dead code. group required the author to import a type
and choose a widget. fold() asks only for a name.

See ADR-0035.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: Documentation

**Files:**
- Modify: `docs/guides/ports.md`
- Modify: `barn/haybale-core/haybale_core/types/specs.py` — mark `GROUP` as superseded

**Interfaces:**
- Consumes: everything above.
- Produces: nothing code-facing.

- [x] **Step 1: Document `fold()` in the ports guide**

Add a "Folds" section to `docs/guides/ports.md` covering: what a fold is, the
`with self.fold("Name"):` form, that it carries no pin and no widget, that its
state persists, `default=` and `on_change=`, one-direction-per-fold, and
nesting. Link to [ADR-0035](../adr/0035-fold-replaces-group-and-section.md).

Follow `docs/reference/doc-authoring.md` for front matter and nav wiring.

- [x] **Step 2: Mark `GROUP` superseded**

In `barn/haybale-core/haybale_core/types/specs.py`, update the `GROUP` class
docstring:

```python
class GROUP(PrimitiveType[bool]):
    """Group data type.

    Superseded by ``NodeData.fold()``, which mints its own container port. Kept
    for graphs saved before the change; new nodes use ``fold()``.
    """
```

- [x] **Step 3: Build the docs**

```sh
uv run mkdocs build --strict
```

Expected: no warnings.

- [x] **Step 4: Commit**

```bash
git add docs/ barn/haybale-core/haybale_core/types/specs.py
git commit -m "docs: document fold(), mark GROUP superseded

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Done When

- [x] No `self.group(` or `self.section(` call sites remain.
- [x] `DataPort` has no `section` or `is_section` field.
- [x] `uv run pytest -m "not browser and not perf" -q` exits 0.
- [x] `uv run ruff check .` and `uv run ruff format --check .` clean.
- [x] `uv run mypy` over the `CLAUDE.md` package list clean.
- [x] `uv run mkdocs build --strict` clean of any warning introduced by this plan (one pre-existing, unrelated warning in `guides/panels.md` still aborts strict mode; see below).
- [ ] In the running app, the `Fold` testbed node shows a triangle header, folds on click, and reopens folded after a save/reload. Not yet verified interactively.
