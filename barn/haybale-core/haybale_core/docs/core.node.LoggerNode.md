# Logger

`core:node:LoggerNode` · kind: node

Log a message to the Python logging system at a configurable severity

## Ports

| id | direction | type | description |
|---|---|---|---|
| exec | inlet | core:type:EXEC | Signal for controlling execution flow between nodes |
| prepend | inlet | builtin:type:STRING | Text data |
| message | inlet | builtin:type:STRING | Text data |
| severity | config | builtin:type:STRING | Log level this message is emitted at. |
| done | outlet | core:type:EXEC | Signal for controlling execution flow between nodes |

## Notes

Logs a message through Python's logging system at a configurable severity.

can be configured to log at DEBUG, INFO, WARNING, ERROR, or CRITICAL levels
by setting the `severity` config property. The message is prepended with a user-defined string.
