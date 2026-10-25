# Print

`haybale-core:node:PrintNode` · kind: node

Print to the haywire UI console

## Ports

| id | direction | type | description |
|---|---|---|---|
| `exec` | inlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `message` | inlet | `haywire-core:type:STRING` | Text data |
| `done` | outlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |

## Notes

Prints a message to the haywire ui console.
