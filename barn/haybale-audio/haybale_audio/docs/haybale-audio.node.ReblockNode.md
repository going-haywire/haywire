# Reblock

`haybale-audio:node:ReblockNode` · kind: node

Re-cuts audio blocks to a fixed size and delivers them to Audio Event nodes

## Ports

| id | direction | type | description |
|---|---|---|---|
| `write` | inlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `audio` | inlet | `haybale-audio:type:AUDIO` | Block to add |
| `callbacks` | inlet | `haybale-core:type:PooledType` | Connect to an Audio Event node. |
| `status` | config | `haywire-core:type:STRING` | Text data |
| `next` | outlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |

## Settings

| name | bag | default | description |
|---|---|---|---|
| `block_size` | reblock | `256` | Samples per delivered block. |

## Notes

Collects the blocks that reach `Write` and delivers blocks of exactly `Block Size` samples to
every Audio Event listening, in order. One input block can give several output blocks or none.

The delivered blocks start a new flow: the Audio Event that receives them is the queue between
the two rates. A change of channel count or sample rate in the input drops the samples still held.

Inputs:
    write: Add the block on `audio`
    audio: The block to add
    callbacks: Pooled CALLBACK_AUDIO subscriptions from Audio Event nodes

Outputs:
    next: Control flow after the block is taken in
