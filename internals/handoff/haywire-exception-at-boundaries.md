---
name: haywire-exception-at-boundaries
description: Handoff — make every error on the main editing and running pathways of the studio land in the error ledger as a HaywireException, by converting at a short list of central boundaries instead of throwing HaywireException at every failure site
metadata:
  type: project
  status: landed
---

# Handoff — HaywireException at the boundaries

**Status:** **landed** 2026-10-26 on branch `fix/follow-ups-e` (backlog #47). Settled by an
inquisition (2026-10-26); decision and rationale in
[ADR 0061](../../docs/adr/0061-errors-reach-the-ledger-at-named-boundaries.md), current design in
[`docs/architecture/errors/errors-arch.md`](../../docs/architecture/errors/errors-arch.md). The
text below is the pre-design record.

**Released:** [`reload-without-history-loses-setup.md`](reload-without-history-loses-setup.md)
(open question 4 settled: a detected loss goes to the ledger only, `report_loss`).

**Raised during:** follow-up #21 of `docs/superpowers/plans/2026-10-22-open-follow-ups.md`
(Update Macro's `open_macro_with` failing reaches only the console and a toast).

## Goal

Every error that happens while a user (or an agent) edits or runs a graph in the studio is
recorded in the error ledger (`haywire.core.errors.ledger.ErrorLedger`) as a
`HaywireException`. That makes it visible in the Errors editor (unseen badge) and to agents
through Farmhand's `studio_get_errors`, with the context needed to act on it (graph, node,
action, tool).

**Not the goal:** wrapping every failure in a `HaywireException`. Inner code keeps raising
plain Python exceptions; a short, named list of boundaries converts them.

## How errors are handled now (2026-10-23)

- **About 300 `except Exception` sites:** haywire-core `core/` ~150, `ui/` ~50, graph-editor
  ~45, haystack ~16, haywire-studio ~21, haybale-studio ~12. Most end in
  `logger.error`/`warning`, which goes to the console only.
- **The ledger is fed only by `HaywireException.log()`**
  (`core/errors/haywire_exception.py:971-980`). Raising one records nothing; a `NodeWarning`
  never reaches the ledger. `.log()` call sites today, by file:
  - `core/node/node_wrapper.py`, `core/node/base.py` (build stages, settings-format warning)
  - `core/edge/edge_wrapper.py`
  - `core/execution/vm.py`, `core/assembly/flow_assembly_manager.py`
  - `core/library/base.py`, `core/state/container.py`
  - `ui/widget/factory.py`, `ui/editor/wrapper.py`, `ui/keymap/keymap.py`
  - `haybale_graph_editor/editors/graph_canvas/ui_node.py`
- **Central pathways that do not reach the ledger:**

  | Boundary | Where | Today |
  |---|---|---|
  | Every edit | `Editor._apply` / `_apply_value`, `core/graph/editor.py:~443` | `logger.error`, `return False` |
  | Validation pass, node and edge loops | `core/graph/validation.py:358`, `:393` | `logger.error` (the node build stages inside do log) |
  | Signal subscribers | `core/signals/bus.py:106`, `dispatcher.py:89` | `logger.exception` / `warning`, continue |
  | UI handlers, timers | NiceGUI | **no global hook**: no `app.on_exception`, no `threading.excepthook`, no loop exception handler anywhere |
  | Farmhand tool calls | `haywire_studio/farmhand/host.py:74` `_format_tool_error` | formatted for the agent; not in the ledger unless the tool logged it |
  | Graph file load | `BaseGraph.load_from_file`, `core/graph/base.py:~1284` | catches everything, `logger.error`, `return False` |
  | Feature handlers | e.g. Update Macro, `haybale_haystack/panels/graph/menu/macro.py:244-253` | `logger.warning` + toast |

- **Already converted:** node build stages, edges, the VM, assembly, library scan and hot
  reload, widget and editor construction.

## Proposed strategy (to be settled)

1. **Inner code raises plain exceptions** (`ValueError`, `KeyError`, …) or returns its
   refusal. It builds a `HaywireException` only where it holds context no boundary has (the
   node build stages are the model).
2. **A named list of boundaries converts.** Each one catches, wraps with
   `HaywireException.from_exception(e, operation=…)`, enriches with what it knows
   (`graph_id`, `node_id`, action description, tool name), calls `.log()`, then runs its
   existing fallback (return `False`, toast, continue with the next subscriber). Candidates:
   the rows of the table above, plus `threading.excepthook` and the asyncio loop's exception
   handler as the last resort.
3. **Refusals are not errors.** Expected outcomes (unsaved edits, missing permission,
   invalid input, a level-mode refusal) are not ledger entries. They need one recognizable
   form that boundaries let through. Existing forms: `ValueError` by convention, `False`
   returns, `FarmhandError` (agent-facing, `core/farmhand/errors.py`).
4. **No double entries.** A boundary that catches a `HaywireException` enriches and logs it
   but never wraps it again; `ErrorLedger.record` is already idempotent per object.
5. **The local catches stay** where they are deliberate fallbacks. Convert only those on
   the main pathways that swallow a real failure silently (`logger.debug`, an unreported
   `False`).

## Open design questions

1. **Refusal type.** Introduce a `Refusal` exception (boundaries skip the ledger), or keep
   refusals as `ValueError`/`False` and accept that a boundary cannot tell a refusal from a
   bug? How does it relate to `FarmhandError`?
2. **The UI safety net.** `app.on_exception` in the studio app (haywire-studio) catches what
   handlers and timers leak. What context can it add (session, principal, active editor)?
   Does it also show a toast, or only record?
3. **Flood control.** A validation or signal failure can repeat every frame or every
   publish. Runtime errors already throttle (only the first after a clear redraws,
   `NodeWrapper._add_runtime_error`). The ledger needs the same, or a dedup key.
4. **Detected conditions, not caught exceptions.** Some losses are detected, not raised:
   a reload without an undo history (the blocked handoff), a stand-in edit lost at save
   (backlog #45), a special skin meeting a node it cannot draw (the Inset's message in
   the card, `haybale_graph_editor/skins/inset_skin.py`, backlog #4; it draws on every
   redraw, so a ledger entry needs dedup). Do they go to the ledger as `HaywireException.create(...,
   severity=WARNING)`, to the card as `NodeWarning`, or both? One rule for all of them.
5. **Threads.** `.log()` already runs from watchdog and timer threads (the ledger has a
   lock). Does a boundary off the main thread need anything more?
6. **Farmhand.** Should a tool call's internal error also be logged to the ledger, or is
   the error returned to the agent enough? Agents read `studio_get_errors`, so logging makes
   failures visible across calls.
7. **Inventory scope.** Which "main pathways" count: editing, running, load and save,
   hot reload, Farmhand? Settle the list, then audit only those for silent swallows.

## Suggested order once settled

1. ADR plus the refusal convention.
2. The UI safety net (one hook covers the most ground).
3. `Editor._apply` and the validation loops.
4. Signal subscribers, the Farmhand runner, load and save.
5. Feature handlers on the main pathways (Update Macro first; see #21).
6. Release the held reload handoff with the answer to question 4.

## Related

- Backlog #21: fixed minimally (the empty entry is closed); its error stays a `ValueError`
  until this lands.
- Backlog #45 (stand-in edits lost at save): question 4 applies.
- `.insights/feedback_nicegui_async.md`: handler and slot-stack rules a UI hook must
  respect.
