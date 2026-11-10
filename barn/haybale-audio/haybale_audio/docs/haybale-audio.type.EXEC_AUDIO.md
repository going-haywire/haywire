# Audio Execution Signal

`haybale-audio:type:EXEC_AUDIO` · kind: type

Signal for sequencing the nodes of an audio flow

## Details

- **wire_type**: `haywire-core:wire:ControlWire`
- **default**: `{'value': {}}`
- **color**: `#3f96b8`

## Notes

The execution signal between the nodes of an audio flow, everything after an Audio Event.

It is an `EXEC` that only audio nodes accept. An `EXEC_AUDIO` outlet connects to `EXEC_AUDIO`
and to `EXEC` inlets; a plain `EXEC` outlet does not connect to an `EXEC_AUDIO` inlet. An audio
flow can therefore drive a standard control node, and a standard control node cannot drive an
audio flow. Starting and stopping audio nodes stays with plain `EXEC`.

A control node driven from an audio flow runs inside the flow's pass, so its time counts against
the block period.
