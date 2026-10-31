# Split Path

`haybale-core:node:SplitPathNode` · kind: node

Splits a path into its volume, folder, name and extension

## Ports

| id | direction | type | description |
|---|---|---|---|
| `path` | inlet | `haywire-core:type:PATH` | A file or folder inside a named volume such as the project folder or `models`. The graph stores the volume and the path within it, so it keeps working on another machine. |
| `volume` | outlet | `haywire-core:type:FOLDER_PATH` | A folder inside a named volume such as the project folder or `models`. |
| `folder` | outlet | `haywire-core:type:STRING` | Text data |
| `stem` | outlet | `haywire-core:type:STRING` | Text data |
| `extension` | outlet | `haywire-core:type:STRING` | Text data |
| `parent` | outlet | `haywire-core:type:FOLDER_PATH` | A folder inside a named volume such as the project folder or `models`. |

## Notes

Splits a path into its volume, folder, name and extension.

Nothing is read from disk. For `a/b/x.png` in a volume:

- `Volume`: the volume's root folder.
- `Folder`: `a/b`, empty when the file is directly in the volume.
- `Name`: `x`.
- `Extension`: `.png`, including the dot; empty when there is none.
- `Parent`: the folder `a/b` as a folder path.

`Folder`, `Name` and `Extension` fit Output Path's `Subfolder`, `Name` and
`Extension`, so a path can be rebuilt with a changed suffix or in another folder:

```
Split Path.Folder    → Output Path.Subfolder
Split Path.Name      → Output Path.Name        Suffix = "_x4"
Split Path.Extension → Output Path.Extension
```
