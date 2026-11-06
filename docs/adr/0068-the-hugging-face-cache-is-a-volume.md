---
name: the-hugging-face-cache-is-a-volume
description: The Hugging Face cache is the volume haybale-models:volume:hf-cache, shared with other HF tools by default, always passed as cache_dir, never deleted by haywire
status: accepted
see-also: ADR-0065, ADR-0067, ADR-0073, ADR-0074
level: library
---

# The Hugging Face cache is a volume, shared by default, never deleted by haywire

> **Superseded in part by [ADR 0073](0073-framework-caches-are-removable-for-fetched-files.md).** D4 (never delete) now has one exception, for framework cache volumes only: a file haybale-models itself fetched for a catalog entry, recorded in `fetched.json`. [ADR 0074](0074-the-catalog-entry-entitles-remove.md) extends it: a catalog entry entitles Remove of its own files in any cache, the Hugging Face cache included.

**Context.**

- `hf://` model references download through `huggingface_hub`, into a cache that other tools on the machine use too.
- Weights are many gigabytes; a second copy per tool is costly.
- The cache location must be movable like any other large folder (ADR 0065).

**Decision.**

- **D1** The cache is the volume `haybale-models:volume:hf-cache`. Its suggested location is Hugging Face's own resolved default (`$HF_HUB_CACHE`, else `$HF_HOME/hub`, else `~/.cache/huggingface/hub`), written once when the library first enables.
- **D2** Every call passes `cache_dir=` explicitly. haybale-models sets no environment variable.
- **D3** Resolution reads the cache with `try_to_load_from_cache`; only a download uses `hf_hub_download`.
- **D4** Haywire never deletes in the HF cache. The Models editor lists the cached files haywire uses, read-only, as "external"; the Volumes editor shows where the cache lives.
- **D5** `huggingface_hub` is a hard dependency of haybale-models; haywire-core never imports it.

**Considered.**

- *The Hugging Face default, untouched.* Cannot be relocated from the volumes editor.
- *A private haywire cache.* Multi-gigabyte duplicates of what other tools already hold.
- *Plain HTTPS downloads.* No sharing with other tools, and a risk with Xet-backed files.

**Consequences.**

- Other tools and haywire share one copy of each file.
- The volume's location is fixed at first enable; moving it later is the user's act in the Volumes editor, and the old cache stays where it was.
- Freeing HF disk space is done outside haywire.
