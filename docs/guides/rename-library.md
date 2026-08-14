---
status: draft
doc_template: guide
scope: Renaming a project-local haybale library with the `haywire rename` CLI, and confirming the result with `haywire verify`
see-also:
  - ../haybale/haybale-canon.md
  - ./sharing-libraries.md
  - ../reference/files/haybale-toml.md
  - ../reference/glossary.md
---

# Renaming a library — Author guide

A library's distribution name is stamped into every component's registry key
(`haybale-your-lib:node:Resize`) and into every saved graph that uses it.
There is no supported rename path in the studio — `name` is read-only
everywhere — because changing it by hand means editing a name in one place
and leaving thousands of stale key prefixes behind in every graph that
referenced it. `haywire rename` is the one supported way to do this: it finds
every reference across the project and rewrites them together, or tells you
exactly what it can't touch safely.

## 1. The short version

```sh
uv run haywire rename haybale-old-name haybale-new-name --verbose
```

Run without `--apply`, this is a dry run: a full preflight report of what
would change, and nothing is written. When it looks right:

```sh
uv run haywire rename haybale-old-name haybale-new-name --apply
```

You'll be asked to confirm once (twice if the target name doesn't start with
`haybale-` or `hay-` — see [§3](#3-choosing-a-name)). Add `--yes` to skip the
prompts for scripting. When it finishes:

```sh
uv run haywire verify        # confirm every graph's keys still resolve
git diff                     # review what changed
```

then restart the studio to pick up the change.

The most common reason to run this: `haywire init` scaffolds new project
libraries under the `hay-` prefix, which is reserved for local-only work —
you rename off it (to `haybale-your-lib`, conventionally) before publishing
with [`haywire share`](./sharing-libraries.md). See
[haybale-canon §5](../haybale/haybale-canon.md#5-naming-and-versioning) for
the naming convention and why `hay-` exists.

## 2. What gets renamed

Renaming changes a library's **identity only**: its distribution name
(`name` in `haybale.toml`), its Python module directory, and the
registry-key prefix stamped into every saved graph. Everything descriptive —
`label`, `description`, `tags`, `homepage_url`, `notes` — is preserved
byte-for-byte, as is every dependent's own metadata about the library it
still depends on.

Concretely, one run touches:

| What | How |
| --- | --- |
| The library directory | `barn/<old-dist>/` → `barn/<new-dist>/`, and its module subdirectory renamed to match |
| `haybale.toml` | Only `name` changes |
| The library's `pyproject.toml` | `name`, the `haywire.libraries` entry-point key, and the wheel's `packages` list — `description` and everything else untouched |
| The project's `pyproject.toml` | The dependency string and the `[tool.uv.sources]` key, if present |
| `.haywire/marketplace.toml` | The library's own `[[heaps]]` entry, and any *other* heap's `linked_libraries` that names the old module |
| Every saved graph, anywhere in the workspace | Every `registry_key`, `widget_key`, and `chain_adapter_keys` entry belonging to the library; `node_data.library.name`, `.module_name`, `.folder_path`; `node_data.identity.module` |
| Python sources — the library itself, and every sibling that depends on it | `import`/`from` statements naming the old module, and any registry-key string literal a component hardcodes as its own (a widget's `widget_key=` kwarg is the common case) |
| `uv sync` | Run last, to update the lockfile against the new package name |

Graph discovery isn't limited to a `graphs/` folder or a `.haywire`
extension — every graph anywhere in the workspace is found by content, so a
graph checked into `barn/<lib>/<mod>/examples/` or living outside any
particular folder is still found and patched.

### What it deliberately does not touch

- **Prose.** A docstring, comment, or string that merely *mentions* the old
  name — `"""Creates ~/.haywire/db/haybale_old_name/config.toml."""` — is
  reported, never rewritten. The data at that path hasn't moved just because
  the name did; rewriting the literal would make it lie a different way.
- **A path field that doesn't match the expected shape.** `folder_path` is
  only rewritten when its trailing segment is exactly
  `.../<old-dist>/<old-module>` — a path captured on a different machine, or
  moved by something other than this rename, is reported instead of guessed
  at.
- **Persistent storage.** `~/.haywire/db/<old-module>/`, if it exists, is
  reported with the `mv` command to relocate it yourself — it lives outside
  the workspace, so the rename never writes there.

Anything the tool declines to touch shows up in the **unrecognized
occurrences** section of the report (`--verbose` lists every hit; without
it, just the count). This is a drift report, not a failure — it's telling
you what a human still needs to look at.

## 3. Choosing a name

Both names are taken **verbatim** — the old name exactly as it appears in
`barn/`, and the new name exactly as you want it. Nothing is reconstructed
or auto-prefixed on your behalf.

`haybale-` and `hay-` are treated as conventional; a target starting with
either needs no extra confirmation. Anything else — including a bare name,
or one starting with `haywire-` (the framework's own reserved prefix) —
still works, but you're asked to confirm it's not a typo before the rename
proceeds.

Before it runs, the target name is checked against five namespaces it could
collide with, any of which blocks the rename:

1. **The same name** — renaming to what it's already called.
2. **An existing `barn/` directory** at the target name.
3. **A module-name clash** — `haybale-my-lib` and `haybale-My_Lib` both
   normalize to the same importable module (`haybale_my_lib`), so even a
   *different*-looking sibling can collide.
4. **An installed distribution** — the target name is already installed in
   this environment.
5. **A `[[heaps]]` entry** already using that name in
   `.haywire/marketplace.toml` (the project's own local-library list).

A sixth check only warns rather than blocks: if the target name matches a
remote `[[caches]]` row (a marketplace catalog entry, not a local one), the
local library will shadow it — sometimes deliberate, so it's reported and
the rename proceeds.

## 4. What has to be true before you rename

`haywire rename`'s preflight is strictly read-only — it writes nothing,
not even a temp file — so you can run it (without `--apply`) as often as
you like to see what it would do.

**A clean working tree.** `git status --porcelain` must be empty across the
*whole* repository, not just the library being renamed. There is no
`--allow-dirty` escape hatch. This is what makes git the complete rollback:
if the tree is proven clean before anything is written, everything dirty
afterward is provably this run's own work, and `git checkout . && git clean
-fd` restores the start state exactly. If the rename fails partway through —
every phase after the first can fail without corrupting what came before —
the failure message always repeats this exact recovery command.

If your tree is dirty, the report names every changed file and the fix:

```sh
git add -A && git commit -m "wip before rename"
# or
git stash --include-untracked
```

**Write access.** The tool checks that it can actually write everywhere it
plans to — including, for the two directory renames, write access on the
*parent* directory (that's where the rename operation itself happens), not
just the directory being moved.

## 5. Running it

### 5.1 Dry run (the default)

```sh
uv run haywire rename haybale-old-name haybale-new-name --verbose
```

Prints the full preflight report and changes nothing. Without `--verbose`,
each category (library config, Python sources, graphs, dependents) shows a
count; `--verbose` lists every file and, for unrecognized occurrences, every
site.

### 5.2 Applying it

```sh
uv run haywire rename haybale-old-name haybale-new-name --apply
```

Confirmation happens up to twice, unless `--yes` is passed:

1. Only if the target name needs the prefix confirmation from
   [§3](#3-choosing-a-name).
2. Always: a summary of the distribution names, the reference count, and
   that `uv sync` will run — your final "go".

The rename then runs in five phases, each one stopping immediately (with the
recovery hint) if it fails:

1. Rename the module directory.
2. Update the library's own `haybale.toml` and `pyproject.toml`, and rewrite
   its Python sources.
3. Rename the library directory itself.
4. Update the project's `pyproject.toml`, `.haywire/marketplace.toml`,
   every saved graph, and every dependent library's references.
5. Run `uv sync`.

If `uv sync` is the one that fails — the only phase that can leave a message
*without* the `git checkout` recovery hint — the source rename already
completed correctly by that point; the message tells you to fix your
environment and re-run `uv sync` yourself rather than suggesting you discard
good work.

### 5.3 Confirming the result

```sh
uv run haywire verify
```

Resolves every registry key in every graph against the libraries actually
installed — without instantiating a single node, so it never touches
hardware (a camera node's constructor would otherwise open the device) and
never repoints the studio's own live state. Exit code `0` means every graph
resolves; `1` means at least one key is unresolved, with the graph, the key,
and how many times it appears. `--verbose` also lists graphs that passed.

Run it as a separate command, in a separate process from any running studio
— booting the check means loading a full library system, which is exactly
the kind of state-mutating operation that must never happen as a side
effect inside a process someone is actively using.

## 6. Common pitfalls

**The report shows "unrecognized occurrences" I expected to be patched.**
Check what field it's pointing at. If it's inside a saved graph's
`node_data.library.folder_path`, `.module_name`, or `identity.module`, and
the count seems high, re-run with `--verbose` and look at the actual paths —
these are rewritten too as of the current tool, so a leftover there usually
means the value didn't match the expected shape (see
[§2](#what-it-deliberately-does-not-touch)) rather than a gap in the tool.
A prose hit — a comment or docstring mentioning the old name — is expected
and needs a human's judgment call, not the tool's.

**`haywire rename` reports collisions but I don't see the conflicting
library.** Check module-name normalization (§3, item 3) — two differently
*spelled* names can still collide once case and separators are normalized.
The blocker message names the exact sibling it collided with.

**`haywire verify` reports unresolved keys after a successful rename.**
Two likely causes: (1) you haven't restarted the studio / re-run the
process the check depends on picking up the renamed library, since a
booted library system is a snapshot; or (2) the unresolved key genuinely
predates this rename — a stale reference to a library that was removed or
renamed some other way in the past. `haywire verify`'s job is only to
surface these, not to explain their history.

**I want to rename a library that other project libraries depend on.**
This is handled automatically — every sibling library's `linked_libraries`
(in its `haybale.toml`) and any `dependencies` entry (in its
`pyproject.toml`) that names the renamed library are found and rewritten in
the same run, alongside the library's own imports and registry-key
literals. You don't need to rename dependents by hand or run the tool once
per library.

## 7. Reading on

- **Library naming conventions**, and why `hay-` exists as a separate
  namespace:
  [haybale-canon §5](../haybale/haybale-canon.md#5-naming-and-versioning).
- **What happens after a rename, if you're publishing**:
  [sharing-libraries](./sharing-libraries.md).
- **The full `haybale.toml` field reference**, including which fields a
  rename touches and which it never does:
  [reference/files/haybale-toml.md](../reference/files/haybale-toml.md).
- **Vocabulary** — distribution name vs. module name vs. registry key:
  [reference/glossary.md](../reference/glossary.md).
