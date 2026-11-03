# Split Path

`haybale-core:node:SplitPathNode` · kind: node

Splits a path into its volume, base, subfolder, stem and extension

## Ports

| id | direction | type | description |
|---|---|---|---|
| `path` | inlet | `haywire-core:type:PATH` | A file or folder inside a named volume such as the project folder or `models`. The graph stores the volume and the path within it, so it keeps working on another machine. |
| `parts.folder` | outlet | `haywire-core:type:STRING` | <base>/<sub>, inside the volume |
| `parts.stem` | outlet | `haywire-core:type:STRING` | <stem>, the file name without extension |
| `parts.extension` | outlet | `haywire-core:type:STRING` | <ext>, with the dot |

## Settings

| name | bag | default | description |
|---|---|---|---|
| `volume` | parts | `{'value': {'volume': '', 'relative': ''}}` | The volume's root folder: <volume> |
| `base` | parts | `{'value': {'volume': '', 'relative': ''}}` | The folder the path was listed from: <volume>/<base> |
| `parent` | parts | `{'value': {'volume': '', 'relative': ''}}` | The folder the file is in: <volume>/<base>/<sub> |
| `base_folder` | parts | `'<promote to evaluate>'` | <base>, inside the volume |
| `subfolder` | parts | `'<promote to evaluate>'` | <sub>, inside the base |
| `folder` | parts | `'<ready>'` | <base>/<sub>, inside the volume |
| `stem` | parts | `'<ready>'` | <stem>, the file name without extension |
| `extension` | parts | `'<ready>'` | <ext>, with the dot |
| `name` | parts | `'<promote to evaluate>'` | <stem><ext>, the file name |
| `base_on_disk` | parts | `'<promote to evaluate>'` | Where <volume>/<base> is on this machine |
| `parent_on_disk` | parts | `'<promote to evaluate>'` | Where <volume>/<base>/<sub> is on this machine |
| `path_on_disk` | parts | `'<promote to evaluate>'` | Where the file is on this machine |

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

Every part is a setting. Promote the ones you need to an outlet, or to a row
on the card to look at them while the graph runs. Only promoted parts are
worked out; the others show `<promote to evaluate>`. A promoted part shows
`<ready>` until the node runs. The graph saves which parts are promoted, never
their values. The parts that are paths can only become
outlets, and show no value in the properties.

| Part | Kind | Holds |
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

`Folder`, `Stem` and `Extension` are outlets on a new node. The `on Disk` parts
differ between machines, and are empty when the volume is not defined here.
Nothing is read from disk.

Rebuild a listed file in another folder, keeping its subfolders:

```text
For Each File.Path → Split Path
Split Path.Subfolder → Output Path.Subfolder
Split Path.Stem      → Output Path.Stem        Suffix = "_x4"
Split Path.Extension → Output Path.Extension
```
