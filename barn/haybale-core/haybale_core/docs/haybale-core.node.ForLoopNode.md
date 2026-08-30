# For Loop

`haybale-core:node:ForLoopNode` · kind: node

Iterate with start, end, and step control

## Ports

| id | direction | type | description |
|---|---|---|---|
| execute | inlet | haybale-core:type:EXEC | Signal for controlling execution flow between nodes |
| start | inlet | haywire-core:type:INT | Whole number |
| end | inlet | haywire-core:type:INT | Whole number |
| step | inlet | haywire-core:type:INT | Whole number |
| break_loop | inlet | haybale-core:type:EXEC | Signal for controlling execution flow between nodes |
| loop_body | outlet | haybale-core:type:EXEC | Signal for controlling execution flow between nodes |
| index | outlet | haywire-core:type:INT | Whole number |
| completed | outlet | haybale-core:type:EXEC | Signal for controlling execution flow between nodes |

## Notes

Standard for-loop iteration node.

Executes loop body from start index to end index with specified step.

Inputs:
    execute: Start loop execution
    start: Starting index (inclusive)
    end: Ending index (exclusive)
    step: Increment per iteration
    break_loop: Control inlet to break out of loop

Outputs:
    loop_body: Execute on each iteration
    index: Current iteration index
    completed: Execute when loop finishes
