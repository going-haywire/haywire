---
name: subgraph-review-remaining-points
description: Handoff — what the Subgraph (Slice 1) review left open: two unreviewed areas (UX/undo, VM/execution), four small code and doc corrections, and one ADD glyph-metric defect
metadata:
  type: project
  status: open
---

# Subgraph review — what is still open

The Slice-1 Subgraph feature (commit `10500f44`) was reviewed on 2026-09-17/18
in three planned passes: **storage & management**, **UX (actions, editors, undo
history)**, and **graph compilation & execution**. Pass 1 completed and its
findings landed. Pass 3 was covered only where it met the assembly seam. **Pass
2 was never started.**

Everything below is unstarted unless marked otherwise. All the landed work is
uncommitted on `feat/graph-nodes-slice1`.

## 1. UX pass — DONE (2026-09-19)

Reviewed: the level system, `SubgraphContainer`, the collapse/expand round
trip, and instant switching. One defect found, fixed and covered; everything
else held up.

**Fixed: `can_undo()` ignored pending actions — every unfenced edit was
silently un-undoable.** `HistoryManager` holds a fresh action in
`_pending_actions` until something flushes it, but `can_undo()` read only
`history`. `Editor.undo()` gates on that predicate, so it early-returned and
undid nothing; `_update_undo_redo_buttons` reads the same predicate, so the
toolbar button sat disabled too. `HistoryManager.undo()` flushes on its own and
would have worked — only the guard was wrong. Drag and resize place fences and
so escaped it; add node/edge, delete, collapse and expand did not. Pre-existing
and framework-wide, not Subgraph-specific. `can_undo()` now counts
`_pending_actions`, with three regression tests in `test_history_manager.py`.

The suite had fenced around it: `test_group_verbs.py` called `add_fence()`
before asserting `can_undo()`, with a comment reading the behaviour as correct.
That fence is now removed, so the test would catch a regression.

Held up under review:

- **The shared history's forward direction** (the question this doc flagged).
  An undo issued at the document level does reach an edit made inside a Group,
  open or closed — actions carry their own graph reference, so the history is
  graph-agnostic. Verified end to end once the `can_undo()` bug was out of the
  way.
- **`_prune_dead_levels` compares definitions by identity, not by key.** This
  matters: redoing a collapse builds a *new* `SubgraphDefinition` object under
  the *same* key (verified). A key comparison would leave a stale level pointing
  at a dead definition; the identity check closes it correctly.
- **Re-entry keeps the open container**, so a Group keeps its canvas, viewport
  and undo state. The throwaway `SubgraphContainer` that `descend_into` builds
  to compute a level key is harmless — `Editor.__init__` is inert.
- **Instant switching**, covered by `test_graph_hidden_level_edges.py` in the
  browser harness; the hidden-canvas remount path follows the known
  multi-canvas DOM trap correctly.

## 2. Execution pass — partially reviewed

Reviewed: ADR 0036's core argument (crossed, not inlined), `FlatGraphView`, the
crossing vocabulary, and the three workers' hot paths.

Not reviewed:

- Lazy edge propagation across a boundary. ADR 0036 asserts "lazy edges need no
  special handling" — unverified by test.
- A loopback straddling the boundary. ADR 0036 argues it is safe for Groups and
  unsafe for Functions; no test exercises the Group case.
- Callback edges into or out of a Subgraph.
- Behaviour under the threaded scheduler. Every Subgraph test drives the VM
  directly and synchronously (`tests/core/test_assembly/test_flat_view.py:1`
  says so explicitly), so nothing covers a Group in a real scheduler thread.

## 3. Code corrections — small, known, unstarted

**`NodeData.behavior`'s docstring is wrong for one subclass.**
`packages/haywire-core/src/haywire/core/node/data.py:105` says *"Node behavior
flags (read-only, from class)"*. `GraphNode` overrides the property to derive
`node_type` per instance (`graph_node.py:240`), which is the only per-instance
`behavior` in the codebase. Either widen the base docstring or note the
exception. The sibling lines 100 and 110 (`identity`, `library`) are accurate.

**`ADD`'s filled outlet glyph draws inset.** `add.py:56` declares
`icon_in="add_circle_outline"` and `icon_out="add_circle"`. Measured in the
browser harness: with identical CSS (`right: -13px`), identical 18px box, a
`circle` pin centres at +0 from the card edge and an `add_circle` pin at +10.
So a growing slot on an **outlet** side reads visibly inside the card, while the
same slot on an inlet side sits correctly. Predates this work and is shared with
`AddPortTestNode`. `tests/ui/harness/test_boundary_skin.py` documents the
tolerance (`_TOLERANCE = 12`) rather than absorbing it silently — tighten that
constant once the glyph is fixed.

**No rename verb exists anywhere.** ADR 0036 settles that an interface port's
**label** may be changed and its **id** may not, but the pin menu
(`barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/port/port.py`)
has Edit / Type / Widget / Reset / Set-to-none / Detach / Remove and no rename
row. The removal row already appears on an interface port, because it gates on
`is_user_removable()` and those ports are now `RESOLVED`. Rename needs both a
verb and a menu row before the decision is reachable by a user.

**`docs/components/nodes/node-canon.md` does not mention the growing slot.**
The ADR and the glossary both do. The canon is where a node author would look.

## 4. A trap worth writing up

A bare `rejig()` flags **every** port for removal, so it drops a boundary node's
growing slot along with the interface. It bit twice in one session: once in
`_BuildSubgraphAction._build_boundary` (fixed there by re-adding the slots
explicitly) and once in the harness fixture (fixed with
`rejig(exclude=r"^slot_")`). Any future code that rebuilds a boundary node's
ports will hit it a third time. Candidate for `.insights/`.

## 5. Not a code change — check before committing

`graphs/10x64n_sub.haywire` is modified in the working tree (832 insertions,
335 deletions). The diff is port values and `modified_at`, i.e. a manual studio
session, not a code change. Decide whether it belongs in the commit.

## What landed, for context

Pass 1 produced six fixes, all verified (full gate: 5434 non-browser + 135
browser, 0 failures):

- paste shared one `SubgraphDefinition` between two cards — fixed, plus the
  nested case, where `instantiate()` dropped the inner `subgraphs` table.
- `StructuralValidator.validate_subgraph_contents` was dead code while a comment
  in `flow_assembly_manager.py` claimed it ran — now wired, with the one-card
  invariant beside it.
- a dangling `subgraph_key` was silent — now reported on the card.
- the tree-wide id scan moved from per-mint to an assertion in `add_subgraph`.
- `on_assembly()` added as a lifecycle hook; the three Subgraph workers now
  cache their crossings and port pairs there.
- `reassemble_dirty_flows` and `mark_flow_dirty` deleted (no production caller;
  revisit when incremental reassembly is wanted).

ADR 0036 was rewritten to cover the interface-ownership design settled in the
inquisition, and `docs/reference/glossary.md` gained **Growing slot**,
**Interface port** and **Interface reconcile**.
