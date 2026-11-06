---
name: the-catalog-entry-entitles-remove
description: A catalog entry entitles haybale-models to remove that entry's files from any volume that holds them — Models volume, framework caches, Hugging Face cache — whoever fetched them; and Cancel is offered only where a download can really stop
status: accepted
see-also: ADR-0068, ADR-0072, ADR-0073
level: library
---

# The catalog entry entitles Remove; Cancel only where a download stops

**Context.**

- ADR 0073 let haybale-models remove a file from a framework cache only when it had fetched that file itself, proven by a record in `fetched.json`. The Hugging Face cache stayed read-only (ADR 0068 D4).
- In use this left no way to take back a model: a ~1 GB whole-repo snapshot fetched from the Models editor could only be deleted by hand, and a file another tool had put in a cache showed as present but could not be removed, although the same row offered to download it.
- The Models editor drew Cancel on every running download. A Hugging Face download cannot be stopped mid-transfer in-process (`hf_hub_download` blocks; Xet transfers report progress from a Rust thread that swallows exceptions), so Cancel only discarded the result once every byte had arrived.

**Decision.**

- **The catalog entry is the entitlement.** A catalog row whose resource is found offers Remove (ADMIN) for exactly the files that resource resolves to, in whichever volume holds them: the Models volume, a framework cache volume, or the Hugging Face cache. Who fetched the file does not matter: the same row offers to download it again.
- **Remove is a model-source part** (`ModelSource.remove`). A folder source deletes the file and the folders it leaves empty. The `hf` source deletes the snapshot link, and its blob only when no other snapshot of the repo links to it; `refs/` and the cached tree listing stay. Nothing outside the source's volume is ever deleted, through a link or otherwise.
- **The confirmation names every catalog entry and open graph using the files** and, for a cache volume, says the cache is shared with other tools.
- **Fetch records stay** for what they still do: a recorded digest outweighs a file name when a pin is checked, and a fetch never overwrites an unrecorded file. Remove deletes a file's record when there is one and never requires one.
- **Cancel only where it stops.** A model source declares `cancels_running`; `https` does, `hf` does not. A running job takes the flag of the source fetching it; the queue refuses to cancel a running job that cannot stop, and the editor draws Cancel only for queued jobs and running jobs that can stop.

**Considered.**

- *Keep ADR 0073 (fetched files only).* Safe for other tools' files, but a user cannot take back what the catalog offers, and the HF cache is never cleaned.
- *Remove any file in a cache volume.* Rows outside the catalog (the Huggingface section, loose cache files) carry no entitlement: haybale-models does not know they are models.
- *`delete_revisions` for Hugging Face.* Deletes the whole commit, including files another entry or tool fetched for it.
- *Keep Cancel and make it discard after the transfer.* The button would promise something it does not do. A subprocess fetch (MS6) is the way to make `hf` cancellable; it then sets `cancels_running`.

**Consequences.**

- Remove may delete a file another tool put in a shared cache when a catalog entry names it. The confirmation says so; a fetch from the same row restores it.
- ADR 0073 is superseded: the record no longer gates Remove. ADR 0068 D4 (never delete in the Hugging Face cache) is superseded for files a catalog entry resolves to.
- A Hugging Face download, once running, shows no Cancel until MS6.
