---
status: current
doc_template: system-reference
scope: How failures on the studio's main pathways reach the error ledger — Refusal vs failure, report_failure and report_loss, the error boundaries, ledger dedup and the studio's safety net
see-also:
  - ../../adr/0061-errors-reach-the-ledger-at-named-boundaries.md
  - ../../reference/glossary.md
  - ../../components/farmhands/farmhand-canon.md
---

# Errors — Architecture

Every failure on the studio's editing, running, load/save, hot-reload and Farmhand pathways, and every detected loss of user work, lands in the **error ledger** with the context to act on it: the Errors editor shows it with its unseen badge, and agents read it through `studio_get_errors`. Expected rejections do not. Inner code keeps raising plain Python exceptions; a short, named list of **error boundaries** records them. The why is in [ADR 0061](../../adr/0061-errors-reach-the-ledger-at-named-boundaries.md).

## 1. Three outcomes

| Outcome | What it is | Where it goes |
|---|---|---|
| **Refusal** | An expected rejection that correct code can reach: bad user input, a stale id after another session's edit, a name collision. Raised as `Refusal`. | Back to the caller (a `False`, a toast with its own message, `[refused] …` for an agent). Never the ledger. |
| **Failure** | Any other exception, `ValueError` included: only a bug or a broken environment reaches it. | The ledger (`ERROR`), then the boundary's own fallback. |
| **Detected loss** | Something of the user's silently dropped, found by a check rather than raised. | The ledger (`WARNING`), via `report_loss`. |

`Refusal` (`packages/haywire-core/src/haywire/core/errors/refusal.py`) subclasses `Exception`, not `ValueError`, so an `except ValueError` never catches one by accident. `FarmhandError` (`packages/haywire-core/src/haywire/core/farmhand/errors.py`) is a `Refusal` with a code, ids and a hint.

**Sorting a raise:** if correct code can reach it, raise `Refusal`; if only a bug can, raise anything else.

## 2. The helpers

Both live in `packages/haywire-core/src/haywire/core/errors/boundary.py` and are exported from `haywire.core.errors`.

```python
try:
    ...
except Exception as e:
    report_failure(e, operation="Apply edit", graph_id=graph.graph_id, action=action.description)
    return False
```

- **`report_failure(exc, *, operation, message=None, severity=ERROR, refusals_fail=False, **context)`**, called in an `except` block:
    - a `Refusal` returns `None`, records nothing and is logged at `INFO` (`"<operation> refused: <message>"`), unless `refusals_fail=True`, which records it like any failure;
    - a `HaywireException` is reused: only its empty `graph_id`, `node_id`, `edge_id`, `registry_key`, `library_identity`, `module_name` and `operation` are filled, so context set closer to the failure wins;
    - anything else is wrapped with `HaywireException.from_exception`. Its `message` is the entry's headline in the Errors list: a boundary that knows its subject names it (`"Could not load graph 'loop.haywire'"`, `"Tool 'x' failed"`); otherwise it defaults to `"<operation> failed"`;
    - other `context` keys go into `details` (path, action, tool, signal, …). The detailed report, in the console and the Errors editor alike, prints `Graph`, `Node`, `Edge` and every `details` entry as `Key : value`;
    - returns the logged `HaywireException`, and never raises.
- **`report_loss(message, *, operation, **context)`** records a `WARNING` entry for a detected loss; it returns the entry, or `None` if recording failed, and never raises.

`HistoryManager.error_context` is merged into the context of its four boundaries. An `Editor` that creates its own history sets `graph_id` there; a history shared by several editors (a Group's interior records on its host's, ADR 0059) carries no `graph_id`, since no single graph is true for all its edits.

`graph_id` context is always the runtime `graph.graph_id`.

## 3. The boundaries

Each boundary calls `report_failure` and then does what it did before: return `False`, continue with the next item, or toast.

| Boundary | Where | `operation` | A `Refusal` |
|---|---|---|---|
| UI safety net (`app.on_exception`) | `packages/haywire-studio/src/haywire_studio/error_hooks.py` `ErrorHooks.on_ui_exception` | `UI handler` | toasted with its own message (logged at `INFO` when there is no client), not recorded |
| Thread, uncaught and asyncio hooks | same file, `_on_thread_exception`, `_on_uncaught`, `on_loop_exception` | `Thread`, `Uncaught`, `Asyncio` | not recorded; the previous hook still runs |
| `Editor` writes | `packages/haywire-core/src/haywire/core/graph/editor.py` `_apply`, `_apply_value`, `reset_nodes`, and the action builds of `split_edge_with_reroute`, `dissolve_reroute`, `expand_group` | `Apply edit`, `Reset nodes` | `False`, not recorded |
| Undo history | `packages/haywire-core/src/haywire/core/undo/history_manager.py` `add_action`, `add_value_action`, `undo`, `redo` | `Apply edit`, `Undo`, `Redo` | edit: `False`, not recorded; undo/redo: recorded (`refusals_fail`) |
| Validation loops | `packages/haywire-core/src/haywire/core/graph/validation.py` node and edge loops | `Validate node`, `Validate edge` | not recorded |
| Signal bus | `packages/haywire-core/src/haywire/core/signals/bus.py` `publish` | `Signal handler` | recorded (`refusals_fail`) |
| Cross-session broadcast | `packages/haywire-core/src/haywire/core/signals/dispatcher.py` `broadcast` | `Signal broadcast` | recorded (`refusals_fail`) |
| Farmhand runner | `packages/haywire-studio/src/haywire_studio/farmhand/host.py` tool call | `Farmhand tool` | rendered `[refused] …` or `[code] …`, not recorded |
| Graph load | `packages/haywire-core/src/haywire/core/graph/base.py` `load_from_dict` (per subgraph, node, edge, and whole), `load_from_file` | `Load graph` | recorded (`refusals_fail`) |
| Graph save | same file, `save_to_file` | `Save graph` | recorded (`refusals_fail`) |
| Hot reload | `packages/haywire-core/src/haywire/core/registry/base.py` `_reload_unmanaged_module`, `registry/component.py` `_notify_registry_subscribers`, `registry/dependency_graph.py` (dependency extraction, relative imports), `registry/folder_scan.py` (class filter) | `Hot reload` | recorded (`refusals_fail`) |
| Update Macro | `barn/haybale-haystack/haybale_haystack/panels/graph/menu/macro.py` `_update_macro` | `Update Macro` | not recorded |

Node build stages, edges, the VM, assembly, library scans and widget and editor construction log their own `HaywireException`s with richer context; a boundary that catches one of those adds nothing twice (see §4).

**Actions.** `ActionBase.execute` and `undo` (`packages/haywire-core/src/haywire/core/undo/base_action.py`) re-raise a `Refusal` unchanged and wrap anything else in `RuntimeError`, so a refusal raised inside an action still reaches the history boundary as a refusal.

**Farmhand.** A failure's error line ends in `(ledger_seq=<n>)`, so the agent can point the user at the entry; `_format_tool_error` in `host.py` renders all three forms.

## 4. The ledger

`ErrorLedger.record` (`packages/haywire-core/src/haywire/core/errors/ledger.py`):

- **Once per object.** An exception already recorded keeps its `ledger_seq`; a second `.log()` is a no-op.
- **Repeats merge while unseen.** `HaywireException.fingerprint()` is `(operation, registry_key, graph_id, node_id, edge_id, category, filename, line_number, message with every digit run replaced by #)`: the same failure raised from another source line is a separate entry. The ledger computes it once, when it first records the exception, and keeps it as `ledger_fingerprint`. A fresh exception matching an unseen entry bumps that entry's `count` and `last_seen_at`, takes its seq and adds no entry. A seen or deleted entry is never merged into: the repeat appears as new. Separately, two boundaries reporting one raised exception (both wrap the same `original_exception` object) are one occurrence: the second adds no entry and no count, whether the entry was seen or not. `HaywireException.log()` prints the full report only for an added entry; a merged repeat logs one DEBUG line, so a failure raised every frame prints once until its entry is seen.
- **A merge notifies no one.** Listeners fire only when an entry is added. This keeps a failing `ErrorLogged` subscriber from feeding itself through the signal bus, and means the Errors editor's `×count` refreshes with the next new entry or triage action.

## 5. The studio's safety net

`ErrorHooks` (`packages/haywire-studio/src/haywire_studio/error_hooks.py`) is built by `HaywireApp`, installed on startup (the loop handler needs the running loop) and uninstalled on shutdown (`packages/haywire-studio/src/haywire_studio/app.py`).

- **UI handlers and timers.** The client is captured first; a failure is recorded with the session's `principal` and `session_id` and the user who triggered it sees "Something went wrong — see Errors". A `Refusal` is toasted with its own message. A toast with no client, or to a deleted one, is dropped.
- **Last resort.** `threading.excepthook`, `sys.excepthook` and the asyncio loop handler record, then call the hook they replaced. `uninstall` restores only hooks still pointing at `ErrorHooks`.

Only the studio app installs these. Core, the CLI and tests never do, so a failure there reaches the ledger only through the boundaries above.

## 6. Adding a boundary

Pick a catch on a pathway in scope whose fallback today swallows a real failure (`logger.error`, an unreported `False`). Keep the fallback, add `report_failure` with an `operation` a user would recognize and the context you hold, and decide whether a `Refusal` there is the user's (default) or a failure (`refusals_fail=True`). Raise `Refusal`, not `ValueError`, for the expected rejections the code below it can reach.
