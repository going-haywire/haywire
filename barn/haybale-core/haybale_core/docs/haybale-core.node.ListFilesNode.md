# List Files

`haybale-core:node:ListFilesNode` · kind: node

Lists the files in a folder that match the pattern, each time it runs

## Ports

| id | direction | type | description |
|---|---|---|---|
| `execute` | inlet | `haywire-core:type:EXEC` | Lists the folder's files again |
| `folder` | inlet | `haywire-core:type:FOLDER_PATH` | Folder to list |
| `listing.pattern` | config | `haywire-core:type:STRING` | File names to match, such as \*.png<br><br>Separate patterns with ; as in \*.png;\*.jpg<br>\* any characters, <br>? one character, <br>[abc] one of a, b or c<br>Upper and lower case match alike; <br>empty matches every file |
| `next` | outlet | `haywire-core:type:EXEC` | Runs after the files are listed |
| `files` | outlet | `haybale-core:type:ArrayType` | The matching files, in name order |

## Settings

| name | bag | default | description |
|---|---|---|---|
| `pattern` | listing | `'*'` | File names to match, such as \*.png<br><br>Separate patterns with ; as in \*.png;\*.jpg<br>\* any characters, <br>? one character, <br>[abc] one of a, b or c<br>Upper and lower case match alike; <br>empty matches every file |
| `recursive` | listing | `False` | Also list the files of every subfolder |
| `limit` | listing | `0` | Only the first files, in name order; 0 takes all |
| `total` | listing | `0` | Number of files found |

## Notes

Lists the files in a folder that match the pattern, each time it runs.

- `Pattern`: one or more file-name patterns separated by `;`, such as
  `*.png;*.jpg`. Upper and lower case are not told apart; empty matches every file.
- `Subfolders`: also list the files of every subfolder.
- `Limit`: only the first files, in name order; 0 takes all of them.

Pattern shows as a row on the card; the others are in the properties. Promote
one to a row, or to an inlet to drive it from the graph. `Total` can be
promoted to an outlet.

`Files` holds the paths in name order and `Total` how many there are. Each path
remembers `Folder` as its base, so Split Path can give its `Subfolder` below it.
Files and folders whose names start with `.` are skipped, folders reached
through a link are not entered, and a linked file pointing outside the folder
is skipped.

The folder is read again every time `Execute` runs, so files added meanwhile
are found. Go through the list with Loop Array or Step Array:

```text
List Files → Loop Array (Array = Files) → Load Image → Save Image
```

A folder that cannot be listed (its volume is not defined, it does not exist,
or it is a file) is reported as an error.
