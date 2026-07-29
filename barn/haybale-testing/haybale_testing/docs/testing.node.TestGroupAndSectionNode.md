# Group And Sections

`testing:node:TestGroupAndSectionNode` · kind: node

Tests Rendering for Group and Sections

## Ports

| id | direction | type | description |
|---|---|---|---|
| execute | inlet | core:type:EXEC | Signal for controlling execution flow between nodes |
| sequential_mode | inlet | builtin:type:BOOL | Sequential Mode - if multiple callbacks, emit in sequence |
| payload | inlet | builtin:type:FLOAT | Decimal numberer |
| mode_switch | config | core:type:GROUP | Inlet group |
| custom_callback_name | config | builtin:type:STRING | Text data |
| exec | outlet | core:type:EXEC | Signal for controlling execution flow between nodes |

## Notes

Test-only
