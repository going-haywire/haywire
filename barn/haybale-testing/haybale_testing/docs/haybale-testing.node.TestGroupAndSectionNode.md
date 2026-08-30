# Group And Sections

`haybale-testing:node:TestGroupAndSectionNode` · kind: node

Tests Rendering for Group and Sections

## Ports

| id | direction | type | description |
|---|---|---|---|
| execute | inlet | haybale-core:type:EXEC | Signal for controlling execution flow between nodes |
| sequential_mode | inlet | haywire-core:type:BOOL | Sequential Mode - if multiple callbacks, emit in sequence |
| payload | inlet | haywire-core:type:FLOAT | Decimal numberer |
| mode_switch | config | haybale-core:type:GROUP | Inlet group |
| custom_callback_name | config | haywire-core:type:STRING | Text data |
| exec | outlet | haybale-core:type:EXEC | Signal for controlling execution flow between nodes |

## Notes

Test-only
