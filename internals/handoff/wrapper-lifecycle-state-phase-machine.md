# Handoff: Unify wrapper lifecycle state into a phase machine

**Status:** deferred design idea (not started)
**Origin:** thermo-nuclear node-architecture review, 2026-06-13. This was finding §3, deferred out of the current implementation pass (which is doing P0/P1 + `base.py` split + `get_*` wrapper removal — see "Not this work" below).

---

## The problem

Three wrapper state classes independently re-implement the same lifecycle-state idea — parallel `error_*` slots, `is_*` phase flags, and hand-maintained `is_valid()` / `get_errors()` / `_clear_errors()` — with **no shared base**:

| Class | File | Phases (is_* flags) | Error slots |
|---|---|---|---|
| `NodeWrapperState` | `packages/haywire-core/src/haywire/core/node/node_wrapper.py:31` | `is_registered`, `is_imported`, `is_instantiated`, `is_initialized`, `is_structural`, `has_test_passed`, `is_executing` | `error_import`, `error_instantiate`, `error_initialize`, `error_structural`, `error_test`, `error_custom`, `error_runtime` (+ dead `error` — being deleted in current pass) |
| `EdgeWrapperState` | `packages/haywire-core/src/haywire/core/edge/edge_wrapper.py:27` | `is_registered`, `is_formally_validated`, `is_built`, `is_structural`, `has_test_passed`, `is_inlet_linked`, `is_outlet_linked`, `is_linked`, `is_executing` | `error_link`, `error_formal`, `error_build`, `error_structural`, `error_test` |
| `EditorWrapperState` | `packages/haywire-core/src/haywire/ui/editor/wrapper.py:34` | `is_imported`, `is_dirty` | `error_import`, `error_instantiate`, `error_runtime` |

Each repeats the same maintenance burden: adding a phase means editing the field list **plus** `get_errors`/`get_error`, `_clear_errors`, and `is_valid` in lockstep. This is the textbook "repeated conditionals signal a missing model."

Note the build pipelines are **linear phase machines** already — e.g. `NodeWrapper.build()` (node_wrapper.py ~283) is a nested `if self._instantiate(): if self._initialize(): if self._structural_validation(): if self._test():` pyramid, and each `_instantiate`/`_initialize`/`_structural_validation`/`_test` method is the *same* try/except → enrich → log → set-flag shape.

## The idea

Extract a shared `WrapperLifecycleState` base (candidate home: `core/registry/` or a new `core/lifecycle/`) that models phases + per-phase errors generically, e.g. an ordered `Phase` enum, a `dict[Phase, HaywireException | None]`, and a `reached: set[Phase]`. Then:

- `is_valid()` → "all build phases reached, none errored"
- `get_errors()` → `[e for e in errors.values() if e]`
- `_clear_errors()` → "drop all except the import/load phase" (the one rule that must survive)
- `build()` pyramid → a phase loop with a single `_run_phase(phase, fn)` helper

## Why it was deferred (the trap)

This is **not** a node-local change. The reviewer's original §3 scoped it as node-only, but the three-state discovery flips that:

- **Node-only re-model is wrong** — it manufactures divergence between three siblings that currently look identical.
- **The correct fix (shared base) is cross-cutting** — spans `core/node`, `core/edge`, and `ui/editor`, each with genuinely different phase sets (edge has `is_built`/`is_linked`/inlet+outlet link phases; editor has only import/instantiate/runtime, no init/structural/test). The base must be **minimal** and let each wrapper declare its own phase set.
- It touches **live error-rendering paths**, especially the editor's `error_runtime` (draw/on_focus/redraw handlers) — see `ui/editor/wrapper.py` runtime capture sites around lines 409, 475, 512, 546, 569.

So it needs its own focused design session, not a rider on the cleanup pass.

## Key constraints to preserve

1. **`error_import` / load-phase errors only clear on hot-reload**, never on a normal rebuild. Currently encoded as a deliberate omission in `_clear_errors` (node_wrapper.py:100, editor wrapper.py:81). Must become an explicit predicate in the base.
2. **Warnings are advisory and do NOT affect `is_valid()`** (ADR 0005). Node uses `list[NodeWarning]`; edge uses `list[str]`. The base must keep warnings orthogonal to validity.
3. **Runtime errors do not invalidate** the wrapper (editor `is_valid()` ignores `error_runtime`; node's `is_valid()` likewise excludes runtime). Best-effort recovery semantics must survive.
4. **External readers exist** — at minimum `ui/editor/wrapper.py` reads node-style fields, and several UI/validation paths read `error_*`/`is_*` directly. Any field-shape change needs a caller sweep (string-based `patch(...)` too — run `/check-rename`).

## Open questions for the design session

- Where does the base live — `core/registry/`, new `core/lifecycle/`, or alongside `lifecycle_event.py`?
- Is `Phase` a single shared enum, or per-wrapper enums over a generic base? (Edge/editor/node phase sets barely overlap — likely per-wrapper.)
- Does `EditorWrapperState` (UI layer) inheriting a `core/` base violate the "no UI imports in core, but UI may import core" boundary? (It's fine — UI depends on core — but confirm direction.)
- Worth an **ADR**? Likely yes: "all wrappers share one lifecycle-state base" is hard-to-reverse, surprising without context, and a real trade-off (uniformity vs. per-wrapper phase divergence). Use `docs/adr/` next sequential number.

## Not this work (the current pass, do not redo)

The in-progress cleanup pass already handles, separately from this idea:
- Deleting dead `NodeWrapperState.error` (bare field), `NodeWrapper.validate()`, `NodeMiddleware`, `NodeMeta`, `NodeBehavior`, `NodeUserMetadata`, `NodeErrorInfo` + `render_error_info`.
- Fixing `inlet`/`set_outlet` → `value`/`out` docstrings.
- Collapsing `_create_executor` arity ladder.
- Splitting `base.py` at the `NodeData`/`BaseNode` seam.
- Removing the four `get_*` port-query wrappers.

This handoff is **only** about the three-way lifecycle-state unification.

## Suggested skills for the next agent

- **`/design`** — this is an architectural change touching class hierarchies and a new shared base; run the structured design interview first.
- **`/inquisition`** — to stress-test the minimal-base boundary against the three divergent phase sets before any code.
- **`/check-rename`** — after any field-shape change, to catch string-based `patch(...)`/citation references the IDE misses.
- **`/haywire-codesanitizer`** or **`/verify`** — full ruff/mypy/pytest gate after the refactor.
