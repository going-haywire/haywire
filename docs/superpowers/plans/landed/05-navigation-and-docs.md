# Step 5 — Navigation, interface editing, and docs

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The user can collapse a selection from the toolbar, step inside a Group,
edit its interface, step back out, and see errors from inside a closed Group. Plus
the documentation this feature owes.

**Architecture:** Descent is a tab **re-key**, not a new tab: `wrapper.repayload()`
already swaps which container a live tab shows. A Subgraph just needs to be a
`GraphContainer` with a synthetic `binding_id` — which the protocol already
permits. Design record: [graph-nodes.md](../2026-09-14-graph-nodes.md),
decisions 10, 11, 26.

**Tech Stack:** Python 3.12, NiceGUI 3.13, Playwright, pytest.

## Global Constraints

- Line length 109 (`ruff`). CI runs BOTH `ruff check .` and `ruff format --check .`.
- UI rules, tokens and anti-patterns are canonical in
  `docs/reference/design-guide.md`. Follow it; do not invent a second design doc.
- Playwright tests elsewhere than `tests/ui/harness/` must carry
  `@pytest.mark.browser` — see `.insights/project_playwright_asyncio_order_trap.md`.
- A handler that redraws its own container deletes its slot mid-flight. Capture
  `ui.context.client` first — see `.insights/feedback_nicegui_async.md`.

## Pre-Flight Baseline

```sh
uv run ruff check barn/haybale-graph-editor/
uv run mypy barn/haybale-graph-editor/haybale_graph_editor/
uv run pytest tests/ui/ -m "not browser" -q
```

## File Structure

| File | Responsibility |
|---|---|
| `barn/haybale-graph-editor/haybale_graph_editor/protocols.py` | Gains `SubgraphContainer`. |
| `.../editors/graph_editor.py` | Descend / ascend, breadcrumb. |
| `.../editors/graph_canvas/handlers/selection_toolbar.py` | Collapse / expand / enter verbs. |
| `.../editors/graph_canvas/handlers/context_menu.py` | Same verbs in the context menu. |
| `.../editors/graph_canvas/handlers/visual_layer.py` | Event processing for the verbs. |
| `docs/reference/glossary.md`, `docs/adr/0036-*.md`, `docs/architecture/graph/graph-arch.md` | Documentation. |

---

### Task 1: `SubgraphContainer`

**Files:** Modify `barn/haybale-graph-editor/haybale_graph_editor/protocols.py`

- `SubgraphContainer(GraphContainer)` with a synthetic `binding_id`
  (`<host binding_id>#<subgraph key>`). The protocol already allows synthetic
  tokens: *"for an unsaved graph a synthetic token assigned by the source"*
  (`protocols.py:27-29`).
- `save()` delegates to the host entry; `unsaved` reads the host's; `display_name`
  is the Group's label.
- Register it in `GraphAppState` on descent so `GraphEditor` can resolve it by
  `binding_id` like any other container.

- [ ] A `SubgraphContainer` resolves through `GraphAppState` and renders.

### Task 2: Descend and ascend

**Files:** Modify `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_editor.py`

- Descend/ascend by **`wrapper.repayload(binding_id, new_label=...)`**
  (`graph_editor.py:180`) — the same primitive that already re-keys a tab whose
  container was rekeyed elsewhere. One tab throughout.
- A breadcrumb bar built from the descent stack; clicking a crumb ascends to it.
- The tab's dirty dot and Save keep pointing at the **host file**, which is correct
  for Slice 1 because a Group belongs to it. (Slice 2's Macro is the case where
  that stops being true, which is why a Macro opens as its own document.)

- [ ] Descend then ascend returns to the host graph with pan/zoom intact.
- [ ] The dirty dot reflects the host file at every depth.

### Task 3: Toolbar and context-menu verbs

**Files:** Modify `selection_toolbar.py`, `context_menu.py`, `visual_layer.py`

Three verbs, wired at the three sites `dissolve_reroute` already uses
(`selection_toolbar.py:286`, `context_menu.py:669`, `visual_layer.py:730`):

- **Collapse to Group** — on a multi-node selection. Refuses non-convex selections
  with the intervening nodes named and an offer to extend (step 4, Task 1).
- **Expand Group** — on a selected Graph-node.
- **Enter Group** — on a selected Graph-node.

Double-click on a Graph-node is a **secondary accelerator** for Enter. It is
currently unbound on the canvas (the only `dblclick` in the repo is `drag.vue`),
and it is what every comparable editor does — but discoverability rests on the
toolbar button, not the gesture.

- [ ] All three verbs appear only for selections they apply to.
- [ ] A non-convex collapse shows the named reason and the extend offer.

### Task 4: Interface editing and error surfacing

**Files:** Modify the Ports panel path as needed

- Interface editing is the **Ports panel on a boundary node** — it already
  supports drag-to-reorder, with the user's order winning over the author's
  (`glossary.md:60`, commit `1e1957ed`).
- Adding or removing a boundary port reconciles every bound Graph-node, dropping
  edges that lose their port. This is the same reconciliation hot-reload already
  performs when a node class's ports change.
- An error inside a closed Group shows a **badge on the card**; clicking descends
  to the failing node. Free under decision 9 — the executing node *is* the
  on-canvas node, so no id translation is needed.

- [ ] Reordering ports on a boundary node reorders the Graph-node's pins.
- [ ] An error inside a closed Group is visible on the card and navigable.

### Task 5: Documentation

**Files:** `docs/reference/glossary.md`, `docs/adr/0036-*.md`, `docs/architecture/graph/graph-arch.md`, `docs/architecture/execution/assembly/assembly-arch.md`, `docs/components/nodes/node-canon.md`

- **Glossary:** add **Graph-node** (the card), **Subgraph** (the contents, and only
  the contents), **Subgraph Input/Output**, and the three variants **Group** /
  **Macro** (Slice 2) / **Function** (Slice 3). Rewrite the two rows that list
  "Group"/"group collapse" as aliases to avoid (`glossary.md:59,463`) — the word
  now names a Graph-node variant, and `parent_fold`/`is_fold` is what the port
  layer calls its own hierarchy.
- **ADR 0036** (next free number): inlining as the Slice-1 mechanism and why the
  VM needed no change; **Group / Macro / Function** named for mechanism, with
  Abstraction and "Module" both rejected and why; no-recursion as the stated price
  of inlining; boundary nodes as a new `NodeType` rather than EVENT/OUTPUT, and
  why one mixed pair serves both mechanisms; mechanism carried by the kind rather
  than a per-placement config.
- `docs/architecture/graph/graph-arch.md` is a **placeholder** — fill in its
  Subgraph sections rather than adding a new page.
- Fix the `(Future) Cycle detection in data-flow` row in `assembly-arch.md §2.3`:
  it is implemented, in `DataFlowBuilder._check_cycles`
  (`data_flow_builder.py:159-212`), not in `_validate_graph()`.
- `docs/components/nodes/node-canon.md` — a Graph-nodes section.

- [ ] `uv run mkdocs serve` renders with no broken links.

---

## Verification

```sh
uv run ruff check . && uv run ruff format --check .
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/ tests/
uv run pytest -m "not browser and not perf" -q > /tmp/t.log 2>&1; echo "exit=$?"
uv run pytest -m browser -q
```

**Manual** — `uv run haywire`:

1. Build a chain containing a `ControlSwitch` and a `ForLoop`.
2. Select a convex middle section; collapse it from the toolbar.
3. Confirm the card's pins match the crossing edges, with the Switch's two exec
   exits both present.
4. Run the graph; behaviour must be identical to before the collapse.
5. Descend, edit inside, ascend.
6. Expand; the graph is back where it started.
7. Try a non-convex selection; confirm the refusal names the intervening node.

⚠️ `tests/studio/test_docs/test_generate.py` runs `git checkout -- barn/haybale-testing`
in teardown and silently discards uncommitted work there — commit before running the
full suite. See `.insights/project_docs_test_reverts_barn_testing.md`.

## Depends on / unblocks

- Depends on: steps 1–4.
- Unblocks: Slice 2 (Macro), which reuses `SubgraphContainer` and the descent path.
