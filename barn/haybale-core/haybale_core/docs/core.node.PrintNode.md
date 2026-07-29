# Print

`core:node:PrintNode` · kind: node

Print to the haywire UI console

## Ports

| id | direction | type | description |
|---|---|---|---|
| exec | inlet | core:type:EXEC | Signal for controlling execution flow between nodes |
| message | inlet | builtin:type:STRING | Text data |
| done | outlet | core:type:EXEC | Signal for controlling execution flow between nodes |

## Notes

Prints a message to the haywire ui console.
