# Test Print

`testing:node:TestPrintNode` · kind: node

Test version of Logger — logs a message and continues flow

## Ports

| id | direction | type | description |
|---|---|---|---|
| exec | inlet | core:type:EXEC | Signal for controlling execution flow between nodes |
| prepend | inlet | builtin:type:STRING | Text data |
| message | inlet | builtin:type:STRING | Text data |
| done | outlet | core:type:EXEC | Signal for controlling execution flow between nodes |

## Notes

Test-only control node that logs a message.

Mirrors the port shape of ``haybale_core``'s ``LoggerNode``
(``exec`` inlet, ``done`` outlet, ``prepend`` + ``message`` STRING inlets)
so framework execution tests can use a testbed-owned sink instead of
reaching into another library.
