---
status: placeholder
doc_template: impl-spec
scope: The Graph as data structure: variables, validation pipeline, graph-nodes, haystacks, serialization
see-also:
  - ../../archive/whitepaper/Haywire_design.md
---

# Graph — Architecture

*This is a placeholder. Content has not yet been written.*

**Template:** `impl-spec` — when filled in, this file will follow the proven shape from `library_state.md`:

1. **Mental model.** What this subsystem is, in one paragraph.
2. **Contract.** Declaration / registration / access / invariants.
3. **Lifecycle.** Creation, hot-reload, ordering, observability.
4. **Boundary.** What this is NOT for.
5. **Examples.** Concrete worked cases.
6. **Open questions.** What remains undecided.

**Scope.** The Graph as data structure: variables, validation pipeline, graph-nodes, haystacks, serialization.

## Source material

When migrating, draw from:

- [Haywire_design.md (whitepaper)](../../archive/whitepaper/Haywire_design.md)

## GraphEntry execution lifecycle

`GraphEntry` separates *assembly* from *starting*:

- `compile() -> CompileResult` — builds the per-entry `Interpreter` and calls
  `load_graph` (which assembles the graph; assembly raises `RuntimeError` on an
  invalid graph). The exception is caught and converted to a `CompileResult`
  verdict (`ok` + optional `error`); a failed compile leaves the entry
  non-executing with `interpreter = None`.
- `start()` — dispatches `BEGIN_PLAY` on the already-compiled interpreter.
- `start_execution() -> CompileResult` — compile then (if `ok`) start; the
  back-compatible combined entry point. Returns the verdict so callers (play
  button, haystack load, autorestart) surface assembly failure rather than
  letting a `RuntimeError` escape.

## Run policy

Each `GraphEntry` owns a `GraphRunSettings` bag (purely local, never
registry-backed) describing *how* it runs within its haystack — currently the
`autorestart` flag. It is persisted under the `[graphs.run]` table of the
haystack TOML (omitted when at defaults; sparse). When a running graph is
auto-stopped by a reassembly-requiring validation change
(`HaystackState._on_entry_validation`) and `autorestart` is set, the entry is
recompiled and restarted — but only if `compile()` reports the rebuilt graph is
viable; otherwise it stays stopped.

## TODO

- [ ] Write content
- [ ] Verify against codebase
- [ ] Archive source files
