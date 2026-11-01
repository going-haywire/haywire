---
name: models-are-identified-by-digest
description: A model is named by a file reference (URI plus sha256) or a catalog reference that follows the catalog; the variant comes from the host, not from the graph
status: accepted
see-also: ADR-0065
level: library
---

# Models are identified by digest; catalog references follow the catalog

**Context.**

- A graph that uses a model must run on another machine, with another architecture, GPU or drive layout.
- The same catalog entry ships several variants (format, backend, precision). Which one fits depends on the machine.
- Files get moved, renamed and re-downloaded; a path or a file name does not identify a model.

**Decision.**

- **D1** A **model reference** is either a **file reference** (source URI(s) and, once pinned, a sha256) or a **catalog reference** (`<library-id>:model:<stem>`).
- **D2** Files resolve by sha256 through the index wherever they sit in the models volume; a file reference without a digest resolves by source URI until the user pins it.
- **D3** A catalog reference stores no digest and no variant. It follows the catalog: the file used is the variant that best fits this machine.
- **D4** The variant is chosen from an ordered list of tag sets: the node's `model_preference(port_id)`, else the port's `prefer`, else `[{}]`. A tag a variant lacks is a wildcard.
- **D5** The worker uses the best local match. When a better variant exists but is not downloaded, the node carries a warning and the needs-list offers it.
- **D6** Resolution is offline: no network call on the run path.

**Considered.**

- *A digest pin on every catalog reference.* The pinned file is the wrong one on another architecture.
- *The user's variant choice stored in the graph.* Not portable; the graph would carry one machine's hardware.

**Consequences.**

- A graph with catalog references runs wherever the catalog entry has a fitting variant, and may use different files on different machines.
- Bit-exact reproduction needs a file reference with a digest.
- A catalog edit can change what a graph uses; this is by design.
