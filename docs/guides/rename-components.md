---
status: draft
doc_template: guide
scope: Migrating saved graphs after component classes are renamed, with `haywire rename --map` and a key map
see-also:
  - ./rename-library.md
  - ../reference/glossary.md
  - ../adr/0091-a-release-that-renames-components-migrates-graphs-on-load.md
---

# Renaming components — Author guide

Every saved graph records each component it uses by its **registry key**,
`<dist>:<kind>:<ClassName>` (`haybale-core:node:BeginPlayEventNode`). On load, the
graph loader looks a component up by that key and nothing else. If you rename a
node, type or widget class, its key changes too, so every graph that still holds
the old key stops loading.

**The 0.6 renames migrate on load.** Haywire 0.6 renamed components across
`haywire-core` and the bundled libraries. Their key maps ship inside
`haywire-core` (`haywire/core/renames/0.6/`), and graph file format v6 applies
them to every file saved before 0.6 as it loads: open the graph and it has the
new keys, and it keeps them on its next save. You don't need to run anything
for those renames.

For any other rename, such as your own library's, `haywire rename --map <file>`
migrates the graphs once. Use it too to rewrite files on disk without opening
them in the studio. You write a **key map**
that lists each old key and its new key. The command finds every graph in the
project and rewrites the keys the map lists.

To rename a whole library (its distribution name, not single components), see
[Renaming a library](./rename-library.md). Both modes share the same command,
graph discovery and safety rules.

## 1. The short version

Stop the studio, commit everything, then:

```sh
uv run haywire rename --map renames.toml --dry-run --verbose   # what would change
uv run haywire rename --map renames.toml                       # rewrite the graphs
git diff                                               # review, then commit
```

The map is any TOML file, anywhere on disk. A library that publishes a
release with renamed components can ship its map, and every project that uses
the library runs the same command on its own graphs.

## 2. The key map

```toml
[[rename]]
old = "haybale-core:node:BeginPlayNode"
new = "haybale-core:node:BeginPlayEventNode"

[[rename]]
old = "haybale-core:type:ArrayType"
new = "haybale-core:type:ARRAY"
# Optional, always as a pair: the class's module moved too.
old_module = "haybale_core.types.array_type"
new_module = "haybale_core.types.array"
```

| Field                       | Meaning                                                                                       |
| --------------------------- | --------------------------------------------------------------------------------------------- |
| `old`, `new`                | Whole registry keys. The kind (`node`, `type`, `widget`, `adapter`, …) must stay the same     |
| `old_module`, `new_module`  | Dotted module paths. Set both when the class moved to another module, or leave both out        |

The command refuses a map, and names every problem, when it has an unknown
field, a value that isn't a whole key, an entry whose key doesn't change, an
entry that changes the kind, only one of the two module fields, the same `old`
twice, or a **chain**. A chain is an entry whose `new` is another entry's `old`.
Each key is rewritten once, so a chain wouldn't be followed. Map every old key
straight to its final key.

A key may change its distribution too (`haybale-a:node:X` → `haybale-b:node:X`),
for a component that moved to another library.

## 3. What gets rewritten

| Field                                                | Rewritten when                                                                                           |
| ---------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| `registry_key`, `widget_key`, `chain_adapter_keys`   | The whole value equals an `old` key, at any depth, nested subgraphs included                              |
| The keys of the `declarations` table                 | The key equals an `old` key; if the table already holds the new key too, its own entry wins               |
| `class_name`, `registry_id` beside a renamed `registry_key` | They equal the old class name (a node's `identity`, a port's `kwargs`)                            |
| `module` beside a renamed `registry_key`             | The entry sets `old_module`/`new_module` and the value equals `old_module`                               |

Only whole values match, never part of one. A map entry for
`haybale-image:type:IMAGE_RGB` doesn't touch `haybale-image:type:IMAGE_RGBA`,
and one for `haybale-core:node:BeginPlayNode` doesn't touch
`haybale-testing:node:TestBeginPlayNode`.

`class_name`, `registry_id`, `module` and `label` are descriptive copies: the
loader never reads them back. `class_name` and `registry_id` are rewritten so
that a migrated graph doesn't show stale names.

Two copies can stay stale, and the report doesn't list them:

- **`module`**, when the class moved to another module and the entry has no
  `old_module`/`new_module` pair. Give the pair whenever the module changed.
- **`label`**, the class's default title saved in a node's `identity`, is
  never rewritten. A renamed class with a new label shows its old one until
  you edit the file. A title the user gave the node is stored elsewhere and
  isn't affected.

### Parameterized types

`ArrayType[INT]`, `PooledType[ArrayType[STRING]]` and `OPTIONAL[INT]` save as
the family's own key, with the element in a nested `element_type`:

```json
"recipe": {
  "registry_key": "haybale-core:type:PooledType",
  "element_type": {
    "registry_key": "haybale-core:type:ArrayType",
    "element_type": {"registry_key": "haywire-core:type:INT"}
  }
}
```

So one entry per family covers every parameterization, and one entry per
element type covers it wherever it is nested. The bare `"ArrayType"` you see
in saved graphs is the `class_name`/`registry_id` copy beside the key, which
the entry rewrites too. A saved port `label` such as `"ARRAY[INT]"` is display
text and is left as it is.

### What it does not touch

- **Python sources, tests and docs.** Rename the classes in code yourself first.
  In the haywire repo, run `/check-rename` afterwards for string references the
  IDE missed. The report repeats this.
- **Node ids** such as `BeginPlayNode_ea80758b`. They're opaque, and edges point
  at them.
- **Labels and other text** in a graph.
- **Keys in other fields**, such as a graph's `skin`. When one holds a whole
  `old` key, it appears under **unrecognized occurrences** in the report
  (`--verbose` lists each field path), for you to fix by hand.

## 4. Running it

The rules are the same as for a library rename
([Renaming a library §4](./rename-library.md#4-what-has-to-be-true-before-you-rename)):
the studio is stopped and the whole working tree is clean, so `git checkout .`
undoes the run.

`--dry-run` prints, for each map entry found, how many keys it
rewrites and in how many graphs, then the graph files, the number of
descriptive copies and the unrecognized occurrences. Entries found in no graph
are counted, and `--verbose` lists them. That's normal for a map that covers
more libraries than the project uses.

Without `--dry-run`, the same report is printed and the graphs are rewritten.
There is no confirmation prompt.
Each file keeps its own formatting: every value the map doesn't list stays
byte-identical.

## 5. Confirming the result

```sh
uv run haywire verify
```

`verify` reads the files as they are on disk. A graph saved before 0.6 that
you haven't opened and saved since lists the 0.6 old keys as unresolved,
although it loads with the new ones; `haywire rename --map` with the bundled
maps, or a save from the studio, rewrites the file.

After the run, the graphs hold the new keys, so `verify` passes once the
renamed classes are installed. If you migrate graphs before you rename the
classes, `verify` lists exactly the new keys as unresolved until you do.
