# List Files

`haybale-core:node:ListFilesNode` · kind: node

Lists the files in a folder that match the pattern, each time it runs

## Ports

| id | direction | type | description |
|---|---|---|---|
| `execute` | inlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `folder` | inlet | `haywire-core:type:FOLDER_PATH` | A folder inside a named volume such as the project folder or `models`. |
| `pattern` | inlet | `haywire-core:type:STRING` | Text data |
| `recursive` | inlet | `haywire-core:type:BOOL` | True or False |
| `limit` | inlet | `haywire-core:type:INT` | Whole number |
| `next` | outlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `files` | outlet | `haybale-core:type:ArrayType` | Homogeneous typed array |
| `total` | outlet | `haywire-core:type:INT` | Whole number |

## Notes

Lists the files in a folder that match the pattern, each time it runs.

- `Pattern`: one or more file-name patterns separated by `;`, such as
  `*.png;*.jpg`. Upper and lower case are not told apart; empty matches every file.
- `Subfolders`: also list the files of every subfolder.
- `Limit`: only the first files, in name order; 0 takes all of them.

`Files` holds the paths in name order and `Total` how many there are. Files and
folders whose names start with `.` are skipped, folders reached through a link
are not entered, and a linked file pointing outside the folder is skipped.

The folder is read again every time `Execute` runs, so files added meanwhile
are found. Go through the list with Loop Array or Step Array:

```text
List Files → Loop Array (Array = Files) → Load Image → Save Image
```

A folder that cannot be listed (its volume is not defined, it does not exist,
or it is a file) is reported as an error.
