# Output Path

`haybale-core:node:OutputPathNode` · kind: node

Builds a file path from a folder, a subfolder, a name and an extension

## Ports

| id | direction | type | description |
|---|---|---|---|
| `folder` | inlet | `haywire-core:type:FOLDER_PATH` | A folder inside a named volume such as the project folder or `models`. |
| `subdir` | inlet | `haywire-core:type:STRING` | Text data |
| `stem` | inlet | `haywire-core:type:STRING` | Text data |
| `suffix` | inlet | `haywire-core:type:STRING` | Text data |
| `extension` | inlet | `haywire-core:type:STRING` | Text data |
| `path` | outlet | `haywire-core:type:FILE_PATH` | A file inside a named volume such as the project folder or `models`. |
| `out_folder` | outlet | `haywire-core:type:FOLDER_PATH` | A folder inside a named volume such as the project folder or `models`. |

## Notes

Builds a file path from a folder, a subfolder, a name and an extension.

The result is `Folder / Subfolder / Name + Suffix + Extension`, in the same
volume as `Folder`. Nothing is created on disk.

- `Subfolder`: a relative path such as `a/b`; empty puts the file directly in `Folder`.
- `Extension`: `png` and `.png` both work; empty gives a name without extension.

Fed from For Each File's `Subfolder`, `Stem` and `Extension`, it mirrors the
input folder's structure under another folder:

```
For Each File.Subfolder → Subfolder
For Each File.Stem      → Name        Suffix = "_x4"
For Each File.Extension → Extension
```

`Folder` is the folder the file goes in. Save Image does not create folders, so
create it first:

```
Output Path.Parent → Create Folder → Save Image
```

The node reports an error naming the part when a name is empty or contains
`/` or `\`, or when the subfolder is absolute or contains `..`.
