# New Node wizard: create a node in your own library

## Context

A user who wants a node of their own has no affordance in the studio for making
one. The only path today is Farmhand's `studio_scaffold_component`, which an
agent calls and a person never sees. Its inline stub reports the wrong registry
key (finding 1).

**Outcome:** from the canvas, a user starts from a **Node template** or clones an
existing node, names it, sees the file that will be written, and clicks Create.
The wizard waits for the registry to confirm the node exists, then offers Edit
(the source editor), Place (on the canvas) or Close. From a selected node the
same wizard opens already cloning that node. An agent writing node source through
Farmhand gets the same dependency bookkeeping and the same "did it register"
answer.

**Status: 2026-09-24.** Settled by design interview (21 decisions, below).
Unbuilt. No ADR, by the user's call.

---

## The user story

1. I right-click the canvas and click the new-node icon in the menu's top row.
   The wizard asks whether I start from a template or clone a node, and I search
   a flat list for it.
2. I give it a label. The class name fills in from it and I can change it. Menu,
   tags and description are prefilled from what I picked. I pick the library if
   my project has more than one.
3. I see the path, the registry key, which imports were rewritten, and the full
   source that will be written. Nothing is on disk yet.
4. I click Create. The wizard waits until the node registers, then shows its key
   with Close, Edit and Place. If the file fails to import, it shows the error
   and an Open file button, and the file stays.
5. With one node selected, "Clone to Library…" in its menu (or the toolbar's ⋯)
   opens the wizard at step 2 with that node as the source.
6. As an agent, I read a few nodes, write a new one with
   `studio_write_component_source`, and the result tells me whether it
   registered, what it added to `linked_libraries`, and which pyproject
   declaration share will ask for.

---

## What the walk of the code established

### Promote to Macro is the pattern to follow

[`_promote_flow/`](../../../barn/haybale-graph-editor/haybale_graph_editor/_promote_flow/)
is a `StepFlow` over a pure core pipeline (`plan_promotion` / `write_macro_file`
in [promote.py](../../../packages/haywire-core/src/haywire/core/macro/promote.py)),
three steps, only the last one writes.
[`promotion_targets()`](../../../packages/haywire-core/src/haywire/core/macro/promote.py#L92)
already answers "which libraries can receive a file": editable, registered the
kind's folder, the one under `workspace_root/barn` first. It reads
`MacroRegistry._folder_to_library`, which every `ComponentRegistry` has, so the
same walk works over `NodeRegistry`.

### A node's registry key is its class name

`@node` defaults `registry_id` to `inner_cls.__name__`
([decorator.py:246](../../../packages/haywire-core/src/haywire/core/node/decorator.py#L246)),
so the class name is the key and renaming it later orphans every graph using the
node. Identity is inherited from a decorated parent and overridden by the
child's kwargs, so a class's *resolved* `class_identity` can carry menu and tags
its own decorator never mentions.

### Node source is not portable as written

Node files use relative imports, both at the top
(`from .base_estimator_node import BaseEstimatorNode`) and inside method bodies
(`from ..types.specs import EXEC` inside `init()`,
[switch.py:39](../../../barn/haybale-core/haybale_core/nodes/switch.py#L39)). A
verbatim copy into another library fails to import. Of 42 node files in the
barn, one declares more than one `@node` class
([size_box_node.py](../../../barn/haybale-testing/haybale_testing/nodes/testbed/size_box_node.py),
three).

### No templates exist, and the Farmhand stub is wrong

Builtin ships only framework nodes (error, reroute, Graph-node, macro placement,
Subgraph Input/Output). Farmhand's `_NODE_TEMPLATE` is an untested string in
[authoring.py:35](../../../barn/haybale-studio/haybale_studio/farmhands/authoring.py#L35).

### EXEC and CALLBACK are not in builtin

Both are defined in haybale-core
([specs.py:86](../../../barn/haybale-core/haybale_core/types/specs.py#L86)).
Saved graphs carry the type key per port (`ports/<id>/kwargs/registry_key:
"haybale-core:type:EXEC"`, 7226 occurrences in the repo's own graphs), so moving
the types changes their key and orphans those ports unless an alias exists. A
release `haywire init` project depends on haywire-studio, haybale-studio,
haybale-marketplace and its own library only
([init.py:220](../../../packages/haywire-studio/src/haywire_studio/init.py#L220)).
haybale-core is added under `--dev` alone.

### The two toolbars

The graph editor has no persistent toolbar. `GraphToolBar` is the icon row at
the top of the canvas right-click menu
([graph_context.py:56](../../../barn/haybale-graph-editor/haybale_graph_editor/surfaces/graph_context.py#L56)).
The node toolbar is the floating `SelectionToolbar`; its ⋯ renders the same
`SelectionMenu` panels as the node right-click menu. No last mouse position is
tracked anywhere. The right-click point is `_open_ctx.canvas_pos`
([context_menu.py:366](../../../barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/context_menu.py#L366)),
and it is gone once the menu closes.

### The add-node picker cannot go inside a dialog

`NodeMenuBuilder` builds nested `ui.menu` flyouts, which render under a `Popup`
(QMenu z-6000 < Popup z-7001,
[.insights](../../../.insights/feedback_nicegui_nested_menu_flyouts.md)). Its
search results are a plain list.

### What the registry says, and when

- A new file that fails to import emits **no** lifecycle event.
  `CLASS_RELOAD_FAILED` is emitted on MODIFIED, per key the module already had
  ([base.py:387](../../../packages/haywire-core/src/haywire/core/registry/base.py#L387)).
  A new module has no keys, so its failure reaches only the error ledger,
  enriched with `module_name`.
- `add_registry_subscriber` is registry-to-registry propagation, wired in
  [di/config.py:447](../../../packages/haywire-core/src/haywire/core/di/config.py#L447).
  The consumer hooks are `add_batch_event_subscriber` (lifecycle batches) and
  `ErrorLedger.add_listener`.
- The watcher runs only when `enforce_file_watching or identity.file_watcher`
  ([base.py:101](../../../packages/haywire-core/src/haywire/core/library/base.py#L101)),
  and `@library(file_watcher=)` defaults to False. `haywire init` scaffolds it
  True.
- `linked_libraries` sets a module's hot-reload tracking scopes when it
  registers (`_get_tracking_scopes`,
  [base.py:855](../../../packages/haywire-core/src/haywire/core/registry/base.py#L855)).
  `BaseLibrary._reload_metadata()` refreshes it from `haybale.toml` in place.
  A `.py` that registers before the toml change is seen gets the old scopes.

### Access

Farmhand's source-writing tools are ADMIN
([authoring.py:77](../../../barn/haybale-studio/haybale_studio/farmhands/authoring.py#L77)).
Graph-editor menu panels declare no tier and default to VIEW, Promote to Macro
included (finding 2). ADR 0027: tiers guard against ignorance, and "edit is
already admin at the machine level".

---

## Decisions

| # | Decision |
|---|---|
| 1 | The new node is a **starting point for code**. The wizard writes a `.py` file and the user edits Python next. A metadata-only variant (a subclass under a new name) is not offered. |
| 2 | **Authoring targets**: libraries that are `InstallType.is_editable()`, registered a `nodes/` folder with `NodeRegistry`, and run a file watcher (decision 17). The project library sorts first and is the default; a selector appears only for several targets; none gives a blocking message pointing at `haywire init`. `promotion_targets()` generalizes into `authoring_targets(library_system, registry_cls, workspace_root)`, shared with Promote to Macro. The watcher condition is the node wizard's filter, not the shared function's. |
| 3 | A clone copies the **whole module** when it declares one `@node` class, and **extracts** the class, its decorators and the module's imports when the module declares several. |
| 4 | In an extracted clone, module-level names the class uses that are not imports (helpers, constants, sibling classes) are **imported from the source module**: `from <source module> import _helper, SIZE`. One AST pass, no transitive closure, so no registered sibling class is ever copied. |
| 5 | Every relative import in the copied source, top-level or inside a method, is rewritten to an absolute one against the source package. Libraries the result imports that the target's `linked_libraries` does not list are **unioned in automatically** (the Linked registration rule). The library pyproject is not touched; share's Detect step flags the undeclared import as it does for hand-written code. `haywire.*` imports and same-library clones declare nothing. |
| 6 | A **Node template** is a real registered node class flagged in its identity. "From template" runs the clone pipeline with the template class as the source. Any library may ship templates. |
| 7 | Builtin ships the **Data node** template (FLOAT in, FLOAT out). |
| 8 | EXEC and CALLBACK move to builtin in a **separate later plan** with a `TypeRegistry` key alias. That plan adds the Control, Event and Output templates. The wizard lists whatever is flagged, so it does not change when they land. |
| 9 | The flag is a public field, **`NodeIdentity.template: bool = False`**, following `hidden`, not the `_is_*` framework role markers. `@node` stamps `hidden=True` whenever `template=True`, so every existing hidden filter (add-node menu, search, QUICKREF) applies unchanged. |
| 10 | Clone sources: visible node classes with readable source (`inspect.getsource` succeeds). Excluded: `_is_*` framework role nodes, macros, hidden nodes. Templates are listed only under "from template". A deprecated node may be cloned. |
| 11 | Entry points: an icon on **`GraphToolBar`**, and a **"Clone to Library…"** row on **`SelectionMenu`**, shown when exactly one eligible node is selected. The row appears in the node right-click menu and in the floating toolbar's ⋯. |
| 12 | Step 1 (graph entry only) is one **Source** step: a Template / Clone toggle, a search field and a flat list. Templates group by library, clone sources by menu path. Picking a row advances. No flyouts. The filter logic comes out of `NodeMenuBuilder._update_search_results` rather than being written twice. |
| 13 | The user enters a **Label** and a **Class name**. The class name derives from the label until the user edits it. The file name derives from the class name (`BlurFilter` → `nodes/blur_filter.py`) and is shown read-only. Live refusals: key already registered in the target, file exists, class name not a valid identifier, file stem matching `dev_*` / `*_dev` (which would not register). |
| 14 | Menu (combobox of existing paths plus free text), tags (chips) and description (textarea) are **prefilled from the source's resolved `class_identity`**, templates and clones alike. The clone's label starts as `<source label> Copy`. The rewritten `@node(...)` states all four fields explicitly and drops `registry_id`, `template`, `hidden` and `deprecation_warning`. Behaviour flags are not offered; the user edits them in source. The source's class docstring is copied as written. |
| 15 | The wizard **does not place** the node by itself. The result step's Place button does, as one undoable add: at the right-click point from the graph entry, beside the source node from the node entry. |
| 16 | The **Plan** step is read-only and shows the path, key, copy mode, rewritten imports, free names imported, `linked_libraries` additions, and the **full generated source**. The **Result** step is terminal: success shows the key with **Close · Edit · Place**; failure shows the ledger message and path with **Close · Open file**. Edit publishes `RevealComponentSource`; Open file publishes `RevealSource`, because a key that never registered cannot open by key. |
| 17 | **The watcher triggers registration.** Create subscribes to `NodeRegistry` lifecycle batches (`CLASS_ADDED` or `CLASS_RELOADED` for the expected key means success) and to the error ledger (an entry for the expected module means failure), then writes, then waits with a timeout. The wizard never dispatches a file event itself. |
| 18 | Both entry panels require **ADMIN**, the tier Farmhand's source writes already require. |
| 19 | Layering follows promote. The pure pipeline lives in **`haywire.core.authoring`**: `authoring_targets()`, `plan_node()`, `write_node()`, the registration waiter. The UI lives in **`haybale_graph_editor/_new_node_flow/`** (`_state.py`, `panels.py`, `chrome.py`, `copy.py`). |
| 20 | Farmhand: `studio_scaffold_component(kind="node")` goes through the pipeline with the builtin Data template and reports the observed key. `studio_write_component_source` applies Linked registration before writing and returns the registration outcome. Both return the same result shape. No `clone_node` tool: an agent writes from what it read. |
| 21 | Out of scope: see the last section. |

---

## Architecture

### `authoring_targets()`

`promotion_targets()` moves to `haywire/core/authoring/targets.py` and takes the
registry class:

```python
def authoring_targets(
    library_system, registry_cls: type[ComponentRegistry], workspace_root: Path | None = None
) -> list[AuthoringTarget]: ...
```

`AuthoringTarget` is `PromotionTarget` renamed (`library_id`, `label`, `folder`,
`is_project_library`) plus `is_watched`, read from the library instance. Promote
calls it with `MacroRegistry` and ignores `is_watched`; the node wizard calls it
with `NodeRegistry` and keeps the watched targets. `promotion_targets` stays as
a one-line wrapper only if a caller outside promote still needs the old name;
otherwise it goes.

### `NodeIdentity.template`

A new field beside `search_tags` and `menu`
([identity.py](../../../packages/haywire-core/src/haywire/core/node/identity.py)).
`@node` sets `hidden=True` when `template=True`. `NodeFactory` gains
`list_templates()` (identities with `template=True`, grouped by library) so the
wizard never walks the registry itself. A subclass of a template inherits
`template=True` through the identity merge; that is correct for a template
family and irrelevant for clones, whose decorator drops it (decision 14).

### The builtin Data template

`haywire/barn/builtin/nodes/templates/data_node.py`, registered by builtin's
existing `nodes/` scan. It is the current Farmhand stub made into a teaching
example: absolute imports only, no module-level names besides imports, a
docstring telling the reader what to change. A test holds every template to
that contract (see below), so a template can never produce a clone that imports
helpers from builtin.

### The pipeline: `plan_node()` / `write_node()`

`haywire/core/authoring/node_clone.py`, no NiceGUI.

```python
@dataclass
class NodeFields:
    label: str
    class_name: str
    menu: str
    search_tags: list[str]
    description: str

def plan_node(source_cls: type[BaseNode], fields: NodeFields, target: AuthoringTarget,
              libraries: HaywireLibrarySource) -> NodePlan: ...

def write_node(plan: NodePlan, library: BaseLibrary) -> Path: ...
```

`plan_node` reads the source file and works on its AST:

1. **Mode.** Count `ClassDef`s decorated with a `node(...)` call. One: whole
   module. More: extract.
2. **Extract** (several classes only). The class from its first decorator's
   `lineno` to `end_lineno`, plus every top-level import statement, including
   `from __future__` and `if TYPE_CHECKING:` blocks. Free names: every `Name`
   loaded inside the class subtree, minus names the class binds, minus builtins,
   minus imported names, intersected with the module's top-level bindings
   (`def`, `class`, assignment). They become one
   `from <source module> import …` line.
3. **Rewrite imports.** Every `ImportFrom` with `level > 0`, anywhere in the
   copied text, becomes absolute via `importlib.util.resolve_name` against the
   source module's package.
4. **Rename.** The `ClassDef` name, and `Name` nodes equal to the old class name
   inside the class subtree (`super(Old, self)`, `"Old"` annotations).
5. **Rewrite the decorator.** Replace the class's own `@node(...)` call.
   Keywords the wizard does not own keep their source text
   (`ast.get_source_segment`), so `node_type=NodeType.DATA` survives as written.
   The four field keywords are written from `NodeFields`; `registry_id`,
   `template`, `hidden` and `deprecation_warning` are dropped.
6. **Linked additions.** The top-level modules the result imports, resolved
   through `HaywireLibrarySource` to installed registered libraries, minus the
   target itself, minus names already in its `linked_libraries`, minus
   `haywire`. The same predicate `detect_deps` applies per library, applied here
   to one source text.
7. **Refusals**, carried on the plan the way `PromotionPlan.refusal` is:
   source unreadable, key taken, file exists, invalid class name, `dev_*` stem.

`NodePlan` holds `path`, `registry_key`, `module_name`, `source`, `mode`,
`rewritten_imports`, `free_names`, `linked_additions` and `refusal`. Holding one
changes nothing on disk.

`write_node` does the one mutation, in this order:

1. Union `linked_additions` into `haybale.toml`, then call the library's
   `_reload_metadata()` synchronously, so the identity has the new scopes before
   the watcher sees the `.py`. The union writer comes out of
   `apply_linked_registrations`
   ([dependencies.py:122](../../../packages/haywire-core/src/haywire/core/publishing/pipeline/steps/dependencies.py#L122)),
   which today takes a `SharePipeline`. Share keeps calling it; this is the
   pipeline-free core under it.
2. Write the `.py`, refusing if the file appeared since the plan.

### The registration waiter

`haywire/core/authoring/registration.py`:

```python
class RegistrationWatch:
    """Subscribe before a write, then await the registry's answer for one key."""
    def __init__(self, registry: ComponentRegistry, ledger: ErrorLedger,
                 registry_key: str, module_name: str): ...
    def __enter__(self) -> "RegistrationWatch": ...   # subscribes
    def __exit__(self, *exc) -> None: ...              # unsubscribes
    async def result(self, timeout_s: float) -> RegistrationOutcome: ...
```

`RegistrationOutcome.status` is `"added" | "reloaded" | "failed" | "timeout"`,
with the ledger entries on failure. The first answer wins. Both callbacks fire
on the watcher's thread, so the watch hands the answer to the waiting coroutine
through `loop.call_soon_threadsafe`. The timeout covers the watcher's 0.5 s
debounce with margin.

### The flow: `_new_node_flow/`

`NewNodeFlow(StepFlow)` with steps `source → details → planned → created | failed`.
The node entry constructs it at `details` with the source class set. It depends
on a narrow protocol, as `PromoteFlow` depends on `PromoteSource`, so the tests
drive it without a browser:

```python
class NewNodeHost(Protocol):
    def place(self, registry_key: str) -> None: ...
    def reveal_component(self, registry_key: str) -> None: ...
    def open_file(self, path: Path) -> None: ...
```

- `advance_from_source`: records the picked class.
- `advance_from_details`: `plan_node`, read-only, then `planned`.
- `advance_from_planned`: opens a `RegistrationWatch`, runs `write_node` off the
  event loop, awaits the outcome, then `created` or `failed`. The only mutating
  step.

Click handlers return the coroutine, never schedule it
([.insights](../../../.insights/project_stepper_flows.md)). The generated source
preview is read-only.

### Entry panels and provider verbs

- `NewNodeToolbarPanel` on `GraphToolBar`, `access=ADMIN`, polls an active
  graph. `GraphActions` gains `open_new_node_wizard()`.
  `SessionContextMenuProvider` implements it: it captures `_open_ctx.canvas_pos`
  before the menu closes, so Place has a position after the menu is gone.
- `CloneToLibraryMenuPanel` on `SelectionMenu`, `access=ADMIN`, polls exactly
  one selected node that passes decision 10. `SelectionActions` gains
  `clone_to_library(node_id)`; `SelectionToolbarProvider` delegates it to the
  menu provider, as it does its other verbs. Place goes beside the source node.
- Place emits `NodeCreateRequestEvent` with the captured position, the path
  `create_node_at_click` already takes.

### Farmhand

- `studio_scaffold_component(kind="node", name, label=None, library=None)`:
  `name` is the class name (PascalCase kept, snake_case converted), `label`
  defaults to it. Runs `plan_node` over the builtin Data template, then
  `write_node` inside a `RegistrationWatch`. Other kinds keep the generic stub.
- `studio_write_component_source`: before writing, computes linked additions for
  the new source (decision 5's predicate), unions and refreshes as `write_node`
  does, then writes inside a `RegistrationWatch` (`added` for a new file,
  `reloaded` for an existing one).

Both return:

```
summary, path, library,
registry_key            observed from the lifecycle event, not derived
registration            "added" | "reloaded" | "failed" | "timeout"
errors                  ledger entries when failed
linked_libraries_added  names written to haybale.toml
undeclared_imports      distributions the library pyproject lacks (not written)
help                    "`haywire share` declares undeclared imports."
```

---

## Build order

1. **`authoring_targets()`** (2). Move and generalize; promote calls it. The
   promote tests stay unchanged and green.
2. **`NodeIdentity.template` and the Data template** (6, 7, 9). Field, hidden
   stamp, `NodeFactory.list_templates()`, the builtin template file, the
   template-contract test.
3. **`plan_node`** (3, 4, 5, 13, 14). Pure, tested over fixture modules.
4. **`write_node` and `RegistrationWatch`** (5, 17). Toml union and refresh,
   write order, outcome over a real `NodeRegistry` with a watched temp library.
5. **Farmhand** (20). Scaffold and write over steps 3–4; fix the key report.
6. **`NewNodeFlow`** (12, 13, 15, 16). State machine and panels, tested without a
   browser like `PromoteFlow`.
7. **Entry panels and verbs** (11, 18). Two panels, two provider verbs, Place.
8. **Docs** (below).

Steps 1–4 are core with no UI; 5 is the agent path; 6–7 are the studio.

---

## Test coverage this plan needs

- `authoring_targets`: editable + folder + project-first for both registries;
  `is_watched` reported; promote's existing target tests pass unchanged.
- `template=True` implies hidden: absent from the add-node menu, search and
  QUICKREF, present in `list_templates()`.
- Template contract: every registered template has only absolute imports and no
  module-level names besides imports; `plan_node` over it yields no free names
  and no linked additions; its clone instantiates and passes `on_testrun()`.
- `plan_node` fixtures:
  - single-class module copied whole, relative imports rewritten top-level and
    inside a method;
  - multi-class module extracted, a helper and a constant imported from the
    source module, a sibling `@node` class never copied;
  - a subclass whose menu and tags come from a decorated parent gets them
    explicitly in its rewritten decorator;
  - `super(Old, self)` renamed;
  - `node_type=NodeType.DATA` kept as source text;
  - `template`, `hidden`, `deprecation_warning`, `registry_id` dropped;
  - each refusal of decision 13.
- Linked additions: a clone of a visiongraph node into the project library adds
  `haybale_visiongraph`; a same-library clone and a builtin template add
  nothing; existing entries survive the union.
- Write order: after `write_node`, the new module's tracking scopes include the
  added library (the `.py` registered under the refreshed identity).
- `RegistrationWatch`: `added` on a good file; `failed` with the ledger entry on
  a file whose import raises (no lifecycle event exists for it); `timeout` when
  nothing arrives; `reloaded` on overwrite.
- `NewNodeFlow`: graph entry starts at `source`, node entry at `details`;
  only `advance_from_planned` touches disk; Place, Edit and Open file call the
  host.
- Panels: both gated to ADMIN; the clone row absent for zero, several, or an
  ineligible selection (reroute, Graph-node, placement).
- Farmhand: scaffold reports the key that actually registered; write reports
  linked additions and undeclared imports.
- Gate per [CLAUDE.md](../../../CLAUDE.md). Commit `barn/haybale-testing` before
  the full suite
  ([.insights](../../../.insights/project_docs_test_reverts_barn_testing.md)).

---

## Docs to land with the code

Written in the same commit series as the feature, not before.

**Glossary** (`docs/reference/glossary.md`):
- **Authoring target** (Library & Plugin System): a library a component may be
  written into. Editable, registered the kind's folder; for nodes, also watched.
  Shared by Promote to Macro and the New Node wizard.
- **Node template** (Node Behaviors): a registered node class with
  `template=True`, hidden from the add-node menu, that exists to be cloned. Any
  library may ship templates.
- **"Template": two meanings**, a disambiguation entry. A **Macro template** is
  tracked: every placement follows it. A **Node template** is copied: a clone
  never follows it.
- **Clone** (a node clone): a new node class written into an authoring target
  from an existing class or a template. Aliases to avoid: **duplicate**, which
  is `DuplicateNodeAction`, a canvas copy of a node instance
  ([graph_actions.py:438](../../../packages/haywire-core/src/haywire/core/undo/actions/graph_actions.py#L438)).
- **Builtin library** paragraph: its charter widens from framework primitives to
  also cover authoring starting points (the Data template).
- **`LibraryIdentity`** row: it cites `update_identity_from_toml()`; the method
  is `BaseLibrary._reload_metadata()` (finding 3).

**Reference and canon:**
- [haybale-toml.md:365](../../reference/files/haybale-toml.md): same method-name
  fix.
- Node canon: `template=True`, what a template must satisfy, and how a library
  ships one.
- The `@node` docstring's identity field list gains `template`.
- Farmhand tool docs: the new result fields on scaffold and write.

---

## Findings outside this plan

1. **Farmhand scaffold reports a key that never registers.** It returns
   `f"{lib}:node:{name}"` while the class it writes registers under its class
   name, and `"MyNode".capitalize()` gives `Mynode`. Fixed by decision 20.
2. **Promote to Macro declares no access tier**, so it defaults to VIEW while it
   writes a `.hwm` into a library. It should probably match decision 18. Not
   changed here.
3. **Doc drift:** the glossary and haybale-toml.md cite
   `update_identity_from_toml()`; the code has `_reload_metadata()`. Fixed with
   the docs above.
4. **A release project has no EXEC type** until the user installs haybale-core,
   which the `haywire init` baseline does not include. Plan 8's EXEC move
   resolves it.

---

## Follow-ons

1. **Replace Node**: a `ReplaceNodeAction` the user runs from the node context
   menu, swapping a card for another key while keeping position, props, port
   values and edges by port id. Same shape as `PromoteGroupToMacroAction`.
2. **EXEC and CALLBACK into builtin** with a `TypeRegistry` alias for the
   `haybale-core:type:*` keys, then the Control, Event and Output templates.
3. **`template=` on `studio_scaffold_component`**, once more than one template
   exists.
4. **Promote to Macro's access tier** (finding 2).

## Out of scope

- Replace Node (follow-on 1) and the EXEC move (follow-on 2).
- Duplicate Macro, and cloning any component kind other than a node class.
- Writing library pyproject dependencies; share owns them.
- Automatic placement on the canvas; only the Place button places.
- Undoing the file write or committing to git; git is the source-level undo.
- Editing, renaming or deleting existing nodes; the wizard only creates.
- Creating a library when no authoring target exists.
- Behaviour flags in the wizard.
- Cloning several nodes at once; the node entry needs exactly one.
- A `clone_node` Farmhand tool.
