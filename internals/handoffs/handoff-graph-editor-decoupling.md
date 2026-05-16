# Handoff — Full GraphEditor decoupling: move graph-shaped code from haybale-studio into haybale-graph-editor

## What this is

A design conversation with the user, scoped to **the larger carve-out beyond the one already shipped**, walking through what it would take to make `haybale-graph-editor` truly self-contained — owning not just `GraphEditor` itself but all the state, canvas, panels, and editors that are graph-shaped. **No code has been written.** The user explicitly confirmed they want this direction ("if the carve-out of haybale_graph_editor should make any sense, then we have to cut those ties with studio and PropertiesEditor — otherwise we as well can leave it in studio. it's either-or") but recognised that prerequisite work has to land first.

## What's already shipped (do not re-do)

The first carve-out is **complete and merged to master**:

- New library `barn/haybale-graph-editor/` exists with `GraphContainer` protocol, `GraphAppState` registry, and `GraphEditor` itself (moved from haystack).
- `haybale-haystack` is now a source library that registers `GraphEntry` containers into `GraphAppState`.
- `haywire-core` is untouched.
- 1123 tests passing, lint + mypy clean (modulo one pre-existing weakref typing error).
- Implementation plan: [`internals/superpowers/plans/2026-05-16-graph-editor-carveout.md`](../superpowers/plans/2026-05-16-graph-editor-carveout.md)
- Stale prior handoff: [`internals/handoffs/handoff-graph-editor-carveout.md`](./handoff-graph-editor-carveout.md) — describes the work that has since landed
- Relevant master commits: `0f467afd` (the squashed carve-out), `803c7fae` (dependency-name fix), `93c1faf8` (insights), `7da80092` (topo-sort speculative), `141fbf3d` (archive speculatives)

**What's still wrong after that first carve-out** (and what this handoff is about):

- `EditState`, the graph-canvas widget, the context-menu panels, the properties editor, and the node/edge/port properties panels all still live in `haybale-studio`.
- `haybale-graph-editor` *depends on* `haybale-studio` to get them (`from haybale_studio.editors.graph_canvas.graph_canvas_manager import GraphCanvasManager`, `from haybale_studio.state.edit_state import EditState`).
- That dependency is upside-down: the editor library imports from the host shell. A second graph-source library couldn't reasonably coexist without studio being loaded.
- Result: the first carve-out's "decoupling" claim is partial. The architectural goal isn't met until this larger move lands.

## The user's framing

> "PropertiesEditor has to stay with studio and no tight reference between third party panels and PropertiesEditor should exist."
> "Focus is that decoupling methodology. PropertiesEditor just sorts for Focus and displays the panel it finds accordingly."
> "the decoupling would require the new panel shape, and then the new sorting for focus in properties editor before anything like that could be approached"

This sets three explicit prerequisites for this work:

1. **Panel architecture rewrite must land first** — see [`handoff-panel-shape-annotation-actions.md`](./handoff-panel-shape-annotation-actions.md). The new model removes `action=` from `@panel(...)` and uses focus as the routing primitive.
2. **PropertiesEditor focus-query refactor must land** — Properties Editor stops routing panels by `actions_provider isinstance check` and queries the panel registry by focus only.
3. **Only then** can the actual graph-editor decoupling be attempted.

Note: the user said **"PropertiesEditor has to stay with studio."** This is **opposite** to my earlier suggestion of moving PropertiesEditor into `haybale-graph-editor`. The decision the user landed on: PropertiesEditor is generic, focus-driven; it stays in studio; graph-related panels move out and depend on focus declarations only — not on PropertiesEditor's class.

## What "fully decoupled" looks like

After all prereqs and this work:

```
haybale-graph-editor (becomes substantial; owns all graph-shaped UI)
├── editors/
│   ├── graph_editor.py           (already there)
│   ├── node_source_editor.py     (moved from studio)
│   ├── library_component_editor.py (moved from studio)
│   └── graph_canvas/             (moved from studio — 14 files)
├── state/
│   ├── graph_app_state.py        (already there)
│   └── edit_state.py             (moved from studio)
├── panels/
│   ├── context_menu/             (moved from studio — 7 files)
│   └── properties/               (node/edge/port property panels; moved from studio)
├── protocols.py                  (already has GraphContainer; add ContextActions protocols here too)
└── focuses/
    └── graph_focuses.py          (the 5–7 graph-bound focuses moved out of haybale-studio/focuses.py)

haybale-studio (becomes a thin shell)
├── editors/
│   ├── properties_editor.py        (stays — generic, focus-driven)
│   ├── file_browser.py
│   ├── file_viewer.py
│   ├── code_editor.py
│   ├── library_browser_editor.py
│   ├── library_overview_editor.py
│   └── terminal_editor.py
├── panels/
│   ├── app_panels.py              (stays — non-graph-specific settings)
│   ├── canvas_settings.py         (stays — though it's graph-related, contains no graph state imports)
│   ├── execution_panel.py
│   ├── debug_panel.py
│   └── file_browser_menu/
└── focuses.py                    (only AppFocus and ExecutionFocus remain)

haywire-core (still untouched by this carve-out — except for the haywire-core → haybale-studio runtime import described below)
```

## Architectural hazards established during the conversation

Each hazard was identified during the design discussion. The next session must respect these.

### Hazard 1 — `haywire-core` imports from `haybale-studio` at runtime ⚠️

- [`packages/haywire-core/src/haywire/ui/components/graph/canvas.py:16`](../../packages/haywire-core/src/haywire/ui/components/graph/canvas.py#L16) — `from haybale_studio.editors.graph_canvas.event_definitions import BaseGraphEvent, GRAPH_EVENT_REGISTRY`
- [`packages/haywire-core/src/haywire/ui/components/graph/generators.py:12`](../../packages/haywire-core/src/haywire/ui/components/graph/generators.py#L12) — same module

The framework imports from the plugin — a directional inversion that already exists in master and was missed during the first carve-out. **This MUST be addressed as the very first sub-PR of this work.** The fix is to relocate `event_definitions.py` into `haywire-core` itself (it's framework-level wire-protocol definitions, not plugin-specific behaviour). This is independently beneficial — strict improvement regardless of whether the bigger carve-out proceeds.

### Hazard 2 — `EditState` is currently the canonical `SessionState` example for framework tests

Framework-level tests at `tests/core/test_session/test_context.py` and `tests/core/test_session/test_context_reactive.py` import `EditState` to exercise `SessionState` behaviour. After `EditState` moves to `haybale-graph-editor`, framework tests would depend on a plugin to test framework behaviour — a smell.

The right move is to extract a tiny test fixture `SessionState` subclass (e.g. `tests/conftest.py` defines a 3-field stub) and migrate the framework tests off `EditState` BEFORE moving `EditState` itself. This sub-task is small but must be done early.

### Hazard 3 — `PropertiesEditorActions` is currently a shared action protocol

The `PropertiesEditorActions` Protocol from [`barn/haybale-studio/haybale_studio/editors/properties_editor_actions.py`](../../barn/haybale-studio/haybale_studio/editors/properties_editor_actions.py) is the routing key for 11 panels, 9 of which would move to graph-editor and 2–4 of which would stay in studio (the non-graph settings panels). Today those panels declare `action=PropertiesEditorActions` and `focus=...`.

**After the panel-architecture rewrite** (the prereq), this hazard evaporates: panels declare only `focus=`, and the file `properties_editor_actions.py` is deleted entirely. PropertiesEditor queries the registry by focus alone. No third-party panel ever imports `PropertiesEditor` or anything from its module.

This is the load-bearing reason the panel rewrite must precede this work.

### Hazard 4 — `focuses.py` is split between graph-bound and host-agnostic

9 focus classes in [`barn/haybale-studio/haybale_studio/focuses.py`](../../barn/haybale-studio/haybale_studio/focuses.py):

- Stays in studio (host-agnostic): `AppFocus`, `ExecutionFocus`
- Stays in studio (graph-adjacent but no graph-state imports): `CanvasFocus`, `SettingsFocus` — verify case-by-case
- Moves to graph-editor (read `EditState`): `GraphFocus`, `NodeFocus`, `EdgeFocus`, `PortFocus`, `SelectionFocus`

The file gets split. New: `barn/haybale-graph-editor/haybale_graph_editor/focuses.py`. Each panel in either library must import its focus from the right place.

### Hazard 5 — Stay-behind studio panels currently import `PropertiesEditorActions`

The 4 non-graph panels that stay in studio (`app_panels.py`, `canvas_settings.py`, `debug_panel.py`, `execution_panel.py`) currently declare `action=PropertiesEditorActions`. After the panel rewrite, those declarations are simply dropped — the panels declare only `focus=` and have no host coupling. This is part of the panel-architecture-rewrite sweep, not this work specifically.

### Hazard 6 — Dependency direction inversion

Today: `haybale-graph-editor` → `haybale-studio` (for `GraphCanvasManager`, `EditState`).
After: `haybale-studio` → `haybale-graph-editor` is NOT introduced — the user explicitly wants no studio dependency on graph-editor. PropertiesEditor stays generic; it queries panels by focus and never imports any graph-editor symbol. The dependency direction collapses cleanly: graph-editor depends on `haywire-core` + `haybale-core` only; studio depends on the same.

Each library independently registers its panels into the shared `PanelRegistry`. PropertiesEditor's focus query finds them all without knowing which library produced them.

### Hazard 7 — Library enable order

`HaystackState.on_enable` already reads `app_data[GraphAppState]` (from the first carve-out). This work adds more cross-library state references (e.g. graph-editor focuses' `available()` methods read `EditState`, and `EditState` lives in graph-editor while focuses can be invoked from any host's panel-rendering pass). Enable order matters.

Today the order works by discovery-order luck; see [`internals/speculatives/library_dependency_ordering.md`](../speculatives/library_dependency_ordering.md). That speculative becomes more important after this carve-out. Recommendation: implement the library-dependency-ordering proposal *before or in parallel with* this work, not after.

## The proposed PR decomposition

Four ordered sub-PRs. Each independently shippable, each leaves the test suite green. Total scope ~69 files, comparable to the first carve-out × 3.

### Sub-PR 0 (prerequisite, NOT counted in the 4) — Panel architecture rewrite

See [`handoff-panel-shape-annotation-actions.md`](./handoff-panel-shape-annotation-actions.md). This MUST land first. Roughly 35 files modified (every panel declaration in the codebase + framework changes + tests).

### Sub-PR 0.5 (prerequisite) — Library-dependency-ordering implementation

See [`internals/speculatives/library_dependency_ordering.md`](../speculatives/library_dependency_ordering.md). Roughly 30 LOC change in `LibraryRegistry`, plus tests. Could land in parallel with Sub-PR 0 since they're independent.

### Sub-PR 1 — Fix the `haywire-core` → `haybale-studio` runtime import

Move [`barn/haybale-studio/haybale_studio/editors/graph_canvas/event_definitions.py`](../../barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/event_definitions.py) into `haywire-core` (likely under `packages/haywire-core/src/haywire/ui/components/graph/event_definitions.py`). Update the two importing files in `haywire-core`. Update the graph-canvas module to re-import from the new location (or be moved entirely in Sub-PR 2). Roughly 5 files. Independent of the panel rewrite — could land at any time, even before Sub-PR 0.

### Sub-PR 2 — Move `EditState` + the graph canvas

Extract a fixture `SessionState` for the framework tests (`tests/core/test_session/`). Migrate framework tests off `EditState`. Then `git mv`:
- `barn/haybale-studio/haybale_studio/state/edit_state.py` → `barn/haybale-graph-editor/haybale_graph_editor/state/edit_state.py`
- `barn/haybale-studio/haybale_studio/editors/graph_canvas/` (subtree, 14 files) → `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/`

Update all importers (~25 files). The dependency inversion happens here: `haybale-graph-editor` no longer imports from `haybale-studio` for these things.

### Sub-PR 3 — Move context-menu panels + their action protocols

The five canvas-context Protocols (`CanvasContextActions`, `NodeContextActions`, `EdgeContextActions`, `SelectionContextActions`, `PortContextActions`) currently live in [`barn/haybale-studio/haybale_studio/editors/graph_canvas/handlers/context_menu_actions.py`](../../barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/context_menu_actions.py). Move them to `barn/haybale-graph-editor/haybale_graph_editor/protocols.py` (or a sibling file).

Move [`barn/haybale-studio/haybale_studio/panels/context_menu/`](../../barn/haybale-studio/haybale_studio/panels/context_menu/) subtree (7 files) into `barn/haybale-graph-editor/haybale_graph_editor/panels/context_menu/`. The `file_actions.py` in there stays in studio — it's about the file browser, not graph editing.

### Sub-PR 4 — Move node/edge property panels + graph-bound focuses + remaining graph editors

Move:
- The 6 property panels from `barn/haybale-studio/haybale_studio/panels/` (node_settings, node_props_panel, node_status, node_ports_panel, edge_panels, graph_info_panel) → `barn/haybale-graph-editor/haybale_graph_editor/panels/properties/`
- `barn/haybale-studio/haybale_studio/editors/node_source_editor.py` → `barn/haybale-graph-editor/haybale_graph_editor/editors/node_source_editor.py`
- `barn/haybale-studio/haybale_studio/editors/library_component_editor.py` → `barn/haybale-graph-editor/haybale_graph_editor/editors/library_component_editor.py`
- Split [`barn/haybale-studio/haybale_studio/focuses.py`](../../barn/haybale-studio/haybale_studio/focuses.py): keep `AppFocus`, `ExecutionFocus`, `CanvasFocus`, `SettingsFocus` in studio; move `GraphFocus`, `NodeFocus`, `EdgeFocus`, `PortFocus`, `SelectionFocus` to `barn/haybale-graph-editor/haybale_graph_editor/focuses.py`

Update all importers; sweep tests.

## Files to be moved (counted)

Estimate from grep done during the conversation: **~34 file moves + ~35 modified-but-not-moved = ~69 files**, almost exactly 3× the first carve-out. The PR decomposition above splits this so each PR is roughly the size of the first carve-out or smaller.

## Critical reference findings (established during the conversation)

- **`PropertiesEditorActions.clear_selection()` is implemented but never called.** Verified. Will be deleted as part of the panel rewrite. See the panel handoff.
- **The first carve-out's `haybale-graph-editor` already structurally depends on `haybale-studio`.** Two imports in [`barn/haybale-graph-editor/haybale_graph_editor/editors/graph_editor.py:28-29`](../../barn/haybale-graph-editor/haybale_graph_editor/editors/graph_editor.py#L28-L29) prove it. These are exactly what Sub-PRs 2 + 3 resolve.
- **6 studio editors are not graph-shaped** and stay in studio: `code_editor`, `file_browser`, `file_viewer`, `library_browser_editor`, `library_overview_editor`, `terminal_editor`. Verified none of them import `EditState` or graph canvas modules.
- **`haybale-testing` has 5 files** that import graph-editor state/canvas modules. Sub-PR 2 must update them.
- **Test pollution:** 17 test files reference the candidate-to-move modules. Many tests use `EditState` as the canonical `SessionState` example, which is exactly the hazard described above.

## Open questions for the next session

These weren't resolved and may require new design conversations:

1. **Does `haybale-studio` depend on `haybale-graph-editor`?** The user said no, but check whether PropertiesEditor genuinely never needs anything from graph-editor (e.g., for `Focus` class re-exports, or for `EditState` references in `Focus.available()` methods of focuses that stay in studio). If `CanvasFocus` stays in studio but reads `EditState`, that's a dependency.
2. **Does `barn/haybale-haystack/` need changes?** Haystack today reads `EditState` (it imports it at line 40 of `haystack_editor.py`). After EditState moves, haystack would depend on graph-editor for `EditState` — that's already true after the first carve-out (haystack depends on graph-editor for `GraphAppState`), so this is consistent.
3. **What's the ownership of `properties_editor_actions.py`?** Will it be deleted entirely (after the panel rewrite removes all `action=...` references) or kept as a no-op for backward compatibility? Probably deleted.
4. **What's the ownership of focus classes referenced by both libraries?** E.g., `CanvasFocus` is currently defined in studio. If it gates visibility on `EditState`-something AND is used by both studio panels (canvas_settings) and graph-editor panels — does it move with the graph state, or stay near the studio panels that reference it? Probably moves with `EditState`.
5. **Is there a meaningful "studio without graph-editor" scenario?** If yes, the carve-out enables it. If no, the carve-out is purely an architecture-cleanliness move. Worth confirming the use case before committing 4 PRs of work.

## Suggested skills for the next session

- **`inquisition`** — definitely; this work touches a lot of files and there are 5+ open questions. Work through them before any plan is written.
- **`writing-plans`** — once design is locked, write a 4-PR plan (each PR its own plan file).
- **`subagent-driven-development`** — execute each PR with the same TDD-and-checkpoint pattern that worked for the first carve-out.
- **`haywire-libs`** — load the library system docs.
- **`haywire-ui`** — load the UI architecture docs (editors, panels, slot model).

## What the next session should do

1. **Read both handoff documents** ([this one](./handoff-graph-editor-decoupling.md) and [`handoff-panel-shape-annotation-actions.md`](./handoff-panel-shape-annotation-actions.md)) front to back.
2. **Confirm the prerequisite chain.** This work is **blocked** on:
   - Panel architecture rewrite (the other handoff) landing first
   - Library-dependency-ordering ideally landing too (lower priority but reduces risk)
   - Sub-PR 1 (haywire-core → haybale-studio import fix) — this can be done at any time, even now, as a standalone cleanup
3. **Do not start sub-PRs 2/3/4 until prerequisite (1) is done.** The panel rewrite is the load-bearing piece; without it, every `action=PropertiesEditorActions` would have to be plumbed through during the carve-out, creating massive churn.
4. **Consider whether to land Sub-PR 1 immediately** as a standalone cleanup, regardless of whether the rest of this work proceeds. It's strictly beneficial.

## Constraints the next session must respect (from CLAUDE.md)

- **No singleton/registration assumptions without confirming.** This is a registry-level refactor.
- **Read files before editing; grep for callers before modifying functions.** ~69 files; a missed importer in any of them breaks the suite.
- **Pre-edit baseline:** for each sub-PR, run `uv run ruff check <path>` + `uv run mypy <path>` first.
- **Tests after each sub-PR:** `uv run pytest -m "not integration"` green before committing.
- **`HaystackTeardown.entry_ids` (signal payload) is out of scope** — frozen for cross-session compatibility, as established in the first carve-out.

## Related artifacts (do not duplicate; reference)

- [`internals/handoffs/handoff-panel-shape-annotation-actions.md`](./handoff-panel-shape-annotation-actions.md) — REQUIRED prerequisite for the panel-related sub-PRs
- [`internals/handoffs/handoff-graph-editor-carveout.md`](./handoff-graph-editor-carveout.md) — STALE; describes the first carve-out which is complete
- [`internals/superpowers/plans/2026-05-16-graph-editor-carveout.md`](../superpowers/plans/2026-05-16-graph-editor-carveout.md) — the completed plan; this work is a strict superset in intent but a different shape
- [`internals/speculatives/library_dependency_ordering.md`](../speculatives/library_dependency_ordering.md) — relevant, should land before or alongside
- [`internals/speculatives/archive/`](../speculatives/archive/) — archived prior design specs (panel contract, event bus, signal-field unification, panel reactivity) for historical context
- [`.insights/project_library_dependencies_use_package_names.md`](../../.insights/project_library_dependencies_use_package_names.md) — the package-name vs library-id pitfall surfaced during the first carve-out
