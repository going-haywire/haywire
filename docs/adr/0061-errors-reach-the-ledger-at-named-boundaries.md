---
name: errors-reach-the-ledger-at-named-boundaries
description: Failures on the studio's editing, running, load/save, hot-reload and Farmhand pathways reach the error ledger through report_failure at a short list of named error boundaries; a Refusal marks an expected rejection and stays out; repeats merge into the unseen entry
status: accepted
see-also: ADR-0055, ADR-0059
level: core
---

# Errors reach the ledger at named boundaries

**Context.**

- The error ledger was fed only by `HaywireException.log()`. About 300 `except Exception` sites ended in `logger.error`, which reaches the console only. Every edit (`Editor._apply`), the validation loops, signal subscribers, graph load and save, the Farmhand runner and feature handlers such as Update Macro swallowed real failures that way, and the studio had no global hook: no `app.on_exception`, no `threading.excepthook`, no loop exception handler (handoff `haywire-exception-at-boundaries`, 2026-10-23).
- A boundary could not tell an expected rejection from a bug: refusals were `ValueError` by convention, a `False` return, or `FarmhandError`, and `ValueError` is also what a bug raises.
- Some losses are detected, not raised (a reload without an undo history, backlog #46), and had no channel at all.

**Decision.**

- **The ledger takes failures and detected losses; refusals stay out.** A loss is recorded as a `WARNING`.
- **`Refusal`** (`haywire.core.errors`) is the exception for an expected rejection. It subclasses `Exception`, not `ValueError`, so a converted raise does not change which `except ValueError` blocks catch it. `FarmhandError` subclasses it. Any other exception, `ValueError` included, is a failure.
- **Sorting rule.** A raise that correct code can reach (user input, a stale id after another session's edit, a name collision) becomes a `Refusal`; one only a bug can reach stays a failure. Applied only on the pathways in scope, not repo-wide.
- **Pathways in scope:** editing, running, load and save, hot reload, Farmhand, and the feature handlers on them (Update Macro first).
- **One helper, called in each boundary's `except`.** `report_failure(exc, operation=..., **context)` lets a `Refusal` through (returns `None`), reuses a `HaywireException` and fills only its empty fields, otherwise wraps, enriches and logs; it returns the logged entry and never raises. `report_loss(message, operation=..., **context)` records a detected loss. Each boundary then runs its existing fallback (`return False`, continue, toast).
- **`refusals_fail=True`** records a `Refusal` as a failure. The signal bus and the cross-session broadcast use it (a subscriber has no user to refuse), and so do load, save, hot reload, undo and redo: a stale id or a narrowed promotable met there is a lost piece of the file or an inconsistency, not a user's request turned down; an undo or redo replays recorded history rather than a new request. A refusal `report_failure` lets through is logged at `INFO`.
- **`Editor` writes.** `_apply`, `_apply_value` and `reset_nodes` record a failure and return `False`; a `Refusal` returns `False` unrecorded. The `bool` API is unchanged. `HistoryManager.add_action`, `add_value_action`, `undo` and `redo` are boundaries too: a recorded edit runs inside the history, so it never reaches `Editor._apply`'s own catch. A refused undo or redo is recorded (above).
- **`ActionBase.execute`/`undo` re-raise a `Refusal` unwrapped**; any other exception is still wrapped in `RuntimeError`. Otherwise every refusal raised by an action arrived at the boundary as a failure.
- **Validation loops** record each failing node or edge and continue; nothing new appears on the card.
- **Signal bus:** a failing subscriber is recorded, with no toast, and delivery continues to the rest.
- **Farmhand:** an unexpected failure is recorded and the agent's error line gets `(ledger_seq=<n>)`; a plain `Refusal` renders as `[refused] <message>` and a `FarmhandError` as before, neither recorded.
- **The studio app installs the safety net.** `app.on_exception` records a handler failure with the session's principal and session id and toasts "Something went wrong — see Errors"; a leaked `Refusal` is toasted with its own message and not recorded. `threading.excepthook`, `sys.excepthook` and the asyncio loop handler record, then chain to the hook they replaced. Core, the CLI and tests never install them.
- **Dedup.** A failure whose fingerprint `(operation, registry_key, graph_id, node_id, edge_id, category, filename, line_number, message with digits as #)` matches an unseen entry merges into it: `count` and `last_seen_at` rise, no entry is added, no seq is spent. A seen or deleted entry is not merged into; the repeat is new.
- **A merge fires no ledger listener.** Nothing new appeared, and a listener firing on a merge closes a loop: a failing `ErrorLogged` subscriber is recorded, the record re-broadcasts `ErrorLogged`, the subscriber fails again, once per loop tick, forever.

**Considered.**

- *Throwing `HaywireException` at every failure site.* About 300 sites, and most lack the context a boundary holds (graph, action, tool, principal).
- *`ValueError` as the refusal convention.* A bug raises `ValueError` as readily; a boundary could not record one without recording the other.
- *Result objects for `Editor` verbs*, carrying the refusal message to the caller. Changes every caller of a `bool` API for a message no caller shows today.
- *Per-boundary throttles.* Each boundary would carry its own rule; one dedup in the ledger covers them all.
- *Installing the process hooks from core.* Core also runs in the CLI, the docs generator and tests, where replacing `sys.excepthook` is someone else's business.

**Consequences.**

- The refusal message of an `Editor` verb is dropped: the caller sees `False`.
- A validation failure shows nothing new on the card; it is in the Errors editor and in `studio_get_errors`.
- The dedup key ignores digits in the message, so "Node 3 failed" and "Node 7 failed" at the same place are one entry with `count == 2`; the source location (`filename`, `line_number`) is part of the key, so generic "<operation> failed" messages from different bugs stay apart, and one bug raised from two lines is two entries. Merged repeats keep only the first traceback.
- Because a merge notifies no one, the Errors editor's `×count` refreshes only with the next new entry or a triage action.
- A stale id met during load or hot reload is recorded, even where an edit would have been refused.
- The other `except` sites keep logging to the console; widening the list is a matter of adding a `report_failure` call.
- Backlog #46 is unblocked: its warning is a detected loss, ledger only (`report_loss`); no `NodeWarning`.
