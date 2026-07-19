# Destination & v1 scope

Type: grilling
Status: resolved
Blocked by: —
Resolved: 2026-07-18

## Question

Confirm the destination and draw the v1 scope line for the Haywire MCP server. The map's destination was named autonomously from the original brief; this session validates or redraws it with the user before the other grilling tickets build on it.

To settle, via `/inquisition` + `/domain-modeling`:

- Is the deliverable a spec to hand to `/writing-plans` (current assumption), or should this effort carry further (e.g. into a prototype-backed spec)?
- Which libraries contribute MCP capability in v1 — marketplace, haystack, graph-editor as briefed? Any others (haybale-core node/type introspection)?
- Mutating vs read-only: the brief includes installs, graph saves, node adds, and *creating new node classes in the local library*. Is all of that v1, or is v1 read/query-heavy with mutations staged?
- Is graph **execution control** (compile/start/stop via `GraphEntry`) in scope at all? The brief omits it but the capability exists.
- Who is the expected MCP client (Claude Code against the user's own studio? third-party agents?) — this shapes the safety posture ticket.
- Vocabulary: what do we *call* a library's MCP contribution (candidate terms to test against the glossary's five meanings of "library").

## Answer

Grilled 2026-07-18 (six questions, all confirmed by the user):

1. **Problem/client — copilot first, headless later.** v1 targets an AI agent (Claude Code/Desktop-style, trusted local user) connected to the user's *live* studio; changes appear in the open browser session. The spec keeps a headless-host door open (engine already hints at it via `HostStore.in_memory()`) but does not design it.
2. **Contributing libraries — the three briefed plus a framework-owned baseline.** haybale-marketplace, haybale-haystack, haybale-graph-editor contribute per the brief. The Farmhand host itself additionally ships built-in orientation tools (list enabled libraries, studio status/version) that exist on a bare studio and act as the contribution API's reference implementation.
3. **Mutation scope — full brief in v1, node authoring included.** Install libraries, create/save graphs, add/connect nodes, AND generate new node classes into the project-local barn library. Risk is addressed by guardrails (tickets 06 & 08), not by scoping down.
4. **Execution control — in scope, v1.** compile / start / stop via `GraphEntry`, closing the agent's build→verify loop. Feeds ticket 07's haystack tool surface.
5. **Deliverable — spec, validated by one prototype, then hand off.** Decision tickets + the mount prototype (ticket 09) fold into `spec.md`; implementation is a separate effort via `/writing-plans`.
6. **Vocabulary — the subsystem is named "Farmhand"; contributions are plain "MCP tools".** Whether Farmhand ships as its own `haybale-farmhand` package or as a first-degree citizen of haywire is decided later by the architectural complexity found in tickets 04/05. Recorded in `docs/reference/glossary.md` (new "Farmhand — MCP server" section, marked planned).

Map updates from this resolution: destination now names Farmhand; "graph execution control" and "core-vs-studio placement" fog entries cleared (owned by tickets 07 and 04 respectively); packaging constraint folded into ticket 04; baseline tools folded into ticket 07.
