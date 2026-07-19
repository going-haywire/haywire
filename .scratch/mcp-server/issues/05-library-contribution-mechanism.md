# Library contribution mechanism

Type: grilling
Status: resolved
Blocked by: 04
Resolved: 2026-07-19

## Question

How does a haybale library declare and register its MCP capability so that enabling the library adds tools and disabling removes them?

The existing pattern is `BaseLibrary.register_components()` + `add_folder_to_registry(folder, registry_cls)` into typed registries. Candidate shapes to grill (this is exactly the registration-path decision CLAUDE.md forbids assuming):

- A new typed registry (e.g. an MCP tool/contribution registry) scanned from a conventional folder (`mcp/`), symmetric with `NodeRegistry` et al., with the MCP host subscribing to registry add/remove events to drive `tools/list_changed`.
- A hook method on `BaseLibrary` (like `on_library_enable`) returning tool definitions.
- Entry-point/decorator-based declaration on the `@library` decorator.

Must also settle:

- Tool naming/namespacing per library (collision rules, e.g. `haystack.save_graph`).
- How contributed tools resolve services — ambient DI context (`get_library_state_container()` et al.) vs injected handles.
- Hot-reload: what happens to registered tools when the file-watcher reloads a library module, and on marketplace install/uninstall mid-session (`LibraryManager` evictions).
- Whether the mechanism lives in haywire-core (any host can serve MCP) or the studio, consistent with ticket 04's outcome.

Run with `/design`; record the settled shape as the ticket answer.

## Answer

Grilled 2026-07-19 via /design (registry machinery read first — DI providers, `add_class_registry` wiring at `di/config.py:373-382`, lifecycle-event consumer pattern — assumptions confirmed) + /inquisition; all seven forks user-confirmed:

1. **Mechanism: a new typed class registry in haywire-core** (working names `FarmhandToolRegistry` / `FarmhandTool`; kind constant `mcp`), provided as a DI singleton and linked via `add_class_registry` like the nine existing registries. Libraries contribute via `self.add_folder_to_registry(str(base_path / "mcp"), registry_cls=FarmhandToolRegistry)` in `register_components()`. Tools are thereby a new **Component** kind with registry keys `{lib_id}:mcp:{name}`, inheriting folder-scan, hot-reload, enable/disable eviction, and lifecycle events for free. Spec note: `mcp/` slots into the canonical scan order after `state/` (tools may reference library states). Rejected: hook-method and decorator declaration (both would re-invent the change feed the registry provides).
2. **Unit: one class per tool** — a `FarmhandTool` subclass with declarative metadata + one `async run(ctx, ...)` handler. Preserves per-tool lifecycle events, per-file hot-reload, and one-key-one-tool.
3. **Input schema: derived from the `run()` signature** (type hints + defaults → JSON Schema — the established node-`worker()` signature-analysis idiom, `node/base.py:178-231`), with an optional class-attribute override for constraints hints can't express. Rejected: hand-written schema dicts (drift risk), attrs params classes (second class per tool).
4. **Naming: MCP-visible name = `{lib_id}_{name}`** (e.g. `haystack_save_graph`, shown by Claude Code as `mcp__farmhand__haystack_save_graph`). Collision-proof by construction (`lib_id` uniqueness is registry-enforced); `studio` is a **reserved prefix** for host-owned baseline tools that no library id may claim (enforced at registration). Rejected: dot-join (unverified client charset tolerance), flat names (registration-order collisions).
5. **Handler context: a `FarmhandContext` passed to every `run()`** — typed accessors for state container/registries (wrapping ambient DI getters), `broadcast(signal)` (signal emission is caller-owned per inventory gap 5), `offload(fn)` (handlers share the NiceGUI asyncio loop in-process, so blocking work must be thread-offloaded — the affinity hazard inverts), MCP progress bridging (for `on_output` streaming installs) and cancellation. Turns the ADR-0002/gap-5 conventions into methods; future enforcement point for ticket 06's guardrails.
6. **Change pipeline: single path.** The studio host subscribes to the registry's `CLASS_ADDED`/`CLASS_REMOVED` lifecycle events (the `LibraryStateContainer` consumer pattern); on added → wrap as SDK tool, `add_tool`, `send_tool_list_changed()` per live session from Farmhand's session registry; on removed → inverse. Enable/disable/hot-reload/install/uninstall all already flow through registry events — one subscription, one tested path. **Baseline tools register through the same registry** (studio host, `studio` prefix, at startup) and are thereby the mechanism's reference implementation (per tickets 01/04).

Map updates: tool-schema-versioning fog folded into ticket 07 (signature-derived schemas + per-session re-fetch make it a surface convention, not an effort); glossary MCP-tool entry updated; ticket 10 (testing strategy) unblocked.
