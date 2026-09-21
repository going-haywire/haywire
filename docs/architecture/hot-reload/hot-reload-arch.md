---
status: draft
doc_template: impl-spec
scope: Cross-cutting hot-reload pipeline — FileWatcher → BaseRegistry events → wrapper rebuild → graph revalidation
see-also:
  - ../library-system/library-system-arch.md
  - ../execution/edges/edges-arch.md
  - ../execution/assembly/assembly-arch.md
  - ../session-and-state/session-and-state-arch.md
  - ../../reference/glossary.md
---

# Hot-Reload — Architecture

## 1. Mental model

Hot-reload is the framework's response to a `.py` file change in a library that has `file_watcher=True`. It re-imports the changed module, re-registers any decorated classes from that module under their existing `registry_key`s, and allows thus every wrapper to rebuild the referenced class on the spot.

It is a **cross-cutting** subsystem: every registry (NodeRegistry, EdgeRegistry, AdapterRegistry, WidgetRegistry, SkinRegistry, ThemeRegistry, SettingsRegistry, LibraryStateRegistry, EditorTypeRegistry, PanelRegistry) subscribes to the same `BaseRegistry` event pipeline. Hot-reload doesn't know what kind of class is reloading — it just fires events; consumers (factories, wrappers, the graph) handle the rebuild for their own concerns.

The discipline is: **every wrapper rebuilds references of a reloaded class** so user code sees only the new class. Managed modules are evicted from `sys.modules` before re-import (`del sys.modules[name]` in `folder_scan.py`), so the module object is replaced — not accumulated. Closures and direct attribute references to old classes can still pin memory, but the module slot itself is reused.

## 2. Contract

### 2.1 The cascade

```text
File change
  ↓
FileWatcher → FileChangeEvent
  ↓
BaseClassRegistry.event_dispatcher()
  ├─ _on_creation
  ├─ _on_change
  └─ _on_delete
  ↓
_reload_managed_module()                    [Internal state updated]
  ├─ Reload Classes
  ├─ Add Classes
  └─ Remove Classes
  ↓
_notify_customer_callbacks()                [Factories rebuild instances]
  ├─ NodeFactory._on_node_reloaded()
  ├─ NodeRenderFactory._on_renderer_reloaded()
  └─ NodeRenderFactory._on_widget_reloaded()
  ↓
_notify_registry_subscribers()              [Cross-registry cascade]
  ├─ NodeRegistry.event_dispatcher()
  ├─ Renderer Registry
  ├─ Widget Registry
  └─ ... other registries
  ↓
[Cascade reload]                            [Dependent nodes rebuilt]
```

### 2.2 What runs when

| Trigger | Mechanism |
|---|---|
| `FileWatcher` detects a file change | `watchdog` filesystem observer; one per library with `file_watcher=True`. The handler is a **router**: it offers *every* non-directory event to the registries that claimed the folder. `BaseRegistry.event_dispatcher` drops anything that is not a `.py` — deciding that only modules reload is the registry's business, not the watcher's, which is why a **document registry** claiming a different suffix (`MacroRegistry`, `.hwm`) needed no watcher change at all. A library's own `haybale.toml` is picked up on the root fallback by `_HaybaleTomlWatcher`, which refreshes the identity without any module reload |
| Module reload | `importlib.reload(module)` |
| Class re-registration | Decorator (`@node`, `@type`, etc.) re-runs on import; `BaseRegistry._class_filter` picks up the new class under the same `registry_key` |
| Wrapper rebuild | `NodeWrapper.build()` re-instantiates from current code, discarding values, `props` and `store` (§3.2); `EdgeWrapper.build()` runs the 4-stage pipeline against new ports |
| Graph revalidation | `ValidationManager` debounce-batches the dirty events; flows reassemble |

### 2.3 What hot-reload does NOT unload

Hot-reload **does not** fully unload the *old* module, but it does replace it in `sys.modules`. The managed reload path (`_reload_managed_module`) calls `module_scan_for_classes` with `force_reload=True`, which does:

```python
if force_reload and module_name in sys.modules:
    del sys.modules[module_name]   # evict stale entry
importlib.import_module(module_name)  # fresh import replaces it
```

So the `sys.modules` slot is reused, not accumulated. What can still pin old class objects in memory:

- Closures captured by long-lived callbacks
- Direct attribute references (`some_obj.cached_class = OldClass`)

## 3. Lifecycle

### 3.1 Per-registry consumer hooks

Each registry attaches its own consumers:

| Registry | What it does on reload |
|---|---|
| `NodeRegistry` | The lifecycle batch is relayed **per registry key** to every NodeWrapper subscribed on that key, across every open graph — all graphs share one factory. Each wrapper rebuilds, unless its node absorbs the reload itself (§3.2) |
| `MacroRegistry` | A **document registry** ([ADR 0037](../../adr/0037-macros-are-node-kind-components.md)): a saved `.hwm` file emits `CLASS_RELOADED` on the macro's own key, and the same per-key relay reaches every placement of it |
| `EdgeRegistry` (implicit via NodeRegistry) | Affected EdgeWrappers re-run their 4-stage build against new port objects |
| `AdapterRegistry` | Edges using a reloaded adapter rebuild their adapter chain |
| `WidgetRegistry` | New widget instances pick up the new class; existing widgets don't swap mid-render (NiceGUI element teardown is risky) |
| `ThemeRegistry` | Active workbench theme is re-applied via `apply_workbench_theme()` (CSS variables re-injected) |
| `SettingsRegistry` | Schema descriptors re-bind; `cls._registry` is re-wired on the new class |
| `LibraryStateRegistry` | Container disable/re-enable cycle — `on_disable` on old instance, swap class, `on_enable` on new instance ([session-and-state §3.4](../session-and-state/session-and-state-arch.md#34-hot-reload-semantics)) |
| `PanelRegistry` / `EditorTypeRegistry` | New classes picked up at next render boundary; existing instances continue until natural slot/binding change |

### 3.2 Rebuild discards node state

A reloaded node is rebuilt **fresh from current code**, not restored:

```text
Reload class:
  importlib.reload(module)   # @node decorator re-runs, registry updates
  ↓
Per-key relay:
  NodeWrapper._on_node_lifecycle_event   # marks NODE_HOT_RELOADED
  ↓
Validation:
  node_wrapper.build()       # no node_info → a fresh init()
  edges revalidate           # 4-stage edge build against new port objects
```

`build()` is called with **no** `node_info`, so the node runs its `init()` again. Port values, `props` — including the user's label — and the `store` are gone. Only the node's position survives, plus its edges, which rebind by port id.

That is deliberate rather than an oversight. `_initialize_from_dict` restores the *serialized* port set without calling `init()`, so carrying saved state across a class reload would keep showing the old port set and hide the new ports the author just wrote — the one thing the author is reloading to see.

A node whose definition lives **outside its class** must not take that path. `BaseNode.on_class_reloaded(event) -> bool` returns `False` by default; `NodeWrapper` consults it first on a successful lifecycle event and returns early when it answers `True`. A macro placement answers `True` and swaps its interior in place, keeping its values and label ([ADR 0038](../../adr/0038-a-placements-interior-is-runtime-state.md)). An override that raises is logged, and the node takes the generic rebuild.

`cache` containers are not preserved either — see §3.5.

### 3.3 Edge revalidation

When a node hot-reloads, its attached edges need to re-resolve port references and re-test adapter chains:

1. `NodeWrapper.build()` instantiates the new class, calls `init()`, builds new port objects.
2. All attached edges marked `EDGE_ADAPTERS_RELOADED` (priority 80) in the dirty queue.
3. `EdgeWrapper._formal_validation()` refreshes `_outlet_port` / `_inlet_port` references from the new node instance.
4. `_build_adapter_chain()` re-resolves the chain (adapter classes may have reloaded too).
5. `_test()` runs the chain against a sample value; on failure, edge transitions to non-functional and gets unlinked.
6. On success, `link()` registers at the new ports — including any displaced/re-enableable edges in `_all_edges`.

See [edges §3.7](../execution/edges/edges-arch.md#37-hot-reload-coordination-node-rebuild) for full mechanics.

### 3.4 Flow reassembly

Once edges have rebuilt and the dirty queue settles, `FlowAssemblyManager` reassembles the affected Flows. Only Flows whose reachable set includes a reloaded node/edge reassemble; unrelated Flows are untouched.

See [assembly §3.4](../execution/assembly/assembly-arch.md#34-hot-reload-coordination).

### 3.5 LibraryState reload — disable + enable

State classes ([components/states](../../components/states/state-canon.md)) follow a strict exit-before-enter discipline:

```text
1. on_disable() runs on the OLD instance, against the OLD class
2. Class is swapped in LibraryStateRegistry
3. on_enable() runs on a NEW instance, against the NEW class
```

In-flight state is lost. If `on_enable` is expensive (warming a cache, scanning hardware), reload pays that cost again — by design.

### 3.6 Theme reload

`ThemeRegistry` has the smoothest reload path:

1. New theme class registered.
2. If the active workbench theme key matches the reloaded class, `AppShell.apply_workbench_theme()` runs.
3. Each CSS variable is re-injected via `document.documentElement.style.setProperty(...)`.
4. The browser re-paints; no page reload.

A node-flavoured theme's reload is similar: the studio re-injects that tier's
CSS variables (global `:root`, or the graph's `.graph-canvas` element if the
reloaded theme is the graph's active one) and the browser re-resolves every
`var()` reference downstream — no per-node Python fetch. See
[theme-canon](../../components/themes/theme-canon.md).

## 4. Boundary

Hot-reload is **not**:

- A **safe mechanism for production code** — file watching is `EDITABLE` / `FOLDER` install only ([library-system §2.3](../library-system/library-system-arch.md#23-installtype-enum-haywirecorelibraryinstall_typepy)). Pip-from-wheel installs (`REGULAR`) have no live source path.
- A **module-unloading tool** — The managed path evicts and replaces the module in `sys.modules`, but old class objects held by closures or direct references remain in memory until GC collects them. Restart is the most thorough cleanup.

## 5. Examples

### 5.1 What gets rebuilt when you edit a node class

Edit `barn/haybale-mylib/haybale_mylib/nodes/foo.py`:

```text
1. FileWatcher fires FileChangeEvent
2. BaseRegistry reloads haybale_mylib.nodes.foo
3. @node decorator re-runs → NodeRegistry updates FooNode under registry_key
4. NodeFactory relays the batch to every wrapper subscribed on that registry_key
5. Each wrapper:
   - offers the event to its node via on_class_reloaded() — a macro
     placement absorbs it here and stops (ADR 0038)
   - otherwise marks NODE_HOT_RELOADED and calls build() with no node_info
   - the new class instantiates and runs init(): values, props and store go
6. Each wrapper's edges:
   - mark EDGE_ADAPTERS_RELOADED
   - 4-stage build re-runs against new port objects
   - link() / unlink() based on test result
7. ValidationManager debounce settles
8. FlowAssemblyManager reassembles affected Flows
9. UI re-renders the canvas
```

Total time: typically 100–500ms for a small graph.

### 5.2 What gets rebuilt when you edit an adapter class

```text
1. FileWatcher fires
2. AdapterRegistry updates the adapter class
3. EdgeRegistry: every edge whose chain includes this adapter marks EDGE_ADAPTERS_RELOADED
4. AdapterFactory.create_chain() re-runs for affected edges
5. Each edge's _test() validates the new chain
6. Edges that pass: link() — connection works again
7. Edges that fail: unlink() — connection greys out, error surfaced in UI
8. No node reload, no flow reassembly (unless an edge changes link state)
```

Adapters are cheap to reload — typically under 50ms.

### 5.3 What gets rebuilt when you edit a state class

```text
1. FileWatcher fires
2. LibraryStateRegistry updates the class
3. LibraryStateContainer:
   - For AppState: disable old instance → store new instance → enable
   - For SessionState: per-session disable → per-session new instance → per-session enable
4. No node/edge/Flow rebuild (state is consumed at access time, not capture time)
```

State reload is fast for cheap `on_enable` and slow for expensive ones (hardware scan, cache warming). The author trades reload speed against the cost of preserving stale state.

## 6. Open questions

- **Stale class reference cleanup.** Managed modules are evicted from `sys.modules` before re-import, so the slot is reused. Old class objects held by closures or direct attribute references (`some_obj.cls = OldClass`) are not actively hunted down — they survive until GC. A reference-audit pass after each reload could catch stragglers, but is not implemented.
- **Granular flow reassembly.** Currently any change inside a Flow's reachable set rebuilds the whole Flow. Could rebuild only the affected localized data-flow subtree.
- **State migration hook.** `LibraryState.on_reload(old_instance)` could let authors carry forward expensive-to-rebuild state across class versions. Currently destroyed by design.
- **Hot-reload of editor / panel classes.** New classes are picked up at next render; existing instances don't swap mid-render. Would be useful for live UI development but requires careful slot/binding lifecycle handling.

## Key files

- `src/haywire/core/library/file_watcher.py` — `FileWatcher`, `LibraryFileHandler`
- `src/haywire/core/registry/component.py` — `ComponentRegistry` (the base both registry families share: folder bookkeeping, lifecycle queue, subscribers)
- `src/haywire/core/registry/base.py` — `BaseRegistry` (event dispatcher, customer callbacks, registry subscribers)
- `src/haywire/core/registry/document.py` — `DocumentRegistry` (file-backed components; content hashing, file events → lifecycle events)
- `src/haywire/core/macro/registry.py` — `MacroRegistry` (`.hwm` documents)
- `src/haywire/core/node/node_wrapper.py` — `NodeWrapper.build()` (fresh rebuild) and `on_class_reloaded` consultation
- `src/haywire/core/edge/edge_wrapper.py` — `EdgeWrapper.build()` (4-stage pipeline)
- `src/haywire/core/state/container.py` — `LibraryStateContainer` (disable+enable cycle)
- `src/haywire/ui/themes/registry.py` — `ThemeRegistry` (apply_workbench_theme on reload)
