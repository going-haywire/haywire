---
name: reload-without-history-loses-setup
description: Handoff — a hot reload in a graph with no undo history (a never-opened Group interior, mainly) wipes the user's setup on its nodes silently; record the step on the host's history and warn through the ledger and the card where no history exists
metadata:
  type: project
  status: open
---

# Handoff — A reload in a graph without a history loses the user's setup silently

**Status:** not started. Design discussed and a direction recommended (option (a) below), not
settled with the user. No code, no branch. Raised during follow-up #37 of
`docs/superpowers/plans/2026-10-22-open-follow-ups.md` (branch `fix/follow-ups-a`, 2026-10-22).

## The problem

A hot reload rebuilds every placed node of the reloaded class pristine through `init()` (ADR
0059). The user's setup on those nodes (promotions, setting and port values, grown pins,
label) survives only as an undo step: the validation pass keeps each node's data before the
rebuild and records it on the graph's history.

The step is recorded only when the graph has a history (`BaseGraph.history`, set by an `Editor`
through `BaseGraph.set_history`) and the batch runs on the main thread. Otherwise the setup is
gone, with nothing shown anywhere: no log above debug, no ledger entry, no badge.

`docs/components/nodes/node-canon.md` (§ hot-reload) now states the limits. That is
documentation, not a remedy.

## Where it happens

`packages/haywire-core/src/haywire/core/graph/validation.py` (line refs as of 2026-10-22):

- `:318-325`: a `NODE_HOT_RELOADED` node is captured (`_capture_for_undo`), rebuilt, then
  dropped from the batch if it became a stand-in or its data did not change
  (`_unchanged_by_reload`).
- `:430` `_capture_for_undo`: returns at once when `self._graph.history is None`, so nothing
  is even captured.
- `:454` `_record_reload`: returns when there is no history, and logs at **debug** when the
  batch runs off the main thread (`:459`).

## Which graphs have no history

- **A Group interior that was never opened.** This is the real case. Its `Editor`, sharing the
  host's history, is created only when the interior is opened
  (`barn/haybale-graph-editor/haybale_graph_editor/protocols.py:120`, `SubgraphContainer`).
  Until then the definition graph has `history = None`. ADR 0059 accepted this as a
  consequence (line 32: "A Group whose interior was never opened has no editor … not
  recorded").
- **A Macro's interior** (`barn/builtin/nodes/macro_node.py:~140`, `SyncScheduler`, no editor).
  It is rebuilt from the macro file, but an edited instance ("modified instance", see
  `edit-instance-followups.md`) may hold per-instance setup. See the open question below.
- Graphs built for one task, such as the docs generator (`packaging/docs/extract.py:154`) and
  Farmhand's verify and describe tools (`haybale_studio/farmhands/authoring.py:367`,
  `catalog.py:264`). They hold no user setup, so there is nothing to lose.
- Every graph a user opens in the studio has an editor (`haystack_state.py:273`), on a
  `LoopScheduler`, so it validates on the main thread.

## Options discussed

**(a) Recommended: close the hole, then warn for what is left.**

1. **Record on the host's history.** When the reloading graph has no history of its own, use
   the nearest one up the host chain. A Subgraph definition knows its host
   (`definition._host_graph`, set in `BaseGraph.add_subgraph`, `base.py:368`), and
   `BaseGraph.root_graph` (`base.py:317`) already walks the chain. An opened interior uses the
   host's history anyway (`protocols.py:120`), so undo order stays correct. ADR 0059's
   consequence at line 32 changes to "recorded on the host's history". Undo then rebuilds the
   interior nodes via `RebuildNodesAction(self._graph, …)`, which takes the definition graph,
   so the action needs no change. Check that undo works while the interior is still closed.
2. **Warn where there is still no history**, or the batch ran off the main thread, through
   both channels:
   - **Ledger:** one `HaywireException.create(…, severity=ErrorSeverity.WARNING)` per batch,
     enriched with `graph_id` and the affected node ids, then `.log()`. It appears in the
     Errors editor (unseen badge) and in Farmhand's `studio_get_errors`. A `NodeWarning` does
     **not** reach the ledger: only `HaywireException.log()` records
     (`errors/haywire_exception.py:972-980`). Precedent for a WARNING-severity
     `HaywireException`: `BaseNode._initialize_from_dict` (`node/base.py:344-347`).
   - **Card:** `NodeWarning(kind="reload", message="Rebuilt from new code; its previous setup
     could not be kept for undo")` on each affected node. That gives the existing amber badge,
     and Farmhand's `inspect_node` shows it in `state.warnings`. Nothing branches on
     `NodeWarning.kind` today, so no UI change is needed. Update `NodeWarning`'s docstring,
     which says "compatibility" is the only kind. `NodeWrapper.build()` clears warnings at its
     start, so add the warning *after* the build; it then stays until the next rebuild or
     Reset.
   - To know which nodes were affected without a history, the capture must run anyway
     (today `_capture_for_undo` skips it). Comparing with `_unchanged_by_reload` keeps an
     untouched node from being flagged.

**(b) Warning only.** Keep ADR 0059's decision for Group interiors and add only part 2 of (a).

**(c) Raise an exception. Rejected.** The loss is known only after `build()`. Raising then
restores nothing and aborts the rest of the validation pass (nodes and edges of the batch
left unvalidated). Raising *before* the rebuild would leave the old code running for those
nodes, which defeats hot reload.

## Open questions

- **Macro interiors** have a `_host_graph` too (`host.add_subgraph(definition)` in
  `macro_node.py`), so option (a) part 1 would also record reloads inside a Macro interior
  on the host's history. Is undo of a template-instantiated interior meaningful, or must
  Macro interiors (`definition.template_key is not None`) be excluded? Check against
  ADR 0038 and the edit-instance work.
- Off-main-thread batches: is there still a real path? The studio's graphs use
  `LoopScheduler`. If none remains, the warning there may only be a guard.

## Tests to write

In `tests/core/test_node/test_reload_undo.py` (helpers `_graph_with_editor`, `_printer`,
`_reload` exist):

- A Group interior that was never opened: reload a node inside it, undo on the host's editor,
  and the node's setup comes back.
- A graph with no history: reload a changed node, and the ledger gains one WARNING entry
  naming the node and the node carries a `NodeWarning(kind="reload")`. An untouched node gets
  neither.
- The existing `test_a_graph_without_an_editor_records_nothing` and
  `test_a_reload_validated_off_the_main_thread_records_nothing` change their expectations.

## Docs to update when it lands

- ADR 0059: Decision "Not recorded" list and Consequences (line 32).
- `docs/components/nodes/node-canon.md` § hot-reload: the limits paragraph (written in #37).
- `docs/reference/glossary.md` if a term is added for the reload warning.
