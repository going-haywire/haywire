---
name: model-sources
description: The files behind one kind of address are found and fetched by a model source. haybale-models owns a fixed set of built-in sources, looked up by address prefix; libraries never register sources
status: accepted
see-also: ADR-0067, ADR-0068, ADR-0071, ADR-0073, ADR-0074
level: library
---

# Model sources

**Context.**

- Addresses (`https://`, `hf://`) were handled by two hard-wired code paths in haybale-models: one HTTPS downloader into the Models volume and one Hugging Face cache lookup. Adding a framework cache (`torchhub://`, `ultralytics://`) would have meant a third and fourth path through the resolver, the queue and the editor.

**Decision.**

- **A model source is the thing behind a prefix.** It declares its prefixes, label and volume, and offers `parse`, `find` (offline, never hashes a whole cache) and `fetch` (progress, cancel; `SourceFailed` means try the next address). `https`/`http` and `hf` are today's code moved behind this shape.
- **The set is fixed and owned by haybale-models.** New locations (`torchhub`, framework caches) become built-ins by need; libraries never register sources. A library with an unusual model location manages its files itself, as haybale-visiongraph does.
- **Lookup is by address prefix**, case-insensitively, the same for a catalog entry and a pasted reference.
- **An unknown prefix is shown, not hidden.** The row reads `source unavailable: <prefix>:// not provided` and the editor offers no Download for it.

**Considered.**

- *Library-registered sources in `on_enable`.* Built in MS1 and dropped: registration across libraries was lost when haybale-models reloaded (a fresh source set, providers' `on_enable` not re-run), the need is rare (MS-Q18), and a library can manage its own files.
- *A component kind with its own registry.* Hot-reload bookkeeping and a global key for something that is a handful of built-ins.
- *A global registry keyed by prefix alone.* Two registrants could claim one prefix, the later silently winning.

**Consequences.**

- Later slices add built-in sources (`torchhub`, framework caches) without touching the resolver or the queue.
- An address with an unknown prefix, `ftp://` included, now fails as "source unavailable" instead of taking the HTTP path.
- The offline lookup follows the order in which a resource lists its addresses.
- A pinned reference rejects a found file only when that file's digest is known and differs from the pin.
- **Amended by MS2 (cache sources).** A model source may be a folder source (`FolderSource`, `TorchHubSource`): a folder of files named by file name, located from environment variables with a home default. `torchhub`, `rembg`, `keras` and `ultralytics` are built in; none adds a dependency. A catalog resource or file may carry `cache`, an address a folder source serves.
- **Cache volumes appear on first need.** `haybale-models:volume:<prefix>` is adopted by a lookup when the framework's suggested folder already exists; a missing folder waits for the first fetch into the cache, which creates it. The fetch creates a folder only at the suggested location: a volume moved to a folder that does not exist fails the job with `<label> cache volume folder does not exist: <path>`.
- **Fetch records.** What haybale-models fetched into a cache volume is kept in `fetched.json`, keyed by volume and relative path; it carries known digests and guards against overwriting; Remove is decided by the catalog entry ([ADR 0074](0074-the-catalog-entry-entitles-remove.md)).
