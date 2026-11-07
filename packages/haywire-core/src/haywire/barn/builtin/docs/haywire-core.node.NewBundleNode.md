# New Bundle

`haywire-core:node:NewBundleNode` · kind: node

Starts an empty bundle, for Metadata nodes to stamp values on

## Ports

| id | direction | type | description |
|---|---|---|---|
| `bundle` | outlet | `haywire-core:type:BUNDLE` | A bundle with no fields |

## Notes

Starts an empty bundle.

Wire it into a **Metadata** node and stamp values on it, to make several values
travel together on one wire.
