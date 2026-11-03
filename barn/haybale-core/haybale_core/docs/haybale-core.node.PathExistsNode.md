# Path Exists?

`haybale-core:node:PathExistsNode` · kind: node

Continues on Exists or Missing, depending on whether a file or folder is there

## Ports

| id | direction | type | description |
|---|---|---|---|
| `exec` | inlet | `haywire-core:type:EXEC` | Checks the path |
| `path` | inlet | `haywire-core:type:PATH` | File or folder to look for |
| `exists` | outlet | `haywire-core:type:EXEC` | Runs when it is there |
| `missing` | outlet | `haywire-core:type:EXEC` | Runs when it is not there |

## Notes

Continues on `Exists` or `Missing`, depending on whether a file or folder is there.

Any file or folder at the path counts as there. A path that cannot be found on
this machine at all, because its volume is not defined or the path leads outside
its volume, is reported as an error.

Resume a batch by skipping files whose result is already saved:

```
For Each File → Path Exists? (Path = Output Path) → Missing → Save
```
