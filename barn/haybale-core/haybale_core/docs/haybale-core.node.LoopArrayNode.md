# Loop Array

`haybale-core:node:LoopArrayNode` · kind: node

Runs the loop body once for each item of an array

## Ports

| id | direction | type | description |
|---|---|---|---|
| `execute` | inlet | `haywire-core:type:EXEC` | Starts the loop over the array |
| `break_loop` | inlet | `haywire-core:type:EXEC` | Ends the loop early, through Stopped |
| `array` | inlet | `haywire-core:type:ADD` | The items to go through |
| `progress.main` | config | `haywire-core:type:PROGRESS` |  |
| `item` | outlet | `haywire-core:type:ADD` | The current item |
| `failed` | outlet | `haywire-core:type:ADD` | Items whose iteration failed |
| `loop_body` | outlet | `haywire-core:type:EXEC` | Runs once per item |
| `index` | outlet | `haywire-core:type:INT` | Position of the current item, from 0 |
| `total` | outlet | `haywire-core:type:INT` | Number of items |
| `completed` | outlet | `haywire-core:type:EXEC` | Runs when every item was gone through |
| `stopped` | outlet | `haywire-core:type:EXEC` | Runs when Break or On Error = stop ended the loop early |

## Settings

| name | bag | default | description |
|---|---|---|---|
| `on_error` | errors | `'continue'` | After a failed iteration: continue with the next one, or stop |
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
