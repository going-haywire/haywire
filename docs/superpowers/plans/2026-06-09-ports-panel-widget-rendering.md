# Ports Panel Widget Rendering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **No automated tests in this plan** (per author decision). Each task verifies with `ruff`, `mypy`, and a described manual check in the running app, then commits.

**Goal:** Make the node Ports Panel render each port's live, editable Widget (the same one the node card shows) — giving a second editing surface for nodes whose Skin omits inline widgets (e.g. top-to-bottom flow skins).

**Architecture:** The Ports Panel obtains the singleton `WidgetFactory` through `IProjectState` (`ctx.app.widget_factory`) and renders a live `IWidget` per port that satisfies `widget_key is not None and should_show_widget()` — the same predicate the Skin uses. The panel **owns the lifecycle** of the widget instances it creates: it stores them and calls `cleanup()` on the prior batch at the top of every `draw()` (redraws and selection changes share this teardown). Factory hot-reload tracking is kept separate from the Skin's by registering panel widgets under a namespaced node id (`panel:<node_id>`). Widget-less ports keep today's read-only `info_row`.

**Tech Stack:** Python 3.10+, NiceGUI/Quasar, `injector` DI, the Haywire panel system (`@panel`, `BasePanel`, `PanelLayout`), `BaseWidget`/`WidgetFactory`, `hui` (`haywire.ui.elements`).

**Decision record:** The full design rationale (11 resolved questions) lives in the author's memory file `project_ports_panel_widgets.md`. Key locked decisions: always-on secondary surface (not skin-driven fallback); panel owns widget lifecycle; factory via `IProjectState`; namespaced `panel:<node_id>` tracking key; honour `should_show_widget()`; `redraw_on=(SelectionMoved, GraphDataMutated, ActiveGraphMoved)`; accept full rebuild churn; label-above-widget layout; layered error handling; ADR `0008-ports-panel-widget-rendering.md` written as the final step.

---

## File Structure

| File | Responsibility | Change |
|------|----------------|--------|
| `packages/haywire-core/src/haywire/core/session/protocols.py` | `IProjectState` structural protocol the panel reads `ctx.app` against | Add `widget_factory` attribute |
| `packages/haywire-core/src/haywire/core/di/config.py` | `LibrarySystemService` DI accessors | Add `get_widget_factory()` accessor |
| `packages/haywire-studio/src/haywire_studio/app.py` | `HaywireApp.setup_shared_services()` — wires DI services onto the app (which satisfies `IProjectState`) | Set `self.widget_factory` |
| `barn/haybale-graph-editor/haybale_graph_editor/panels/node_ports_panel.py` | The Ports Panel — renders live widgets + read-only rows, owns widget lifecycle | Rewrite `draw()`, add lifecycle + redraw, fix stale header |
| `docs/adr/0008-ports-panel-widget-rendering.md` | Records the architectural decision | Create (final task) |

Each task is self-contained and leaves the repo compiling/linting clean.

### Pre-flight baseline (run once before Task 1)

Per CLAUDE.md, establish a baseline so post-edit failures are attributable. Run and confirm clean:

```sh
uv run ruff check packages/haywire-core/src/haywire/core/session/protocols.py packages/haywire-core/src/haywire/core/di/config.py packages/haywire-studio/src/haywire_studio/app.py barn/haybale-graph-editor/haybale_graph_editor/panels/node_ports_panel.py
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-TEST_A/haybale_test_a/
```

Expected: no errors. If there is pre-existing noise, note it — anything *new* after your edits is yours to fix. (Note: `haybale-graph-editor` is not in the CLAUDE.md mypy invocation list; that is the project's existing config — do not add it. Lint it with `ruff` as shown.)

---

## Task 1: Expose `WidgetFactory` through `IProjectState`

The panel only receives a `SessionContext`; it reaches framework services via `ctx.app.<service>` (e.g. `node_factory`, `panel_registry`). `WidgetFactory` is a DI singleton not yet surfaced this way. This task adds the protocol attribute, a DI accessor mirroring `get_skin_factory`, and the app-side wiring — so `ctx.app.widget_factory` resolves.

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/session/protocols.py`
- Modify: `packages/haywire-core/src/haywire/core/di/config.py` (after the `get_skin_factory` accessor, ~line 669)
- Modify: `packages/haywire-studio/src/haywire_studio/app.py:148` (alongside the other `get_*_factory()` lines)

- [ ] **Step 1: Add `widget_factory` to the `IProjectState` protocol**

In `packages/haywire-core/src/haywire/core/session/protocols.py`, the protocol currently ends at the `panel_registry` line. Add a `widget_factory` attribute. The protocol uses `Any  # <RealType>` comments (matching `node_factory: Any  # NodeFactory`) to avoid import cycles, so do the same — do **not** add a runtime import of `WidgetFactory` here.

Add, immediately after the `panel_registry: Any  # PanelRegistry ...` line:

```python
    widget_factory: Any  # WidgetFactory — set by HaywireApp.setup_shared_services()
    """Singleton factory that builds inline port Widgets. See get_widget_factory()."""
```

- [ ] **Step 2: Add a `get_widget_factory()` accessor to `LibrarySystemService`**

In `packages/haywire-core/src/haywire/core/di/config.py`, `WidgetFactory` is already imported at the top (line 19: `from ...ui.widget.factory import WidgetFactory`). Add an accessor mirroring `get_skin_factory` (lines 667–669). Insert it directly after the `get_skin_factory` method (after line 669, before `get_theme_registry`):

```python
    def get_widget_factory(self) -> WidgetFactory:
        """Get the widget factory."""
        return self.injector.get(WidgetFactory)
```

- [ ] **Step 3: Wire `self.widget_factory` in `setup_shared_services()`**

In `packages/haywire-studio/src/haywire_studio/app.py`, the factories are assigned around lines 146–150. Add the widget factory alongside `skin_factory` (after line 148):

```python
        self.skin_factory = self.library_service.get_skin_factory()
        self.widget_factory = self.library_service.get_widget_factory()
```

(Place the new line immediately after the existing `self.skin_factory = ...` line. No new import is needed — it goes through `library_service`.)

- [ ] **Step 4: Verify lint + types are clean**

Run:

```sh
uv run ruff check packages/haywire-core/src/haywire/core/session/protocols.py packages/haywire-core/src/haywire/core/di/config.py packages/haywire-studio/src/haywire_studio/app.py
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/
```

Expected: no new errors versus the pre-flight baseline.

- [ ] **Step 5: Manual smoke check — the app still boots and `widget_factory` resolves**

Run the app briefly to confirm nothing in startup/DI broke:

```sh
uv run haywire
```

Expected: the studio launches without an exception during `setup_shared_services`. Close it once the window/log shows it reached the workspace. (We exercise `ctx.app.widget_factory` for real in Task 3's manual check.)

- [ ] **Step 6: Commit**

```bash
git add packages/haywire-core/src/haywire/core/session/protocols.py packages/haywire-core/src/haywire/core/di/config.py packages/haywire-studio/src/haywire_studio/app.py
git commit -m "feat: expose WidgetFactory via IProjectState for panel widget rendering

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Add widget lifecycle ownership to the Ports Panel

Give the panel instance the machinery to own its created widgets: a list to hold them, a method to dispose the previous batch, and a one-time client-disconnect hook. This task adds the lifecycle scaffolding **without yet rendering widgets** (Task 3 wires it into `draw()`), so the change is small and reviewable on its own.

**Why this matters:** `BaseWidget.render()` subscribes to `port._data.on_changed` and only unsubscribes in `cleanup()`. The panel re-mounts on every redraw/selection change; if it never calls `cleanup()`, each redraw leaks a live subscription. The panel must dispose its prior batch before building a new one.

**Files:**
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/panels/node_ports_panel.py`

- [ ] **Step 1: Fix the stale path-header comment (Q9 in-scope cleanup)**

The file's first line wrongly claims it lives in core. Replace line 1:

```python
# packages/haywire-core/src/haywire/ui/panels/node_ports_panel.py
```

with:

```python
# barn/haybale-graph-editor/haybale_graph_editor/panels/node_ports_panel.py
```

- [ ] **Step 2: Add imports for widget lifecycle and NiceGUI context**

At the top of the file, the existing imports include `from haywire.ui import elements as hui` and the panel imports. Add the typing + nicegui imports needed for lifecycle. Update the `TYPE_CHECKING` block and add a `nicegui` import.

Add to the top-level imports (after the existing `from haywire.ui.panel.decorator import panel` line):

```python
from nicegui import ui
```

Extend the `TYPE_CHECKING` block so it reads:

```python
if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext
    from haywire.ui.widget.interface import IWidget
```

- [ ] **Step 3: Add an `__init__` that holds the panel's widget instances**

`BasePanel` has no `__init__` of its own beyond ABC; panels are plain instances. Add an `__init__` to `NodePortsPanel` that initialises the instance state. Insert it as the first method of the class body, before `poll`:

```python
    def __init__(self) -> None:
        super().__init__()
        # Live widget instances this panel created, keyed by port id. The panel
        # owns their lifecycle: the previous batch is cleaned up at the top of
        # every draw() (redraws + selection changes share this teardown), and a
        # final sweep runs on client disconnect.
        self._widgets: dict[str, "IWidget"] = {}
        self._disconnect_registered: bool = False
```

- [ ] **Step 4: Add a `_dispose_widgets()` helper**

Add this method to the class (place it after `__init__`, before `poll`). It calls `cleanup()` on each held widget and clears the map. `BaseWidget.cleanup()` is final and idempotent, so double-calling (disconnect + next draw) is safe.

```python
    def _dispose_widgets(self) -> None:
        """Clean up every widget instance this panel created, then forget them.

        Called at the top of each draw() before rebuilding, and once on client
        disconnect. BaseWidget.cleanup() is idempotent, so overlapping calls are
        safe. Each cleanup() drops the widget's port.on_changed subscription.
        """
        for widget in self._widgets.values():
            try:
                widget.cleanup()
            except Exception:
                # A widget that fails to clean up must not block the others.
                pass
        self._widgets.clear()
```

- [ ] **Step 5: Verify mypy is clean**

Run:

```sh
uv run mypy packages/haywire-core/src/
```

Expected: no new errors. The `IWidget` import is under `TYPE_CHECKING` and referenced only via string annotations, which is correct.

> **Skip `ruff check` for this task.** The `from nicegui import ui` import added in Step 2 is not yet used (it is consumed in Task 3), so `ruff` would flag F401 here. Do **not** add a `# noqa` to silence it — instead run the `ruff` pass at Task 3 Step 7, by which point `ui` is used. This task is still independently committable; the unused import is resolved within the same feature branch one task later.

- [ ] **Step 6: Commit**

```bash
git add barn/haybale-graph-editor/haybale_graph_editor/panels/node_ports_panel.py
git commit -m "feat: add widget lifecycle ownership scaffolding to Ports panel

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Render live widgets in `draw()`

Rewrite `draw()` to: dispose the prior batch, register the disconnect sweep once, declare `redraw_on`, and for each port either render its live widget (label above, via the factory) or fall back to the read-only `info_row`. Layered error handling keeps one bad port from blanking the panel.

**Files:**
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/panels/node_ports_panel.py`

**Reference — `WidgetFactory.render_widget` contract (already implemented, do not change):**
- Signature: `render_widget(self, registry_key: str, port: DataPort, node_id: str) -> tuple[IWidget | None, ui.element]`
- It **builds the widget element in the current NiceGUI context** (whatever `with` block is active at call time) and returns `(instance, element)`.
- On widget failure it returns `(None, <error element>)` — it renders an inline error chip and does **not** raise. So a single bad widget degrades to a chip in its own slot.
- `port.widget_key` is the registry key string; `port.id` is the port id; `port.label` is the human label.

- [ ] **Step 1: Add `redraw_on` to the `@panel(...)` decorator**

The decorator currently is:

```python
@panel(
    focus=NodeFocus,
    label="Ports",
    icon=hui.icon.node_ports,
    default_open=False,
    order=20,
)
```

Add the redraw signals so link-state changes (which flip `should_show_widget()`) re-mount the panel. Change it to:

```python
@panel(
    focus=NodeFocus,
    label="Ports",
    icon=hui.icon.node_ports,
    default_open=False,
    order=20,
    redraw_on=(SelectionMoved, GraphDataMutated, ActiveGraphMoved),
)
```

And add the signal import near the other top-level imports:

```python
from haywire.core.session.signals import (
    ActiveGraphMoved,
    GraphDataMutated,
    SelectionMoved,
)
```

- [ ] **Step 2: Add a per-port render helper that renders a widget or a fallback row**

Add this method to the class (place it after `_dispose_widgets`, before `poll`). It takes `widget_factory` as an explicit parameter (no closures — keeps it self-contained and typed). It encapsulates the per-port decision and the narrow per-port error guard (Q11 layered handling), and renders into the *current* NiceGUI context, so the `draw()` caller wraps it in the section/column.

```python
    def _render_port(self, port, node_id: str, widget_factory) -> None:
        """Render one port: its live widget (label above) when one applies,
        otherwise a read-only id/type metadata row.

        Honours should_show_widget() — the same predicate the Skin uses — so the
        two surfaces stay semantically identical (a linked inlet / an outlet
        shows no widget here either). A narrow try/except keeps one failing port
        from blanking the whole panel; widget-render failures are already
        isolated by WidgetFactory.render_widget (it returns an inline error
        element rather than raising). The namespaced 'panel:<node_id>' key keeps
        this panel's hot-reload tracking separate from the Skin's, so the Skin
        tearing down the node card (unregister_widget_for_node(node_id)) can't
        clobber it.
        """
        try:
            shows_widget = (
                widget_factory is not None
                and port.widget_key is not None
                and port.should_show_widget()
            )
            if shows_widget:
                with ui.column().classes("w-full gap-0 compact-fields"):
                    ui.label(port.label).classes("text-xs hw-text-dim px-2 pt-1")
                    instance, _element = widget_factory.render_widget(
                        registry_key=port.widget_key,
                        port=port,
                        node_id=f"panel:{node_id}",
                    )
                    if instance is not None:
                        self._widgets[port.id] = instance
            else:
                hui.info_row(str(port.id), _type_name(port))
        except Exception:
            hui.error_label(f"Error rendering port '{getattr(port, 'id', '?')}'")
```

- [ ] **Step 3: Rewrite the body of `draw()` — teardown + disconnect registration**

Replace the entire existing `draw()` method. The new version first disposes the prior batch and registers the one-time disconnect sweep, then renders. Here is the complete replacement `draw()`:

```python
    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        # Dispose the previous batch before building a new one. draw() is the
        # single teardown point: a redraw_on redraw and a selection change both
        # re-enter here, and BaseWidget.cleanup() is idempotent.
        self._dispose_widgets()

        node = ctx.data[EditState].active_node
        if node is None:
            return

        widget_factory = getattr(ctx.app, "widget_factory", None)

        with layout:
            # Register a one-time client-disconnect sweep so the final batch is
            # cleaned up when the page closes (draw() won't run again then).
            if not self._disconnect_registered:
                try:
                    ui.context.client.on_disconnect(self._dispose_widgets)
                    self._disconnect_registered = True
                except Exception:
                    pass

            try:
                hw_node = node.node if hasattr(node, "node") else None
                if hw_node is None:
                    hui.empty_state("No port data available", icon=hui.icon.node_ports)
                    return

                inlets = list(getattr(hw_node, "inlets", {}).values())
                outlets = list(getattr(hw_node, "outlets", {}).values())
                configs = [
                    p
                    for p in getattr(hw_node, "ports", {}).values()
                    if hasattr(p, "flow_type")
                    and str(getattr(p.flow_type, "name", "")) == "NONE"
                ]

                node_id = getattr(node, "node_id", "")

                hui.section_label(f"Inlets ({len(inlets)})")
                for port in inlets:
                    self._render_port(port, node_id, widget_factory)

                hui.section_label(f"Outlets ({len(outlets)})")
                for port in outlets:
                    self._render_port(port, node_id, widget_factory)

                if configs:
                    hui.section_label(f"Config ({len(configs)})")
                    for port in configs:
                        self._render_port(port, node_id, widget_factory)

            except Exception:
                # Structural backstop (Q11): a malformed node / port collection
                # must not throw through the panel host. Per-port failures are
                # handled inside _render_port; this catches everything above the
                # port loops.
                hui.error_label("Error reading ports")
```

- [ ] **Step 4: Add the `_type_name` helper as a module-level function**

The original `draw()` defined `_type_name` as a nested function. Promote it to a module-level helper so `_render_port` can call it. Add this near the top of the file, after the imports and before the `@panel` decorator:

```python
def _type_name(port: object) -> str:
    """Human-readable data-type name for a port's read-only metadata row."""
    port_type = getattr(port, "data_type", None)
    return port_type.__class__.__name__ if port_type else "—"
```

The old nested `_type_name` inside `draw()` is already gone (Step 3 replaced the whole method); this step just adds the module-level version that `_render_port` calls.

- [ ] **Step 5: Confirm the final import block and class shape**

The top of the file should now have (order may vary, but all present):

```python
from __future__ import annotations

from typing import TYPE_CHECKING

from nicegui import ui

from haywire.core.session.signals import (
    ActiveGraphMoved,
    GraphDataMutated,
    SelectionMoved,
)
from haywire.ui import elements as hui
from haywire.ui.panel import BasePanel, PanelLayout
from haywire.ui.panel.decorator import panel

from ..focuses import NodeFocus
from ..state.edit_state import EditState

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext
    from haywire.ui.widget.interface import IWidget
```

And the class has, in order: `__init__`, `_dispose_widgets`, `_render_port`, `poll`, `draw`.

- [ ] **Step 6: Verify lint + types**

Run:

```sh
uv run ruff check barn/haybale-graph-editor/haybale_graph_editor/panels/node_ports_panel.py
uv run ruff format --check barn/haybale-graph-editor/haybale_graph_editor/panels/node_ports_panel.py
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/
```

Expected: no new errors. If `ruff format --check` reports drift, run `uv run ruff format barn/haybale-graph-editor/haybale_graph_editor/panels/node_ports_panel.py` and re-check.

- [ ] **Step 7: Manual check — widgets appear, edit live, both ways, and survive selection/edge changes**

Run the app:

```sh
uv run haywire
```

Then in the studio:

1. Create or open a graph with a node that has a widgeted **config** or **unlinked inlet** port (e.g. a haybale-core node using `KnobWidget`/a number widget, or a node with a config port). Select the node.
2. Open the right-hand Properties editor → **Ports** panel. Confirm: under Inlets/Config the widgeted ports now render an actual control (slider/number/etc.) with the port label above it, not just a metadata row.
3. **Two-way sync:** drag the widget in the node card → the panel's widget updates. Change the panel's widget → the node card's widget and the port value update. (Both bind to the same port value.)
4. **Visibility mirror:** connect an edge into a previously-unlinked inlet. The panel re-mounts (via `GraphDataMutated`); that inlet's widget is replaced by the read-only `info_row` (because `should_show_widget()` is now False for a `NOT_LINKED` inlet). Disconnect → the widget returns.
5. **Outlets:** confirm outlets still show read-only rows (default `NEVER`).
6. **No leak / no crash:** select several different nodes in a row, move unrelated nodes (triggers `GraphDataMutated`), undo/redo. The panel should rebuild cleanly each time with no console errors and no duplicated/stuck widgets.

Expected: all of the above behave as described; no exceptions in the console bridge / terminal.

- [ ] **Step 8: Commit**

```bash
git add barn/haybale-graph-editor/haybale_graph_editor/panels/node_ports_panel.py
git commit -m "feat: render live editable port widgets in the Ports panel

The Ports panel now renders each port's live Widget (the same instance type
the node card shows) when widget_key is set and should_show_widget() is true,
falling back to the read-only id/type row otherwise. This gives a second
editing surface for nodes whose Skin omits inline widgets (e.g. top-to-bottom
flow skins). The panel owns the lifecycle of the widgets it creates and
registers them under a namespaced 'panel:<node_id>' key so factory hot-reload
tracking stays separate from the Skin's.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Write the ADR (final step)

The design is hard-to-reverse (the two-live-surfaces intent), surprising (namespaced tracking key, panel-owned cleanup, two live widgets per port), and the result of real rejected alternatives — so it warrants an ADR. The author chose to write it **after** the code lands, so it records the shipped shape.

**Files:**
- Create: `docs/adr/0008-ports-panel-widget-rendering.md`

- [ ] **Step 1: Confirm the next ADR number**

```sh
ls docs/adr/
```

Expected: highest existing is `0007-...`. Use `0008`. If a higher number now exists, use the next free number and adjust the filename below.

- [ ] **Step 2: Write the ADR**

Create `docs/adr/0008-ports-panel-widget-rendering.md` with:

```markdown
---
status: accepted
---

# Ports Panel renders live port Widgets as an always-on secondary surface

The node Ports Panel now renders each port's live, editable Widget — the same
control the node card shows — in addition to (not instead of) the in-node
rendering. The same port may have a live Widget instance in both the node card
(via the Skin) and the Ports Panel at once, each with its own
`port.on_changed` subscription. The motivating case is Skins that deliberately
omit inline widgets (e.g. a flow-direction skin laying nodes out top-to-bottom):
the panel keeps those ports editable.

## Why this shape

- **Always-on secondary surface, not a skin-driven fallback.** Whether a Skin
  renders a widget is a private Skin decision and is not queryable; coupling the
  panel to it would be fragile. The panel instead renders unconditionally and
  honours the port's own `should_show_widget()` (ADR 0003) — the same predicate
  the Skin uses. A Skin that omits a widget does so by not calling
  `render_widget` in `render()`, which is orthogonal to `should_show_widget()`,
  so the panel surfaces the omitted widget for free without knowing the active
  Skin.
- **Panel owns widget lifecycle.** `BaseWidget.render()` subscribes to
  `port.on_changed` and only unsubscribes in the final, idempotent `cleanup()`.
  The panel re-mounts on every `redraw_on` signal and selection change, so it
  stores the instances it creates and disposes the prior batch at the top of
  every `draw()`, plus a one-time client-disconnect sweep. This is contained in
  the panel; the shared panel framework gained no new teardown hook.
- **Namespaced factory tracking key.** The singleton `WidgetFactory` tracks
  `widget_key -> {node_ids}` for hot-reload and purges by `node_id` in
  `unregister_widget_for_node`. The panel registers its widgets under
  `panel:<node_id>` so the Skin tearing down the node card cannot clobber the
  panel's tracking entry, and vice versa.
- **Factory reached via `IProjectState`.** The panel obtains the factory as
  `ctx.app.widget_factory`, mirroring how it already reaches `node_factory` and
  `panel_registry`. Chosen over a module-level global-injector accessor to keep
  the access typed and consistent with the established `ctx.app.<service>`
  pattern, and to avoid introducing global-injector usage in the UI layer.

## Considered alternatives

- **Skin-driven fallback** (panel shows a widget only for ports the Skin hid):
  rejected — Skin render decisions are private and not queryable; would couple
  the panel to internal Skin state. Honouring `should_show_widget()` achieves
  the same user-visible outcome without the coupling.
- **Panel ignores `should_show_widget()` and renders every widget:** rejected —
  shows dead controls for linked inlets / outlets (the edge or display semantics
  make editing meaningless), adding noise.
- **A new panel teardown hook on `BasePanel`:** rejected for now — the
  top-of-`draw()` dispose pattern is sufficient and keeps the shared framework
  unchanged.
- **Global-injector accessor for the factory:** rejected in favour of
  `IProjectState` exposure (typed, consistent with existing service access).

## Consequences

- Any `GraphDataMutated` re-mounts all display panels (existing behaviour) and
  rebuilds every Ports-panel widget instance. Accepted as consistent with the
  existing `node_settings.py` panel; a heavy/stateful widget on an `ALWAYS`/
  config port would rebuild on unrelated edits.
- Panel widgets are **not** hot-reload-live: a widget-library reload re-renders
  the node card's instances but not the panel's until the panel next redraws.
  Deferred follow-up.
- `IProjectState` gains a `widget_factory` attribute; `LibrarySystemService`
  gains `get_widget_factory()`.
```

- [ ] **Step 3: Verify the docs site still builds the ADR (optional but cheap)**

```sh
uv run mkdocs build 2>&1 | tail -20
```

Expected: build succeeds (or only pre-existing warnings). If ADRs are not in the mkdocs nav, this step may simply confirm no broken-link errors were introduced; that is fine.

- [ ] **Step 4: Commit**

```bash
git add docs/adr/0008-ports-panel-widget-rendering.md
git commit -m "docs: ADR 0008 — Ports panel live widget rendering

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Out of scope (do NOT implement — locked in design Q10)

- Panel-widget hot-reload liveness (deferred follow-up).
- Any new per-port "show in panel" toggle or new `ShowWidgetStrategy` value.
- Editing port metadata (rename/retype ports, add/remove dynamic ports, edit `widget_key`).
- Per-port / per-section collapse controls beyond the panel's existing expansion state.
- The unrelated stale-header / `.codemap`-path doc drift in `node_props_panel.py`, `panel/base.py`, and `CLAUDE.md` (logged for a separate tidy-up; only `node_ports_panel.py`'s own header is fixed here in Task 2 Step 1).

## Final full-suite gate (after Task 4)

Per CLAUDE.md, run the full quality suite once at the end and confirm clean before presenting the work as complete:

```sh
uv run ruff check .
uv run ruff format --check .
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-TEST_A/haybale_test_a/
uv run pytest -m "not integration"
```

Expected: lint/format/type checks clean; the existing test suite passes (this plan adds no tests but must not break any). Any new failure attributable to these changes is yours to fix.
```
