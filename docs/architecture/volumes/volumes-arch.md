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
location = "/Users/me/.haywire/db/haybale_models/models"

[volumes."user:volume:scans"]
label = "Scans"
description = "Scanner drive"
location = "/Volumes/Scans"
```

Everything in an entry except its key can be changed: label, description and location. `location` must be absolute; `label` defaults to the key's name part.

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

`ensure_volume` writes the entry only when the key is absent. It never changes a volume the user edited and never creates the folder: the library creates it when it first writes there. It is safe on every enable and hot reload. Deleting a library's volume therefore resets it: the library adds it back with its suggested location the next time it starts. Uninstalling the library leaves its entry in the file as an ordinary volume.

The suggested location of a library's volume is the library's choice. For model weights the suggestion is `~/.haywire/db/<module>/models`, so a tool that resets a library's data under `~/.haywire/db/` has to leave a `models` folder alone.

## The value

`VolumePath(volume, relative)` is a frozen dataclass; `volume` is the volume key. `relative` is a POSIX-style string (`/` separators) kept **verbatim**: nothing in the class rewrites or validates it. It serializes as `{"volume": ..., "relative": ...}`; a missing volume means the project volume.

The `PATH`, `FILE_PATH` and `FOLDER_PATH` types (`haywire/barn/builtin/types/path.py`) carry a `VolumePath`. `PATH` leaves the widget `mode` unset (the widget defaults to `file`); `FILE_PATH` and `FOLDER_PATH` preset it to `file` and `folder`. Their default is the project volume with an empty `relative`.

## Resolution

`location_of(key)` returns the volume's root: the open project's folder for the project volume, otherwise the entry's location. A key with no entry, or the project volume with no project open, raises `VolumeUndefinedError`.

`resolve(path)` joins `relative` onto that root and returns the symlink-resolved absolute path. Resolving never creates a folder, and a root that does not exist yet (an unplugged drive, a folder not downloaded yet) still resolves.

### Escape refusal

The check runs on the **resolved** path, so it covers every way out of the root. `resolve` raises `VolumeEscapeError` when:

- `relative` is absolute, in POSIX form (`/etc`) or with a Windows drive (`C:\x`);
- `..` segments lead outside the root;
- a symlink inside the volume points outside it (the message names the symlinked component);
- `relative` is not a string, or contains a NUL byte.

A symlink loop or an OS error while resolving raises `VolumeError`. A backslash in `relative` is an ordinary character on POSIX and is not interpreted as a separator.

## Status

`list_volumes()` returns a `VolumeStatus` per volume: `key`, `label`, `description`, `location` (`None` when there is none), `exists` (whether the folder is there) and `editable` (`False` only for the project volume). The project volume comes first, the rest sorted by label.

## Picking a path

`PathWidget` (`haywire/barn/builtin/widgets/path_widget.py`) is the widget for the three path types: a volume select listing volumes by label, a text field for `relative`, and a browse button. The volume list is refreshed each time it opens, so a volume added meanwhile shows up. A value whose volume is not on this machine keeps it, listed under its name. A status line shows where the path points on this machine, or what is wrong: the volume is not defined here, or its folder is missing. The widget has no way to add a volume.

Its `mode` property selects `file` (existing file), `folder`, or `save` (a folder plus a file name typed in the browser). `extensions` filters the files the browser lists. The browser popup is built from the shared folder tree in `haywire/ui/elements/folder_tree.py` (`FolderTreeModel` and `folder_tree`), the same eager-then-lazy tree the file browser editor uses.

## The Volumes editor

`VolumesEditor` (`barn/haybale-studio/haybale_studio/editors/volumes_editor.py`) is an editor with `requires=AccessTier.ADMIN`. It shows one row per volume: the label, and below it the location (or "not defined on this machine") with a missing marker. The location line crops its middle to fit the row (`hui.fitted_path`, `haywire/ui/elements/path_fit.py`: the line carries the path's parts, and a ResizeObserver script writes the longest split of them that fits), with the full path as its tooltip.

A row's button opens the volume's details in a modal. When the session holds `admin`, the modal edits label, description and location (the key is shown, not editable) and offers Delete; for a library's volume it says that deleting resets it. The project volume, and every volume for a session without `admin`, opens read-only. The header's add button opens an Add modal: a name (the key is `user:volume:<name>`), label, description and location. Writes go through `VolumeStore`; a store error shows in the modal and keeps it open. Locations are typed as absolute server paths, since the browser cannot pick a folder on the server.

## The CLI

`haywire volumes` (`packages/haywire-studio/src/haywire_studio/cli/volumescmd.py`) edits the same file on the server. `set` and `remove` take a key, or its name part when exactly one volume has that name. Folders are made absolute against the current directory and never created.

| Command | Effect |
| --- | --- |
| `haywire volumes list` | One line per volume: key, label, location, `(missing)` |
| `haywire volumes add NAME FOLDER [--label L] [--description D]` | Add `user:volume:NAME` |
| `haywire volumes set VOLUME [--location F] [--label L] [--description D]` | Change the given fields |
| `haywire volumes remove VOLUME` | Delete the volume; exits 1 if there is none |

The CLI runs without a workspace root, so the project volume has no location there.
