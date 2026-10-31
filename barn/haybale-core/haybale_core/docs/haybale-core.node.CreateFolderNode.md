# Create Folder

`haybale-core:node:CreateFolderNode` · kind: node

Creates a folder inside a volume, including any folders above it

## Ports

| id | direction | type | description |
|---|---|---|---|
| `exec` | inlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `path` | inlet | `haywire-core:type:FOLDER_PATH` | A folder inside a named volume such as the project folder or `models`. |
| `next` | outlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `folder` | outlet | `haywire-core:type:FOLDER_PATH` | A folder inside a named volume such as the project folder or `models`. |

## Notes

Creates a folder inside a volume, including any folders above it.

A folder that already exists is left as it is. `Folder` passes `Path` on, so
the next node can use it.

The volume's own location must already exist: a volume whose drive is not
mounted is reported as an error and nothing is created. An error is also
reported when the path leads outside its volume or a file is in the way.

Save Image does not create folders; create the output folder first:

```
Output Path.Folder → Create Folder → Save Image
```
