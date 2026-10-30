---
status: draft
doc_template: system-reference
scope: Volumes — named per-machine roots that graphs reference as (volume, relative) instead of absolute paths; declaration, volumes.toml, resolution, escape refusal, the path widget, the Volumes editor and the CLI
see-also:
  - ../settings/settings-arch.md
  - ../../adr/0065-named-volumes-instead-of-absolute-paths.md
  - ../../reference/glossary.md
---

# Volumes — Architecture

A **volume** is a named root folder. A graph never stores an absolute path: it stores a **volume path**, the pair `(volume, relative)`, and each machine says where the volume lives. The same graph then runs on another machine once that machine defines the volume.

Code: `packages/haywire-core/src/haywire/core/volumes/`.

## The value

`VolumePath(volume, relative)` is a frozen dataclass. `relative` is a POSIX-style string (`/` separators) kept **verbatim**: nothing in the class rewrites or validates it. It serializes as `{"volume": ..., "relative": ...}`; missing keys default to `project` and an empty string.

The `PATH`, `FILE_PATH` and `FOLDER_PATH` types (`haywire/barn/builtin/types/path.py`) carry a `VolumePath`. `PATH` leaves the widget `mode` unset (the widget defaults to `file`); `FILE_PATH` and `FOLDER_PATH` preset it to `file` and `folder`. Their default is `project` with an empty `relative`.

## Declaring a volume

A volume is a `Volume` subclass. Defining the class registers it by `name` (a name matches `^[a-z][a-z0-9_-]*$`). The registry follows the Surface pattern: registration happens on import, redefining the same module and qualname (hot reload) replaces the earlier class, and a name already held by a class from another module or qualname raises `ValueError`.

| Attribute | Meaning |
| --- | --- |
| `name`, `label`, `description` | Identity and display text |
| `default()` | Location used when `volumes.toml` has no entry; `None` for none |
| `configurable` | Whether `volumes.toml` may override `default()` (default `True`) |

Two volumes are declared by the framework. `project` is the ambient workspace root, read on every call so it follows a project switch, and is not configurable:

```python
--8<-- "packages/haywire-core/src/haywire/core/volumes/volume.py:project-volume"
```

`home` is `Path.home()` and is configurable. A library declares its own volume (for example `models`) by subclassing `Volume`; with no `default()`, the volume stays undefined until `volumes.toml` names it.

## The volumes file

`~/.haywire/volumes.toml` holds the location of each configurable volume on this machine:

```toml
[volumes]
models = "/Volumes/Fast/models"
```

`VolumeStore` reads it, re-reading when the file's modification time or size changes, and writes it through `haywire.core.tomlio`. When reading, a malformed file, an invalid name, or a location that is not absolute is logged and ignored; the rest still applies. `set()` and `remove()` raise the parser's `ValueError` on a malformed file instead of overwriting it. An entry may name a volume nobody declared (a folder an administrator defined outside any library). `set()` raises `ValueError` for an invalid name, a non-configurable volume, or a relative location. The ambient store comes from `get_volume_store()`; `set_volume_store()` installs another one, which tests use with a store on a temporary path.

The file is not a setting: the app never writes the global settings tier, and workspace `settings.json` is committed with the project, while a volume location is per machine.

## Resolution

`location_of(name)` picks the volume's root in this order:

1. A declared volume that is not configurable: its `default()`.
2. The `volumes.toml` entry.
3. The declared volume's `default()`.
4. Otherwise `VolumeUndefinedError`.

`resolve(path)` joins `relative` onto that root and returns the symlink-resolved absolute path. Resolving never creates a folder, and a root that does not exist yet (an unplugged drive, a folder not downloaded yet) still resolves.

### Escape refusal

The check runs on the **resolved** path, so it covers every way out of the root. `resolve` raises `VolumeEscapeError` when:

- `relative` is absolute, in POSIX form (`/etc`) or with a Windows drive (`C:\x`);
- `..` segments lead outside the root;
- a symlink inside the volume points outside it (the message names the symlinked component).

A backslash in `relative` is an ordinary character on POSIX and is not interpreted as a separator.

## Status

`list_volumes()` returns a `VolumeStatus` for every declared or configured volume: `name`, `label`, `description`, `location`, `source` (`configured`, `default`, `fixed` for a non-configurable volume, or `undefined`), `exists`, `declared` and `configurable`. `project` and `home` come first, the rest by name.

## Picking a path

`PathWidget` (`haywire/barn/builtin/widgets/path_widget.py`) is the widget for the three path types: a volume select, a text field for `relative`, and a browse button. A status line shows where the path points on this machine, or what is wrong: the volume is undefined, or its folder is missing. The widget has no way to define a volume.

Its `mode` property selects `file` (existing file), `folder`, or `save` (a folder plus a file name typed in the browser). `extensions` filters the files the browser lists. The browser popup is built from the shared folder tree in `haywire/ui/elements/folder_tree.py` (`FolderTreeModel` and `folder_tree`), the same eager-then-lazy tree the file browser editor uses.

## The Volumes editor

`VolumesEditor` (`barn/haybale-studio/haybale_studio/editors/volumes_editor.py`) is an editor with `requires=AccessTier.ADMIN`. It shows one row per volume, with location, source and a missing marker, and lets an administrator set or remove a location through `VolumeStore`. Locations are typed as absolute server paths, since the browser cannot pick a folder on the server.

## The CLI

`haywire volumes` (`packages/haywire-studio/src/haywire_studio/cli/volumescmd.py`) edits the same file on the server:

| Command | Effect |
| --- | --- |
| `haywire volumes list` | One line per volume: name, source, location, `(missing)` |
| `haywire volumes set NAME FOLDER` | Define a location; a relative `FOLDER` is made absolute against the current directory; the folder is not created |
| `haywire volumes remove NAME` | Delete the entry; exits 1 if there is none |

The CLI runs without a workspace root, so `project` is listed as undefined there.
