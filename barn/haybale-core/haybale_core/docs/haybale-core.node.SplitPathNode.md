# Split Path

`haybale-core:node:SplitPathNode` · kind: node

Splits a path into its volume, base, subfolder, stem and extension

## Ports

| id | direction | type | description |
|---|---|---|---|
| `path` | inlet | `haywire-core:type:PATH` | Path to split |
| `volume` | outlet | `haywire-core:type:FOLDER_PATH` | The volume's root folder: <volume> |
| `base` | outlet | `haywire-core:type:FOLDER_PATH` | The folder the path was listed from: <volume>/<base> |
| `parent` | outlet | `haywire-core:type:FOLDER_PATH` | The folder the file is in: <volume>/<base>/<sub> |
| `base_folder` | outlet | `haywire-core:type:STRING` | <base>, inside the volume |
| `subfolder` | outlet | `haywire-core:type:STRING` | <sub>, inside the base |
| `folder` | outlet | `haywire-core:type:STRING` | <base>/<sub>, inside the volume |
| `stem` | outlet | `haywire-core:type:STRING` | <stem>, the file name without extension |
| `extension` | outlet | `haywire-core:type:STRING` | <ext>, with the dot |
| `name` | outlet | `haywire-core:type:STRING` | <stem><ext>, the file name |
| `base_on_disk` | outlet | `haywire-core:type:STRING` | Where <volume>/<base> is on this machine |
| `parent_on_disk` | outlet | `haywire-core:type:STRING` | Where <volume>/<base>/<sub> is on this machine |
| `path_on_disk` | outlet | `haywire-core:type:STRING` | Where the file is on this machine |

## Notes

Splits a path into its volume, base, subfolder, stem and extension.

A path is read as

```text
<volume>/<base>/<sub>/<stem><ext>
```

`<base>` is the folder a path was listed from: List Files and For Each File
give every path their `Folder` as its base. `<sub>` is the rest of the folder
below it, empty unless `Subfolders` was on. A path typed in by hand has no
base, so `<sub>` is its whole folder.

| Outlet | Kind | Holds |
|---|---|---|
| `Volume` | path | `<volume>` |
| `Base` | path | `<volume>/<base>` |
| `Parent` | path | `<volume>/<base>/<sub>` |
| `Basefolder` | text | `<base>` |
| `Subfolder` | text | `<sub>` |
| `Folder` | text | `<base>/<sub>` |
| `Stem` | text | `<stem>` |
| `Extension` | text | `<ext>`, such as `.png`; empty when there is none |
| `Name` | text | `<stem><ext>` |
| `Base on Disk` | text | where `<volume>/<base>` is on this machine |
| `Parent on Disk` | text | where `<volume>/<base>/<sub>` is on this machine |
| `Path on Disk` | text | where the file is on this machine |

A new node shows `Folder`, `Stem` and `Extension`; show the others from the
Ports panel. Only connected outlets are worked out; connecting one makes the
node run again. The `on Disk` outlets
differ between machines, and are empty when the volume is not defined here.
Nothing is read from disk.

Rebuild a listed file in another folder, keeping its subfolders:

```text
For Each File.Path → Split Path
Split Path.Subfolder → Output Path.Subfolder
Split Path.Stem      → Output Path.Stem        Suffix = "_x4"
Split Path.Extension → Output Path.Extension
```
