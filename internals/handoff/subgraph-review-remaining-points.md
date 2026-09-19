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

## 2. Execution pass — DONE (2026-09-19)

Reviewed earlier: ADR 0036's core argument (crossed, not inlined),
`FlatGraphView`, the crossing vocabulary, and the three workers' hot paths.
This pass covered the four remaining items; all now have tests in
`tests/core/test_assembly/test_subgraph_execution_edges.py`.

Held up as the ADR claims:

- **Lazy edges across a boundary.** A card's `_execute` drains the pull before
  the crossing is taken, so the Subgraph Input copies a resolved value. Covered
  in both directions (lazy into the card, lazy out of it).
- **A loop straddling the boundary.** The inlined control graph spans host and
  Subgraph, so the loopback push and pop land in the same local list. A
  ForLoop whose body runs inside a Group assembles into one flow and
  terminates.
- **The threaded scheduler.** A control Group runs to completion through it.

**Found: `is_lazy` did not reach the live pipe.** A `Pipe` copies `is_lazy` at
construction and the setter only wrote the flag, so toggling an edge to lazy in
the studio had no effect until some later structural change happened to touch
the same outlet — order-dependent and silent. Not Subgraph-specific. Fixed in
the setter; regression tests in `tests/core/test_edge/test_edge_lazy_toggle.py`.

**Found: collapse could mint a CALLBACK interface port.** Callbacks cannot
cross a boundary at all — the subscription travels as a port value pooled on
the sink keyed by that edge, and no relay can be written (see the new ADR 0036
section for the full argument, settled by inquisition). `CollapseToGraphNodeAction`
now refuses a selection a callback edge crosses, in either direction. The
growing slot needed no change: it is `FlowType.DATA`, so formal edge validation
already rejects a callback into it. Those are the only two paths that create an
interface port.

Also corrected: `_validate_callback_edge`'s docstring blamed a wiring-time read
in the assembly manager, which is not what happens. The rule is right; its
stated reason was not.

## 3. Code corrections

**`NodeData.behavior` — DONE (2026-09-19).** Settled by inquisition as a
missing contract rather than a stale sentence, then made structural: `behavior`
is instance state, stamped from `class_behavior` at construction, with
`set_node_type()` the one guarded write (it replaces the frozen dataclass,
touching `node_type` alone). `GraphNode` sheds the property override, the
`_behavior=None` sentinel and `_derive_behavior`.

Worth knowing: the old property's `None` fallback was load-bearing, not a
guard — it re-derived on every read, which is how an unbound card reported
DATA. `reconcile_interface` returns early with no Subgraph bound, so stamping
only there regressed an unbound card to CONTROL. `init()` stamps too.

Glossary corrected: NodeType is declared by the decorator, not "determined by
its EXEC port configuration"; and "immutable" is not "per class".

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

**`node-canon.md` growing-slot section — DONE (2026-09-19).** Added alongside
the `rejig` filter rule, since the two are the same subject from a node
author's side.

## 4. The `rejig()` trap — DONE (2026-09-19)

A bare `rejig()` flags **every** port, so it dropped a boundary node's growing
slot along with the interface it was rebuilding — silently, and twice in one
session, with two different ad-hoc fixes.

Closed by giving the filters what they were missing: `include`/`exclude` now
take a list of OR'd criteria — exact ids, `PortOrigin` values, compiled
patterns — so one call can say "rebuild the interface, keep what the node
declared". Both sites now use `exclude=[PortOrigin.DECLARED]`, and
`_build_boundary` sheds its manual snapshot-and-re-add.

Match by **origin, not id pattern**, where the distinction is ownership:
`^slot_` holds only while the naming convention does.

The bare form stays sharp deliberately — "flag everything" is predictable,
where "flag everything except a category you have to know about" is not. No
`.insights/` entry: the rule belongs in `rejig()`'s docstring, which now leads
with it (*flag only what this call owns*) and names both cases that need a
filter. `node-canon.md` carries the same rule.

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
