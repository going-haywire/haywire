# Add Port TestNode

`haybale-testing:node:AddPortTestNode` · kind: node

## Ports

| id | direction | type | description |
|---|---|---|---|
| add_in_0 | inlet | haywire-core:type:ADD | Grows a new port from whatever connects to it |
| str_in_0 | inlet | haywire-core:type:ADD | Grows a new port from whatever connects to it |
| add_out_0 | outlet | haywire-core:type:ADD | Grows a new port from whatever connects to it |

## Notes

Node whose ADD pins grow real ports when something connects to them.

Starts with one undecided inlet, `add_in_0`, one undecided outlet,
`add_out_0`, and one decided inlet, `str_in_0`, typed `ADD[TEST_STRING]`.

Connecting to an undecided pin replaces it with a port of the connected
type. Connecting to the decided pin replaces it with a `TEST_STRING` port,
and anything convertible to it may connect — the value arrives converted.
Each side appends a fresh slot below, so it always ends in one open pin.

A resolved pin stays once its edge is gone — unplugging leaves an empty
typed slot the user can reconnect, and removing it for good is a separate
gesture on the pin menu. Slot indices are never reused, so the pins a saved
graph refers to keep their ids.

A connection between two undecided pins is ignored — neither end has a type
to adopt — and both stay undecided.
