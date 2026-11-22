---
name: a-release-that-renames-components-migrates-graphs-on-load
description: The component renames of a lockstep release ship as key maps in haywire-core, and a new graph file format version applies them to every older file as it loads
status: accepted
see-also: ADR-0076, ADR-0085
level: framework
---

# A release that renames components migrates graphs on load

**Context.**

- Release 0.6 renamed 48 components across `haywire-core` and the bundled libraries (`docs/reference/component-naming.md`). A saved graph names each component by its registry key, so every graph saved before 0.6 holds keys 0.6 no longer registers.
- `haywire rename --map` rewrites graph files on disk from a key map. Every project would have to run it once per bundled map, after upgrading and before opening a graph.
- Every library whose components 0.6 renamed releases in lockstep with core, so a file's format version tells whether it was saved before the renames: every file at format v5 or older was.

**Decision.**

- **Graph file format v6 applies the bundled 0.6 key maps** (`haywire/core/renames/0.6/*.toml`) to the whole document during pre-hydration: `registry_key`, `widget_key` and `chain_adapter_keys` at any depth, the keys of the `declarations` table, and a renamed key's `class_name`, `registry_id` and `module` copies. The file keeps the new keys on its next save.
- **Only whole keys match and the maps hold no chains**, so a v5 file that already holds the new keys passes through unchanged.
- **One implementation.** The key map parser and the graph rewrite live in `haywire.core.renames`; pre-hydration and the `haywire rename` CLI both use them.
- **A later lockstep release that renames components** does the same: its maps under `renames/<release>/` and a format version that applies them.

**Considered.**

- *The CLI only.* Every user runs it once per map, and a graph opened before that fails to load.
- *Runtime key aliases in the registry.* Old keys would live on in files and in the registry forever.

**Consequences.**

- `haywire verify` reads files as they are on disk, so it still reports the old keys of a pre-0.6 graph that was not saved since.
- An external library's own renames are not bundled and still need `haywire rename --map`.
- A malformed bundled map would fail every pre-0.6 load; a test loads all of them and expects no problem.
