# Subgraph Output

`haywire-core:node:SubgraphOutputNode` · kind: node

Defines the outlets of the Graph-node that owns this Subgraph.

## Ports

| id | direction | type | description |
|---|---|---|---|
| slot_0 | inlet | haywire-core:type:ADD | Grows a new port from whatever connects to it |

## Notes

Carries only **inlets** — the values leaving for the parent graph.

Named for the side it represents on the Graph-node card, not for its own
ports: it is the card's *output* side, so inside the Subgraph it collects
those values in. Each inlet here becomes one outlet on the Graph-node.

Ships carrying only its growing slot. The collapse action stamps the
interface around it, and connecting an interior outlet to the slot grows one
more — so a Subgraph can gain an output at any time.
