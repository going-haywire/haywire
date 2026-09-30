# Test Record Emit

`haybale-testing:node:TestRecordEmitNode` · kind: node

Test control node emitting to every dataclass subscription in its pool

## Ports

| id | direction | type | description |
|---|---|---|---|
| execute | inlet | haybale-core:type:EXEC | Signal for controlling execution flow between nodes |
| subscriptions | inlet | haybale-core:type:PooledType | Multi-source aggregation |
| exec | outlet | haybale-core:type:EXEC | Signal for controlling execution flow between nodes |

## Notes

Test-only emitter collecting `TEST_RECORD_CALLBACK` subscriptions in a pooled inlet.
