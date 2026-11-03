# Step Array

`haybale-core:node:StepArrayNode` · kind: node

Goes through an array one item at a time, each time Next runs

## Ports

| id | direction | type | description |
|---|---|---|---|
| `start` | inlet | `haywire-core:type:EXEC` | Reads the array and steps to its first item |
| `next` | inlet | `haywire-core:type:EXEC` | Steps to the next item |
| `stop` | inlet | `haywire-core:type:EXEC` | Forgets the array; Next does nothing until Start |
| `array` | inlet | `haywire-core:type:ADD` | The items to step through |
| `mode` | inlet | `haywire-core:type:STRING` | At the end: once stops, loop starts over, palindrome turns back |
| `item` | outlet | `haywire-core:type:ADD` | The current item |
| `step` | outlet | `haywire-core:type:EXEC` | Runs with each item |
| `index` | outlet | `haywire-core:type:INT` | Position of the current item, from 0 |
| `total` | outlet | `haywire-core:type:INT` | Number of items |
| `completed` | outlet | `haywire-core:type:EXEC` | Signal the array ran out (once) or a round ended (loop, palindrome) |

## Notes

Goes through an array one item at a time, each time `Next` runs.

Unlike Loop Array, which goes through the whole array at once, Step Array moves
on only when told to, so the graph sets the pace: drive `Next` from a Tick Event
whose Tick Emit runs at 0.5 FPS and every item shows for 2 seconds.

- `Start` reads the array, goes to the first item and runs `Step`.
- `Next` goes to the following item and runs `Step`. Before the first `Start`,
  and after the array has run out in `once` mode, it does nothing.
- `Stop` forgets the array; `Next` does nothing until the next `Start`.

`Mode` decides what happens at the end of the array:

- `once`: after the last item, `Next` runs `Completed`.
- `loop`: after the last item comes the first again (0 1 2 0 1 2 …).
- `palindrome`: the items go back and forth, without showing an end twice
  (0 1 2 1 0 1 …).

In `loop` and `palindrome` every return to the first item runs `Completed` and
then `Step`, so `Completed` counts the rounds. An empty array runs `Completed`
at `Start`. `Item` takes the type of the array's items; `Index` is the item's
position in the array and `Total` the array's length.

```text
Begin Play → List Files → Step Array.Start      (Array = Files)
Tick Event → Step Array.Next → Load Image → View Image
```
