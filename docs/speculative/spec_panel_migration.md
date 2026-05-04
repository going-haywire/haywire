# Migration: legacy `BasePanel` to the new panel contract

> Status: **Phase 1 + Phase 1.5 complete (2026-05-03 / 2026-05-04).**
> All production panels and test fixtures run on the new `Panel`
> contract. 0 `BasePanel` panels remain. The class itself — along
> with `register_scope`, `get_scopes`, `ScopeDescriptor`,
> `editors=`/`scopes=` decorator args, the legacy `_index` and
> dual-mode `_class_filter`, the `metadata['on_emit_event']` bridge,
> and the `data-hw-*-menu-scope` DOM attributes — is removed.
> Cross-package layering fixed: `PropertiesEditorActions` moved from
> `haybale-studio` to `haybale-core`.
>
> Companion to [`spec_panel_contract.md`](spec_panel_contract.md).
> Inventories the existing `BasePanel` subclasses, maps each to its
> destination under the new contract, and identifies framework-level
> work and gaps that have to be resolved during the transition.
>
> This is not an implementation plan with task breakdowns and
> sequencing — it's the inventory and gap analysis a real plan would
> build on.

---

## 1. Scope

The contract spec (`spec_panel_contract.md`) describes the destination
state. This document covers the path from today's codebase:

- All `BasePanel` subclasses currently in `barn/haybale-core` and
  `barn/haybale-studio` (production code).
- Test fixture panels in `barn/haybale-testing` that mirror production.
- Framework code that's deprecated by the new contract:
  `PanelRegistry.register_scope`, `get_scopes`, `ScopeDescriptor`,
  the scope registration call sites.

Out of scope for this document:

- Phase 2 reactivity migration (the `panels_and_hosts` Step 0–3 work
  did this for some panels already; that branch is closed and its
  approach is captured in `spec_panel_reactivity.md`).
- The reactive subsystem implementation itself.
- Editor/host code changes beyond what the panel migration directly
  requires.

---

## 2. Inventory: BasePanel subclasses in production

33 production `BasePanel` subclasses, grouped by their target host
and current scope.

### 2.1 PropertiesEditor panels (haybale-core)

14 panels across 5 scopes.

| Scope | Panel class | File |
|---|---|---|
| `settings` | NodeSettingsPanel | `panels/node_settings.py` |
| `node` | NodePortsPanel | `panels/node_ports_panel.py` |
| `node` | NodeStatusPanel | `panels/node_status.py` |
| `node` | NodeInfoPanel | `panels/node_props_panel.py` |
| `node` | NodePropertiesPanel | `panels/node_props_panel.py` |
| `edge` | EdgeErrorsPanel † | `panels/edge_panels.py` |
| `edge` | EdgeWarningsPanel † | `panels/edge_panels.py` |
| `edge` | ExecutionStatisticsEdgePanel | `panels/edge_panels.py` |
| `edge` | ConnectionPathEdgePanel | `panels/edge_panels.py` |
| `canvas` | CanvasSettingsPanel | `panels/canvas_settings.py` |
| `canvas` | NodeSkinSettingsPanel | `panels/canvas_settings.py` |
| `canvas` | EdgeUISettingsPanel | `panels/canvas_settings.py` |
| `canvas` | EditorZoomPanSettingsPanel | `panels/canvas_settings.py` |
| `canvas` | MinimapSettingsPanel | `panels/canvas_settings.py` |
| `graph` | GraphInfoPanel | `panels/graph_info_panel.py` |

† Dual-registered under `editors=["context_menu", "properties"]`. See
§3.3 for how the new contract handles this case.

### 2.2 PropertiesEditor panels (haybale-studio)

4 panels across 2 scopes.

| Scope | Panel class | File |
|---|---|---|
| `execution` | ExecutionSettingsPanel | `panels/execution_panel.py` |
| `execution` | DebugSettingsPanel | `panels/debug_panel.py` |
| `app` | ThemeSettingsPanel | `panels/app_panels.py` |
| `app` | NodeSkinDefaultPanel | `panels/app_panels.py` |
| `app` | EditorSettingsPanel | `panels/app_panels.py` |

### 2.3 Context-menu panels (haybale-core)

14 panels across 6 scopes.

| Scope | Panel class | File |
|---|---|---|
| `selection` | CopySelectionPanel | `panels/context_menu/selection_actions.py` |
| `selection` | PasteSelectionPanel | `panels/context_menu/selection_actions.py` |
| `node` | DeleteNodePanel | `panels/context_menu/node_actions.py` |
| `node` | CopyNodePanel | `panels/context_menu/node_actions.py` |
| `node` | RedrawNodePanel | `panels/context_menu/node_actions.py` |
| `node` | RevalidateNodePanel | `panels/context_menu/node_actions.py` |
| `node` | ResetNodePanel | `panels/context_menu/node_actions.py` |
| `node.errors` | NodeErrorsPanel | `panels/context_menu/node_errors.py` |
| `edge` | DeleteEdgePanel | `panels/edge_panels.py` |
| `edge` | ReconnectEdgePanel | `panels/context_menu/edge_actions.py` |
| `edge` | EdgeErrorsPanel † | `panels/edge_panels.py` |
| `edge` | EdgeWarningsPanel † | `panels/edge_panels.py` |
| `port.info` | PortInfoPanel | `panels/context_menu/port_info.py` |
| `canvas` | CreateNodePanel | `panels/context_menu/create_node_panel.py` |

† Same dual-registered pair as §2.1.

### 2.4 Test fixtures (haybale-testing)

12 panels in `barn/haybale-testing/haybale_testing/panels/` that
mirror production panels for test purposes:

- `test_create_node_panel.py` — 1 panel
- `test_selection_panels.py` — 2 panels
- `test_node_panels.py` — 5 panels
- `test_edge_panels.py` — 5 panels (one extra: TestInspectEdgePanel)

These migrate alongside their production counterparts.

---

## 3. Mapping legacy declarations to the new contract

### 3.1 `editors=...` → `action=...`

The legacy `editors=` argument names which editor types a panel
appears in (string-keyed). The new `action=` argument names a type
contract the host must satisfy (class-keyed).

| Legacy `editors=` | New `action=` | Status |
|---|---|---|
| `"properties"` | `PropertiesEditorActions` | Protocol exists (`barn/haybale-studio/haybale_studio/editors/properties_editor_actions.py`) — designed in `panels_and_hosts` Step 2; one method (`clear_selection`); needs expansion as panels migrate and reveal real verb requirements. |
| `"context_menu"` | `ContextMenuActions` | **Does not exist.** Must be designed before the context-menu panels migrate. See §4.1. |

### 3.2 `scopes=...` → `focus=...`

The legacy `scopes=` argument names a registration string. The new
`focus=` argument names a Focus class.

| Legacy scope | Focus class | Status |
|---|---|---|
| `"app"` | `AppFocus` | exists (`barn/haybale-studio/haybale_studio/focuses.py`) |
| `"execution"` | `ExecutionFocus` | exists |
| `"canvas"` | `CanvasFocus` | exists |
| `"settings"` | `SettingsFocus` | exists |
| `"graph"` | `GraphFocus` | exists (`barn/haybale-core/haybale_core/focuses.py`) |
| `"node"` | `NodeFocus` | exists |
| `"edge"` | `EdgeFocus` | exists |
| `"selection"` | — | **Gap.** No SelectionFocus today. See §4.2. |
| `"node.errors"` | — | **Gap.** Likely folds into NodeFocus + panel-level `poll`. See §4.3. |
| `"port.info"` | `PortFocus`? | **Gap.** PortFocus exists, but the scope used dot-notation suggesting a sub-scope. Needs review during migration. See §4.4. |

### 3.3 Dual-registered panels

`EdgeErrorsPanel` and `EdgeWarningsPanel` register under
`editors=["context_menu", "properties"]` today. Two paths in the new
contract:

**Path A — keep two classes, one per host.** Mirrors the
`panels_and_hosts` branch's Step 3 approach. Each panel splits into
two classes that share helper functions for predicate and rendering
logic. This is the workaround the new design was meant to dissolve;
not recommended.

**Path B — define a shared capability Protocol.** A capability
Protocol like `ShowsEdgeDiagnostics` (or a more general `Inspectable`)
declares the verbs both hosts can satisfy. Both hosts implement the
Protocol; the single panel declares `action=ShowsEdgeDiagnostics` and
appears in both naturally.

The new contract favors Path B. Migration of the dual-registered
panels should be deferred until both PropertiesEditorActions and
ContextMenuActions are defined and a candidate shared Protocol can
be identified.

---

## 4. Gaps and open questions

### 4.1 `ContextMenuActions` Protocol design

The context-menu host today does not have a typed actions Protocol.
Designing it requires inspecting what its 14 panels currently call.
Likely verbs based on panel names:

- `delete_nodes(node_ids: list[str]) -> None`
- `copy_nodes(node_ids: list[str]) -> None`
- `paste_at(position: ...) -> None`
- `redraw_node(node_id: str) -> None`
- `revalidate_node(node_id: str) -> None`
- `reset_node(node_id: str) -> None`
- `delete_edges(edge_ids: list[str]) -> None`
- `reconnect_edge(edge_id: str) -> None`
- `create_node_at(position: ..., node_class: type) -> None`

The actual surface should be derived from the panels' current
`metadata["on_emit_event"]` call sites — those are the verbs the
panels need. Design happens during migration, not now.

### 4.2 SelectionFocus

The `"selection"` scope today gates panels on "is anything currently
selected" (selection_actions.py: CopySelectionPanel, PasteSelectionPanel).

Two options:

- **Define `SelectionFocus`.** A new Focus class whose `available()`
  returns True when `len(ctx.selected_nodes.value) > 0` (or similar).
  Clean but adds a new focus class to the toolbar.
- **Fold into existing focuses.** Selection-driven panels become panels
  under NodeFocus (or a new general-purpose AppFocus-equivalent for
  context-menu) with a `poll()` that checks selection size. Avoids
  the new focus class.

Selection panels are context-menu-only today, where focus tabs are
less prominent. Folding (option 2) is probably cleaner. Decide during
migration based on what the context-menu host's UX actually needs.

### 4.3 NodeErrorsFocus

The `"node.errors"` scope is used by exactly one panel
(NodeErrorsPanel in context_menu). It gates on "the active node has
errors."

The dot-notation (`node.errors`) suggests a sub-scope under `node`,
which the legacy registry didn't really support — it's a string match.
The new contract's natural equivalent is `focus=NodeFocus` with a
`poll()` that gates on the error condition:

```python
@panel(action=ContextMenuActions, focus=NodeFocus, ...)
class NodeErrorsPanel(Panel):
    @classmethod
    def poll(cls, ctx) -> bool:
        node = ctx.active_node.value
        return node is not None and node.has_errors()
```

No new Focus class needed. The dot-notation goes away naturally.

### 4.4 PortFocus and the `port.info` scope

`PortFocus` exists and gates on `ctx.active_port.value is not None`.
The legacy scope `port.info` is used by one panel (PortInfoPanel,
context-menu). Same situation as 4.3: the dot-notation was a quirk of
the string-keyed registry. Migration target: `focus=PortFocus`. The
panel's `poll()` can refine further if `port.info` had additional
gating (review during migration).

### 4.5 Settings system integration

Many migrated panels write to settings — node properties, canvas
defaults, theme tokens, etc. The contract spec says (§3.4) these
writes go through the settings system directly, not through actions.

Migration must verify: legacy panels using `metadata["on_emit_event"]`
to mutate state need to be examined. Some are domain verbs (delete,
reconnect — those go on the action Protocol). Some are settings
writes (the bulk of the canvas_settings/app_panels content — those
go through the settings registry directly). The audit happens
per-panel during migration.

---

## 5. Framework cleanup post-migration

Once all panels listed in §2 have migrated:

- Remove `BasePanel` from `packages/haywire-core/src/haywire/ui/panel/base.py`.
- Remove the legacy `editors=`/`scopes=` arguments from
  `@panel` decorator (`packages/haywire-core/src/haywire/ui/panel/decorator.py`).
- Remove `PanelRegistry.register_scope`, `PanelRegistry.get_scopes`,
  and the entire `ScopeDescriptor` class (`packages/haywire-core/src/haywire/ui/panel/scope.py`).
- Remove `barn/haybale-studio/haybale_studio/editors/scopes.py` (the
  scope registration call site).
- Remove the legacy `(editor_key, scope_id)` index in
  `PanelRegistry`; the new index is keyed by (action class, focus class).
- Remove the legacy `_host_class_to_editor_key` /
  `_focus_class_to_scope_id` translation helpers in
  `PanelRegistry` and `@panel` decorator (these exist on the
  `panels_and_hosts` branch and should not be re-introduced when
  building the new design).

Tests that exercise `register_scope` / `get_scopes` / `ScopeDescriptor`
either get rewritten against the new APIs or removed if redundant.

---

## 6. Suggested migration tracks

A real implementation plan would sequence the work; this section
sketches a coarse-grained ordering that minimizes risk.

**Track A — PropertiesEditor panels (haybale-core + haybale-studio).**
18 panels. PropertiesEditorActions exists (one method); expand as
panel migrations reveal needed verbs. All Focus classes exist. No
gaps in §4 block this track. The largest track but the most
mechanical.

**Track B — ContextMenuActions Protocol design.** Pre-requisite for
Track C. Audit the context-menu panels' current `metadata` and
`on_emit_event` usage; design the Protocol surface; implement on the
context-menu host (whatever that host is — context-menu rendering
today is a popup mounted ad-hoc; how it becomes an action-providing
host is part of this track's design).

**Track C — Context-menu panels.** 14 panels. Depends on Track B.
Resolve the `selection` and `port.info` gaps (§4.2, §4.4) inline as
panels migrate.

**Track D — Dual-host edge panels.** 2 panels. Depends on Tracks A
and B both providing concrete actions surfaces. Identify a shared
capability Protocol; collapse the dual-class pattern (per §3.3 Path B).

**Track E — Test fixtures.** 12 panels. Migrates alongside the
production panels they mirror. Not a separate track in scheduling
terms — fold into A and C.

**Track F — Cleanup.** Remove deprecated framework code per §5.
Final track, gated on all production and test panels migrated.

---

## 7. Out of scope (this document)

- **Implementation sequencing and per-task breakdowns.** This is the
  inventory and gap-analysis layer; the actual plan with steps,
  PR boundaries, and verification gates is downstream.
- **Phase 2 reactivity migration.** Panels migrate first to the
  contract (Phase 1). Reactive lifecycle migration is a separate
  pass per `spec_panel_reactivity.md` §8.3.
- **Host-side migration.** PropertiesEditor and the context-menu
  host need updates to use the new registry queries (`get_panels_for`,
  `get_focuses_for`). These are part of host-side work, not panel-
  side migration.
- **`panels_and_hosts` branch resurrection.** That branch is closed.
  Its panel migrations to `Child[PropertiesEditorContext]` are not a
  starting point — they were keyed against a different design (host=,
  not action=). Reference its commits for shape and patterns; do not
  cherry-pick.
