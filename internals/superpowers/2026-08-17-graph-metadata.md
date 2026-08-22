# Graph identity, metadata + file-format migration — implementation plan

**Status:** ready to build · **Settled:** 2026-08-17, revised 2026-08-22
(identity model, `meta` bag, pre-hydration)

Closes three gaps at once:

1. **Identity.** `graph_id` has inconsistent lifecycle management. It is set once
   at construction from two *different* schemes (`__unsaved_N__` for new graphs,
   `path.stem` for opened ones), never updated when the graph is saved-as or
   renamed, and overwritten from the file on load — so a copied graph claims its
   ancestor's id.
2. **Metadata.** `BaseGraph` carries metadata fields that round-trip through JSON
   but that nothing writes and no UI exposes. `created_at` was never stamped;
   `name` was set inconsistently and read by nothing but one info row.
3. **Format churn.** The `.haywire` format has no version marker and no upgrade
   path, so every structural change either breaks existing files or forces
   hand-migration. The first two gaps change that format — Task 9 makes this and
   every future change survivable.

Vocabulary for everything below is canon in
[reference/glossary.md](../../docs/reference/glossary.md).

---

## The two-identity model

The core insight of the 2026-08-21 revision: **"which graph?" is two different
questions**, and the old design tried to answer them with one drifting field.

| Field | Question | Lifetime | Owner |
|---|---|---|---|
| `graph_id` | *which loaded instance?* | one process, one load | `BaseGraph` (haywire-core) |
| `binding_id` | *which tab, across restarts?* | as long as the file path | `GraphEntry` (haybale-haystack) |

Each is written by exactly one rule, and **neither ever needs to be kept in sync
with the other**. That is what removes the lifecycle problem — not a better sync
discipline, but the removal of any need for one.

There is deliberately **no persisted document identity** — nothing today needs
one.

### `graph_id` — transient instance identity

A `uuid4` minted in `BaseGraph.__init__`, **never serialized**, never reassigned.
Two tabs opened on the same file get two different `graph_id`s, which is correct:
they are two live instances.

It has no lifecycle to manage because it is written once and never again. Every
path that used to be a drift site (`_save_entry`'s rekey, `rename_graph`,
`load_from_dict`) simply stops touching it.

This also **fixes error navigation**. `RevealGraphInstance` compares
`error.graph_id` against `graph.graph_id`
([graph_editor.py:135](../../barn/haybale-graph-editor/haybale_graph_editor/editors/graph_editor.py#L135)),
and errors are stamped from the live graph at raise time
([node_wrapper.py:254](../../packages/haywire-core/src/haywire/core/node/node_wrapper.py#L254)
and 7 sibling sites). Under a path-valued `graph_id`, two entries backed by the
same file produce ambiguous locators. Under a per-instance uuid the answer is
unique. `error_navigation.py`'s docstring already states the intent — "each open
tab in this session self-matches against its own live `BaseGraph.graph_id`" — the
type was simply wrong.

### `binding_id` — persistent tab identity

Stays a computed property on `GraphEntry`, but its unsaved branch changes:

```python
@property
def binding_id(self) -> str:
    return str(self.path) if self.path is not None else self.graph.graph_id
```

`str(path)` for saved graphs is **required, not incidental**: the workspace
snapshot persists `binding_id`
([slot.py:119-120](../../packages/haywire-core/src/haywire/ui/app/slot.py#L119-L120))
and reads it back to restore tabs on the next launch
([slot.py:170](../../packages/haywire-core/src/haywire/ui/app/slot.py#L170)). A
transient uuid there would resolve to nothing after a restart and every graph tab
would silently vanish.

The unsaved branch has no such constraint — an untitled graph has no file, so no
restart can restore it regardless. That is precisely why `graph_id` can serve
there, and why `_unsaved_id` / the `new_counter`-as-identity scheme can go.

That is a correctness gain, not just a simplification:
`HaystackSettings.new_counter` is a *persisted setting*, so two projects or a
settings reset can collide two live entries onto one key. A uuid cannot.

---

## Field model

**Editable — a `GraphSettings` bag at `graph.meta`, serialized under `"meta"`:**

| Field | Default | Notes |
|---|---|---|
| `label` | `""` | free-text title, no navigation role |
| `description` | `""` | |
| `author` | `""` | blank until typed |
| `version` | `"1.0.0"` | |

A settings bag rather than four plain attributes: the settings framework already
owns editing (`render_settings` draws the whole bag), serialization, and change
propagation. Task 6 shrinks to two lines because of it.

**Read-only — plain attributes, persisted at the top level of the file:**

| Field | Written when | Written by |
|---|---|---|
| `filestem` | save **and load** | stamped from the real path, never trusted from the file |
| `created_at` | once, at construction | `BaseGraph.__init__` |
| `modified_at` | every save | `save_to_file` |

These stay **out** of the bag deliberately. They are framework-written with no
setter, and a generic bag renderer draws every field as editable — putting them
in `meta` would mean fighting the renderer to make three rows read-only.

### `filestem` is derived on load, not read from the file

A file's stem is a fact about the *file*, so trusting a copy stored inside it is
the same category of lie as the old persisted `graph_id` — it goes stale the
moment the file is renamed or copied.

This is not hypothetical. Every existing graph already carries a wrong value:

| File | stored `name` |
|---|---|
| `10x200nodes.haywire` | `"Untitled 6"` |
| `empty.haywire` | `"Untitled 9"` |
| `settings.haywire` | `"Untitled 11"` |
| `webcam.haywire` / `loop.haywire` / `oakNwebCam.haywire` | `"Untitled 1"` (all three) |

`name` was stamped at creation and never updated on save — gap #2 from this
plan's intro, visible as data. A straight `name` → `filestem` rename would
propagate that garbage under a field name that promises otherwise.

So: `load_from_file` stamps `self.filestem = Path(filepath).stem` **after**
`load_from_dict` returns, and `save_to_file` stamps it before serializing.
`to_dict` still emits it — useful for a graph detached from its path (pasted into
a bug report) — but no load path ever trusts it.

**Runtime only — never serialized, no setter:**

| Field | Value |
|---|---|
| `graph_id` | `uuid4`, minted in `__init__` |
| `binding_id` | `str(path)` when saved, `graph.graph_id` when not — computed on `GraphEntry` |

`graph_id` keeps its name deliberately. `binding_id` is a haystack/studio concept
(the key a container is filed under in `GraphAppState`) and `BaseGraph` lives in
haywire-core, which must not be named after a studio-layer registry.

### Metadata edits do not dirty the graph

A `meta` write does **not** set `entry.unsaved`, matching `graph.props` today:
`HaystackState._on_entry_validation` only marks unsaved when
`result.nodes or result.edges` changed
([haystack_state.py:181](../../barn/haybale-haystack/haybale_haystack/state/haystack_state.py#L181)),
and a settings write touches neither.

The consequence is real and accepted: a metadata edit made and never followed by
a structural change is lost on close, with no prompt. Settings behave this way
already; metadata is not being made an exception in either direction.

---

## Task 1 — Identity on `BaseGraph`

`packages/haywire-core/src/haywire/core/graph/base.py`

1. **Constructor** (line ~88). Drop the `graph_id` parameter entirely — an
   instance id supplied from outside is exactly the drift this plan removes.

   ```python
   def __init__(self, name: str, validation_delay_ms: float = 50.0, ...):
       self.graph_id: str = str(uuid.uuid4())
   ```

   `self.name = name or f"Graph_{graph_id}"` (line 108) loses its fallback —
   a uuid is useless as a display name. Use `name or "Untitled"`.

   Four non-test call sites pass a `graph_id` and must drop it:
   - [haystack_state.py:202](../../barn/haybale-haystack/haybale_haystack/state/haystack_state.py#L202) (see Task 2)
   - [extract.py:140](../../packages/haywire-studio/src/haywire_studio/packaging/docs/extract.py#L140) — `graph_id="docs_gen"`
   - [catalog.py:264](../../barn/haybale-studio/haybale_studio/farmhands/catalog.py#L264) — `graph_id="describe"`
   - [authoring.py:235](../../barn/haybale-studio/haybale_studio/farmhands/authoring.py#L235) — positional `"farmhand_verify"`

   The last three are throwaway graphs built for introspection; they only need
   the `name`. Grep tests for `BaseGraph(` too — it is a wide but mechanical fix.

2. Also in `__init__`: stamp `self.created_at = datetime.now().isoformat()`
   (currently never written — it stays `None` for the lifetime of every graph).
   The four editable fields move to the `meta` bag (Task 1b); `self.description`,
   `self.version` and `self.author` (lines 116-118) are **deleted** as plain
   attributes.

3. `to_dict` (line ~904): **drop `graph_id`**; add `filestem` and
   `"meta": self.meta.to_dict()`. Keep `created_at`, `modified_at`. Remove
   `description`, `version`, `author` — they now live inside `meta`.

4. `load_from_dict` (line ~931): call `prehydrate(data)` as the **first**
   statement (Task 9), so everything below only ever sees current-shape data and
   never grows an `if "old_key" in data` branch.

   Then **stop reading `graph_id`** (line 933) — it is a runtime instance id, and
   a file that records one lies the moment it is copied *or* opened twice.
   **Do not read `filestem` either** — see step 6. Restore the bag beside the
   existing `props` restore (line ~948):

   ```python
   self.meta.reset_all()
   self.meta.from_dict(data.get("meta", {}))
   ```

   `reset_all()` first, for the same reason `props` does it: `load_from_dict` may
   reuse a live graph whose bag still carries the previous graph's values.
   Ordering relative to nodes does not matter for `meta` (unlike `props`, it has
   no node-side mirrors), but keeping the two restores adjacent is clearer.

5. `save_to_file` (line ~1107), alongside the existing `modified_at` stamp, set
   `self.filestem = Path(filepath).stem`.

   Order matters: it must be set **before** `to_dict()` is called at line ~1133,
   or the write persists the previous save's stem.

6. `load_from_file` (line ~1156): after `load_from_dict` returns successfully,
   stamp `self.filestem = Path(filepath).stem`.

   This is the load half of the "derived, never trusted" rule above. Without it,
   every existing fixture loads with `filestem="Untitled N"` — the stale value
   `name` has carried since creation.

7. `__str__` (line ~1091) interpolates `self.graph_id` into a human-readable
   repr. A raw uuid there is noise — prefer `self.name` plus a short prefix
   (`self.graph_id[:8]`) so log lines stay greppable.

**Unsaved graphs need a `filestem` too.** Neither stamp fires before the first
save, so `__init__` seeds it from the constructor's `name` (the `"Untitled N"`
haystack passes). That value is honest *only* while `path is None` — which is
exactly when it is the right thing to show in a tab.

---

## Task 1b — The `meta` settings bag

New: `packages/haywire-core/src/haywire/core/graph/metadata.py`, mirroring
[properties.py](../../packages/haywire-core/src/haywire/core/graph/properties.py)
(which defines `GraphProperties`, the `graph.props` bag).

```python
class GraphMetadata(GraphSettings):
    """Document metadata for a graph, available as ``graph.meta``."""

    label = setting[STR]("", label="Label", order=10)
    description = setting[STR]("", label="Description", order=20)
    author = setting[STR]("", label="Author", order=30)
    version = setting[STR]("1.0.0", label="Version", order=40)
```

Construct it in `BaseGraph.__init__` next to `props`
([base.py:139-140](../../packages/haywire-core/src/haywire/core/graph/base.py#L139-L140)):

```python
self.meta: GraphMetadata = GraphMetadata(registry=settings_registry, graph=self)
self.meta._subscribe_settings()
```

Two hand-wired seams must learn about the second bag. Graphs have **no**
`_settings_bags` auto-discovery — unlike nodes, every graph bag is wired
explicitly, so neither of these updates itself:

- **`settings_bag_for`**
  ([base.py:870-881](../../packages/haywire-core/src/haywire/core/graph/base.py#L870-L881))
  is THE lookup seam for graph mirrors (a node bag's `graph(src=...)` resolves
  through it) and currently hardcodes `self.props`. It must check both bags. Its
  own docstring anticipates this: *"One framework bag today; a future
  registration path for library graph bags changes only this method."*
- **`cleanup`** ([base.py:888](../../packages/haywire-core/src/haywire/core/graph/base.py#L888))
  releases only `self.props`. Without a matching `self.meta.cleanup()` the bag's
  registry subscriptions leak for every graph ever closed.

`meta` declares no `shadow()` fields and no node-side mirrors — it is plain
per-graph document data, not a settings tier. That is why its restore order
relative to nodes is unconstrained.

Tests: `tests/core/test_graph/test_graph_props_serialization.py` is the closest
existing home — it already covers the sibling `props` bag, so the `meta` cases
mirror its existing shape.

Cover: `graph_id` absent from `to_dict`; two graphs built from the same dict have
different `graph_id`s; `graph_id` unchanged across a save/load/save-as cycle;
`created_at` and `filestem` round-trip; `meta` round-trips through
`to_dict`/`load_from_dict`; a `load_from_dict` with no `"meta"` key yields the
declared defaults; and loading a second graph into a live object does not leak
the first graph's `meta` values (the `reset_all` guard).

---

## Task 2 — `GraphEntry.binding_id`

`barn/haybale-haystack/haybale_haystack/graph_entry.py`

1. Delete the `_unsaved_id` field (line 53) and its docstring entry (lines 40-43).
2. `binding_id` (line 58) returns `self.graph.graph_id` when `path is None`.
3. `display_name` (line 71) is untouched — it reads `graph.name`, not the id.

`barn/haybale-haystack/haybale_haystack/state/haystack_state.py`

1. `_make_graph_and_editor` (line 189) drops its `graph_id` parameter.
2. `create_new` (line 210) stops minting `f"__unsaved_{counter}__"`. The counter
   **stays** — it still feeds the `"Untitled N"` display name — but it is no
   longer an identity source. Drop `_unsaved_id=binding_id` from the
   `GraphEntry(...)` construction; `entry.binding_id` then reads through to the
   graph.
3. `open_graph` (line 249) passes only `str(path)` as the name.

**Untouched, and load-bearing:** `_recover_stale_binding_id`
([graph_editor.py:158](../../barn/haybale-graph-editor/haybale_graph_editor/editors/graph_editor.py#L158))
recovers a rekeyed tab by **graph object identity** via `get_by_graph`, never by
parsing the id string. That is why a save-as (uuid → path) remains safe: the id's
shape is genuinely opaque to that path.

**Docstring drift to fix:** `"__unsaved_N__"` is hardcoded in
[graph_app_state.py:68-69](../../barn/haybale-graph-editor/haybale_graph_editor/state/graph_app_state.py#L68-L69)
(`rekey`), [haywire_exception.py:492](../../packages/haywire-core/src/haywire/core/errors/haywire_exception.py#L492),
and [graph_editor.py:162](../../barn/haybale-graph-editor/haybale_graph_editor/editors/graph_editor.py#L162).

---

## Task 3 — Workspace stops persisting unsaved tabs

An unsaved graph cannot be restored — it has no file. Persisting its binding is
dead weight that resolves to nothing on the next launch.

[slot.py:119-120](../../packages/haywire-core/src/haywire/ui/app/slot.py#L119-L120)
writes `binding_id` unconditionally, and cannot special-case "unsaved graph"
without knowing about graphs — a layering violation.

### Split `is_unsaved` out of `is_dirty`

The flag needed here does not exist yet, and the existing one is currently doing
two jobs. `is_dirty` means *state changed since the last write, and would be lost*
— `CodeEditor` honours that exactly (`self._content != self._original`,
[code_editor.py:273](../../barn/haybale-studio/haybale_studio/editors/code_editor.py#L273)).
`GraphEditor` overloads it
([graph_editor.py:338](../../barn/haybale-graph-editor/haybale_graph_editor/editors/graph_editor.py#L338)):

```python
self.wrapper.set_dirty(entry.unsaved or entry.path is None, refresh=True)
```

because a never-saved graph also risks loss and the dirty dot was the only
channel available to say so. But "would be lost on close" and "has no file
backing it" are different facts:

| Tab state | `is_dirty` | `is_unsaved` |
|---|---|---|
| New empty graph | False | **True** |
| New graph, node added | True | **True** |
| Saved graph, edited | **True** | False |
| Saved graph, just saved | False | False |

The snapshot must keep row 3 and drop rows 1–2 — only `is_unsaved` expresses
that. The dirty badge should light for rows 2 and 3, i.e. `is_dirty or
is_unsaved`, which is what `GraphEditor` currently computes by hand.

**Add `is_unsaved: bool = False` to `EditorWrapperState`** beside `is_dirty`
([wrapper.py:55](../../packages/haywire-core/src/haywire/ui/editor/wrapper.py#L55)),
with a `set_unsaved()` setter mirroring `set_dirty()`. Then:

- `GraphEditor._sync_tab_dirty` sets both honestly — `set_dirty(entry.unsaved)`
  and `set_unsaved(entry.path is None)`.
- Both slots draw the badge on `is_dirty or is_unsaved`
  ([tab_slot.py:80](../../packages/haywire-core/src/haywire/ui/app/tab_slot.py#L80),
  [icon_slot.py:149](../../packages/haywire-core/src/haywire/ui/app/icon_slot.py#L149)).
- `to_snapshot`
  ([slot.py:111-123](../../packages/haywire-core/src/haywire/ui/app/slot.py#L111-L123))
  skips a wrapper whose `state.is_unsaved` is True — structurally the same as the
  `OpenBehavior.REQUIRED` skip two lines above it.
- `CodeEditor` needs no change: a file-backed binding is never unsaved in this
  sense.

Reading plain wrapper state means `to_snapshot` never needs an editor instance,
so lazily-instantiated wrappers raise no edge case.

⚠️ **The hot-reload path must not clear `is_unsaved`.** It clears `is_dirty` at
[wrapper.py:302](../../packages/haywire-core/src/haywire/ui/editor/wrapper.py#L302)
because a class swap gives the new instance fresh content — but a class swap does
not give the graph a file.

`BaseEditor.handle_close_request`'s docstring
([base.py:135](../../packages/haywire-core/src/haywire/ui/editor/base.py#L135))
tells editors to read `state.is_dirty` to decide whether to prompt; it should now
mention both flags.

**Note:** old `workspace_state.json` files still carry `__unsaved_3__` strings.
On next launch those resolve to nothing and the tab is skipped with a warning
([slot.py:165](../../packages/haywire-core/src/haywire/ui/app/slot.py#L165)) —
already today's behavior for a stale unsaved tab, so no regression and no
migration needed.

---

## Task 4 — `GraphContainer`: Protocol → ABC, `GraphEntry` inherits

`barn/haybale-graph-editor/haybale_graph_editor/protocols.py`

haystack already declares `haybale-graph-editor>=0.1.2` in its dependencies
([pyproject.toml:11](../../barn/haybale-haystack/pyproject.toml#L11)), so the
import direction is available and no cycle is created.

1. Convert `GraphContainer` from `Protocol` + `@runtime_checkable` to `abc.ABC`
   with `@abstractmethod`.
2. Declare `binding_id` and `display_name` **read-only** — matching what
   `GraphEntry` actually implements. The current settable declaration is the sole
   reason for the two `# type: ignore[arg-type]` casts at
   [haystack_state.py:230](../../barn/haybale-haystack/haybale_haystack/state/haystack_state.py#L230)
   and [:257](../../barn/haybale-haystack/haybale_haystack/state/haystack_state.py#L257);
   both casts and their explanatory comments delete.
3. `class GraphEntry(GraphContainer)`.

**Trap:** `GraphEntry` is a `@dataclass`. Inheriting from a `Protocol` base while
also subclassing it is the configuration most likely to bite — the protocol's
`@property` declarations become real class attributes that a dataclass field can
shadow badly. Converting to a plain ABC first is what makes this clean; do not
skip step 1 and inherit from the `Protocol` directly.

`tests/graph_editor/test_graph_container_protocol.py` relies on
`@runtime_checkable` for `isinstance`. With an ABC `isinstance` still works —
better, since it checks the real type rather than attribute names — but the test
needs rewriting.

Independent of the identity work — landable on its own.

---

## Task 5 — `GraphSaved` signal

`packages/haywire-core/src/haywire/core/signals/vocabulary.py`

```python
@dataclass(frozen=True)
class GraphSaved(Signal):
    """A graph was written to disk. Cross-session."""

    cross_session: ClassVar[bool] = True
```

Payload-free, matching `GraphDataMutated` — subscribers re-read their own state.
Cross-session because a save mutates state every session shares (the file on
disk), so every session's view of `modified_at` goes stale at that moment.

Emit from **`HaystackState._save_entry`**
([haystack_state.py:308](../../barn/haybale-haystack/haybale_haystack/state/haystack_state.py#L308)),
beside the existing `_broadcast_data_mutated()`. That is the single choke point:
the graph editor's save button, Ctrl+S, the haystack row save and the Farmhand
save tool all delegate there. Update the method docstring's "Side effects" list.

`GraphSaved` is **additive** — it does not replace the save-path
`GraphDataMutated`, which node/edge panels legitimately use to refresh dirty
markers.

---

## Task 6 — `GraphMetadataPanel`

New file:
`barn/haybale-graph-editor/haybale_graph_editor/panels/properties/setting/metadata.py`

A sibling of
[setting/graph.py](../../barn/haybale-graph-editor/haybale_graph_editor/panels/properties/setting/graph.py)
(`GraphSettingsPanel`, which renders `graph.props`) — copy it and change the bag.
Panel registration is folder-recursive (`haybale_graph_editor/__init__.py:55`),
so no wiring is needed.

```python
@panel(
    focus=GraphFocus,
    label="Graph Metadata",
    icon=hui.icon.graph,
    order=15,                      # between GraphInfoPanel (10) and GraphSettingsPanel (20)
    default_open=True,
    redraw_on=(ActiveGraphMoved, GraphSaved),
)
class GraphMetadataPanel(BasePanel):
    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        graph_obj = ctx.data[EditState].active_graph
        return graph_obj is not None and getattr(graph_obj, "meta", None) is not None

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        graph_obj = ctx.data[EditState].active_graph
        if graph_obj is None:
            return
        with layout:
            render_settings(graph_obj.meta)
```

`render_settings` owns the editing surface, so the panel inherits commit-on-blur,
correct event wiring and change propagation from the settings framework. Three
hazards the hand-built version had to solve individually — a `_commit` choke
point, the `update:value` vs `update:modelValue` trap
(`.insights/project_nicegui_input_update_value_event.md`), and blur-vs-keystroke
timing — do not arise.

The read-only trio (`filestem`, `created_at`, `modified_at`) belongs to
`GraphInfoPanel`, not here — see below.

**`redraw_on` deliberately excludes `GraphDataMutated`.** That signal means
*"graph contents (nodes, edges, props) changed"* — metadata is not content.
Subscribing to it to catch a save would be subscribing to the wrong thing for a
side effect, and would redraw the panel on every node edit, risking a mid-typing
rebuild (`.insights/feedback_nicegui_outbox_updatevalue_stomp.md`). `GraphSaved`
is what actually changes `modified_at`.

**Open decision for the implementer:** the panel declares no `access=` tier, so
it defaults to visible — matching `GraphSettingsPanel`. But a VIEW-tier
principal would then see editable inputs. Recommend `access=AccessTier.EDIT`.

### `GraphInfoPanel` gains the read-only rows

`introspect/graph.py` keeps its node/edge counts and gains `filestem`,
`created_at` and `modified_at` as `hui.info_row`s — it is already the read-only
panel, so the three framework-written fields land where they belong instead of
forcing a mixed editable/read-only panel.

Add `GraphSaved` to its `redraw_on` so `modified_at` refreshes on save.

It also reads `graph.name` with a `graph_id` fallback at line 48; the fallback
now yields a raw uuid, so drop it in favour of `"?"`.

`graph_id` is never shown — a transient uuid means nothing to a user.

### No undo

Metadata edits are **not** undoable, matching every other row in the Properties
Editor — including `graph.props`, which `meta` now sits beside. Verified:
`Editor.set_property` (the undo-recorded path) has exactly three non-test callers
— the Farmhand tool and the canvas resize handler (`interaction.py:76-78`).
`render_utils.py` contains no reference to `editor`, `set_property`, or
`history`; panel rows write straight to the bag or port. Making metadata undoable
would make it the *only* undoable thing in that editor.

---

## Task 7 — Farmhand read

`barn/haybale-graph-editor/haybale_graph_editor/farmhands/editor_tools.py`

Add a `"metadata"` key to `GraphEditorQueryGraphTool.run`'s returned dict
(line ~528), populated from `graph.meta.to_dict()`. The return shape is a flat
dict, so this is purely additive.

`query_graph` is the orientation call agents already make, and metadata is
orientation information — "what is this graph for" is otherwise unanswerable
from node topology. Folding it in costs no new tool slot.

The tool's own instructions warn against unfocused calls; `description` is free
text, so **truncate it** in the payload.

---

## Task 8 — Farmhand write

Same file. New `graph_editor_set_metadata`:

```python
@farmhand(
    label="Set graph metadata",
    registry_id="set_metadata",
    annotations=_MUTATING,
    access=AccessTier.EDIT,
)
class GraphEditorSetMetadataTool(Farmhand):
    async def run(
        self,
        ctx: FarmhandContext,
        binding_id: str,
        label: str | None = None,
        description: str | None = None,
        author: str | None = None,
        version: str | None = None,
    ) -> dict:
```

Each provided kwarg is written to the corresponding field on `graph.meta`.

- **Closed kwarg set** of exactly the four editable fields — unlike
  `set_property`, which resolves `name` dynamically against ports and bags.
  Unknown fields are impossible by signature. `graph_id`, `filestem`,
  `created_at` and `modified_at` are all structurally unreachable here.
- Multiple fields per call: metadata fields are few, fixed, and naturally set
  together (an agent describing a graph it just built sets `description` and
  `version` at once).
- Keep `set_property`'s **read-back verification** discipline — re-read after
  writing and raise a structured `FarmhandError` if a value did not take. This is
  **load-bearing for a settings bag**: a validator-rejected settings write is
  dropped *silently* (`.insights/project_settings_bags_include_props.md`), so the
  read-back is the only thing that turns a lost write into an error.
- Does **not** mark the entry `unsaved` — see "Metadata edits do not dirty the
  graph" above.
- **No `ctx.fence(editor)`** — that fence exists to make one tool call one undo
  gesture, and metadata has no undo.
- `binding_id` here is the *address* of the graph to write to, not a field being
  written.

**Known gap:** an agent's write will not reach an open panel — neither
`ActiveGraphMoved` nor `GraphSaved` fires on a metadata write. Broadcasting
`GraphSaved` would be semantically wrong (nothing was saved). Either accept the
staleness or introduce a narrower signal; recommend **accept** for now and
revisit if it bites.

---

## Task 9 — Pre-hydration: the format migration chain

The `.haywire` format will keep changing. Rather than hand-editing fixtures on
every change (and abandoning any file a user already has), old dicts are upgraded
to the current shape **before** `load_from_dict` sees them.

New package: `packages/haywire-core/src/haywire/core/graph/prehydration/`

```
__init__.py   -> prehydrate(), CURRENT_FORMAT_VERSION, _HEAD
upgrader.py   -> Upgrader ABC, UpgradeAncient, UnknownGraphFormat
v1.py, v2.py  -> one module per version step
```

A working sketch of everything below — with the six cases exercised — is in the
session scratchpad as `prehydration.py`.

### The `Upgrader` contract

```python
class Upgrader(ABC):
    to_version: int                                     # the version this PRODUCES

    @abstractmethod
    def detect(self, data: GraphDict) -> bool: ...      # already this shape or newer?
    @abstractmethod
    def _change_structure(self, data: GraphDict) -> GraphDict: ...
    @abstractmethod
    def _predecessor(self) -> "Upgrader": ...

    def upgrade(self, data: GraphDict) -> GraphDict:
        if self.detect(data):
            _validate(data)                             # see below — runs on every path
            return data                                 # short-circuit
        data = self._predecessor().upgrade(data)        # recurse down
        data = self._change_structure(data)             # this version's step
        data["format_version"] = self.to_version
        return data
```

`upgrade` is a **template method** — the recurse / short-circuit / stamp sequence
is written once in the ABC. Subclasses supply only the three abstract methods, so
a new version cannot get the sequencing subtly wrong (an inverted guard, a
missing stamp).

`detect` means *"already at `to_version` **or newer**"*, not *"is exactly this
version"*. That is what makes the short-circuit correct: a current file matches
at the head and returns untouched, never recursing.

**Per-version detection is the point of the recursion.** Each version decides for
itself what proves a file is already its shape, and that signal is not always a
version number — versions predating the `format_version` key must detect
structurally:

```python
class UpgradeVersionOne(Upgrader):        # v0 -> v1: drop graph_id and name
    to_version = 1

    def detect(self, data):
        if data.get("format_version", 0) >= self.to_version:
            return True
        return "graph_id" not in data and "name" not in data
```

**v1 drops `name` rather than renaming it to `filestem`.** An upgrader receives a
dict, not a filename, so it cannot compute the correct stem — and every existing
file's `name` is the stale `"Untitled N"` (see "`filestem` is derived on load"
above). Renaming would launder a wrong value into a field that promises
otherwise. `load_from_file` stamps the real stem immediately afterwards.

A detection rule that later proves wrong is fixed in its own class, without
touching any other upgrader.

### Validation runs on every path, not just the terminator

```python
_REQUIRED = ("nodes", "edges")

def _validate(data: GraphDict) -> None:
    missing = [k for k in _REQUIRED if k not in data]
    if missing:
        raise UnknownGraphFormat(f"missing required key(s): {', '.join(missing)}")
```

`UpgradeAncient.detect` calls it — by the time recursion reaches the terminator,
no later version claimed the dict, so it is either genuinely ancient or not a
graph at all.

⚠️ **But the short-circuit must validate too**, and this is easy to get wrong.
Detection rules are often *absence*-based (v1's signal is "`graph_id` and `name`
are both gone"), and absence matches unrelated dicts. `{"totally": "unrelated"}`
has neither key, so v1 claims it, the chain short-circuits at the head, and the
terminator never runs. Calling `_validate` on the short-circuit path closes that
hole — a `detect` that says "already current" must still be answering *about a
graph*.

Found by the sketch's own test case; the first version of this chain returned
garbage for a non-graph dict.

**`_REQUIRED` is verified against the real fixtures:** `"edges"` is present as
`{}` even in the three edge-less graphs, so the check is on **presence, not
truthiness**. Do not "simplify" it to `if not data.get("edges")`.

### `prehydrate` — two failures, reported differently

```python
_HEAD: Upgrader = UpgradeVersionTwo()
CURRENT_FORMAT_VERSION = _HEAD.to_version   # derived — the two cannot drift

def prehydrate(data: GraphDict) -> GraphDict:
    found = data.get("format_version", 0)
    if found > CURRENT_FORMAT_VERSION:
        raise HaywireException(...)         # from the future -> "update Haywire"
    try:
        return _HEAD.upgrade(data)
    except UnknownGraphFormat as exc:
        raise HaywireException(...) from exc  # not a graph -> "open a different file"
```

The future-version check is **upfront, not in the `except`**. A v99 file that
still has `nodes` and `edges` passes the terminator's validation and would sail
through the chain unchanged — silently half-loading a shape we cannot read.
`format_version` is the one field whose meaning is guaranteed stable across
versions, so it is the only thing testable before the chain touches anything.

`UnknownGraphFormat` is internal to the package; `prehydrate` converts both
failures into `HaywireException` at the boundary.

### ⚠️ `format_version` is NOT `meta.version`

`meta.version` is user-editable free text (`"1.0.0"` by default). If the chain
read `version`, a user typing `2.0` into the metadata panel would make their file
claim to be schema v2 — silent, unrecoverable corruption.

`format_version` is framework-owned, an integer, and stays **top-level** — never
inside `meta`, whose own shape may migrate. The sketch's `spoofed` test case
covers exactly this.

### Wiring

- Call `prehydrate` at the **top of `load_from_dict`**, not in `load_from_file`.
  `load_from_dict` is public and called directly by tests and the docs generator;
  a migration only some callers get is a bug waiting to happen. Detection on an
  already-current dict is one dict lookup.
- `save_to_file` stamps `format_version = CURRENT_FORMAT_VERSION`.
- Upgraders **mutate in place**; `prehydrate` documents that the caller hands
  over ownership. `load_from_dict` owns its freshly-parsed dict, so this is safe.

### What this replaces

**The six existing `.haywire` files are left untouched** — no hand-migration.
They are v0-shaped and get upgraded on every load, which means the migration path
is exercised by every test run rather than by nothing.

```text
graphs/empty.haywire      graphs/webcam.haywire     graphs/loop.haywire
graphs/settings.haywire   graphs/oakNwebCam.haywire graphs/10x200nodes.haywire
```

Two upgraders cover this plan's changes: **v1** drops `graph_id` and `name`;
**v2** nests `label`/`description`/`author`/`version` into `meta`.

Verified against all six real fixtures — every one upgrades cleanly to v2, and
`"edges"` is present as `{}` even in the three edge-less graphs
(`10x200nodes`, `empty`, `settings`), so the terminator's `_REQUIRED` floor
holds. `label` is absent from every file and correctly falls back to `""`.

Tests: round-trip each historical shape (v0, v1, current) to the current one;
assert a current dict is returned untouched; assert both failure modes raise
distinctly. Ancient fixtures are the real regression test — if an upgrader
breaks, the suite fails on load.

**`rename/discovery.py:43` needs its marker list trimmed.** It sniffs `.haywire`
files with `_MARKERS = (b'"graph_id"', b'"registry_key"', b'"nodes"')` and
`"graph_id"` no longer serializes *for new saves* (old files on disk still carry
it). The match is `any(...)`
([discovery.py:55](../../packages/haywire-studio/src/haywire_studio/packaging/rename/discovery.py#L55)),
so simply **drop the dead marker** — `"registry_key"` and `"nodes"` both still
appear in every graph, and `_is_graph` confirms by structure afterwards.

---

## Task 10 — `name` → `filestem` rename (land separately)

~69 call sites including test fixtures. Mechanical but wide, and it shares
**nothing** with the identity work — land it as its own commit or the diff
becomes unattributable.

This is the **in-memory attribute** rename. The on-disk key is already handled:
v1 drops `name` and `load_from_file` stamps `filestem` (Task 9), so by the time
this lands no file is read for it.

Only three non-test readers of `graph.name` exist, and all three confirm the
rename is honest:

- `graph_to_python.py:25` sanitises it into a **Python function name** — a
  filename stem is exactly right; a free-text `label` would be wrong.
- `graph_to_python.py:66` — the docstring header of generated code.
- `graph_editor.py:154` passes it as `label=` to `Reveal`, a **tab label**,
  which per this design is filename-derived.

All three get a *correct* value for the first time once `filestem` is stamped
from the real path — today they render `"Untitled 1"` for `webcam.haywire`.

`filestem` over `filename` because the field holds the stem (`face_tracker`), not
the basename (`face_tracker.haywire`).

After the rename run `/check-rename`: the IDE misses string-based references
(`patch("...")`, `monkeypatch.setattr`, doc citations).

---

## Suggested landing order

1. **Task 4** (Protocol → ABC) — independent, small, removes two `type: ignore`s.
2. **Task 9** (pre-hydration) **first, with only `UpgradeAncient` and the
   plumbing** — landing the chain before the format changes means v1 and v2 are
   written against a format that still exists on disk, and the fixtures prove it.
3. **Tasks 1 + 1b + 2** together — the identity change and the `meta` bag alter
   the same constructor and the same file format; each adds its upgrader to the
   chain as it lands.
4. **Task 3** (workspace filter) — depends on 3 only for its rationale.
5. **Tasks 5–8** (signal, panels, Farmhand) — pure additions on top of a settled
   field model.
6. **Task 10** (`name` → `filestem`) — last, alone.

---

## Verification

Per `CLAUDE.md`, establish a baseline **before** starting — this is a multi-file
refactor with a signature change:

```sh
uv run ruff check <paths>
uv run mypy <paths>
```

The codebase has no errors; anything new afterwards is ours. Then:

```sh
uv run pytest tests/core/test_graph/ tests/graph_editor/ tests/haystack/
uv run pytest -m "not browser and not perf" -q > /tmp/t.log 2>&1; echo "exit=$?"
uv run ruff check . && uv run ruff format --check .
```

Both ruff commands — CI runs both and they catch disjoint problems.

⚠️ `tests/studio/test_docs/test_generate.py`'s teardown runs
`git checkout -- barn/haybale-testing`, silently discarding any uncommitted edit
there. Commit work under that dir before running the full suite
(`.insights/project_docs_test_reverts_barn_testing.md`).

---

## Scope boundaries

**Not doing:** any persisted document identity (nothing needs one) · migrating
`__unsaved_N__` strings out of existing `workspace_state.json` (they already fail
harmlessly) · a user-editable title that drives navigation (tabs and haystack
rows stay filename-derived) · migrating metadata into a settings bag (metadata
describes the document; `graph.props` configures the program) · undo for metadata
· `author` auto-populated from the authenticated principal · `modified_by` /
richer provenance · a description prompt in the Save-As dialog · fixing the
pre-existing double-broadcast at `graph_editor.py:384` · an ADR.

## Docs

`docs/reference/glossary.md` was updated during the 2026-08-17 design session:
added `graph_id`, `fs_uuid`, `origin_hash`, graph `filestem`, **graph metadata**,
and `binding_id`.

**This revision supersedes those entries** and they must be rewritten:

- `graph_id` — now a transient per-instance uuid, never serialized (not
  `str(path)`). State explicitly that two tabs on one file hold two `graph_id`s.
- `fs_uuid` and `origin_hash` — **delete both entries.** Neither field exists; a
  reader would go looking for something that was never built.
- `binding_id` — the unsaved branch is now `graph.graph_id`, not `__unsaved_N__`.
