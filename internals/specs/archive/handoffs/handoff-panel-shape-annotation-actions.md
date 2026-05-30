# Handoff — Panel architecture: annotation-based actions, focus-as-routing-primitive

## What this is

A design conversation, reached but not yet implemented, to clean up the panel system so it can support broader carve-outs (notably the `haybale-graph-editor` decoupling described in [`handoff-graph-editor-decoupling.md`](./handoff-graph-editor-decoupling.md)). **No code has been written yet.**

Triggered by the observation that `PropertiesEditorActions` (the action Protocol for properties-pane panels) is effectively vestigial — it declares one method (`clear_selection`) that is **never called** anywhere in the codebase. None of the 11 panels declaring `action=PropertiesEditorActions` ever invoke a method via their `actions` parameter. The Protocol exists purely as a routing label.

That observation generalised into a re-examination of the three primitives in the current `@panel` decorator (`action`, `focus`, `redraw_on`), and surfaced a cleaner mental model.

## The agreed mental model

A panel has three orthogonal facets, each with one primitive:

| Facet | Question it answers | Primitive |
|---|---|---|
| **Routing / topic** | Where does this panel appear? What is it about? | `focus=` (Focus subclass) |
| **Verb surface** | What can the panel invoke on its host? | type annotation `actions: SomeProtocol` |
| **Refresh** | When does the panel re-render? | `redraw_on=(...)` (tuple of Signal types) |

**Critical change vs. today:** the `action=` argument to `@panel` is **removed entirely**. Today it conflates two jobs (routing label + verb surface). The new model:

- **Routing/visibility is focus-only.** Hosts query the registry by focus. PropertiesEditor sorts panels by `Focus.order` and groups them by focus tab. Context-menu hosts query panels matching the click context's focus.
- **Verb surface is an annotation.** A panel declares `actions: NodeContextActions` as a regular type annotation in the class body. The framework reads `cls.__annotations__` (via `typing.get_type_hints`) at class-definition time, records the required Protocol, and at mount time sets `panel.actions = host` if `isinstance(host, Protocol)` succeeds. Panels without an `actions:` annotation have no host coupling.

The "host" concept (a separate class attribute used as a routing key) was **explicitly rejected by the user** — the goal is that third-party panels never reference the host class.

## The two natural panel patterns

Falling out of the model:

### Display panel — properties pane, info readouts

```python
class ThemeSettingsPanel(BasePanel):
    # no `actions:` annotation — display-only

    def draw(self, ctx: SessionContext, layout: PanelLayout) -> None:
        registry = ctx.app.library_service.get_settings_registry()
        render_schema(WorkbenchThemeSettings, registry)
```

Decorator: `@panel(focus=AppFocus, label="Workbench", redraw_on=(...))`.

### Action panel — context menus

```python
class DeleteNodePanel(BasePanel):
    actions: NodeContextActions  # framework injects host instance at mount

    def draw(self, ctx: SessionContext, layout: PanelLayout) -> None:
        node = ctx.data[EditState].active_node
        if node is None:
            return
        layout.button(
            "Delete Node",
            icon=hui.icon.delete,
            on_click=lambda: self.actions.delete_node(node.node_id),
        )
```

Decorator: `@panel(focus=NodeFocus, label="Delete", redraw_on=(...))`. The `actions:` annotation is the host-surface declaration. `draw()` accesses `self.actions.X` directly; no factory method indirection.

## Why this resonates

- **`actions:` annotation is one declaration doing two jobs**: tells the framework the contract; provides the injection point. Standard Python pattern (Pydantic / FastAPI / attrs all use type annotations as metadata).
- **Three orthogonal axes** with one primitive each — no overloaded `action=`, no empty marker Protocols, no host class import in third-party panels.
- **Backward compatibility** is straightforward: existing `PropertiesEditorActions` becomes a no-op Protocol that nothing references; existing context-menu Protocols (`NodeContextActions`, `EdgeContextActions`, etc.) keep their methods and just move from `action=` parameter to `actions:` annotation on the panels that use them.

## Open questions for the next session

These weren't resolved during the design conversation and need answers (probably via the `inquisition` skill) before implementation begins:

1. **Inheritance behaviour for the `actions:` annotation.** Should `BasePanel` define `actions: Any = None` as a fallback so attribute access on undeclared panels is safe? Or should accessing `self.actions` on a display panel that doesn't declare it raise `AttributeError`? Affects ergonomics in subclasses and tests.
2. **Optional actions via `Optional[T]`.** Is `actions: Optional[NodeContextActions] = None` (host may or may not satisfy the protocol; panel handles both) a first-class pattern, or should it be discouraged? Affects framework injection logic — does the framework check `isinstance` and skip injection on mismatch, or always inject `None` and let the panel handle it?
3. **`@panel(action=...)` deprecation path.** Land the new annotation pattern first while keeping `action=` working (deprecated), then sweep all panels, then remove `action=`? Or do a single hard-cutover migration? Affects PR size and rollback risk.
4. **Forward references.** Confirm that `typing.get_type_hints(cls)` resolves string annotations correctly under the codebase's hot-reload regime (modules can be reloaded; class objects can change). Should be standard but worth a small test.
5. **PropertiesEditor's panel query without action filtering.** Today it calls `panel_registry.get_panels_for(actions_provider=self, focus=...)`. The new model needs `get_panels_for(focus=...)` — a simpler signature. Confirm that returning panels regardless of action protocol doesn't surface unwanted panels (it shouldn't, because focus is already specific to the panel's topic, but worth a sanity pass).
6. **`get_redraw_signals_for` and the bus-subscription union.** Today this method walks panels matching `actions_provider` and unions their `redraw_on` sets. After the change it walks panels matching some focus criterion. Needs to be rethought — possibly per-focus union instead of per-host.

## Files that will change (estimate)

This is a framework change touching every panel declaration. Approximate scope:

- **Modified — `haywire-core`:**
  - `packages/haywire-core/src/haywire/ui/panel/decorator.py` — drop the `action=` argument; add annotation-introspection in the decorator (or in `BasePanel.__init_subclass__`).
  - `packages/haywire-core/src/haywire/ui/panel/identity.py` — replace `action: type` field with `action_protocol: Optional[type]` derived from annotations.
  - `packages/haywire-core/src/haywire/ui/panel/registry.py` — simplify `get_panels_for` signature; rework `get_redraw_signals_for`.
  - `packages/haywire-core/src/haywire/ui/panel/base.py` — likely add `actions: Any = None` as a typed fallback so subclasses can shadow it without `AttributeError` risk.
- **Modified — every panel-hosting editor:** `barn/haybale-studio/haybale_studio/editors/properties_editor.py` (host query), `barn/haybale-haystack/haybale_haystack/editors/haystack_editor.py` (if it hosts panels — verify), graph-canvas context-menu providers in `barn/haybale-studio/haybale_studio/editors/graph_canvas/handlers/`.
- **Modified — every panel:** roughly **30 panel files** across `barn/haybale-studio/haybale_studio/panels/`, `barn/haybale-haystack/haybale_haystack/panels/`, `barn/haybale-testing/`. Each needs:
  - Drop `action=X` from the `@panel(...)` call
  - Where the panel uses a verb surface: add `actions: X` as a class-body annotation; change `def draw(self, ctx, layout, actions)` to `def draw(self, ctx, layout)` accessing `self.actions`
  - Where the panel doesn't use a verb surface (most properties-pane panels): just drop the parameter
- **Deleted:** `barn/haybale-studio/haybale_studio/editors/properties_editor_actions.py` (the empty `PropertiesEditorActions` Protocol — no longer needed). `clear_selection()` on `PropertiesEditor` can be removed (verified never called).
- **Tests:** every test that mounts panels or checks action routing — non-trivial sweep; expect ~15–20 test files to need updates.
- **Docs:** `docs/components/panels/panel-canon.md`, `docs/components/editors/editor-canon.md` — describe the new model.

## Critical reference findings (established during the conversation)

- **`PropertiesEditorActions.clear_selection()` is implemented on `PropertiesEditor` but is never called anywhere.** Verified via `grep -rn "clear_selection" barn/ packages/ tests/` returning only the declaration and the implementation. Safe to remove with no behavioural change.
- **Existing action protocols by status:**
  - `PropertiesEditorActions` — empty marker, only-routing role, vestigial
  - `FileBrowserActions` — has real methods; load-bearing
  - `CanvasContextActions`, `NodeContextActions`, `EdgeContextActions`, `SelectionContextActions`, `PortContextActions` — all have real verb methods used by canvas context-menu panels; load-bearing
- **The panel registry's routing check** ([`packages/haywire-core/src/haywire/ui/panel/registry.py:102`](../../packages/haywire-core/src/haywire/ui/panel/registry.py#L102)) is the `isinstance(actions_provider, action)` line. This is what needs to be re-architected — the panel's required protocol becomes an annotation, and the host injection happens at mount time instead of being a registry-level filter.
- **9 focuses in `haybale-studio/focuses.py`**: `AppFocus`, `ExecutionFocus`, `CanvasFocus`, `SettingsFocus`, `GraphFocus`, `NodeFocus`, `EdgeFocus`, `PortFocus`, `SelectionFocus`. The first two are host-agnostic; the rest are graph-state-bound. Splitting them later (for the graph-editor decoupling) is downstream of this work but worth keeping in mind.

## Suggested skills for the next session

- **`inquisition`** — work through the 6 open questions above before any code is touched.
- **`writing-plans`** — once the open questions are resolved, produce a multi-stage implementation plan (likely 3–4 PRs: framework change, panel sweep, PropertiesEditor host-query refactor, cleanup).
- **`subagent-driven-development`** — execute the plan stage by stage. Each PR's scope is small enough to handle this way.
- **`haywire-ui`** — load the UI architecture docs before scaffolding the framework changes.

## What the next session should do

1. **Read this handoff and confirm the model**. The mental model section ("Routing/topic", "Verb surface", "Refresh") should be quoted back to the user verbatim for sign-off, since this is the core architectural claim.
2. **Open the `inquisition` skill** to walk through the 6 open questions in order. Each is small but consequential.
3. **Do not begin implementation until both this handoff AND the graph-editor decoupling handoff have aligned on dependencies.** The user has explicitly noted: "the decoupling would require the new panel shape, and then the new sorting for focus in properties editor before anything like that could be approached." Implementation order is: panel shape → PropertiesEditor focus-query refactor → graph-editor decoupling.

## Constraints the next session must respect (from CLAUDE.md)

- **No singleton/registration assumptions without confirming.** This refactor touches DI / registry semantics; confirm before changing class hierarchies.
- **Read files before editing; grep for callers before modifying functions.** The `get_panels_for` signature change has ~10+ call sites including tests.
- **Pre-edit baseline:** for substantial changes, run `uv run ruff check <path>` and `uv run mypy <path>` first, baseline the noise, then re-run after edits.
- **Test suite after the refactor:** run `uv run pytest -m "not integration"` and confirm green. Some tests will need rewriting (any test that constructed an actions-provider stub).

## Related artifacts (do not duplicate; reference)

- [`internals/handoffs/handoff-graph-editor-decoupling.md`](./handoff-graph-editor-decoupling.md) — depends on this work landing first
- [`internals/speculatives/archive/spec_panel_contract.md`](../speculatives/archive/spec_panel_contract.md) — archived Phase 1 panel contract spec; the "Phase 2 reactive subscriptions" content in there was the original direction and is now superseded by this proposal
- [`internals/speculatives/archive/event_bus_redesign.md`](../speculatives/archive/event_bus_redesign.md) — archived; provides historical context on why the panel system has its current shape
- [`internals/speculatives/library_dependency_ordering.md`](../speculatives/library_dependency_ordering.md) — orthogonal but related: the framework-level work to make library enable order respect declared dependencies. Will become more important as carve-outs introduce more cross-library state references.
- Existing panel decorator: [`packages/haywire-core/src/haywire/ui/panel/decorator.py`](../../packages/haywire-core/src/haywire/ui/panel/decorator.py)
- Existing panel registry: [`packages/haywire-core/src/haywire/ui/panel/registry.py`](../../packages/haywire-core/src/haywire/ui/panel/registry.py)
- Existing PropertiesEditor: [`barn/haybale-studio/haybale_studio/editors/properties_editor.py`](../../barn/haybale-studio/haybale_studio/editors/properties_editor.py)
- Existing focus definitions: [`barn/haybale-studio/haybale_studio/focuses.py`](../../barn/haybale-studio/haybale_studio/focuses.py)
