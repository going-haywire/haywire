# Resolve Path

`haybale-core:node:ResolvePathNode` · kind: node

Gives the absolute location of a path on this machine, as text

## Ports

| id | direction | type | description |
|---|---|---|---|
| `path` | inlet | `haywire-core:type:PATH` | A file or folder inside a named volume such as the project folder or `models`. The graph stores the volume and the path within it, so it keeps working on another machine. |
| `resolved` | outlet | `haywire-core:type:STRING` | absolute location of a path on this machine |

## Notes

Gives the absolute location of a path on this machine, as text.

Use it to hand a path to something outside the graph, or to see where a file
is. The result differs between machines, so keep paths as paths inside the
graph. A path wired straight to a text inlet arrives as `volume name:path`
instead, the same on every machine.

The file or folder need not exist. A path whose volume is not defined here,
or that leads outside its volume, is reported as an error.
