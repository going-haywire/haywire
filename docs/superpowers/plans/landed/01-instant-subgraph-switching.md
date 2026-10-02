# Instant switching between a graph and its Groups

## Context

Switching between two open graph *documents* is instant, because the EDIT slot
keeps every panel mounted:

> Each wrapper gets its own `ui.tab_panel` keyed by `binding_id`. All panels live
> in the DOM simultaneously; switching toggles visibility via `set_value` rather
> than clearing and re-rendering.
> — [slot.py:406-409](packages/haywire-core/src/haywire/ui/app/slot.py#L406-L409)

Entering a Group re-keys a single wrapper and redraws it, so each navigation
remounts the canvas. On a graph that takes seconds to build, every trip in and
out pays that cost — and patching a Group means going back and forth repeatedly.

**Outcome:** a Group opens once and stays mounted. Returning to it, or to the
graph above it, costs a `set_value`. Zoom, pan and selection survive per level.

This wants to land before Slice 2 (Macro): a Macro opens as its own document, so
it needs the one-wrapper-per-Subgraph navigation this installs.

## Decisions

| Decision | Choice |
|---|---|
Where a Group tab appears | The main tab row, distinguished by `GraphEditor.draw_tab`. Revisit if it crowds. |
Restored on restart | No. A Group tab is transient. |

## What to build

### 1. Navigate by `Reveal`

`Slot.reveal` is find-or-switch on `(editor_key, binding_id)`
([slot.py:531-590](packages/haywire-core/src/haywire/ui/app/slot.py#L531-L590)),
`GraphEditor` is `ON_PAYLOAD`, and a `SubgraphContainer` carries a distinct
`binding_id` in `GraphAppState`. Publishing a `Reveal` for it opens a tab on
first visit and switches to it on every visit after — the call
`HaystackEditor` uses to open a graph
([haystack_editor.py:104](barn/haybale-haystack/haybale_haystack/editors/haystack_editor.py#L104)).

In [graph_editor.py](barn/haybale-graph-editor/haybale_graph_editor/editors/graph_editor.py):

- `descend_into` builds and registers the `SubgraphContainer`, then publishes
  `Reveal(editor=GraphEditor, binding_id=container.binding_id, label=…)`.
- `ascend`, `ascend_to` and each breadcrumb crumb publish `Reveal` for the
  ancestor's `binding_id`.
- An ancestor's container stays registered while its tab is open.
- `SubgraphNavigation` carries the descend case only (`graph_id`, `node_id`) —
  the canvas knows the node, and only the owning tab can build the container.
  Handle it with `@react_on`; `Reveal` does the switching.
- `_relocate` and the `wrapper.redraw()` path go away. `_ensure_drawn`
  ([slot.py:449-458](packages/haywire-core/src/haywire/ui/app/slot.py#L449-L458))
  draws each panel once, on first activation, through the path a document graph
  uses.

### 2. Release a container with its tab

`wrapper.cleanup()` calls `GraphEditor.cleanup()` on tab close
([wrapper.py:696](packages/haywire-core/src/haywire/ui/editor/wrapper.py#L696)).
Unregister the container there when this tab's entry is a `SubgraphContainer`.

A Group tab whose host has closed resolves to nothing, and `on_focus` /
`_update_header` already `force_close()` on that — `_update_header` runs on every
broadcast `GraphDataMutated`, so the stale tab clears itself promptly.

### 3. Keep Group tabs out of the workspace snapshot

`to_snapshot` skips a wrapper on `is_unsaved`
([wrapper.py:62-73](packages/haywire-core/src/haywire/ui/editor/wrapper.py#L62-L73)).
Add `is_transient` to `EditorWrapperState` with a `set_transient()` mutator,
honoured by `to_snapshot`, and set it from `GraphEditor` once the entry is known
to be a `SubgraphContainer`.

Keep the test for it in the slot layer: the slot must not know what a Subgraph is.

### 4. Make a Group tab read as one

The tab interior is editor-owned through `render_tab_into` → `BaseEditor.draw_tab`
([wrapper.py:516-552](packages/haywire-core/src/haywire/ui/editor/wrapper.py#L516-L552)).
Override `draw_tab` on `GraphEditor`: a Group tab shows a Group icon and the
Subgraph label; a document tab keeps its current form. Use `hui.icon.*`, and keep
the method non-raising.

### 5. Scope the edge-draw gate to its own canvas

`_await_client_drawn` resolves the SVG layer by a document-global id
([visual_layer.py:311](barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/visual_layer.py#L311)),
while `connection-svg` is a template literal duplicated once per mounted canvas
([canvas.vue:14](packages/haywire-core/src/haywire/ui/components/graph/canvas.vue#L14)).
The gate must count the paths of the canvas it is loading. The canvas root
carries a unique `:id="containerId"`
([canvas.py:62](packages/haywire-core/src/haywire/ui/components/graph/canvas.py#L62)),
so scope the query to it:

```js
const root = document.getElementById('<containerId>');
const svg = root ? root.querySelector('.connection-svg') : null;
```

[debug_overlay.vue:605-607](packages/haywire-core/src/haywire/ui/components/debug_overlay/debug_overlay.vue#L605-L607)
does the same, by class, for the same reason. Confined to `visual_layer.py`.

### 6. Record the remaining single-canvas assumptions

Add an `.insights/` entry covering the places that resolve DOM globally while N
canvases are mounted, each with its symptom: the `[data-node-id]` marquee sweep
([canvas.vue:2367-2390](packages/haywire-core/src/haywire/ui/components/graph/canvas.vue#L2367-L2390)),
`_cleanupObservers` disconnecting every canvas's observers
([canvas.vue:986-992](packages/haywire-core/src/haywire/ui/components/graph/canvas.vue#L986-L992)),
`SkinFactory` keyed by `node_id` app-wide, `GraphEditor.draw()` clearing
session-wide selection, document-global node/pin/edge ids, and the full-viewport
load overlay.

Include the standing cost: keep-alive holds every open Group in the DOM, and the
Vue page-render walk scales with total element count
([ADR 0006](docs/adr/0006-node-render-performance.md)), so each open Group makes
every interaction fractionally slower. Closing a tab is the release valve.

## Reuse

- `Slot.reveal` — find-or-switch. No new slot API.
- `_ensure_drawn` — first draw on activation. A canvas drawn into a hidden panel
  measures zero size; documents work because `zoom_container._on_ready` defers
  centring to the Vue `transform-changed` signal.
- `BaseEditor.draw_tab` / `render_tab_into` — editor-owned tab interior.
- `to_snapshot`'s `is_unsaved` skip — the shape for an exclusion flag.
- `hui.icon.*`, `hui.icon_action`.

## Verification

Extend `tests/graph_editor/test_subgraph_container.py` and
`tests/graph_editor/test_group_verbs.py`:

- Descending publishes `Reveal` with the container's `binding_id` and label.
- Ascending publishes `Reveal` for the ancestor **and leaves every ancestor
  container registered** — the tabs above are alive and resolve through them.
- Closing a Group tab unregisters its container; closing a document tab leaves
  Subgraphs it never owned alone.
- `to_snapshot` omits a transient wrapper and keeps a normal one.
- `draw_tab` distinguishes a Group tab, and does not raise when the entry is gone.
- `SubgraphNavigation` is handled with `@react_on`.

**Gate** (per [CLAUDE.md](CLAUDE.md)):

```sh
uv run ruff check . && uv run ruff format --check .
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/*/ tests/
uv run pytest -m "not browser and not perf" -q > /tmp/t.log 2>&1; echo "exit=$?"
uv run pytest -m browser -q
```

**Manual** — `uv run haywire`, on a graph slow enough to notice the mount:

1. Collapse a selection and enter the Group; the first entry mounts.
2. Ascend via the breadcrumb, then re-enter. Both are instant.
3. Zoom, pan and selection are preserved per level across switches.
4. The Group has its own tab, reads as a Group, and closes without disturbing
   the host.
5. Close the host with a Group tab open; the Group tab clears itself.
6. Restart; document tabs return and Group tabs do not.
7. With a Group and a large document open, open a third large graph; its load
   overlay releases against its own canvas.
