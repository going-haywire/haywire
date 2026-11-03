# Path Demo

`haybale-example:node:PathDemoNode` · kind: node

Picks files and folders inside volumes and shows where they are on this machine.

## Ports

| id | direction | type | description |
|---|---|---|---|
| `path` | inlet | `haywire-core:type:PATH` | A file or a folder |
| `file` | inlet | `haywire-core:type:FILE_PATH` | An existing file |
| `image` | inlet | `haywire-core:type:FILE_PATH` | A PNG or JPEG file |
| `folder` | inlet | `haywire-core:type:FOLDER_PATH` | A folder |
| `save_to` | inlet | `haywire-core:type:FILE_PATH` | A file to save to; it need not exist yet |
| `path_resolved` | outlet | `haywire-core:type:STRING` | Where Path is on this machine |
| `file_resolved` | outlet | `haywire-core:type:STRING` | Where File is on this machine |
| `image_resolved` | outlet | `haywire-core:type:STRING` | Where Image is on this machine |
| `folder_resolved` | outlet | `haywire-core:type:STRING` | Where Folder is on this machine |
| `save_to_resolved` | outlet | `haywire-core:type:STRING` | Where Save to is on this machine |
| `problems` | outlet | `haywire-core:type:STRING` | Why an inlet could not be resolved, one line each |

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
