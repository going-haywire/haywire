# Any Port TestNode

`haybale-testing:node:AnyPortTestNode` · kind: node

## Ports

| id | direction | type | description |
|---|---|---|---|
| any_in_0 | inlet | haywire-core:type:ANY | Undecided until connected; the node retypes the port from the other end |
| any_out_0 | outlet | haywire-core:type:ANY | Undecided until connected; the node retypes the port from the other end |

## Notes

Node whose ANY pins adopt the type of whatever is connected to them.

Starts with one undecided inlet, `any_in_0`, and one undecided outlet,
`any_out_0`. Connecting to either replaces it with a port of the connected
type and appends a fresh ANY slot below, so each side always ends in
exactly one undecided pin.

A resolved pin stays once its edge is gone — unplugging leaves an empty
typed slot the user can reconnect, and removing it for good is a separate
gesture on the pin menu. Slot indices are never reused, so the pins a saved
graph refers to keep their ids.

A connection between two ANY pins is ignored — neither end has a type to
adopt — and both stay undecided.
