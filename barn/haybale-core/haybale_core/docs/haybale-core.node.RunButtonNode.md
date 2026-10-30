# Run Button

`haybale-core:node:RunButtonNode` · kind: node

A button on the card that triggers connected Tick Event flows while the graph runs

## Ports

| id | direction | type | description |
|---|---|---|---|
| `start` | inlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `stop` | inlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `callbacks` | inlet | `haybale-core:type:PooledType` | Multi-source aggregation |
| `button.run` | config | `haywire-core:type:BOOL` | Press to trigger the connected flows once |
| `started` | outlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `stopped` | outlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |

## Settings

| name | bag | default | description |
|---|---|---|---|
| `run` | button | `False` | Press to trigger the connected flows once |

## Notes

A button on the card that triggers connected Tick Event flows while the graph runs.

Wire `Begin Play` to `Start`, and the `Listen` outlet of each Tick Event to
`Trigger`. Every press of *Run* then starts each connected Tick Event's flow
once; the Tick Event's *Delta Time* is the time since the previous press.

```text
Begin Play → Start                 Tick Event.Listen → Trigger
                                   Tick Event → For Each File → …
```

The button works from *Start* until *Stop* or until the graph stops. A press
made while the graph is stopped shows as pending and is cleared when the graph
starts again.
