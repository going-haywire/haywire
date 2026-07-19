# Final spec assembly

Type: task
Status: resolved
Blocked by: 08, 09, 10
Resolved: 2026-07-19
Asset: [spec.md](../spec.md)

## Question

Fold every resolved decision on this map into the destination artifact: `.scratch/mcp-server/spec.md`, ready for `/writing-plans`.

Graduated from fog once all decision tickets existed (ticket 07 closed the set). AFK task — no new decisions; if assembly surfaces a contradiction between resolved tickets, stop and open a grilling ticket instead of resolving it silently.

Assembly inputs (zoom each ticket's Answer; the map's Decisions-so-far is the index):

- Scope & vocabulary: Destination & v1 scope (01) + glossary's Farmhand section.
- Facts & citations: the two research assets (`assets/mcp-sdk-research.md`, `assets/wrappable-operations-inventory.md`) — cite, don't restate.
- Architecture: Process & transport model (04), Library contribution mechanism (05), Session/concurrency/safety (06).
- Surface: v1 tool surface (07) — its tables paste in directly; Node authoring via MCP (08).
- Validation & verification: mount prototype findings (09), Testing strategy (10).

Spec must also carry, explicitly: the two mandated core work items (undoable `set_property` Editor primitive; canon packaging into the wheel), the later-work notes (promotion undo-routing, haystack-file tools, offline file-format reads, prompts, Claude Desktop bridge, fall-2026 SDK v2 / 2026-07-28 spec re-evaluation), and the v1 non-goals from Out of scope / deferrals.

Resolution = spec.md written and linked; close this ticket and the map is complete.

## Answer

Assembled 2026-07-19: [spec.md](../spec.md) — nine sections folding all ten resolutions: scope (01), architecture with the prototype-proven runner-task lifespan (04+09), contribution mechanism (05), session/concurrency/safety model (06), the full 34-tool surface with resources and conventions (07+08), the three mandated core work items (set_property primitive, canon packaging, error ledger), the nine-row testing contract (10), later-work register, and non-goals. Research assets cited, not restated.

Contradiction check during assembly: clean. The single supersession — ticket 02's AsyncExitStack lifespan recipe replaced by ticket 09's single-runner-task pattern — is explicit in spec §2 and was a documented prototype finding, not a silent conflict.

The map is complete: no open tickets, no fog. Handoff: `/writing-plans` against spec.md.
