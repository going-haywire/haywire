# Clip Queue

`haybale-audio:node:ClipQueueNode` · kind: node

Holds audio clips until a flow takes them, one at a time

## Ports

| id | direction | type | description |
|---|---|---|---|
| `push` | inlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `pop` | inlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `clear` | inlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `clip` | inlet | `haybale-audio:type:AUDIO_CLIP` | The clip to push |
| `status` | config | `haywire-core:type:STRING` | Text data |
| `pushed` | outlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `popped` | outlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `empty` | outlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `cleared` | outlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `clip_out` | outlet | `haybale-audio:type:AUDIO_CLIP` | The clip the last pop took |
| `count` | outlet | `haywire-core:type:INT` | Clips waiting in the queue |

## Settings

| name | bag | default | description |
|---|---|---|---|
| `order` | queue | `'Oldest first'` | Oldest first plays clips in the order they came. Newest first takes the latest clip. Newest only keeps just the latest clip: a Push replaces the one waiting. |
| `max_clips` | queue | `16` | How many clips the queue holds; a Push to a full queue drops the oldest clip. |

## Notes

Holds clips pushed in by one flow until another flow pops them, in the order chosen.

Played one after another through a Clip Player, Clip Player's `On Finish` pops the next clip:

```text
Clip Event → Clip Ready → Clip Queue (Push), Clip → Clip
Clip Player (On Finish) ← Tick Event → Clip Queue (Pop) → Popped → Clip Player (Start)
```

`Pop` on an empty queue continues on `Empty`. The chain needs a first Pop while the player is
idle, such as from a Run Button; after that each clip's end pops the next.

Inputs:
    push: Add the clip on `clip` to the queue
    pop: Take the next clip, by `Order`, onto the `clip` outlet
    clear: Drop every clip in the queue
    clip: The clip to push

Outputs:
    pushed: Control flow after a push
    popped: Control flow after a pop that took a clip
    empty: Control flow after a pop on an empty queue
    cleared: Control flow after a clear
    clip_out: The clip the last pop took
    count: How many clips wait in the queue
