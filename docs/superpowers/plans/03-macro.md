# Slice 2 — Macro: a Subgraph that lives in its own file

## Context

Slice 1 delivered the **Group**: a Graph-node whose Subgraph lives in the parent
`.haywire` file, serving exactly one card. A **Macro** is the same card over a
Subgraph that lives in **its own file**, is a library component, and can be
placed any number of times in any graph.

> | **Macro** | own file, a library component | any graph | **inlined** at assembly | 2 |
> — [2026-09-14-graph-nodes.md:97](2026-09-14-graph-nodes.md)

**Outcome:** a user picks a macro from the add-node menu, gets a card wired like
any other node, and the graph runs as if the macro's interior had been pasted in.
Saving the macro file updates every placement in every open graph, keeping their
values, labels and surviving edges. A Group can be promoted into a macro in one
action.

**Status — 2026-09-20.** Settled by design interview (21 decisions, below). This
revision supersedes the 2026-09-15 draft, whose two blockers are gone: instant
switching landed in `10500f44`, and `GraphNode._watch_definition()`
([graph_node.py:89-111](packages/haywire-core/src/haywire/barn/builtin/nodes/graph_node.py#L89-L111))
gives `reconcile_interface()` its caller. The draft's "reload fan-out — the real
open surface" turned out to be machinery that already exists once a placement's
registry key is the macro's own (decision 2).

**Built**, except for the UI over steps 7–8: the editing surface and
"Promote to Macro…" landed as core helpers with no call site, so a macro can
be placed and reloaded but not yet made from inside the studio.

---

## The user story

1. A macro is a `.hwm` file in a library's `macros/` folder — a `BaseGraph`
   document holding two boundary nodes and the interior.
2. Macros appear in the add-node menu under `<library>/macros`.
3. Selecting one places a `MacroNode` whose interior is instantiated from the file.
4. Each placement is its own instantiation; two placements never share nodes.
5. Saving the file updates every placement, in place. Removed pins drop their
   edges to the ghost pin and the error ledger reports each one.
6. "Promote to Macro…" on a Group writes the file into an editable library and
   swaps the Group card for a placement, undoably.
7. "Edit Macro…" opens the file as its own document — its own tab, dirty dot,
   Save and undo stack.

---

## What the walk of the code established

Verified against `master` at the time of writing. These are the reasons the
slice is assembly of existing parts rather than new invention.

### The assembly and validation walks need no change

The tree walks never consult the *root* graph's subgraph table; each recurses on
`graph.subgraphs` at whatever level it stands
([flat_view.py:294-317](packages/haywire-core/src/haywire/core/assembly/flat_view.py#L294-L317),
[base.py:288-299](packages/haywire-core/src/haywire/core/graph/base.py#L288-L299)),
and `resolve_definition()` resolves from the graph that owns the node
([graph_node.py:141-153](packages/haywire-core/src/haywire/barn/builtin/nodes/graph_node.py#L141-L153)).
A placement registers its live instantiation in its *owning graph's* table —
where a Group's sits — and every walk finds it. The macro **file** is the
template; each **placement's instantiation** lives in the host tree.

### `instantiate()` already does the per-placement work

[`SubgraphDefinition.instantiate()`](packages/haywire-core/src/haywire/core/graph/subgraph.py#L155-L219)
mints tree-unique node ids and rewrites every edge onto them, recursing through
nested definitions. Its input is the `nodes`/`edges`/`subgraphs` tables that
`BaseGraph.to_dict()` produces — so a macro file **is** a graph document, and
the graph editor loads it unchanged.

### The lifecycle relay is the fan-out

`NodeFactory` relays registry lifecycle events **per registry key** to every
`NodeWrapper` subscribed on that key
([factory.py:88-103](packages/haywire-core/src/haywire/core/node/factory.py#L88-L103),
[node_wrapper.py:150](packages/haywire-core/src/haywire/core/node/node_wrapper.py#L150)),
across every open graph, since all graphs share one factory. If a placement's
`registry_key` is `lib:macro:Blur`, a reload of that key reaches every placement
with no new machinery. This is decision 2, and the whole reason the previous
draft's open surface closed.

### But the generic rebuild discards state

On `NODE_HOT_RELOADED` the validator calls `node_wrapper.build()` with no
`node_info` ([validation.py:265-268](packages/haywire-core/src/haywire/core/graph/validation.py#L265-L268))
→ fresh `init()`. Port values, `props` (the label) and the **store** are gone;
only position and edges survive (edges rebind by port id —
[test_edges.py:931](tests/core/test_graph/test_edges.py#L931)). That is
deliberate: `_initialize_from_dict` restores the *serialized* port set without
calling `init()` ([data.py:784-807](packages/haywire-core/src/haywire/core/node/data.py#L784-L807)),
so carrying state across a class reload would hide an author's new ports. A
placement therefore must not take the generic rebuild (decision 7).

### The watcher is suffix-agnostic

`_get_matching_registries` routes *every* file under a claimed folder
([file_watcher.py:106-131](packages/haywire-core/src/haywire/core/library/file_watcher.py#L106-L131));
the `.py` filter is `BaseRegistry.event_dispatcher`'s own
([base.py:375](packages/haywire-core/src/haywire/core/registry/base.py#L375)).
A document registry receives `.hwm` events with no watcher change. A studio save
is an atomic write ([base.py:1127](packages/haywire-core/src/haywire/core/graph/base.py#L1127)),
which the watcher already classifies as MODIFIED.

### `BaseRegistry` is module-centric end to end

Storage is `Dict[str, type[T]]` with `T` bound to `RegisteredClass`; bookkeeping
keys on `cls.__module__`; reload is `sys.modules`/`importlib`/`DependencyGraph`;
rollback snapshots `sys.modules`. What consumers touch is thin: `add_folder` /
`remove_folder` (library), `event_dispatcher` (watcher), `add_batch_event_subscriber`
with `LifeCycleEvent` batches (factory), `get` / `has` / `list_names` /
`list_visible_names` / `get_node_lastevent`. That split is decision 3.

### Kind-generic consumers read `.class_identity` off `get()`

Docs extraction ([extract.py:142-154](packages/haywire-studio/src/haywire_studio/packaging/docs/extract.py#L142-L154))
and the farmhand helpers ([_helpers.py:27-28](barn/haybale-studio/haybale_studio/farmhands/_helpers.py#L27-L28))
do `registry.list_names()` → `registry.get(key)` → `.class_identity`. Whatever
the macro registry hands back must satisfy the `RegisteredClass` Protocol
([base.py:56-73](packages/haywire-core/src/haywire/core/registry/base.py#L56-L73)).
That is decision 4.

### Smaller facts that shaped a decision

- `NodeMenuBuilder` is constructed per context-menu open
  ([context.py:163](barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/graph/context.py#L163));
  its `_menu_cache` lives one draw. No invalidation is needed on reload.
- A `Fence` is a grouping boundary between undo groups
  ([history_manager.py:20-35](packages/haywire-core/src/haywire/core/undo/history_manager.py#L20-L35));
  it does not block undo. The draft's M5 assumed it did.
- Subgraph containment (`validate_subgraph_contents`,
  [structural_validator.py:337-395](packages/haywire-core/src/haywire/core/validation/structural_validator.py#L337-L395))
  runs in one place: host assembly ([flow_assembly_manager.py:208](packages/haywire-core/src/haywire/core/assembly/flow_assembly_manager.py#L208)).
  A macro document open on its own is never assembled, so it never runs there.
- An edge whose pin vanished fails formal validation with "Ports not found" and
  `.log()`s into the ledger with `edge_id`/`graph_id`
  ([edge_wrapper.py:690-730](packages/haywire-core/src/haywire/core/edge/edge_wrapper.py#L690-L730)).
  The cross-graph report the draft asked for already exists.
- `descend_into` duck-types on `resolve_definition`
  ([graph_editor.py:661-688](barn/haybale-graph-editor/haybale_graph_editor/editors/graph_editor.py#L661-L688))
  and there is no read-only editor mode anywhere.
- `InstallType.is_editable()` ([install_type.py:20-29](packages/haywire-core/src/haywire/core/library/install_type.py#L20-L29))
  is the core gate for "may this library's source be edited in place".
- Every way a node enters a graph — menu, paste, Farmhand, file load — goes
  through `create_node_wrapper → build()`, and `post_init` runs *before*
  structural validation ([node_wrapper.py:273-278](packages/haywire-core/src/haywire/core/node/node_wrapper.py#L273-L278)).
  A refusal that must precede instantiation lives in the node, not the validator.
- `NodeWrapper._rebuild()` ([node_wrapper.py:243](packages/haywire-core/src/haywire/core/node/node_wrapper.py#L243))
  carries state over, then marks `NODE_HOT_RELOADED`, which discards it again.
  It has no callers.

---

## Decisions

| # | Decision |
|---|---|
| 1 | Macro files arrive from outside the studio **or** through **"Promote to Macro…"** on a Group. No "New Macro" from scratch in this slice. |
| 2 | A macro **is a node kind**. A placement's `NodeWrapper.registry_key` is the macro's own key `lib:macro:Name`; `NodeFactory.get_node()` returns `MacroNode` for it; the wrapper's per-key subscription is the reload fan-out. |
| 3 | Extract the registry contract into a base: `HotReloadRegistry` ← **`ComponentRegistry`** (folder bookkeeping, lifecycle queue, both subscriber lists, `get/has/list_*`, last-event lookup) ← `BaseRegistry` (class-backed, behaviour unchanged) and **`DocumentRegistry`** (file-backed) ← `MacroRegistry`. `BaseLibrary`'s registry typing and the watcher's target type widen to the base. Function (Slice 3) is the second `DocumentRegistry`. |
| 4 | `MacroRegistry.get(key)` returns a **Macro template**: the parsed document, its path, a content hash, a per-macro `class_identity: NodeIdentity` (`registry_key`, label = filestem, `description` = `meta.description`, `menu` per decision 6, a macro icon) and `class_library`. It satisfies `RegisteredClass`, so kind-generic consumers never learn it is not a class. `NodeFactory` takes both registries and dispatches on the key's kind segment. |
| 5 | A macro file carries the extension **`.hwm`**. Function gets a sibling extension later. |
| 6 | Menu path is fixed: **`<library id>/macros`**. |
| 7 | A template reload is **absorbed in place**, never rebuilt. `BaseNode.on_class_reloaded(event) -> bool` (default `False`); `NodeWrapper._on_node_lifecycle_event` consults it first on a successful event and returns when it answers `True`. `MacroNode` swaps the definition (remove old from the host table, instantiate the new template under the same key) and calls `reconcile_interface()` — the path a Group's interior edit already takes. Values, label, and edges on surviving pins are untouched by construction. |
| 8 | A placement's **interior is never serialized** into the host. `SubgraphDefinition.template_key: str | None` marks a template-instantiated definition; `BaseGraph.to_dict` skips marked entries. The definition's **key is derived from the card's node id** (`MacroNode.subgraph_key` returns `macro_<node_id>` and never reads the store), so two cards cannot share an interior and the store carries nothing. On `post_init`: if the host table holds the derived key, remove it; instantiate from the template; bind; reconcile. |
| 9 | The **watcher** is the only reload trigger. A studio save arrives as MODIFIED after the 0.5 s debounce. An unwatched library does not propagate — same rule as `.py`. |
| 10 | A reload is **not an undo subject**: not an action, no fence. The interface is owned by the template, never by an action, so undo past a reload cannot resurrect a pin. |
| 11 | Lost connections are reported by the **edge itself**: each orphaned edge lands in the error ledger via formal validation. No new reporting. |
| 12 | Descending into a placement is **refused** and opens the macro document instead. Look-inside waits for a read-only editor mode. |
| 13 | Containment (one Input, one Output, no EVENT/OUTPUT) is validated **at registry load**, against node classes via `NodeRegistry`, without instantiating. A failing file emits `RELOAD_FAILED` on its key: ledger entry pointing at the document, every placement takes the existing warning-event path (badge, previous interior kept). |
| 14 | **No recursion**, refused at **bind time** in `MacroNode`: the `template_key`s walking up the host chain (including an open macro document's own key) intersected with the macro keys transitively reachable from the added key (read off the registry's templates). Non-empty → the card lands in structural error naming the cycle, before any save. The registry runs the same closure on load as the backstop for files edited outside the studio. |
| 15 | **Promote to Macro…** = write `<lib>/macros/<Name>.hwm` + `macro_registry.register_file(path)` synchronously (the watcher's later CREATED is a no-op by content hash) + **one undoable action group**: remove the Group card and its definition, create the placement at the same position; edges re-attach by pin id. Undo restores the Group; the file stays. |
| 16 | Promotion targets: every library with `InstallType.is_editable()` that registered a `macros/` folder with `MacroRegistry`. Default (and sole choice when alone) is the one under `workspace_root/barn` — a path test the editor makes itself, not an import from haybale-marketplace. |
| 17 | A macro's filestem matches `^[A-Za-z][A-Za-z0-9_-]*$`. Validated live in the promote dialog and at scan (a non-conforming file is skipped with a ledger warning). Same stem twice in one library → duplicate-key `ValueError`; across libraries → distinct keys, `get_alternate_node_registry_keys` applies. A rename is DELETE+CREATE, as for a class. |
| 18 | "Edit Macro…" on a macro from a non-editable library is **refused with the reason**. Component Docs still work. |
| 19 | `haywire docs` routes `"macro"` through `_node_record` — a macro is documented like a node, by its interface. `describe_component` works through decision 4. |
| 20 | `MacroNode` is a subclass of `GraphNode` differing in five places: key derivation (8), definition instantiation (8), label write-back (a no-op — `_on_label_changed` becomes Group-only), `on_class_reloaded` (7), the cycle check (14). `display_label` needs no override: `props.label or identity.label` already reads the template's identity. |
| 21 | Folded in: delete the dead `NodeWrapper._rebuild()`; the two false statements of the previous draft are corrected here. |

---

## Architecture

### The registries

```
HotReloadRegistry            event_dispatcher(FileChangeEvent)      — stays one method;
   │                                                                   _HaybaleTomlWatcher needs it thin
   └── ComponentRegistry     add_folder/remove_folder (abstract), _folder_to_library,
        │                    _lifecycle_event_queue, _regkey_to_last_lifecycle_event,
        │                    _registry_subscribers, _batch_event_subscribers,
        │                    _queue_lifecycle_event, _notify_*, get/has/list_names/
        │                    list_visible_names, get_lastevent
        ├── BaseRegistry     FolderScanMixin + module reload + rollback (unchanged)
        └── DocumentRegistry glob one suffix, parse on load, content hash,
             │               CREATED/MODIFIED/DELETED → ADDED/RELOADED/REMOVED,
             │               parse failure → RELOAD_FAILED (key kept, error attached)
             └── MacroRegistry  .hwm; validates containment (13) and cycles (14);
                                builds the Macro template (4)
```

A pure move of the plumbing; the registry test suite is the safety net.
`kind_registry_map()` gains `"macro": MacroRegistry`, `KIND_FOLDERS["macro"] =
"macros"`, `_KIND_TO_AREA["macro"] = "macros"`
([kinds.py](packages/haywire-core/src/haywire/core/library/kinds.py)).
`_REGISTRY_SCAN_PRIORITY["MacroRegistry"] = 75` — after `NodeRegistry` (70),
because containment reads node classes. `haywire init`'s scaffold gains a
`macros/` folder and its `add_folder_to_registry` line
([init.py](packages/haywire-studio/src/haywire_studio/init.py)).

The lifecycle event names stay `CLASS_*`; a note on the enum says a document
registry emits them for documents.

### The template and the factory

`NodeFactory(node_registry, macro_registry)`. `get_node`, `get_node_lastevent`,
`_build_node_info`, `get_menu_structure`, `search_nodes`, `list_all_nodes`
dispatch on the key's kind segment or iterate both. `get_node("lib:macro:X")`
returns `MacroNode` when a template is present and takes the error-node path
otherwise — so a graph using a macro from an absent library loads its placement
as the error node, built from the same serialized `ports` block, exactly as any
missing node does. `MacroNode` fetches its template through the factory by
`wrapper.registry_key`.

`extract.py`'s `_record_from_class` receives a template for `"macro"`; the
`kind in ("node", "macro")` branch instantiates it in the throwaway graph.

### The file

A `.hwm` is `BaseGraph.to_dict()` output — `format_version`, `meta`, `nodes`,
`edges`, `variables`, `props`, `subgraphs` — minus `key`. The graph editor
opens it as an ordinary document. Its `meta.description` reaches the template
identity; its `meta.label` keeps its no-navigation role (M3 of the previous
draft stands). Prehydration/format bumps apply as to any graph file.

### `MacroNode`

```python
@node(label="Macro", hidden=True, is_mutable=True, _is_macro_node=True, ...)
class MacroNode(GraphNode):
    @property
    def subgraph_key(self) -> str:            # 8 — derived, never stored
        return f"macro_{self.node_id}"

    def post_init(self) -> None:
        self._refuse_if_cyclic()               # 14 — before any instantiation
        self._instantiate_from_template()      # 8 — remove stale, instantiate, mark template_key
        super().post_init()                    # reconcile + watch definition

    def _on_label_changed(self, *_): pass      # 20 — Group-only write-back

    def on_class_reloaded(self, event) -> bool:  # 7
        self._instantiate_from_template()
        self.reconcile_interface()
        return True
```

`_instantiate_from_template`: `host = self.wrapper.graph`; if
`host.get_subgraph(key)` exists, `host.remove_subgraph(key)`; create
`SubgraphDefinition(key, label=template.label)`, set `definition.template_key`,
`host.add_subgraph(definition)`, `definition.instantiate(nodes, edges, subgraphs)`
from the template's tables.

### Serialization

`BaseGraph.to_dict` skips `subgraphs` entries whose `template_key` is set. The
placement serializes as any node: `registry_key`, position, `node_data` with the
mirrored `ports` (values), `props`, an empty-of-key `store`. Load restores the
pins from the file, `post_init` instantiates and reconciles them against the
live template — the load path a Group already takes.

### Reload

```
save .hwm ──watcher──▶ MacroRegistry.event_dispatcher(MODIFIED)
   parse → hash unchanged? → done
   validate containment (13), cycles (14) → RELOAD_FAILED on failure
   replace template → queue RELOADED(key, affected_class=MacroNode)
   ──batch──▶ NodeFactory ──per key──▶ every NodeWrapper on that key
      _on_node_lifecycle_event: success → node.on_class_reloaded(event) → True
         MacroNode: swap definition, reconcile_interface()
            rejig → validation → redraw, host goes dirty
            pin gone → edge unlinked → ghost pin + ledger entry (11)
```

No fence, no action (10). The `MacroNode` that answers `True` skips the
`NODE_HOT_RELOADED` rebuild entirely.

### Editing surface

- **Edit Macro…** — from the placement's context menu, the add-node menu's
  right-click (`ctx.active_component`), the library overview row, and ledger
  navigation. All resolve to "open the component's source", which for a macro
  key is its document. Refused with a reason for a non-editable library (18).
- **Descend** on a placement → Edit Macro… (12).
- **Promote to Macro…** — a stepper per `.insights/project_stepper_flows.md`:
  name (17, live validation, sanitized suggestion) + target library (16) →
  write/register/swap (15). Only the last step writes.
- The macro document's own tab is named from the file stem
  (`GraphEntry.display_name`). It is a root graph with no EVENT node; Run finds
  nothing to assemble.

---

## Build order

1. **Registry base extraction** (3). `ComponentRegistry`; retype `BaseLibrary`
   and the watcher. No behaviour change; full registry suite green.
2. **`DocumentRegistry` + `MacroRegistry`** (4, 5, 13, 14-backstop, 17).
   Kind maps, scan priority, scaffold folder. Containment and cycle checks over
   dicts. Template with `class_identity`.
3. **`NodeFactory` over both registries** (2, 4). Menu (6), search, docs (19).
4. **`_on_label_changed` Group-only; `on_class_reloaded` hook; delete
   `_rebuild()`** (7, 20, 21). Land the hook with a test that `BaseNode`'s
   default still rebuilds.
5. **`MacroNode`** (8, 14-bind, 20). Derived key, `template_key` marker,
   `to_dict` skip, instantiate-on-`post_init`, cycle refusal.
6. **Reload end-to-end** (7, 9, 10, 11). Two placements in two graphs, one save.
7. **Editing surface** (12, 18) — descend redirect, Edit Macro…, refusal.
8. **Promote to Macro…** (1, 15, 16, 17). Stepper, synchronous register,
   undoable swap.
9. **Docs** (19) — see below. Plus the `macros/` folder and its registration in
   `haybale-example` and `haybale-visiongraph`, and the `haywire init` scaffold
   creating `macros/` (a `.gitkeep`, not an `__init__.py` — a macro is a
   document, not a module).

Steps 1–3 are registry work with no node behaviour; 4–6 are the feature;
7–8 are UI.

---

## Test coverage this slice needs

- Registry extraction: existing registry suite unchanged; a `DocumentRegistry`
  fake receives CREATED/MODIFIED/DELETED and emits ADDED/RELOADED/REMOVED;
  unchanged content on MODIFIED emits nothing.
- Two placements of one macro in one graph assemble and run independently;
  each definition resolves its own card (finding 3 of the previous draft).
- Paste of a placement into the same graph yields two interiors (8).
- Renaming one placement leaves the others and the file untouched (20).
- Round-trip: host file carries no interior; load rebuilds it; pins reconcile.
- Absent library → placement loads as the error node with its pins.
- Reload: values, label and surviving edges kept; a removed pin drops its
  edges to the ghost pin and the ledger holds one entry per edge (7, 11);
  undo history untouched (10).
- Reload failure (containment, cycle, parse): `RELOAD_FAILED`, placements
  badge, previous interior kept (13).
- Cycle at bind time: A in A, B in A where B → A; refused on the card the user
  placed (14).
- `BaseNode.on_class_reloaded` default → generic rebuild still happens (7).
- Promote: file written, key resolves immediately, card swapped, edges
  re-attached; undo restores the Group and leaves the file (15). Watcher's
  CREATED after the synchronous register is a no-op.
- Filestem rule (17): dialog rejects, scan skips with a ledger warning.
- `haywire docs --all` emits a page per macro with its interface (19).
- Gate per [CLAUDE.md](CLAUDE.md); commit `barn/haybale-testing` before the
  full suite ([.insights](.insights/project_docs_test_reverts_barn_testing.md)).

---

## Docs to land with the code

**Landed.** Written in the same commit series as the feature, not before.

Two corrections found while writing them, both in
`architecture/hot-reload/hot-reload-arch.md`: its §3.2 described a
**recipe-based rebuild** (`serialize_recipe`/`build_from_recipe`) that does not
exist — neither symbol has a caller anywhere — and claimed "recipes are how user
data survives reload", which is the opposite of what happens. Rewritten to what
the code does, per the finding below. The file-watcher fact was already
documented correctly at §2.2.

**Glossary** (`docs/reference/glossary.md`, Encapsulation section):
- **Macro** — revise: *is a node kind*; a placement's registry key is the
  macro's own; the factory, the add-node menu and the hot-reload relay treat it
  like any node.
- **Macro template** — the registry's entry for one file: parsed document,
  path, per-macro identity. Three things: the file on disk, the template in the
  registry, each placement's live `SubgraphDefinition`.
- **Placement** — one card standing for a macro in a host graph; owns its own
  interior, keyed by its node id.
- **`.hwm`** — the macro file: a graph document by another suffix.
- **Promote to Macro** — the Group → Macro action.
- **Document registry** — a `ComponentRegistry` over files rather than classes
  (Library & Plugin System section).

**ADRs** (`docs/adr/`):
- **0037 — Macros are node-kind components.** Decisions 2, 3, 4, 5: a document
  registered under the class contract, keyed like a node. Hard to reverse (file
  format, every consumer), surprising, and the `MacroNode`-plus-store-reference
  alternative was real.
- **0038 — A placement's interior is runtime state.** Decisions 7, 8, 10: never
  serialized, keyed by the card's node id, reloads absorbed rather than rebuilt.
  Same three tests.

**Architecture/reference facts** (found only in code this session):
- Hot reload rebuilds a node fresh: values, props and store are discarded;
  edges rebind by port id. (`docs/architecture` libraries/hot-reload page.)
- Subgraph containment is checked only at host assembly. (Encapsulation page.)
- An undo `Fence` groups actions; it does not block undo. (Undo page.)
- The file watcher routes every file under a claimed folder; the `.py` filter
  is `BaseRegistry`'s. (Libraries page.)

---

## Follow-ons

In order of how many decisions above deferred to them:

1. **Read-only graph editor mode.** Look inside a placement's running interior
   (decision 12, and decision 10 of the parent plan); view a macro from an
   installed library (18). Gates every mutating path; the auth work's gated
   surfaces are the nearest precedent.
2. **Fork an installed macro into the project** (18) — needs the read-only mode
   or a save-elsewhere document state, and the copy-with-dependencies story.
3. **Live containment in the macro document** (13) — waits on a UI home for
   graph-level structural errors. **Hide EVENT/OUTPUT from the add menu** in a
   macro document — waits on `NodeMenuBuilder` knowing its container.
4. **New Macro from scratch** (1); **folder-derived menu paths** (6) — the
   latter is a compatible extension of the fixed path.
5. **Macro rename re-pointing placements** — `haywire rename`'s JSON-aware
   patching (17).
6. **Value-preserving hot reload for ordinary nodes**, and the latent Group
   orphaning when `graph_node.py` itself is hot-reloaded (both from the Q7 walk).

## Out of scope

Marketplace publishing and versioning of macros; Farmhand tools for macros
beyond `describe_component`; Function (Slice 3); recursion (Functions only).
