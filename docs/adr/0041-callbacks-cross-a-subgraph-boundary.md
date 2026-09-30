---
name: callbacks-cross-a-subgraph-boundary
description: An immediate interface port relays each write across the card at wiring time, as a reroute does along an edge; reconcile resyncs both sides, execution copies only deferred values, a bare ADD grows any flow, and a graph tree validates under one lock — supersedes ADR 0036's "A callback may not cross the boundary"
status: accepted
see-also: ADR-0036, ADR-0037, ADR-0038, ADR-0039, ADR-0040
level: architectural
---

# Callbacks cross a Subgraph boundary through an immediate relay

**Context.** ADR 0036 refused callback crossings: a boundary node copies values when it executes, a subscription must arrive without anything executing, and a relayed copy would re-key the emitter's pool so that unlinking outside never reached inside. Two later changes removed both reasons. A reroute relays an immediate write at once from its inlet's `on_change` (ADR 0039), and an unlinked inlet shows its own value — for a callback, an empty name the emitter's pool drops (ADR 0040) — so removing any edge on a relay path unsubscribes through the next edge's own key. ADR 0036 also said the growing slot grows an `EXEC` port; it could not, because a bare `ADD` is `FlowType.DATA` and formal validation requires equal flows.

**Decision.**

- *Relay.* Every immediate interface inlet relays each write to its partner at once, from an `on_change` handler (`RELAY_HANDLER`, `hb_relay`) on its own node: the card's inlet writes the Subgraph Input's outlet, the Subgraph Output's inlet writes the card's outlet. The partner is found by id through `subgraph_crossing`, per call, with no cache. Keyed on `is_immediate`, not on `CALLBACK`. A listener is an EVENT node, which a Subgraph may not contain, so inward a subscription reaches an interior emitter, and outward it crosses only on its way through — a reroute, a direct Input-to-Output edge, a nested card.
- *Resync.* `reconcile_interface` — the single funnel where card and interior meet (collapse, re-bind, growth, load, macro reload) — ends by copying every immediate pair once in both directions.
- *One route per value.* The execution-time copy pairs deferred ports only.
- *Growth.* A bare `ADD` accepts an edge of any flow, and the edge takes the other end's flow, so a boundary slot grows data, control and callback ports.
- *Arity.* One subscription per interface port; emitters pool.
- *Defaults.* An immediate interface port takes its type's default, never the interior port's: a listener's default is its own subscription, which would outlive the edge that brought it.
- *Locks.* A Subgraph validates under its host's validation lock, so every batch of a graph tree runs one at a time on any thread, and relay writes nested either way inside a batch are re-entrant.

**Alternatives.** *Keep refusing* — the reasons no longer hold. *Cache the pairs* — needs invalidation on every reconcile, rebuild and reload. *A relay object owned by the definition* — a second relay mechanism beside the reroute's, and field events fire for writes the node never sees. *Serialize `ThreadingTimerScheduler` batches* — `force_immediate_validation()` bypasses schedulers. *Pooled interface ports* — a keyed pool relay, the per-source key problem ADR 0036 described. *Smooth over collapse churn* — a notification hold used by two actions.

**Consequences.**

- Collapse and expand drop the subscription and add it back under the new edge; an emitter reacting to pool changes sees both.
- A second listener outside needs a second interface port, grown inside.
- Allowing a listener inside a Subgraph would need containment to admit EVENT nodes, which ADR 0036's assembly excludes; the outward relay already covers it if that changes.
- EdgeKind (edge-kinds step 5) gets the boundary relay for any immediate kind.
