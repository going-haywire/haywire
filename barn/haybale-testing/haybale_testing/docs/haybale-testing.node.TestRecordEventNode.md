# Test Record Event

`haybale-testing:node:TestRecordEventNode` · kind: node

Test event node whose subscription is a dataclass callback value

## Ports

| id | direction | type | description |
|---|---|---|---|
| subscription | outlet | haybale-testing:type:TEST_RECORD_CALLBACK | Test callback subscription carried as a dataclass |
| triggered | outlet | haybale-core:type:EXEC | Signal for controlling execution flow between nodes |

## Notes

Test-only event node publishing a `TEST_RECORD_CALLBACK` subscription named after itself.
