# Output Path

`haybale-core:node:OutputPathNode` · kind: node

Builds a file path from a folder, a subfolder, a stem and an extension

## Ports

| id | direction | type | description |
|---|---|---|---|
| `folder` | inlet | `haywire-core:type:FOLDER_PATH` | Folder the file goes in |
| `subdir` | inlet | `haywire-core:type:STRING` | Subfolders below Folder, such as a/b; may be empty |
| `stem` | inlet | `haywire-core:type:STRING` | File name without extension |
| `suffix` | inlet | `haywire-core:type:STRING` | Added after the stem, such as _x4 |
| `extension` | inlet | `haywire-core:type:STRING` | File extension, png or .png; empty for none |
| `path` | outlet | `haywire-core:type:FILE_PATH` | The composed file path |
| `out_folder` | outlet | `haywire-core:type:FOLDER_PATH` | The folder the file goes in, subfolders included |

## Notes

Builds a file path from a folder, a subfolder, a stem and an extension.

The result is `Folder / Subfolder / Stem + Suffix + Extension`, in the same
volume as `Folder`. Nothing is created on disk.

- `Subfolder`: a relative path such as `a/b`; empty puts the file directly in `Folder`.
- `Extension`: `png` and `.png` both work; empty gives a file name without extension.

Fed from For Each File's `Subfolder`, `Stem` and `Extension`, it mirrors the
input folder's structure under another folder:

```
For Each File.Subfolder → Subfolder
For Each File.Stem      → Stem        Suffix = "_x4"
For Each File.Extension → Extension
```

`Folder` is the folder the file goes in. Save Image does not create folders, so
create it first:

```
Output Path.Parent → Create Folder → Save Image
```

The node reports an error naming the part when the stem is empty or contains
`/` or `\`, or when the subfolder is absolute or contains `..`.
