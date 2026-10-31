# Loop Array

`haybale-core:node:LoopArrayNode` · kind: node

Runs the loop body once for each item of an array

## Ports

| id | direction | type | description |
|---|---|---|---|
| `execute` | inlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `break_loop` | inlet | `haywire-core:type:EXEC` | Signal to stop loop |
| `array` | inlet | `haywire-core:type:ADD` | Grows a new port from whatever connects to it |
| `on_error` | inlet | `haywire-core:type:STRING` | Text data |
| `progress.main` | config | `haywire-core:type:PROGRESS` |  |
| `item` | outlet | `haywire-core:type:ADD` | Grows a new port from whatever connects to it |
| `failed` | outlet | `haywire-core:type:ADD` | Grows a new port from whatever connects to it |
| `loop_body` | outlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `index` | outlet | `haywire-core:type:INT` | Whole number |
| `total` | outlet | `haywire-core:type:INT` | Whole number |
| `completed` | outlet | `haywire-core:type:EXEC` | Signal the loop completed |
| `stopped` | outlet | `haywire-core:type:EXEC` | Signal if the loop was interrupted and was never completed |

## Settings

| name | bag | default | description |
|---|---|---|---|
| `main` | progress | `PROGRESS(active=False, fraction=None, label='')` |  |

## Notes

Runs the loop body once for each item of an array.

Wire any array into `Array`: `Item` takes the type of its items, so a list of
file paths gives a file path, a list of numbers a number. For each item the loop
sets `Item`, `Index` (from 0) and `Total`.

- `On Error`: when an iteration fails and the graph's *On Exception* setting is
  `branch`, `continue` goes on with the next item and `stop` ends the loop through
  `Stopped`. With `frame` or `run` the loop ends at the first failure, without
  `Completed` or `Stopped`.

When the loop ends, `Failed` lists the items whose iteration failed. `Completed`
runs when every item was gone through, also at once for an empty array;
`Stopped` runs when `Break` (wired from the loop body) or `On Error` = `stop`
ended the loop early. The array is read when the loop starts.

```text
List Files → Loop Array (Array = Files) → Load Image → Save Image
```
