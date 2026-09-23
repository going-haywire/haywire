# Subgraph Input

`haywire-core:node:SubgraphInputNode` · kind: node

Defines the inlets of the Graph-node that owns this Subgraph.

## Ports

| id | direction | type | description |
|---|---|---|---|
| slot_0 | outlet | haywire-core:type:ADD | Grows a new port from whatever connects to it |

## Notes

Carries only **outlets** — the values arriving from the parent graph.

Named for the side it represents on the Graph-node card, not for its own
ports: it is the card's *input* side, so inside the Subgraph it hands those
values out. Each outlet here becomes one inlet on the Graph-node.

Ships carrying only its growing slot. The collapse action stamps the
interface around it, and connecting an interior inlet to the slot grows one
more — so a Subgraph can gain an input at any time.
