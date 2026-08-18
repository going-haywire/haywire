# Graph metadata — implementation plan

**Status:** ready to build · **Settled:** 2026-08-17 (inquisition session)

Closes the lifecycle gap: `BaseGraph` carries metadata fields that round-trip
through JSON but that nothing writes and no UI exposes. `created_at` was never
stamped; `name` was set inconsistently (`"Untitled N"` for new graphs, the full
path for opened ones) and read by nothing but one info row.

Vocabulary for everything below is canon in
[reference/glossary.md](../../docs/reference/glossary.md) — see `graph_id`,
`graph_uuid`, `origin_hash`, graph `filestem`, and **graph metadata**.

---

## Field model

**Persisted at the top level of the `.haywire` file:**

| Field | Editable | Written when | Written by |
|---|---|---|---|
| `label` | **yes** | on edit | panel / `set_metadata` — free-text title, no navigation role |
| `description` | **yes** | on edit | panel / `set_metadata` |
| `author` | **yes** | on edit | panel / `set_metadata` — blank until typed |
| `version` | **yes** | on edit | panel / `set_metadata` — `"1.0.0"` at creation |
| `filestem` | no | save / save-as | `save_to_file` stamps `path.stem`; `"Untitled N"` while unsaved |
| `created_at` | no | once, at construction | `BaseGraph.__init__` |
| `modified_at` | no | every save | `save_to_file` |
| `graph_uuid` | no | at creation; re-minted on load | `__init__` / `load_from_dict` |
| `origin_hash` | no | save / save-as | `save_to_file` |

**Runtime only — never serialized, no setter, not settable by panel or tool:**

| Field | Value |
|---|---|
| `graph_id` | `str(path)`, or `__unsaved_N__` while unsaved |
| `binding_id` | the same string, computed property on `GraphEntry` |

`graph_id` keeps its name deliberately. It is *not* renamed to `binding_id`:
`binding_id` is a haystack/studio concept (the key a container is filed under in
`GraphAppState`) and `BaseGraph` lives in `haywire-core`, which must not be named
after a studio-layer registry. `GraphEntry.binding_id` already owns that name;
two same-named attributes on different objects would have to be kept in sync by
convention alone.

---

## Task 1 — Field model on `BaseGraph`

`packages/haywire-core/src/haywire/core/graph/base.py`

1. In `__init__` (around lines 107–120):
   - rename `self.name` → `self.filestem` (keep the constructor parameter
     positional; see Task 7 for call sites)
   - add `self.label: str = ""`
   - stamp `self.created_at = datetime.now().isoformat()` (currently never
     written — it stays `None` for the lifetime of every graph)
   - mint `self.graph_uuid: str = str(uuid.uuid4())`
   - add `self.origin_hash: str = ""`

2. `to_dict` (line ~904): **drop `graph_id`**; add `label`, `filestem`,
   `graph_uuid`, `origin_hash`. Keep `description`, `version`, `author`,
   `created_at`, `modified_at`.

3. `load_from_dict` (line ~931): **stop reading `graph_id` from the file.**
   It is a runtime location key — a file that records its own location lies as
   soon as it is copied. Read the rest, then apply the re-mint rule below.

4. `save_to_file` (line ~1107): alongside the existing `modified_at` stamp, set
   `self.filestem = Path(filepath).stem` and
   `self.origin_hash = sha256(str(Path(filepath).resolve()).encode()).hexdigest()`.

### The re-mint rule

On load, compare `sha256` of the file's own absolute path against the stored
`origin_hash`. When they differ the file is a fork (a copy) and a **fresh
`graph_uuid` is minted**, so a duplicated graph never shares its ancestor's
identity.

The hash — rather than a readable path — is deliberate: a `.haywire` file
travels between users, and storing `/home/ann/proj/graphs/a.haywire` ships one
user's home directory to everyone who opens the graph. Nothing ever needs to
recover the path, only to compare, so a one-way function costs nothing.

> A **workspace-relative** path was considered and rejected: Ann's and Bob's
> copies are both `graphs/a.haywire`, so they compare equal and the re-mint never
> fires — defeating the feature in exactly the sharing scenario that motivates
> it. A hand-rolled scramble was also rejected: every step is a known permutation
> of a known string, so it is trivially reversible, and the character multiset is
> preserved, leaving short usernames readable straight off the output.

**Accepted false positive:** a plain *move* hashes differently and also
re-mints. Move and copy are indistinguishable from the file alone.

**Open decision for the implementer:** does a re-mint mark the graph dirty?
Marking it dirty means merely *opening* a moved graph offers to save it, which
is surprising; not marking it means the fresh uuid lives only in memory until an
unrelated edit. Recommend **not** dirty — the uuid persists on the next real
save, and an unsaved copy has no identity worth defending.

Tests: `tests/core/test_graph/test_graph_props_serialization.py` is the closest
existing home; add round-trip coverage for every field plus re-mint on
hash-mismatch and stability on hash-match.

---

## Task 2 — `GraphSaved` signal

`packages/haywire-core/src/haywire/core/session/signals/vocabulary.py`

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
(`barn/haybale-haystack/haybale_haystack/state/haystack_state.py:308`), beside
the existing `_broadcast_data_mutated()`. That is the single choke point: the
graph editor's save button, Ctrl+S, the haystack row save and the Farmhand save
tool all delegate there. Update the method docstring's "Side effects" list.

`GraphSaved` is **additive** — it does not replace the save-path
`GraphDataMutated`, which node/edge panels legitimately use to refresh dirty
markers.

> Out of scope: `graph_editor._save_graph` publishes `GraphDataMutated` a second
> time at `graph_editor.py:384` after `_save_entry` already did. Harmless,
> pre-existing, left alone.

---

## Task 3 — `GraphMetadataPanel`

New file: `barn/haybale-graph-editor/haybale_graph_editor/panels/properties/metadata/graph.py`

A third sibling beside `introspect/` (read-only) and `setting/` (settings bags).
Metadata is neither — it is writable, but not a `Settings` bag. Panel
registration is folder-**recursive**
(`haybale_graph_editor/__init__.py:55`), so a new subdirectory needs no wiring.

```python
@panel(
    focus=GraphFocus,
    label="Graph Metadata",
    icon=hui.icon.graph,
    order=15,                      # between GraphInfoPanel (10) and GraphSettingsPanel (20)
    redraw_on=(ActiveGraphMoved, GraphSaved),
)
```

`GraphInfoPanel` (`introspect/graph.py`) is **left untouched** — it keeps
node/edge counts and stays read-only, so no existing tests churn.

**Rows** — read-only via `hui.info_row`, editable via `hui.input_field`:

- read-only: `filestem`, `created_at`, `modified_at`
- editable: `label`, `description`, `author`, `version`

`graph_uuid` and `origin_hash` are not shown.

**`redraw_on` deliberately excludes `GraphDataMutated`.** That signal means
*"graph contents (nodes, edges, props) changed"* — metadata is not content.
Subscribing to it to catch a save would be subscribing to the wrong thing for a
side effect, and would redraw the panel on every node edit, risking a mid-typing
rebuild (`.insights/feedback_nicegui_outbox_updatevalue_stomp.md`). `GraphSaved`
is what actually changes `modified_at`.

### Commit path

Route every write through **one** choke point:

```python
def _commit(self, graph, entry, field: str, value: str) -> None:
    setattr(graph, field, value)
    entry.unsaved = True
```

Marking `unsaved` explicitly is **required**: `HaystackState._on_entry_validation`
only sets it when `result.nodes or result.edges` changed
(`haystack_state.py:181`), and a metadata edit touches neither. Without this the
edit is silently lost on close.

Commit on **blur/change**, not per keystroke.

**Traps:** `ui.input` emits `update:value`, not `update:modelValue` — a widget
binding on the wrong event silently drops every edit in-browser
(`.insights/project_nicegui_input_update_value_event.md`). Prefer `on_change=`
on `hui.input_field` over a manual binding.

**Open decision for the implementer:** the panel declares no `access=` tier, so
it defaults to visible — matching `GraphSettingsPanel`. But a VIEW-tier
principal would then see editable inputs. Recommend `access=AccessTier.EDIT`.

### No undo

Metadata edits are **not** undoable, matching every other row in the Properties
Editor. Verified: `Editor.set_property` (the undo-recorded path) has exactly
three non-test callers — the Farmhand tool and the canvas resize handler
(`interaction.py:76-78`). `render_utils.py` contains no reference to `editor`,
`set_property`, or `history`; panel rows write straight to the bag or port. Making
metadata undoable would make it the *only* undoable thing in that editor.

---

## Task 4 — Farmhand read

`barn/haybale-graph-editor/haybale_graph_editor/farmhands/editor_tools.py`

Add a `"metadata"` key to `GraphEditorQueryGraphTool.run`'s returned dict
(line ~528). The return shape is a flat dict, so this is purely additive.

`query_graph` is the orientation call agents already make, and metadata is
orientation information — "what is this graph for" is otherwise unanswerable
from node topology. Folding it in costs no new tool slot.

The tool's own instructions warn against unfocused calls; `description` is free
text, so **truncate it** in the payload.

---

## Task 5 — Farmhand write

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

- **Closed kwarg set** of exactly the four editable fields — unlike
  `set_property`, which resolves `name` dynamically against ports and bags.
  Unknown fields are impossible by signature.
- Multiple fields per call: metadata fields are few, fixed, and naturally set
  together (an agent describing a graph it just built sets `description` and
  `version` at once).
- Keep `set_property`'s **read-back verification** discipline — re-read after
  writing and raise a structured `FarmhandError` if a value did not take.
- Mark the entry `unsaved` (same reason as Task 3).
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

## Task 6 — Migrate existing `.haywire` files

**No back-compat code.** These six files are the only graphs in existence:

```
graphs/empty.haywire      graphs/webcam.haywire     graphs/loop.haywire
graphs/settings.haywire   graphs/oakNwebCam.haywire graphs/10x200nodes.haywire
```

For each: remove `"graph_id"`; rename `"name"` → `"filestem"`; add `"label": ""`,
`"graph_uuid"` (a fresh uuid each), `"origin_hash": ""`, and a `"created_at"`
stamp. An empty `origin_hash` will not match any real path hash, so the first
load re-mints — harmless for these fixtures, and avoids hand-computing hashes.

**`rename/discovery.py:43` needs a new format marker.** It currently sniffs
`.haywire` files with `_MARKERS = (b'"graph_id"', b'"registry_key"', b'"nodes"')`
and `"graph_id"` no longer serializes. `b'"graph_uuid"'` is the natural
replacement.

---

## Task 7 — `name` → `filestem` rename

~69 call sites including the `BaseGraph(graph_id, name, ...)` constructor
signature and test fixtures. Mechanical but wide.

Only **three** non-test readers of `graph.name` exist, and both usages confirm
the rename is honest:

- `graph_to_python.py:25` sanitises it into a **Python function name** — a
  filename stem is exactly right; a free-text `label` would be wrong.
- `graph_to_python.py:66` — the docstring header of generated code.
- `graph_editor.py:154` passes it as `label=` to `Reveal`, a **tab label**,
  which per this design is filename-derived.

`filestem` over `filename` because the field holds the stem (`face_tracker`),
not the basename (`face_tracker.haywire`) — `filename` would mislead.

After the rename run `/check-rename`: the IDE misses string-based references
(`patch("...")`, `monkeypatch.setattr`, doc citations).

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

---

## Scope boundaries

**Not doing:** a user-editable title that drives navigation (tabs and haystack
rows stay filename-derived — a free-text title competing with the filename makes
"which file am I editing?" unanswerable) · migrating metadata into a settings bag
(metadata describes the document; `graph.props` configures the program) · undo
for metadata · `author` auto-populated from the authenticated principal or the OS
user · `modified_by` / richer provenance · a description prompt in the Save-As
dialog · settable `graph_id` / `binding_id` (no setter exists — `binding_id` is a
computed property, and that is what stops a copied file lying about its location)
· fixing the double-broadcast at `graph_editor.py:384` · an ADR · a doc-drift
note for the `haywire_exception` docstring.

## Docs

`docs/reference/glossary.md` was updated during the design session: added
`graph_id`, `graph_uuid`, `origin_hash`, graph `filestem`, **graph metadata**,
and `binding_id`; corrected the error-locator entry, which claimed `graph_id`
was the `binding_id` while the code passed `path.stem`.
