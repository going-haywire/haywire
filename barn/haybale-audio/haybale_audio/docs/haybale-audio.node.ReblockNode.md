# Reblock

`haybale-audio:node:ReblockNode` · kind: node

Re-cuts audio blocks to a fixed size and delivers them to Audio Event nodes

## Ports

| id | direction | type | description |
|---|---|---|---|
| `write` | inlet | `haybale-audio:type:EXEC_AUDIO` | Signal for sequencing the nodes of an audio flow |
| `audio` | inlet | `haybale-audio:type:AUDIO` | Block to add |
| `callbacks` | inlet | `haybale-core:type:PooledType` | Connect to an Audio Event node. |
| `status` | config | `haywire-core:type:STRING` | Text data |
| `next` | outlet | `haybale-audio:type:EXEC_AUDIO` | Signal for sequencing the nodes of an audio flow |

## Settings

| name | bag | default | description |
|---|---|---|---|
| `block_size` | reblock | `256` | Samples per delivered block. |

## Notes

Collects the blocks that reach `Write` and delivers blocks of exactly `Block Size` samples to
every Audio Event listening, in order. One input block can give several output blocks or none.

The delivered blocks start a new flow: the Audio Event that receives them is the queue between
the two rates. A change of channel count or sample rate in the input drops the samples still held.

Use cases:

- Give a node the block size it wants. A microphone may deliver 1024 samples at a time, a
  speech model may want 512 and an OMT send wants 256 or more. Put a Reblock in front of the node
  that cares and set `Block Size` to what it needs.
- Re-cut after a Resample. A Resample changes the size of its blocks with the rate (441
  samples at 44.1 kHz become about 480 at 48 kHz). A Reblock behind it restores a fixed size.
- Change the pace of a flow. 256 samples at 48 kHz is 187 events per second; 1024 is 47. A
  flow that does more work per block can run on the larger ones.

```text
File Player → Audio Event → Resample (16000) → Audio Event → Reblock (512) → Audio Event → …
```

A Reblock adds delay: samples wait until a whole block has collected, up to one block of the size
it delivers. An Audio Mixer and a Device Out take any block size, so neither needs one in front.

Inputs:
    write: Add the block on `audio`
    audio: The block to add
    callbacks: Pooled CALLBACK_AUDIO subscriptions from Audio Event nodes

Outputs:
    next: Control flow after the block is taken in
