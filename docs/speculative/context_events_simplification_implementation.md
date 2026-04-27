# Implementation plan: bus split (`ContextChangedEvent` → `ContextSignal` + `RevealRequest`)

> Status: actionable plan. Companion to
> [context_events_simplification.md](context_events_simplification.md), which holds
> the design rationale (§§1–11). This file holds the *how*; the design doc holds
> the *why*.
> Date: 2026-04-27, branch `code_refactoring_squashed`.

## Locked decisions (Q1–Q9 from inquisition)

| # | Decision | One-line rationale |
| --- | --- | --- |
| Q1A | Single PR with framework → emit sites → filter sites → delete; ~20+ files; intermediate states must compile and pass tests for already-migrated surface | No shipped dual API; reviewable staging |
| Q2A | One file: `context_events.py` renamed to `context_signals.py`; holds `ContextSignal`, `Subject`, `RevealRequest`, predicates, the 9 core signal classes | Closed core vocab is small + tightly coupled; library authors just import the base from a stable path |
| Q3A | `session.signal(signal_obj)` and `session.reveal(reveal_request_obj)` — two methods on `Session`, each takes one struct arg | Method-name asymmetry is the channel-split cue; struct args make tests assert cleanly |
| Q4A | Lean on existing `LibraryIdentity.dependencies` for cross-library subscription; no `__instancecheck__`, no AST inspection | Mechanism already exists; no cross-library subscriptions today; YAGNI |
| Q5D | One-paragraph note in `LibraryIdentity.dependencies` field comment + `ContextSignal` class docstring; both ship in this PR | Co-located with the API surface authors actually touch |
| Q6B | EDITOR_FOCUSED sites → single `session.reveal(...)` line; reveal-bundling sites with a real change_type → two-line `signal()` + `reveal()` | §11 audit table is canonical; PR description cites it |
| Q7A | Tests migrate lockstep with production code per Q1A step; framework-level behaviors (cross_session routing, subject stamping, signal/reveal ordering) get new unit tests written first within step 1 | Pragmatic; preserves find-and-replace; latent-bug-flip tests get explicit checklist items |
| Q8A | Two callbacks on `Session` (`_signal_callback`, `_reveal_callback`) bound by AppShell; cross-session broadcast triggered inside `Session.signal()` when `type(s).cross_session` is True | Smallest delta from today's `_orchestrator_callback`; keeps cross-session out of the UI layer |
| Q9A | Drop `ContextChangedEvent.detail`; signals carry typed fields per-class; only `GraphRemoved(entry_id: str)` has inline payload | Typed-class vocabulary's whole point is no escape hatches |

---

## Step 1 — Framework first

Land the new vocabulary alongside the old. Both APIs work. No call site is migrated yet.

### Files touched (~6)

- `packages/haywire-core/src/haywire/ui/context_signals.py` *(new — replaces `context_events.py`)*
- `packages/haywire-core/src/haywire/ui/session.py`
- `packages/haywire-core/src/haywire/ui/session_manager.py`
- `packages/haywire-core/src/haywire/ui/app/shell.py`
- `packages/haywire-core/src/haywire/core/library/identity.py` *(docstring only)*
- `tests/ui/test_context_signals.py` *(new)*

### What lands

1. **Rename `context_events.py` → `context_signals.py`.** The old `ContextChangedEvent` and `ContextChangeType` stay in place inside the renamed file (they get deleted in step 4). Update the file's existing imports.
2. **Add the new vocabulary in `context_signals.py`:**
   - `Subject` — frozen dataclass with `peer_id: Optional[str]`. `Subject.SELF` is a sentinel singleton (`peer_id=None`); `Subject.peer(session_id)` is a factory.
   - `ContextSignal` — frozen dataclass base. Instance field: `subject: Subject = Subject.SELF`. ClassVar: `cross_session: ClassVar[bool] = False`. Methods: `is_local()`, `is_from_peer()`. Class docstring carries the §7.5 cross-library-subscription note (Q5D).
   - The 9 core signal classes (per §11): `ActiveGraphMoved`, `ActiveFileMoved`, `ActiveLibraryMoved`, `ActiveComponentMoved`, `LibraryCatalogChanged` (`cross_session=True`), `SelectionMoved`, `GraphDataMutated` (`cross_session=True`), `GraphRemoved(entry_id: str)` (`cross_session=True`), `ThemeMoved`.
   - `RevealRequest` — frozen dataclass with `editor: type[BaseEditor]`, `payload: Optional[str] = None`, `label: Optional[str] = None`.
3. **Wire new methods into `Session`:**
   - `_signal_callback: Optional[Callable[[ContextSignal], None]] = None`
   - `_reveal_callback: Optional[Callable[[RevealRequest], None]] = None`
   - `set_signal_orchestrator(cb)` / `set_reveal_orchestrator(cb)` — separate from the existing `set_orchestrator` (which stays for now).
   - `signal(s: ContextSignal) -> None` — calls `_signal_callback(s)`; if `type(s).cross_session`, *also* calls `self._session_manager.broadcast_signal(s, origin=self.session_id)`.
   - `reveal(r: RevealRequest) -> None` — calls `_reveal_callback(r)`. Local only; no broadcast.
4. **Add `SessionManager.broadcast_signal(signal, origin_session_id)`** — peer-stamps subject:
   ```python
   def broadcast_signal(self, signal: ContextSignal, origin_session_id: str) -> None:
       for session_id, session in list(self._sessions.items()):
           try:
               delivered = signal if session_id == origin_session_id \
                           else replace(signal, subject=Subject.peer(origin_session_id))
               session._dispatch_signal(delivered)
           except Exception as e:
               logger.warning(...)
   ```
   The existing `broadcast(event)` stays for now — it's still called by old emit sites.
5. **Add `AppShell._on_signal(s)` and `AppShell._on_reveal(r)`** alongside the existing `_on_context_changed(event)`. `_on_signal` runs the per-slot poll/draw loop with the new signal; `_on_reveal` calls the existing `_reveal_editor` logic. AppShell's `__init__` registers both new callbacks plus the old one.
6. **Add slot.handle_signal(s)** alongside existing `slot.handle_context_event(event)`. Polls editors with the new signal; calls draw if poll returns True. Same shape as today's handler.
7. **Update `BaseEditor.poll` signature in the docstring** (not the runtime — that comes in step 3) to mention both forms accept either ContextChangedEvent or ContextSignal during migration.
8. **Update `LibraryIdentity.dependencies` comment** (`packages/haywire-core/src/haywire/core/library/identity.py:18-19`) per Q5D.
9. **Write `tests/ui/test_context_signals.py`** — covers:
   - `ContextSignal` is frozen, default subject is SELF, `cross_session` defaults False
   - `is_local()` / `is_from_peer()` predicates
   - `Subject.SELF` is singleton; `Subject.peer(id)` produces equal subjects for equal ids
   - `Session.signal(s)` calls the registered callback once for `cross_session=False` signals; calls callback + triggers broadcast for `cross_session=True`
   - `SessionManager.broadcast_signal` stamps `peer(origin_id)` on non-origin sessions, leaves origin as SELF
   - Signal/reveal ordering: `session.signal(s)` returns before `session.reveal(r)` runs; reveal observes post-signal context
   - `RevealRequest` is frozen; equality works as expected for test assertions

### Done when

`uv run pytest -m "not integration"` is green; all 11 existing test files still pass (they use the old API, which still exists); the new test file passes.

---

## Step 2 — Migrate emit sites

Rewrite every `notify_context_changed` and `notify_cross_session_context_change` call site to use the new API. Old API still exists but is no longer called from production code.

### Files touched (~12 production + corresponding test files)

Production:
- `packages/haywire-core/src/haywire/ui/app/shell.py` (1 emit)
- `packages/haywire-core/src/haywire/ui/app/tab_slot.py` (1 emit — WORKSPACE_CHANGED, this just deletes per Q6A)
- `packages/haywire-core/src/haywire/ui/app/icon_slot.py` (1 emit — same, delete)
- `packages/haywire-core/src/haywire/ui/graph_canvas/handlers/selection.py` (1 emit)
- `packages/haywire-studio/src/haywire_studio/haystack.py` (1 emit)
- `barn/haybale-core/haybale_core/panels/context_menu/create_node_panel.py` (1 emit — splits per Q6B; respects §8.6 byte-stable promise)
- `barn/haybale-studio/haybale_studio/editors/file_browser.py` (3 emits)
- `barn/haybale-studio/haybale_studio/editors/file_viewer.py` (1 emit)
- `barn/haybale-studio/haybale_studio/editors/graph_editor.py` (~6 emits)
- `barn/haybale-studio/haybale_studio/editors/haystack_editor.py` (~9 emits)
- `barn/haybale-studio/haybale_studio/editors/library_browser_editor.py` (1 emit — splits per Q6B)
- `barn/haybale-studio/haybale_studio/editors/library_overview_editor.py` (~3 emits)
- `barn/haybale-studio/haybale_studio/editors/library_component_editor.py` (1 emit)
- `barn/haybale-studio/haybale_studio/editors/node_source_editor.py` (1 emit)

Tests: corresponding test files migrate alongside (Q7A — lockstep).

### Rewrite rules (per Q6B)

| Today's site | New form |
| --- | --- |
| `notify_context_changed(ContextChangedEvent(EDITOR_FOCUSED, reveal_editor=X, reveal_payload=Y, reveal_label=Z))` | `session.reveal(RevealRequest(editor=X, payload=Y, label=Z))` — single line, no signal |
| `notify_context_changed(ContextChangedEvent(<change_type>, reveal_editor=X, ...))` with real change_type | `session.signal(<MappedSignal>())` then `session.reveal(RevealRequest(...))` — two lines |
| `notify_context_changed(ContextChangedEvent(<change_type>))` with no reveal | `session.signal(<MappedSignal>())` — single line |
| `notify_cross_session_context_change(ContextChangedEvent(DATA_MUTATED))` | `session.signal(GraphDataMutated())` — single line; routing comes from class-level `cross_session=True` |
| `notify_context_changed(ContextChangedEvent(WORKSPACE_CHANGED))` (slots) | Delete the line. `on_focus` already fires (verified §5). |

State-mutation lines (`context.active_graph = ...`) stay byte-identical above the emit lines — they were never on the bus.

§11 mapping table is the canonical reference for which signal class each old change_type maps to.

### Done when

`uv run pytest -m "not integration"` is green. Production code no longer references `notify_context_changed`, `notify_cross_session_context_change`, `ContextChangedEvent`, or `ContextChangeType`. Old API methods on Session still exist (deleted in step 4) but are unused.

---

## Step 3 — Migrate filter sites

Rewrite every `event.change_type in {...}` filter in editor `poll()` methods to `isinstance(signal, (...))`.

### Files touched (~7)

Production (per §11 audit):
- `barn/haybale-studio/haybale_studio/editors/properties_editor.py:73-80`
- `barn/haybale-studio/haybale_studio/editors/node_source_editor.py:54-97`
- `barn/haybale-studio/haybale_studio/editors/library_component_editor.py:53-56`
- `barn/haybale-studio/haybale_studio/editors/library_browser_editor.py:54`
- `barn/haybale-studio/haybale_studio/editors/library_overview_editor.py:100`
- `barn/haybale-studio/haybale_studio/editors/code_editor.py:108`
- `barn/haybale-studio/haybale_studio/editors/haystack_editor.py:84-87`

Plus orchestrator branch:
- `packages/haywire-core/src/haywire/ui/app/shell.py:588` (the `if event.change_type == ContextChangeType.GRAPH_REMOVED` branch becomes `if isinstance(signal, GraphRemoved)`; reads `signal.entry_id` instead of `event.detail` — single-line tweak per Q9A).

Tests migrate alongside.

### Rewrite rules

| Today's filter | New form |
| --- | --- |
| `event.change_type == ContextChangeType.X` | `isinstance(signal, MappedSignal)` |
| `event.change_type in (ContextChangeType.X, ContextChangeType.Y)` | `isinstance(signal, (MappedSignal1, MappedSignal2))` |
| `event.change_type in self._RELEVANT_EVENTS` (frozenset) | Replace `_RELEVANT_EVENTS` frozenset with a tuple of signal classes; filter becomes `isinstance(signal, self._RELEVANT_SIGNALS)` |
| Filters today matching `LIBRARY_STATE_CHANGED` | Match *both* `ActiveLibraryMoved` and `LibraryCatalogChanged` (per §11.2 editorial decision #6 — widen during migration; tighten as a separate post-migration pass if desired) |

`BaseEditor.poll` signature changes: `event: ContextChangedEvent` → `signal: ContextSignal`. The parameter rename is part of this step.

### Done when

`uv run pytest -m "not integration"` is green. No production code references `event.change_type`, `ContextChangeType`, or `ContextChangedEvent` for filtering. `BaseEditor.poll`'s parameter is named `signal` everywhere.

---

## Step 4 — Delete old API

### Files touched (~3)

- `packages/haywire-core/src/haywire/ui/context_signals.py` — delete `ContextChangedEvent`, `ContextChangeType`
- `packages/haywire-core/src/haywire/ui/session.py` — delete `notify_context_changed`, `notify_cross_session_context_change`, `_orchestrator_callback`, `set_orchestrator`
- `packages/haywire-core/src/haywire/ui/session_manager.py` — delete the old `broadcast(event)` method (the new `broadcast_signal` replaces it)
- `packages/haywire-core/src/haywire/ui/app/shell.py` — delete `_on_context_changed`

### Done when

`uv run pytest` (full suite, including integration) is green. `uv run mypy packages/haywire-core/src/` is green. `uv run ruff check .` is green. `grep -r "ContextChangedEvent\|ContextChangeType\|notify_context_changed\|notify_cross_session_context_change" packages/ barn/ tests/ --include="*.py"` returns no results.

---

## Latent-bug-flip checklist (per §11)

The migration intentionally changes behavior for two cases. Test these explicitly:

- [ ] **`LibraryCatalogChanged` is `cross_session=True`.** Today's enable/disable/install in session A does not refresh session B's library browser. After migration: it does. Add an integration test if one doesn't exist; confirm a test that previously passed with local-only behavior now passes with cross-session behavior.
- [ ] **`GraphRemoved` is `cross_session=True`.** Today, removing a graph in session A leaves dangling tabs in session B for the same graph. After migration: session B's tabs close. Add a regression test for this.

If either of these surfaces an *existing* test that was encoding the latent bug (testing local-only behavior on what should be cross-session), update the test to reflect the new correct behavior and call it out in the PR description.

---

## §8 commitment audit

Before merging, verify the §8.6 byte-stable promise:

- [ ] `barn/haybale-core/haybale_core/panels/context_menu/create_node_panel.py:64-70` reads as the §8.3 example (state mutation, signal, reveal — three lines).
- [ ] No panel signature changes — every panel's `poll(cls, context)` and `draw(cls, context, container)` stays as-is. (The only `poll`/`draw` signature change is on `BaseEditor`, where the parameter rename `event` → `signal` is part of step 3.)
- [ ] `context.metadata` still carries the popup-ephemeral keys (`edge_state`, `pending_connection`, `context_menu_screen_pos`, `edge_reconnect_end`, `on_emit_event`) untouched.

---

## Out of scope (do not creep)

The following are tempting during migration but explicitly deferred:

- §8 context-menu scope refactor (Q7D)
- §4.5 dataclass nesting (Q5C)
- Cross-session ordering tightening (§6.5 known weak spot)
- Tightening filter sites that today widen across the LIBRARY_STATE_CHANGED split (§11.2 editorial decision #6)
- Building a `docs/library/` authoring guide (the docstrings from Q5D are sufficient for now)
- True pub/sub on Session (Q8B alternative)

If any of these blocks the migration, raise it for re-design rather than fixing it inline.

---

## PR description checklist

The PR description must include:

- [ ] Cross-link to [context_events_simplification.md](context_events_simplification.md) §11 as the canonical migration mapping
- [ ] Honest scope: ~20 files, ~30 emit-site rewrites, ~8 filter-site rewrites
- [ ] Two latent-bug flips called out explicitly (`LibraryCatalogChanged`, `GraphRemoved`)
- [ ] Q6B emit-site rewrite rule (EDITOR_FOCUSED collapses, real change_types split)
- [ ] §8.6 commitment confirmed (panel signatures unchanged, `context.metadata` untouched)
- [ ] Verification: `pytest`, `ruff check`, `mypy` all clean
