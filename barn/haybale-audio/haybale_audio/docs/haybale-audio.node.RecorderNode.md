# Recorder

`haybale-audio:node:RecorderNode` · kind: node

Writes audio blocks to a file

## Ports

| id | direction | type | description |
|---|---|---|---|
| `write` | inlet | `haybale-audio:type:EXEC_AUDIO` | Signal for sequencing the nodes of an audio flow |
| `stop` | inlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `audio` | inlet | `haybale-audio:type:AUDIO` | Block to append |
| `path` | inlet | `haywire-core:type:FILE_PATH` | File to write; its extension picks the format |
| `status` | config | `haywire-core:type:STRING` | Text data |
| `next` | outlet | `haybale-audio:type:EXEC_AUDIO` | Signal for sequencing the nodes of an audio flow |
| `frames` | outlet | `haywire-core:type:INT` | Whole number |

## Notes

Appends each block to a file. The first block opens it and fixes its channel count and sample
rate; a later block that differs is an error. WAV files are written as 32-bit float.

Inputs:
    write: Append the block on `audio` (wire it to an Audio Event's Block Ready)
    stop: Close the file; the next `write` starts a new recording
    audio: The block to append
    path: File to write; its extension picks the format

Outputs:
    next: Control flow after a block is written
    frames: Frames written to the current file
