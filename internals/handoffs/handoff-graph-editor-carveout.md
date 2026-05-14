# Handoff — Carving `GraphEditor` out of `haybale-haystack` into its own library

## What this is

An interactive design conversation (using the `inquisition` skill flow) walking through how to extract `GraphEditor` from `haybale-haystack` into a new library `haybale-graph-editor`, so that other graph-management libraries can depend on the editor.

**No code has been written.** The conversation is in the design phase — questions Q1–Q6 have been answered; Q7 and Q8 are open. The next session should resume by asking Q7 (or accept the recommendation), then Q8, then either continue interviewing or transition to writing a plan.

## Status: where we are in the interview

Decisions locked in (with the user's chosen letter and brief rationale):

- **Q1 — Goal:** **B** — multiple graph-management libraries should coexist *simultaneously* (not just be substitutable).
- **Q2 — How a tab knows which source owns it:** **A** — tagged payloads `(source_id, entry_id)`. Subsequently superseded by the container-as-bound-object model.
- **Q3 — Source identity / lookup:** Asked but **superseded** by the user's reframing in Q4 (see below).
- **Q4 — User's reframe:** The payload should be a **reference to a container that holds the graph**, with a `save()` method. The whole "tag the payload, look up the source" path was dropped in favor of: the source creates a container, hands it to the editor via the wrapper; the editor just calls `container.save()`.
- **Q5 (revised) — Protocol shape:** **D-ish** — `GraphContainer` is a Protocol in the new library; `GraphEntry` stays in haystack as a concrete dataclass and structurally satisfies the protocol. User pushed back on bloated protocol surface — final minimal protocol is:
  - `editor: Editor`
  - `path: Optional[Path]`
  - `unsaved: bool`
  - `display_name: str`
  - `save(save_as: Optional[Path] = None) -> Optional[str]` (returns new binding_id on save-as, else None)
- **Q6 — Cold-restore string→container resolution:** **A** (recommended, awaiting explicit confirmation) — GraphEditor lazily walks `context.app_data` on first `on_focus` after restore looking for *any* object implementing a tiny `GraphSource` protocol (`get_by_id(binding_id) -> Optional[GraphContainer]`).
- **Terminology correction by user:** `payload` in `EditorWrapper` has already been renamed to `binding_id`. The wrapper's composite identity is `editor_binding_id = "editor_key::binding_id"`. See [wrapper.py:104,170-181](packages/haywire-core/src/haywire/ui/editor/wrapper.py#L104).

## Open questions

- **Q7 — `entry.save()` implementation:** Does `GraphEntry` hold a back-reference to `HaystackState` (option A, recommended), or an injected callable (option B)?
- **Q8 — Scope confirmation:** Final IN/OUT list for the carve-out, listed near the end of the conversation. Pending user sign-off.

## The converged design

```
haybale-graph-editor (NEW library)
├── GraphContainer (Protocol)   — what GraphEditor consumes
│     editor, path, unsaved, display_name, save(save_as) -> Optional[str]
├── GraphSource (Protocol)      — touched only on cold-restore
│     get_by_id(binding_id: str) -> Optional[GraphContainer]
└── GraphEditor                  — moved verbatim, then adapted:
      - reads self.wrapper.bound_object instead of looking up HaystackState
      - on on_focus, if bound_object is None: scan app_data for a GraphSource
      - calls container.save(save_as) instead of haystack.save_graph(entry, ...)

haywire-core (small extension)
└── EditorWrapper.bound_object: Optional[Any] = None
      - runtime-only carry-along, NOT part of binding_id / split_id / persistence
      - settable via actions.reveal(..., bound_object=container)

haybale-haystack (now depends on haybale-graph-editor)
├── GraphEntry — stays here; gains save() + back-ref to HaystackState
├── HaystackState — gains nothing new (get_by_id and save logic already exist)
├── HaystackEditor — update its actions.reveal() calls to pass bound_object=entry
└── panels/file_browser/open_in_haystack.py — same: pass bound_object=entry
```

## Critical reference findings (from code-tracing during the interview)

These were established factually by reading code, not by speculation. The next session can trust them without re-tracing:

- **Direct coupling editor→source today is exactly two methods:** `HaystackState.get_by_id(payload)` (4 call sites) and `HaystackState.save_graph(entry, save_as=...)` (2 call sites). All in [graph_editor.py](barn/haybale-haystack/haybale_haystack/editors/graph_editor.py).
- **The source never calls into the editor directly.** Cross-direction communication is via session signals only (`GraphDataMutated`, `ActiveGraphMoved`, `HaystackReloaded`, `HaystackTeardown`).
- **GraphEditor.redraw_on_signal returns False for everything** ([graph_editor.py:84-90](barn/haybale-haystack/haybale_haystack/editors/graph_editor.py#L84-L90)). Editor never redraws on signals; it's purely pull-based via `draw`/`on_focus`/`save`/`undo`/`redo`.
- **Dirty flow is three independent layers:**
  - Layer 1 (per-graph `entry.unsaved`): set by `HaystackState._on_entry_validation`; read by GraphEditor at redraw time.
  - Layer 2 (`_haystack_dirty`): haystack-internal, irrelevant to carve-out.
  - Layer 3 (`wrapper._state.is_dirty`): set by `GraphEditor._sync_tab_dirty` calling `wrapper.set_dirty(...)`.
- **`actions.reveal(GraphEditor, ...)` call sites that need updating to pass `bound_object`:**
  - [haystack_editor.py:606, 622, 736, 795](barn/haybale-haystack/haybale_haystack/editors/haystack_editor.py)
  - [open_in_haystack.py:66](barn/haybale-haystack/haybale_haystack/panels/file_browser/open_in_haystack.py#L66)
- **Tab restore from saved settings** is the residual coupling: the slot rehydrates `(editor_key, binding_id)` but cannot reconstruct `bound_object` — hence the `GraphSource` protocol exists only for this path.
- **`Protocol` is idiomatic in this codebase** — already used in `haywire.core.session.protocols.IProjectState` and the panel `action=` system.

## Files that will change (when implementation starts)

- **New:** `barn/haybale-graph-editor/` (full library skeleton mirroring `barn/haybale-haystack/`)
- **Moved:** `barn/haybale-haystack/haybale_haystack/editors/graph_editor.py` → `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_editor.py`
- **Modified — haywire-core:** [packages/haywire-core/src/haywire/ui/editor/wrapper.py](packages/haywire-core/src/haywire/ui/editor/wrapper.py) (add `bound_object`), and whatever defines `actions.reveal` to accept it
- **Modified — haybale-haystack:**
  - `pyproject.toml` — add dependency
  - `graph_entry.py` — add `save()` + `_haystack` back-ref
  - `editors/haystack_editor.py` — import `GraphEditor` from new library; pass `bound_object=entry` in reveals
  - `panels/file_browser/open_in_haystack.py` — same
- **Modified — tests:** [tests/studio/test_graph_editor_on_focus.py:12](tests/studio/test_graph_editor_on_focus.py#L12) (import path)
- **Modified — docs:** [docs/components/editors/editor-canon.md](docs/components/editors/editor-canon.md), [docs/reference/glossary.md](docs/reference/glossary.md) (mentions of GraphEditor)

## What the next session should do

1. **Resume the interview** by posing Q7 (back-ref vs callable) and Q8 (scope confirmation) to the user. Do NOT begin implementation until both are answered.
2. **After Q7/Q8 close:** offer to switch to the `writing-plans` skill to produce a concrete implementation plan, or keep iterating if more questions surface.
3. **Do not assume the user wants implementation yet** — this has been a design conversation. Confirm before coding.

## Suggested skills for the next session

- **`inquisition`** — to continue the interview through Q7/Q8 and any follow-up branches.
- **`writing-plans`** — once design is locked, to produce a multi-step implementation plan.
- **`haywire-libs`** — load Haywire library plugin system docs (entry points, BaseLibrary, register_components) before scaffolding the new `haybale-graph-editor`.
- **`haywire-ui`** — load Haywire UI architecture docs (editors, panels, slot model) for context on EditorWrapper/Slot changes.
- **`codemap-navigator`** — if available `.codemap/` exists, consult before opening source files.

## Constraints the next session must respect (from CLAUDE.md)

- **No singleton/registration assumptions without confirming:** CLAUDE.md explicitly warns "do NOT assume singleton patterns, library ownership models, or registration paths. Ask for confirmation before implementing architectural decisions that affect class hierarchies or dependency injection."
- **Read files before editing; grep for callers before modifying functions.**
- **Pre-edit baseline:** for substantial changes (which this will be), run `uv run ruff check <path>` and `uv run mypy <path>` first, baseline the noise, then re-run after edits.
- **Tests after the refactor:** run the full suite, confirm green, especially `tests/studio/test_graph_editor_on_focus.py` which directly imports the relocated class.
