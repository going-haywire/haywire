# Control Switch

`haybale-core:node:ControlSwitch` · kind: node

Switches control flow based on condition

## Ports

| id | direction | type | description |
|---|---|---|---|
| exec | inlet | haybale-core:type:EXEC | Signal for controlling execution flow between nodes |
| compare | inlet | haywire-core:type:INT | Whole number |
| with | inlet | haywire-core:type:INT | Whole number |
| DataType | config | haywire-core:type:STRING |  |
| condition | config | haywire-core:type:STRING | set form of comparison |
| true | outlet | haybale-core:type:EXEC | Signal for controlling execution flow between nodes |
| false | outlet | haybale-core:type:EXEC | Signal for controlling execution flow between nodes |
| test | outlet | haywire-core:type:INT | Whole number |

## Notes

Triggered when execution is switching control flow based on condition.
