---
name: framework-caches-are-removable-for-fetched-files
description: Framework caches (torch hub, rembg, Keras, Ultralytics) are cache volumes that haywire otherwise treats read-only; haybale-models may remove a file it fetched for a catalog entry, recorded in fetched.json, and nothing else
status: superseded
see-also: ADR-0065, ADR-0068, ADR-0072, ADR-0074
level: library
---

# Framework caches are removable for the files haybale-models fetched

> **Superseded by [ADR 0074](0074-the-catalog-entry-entitles-remove.md).** A catalog entry now entitles Remove of its files from any volume, the Hugging Face cache included, whoever fetched them; fetch records no longer gate Remove.

**Context.**

- Catalog entries may carry a `cache` address (`torchhub://<file>`), so a fetched file lands where the framework's own loader looks. These folders are shared with every other tool on the machine.
- ADR 0068 D4 makes the Hugging Face cache read-only to haywire: never delete. Applied unchanged to framework caches, a user could fetch a model in the Models editor but never take it back, and a wrong fetch would stay forever.
- Deleting by location is unsafe: a file in a shared cache may have been put there by another tool.

**Decision.**

- **Framework caches are cache volumes**, created on the first fetch into them (ADR 0072), and read-only to haywire with one exception.
- **Exception.** haybale-models may remove a file it fetched into a cache volume for a catalog entry. Every such fetch is recorded in `fetched.json` in the library's storage folder, keyed by volume key and relative path, so a relocated volume keeps its records.
- **Remove is offered only on a catalog row, only for a recorded file.** A file in a cache that was not recorded reads `<label> cache` and has no Remove. The confirmation names every catalog entry and graph using the file and warns that the cache is shared. Remove needs ADMIN, like Fetch.
- **Fetch never overwrites an unrecorded cache file.**
- **The Hugging Face cache stays as ADR 0068 D4 says.** Its files are read-only; it is not filled by a `cache` address.

**Considered.**

- *Never delete in any cache (ADR 0068 unchanged).* Safe, but a user cannot undo a fetch.
- *Delete any file in a cache volume.* Could destroy another tool's files.
- *Infer ownership from the file name or digest.* A file of the same name may come from the framework itself; only a record of our own fetch proves ownership.

**Consequences.**

- Records are state outside the catalog: a file removed or replaced by hand leaves a stale record. A record keeps the file's size; while the file is missing, or its size differs from the record's, the file counts as unrecorded: no Remove, and a fetch does not overwrite it. A record written without a size (before sizes were kept) still counts. A matching record's digest is the file's known digest when a pin is checked.
- A file fetched before records existed, or copied in by hand, is never removable here.
- ADR 0068 is superseded in part: D4 has this exception, for framework cache volumes.
