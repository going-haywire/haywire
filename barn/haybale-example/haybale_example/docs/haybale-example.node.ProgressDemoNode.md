# Progress Demo

`haybale-example:node:ProgressDemoNode` · kind: node

Simulates slow work and shows its progress on the card: overall, per job, final stage.

## Ports

| id | direction | type | description |
|---|---|---|---|
| `exec` | inlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `jobs` | inlet | `haywire-core:type:INT` | Whole number |
| `steps` | inlet | `haywire-core:type:INT` | Whole number |
| `step_ms` | inlet | `haywire-core:type:FLOAT` | Decimal number |
| `progress.main` | config | `haywire-core:type:PROGRESS` |  |
| `progress.job` | config | `haywire-core:type:PROGRESS` |  |
| `done` | outlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `processed` | outlet | `haywire-core:type:INT` | Whole number |

## Settings

| name | bag | default | description |
|---|---|---|---|
| `main` | progress | `PROGRESS(active=False, fraction=None, label='')` |  |
| `job` | progress | `PROGRESS(active=False, fraction=None, label='')` |  |

## Notes

Simulates slow work and shows its progress on the card.

Trigger `exec` to run. The Progress bar fills as the jobs pass, the Job bar
fills with the steps of the current job, and the closing "finishing" stage
sweeps the Progress bar because its length is unknown. `done` fires when
the run ends and `processed` gives the number of steps run.
