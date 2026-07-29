# For Loop

`core:node:ForLoopNode` · kind: node

Iterate with start, end, and step control

## Ports

| id | direction | type | description |
|---|---|---|---|
| execute | inlet | core:type:EXEC | Signal for controlling execution flow between nodes |
| start | inlet | builtin:type:INT | Whole number |
| end | inlet | builtin:type:INT | Whole number |
| step | inlet | builtin:type:INT | Whole number |
| break_loop | inlet | core:type:EXEC | Signal for controlling execution flow between nodes |
| loop_body | outlet | core:type:EXEC | Signal for controlling execution flow between nodes |
| index | outlet | builtin:type:INT | Whole number |
| completed | outlet | core:type:EXEC | Signal for controlling execution flow between nodes |

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
