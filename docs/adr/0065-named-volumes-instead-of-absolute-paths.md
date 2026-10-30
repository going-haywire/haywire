---
name: named-volumes-instead-of-absolute-paths
description: Graphs store paths as (volume key, relative); ~/.haywire/volumes.toml is the list of volumes on the machine; libraries add theirs from AppState.on_enable; escapes are refused on the resolved path
status: accepted
see-also: ADR-0016, ADR-0060
level: framework
---

# Named volumes instead of absolute paths

**Context.**

- A node that reads or writes files needs a path. An absolute path in a graph breaks on every other machine and leaks the author's folder layout.
- Large inputs (model weights, footage) live outside the project, on a different drive per machine.
- The global settings tier is never written by the app, and workspace `settings.json` is committed with the project, so neither can hold a per-machine location the UI edits.
- Libraries need volumes of their own (haybale-models needs one for model weights), and a user needs to see who added a volume and to change where it lives.

**Decision.**

- **D1** A graph stores a **volume path**, `(volume key, relative)`, never an absolute path. `relative` is a POSIX-style string kept verbatim; the resolver interprets it and nothing rewrites it.
- **D2** `~/.haywire/volumes.toml` is the **single list** of volumes on this machine: one entry per volume with key, label, description and location. Everything in an entry except the key can be edited.
- **D3** A **volume key** follows the registry-key pattern `<library-id>:volume:<name>`; a volume a user adds is `user:volume:<name>`. A key never changes; renaming means a new volume.
- **D4** The **project volume** (`haywire-core:volume:project`) is built in: the ambient workspace root, read on every call, never stored, never editable. There is no other built-in volume.
- **D5** A library adds its volume from its `AppState.on_enable` with `ensure_volume(key, label, description, location)`, which writes only when the key is absent and never creates the folder. Deleting a library's volume resets it: the library adds it back on its next start. Uninstalling a library leaves its entry as an ordinary volume.
- **D6** Resolution: the project volume → the file entry → `VolumeUndefinedError`. Resolving never creates a folder, and a root that does not exist still resolves.
- **D7** Escapes are refused: any `..` segment in `relative` (even one that stays inside), an absolute `relative` (POSIX or drive-letter), and — checked on the **resolved** path — a symlink inside the volume pointing outside it raise `VolumeEscapeError`.
- **D8** Bad entries are logged and skipped when reading. An unreadable file lists only the project volume; writes raise instead of overwriting it, and `ensure_volume` logs and adds nothing. Writes are serialized per file and replace it atomically.
- **D9** Volumes are edited in an ADMIN-only Volumes editor and the `haywire volumes` CLI. The path widget picks a volume and a relative path; it cannot add a volume. Status carries facts (location, exists, editable), not a source.
- **D10** The suggested location for model weights is `~/.haywire/db/<module>/models`. Any tool that resets library data under `~/.haywire/db/` has to leave a `models` folder alone.
- **D11** The concept is called **volume**, not "anchor": "anchor" is the UI attach point of flyouts, popups and pins.

**Considered.**

- *Absolute paths in the graph.* Not portable.
- *Paths relative to the project only.* Cannot reach shared model folders or other drives.
- *Volume locations as a setting.* The app never writes the global tier, and the workspace tier is committed, so a per-machine location would leak into the repository.
- *Volumes declared as classes in code, with the file holding only location overrides.* Label and description could not be edited, a user-added volume was a second kind of volume, and the UI needed a "source" (declared default, configured, fixed) that read as noise.
- *A `home` volume.* No consumer needs blanket access to the home folder; a user adds a volume for the folder they want.
- *Model weights in a visible folder or the platform data folder.* Kept beside the library's other data; a user can move the volume anywhere.
- *Defining a volume from inside the path widget.* Spreads an administrative write over every node card; one editor and the CLI keep it behind ADMIN.
- *Naming the concept "anchor".* Collides with the UI term.

**Consequences.**

- A graph moves between machines once each has the volumes it uses; a missing volume shows in the widget's status line and raises `VolumeUndefinedError` at resolve time. A user volume is portable by name: adding `scans` on another machine gives the same key.
- A volume location that is missing (unplugged drive) is a valid location: the widget and editor mark it, and resolving still returns the path.
- Reading a path that crosses an outward symlink fails by design, even when the link target is wanted.
- A library's label or description changes do not reach a volume already in the file; the user's file wins.
- The `haywire volumes` CLI runs without a workspace, so the project volume has no location there.
