# For Each File

`haybale-core:node:ForEachFileNode` · kind: node

Runs the loop body once for each file in a folder that matches the pattern

## Ports

| id | direction | type | description |
|---|---|---|---|
| `execute` | inlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `break_loop` | inlet | `haywire-core:type:EXEC` | Signal to stop loop |
| `folder` | inlet | `haywire-core:type:FOLDER_PATH` | A folder inside a named volume such as the project folder or `models`. |
| `pattern` | inlet | `haywire-core:type:STRING` | Text data |
| `recursive` | inlet | `haywire-core:type:BOOL` | True or False |
| `limit` | inlet | `haywire-core:type:INT` | Whole number |
| `on_error` | inlet | `haywire-core:type:STRING` | Text data |
| `progress.main` | config | `haywire-core:type:PROGRESS` |  |
| `loop_body` | outlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `path` | outlet | `haywire-core:type:FILE_PATH` | A file inside a named volume such as the project folder or `models`. |
| `subdir` | outlet | `haywire-core:type:STRING` | Text data |
| `stem` | outlet | `haywire-core:type:STRING` | Text data |
| `extension` | outlet | `haywire-core:type:STRING` | Text data |
| `index` | outlet | `haywire-core:type:INT` | Whole number |
| `total` | outlet | `haywire-core:type:INT` | Whole number |
| `failed` | outlet | `haybale-core:type:ArrayType` | Homogeneous typed array |
| `completed` | outlet | `haywire-core:type:EXEC` | Signal the loop completed |
| `stopped` | outlet | `haywire-core:type:EXEC` | Signal if the loop was interruted and was never completed |

## Settings

| name | bag | default | description |
|---|---|---|---|
| `main` | progress | `PROGRESS(active=False, fraction=None, label='')` |  |

## Notes

Runs the loop body once for each file in a folder that matches the pattern.

- `Pattern`: one or more file-name patterns separated by `;`, such as
  `*.png;*.jpg`. Upper and lower case are not told apart; empty matches every file.
- `Subfolders`: also go through every subfolder.
- `Limit`: only the first files, in name order; 0 takes all of them.
- `On Error`: when an iteration fails and the graph's *On Exception* setting is
  `branch`, `continue` goes on with the next file and `stop` ends the loop through
  `Stopped`. With `frame` or `run` the loop ends at the first failure, without
  `Completed` or `Stopped`.

Files and folders whose names start with `.` are skipped, folders reached
through a link are not entered, and a linked file pointing outside the folder
is skipped. The list of files is taken when the loop starts.

For each file the loop sets `Path`, `Subfolder` (its folder relative to `Folder`,
empty at the top), `Stem` (its name without extension), `Extension` (such as
`.png`), `Index` (from 0) and `Total`. `Path` remembers `Folder` as its base, so
Split Path gives the same `Subfolder`. When the loop ends, `Failed` lists the
files whose iteration failed. `Completed` runs when every file was gone through;
`Stopped` runs when `Break` (wired from the loop body) or `On Error` = `stop`
ended the loop early.

Resume a batch by skipping files whose result is already saved:

```text
For Each File → Path Exists? (Path = Output Path) → Missing → Save
```

A folder that cannot be listed (its volume is not defined, it does not exist,
or it is a file) is reported as an error.
