---
name: graph-notices-are-a-library-extensible-store
description: GraphAppState holds notices that any library posts about an open graph; the haystack row shows them as an icon with a count and a popup with each notice's action
status: accepted
see-also: ADR-0067
level: framework
---

# Graph notices are a library-extensible store on GraphAppState

**Context.**

- A library knows things about an open graph that the user should see before pressing play: models missing, a library version differing from the one the graph was saved with.
- The graph manager (haystack) must not know about each library, and haystack is baseline while haybale-models is not.
- Per-card warnings do not cover facts that belong to the whole graph.

**Decision.**

- **D1** `GraphAppState` keeps a notice store per open graph: `post_notice(binding_id, notice)` and `retract_notice(binding_id, key)`. A `GraphNotice` has a key namespaced by its producer, a text, and an optional action with a label and an access tier.
- **D2** Posting under an existing key replaces the notice.
- **D3** `GraphAppState` also offers a zero-argument listener fired when graphs open or close, so a producer can re-walk them.
- **D4** A payload-free cross-session signal, `GraphNoticesChanged`, tells editors to re-read the store.
- **D5** The haystack row shows an icon with the count beside play; its popup lists each notice and its action. The action shows only to sessions that meet `requires`.
- **D6** Play is never disabled by a notice. A dismissable notice is dismissed per editor; the store keeps it.
- **D7** Two producers exist: the models needs-list, and the load-time library compatibility findings.

**Considered.**

- *Haystack depends on haybale-models.* It would make haybale-models baseline.
- *Per-card warnings only.* No place for a fact about the graph as a whole.
- *A notice strip inside the editor.* Takes canvas space and is absent in the haystack's list of graphs.

**Consequences.**

- Any library can tell the user about a graph without the graph manager knowing it.
- Notices are runtime state: they are not saved with the graph and are recomputed when it opens.
