# Visual Probe

`haybale-testing:node:VisualProbeNode` · kind: node

Test-only: a data node with pins on a drawn-only wire.

## Ports

| id | direction | type | description |
|---|---|---|---|
| note_in | inlet | haybale-testing:type:TEST_VISUAL | Test-only: a text value on a drawn-only wire |
| count_in | inlet | haybale-testing:type:TEST_VISUAL_COUNT | Test-only: a number on a drawn-only wire |
| note_out | outlet | haybale-testing:type:TEST_VISUAL | Test-only: a text value on a drawn-only wire |
| value | outlet | haywire-core:type:FLOAT | Decimal numberer |

## Notes

Data node with `TEST_VISUAL` pins `note_in` and `note_out`, a `TEST_VISUAL_COUNT` inlet `count_in`,
and a float outlet `value`.
