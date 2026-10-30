# Path Demo

`haybale-example:node:PathDemoNode` · kind: node

Picks files and folders inside volumes and shows where they are on this machine.

## Ports

| id | direction | type | description |
|---|---|---|---|
| `path` | inlet | `haywire-core:type:PATH` | A file or folder inside a named volume such as the project folder or `models`. The graph stores the volume and the path within it, so it keeps working on another machine. |
| `file` | inlet | `haywire-core:type:FILE_PATH` | A file inside a named volume such as the project folder or `models`. |
| `image` | inlet | `haywire-core:type:FILE_PATH` | A file inside a named volume such as the project folder or `models`. |
| `folder` | inlet | `haywire-core:type:FOLDER_PATH` | A folder inside a named volume such as the project folder or `models`. |
| `save_to` | inlet | `haywire-core:type:FILE_PATH` | A file inside a named volume such as the project folder or `models`. |
| `path_resolved` | outlet | `haywire-core:type:STRING` | Text data |
| `file_resolved` | outlet | `haywire-core:type:STRING` | Text data |
| `image_resolved` | outlet | `haywire-core:type:STRING` | Text data |
| `folder_resolved` | outlet | `haywire-core:type:STRING` | Text data |
| `save_to_resolved` | outlet | `haywire-core:type:STRING` | Text data |
| `problems` | outlet | `haywire-core:type:STRING` | Text data |

## Notes

Picks files and folders inside volumes and shows where they are on this machine.

Each inlet stores a volume and a path inside it, never an absolute path, so
the graph works on any machine that has the same volumes. Each `… resolved`
outlet gives the absolute path on this machine, or nothing when the path
cannot be resolved; `problems` says why, one line per inlet.

- `Path`: any file or folder.
- `File`: an existing file.
- `Image`: a file, with the browser showing only PNG and JPEG files.
- `Folder`: a folder.
- `Save to`: a folder plus a file name typed in the browser.

Volumes are added and moved in the Volumes editor.
