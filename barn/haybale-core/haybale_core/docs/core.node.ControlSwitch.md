# Control Switch

`core:node:ControlSwitch` · kind: node

Switches control flow based on condition

## Ports

| id | direction | type | description |
|---|---|---|---|
| exec | inlet | core:type:EXEC | Signal for controlling execution flow between nodes |
| compare | inlet | builtin:type:INT | Whole number |
| with | inlet | builtin:type:INT | Whole number |
| DataType | config | builtin:type:STRING |  |
| condition | config | builtin:type:STRING | set form of comparison |
| true | outlet | core:type:EXEC | Signal for controlling execution flow between nodes |
| false | outlet | core:type:EXEC | Signal for controlling execution flow between nodes |
| test | outlet | builtin:type:INT | Whole number |

## Notes

Triggered when execution is switching control flow based on condition.
