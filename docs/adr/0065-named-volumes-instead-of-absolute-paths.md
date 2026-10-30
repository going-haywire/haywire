---
name: named-volumes-instead-of-absolute-paths
description: Graphs store paths as (volume, relative) against named per-machine volumes kept in ~/.haywire/volumes.toml; volumes are declared Surface-style; escapes are refused on the resolved path
status: accepted
see-also: ADR-0016, ADR-0060
level: framework
---

# Named volumes instead of absolute paths

**Context.**

- A node that reads or writes files needs a path. An absolute path in a graph breaks on every other machine and leaks the author's folder layout.
- Large inputs (model weights, footage) live outside the project, on a different drive per machine.
- The global settings tier is never written by the app, and workspace `settings.json` is committed with the project, so neither can hold a per-machine location the UI edits.

**Decision.**

- **D1** A graph stores a **volume path**, `(volume, relative)`, never an absolute path. `relative` is a POSIX-style string kept verbatim; the resolver interprets it and nothing rewrites it.
- **D2** A **volume** is a named root, declared as a `Volume` subclass: registered on import, superseded on hot reload, a name collision between different classes raises (the Surface pattern). Names match `^[a-z][a-z0-9_-]*$`. The framework declares `project` (the ambient workspace root, not configurable, read on every call) and `home`.
- **D3** Where a volume lives on this machine is kept in `~/.haywire/volumes.toml`, not in settings. An entry may name a volume nobody declared.
- **D4** Resolution order: a non-configurable volume's default; else the `volumes.toml` entry; else the declared default; else `VolumeUndefinedError`. Resolving never creates a folder, and a root that does not exist still resolves.
- **D5** Escapes are refused on the **resolved** path: `..`, an absolute `relative` (POSIX or drive-letter), and a symlink inside the volume pointing outside it raise `VolumeEscapeError`.
- **D6** When reading, a malformed volumes file, or an entry with an invalid name or a relative location, is logged and ignored. Writing (`set`, `remove`) raises on a malformed file instead of overwriting it.
- **D7** Volumes are defined in an ADMIN-only Volumes editor and the `haywire volumes` CLI. The path widget picks a volume and a relative path; it cannot define a volume.
- **D8** The concept is called **volume**, not "anchor": "anchor" is the UI attach point of flyouts, popups and pins.

**Considered.**

- *Absolute paths in the graph.* Not portable.
- *Paths relative to the project only.* Cannot reach shared model folders or other drives.
- *Volume locations as a setting.* The app never writes the global tier, and the workspace tier is committed, so a per-machine location would leak into the repository.
- *Defining a volume from inside the path widget.* Spreads an administrative write over every node card; one editor and the CLI keep it behind ADMIN.
- *Naming the concept "anchor".* Collides with the UI term.

**Consequences.**

- A graph moves between machines once each defines the volumes it uses; an undefined volume shows in the widget's status line and raises `VolumeUndefinedError` at resolve time.
- A volume location that is missing (unplugged drive) is a valid location: the widget and editor mark it, and resolving still returns the path.
- Reading a path that crosses an outward symlink fails by design, even when the link target is wanted.
- The `haywire volumes` CLI runs without a workspace, so it cannot show `project`.
