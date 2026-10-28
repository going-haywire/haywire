---
name: draw-performance-regression-fix
description: Handoff — opening the 512-node graph got ~5 s slower (17 s → 22 s) at edd6ee50, where _claim_session_state started clearing the selection and publishing SelectionMoved; NodeWriteGate and the canvas.vue lookup scoping are cleared
metadata:
  type: project
  status: done
---

# Handoff — draw-performance regression: the selection clear in `_claim_session_state`

**Resolved 2026-10-20** on branch `fix/session-lifetime-and-large-graph-load`. The hypothesis held: `_clear_selection` published `SelectionMoved` even when the selection was already empty, and every subscribing panel redrew for it during the load. It now publishes only when it cleared something (`90542797`). Metric A on the 512-node graph went from 23.0 s to 16.7 s; the same branch then took it to about 12 s in Chrome and Firefox (edges after nodes, a measure-then-draw edge batch, and id lookups that Firefox does not turn into subtree scans). The 17 s baseline item below (step 5) was not part of the fix; what remains of the load is the per-message Vue render walk.

**Status (original):** diagnosed by bisection on 2026-10-16. The mechanism is not yet proven and nothing is fixed. The work is on branch `feat/editor-modes-slice1` (head `83a65e8f`, slice 5a squashed). It does not block slice 5b.

Line references are from 2026-10-16. Check them before you rely on them.

## Symptom

Opening `graphs/10x512n_5x448e.haywire` (512 nodes with ~10 inlets and outlets each, 2688 edges) takes about 22 s, from clicking the graph in the Haystack until every edge is drawn. Before slice 2 it took about 17 s.

## Measurements

These are the minimum of 3 warm runs in headless Chromium at 1600x900. Metric A is load to all edges drawn. Metric B is one `_relayoutEdges()`.

| Commit | What | A (ms) | B (ms) |
|---|---|---|---|
| `cfda8ef8^` | before the write gate | 16,760 | 810 |
| `cfda8ef8` | `NodeWriteGate` on widgets (slice 1) | 16,766 | 799 |
| `28ddd3a2` | last commit before the step | ~17,000 | — |
| **`edd6ee50`** | **the step** | **~22,400** | — |
| `c077de9a` | slice-1 head before slice 5a | 22,219 | 783 |
| `2b9fc5fd`* | 5a, before the lookup scoping | 21,794 | 774 |
| `4341187d`* | 5a, canvas.vue lookups scoped to `this.$el` | 22,125 | 807 |
| `83a65e8f` | current head (5a squashed) | 22,598 | 824 |

\* These are in the pre-squash 5a history, which lives under tag `editor-modes-slice5a-full`.

The bisection covered all 60 commits between `cfda8ef8` and `c077de9a`, one 3-run measurement each.

## Cleared suspects

- **`NodeWriteGate`:** `UINode._apply_write_gates` runs 512 times per load, about 3 ms in total, and metric A is unchanged with and without it.
- **The canvas.vue lookup scoping (5a-3):** about 375k id lookups per load. Moving from `document.getElementById` to `this.$el.querySelector('[id="…"]')` adds about 0.3 s, which is within noise. A `getElementById` with a `this.$el.contains()` check plus a fallback was tried on `83a65e8f` and saved nothing measurable, so keep the scoping as it is.

## Suspect: `edd6ee50`, "a focus that moves the active graph clears the selection"

`GraphEditor._claim_session_state` (`barn/haybale-graph-editor/haybale_graph_editor/editors/graph_editor.py`) now calls `_clear_selection(context)` whenever the session's `active_graph` changes. That publishes `SelectionMoved`. It also replaced the explicit clears in `_switch_level` and `_repoint_level`, and `draw()` now uses `_clear_selection`.

The hypothesis is that during a load `_claim_session_state` runs many times, or the clear runs while the canvas is still streaming nodes. Each `SelectionMoved` then makes its subscribers redraw: properties, ports, the selection toolbar, minimap and other panels. Each redraw is a server message, and every server message rebuilds the whole page's VNode tree (`.insights/project_nicegui_component_vs_native_tag.md`). The cost would therefore grow with the number of elements on the page.

This is unproven. The bisection only shows that this commit holds the step.

## Next steps

1. Count `_claim_session_state` calls, `_clear_selection` calls and `SelectionMoved` publications during one load of the 512-node graph. Time each `SelectionMoved` subscriber, using a timing wrapper like the one in `.scratch/draw-perf/run_studio.py`.
2. Fix it with the smallest change the count supports, for example:
   - publish `SelectionMoved` only when the selection was non-empty (an empty selection clearing to empty changes nothing);
   - or skip the claim/clear while a level is being mounted or loaded.
3. Keep the behaviour `edd6ee50` fixed: a selection made on a locked placement level must not survive a focus or level switch into an unlocked graph. The tests in `tests/graph_editor/test_graph_editor_levels.py` and `tests/graph_editor/test_graph_editor_placement_levels.py` cover it.
4. Pin the fix with a test that counts `SelectionMoved` during a load. Re-measure with `.scratch/draw-perf/bis.sh <sha>`; the target is about 17 s.
5. The ~17 s baseline is its own, older problem: the Vue full-tree walk per server message (memory: large-graph perf). It is out of scope here.

## Harness

`.scratch/draw-perf/`; see its `README.md`. The bisect scripts (`bis.sh`, `runall.sh`, `measure.py`) and raw
results were removed on 2026-10-28, once this was resolved; recover them from git history. In short, they did:
- create a worktree with `git worktree add --detach .scratch/draw-perf/c2 <sha>`, then run `uv sync` in it;
- then run `.scratch/draw-perf/bis.sh <sha>`.

It runs its own studio on port 8191 with a scratch HOME. Stop any other studio on 8191 first.
