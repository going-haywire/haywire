# Fold

`haybale-testing:node:TestFoldNode` · kind: node

Tests fold rendering

## Ports

| id | direction | type | description |
|---|---|---|---|
| execute | inlet | haybale-core:type:EXEC | Signal for controlling execution flow between nodes |
| in_group_inlet | inlet | haywire-core:type:STRING | Text data |
| sequential_mode | inlet | haywire-core:type:BOOL | Sequential Mode - if multiple callbacks, emit in sequence |
| payload | inlet | haywire-core:type:FLOAT | Decimal numberer |
| custom_name | config | haywire-core:type:BOOL | True or False |
| custom_callback_name | config | haywire-core:type:STRING | Text data |
| custom_pin | config | haywire-core:type:BOOL | True or False |
| exec | outlet | haybale-core:type:EXEC | Signal for controlling execution flow between nodes |

## Notes

Test-only
