---
status: draft
doc_template: system-reference
scope: Volumes — named per-machine roots that graphs reference as (volume key, relative) instead of absolute paths; the volumes file, keys, how libraries add volumes, resolution, escape refusal, the path widget, the Volumes editor and the CLI
see-also:
  - ../settings/settings-arch.md
  - ../../components/states/state-canon.md
  - ../../adr/0065-named-volumes-instead-of-absolute-paths.md
  - ../../reference/glossary.md
---

# Volumes — Architecture

A **volume** is a named root folder. A graph never stores an absolute path: it stores a **volume path**, the pair `(volume key, relative)`, and each machine says where the volume lives. The same graph then runs on another machine once that machine has the volume.

Code: `packages/haywire-core/src/haywire/core/volumes/`.

## The volumes file

`~/.haywire/volumes.toml` is the list of volumes on this machine. Each volume is one table, keyed by its **volume key**:

```toml
[volumes."haybale-models:volume:models"]
label = "Models"
description = "Models on this machine"
location = "/Volumes/Big/models"
suggested = "/Users/me/.haywire/db/haybale_models/models"

[volumes."user:volume:scans"]
label = "Scans"
description = "Scanner drive"
location = "/Volumes/Scans"
```

Everything in an entry except its key can be changed: label, description and location. `location` must be absolute; `label` defaults to the key's name part. `suggested`, on a library's volume only, is the location its library suggests (see below); the library writes it, and a non-absolute one is ignored with a warning.

`VolumeStore` reads and writes the file. It re-reads the file when its modification time or size changes. A write re-reads the file under a per-file lock, applies the change, and replaces the file atomically (a temporary file renamed over it), so libraries adding volumes from several threads at once lose nothing. When reading, a bad entry (an invalid key, a relative location) is logged and skipped. An unreadable file lists only the project volume, and writes to it raise `ValueError` instead of overwriting it. An entry in the older form `[volumes] scans = "/abs"` reads as the user volume `scans` and is rewritten in the table form on the next write.

The ambient store comes from `get_volume_store()`; `set_volume_store()` installs another, which tests use with a store on a temporary path.

The file is not a setting: the app never writes the global settings tier, and workspace `settings.json` is committed with the project, while volumes are per machine.

## Keys

A volume key follows the registry-key pattern `<library-id>:volume:<name>` (`^[a-z][a-z0-9-]*:volume:[a-z][a-z0-9_-]*$`). The prefix says who added the volume:

| Key | Added by |
| --- | --- |
| `haywire-core:volume:project` | built in |
| `haybale-models:volume:models` | the haybale-models library |
| `user:volume:scans` | a user, in the Volumes editor or the CLI (`user_volume_key("scans")`) |

A key never changes once the volume exists; renaming a volume means adding a new one.

## The project volume

`PROJECT_KEY` (`haywire-core:volume:project`) is built in: it is the open project's folder, read from the ambient workspace root on every call so it follows a project switch. It is never stored in the file, and it cannot be changed or deleted. With no project open it has no location. It is the only volume that cannot be changed.

## How a library adds a volume

A library adds its volume from its `AppState.on_enable` with `ensure_volume`:

```python
--8<-- "packages/haywire-core/src/haywire/core/volumes/store.py:ensure-volume"
```

`ensure_volume` adds the entry only when the key is absent, and records its `location` as the entry's `suggested` location, also on an entry that already exists. It never changes a volume's label, description or location once the volume exists, and never creates the folder: the library creates it when it first writes there. It is safe on every enable and hot reload; it writes the file only when something changed.

A library's volume cannot be deleted. `VolumeStore.reset(key)` (the editor's "Reset to suggested location", `haywire volumes reset`) writes `suggested` back to `location` at once, so the volume never disappears while its library depends on it. Only user volumes (`user:volume:…`) can be deleted; the key tells which is which (`is_user_volume_key`). Uninstalling the library leaves its entry in the file.

The suggested location of a library's volume is the library's choice. For model weights the suggestion is `~/.haywire/db/<module>/models`, so a tool that resets a library's data under `~/.haywire/db/` has to leave a `models` folder alone.

## The value

`VolumePath(volume, relative)` is a frozen dataclass; `volume` is the volume key. `relative` is a POSIX-style string (`/` separators) kept **verbatim**: nothing in the class rewrites or validates it. It serializes as `{"volume": ..., "relative": ...}`; a missing volume means the project volume.

An optional third field, `base`, marks the folder a listing started from, a leading part of `relative`. List Files and For Each File set it to their `Folder`; every other node that builds a path leaves it empty. `subpath` is the part of `relative` below `base` (all of `relative` when `base` is empty or not a leading part). `base` takes no part in equality or hashing, and is serialized only when set. Split Path splits a path at its base into `Base`, `Subfolder`, `Name` and `Extension`.

The `PATH`, `FILE_PATH` and `FOLDER_PATH` types (`haywire/barn/builtin/types/path.py`) carry a `VolumePath`. `PATH` leaves the widget `mode` unset (the widget defaults to `file`); `FILE_PATH` and `FOLDER_PATH` preset it to `file` and `folder`. Their default is the project volume with an empty `relative`.

## Resolution

`location_of(key)` returns the volume's root: the open project's folder for the project volume, otherwise the entry's location. A key with no entry, or the project volume with no project open, raises `VolumeUndefinedError`.

`resolve(path)` joins `relative` onto that root and returns the result as configured: a root that is itself a symlink stays as written, and so does a symlink inside the volume that stays inside it. Resolving never creates a folder, and a root that does not exist yet (an unplugged drive, a folder not downloaded yet) still resolves. Code that compares a resolved path with symlink-followed paths (such as `list_files` checking where a linked file leads) follows the root's link itself.

### Escape refusal

`relative` is checked as written. Then each component below the root is looked at with `lstat`, stopping at the first one that does not exist; only when one of them is a symlink are the path and the root followed (`Path.resolve()`) and compared, which catches a symlink leading out. A path with no symlink inside the volume costs a few `lstat` calls and nothing more. `resolve` raises `VolumeEscapeError` when:

- `relative` is absolute, in POSIX form (`/etc`) or with a Windows drive (`C:\x`);
- `relative` has a `..` segment, even one that would stay inside the root (`a/../b`): a volume path names its target directly;
- a symlink inside the volume points outside it (the message names the symlinked component);
- `relative` is not a string, or contains a NUL byte.

A symlink loop or an OS error while resolving raises `VolumeError`. A backslash in `relative` is an ordinary character on POSIX and is not interpreted as a separator.

## Status

`list_volumes()` returns a `VolumeStatus` per volume: `key`, `label`, `description`, `location` (`None` when there is none), `exists` (whether the folder is there), `editable` (`False` only for the project volume) and `suggested` (the location a library volume resets to, `None` when there is none). The project volume comes first, the rest sorted by label.

## Picking a path

`PathWidget` (`haywire/barn/builtin/widgets/path_widget.py`) is the widget for the three path types: a volume select listing volumes by label, a text field for `relative`, and a browse button. The volume list is refreshed each time it opens, so a volume added meanwhile shows up. A value whose volume is not on this machine keeps it, listed under its name. A status line shows where the path points on this machine, cropped in its middle to fit (`hui.fitted_path`), or what is wrong: the volume is not defined here, or its folder is missing. The widget declares `min_width`, so a long path never sets the node's minimum width. The widget has no way to add a volume.

Its `mode` property selects `file` (existing file), `folder`, or `save` (a folder plus a file name typed in the browser). `extensions` filters the files the browser lists. The browser popup is built from the shared folder tree in `haywire/ui/elements/folder_tree.py` (`FolderTreeModel` and `folder_tree`), the same eager-then-lazy tree the file browser editor uses.

## The Volumes editor

`VolumesEditor` (`barn/haybale-studio/haybale_studio/editors/volumes_editor.py`) is an editor with `requires=AccessTier.ADMIN`. It shows one row per volume: the label, and below it the location (or "not defined on this machine") with a missing marker. The location line crops its middle to fit the row (`hui.fitted_path`, `haywire/ui/elements/path_fit.py`: the line carries the path's parts, and a ResizeObserver script writes the longest split of them that fits), with the full path as its tooltip.

A row's button opens the volume's details in a modal. When the session holds `admin`, the modal edits label, description and location (the key is shown, not editable). A user volume offers Delete; a library's volume shows its suggested location and offers "Reset to suggested location" instead (no button when no suggestion is recorded). The project volume, and every volume for a session without `admin`, opens read-only. The header's add button opens an Add modal: a name (the key is `user:volume:<name>`), label, description and location. Writes go through `VolumeStore`; a store error shows in the modal and keeps it open. Locations are typed as absolute server paths, since the browser cannot pick a folder on the server.

## The CLI

`haywire volumes` (`packages/haywire-studio/src/haywire_studio/cli/volumescmd.py`) edits the same file on the server. `set`, `remove` and `reset` take a key, or its name part when exactly one volume has that name. Folders are made absolute against the current directory and never created.

| Command | Effect |
| --- | --- |
| `haywire volumes list` | One line per volume: key, label, location, `(missing)` |
| `haywire volumes add NAME FOLDER [--label L] [--description D]` | Add `user:volume:NAME` |
| `haywire volumes set VOLUME [--location F] [--label L] [--description D]` | Change the given fields |
| `haywire volumes remove VOLUME` | Delete a user volume; exits 1 if there is none or it is a library's |
| `haywire volumes reset VOLUME` | Set a library's volume back to its suggested location |

The CLI runs without a workspace root, so the project volume has no location there.
